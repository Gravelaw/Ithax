"""A project's imported data files and their column index (spec 3 "Endpoints", the data rows
and notes, and "Project folder"; AKS-113).

``DataStore`` is what the data routes call:

- **Importing.** ``upload`` checks the name (``lcsim.model.data_files.file_name_problem``),
  reads the bytes (``read_table``: E189 for content that cannot be used), checks the
  declared units against the columns read (E184), and saves the file unchanged and its
  entry in ``data/index.json`` together (``lcsim.service.commit``: the file, then the index,
  which commits; a failure puts the previous file back, E186). A name already in the index
  is imported again in its place; one that differs from an indexed name only in letter
  case is E184, since Windows takes the two as one file. The save holds the project's
  write lock (``ModelStore.locked``), so no model write or run creation meets half an
  import.
- **Listing** the index's files in the order first imported.
- **Removing** a file: its entry is removed from the index (the commit), then the file. A
  file the model names may be removed; validation then reports E162.
- **Fitting** a column (``lcsim.model.fit``) from the file's bytes as they are now, which
  must still have the hash recorded at import (E189 otherwise), with the column's histogram
  for the Data screen's chart (AKS-120).

Errors are spec 3 bodies: 404 with E185 (no such project or file), 400 with E184, E186 or
E189; never exception text.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lcsim.model.data import (
    INDEX_FILE,
    DataFile,
    DataIndex,
    index_bytes,
    new_entry,
    read_data_index,
    time_units,
)
from lcsim.model.data_files import Table, UnreadableData, file_format, file_name_problem, read_table
from lcsim.model.fit import SCORE, fit_column, histogram
from lcsim.model.issues import Issue, pointer
from lcsim.service.commit import CommitFailed, Planned, replace_in_order
from lcsim.service.errors import MALFORMED, NOT_FOUND, PROJECT_FOLDER, ServiceError, malformed
from lcsim.service.model_store import ModelStore
from lcsim.strict_json import read_json

__all__ = ["DATA_FOLDER", "UNUSABLE", "DataStore", "parse_units"]

_log = logging.getLogger(__name__)

#: The project folder's folder of imported files (spec 3 "Project folder").
DATA_FOLDER = "data"
#: Spec 1: a data file that cannot be imported, or a column that cannot be fitted (400).
UNUSABLE = "E189"


def _issue(code: str, path: str, message: str, hint: str) -> Issue:
    return Issue(code=code, component=None, path=path, message=message, hint=hint)


def _unusable(path: str, message: str, hint: str) -> ServiceError:
    return ServiceError(400, UNUSABLE, message, [_issue(UNUSABLE, path, message, hint)])


def _bad(path: str, message: str, hint: str) -> ServiceError:
    return malformed([_issue(MALFORMED, path, message, hint)])


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_units(text: str | None) -> dict[str, str | None]:
    """The ``units`` part of an upload: a JSON object mapping column names to a Phase 1
    time unit or ``null``; E184 at ``/units`` or ``/units/<column>`` otherwise."""
    if text is None:
        return {}
    hint = 'Send a JSON object of column names and units, such as {"gap_min": "min"}.'
    try:
        document = read_json(text.encode("utf-8", "surrogatepass"))
    except ValueError:
        raise _bad("/units", "The part 'units' is not a JSON object.", hint) from None
    if not isinstance(document, dict):
        raise _bad("/units", "The part 'units' is not a JSON object.", hint)
    units: dict[str, str | None] = {}
    for column, unit in document.items():
        if unit is not None and unit not in time_units():
            raise _bad(
                pointer("units", column),
                f"The unit of the column '{column}' is not one of "
                f"{', '.join(time_units())} or null.",
                "Declare a time unit (s, min, h or d), or null for plain numbers.",
            )
        units[column] = unit
    return units


class DataStore:
    """The data files of the registered projects, through the model store's projects and
    write locks."""

    def __init__(self, models: ModelStore) -> None:
        self.models = models

    def _folder(self, pid: str) -> Path:
        """The ``data/`` folder of project ``pid`` (made when it is missing)."""
        folder = self.models.project_folder(pid) / DATA_FOLDER
        try:
            folder.mkdir(exist_ok=True)
        except OSError:
            raise ServiceError(
                400,
                PROJECT_FOLDER,
                f"The data folder '{folder}' cannot be made, so the project's data cannot be used.",
            ) from None
        return folder

    def index(self, pid: str) -> DataIndex:
        """The column index of project ``pid``."""
        return read_data_index(self._folder(pid))

    def files(self, pid: str) -> list[dict[str, Any]]:
        """The imported files of project ``pid``, in the order first imported."""
        with self.models.locked(pid):
            return [entry.as_dict() for entry in self.index(pid).entries()]

    def check_project(self, pid: str) -> None:
        """404 with E185 or 400 with E186 unless project ``pid`` can be used; before an
        upload is read."""
        self._folder(pid)

    # --- importing ---------------------------------------------------------------------

    def upload(
        self, pid: str, name: str, raw: bytes, units: Mapping[str, str | None]
    ) -> dict[str, Any]:
        """Imports the file ``name`` with bytes ``raw``; the entry and its ``preview``."""
        problem = file_name_problem(name)
        if problem is not None:
            raise _bad(
                "/file",
                problem,
                "Rename the file, for example to 'arrivals.csv', and import it again.",
            )
        try:
            table = read_table(raw, file_format(name))
        except UnreadableData as unreadable:
            raise _unusable("/file", unreadable.message, unreadable.hint) from None
        _check_units(table, units)
        entry = new_entry(name, raw, table, units, _now())
        with self.models.locked(pid):
            folder = self._folder(pid)
            current = read_data_index(folder)
            clash = next(
                (
                    other
                    for other in current.files
                    if other != name and other.casefold() == name.casefold()
                ),
                None,
            )
            if clash is not None:
                raise _bad(
                    "/file",
                    f"The project already has the file '{clash}', whose name differs from "
                    f"'{name}' only in letter case; Windows takes them as one file.",
                    f"Import it as '{clash}' to replace it, or under another name.",
                )
            files = dict(current.files)
            files[name] = entry  # in place when it was imported before
            self._save(
                folder,
                [Planned(folder / name, raw, _previous(folder / name, name in current.files))],
                files.values(),
                "imported",
            )
        return {**entry.as_dict(), "preview": [list(row) for row in table.preview]}

    def _save(
        self, folder: Path, planned: list[Planned], files: Iterable[DataFile], what: str
    ) -> None:
        """Saves ``planned`` and then the index listing ``files`` (the commit); E186 when
        the folder cannot be written, with the folder as it was."""
        index = folder / INDEX_FILE
        try:
            previous = index.read_bytes() if index.exists() else None
        except OSError:
            previous = None
        try:
            replace_in_order([*planned, Planned(index, index_bytes(files), previous)])
        except CommitFailed:
            raise ServiceError(
                400,
                PROJECT_FOLDER,
                f"The data folder '{folder}' cannot be written, so the file was not {what}.",
            ) from None

    # --- removing ----------------------------------------------------------------------

    def _entry(self, folder: Path, name: str) -> tuple[DataIndex, DataFile]:
        current = read_data_index(folder)
        entry = current.file(name)
        if entry is None:
            raise ServiceError(404, NOT_FOUND, f"The project has no imported file '{name}'.")
        return current, entry

    def delete(self, pid: str, name: str) -> list[dict[str, Any]]:
        """Removes the file ``name`` and its entry; the files that remain."""
        with self.models.locked(pid):
            folder = self._folder(pid)
            current, _entry = self._entry(folder, name)
            remaining = [entry for entry in current.entries() if entry.name != name]
            self._save(folder, [], remaining, "removed")
            try:
                (folder / name).unlink(missing_ok=True)
            except OSError:
                # The index no longer lists it, so it is not part of the project.
                _log.warning("The file %s could not be removed.", folder / name, exc_info=True)
            return [entry.as_dict() for entry in remaining]

    # --- fitting -----------------------------------------------------------------------

    def fit(self, pid: str, name: str, column: str) -> dict[str, Any]:
        """The candidates fitted to column ``column`` of file ``name``."""
        with self.models.locked(pid):
            folder = self._folder(pid)
            _current, entry = self._entry(folder, name)
            try:
                raw = (folder / name).read_bytes()
            except OSError:
                raw = None
        declared = entry.column(column)
        if declared is None:
            raise _bad(
                "/column",
                f"The file '{name}' has no column '{column}'.",
                "Name one of the columns that GET .../data lists for the file.",
            )
        if declared.type != "number":
            words = "text" if declared.type == "text" else "no values"
            raise _unusable(
                "/column",
                f"The column '{column}' of '{name}' holds {words}, so no distribution can be "
                "fitted to it.",
                "Choose a column of numbers.",
            )
        changed = _unusable(
            "/file",
            f"The file '{name}' is missing or has changed since it was imported.",
            "Import the file again, then fit the column.",
        )
        if raw is None or hashlib.sha256(raw).hexdigest() != entry.sha256:
            raise changed
        try:
            table = read_table(raw, entry.format)
        except UnreadableData:  # the bytes read as imported, since their hash is the same
            raise changed from None
        values = next(item.values for item in table.columns if item.name == column)
        candidates = fit_column(values, declared.unit)
        return {
            "file": name,
            "column": column,
            "unit": declared.unit,
            "values": int(values.size),
            "score": SCORE,
            "candidates": [candidate.as_dict() for candidate in candidates],
            "histogram": histogram(values),
        }


def _previous(path: Path, indexed: bool) -> bytes | None:
    """The bytes a save replaces at ``path``, put back if it fails; a file there that the
    index does not list is not part of the project and is not kept."""
    if not indexed:
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def _check_units(table: Table, units: Mapping[str, str | None]) -> None:
    """E184 for a unit declared for a column the table does not have, or for one that does
    not hold numbers."""
    kinds = {column.name: column.type for column in table.columns}
    for column, unit in units.items():
        if column not in kinds:
            raise _bad(
                pointer("units", column),
                f"The part 'units' names the column '{column}', which the file does not have.",
                "Name only columns of the file's first row.",
            )
        if unit is not None and kinds[column] != "number":
            raise _bad(
                pointer("units", column),
                f"The column '{column}' does not hold numbers, so it takes no unit.",
                "Declare units only for columns of numbers.",
            )
