"""The process adapter: the ``process`` domain on SimPy (spec 2).

Registered in ``pyproject.toml`` as entry point ``simpy`` in group ``lcsim.engines``
(spec 1 "Engine contract"). Its ``capabilities()`` reports the model layer's ``process``
catalogue (``lcsim.model.catalogue.PROCESS_TYPES``), which spec 1 "Validation" requires it
to equal, and SimPy's licence (MIT) and invocation (imported, ``in-process``; spec 1
"Engine licence rule"). ``translate``, ``run`` and ``collect`` are filled in by AKS-98.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import lcsim
from lcsim.engines.adapter import CancelToken, Capabilities, Progress, Results
from lcsim.model.catalogue import PROCESS_TYPES
from lcsim.model.issues import Issue
from lcsim.model.model import Model

__all__ = ["ProcessAdapter"]

_NOT_YET = "the process adapter's {} is built in AKS-98 (M2)"


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
        """Writes SimPy's input into ``workdir``; not built yet."""
        raise NotImplementedError(_NOT_YET.format("translate"))

    def run(
        self,
        workdir: Path,
        on_progress: Callable[[Progress], None],
        cancel: CancelToken,
        workers: int,
    ) -> None:
        """Runs every scenario and replication; not built yet."""
        raise NotImplementedError(_NOT_YET.format("run"))

    def collect(self, workdir: Path) -> Results:
        """Reads the per-replication values into ``Results``; not built yet."""
        raise NotImplementedError(_NOT_YET.format("collect"))
