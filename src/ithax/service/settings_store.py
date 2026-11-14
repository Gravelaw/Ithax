"""The user's settings in ``settings.json``, read and written whole (spec 3 "Endpoints",
``GET /v1/settings`` and ``PUT /v1/settings``; AKS-119, owner to confirm).

``settings.json`` in the configuration folder holds seven keys the service knows:

- ``tier``: ``low``, ``mid`` or ``high`` (spec 3 "Hardware tiers"), read at start;
- ``max_concurrent_runs``, ``run_time_limit_s``, ``run_memory_limit_bytes``: the run
  settings (spec 3 "Run queue", ``ithax.service.run_settings``), read at start;
- ``idle_timeout_minutes``: the idle timeout (spec 3 "Lifetime",
  ``ithax.service.idle_settings``), read at start unless ``--idle-minutes`` was given;
- ``finding_thresholds``: the five thresholds of spec 4's finding rules (spec 3 "Finding
  thresholds", ``ithax.service.finding_settings``), read at each summary;
- ``interface``: the interface's seven preferences, which the service stores and does not
  use (``INTERFACE_DEFAULTS``).

``SettingsStore.read`` gives each as the service takes it now, with its default where the
key is absent or holds a value that cannot be used, and the W220 issues of the thresholds and
of the idle timeout.
``SettingsStore.write`` takes a request body: a JSON object (read by the strict reader) of
any of the seven keys, each replacing the stored key whole, ``null`` removing it; every value
is checked by the rule the service reads it with, every problem is an E184 issue at its JSON
Pointer in the body, and nothing is written when there is one. Writes are made one at a
time, through a temporary file and a rename; other keys of the file are kept, and a file
that cannot be read is replaced, as the first start replaces it.
"""

from __future__ import annotations

import dataclasses
import logging
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ithax.model.issues import Issue, pointer
from ithax.service.errors import MALFORMED, malformed
from ithax.service.finding_settings import (
    FINDING_THRESHOLDS,
    THRESHOLD_RANGES,
    ThresholdRange,
    read_finding_settings,
)
from ithax.service.hardware import SETTINGS_FILE, TIERS, Hardware, TierName, tier_for
from ithax.service.idle_settings import (
    IDLE_TIMEOUT,
    IDLE_WORDS,
    MAX_IDLE_MINUTES,
    read_idle_settings,
)
from ithax.service.projects_store import write_json
from ithax.service.run_settings import MAX_CONCURRENT_RUNS, MAX_TIME_LIMIT_S, read_run_settings
from ithax.strict_json import MAX_WHOLE, read_json, read_json_file, real_in, whole_in

__all__ = [
    "INTERFACE",
    "INTERFACE_DEFAULTS",
    "MOTIONS",
    "SETTINGS_KEYS",
    "TEXT_SIZES",
    "THEMES",
    "UNDO_STEPS_MAX",
    "UNDO_STEPS_MIN",
    "SettingsStore",
    "check_settings",
    "recommended_undo_steps",
]

#: The key of the interface's preferences in ``settings.json``.
INTERFACE = "interface"

#: The keys of ``settings``, in the order ``GET /v1/settings`` gives them.
SETTINGS_KEYS = (
    "tier",
    "max_concurrent_runs",
    "run_time_limit_s",
    "run_memory_limit_bytes",
    IDLE_TIMEOUT,
    FINDING_THRESHOLDS,
    INTERFACE,
)

THEMES = ("system", "light", "dark")
TEXT_SIZES = (100, 125, 150, 175, 200)
MOTIONS = ("system", "full", "reduced", "off")

#: Spec 3 "Undo and redo": at least 100 steps; the owner review's Settings choice keeps
#: up to this many (AKS-119, owner to confirm).
UNDO_STEPS_MIN = 100
UNDO_STEPS_MAX = 10_000

_RECOMMENDED_UNDO_STEPS: Mapping[str, int] = {"low": 200, "mid": 500, "high": 1000}

_log = logging.getLogger(__name__)


def recommended_undo_steps(tier: TierName) -> int:
    """The undo steps the owner design review recommends on ``tier`` (design choice 1)."""
    return _RECOMMENDED_UNDO_STEPS[tier]


def _boolean(value: object) -> bool:
    return isinstance(value, bool)


