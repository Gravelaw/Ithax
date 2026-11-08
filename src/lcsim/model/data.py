"""The project's ``data/`` folder as the model layer sees it: an index of imported files.

Spec 1 "Distributions", ``empirical`` with ``data``: a distribution may name a column of a
file in the project's ``data/`` folder (``{"file": ..., "column": ...}``). Values are read
as numbers or as quantities per the column index's declared unit, and a missing or changed
file is E162. Spec 3 "Project folder": ``data/`` holds the imported files, unchanged, plus a
column index.

``DataIndex`` holds what validation checks (AKS-90): which files were imported, their
columns with each column's type and declared unit, and the SHA-256 of each file as
imported; it reads the folder only to hash a file now. The import endpoint (AKS-113) writes
the index as ``data/index.json`` (``INDEX_FILE``, ``index_bytes``), and ``read_data_index``
reads it back with the strict reader, every value of a declared kind and range; an index
that cannot be read is an empty index, so every ``data`` reference is E162 until the files
are imported again (spec 3 "Project folder", owner to confirm). ``new_entry`` makes the
entry of a file just read (``lcsim.model.data_files``). No values are read here: a run
target reads them (``lcsim.runs.snapshots``).
"""

from __future__ import annotations

import hashlib
import logging
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy

from lcsim.model.data_files import (
    COLUMN_TYPES,
    FORMATS,
    ColumnType,
    ColumnValues,
    Table,
    file_name_problem,
)
from lcsim.model.units import PHASE_1_UNITS, Dimension, QuantityError, parse_quantity
from lcsim.strict_json import MAX_WHOLE, encode_json, read_json_file, real_in, whole_in

__all__ = [
    "EMPTY_DATA_INDEX",
    "INDEX_FILE",
    "INDEX_VERSION",
    "DataColumn",
    "DataFile",
    "DataIndex",
    "file_sha256",
    "fits_in_seconds",
    "index_bytes",
    "new_entry",
    "read_data_index",
    "time_units",
]

_log = logging.getLogger(__name__)

#: The column index's file name in ``data/``, and its layout version.
INDEX_FILE = "index.json"
INDEX_VERSION = 1

# A SHA-256 digest as lower-case hexadecimal, as ``hashlib`` writes it.
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CHUNK = 1 << 20


@dataclass(frozen=True)
class DataColumn:
    """One column of an imported file: its name, its declared unit and its type.

    ``unit`` is the unit the column's values are written in (a Phase 1 unit symbol such as
    ``min``), or ``None`` when they are plain numbers (spec 1 "Distributions"). ``type`` is
    ``number``, ``text`` or ``empty`` (``lcsim.model.data_files``). ``largest`` is the
    largest absolute value of a ``number`` column as the file holds it (``None`` for
    another type), so validation can tell whether every value fits in seconds without
    reading the file (``fits_in_seconds``; Codex on PR #37).
    """

    name: str
    unit: str | None = None
    type: ColumnType = "number"
    largest: float | None = None

    def as_dict(self) -> dict[str, Any]:
        """The column as the index and the API write it."""
        return {"name": self.name, "type": self.type, "unit": self.unit, "largest": self.largest}


@dataclass(frozen=True)
class DataFile:
    """One imported file of ``data/``: its name in the folder, its columns, and the
    SHA-256 of its bytes when it was imported (lower-case hexadecimal); with its format,
    the worksheet read (``None`` for a CSV), its size in bytes, its number of records and
    when it was imported (spec 3 ``GET .../data``)."""

    name: str
    columns: tuple[DataColumn, ...]
    sha256: str
    format: str = "csv"
    sheet: str | None = None
    size: int = 0
    rows: int = 0
    imported: str = ""

    def __post_init__(self) -> None:
        _check_name(self.name)
        if _SHA256.fullmatch(self.sha256) is None:
            raise ValueError(f"the SHA-256 of {self.name!r} is not 64 lower-case hex digits")

    def column(self, name: str) -> DataColumn | None:
        """The column called ``name``, or ``None``."""
        return next((column for column in self.columns if column.name == name), None)

    def as_dict(self) -> dict[str, Any]:
        """The file as the index and ``GET .../data`` write it."""
        return {
            "name": self.name,
            "format": self.format,
            "sheet": self.sheet,
            "size": self.size,
            "sha256": self.sha256,
            "imported": self.imported,
            "rows": self.rows,
            "columns": [column.as_dict() for column in self.columns],
        }


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

    def entries(self) -> tuple[DataFile, ...]:
        """The imported files in the index's order (the order first imported)."""
        return tuple(self.files.values())

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


def time_units() -> tuple[str, ...]:
    """The units a column may declare: the Phase 1 time units (spec 1 "Quantities")."""
    return tuple(unit for unit, dimension in PHASE_1_UNITS.items() if dimension is Dimension.TIME)


