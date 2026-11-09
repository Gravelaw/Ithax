"""The built Linux package, installed and run (spec 3 "Packaging" and its acceptance row
"Fresh install to first result under ten minutes on Linux in a clean container"; spec 0
principle 6; AKS-127).

Marker ``package``: excluded from ``bash scripts/check.sh`` as ``perf`` is; run with
``pytest -m package`` after ``python scripts/package_linux.py`` and by the CI job
``package``. The archive is ``dist/lcsim-<version>-linux-x86_64.tar.gz`` (or
``LCSIM_PACKAGE``); the test fails, rather than skips, when it is missing.

The clean container is a plain ``ubuntu:24.04`` image run by Docker, as its ordinary user
``ubuntu``, with only the package's folder and this folder mounted read-only; the offline
run adds ``--network none``. Where Docker cannot run (``LCSIM_PACKAGE_RUNNER=local``), the
same script runs in a fresh home folder with a minimal environment, offline inside
``unshare -rn`` (a network namespace holding only loopback). The desktop check needs a
display server and ``tauri-driver`` as ``tests/desktop/test_shell.py`` does.
"""

import contextlib
import json
import os
import subprocess
import sys
import tarfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from scipy.stats import t as student_t

import lcsim
from desktop.test_shell import (
    HOME_HEADING,
    WAIT_S,
    command_lines,
    display,  # noqa: F401 (the fixture)
    driver,
    stop_service,
)
from lcsim.service.discovery import probe, read_service_file

pytestmark = [
    pytest.mark.package,
    pytest.mark.skipif(sys.platform != "linux", reason="the Linux package is tested on Linux"),
]

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
NAME = f"lcsim-{lcsim.__version__}-linux-x86_64"
ARCHIVE = Path(os.environ.get("LCSIM_PACKAGE", ROOT / "dist" / f"{NAME}.tar.gz"))
IMAGE = "ubuntu:24.04"
#: Spec 3's acceptance row: under ten minutes from install to a first result.
LIMIT_S = 600.0
#: Sets the loopback interface up (SIOCGIFFLAGS, then SIOCSIFFLAGS with IFF_UP), for
#: ``unshare -rn``, without needing ``ip`` from iproute2.
LOOPBACK_UP = (
    "import fcntl, socket, struct; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); "
    "r = fcntl.ioctl(s, 0x8913, struct.pack('16sH14s', b'lo', 0, b'')); "
    "f = struct.unpack('16sH14s', r)[1]; "
    "fcntl.ioctl(s, 0x8914, struct.pack('16sH14s', b'lo', f | 1, b''))"
)
TEMPLATES = sorted(path.name for path in (ROOT / "templates").iterdir() if path.is_dir())


@pytest.fixture(scope="module")
def archive() -> Path:
    if not ARCHIVE.is_file():
        pytest.fail(f"{ARCHIVE} is missing: run python scripts/package_linux.py first")
    return ARCHIVE


def docker_works() -> bool:
    with contextlib.suppress(OSError, subprocess.TimeoutExpired):
        return subprocess.run(["docker", "info"], capture_output=True, timeout=30).returncode == 0
    return False


def runner() -> str:
    chosen = os.environ.get("LCSIM_PACKAGE_RUNNER") or ("docker" if docker_works() else "local")
    assert chosen in ("docker", "local"), chosen
    return chosen


