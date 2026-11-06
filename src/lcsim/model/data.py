"""The project's ``data/`` folder as the model layer sees it: an index of imported files.

Spec 1 "Distributions", ``empirical`` with ``data``: a distribution may name a column of a
file in the project's ``data/`` folder (``{"file": ..., "column": ...}``). Values are read
as numbers or as quantities per the column index's declared unit, and a missing or changed
file is E162. Spec 3 "Project folder": ``data/`` holds the imported files, unchanged, plus a
column index.

The import endpoint (spec 3, M6) writes the column index; its file format is decided
there. Until then the model layer needs only what E162 checks: which files were imported,
their columns with each column's declared unit, and the SHA-256 of each file as imported.
``DataIndex`` holds exactly that, and reads the folder only to hash a file now. No values
are read and nothing is sampled here (``empirical`` with ``data`` runs from M6; Build guide
"Known gaps").
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

__all__ = ["EMPTY_DATA_INDEX", "DataColumn", "DataFile", "DataIndex", "file_sha256"]

# A SHA-256 digest as lower-case hexadecimal, as ``hashlib`` writes it.
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CHUNK = 1 << 20


@dataclass(frozen=True)
class DataColumn:
    """One column of an imported file: its name and its declared unit.

    ``unit`` is the unit the column's values are written in (a Phase 1 unit symbol such as
    ``min``), or ``None`` when they are plain numbers (spec 1 "Distributions").
    """

    name: str
    unit: str | None = None


@dataclass(frozen=True)
class DataFile:
    """One imported file of ``data/``: its name in the folder, its columns, and the
    SHA-256 of its bytes when it was imported (lower-case hexadecimal)."""

    name: str
    columns: tuple[DataColumn, ...]
    sha256: str

    def __post_init__(self) -> None:
        _check_name(self.name)
        if _SHA256.fullmatch(self.sha256) is None:
            raise ValueError(f"the SHA-256 of {self.name!r} is not 64 lower-case hex digits")

    def column(self, name: str) -> DataColumn | None:
        """The column called ``name``, or ``None``."""
        return next((column for column in self.columns if column.name == name), None)


@dataclass(frozen=True)
class DataIndex:
    """The column index of a project's ``data/`` folder.

    ``folder`` is the ``data/`` folder itself; ``files`` maps each imported file's name to
    its entry. An index with files needs its folder, so that a file can be hashed now and
    compared with the hash recorded at import.
    """

    folder: Path | None = None
    files: Mapping[str, DataFile] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, entry in self.files.items():
            if entry.name != name:
                raise ValueError(f"the index entry under {name!r} is for {entry.name!r}")
        if self.files and self.folder is None:
            raise ValueError("an index with files needs the data/ folder")
        object.__setattr__(self, "files", MappingProxyType(dict(self.files)))

    def file(self, name: str) -> DataFile | None:
        """The imported file called ``name``, or ``None`` when the index has none."""
        return self.files.get(name)

    def current_sha256(self, name: str) -> str | None:
        """The SHA-256 of ``data/<name>`` as it is now, or ``None`` when the index has no
        such file, or it is no longer a readable file in the folder."""
        if self.folder is None or name not in self.files:
            return None
        try:
            return file_sha256(self.folder / name)
        except OSError:
            return None


def file_sha256(path: Path) -> str:
    """The SHA-256 of the file at ``path``, as lower-case hexadecimal.

    Raises ``OSError`` when the file cannot be read, as ``open`` does.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _check_name(name: str) -> None:
    # A name in the folder itself: never a path that could leave data/.
    if name in ("", ".", "..") or "/" in name or "\\" in name or "\x00" in name:
        raise ValueError(f"{name!r} is not the name of a file in data/")


# A project with nothing imported: every data reference is E162.
EMPTY_DATA_INDEX = DataIndex()