def _one_of(choices: tuple[object, ...]) -> Callable[[object], bool]:
    def check(value: object) -> bool:
        # A bool is never a number, and a float never a whole size (100.0 is not 100 here).
        return type(value) in (str, int) and value in choices

    return check


def _undo_steps(value: object) -> bool:
    return value is None or whole_in(value, UNDO_STEPS_MIN, UNDO_STEPS_MAX) is not None


@dataclass(frozen=True)
class _Preference:
    default: object
    check: Callable[[object], bool]
    words: str


_PREFERENCES: dict[str, _Preference] = {
    "first_start_seen": _Preference(False, _boolean, "true or false"),
    "ask_before_deleting": _Preference(True, _boolean, "true or false"),
    "undo_steps": _Preference(
        None,
        _undo_steps,
        f"a whole number from {UNDO_STEPS_MIN} to {UNDO_STEPS_MAX:,}, or null for the "
        "number recommended for the tier",
    ),
    "theme": _Preference("system", _one_of(THEMES), "system, light or dark"),
    "text_size": _Preference(100, _one_of(TEXT_SIZES), "100, 125, 150, 175 or 200"),
    "motion": _Preference("system", _one_of(MOTIONS), "system, full, reduced or off"),
    "colour_blind_charts": _Preference(False, _boolean, "true or false"),
}

#: Each interface preference and its default (spec 3 "Endpoints", ``GET /v1/settings``).
INTERFACE_DEFAULTS: Mapping[str, object] = {
    name: preference.default for name, preference in _PREFERENCES.items()
}

_TIER_NAMES = tuple(tier.name for tier in TIERS)


def _tier(value: object) -> bool:
    return isinstance(value, str) and value in _TIER_NAMES


def _whole(minimum: int, maximum: int) -> Callable[[object], bool]:
    return lambda value: whole_in(value, minimum, maximum) is not None


#: The top-level settings other than the two objects: their checks and how they are worded.
_PLAIN: dict[str, tuple[Callable[[object], bool], str]] = {
    "tier": (_tier, "low, mid or high"),
    "max_concurrent_runs": (
        _whole(1, MAX_CONCURRENT_RUNS),
        f"a whole number from 1 to {MAX_CONCURRENT_RUNS}",
    ),
    "run_time_limit_s": (
        lambda value: real_in(value, 0.0, MAX_TIME_LIMIT_S, above_minimum=True) is not None,
        f"a number of seconds above 0 and at most {MAX_TIME_LIMIT_S:,.0f} (7 days)",
    ),
    "run_memory_limit_bytes": (
        _whole(1, MAX_WHOLE),
        "a whole number of bytes from 1 to 2**63 - 1",
    ),
    IDLE_TIMEOUT: (_whole(1, MAX_IDLE_MINUTES), IDLE_WORDS),
}


def _issue(path: str, message: str, hint: str) -> Issue:
    return Issue(code=MALFORMED, component=None, path=path, message=message, hint=hint)


def _value_issue(path: str, name: str, words: str) -> Issue:
    return _issue(
        path,
        f"The setting '{name}' must be {words}.",
        f"Send {words}, or null to use the default.",
    )


def _unknown(path: str, name: str, known: str) -> Issue:
    return _issue(path, f"'{name}' is not a setting here.", f"The settings here are {known}.")


def _check_object(
    value: object,
    place: str,
    name: str,
    checks: Mapping[str, tuple[Callable[[object], bool], str]],
) -> list[Issue]:
    """The issues of ``finding_thresholds`` or ``interface``: an object of known keys."""
    if not isinstance(value, dict):
        return [_value_issue(place, name, f"an object of {', '.join(checks)}, or null")]
    issues: list[Issue] = []
    for key, item in value.items():
        path = place + pointer(key)
        check = checks.get(key)
        if check is None:
            issues.append(_unknown(path, key, ", ".join(checks)))
        elif not check[0](item):
            issues.append(_value_issue(path, key, check[1]))
    return issues


def _threshold(bounds: ThresholdRange) -> Callable[[object], bool]:
    def check(value: object) -> bool:
        number = real_in(value, bounds.minimum, bounds.maximum, above_minimum=bounds.above_minimum)
        return number is not None

    return check


_THRESHOLD_CHECKS: dict[str, tuple[Callable[[object], bool], str]] = {
    key: (_threshold(bounds), bounds.words) for key, bounds in THRESHOLD_RANGES.items()
}

