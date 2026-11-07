"""Comparing two runs as spec 1 "Identical runs" defines it (AKS-104).

"Identical means: `summary.json` metrics equal to full floating-point precision, every
table under `tables/` equal row for row, and `model.json` byte-equal. `manifest.json` may
differ only in `run_id`, `created`, `started`, `ended`, `host`."

Tables are compared as Arrow tables, not as file bytes (byte-identical Parquet was dropped
as a property of the writer, not of the product; docs/DECISIONS.md). ``pyarrow``'s
``Table.equals`` treats NaN as unequal to itself, and a `replications` table holds NaN for
a mean over no items (spec 1 "Tables for the `process` domain"), so float cells are
compared by ``float.hex``: exact to the last bit, NaN equal to NaN, and 0.0 apart from
-0.0.
"""

import json
import math
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

#: The manifest fields spec 1 lets two identical runs differ in.
MAY_DIFFER = frozenset({"run_id", "created", "started", "ended", "host"})


def cell_key(value: object) -> object:
    """A cell as compared: a float by its exact hex form (NaN equal to NaN), else as is."""
    if isinstance(value, float):
        return float.hex(value)
    return value


def table_rows(table: Any) -> list[tuple[object, ...]]:
    """An Arrow table's rows, in order, with float cells as ``cell_key`` gives them."""
    columns = [table.column(name).to_pylist() for name in table.column_names]
    return [tuple(cell_key(value) for value in row) for row in zip(*columns, strict=True)]


def tables_equal(first: Any, second: Any) -> bool:
    """Two Arrow tables equal row for row: the same schema (names, types and order) and
    the same rows in the same order, float cells exact and NaN-aware."""
    return bool(first.schema.equals(second.schema)) and table_rows(first) == table_rows(second)


def has_nan(table: Any) -> bool:
    """Whether any float cell of an Arrow table is NaN."""
    return any(
        isinstance(value, float) and math.isnan(value)
        for name in table.column_names
        for value in table.column(name).to_pylist()
    )


def read_table(path: Path) -> Any:
    """A Parquet file as an Arrow table."""
    return pq.read_table(path)


def read_tables(folder: Path) -> dict[str, Any]:
    """Every table under a run folder's ``tables/``, by file name."""
    return {path.name: read_table(path) for path in sorted((folder / "tables").iterdir())}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def summary_metrics(folder: Path) -> dict[str, Any]:
    """Each scenario's ``metrics`` from a run's ``summary.json``, by scenario id."""
    summary = read_json(folder / "summary.json")
    return {scenario: entry["metrics"] for scenario, entry in summary["scenarios"].items()}


def manifest_differences(first: Path, second: Path) -> set[str]:
    """The manifest fields whose values differ between two run folders, keys present in
    only one manifest included."""
    one = read_json(first / "manifest.json")
    two = read_json(second / "manifest.json")
    return {key for key in one.keys() | two.keys() if one.get(key, ...) != two.get(key, ...)}


def identical_differences(first: Path, second: Path) -> list[str]:
    """What keeps two run folders from being identical as spec 1 defines it; empty when
    they are identical."""
    problems: list[str] = []
    if summary_metrics(first) != summary_metrics(second):
        problems.append("summary.json metrics differ")
    tables_one, tables_two = read_tables(first), read_tables(second)
    if tables_one.keys() != tables_two.keys():
        problems.append(f"tables/ differ: {sorted(tables_one)} and {sorted(tables_two)}")
    for name in sorted(tables_one.keys() & tables_two.keys()):
        if not tables_equal(tables_one[name], tables_two[name]):
            problems.append(f"tables/{name} differs")
    if (first / "model.json").read_bytes() != (second / "model.json").read_bytes():
        problems.append("model.json differs")
    unexpected = manifest_differences(first, second) - MAY_DIFFER
    if unexpected:
        problems.append(f"manifest.json differs in {sorted(unexpected)}")
    return problems
