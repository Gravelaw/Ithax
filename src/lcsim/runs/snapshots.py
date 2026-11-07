"""The columns a run copies for ``empirical`` ``data`` (spec 1 "Distributions" and "Run folder
and results"; AKS-113).

When a run is created, ``read_columns(model, data)`` reads every ``data`` reference of the
model from the bytes of its file in the project's ``data/`` folder. Each file is read once:
its SHA-256 is taken from the very bytes the column is read from, so a file replaced after
validation is never copied under the hash it had before; a file that is missing, or whose
hash is not the one the column index recorded, is E162 at the reference, and so is a column
that is not numbers. ``with_columns(model, columns)`` gives the model whose ``data``
distributions also hold their values in seconds (the distribution sampler and the engine
input sample those), and ``write_snapshots(folder, columns)`` writes each column to
``<run>/data/<component id>.<setting>.parquet``: ``value`` (float64, the values as the file
holds them, empty cells left out) and ``unit`` (the declared unit, ``1`` for none).
``ColumnSnapshot.record()`` is the reference's ``data_files`` entry of the manifest.
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy
import pyarrow as pa
import pyarrow.parquet as pq

from lcsim.model.catalogue import PROCESS_TYPES, SettingKind
from lcsim.model.data import DataIndex
from lcsim.model.data_files import UnreadableData, read_table
from lcsim.model.issues import Issue, pointer
from lcsim.model.model import Component, Distribution, Model
from lcsim.model.units import Dimension, parse_quantity

__all__ = [
    "DATA_FOLDER",
    "ColumnSnapshot",
    "read_columns",
    "read_snapshot",
    "snapshot_name",
    "with_columns",
    "write_snapshots",
]

#: The run folder's folder of copied columns.
DATA_FOLDER = "data"

#: The unit column's word for a column of plain numbers (as in the results tables).
_NO_UNIT = "1"

Values = numpy.ndarray[Any, numpy.dtype[numpy.float64]]


def snapshot_name(component: str, setting: str) -> str:
    """The file name of the snapshot of a component's setting: ``<component>.<setting>.parquet``."""
    return f"{component}.{setting}.parquet"


@dataclass(frozen=True)
class ColumnSnapshot:
    """One ``data`` reference as a run read it: where it is in the model, the file and
    column it names, the hash of the bytes read, the column's declared unit and its values
    as the file holds them."""

    component: str
    setting: str
    file: str
    column: str
    sha256: str
    unit: str | None
    values: Values = field(compare=False)

    def seconds(self) -> Values:
        """The values in SI units: times in seconds, plain numbers as they are."""
        if self.unit is None:
            return self.values
        return self.values * parse_quantity(f"1 {self.unit}", Dimension.TIME).magnitude

    def record(self) -> dict[str, str]:
        """The manifest's ``data_files`` entry of this reference."""
        return {
            "component": self.component,
            "setting": self.setting,
            "file": self.file,
            "column": self.column,
            "sha256": self.sha256,
        }


def _references(model: Model) -> Iterator[tuple[int, Component, str, Distribution]]:
    """Every ``data`` distribution of the model: its component's index, the component, the
    setting and the distribution, in component order and the type's setting order."""
    for index, component in enumerate(model.components):
        for spec in PROCESS_TYPES[component.type].settings:
            value = component.settings.get(spec.name)
            if (
                spec.kind is SettingKind.DISTRIBUTION
                and isinstance(value, Distribution)
                and value.data is not None
            ):
                yield index, component, spec.name, value


