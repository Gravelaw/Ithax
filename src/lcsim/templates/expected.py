"""A template's ``expected.json`` and how a run is judged against it (spec 4 "Template
package"; AKS-122).

``expected.json`` is an array of rows ``{metric, value, method, source, reference, run?}``.
``read_rows`` checks their layout and returns the rows with the problems found, each at a
JSON Pointer into the array; the package loader turns them into E195 issues and checks the
metric names against the model.

``summary_estimates`` reads a ``summary.json`` dict as one ``Estimate`` per metric name:
the scenario ``default``'s metrics of a process run (with ``search.best.<variable>`` for a
search), or ``objective`` and ``variables.<id>`` of an optimization run. ``judge`` applies
a row's pass rule, spec 2's: ``three_se`` (|mean - value| <= 3 standard errors, the
standard error being the half-width divided by the t quantile the summary used),
``exact`` (equal to four significant figures) and ``sig_figs_4`` (one value equal to four
significant figures).
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from scipy.stats import t

from lcsim.strict_json import real_in

__all__ = [
    "METHODS",
    "ROW_KEYS",
    "RUNS",
    "SE_LIMIT",
    "SOURCES",
    "Estimate",
    "ExpectedRow",
    "Judgement",
    "RowProblem",
    "four_figures",
    "judge",
    "read_rows",
    "summary_estimates",
]

Method = Literal["three_se", "exact", "sig_figs_4"]
Source = Literal["theory", "benchmark", "recorded"]
Run = Literal["template", "exercise"]

#: Spec 2's pass rules.
METHODS: tuple[Method, ...] = ("three_se", "exact", "sig_figs_4")
SOURCES: tuple[Source, ...] = ("theory", "benchmark", "recorded")
#: The model a row is judged on: as written, or after the exercise's edits.
RUNS: tuple[Run, ...] = ("template", "exercise")
REQUIRED_KEYS = ("metric", "value", "method", "source", "reference")
ROW_KEYS = (*REQUIRED_KEYS, "run")
# The largest float: a whole number beyond it cannot be read as one (strict_json.real_in).
_LARGEST = sys.float_info.max
#: Spec 2 "Benchmarks": |estimate - known answer| <= 3 x standard error.
SE_LIMIT = 3.0


@dataclass(frozen=True)
class ExpectedRow:
    """One row of ``expected.json``; ``value`` in SI units, as ``summary.json`` has it."""

    metric: str
    value: float
    method: Method
    source: Source
    reference: str
    run: Run = "template"


@dataclass(frozen=True)
class RowProblem:
    """A layout problem: ``path`` is a JSON Pointer into ``expected.json``."""

    path: str
    message: str
    hint: str


@dataclass(frozen=True)
class Estimate:
    """A metric as ``summary.json`` reports it: ``mean`` and ``half_width`` (``None`` when
    undefined), the ``n`` values they are over and the ``confidence`` of the half-width;
    a single value (an optimization result, a search's best) has ``n`` 1 and no
    half-width or confidence."""

    mean: float | None
    half_width: float | None
    n: int
    confidence: float | None


@dataclass(frozen=True)
class Judgement:
    """A row judged: whether it passed, the estimate and its standard error (``None``
    where there is none), and ``problem``, why no estimate could be judged (empty when
    it was)."""

    row: ExpectedRow
    passed: bool
    estimate: float | None
    se: float | None
    problem: str = ""

    def message(self) -> str:
        """One line naming the metric, the run, and why the row failed or passed."""
        where = f"{self.row.metric} ({self.row.run})"
        if self.problem:
            return f"{where}: {self.problem}"
        return (
            f"{where}: estimate {self.estimate!r}, expected {self.row.value!r} by "
            f"{self.row.method}, standard error {self.se!r}: "
            f"{'passed' if self.passed else 'failed'}"
        )


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _row(index: int, item: object, problems: list[RowProblem]) -> ExpectedRow | None:
    at = f"/{index}"
    if not isinstance(item, dict):
        problems.append(
            RowProblem(at, f"Row {index} is not an object.", "Write each row as an object.")
        )
        return None
    found = len(problems)
    for key in item:
        if key not in ROW_KEYS:
            problems.append(
                RowProblem(
                    f"{at}/{key}",
                    f"Row {index} has the unknown key '{key}'.",
                    f"Use only {', '.join(ROW_KEYS)}.",
                )
            )
    for key in REQUIRED_KEYS:
        if key not in item:
            problems.append(
                RowProblem(f"{at}/{key}", f"Row {index} has no '{key}'.", f"Add '{key}'.")
            )
    checks: tuple[tuple[str, bool, str], ...] = (
        ("metric", _text(item.get("metric")) is not None, "a metric name as text"),
        (
            "value",
            _number(item.get("value")) is not None,
            "a finite number",
        ),
        ("method", item.get("method") in METHODS, f"one of {', '.join(METHODS)}"),
        ("source", item.get("source") in SOURCES, f"one of {', '.join(SOURCES)}"),
        ("reference", _text(item.get("reference")) is not None, "non-empty text"),
        ("run", item.get("run", "template") in RUNS, f"one of {', '.join(RUNS)}"),
    )
    for key, good, kind in checks:
        if key in item and not good:
            problems.append(
                RowProblem(
                    f"{at}/{key}",
                    f"Row {index}'s '{key}' is not {kind}.",
                    f"Set '{key}' to {kind}.",
                )
            )
    if len(problems) > found:
        return None
    value = _number(item["value"])
    assert value is not None
    return ExpectedRow(
        metric=item["metric"],
        value=value,
        method=item["method"],
        source=item["source"],
        reference=item["reference"],
        run=item.get("run", "template"),
    )


def read_rows(document: object) -> tuple[tuple[ExpectedRow, ...], tuple[RowProblem, ...]]:
    """The rows of ``expected.json`` and the layout problems found; a row with a problem
    is left out."""
    if not isinstance(document, list) or not document:
        problem = RowProblem(
            "", "expected.json is not an array of one or more rows.", "Write an array of rows."
        )
        return (), (problem,)
    problems: list[RowProblem] = []
    rows = [_row(index, item, problems) for index, item in enumerate(document)]
    return tuple(row for row in rows if row is not None), tuple(problems)


def _number(value: object) -> float | None:
    return real_in(value, -_LARGEST, _LARGEST)


def summary_estimates(summary: Mapping[str, Any]) -> dict[str, Estimate]:
    """Every metric of ``summary`` by the name ``expected.json`` uses for it."""
    estimates: dict[str, Estimate] = {}
    scenarios = summary.get("scenarios")
    if isinstance(scenarios, Mapping) and isinstance(scenarios.get("default"), Mapping):
        confidence = _number(summary.get("confidence"))
        for name, metric in scenarios["default"].get("metrics", {}).items():
            estimates[name] = Estimate(
                mean=_number(metric.get("mean")),
                half_width=_number(metric.get("half_width")),
                n=int(metric.get("n", 0)),
                confidence=confidence,
            )
    search = summary.get("search")
    if isinstance(search, Mapping):
        for name, value in search["best"]["set"].items():
            estimates[f"search.best.{name}"] = Estimate(_number(value), None, 1, None)
    if "objective" in summary and isinstance(summary.get("variables"), Mapping):
        estimates["objective"] = Estimate(_number(summary["objective"]), None, 1, None)
        for name, value in summary["variables"].items():
            estimates[f"variables.{name}"] = Estimate(_number(value), None, 1, None)
    return estimates


def four_figures(value: float) -> float:
    """``value`` rounded to four significant figures."""
    return float(f"{value:.3e}")


def judge(row: ExpectedRow, estimates: Mapping[str, Estimate]) -> Judgement:
    """``row`` judged by its method against ``estimates`` (``summary_estimates``)."""
    estimate = estimates.get(row.metric)
    if estimate is None:
        return Judgement(row, False, None, None, "not reported by the run")
    if estimate.mean is None:
        return Judgement(row, False, None, None, "the run's mean is undefined")
    mean = estimate.mean
    if row.method == "sig_figs_4":
        if estimate.n != 1:
            return Judgement(row, False, mean, None, f"{estimate.n} values; sig_figs_4 takes one")
        return Judgement(row, four_figures(mean) == four_figures(row.value), mean, None)
    if row.method == "exact":
        return Judgement(row, four_figures(mean) == four_figures(row.value), mean, None)
    if estimate.half_width is None or estimate.confidence is None or estimate.n < 2:
        return Judgement(row, False, mean, None, "the run gives no standard error")
    quantile = float(t.ppf(1 - (1 - estimate.confidence) / 2, estimate.n - 1))
    se = estimate.half_width / quantile
    return Judgement(row, abs(mean - row.value) <= SE_LIMIT * se, mean, se)
