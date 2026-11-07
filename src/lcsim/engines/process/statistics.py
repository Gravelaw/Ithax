"""Per-replication bookkeeping for spec 2 "Statistic definitions".

Nothing here depends on SimPy: a block reports its changes with the simulation time, and
these classes keep the sums. A time-weighted mean is a sum of value times duration over the
observed period divided by its length; that is bookkeeping, not a numerical method
(guide rule 7).

- The observed period runs from the end of warm-up to the end of the run. An event at
  exactly the warm-up time belongs to it; an event at the end time never runs (spec 2
  "Simultaneous events").
- A time-weighted value integrates only over the period, so a value held across the end of
  warm-up adds only its part after warm-up. Its maximum is the largest of the value held
  at the end of warm-up and every value taken during the period, including one held for
  no time.
- A mean over no observations is NaN (spec 1 "Tables for the ``process`` domain").
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = ["Tally", "TimeWeighted", "Window"]


@dataclass(frozen=True)
class Window:
    """The observed period, from ``warmup`` to ``end``, in seconds from the run start."""

    warmup: float
    end: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.warmup < self.end:
            raise ValueError(
                f"warm-up {self.warmup!r} s is not from 0 s to below the end {self.end!r} s"
            )

    @property
    def period(self) -> float:
        """The length of the observed period."""
        return self.end - self.warmup

    def observes(self, time: float) -> bool:
        """Whether an event at ``time`` falls in the observed period."""
        return time >= self.warmup


class TimeWeighted:
    """A value that holds between changes, such as a queue length or a busy count."""

    def __init__(self, window: Window, value: float = 0.0) -> None:
        self._window = window
        self._value = value
        self._time = 0.0
        self._area = 0.0
        self._max: float | None = None

    @property
    def value(self) -> float:
        """The value now."""
        return self._value

    def set(self, time: float, value: float) -> None:
        """The value becomes ``value`` at ``time``."""
        self._advance(time)
        self._value = value
        if self._window.observes(time):
            self._max = value if self._max is None else max(self._max, value)

    def add(self, time: float, change: float) -> None:
        """The value changes by ``change`` at ``time``."""
        self.set(time, self._value + change)

    def mean(self) -> float:
        """The time-weighted mean over the observed period."""
        self._advance(self._window.end)
        return self._area / self._window.period

    def maximum(self) -> float:
        """The largest value in the observed period."""
        self._advance(self._window.end)
        assert self._max is not None  # the end is after warm-up
        return self._max

    def _advance(self, time: float) -> None:
        if time < self._time:
            raise ValueError(f"time {time!r} s is before the last change at {self._time!r} s")
        start = max(self._time, self._window.warmup)
        stop = min(time, self._window.end)
        if stop > start:
            self._area += self._value * (stop - start)
        if self._max is None and time > self._window.warmup:
            # The value held since before warm-up is still held after it.
            self._max = self._value
        self._time = time


class Tally:
    """Observations of one kind, such as waits; their plain mean."""

    def __init__(self) -> None:
        self.count = 0
        self._total = 0.0

    def observe(self, value: float) -> None:
        """Adds one observation."""
        self.count += 1
        self._total += value

    def mean(self) -> float:
        """The mean of the observations, NaN when there are none."""
        return self._total / self.count if self.count else math.nan
