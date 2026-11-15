"""Saving several files of a project folder as one change (spec 3 "Revision", AKS-111;
the data import, AKS-113; #71).

``replace_in_order(files)`` works in three steps:
1. It writes every file's final bytes to a synced temporary file beside its target.
2. It writes the commit record ``RECORD``, which names each temporary and its target. That
   write is the commit point: from then on the change is decided.
3. It renames the temporaries into place in the order given, and removes the record.

A failure before the record removes the temporaries and raises ``CommitFailed`` with
``pending`` false: nothing was saved, and the folder is as it was. A target that is a
folder is refused so, before anything is written, since no rename onto it can succeed.

After the record, nothing is ever put back: the change only goes forward (redo only,
``docs/research/m14-atomic-save.md``). A rename that fails raises ``CommitFailed`` with
``pending`` true: the record and the temporaries stay, and the next ``replay`` finishes the
change. The caller answers with its own coded issue and never shows the exception. The model
store saves ``model.json`` then ``project.json`` (the revision); a data import saves the file
then ``data/index.json``.

``replay(folder)`` finishes a recorded change. It renames each temporary that is still
there onto its target, in order; a rename already done has no temporary left, so a replay
can stop part-way and run again. It raises ``CommitFailed`` (``pending``) when the record
cannot be read or the renames fail, so a folder is never used with a change half done. The
projects store calls it on every use of a project folder (``ithax.service.projects_store``).

Every commit and every replay holds its folder's lock (``_lock_of``, one per resolved
folder path) for the whole of it, from writing or reading the record to removing it, so a
replay never removes a record that a later commit wrote (second review of PR #182). The
service is the only writer of a project folder (the interface and the MCP server go through
it), so a lock in the process is enough.
"""

from __future__ import annotations

import contextlib
import logging
import os
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ithax.files import atomic_write, sync_folder, temporary_path, write_synced
from ithax.strict_json import encode_json, read_json_object_file

__all__ = ["RECORD", "CommitFailed", "Planned", "replace_in_order", "replay"]

#: The commit record in the folder of a commit's files, while its renames are under way.
RECORD = ".ithax-commit.json"

_log = logging.getLogger(__name__)

# One lock per folder (by resolved path), held for a whole commit or replay.
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


@dataclass(frozen=True)
class Planned:
    """A file to save: its path and its new bytes."""

    path: Path
    data: bytes


class CommitFailed(Exception):
    """The change is not in place. With ``pending`` false nothing was saved and the folder
    is as it was; with ``pending`` true the change is recorded and the next ``replay``
    finishes it."""

    def __init__(self, *, pending: bool) -> None:
        super().__init__("pending" if pending else "not saved")
        self.pending = pending


def _lock_of(folder: Path) -> threading.Lock:
    """The lock of ``folder``, the same for every name of it."""
    key = str(folder.resolve())
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


def replace_in_order(files: Sequence[Planned]) -> None:
    """Saves ``files`` in order as one change; ``CommitFailed`` when it is not in place."""
    folder = _one_folder(files)
    with _lock_of(folder):
        temporaries = [temporary_path(planned.path) for planned in files]
        renames = [
            (temporary.name, planned.path.name)
            for planned, temporary in zip(files, temporaries, strict=True)
        ]
        try:
            for planned in files:
                # A rename onto a folder can never be finished, so it is refused here,
                # before the commit point, with nothing saved.
                if planned.path.is_dir():
                    raise IsADirectoryError(planned.path)
            for planned, temporary in zip(files, temporaries, strict=True):
                write_synced(temporary, planned.data)
            atomic_write(folder / RECORD, encode_json({"renames": [list(r) for r in renames]}))
        except OSError:
            _log.warning("Writing %s failed.", folder, exc_info=True)
            for temporary in temporaries:
                with contextlib.suppress(OSError):
                    temporary.unlink()
            raise CommitFailed(pending=False) from None
        _finish(folder, renames)


def _one_folder(files: Sequence[Planned]) -> Path:
    """The folder every file of a commit sits in; its record goes there."""
    folders = {planned.path.parent for planned in files}
    if len(folders) != 1:
        raise ValueError(
            f"a commit's files must sit in one folder, not {sorted(map(str, folders))}"
        )
    return folders.pop()


def _plain_name(name: object) -> bool:
    """Whether ``name`` is a file name with no folder part that the system can open."""
    if not isinstance(name, str) or name in ("", ".", ".."):
        return False
    forbidden = {"/", "\\", "\0", os.sep, *([os.altsep] if os.altsep else [])}
    return not any(character in name for character in forbidden)


def _renames(record: Path) -> list[tuple[str, str]] | None:
    """The record's renames, or ``None`` when it cannot be read as one: a list of pairs
    of plain file names."""
    try:
        document = read_json_object_file(record)
    except (OSError, ValueError):
        return None
    renames = document.get("renames")
    if not isinstance(renames, list) or not renames:
        return None
    pairs: list[tuple[str, str]] = []
    for pair in renames:
        if not (isinstance(pair, list) and len(pair) == 2 and all(map(_plain_name, pair))):
            return None
        pairs.append((pair[0], pair[1]))
    return pairs


def _finish(folder: Path, renames: Sequence[tuple[str, str]]) -> None:
    """Renames each temporary still in ``folder`` onto its target, in order, then removes
    the record; ``CommitFailed`` (``pending``) when that fails."""
    try:
        for source, target in renames:
            if (folder / source).exists():
                # The commit's own renames, in its order (module docstring), so not
                # ithax.files's.
                os.replace(folder / source, folder / target)  # noqa: TID251
        sync_folder(folder)
        (folder / RECORD).unlink()
    except (OSError, ValueError):
        _log.error("The change recorded in %s could not be finished.", folder, exc_info=True)
        raise CommitFailed(pending=True) from None


def replay(folder: Path) -> bool:
    """Finishes the change recorded in ``folder``; whether there was one. It waits for a
    commit or replay of ``folder`` under way. ``CommitFailed`` (``pending``) when the
    record cannot be read or its renames fail."""
    with _lock_of(folder):
        record = folder / RECORD
        if not record.exists():
            return False
        renames = _renames(record)
        if renames is None:
            _log.error("The commit record %s cannot be read.", record)
            raise CommitFailed(pending=True)
        _finish(folder, renames)
    _log.warning("A save interrupted in %s was finished.", folder)
    return True
