"""The finding thresholds in ``settings.json`` (spec 3 "Service rules", Finding thresholds;
spec 4 "Finding rules": "Thresholds are proposed defaults and are user-adjustable"; AKS-135,
owner to confirm).

``finding_thresholds`` in ``settings.json`` in the configuration folder is an object with up
to five keys, the fields of ``lcsim.findings.Thresholds``:

- ``bottleneck_utilization`` and ``idle_utilization``: numbers from 0 to 1 (defaults 0.85
  and 0.30);
- ``relative_half_width``: a number above 0 and at most 1 (default 0.10);
- ``min_time_s`` and ``min_rate_per_s``: numbers from 0 (defaults 60 s and 1 per hour, as
  per second).

The file is read each time the summary computes findings, so a change takes effect at the
next ``GET /v1/runs/{rid}/summary`` without a restart; the findings are not stored. A key
that is absent takes its default. A value that cannot be used (another kind, a ``bool``, or
a number out of its range, checked before any conversion as ``lcsim.strict_json.real_in``
does), a key that is not one of the five, ``finding_thresholds`` that is not an object, and
a ``settings.json`` that exists but cannot be read (or is not an object) are each refused as
a spec 1 W220 issue at its place in the file, and the default is used for what it refused;
each issue is also logged. Reading never fails.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, fields
from pathlib import Path

from lcsim.findings import DEFAULT_THRESHOLDS, Thresholds
from lcsim.model.issues import Issue, pointer
from lcsim.service.hardware import SETTINGS_FILE
from lcsim.strict_json import read_json_file, real_in

__all__ = [
    "FINDING_THRESHOLDS",
    "SETTINGS_PROBLEM",
    "FindingSettings",
    "read_finding_settings",
]

#: The key of the thresholds in ``settings.json``.
FINDING_THRESHOLDS = "finding_thresholds"

#: Spec 1: a finding threshold in ``settings.json`` that cannot be used (AKS-135).
SETTINGS_PROBLEM = "W220"

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Range:
    minimum: float
    maximum: float
    above_minimum: bool
    words: str


#: The range of each threshold, as ``Thresholds`` checks it.
_RANGES: dict[str, _Range] = {
    "bottleneck_utilization": _Range(0.0, 1.0, False, "a number from 0 to 1"),
    "idle_utilization": _Range(0.0, 1.0, False, "a number from 0 to 1"),
    "relative_half_width": _Range(0.0, 1.0, True, "a number above 0 and at most 1"),
    "min_time_s": _Range(0.0, sys.float_info.max, False, "a number of seconds from 0"),
    "min_rate_per_s": _Range(0.0, sys.float_info.max, False, "a number per second from 0"),
}
assert list(_RANGES) == [item.name for item in fields(Thresholds)]

_KEYS = ", ".join(_RANGES)


@dataclass(frozen=True)
class FindingSettings:
    """The thresholds the finding rules use, and the W220 issues of reading them."""

    thresholds: Thresholds
    issues: tuple[Issue, ...]


def _issue(path: str, message: str, hint: str) -> Issue:
    issue = Issue(code=SETTINGS_PROBLEM, component=None, path=path, message=message, hint=hint)
    _log.warning("%s at '%s': %s", issue.code, issue.path, issue.message)
    return issue


def read_finding_settings(config_dir: Path) -> FindingSettings:
    """The finding thresholds of ``settings.json`` in ``config_dir``, with spec 4's
    defaults for whatever is absent or refused, and the W220 issues of what was refused."""
    path = config_dir / SETTINGS_FILE
    if not path.exists():
        return FindingSettings(DEFAULT_THRESHOLDS, ())
    try:
        loaded = read_json_file(path)
    except (OSError, ValueError):  # the strict reader's refusal is a ValueError
        loaded = None
    if not isinstance(loaded, dict):
        issue = _issue(
            "",
            f"The finding thresholds cannot be read: {SETTINGS_FILE} in the configuration "
            "folder is not a JSON object the service can read, so the default thresholds "
            "are used.",
            f"Correct {SETTINGS_FILE}, or remove it to use every default.",
        )
        return FindingSettings(DEFAULT_THRESHOLDS, (issue,))
    if FINDING_THRESHOLDS not in loaded:
        return FindingSettings(DEFAULT_THRESHOLDS, ())
    given = loaded[FINDING_THRESHOLDS]
    if not isinstance(given, dict):
        issue = _issue(
            pointer(FINDING_THRESHOLDS),
            f"'{FINDING_THRESHOLDS}' in {SETTINGS_FILE} is not an object, so the default "
            "thresholds are used.",
            f'Write it as an object of thresholds, such as {{"bottleneck_utilization": 0.9}}; '
            f"its keys are {_KEYS}.",
        )
        return FindingSettings(DEFAULT_THRESHOLDS, (issue,))
    values: dict[str, float] = {}
    issues: list[Issue] = []
    for key, value in given.items():
        place = pointer(FINDING_THRESHOLDS, key)
        bounds = _RANGES.get(key)
        if bounds is None:
            issues.append(
                _issue(
                    place,
                    f"'{key}' in '{FINDING_THRESHOLDS}' in {SETTINGS_FILE} is not a finding "
                    "threshold, so it is not used.",
                    f"The finding thresholds are {_KEYS}.",
                )
            )
            continue
        number = real_in(value, bounds.minimum, bounds.maximum, above_minimum=bounds.above_minimum)
        if number is None:
            default = getattr(DEFAULT_THRESHOLDS, key)
            issues.append(
                _issue(
                    place,
                    f"The finding threshold '{key}' in {SETTINGS_FILE} is not "
                    f"{bounds.words}, so its default, {default:g}, is used.",
                    f"Set '{key}' to {bounds.words}, or remove it to use the default.",
                )
            )
            continue
        values[key] = number
    return FindingSettings(Thresholds(**values), tuple(issues))
