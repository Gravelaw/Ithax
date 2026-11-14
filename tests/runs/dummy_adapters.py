"""Minimal test adapters for the local run target (AKS-103).

They implement the spec 1 adapter interface without an engine. The run target creates
the adapter's class with no arguments in its spawned worker process, so this module must
be importable there: pytest puts ``tests/runs`` on ``sys.path``, and ``spawn`` passes
``sys.path`` to the child.

Each method records where it ran: the parent instance keeps ``calls`` (method name and
process id); ``run``, which runs in the worker process, writes ``run.json`` in its
workdir instead, since the worker's instance is a different object.
"""

from __future__ import annotations

import json
import math
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pyarrow as pa

from ithax.engines.adapter import CancelToken, Capabilities, Progress, Results
from ithax.engines.optimize.adapter import HighsAdapter
from ithax.engines.optimize.solver import solve
from ithax.engines.optimize.translate import read_input
from ithax.model.catalogue import PROCESS_TYPES
from ithax.model.issues import Issue
from ithax.model.model import Model
from ithax.model.units import Quantity

RUN_RECORD = "run.json"
INPUT_FILE = "dummy_input.json"
OUTPUT_FILE = "dummy_output.json"


class DummyAdapter:
    """Passes through all five methods; reports two progress values."""

    name = "dummy"
    version = "9.9.9"

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []
        self.issues: list[Issue] = []
        self.on_translate: Callable[[], object] | None = None
        self.on_collect: Callable[[], object] | None = None

    def capabilities(self) -> Capabilities:
        self.calls.append(("capabilities", os.getpid()))
        return Capabilities(
            domains=("process",),
            component_types=PROCESS_TYPES,
            hardware=(),
            parallel_modes=("replications",),
            licence="MIT",
            invocation="in-process",
        )

    def validate(self, model: Model) -> list[Issue]:
        self.calls.append(("validate", os.getpid()))
        return list(self.issues)

    def translate(self, model: Model, experiment_id: str | None, workdir: Path) -> None:
        self.calls.append(("translate", os.getpid()))
        (workdir / INPUT_FILE).write_text(
            json.dumps({"experiment": experiment_id, "model": model.meta.name}), encoding="utf-8"
        )
        if self.on_translate is not None:
            self.on_translate()

    def run(
        self,
        workdir: Path,
        on_progress: Callable[[Progress], None],
        cancel: CancelToken,
        workers: int,
    ) -> None:
        engine_input = json.loads((workdir / INPUT_FILE).read_text(encoding="utf-8"))
        record = {"pid": os.getpid(), "workers": workers, "input": engine_input}
        (workdir / RUN_RECORD).write_text(json.dumps(record), encoding="utf-8")
        self.work(workdir, on_progress, cancel)

    def work(
        self, workdir: Path, on_progress: Callable[[Progress], None], cancel: CancelToken
    ) -> None:
        on_progress(Progress(0.5, "Replication 1 of 2"))
        on_progress(Progress(1.0, "Replication 2 of 2"))
        (workdir / OUTPUT_FILE).write_text("[0.5, 0.7]", encoding="utf-8")

    def collect(self, workdir: Path) -> Results:
        self.calls.append(("collect", os.getpid()))
        if self.on_collect is not None:
            self.on_collect()
        values = json.loads((workdir / OUTPUT_FILE).read_text(encoding="utf-8"))
        table = pa.table(
            {
                "scenario": ["default"] * len(values),
                "replication": list(range(len(values))),
                "metric": ["till.utilization"] * len(values),
                "value": [float(value) for value in values],
                "unit": ["1"] * len(values),
            }
        )
        return Results(tables={"replications": table}, warnings=[])


class SlowAdapter(DummyAdapter):
    """Reports progress every 0.05 s until cancelled (at most 30 s)."""

    def work(
        self, workdir: Path, on_progress: Callable[[Progress], None], cancel: CancelToken
    ) -> None:
        deadline = time.monotonic() + 30
        while not cancel.is_set() and time.monotonic() < deadline:
            on_progress(Progress(0.25, "Working"))
            time.sleep(0.05)


class StubbornAdapter(DummyAdapter):
    """Ignores cancel and sleeps for 30 s."""

    def work(
        self, workdir: Path, on_progress: Callable[[Progress], None], cancel: CancelToken
    ) -> None:
        on_progress(Progress(0.1, "Ignoring cancel"))
        time.sleep(30)


class FailingAdapter(DummyAdapter):
    """``run`` raises with a detail that must stay out of the issue's message."""

    def work(
        self, workdir: Path, on_progress: Callable[[Progress], None], cancel: CancelToken
    ) -> None:
        raise RuntimeError("secret engine detail 4711")