def clean_install(archive: Path, offline: bool, tmp_path: Path) -> tuple[float, dict[str, Any]]:
    """Run ``clean_install.sh`` in a clean environment; the wall time from before the
    environment starts until the first result, and the result."""
    extra = ["--offline"] if offline else []
    if runner() == "docker":
        command = ["docker", "run", "--rm", "--user", "ubuntu"]
        command += ["--network", "none"] if offline else []
        command += ["-v", f"{archive.parent}:/pkg:ro", "-v", f"{HERE}:/check:ro", IMAGE]
        command += ["sh", "/check/clean_install.sh", "/pkg", archive.name, *extra]
        environment = None
    else:
        home = tmp_path / "home"
        home.mkdir()
        # A new network namespace starts with loopback down; the service needs it up.
        up = ["sh", "-c", '"$0" -I -c "$1" && shift && exec "$@"', sys.executable, LOOPBACK_UP]
        command = ["unshare", "-rn", *up] if offline else []
        command += ["sh", str(HERE / "clean_install.sh"), str(archive.parent), archive.name]
        command += extra
        environment = {"HOME": str(home), "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
    started = time.monotonic()
    done = subprocess.run(
        command, capture_output=True, text=True, timeout=LIMIT_S + 60, env=environment
    )
    elapsed = time.monotonic() - started
    assert done.returncode == 0, done.stdout + done.stderr
    lines = done.stdout.splitlines()
    steps = {line.split()[1]: float(line.split()[2]) for line in lines if line.startswith("step ")}
    result: dict[str, Any] = json.loads(next(line for line in lines if line.startswith("{")))
    result["steps_s"] = steps
    result["runner"] = runner()
    print(json.dumps({"wall_s": round(elapsed, 2), **result}))
    return elapsed, result


def assert_first_result(result: dict[str, Any]) -> None:
    assert result["interface_title"] == "lcsim"
    assert result["templates"] == TEMPLATES
    assert result["engines"] == ["highs", "simpy"]
    assert result["run_state"] == "done"
    # The coffee shop's till.wait.mean within 3 standard errors of the M/M/1 value, 270 s
    # (spec 2's pass rule; the template's expected.json).
    n = result["till_wait_n"]
    error = result["till_wait_half_width_s"] / student_t.ppf(0.5 + result["confidence"] / 2, n - 1)
    assert abs(result["till_wait_mean_s"] - 270.0) <= 3 * error
    assert result["findings"] == []


def test_the_checksum_file_verifies_the_archive(archive: Path) -> None:
    checksum = archive.with_name(archive.name + ".sha256")
    done = subprocess.run(
        ["sha256sum", "-c", checksum.name], cwd=archive.parent, capture_output=True, text=True
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout == f"{archive.name}: OK\n"


def test_the_archive_holds_the_interface_service_engines_and_templates(archive: Path) -> None:
    with tarfile.open(archive) as tar:
        members = {member.name: member for member in tar.getmembers()}
    assert all(name == NAME or name.startswith(f"{NAME}/") for name in members)
    assert not [name for name in members if ".." in Path(name).parts or name.startswith("/")]
    for command in ("bin/lcsim", "bin/lcsim-launcher", "bin/lcsim-mcp", "install.sh"):
        assert members[f"{NAME}/{command}"].mode == 0o755, command
    for name in (
        "uninstall.sh",
        "LICENSE",
        "INSTALL.txt",
        "THIRD-PARTY-LICENSES.txt",
        "BUILD-INFO.json",
        "share/lcsim.png",
        "lib/lcsim-desktop",
        "python/bin/python3.13",
        "python/licenses/LICENSE.cpython.txt",
        "python/share/lcsim/ui/index.html",
        "python/share/lcsim/ui/THIRD-PARTY-NOTICES.txt",
    ):
        assert f"{NAME}/{name}" in members, name
    site = f"{NAME}/python/lib/python3.13/site-packages"
    for package in ("lcsim", "simpy", "highspy", "pyomo", "optuna", "scipy", "fastapi"):
        assert f"{site}/{package}/__init__.py" in members, package
    assert f"{site}/lcsim/service/__init__.py" in members
    shipped = {
        name.split("/")[5]
        for name in members
        if name.startswith(f"{NAME}/python/share/lcsim/templates/") and name.count("/") >= 6
    }
    assert sorted(shipped) == TEMPLATES
    for tid in TEMPLATES:
        assert f"{NAME}/python/share/lcsim/templates/{tid}/template.json" in members
    assert not [name for name in members if "/lib-dynload/_dbm." in name]


def test_fresh_install_to_first_result_under_ten_minutes(archive: Path, tmp_path: Path) -> None:
    elapsed, result = clean_install(archive, offline=False, tmp_path=tmp_path)
    assert_first_result(result)
    assert elapsed < LIMIT_S


def test_the_install_and_first_result_work_offline(archive: Path, tmp_path: Path) -> None:
    elapsed, result = clean_install(archive, offline=True, tmp_path=tmp_path)
    # The block holds: inside it, an outbound name lookup and connection both fail.
    assert result["outbound"]["lookup"].startswith("failed")
    assert result["outbound"]["connect"].startswith("failed")
    assert_first_result(result)
    assert elapsed < LIMIT_S


@pytest.fixture
def unpacked(archive: Path, tmp_path: Path) -> Iterator[tuple[Path, dict[str, str]]]:
    """The package unpacked and installed for a fresh home folder on this machine; its
    folder and the environment of that user."""
    home = tmp_path / "home"
    (home / "opt").mkdir(parents=True)
    with tarfile.open(archive) as tar:
        tar.extractall(home / "opt", filter="tar")
    folder = home / "opt" / NAME
    environment = {"HOME": str(home), "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
    done = subprocess.run(
        [folder / "install.sh"], env=environment, capture_output=True, text=True, timeout=120
    )
    assert done.returncode == 0, done.stdout + done.stderr
    yield folder, environment
    stop_service(home / ".config" / "lcsim")


def test_install_links_the_commands_and_uninstall_removes_them(
    unpacked: tuple[Path, dict[str, str]],
) -> None:
    folder, environment = unpacked
    home = Path(environment["HOME"])
    links = [home / ".local" / "bin" / name for name in ("lcsim", "lcsim-launcher", "lcsim-mcp")]
    entry = home / ".local" / "share" / "applications" / "lcsim.desktop"
    assert [link.readlink() for link in links] == [folder / "bin" / link.name for link in links]
    assert f'Exec="{folder}/bin/lcsim"' in entry.read_text("utf-8")
    done = subprocess.run(
        [folder / "uninstall.sh"], env=environment, capture_output=True, text=True, timeout=60
    )
    assert done.returncode == 0, done.stderr
    assert not [link for link in links if link.is_symlink()]
    assert not entry.exists()
    assert folder.is_dir()


def test_the_bundled_console_scripts_run_from_where_the_package_was_unpacked(
    unpacked: tuple[Path, dict[str, str]],
) -> None:
    folder, environment = unpacked
    bin_dir = folder / "python" / "bin"
    for path in sorted(bin_dir.iterdir()):
        if path.is_file() and not path.is_symlink() and path.read_bytes().startswith(b"#!"):
            first_lines = path.read_bytes().split(b"\n")[:3]
            # Every script runs the Python beside it, none a path from the build.
            assert not [line for line in first_lines if b"/dist/" in line or b"/tmp" in line], path
    done = subprocess.run(
        [bin_dir / "uvicorn", "--version"], env=environment, capture_output=True, text=True
    )
    assert done.returncode == 0, done.stderr
    assert "uvicorn 0.54.0" in done.stdout
    record = next(
        (folder / "python" / "lib" / "python3.13" / "site-packages").glob("lcsim-*/RECORD")
    )
    assert "direct_url.json" not in record.read_text("utf-8")


def test_lcsim_without_a_display_opens_the_interface_through_the_launcher(
    unpacked: tuple[Path, dict[str, str]],
) -> None:
    folder, environment = unpacked
    done = subprocess.run(
        [folder / "bin" / "lcsim", "--print-url"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    assert done.stderr.startswith(
        "lcsim: opening the interface in the browser, since no display is set"
    )
    assert done.stdout.startswith("http://127.0.0.1:")
    info = read_service_file(Path(environment["HOME"]) / ".config" / "lcsim")
    assert info is not None and probe(info)
    # The service runs on the package's own Python.
    command = (Path("/proc") / str(info.pid) / "cmdline").read_bytes().split(b"\0")
    assert command[0] == str(folder / "python" / "bin" / "python3").encode()


def test_the_installed_shell_reaches_home(
    unpacked: tuple[Path, dict[str, str]],
    display: str,  # noqa: F811
    tmp_path: Path,
) -> None:
    """``lcsim`` with a display runs the installed desktop shell, which starts the
    package's Python and service with the installed interface and templates."""
    folder, environment = unpacked
    home = Path(environment["HOME"])
    config_dir = home / ".config" / "lcsim"
    with driver(display, "python-unused", tmp_path / "driver.log") as web:
        capabilities = {
            "tauri:options": {
                "application": str(home / ".local" / "bin" / "lcsim"),
                "args": ["--config-dir", str(config_dir), "--data-dir", str(home / "data")],
            }
        }
        value = web.call("POST", "/session", {"capabilities": {"alwaysMatch": capabilities}})
        web.session = value["sessionId"]
        web.wait_for_url("http://127.0.0.1:")
        web.click(web.find("//button[normalize-space()='Continue']"))
        web.find(f"//h1[normalize-space()='{HOME_HEADING}']")
        info = read_service_file(config_dir)
        assert info is not None and probe(info)
        assert web.url() == f"http://127.0.0.1:{info.port}/v1/ui/"
        command = (Path("/proc") / str(info.pid) / "cmdline").read_bytes().split(b"\0")
        assert command[0] == str(folder / "python" / "bin" / "python3").encode()
        assert b"--ui-dir" not in command  # the installed interface, by the service's default
        shell = str(folder / "lib" / "lcsim-desktop").encode()
        assert any(line.startswith(shell) for line in command_lines())
        web.close_window()
    deadline = time.monotonic() + WAIT_S
    while any(line.startswith(shell) for line in command_lines()):
        assert time.monotonic() < deadline, "the shell did not end"
        time.sleep(0.2)