def read_columns(
    model: Model, data: DataIndex
) -> tuple[tuple[ColumnSnapshot, ...], tuple[Issue, ...]]:
    """The columns of every ``data`` reference of ``model``, read from the files of
    ``data`` (the project's column index), and the E162 issues of those that cannot be
    read; the model has been validated against the same index."""
    columns: list[ColumnSnapshot] = []
    issues: list[Issue] = []
    files: dict[str, tuple[bytes, str] | None] = {}
    for index, component, setting, distribution in _references(model):
        reference = distribution.data
        assert reference is not None
        at = ("components", index, "params", setting, "data")
        where = f"the '{setting}' setting of '{component.id}'"
        entry = data.file(reference.file)
        if reference.file not in files:
            files[reference.file] = _read_file(data, reference.file)
        read = files[reference.file]
        if entry is None or read is None or read[1] != entry.sha256:
            problem = (
                "is missing from the project's data/ folder"
                if read is None
                else "has changed since it was imported"
            )
            issues.append(
                _issue(
                    component.id,
                    (*at, "file"),
                    f"In {where}, the data file '{reference.file}' {problem}, so the run "
                    "cannot copy its column.",
                    "Import the file again, then start the run again.",
                )
            )
            continue
        column = entry.column(reference.column)
        assert column is not None and column.type == "number"  # validated against `data`
        values = _column_values(read[0], entry.format, reference.column)
        if values is None:  # the bytes hashed as imported, so they read as imported
            issues.append(
                _issue(
                    component.id,
                    (*at, "column"),
                    f"In {where}, the column '{reference.column}' of '{reference.file}' "
                    "cannot be read as numbers.",
                    "Import the file again, then start the run again.",
                )
            )
            continue
        columns.append(
            ColumnSnapshot(
                component.id,
                setting,
                reference.file,
                reference.column,
                read[1],
                column.unit,
                values,
            )
        )
    return tuple(columns), tuple(issues)


def _read_file(data: DataIndex, name: str) -> tuple[bytes, str] | None:
    """The bytes of ``data/<name>`` and their SHA-256, or ``None`` when it cannot be read."""
    assert data.folder is not None  # an index that lists a file has its folder
    try:
        raw = (data.folder / name).read_bytes()
    except OSError:
        return None
    return raw, hashlib.sha256(raw).hexdigest()


def _column_values(raw: bytes, form: str, name: str) -> Values | None:
    try:
        table = read_table(raw, form)
    except UnreadableData:
        return None
    column = next((item for item in table.columns if item.name == name), None)
    if column is None or column.type != "number":
        return None
    return column.values


def _issue(component: str, at: Sequence[str | int], message: str, hint: str) -> Issue:
    return Issue(code="E162", component=component, path=pointer(*at), message=message, hint=hint)


def with_columns(model: Model, columns: Sequence[ColumnSnapshot]) -> Model:
    """``model`` with each read column's values, in seconds, in its distribution's
    ``values``, beside its ``data`` reference."""
    if not columns:
        return model
    by_place: Mapping[tuple[str, str], ColumnSnapshot] = {
        (column.component, column.setting): column for column in columns
    }
    components = []
    for component in model.components:
        settings = dict(component.settings)
        for setting, value in component.settings.items():
            column = by_place.get((component.id, setting))
            if column is not None and isinstance(value, Distribution):
                values = tuple(float(number) for number in column.seconds())
                settings[setting] = dataclasses.replace(value, values=values)
        components.append(dataclasses.replace(component, settings=settings))
    return dataclasses.replace(model, components=tuple(components))


def write_snapshots(folder: Path, columns: Sequence[ColumnSnapshot]) -> None:
    """Writes each column to ``folder/data/<component>.<setting>.parquet``; nothing, and
    no ``data/``, when there are none."""
    if not columns:
        return
    target = folder / DATA_FOLDER
    target.mkdir(parents=True, exist_ok=True)
    for column in columns:
        unit = column.unit if column.unit is not None else _NO_UNIT
        table = pa.table(
            {
                "value": pa.array(column.values, type=pa.float64()),
                "unit": pa.array([unit] * len(column.values), type=pa.string()),
            }
        )
        pq.write_table(table, target / snapshot_name(column.component, column.setting))


def read_snapshot(path: Path) -> tuple[Values, str | None]:
    """The values and the declared unit (``None`` for plain numbers) of a snapshot."""
    table = pq.read_table(path)
    values = numpy.asarray(table.column("value").to_numpy(), dtype=numpy.float64)
    units = set(table.column("unit").to_pylist())
    unit = units.pop() if units else _NO_UNIT
    return values, None if unit == _NO_UNIT else str(unit)
