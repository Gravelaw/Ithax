"""Across-replication statistics and paired scenario differences (spec 2 "Statistic
definitions"; AKS-102): ``lcsim.runs.statistics``.

The half-widths are checked against a hand computation with ``scipy.stats.t.ppf`` on small
fixtures, and against published quantiles, so no t table is hard-coded in the product.
"""

import math
import statistics

import pyarrow as pa
import pytest
from scipy.stats import t

from lcsim.runs.statistics import (
    Estimate,
    MetricEstimate,
    ScenarioDifference,
    across_replications,
    estimate,
    paired_differences,
    t_quantile,
)

NAN = math.nan


def replications(rows: list[tuple[str, int, str, float, str]]) -> pa.Table:
    """A ``replications`` table (spec 1 "Tables for the process domain") from rows."""
    names = ["scenario", "replication", "metric", "value", "unit"]
    return pa.table({name: [row[i] for row in rows] for i, name in enumerate(names)})


# ---------------------------------------------------------------------------------------
# One metric


def test_t_quantile_is_scipy_two_sided() -> None:
    assert t_quantile(0.95, 3) == t.ppf(0.975, 2)
    assert t_quantile(0.99, 30) == t.ppf(0.995, 29)
    # Published values: t(0.975, 2) = 4.3027, t(0.975, 29) = 2.0452, t(0.995, 2) = 9.9248.
    assert t_quantile(0.95, 3) == pytest.approx(4.302652729749464, rel=1e-12)
    assert t_quantile(0.95, 30) == pytest.approx(2.045229642132703, rel=1e-12)
    assert t_quantile(0.99, 3) == pytest.approx(9.924843200918276, rel=1e-12)


def test_t_quantile_needs_two_values() -> None:
    with pytest.raises(ValueError, match="needs 2"):
        t_quantile(0.95, 1)


def test_the_half_width_equals_a_hand_computation() -> None:
    # 1, 2, 3: mean 2, sample sd 1 (n - 1 denominator), n 3.
    found = estimate([1.0, 2.0, 3.0], 0.95)
    assert found == Estimate(mean=2.0, half_width=t.ppf(0.975, 2) * 1.0 / math.sqrt(3), n=3)
    # Four values at 90%: hand computation of the sample sd.
    values = [4.0, 7.0, 5.5, 9.25]
    mean = sum(values) / 4
    sd = math.sqrt(sum((value - mean) ** 2 for value in values) / 3)
    found = estimate(values, 0.90)
    assert found.mean == pytest.approx(mean, rel=1e-15)
    assert found.half_width == pytest.approx(t.ppf(0.95, 3) * sd / 2, rel=1e-13)
    assert found.n == 4


def test_no_spread_gives_a_zero_half_width() -> None:
    assert estimate([5.0, 5.0, 5.0], 0.95) == Estimate(5.0, 0.0, 3)


def test_nan_values_are_left_out_and_counted() -> None:
    """Spec 2 "Statistic definitions": the mean and half-width are over the n values
    that remain, with t at n - 1 degrees of freedom."""
    found = estimate([1.0, NAN, 2.0, 3.0, NAN], 0.95)
    assert found == estimate([1.0, 2.0, 3.0], 0.95)
    assert found.n == 3


def test_one_value_has_no_half_width_and_none_has_no_mean() -> None:
    assert estimate([NAN, 4.0], 0.95) == Estimate(4.0, None, 1)
    assert estimate([NAN, NAN], 0.95) == Estimate(None, None, 0)
    assert estimate([], 0.95) == Estimate(None, None, 0)


@pytest.mark.parametrize(
    ("found", "separated"),
    [
        (Estimate(1.0, 0.5, 3), True),
        (Estimate(-1.0, 0.5, 3), True),
        (Estimate(1.0, 1.0, 3), False),  # strict: the interval touches zero
        (Estimate(0.0, 0.0, 3), False),
        (Estimate(0.1, 0.0, 3), True),
        (Estimate(1.0, None, 1), False),
        (Estimate(None, None, 0), False),
    ],
)
def test_separated_means_the_interval_excludes_zero(found: Estimate, separated: bool) -> None:
    assert found.separated is separated


def test_metric_estimate_as_dict() -> None:
    assert MetricEstimate(Estimate(2.0, 0.5, 30), "s").as_dict() == {
        "mean": 2.0,
        "half_width": 0.5,
        "unit": "s",
        "n": 30,
    }
    assert MetricEstimate(Estimate(None, None, 0), "s").as_dict() == {
        "mean": None,
        "half_width": None,
        "unit": "s",
        "n": 0,
    }


# ---------------------------------------------------------------------------------------
# A replications table

