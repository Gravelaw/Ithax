"""The finding rules of spec 4 "Finding rules" (AKS-117).

``find(summary, model, thresholds)`` reads a finished run, its ``summary.json`` (spec 1
"Run folder and results") and the model that ran (the run folder's ``model.json``, loaded),
and returns the findings: short statements in plain language, made by fixed rules, so the
same input always gives the same findings, offline, with no model, network, solver or
random number involved. Nothing is recomputed from the replications: every number is the
summary's, and ``unstable`` restates the W201 issues the summary already carries (spec 4:
"one computation, not two").

The rules, in spec 4's order (``RULES``):

- ``bottleneck``: in each scenario, the server with the highest utilization (ties: the
  longest mean wait, then the first in the model), when it is at least
  ``bottleneck_utilization``. Utilization is relative to available capacity (spec 2
  "Statistic definitions"); for a server whose capacity a ``schedule`` (on it or its pool)
  or a ``failure`` changes, the text says "of the time it was available".
- ``unstable``: one finding for each server named by a W201 issue in ``warnings``.
- ``idle_capacity``: in each scenario, each server below ``idle_utilization`` that no
  ``schedule`` changes (on the server or on its pool).
- ``not_enough_runs``: in each scenario, one finding listing every key metric whose
  half-width is above ``relative_half_width`` of its mean, a time's mean being at least
  ``min_time_s`` and a rate's at least ``min_rate_per_s``; and for each pair of scenarios,
  one finding listing every key metric whose paired difference is not separated and has a
  half-width above that share of the smaller of the two means (both means passing the same
  floor).
- ``optimization_result``: a search run's ``search`` block (spec 2 "Simulation-based
  optimization") or a mathematical optimization's solution.

Findings come in a fixed order: ``optimization_result``, then ``unstable``, then for each
scenario in the summary's order ``bottleneck``, ``idle_capacity`` (servers in model order)
and ``not_enough_runs``, then the scenario pairs in the summary's ``differences`` order.

The readings of spec 4 these rules make are proposed defaults, owner to confirm
(``docs/DECISIONS.md``, AKS-117; research note ``docs/research/spec-4-findings-wording.md``).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, fields
from fractions import Fraction
from typing import Any, Literal

from lcsim.findings.display import figures, percent, quantity, value_text
from lcsim.model.model import JsonValue, Model, ParameterType
from lcsim.strict_json import is_finite_real, is_number

__all__ = [
    "DEFAULT_THRESHOLDS",
    "RULES",
    "Finding",
    "Rule",
    "Severity",
    "Thresholds",
    "find",
    "key_metrics",
    "n_required",
]

Rule = Literal["bottleneck", "unstable", "idle_capacity", "not_enough_runs", "optimization_result"]
Severity = Literal["info", "warning"]

#: Spec 4's rules, in its order.
RULES: tuple[Rule, ...] = (
    "bottleneck",
    "unstable",
    "idle_capacity",
    "not_enough_runs",
    "optimization_result",
)

Metrics = Mapping[str, Mapping[str, Any]]


@dataclass(frozen=True)
class Thresholds:
    """The thresholds of the rules, spec 4's proposed defaults unless given.

    ``bottleneck_utilization`` and ``idle_utilization`` are fractions from 0 to 1;
    ``relative_half_width`` is the share of the mean above which a half-width is too wide,
    above 0 and at most 1; ``min_time_s`` (seconds) and ``min_rate_per_s`` (per second) are
    the smallest means ``not_enough_runs`` judges, at least 0. A value outside these ranges
    raises ``ValueError``: the settings that make the thresholds adjustable check them first
    and report a problem as an issue (AKS-135).
    """

    bottleneck_utilization: float = 0.85
    idle_utilization: float = 0.30
    relative_half_width: float = 0.10
    min_time_s: float = 60.0
    min_rate_per_s: float = 1 / 3600

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if not is_number(value):
                raise ValueError(f"threshold {item.name} must be a number, not {value!r}")
            if not is_finite_real(value) or value < 0:
                raise ValueError(f"threshold {item.name} must be a finite number at least 0")
        for name in ("bottleneck_utilization", "idle_utilization", "relative_half_width"):
            if getattr(self, name) > 1:
                raise ValueError(f"threshold {name} must be at most 1")
        if self.relative_half_width == 0:
            raise ValueError("threshold relative_half_width must be above 0")


#: Spec 4's defaults: 0.85, 0.30, 10%, 60 s and 1 per hour.
DEFAULT_THRESHOLDS = Thresholds()


@dataclass(frozen=True)
class Finding:
    """One finding, as spec 4 shows it: ``{rule, severity, component, scenario, text,
    evidence}``. ``component`` and ``scenario`` are ``None`` when the finding is not about
    one component or one scenario. ``evidence`` holds the summary's values it rests on, in
    SI units; ``text`` uses display units."""

    rule: Rule
    severity: Severity
    component: str | None
    scenario: str | None
    text: str
    evidence: Mapping[str, JsonValue] = field(default_factory=dict)

    def as_dict(self) -> dict[str, JsonValue]:
        """The finding as the JSON object of spec 4, keys in spec order."""
        return {
            "rule": self.rule,
            "severity": self.severity,
            "component": self.component,
            "scenario": self.scenario,
            "text": self.text,
            "evidence": dict(self.evidence),
        }


def _decimal(value: float) -> Fraction:
    """A number as the decimal ``summary.json`` writes it (the shortest text that reads
    back as the same float), exactly."""
    return Fraction(repr(float(value)))


def n_required(n: int, half_width: float, mean: float, share: float = 0.1) -> int:
    """Spec 4: n x (half_width / (share x mean))^2, rounded up to the next multiple of 10;
    the replications that would give an interval of ``share`` of the mean (Kelton et al.'s
    n = n0 h0^2 / h^2, research note). Computed exactly, each number read as the decimal it
    is written as (``summary.json`` writes 0.2 and the threshold 0.1, not their binary
    approximations), so a result on a multiple of 10 stays there."""
    ratio = _decimal(half_width) / (_decimal(share) * abs(_decimal(mean)))
    return math.ceil(n * ratio**2 / 10) * 10


# --- reading the model ---------------------------------------------------------------------


def _servers(model: Model) -> list[str]:
    return [component.id for component in model.components if component.type == "server"]


def _targets(model: Model, kind: str) -> set[str]:
    return {
        target
        for component in model.components
        if component.type == kind and isinstance(target := component.settings.get("target"), str)
    }


def _scheduled(model: Model) -> set[str]:
    """Servers a ``schedule`` changes: on the server, or on the pool the server names."""
    targets = _targets(model, "schedule")
    return {
        component.id
        for component in model.components
        if component.type == "server"
        and (component.id in targets or component.settings.get("pool") in targets)
    }


def _without_a_queue(model: Model) -> set[str]:
    """Servers with ``queue_capacity`` 0: their items wait in the block before them, so their
    own wait says nothing (spec 4 "Finding rules", AKS-125)."""
    return {
        component.id
        for component in model.components
        if component.type == "server" and component.settings.get("queue_capacity") == 0
    }


def _available_time(model: Model) -> set[str]:
    """Servers whose available capacity varies: scheduled, or the target of a ``failure``."""
    return _scheduled(model) | (_targets(model, "failure") & set(_servers(model)))


def _of_the_time(server: str, varying: set[str]) -> str:
    return "of the time it was available" if server in varying else "of the time"


# --- reading the summary -------------------------------------------------------------------


def _mean(metrics: Metrics, metric: str) -> float | None:
    entry = metrics.get(metric)
    if entry is None:
        return None
    mean = entry["mean"]
    return None if mean is None else float(mean)


def _busiest(metrics: Metrics, model: Model) -> tuple[str, float] | None:
    """The server with the highest utilization (ties: the longest mean wait, an undefined
    wait counting as the shortest, then the first in the model), with its utilization."""
    best: tuple[str, float, float] | None = None
    for server in _servers(model):
        utilization = _mean(metrics, f"{server}.utilization")
        if utilization is None:
            continue
        wait = _mean(metrics, f"{server}.wait.mean")
        rank = -math.inf if wait is None else wait
        if best is None or (utilization, rank) > (best[1], best[2]):
            best = (server, utilization, rank)
    return None if best is None else (best[0], best[1])


def key_metrics(metrics: Metrics, model: Model) -> list[str]:
    """Spec 4's key metrics of one scenario, each once, in this order: every metric named in
    an objective, then in a constraint, then each sink's ``throughput`` and
    ``cycle_time.mean`` (sinks in model order), then the ``wait.mean`` of the server with
    the highest utilization; only those the summary has."""
    names = [objective.metric for objective in model.objectives]
    names += [constraint.metric for constraint in model.constraints]
    for component in model.components:
        if component.type == "sink":
            names += [f"{component.id}.throughput", f"{component.id}.cycle_time.mean"]
    busiest = _busiest(metrics, model)
    if busiest is not None:
        names.append(f"{busiest[0]}.wait.mean")
    return [name for name in dict.fromkeys(names) if name in metrics]


def _big_enough(mean: float, unit: str, thresholds: Thresholds) -> bool:
    """A mean ``not_enough_runs`` judges: a time at least ``min_time_s``, a rate at least
    ``min_rate_per_s``, anything else not zero."""
    if unit == "s":
        return abs(mean) >= thresholds.min_time_s
    if unit == "1/s":
        return abs(mean) >= thresholds.min_rate_per_s
    return mean != 0


def _listed(names: Sequence[str]) -> str:
    """``a``, ``a and b``, ``a, b and c``; callers never pass an empty list."""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _share_text(share: float) -> str:
    return f"{share * 100:g}%"


# --- the rules -----------------------------------------------------------------------------


def _bottleneck(
    scenario: str, metrics: Metrics, model: Model, thresholds: Thresholds
) -> list[Finding]:
    busiest = _busiest(metrics, model)
    if busiest is None or busiest[1] < thresholds.bottleneck_utilization:
        return []
    server, utilization = busiest
    wait = _mean(metrics, f"{server}.wait.mean")
    busy = f"{percent(utilization)} {_of_the_time(server, _available_time(model))}"
    text = f"{server} is the bottleneck: busy {busy}"
    if wait is None or server in _without_a_queue(model):
        text += "."
    else:
        text += f", with an average wait of {quantity(wait, 's')}."
    evidence: dict[str, JsonValue] = {
        f"{server}.utilization": utilization,
        f"{server}.wait.mean": wait,
    }
    return [Finding("bottleneck", "info", server, scenario, text, evidence)]


def _unstable(warnings: Iterable[Mapping[str, Any]]) -> list[Finding]:
    found: list[Finding] = []
    seen: set[str] = set()
    for issue in warnings:
        server = issue.get("component")
        if issue.get("code") != "W201" or not isinstance(server, str) or server in seen:
            continue
        seen.add(server)
        text = (
            f"{server} cannot keep up. Work arrives faster than it can be done, so the queue "
            "will keep growing."
        )
        evidence: dict[str, JsonValue] = {
            "warning": "W201",
            "path": issue.get("path"),
            "message": issue.get("message"),
        }
        found.append(Finding("unstable", "warning", server, None, text, evidence))
    return found


def _idle_capacity(
    scenario: str, metrics: Metrics, model: Model, thresholds: Thresholds
) -> list[Finding]:
    scheduled = _scheduled(model)
    varying = _available_time(model)
    found: list[Finding] = []
    for server in _servers(model):
        utilization = _mean(metrics, f"{server}.utilization")
        if utilization is None or server in scheduled:
            continue
        if utilization < thresholds.idle_utilization:
            text = f"{server} is idle {percent(1 - utilization)} {_of_the_time(server, varying)}."
            evidence: dict[str, JsonValue] = {f"{server}.utilization": utilization}
            found.append(Finding("idle_capacity", "info", server, scenario, text, evidence))
    return found


def _not_enough_runs(
    scenario: str, metrics: Metrics, model: Model, thresholds: Thresholds
) -> list[Finding]:
    share = thresholds.relative_half_width
    listed: list[str] = []
    for metric in key_metrics(metrics, model):
        entry = metrics[metric]
        mean, half_width = entry["mean"], entry["half_width"]
        if mean is None or half_width is None or not _big_enough(mean, entry["unit"], thresholds):
            continue
        if half_width > share * abs(mean):
            listed.append(metric)
    if not listed:
        return []
    widest = max(listed, key=lambda name: metrics[name]["half_width"] / abs(metrics[name]["mean"]))
    entry = metrics[widest]
    required = max(
        n_required(metrics[name]["n"], metrics[name]["half_width"], metrics[name]["mean"], share)
        for name in listed
    )
    mean_text = value_text(widest, entry["mean"], entry["unit"])
    half_text = value_text(widest, entry["half_width"], entry["unit"], like=entry["mean"])
    text = (
        f"The estimates for {_listed(listed)} are still uncertain: {widest} is {mean_text} plus "
        f"or minus {half_text}. About {required} replications would be needed for a "
        f"{_share_text(share)} interval."
    )
    evidence: dict[str, JsonValue] = {name: dict(metrics[name]) for name in listed}
    evidence["n_required"] = required
    return [Finding("not_enough_runs", "warning", None, scenario, text, evidence)]


def _cannot_tell_apart(
    pair: Mapping[str, Any],
    scenarios: Mapping[str, Mapping[str, Any]],
    model: Model,
    thresholds: Thresholds,
) -> list[Finding]:
    later, earlier = pair["scenario"], pair["against"]
    first, second = scenarios[earlier]["metrics"], scenarios[later]["metrics"]
    names = dict.fromkeys([*key_metrics(first, model), *key_metrics(second, model)])
    listed: list[str] = []
    for metric in names:
        difference = pair["metrics"].get(metric)
        if difference is None or difference["separated"] or difference["half_width"] is None:
            continue
        means = [_mean(first, metric), _mean(second, metric)]
        if None in means:
            continue
        smaller = min(abs(value) for value in means if value is not None)
        if not _big_enough(smaller, difference["unit"], thresholds):
            continue
        if difference["half_width"] > thresholds.relative_half_width * smaller:
            listed.append(metric)
    if not listed:
        return []
    text = f"{earlier} and {later} cannot be told apart on {_listed(listed)} yet."
    evidence: dict[str, JsonValue] = {"scenarios": [earlier, later]}
    evidence.update({name: dict(pair["metrics"][name]) for name in listed})
    return [Finding("not_enough_runs", "warning", None, later, text, evidence)]


def _setting_text(name: str, value: float, model: Model) -> str:
    parameter = model.parameters.get(name)
    kind: ParameterType | None = None if parameter is None else parameter.type
    shown = quantity(value, "s") if kind == "quantity" else figures(value, 4)
    return f"{name} = {shown}"


def _settings_text(values: Mapping[str, float], model: Model) -> str:
    return ", ".join(_setting_text(name, value, model) for name, value in values.items())


def _values_text(values: Mapping[str, float], model: Model) -> str:
    """A mathematical optimization's values: those not 0 (a -0 is 0), then how many are 0
    (spec 4 "Finding rules", AKS-125)."""
    zeros = sum(1 for value in values.values() if value == 0)
    if values and zeros == len(values):
        return "every variable at 0"
    text = _settings_text({name: value for name, value in values.items() if value != 0}, model)
    if zeros:
        text += f", and {zeros} other{'s' if zeros > 1 else ''} at 0"
    return text


def _search_sense(summary: Mapping[str, Any], model: Model) -> str:
    """The sense of the objective the run's search optimized: the experiment the summary
    names, its ``search.objective`` id, then that objective (as ``search_summary`` finds the
    metric), never an objective found by its metric, which two objectives may share."""
    experiment = next(item for item in model.experiments if item.id == summary["experiment"])
    assert experiment.search is not None
    objective_id = experiment.search.objective
    return next(item.sense for item in model.objectives if item.id == objective_id)


def _search_result(summary: Mapping[str, Any], model: Model) -> list[Finding]:
    search = summary["search"]
    scenario = next(iter(summary["scenarios"]), None)
    metric = search["objective"]["metric"]
    before, after = search["objective"]["before"], search["objective"]["after"]
    candidates = search["candidates"]
    unit = candidates[0]["metrics"][metric]["unit"]
    best = search["best"]["set"]
    settings = _settings_text(best, model)

    def shown(value: float | None) -> str:
        return "not defined" if value is None else value_text(metric, value, unit)

    evidence: dict[str, JsonValue] = {
        "status": search["status"],
        "best": dict(best),
        "metric": metric,
        "before": before,
        "after": after,
        "separated": search["separated"],
    }
    if search["status"] == "infeasible":
        text = (
            f"No setting tried meets every constraint. With the starting values, {settings}, "
            f"{metric} is {shown(before)}."
        )
        return [Finding("optimization_result", "warning", None, scenario, text, evidence)]
    baseline = candidates[0]
    if best == baseline["set"]:
        text = (
            f"Best found: the starting values, {settings}. No setting tried improved {metric}, "
            f"which is {shown(before)}."
        )
    else:
        sense = _search_sense(summary, model)
        better = (
            before is not None
            and after is not None
            and (after < before if sense == "minimize" else after > before)
        )
        if not baseline["feasible"]:
            text = (
                f"Best found: {settings}. The starting values break a constraint; {metric} went "
                f"from {shown(before)} to {shown(after)}."
            )
        else:
            verb = "improved" if better else "went"
            text = (
                f"Best found: {settings}. {metric} {verb} from {shown(before)} to {shown(after)}."
            )
    runner_up = any(
        candidate["confirmed"] and candidate["feasible"] and candidate["set"] != best
        for candidate in candidates
    )
    if runner_up:
        if search["separated"]:
            text += " It is clearly better than the next best setting tried."
        else:
            text += " The next best setting tried cannot be told apart from it yet."
    return [Finding("optimization_result", "info", None, scenario, text, evidence)]


def _program_result(summary: Mapping[str, Any], model: Model) -> list[Finding]:
    status = summary["status"]
    if status == "infeasible":
        text = "No values meet every constraint: the problem is infeasible."
        return [Finding("optimization_result", "warning", None, None, text, {"status": status})]
    if status == "unbounded":
        text = "The objective can be improved without limit: a bound or a constraint is missing."
        return [Finding("optimization_result", "warning", None, None, text, {"status": status})]
    assert model.program is not None
    variables = summary["variables"]
    ordered = {
        item.id: variables[item.id] for item in model.program.variables if item.id in variables
    }
    constraints = summary["constraints"]
    tight = [
        item.id for item in model.program.constraints if constraints.get(item.id, {}).get("tight")
    ]
    objective = figures(summary["objective"], 4)
    text = f"Best found: {_values_text(ordered, model)}. The objective is {objective}"
    if tight:
        text += f", with {_listed(tight)} tight."
    elif constraints:
        text += "; no constraint is tight."
    else:
        text += "."
    evidence: dict[str, JsonValue] = {
        "status": status,
        "objective": summary["objective"],
        "variables": dict(variables),
        "tight": list(tight),
    }
    return [Finding("optimization_result", "info", None, None, text, evidence)]


def find(
    summary: Mapping[str, Any], model: Model, thresholds: Thresholds = DEFAULT_THRESHOLDS
) -> list[Finding]:
    """The findings of a finished run, from its ``summary.json`` and the model that ran, in
    the fixed order of the module docstring. ``summary`` is read, never changed."""
    found: list[Finding] = []
    if model.program is not None:
        return _program_result(summary, model)
    if "search" in summary:
        found += _search_result(summary, model)
    found += _unstable(summary["warnings"])
    scenarios: Mapping[str, Mapping[str, Any]] = summary["scenarios"]
    for scenario, results in scenarios.items():
        metrics: Metrics = results["metrics"]
        found += _bottleneck(scenario, metrics, model, thresholds)
        found += _idle_capacity(scenario, metrics, model, thresholds)
        found += _not_enough_runs(scenario, metrics, model, thresholds)
    for pair in summary["differences"]:
        found += _cannot_tell_apart(pair, scenarios, model, thresholds)
    return found
