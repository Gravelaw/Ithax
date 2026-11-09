"""Spec 0 "Success measures", low-tier performance, and spec 3 acceptance (M10, agent on a
capped container, owner confirms): "All Phase 1 templates run on a machine or virtual
machine capped to the low tier" (AKS-125).

Run with ``taskset -c 0-3 pytest -m perf`` (guide "Performance measurement protocol") inside
a memory cap of 8 GB, the low tier of spec 0 "Platform and hardware"; how the cap was
enforced in the agent container is in ``docs/research/performance.md``. Each of the ten
template packages under ``templates/`` is run twice, as a learner runs it: the template's
model and its exercise's model (``template.json``'s ``exercise.edits`` applied), each with
the experiment ``template.json`` names (``None`` for an optimization model), through the
local target from ``create`` to the end of ``execute`` (loading, validate, translate, the
engine, collect and the run folder), with ``workers`` the cores this process may use, as in
the M3 check.

Recorded per run: the wall time and the peak resident memory of this process and its
descendants (sampled from ``/proc`` every 0.1 s). Once per session: peak resident memory from
``resource.getrusage`` (``RUSAGE_SELF`` and ``RUSAGE_CHILDREN``), the memory cap this process
runs under (the control group's limit and ``RLIMIT_AS``), core counts, physical memory and the
Python version. Spec 0 sets no time target, only "run to completion"; each run must end
``done``.
"""

import importlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from lcsim.runs.targets import LocalTarget
from lcsim.templates import load_package, package_folders
from lcsim.templates.expected import RUNS, Run
from perf.test_service import machine
from perf.test_three_machine_line import TreeMemorySampler, max_rss_bytes, mib, usable_cores

pytestmark = pytest.mark.perf

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "templates"
BENCHMARK_CASES = frozenset(path.parent.name for path in (ROOT / "benchmarks").glob("*/model.json"))
IDS = [folder.name for folder in package_folders(TEMPLATES)]

#: The low tier's memory, spec 0 "Platform and hardware" (8 GB, read as 8 GiB, the larger).
LOW_TIER_BYTES = 8 * 2**30


def cgroup_memory_limit(
    proc: Path = Path("/proc"), root: Path = Path("/sys/fs/cgroup")
) -> int | None:
    """The memory limit in bytes of the control group this process is in: cgroup v1's
    ``memory.limit_in_bytes`` or v2's ``memory.max``; ``None`` where there is no control
    group (Windows, macOS) or no limit."""
    try:
        lines = (proc / "self" / "cgroup").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        _, controllers, path = line.split(":", 2)
        relative = path.lstrip("/")
        if "memory" in controllers.split(","):
            limit_file = root / "memory" / relative / "memory.limit_in_bytes"
        elif controllers == "":
            limit_file = root / relative / "memory.max"
        else:
            continue
        try:
            text = limit_file.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        # cgroup v1 writes a page-rounded 2**63 - 1 for "no limit"; v2 writes "max".
        if text != "max" and int(text) < 2**62:
            return int(text)
    return None


def address_space_limit() -> int | None:
    """``RLIMIT_AS`` in bytes, ``None`` when unlimited or where ``resource`` does not exist."""
    try:
        resource = importlib.import_module("resource")
    except ImportError:
        return None
    soft: int = resource.getrlimit(resource.RLIMIT_AS)[0]
    return None if soft == resource.RLIM_INFINITY else soft


@pytest.mark.parametrize("run", RUNS)
@pytest.mark.parametrize("tid", IDS)
def test_each_template_runs_to_completion_on_the_low_tier(
    tid: str, run: Run, tmp_path: Path, perf_record: Callable[[dict[str, Any]], None]
) -> None:
    package = load_package(TEMPLATES / tid, benchmark_cases=BENCHMARK_CASES).package
    assert package is not None
    model_file = json.dumps(package.document(run)).encode("utf-8")
    workers = usable_cores()
    with TreeMemorySampler() as sampler:
        started = time.perf_counter()
        local = LocalTarget(tmp_path / "runs", workers=workers).create(
            model_file, package.experiment
        )
        state = local.execute()
        wall_s = time.perf_counter() - started
    record = {
        "check": f"template {tid}, {run}",
        "state": state,
        "wall_s": round(wall_s, 2),
        "workers": workers,
        "peak_rss_tree_mib": mib(sampler.peak),
    }
    perf_record(record)
    assert state == "done", record
    assert (local.folder / "summary.json").is_file()


def test_the_session_records_its_machine_and_memory_cap(
    perf_record: Callable[[dict[str, Any]], None],
) -> None:
    """Runs after the template runs (pytest keeps the file's order), so the ``getrusage``
    peaks cover them; the cap is recorded, not asserted, so the check also runs uncapped."""
    cap = cgroup_memory_limit()
    record = {
        "check": "templates, machine and memory cap",
        "cgroup_memory_limit_gib": None if cap is None else round(cap / 2**30, 2),
        "rlimit_as_gib": None if (limit := address_space_limit()) is None else limit / 2**30,
        "within_low_tier_memory": cap is not None and cap <= LOW_TIER_BYTES,
        "peak_rss_self_mib": mib(max_rss_bytes("self")),
        "peak_rss_children_mib": mib(max_rss_bytes("children")),
        **machine(),
    }
    perf_record(record)
    assert record["affinity_cores"] is not None
