"""The run settings in ``settings.json`` (spec 3 "Run queue"; spec 4 "Limits"; AKS-112,
owner to confirm).

The service reads them from the configuration folder when it starts:

- ``max_concurrent_runs``: a whole number from 1, default 1;
- ``run_time_limit_s``: a number above 0, default 600 (10 minutes);
- ``run_memory_limit_bytes``: a whole number above 0, default half the physical memory
  (not enforced where it cannot be read, spec 1 E192).

A key that is absent takes its default; one holding another value takes its default too,
and that is logged. A file the strict reader refuses (``ithax.strict_json``: not JSON, or
holding ``NaN``, an infinity or text that is not valid Unicode) gives every default (the
tier's own reading of the file, ``ithax.service.hardware.active_tier``, logs and replaces
it). Settings writes the keys at M9.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from ithax.runs.limits import DEFAULT_TIME_LIMIT_S, Limits
from ithax.service.hardware import SETTINGS_FILE
from ithax.strict_json import MAX_WHOLE, read_json_file, real_in, whole_in

__all__ = ["MAX_CONCURRENT_RUNS", "MAX_TIME_LIMIT_S", "RunSettings", "read_run_settings"]

_N = TypeVar("_N", int, float)

#: The bounds of the run settings (review of PR #36, owner to confirm): at most 64 runs at
#: once, and a time limit of at most 7 days.
MAX_CONCURRENT_RUNS = 64
MAX_TIME_LIMIT_S = 7 * 24 * 3600.0

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunSettings:
    """How many runs may run at once, and the limits of each."""

    max_concurrent_runs: int = 1
    limits: Limits = field(default_factory=Limits)


def _setting(settings: dict[str, Any], key: str, parsed: _N | None, default: str) -> _N | None:
    """``parsed`` (the value of ``key`` through its typed, bounded parser), or ``None`` for
    the default; a value present but refused is logged."""
    if key in settings and parsed is None:
        _log.warning(
            "%s in %s is not valid; the default (%s) is used.", key, SETTINGS_FILE, default
        )
    return parsed


def read_run_settings(config_dir: Path) -> RunSettings:
    """The run settings of ``settings.json`` in ``config_dir``."""
    try:
        loaded = read_json_file(config_dir / SETTINGS_FILE)
    except (OSError, ValueError):
        loaded = None
    settings: dict[str, Any] = loaded if isinstance(loaded, dict) else {}
    defaults = RunSettings()
    concurrent = _setting(
        settings,
        "max_concurrent_runs",
        whole_in(settings.get("max_concurrent_runs"), 1, MAX_CONCURRENT_RUNS),
        "1",
    )
    time_s = _setting(
        settings,
        "run_time_limit_s",
        real_in(settings.get("run_time_limit_s"), 0.0, MAX_TIME_LIMIT_S, above_minimum=True),
        "600",
    )
    memory = _setting(
        settings,
        "run_memory_limit_bytes",
        whole_in(settings.get("run_memory_limit_bytes"), 1, MAX_WHOLE),
        "half the physical memory",
    )
    return RunSettings(
        max_concurrent_runs=defaults.max_concurrent_runs if concurrent is None else concurrent,
        limits=Limits(
            time_s=DEFAULT_TIME_LIMIT_S if time_s is None else time_s,
            memory_bytes=defaults.limits.memory_bytes if memory is None else memory,
        ),
    )
