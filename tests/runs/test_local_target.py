"""The ``local`` run target (spec 1 "Run targets" and "Run folder and results"; AKS-103):
the run folder, the manifest, job states, cancel, E172, E190, E191 and E192.

Each test that executes a run starts one spawned worker process (about a second), so the
models are small.
"""

import json
import os
import socket
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest
from dummy_adapters import (
    GRANDCHILD_RECORD,
    RUN_RECORD,
    BadTablesAdapter,
    CollectFailingAdapter,
    CrashingAdapter,
    DummyAdapter,
    FailingAdapter,
    LingeringAdapter,
    SlowAdapter,
    SpawningStubbornAdapter,
    StubbornAdapter,
    TranslateFailingAdapter,
)

import lcsim
from lcsim.engines.adapter import EngineAdapter
from lcsim.model.issues import Issue
from lcsim.model.streams import generator_info
from lcsim.runs import targets
from lcsim.runs.ids import RUN_ID_PATTERN
from lcsim.runs.limits import Limits
from lcsim.runs.lock import LOCK_FILE, take_lock
from lcsim.runs.manifest import MANIFEST_KEYS, new_manifest, read_manifest, write_manifest
from lcsim.runs.states import StateError
from lcsim.runs.targets import LocalRun, LocalTarget, RunRefused, recover_interrupted

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"

#: The run folder's files once a run is done (spec 1 "Run folder and results").
DONE_FILES = ["engine", "log.txt", "manifest.json", "model.json", "summary.json", "tables"]


def coffee_shop(**changes: Any) -> dict[str, Any]:
    """The coffee shop, shortened to 5 h with 30 min of warm-up and 2 replications."""
    document: dict[str, Any] = json.loads(
        (EXAMPLES / "coffee_shop.json").read_text(encoding="utf-8")
    )
    document["experiments"][0].update({"length": "5 h", "warmup": "30 min", "replications": 2})
    document["experiments"][0].update(changes)
    return document


def file_bytes(document: Mapping[str, Any]) -> bytes:
    # Indented, with a trailing space and no final newline: model.json must keep the
    # file's bytes as they are.
    return (json.dumps(document, indent=3) + " ").encode("utf-8")


def target(tmp_path: Path, adapter: EngineAdapter | None = None, **options: Any) -> LocalTarget:
    adapters = None if adapter is None else {adapter.name: adapter}
    return LocalTarget(tmp_path / "runs", adapters=adapters, **options)


def tree(folder: Path) -> list[str]:
    return sorted(str(path.relative_to(folder)) for path in folder.rglob("*"))


def log_text(run: LocalRun) -> str:
    return (run.folder / "log.txt").read_text(encoding="utf-8")


def error_of(run: LocalRun) -> dict[str, Any]:
    error = read_manifest(run.folder)["error"]
    assert isinstance(error, dict)
    return error


# --- a full run ----------------------------------------------------------------------------