class CrashingAdapter(DummyAdapter):
    """``run`` ends its process without reporting."""

    def work(
        self, workdir: Path, on_progress: Callable[[Progress], None], cancel: CancelToken
    ) -> None:
        os._exit(7)


class TranslateFailingAdapter(DummyAdapter):
    """``translate`` raises, in the process that drives the run."""

    def translate(self, model: Model, experiment_id: str | None, workdir: Path) -> None:
        raise OSError("translate detail 815")


class CollectFailingAdapter(DummyAdapter):
    """``collect`` raises, in the process that drives the run."""

    def collect(self, workdir: Path) -> Results:
        raise KeyError("collect detail 42")


GRANDCHILD_RECORD = "grandchild.json"


class SpawningStubbornAdapter(DummyAdapter):
    """Starts a child process of its own (recorded in ``grandchild.json``), then ignores
    cancel and sleeps for 30 s."""

    def work(
        self, workdir: Path, on_progress: Callable[[Progress], None], cancel: CancelToken
    ) -> None:
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        (workdir / GRANDCHILD_RECORD).write_text(json.dumps(child.pid), encoding="utf-8")
        on_progress(Progress(0.1, "Ignoring cancel"))
        time.sleep(30)


class LingeringAdapter(DummyAdapter):
    """Returns at once but leaves a non-daemon thread sleeping for 30 s, so its process
    reports, closes its pipe and then does not end."""

    def work(
        self, workdir: Path, on_progress: Callable[[Progress], None], cancel: CancelToken
    ) -> None:
        threading.Thread(target=time.sleep, args=(30,), daemon=False).start()


class BadTablesAdapter(DummyAdapter):
    """``collect`` returns a table spec 1 does not name, which writing refuses."""

    def collect(self, workdir: Path) -> Results:
        results = super().collect(workdir)
        return Results(tables={"bad_table": results.tables["replications"]}, warnings=[])


class TermIgnoringAdapter(DummyAdapter):
    """Ignores SIGTERM and cancel, and sleeps for 30 s (POSIX)."""

    def work(
        self, workdir: Path, on_progress: Callable[[Progress], None], cancel: CancelToken
    ) -> None:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        on_progress(Progress(0.1, "Ignoring cancel and SIGTERM"))
        time.sleep(30)


class IterationLimitedAdapter(HighsAdapter):
    """The HiGHS adapter with a simplex iteration limit of 0 and presolve off, so that
    HiGHS really ends with ``iterationLimit`` in the worker (AKS-108)."""

    def run(
        self,
        workdir: Path,
        on_progress: Callable[[Progress], None],
        cancel: CancelToken,
        workers: int,
    ) -> None:
        solve(read_input(workdir), options={"simplex_iteration_limit": 0, "presolve": "off"})


SEARCH_INPUT = "search_input.json"
SEARCH_OUTPUT = "search_output.json"


def search_metrics(recipe: str, values: dict[str, float], replication: int) -> dict[str, float]:
    """The metrics ``SearchAdapter`` reports for one replication: ``till.wait.mean`` (the
    objective) and ``till.utilization`` (the constraint), chosen by the model's name.

    - ``bowl``: wait (tills - 4)² plus a little noise, utilization 1/tills, so with
      utilization >= 0.2 the feasible tills are 1 to 5 and the best is 4; with a second
      parameter ``staff``, wait adds (staff - 2)².
    - ``late``: utilization is 1 at replications 0 to 9 for tills 2 or more and 0 after, and
      the reverse for tills 1, so every candidate but tills 1 is feasible at a search stage
      of 10 replications (0 to 9) and infeasible confirmed at 30 (replications 10 to 39,
      #79: mean 0), while tills 1 is the reverse (mean 1); tills 6 stays feasible
      (utilization 1) when ``rescue`` is in the recipe. Wait is tills, so the larger tills
      look worse.
    - ``flat``: wait 10 + (r mod 3 - 1) x tills, utilization 1: every candidate has mean
      wait 10 over 30 replications, and two differ by a spread around 0.
    - ``nan``: wait NaN for tills 2, otherwise tills; utilization 1.
    - ``mixed``: wait (rate - 1)² + (delay / 60 - 2)² + (tills - 2)², utilization 1.
    """
    tills = values.get("tills", 1.0)
    r = replication
    if recipe == "bowl":
        wait = (tills - 4) ** 2 + 0.01 * (r % 2) + (values.get("staff", 2.0) - 2) ** 2
        return {"till.wait.mean": wait, "till.utilization": 1 / tills}
    if recipe.startswith("late"):
        early = r < 10
        if tills == 1:
            utilization = 0.0 if early else 1.0
        elif tills == 6 and "rescue" in recipe:
            utilization = 1.0
        else:
            utilization = 1.0 if early else 0.0
        return {"till.wait.mean": tills, "till.utilization": utilization}
    if recipe == "flat":
        return {"till.wait.mean": 10 + (r % 3 - 1) * tills, "till.utilization": 1.0}
    if recipe == "nan":
        return {"till.wait.mean": math.nan if tills == 2 else tills, "till.utilization": 1.0}
    if recipe == "mixed":
        wait = (values["rate"] - 1) ** 2 + (values["delay"] / 60 - 2) ** 2 + (tills - 2) ** 2
        return {"till.wait.mean": wait, "till.utilization": 1.0}
    raise ValueError(f"no recipe {recipe!r}")


