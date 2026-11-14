"""The desktop shell, built and driven (spec 3 "Service rules", Desktop shell; AKS-142).

Marker ``desktop``: excluded from ``bash scripts/check.sh`` as ``perf`` is, run with
``pytest -m desktop`` and by the CI job ``desktop``. It needs, on Linux:

- the built shell, ``cd desktop && npm ci && npm run build``
  (``desktop/src-tauri/target/release/ithax-desktop``, or ``ITHAX_DESKTOP_APP``);
- the built interface, ``cd ui && npm run build`` (``ui/dist``);
- ``tauri-driver`` (``cargo install tauri-driver --version 2.1.0 --locked``) and
  ``WebKitWebDriver`` (Debian and Ubuntu package ``webkit2gtk-driver``);
- ``Xvfb`` (package ``xvfb``), which the test starts on a free display.

The test drives the shell through ``tauri-driver`` with plain WebDriver calls (``http.client``),
against a real service the shell starts through the launcher, with this Python.
"""

import contextlib
import http.client
import http.server
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ithax.service.discovery import SERVICE_FILE, probe, read_service_file

pytestmark = [
    pytest.mark.desktop,
    pytest.mark.skipif(sys.platform != "linux", reason="the desktop shell is tested on Linux"),
]

ROOT = Path(__file__).resolve().parents[2]
# Also read under its old name, LCSIM_DESKTOP_APP, for one release (#70).
APP = Path(
    os.environ.get("ITHAX_DESKTOP_APP")
    or os.environ.get("LCSIM_DESKTOP_APP")
    or ROOT / "desktop" / "src-tauri" / "target" / "release" / "ithax-desktop"
)
UI_DIST = ROOT / "ui" / "dist"
HOME_HEADING = "What would you like to do?"
WAIT_S = 60.0


def free_port() -> int:
    with socket.socket() as handle:
        handle.bind(("127.0.0.1", 0))
        port: int = handle.getsockname()[1]
        return port


def program(name: str) -> str:
    """``name`` on the search path or in Cargo's folder; the test fails when it is missing."""
    for folder in [*os.environ.get("PATH", "").split(os.pathsep), str(Path.home() / ".cargo/bin")]:
        candidate = Path(folder) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    pytest.fail(f"{name} is not installed (see this module's docstring)")


class WebDriver:
    """The few WebDriver calls the test needs, to one ``tauri-driver``, over one kept-alive
    connection.

    ``tauri-driver`` 2.1.0 forwards each request to ``WebKitWebDriver`` through a pool of
    connections that does not retry. A request that says ``Connection: close`` (as each of
    ``urllib``'s does) is forwarded saying so; ``WebKitWebDriver`` then closes its end after
    answering, and the pool now and then sent the next request on that closing connection,
    which ``tauri-driver`` answered by dropping ours (about one call in ten; seen with
    ``strace``, 2026-11-09). Requests that keep the connection alive never met it."""

    def __init__(self, port: int) -> None:
        self.port = port
        self.session = ""
        self.connection = http.client.HTTPConnection("127.0.0.1", port, timeout=WAIT_S)

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        data = None if body is None else json.dumps(body).encode()
        try:
            self.connection.request(
                method, path, body=data, headers={"Content-Type": "application/json"}
            )
            response = self.connection.getresponse()
            payload = response.read()
        except (OSError, http.client.HTTPException):
            # A connection that failed is opened afresh by the next call.
            self.connection.close()
            raise
        if response.status != 200:
            raise AssertionError(f"{method} {path}: {response.status} {payload!r}")
        return json.loads(payload or b"{}").get("value")

    def start(self, args: list[str]) -> None:
        capabilities = {"tauri:options": {"application": str(APP), "args": args}}
        value = self.call("POST", "/session", {"capabilities": {"alwaysMatch": capabilities}})
        self.session = value["sessionId"]

    def end(self) -> None:
        if self.session:
            with contextlib.suppress(AssertionError, OSError, http.client.HTTPException):
                self.call("DELETE", f"/session/{self.session}")
            self.session = ""

    def find(self, xpath: str, timeout_s: float = WAIT_S) -> str:
        """The first element ``xpath`` finds, waiting up to ``timeout_s`` for it."""
        deadline = time.monotonic() + timeout_s
        while True:
            found = self.call(
                "POST", f"/session/{self.session}/elements", {"using": "xpath", "value": xpath}
            )
            if found:
                element: str = next(iter(found[0].values()))
                return element
            assert time.monotonic() < deadline, f"nothing matched {xpath}"
            time.sleep(0.2)

    def click(self, element: str) -> None:
        self.call("POST", f"/session/{self.session}/element/{element}/click", {})

    def text(self, element: str) -> str:
        value: str = self.call("GET", f"/session/{self.session}/element/{element}/text")
        return value

    def url(self) -> str:
        value: str = self.call("GET", f"/session/{self.session}/url")
        return value

    def wait_for_url(self, prefix: str, timeout_s: float = WAIT_S) -> str:
        """The window's address once it starts with ``prefix``, waiting up to ``timeout_s``."""
        deadline = time.monotonic() + timeout_s
        while not (address := self.url()).startswith(prefix):
            assert time.monotonic() < deadline, f"the window stayed at {address}"
            time.sleep(0.2)
        return address

    def handles(self) -> list[str]:
        value: list[str] = self.call("GET", f"/session/{self.session}/window/handles")
        return value

    def close_window(self) -> None:
        """Closes the window, as its close button does; the session ends with it."""
        with contextlib.suppress(OSError, http.client.HTTPException):
            self.call("DELETE", f"/session/{self.session}/window")
        self.session = ""

    def run(self, script: str) -> Any:
        return self.call(
            "POST", f"/session/{self.session}/execute/sync", {"script": script, "args": []}
        )