_PREFERENCE_CHECKS: dict[str, tuple[Callable[[object], bool], str]] = {
    key: (preference.check, preference.words) for key, preference in _PREFERENCES.items()
}


def check_settings(body: object) -> list[Issue]:
    """The E184 issues of a ``PUT /v1/settings`` body, in body order; none when it can be
    written."""
    if not isinstance(body, dict):
        return [
            _issue(
                "",
                "The settings must be a JSON object.",
                f"Send an object of any of {', '.join(SETTINGS_KEYS)}.",
            )
        ]
    issues: list[Issue] = []
    for key, value in body.items():
        place = pointer(key)
        if key not in SETTINGS_KEYS:
            issues.append(_unknown(place, key, ", ".join(SETTINGS_KEYS)))
        elif value is None:
            continue
        elif key == FINDING_THRESHOLDS:
            issues.extend(_check_object(value, place, key, _THRESHOLD_CHECKS))
        elif key == INTERFACE:
            issues.extend(_check_object(value, place, key, _PREFERENCE_CHECKS))
        elif not _PLAIN[key][0](value):
            issues.append(_value_issue(place, key, _PLAIN[key][1]))
    return issues


def _stored(path: Path) -> dict[str, Any] | None:
    """The settings file as an object, or ``None`` when it is missing or cannot be read."""
    try:
        loaded = read_json_file(path)
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _preferences(stored: object) -> dict[str, object]:
    """The interface's preferences as stored, each that cannot be used read as its
    default (and logged)."""
    given = stored if isinstance(stored, dict) else {}
    if stored is not None and not isinstance(stored, dict):
        _log.warning(
            "'%s' in %s is not an object; its defaults are used.", INTERFACE, SETTINGS_FILE
        )
    preferences: dict[str, object] = {}
    for name, preference in _PREFERENCES.items():
        value = given.get(name, preference.default)
        if not preference.check(value):
            _log.warning(
                "'%s.%s' in %s is not valid; the default is used.", INTERFACE, name, SETTINGS_FILE
            )
            value = preference.default
        preferences[name] = value
    return preferences


class SettingsStore:
    """``settings.json`` in ``config_dir``, for a service on ``hardware``."""

    def __init__(self, config_dir: Path, hardware: Hardware) -> None:
        self._path = config_dir / SETTINGS_FILE
        self._config_dir = config_dir
        self._hardware = hardware
        self._lock = threading.Lock()

    def read(self) -> dict[str, Any]:
        """The body of ``GET /v1/settings``: ``{settings, issues}``."""
        stored = _stored(self._path) or {}
        tier = stored.get("tier")
        run = read_run_settings(self._config_dir)
        findings = read_finding_settings(self._config_dir)
        idle = read_idle_settings(self._config_dir)
        settings = {
            "tier": tier if _tier(tier) else tier_for(self._hardware),
            "max_concurrent_runs": run.max_concurrent_runs,
            "run_time_limit_s": run.limits.time_s,
            "run_memory_limit_bytes": run.limits.memory_bytes,
            IDLE_TIMEOUT: idle.minutes,
            FINDING_THRESHOLDS: dataclasses.asdict(findings.thresholds),
            INTERFACE: _preferences(stored.get(INTERFACE)),
        }
        issues = (*findings.issues, *idle.issues)
        return {"settings": settings, "issues": [issue.as_dict() for issue in issues]}

    def write(self, raw: bytes) -> dict[str, Any]:
        """Write the settings of a ``PUT /v1/settings`` body and return the new
        ``GET /v1/settings`` body; a body that cannot be written raises 400 with E184."""
        try:
            body = read_json(raw)
        except ValueError:
            raise malformed(
                [
                    _issue(
                        "",
                        "The request body is not JSON the service can store.",
                        "Send one JSON object, without NaN or infinities, in UTF-8.",
                    )
                ]
            ) from None
        issues = check_settings(body)
        if issues:
            raise malformed(issues)
        assert isinstance(body, dict)
        with self._lock:
            stored = _stored(self._path)
            if stored is None:
                if self._path.exists():
                    _log.warning("%s cannot be read; it is replaced.", self._path)
                stored = {}
            for key, value in body.items():
                if value is None:
                    stored.pop(key, None)
                else:
                    stored[key] = value
            self._config_dir.mkdir(parents=True, exist_ok=True)
            write_json(self._path, stored)
        return self.read()
