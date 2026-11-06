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
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pyarrow as pa

from lcsim.engines.adapter import CancelToken, Capabilities, Progress, Results
from lcsim.model.catalogue import PROCESS_TYPES
from lcsim.model.issues import Issue
from lcsim.model.model import Model

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
        self.on_translate: Callable[[], None] | None = None
        self.on_collect: Callable[[], None] | None = None

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

    def translate(self, model: Model, experiment_id: str, workdir: Path) -> None:
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

    def translate(self, model: Model, experiment_id: str, workdir: Path) -> None:
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
