"""The AppImage's own parts (#88; ``docs/research/m16-appimage.md``): the AppDir the build
makes from the package folder, its entry point, and the appimagetool call. The built
AppImage itself is tested under the marker ``package`` (``test_linux_package.py``)."""

import configparser
import contextlib
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

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
    launcher returns once the service answers. The service writes ``ended`` as it ends, at
    ``stop`` or on TERM or HUP."""
    folder = stage(tmp_path)
    (folder / "python").mkdir()
    shutil.copy2(shutil.which("sh") or "/bin/sh", folder / "python" / "service")
    service = (
        f'trap "touch {tmp_path}/ended; exit 0" TERM HUP; echo $$ > "{tmp_path}/started"; '
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


def parent_pid(pid: int) -> int | None:
    """``pid``'s parent, or ``None`` for a process that ended while /proc was read."""
    with contextlib.suppress(OSError):
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("PPid:"):
                return int(line.split()[1])
    return None


def waiter_pids(folder: Path) -> list[int]:
    """AppRun's background waiters for ``folder``: the processes still running its AppRun
    whose parent does not, which leaves out the short subshells a waiter starts."""
    apprun = {
        int(path.parent.name)
        for path in Path("/proc").glob("[0-9]*/cmdline")
        if str(folder / "AppRun").encode() in cmdline(path)
    }
    parents = {pid: parent_pid(pid) for pid in apprun}
    return sorted(
        pid for pid, parent in parents.items() if parent is not None and parent not in apprun
    )


@pytest.mark.parametrize("number", [3, 4, 9])
def test_apprun_keeps_every_descriptor_it_inherits(tmp_path: Path, number: int) -> None:
    # The runtime's keepalive pipe (type2-runtime runtime.c): mounted, the AppImage stays
    # mounted only while a process holds its read end, which AppRun inherits, often as 3.
    # AppRun once took 3 for a copy of standard input, closing the pipe, and the mount went
    # away under the launcher (CI run 43761150645).
    folder = stage(tmp_path)
    pid_file = tmp_path / "command.pid"
    (folder / "bin" / "ithax-mcp").write_text(
        f'#!/bin/sh\necho $$ > "{pid_file}"\nexec sleep 60\n', "ascii"
    )
    build.make_appdir(folder, APPIMAGE / "AppRun")
    read_end, write_end = os.pipe()
    apprun = subprocess.Popen(
        [
            sys.executable,
            "-c",
            f"import os, sys; os.dup2({read_end}, {number}); os.close({read_end}); "
            'os.execvp("sh", ["sh", sys.argv[1], "mcp"])',
            str(folder / "AppRun"),
        ],
        pass_fds=(read_end,),
        env={"PATH": os.environ["PATH"]},
    )
    os.close(read_end)
    try:
        wait_until(lambda: pid_file.exists() and bool(pid_file.read_text().strip()), "no start")
        # Someone still holds the read end, so writing does not break the pipe.
        assert os.write(write_end, b"x") == 1
        holders = [
            int(fd.parent.parent.name)
            for fd in Path("/proc").glob(f"[0-9]*/fd/{number}")
            if int(fd.parent.parent.name) in (apprun.pid, int(pid_file.read_text()))
        ]
        assert apprun.pid in holders
    finally:
        apprun.send_signal(signal.SIGTERM)
        apprun.wait(timeout=30)
        os.close(write_end)


def staged_with_service_and_command(tmp_path: Path) -> Path:
    """A package folder whose ``mcp`` starts the service, as the desktop shell or the MCP
    server can, and then keeps running until stopped."""
    folder = staged_with_service(tmp_path)
    (folder / "bin" / "ithax-mcp").write_text(
        '#!/bin/sh\nhere=$(dirname "$(readlink -f "$0")")\n'
        '"$here/ithax-launcher" > /dev/null\nexec sleep 60\n',
        "ascii",
    )
    return folder


PHASES = ("before the command", "command", "foreground stay", "background waiter")
SIGNALS: dict[int, int] = {signal.SIGTERM: 143, signal.SIGINT: 143, signal.SIGHUP: 129}


def signal_cases() -> list[Any]:
    """Every phase of AppRun against every signal, with and without a service the command
    has started (detached), mounted and extracted where the phase is in both. Not every
    combination exists: before the command nothing is started yet; AppRun stays only while a
    service runs, in the foreground when extracted and as the background waiter when
    mounted."""
    cases = []
    for number in SIGNALS:
        name = signal.Signals(number).name
        cases.append(pytest.param("before the command", number, False, False, id=f"before-{name}"))
        for detached in (False, True):
            for extracted in (False, True):
                cases.append(
                    pytest.param(
                        "command",
                        number,
                        detached,
                        extracted,
                        id=f"command-{name}-{'service' if detached else 'alone'}-"
                        f"{'extracted' if extracted else 'mounted'}",
                    )
                )
        cases.append(pytest.param("foreground stay", number, True, True, id=f"foreground-{name}"))
        cases.append(pytest.param("background waiter", number, True, False, id=f"waiter-{name}"))
    return cases