ROWS = [
    ("base", 0, "till.wait.mean", 100.0, "s"),
    ("base", 0, "till.utilization", 0.70, "1"),
    ("base", 1, "till.wait.mean", 120.0, "s"),
    ("base", 1, "till.utilization", 0.75, "1"),
    ("base", 2, "till.wait.mean", NAN, "s"),
    ("base", 2, "till.utilization", 0.80, "1"),
    ("two", 0, "till.wait.mean", 10.0, "s"),
    ("two", 0, "till.utilization", 0.35, "1"),
    ("two", 1, "till.wait.mean", 30.0, "s"),
    ("two", 1, "till.utilization", 0.40, "1"),
    ("two", 2, "till.wait.mean", 20.0, "s"),
    ("two", 2, "till.utilization", 0.38, "1"),
]


def test_across_replications_per_scenario_in_row_order() -> None:
    found = across_replications(replications(ROWS), ["base", "two"], 0.95)
    assert list(found) == ["base", "two"]
    assert list(found["base"]) == ["till.wait.mean", "till.utilization"]
    wait = found["base"]["till.wait.mean"]
    assert wait == MetricEstimate(estimate([100.0, 120.0], 0.95), "s")
    assert wait.estimate.n == 2
    utilization = found["two"]["till.utilization"]
    assert utilization.unit == "1"
    assert utilization.estimate.mean == pytest.approx(statistics.fmean([0.35, 0.40, 0.38]))
    assert utilization.estimate.half_width == pytest.approx(
        t.ppf(0.975, 2) * statistics.stdev([0.35, 0.40, 0.38]) / math.sqrt(3)
    )


def test_across_replications_follows_the_given_scenario_order() -> None:
    found = across_replications(replications(ROWS), ["two", "base", "none"], 0.95)
    assert list(found) == ["two", "base", "none"]
    assert found["none"] == {}


def test_paired_differences_later_minus_earlier() -> None:
    found = paired_differences(replications(ROWS), ["base", "two"], 0.95)
    assert len(found) == 1
    pair = found[0]
    assert (pair.scenario, pair.against) == ("two", "base")
    assert list(pair.metrics) == ["till.wait.mean", "till.utilization"]
    # Replication 2 of base has a NaN wait, so only replications 0 and 1 pair: -90, -90.
    wait = pair.metrics["till.wait.mean"]
    assert wait == MetricEstimate(Estimate(-90.0, 0.0, 2), "s")
    assert wait.estimate.separated
    utilization = pair.metrics["till.utilization"]
    differences = [0.35 - 0.70, 0.40 - 0.75, 0.38 - 0.80]
    assert utilization.estimate == estimate(differences, 0.95)
    assert utilization.estimate.separated


def test_paired_differences_take_every_pair_in_scenario_order() -> None:
    rows = [
        (scenario, rep, "x.count", float(value), "1")
        for scenario, values in (("a", (1, 2)), ("b", (3, 5)), ("c", (2, 2)))
        for rep, value in enumerate(values)
    ]
    found = paired_differences(replications(rows), ["a", "b", "c"], 0.95)
    assert [(pair.scenario, pair.against) for pair in found] == [("b", "a"), ("c", "a"), ("c", "b")]
    assert found[0].metrics["x.count"].estimate == estimate([2.0, 3.0], 0.95)
    # c - a: 1, 0; c - b: -1, -3.
    assert found[1].metrics["x.count"].estimate == estimate([1.0, 0.0], 0.95)
    assert found[2].metrics["x.count"].estimate == estimate([-1.0, -3.0], 0.95)


def test_one_scenario_has_no_differences() -> None:
    assert paired_differences(replications(ROWS), ["base"], 0.95) == []


def test_a_metric_missing_from_one_scenario_is_not_paired() -> None:
    rows = [*ROWS, ("base", 0, "x.count", 1.0, "1"), ("base", 1, "x.count", 2.0, "1")]
    found = paired_differences(replications(rows), ["base", "two"], 0.95)
    assert "x.count" not in found[0].metrics


def test_scenario_difference_as_dict() -> None:
    pair = ScenarioDifference(
        scenario="two",
        against="base",
        metrics={
            "till.wait.mean": MetricEstimate(Estimate(-90.0, 5.0, 2), "s"),
            "x.count": MetricEstimate(Estimate(1.0, None, 1), "1"),
        },
    )
    assert pair.as_dict() == {
        "scenario": "two",
        "against": "base",
        "metrics": {
            "till.wait.mean": {
                "mean": -90.0,
                "half_width": 5.0,
                "unit": "s",
                "n": 2,
                "separated": True,
            },
            "x.count": {"mean": 1.0, "half_width": None, "unit": "1", "n": 1, "separated": False},
        },
    }
