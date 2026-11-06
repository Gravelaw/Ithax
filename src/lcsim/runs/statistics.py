"""Across-replication statistics and paired scenario differences (spec 2 "Statistic
definitions"; spec 1 "Division of labour": the manager computes them for every adapter).

Closed-form calculators (guide rule 7), over the ``replications`` table of spec 1 "Tables
for the ``process`` domain":

- **Across replications.** The mean of the replication values, and the half-width
  t(1 - (1 - confidence)/2, n - 1) x s / √n, where s is their sample standard deviation
  (n - 1 denominator) and t comes from ``scipy.stats.t.ppf``; no table is hard-coded.
  This is the Student t confidence interval for a mean of independent values, as in any
  statistics text (for example NIST/SEMATECH e-Handbook of Statistical Methods, section
  7.2.2.1). A NaN value is left out; n counts the values that remain. With n = 1 the
  half-width is undefined, and with n = 0 the mean too (``None``).
- **Between scenarios.** For each pair of scenarios in the experiment's order, the later
  scenario's value minus the earlier's, per replication (same replication number, same
  random streams); a replication is paired only when both values are not NaN. The paired
  differences get the same mean and half-width; the pair is separated when the interval
  excludes zero: n ≥ 2 and |mean| > half-width.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from scipy.stats import t

from lcsim.engines.adapter import Table

__all__ = [
    "Estimate",
    "MetricEstimate",
    "ScenarioDifference",
    "across_replications",
    "estimate",
    "paired_differences",
    "t_quantile",
]


def t_quantile(confidence: float, n: int) -> float:
    """t(1 - (1 - confidence)/2, n - 1), the two-sided Student t quantile for ``n`` values,
    from ``scipy.stats.t.ppf``. ``n`` below 2 raises ``ValueError``."""
    if n < 2:
        raise ValueError(f"{n} values; a t quantile needs 2")
    return float(t.ppf(1 - (1 - confidence) / 2, n - 1))


@dataclass(frozen=True)
class Estimate:
    """A mean with its half-width over ``n`` values; ``None`` where undefined."""

    mean: float | None
    half_width: float | None
    n: int

    @property
    def separated(self) -> bool:
        """Whether the interval excludes zero: n ≥ 2 and |mean| > half-width."""
        if self.mean is None or self.half_width is None:
            return False
        return abs(self.mean) > self.half_width


def estimate(values: Iterable[float], confidence: float) -> Estimate:
    """The mean of ``values`` and its half-width at ``confidence``, NaN values left out."""
    kept = [value for value in values if not math.isnan(value)]
    n = len(kept)
    if n == 0:
        return Estimate(None, None, 0)
    mean = statistics.fmean(kept)
    if n == 1:
        return Estimate(mean, None, 1)
    half_width = t_quantile(confidence, n) * statistics.stdev(kept) / math.sqrt(n)
    return Estimate(mean, half_width, n)


@dataclass(frozen=True)
class MetricEstimate:
    """One metric's estimate and its unit (spec 1 "Tables for the ``process`` domain")."""

    estimate: Estimate
    unit: str

    def as_dict(self) -> dict[str, Any]:
        """``{mean, half_width, unit, n}``, the ``summary.json`` metric of spec 1."""
        return {
            "mean": self.estimate.mean,
            "half_width": self.estimate.half_width,
            "unit": self.unit,
            "n": self.estimate.n,
        }


@dataclass(frozen=True)
class ScenarioDifference:
    """The paired differences ``scenario`` minus ``against``, by metric."""

    scenario: str
    against: str
    metrics: Mapping[str, MetricEstimate]

    def as_dict(self) -> dict[str, Any]:
        """The ``summary.json`` entry of spec 1: ``{scenario, against, metrics}``, each
        metric ``{mean, half_width, unit, n, separated}``."""
        return {
            "scenario": self.scenario,
            "against": self.against,
            "metrics": {
                metric: {**item.as_dict(), "separated": item.estimate.separated}
                for metric, item in self.metrics.items()
            },
        }


# A scenario's metrics, in row order: metric -> (unit, replication -> value).
_Values = dict[str, tuple[str, dict[int, float]]]


def _by_scenario(replications: Table) -> dict[str, _Values]:
    """The table's values grouped by scenario and metric, in row order; a metric's unit is
    that of its first row."""
    grouped: dict[str, _Values] = {}
    columns = [
        replications.column(name).to_pylist()
        for name in ("scenario", "replication", "metric", "value", "unit")
    ]
    for scenario, replication, metric, value, unit in zip(*columns, strict=True):
        metrics = grouped.setdefault(scenario, {})
        metrics.setdefault(metric, (unit, {}))[1][replication] = value
    return grouped


def across_replications(
    replications: Table, scenario_ids: Sequence[str], confidence: float
) -> dict[str, dict[str, MetricEstimate]]:
    """Each scenario's metrics (in ``scenario_ids`` order, then the table's row order) with
    their mean and half-width across replications. A scenario with no rows has none."""
    grouped = _by_scenario(replications)
    return {
        scenario: {
            metric: MetricEstimate(estimate(values.values(), confidence), unit)
            for metric, (unit, values) in grouped.get(scenario, {}).items()
        }
        for scenario in scenario_ids
    }


def paired_differences(
    replications: Table, scenario_ids: Sequence[str], confidence: float
) -> list[ScenarioDifference]:
    """The paired differences of every pair of scenarios, in ``scenario_ids`` order (the
    first with the second, the first with the third, ..., then the second with the third),
    each the later minus the earlier. A metric is paired when both scenarios report it,
    in the earlier scenario's row order, with its unit."""
    grouped = _by_scenario(replications)
    pairs: list[ScenarioDifference] = []
    for index, against in enumerate(scenario_ids):
        for scenario in scenario_ids[index + 1 :]:
            earlier = grouped.get(against, {})
            later = grouped.get(scenario, {})
            metrics: dict[str, MetricEstimate] = {}
            for metric, (unit, before) in earlier.items():
                if metric not in later:
                    continue
                after = later[metric][1]
                differences = [
                    after[rep] - before[rep]
                    for rep in sorted(before.keys() & after.keys())
                    if not math.isnan(before[rep]) and not math.isnan(after[rep])
                ]
                metrics[metric] = MetricEstimate(estimate(differences, confidence), unit)
            pairs.append(ScenarioDifference(scenario, against, metrics))
    return pairs
