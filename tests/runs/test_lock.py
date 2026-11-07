"""The run lock that tells E191 whether a run's process is alive (AKS-103)."""

import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

from lcsim.runs.lock import (
    LOCK_FILE,
    PosixLocker,
    WindowsLocker,
    default_locker,
    is_held,
    take_lock,
)


def test_a_held_lock_is_seen_as_held_and_released_on_release(tmp_path: Path) -> None:
    path = tmp_path / LOCK_FILE
    assert not is_held(path)  # no file: nobody holds it
    lock = take_lock(path)
    assert path.read_text(encoding="ascii") == str(os.getpid())
    assert is_held(path)  # another open file of the same process is refused too
    lock.release()
    assert not is_held(path)
    assert path.exists()
    lock.release()  # a second release does nothing


def test_release_can_remove_the_file(tmp_path: Path) -> None:
    path = tmp_path / LOCK_FILE
    lock = take_lock(path)
    lock.release(remove=True)
    assert not path.exists()


def test_a_held_lock_cannot_be_taken_again(tmp_path: Path) -> None:
    path = tmp_path / LOCK_FILE
    lock = take_lock(path)
    with pytest.raises(BlockingIOError, match="held"):
        take_lock(path)
    lock.release()


def test_the_lock_is_released_when_its_process_ends(tmp_path: Path) -> None:
    path = tmp_path / LOCK_FILE
    code = (
        "import sys, time\n"
        "from pathlib import Path\n"
        "from lcsim.runs.lock import take_lock\n"
        "take_lock(Path(sys.argv[1]))\n"
        "print('locked', flush=True)\n"
        "time.sleep(30)\n"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(path)], stdout=subprocess.PIPE, text=True
    )
    try:
        assert child.stdout is not None and child.stdout.readline().strip() == "locked"
        assert is_held(path)
    finally:
        child.kill()
        child.wait()
    assert not is_held(path)


class FakeMsvcrt(types.ModuleType):
    """Stands in for Windows' ``msvcrt``: records calls; refuses while ``held``."""

    LK_NBLCK = 2
    LK_UNLCK = 0

    def __init__(self) -> None:
        super().__init__("msvcrt")
        self.calls: list[tuple[int, int, int]] = []
        self.held = False

    def locking(self, fd: int, mode: int, nbytes: int) -> None:
        self.calls.append((os.lseek(fd, 0, os.SEEK_CUR), mode, nbytes))
        if mode == self.LK_NBLCK and self.held:
            raise PermissionError(13, "locked")


def test_the_windows_locker_locks_the_first_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeMsvcrt()
    monkeypatch.setitem(sys.modules, "msvcrt", fake)
    locker = WindowsLocker()
    path = tmp_path / LOCK_FILE
    lock = take_lock(path, locker=locker)
    assert fake.calls == [(0, FakeMsvcrt.LK_NBLCK, 1)]
    lock.release()
    assert fake.calls[-1] == (0, FakeMsvcrt.LK_UNLCK, 1)
    fake.held = True
    assert is_held(path, locker=locker)
    with pytest.raises(BlockingIOError):
        take_lock(path, locker=locker)


def test_the_locker_follows_the_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    assert isinstance(default_locker("posix"), PosixLocker)
    monkeypatch.setitem(sys.modules, "msvcrt", FakeMsvcrt())  # Windows' module, faked
    assert isinstance(default_locker("nt"), WindowsLocker)
