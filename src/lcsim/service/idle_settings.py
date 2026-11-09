"""The idle timeout in ``settings.json`` (spec 3 "Service rules", Lifetime; owner decision
B5, AKS-141; key, bounds and precedence owner to confirm).

``idle_timeout_minutes`` in ``settings.json`` in the configuration folder is a whole number
of minutes from 1 to 10,080 (7 days), read as ``max_concurrent_runs`` is (a JSON integer,
not a ``bool`` or a number with a fraction), default 30. The service reads it when it
starts (``lcsim.service.main``), unless ``--idle-minutes`` was given, so a change takes
effect at the next start; ``GET /v1/settings`` reads it at each request.

A key that is absent takes the default. A value that cannot be used is refused as a spec 1
W220 issue at ``/idle_timeout_minutes``, logged, and the default is used. A
``settings.json`` that exists but cannot be read (or is not an object) gives the default
too; its W220 issue is the one the finding thresholds give at ``""``
(``lcsim.service.finding_settings``), so it is logged here and not listed twice. Reading
never fails.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from lcsim.model.issues import Issue, pointer
from lcsim.service.finding_settings import SETTINGS_PROBLEM
from lcsim.service.hardware import SETTINGS_FILE
from lcsim.strict_json import read_json_file, whole_in

__all__ = [
    "DEFAULT_IDLE_MINUTES",
    "IDLE_TIMEOUT",
    "IDLE_WORDS",
    "MAX_IDLE_MINUTES",
    "IdleSettings",
    "read_idle_settings",
]

#: The key of the idle timeout in ``settings.json``.
IDLE_TIMEOUT = "idle_timeout_minutes"

#: Spec 3 "Lifetime": 30 idle minutes by default (owner decision B5).
DEFAULT_IDLE_MINUTES = 30

#: Spec 3 "Lifetime": at most 7 days, the upper bound of ``run_time_limit_s``.
MAX_IDLE_MINUTES = 7 * 24 * 60

#: How a message words the idle timeout's range.
IDLE_WORDS = f"a whole number of minutes from 1 to {MAX_IDLE_MINUTES:,} (7 days)"

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class IdleSettings:
    """The idle timeout the service takes, in minutes, and the W220 issues of reading it."""

    minutes: int
    issues: tuple[Issue, ...]

    @property
    def timeout_s(self) -> float:
        """The idle timeout in seconds, as ``lcsim.service.lifetime.Lifetime`` takes it."""
        return self.minutes * 60.0


def read_idle_settings(config_dir: Path) -> IdleSettings:
    """The idle timeout of ``settings.json`` in ``config_dir``, with the default for what
    is absent or refused, and the W220 issue of a value refused."""
    path = config_dir / SETTINGS_FILE
    if not path.exists():
        return IdleSettings(DEFAULT_IDLE_MINUTES, ())
    try:
        loaded = read_json_file(path)
    except (OSError, ValueError):  # the strict reader's refusal is a ValueError
        loaded = None
    if not isinstance(loaded, dict):
        _log.warning(
            "%s cannot be read; the default idle timeout (%d minutes) is used.",
            SETTINGS_FILE,
            DEFAULT_IDLE_MINUTES,
        )
        return IdleSettings(DEFAULT_IDLE_MINUTES, ())
    if IDLE_TIMEOUT not in loaded:
        return IdleSettings(DEFAULT_IDLE_MINUTES, ())
    minutes = whole_in(loaded[IDLE_TIMEOUT], 1, MAX_IDLE_MINUTES)
    if minutes is not None:
        return IdleSettings(minutes, ())
    issue = Issue(
        code=SETTINGS_PROBLEM,
        component=None,
        path=pointer(IDLE_TIMEOUT),
        message=(
            f"The idle timeout '{IDLE_TIMEOUT}' in {SETTINGS_FILE} is not {IDLE_WORDS}, so "
            f"its default, {DEFAULT_IDLE_MINUTES} minutes, is used."
        ),
        hint=(
            f"Set '{IDLE_TIMEOUT}' to a whole number from 1 to {MAX_IDLE_MINUTES:,}, or "
            "remove it to use the default."
        ),
    )
    _log.warning("%s at '%s': %s", issue.code, issue.path, issue.message)
    return IdleSettings(DEFAULT_IDLE_MINUTES, (issue,))
