"""The process adapter: the ``process`` domain on SimPy (spec 2).

Registered in ``pyproject.toml`` as entry point ``simpy`` in group ``lcsim.engines``
(spec 1 "Engine contract"). Its ``capabilities()`` reports the model layer's ``process``
catalogue (``lcsim.model.catalogue.PROCESS_TYPES``), which spec 1 "Validation" requires it
to equal, and SimPy's licence (MIT) and invocation (imported, ``in-process``; spec 1
"Engine licence rule").

``translate`` writes ``workdir/input.json`` (``lcsim.engines.process.translate``); ``run``
runs every scenario and replication from it (``lcsim.engines.process.runner``) and writes
``workdir/output/replications.parquet`` and ``workdir/output/timeseries.parquet`` once all
have finished, nothing when cancelled; ``collect`` reads both tables into ``Results``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pyarrow.parquet as pq

import lcsim
from lcsim.engines.adapter import CancelToken, Capabilities, Progress, Results
from lcsim.engines.process.runner import (
    REPLICATIONS_SCHEMA,
    TIMESERIES_SCHEMA,
    replications_table,
    run_all,
    timeseries_table,
    write_table,
)
from lcsim.engines.process.translate import read_input, write_input
from lcsim.model.catalogue import PROCESS_TYPES
from lcsim.model.issues import Issue
from lcsim.model.model import Model

__all__ = ["REPLICATIONS_FILE", "TIMESERIES_FILE", "ProcessAdapter"]

#: Where ``run`` writes the ``replications`` table, relative to ``workdir``.
REPLICATIONS_FILE = Path("output") / "replications.parquet"
#: Where ``run`` writes the ``timeseries`` table, relative to ``workdir``.
TIMESERIES_FILE = Path("output") / "timeseries.parquet"


class ProcessAdapter:
    """The SimPy adapter for the ``process`` domain."""

    name: str = "simpy"
    # The product's own adapters ship with the product, so they carry its version.
    version: str = lcsim.__version__

    def capabilities(self) -> Capabilities:
        """The ``process`` domain, the twelve types of the model layer's catalogue, no
        special hardware, parallel replications, MIT, imported into the process."""
        return Capabilities(
            domains=("process",),
            component_types=PROCESS_TYPES,
            hardware=(),
            parallel_modes=("replications",),
            licence="MIT",
            invocation="in-process",
        )

    def validate(self, model: Model) -> list[Issue]:
        """Checks beyond the common ones (codes E300 to E399): none so far."""
        return []

    def translate(self, model: Model, experiment_id: str, workdir: Path) -> None:
        """Writes the engine input of experiment ``experiment_id`` to
        ``workdir/input.json``."""
        write_input(model, experiment_id, workdir)

    def run(
        self,
        workdir: Path,
        on_progress: Callable[[Progress], None],
        cancel: CancelToken,
        workers: int,
    ) -> None:
        """Runs every scenario and replication with up to ``workers`` processes, then
        writes the ``replications`` and ``timeseries`` tables; writes nothing when
        ``cancel`` is set."""
        engine_input = read_input(workdir)
        for output in (REPLICATIONS_FILE, TIMESERIES_FILE):
            (workdir / output).unlink(missing_ok=True)
        done = run_all(workdir, engine_input, on_progress, cancel, workers)
        if done is not None:
            write_table(timeseries_table(engine_input, done), workdir / TIMESERIES_FILE)
            write_table(replications_table(engine_input, done), workdir / REPLICATIONS_FILE)

    def collect(self, workdir: Path) -> Results:
        """The ``replications`` and ``timeseries`` tables ``run`` wrote;
        ``FileNotFoundError`` when ``run`` did not finish."""
        replications = pq.read_table(workdir / REPLICATIONS_FILE, schema=REPLICATIONS_SCHEMA)
        timeseries = pq.read_table(workdir / TIMESERIES_FILE, schema=TIMESERIES_SCHEMA)
        return Results(tables={"replications": replications, "timeseries": timeseries}, warnings=[])
