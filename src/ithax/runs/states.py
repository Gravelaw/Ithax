"""Job states and their allowed moves (spec 1 "Run targets" and "Run folder and results").

The moves are ``queued`` to ``running``; ``running`` to ``done``, ``failed`` or
``cancelled``; ``queued`` to ``cancelled``; and ``queued`` to ``failed``, which only E191
uses, for a queued run whose process is gone (AKS-103, owner to confirm). Every other move
is refused with ``StateError``.
"""

from __future__ import annotations

from typing import Literal, TypeAlias, get_args

__all__ = ["ALLOWED_MOVES", "FINAL_STATES", "JOB_STATES", "JobState", "StateError", "check_move"]

JobState: TypeAlias = Literal["queued", "running", "done", "failed", "cancelled"]
JOB_STATES: tuple[JobState, ...] = get_args(JobState)

#: The states a run never leaves.
FINAL_STATES: tuple[JobState, ...] = ("done", "failed", "cancelled")

ALLOWED_MOVES: frozenset[tuple[JobState, JobState]] = frozenset(
    {
        ("queued", "running"),
        ("running", "done"),
        ("running", "failed"),
        ("running", "cancelled"),
        ("queued", "cancelled"),
        ("queued", "failed"),
    }
)


class StateError(ValueError):
    """A move between job states that spec 1 does not allow: a fault in the caller."""


def check_move(old: str, new: str) -> None:
    """Raises ``StateError`` unless a run may move from ``old`` to ``new``."""
    if (old, new) not in ALLOWED_MOVES:
        raise StateError(f"a run cannot move from {old!r} to {new!r}")
