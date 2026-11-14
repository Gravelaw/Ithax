"""The guard against zero-time loops (spec 2 "Zero-time loops"; #74, M2-5 and M4-14).

Items that circle blocks taking no time keep the clock at one instant forever. A
replication counts the events it runs and the same-instant transfer steps at each
instant, from 0 whenever the clock moves, and stops with E196 past ``INSTANT_STEP_LIMIT``.
"""

import pickle
from typing import Any

import pytest
import simpy
from conftest import model_document

from ithax.engines.adapter import RunIssue
from ithax.engines.process import blocks
from ithax.engines.process.blocks import InstantCounter, ZeroTimeLoop
from ithax.engines.process.replication import run_replication, zero_time_issue
from ithax.engines.process.translate import engine_input
from ithax.model.loading import load_document


def one_item() -> dict[str, Any]:
    return {
        "id": "arrivals",
        "type": "source",
        "params": {"interarrival": {"dist": "constant", "value": "60 s"}, "max_items": 1},
    }


def branch_loop() -> dict[str, Any]:
    """One item into a branch whose only weighted route leads back to itself: it circles
    inside one SimPy event, as same-instant transfer steps."""
    return model_document(
        [
            one_item(),
            {
                "id": "loop",
                "type": "branch",
                "params": {
                    "routes": ["again", "done"],
                    "rule": "probability",
                    "weights": {"again": 1, "done": 0},
                },
            },
            {"id": "exit", "type": "sink", "params": {}},
        ],
        [("arrivals.out", "loop.in"), ("loop.again", "loop.in"), ("loop.done", "exit.in")],
        length="10 s",
    )


def server_loop() -> dict[str, Any]:
    """One item into a server of 0 s service routed back to itself: each service ends in a
    new SimPy event at the same instant."""
    till = {
        "id": "till",
        "type": "server",
        "params": {"capacity": 1, "service": {"dist": "constant", "value": "0 s"}},
    }
    return model_document(
        [one_item(), till], [("arrivals.out", "till.in"), ("till.out", "till.in")], length="10 s"
    )


def run(document: dict[str, Any]) -> Any:
    result = load_document(document)
    assert result.model is not None
    return run_replication(engine_input(result.model, "e"), 0, 0, lambda: False)


def test_the_limit_is_a_million_steps_at_one_instant() -> None:
    assert blocks.INSTANT_STEP_LIMIT == 1_000_000


@pytest.mark.parametrize("document", [branch_loop, server_loop], ids=["transfers", "events"])
def test_a_zero_time_loop_stops_the_replication_with_e196(
    document: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(blocks, "INSTANT_STEP_LIMIT", 5_000)
    with pytest.raises(RunIssue) as raised:
        run(document())
    issue = raised.value.issue
    assert issue.code == "E196" and issue.severity == "error"
    assert issue.path == "" and issue.component is None
    assert "at 0 s of replication 1 of scenario 'default' without time passing" in issue.message
    assert str(raised.value).startswith("E196: The run was stopped")


def test_a_real_loop_is_stopped_at_the_real_limit() -> None:
    """The transfer loop at the true limit: about a second."""
    with pytest.raises(RunIssue) as raised:
        run(branch_loop())
    assert "more than 1,000,000 events" in raised.value.issue.message


def test_the_count_starts_again_when_the_clock_moves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(blocks, "INSTANT_STEP_LIMIT", 3)
    env = simpy.Environment()
    counter = InstantCounter(env)
    for _ in range(3):
        counter.tick()
    env.run(until=1.0)
    for _ in range(3):
        counter.tick()  # three at 1 s: at the limit, not past it
    with pytest.raises(ZeroTimeLoop) as raised:
        counter.tick()
    assert raised.value.at == 1.0


def test_a_model_whose_items_take_time_is_not_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    """The same server loop with 1 s of service: one event a second, never many at once."""
    monkeypatch.setattr(blocks, "INSTANT_STEP_LIMIT", 50)
    document = server_loop()
    document["components"][1]["params"]["service"]["value"] = "1 s"
    assert run(document) is not None


def test_the_issue_crosses_a_process_boundary() -> None:
    """A replication runs in a worker process; its ``RunIssue`` is pickled to the parent."""
    issue = zero_time_issue(12.5, "base", 3)
    copy = pickle.loads(pickle.dumps(RunIssue(issue)))
    assert copy.issue == issue
    assert "at 12.5 s of replication 4 of scenario 'base'" in issue.message
