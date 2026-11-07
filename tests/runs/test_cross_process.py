"""Spec 1 acceptance (M3): "Two separately started worker processes produce `replications`
tables equal row for row for the same model and seed" (AKS-104).

Two run folders are prepared from the same model file (created by the local target, the
process adapter's input translated into each ``engine/``). Then two workers are started as
separate operating-system processes with ``python -m lcsim.runs.worker`` (spec 1 "Run
targets"), at the same time, from different working directories, with different
``PYTHONHASHSEED`` values (spec 1 "Random streams" forbids the salted ``hash()``), and with
``--workers 1`` and ``--workers 2``, so that the result is shown not to depend on the
process layout. Their ``engine/output/replications.parquet`` tables must be equal row for
row, and equal to the ``tables/replications.parquet`` of a run made through
``LocalTarget.execute``.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from run_comparison import read_table, tables_equal

from lcsim.engines.process.adapter import REPLICATIONS_FILE, TIMESERIES_FILE, ProcessAdapter
from lcsim.model.loading import load_text
from lcsim.runs.targets import LocalTarget
from lcsim.runs.worker import EXIT_DONE

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def model_file() -> bytes:
    """The coffee shop, 6 replications of 50 h after 5 h of warm-up, with two scenarios."""
    document: dict[str, Any] = json.loads(
        (EXAMPLES / "coffee_shop.json").read_text(encoding="utf-8")
    )
    document["experiments"][0].update(
        {
            "length": "50 h",
            "warmup": "5 h",
            "replications": 6,
            "scenarios": [{"id": "one_till", "set": {}}, {"id": "two_tills", "set": {"tills": 2}}],
        }
    )
    return json.dumps(document).encode("utf-8")


def prepared_engine_folder(runs: Path, model: bytes) -> Path:
    """A run folder made by the local target, with the process adapter's input translated
    into its ``engine/`` (the worker reads the engine's name from the manifest)."""
    run = LocalTarget(runs).create(model, "base")
    loaded = load_text(model)
    assert loaded.model is not None
    ProcessAdapter().translate(loaded.model, "base", run.engine_folder)
    run.cancel()  # the queued run is not executed through the target; this frees its lock
    return run.engine_folder


@pytest.fixture(scope="module")
def outputs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """The two workers' output folders, by worker count, and the local target's run."""
    root = tmp_path_factory.mktemp("cross_process")
    model = model_file()
    engines = {workers: prepared_engine_folder(root / "runs", model) for workers in (1, 2)}
    processes: dict[int, subprocess.Popen[str]] = {}
    for workers, engine in engines.items():
        cwd = root / f"cwd_{workers}"
        cwd.mkdir()
        environment = {**os.environ, "PYTHONHASHSEED": str(workers)}
        processes[workers] = subprocess.Popen(
            [sys.executable, "-m", "lcsim.runs.worker", str(engine), "--workers", str(workers)],
            cwd=cwd,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    pids = {process.pid for process in processes.values()}
    assert len(pids) == 2 and os.getpid() not in pids
    for process in processes.values():
        _, err = process.communicate(timeout=300)
        assert process.returncode == EXIT_DONE, err
    target_run = LocalTarget(root / "target_runs").create(model, "base")
    assert target_run.execute() == "done"
    return {
        "workers_1": engines[1],
        "workers_2": engines[2],
        "target": target_run.folder / "tables",
    }


def test_two_separately_started_workers_give_equal_replications_tables(
    outputs: dict[str, Path],
) -> None:
    one = read_table(outputs["workers_1"] / REPLICATIONS_FILE)
    two = read_table(outputs["workers_2"] / REPLICATIONS_FILE)
    assert one.num_rows > 0
    assert set(one.column("scenario").to_pylist()) == {"one_till", "two_tills"}
    assert sorted(set(one.column("replication").to_pylist())) == list(range(6))
    assert tables_equal(one, two)


def test_their_timeseries_tables_are_equal_too(outputs: dict[str, Path]) -> None:
    one = read_table(outputs["workers_1"] / TIMESERIES_FILE)
    two = read_table(outputs["workers_2"] / TIMESERIES_FILE)
    assert one.num_rows > 0
    assert tables_equal(one, two)


def test_the_local_target_writes_the_same_replications_table(outputs: dict[str, Path]) -> None:
    worker = read_table(outputs["workers_1"] / REPLICATIONS_FILE)
    target = read_table(outputs["target"] / "replications.parquet")
    assert tables_equal(worker, target)
