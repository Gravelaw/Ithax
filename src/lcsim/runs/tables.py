"""Writing ``summary.json`` and ``tables/*.parquet`` into a folder (spec 1 "Run folder and
results" and "Tables for the ``process`` domain"; AKS-102).

The folder is the run folder ``runs/<run_id>/``, which the run target (AKS-103) chooses;
nothing here knows about it. Each file is written with ``lcsim.files``, so a reader never
sees half a file.

- ``tables/<name>.parquet``: only the names spec 1 lists (``replications``,
  ``timeseries``; ``GET .../tables/{name}`` accepts only these). Units are a column, not
  Parquet metadata: a table must have a ``unit`` column, and any schema metadata is
  dropped.
- ``summary.json``: UTF-8 JSON, indented, with a final newline. NaN and infinities are
  refused (``ValueError``), since JSON has neither; an undefined value is ``null``.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from lcsim.engines.adapter import Table
from lcsim.files import atomic_write, atomic_write_with
from lcsim.strict_json import encode_json

__all__ = ["SUMMARY_FILE", "TABLES_FOLDER", "TABLE_NAMES", "write_summary", "write_tables"]

#: Spec 1 "Run folder and results": the tables a run folder may hold.
TABLE_NAMES = ("replications", "timeseries")
#: The tables' folder inside the run folder.
TABLES_FOLDER = "tables"
#: The summary's file name inside the run folder.
SUMMARY_FILE = "summary.json"


def write_tables(tables: Mapping[str, Table], folder: Path) -> list[Path]:
    """Writes each table to ``folder/tables/<name>.parquet`` and returns the paths, in the
    order of ``tables``. A name spec 1 does not list, or a table with no ``unit`` column,
    raises ``ValueError`` before anything is written."""
    for name, table in tables.items():
        if name not in TABLE_NAMES:
            raise ValueError(f"{name!r} is not a table spec 1 names ({', '.join(TABLE_NAMES)})")
        if "unit" not in table.column_names:
            raise ValueError(f"table {name!r} has no 'unit' column")
    paths: list[Path] = []
    for name, table in tables.items():
        path = folder / TABLES_FOLDER / f"{name}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        plain = table.replace_schema_metadata(None)
        atomic_write_with(path, partial(pq.write_table, plain))
        paths.append(path)
    return paths


def write_summary(summary: Mapping[str, Any], folder: Path) -> Path:
    """Writes ``summary`` to ``folder/summary.json`` and returns the path."""
    data = encode_json(summary)
    path = folder / SUMMARY_FILE
    folder.mkdir(parents=True, exist_ok=True)
    atomic_write(path, data)
    return path