def test_a_run_writes_the_full_run_folder(tmp_path: Path) -> None:
    document = coffee_shop()
    # A normal service time with mean below 2 sd: W202 when the file loads.
    document["components"][1]["params"]["service"] = {
        "dist": "normal",
        "mean": "1.5 min",
        "sd": "1 min",
    }
    model_file = file_bytes(document)
    adapter = DummyAdapter()
    run = target(tmp_path, adapter, client="mcp", project_id="p-1").create(model_file, "base")
    assert RUN_ID_PATTERN.fullmatch(run.run_id)
    assert run.folder == tmp_path / "runs" / run.run_id
    assert run.engine_folder == run.folder / "engine"
    assert str(run.state) == "queued"  # str(): mypy would keep the narrowed state
    assert tree(run.folder) == ["engine", "log.txt", "manifest.json", "model.json", LOCK_FILE]
    queued = read_manifest(run.folder)
    assert queued["state"] == "queued" and queued["started"] is None

    assert run.execute() == "done"
    assert run.state == "done"
    assert sorted(path.name for path in run.folder.iterdir()) == DONE_FILES
    assert (run.folder / "model.json").read_bytes() == model_file
    assert tree(run.folder / "tables") == ["replications.parquet"]

    manifest = read_manifest(run.folder)
    assert manifest == run.manifest
    assert list(manifest) == list(MANIFEST_KEYS)  # no error key on a done run
    info = generator_info()
    assert manifest["run_id"] == run.run_id
    assert manifest["project_id"] == "p-1"
    assert manifest["experiment_id"] == "base"
    assert manifest["scenario_ids"] == ["default"]
    assert manifest["state"] == "done"
    assert manifest["target"] == "local"
    assert manifest["host"] == socket.gethostname()
    assert manifest["client"] == "mcp"
    assert manifest["engine"] == {"name": "dummy", "version": "9.9.9"}
    assert manifest["generator"] == {"name": info.name, "numpy_version": info.numpy_version}
    assert manifest["product_version"] == lcsim.__version__
    assert manifest["format_version"] == "0.1"
    assert manifest["seed"] == 12345
    assert manifest["fraction"] == 1.0
    assert manifest["data_files"] == []
    created, started, ended = manifest["created"], manifest["started"], manifest["ended"]
    assert isinstance(created, str) and isinstance(started, str) and isinstance(ended, str)
    assert created <= started <= ended and ended.endswith("Z")
    assert manifest["run_id"].startswith(created[:4] + created[5:7] + created[8:10] + "T")

    summary = json.loads((run.folder / "summary.json").read_text(encoding="utf-8"))
    assert summary["scenarios"]["default"]["metrics"]["till.utilization"]["mean"] == 0.6
    # The load-time warning comes first (AKS-103, owner to confirm).
    assert [warning["code"] for warning in summary["warnings"]] == ["W202"]

    log = log_text(run)
    for line in ("queued", "running", "done"):
        assert f"state {line}" in log
    assert run.execute() == "done"  # a finished run is not run again


def test_a_run_id_already_used_is_drawn_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    taken = "20261106T000000-AAAAAA"
    (tmp_path / "runs" / taken).mkdir(parents=True)
    ids = iter([taken, taken, "20261106T000000-BBBBBB"])
    monkeypatch.setattr(targets, "new_run_id", lambda moment: next(ids))
    run = target(tmp_path, DummyAdapter()).create(file_bytes(coffee_shop()), "base")
    assert run.run_id == "20261106T000000-BBBBBB"
    assert list((tmp_path / "runs" / taken).iterdir()) == []
    run.cancel()


def test_a_seed_chosen_at_load_is_recorded_in_the_manifest(tmp_path: Path) -> None:
    document = coffee_shop()
    del document["experiments"][0]["seed"]
    model_file = file_bytes(document)
    run = target(tmp_path, DummyAdapter()).create(model_file, "base", seed_source=lambda: 77)
    assert read_manifest(run.folder)["seed"] == 77
    assert (run.folder / "model.json").read_bytes() == model_file  # the file, unchanged
    run.cancel()


def test_a_real_run_with_two_workers_writes_only_inside_engine(tmp_path: Path) -> None:
    model_file = file_bytes(coffee_shop())
    before = tree(tmp_path)
    run = target(tmp_path, workers=2).create(model_file, "base")
    assert run.execute() == "done", log_text(run)
    after = tree(tmp_path)
    prefix = f"runs/{run.run_id}/"
    new = [path for path in after if path not in before]
    outside_engine = [path for path in new if not path.startswith(prefix + "engine/")]
    assert outside_engine == [
        "runs",
        f"runs/{run.run_id}",
        prefix + "engine",
        prefix + "log.txt",
        prefix + "manifest.json",
        prefix + "model.json",
        prefix + "summary.json",
        prefix + "tables",
        prefix + "tables/replications.parquet",
        prefix + "tables/timeseries.parquet",
    ]
    assert tree(run.engine_folder) == [
        "input.json",
        "output",
        "output/replications.parquet",
        "output/timeseries.parquet",
    ]
    manifest = read_manifest(run.folder)
    assert manifest["engine"] == {"name": "simpy", "version": lcsim.__version__}
    replications = pq.read_table(run.folder / "tables" / "replications.parquet")
    assert set(replications.column("replication").to_pylist()) == {0, 1}
    summary = json.loads((run.folder / "summary.json").read_text(encoding="utf-8"))
    assert summary["fidelity_label"] == "Standard: 2 replications of 5 h, 95% confidence"


