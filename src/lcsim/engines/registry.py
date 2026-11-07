"""Engine discovery and selection (spec 1 "Engine contract" and "Top-level keys").

Adapters are Python entry points in group ``lcsim.engines``, each naming a class that
implements ``EngineAdapter``; the product's own adapters are registered the same way in
its ``pyproject.toml`` (confirmed by ``docs/research/spec-1-plugin-mechanisms.md``).

``load_adapters`` lists the entry points without importing them, then loads each inside a
guard. Left out and logged, never fatal:

- every entry point whose name is shared with another, without importing either;
- one that fails to import, whose object cannot be created with no arguments, whose
  object does not provide the ``EngineAdapter`` members (with ``name`` and ``version`` as
  text), whose ``capabilities()`` fails or does not return ``Capabilities``, or whose
  ``name`` differs from its entry-point name.

``installed_adapters`` runs discovery once per process. ``installed_engines`` turns
adapters into the model layer's ``InstalledEngine`` records. Every Phase 1 domain has its
adapter from M5, so a domain no installed adapter handles is E102 (the model layer's
stand-in for ``optimization`` is gone; AKS-108).
``select_adapter`` picks the adapter for a model's ``domain`` and ``run.engine`` by the
spec 1 "Top-level keys" rule, with E102 at ``/domain`` or ``/run/engine``.
"""

from __future__ import annotations

import functools
import logging
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points
from types import MappingProxyType

from lcsim.engines.adapter import Capabilities, EngineAdapter
from lcsim.model.issues import Issue
from lcsim.model.validation import InstalledEngine, engine_issues

__all__ = [
    "ENTRY_POINT_GROUP",
    "Selection",
    "installed_adapters",
    "installed_engines",
    "load_adapters",
    "select_adapter",
]

# Spec 1 "Engine contract": renamed with the placeholder package before the first release.
ENTRY_POINT_GROUP = "lcsim.engines"

_log = logging.getLogger(__name__)


def load_adapters() -> dict[str, EngineAdapter]:
    """Every installed adapter that loads, by entry-point name, in name order.

    Reads the entry points afresh on each call; ``installed_adapters`` keeps the first
    result for the process.
    """
    points = sorted(entry_points(group=ENTRY_POINT_GROUP), key=lambda point: point.name)
    counts = Counter(point.name for point in points)
    adapters: dict[str, EngineAdapter] = {}
    for name, count in counts.items():
        if count > 1:
            values = ", ".join(point.value for point in points if point.name == name)
            _log.warning(
                "Engine entry points %r (%s) share one name; all %d are left out.",
                name,
                values,
                count,
            )
    for point in points:
        if counts[point.name] == 1 and (adapter := _load(point)) is not None:
            adapters[point.name] = adapter
    return adapters


def _load(point: EntryPoint) -> EngineAdapter | None:
    """The adapter an entry point names, or ``None`` after logging why it is left out."""
    try:
        adapter = point.load()()
        problem = _problem(point, adapter)
    except Exception:
        _log.warning(
            "Engine entry point %r (%s) failed to load and is left out.",
            point.name,
            point.value,
            exc_info=True,
        )
        return None
    if problem is not None:
        _log.warning(
            "Engine entry point %r (%s) is left out: %s.", point.name, point.value, problem
        )
        return None
    assert isinstance(adapter, EngineAdapter)  # _problem checked it
    return adapter


def _problem(point: EntryPoint, adapter: object) -> str | None:
    """Why ``adapter``, made from ``point``, cannot be used, or ``None``."""
    if not (
        isinstance(adapter, EngineAdapter)
        and isinstance(adapter.name, str)
        and isinstance(adapter.version, str)
    ):
        return "its object does not provide the EngineAdapter members"
    if adapter.name != point.name:
        return f"its adapter is named {adapter.name!r}"
    if not isinstance(adapter.capabilities(), Capabilities):
        return "its capabilities() does not return Capabilities"
    return None


@functools.cache
def installed_adapters() -> Mapping[str, EngineAdapter]:
    """The installed adapters, discovered on the first call and kept for the process.

    An engine installed later is found after a restart (spec 1 "Engine contract").
    """
    return MappingProxyType(load_adapters())


def installed_engines(
    adapters: Mapping[str, EngineAdapter] | None = None,
) -> tuple[InstalledEngine, ...]:
    """The engines that engine selection sees: one per adapter, by name.

    ``adapters`` defaults to ``installed_adapters()``.
    """
    if adapters is None:
        adapters = installed_adapters()
    return tuple(
        InstalledEngine(name, adapters[name].capabilities().domains) for name in sorted(adapters)
    )


@dataclass(frozen=True)
class Selection:
    """The adapter chosen for a model, or the issues that stop the choice.

    ``adapter`` is ``None`` exactly when ``issues`` holds the E102 issue: no single engine
    handles the domain.
    """

    adapter: EngineAdapter | None
    issues: tuple[Issue, ...]


def select_adapter(
    domain: str,
    engine: str | None,
    adapters: Mapping[str, EngineAdapter] | None = None,
) -> Selection:
    """The adapter for a model of ``domain`` whose ``run.engine`` is ``engine`` (``None``
    when the file has none), by spec 1 "Top-level keys".

    ``adapters`` defaults to ``installed_adapters()``.
    """
    if adapters is None:
        adapters = installed_adapters()
    issues = engine_issues(domain, engine, installed_engines(adapters))
    if issues:
        return Selection(None, tuple(issues))
    chosen = [
        adapter
        for name, adapter in adapters.items()
        if domain in adapter.capabilities().domains and engine in (None, name)
    ]
    # engine_issues found exactly one engine, and every engine is an adapter.
    [adapter] = chosen
    return Selection(adapter, ())
