"""What the service needs of the ``local`` run target (AKS-112): state and progress hooks,
a request's ``target`` overriding ``run.target``, a cancel that says whether it was
accepted, ``interrupt`` (E191 when the service stops), the experiment-choice error, and
``recover_interrupted`` skipping folders that are not runs."""

import json
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from dummy_adapters import DummyAdapter, SlowAdapter

from lcsim.engines.adapter import EngineAdapter
from lcsim.runs.lock import LOCK_FILE
from lcsim.runs.manager import ExperimentChoiceError
from lcsim.runs.manifest import MANIFEST_FILE, read_manifest
from lcsim.runs.states import JobState
from lcsim.runs.targets import LocalRun, LocalTarget, RunRefused, recover_interrupted

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def coffee_shop(**run: Any) -> bytes:
    document: dict[str, Any] = json.loads((EXAMPLES / "coffee_shop.json").read_text())
    document["experiments"][0].update({"length": "1 h", "warmup": "0 s", "replications": 2})
    document["run"].update(run)
    return json.dumps(document).encode()


def target(tmp_path: Path, adapter: EngineAdapter, **options: Any) -> LocalTarget:
    return LocalTarget(tmp_path / "runs", adapters={adapter.name: adapter}, **options)


def wait_until(condition: Callable[[], object], timeout_s: float = 60.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.01)


def test_the_hooks_see_every_state_change_and_every_progress_report(tmp_path: Path) -> None:
    states: list[tuple[str, JobState]] = []
    progress: list[tuple[str, float, str]] = []
    local = target(
        tmp_path,
        DummyAdapter(),
        on_state=lambda run, state: states.append((run.run_id, state)),
        on_progress=lambda run, fraction, message: progress.append((run.run_id, fraction, message)),
    )
    run = local.create(coffee_shop(), "base")
    assert run.execute() == "done"
    assert states == [(run.run_id, "running"), (run.run_id, "done")]
    assert progress == [
        (run.run_id, 0.5, "Replication 1 of 2"),
        (run.run_id, 1.0, "Replication 2 of 2"),
    ]


def test_a_request_target_overrides_run_target_and_is_recorded(tmp_path: Path) -> None:
    local = target(tmp_path, DummyAdapter())
    run = local.create(coffee_shop(target="cluster"), "base", target="local")
    assert run.manifest["target"] == "local"
    run.cancel()
    with pytest.raises(RunRefused) as refused:
        local.create(coffee_shop(), "base", target="remote")
    (issue,) = refused.value.issues
    assert issue.code == "E172"
    assert issue.path == "/target"
    assert "'remote'" in issue.message
    with pytest.raises(RunRefused) as refused:
        local.create(coffee_shop(target="cluster"), "base")
    assert refused.value.issues[0].path == "/run/target"


@pytest.mark.parametrize(
    ("experiment_id", "domain", "reason"),
    [(None, "process", "missing"), ("nope", "process", "unknown")],
)
def test_a_wrong_experiment_choice_raises_with_its_reason(
    tmp_path: Path, experiment_id: str | None, domain: str, reason: str
) -> None:
    with pytest.raises(ExperimentChoiceError) as error:
        target(tmp_path, DummyAdapter()).create(coffee_shop(), experiment_id)
    assert error.value.reason == reason
    assert isinstance(error.value, ValueError)
    assert not (tmp_path / "runs").exists() or list((tmp_path / "runs").iterdir()) == []


def test_cancel_says_whether_it_was_accepted(tmp_path: Path) -> None:
    local = target(tmp_path, DummyAdapter())
    queued = local.create(coffee_shop(), "base")
    assert queued.cancel() is True
    assert queued.state == "cancelled"
    assert queued.cancel() is False
    done = local.create(coffee_shop(), "base")
    assert done.execute() == "done"
    assert done.cancel() is False


def test_cancelling_a_running_run_twice_is_accepted_twice(tmp_path: Path) -> None:
    run = target(tmp_path, SlowAdapter()).create(coffee_shop(), "base")
    states: list[JobState] = []
    thread = threading.Thread(target=lambda: states.append(run.execute()))
    thread.start()
    wait_until(lambda: run.manifest["fraction"] == 0.25)
    assert run.cancel() is True
    assert run.cancel() is True
    thread.join(60)
    assert states == ["cancelled"]


def interrupted(run: LocalRun) -> None:
    manifest = read_manifest(run.folder)
    assert manifest["state"] == "failed"
    assert manifest["error"]["code"] == "E191"
    assert not (run.folder / LOCK_FILE).exists()


def test_interrupting_a_queued_run_fails_it_with_e191(tmp_path: Path) -> None:
    states: list[JobState] = []
    local = target(tmp_path, DummyAdapter(), on_state=lambda run, state: states.append(state))
    run = local.create(coffee_shop(), "base")
    run.interrupt()
    interrupted(run)
    assert states == ["failed"]
    assert run.execute() == "failed"
    run.interrupt()  # a final run is left as it is
    assert states == ["failed"]


def test_interrupting_a_running_run_stops_it_and_fails_it_with_e191(tmp_path: Path) -> None:
    run = target(tmp_path, SlowAdapter()).create(coffee_shop(), "base")
    states: list[JobState] = []
    thread = threading.Thread(target=lambda: states.append(run.execute()))
    thread.start()
    wait_until(lambda: run.manifest["fraction"] == 0.25)
    run.interrupt()
    thread.join(60)
    assert states == ["failed"]
    interrupted(run)


def test_recover_interrupted_skips_folders_that_are_not_runs(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    for name, text in (
        ("20261107T100000-AAAAAA", "{"),
        ("20261107T100001-BBBBBB", "[]"),
        ("20261107T100002-CCCCCC", json.dumps({"state": "running"})),
    ):
        (runs / name).mkdir(parents=True)
        (runs / name / MANIFEST_FILE).write_text(text)
    assert recover_interrupted(runs) == []
    assert (runs / "20261107T100000-AAAAAA" / MANIFEST_FILE).read_text() == "{"


def test_an_unexpected_failure_while_driving_a_run_fails_it_with_e190(tmp_path: Path) -> None:
    def broken(run: LocalRun, fraction: float, message: str) -> None:
        raise RuntimeError("hook detail 99")

    run = target(tmp_path, DummyAdapter(), on_progress=broken).create(coffee_shop(), "base")
    assert run.execute() == "failed"
    manifest = read_manifest(run.folder)
    assert manifest["error"]["code"] == "E190"
    assert "hook detail 99" not in manifest["error"]["message"]
    assert "hook detail 99" in (run.folder / "log.txt").read_text()
    assert not (run.folder / LOCK_FILE).exists()


def test_a_failure_after_the_run_ended_leaves_its_final_state(tmp_path: Path) -> None:
    def broken(run: LocalRun, state: JobState) -> None:
        if state == "done":
            raise RuntimeError("hook detail 98")

    run = target(tmp_path, DummyAdapter(), on_state=broken).create(coffee_shop(), "base")
    with pytest.raises(RuntimeError):
        run.execute()
    assert read_manifest(run.folder)["state"] == "done"