def test_run_runs_in_the_worker_process_and_receives_workers(tmp_path: Path) -> None:
    run = target(tmp_path, DummyAdapter(), workers=3).create(file_bytes(coffee_shop()), "base")
    assert run.execute() == "done"
    record = json.loads((run.engine_folder / RUN_RECORD).read_text(encoding="utf-8"))
    assert record["pid"] != os.getpid()
    assert record["workers"] == 3


# --- refused before a run exists ---------------------------------------------------------


def refused(tmp_path: Path, document: Any, adapter: EngineAdapter | None = None) -> RunRefused:
    with pytest.raises(RunRefused) as caught:
        target(tmp_path, adapter or DummyAdapter()).create(file_bytes(document), "base")
    assert not (tmp_path / "runs").exists() or list((tmp_path / "runs").iterdir()) == []
    return caught.value


@pytest.mark.parametrize("where", ["remote", "cluster"])
def test_remote_and_cluster_are_refused_with_e172_and_no_folder(tmp_path: Path, where: str) -> None:
    document = coffee_shop()
    document["run"]["target"] = where
    refusal = refused(tmp_path, document)
    [issue] = refusal.issues
    assert issue.code == "E172" and issue.severity == "error"
    assert issue.path == "/run/target" and issue.component is None
    assert f"'{where}'" in issue.message and "M11" in issue.message
    assert "E172" in str(refusal)


def test_a_target_that_is_not_text_is_refused_with_e172(tmp_path: Path) -> None:
    document = coffee_shop()
    document["run"]["target"] = 3
    [issue] = refused(tmp_path, document).issues
    assert issue.code == "E172" and "3" in issue.message


def test_a_file_with_errors_is_refused_with_its_issues(tmp_path: Path) -> None:
    document = coffee_shop()
    document["components"][1]["type"] = "nonsense"
    refusal = refused(tmp_path, document)
    assert "E120" in [issue.code for issue in refusal.issues]


def test_validate_errors_and_e173_are_refused(tmp_path: Path) -> None:
    adapter = DummyAdapter()
    adapter.issues = [Issue("E300", None, "", "The engine refuses this.", "Change it.")]
    assert [issue.code for issue in refused(tmp_path, coffee_shop(), adapter).issues] == ["E300"]
    document = coffee_shop()
    document["run"]["fidelity"] = "high"
    assert [issue.code for issue in refused(tmp_path, document).issues] == ["E173"]


def test_no_single_engine_is_refused_with_e102(tmp_path: Path) -> None:
    document = coffee_shop()
    document["run"]["engine"] = "missing"
    assert "E102" in [issue.code for issue in refused(tmp_path, document).issues]


def test_what_cannot_run_yet_raises(tmp_path: Path) -> None:
    local = target(tmp_path, DummyAdapter())
    with pytest.raises(ValueError, match="no experiment 'other'"):
        local.create(file_bytes(coffee_shop()), "other")
    searching = coffee_shop(search={"objective": "wait"})
    searching["objectives"] = [{"id": "wait", "metric": "till.wait.mean", "sense": "minimize"}]
    with pytest.raises(NotImplementedError, match="M5"):
        local.create(file_bytes(searching), "base")
    product_mix = {
        "format_version": "0.1",
        "meta": {"name": "Product mix"},
        "domain": "optimization",
        "variables": [{"id": "chairs", "type": "continuous", "lower": 0}],
        "objective": {"sense": "maximize", "linear": {"chairs": 45}},
        "constraints": [{"id": "wood", "linear": {"chairs": 5}, "op": "<=", "rhs": 400}],
    }
    with pytest.raises(NotImplementedError, match="M5"):
        LocalTarget(tmp_path / "runs").create(file_bytes(product_mix), "base")
    assert not (tmp_path / "runs").exists() or list((tmp_path / "runs").iterdir()) == []


