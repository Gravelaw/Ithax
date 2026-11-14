"""A search experiment on the ``local`` run target (spec 1 "Division of labour" and "How the
``local`` target runs a run"; spec 2 "Simulation-based optimization"; AKS-109): each
candidate evaluation is translated and collected here and run in a spawned worker of its
own, in its own subfolder of ``engine/``, and the run has the states and events of any run.

Each evaluation starts a worker (about a second), so the searches are small.
"""

import json
import threading
import time
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest
from dummy_adapters import (
    SEARCH_INPUT,
    SEARCH_OUTPUT,
    CollectFailingAdapter,
    SearchAdapter,
    SearchFailingAdapter,
    SearchSlowAdapter,
    TranslateFailingAdapter,
)
from test_search import searching

from ithax.engines.adapter import EngineAdapter
from ithax.runs import targets
from ithax.runs.manifest import MANIFEST_KEYS, read_manifest
from ithax.runs.targets import LocalRun, LocalTarget


def file_bytes(document: dict[str, Any]) -> bytes:
    return json.dumps(document, indent=2).encode("utf-8")


def created(tmp_path: Path, adapter: EngineAdapter, document: dict[str, Any]) -> LocalRun:
    local = LocalTarget(tmp_path / "runs", adapters={adapter.name: adapter})
    return local.create(file_bytes(document), "base")


def log_text(run: LocalRun) -> str:
    return (run.folder / "log.txt").read_text(encoding="utf-8")


def small(**changes: Any) -> dict[str, Any]:
    """`tills` 1 or 2, the baseline 1: two candidates, both confirmed."""
    return searching("bowl", value=1, high=2, **changes)


def test_a_search_run_writes_the_full_run_folder(tmp_path: Path) -> None:
    run = created(tmp_path, SearchAdapter(), small())
    assert run.state == "queued"
    assert run.execute() == "done"
    manifest = read_manifest(run.folder)
    assert list(manifest) == [*MANIFEST_KEYS, "optimizer"]
    assert manifest["optimizer"] == {"name": "exhaustive", "version": None}
    assert manifest["state"] == "done" and manifest["fraction"] == 1.0
    assert manifest["experiment_id"] == "base" and manifest["scenario_ids"] == ["default"]
    assert manifest["seed"] == 12345
    folders = sorted(path.name for path in run.engine_folder.iterdir())
    assert folders == ["confirm-000", "confirm-001", "search-000", "search-001"]
    for folder in folders:
        names = sorted(path.name for path in (run.engine_folder / folder).iterdir())
        assert names == [SEARCH_INPUT, SEARCH_OUTPUT]
    summary = json.loads((run.folder / "summary.json").read_text(encoding="utf-8"))
    assert summary["search"]["best"] == {"set": {"tills": 2}}
    assert summary["scenarios"]["default"]["set"] == {"tills": 2}
    # tables/ holds the best candidate's confirmation: 30 replications of two metrics.
    table = pq.read_table(run.folder / "tables" / "replications.parquet")
    assert table.num_rows == 60
    assert set(table.column("scenario").to_pylist()) == {"default"}
    log = log_text(run)
    for line in ("state queued", "state running", "state done"):
        assert line in log
    assert log.count("worker started") == 4
    for folder in folders:
        assert f"evaluation {folder}" in log
    assert not (run.folder / "worker.lock").exists()


def test_an_optuna_search_records_the_optuna_version(tmp_path: Path) -> None:
    import optuna

    run = created(tmp_path, SearchAdapter(), small(budget=1))
    assert read_manifest(run.folder)["optimizer"] == {
        "name": "optuna",
        "version": optuna.__version__,
    }
    run.cancel()
    assert run.state == "cancelled"


def test_a_failing_candidate_fails_the_run_with_e190(tmp_path: Path) -> None:
    run = created(tmp_path, SearchFailingAdapter(), searching("bowl", value=1, high=3))
    assert run.execute() == "failed"
    error = read_manifest(run.folder)["error"]
    assert error["code"] == "E190" and "2024" not in error["message"]
    log = log_text(run)
    assert "candidate detail 2024" in log and "evaluation search-002" in log
    assert not (run.folder / "summary.json").exists()
    assert not (run.engine_folder / "confirm-000").exists()


def test_a_failing_translate_or_collect_in_a_search_is_e190(tmp_path: Path) -> None:
    run = created(tmp_path / "t", TranslateFailingAdapter(), small())
    assert run.execute() == "failed"
    assert read_manifest(run.folder)["error"]["code"] == "E190"
    assert "translate raised in search-000" in log_text(run)
    run = created(tmp_path / "c", CollectFailingAdapter(), small())
    assert run.execute() == "failed"
    assert read_manifest(run.folder)["error"]["code"] == "E190"
    assert "collect raised in search-000" in log_text(run)


def test_an_error_in_the_search_itself_is_e190(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*arguments: Any) -> None:
        raise RuntimeError("search detail 77")

    monkeypatch.setattr(targets, "run_search", broken)
    run = created(tmp_path, SearchAdapter(), small())
    assert run.execute() == "failed"
    assert read_manifest(run.folder)["error"]["code"] == "E190"
    assert "the search raised" in log_text(run) and "search detail 77" in log_text(run)


def test_a_cancel_while_a_candidate_runs_ends_the_search_cancelled(tmp_path: Path) -> None:
    run = created(tmp_path, SearchSlowAdapter(), small())
    thread = threading.Thread(target=run.execute)
    thread.start()
    deadline = time.monotonic() + 60
    while "evaluation search-001" not in log_text(run):
        assert time.monotonic() < deadline
        time.sleep(0.05)
    time.sleep(0.5)
    run.cancel()
    thread.join(timeout=30)
    assert not thread.is_alive()
    assert run.state == "cancelled"
    assert not (run.folder / "summary.json").exists()
    assert not (run.engine_folder / "confirm-000").exists()
    assert "error" not in read_manifest(run.folder)


def test_a_cancel_during_a_candidates_translate_starts_no_worker_for_it(
    tmp_path: Path,
) -> None:
    adapter = SearchAdapter()
    run = created(tmp_path, adapter, small())
    adapter.on_translate = run.cancel
    assert run.execute() == "cancelled"
    assert "worker started" not in log_text(run)


def test_a_cancel_during_a_candidates_collect_runs_no_further_candidate(
    tmp_path: Path,
) -> None:
    adapter = SearchAdapter()
    run = created(tmp_path, adapter, small())
    adapter.on_collect = run.cancel
    assert run.execute() == "cancelled"
    assert sorted(path.name for path in run.engine_folder.iterdir()) == ["search-000"]
    assert not (run.folder / "summary.json").exists()