def staged_for(tmp_path: Path, phase: str, detached: bool) -> tuple[Path, list[str]]:
    """The package folder for a case and AppRun's arguments. The command writes its PID to
    ``command.pid``; with ``detached`` it first starts the service through the launcher."""
    folder = staged_with_service(tmp_path)
    if phase in ("foreground stay", "background waiter"):
        return folder, ["launcher", "--print-url"]
    start = '"$here/ithax-launcher" > /dev/null\n' if detached else ""
    (folder / "bin" / "ithax-mcp").write_text(
        '#!/bin/sh\nhere=$(dirname "$(readlink -f "$0")")\n'
        f'{start}echo $$ > "{tmp_path}/command.pid"\nexec sleep 60\n',
        "ascii",
    )
    return folder, ["mcp"]


def reach(phase: str, apprun: subprocess.Popen[str], tmp_path: Path, folder: Path) -> int:
    """Wait until AppRun is in ``phase``; the PID to send the signal to."""
    if phase == "before the command":
        hold = tmp_path / "hold"
        wait_until(lambda: hold.exists() and hold.read_text().strip() == "held", "no hold")
        return apprun.pid
    if phase == "command":
        pid_file = tmp_path / "command.pid"
        wait_until(lambda: pid_file.exists() and bool(pid_file.read_text().strip()), "no command")
        return apprun.pid
    assert apprun.stdout is not None
    # The command has returned once AppRun closes the caller's output, in both modes.
    assert apprun.stdout.read() == "http://127.0.0.1:1/v1/ui/#token=t\n"
    if phase == "foreground stay":
        return apprun.pid
    assert apprun.wait(timeout=30) == 0
    [waiter] = waiter_pids(folder)
    return waiter


def from_the_appimage(folder: Path, tmp_path: Path) -> list[str]:
    """What still runs from the AppImage: its processes, AppRun's waiters, the command."""
    left = [f"waiter {pid}" for pid in waiter_pids(folder)]
    left += ["a process from the folder"] if service_running(folder) else []
    pid_file = tmp_path / "command.pid"
    if pid_file.exists() and pid_file.read_text().strip():
        if Path(f"/proc/{int(pid_file.read_text())}").exists():
            left.append("the command")
    return left


@pytest.mark.parametrize(("phase", "number", "detached", "extracted"), signal_cases())
def test_a_signal_in_any_phase_stops_everything_from_the_appimage_before_apprun_ends(
    tmp_path: Path, phase: str, number: int, detached: bool, extracted: bool
) -> None:
    # Reviews of pull request 211 (three findings of the class "a process left behind after
    # a stop"): whatever phase AppRun is in, a TERM, INT or HUP stops everything it started
    # that runs from the AppImage, and AppRun (or its waiter) ends only after all of it has,
    # with 143 for TERM and INT and 129 for HUP.
    folder, arguments = staged_for(tmp_path, phase, detached)
    environment = {"PATH": os.environ["PATH"], "ITHAX_APPRUN_POLL_S": "0.1"}
    if extracted:
        environment["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    if phase == "before the command":
        environment["ITHAX_APPRUN_HOLD"] = str(tmp_path / "hold")
        (tmp_path / "hold").touch()
    with service_stopped_at_the_end(tmp_path, folder):
        apprun = subprocess.Popen(
            ["sh", str(folder / "AppRun"), *arguments],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=environment,
        )
        with apprun:
            try:
                target = reach(phase, apprun, tmp_path, folder)
                if phase == "background waiter" and number == signal.SIGINT:
                    # dash starts a background process with INT ignored, past undoing, so
                    # the waiter cannot take INT; it holds on, and the service its files.
                    os.kill(target, number)
                    time.sleep(1)
                    assert Path(f"/proc/{target}").exists()
                    assert service_running(folder)
                    number = signal.SIGTERM
                os.kill(target, number)
                if target == apprun.pid:
                    assert apprun.wait(timeout=30) == SIGNALS[number]
                else:
                    wait_until(lambda: not Path(f"/proc/{target}").exists(), "waiter lives")
                # Ended only after everything from the AppImage had: nothing is left, and
                # the service, if there was one, saw the signal and ended.
                assert from_the_appimage(folder, tmp_path) == []
                assert (tmp_path / "ended").exists() == detached
                if phase == "before the command":
                    assert not (tmp_path / "command.pid").exists()
            finally:
                if apprun.poll() is None:
                    apprun.kill()
                    apprun.wait()
                pid_file = tmp_path / "command.pid"
                if pid_file.exists() and pid_file.read_text().strip():
                    with contextlib.suppress(ProcessLookupError, ValueError):
                        os.kill(int(pid_file.read_text()), signal.SIGKILL)
