"""Reading an imported data file: CSV or Excel bytes into columns (spec 3 "Endpoints", the
data notes; AKS-113; research note ``docs/research/spec-3-distribution-fit.md``).

``file_name_problem(name)`` says why a file name cannot be used in ``data/``, or ``None``.
``read_table(raw, format)`` reads the bytes of a ``csv`` or ``xlsx`` file into a ``Table``:
the first row names the columns, each later row is a record, and each column has a type
(``number``, ``text`` or ``empty``), its numbers in row order (float64) and the first
records as a preview. Every problem with the content raises ``UnreadableData`` (spec 1
E189) with a message and a hint; an exception from the CSV reader or from openpyxl never
leaves this module, and its text is never shown (guide "Conventions", Errors).

The rules, in brief (spec 3 has them in full):

- **CSV**: UTF-8 with or without a byte order mark, comma separated, ``"`` quotes.
- **Excel**: ``.xlsx`` read with openpyxl in read-only mode, formulas by their saved
  values, from the first worksheet, at most ``MAX_UNPACKED_BYTES`` unpacked. defusedxml is a
  dependency, so openpyxl refuses entity declarations whatever Expat the Python has.
- **Header**: each name stripped, non-empty, not a number, at most ``MAX_COLUMN_NAME``
  characters, unlike the others. Trailing empty header cells of a workbook are not columns.
- **Records**: a row whose cells are all empty is skipped; a shorter row has empty cells
  at its end; a non-empty cell beyond the header is refused. At most ``MAX_RECORDS``
  records and ``MAX_CELLS`` cells.
- **Cells**: a number is finite (in a CSV, text in spec 1's number grammar once stripped,
  the same in an Excel text cell); empty is empty or only spaces; anything else is text,
  an Excel date written in ISO 8601 and a boolean as ``TRUE`` or ``FALSE``.
"""

from __future__ import annotations

import csv
import io
import logging
import re
import sys
import zipfile
from array import array
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any, ClassVar, Literal, Protocol, TypeAlias

import numpy

from lcsim.strict_json import is_number, real_in

__all__ = [
    "COLUMN_TYPES",
    "FORMATS",
    "MAX_CELLS",
    "MAX_COLUMN_NAME",
    "MAX_FILE_BYTES",
    "MAX_NAME_LENGTH",
    "MAX_RECORDS",
    "MAX_UNPACKED_BYTES",
    "PREVIEW_RECORDS",
    "Cell",
    "ColumnType",
    "ColumnValues",
    "Table",
    "UnreadableData",
    "file_format",
    "file_name_problem",
    "read_table",
]

_log = logging.getLogger(__name__)

ColumnType: TypeAlias = Literal["number", "text", "empty"]
#: A column's types, as the column index writes them.
COLUMN_TYPES: tuple[ColumnType, ...] = ("number", "text", "empty")
#: A preview cell: a number, text, or ``None`` for an empty cell.
Cell: TypeAlias = float | str | None

#: The formats an imported file may have, by its name's extension.
FORMATS = ("csv", "xlsx")

#: The largest file that may be imported (spec 3, AKS-113).
MAX_FILE_BYTES = 64 * 2**20
#: The most an ``.xlsx`` may unpack to.
MAX_UNPACKED_BYTES = 512 * 2**20
#: The most records (rows after the header) and cells a file may hold.
MAX_RECORDS = 1_048_576
MAX_CELLS = 10_000_000
#: The longest file name and column name.
MAX_NAME_LENGTH = 100
MAX_COLUMN_NAME = 200
#: How many records the preview holds.
PREVIEW_RECORDS = 10

# Spec 1's number grammar (the JSON number), as in a quantity.
_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
# ASCII letters, digits, space, `.`, `_`, `-`; a letter or digit first; `.csv` or `.xlsx`.
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._-]*\.(?:csv|xlsx)", re.IGNORECASE)
_DEVICE = re.compile(r"(?:con|prn|aux|nul|com[0-9]|lpt[0-9])", re.IGNORECASE)
_FLOAT_MAX = sys.float_info.max


class UnreadableData(Exception):
    """An imported file whose content cannot be used: spec 1 E189 with a message and a
    hint, for the service to turn into an issue."""

    code: ClassVar[str] = "E189"

    def __init__(self, message: str, hint: str) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


@dataclass(frozen=True)
class ColumnValues:
    """One column of a file read: its name, its type and its numbers in row order (empty
    cells left out; empty unless the type is ``number``)."""

    name: str
    type: ColumnType
    values: numpy.ndarray[Any, numpy.dtype[numpy.float64]] = field(compare=False)


@dataclass(frozen=True)
class Table:
    """A file read: its format, the worksheet read (``None`` for a CSV), its columns, the
    number of records and the first records as a preview."""

    format: str
    sheet: str | None
    columns: tuple[ColumnValues, ...]
    records: int
    preview: tuple[tuple[Cell, ...], ...]


