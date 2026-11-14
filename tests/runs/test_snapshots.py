"""``empirical`` with ``data`` in a run (spec 1 "Distributions", "Run folder and results";
build guide known gap "`empirical` with `data` has never run"; AKS-113).

A run created with the project's column index reads every ``data`` reference from the bytes
of its file (hashed again, E162 when changed), copies the column to
``runs/<run_id>/data/<component id>.<setting>.parquet`` and records each reference in the
manifest's ``data_files``; the engine samples the copied values through the component's
stream. The sampling test of spec 1 runs here against the copied column's mean and
population sd.
"""

import dataclasses
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy
import pyarrow.parquet as pq
import pytest

from ithax.model.data import (
    EMPTY_DATA_INDEX,
    INDEX_FILE,
    DataIndex,
    index_bytes,
    new_entry,
    read_data_index,
)
from ithax.model.data_files import UnreadableData, read_table
from ithax.model.distributions import sampler_for
from ithax.model.loading import load_text
from ithax.model.model import Distribution
from ithax.model.streams import generator_for
from ithax.runs import snapshots
from ithax.runs.manifest import read_manifest
from ithax.runs.snapshots import DATA_FOLDER, read_snapshot, snapshot_name
from ithax.runs.targets import LocalTarget, RunRefused

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = 20_000


def shop(service: Any) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((ROOT / "examples" / "coffee_shop.json").read_text())
    document["experiments"][0].update(length="2 h", warmup="0 s", replications=2)
    document["components"][1]["params"]["service"] = service
    return document


def breakdown() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (ROOT / "benchmarks" / "failure" / "model.json").read_text()
    )
    document["experiments"][0].update(length="4 h", warmup="0 s", replications=2)
    params = document["components"][2]["params"]
    params["time_to_failure"] = {
        "dist": "empirical",
        "data": {"file": "repairs.csv", "column": "up_h"},
    }
    params["time_to_repair"] = {
        "dist": "empirical",
        "data": {"file": "repairs.csv", "column": "down_min"},
    }
    return document


def data_ref(file: str, column: str) -> dict[str, Any]:
    return {"dist": "empirical", "data": {"file": file, "column": column}}


def imported(folder: Path, name: str, text: str, units: dict[str, str | None]) -> DataIndex:
    """Imports ``text`` as ``data/<name>`` (the file and its index entry), as the import
    endpoint does, and returns the index read back."""
    data = folder / "data"
    data.mkdir(parents=True, exist_ok=True)
    raw = text.encode("utf-8")
    (data / name).write_bytes(raw)
    current = read_data_index(data)
    entry = new_entry(name, raw, read_table(raw, "csv"), units, "2026-11-07T10:00:00.000Z")
    files = {**current.files, name: entry}
    (data / INDEX_FILE).write_bytes(index_bytes(files.values()))
    return read_data_index(data)


def minutes_column(count: int = 400) -> str:
    rng = numpy.random.default_rng(3)  # test data only; the product never draws from it
    values = rng.exponential(1.5, count).round(3)
    return "minutes,note\n" + "".join(f"{value},x\n" for value in values) + ",\n"


def target(tmp_path: Path, data: DataIndex) -> LocalTarget:
    return LocalTarget(tmp_path / "runs", data=data)


def file_bytes(document: dict[str, Any]) -> bytes:
    return json.dumps(document).encode("utf-8")


# --- the snapshot and the manifest -----------------------------------------------------


