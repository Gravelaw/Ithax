"""The AppImage's own parts (#88; ``docs/research/m16-appimage.md``): the AppDir the build
makes from the package folder, its entry point, and the appimagetool call. The built
AppImage itself is tested under the marker ``package`` (``test_linux_package.py``)."""

import configparser
import contextlib
import os
import shutil
import signal
import subprocess
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from linux_package.build_script import ROOT, build

APPIMAGE = ROOT / "packaging" / "linux" / "appimage"


def stage(tmp_path: Path) -> Path:
    """A package folder with the commands the AppImage runs, each printing its name."""
    folder = tmp_path / "ithax-0.1.0-linux-x86_64"
    (folder / "bin").mkdir(parents=True)
    for command in build.COMMANDS:
        path = folder / "bin" / command
        path.write_text(f'#!/bin/sh\necho {command} "$@"\n', "ascii")
        path.chmod(0o755)
    (folder / "share").mkdir()
    (folder / "share" / "ithax.png").write_bytes(b"\x89PNG icon")
    (folder / "THIRD-PARTY-LICENSES.txt").write_text("Bundled components.\n", "utf-8")
    return folder


def test_the_appimage_is_named_for_the_version_and_machine() -> None:
    assert build.appimage_name("0.1.0") == "ithax-0.1.0-x86_64.AppImage"


def test_the_appdir_adds_the_entry_point_desktop_file_icon_and_runtime_licence(
    tmp_path: Path,
) -> None:
    folder = stage(tmp_path)
    licence = tmp_path / "LICENSE"
    licence.write_text("MIT License\n", "utf-8")
    before = {path.relative_to(folder) for path in folder.rglob("*")}
    build.make_appdir(folder, licence)
    added = {path.relative_to(folder) for path in folder.rglob("*")} - before
    assert added == {
        Path("AppRun"),
        Path("ithax.desktop"),
        Path("ithax.png"),
        Path("LICENSE.type2-runtime.txt"),
    }
    assert (folder / "AppRun").stat().st_mode & 0o777 == 0o755
    assert (folder / "ithax.png").read_bytes() == b"\x89PNG icon"
    assert (folder / "LICENSE.type2-runtime.txt").read_text("utf-8") == "MIT License\n"
    notices = (folder / "THIRD-PARTY-LICENSES.txt").read_text("utf-8")
    assert notices.startswith("Bundled components.\n")
    assert "type2-runtime 20251108" in notices
    assert "MIT" in notices and "LICENSE.type2-runtime.txt" in notices


