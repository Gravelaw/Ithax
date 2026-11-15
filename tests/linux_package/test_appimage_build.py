"""The AppImage's own parts (#88; ``docs/research/m16-appimage.md``): the AppDir the build
makes from the package folder, its entry point, and the appimagetool call. The built
AppImage itself is tested under the marker ``package`` (``test_linux_package.py``)."""

import configparser
import contextlib
import os
import shutil
import subprocess
import time
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


def staged_with_service(tmp_path: Path, service_s: float) -> Path:
    """A package folder whose launcher starts a "service" that runs from the folder for
    ``service_s`` seconds after the launcher has returned, as the real one outlives it."""
    folder = stage(tmp_path)
    (folder / "python").mkdir()
    shutil.copy2(shutil.which("sleep") or "/bin/sleep", folder / "python" / "service")
    launcher = folder / "bin" / "ithax-launcher"
    launcher.write_text(
        '#!/bin/sh\nhere=$(dirname "$(readlink -f "$0")")\n'
        f'"$here/../python/service" {service_s} </dev/null >/dev/null 2>&1 &\n'
        "echo http://127.0.0.1:1/v1/ui/#token=t\n",
        "ascii",
    )
    build.make_appdir(folder, APPIMAGE / "AppRun")
    return folder


def run_apprun(folder: Path, environment: dict[str, str]) -> tuple[float, str]:
    started = time.monotonic()
    done = subprocess.run(
        ["sh", str(folder / "AppRun"), "launcher", "--print-url"],
        capture_output=True,
        text=True,
        timeout=60,
        env={"PATH": os.environ["PATH"], "ITHAX_APPRUN_POLL_S": "0.2", **environment},
    )
    assert done.returncode == 0, done.stderr
    return time.monotonic() - started, done.stdout


def service_running(folder: Path) -> bool:
    for exe in Path("/proc").glob("[0-9]*/exe"):
        with contextlib.suppress(OSError):
            if str(exe.readlink()).startswith(f"{folder}/"):
                return True
    return False


def test_mounted_apprun_answers_at_once_and_keeps_the_files_in_the_background(
    tmp_path: Path,
) -> None:
    folder = staged_with_service(tmp_path, 3)
    elapsed, printed = run_apprun(folder, {})
    assert printed == "http://127.0.0.1:1/v1/ui/#token=t\n"
    assert elapsed < 2
    # The waiter that holds the mount is still there while the service runs.
    waiters = [
        path
        for path in Path("/proc").glob("[0-9]*/cmdline")
        if str(folder / "AppRun").encode() in path.read_bytes()
    ]
    assert service_running(folder)
    assert waiters
    deadline = time.monotonic() + 15
    while service_running(folder) or any(path.exists() for path in waiters):
        assert time.monotonic() < deadline, "the waiter did not end with the service"
        time.sleep(0.1)


def test_extracted_apprun_stays_until_the_service_ends(tmp_path: Path) -> None:
    folder = staged_with_service(tmp_path, 2)
    elapsed, printed = run_apprun(folder, {"APPIMAGE_EXTRACT_AND_RUN": "1"})
    assert printed == "http://127.0.0.1:1/v1/ui/#token=t\n"
    assert elapsed >= 2
    assert not service_running(folder)


def test_extracted_apprun_with_no_cleanup_answers_at_once(tmp_path: Path) -> None:
    folder = staged_with_service(tmp_path, 1)
    elapsed, _printed = run_apprun(folder, {"APPIMAGE_EXTRACT_AND_RUN": "1", "NO_CLEANUP": "1"})
    assert elapsed < 1


def test_apprun_returns_the_commands_status(tmp_path: Path) -> None:
    folder = stage(tmp_path)
    (folder / "bin" / "ithax-mcp").write_text("#!/bin/sh\nexit 3\n", "ascii")
    build.make_appdir(folder, APPIMAGE / "AppRun")
    assert subprocess.run(["sh", str(folder / "AppRun"), "mcp"]).returncode == 3
