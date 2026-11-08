"""``python -m lcsim.service`` (spec 3 "Discovery", "One service per user" and "Lifetime";
AKS-110 acceptance: ``service.json`` written, second start exits when the first answers).

``main`` runs in a thread here, so coverage sees it; one test also runs the module as a
real process, as the interface and the MCP server will start it.
"""

import contextlib
import io
import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx2
import pytest
import uvicorn

from lcsim.service.discovery import SERVICE_FILE, ServiceInfo, read_service_file
from lcsim.service.main import LOCAL_ADDRESS, SignalServer, bind_local, main, raise_again


def wait_for(condition: object, timeout_s: float = 20.0) -> None:
    assert callable(condition)
    deadline = time.monotonic() + timeout_s
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.02)


class Started:
    """``main`` running in a thread, with what it printed and returned."""

    def __init__(self, argv: list[str]) -> None:
        self.output = io.StringIO()
        self.status: list[int] = []
        self.thread = threading.Thread(target=self._run, args=(argv,), daemon=True)
        self.thread.start()

    def _run(self, argv: list[str]) -> None:
        self.status.append(main(argv, out=self.output, err=self.output))


@pytest.fixture
def folders(tmp_path: Path) -> list[str]:
    return ["--config-dir", str(tmp_path / "config"), "--data-dir", str(tmp_path / "data")]


@pytest.fixture
def first(folders: list[str], tmp_path: Path) -> Iterator[ServiceInfo]:
    """A service started by ``main`` that exits after 3 idle seconds."""
    started = Started([*folders, "--idle-minutes", "0.05"])
    config_dir = tmp_path / "config"
    wait_for(lambda: read_service_file(config_dir) is not None)
    info = read_service_file(config_dir)
    assert info is not None
    yield info
    started.thread.join(30)
    assert started.status == [0]


def get_system(info: ServiceInfo) -> httpx2.Response:
    with httpx2.Client(trust_env=False, timeout=5) as client:
        return client.get(
            f"http://{LOCAL_ADDRESS}:{info.port}/v1/system",
            headers={"Authorization": f"Bearer {info.token}"},
        )


def test_main_writes_service_json_and_serves(first: ServiceInfo, tmp_path: Path) -> None:
    assert first.pid == os.getpid()
    assert len(first.token) == 43
    assert first.started.endswith("Z")
    response = get_system(first)
    assert response.status_code == 200
    assert set(response.json()) == {"cores", "memory", "graphics", "tier", "workers"}
    assert (tmp_path / "config" / "settings.json").is_file()


def test_main_exits_when_idle_and_removes_its_file(folders: list[str], tmp_path: Path) -> None:
    started = Started([*folders, "--idle-minutes", "0.005"])
    started.thread.join(30)
    assert started.status == [0]
    assert "lcsim service on 127.0.0.1:" in started.output.getvalue()
    assert not (tmp_path / "config" / SERVICE_FILE).exists()


def test_a_second_start_exits_when_the_first_answers(
    first: ServiceInfo, folders: list[str], tmp_path: Path
) -> None:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        # Bounded, should the probe fail and this start serve instead.
        assert main([*folders, "--idle-minutes", "0.02"]) == 0
    assert f"already running on 127.0.0.1:{first.port}" in output.getvalue()
    assert read_service_file(tmp_path / "config") == first


def test_a_start_overwrites_a_file_whose_service_does_not_answer(
    folders: list[str], tmp_path: Path
) -> None:
    with bind_local() as sock:
        dead_port = sock.getsockname()[1]
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    stale = {"port": dead_port, "token": "old", "pid": 1, "started": "2026-01-01T00:00:00.000Z"}
    (config_dir / SERVICE_FILE).write_text(json.dumps(stale), encoding="utf-8")
    started = Started([*folders, "--idle-minutes", "0.01"])
    wait_for(lambda: (info := read_service_file(config_dir)) is not None and info.token != "old")
    started.thread.join(30)
    assert started.status == [0]


def test_two_starts_at_once_give_one_service(folders: list[str], tmp_path: Path) -> None:
    """Review of PR #34: two starts racing before either has written service.json must
    not both serve; the one that takes the lock serves and the other finds it."""
    starts = [Started([*folders, "--idle-minutes", "0.05"]) for _ in range(2)]
    for start in starts:
        start.thread.join(60)
    assert [start.status for start in starts] == [[0], [0]]
    outputs = [start.output.getvalue() for start in starts]
    served = [output for output in outputs if "lcsim service on" in output]
    found = [output for output in outputs if "already running" in output]
    assert len(served) == 1, outputs
    assert len(found) == 1, outputs


