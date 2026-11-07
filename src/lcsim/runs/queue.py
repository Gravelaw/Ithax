"""The run queue (spec 3 "Run queue"; AKS-112).

At most ``max_concurrent`` runs execute at once; the others wait in ``queued`` and start in
the order they were submitted. Each run executes in a thread of its own (the run target then
starts the run's worker process). A job that is no longer ``queued`` when its turn comes
(cancelled or interrupted while waiting) is skipped. ``close`` starts nothing more, and
``join`` waits for the runs executing.

The threads are daemon threads: a run's worker stops by itself when the service process
ends (spec 1 "Where the methods run"), and the service stops its runs before it exits.
"""

from __future__ import annotations

import collections
import logging
import threading
import time
from typing import Protocol

from lcsim.runs.states import JobState

__all__ = ["Job", "RunQueue"]

_log = logging.getLogger(__name__)


class Job(Protocol):
    """A run the queue can execute (``lcsim.runs.targets.LocalRun``)."""

    @property
    def run_id(self) -> str: ...

    @property
    def state(self) -> JobState: ...

    def execute(self) -> JobState: ...


class RunQueue:
    """Runs jobs in arrival order, at most ``max_concurrent`` at once."""

    def __init__(self, max_concurrent: int) -> None:
        if max_concurrent < 1:
            raise ValueError(f"max_concurrent {max_concurrent!r} is below 1")
        self.max_concurrent = max_concurrent
        self._lock = threading.Lock()
        self._waiting: collections.deque[Job] = collections.deque()
        self._threads: list[threading.Thread] = []
        self._closed = False

    @property
    def running(self) -> int:
        """How many jobs are executing."""
        with self._lock:
            return len(self._threads)

    @property
    def waiting(self) -> list[str]:
        """The run ids of the jobs waiting, in arrival order."""
        with self._lock:
            return [job.run_id for job in self._waiting]

    def submit(self, job: Job) -> None:
        """Adds ``job`` after every job waiting; ``RuntimeError`` once closed."""
        with self._lock:
            if self._closed:
                raise RuntimeError("the run queue is closed")
            self._waiting.append(job)
            self._pump()

    def close(self) -> None:
        """Starts no more jobs."""
        with self._lock:
            self._closed = True
            self._waiting.clear()

    def join(self, timeout_s: float) -> bool:
        """Waits up to ``timeout_s`` for the executing jobs to end; ``True`` when none is
        left."""
        deadline = time.monotonic() + timeout_s
        while True:
            with self._lock:
                threads = list(self._threads)
            if not threads:
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            threads[0].join(remaining)

    def _pump(self) -> None:
        """Starts waiting jobs while there is room; called with the lock held."""
        while not self._closed and self._waiting and len(self._threads) < self.max_concurrent:
            job = self._waiting.popleft()
            if job.state != "queued":
                continue
            thread = threading.Thread(
                target=self._execute, args=(job,), name=f"lcsim-run-{job.run_id}", daemon=True
            )
            self._threads.append(thread)
            thread.start()

    def _execute(self, job: Job) -> None:
        try:
            job.execute()
        except Exception:
            _log.exception("The run %s stopped with an error in the service.", job.run_id)
        finally:
            with self._lock:
                self._threads.remove(threading.current_thread())
                self._pump()