# --- cancel --------------------------------------------------------------------------------


def test_cancelling_a_queued_run_never_starts_it(tmp_path: Path) -> None:
    adapter = DummyAdapter()
    run = target(tmp_path, adapter).create(file_bytes(coffee_shop()), "base")
    run.cancel()
    assert run.state == "cancelled"
    manifest = read_manifest(run.folder)
    assert manifest["state"] == "cancelled" and manifest["started"] is None
    assert isinstance(manifest["ended"], str)
    assert run.execute() == "cancelled"
    assert [name for name, _ in adapter.calls if name in ("translate", "collect")] == []
    assert list(run.engine_folder.iterdir()) == []
    assert not (run.folder / LOCK_FILE).exists()
    run.cancel()  # cancelling a finished run does nothing
    assert run.state == "cancelled"


def test_cancel_during_translate_starts_no_worker(tmp_path: Path) -> None:
    adapter = DummyAdapter()
    run = target(tmp_path, adapter).create(file_bytes(coffee_shop()), "base")
    adapter.on_translate = run.cancel
    assert run.execute() == "cancelled"
    assert not (run.engine_folder / RUN_RECORD).exists()
    assert "collect" not in [name for name, _ in adapter.calls]


def execute_in_thread(run: LocalRun) -> threading.Thread:
    thread = threading.Thread(target=run.execute)
    thread.start()
    return thread


def wait_for(condition: Any, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.02)


def test_cancel_stops_a_running_adapter_within_a_second(tmp_path: Path) -> None:
    run = target(tmp_path, SlowAdapter()).create(file_bytes(coffee_shop()), "base")
    thread = execute_in_thread(run)
    wait_for(lambda: (run.engine_folder / RUN_RECORD).exists())  # run() has started
    wait_for(lambda: read_manifest(run.folder)["fraction"] == 0.25)  # progress written
    cancelled_at = time.monotonic()
    run.cancel()
    thread.join(timeout=30)
    assert not thread.is_alive()
    assert time.monotonic() - cancelled_at < 1.5
    assert run.state == "cancelled"
    manifest = read_manifest(run.folder)
    assert manifest["state"] == "cancelled" and manifest["fraction"] == 0.25
    assert "error" not in manifest
    assert not (run.folder / "summary.json").exists()
    assert not (run.folder / LOCK_FILE).exists()


def test_a_worker_that_ignores_cancel_is_terminated(tmp_path: Path) -> None:
    local = target(tmp_path, StubbornAdapter(), cancel_grace_s=0.2)
    run = local.create(file_bytes(coffee_shop()), "base")
    thread = execute_in_thread(run)
    wait_for(lambda: (run.engine_folder / RUN_RECORD).exists())
    run.cancel()
    thread.join(timeout=30)
    assert run.state == "cancelled"
    assert "terminated" in log_text(run)


def test_cancel_during_collect_ends_cancelled_without_results(tmp_path: Path) -> None:
    # Codex review of PR #24: a cancel accepted while collecting must not end as done.
    adapter = DummyAdapter()
    run = target(tmp_path, adapter).create(file_bytes(coffee_shop()), "base")
    adapter.on_collect = run.cancel
    assert run.execute() == "cancelled"
    assert read_manifest(run.folder)["state"] == "cancelled"
    assert not (run.folder / "summary.json").exists()
    assert not (run.folder / "tables").exists()


