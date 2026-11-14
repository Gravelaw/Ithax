"""Every scenario and replication, in this process or in worker processes (spec 1
"Division of labour" and "Engine adapter interface"; AKS-98).

Results do not depend on ``workers``; ``cancel`` stops a long run quickly, also while
workers run; progress reports a fraction and "Scenario 1 of 2, replication 12 of 30".
"""

import multiprocessing
import re
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from conftest import ModelMaker, line

from ithax.engines.adapter import Progress
from ithax.engines.process.runner import (
    REPLICATIONS_SCHEMA,
    init_worker,
    replications_table,
    run_all,
    run_task,
    timeseries_table,
    write_table,
)
from ithax.engines.process.translate import read_input, write_input

MESSAGE = re.compile(r"Scenario (\d+) of (\d+), replication (\d+) of (\d+)")


def two_scenarios(make_model: ModelMaker, workdir: Path, length: str = "2 h") -> dict[str, Any]:
    components, connections = line(
        {"dist": "exponential", "mean": "2 min"},
        {"dist": "exponential", "mean": "1.5 min"},
        capacity={"$param": "tills"},
    )
    model = make_model(
        components,
        connections,
        length=length,
        warmup="10 min",
        replications=3,
        seed=2024,
        parameters={"tills": {"value": 1, "type": "integer"}},
        scenarios=[{"id": "one", "set": {}}, {"id": "two", "set": {"tills": 2}}],
    )
    write_input(model, "e", workdir)
    return read_input(workdir)


def test_results_do_not_depend_on_workers(make_model: ModelMaker, tmp_path: Path) -> None:
    engine = two_scenarios(make_model, tmp_path)
    serial = run_all(tmp_path, engine, lambda progress: None, threading.Event(), 1)
    parallel = run_all(tmp_path, engine, lambda progress: None, threading.Event(), 2)
    assert serial is not None and parallel is not None
    assert serial == parallel
    assert sorted(serial) == [(s, r) for s in range(2) for r in range(3)]
    assert replications_table(engine, serial).equals(replications_table(engine, parallel))
    assert timeseries_table(engine, serial).equals(timeseries_table(engine, parallel))


@pytest.mark.parametrize("workers", [1, 2])
def test_progress_counts_each_finished_replication(
    make_model: ModelMaker, tmp_path: Path, workers: int
) -> None:
    engine = two_scenarios(make_model, tmp_path, length="30 min")
    reports: list[Progress] = []
    assert run_all(tmp_path, engine, reports.append, threading.Event(), workers) is not None
    assert [report.fraction for report in reports] == [n / 6 for n in range(1, 7)]
    finished = set()
    for report in reports:
        match = MESSAGE.fullmatch(report.message)
        assert match is not None, report.message
        scenario, scenarios, replication, replications = map(int, match.groups())
        assert (scenarios, replications) == (2, 3)
        finished.add((scenario, replication))
    assert finished == {(s, r) for s in (1, 2) for r in (1, 2, 3)}
    if workers == 1:
        assert reports[0].message == "Scenario 1 of 2, replication 1 of 3"
        assert reports[-1].message == "Scenario 2 of 2, replication 3 of 3"


@pytest.mark.parametrize("workers", [1, 2])
def test_a_cancel_set_before_the_run_runs_nothing(
    make_model: ModelMaker, tmp_path: Path, workers: int
) -> None:
    engine = two_scenarios(make_model, tmp_path)
    cancel = threading.Event()
    cancel.set()
    reports: list[Progress] = []
    assert run_all(tmp_path, engine, reports.append, cancel, workers) is None
    assert reports == []


@pytest.mark.parametrize(("workers", "after"), [(1, 0.3), (2, 1.0)])
def test_cancel_stops_a_long_run_quickly(
    make_model: ModelMaker, tmp_path: Path, workers: int, after: float
) -> None:
    """Two scenarios of three replications of 10,000 h would take minutes; the run stops
    within a second of the cancel, also while worker processes run replications (they
    start in under a second here)."""
    engine = two_scenarios(make_model, tmp_path, length="10000 h")
    cancel = multiprocessing.Event()
    timer = threading.Timer(after, cancel.set)
    started = time.monotonic()
    timer.start()
    try:
        assert run_all(tmp_path, engine, lambda progress: None, cancel, workers) is None
    finally:
        timer.cancel()
    assert time.monotonic() - started < after + 1.0


def test_workers_below_one_are_refused(make_model: ModelMaker, tmp_path: Path) -> None:
    engine = two_scenarios(make_model, tmp_path)
    with pytest.raises(ValueError, match="workers 0"):
        run_all(tmp_path, engine, lambda progress: None, threading.Event(), 0)


def test_a_worker_reads_the_input_once_and_runs_pairs(
    make_model: ModelMaker, tmp_path: Path
) -> None:
    """The functions a worker process runs, called here so that they are measured."""
    engine = two_scenarios(make_model, tmp_path, length="30 min")
    stop = multiprocessing.get_context("spawn").Event()
    init_worker(str(tmp_path), stop)
    serial = run_all(tmp_path, engine, lambda progress: None, threading.Event(), 1)
    assert serial is not None
    assert run_task(1, 2) == serial[(1, 2)]
    stop.set()
    assert run_task(0, 0) is None


def test_the_table_has_the_spec_columns_in_scenario_and_replication_order(
    make_model: ModelMaker, tmp_path: Path
) -> None:
    engine = two_scenarios(make_model, tmp_path, length="30 min")
    done = run_all(tmp_path, engine, lambda progress: None, threading.Event(), 1)
    assert done is not None
    shuffled = dict(reversed(list(done.items())))
    table = replications_table(engine, shuffled)
    assert table.schema == REPLICATIONS_SCHEMA
    assert table.schema.names == ["scenario", "replication", "metric", "value", "unit"]
    assert table.num_rows == 6 * 12
    keys = list(zip(table["scenario"].to_pylist(), table["replication"].to_pylist(), strict=True))
    assert keys == sorted(keys, key=lambda key: (["one", "two"].index(key[0]), key[1]))
    assert keys[0] == ("one", 0) and keys[-1] == ("two", 2)
    path = tmp_path / "output" / "replications.parquet"
    write_table(table, path)
    assert sorted(item.name for item in path.parent.iterdir()) == ["replications.parquet"]
