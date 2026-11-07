"""The run settings in ``settings.json`` (spec 3 "Run queue"; spec 4 "Limits"; AKS-112,
owner to confirm).

The service reads them from the configuration folder when it starts:

- ``max_concurrent_runs``: a whole number from 1, default 1;
- ``run_time_limit_s``: a number above 0, default 600 (10 minutes);
- ``run_memory_limit_bytes``: a whole number above 0, default half the physical memory
  (not enforced where it cannot be read, spec 1 E192).

A key that is absent takes its default; one holding another value takes its default too,
and that is logged. A file the strict reader refuses (``lcsim.strict_json``: not JSON, or
holding ``NaN``, an infinity or text that is not valid Unicode) gives every default (the
tier's own reading of the file, ``lcsim.service.hardware.active_tier``, logs and replaces
it). Settings writes the keys at M9.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lcsim.runs.limits import DEFAULT_TIME_LIMIT_S, Limits
from lcsim.service.hardware import SETTINGS_FILE
from lcsim.strict_json import read_json_file

__all__ = ["RunSettings", "read_run_settings"]

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunSettings:
    """How many runs may run at once, and the limits of each."""

    max_concurrent_runs: int = 1
    limits: Limits = field(default_factory=Limits)


def _whole(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _positive(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value > 0


def _setting(settings: dict[str, Any], key: str, valid: bool, default: str) -> bool:
    if key not in settings:
        return False
    if not valid:
        _log.warning(
            "%s in %s is not valid; the default (%s) is used.", key, SETTINGS_FILE, default
        )
        return False
    return True


def read_run_settings(config_dir: Path) -> RunSettings:
    """The run settings of ``settings.json`` in ``config_dir``."""
    try:
        loaded = read_json_file(config_dir / SETTINGS_FILE)
    except (OSError, ValueError):
        loaded = None
    settings: dict[str, Any] = loaded if isinstance(loaded, dict) else {}
    defaults = RunSettings()
    concurrent: Any = settings.get("max_concurrent_runs")
    time_s: Any = settings.get("run_time_limit_s")
    memory: Any = settings.get("run_memory_limit_bytes")
    use_concurrent = _setting(settings, "max_concurrent_runs", _whole(concurrent), "1")
    use_time = _setting(settings, "run_time_limit_s", _positive(time_s), "600")
    use_memory = _setting(
        settings, "run_memory_limit_bytes", _whole(memory), "half the physical memory"
    )
    return RunSettings(
        max_concurrent_runs=concurrent if use_concurrent else defaults.max_concurrent_runs,
        limits=Limits(
            time_s=float(time_s) if use_time else DEFAULT_TIME_LIMIT_S,
            memory_bytes=memory if use_memory else defaults.limits.memory_bytes,
        ),
    )
