"""Run limits (spec 4 "Limits": by default 10 minutes and half of system memory, adjustable;
spec 1 E192; AKS-103).

The time limit counts from the run's ``started``. The memory limit is compared with the
resident memory of the worker process and every process it started (the process adapter's
workers), read from ``/proc``. Where ``/proc`` or the machine's memory size cannot be read
(Windows, macOS), the reading is ``None`` and the memory limit is not enforced
(docs/DECISIONS.md, AKS-103).
"""

from __future__ import annotations

import mmap
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

__all__ = [
    "DEFAULT_TIME_LIMIT_S",
    "PAGE_SIZE",
    "Limits",
    "default_memory_limit",
    "descendant_ids",
    "limit_exceeded",
    "process_tree_memory",
    "system_memory",
]

#: Spec 4 "Limits": 10 minutes.
DEFAULT_TIME_LIMIT_S = 600.0

#: The size of a memory page, the unit of ``/proc/<pid>/statm``.
PAGE_SIZE = mmap.PAGESIZE


def system_memory() -> int | None:
    """The machine's physical memory in bytes, or ``None`` where it cannot be read
    (``os.sysconf`` is missing on Windows)."""
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (AttributeError, ValueError, OSError):
        return None


def default_memory_limit() -> int | None:
    """Half of the machine's physical memory (spec 4 "Limits"), or ``None`` when unknown."""
    total = system_memory()
    return None if total is None else total // 2


@dataclass(frozen=True)
class Limits:
    """A run's time limit in seconds and memory limit in bytes (``None``: not enforced)."""

    time_s: float = DEFAULT_TIME_LIMIT_S
    memory_bytes: int | None = field(default_factory=default_memory_limit)

    def __post_init__(self) -> None:
        if not self.time_s > 0:
            raise ValueError(f"the time limit {self.time_s!r} s is not above 0")
        if self.memory_bytes is not None and self.memory_bytes <= 0:
            raise ValueError(f"the memory limit {self.memory_bytes!r} B is not above 0")


def limit_exceeded(
    limits: Limits, *, elapsed_s: float, memory_bytes: int | None
) -> Literal["time", "memory"] | None:
    """Which limit a run has exceeded, time first, or ``None``. A memory reading of
    ``None``, or no memory limit, is never exceeded."""
    if elapsed_s > limits.time_s:
        return "time"
    if (
        limits.memory_bytes is not None
        and memory_bytes is not None
        and memory_bytes > limits.memory_bytes
    ):
        return "memory"
    return None


def _parent_ids(proc: Path) -> dict[int, int]:
    """Each process id under ``proc`` with its parent's id; processes that end while
    being read are left out."""
    parents: dict[int, int] = {}
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text(encoding="ascii", errors="replace")
        except OSError:
            continue
        # "pid (comm) state ppid ...": comm may hold spaces and parentheses.
        parents[int(entry.name)] = int(stat[stat.rindex(")") + 2 :].split()[1])
    return parents


def _resident(proc: Path, pid: int) -> int:
    """The resident memory of ``pid`` in bytes; 0 when it has ended."""
    try:
        statm = (proc / str(pid) / "statm").read_text(encoding="ascii")
    except OSError:
        return 0
    return int(statm.split()[1]) * PAGE_SIZE


def descendant_ids(pid: int, proc: Path = Path("/proc")) -> list[int]:
    """Every process that ``pid`` started, directly or not, read from ``proc``; empty
    without ``/proc`` (Windows, macOS) or when ``pid`` is not there."""
    if not (proc / str(pid)).is_dir():
        return []
    children: dict[int, list[int]] = {}
    for child, parent in _parent_ids(proc).items():
        children.setdefault(parent, []).append(child)
    found: list[int] = []
    pending = list(children.get(pid, ()))
    while pending:
        current = pending.pop()
        found.append(current)
        pending.extend(children.get(current, ()))
    return found


def process_tree_memory(pid: int, proc: Path = Path("/proc")) -> int | None:
    """The resident memory in bytes of process ``pid`` and every process it started,
    directly or not, read from ``proc``; ``None`` without ``/proc`` or when ``pid`` is
    not there."""
    if not (proc / str(pid)).is_dir():
        return None
    return sum(_resident(proc, current) for current in [pid, *descendant_ids(pid, proc)])
