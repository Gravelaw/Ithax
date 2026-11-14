"""The run queue (spec 3 "Run queue"; AKS-112): at most ``max_concurrent`` runs at once,
the others started in arrival order, each in a thread of its own."""

import threading
import time
from collections.abc import Callable

import pytest

from ithax.runs.queue import RunQueue
from ithax.runs.states import JobState


class Job:
    """A job that runs until ``go`` is set; records when it started."""

    def __init__(self, run_id: str, log: list[str]) -> None:
        self.run_id = run_id
        self._state: JobState = "queued"
        self.go = threading.Event()
        self.log = log

    @property
    def state(self) -> JobState:
        return self._state

    def execute(self) -> JobState:
        if self._state != "queued":
            raise AssertionError("a job that is not queued was started")
        self._state = "running"
        self.log.append(self.run_id)
        self.go.wait(30)
        self._state = "done"
        return "done"


class Raising(Job):
    def execute(self) -> JobState:
        self.log.append(self.run_id)
        raise RuntimeError("job detail")


def wait_until(condition: Callable[[], object], timeout_s: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.01)


def test_jobs_start_in_arrival_order_one_at_a_time() -> None:
    log: list[str] = []
    queue = RunQueue(1)
    jobs = [Job(str(n), log) for n in range(4)]
    for job in jobs:
        queue.submit(job)
    for n, job in enumerate(jobs):
        wait_until(lambda job=job: job.state == "running")  # type: ignore[misc]
        assert queue.running == 1
        assert queue.waiting == [other.run_id for other in jobs[n + 1 :]]
        job.go.set()
    assert queue.join(30)
    assert log == ["0", "1", "2", "3"]
    assert queue.running == 0


def test_at_most_max_concurrent_jobs_run_at_once() -> None:
    log: list[str] = []
    queue = RunQueue(2)
    jobs = [Job(str(n), log) for n in range(3)]
    for job in jobs:
        queue.submit(job)
    wait_until(lambda: len(log) == 2)
    assert jobs[2].state == "queued"
    jobs[1].go.set()
    wait_until(lambda: jobs[2].state == "running")
    for job in jobs:
        job.go.set()
    assert queue.join(30)


def test_a_job_that_left_queued_before_its_turn_is_skipped() -> None:
    log: list[str] = []
    queue = RunQueue(1)
    first, second, third = (Job(str(n), log) for n in range(3))
    queue.submit(first)
    queue.submit(second)
    queue.submit(third)
    second._state = "cancelled"
    first.go.set()
    third.go.set()
    assert queue.join(30)
    assert log == ["0", "2"]


def test_a_job_that_raises_frees_its_place(caplog: pytest.LogCaptureFixture) -> None:
    log: list[str] = []
    queue = RunQueue(1)
    after = Job("after", log)
    queue.submit(Raising("bad", log))
    queue.submit(after)
    wait_until(lambda: after.state == "running")
    after.go.set()
    assert queue.join(30)
    assert log == ["bad", "after"]
    assert "bad" in caplog.text


def test_a_closed_queue_starts_nothing_more() -> None:
    log: list[str] = []
    queue = RunQueue(1)
    first, second = Job("0", log), Job("1", log)
    queue.submit(first)
    queue.submit(second)
    wait_until(lambda: first.state == "running")
    queue.close()
    assert not queue.join(0.05)
    first.go.set()
    assert queue.join(30)
    assert log == ["0"]
    with pytest.raises(RuntimeError):
        queue.submit(Job("2", log))


def test_max_concurrent_must_be_at_least_one() -> None:
    with pytest.raises(ValueError):
        RunQueue(0)


def test_on_finished_is_told_after_the_place_is_free_and_its_failure_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    log: list[str] = []
    seen: list[tuple[str, int]] = []
    queue: RunQueue

    def finished(job: object) -> None:
        assert isinstance(job, Job)
        seen.append((job.run_id, queue.running))
        raise RuntimeError("observer detail")

    queue = RunQueue(1, on_finished=finished)
    job = Job("0", log)
    job.go.set()
    queue.submit(job)
    assert queue.join(30)
    wait_until(lambda: seen)
    assert seen == [("0", 0)]
    wait_until(lambda: "Reporting the end of the run 0 failed" in caplog.text)
