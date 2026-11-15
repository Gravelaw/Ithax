"""Saving several files of a project folder as one change (spec 3 "Revision", AKS-111;
the data import, AKS-113).

``replace_in_order(files)`` writes every file's final bytes to a synced temporary file beside
its target, then the commit record ``RECORD`` naming each temporary and its target (the
commit point, #71), then renames the temporaries into place in the order given, and removes
the record. A failure before the record removes the temporary files; a rename that fails
puts back every file already renamed and removes the record, so the folder is as it was.
Either raises ``CommitFailed``, after logging; the caller answers with its own coded issue
and never shows the exception. The model store saves ``model.json`` then ``project.json``
(the revision); a data import saves the file then ``data/index.json``.

A process that ends during the renames leaves the record. ``replay(folder)`` finishes its
renames: the folder then holds every new file, never a mix of old and new
(``docs/research/m14-atomic-save.md``). It is called the first time a service process uses a
project folder (``ithax.service.projects_store``), when no commit of it can be under way.
"""

from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ithax.files import atomic_write, sync_folder, temporary_path, write_synced
from ithax.strict_json import encode_json, read_json_object_file

__all__ = ["RECORD", "CommitFailed", "Planned", "replace_in_order", "replay"]

#: The commit record in the folder of a commit's files, while its renames are under way.
RECORD = ".ithax-commit.json"

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Planned:
    """A file to save: its path, its new bytes, and the bytes it replaces (``None`` when
    it did not exist), put back if the change fails."""

    path: Path
    data: bytes
    previous: bytes | None


class CommitFailed(Exception):
    """The change was not saved, and the folder is as it was (unless putting a file back
    failed too, which is logged)."""


def replace_in_order(files: Sequence[Planned]) -> None:
    """Saves ``files`` in order, the last rename committing the change; ``CommitFailed``
    when it was not saved."""
    folder = _one_folder(files)
    temporaries = [temporary_path(planned.path) for planned in files]
    record = folder / RECORD
    done: list[Planned] = []
    try:
        try:
            for planned, temporary in zip(files, temporaries, strict=True):
                write_synced(temporary, planned.data)
            renames = [
                [temporary.name, planned.path.name]
                for planned, temporary in zip(files, temporaries, strict=True)
            ]
            atomic_write(record, encode_json({"renames": renames}))
        except OSError:
            _log.warning("Writing %s failed.", folder, exc_info=True)
            raise CommitFailed from None
        for planned, temporary in zip(files, temporaries, strict=True):
            try:
                # Every temporary is written before the first rename; the order is the
                # commit (module docstring), so this rename is not ithax.files's.
                os.replace(temporary, planned.path)  # noqa: TID251
            except OSError:
                _log.warning("Saving %s failed.", planned.path, exc_info=True)
                for earlier in reversed(done):
                    _put_back(earlier)
                _remove(record)
                raise CommitFailed from None
            done.append(planned)
        sync_folder(folder)
        _remove(record)
    finally:
        for temporary in temporaries:
            with contextlib.suppress(OSError):
                temporary.unlink()


def _put_back(planned: Planned) -> None:
    """Puts back the file a failed change replaced."""
    try:
        if planned.previous is None:
            planned.path.unlink()
            return
        atomic_write(planned.path, planned.previous)
    except OSError:
        _log.error("The previous %s could not be put back.", planned.path, exc_info=True)


def _one_folder(files: Sequence[Planned]) -> Path:
    """The folder every file of a commit sits in; its record goes there."""
    folders = {planned.path.parent for planned in files}
    if len(folders) != 1:
        raise ValueError(
            f"a commit's files must sit in one folder, not {sorted(map(str, folders))}"
        )
    return folders.pop()


def _remove(record: Path) -> None:
    try:
        record.unlink(missing_ok=True)
    except OSError:
        _log.error("The commit record %s could not be removed.", record, exc_info=True)


def _renames(record: Path) -> list[tuple[str, str]] | None:
    """The record's renames, or ``None`` when it cannot be read as one: each a pair of
    plain file names (no folder part)."""
    try:
        document = read_json_object_file(record)
    except (OSError, ValueError):
        return None
    renames = document.get("renames")
    if not isinstance(renames, list):
        return None
    pairs: list[tuple[str, str]] = []
    for pair in renames:
        if not (isinstance(pair, list) and len(pair) == 2):
            return None
        source, target = pair
        if not all(isinstance(name, str) and name and Path(name).name == name for name in pair):
            return None
        pairs.append((source, target))
    return pairs


def replay(folder: Path) -> bool:
    """Finishes the commit whose record ``folder`` holds: renames each temporary still
    there onto its target, in order, then removes the record. Whether there was one to
    finish. A record that cannot be read is left, and logged, and nothing changes."""
    record = folder / RECORD
    if not record.exists():
        return False
    renames = _renames(record)
    if renames is None:
        _log.error("The commit record %s cannot be read; the folder is left as it is.", record)
        return False
    try:
        for source, target in renames:
            if (folder / source).exists():
                # Finishing a commit's own renames, in its order (module docstring).
                os.replace(folder / source, folder / target)  # noqa: TID251
        sync_folder(folder)
    except OSError:
        _log.error("The commit recorded in %s could not be finished.", record, exc_info=True)
        return False
    _remove(record)
    _log.warning("A save interrupted in %s was finished.", folder)
    return True