def file_name_problem(name: str) -> str | None:
    """Why ``name`` cannot be the name of an imported file in ``data/``, or ``None``.

    The name is taken as it is, never as a path: 1 to ``MAX_NAME_LENGTH`` characters of
    ASCII letters, digits, space, ``.``, ``_`` and ``-``, a letter or digit first, ending in
    ``.csv`` or ``.xlsx`` in any case, and not a Windows device name before its first ``.``
    (``con.csv`` names the console there).
    """
    if not name:
        return "The file has no name."
    if len(name) > MAX_NAME_LENGTH:
        return f"The file name is {len(name)} characters long; at most {MAX_NAME_LENGTH} are taken."
    if _NAME.fullmatch(name) is None:
        return (
            f"The file name '{name}' cannot be used: a name is ASCII letters, digits, spaces, "
            "'.', '_' and '-', starts with a letter or a digit and ends in .csv or .xlsx."
        )
    if _DEVICE.fullmatch(name.split(".", 1)[0]) is not None:
        return f"The file name '{name}' names a device on Windows, so it cannot be used."
    return None


def file_format(name: str) -> str:
    """The format of a file whose name ``file_name_problem`` accepts: ``csv`` or ``xlsx``."""
    return name.rsplit(".", 1)[1].lower()


def read_table(raw: bytes, format: str) -> Table:
    """The bytes ``raw`` of a ``csv`` or ``xlsx`` file, read. ``UnreadableData`` when
    their content cannot be used; ``ValueError`` for another format (a programming
    error)."""
    if format not in FORMATS:
        raise ValueError(f"no reader for the format {format!r}")
    if len(raw) > MAX_FILE_BYTES:
        raise UnreadableData(
            f"The file is {len(raw)} bytes; at most 64 MiB ({MAX_FILE_BYTES} bytes) is taken.",
            "Import a smaller file, such as only the rows and columns the model needs.",
        )
    if format == "csv":
        return _read_csv(raw)
    return _read_xlsx(raw)


# --- building the table ------------------------------------------------------------------


class _Builder:
    """Collects the records of a file as they are read."""

    def __init__(self, names: Sequence[str]) -> None:
        self.names = tuple(names)
        self.numbers = [array("d") for _ in names]
        self.texts = [False] * len(names)
        self.records = 0
        self.preview: list[tuple[Cell, ...]] = []

    def add(self, row: Sequence[Cell], line: int) -> None:
        width = len(self.names)
        if any(cell is not None for cell in row[width:]):
            raise UnreadableData(
                f"Row {line} has more cells than the header row names ({width}).",
                "Give every column a name in the first row, or remove the extra cells.",
            )
        cells = tuple(row[:width]) + (None,) * (width - len(row))
        if all(cell is None for cell in cells):
            return
        self.records += 1
        if self.records > MAX_RECORDS:
            raise UnreadableData(
                f"The file has more than {MAX_RECORDS} records.",
                "Import a smaller file, such as only the rows the model needs.",
            )
        if self.records * width > MAX_CELLS:
            raise UnreadableData(
                f"The file has more than {MAX_CELLS} cells.",
                "Import a smaller file, such as only the columns the model needs.",
            )
        for index, cell in enumerate(cells):
            if isinstance(cell, float):
                self.numbers[index].append(cell)
            elif cell is not None:
                self.texts[index] = True
        if len(self.preview) < PREVIEW_RECORDS:
            self.preview.append(cells)

    def table(self, format: str, sheet: str | None) -> Table:
        columns = []
        for name, numbers, text in zip(self.names, self.numbers, self.texts, strict=True):
            kind: ColumnType = "text" if text else "number" if numbers else "empty"
            values = numbers if kind == "number" else array("d")
            columns.append(ColumnValues(name, kind, numpy.array(values, dtype=numpy.float64)))
        return Table(format, sheet, tuple(columns), self.records, tuple(self.preview))


def _header(cells: Sequence[object]) -> list[str]:
    names: list[str] = []
    for number, cell in enumerate(cells, start=1):
        if is_number(cell):
            raise _number_header(number)
        name = "" if cell is None else str(cell).strip()
        if not name:
            raise UnreadableData(
                f"Column {number} of the first row is empty; the first row must name every column.",
                "Write a name in the first row above every column.",
            )
        if _NUMBER.fullmatch(name):
            raise _number_header(number)
        if len(name) > MAX_COLUMN_NAME:
            raise UnreadableData(
                f"The name of column {number} is {len(name)} characters long; at most "
                f"{MAX_COLUMN_NAME} are taken.",
                "Shorten the column names in the first row.",
            )
        if name in names:
            raise UnreadableData(
                f"The first row names the column '{name}' twice.",
                "Give every column its own name.",
            )
        names.append(name)
    if not names:
        raise _no_header()
    return names