@pytest.fixture(scope="module")
def display() -> Iterator[str]:
    """A display for the shell: an Xvfb server on a free display number."""
    for need in (APP, UI_DIST / "index.html"):
        if not need.is_file():
            pytest.fail(f"{need} is missing; build it first (see this module's docstring)")
    read, write = os.pipe()
    server = subprocess.Popen(
        [
            program("Xvfb"),
            "-displayfd",
            str(write),
            "-screen",
            "0",
            "1280x1024x24",
            "-nolisten",
            "tcp",
        ],
        pass_fds=(write,),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.close(write)
    with os.fdopen(read) as answer:
        number = answer.readline().strip()
    assert number, "Xvfb did not start"
    yield f":{number}"
    server.terminate()
    server.wait(timeout=10)


@contextlib.contextmanager
def driver(display: str, python: str, log: Path) -> Iterator[WebDriver]:
    """``tauri-driver`` on a free port, its shell run with ``python`` as ``ITHAX_PYTHON``."""
    port = free_port()
    environment = {**os.environ, "DISPLAY": display, "ITHAX_PYTHON": python}
    environment.pop("WAYLAND_DISPLAY", None)
    with log.open("ab") as output:
        process = subprocess.Popen(
            [
                program("tauri-driver"),
                "--port",
                str(port),
                "--native-port",
                str(free_port()),
                "--native-driver",
                program("WebKitWebDriver"),
            ],
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
    web = WebDriver(port)
    deadline = time.monotonic() + WAIT_S
    while True:
        try:
            web.call("GET", "/status")
            break
        except (AssertionError, OSError, http.client.HTTPException):
            assert process.poll() is None, f"tauri-driver stopped; its log is {log}"
            assert time.monotonic() < deadline, f"tauri-driver did not answer; log {log}"
            time.sleep(0.2)
    try:
        yield web
    finally:
        web.end()
        web.connection.close()  # the kept-alive connection (warnings are errors, P20)
        process.terminate()
        process.wait(timeout=10)


def stop_service(config_dir: Path) -> None:
    info = read_service_file(config_dir)
    if info is None:
        return
    with contextlib.suppress(ProcessLookupError):
        os.kill(info.pid, signal.SIGTERM)
    deadline = time.monotonic() + 30
    while (config_dir / SERVICE_FILE).exists():
        assert time.monotonic() < deadline, "the service did not stop"
        time.sleep(0.05)


@contextlib.contextmanager
def other_server() -> Iterator[tuple[str, list[str]]]:
    """A page on another port of 127.0.0.1, and the paths it was asked for: somewhere the
    webview could load if the shell let it, whatever the machine's network."""
    asked: list[str] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            asked.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>elsewhere</h1>")

        def log_message(self, *_: object) -> None:
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/", asked
    finally:
        server.shutdown()
        server.server_close()


def first_start_seen(config_dir: Path) -> bool:
    with contextlib.suppress(OSError, ValueError):
        settings = json.loads((config_dir / "settings.json").read_text(encoding="utf-8"))
        return settings.get("interface", {}).get("first_start_seen") is True
    return False


def shell_running(config_dir: Path) -> bool:
    """Whether the shell started with ``config_dir`` is running."""
    parts = [str(APP).encode(), str(config_dir).encode()]
    return any(all(part in line for part in parts) for line in command_lines())


def command_lines() -> list[bytes]:
    lines = []
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            with contextlib.suppress(OSError):
                lines.append((entry / "cmdline").read_bytes())
    return lines


def test_the_shell_starts_the_service_and_reaches_home(display: str, tmp_path: Path) -> None:
    config_dir, data_dir = tmp_path / "config", tmp_path / "data"
    args = ["--config-dir", str(config_dir), "--data-dir", str(data_dir), "--ui-dir", str(UI_DIST)]
    try:
        with driver(display, sys.executable, tmp_path / "driver.log") as web:
            web.start(args)
            # The shell's own page, then the interface; nothing is looked for in between.
            web.wait_for_url("http://127.0.0.1:")
            # The first start's notice, then Home: Continue saves the notice as seen with
            # PUT /v1/settings, so the page holds the token and the service accepts it.
            web.click(web.find("//button[normalize-space()='Continue']"))
            web.find(f"//h1[normalize-space()='{HOME_HEADING}']")

            info = read_service_file(config_dir)
            assert info is not None and probe(info)
            # The interface's origin is the service's own; the page removed the fragment.
            assert web.url() == f"http://127.0.0.1:{info.port}/v1/ui/"
            # The notice closes at once and its PUT /v1/settings follows.
            deadline = time.monotonic() + WAIT_S
            while not first_start_seen(config_dir):
                assert time.monotonic() < deadline, "the notice was not saved as seen"
                time.sleep(0.1)
            # The token was never on a command line: it travelled on the launcher's pipe.
            assert not any(info.token.encode() in line for line in command_lines())

            # Nothing outside the interface's origin loads, and no window opens.
            # Each script returns before its navigation is asked for, so that WebKitWebDriver
            # never waits on a navigation the shell refuses.
            with other_server() as (elsewhere, asked):
                web.run(f"setTimeout(() => {{ window.location.href = '{elsewhere}navigated'; }});")
                web.run(f"setTimeout(() => {{ window.open('{elsewhere}opened', '_blank'); }});")
                web.run("setTimeout(() => { window.open('/v1/ui/', '_blank'); });")
                # A link that opens a new window, clicked (the Results screen's feedback link
                # is one).
                web.run(
                    "const a = document.createElement('a'); a.id = 'away'; a.textContent = 'away';"
                    " a.target = '_blank'; a.href = '/v1/ui/'; document.body.prepend(a);"
                )
                web.click(web.find("//a[@id='away']", timeout_s=5))
                web.run("setTimeout(() => { window.location.href = 'https://example.com/'; });")
                time.sleep(2.0)
                assert asked == []
            assert web.url() == f"http://127.0.0.1:{info.port}/v1/ui/"
            assert len(web.handles()) == 1
            web.find(f"//h1[normalize-space()='{HOME_HEADING}']", timeout_s=5)
            # Closing the window, as the user does, ends the shell, and only the shell: the
            # service keeps its own lifetime.
            assert shell_running(config_dir)
            web.close_window()
            deadline = time.monotonic() + 10
            while shell_running(config_dir):
                assert time.monotonic() < deadline, "the shell did not close"
                time.sleep(0.1)
            assert probe(info)
    finally:
        stop_service(config_dir)


def test_the_shell_says_why_when_no_service_starts(display: str, tmp_path: Path) -> None:
    missing = str(tmp_path / "no-python")
    with driver(display, missing, tmp_path / "driver.log") as web:
        web.start(["--config-dir", str(tmp_path / "config")])
        status = web.find(
            "//h1[@id='status'][normalize-space()='The engine service did not start']"
        )
        assert web.text(status) == "The engine service did not start"
        detail = web.text(web.find("//p[@id='detail']"))
        assert detail.startswith(f"{missing} could not be run"), detail
        assert "ITHAX_PYTHON" in detail
    assert not (tmp_path / "config" / SERVICE_FILE).exists()
