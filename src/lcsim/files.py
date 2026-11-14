"""The one way the product replaces a file: write a temporary file in the same folder, flush
it to disk, then rename it over the target (docs/retrospective/proposed-agent-setup.md, P5;
#99). A reader sees the old file or the new one, never half of either, and a write that
fails leaves the old file and no temporary behind.

``atomic_write`` takes the new bytes; ``atomic_write_with`` takes a writer for formats whose
library writes to a path itself (Parquet, SQLite). The temporary file is
``.<name>.<pid>.<thread>.tmp`` beside the target (``temporary_path``), so two writers never
share one. With ``mode``, the file is created with exactly that mode, whatever the umask;
without, it gets what ``open`` gives. Ruff's ``banned-api`` sends every other
``os.replace`` and ``os.rename`` here, and ``tests/test_conventions.py`` the method forms.

The multi-file commit of ``lcsim.service.commit`` writes its temporaries with
``write_synced`` and names them with ``temporary_path``, but renames them itself: its order
and roll-back are its own.
"""

from __future__ import annotations

import contextlib
import os
import threading
from collections.abc import Callable
from pathlib import Path

__all__ = ["atomic_write", "atomic_write_with", "temporary_path", "write_synced"]

#: The mode a new file is created with when none is asked for, before the umask.
_OPEN_MODE = 0o666


def temporary_path(path: Path) -> Path:
    """The temporary file beside ``path`` that this process and thread write first."""
    return path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")


def _sync(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _sync_folder(folder: Path) -> None:
    """Flushes the rename to disk. A system that cannot open a folder (Windows) has
    nothing to flush this way."""
    with contextlib.suppress(OSError):
        _sync(folder)


def write_synced(path: Path, data: bytes) -> None:
    """Writes ``data`` to ``path`` and flushes it to disk."""
    path.write_bytes(data)
    _sync(path)


def atomic_write_with(
    path: Path, writer: Callable[[Path], object], *, mode: int | None = None
) -> None:
    """Replaces ``path`` with what ``writer`` writes to the temporary path it is given,
    an empty file created beforehand. Whatever ``writer`` or the rename raises is raised,
    after the temporary is removed."""
    temporary = temporary_path(path)
    with contextlib.suppress(FileNotFoundError):
        temporary.unlink()
    try:
        # Created here, exclusively and with its mode, so the writer fills a file that was
        # never readable more widely than ``mode``.
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        os.close(os.open(temporary, flags, _OPEN_MODE if mode is None else mode))
        if mode is not None:
            # The umask may have removed bits; ``mode`` is wanted exactly.
            os.chmod(temporary, mode)
        writer(temporary)
        _sync(temporary)
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(OSError):
            temporary.unlink()
        raise
    _sync_folder(path.parent)


def atomic_write(path: Path, data: bytes, *, mode: int | None = None) -> None:
    """Replaces ``path`` with ``data``."""
    atomic_write_with(path, lambda temporary: temporary.write_bytes(data), mode=mode)
