"""Saving several files of a project folder as one change (spec 3 "Revision", AKS-111;
the data import, AKS-113).

``replace_in_order(files)`` makes every file's final bytes first, writes each to a temporary
file beside its target, then renames them into place in the order given; the last rename is
the commit. A failure before the commit removes the temporary files and puts back every
file already renamed; a failure at the commit also puts them back, so the folder is as it
was. Either raises ``CommitFailed``, after logging; the caller answers with its own coded
issue and never shows the exception. The model store saves ``model.json`` then
``project.json`` (the revision, the commit); a data import saves the file then
``data/index.json`` (the commit).
"""

from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ithax.files import atomic_write, temporary_path, write_synced

__all__ = ["CommitFailed", "Planned", "replace_in_order"]

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
    temporaries = [temporary_path(planned.path) for planned in files]
    done: list[Planned] = []
    try:
        try:
            for planned, temporary in zip(files, temporaries, strict=True):
                write_synced(temporary, planned.data)
        except OSError:
            _log.warning("Writing %s failed.", files[0].path.parent, exc_info=True)
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
                raise CommitFailed from None
            done.append(planned)
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