def process_ended(pid: int) -> bool:
    """Whether ``pid`` has ended (gone, or a zombie no one has reaped yet)."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    except FileNotFoundError:
        return True
    return stat[stat.rindex(")") + 2] == "Z"


def test_terminating_a_worker_also_ends_the_processes_it_started(tmp_path: Path) -> None:
    # Codex review of PR #24: a forced stop must not leave the worker's children running.
    local = target(tmp_path, SpawningStubbornAdapter(), cancel_grace_s=0.2)
    run = local.create(file_bytes(coffee_shop()), "base")
    thread = execute_in_thread(run)
    wait_for(lambda: (run.engine_folder / GRANDCHILD_RECORD).exists())
    grandchild = json.loads((run.engine_folder / GRANDCHILD_RECORD).read_text(encoding="utf-8"))
    assert not process_ended(grandchild)
    run.cancel()
    thread.join(timeout=30)
    assert run.state == "cancelled"
    wait_for(lambda: process_ended(grandchild), timeout=5)


def test_a_worker_that_lingers_after_its_report_is_still_limited(tmp_path: Path) -> None:
    # Codex review of PR #24: the pipe closing does not mean the worker has ended.
    local = target(
        tmp_path,
        LingeringAdapter(),
        limits=Limits(time_s=0.5, memory_bytes=None),
        limit_grace_s=0.2,
    )
    run = local.create(file_bytes(coffee_shop()), "base")
    started = time.monotonic()
    assert run.execute() == "failed"
    assert time.monotonic() - started < 10
    assert error_of(run)["code"] == "E192"
    assert "terminated" in log_text(run)


# --- E190 ----------------------------------------------------------------------------------


def assert_e190(run: LocalRun, detail: str) -> None:
    assert run.state == "failed"
    error = error_of(run)
    assert error["code"] == "E190" and error["severity"] == "error"
    assert error["path"] == "" and error["component"] is None
    assert "'dummy'" in error["message"]
    assert detail not in error["message"] and detail not in error["hint"]
    assert "log.txt" in error["hint"]
    assert detail in log_text(run)
    assert not (run.folder / "summary.json").exists()


def test_an_adapter_error_in_run_is_e190_with_the_traceback_in_the_log(tmp_path: Path) -> None:
    run = target(tmp_path, FailingAdapter()).create(file_bytes(coffee_shop()), "base")
    assert run.execute() == "failed"
    assert_e190(run, "secret engine detail 4711")
    assert "Traceback" in log_text(run)


def test_a_worker_that_ends_without_reporting_is_e190(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(targets, "process_tree_memory", lambda pid: None)
    run = target(tmp_path, CrashingAdapter()).create(file_bytes(coffee_shop()), "base")
    assert run.execute() == "failed"
    assert_e190(run, "exit status 7")
    assert "memory limit is not enforced" in log_text(run)


def test_translate_and_collect_errors_are_e190(tmp_path: Path) -> None:
    run = target(tmp_path, TranslateFailingAdapter()).create(file_bytes(coffee_shop()), "base")
    assert run.execute() == "failed"
    assert_e190(run, "translate detail 815")
    run = target(tmp_path, CollectFailingAdapter()).create(file_bytes(coffee_shop()), "base")
    assert run.execute() == "failed"
    assert_e190(run, "collect detail 42")
    run = target(tmp_path, BadTablesAdapter()).create(file_bytes(coffee_shop()), "base")
    assert run.execute() == "failed"
    assert_e190(run, "bad_table")
    assert not (run.folder / "tables").exists()


# --- E192 ----------------------------------------------------------------------------------


def test_exceeding_the_time_limit_is_e192(tmp_path: Path) -> None:
    local = target(tmp_path, SlowAdapter(), limits=Limits(time_s=0.3, memory_bytes=None))
    run = local.create(file_bytes(coffee_shop()), "base")
    started = time.monotonic()
    assert run.execute() == "failed"
    assert time.monotonic() - started < 10
    error = error_of(run)
    assert error["code"] == "E192" and "time limit of 0.3 s" in error["message"]
    assert "memory limit is not enforced" in log_text(run)


def test_exceeding_the_memory_limit_is_e192(tmp_path: Path) -> None:
    # One byte: any process exceeds it, so the first reading fires (Linux, with /proc).
    local = target(tmp_path, StubbornAdapter(), limits=Limits(memory_bytes=1), limit_grace_s=0.2)
    run = local.create(file_bytes(coffee_shop()), "base")
    assert run.execute() == "failed"
    error = error_of(run)
    assert error["code"] == "E192" and "memory limit of 1 B" in error["message"]
    assert "terminated" in log_text(run)


def test_limits_are_written_in_plain_units() -> None:
    assert targets.describe_seconds(600.0) == "10 min"
    assert targets.describe_seconds(0.3) == "0.3 s"
    assert targets.describe_bytes(8 * 2**30) == "8 GiB"
    assert targets.describe_bytes(1536 * 2**20) == "1.5 GiB"
    assert targets.describe_bytes(5 * 2**20) == "5 MiB"
    assert targets.describe_bytes(1) == "1 B"


# --- state moves ---------------------------------------------------------------------------


def test_a_run_refuses_moves_outside_the_allowed_ones(tmp_path: Path) -> None:
    run = target(tmp_path, DummyAdapter()).create(file_bytes(coffee_shop()), "base")
    with pytest.raises(StateError):
        run.move("done")
    run.cancel()
    with pytest.raises(StateError):
        run.move("running")
    assert read_manifest(run.folder)["state"] == "cancelled"


# --- E191 ----------------------------------------------------------------------------------


def orphan(runs: Path, run_id: str, state: str, *, locked: bool = False) -> Path:
    """A run folder as a service that stopped would have left it."""
    folder = runs / run_id
    (folder / "engine").mkdir(parents=True)
    manifest = new_manifest(
        run_id=run_id,
        project_id=None,
        experiment_id="base",
        scenario_ids=("default",),
        created=targets.now(),
        host="here",
        client="script",
        engine_name="simpy",
        engine_version="0.0.0",
        format_version="0.1",
        seed=1,
    )
    manifest["state"] = state
    write_manifest(folder, manifest)
    (folder / LOCK_FILE).write_text("12345", encoding="ascii")
    return folder


def test_recovery_fails_runs_whose_process_is_gone_with_e191(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    running = orphan(runs, "20261106T000001-AAAAAA", "running")
    queued = orphan(runs, "20261106T000002-AAAAAA", "queued")
    no_lock = orphan(runs, "20261106T000003-AAAAAA", "running")
    (no_lock / LOCK_FILE).unlink()
    done = orphan(runs, "20261106T000004-AAAAAA", "done")
    live = target(tmp_path, DummyAdapter()).create(file_bytes(coffee_shop()), "base")
    held = orphan(runs, "20261106T000005-AAAAAA", "running")
    lock = take_lock(held / LOCK_FILE, create=False)
    (runs / "notes.txt").write_text("not a run", encoding="utf-8")
    (runs / "20261106T000006-AAAAAA").mkdir()  # no manifest

    marked = recover_interrupted(runs)
    assert marked == [
        "20261106T000001-AAAAAA",
        "20261106T000002-AAAAAA",
        "20261106T000003-AAAAAA",
    ]
    for folder in (running, queued, no_lock):
        manifest = read_manifest(folder)
        assert manifest["state"] == "failed"
        assert isinstance(manifest["ended"], str)
        error = manifest["error"]
        assert isinstance(error, dict) and error["code"] == "E191"
        assert error["path"] == "" and "restart" in error["message"]
        assert not (folder / LOCK_FILE).exists()
        assert "E191" in (folder / "log.txt").read_text(encoding="utf-8")
    assert read_manifest(done)["state"] == "done"
    assert read_manifest(live.folder)["state"] == "queued"
    assert read_manifest(held)["state"] == "running"
    lock.release()
    live.cancel()
    assert recover_interrupted(runs) == ["20261106T000005-AAAAAA"]
    assert recover_interrupted(tmp_path / "nothing") == []
