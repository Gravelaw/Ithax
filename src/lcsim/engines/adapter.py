"""The engine adapter interface (spec 1 "Engine contract" and "Engine adapter interface").

Every engine is driven through one adapter class that implements ``EngineAdapter``; the
core finds adapters as plugins (``lcsim.engines.registry``). The values that cross the
interface are defined here:

- ``Capabilities``: what an adapter runs and how (spec 1 "Engine adapter interface"): its
  domains, its component types with their settings and ports, its hardware needs, its
  parallel modes, the engine's licence identifier and how the engine is invoked (spec 1
  "Engine licence rule");
- ``Progress``: ``fraction`` from 0 to 1, a ``message``, and optional live ``metrics``;
- ``Results``: the tables an adapter collects, its warnings, and an optimization
  adapter's ``solution`` (spec 1 "Division of labour").

``CancelToken`` is supplied by the run target, never by the adapter: a
``multiprocessing.Event`` on the local target.

A component type is described by the model layer's ``BlockType`` (settings and ports),
the same description the ``process`` catalogue uses, so that an adapter's
``capabilities()`` can be compared with that catalogue (spec 1 "Validation").
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Protocol, TypeAlias, get_args, runtime_checkable

import pyarrow as pa

from lcsim.model.catalogue import BlockType
from lcsim.model.issues import Issue
from lcsim.model.model import Model

__all__ = [
    "INVOCATIONS",
    "PARALLEL_MODES",
    "CancelToken",
    "Capabilities",
    "EngineAdapter",
    "Invocation",
    "ParallelMode",
    "Progress",
    "Results",
    "Table",
]

# Spec 1 "Division of labour": a pyarrow Arrow table.
Table: TypeAlias = pa.Table

# Spec 1 "Division of labour": ``Capabilities.parallel_modes`` is drawn from these.
ParallelMode = Literal["replications", "threads", "processes", "gpu"]
PARALLEL_MODES: tuple[ParallelMode, ...] = get_args(ParallelMode)

# Spec 1 "Engine licence rule": the engine runs as a separate process through its own
# files, or is imported into the service process.
Invocation = Literal["process", "in-process"]
INVOCATIONS: tuple[Invocation, ...] = get_args(Invocation)


@runtime_checkable
class CancelToken(Protocol):
    """Set when the run is to stop; ``run`` checks it at least once a second."""

    def is_set(self) -> bool: ...


@dataclass(frozen=True)
class Capabilities:
    """What an adapter declares about its engine (spec 1 "Engine adapter interface").

    ``domains`` are the ``domain`` values it runs. ``component_types`` maps each component
    type it runs to that type's settings and ports. ``hardware`` names what the engine needs
    beyond a CPU and memory, such as ``gpu``; empty for none. ``parallel_modes`` is drawn
    from ``PARALLEL_MODES``. ``licence`` is the engine's SPDX licence identifier, and
    ``invocation`` is ``process`` or ``in-process`` (spec 1 "Engine licence rule").

    ``component_types`` is kept as a read-only copy. A word outside its list, or an empty
    licence, raises ``ValueError``: the adapter is wrong, not the user's model.
    """

    domains: tuple[str, ...]
    component_types: Mapping[str, BlockType]
    hardware: tuple[str, ...]
    parallel_modes: tuple[ParallelMode, ...]
    licence: str
    invocation: Invocation

    def __post_init__(self) -> None:
        unknown = [mode for mode in self.parallel_modes if mode not in PARALLEL_MODES]
        if unknown:
            raise ValueError(
                f"parallel mode {unknown[0]!r} is not one of {', '.join(PARALLEL_MODES)}"
            )
        if self.invocation not in INVOCATIONS:
            raise ValueError(
                f"invocation {self.invocation!r} is not one of {', '.join(INVOCATIONS)}"
            )
        if not self.licence:
            raise ValueError("an engine's capabilities need its licence identifier")
        object.__setattr__(self, "component_types", MappingProxyType(dict(self.component_types)))


@dataclass(frozen=True)
class Progress:
    """A progress report from ``run``: ``fraction`` from 0 to 1, a ``message`` such as
    "Scenario 1 of 2, replication 12 of 30", and optional live ``metrics``.

    A ``fraction`` outside 0 to 1, or not a number, raises ``ValueError``.
    """

    fraction: float
    message: str
    metrics: Mapping[str, float] | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.fraction <= 1 or math.isnan(self.fraction):
            raise ValueError(f"progress fraction {self.fraction!r} is not from 0 to 1")


@dataclass(frozen=True)
class Results:
    """What ``collect`` returns (spec 1 "Division of labour").

    ``tables`` are named as spec 1 "Run folder and results" names them (``replications``,
    ``timeseries``); ``warnings`` are issue objects; ``solution`` is set by optimization
    adapters only, in the ``summary.json`` layout of spec 2 "Optimization model layout".
    """

    tables: dict[str, Table]
    warnings: list[Issue]
    solution: dict[str, Any] | None = None


@runtime_checkable
class EngineAdapter(Protocol):
    """One engine's adapter (spec 1 "Engine contract").

    ``name`` is the adapter name that ``run.engine`` refers to, equal to its entry-point
    name; ``version`` is the adapter's version.
    """

    name: str
    version: str

    def capabilities(self) -> Capabilities: ...
    def validate(self, model: Model) -> list[Issue]: ...
    def translate(self, model: Model, experiment_id: str, workdir: Path) -> None: ...
    def run(
        self,
        workdir: Path,
        on_progress: Callable[[Progress], None],
        cancel: CancelToken,
        workers: int,
    ) -> None: ...
    def collect(self, workdir: Path) -> Results: ...
