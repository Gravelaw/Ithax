"""Writing ``summary.json`` and ``tables/*.parquet`` (spec 1 "Run folder and results" and
"Tables for the process domain"; AKS-102): ``lcsim.runs.tables``."""

import json
import math
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from lcsim.runs.tables import TABLE_NAMES, write_summary, write_tables


def table() -> pa.Table:
    return pa.table(
        {
            "scenario": ["default", "default"],
            "replication": pa.array([0, 1], pa.int64()),
            "metric": ["till.wait.mean", "till.wait.mean"],
            "value": [250.0, math.nan],
            "unit": ["s", "s"],
        }
    )


def test_the_table_names_are_spec_1s() -> None:
    assert TABLE_NAMES == ("replications", "timeseries")


def test_tables_are_written_with_units_as_a_column(tmp_path: Path) -> None:
    source = table().replace_schema_metadata({b"unit": b"s"})
    paths = write_tables({"replications": source, "timeseries": source}, tmp_path)
    assert paths == [
        tmp_path / "tables" / "replications.parquet",
        tmp_path / "tables" / "timeseries.parquet",
    ]
    read = pq.read_table(paths[0])
    assert read.column("unit").to_pylist() == ["s", "s"]
    # Units are a column, not Parquet metadata.
    assert read.schema.metadata is None
    assert read.schema.equals(table().schema)
    for name in ("scenario", "replication", "metric", "unit"):
        assert read.column(name).equals(table().column(name))
    value = read.column("value").to_pylist()
    assert value[0] == 250.0 and math.isnan(value[1])  # NaN != NaN, so not Table.equals
    assert sorted(path.name for path in (tmp_path / "tables").iterdir()) == [
        "replications.parquet",
        "timeseries.parquet",
    ]


def test_no_tables_write_nothing(tmp_path: Path) -> None:
    assert write_tables({}, tmp_path) == []
    assert not (tmp_path / "tables").exists()


def test_an_unknown_table_name_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="'events' is not a table spec 1 names"):
        write_tables({"events": table()}, tmp_path)
    assert not (tmp_path / "tables").exists()


def test_a_table_without_a_unit_column_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="'replications' has no 'unit' column"):
        write_tables({"replications": table().drop_columns(["unit"])}, tmp_path)


def test_summary_json_is_written_as_utf8_json(tmp_path: Path) -> None:
    summary: dict[str, Any] = {
        "model": "Café",
        "scenarios": {"default": {"metrics": {}}},
        "x": None,
    }
    path = write_summary(summary, tmp_path)
    assert path == tmp_path / "summary.json"
    text = path.read_text(encoding="utf-8")
    assert json.loads(text) == summary
    assert "Café" in text and text.endswith("}\n")
    assert not list(tmp_path.glob("*.partial"))


def test_summary_json_refuses_nan(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Out of range float"):
        write_summary({"mean": math.nan}, tmp_path)
    assert not (tmp_path / "summary.json").exists()
