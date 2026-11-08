"""How findings show numbers (spec 4 "Finding rules": evidence in SI units, the text in display
units; research note ``docs/research/spec-4-findings-wording.md``, decision 6; AKS-117)."""

import pytest

from lcsim.findings.display import figures, percent, quantity, value_text


@pytest.mark.parametrize(
    ("value", "digits", "shown"),
    [
        (0.0, 3, "0"),
        (-0.0, 3, "0"),
        (15.6914, 3, "15.7"),
        (2.0917, 3, "2.09"),
        (2200.0, 4, "2,200"),
        (24.000000000000004, 4, "24"),
        (13.999999999999998, 4, "14"),
        (9.996, 3, "10"),
        (0.000123456, 3, "0.000123"),
        (123456.0, 3, "123,000"),
        (-1.5, 3, "-1.5"),
        (5.684341886080802e-14, 3, "0.0000000000000568"),
    ],
)
def test_figures_rounds_to_significant_figures_without_an_exponent(
    value: float, digits: int, shown: str
) -> None:
    assert figures(value, digits) == shown


@pytest.mark.parametrize(
    ("fraction", "shown"),
    [(0.900985, "90%"), (0.995, "100%"), (0.745, "75%"), (0.0, "0%"), (0.25, "25%")],
)
def test_percent_is_a_whole_percentage_with_a_half_rounding_up(fraction: float, shown: str) -> None:
    assert percent(fraction) == shown


@pytest.mark.parametrize(
    ("seconds", "shown"),
    [
        (14.5718, "14.6 s"),
        (59.9, "59.9 s"),
        (60.0, "1 min"),
        (941.482, "15.7 min"),
        (25138.7, "6.98 h"),
        (172800.0, "2 d"),
        (0.0, "0 s"),
    ],
)
def test_a_time_is_shown_in_the_largest_unit_it_reaches(seconds: float, shown: str) -> None:
    assert quantity(seconds, "s") == shown


def test_a_half_width_is_shown_in_the_unit_of_its_mean() -> None:
    assert quantity(125.5, "s", like=941.482) == "2.09 min"
    assert quantity(30.0, "s", like=7200.0) == "0.00833 h"


def test_a_rate_is_shown_per_hour() -> None:
    assert quantity(0.00833495, "1/s") == "30 per hour"
    assert quantity(6.83e-05, "1/s") == "0.246 per hour"


def test_a_fraction_metric_is_a_percentage_and_another_plain_number_is_a_number() -> None:
    assert value_text("weld.utilization", 0.900985, "1") == "90.1%"
    assert value_text("server.availability", 0.8, "1") == "80%"
    assert value_text("server.scheduled_fraction", 1 / 3, "1") == "33.3%"
    assert value_text("till.queue_length.mean", 2.25, "1") == "2.25"
    assert value_text("till.wait.mean", 941.482, "s") == "15.7 min"
    assert value_text("till.wait.mean", 125.5, "s", like=941.482) == "2.09 min"
    assert value_text("exit.throughput", 0.00833495, "1/s") == "30 per hour"
