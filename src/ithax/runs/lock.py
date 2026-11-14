"""The run lock: how E191 tells whether a run's process is alive (spec 1 "Run folder and
results"; AKS-103).

The process that drives a run holds an exclusive lock on ``worker.lock`` in the run folder
from creation until the run reaches a final state. The operating system releases the lock
when that process ends, however it ends, and a process id that is reused cannot hold it,
so "the worker is not alive" is "the lock can be taken" (or the file is gone).

Platform-neutral (spec 3 "Architecture"): ``fcntl.flock`` on Linux and macOS, whose lock
belongs to the open file, so a second open file of the same process is refused too;
``msvcrt.locking`` on Windows, on the file's first byte. Both modules are imported when
used, so this module imports on every platform.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Protocol

__all__ = [
    "LOCK_FILE",
    "Locker",
    "PosixLocker",
    "RunLock",
    "WindowsLocker",
    "default_locker",
    "is_held",
    "take_lock",
]

LOCK_FILE = "worker.lock"


class Locker(Protocol):
    """Takes and releases an exclusive lock on an open file, without waiting."""

    def lock(self, fd: int) -> bool:
        """``True`` when the lock was taken, ``False`` when another holds it."""
        ...

    def unlock(self, fd: int) -> None: ...


class PosixLocker:
    """``fcntl.flock`` (Linux and macOS)."""

    def __init__(self) -> None:
        self._fcntl = importlib.import_module("fcntl")

    def lock(self, fd: int) -> bool:
        try:
            self._fcntl.flock(fd, self._fcntl.LOCK_EX | self._fcntl.LOCK_NB)
        except OSError:
            return False
        return True

    def unlock(self, fd: int) -> None:
        self._fcntl.flock(fd, self._fcntl.LOCK_UN)


class WindowsLocker:
    """``msvcrt.locking`` on the first byte (Windows)."""

    def __init__(self) -> None:
        self._msvcrt = importlib.import_module("msvcrt")

    def lock(self, fd: int) -> bool:
        os.lseek(fd, 0, os.SEEK_SET)  # msvcrt locks from the file's current position
        try:
            self._msvcrt.locking(fd, self._msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True

    def unlock(self, fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        self._msvcrt.locking(fd, self._msvcrt.LK_UNLCK, 1)


def default_locker(os_name: str = os.name) -> Locker:
    """The locker for the platform named by ``os_name`` (``os.name``)."""
    return WindowsLocker() if os_name == "nt" else PosixLocker()


class RunLock:
    """A lock this process holds on a lock file."""

    def __init__(self, path: Path, fd: int, locker: Locker) -> None:
        self.path = path
        self._fd: int | None = fd
        self._locker = locker

    def release(self, *, remove: bool = False) -> None:
        """Releases the lock and closes the file, then removes it when ``remove``; a
        second call does nothing."""
        if self._fd is None:
            return
        fd, self._fd = self._fd, None
        self._locker.unlock(fd)
        os.close(fd)
        if remove:
            self.path.unlink(missing_ok=True)


def take_lock(path: Path, *, create: bool = True, locker: Locker | None = None) -> RunLock:
    """Takes the lock on ``path``, creating the file (holding this process id, for a
    person reading the folder) unless ``create`` is false. Raises ``BlockingIOError``
    when another holds it, and ``FileNotFoundError`` when the file is missing and
    ``create`` is false."""
    chosen = default_locker() if locker is None else locker
    flags = os.O_RDWR | (os.O_CREAT if create else 0)
    fd = os.open(path, flags, 0o644)
    if not chosen.lock(fd):
        os.close(fd)
        raise BlockingIOError(f"the lock {path} is held by another process")
    if create:
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode("ascii"))
    return RunLock(path, fd, chosen)


def is_held(path: Path, *, locker: Locker | None = None) -> bool:
    """Whether a live process holds the lock on ``path``; ``False`` when the file is
    missing. The lock is not kept."""
    try:
        lock = take_lock(path, create=False, locker=locker)
    except FileNotFoundError:
        return False
    except BlockingIOError:
        return True
    lock.release()
    return False