def test_a_start_that_cannot_take_the_lock_and_finds_no_service_fails(
    folders: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import lcsim.service.main as entry
    from lcsim.runs.lock import take_lock

    monkeypatch.setattr(entry, "STARTUP_WAIT_S", 0.3)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    held = take_lock(config_dir / entry.SERVICE_LOCK)
    try:
        error = io.StringIO()
        assert main(folders, err=error) == 1
    finally:
        held.release()
    assert "did not answer" in error.getvalue()
    assert not (config_dir / SERVICE_FILE).exists()


def test_the_lock_is_released_when_the_service_exits(folders: list[str], tmp_path: Path) -> None:
    from lcsim.runs.lock import is_held
    from lcsim.service.main import SERVICE_LOCK

    started = Started([*folders, "--idle-minutes", "0.005"])
    started.thread.join(30)
    assert started.status == [0]
    assert not is_held(tmp_path / "config" / SERVICE_LOCK)


@pytest.mark.parametrize("minutes", ["0", "-1"])
def test_idle_minutes_must_be_above_zero(minutes: str) -> None:
    with pytest.raises(SystemExit) as stopped, contextlib.redirect_stderr(io.StringIO()):
        main(["--idle-minutes", minutes])
    assert stopped.value.code == 2


def test_the_module_entry_point_is_main() -> None:
    import lcsim.service.__main__ as entry

    assert entry.main is main


def test_bind_local_binds_127_0_0_1_on_a_chosen_port() -> None:
    with bind_local() as sock:
        address, port = sock.getsockname()
    assert address == LOCAL_ADDRESS
    assert port > 0


def test_bind_local_closes_its_socket_when_binding_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    import socket

    closed: list[bool] = []

    class Failing(socket.socket):
        def bind(self, address: object) -> None:
            raise OSError("no address")

        def close(self) -> None:
            closed.append(True)
            super().close()

    monkeypatch.setattr(socket, "socket", Failing)
    with pytest.raises(OSError, match="no address"):
        bind_local()
    assert closed == [True]


def test_python_dash_m_lcsim_service_runs_as_a_process(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "lcsim.service",
            "--config-dir",
            str(config_dir),
            "--data-dir",
            str(tmp_path / "data"),
            "--idle-minutes",
            "0.02",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_for(lambda: read_service_file(config_dir) is not None or process.poll() is not None)
        info = read_service_file(config_dir)
        assert info is not None, process.communicate()
        assert info.pid == process.pid
        assert get_system(info).status_code == 200
        stdout, stderr = process.communicate(timeout=60)
    finally:
        if process.poll() is None:  # pragma: no cover - only when the test fails
            process.kill()
    assert process.returncode == 0, stderr
    assert f"lcsim service on 127.0.0.1:{info.port}" in stdout
    assert not (config_dir / SERVICE_FILE).exists()


@pytest.mark.skipif(os.name == "nt", reason="Windows has no SIGTERM to send to a process")
@pytest.mark.parametrize("stop", [signal.SIGTERM, signal.SIGINT], ids=["SIGTERM", "SIGINT"])
def test_a_service_stopped_by_a_signal_removes_its_file(tmp_path: Path, stop: int) -> None:
    """Spec 3 "Discovery": the file is removed when the service exits. uvicorn raises a
    caught signal again once it has shut down, which ended the process before the file was
    removed (M7 "Left"); the service still ends by that signal, so its status says so."""
    config_dir = tmp_path / "config"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "lcsim.service",
            "--config-dir",
            str(config_dir),
            "--data-dir",
            str(tmp_path / "data"),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_for(lambda: read_service_file(config_dir) is not None or process.poll() is not None)
        info = read_service_file(config_dir)
        assert info is not None, process.communicate()
        assert get_system(info).status_code == 200
        process.send_signal(stop)
        process.communicate(timeout=60)
    finally:
        if process.poll() is None:  # pragma: no cover - only when the test fails
            process.kill()
    assert process.returncode == -stop
    assert not (config_dir / SERVICE_FILE).exists()


def test_the_server_keeps_a_caught_signal_for_main() -> None:
    """In the main thread uvicorn installs its handlers; a signal caught while serving is
    kept in ``caught_signals`` instead of being raised as the server finishes."""
    server = SignalServer(uvicorn.Config(app=lambda: None))
    assert threading.current_thread() is threading.main_thread()
    with server.capture_signals():
        server.handle_exit(signal.SIGTERM, None)
    assert server.caught_signals == [signal.SIGTERM]
    assert server.should_exit


def test_main_raises_a_caught_signal_again_after_cleaning_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raised: list[int] = []
    monkeypatch.setattr(signal, "raise_signal", raised.append)
    raise_again([signal.SIGINT, signal.SIGTERM])
    # Last caught first, as uvicorn does.
    assert raised == [signal.SIGTERM, signal.SIGINT]
