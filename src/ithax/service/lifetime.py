"""The service's lifetime (spec 3 "Service rules", Lifetime; AKS-78 open).

Proposed default, owner to confirm: the service stays up while runs are active or clients
are connected, and exits after 30 idle minutes. Idle means nothing is held, where a run,
an open WebSocket and an HTTP request in progress each hold the service; the idle time
counts from the end of the last hold or the last request, whichever came later (AKS-110).

``Lifetime`` keeps that account; ``watch`` checks it from the event loop and calls its
``on_idle`` once the limit is reached.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

__all__ = ["Lifetime", "watch"]


class Lifetime:
    """How long the service has been idle, by ``clock`` (seconds, monotonic)."""

    def __init__(self, timeout_s: float, clock: Callable[[], float] = time.monotonic) -> None:
        if not timeout_s > 0:
            raise ValueError(f"the idle limit {timeout_s!r} s is not above 0")
        self.timeout_s = timeout_s
        self._clock = clock
        self._lock = threading.Lock()
        self._holds = 0
        self._last = clock()

    def touch(self) -> None:
        """Note activity now: the idle time starts again."""
        with self._lock:
            self._last = self._clock()

    @contextmanager
    def hold(self) -> Iterator[None]:
        """Keep the service up while the block runs: a run, a WebSocket, a request."""
        with self._lock:
            self._holds += 1
        try:
            yield
        finally:
            with self._lock:
                self._holds -= 1
                self._last = self._clock()

    @property
    def holds(self) -> int:
        """How many runs, WebSockets and requests hold the service now."""
        with self._lock:
            return self._holds

    def idle_for(self) -> float:
        """Seconds since the service was last active; 0 while anything holds it."""
        with self._lock:
            if self._holds:
                return 0.0
            return max(0.0, self._clock() - self._last)

    def expired(self) -> bool:
        """Whether the service has been idle for its whole limit."""
        return self.idle_for() >= self.timeout_s


async def watch(lifetime: Lifetime, interval_s: float, on_idle: Callable[[], None]) -> None:
    """Check ``lifetime`` every ``interval_s`` seconds; call ``on_idle`` once when it has
    expired, then return."""
    while not lifetime.expired():
        await asyncio.sleep(interval_s)
    on_idle()
