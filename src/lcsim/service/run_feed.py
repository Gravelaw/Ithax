"""The live state and progress of the runs this service drives, behind
``GET /v1/runs/{rid}/events`` (spec 3 "Progress events"; AKS-112).

``RunFeed`` keeps, for each unfinished run, its state, its latest progress fraction and
message, and its listeners. The run target's hooks call ``state`` and ``progress`` from the
run's own thread; each change is recorded and sent to every listener under one lock, and
``listen`` takes its snapshot and registers its listener under the same lock, so a listener
gets the run as it was at one instant and then exactly the changes after it: none is lost
and none is sent twice.

A run that reaches a final state is sent that state and then dropped: a listener that comes
later finds no live run and reads the run's manifest, which the run target writes before it
reports the change.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field

from lcsim.runs.states import FINAL_STATES
from lcsim.service.events import Event, Listener

__all__ = ["RunFeed", "Snapshot", "progress_event", "state_event"]


@dataclass(frozen=True)
class Snapshot:
    """A run's state and latest progress at one instant."""

    state: str
    fraction: float
    message: str


def state_event(state: str) -> Event:
    """``{"type": "state", "state": ...}``."""
    return {"type": "state", "state": state}


def progress_event(fraction: float, message: str) -> Event:
    """``{"type": "progress", "fraction": ..., "message": ...}``."""
    return {"type": "progress", "fraction": fraction, "message": message}


@dataclass
class _Live:
    state: str
    fraction: float = 0.0
    message: str = ""
    listeners: list[Listener] = field(default_factory=list)


class RunFeed:
    """The unfinished runs' state, progress and listeners; safe from any thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, _Live] = {}

    def begin(self, run_id: str) -> None:
        """A run just created, ``queued``, with no progress."""
        with self._lock:
            self._runs[run_id] = _Live("queued")

    def live(self) -> list[str]:
        """The unfinished runs, in the order they began."""
        with self._lock:
            return list(self._runs)

    def snapshot(self, run_id: str) -> Snapshot | None:
        """The run's state and progress now; ``None`` when it is not live."""
        with self._lock:
            live = self._runs.get(run_id)
            return None if live is None else Snapshot(live.state, live.fraction, live.message)

    def progress(self, run_id: str, fraction: float, message: str) -> None:
        """A progress report of ``run_id``."""
        with self._lock:
            live = self._runs.get(run_id)
            if live is None:
                return
            live.fraction, live.message = fraction, message
            for listener in live.listeners:
                listener.deliver(progress_event(fraction, message))

    def state(self, run_id: str, state: str) -> None:
        """A state change of ``run_id``; a final state also drops the run."""
        with self._lock:
            live = self._runs.get(run_id)
            if live is None:
                return
            live.state = state
            for listener in live.listeners:
                listener.deliver(state_event(state))
            if state in FINAL_STATES:
                del self._runs[run_id]

    @contextlib.contextmanager
    def listen(self, run_id: str) -> Iterator[tuple[Snapshot | None, Listener]]:
        """Listen to ``run_id`` while the block runs (called in an event loop): the
        snapshot, ``None`` when the run is not live, and the listener that receives every
        later change."""
        listener = Listener(asyncio.get_running_loop())
        with self._lock:
            live = self._runs.get(run_id)
            snapshot = None
            if live is not None:
                snapshot = Snapshot(live.state, live.fraction, live.message)
                live.listeners.append(listener)
        try:
            yield snapshot, listener
        finally:
            with self._lock:
                if live is not None and listener in live.listeners:
                    live.listeners.remove(listener)