@pytest.mark.parametrize(
    ("arguments", "printed"),
    [
        ([], "ithax\n"),
        (["--idle-minutes", "5"], "ithax --idle-minutes 5\n"),
        (["mcp"], "ithax-mcp\n"),
        (["mcp", "--help"], "ithax-mcp --help\n"),
        (["launcher", "--print-url"], "ithax-launcher --print-url\n"),
    ],
)
def test_apprun_starts_the_app_or_the_command_named(
    tmp_path: Path, arguments: list[str], printed: str
) -> None:
    folder = stage(tmp_path)
    build.make_appdir(folder, APPIMAGE / "AppRun")
    # Run through a link, as the AppImage's runtime does from its mount point.
    link = tmp_path / "linked-AppRun"
    link.symlink_to(folder / "AppRun")
    done = subprocess.run(["sh", str(link), *arguments], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout == printed


def test_the_desktop_file_names_the_icon_and_the_command() -> None:
    entry = configparser.ConfigParser(interpolation=None)
    entry.optionxform = str  # type: ignore[assignment,method-assign]
    entry.read(APPIMAGE / "ithax.desktop", encoding="utf-8")
    desktop = entry["Desktop Entry"]
    assert desktop["Type"] == "Application"
    assert desktop["Name"] == "Ithax"
    assert desktop["Icon"] == "ithax"  # ithax.png at the AppDir's top
    assert desktop["Exec"] == "ithax"
    assert desktop["Categories"].endswith(";")


def test_apprun_is_executable_posix_shell() -> None:
    path = APPIMAGE / "AppRun"
    assert path.stat().st_mode & 0o111
    assert path.read_text("utf-8").startswith("#!/bin/sh\n")
    assert subprocess.run(["sh", "-n", str(path)]).returncode == 0


def test_appimagetool_gets_the_pinned_runtime_and_fixed_times(tmp_path: Path) -> None:
    tool, runtime = tmp_path / "appimagetool", tmp_path / "runtime"
    appdir, target = tmp_path / "AppDir", tmp_path / "out.AppImage"
    command, environment = build.appimage_command(tool, runtime, appdir, target, 1_700_000_000)
    assert command == [
        str(tool),
        "--no-appstream",
        "--runtime-file",
        str(runtime),
        str(appdir),
        str(target),
    ]
    # appimagetool is itself an AppImage: it runs without FUSE by extracting itself.
    assert environment["APPIMAGE_EXTRACT_AND_RUN"] == "1"
    assert environment["SOURCE_DATE_EPOCH"] == "1700000000"
    assert environment["ARCH"] == "x86_64"
    assert environment["PATH"] == os.environ["PATH"]


def staged_with_service(tmp_path: Path) -> Path:
    """A package folder whose launcher starts a "service" that runs from the folder until
    the file ``stop`` appears beside it, and returns once the service runs, as the real
    launcher returns once the service answers. The service writes ``ended`` as it ends."""
    folder = stage(tmp_path)
    (folder / "python").mkdir()
    shutil.copy2(shutil.which("sh") or "/bin/sh", folder / "python" / "service")
    service = (
        f'echo $$ > "{tmp_path}/started"; '
        f'while [ ! -e "{tmp_path}/stop" ]; do sleep 0.05; done; touch "{tmp_path}/ended"'
    )
    launcher = folder / "bin" / "ithax-launcher"
    launcher.write_text(
        '#!/bin/sh\nhere=$(dirname "$(readlink -f "$0")")\n'
        f"\"$here/../python/service\" -c '{service}' </dev/null >/dev/null 2>&1 &\n"
        f'until [ -s "{tmp_path}/started" ]; do sleep 0.05; done\n'
        "echo http://127.0.0.1:1/v1/ui/#token=t\n",
        "ascii",
    )
    build.make_appdir(folder, APPIMAGE / "AppRun")
    return folder


def start_apprun(folder: Path, environment: dict[str, str]) -> subprocess.Popen[str]:
    return subprocess.Popen(
        ["sh", str(folder / "AppRun"), "launcher", "--print-url"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={"PATH": os.environ["PATH"], "ITHAX_APPRUN_POLL_S": "0.1", **environment},
    )


def service_running(folder: Path) -> bool:
    for exe in Path("/proc").glob("[0-9]*/exe"):
        with contextlib.suppress(OSError):
            if str(exe.readlink()).startswith(f"{folder}/"):
                return True
    return False


def cmdline(path: Path) -> bytes:
    """A process's command line, or nothing for one that ended while /proc was read."""
    with contextlib.suppress(OSError):
        return path.read_bytes()
    return b""


def wait_until(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + 30
    while not condition():
        assert time.monotonic() < deadline, what
        time.sleep(0.05)


@contextlib.contextmanager
def service_stopped_at_the_end(tmp_path: Path, folder: Path) -> Iterator[None]:
    try:
        yield
    finally:
        (tmp_path / "stop").touch()
        wait_until(lambda: not service_running(folder), "the service did not end")


def test_mounted_apprun_answers_at_once_and_keeps_the_files_in_the_background(
    tmp_path: Path,
) -> None:
    folder = staged_with_service(tmp_path)
    with service_stopped_at_the_end(tmp_path, folder):
        apprun = start_apprun(folder, {})
        # AppRun returns while the service still runs: it never ends before "stop".
        printed, errors = apprun.communicate(timeout=30)
        assert apprun.returncode == 0, errors
        assert printed == "http://127.0.0.1:1/v1/ui/#token=t\n"
        assert service_running(folder)
        # The waiter that holds the mount is still there while the service runs.
        waiters = [
            path
            for path in Path("/proc").glob("[0-9]*/cmdline")
            if str(folder / "AppRun").encode() in cmdline(path)
        ]
        assert waiters
        (tmp_path / "stop").touch()
        wait_until(
            lambda: not any(path.exists() for path in waiters),
            "the waiter did not end with the service",
        )


def test_extracted_apprun_stays_until_the_service_ends(tmp_path: Path) -> None:
    folder = staged_with_service(tmp_path)
    with service_stopped_at_the_end(tmp_path, folder):
        apprun = start_apprun(folder, {"APPIMAGE_EXTRACT_AND_RUN": "1"})
        wait_until(lambda: (tmp_path / "started").exists(), "the service did not start")
        # Well past several of AppRun's checks, it still waits for the running service.
        time.sleep(1)
        assert apprun.poll() is None
        (tmp_path / "stop").touch()
        printed, errors = apprun.communicate(timeout=30)
        assert apprun.returncode == 0, errors
        assert printed == "http://127.0.0.1:1/v1/ui/#token=t\n"
        # It returned only after the service had ended.
        assert (tmp_path / "ended").exists()


def test_extracted_apprun_with_no_cleanup_answers_at_once(tmp_path: Path) -> None:
    folder = staged_with_service(tmp_path)
    with service_stopped_at_the_end(tmp_path, folder):
        apprun = start_apprun(folder, {"APPIMAGE_EXTRACT_AND_RUN": "1", "NO_CLEANUP": "1"})
        _printed, errors = apprun.communicate(timeout=30)
        assert apprun.returncode == 0, errors
        assert service_running(folder)


def test_apprun_returns_the_commands_status(tmp_path: Path) -> None:
    folder = stage(tmp_path)
    (folder / "bin" / "ithax-mcp").write_text("#!/bin/sh\nexit 3\n", "ascii")
    build.make_appdir(folder, APPIMAGE / "AppRun")
    assert subprocess.run(["sh", str(folder / "AppRun"), "mcp"]).returncode == 3


@pytest.mark.parametrize("signal_number", [signal.SIGTERM, signal.SIGINT, signal.SIGHUP])
def test_a_signal_to_apprun_reaches_the_command_and_apprun_waits_for_it(
    tmp_path: Path, signal_number: int
) -> None:
    # Review of pull request 211: a caller stopping AppRun by its PID stops the command too,
    # as the exec of bin/ithax-mcp did before AppRun.
    folder = stage(tmp_path)
    pid_file = tmp_path / "command.pid"
    (folder / "bin" / "ithax-mcp").write_text(
        f'#!/bin/sh\necho $$ > "{pid_file}"\nexec sleep 60\n', "ascii"
    )
    build.make_appdir(folder, APPIMAGE / "AppRun")
    apprun = subprocess.Popen(
        ["sh", str(folder / "AppRun"), "mcp"],
        env={"PATH": os.environ["PATH"], "ITHAX_APPRUN_POLL_S": "0.2"},
    )
    deadline = time.monotonic() + 10
    while not pid_file.exists() or not pid_file.read_text().strip():
        assert time.monotonic() < deadline, "the command did not start"
        time.sleep(0.05)
    command = int(pid_file.read_text())
    try:
        apprun.send_signal(signal_number)
        assert apprun.wait(timeout=10) != 0
        with pytest.raises(ProcessLookupError):
            os.kill(command, 0)
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.kill(command, signal.SIGKILL)
        if apprun.poll() is None:
            apprun.kill()
            apprun.wait()


def test_apprun_passes_its_standard_input_to_the_command(tmp_path: Path) -> None:
    # The MCP server speaks over standard input and output.
    folder = stage(tmp_path)
    (folder / "bin" / "ithax-mcp").write_text("#!/bin/sh\nexec cat\n", "ascii")
    build.make_appdir(folder, APPIMAGE / "AppRun")
    done = subprocess.run(
        ["sh", str(folder / "AppRun"), "mcp"],
        input='{"jsonrpc": "2.0"}\n',
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout == '{"jsonrpc": "2.0"}\n'
