"""Test adapters for the run endpoints (AKS-112).

The run target creates the adapter's class with no arguments in its spawned worker, so this
module must be importable there: pytest puts ``tests/`` on ``sys.path`` (``tests/service``
is a package), and ``spawn`` passes ``sys.path`` to the child.

``GatedAdapter`` (engine name ``gated``) reports ``Progress(0.5, "Waiting")`` and then waits
until a file named ``GO`` appears in its workdir (the run folder's ``engine/``), or until it
is cancelled; a test controls when each run ends by writing that file. Its results are a
``replications`` table holding a NaN value and a ``timeseries`` table.
"""

from __future__ import annotations

import json
import math
import os
import time
from collections.abc import Callable
from pathlib import Path

import pyarrow as pa

from lcsim.engines.adapter import CancelToken, Capabilities, Progress, Results
from lcsim.model.catalogue import PROCESS_TYPES
from lcsim.model.issues import Issue
from lcsim.model.model import Model

GO_FILE = "GO"
RUN_RECORD = "run.json"
WAITING = "Waiting"


class GatedAdapter:
    """Waits for ``GO`` in its workdir, or for cancel (at most 60 s)."""

    name = "gated"
    version = "1.0.0"

    def capabilities(self) -> Capabilities:
        return Capabilities(
            domains=("process",),
            component_types=PROCESS_TYPES,
            hardware=(),
            parallel_modes=("replications",),
            licence="MIT",
            invocation="in-process",
        )

    def validate(self, model: Model) -> list[Issue]:
        return []

    def translate(self, model: Model, experiment_id: str | None, workdir: Path) -> None:
        (workdir / "input.json").write_text(json.dumps({"experiment": experiment_id}))

    def run(
        self,
        workdir: Path,
        on_progress: Callable[[Progress], None],
        cancel: CancelToken,
        workers: int,
    ) -> None:
        (workdir / RUN_RECORD).write_text(json.dumps({"pid": os.getpid(), "workers": workers}))
        on_progress(Progress(0.5, WAITING))
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if cancel.is_set():
                return
            if (workdir / GO_FILE).exists():
                on_progress(Progress(0.9, "Finishing"))
                return
            time.sleep(0.02)

    def collect(self, workdir: Path) -> Results:
        replications = pa.table(
            {
                "scenario": ["default", "default"],
                "replication": [0, 1],
                "metric": ["till.wait.mean", "till.wait.mean"],
                "value": [12.5, math.nan],
                "unit": ["s", "s"],
            }
        )
        timeseries = pa.table(
            {
                "scenario": ["default"],
                "replication": [0],
                "metric": ["model.wip"],
                "time_s": [0.0],
                "value": [0.1],
                "unit": ["1"],
            }
        )
        return Results(tables={"replications": replications, "timeseries": timeseries}, warnings=[])