class SearchAdapter(DummyAdapter):
    """A process adapter whose metrics are a function of the candidate's parameter values
    and the replication number (``search_metrics``, by the model's name), so that a search
    can be followed exactly. ``translate`` writes the experiment's replications and the
    values of every parameter in its one scenario; ``run`` writes the metrics; ``collect``
    returns the ``replications`` table and, for a recipe ending in ``drift``, a
    ``timeseries`` table whose ``till.queue_length`` doubles after warm-up."""

    def translate(self, model: Model, experiment_id: str | None, workdir: Path) -> None:
        self.calls.append(("translate", os.getpid()))
        [experiment] = [item for item in model.experiments if item.id == experiment_id]
        [scenario] = experiment.scenarios
        values = {
            name: float(value.magnitude if isinstance(value, Quantity) else value)
            for name, value in {
                **{name: parameter.value for name, parameter in model.parameters.items()},
                **scenario.set,
            }.items()
        }
        document = {
            "recipe": model.meta.name,
            "replications": experiment.replications,
            "first_replication": experiment.first_replication,
            "warmup": experiment.warmup.magnitude,
            "values": values,
        }
        (workdir / SEARCH_INPUT).write_text(json.dumps(document), encoding="utf-8")
        if self.on_translate is not None:
            self.on_translate()

    def run(
        self,
        workdir: Path,
        on_progress: Callable[[Progress], None],
        cancel: CancelToken,
        workers: int,
    ) -> None:
        document = json.loads((workdir / SEARCH_INPUT).read_text(encoding="utf-8"))
        recipe = document["recipe"].removesuffix(" drift")
        rows = []
        count, first = document["replications"], document["first_replication"]
        for done, replication in enumerate(range(first, first + count), start=1):
            for metric, value in search_metrics(recipe, document["values"], replication).items():
                rows.append([replication, metric, value])
            on_progress(Progress(done / count, f"Replication {done}"))
        (workdir / SEARCH_OUTPUT).write_text(json.dumps(rows), encoding="utf-8")

    def collect(self, workdir: Path) -> Results:
        self.calls.append(("collect", os.getpid()))
        if self.on_collect is not None:
            self.on_collect()
        rows = json.loads((workdir / SEARCH_OUTPUT).read_text(encoding="utf-8"))
        table = pa.table(
            {
                "scenario": ["default"] * len(rows),
                "replication": [row[0] for row in rows],
                "metric": [row[1] for row in rows],
                "value": [float(row[2]) for row in rows],
                "unit": ["s" if row[1].endswith("wait.mean") else "1" for row in rows],
            }
        )
        tables = {"replications": table}
        document = json.loads((workdir / SEARCH_INPUT).read_text(encoding="utf-8"))
        if document["recipe"].endswith("drift"):
            count = document["replications"]
            times = [document["warmup"] + 60.0 * k for k in range(4)]
            tables["timeseries"] = pa.table(
                {
                    "scenario": ["default"] * 4 * count,
                    "replication": [rep for rep in range(count) for _ in times],
                    "metric": ["till.queue_length"] * 4 * count,
                    "time_s": times * count,
                    "value": [value + rep % 2 for rep in range(count) for value in (1, 1, 2, 2)],
                    "unit": ["1"] * 4 * count,
                }
            )
        return Results(tables=tables, warnings=[])


class SearchFailingAdapter(SearchAdapter):
    """``run`` raises at the third evaluation of a search (its folder ``search-002``)."""

    def run(
        self,
        workdir: Path,
        on_progress: Callable[[Progress], None],
        cancel: CancelToken,
        workers: int,
    ) -> None:
        if workdir.name == "search-002":
            raise RuntimeError("candidate detail 2024")
        super().run(workdir, on_progress, cancel, workers)


class SearchSlowAdapter(SearchAdapter):
    """Waits until cancelled (at most 30 s) at the second evaluation of a search."""

    def run(
        self,
        workdir: Path,
        on_progress: Callable[[Progress], None],
        cancel: CancelToken,
        workers: int,
    ) -> None:
        if workdir.name == "search-001":
            deadline = time.monotonic() + 30
            while not cancel.is_set() and time.monotonic() < deadline:
                on_progress(Progress(0.5, "Working"))
                time.sleep(0.05)
            return
        super().run(workdir, on_progress, cancel, workers)
