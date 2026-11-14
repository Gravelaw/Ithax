"""The registered process adapter (AKS-97, AKS-98).

Its name and version, its engine-specific checks (none yet: codes E300 to E399 are
reserved for them), and ``translate``, ``run`` and ``collect`` end to end: the coffee shop
in a temporary workdir, the ``replications`` and ``timeseries`` tables of spec 1, nothing
written outside ``workdir``, and nothing written by a cancelled run.
"""

import copy
import json
import math
import statistics
import threading
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

import ithax
from ithax.engines.adapter import Progress
from ithax.engines.process.adapter import REPLICATIONS_FILE, TIMESERIES_FILE, ProcessAdapter
from ithax.model.loading import load_document
from ithax.model.model import Model

ROOT = Path(__file__).resolve().parents[3]


def coffee_shop() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (ROOT / "examples" / "coffee_shop.json").read_text(encoding="utf-8")
    )
    return document


def load(document: object) -> Model:
    model = load_document(document).model
    assert model is not None
    return model


def test_the_adapter_is_named_simpy_with_the_product_version() -> None:
    adapter = ProcessAdapter()
    assert adapter.name == "simpy"
    assert adapter.version == ithax.__version__


def test_validate_adds_no_issue_to_a_valid_model() -> None:
    assert ProcessAdapter().validate(load(coffee_shop())) == []


def test_the_coffee_shop_runs_end_to_end(tmp_path: Path) -> None:
    """30 replications of 200 h with 10 h of warm-up, as the file says. Theory (M/M/1,
    arrivals every 2 min, service 1.5 min): wait 270 s, utilization 0.75, queue length
    2.25, cycle time 360 s, throughput 1/120 per second, work in progress 3."""
    adapter = ProcessAdapter()
    workdir = tmp_path / "runs" / "r1" / "engine"
    adapter.translate(load(coffee_shop()), "base", workdir)
    reports: list[Progress] = []
    adapter.run(workdir, reports.append, threading.Event(), 2)
    results = adapter.collect(workdir)

    assert list(results.tables) == ["replications", "timeseries"]
    assert results.warnings == []
    assert results.solution is None
    table = results.tables["replications"]
    assert table.schema == pa.schema(
        [
            ("scenario", pa.string()),
            ("replication", pa.int64()),
            ("metric", pa.string()),
            ("value", pa.float64()),
            ("unit", pa.string()),
        ]
    )
    assert table.num_rows == 30 * 12
    assert set(table["scenario"].to_pylist()) == {"default"}
    assert sorted(set(table["replication"].to_pylist())) == list(range(30))
    assert len(reports) == 30 and reports[-1].fraction == 1.0

    rows = table.to_pylist()
    means = {
        metric: statistics.fmean(row["value"] for row in rows if row["metric"] == metric)
        for metric in {row["metric"] for row in rows}
    }
    units = {row["metric"]: row["unit"] for row in rows}
    assert means["till.utilization"] == pytest.approx(0.75, abs=0.02)
    assert means["till.wait.mean"] == pytest.approx(270.0, rel=0.15)
    assert means["till.queue_length.mean"] == pytest.approx(2.25, rel=0.15)
    assert means["exit.cycle_time.mean"] == pytest.approx(360.0, rel=0.15)
    assert means["exit.throughput"] == pytest.approx(1 / 120, rel=0.02)
    assert means["model.wip.mean"] == pytest.approx(3.0, rel=0.15)
    assert means["arrivals.created"] == pytest.approx(190 * 30, rel=0.02)
    assert means["arrivals.discarded"] == 0.0
    assert units["till.wait.mean"] == "s" and units["exit.throughput"] == "1/s"
    assert units["till.utilization"] == "1"
    assert all(math.isfinite(row["value"]) for row in rows)

    series = results.tables["timeseries"]
    assert series.schema.names == ["scenario", "replication", "metric", "time_s", "value", "unit"]
    assert series.num_rows == 30 * 3 * 200
    assert sorted(set(series["metric"].to_pylist())) == [
        "model.wip",
        "till.queue_length",
        "till.utilization",
    ]
    assert sorted(set(series["time_s"].to_pylist())) == [3600.0 * k for k in range(200)]

    files = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    assert files == [
        "runs",
        "runs/r1",
        "runs/r1/engine",
        "runs/r1/engine/input.json",
        "runs/r1/engine/output",
        "runs/r1/engine/output/replications.parquet",
        "runs/r1/engine/output/timeseries.parquet",
    ]


def short_run(tmp_path: Path) -> tuple[ProcessAdapter, Path]:
    document = copy.deepcopy(coffee_shop())
    document["experiments"][0].update({"length": "5 h", "warmup": "30 min", "replications": 3})
    adapter = ProcessAdapter()
    adapter.translate(load(document), "base", tmp_path)
    return adapter, tmp_path


def test_a_repeat_run_gives_an_equal_table(tmp_path: Path) -> None:
    adapter, workdir = short_run(tmp_path)
    adapter.run(workdir, lambda progress: None, threading.Event(), 1)
    first = adapter.collect(workdir).tables
    adapter.run(workdir, lambda progress: None, threading.Event(), 1)
    second = adapter.collect(workdir).tables
    assert second["replications"].equals(first["replications"])
    assert second["timeseries"].equals(first["timeseries"])


def test_a_cancelled_run_leaves_no_table(tmp_path: Path) -> None:
    adapter, workdir = short_run(tmp_path)
    adapter.run(workdir, lambda progress: None, threading.Event(), 1)
    assert (workdir / REPLICATIONS_FILE).is_file() and (workdir / TIMESERIES_FILE).is_file()
    cancel = threading.Event()
    cancel.set()
    adapter.run(workdir, lambda progress: None, cancel, 1)
    # The earlier tables are gone too.
    assert not (workdir / REPLICATIONS_FILE).exists()
    assert not (workdir / TIMESERIES_FILE).exists()
    with pytest.raises(FileNotFoundError):
        adapter.collect(workdir)


def test_translate_needs_an_experiment_id(tmp_path: Path) -> None:
    # Only an optimization model is translated without one (AKS-108).
    with pytest.raises(ValueError, match="none was given"):
        ProcessAdapter().translate(load(coffee_shop()), None, tmp_path)
    assert not (tmp_path / "input.json").exists()