def new_entry(
    name: str, raw: bytes, table: Table, units: Mapping[str, str | None], imported: str
) -> DataFile:
    """The index entry of the file ``name`` whose bytes ``raw`` were read as ``table``,
    with the declared ``units`` (column name to unit; a column left out has none), imported
    at ``imported``. The caller has checked the units against the table."""
    return DataFile(
        name,
        tuple(
            DataColumn(column.name, units.get(column.name), column.type, _largest(column))
            for column in table.columns
        ),
        hashlib.sha256(raw).hexdigest(),
        format=table.format,
        sheet=table.sheet,
        size=len(raw),
        rows=table.records,
        imported=imported,
    )


def _largest(column: ColumnValues) -> float | None:
    """The largest absolute value of a ``number`` column; ``None`` for another type."""
    if column.type != "number":
        return None
    return float(numpy.max(numpy.abs(column.values)))


def fits_in_seconds(value: float, unit: str) -> bool:
    """Whether ``value`` in ``unit`` is a finite number of seconds: the check an inline
    quantity goes through (spec 1 "Quantities": ``"1e308 min"`` is E141), so a column of
    finite values cannot become an infinite time (Codex on PR #37)."""
    try:
        parse_quantity(f"{float(value)!r} {unit}", Dimension.TIME)
    except QuantityError:
        return False
    return True


def index_bytes(files: Iterable[DataFile]) -> bytes:
    """The bytes of ``data/index.json`` listing ``files`` in the order given."""
    return encode_json(
        {"index_version": INDEX_VERSION, "files": [entry.as_dict() for entry in files]}
    )


def read_data_index(folder: Path) -> DataIndex:
    """The column index of the ``data/`` folder ``folder``: ``data/index.json`` read by the
    strict reader. A folder without one has nothing imported; one that cannot be read, or
    does not hold the layout ``index_bytes`` writes, is taken as empty and logged."""
    path = folder / INDEX_FILE
    if not path.exists():
        return DataIndex(folder)
    try:
        document = read_json_file(path)
        files = _files(document)
    except (OSError, ValueError):  # the strict reader's refusal is a ValueError
        _log.warning("The column index %s cannot be read; it is taken as empty.", path)
        return DataIndex(folder)
    return DataIndex(folder, {entry.name: entry for entry in files})


_ENTRY_KEYS = {"name", "format", "sheet", "size", "sha256", "imported", "rows", "columns"}
_COLUMN_KEYS = {"name", "type", "unit", "largest"}


def _files(document: object) -> list[DataFile]:
    """The entries of an index document; ``ValueError`` for any other layout."""
    if not isinstance(document, dict) or set(document) != {"index_version", "files"}:
        raise ValueError("not an index")
    if whole_in(document["index_version"], INDEX_VERSION, INDEX_VERSION) is None:
        raise ValueError("another index version")
    entries = document["files"]
    if not isinstance(entries, list):
        raise ValueError("no list of files")
    files = [_entry(entry) for entry in entries]
    folded = {entry.name.casefold() for entry in files}
    if len(folded) != len(files):  # two entries for one file (also on Windows)
        raise ValueError("a file listed twice")
    return files


def _entry(entry: object) -> DataFile:
    if not isinstance(entry, dict) or set(entry) != _ENTRY_KEYS:
        raise ValueError("not a file entry")
    name, form, sheet = entry["name"], entry["format"], entry["sheet"]
    if not isinstance(name, str) or file_name_problem(name) is not None:
        raise ValueError("not a file name")
    if form not in FORMATS:
        raise ValueError("not a format")
    if not (sheet is None if form == "csv" else isinstance(sheet, str)):
        raise ValueError("not a sheet")
    size = whole_in(entry["size"], 0, MAX_WHOLE)
    rows = whole_in(entry["rows"], 0, MAX_WHOLE)
    sha256, imported, columns = entry["sha256"], entry["imported"], entry["columns"]
    if size is None or rows is None or not isinstance(imported, str):
        raise ValueError("not a size, record count or time")
    if not isinstance(sha256, str) or _SHA256.fullmatch(sha256) is None:
        raise ValueError("not a SHA-256")
    if not isinstance(columns, list):
        raise ValueError("no list of columns")
    read = tuple(_column(column) for column in columns)
    if len({column.name for column in read}) != len(read):
        raise ValueError("a column named twice")
    return DataFile(name, read, sha256, form, sheet, size, rows, imported)


def _column(column: object) -> DataColumn:
    if not isinstance(column, dict) or set(column) != _COLUMN_KEYS:
        raise ValueError("not a column")
    name, kind, unit, largest = column["name"], column["type"], column["unit"], column["largest"]
    if not isinstance(name, str) or not name:
        raise ValueError("not a column name")
    if kind not in COLUMN_TYPES:
        raise ValueError("not a column type")
    if unit is not None and (kind != "number" or unit not in time_units()):
        raise ValueError("not a unit")
    if kind == "number":
        largest = real_in(largest, 0.0, sys.float_info.max)
        if largest is None:
            raise ValueError("not a largest value")
    elif largest is not None:
        raise ValueError("a largest value for a column without numbers")
    return DataColumn(name, unit, kind, largest)


# A project with nothing imported: every data reference is E162.
EMPTY_DATA_INDEX = DataIndex()