def _number_header(number: int) -> UnreadableData:
    return UnreadableData(
        f"Column {number} of the first row is a number; the first row must hold the column names.",
        "Add a first row that names each column, such as 'minutes between arrivals'.",
    )


def _no_header() -> UnreadableData:
    return UnreadableData(
        "The file has no header row: its first row must name the columns.",
        "Add a first row that names each column.",
    )


def _text_cell(text: str) -> Cell:
    """A cell written as text: empty, a finite number in spec 1's grammar, or text."""
    stripped = text.strip()
    if not stripped:
        return None
    if _NUMBER.fullmatch(stripped):
        number = float(stripped)
        if numpy.isfinite(number):
            return number
    return text


# --- CSV ---------------------------------------------------------------------------------


def _read_csv(raw: bytes) -> Table:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise UnreadableData(
            "The file is not UTF-8 text, so it cannot be read as a CSV file.",
            "Save it as 'CSV UTF-8 (comma delimited)', or import the Excel workbook itself.",
        ) from None
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        rows = _csv_rows(reader)
        header = next(rows, None)
        if header is None:
            raise _no_header()
        builder = _Builder(_header(header))
        for line, row in enumerate(rows, start=2):
            builder.add([_text_cell(cell) for cell in row], line)
    except csv.Error:
        raise UnreadableData(
            f"The CSV file cannot be read near line {reader.line_num}: a quote is not "
            "closed, a field is too long, or the text is not comma-separated values.",
            "Check the file in a spreadsheet program and save it again as CSV.",
        ) from None
    return builder.table("csv", None)


def _csv_rows(reader: Iterable[list[str]]) -> Iterator[list[str]]:
    """The rows of ``reader``, without the lines that are blank before the header."""
    started = False
    for row in reader:
        if not started and not any(cell.strip() for cell in row):
            continue
        started = True
        yield row


# --- Excel -------------------------------------------------------------------------------


class _Workbook(Protocol):
    """What is used of an openpyxl workbook (openpyxl ships no type information)."""

    @property
    def worksheets(self) -> Sequence[Any]: ...

    def close(self) -> None: ...


def _open_workbook(raw: bytes) -> _Workbook:
    """The workbook in ``raw``, opened read-only with saved values (openpyxl)."""
    import openpyxl  # imported here: only an Excel import needs it

    workbook: _Workbook = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    return workbook


def _unopenable() -> UnreadableData:
    return UnreadableData(
        "The file cannot be read as an Excel workbook (.xlsx): it is damaged, protected by a "
        "password, or another kind of file.",
        "Open it in Excel and save it as an unprotected .xlsx workbook, or save the sheet as "
        "CSV UTF-8.",
    )


def _unpacked_size(raw: bytes) -> int:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            return sum(info.file_size for info in archive.infolist())
    except (zipfile.BadZipFile, OSError, ValueError, EOFError):
        raise _unopenable() from None


def _excel_cell(value: object) -> Cell:
    if value is None:
        return None
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int | float):
        # Checked before any conversion: an integer beyond a float, or an infinity, is not
        # a number a distribution can take (lcsim.strict_json).
        number = real_in(value, -_FLOAT_MAX, _FLOAT_MAX)
        if number is not None:
            return number
        return repr(value) if isinstance(value, float) else "a very large number"
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, str):
        return _text_cell(value)
    return str(value)


def _read_xlsx(raw: bytes) -> Table:
    if _unpacked_size(raw) > MAX_UNPACKED_BYTES:
        raise UnreadableData(
            "The workbook is more than 512 MiB unpacked.",
            "Import a smaller workbook, such as one sheet with only the columns the model needs.",
        )
    try:
        workbook = _open_workbook(raw)
    except Exception:  # openpyxl raises many kinds on untrusted bytes (research note)
        _log.info("An Excel file could not be opened.", exc_info=True)
        raise _unopenable() from None
    try:
        if not workbook.worksheets:
            raise UnreadableData(
                "The workbook has no worksheet.",
                "Put the data in the first worksheet of the workbook.",
            )
        sheet = workbook.worksheets[0]
        rows = iter(sheet.iter_rows(values_only=True))
        header = next((row for row in rows if any(cell is not None for cell in row)), None)
        if header is None:
            raise _no_header()
        cells = list(header)
        while cells and _excel_cell(cells[-1]) is None:
            cells.pop()
        builder = _Builder(_header(cells))
        for line, row in enumerate(rows, start=2):
            builder.add([_excel_cell(cell) for cell in row], line)
        return builder.table("xlsx", str(sheet.title))
    except UnreadableData:
        raise
    except Exception:  # an exception while the rows are read (research note)
        _log.info("An Excel file could not be read.", exc_info=True)
        raise _unopenable() from None
    finally:
        workbook.close()
