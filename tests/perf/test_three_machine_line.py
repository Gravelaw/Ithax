"""Spec 2 acceptance (M3 measured, owner confirms): "A 30-replication run of the
three-machine line finishes in under one minute (proposed target; measured per the Build
guide protocol, confirmed by the owner)" (AKS-104).

Run with ``taskset -c 0-3 pytest -m perf`` (guide "Performance measurement protocol"). The
run is ``examples/three_machine_line.json`` unchanged (its experiment ``base``: 30
replications of 100 h after 20 h of warm-up, seed 12345) through the local target, from
``create`` to the end of ``execute``: loading, validate, translate, the worker process,
collect and writing the run folder. ``workers`` is the number of cores this process may
use, as the service gives a run the cores of the active tier (spec 3 "Run queue"); under
``taskset -c 0-3`` that is 4, the low tier's cores.

Recorded: the wall time; peak resident memory from ``resource.getrusage`` (``null`` on
Windows, which has no ``resource``) for this process (``RUSAGE_SELF``) and for the largest of
its finished children, the worker and the pool
processes it started (``RUSAGE_CHILDREN``); the peak resident memory of this process and
all its descendants together, sampled from ``/proc`` every 0.1 s; core counts, physical
memory, and the Python and library versions.
"""

import importlib
import os
import platform
import sys
import threading
import time
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal

import pytest

from lcsim.runs.limits import process_tree_memory, system_memory
from lcsim.runs.targets import LocalTarget

pytestmark = pytest.mark.perf

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "three_machine_line.json"

#: Spec 2's proposed target, in seconds.
TARGET_S = 60.0
#: Libraries whose versions the result depends on.
LIBRARIES = ("lcsim", "numpy", "scipy", "pyarrow", "simpy", "pint", "jsonschema", "pytest")


def usable_cores() -> int:
    """The cores this process may run on (its affinity set where the system has one)."""
    affinity = getattr(os, "sched_getaffinity", None)
    if affinity is not None:
        return len(affinity(0))
    return os.cpu_count() or 1


def max_rss_bytes(who: Literal["self", "children"]) -> int | None:
    """Peak resident memory from ``resource.getrusage`` (``RUSAGE_SELF`` or
    ``RUSAGE_CHILDREN``) in bytes: Linux reports KiB, macOS bytes. ``None`` where the
    ``resource`` module does not exist (Windows), which is imported here, not at the top,
    so that the module still loads there (pytest imports it before deselecting ``perf``)."""
    try:
        resource = importlib.import_module("resource")
    except ImportError:
        return None
    flag = resource.RUSAGE_SELF if who == "self" else resource.RUSAGE_CHILDREN
    value: int = resource.getrusage(flag).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


class TreeMemorySampler:
    """Samples the resident memory of this process and its descendants every 0.1 s."""

    def __init__(self) -> None:
        self.peak: int | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)

    def _sample(self) -> None:
        while True:
            reading = process_tree_memory(os.getpid())
            if reading is not None:
                self.peak = reading if self.peak is None else max(self.peak, reading)
            if self._stop.wait(0.1):
                return

    def __enter__(self) -> "TreeMemorySampler":
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join()


def mib(size: int | None) -> float | None:
    return None if size is None else round(size / 2**20, 1)


def test_a_30_replication_run_of_the_three_machine_line_finishes_in_under_a_minute(
    tmp_path: Path, perf_record: Callable[[dict[str, Any]], None]
) -> None:
    model_file = EXAMPLE.read_bytes()
    workers = usable_cores()
    with TreeMemorySampler() as sampler:
        started = time.perf_counter()
        run = LocalTarget(tmp_path / "runs", workers=workers).create(model_file, "base")
        state = run.execute()
        wall_s = time.perf_counter() - started
    assert state == "done"
    summary = (run.folder / "summary.json").read_text(encoding="utf-8")
    assert '"replications": 30' in summary
    memory = system_memory()
    record = {
        "check": "three_machine_line, 30 replications, local target",
        "wall_s": round(wall_s, 2),
        "target_s": TARGET_S,
        "workers": workers,
        "peak_rss_self_mib": mib(max_rss_bytes("self")),
        "peak_rss_children_mib": mib(max_rss_bytes("children")),
        "peak_rss_tree_mib": mib(sampler.peak),
        "cpu_count": os.cpu_count(),
        "affinity_cores": usable_cores(),
        "memory_gib": None if memory is None else round(memory / 2**30, 2),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "libraries": {name: version(name) for name in LIBRARIES},
    }
    perf_record(record)
    assert wall_s < TARGET_S, record
