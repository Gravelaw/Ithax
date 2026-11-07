"""Project and service folder paths (spec 3 "Endpoints" notes on projects, "Discovery";
redesigned after the review of PR #34, whose three path findings were relative paths,
Windows paths without a drive, and aliases).

Every path the service admits or stores goes through ``canonical``: made absolute against
the working folder, normalised, and resolved to its real path, so symbolic links and
Windows junctions are followed (``Path.resolve``, which does not need the path to exist).
A path a client sends must first be ``fully_qualified`` by the platform's rules (on
Windows a drive and a root, or a UNC share), since ``os.path.isabs`` takes ``\\projects``
there as absolute although it names a folder on whichever drive is current.

``same_folder`` is the one test for "the same project folder": equal canonical paths, or,
when both exist, ``os.path.samefile`` (which also sees two names of one folder that
resolving leaves apart, such as a different letter case on Windows).

``projects.json`` stores canonical paths (rule 5, owner to confirm): the folder itself,
not the name a client used, so a registration survives the alias being removed.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath

__all__ = ["PATH_FLAVOUR", "canonical", "fully_qualified", "same_folder"]

#: The path rules of the platform the service runs on; a test replaces it to check
#: Windows paths on any platform.
PATH_FLAVOUR: type[PurePath] = PureWindowsPath if os.name == "nt" else PurePosixPath


def fully_qualified(path: str, flavour: type[PurePath] | None = None) -> bool:
    """Whether ``path`` names one folder wherever the service is started: on Windows a
    drive and a root (``C:\\projects``) or a share (``\\\\server\\share``), elsewhere a
    root."""
    return (flavour or PATH_FLAVOUR)(path).is_absolute()


def canonical(path: str | os.PathLike[str]) -> Path:
    """``path`` made absolute, normalised and resolved to its real path."""
    return Path(os.path.abspath(path)).resolve()


def same_folder(first: Path, second: Path) -> bool:
    """Whether ``first`` and ``second`` name the same folder."""
    if canonical(first) == canonical(second):
        return True
    try:
        return os.path.samefile(first, second)
    except OSError:
        return False