def test_a_run_copies_the_column_and_records_the_reference(tmp_path: Path) -> None:
    data = imported(tmp_path, "times.csv", minutes_column(), {"minutes": "min"})
    run = target(tmp_path, data).create(file_bytes(shop(data_ref("times.csv", "minutes"))), "base")
    snapshot = run.folder / DATA_FOLDER / "till.service.parquet"
    assert snapshot_name("till", "service") == "till.service.parquet"
    table = pq.read_table(snapshot)
    assert table.column_names == ["value", "unit"]
    assert str(table.schema.field("value").type) == "double"
    source = read_table((tmp_path / "data" / "times.csv").read_bytes(), "csv")
    assert table.column("value").to_pylist() == list(source.columns[0].values)
    assert set(table.column("unit").to_pylist()) == {"min"}
    raw = (tmp_path / "data" / "times.csv").read_bytes()
    assert read_manifest(run.folder)["data_files"] == [
        {
            "component": "till",
            "setting": "service",
            "file": "times.csv",
            "column": "minutes",
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    ]
    values, unit = read_snapshot(snapshot)
    assert unit == "min" and list(values) == list(source.columns[0].values)


def test_a_run_without_data_has_no_data_folder_and_no_data_files(tmp_path: Path) -> None:
    document = shop({"dist": "exponential", "mean": "1.5 min"})
    run = target(tmp_path, EMPTY_DATA_INDEX).create(file_bytes(document), "base")
    assert not (run.folder / DATA_FOLDER).exists()
    assert read_manifest(run.folder)["data_files"] == []


def test_a_column_without_a_unit_is_written_with_unit_one(tmp_path: Path) -> None:
    data = imported(tmp_path, "n.csv", "n\n1\n2\n", {})
    snapshot = snapshots.ColumnSnapshot(
        component="c",
        setting="s",
        file="n.csv",
        column="n",
        sha256="0" * 64,
        unit=None,
        values=numpy.array([1.0, 2.0]),
    )
    assert data.file("n.csv") is not None
    snapshots.write_snapshots(tmp_path / "run", (snapshot,))
    values, unit = read_snapshot(tmp_path / "run" / DATA_FOLDER / "c.s.parquet")
    assert unit is None and list(values) == [1.0, 2.0]
    assert list(snapshot.seconds()) == [1.0, 2.0]


# --- the sampling test (spec 1 "Distributions"; build guide known gap) ------------------


def test_empirical_with_data_passes_the_sampling_test_against_the_copied_column(
    tmp_path: Path,
) -> None:
    data = imported(tmp_path, "times.csv", minutes_column(), {"minutes": "min"})
    document = shop(data_ref("times.csv", "minutes"))
    run = target(tmp_path, data).create(file_bytes(document), "base")
    values, unit = read_snapshot(run.folder / DATA_FOLDER / "till.service.parquet")
    assert unit == "min"
    copied = values * 60.0  # the column in seconds
    mean, sd = float(copied.mean()), float(copied.std())  # population sd (ddof 0)
    assert sd > 0
    service = run.model.components[1].settings["service"]
    assert isinstance(service, Distribution) and service.data is not None
    sampler = sampler_for(run.model, service)
    rng = generator_for(12345, 0, "till")  # one stream of the spec 1 scheme
    drawn = numpy.array([sampler(rng) for _ in range(SAMPLES)])
    standard_error = sd / math.sqrt(SAMPLES)
    assert abs(drawn.mean() - mean) < 4 * standard_error
    # Every sample is one of the copied values (equal probability, with replacement).
    assert set(drawn.tolist()) <= set(copied.tolist())


# --- two data-driven distributions on one component ---------------------------------------


def repairs() -> str:
    rows = [(1.5, 20), (2.0, 35), (0.75, 10), (3.0, 25), (1.25, 30)]
    return "up_h,down_min\n" + "".join(f"{up},{down}\n" for up, down in rows)


def test_a_failure_block_with_both_times_from_data_keeps_both_snapshots(tmp_path: Path) -> None:
    data = imported(tmp_path, "repairs.csv", repairs(), {"up_h": "h", "down_min": "min"})
    run = target(tmp_path, data).create(file_bytes(breakdown()), "benchmark")
    folder = run.folder / DATA_FOLDER
    assert sorted(path.name for path in folder.iterdir()) == [
        "breakdown.time_to_failure.parquet",
        "breakdown.time_to_repair.parquet",
    ]
    up, up_unit = read_snapshot(folder / "breakdown.time_to_failure.parquet")
    down, down_unit = read_snapshot(folder / "breakdown.time_to_repair.parquet")
    assert (list(up), up_unit) == ([1.5, 2.0, 0.75, 3.0, 1.25], "h")
    assert (list(down), down_unit) == ([20.0, 35.0, 10.0, 25.0, 30.0], "min")
    entries = read_manifest(run.folder)["data_files"]
    assert [(entry["setting"], entry["column"]) for entry in entries] == [
        ("time_to_failure", "up_h"),
        ("time_to_repair", "down_min"),
    ]
    assert {entry["file"] for entry in entries} == {"repairs.csv"}
    run.execute()
    assert run.state == "done", (run.folder / "log.txt").read_text()
    engine_input = json.loads((run.folder / "engine" / "input.json").read_text())
    settings = engine_input["scenarios"][0]["components"][2]["settings"]
    assert settings["time_to_failure"] == {
        "dist": "empirical",
        "values": [5400.0, 7200.0, 2700.0, 10800.0, 4500.0],
    }
    assert settings["time_to_repair"] == {
        "dist": "empirical",
        "values": [1200.0, 2100.0, 600.0, 1500.0, 1800.0],
    }


def test_two_runs_of_one_data_model_are_identical(tmp_path: Path) -> None:
    data = imported(tmp_path, "repairs.csv", repairs(), {"up_h": "h", "down_min": "min"})
    local = target(tmp_path, data)
    first = local.create(file_bytes(breakdown()), "benchmark")
    second = local.create(file_bytes(breakdown()), "benchmark")
    for run in (first, second):
        run.execute()
        assert run.state == "done"
    for name in ("summary.json",):
        assert (first.folder / name).read_bytes() == (second.folder / name).read_bytes()
    for name in ("breakdown.time_to_failure.parquet", "breakdown.time_to_repair.parquet"):
        assert pq.read_table(first.folder / DATA_FOLDER / name).equals(
            pq.read_table(second.folder / DATA_FOLDER / name)
        )


# --- E162 --------------------------------------------------------------------------------


def refused(local: LocalTarget, document: dict[str, Any], experiment: str = "base") -> RunRefused:
    with pytest.raises(RunRefused) as caught:
        local.create(file_bytes(document), experiment)
    return caught.value


def test_a_changed_file_is_e162_for_validation_and_for_a_run(tmp_path: Path) -> None:
    data = imported(tmp_path, "times.csv", minutes_column(), {"minutes": "min"})
    document = shop(data_ref("times.csv", "minutes"))
    assert load_text(file_bytes(document), data=data).model is not None
    with (tmp_path / "data" / "times.csv").open("a", encoding="utf-8") as handle:
        handle.write("9.0,y\n")
    issues = load_text(file_bytes(document), data=data).issues
    assert [(issue.code, issue.path) for issue in issues] == [
        ("E162", "/components/1/params/service/data/file")
    ]
    problem = refused(target(tmp_path, data), document)
    assert [issue.code for issue in problem.issues] == ["E162"]
    assert not (tmp_path / "runs").exists() or not list((tmp_path / "runs").iterdir())


def test_a_file_that_changes_after_validation_is_e162_and_creates_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The column is read from bytes hashed afresh, so a file replaced between the check and
    the copy is never copied under the old hash."""
    data = imported(tmp_path, "times.csv", minutes_column(), {"minutes": "min"})
    recorded = data.files["times.csv"].sha256
    (tmp_path / "data" / "times.csv").write_text("minutes,note\n1,x\n", encoding="utf-8")
    monkeypatch.setattr(DataIndex, "current_sha256", lambda self, name: recorded)
    problem = refused(target(tmp_path, data), shop(data_ref("times.csv", "minutes")))
    assert [(issue.code, issue.path) for issue in problem.issues] == [
        ("E162", "/components/1/params/service/data/file")
    ]
    assert "changed" in problem.issues[0].message
    runs = tmp_path / "runs"
    assert not runs.exists() or not list(runs.iterdir())


def test_a_file_that_disappears_before_the_copy_is_e162(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = imported(tmp_path, "times.csv", minutes_column(), {"minutes": "min"})
    recorded = data.files["times.csv"].sha256
    (tmp_path / "data" / "times.csv").unlink()
    monkeypatch.setattr(DataIndex, "current_sha256", lambda self, name: recorded)
    problem = refused(target(tmp_path, data), shop(data_ref("times.csv", "minutes")))
    assert [issue.code for issue in problem.issues] == ["E162"]
    assert "missing" in problem.issues[0].message


def test_without_the_index_every_data_reference_is_refused(tmp_path: Path) -> None:
    imported(tmp_path, "times.csv", minutes_column(), {"minutes": "min"})
    problem = refused(target(tmp_path, EMPTY_DATA_INDEX), shop(data_ref("times.csv", "minutes")))
    assert [issue.code for issue in problem.issues] == ["E162"]


def test_a_column_without_a_unit_cannot_feed_a_time(tmp_path: Path) -> None:
    data = imported(tmp_path, "times.csv", minutes_column(), {})
    problem = refused(target(tmp_path, data), shop(data_ref("times.csv", "minutes")))
    assert [(issue.code, issue.path) for issue in problem.issues] == [
        ("E162", "/components/1/params/service/data/column")
    ]
    built = load_text(file_bytes(shop(data_ref("times.csv", "note"))), data=data)
    assert [issue.code for issue in built.issues] == ["E162"]


@pytest.mark.parametrize("reading", ["unreadable", "text"])
def test_a_column_that_no_longer_reads_as_numbers_is_e162(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reading: str
) -> None:
    """The bytes hashed as imported read as imported; were the reader to change, the run
    is refused rather than copying something else."""
    data = imported(tmp_path, "times.csv", minutes_column(), {"minutes": "min"})

    def read_table_now(raw: bytes, form: str) -> Any:
        if reading == "unreadable":
            raise UnreadableData("unreadable", "hint")
        return read_table(b"minutes\nx\n", form)

    monkeypatch.setattr(snapshots, "read_table", read_table_now)
    problem = refused(target(tmp_path, data), shop(data_ref("times.csv", "minutes")))
    assert [(issue.code, issue.path) for issue in problem.issues] == [
        ("E162", "/components/1/params/service/data/column")
    ]


def test_values_that_overflow_in_seconds_are_refused_even_when_the_index_says_otherwise(
    tmp_path: Path,
) -> None:
    """A run checks the values it copies, not only the index's largest value, so an index
    edited by hand cannot let an infinite time into a run (Codex on PR #37)."""
    data = imported(tmp_path, "times.csv", "minutes\n1\n1e308\n", {"minutes": "min"})
    entry = data.files["times.csv"]
    column = dataclasses.replace(entry.columns[0], largest=1.0)
    edited = dataclasses.replace(entry, columns=(column,))
    (tmp_path / "data" / INDEX_FILE).write_bytes(index_bytes([edited]))
    problem = refused(
        target(tmp_path, read_data_index(tmp_path / "data")), shop(data_ref("times.csv", "minutes"))
    )
    assert [(issue.code, issue.path) for issue in problem.issues] == [
        ("E162", "/components/1/params/service/data/column")
    ]
    assert "seconds" in problem.issues[0].message
    runs = tmp_path / "runs"
    assert not runs.exists() or not list(runs.iterdir())
