"""Per-replication bookkeeping (spec 2 "Statistic definitions"; AKS-98).

The observed period runs from the end of warm-up to the end of the run; an event at the
warm-up instant belongs to it; time-weighted values count only the part of the period
after warm-up; ``max`` takes the value held at the end of warm-up and every value taken
during the period, one held for no time included; a mean over nothing is NaN.
"""

import math

import pytest

from lcsim.engines.process.statistics import Tally, TimeWeighted, Window


def test_a_window_is_the_period_from_warm_up_to_the_end() -> None:
    window = Window(warmup=300.0, end=1200.0)
    assert window.period == 900.0
    assert not window.observes(299.999)
    assert window.observes(300.0)
    assert window.observes(1199.0)


@pytest.mark.parametrize(("warmup", "end"), [(-1.0, 10.0), (10.0, 10.0), (11.0, 10.0)])
def test_a_window_needs_warm_up_from_zero_and_below_the_end(warmup: float, end: float) -> None:
    with pytest.raises(ValueError, match="warm-up"):
        Window(warmup=warmup, end=end)


def test_a_time_weighted_value_without_warm_up() -> None:
    stat = TimeWeighted(Window(0.0, 10.0))
    stat.set(2.0, 1.0)  # 0 over [0, 2)
    stat.add(5.0, 2.0)  # 1 over [2, 5)
    stat.add(6.0, -3.0)  # 3 over [5, 6), then 0
    assert stat.value == 0.0
    assert stat.mean() == pytest.approx((3 * 1 + 1 * 3) / 10)
    assert stat.maximum() == 3.0


def test_a_time_weighted_value_counts_only_the_period_after_warm_up() -> None:
    stat = TimeWeighted(Window(4.0, 10.0))
    stat.set(2.0, 5.0)  # 5 over [2, 6): only [4, 6) is observed
    stat.set(6.0, 1.0)  # 1 over [6, 10)
    assert stat.mean() == (5.0 * 2 + 1.0 * 4) / 6
    assert stat.maximum() == 5.0  # held at the end of warm-up


def test_the_maximum_ignores_values_held_only_before_warm_up() -> None:
    stat = TimeWeighted(Window(4.0, 10.0))
    stat.set(1.0, 9.0)
    stat.set(3.0, 2.0)
    assert stat.maximum() == 2.0
    assert stat.mean() == 2.0


def test_a_value_replaced_at_the_warm_up_instant_was_not_held_in_the_period() -> None:
    stat = TimeWeighted(Window(4.0, 10.0))
    stat.set(1.0, 9.0)
    stat.set(4.0, 1.0)
    assert stat.maximum() == 1.0
    assert stat.mean() == 1.0


def test_a_value_held_for_no_time_counts_in_the_maximum_only() -> None:
    stat = TimeWeighted(Window(0.0, 10.0))
    stat.set(5.0, 7.0)
    stat.set(5.0, 1.0)
    assert stat.maximum() == 7.0
    assert stat.mean() == 0.5


def test_a_value_never_changed_is_its_initial_value() -> None:
    stat = TimeWeighted(Window(3.0, 10.0), value=2.0)
    assert stat.mean() == 2.0
    assert stat.maximum() == 2.0


def test_the_mean_can_be_read_more_than_once() -> None:
    stat = TimeWeighted(Window(0.0, 4.0))
    stat.set(1.0, 4.0)
    assert stat.mean() == 3.0
    assert stat.mean() == 3.0


def test_time_never_runs_backwards() -> None:
    stat = TimeWeighted(Window(0.0, 10.0))
    stat.set(5.0, 1.0)
    with pytest.raises(ValueError, match="before"):
        stat.set(4.0, 2.0)


def test_a_tally_is_the_mean_of_its_observations() -> None:
    tally = Tally()
    for value in (1.0, 2.0, 6.0):
        tally.observe(value)
    assert tally.count == 3
    assert tally.mean() == 3.0


def test_a_tally_of_nothing_is_nan() -> None:
    tally = Tally()
    assert tally.count == 0
    assert math.isnan(tally.mean())
