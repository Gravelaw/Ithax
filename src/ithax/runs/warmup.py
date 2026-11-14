"""The warm-up check and its W210 warning (spec 2 "Statistic definitions", warm-up check;
decided by ``docs/research/spec-2-output-analysis.md``, AKS-129).

For each scenario and each metric of the ``timeseries`` table, each replication's observed
samples are those with ``time_s`` at or after the warm-up, in time order: J of them, the
same in every replication. With h = ⌊J/2⌋, the first half is the first h samples and the
second half the last h. Per replication r: d_r = mean(second half) - mean(first half) and
m_r = mean of all J. Across the n replications: d̄ and m̄ are the means of the d_r and the
m_r, and the half-width is t(0.995, n - 1) x s / √n, s being the sample standard deviation
of the d_r (n - 1 denominator), with t from ``scipy.stats.t.ppf``: a paired t interval at
99%, whatever the experiment's ``confidence``. The metric has changed when |d̄| > half-width
and |d̄| > 0.05 x |m̄|; a metric with m̄ = 0 is not reported as changed (AKS-102). A metric
with J < 2, or with fewer than 2 replications, is not checked.

These are closed-form calculators (guide rule 7): sample means, a sample standard
deviation and a t quantile.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from ithax.engines.adapter import Table
from ithax.model.issues import Issue, pointer
from ithax.runs.statistics import t_quantile

__all__ = ["WARMUP_LEVEL", "WARMUP_THRESHOLD", "Drift", "warmup_check", "warmup_warning"]

#: The level of the paired interval: t(0.995, n - 1).
WARMUP_LEVEL = 0.99
#: The change, as a fraction of the mean, below which a metric has not changed.
WARMUP_THRESHOLD = 0.05

_MESSAGE = "Results were still changing after warm-up: "
_ITEM = (
    "{metric} in scenario {scenario} changed by {percent}% of its mean between the first and "
    "second halves of the observed period"
)
_HINT = "Lengthen 'warmup' and run again."


@dataclass(frozen=True)
class Drift:
    """The warm-up check of one metric in one scenario.

    ``replications`` is n, ``samples`` is J, ``change`` is d̄, ``half_width`` the 99%
    half-width of d̄, ``mean`` is m̄, and ``changed`` the verdict.
    """

    scenario: str
    metric: str
    replications: int
    samples: int
    change: float
    half_width: float
    mean: float
    changed: bool

    @property
    def percent(self) -> int | None:
        """100 x |d̄| / |m̄| to the nearest whole number, a half rounding up; ``None`` when
        m̄ is 0."""
        if self.mean == 0:
            return None
        return math.floor(100 * abs(self.change) / abs(self.mean) + 0.5)


def _drift(scenario: str, metric: str, series: Sequence[Sequence[float]]) -> Drift | None:
    """The check of one metric from each replication's observed samples, or ``None`` when
    it is not checked."""
    samples = len(series[0])
    if any(len(values) != samples for values in series):
        raise ValueError(
            f"{metric} in scenario {scenario}: replications do not have the same number of "
            "observed samples"
        )
    n = len(series)
    half = samples // 2
    if half == 0 or n < 2:
        return None
    d = [
        statistics.fmean(values[samples - half :]) - statistics.fmean(values[:half])
        for values in series
    ]
    change = statistics.fmean(d)
    mean = statistics.fmean(statistics.fmean(values) for values in series)
    half_width = t_quantile(WARMUP_LEVEL, n) * statistics.stdev(d) / math.sqrt(n)
    changed = mean != 0 and abs(change) > half_width and abs(change) > WARMUP_THRESHOLD * abs(mean)
    return Drift(scenario, metric, n, samples, change, half_width, mean, changed)


def warmup_check(timeseries: Table, warmup: float, scenario_ids: Sequence[str]) -> list[Drift]:
    """The check of every metric of ``timeseries`` that is checked, in ``scenario_ids``
    order and then the table's row order. ``warmup`` is in seconds.

    Replications whose observed sample counts differ raise ``ValueError``: spec 1 has an
    adapter sample every replication at the same times.
    """
    columns = [
        timeseries.column(name).to_pylist()
        for name in ("scenario", "replication", "metric", "time_s", "value")
    ]
    # scenario -> metric -> replication -> [(time, value)], in row order.
    grouped: dict[str, dict[str, dict[int, list[tuple[float, float]]]]] = {}
    for scenario, replication, metric, time, value in zip(*columns, strict=True):
        # A metric is listed at its first row, observed or not.
        observed = grouped.setdefault(scenario, {}).setdefault(metric, {})
        samples = observed.setdefault(replication, [])
        if time >= warmup:
            samples.append((time, value))
    drifts: list[Drift] = []
    for scenario in scenario_ids:
        for metric, reps in grouped.get(scenario, {}).items():
            series = [[value for _, value in sorted(reps[rep])] for rep in sorted(reps)]
            found = _drift(scenario, metric, series)
            if found is not None:
                drifts.append(found)
    return drifts


def warmup_warning(drifts: Sequence[Drift], experiment_index: int) -> Issue | None:
    """The one W210 issue for the run when any metric changed, listing each changed metric
    in the order of ``drifts``; ``None`` when none changed. ``experiment_index`` is the
    experiment's position in the model file's ``experiments`` array."""
    changed = [drift for drift in drifts if drift.changed]
    if not changed:
        return None
    items = [
        _ITEM.format(metric=drift.metric, scenario=drift.scenario, percent=drift.percent)
        for drift in changed
    ]
    return Issue(
        code="W210",
        component=None,
        path=pointer("experiments", experiment_index, "warmup"),
        message=_MESSAGE + "; ".join(items) + ".",
        hint=_HINT,
    )
