"""The live state and progress of each run, behind ``GET /v1/runs/{rid}/events`` (spec 3
"Progress events"; AKS-112): a listener gets a snapshot taken at one instant with its
registration, then every later change, so none is lost or sent twice."""

import asyncio
import queue
import threading
from typing import Any

import pytest

from ithax.service.run_feed import RunFeed, Snapshot


async def drain(listener: Any, until_final: bool = True) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    while True:
        event = dict(await asyncio.wait_for(listener.next(), 30))
        events.append(event)
        if event["type"] == "state" and event["state"] in ("done", "failed", "cancelled"):
            return events


def listened(feed: RunFeed, run_id: str) -> Snapshot | None:
    async def snap() -> Snapshot | None:
        with feed.listen(run_id) as (snapshot, _listener):
            return snapshot

    return asyncio.run(snap())


def test_a_listener_gets_the_snapshot_then_every_later_change() -> None:
    feed = RunFeed()
    feed.begin("r")

    async def scenario() -> list[dict[str, Any]]:
        with feed.listen("r") as (snapshot, listener):
            assert snapshot == Snapshot("queued", 0.0, "")
            feed.state("r", "running")
            feed.progress("r", 0.5, "Half")
            feed.state("r", "done")
            return await drain(listener)

    assert asyncio.run(scenario()) == [
        {"type": "state", "state": "running"},
        {"type": "progress", "fraction": 0.5, "message": "Half"},
        {"type": "state", "state": "done"},
    ]
    assert listened(feed, "r") is None  # a final run is no longer live


def test_a_run_not_live_has_no_snapshot_and_changes_to_it_are_ignored() -> None:
    feed = RunFeed()
    feed.progress("gone", 0.1, "x")
    feed.state("gone", "done")
    assert listened(feed, "gone") is None
    assert feed.snapshot("gone") is None
    assert feed.live() == []


def test_listeners_racing_a_publisher_see_each_change_exactly_once() -> None:
    """A thread publishes 200 progress reports and then the final state. Ten listeners
    join after report 20, 40, ..., 200 (the publisher waits for each to have joined),
    while the earlier ones are still draining: each sees the snapshot of its report, then
    exactly the later changes, in order, and the final state once."""
    feed = RunFeed()
    feed.begin("r")
    feed.state("r", "running")
    published: queue.Queue[int] = queue.Queue()
    joined = threading.Semaphore(0)

    def publish() -> None:
        for n in range(1, 201):
            feed.progress("r", n / 200, f"step {n}")
            if n % 20 == 0:
                published.put(n)
                assert joined.acquire(timeout=30)
        feed.state("r", "done")

    async def collect(
        handle: Any, snapshot: Snapshot, listener: Any
    ) -> tuple[Snapshot, list[dict[str, Any]]]:
        try:
            return snapshot, await drain(listener)
        finally:
            handle.__exit__(None, None, None)

    async def join() -> list[tuple[int, tuple[Snapshot, list[dict[str, Any]]]]]:
        loop = asyncio.get_running_loop()
        steps, tasks = [], []
        for _ in range(10):
            step = await loop.run_in_executor(None, published.get, True, 30)
            handle = feed.listen("r")
            snapshot, listener = handle.__enter__()
            joined.release()
            assert snapshot is not None
            steps.append(step)
            tasks.append(asyncio.ensure_future(collect(handle, snapshot, listener)))
        return list(zip(steps, await asyncio.gather(*tasks), strict=True))

    thread = threading.Thread(target=publish)
    thread.start()
    seen = asyncio.run(join())
    thread.join()
    for step, (snapshot, events) in seen:
        assert snapshot == Snapshot("running", step / 200, f"step {step}")
        steps = [event["fraction"] for event in events if event["type"] == "progress"]
        assert steps == [n / 200 for n in range(step + 1, 201)]
        assert events[-1] == {"type": "state", "state": "done"}
        assert sum(1 for event in events if event["type"] == "state") == 1


@pytest.mark.parametrize("final", ["done", "failed", "cancelled"])
def test_live_lists_unfinished_runs(final: str) -> None:
    feed = RunFeed()
    feed.begin("a")
    feed.begin("b")
    assert feed.live() == ["a", "b"]
    assert feed.snapshot("a") == Snapshot("queued", 0.0, "")
    feed.state("a", final)
    assert feed.live() == ["b"]
