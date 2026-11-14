"""A rate quantity in a constraint (#77; M1-7; spec 1 "Quantities", "Metric names").

From format 0.3 a constraint on a rate (``throughput``, ``orders``, ``discarded``) may be
written with a rate unit, ``1/s``, ``1/min``, ``1/h`` or ``1/d``: 30 items per hour is
``"30 1/h"``, read as 30/3600 items per second. A plain number of items per second is
still accepted. A rate unit in a file of an older minor is E100, since a reader of that
minor would not know it.
"""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from ithax.model.loading import load_document
from ithax.model.units import Dimension, Quantity, parse_quantity, units_of
from ithax.runs import search as search_module
from ithax.runs.statistics import Estimate, MetricEstimate

ROOT = Path(__file__).resolve().parents[2]
COFFEE_SHOP: dict[str, Any] = json.loads(
    (ROOT / "examples" / "coffee_shop.json").read_text(encoding="utf-8")
)


def shop(metric: str, value: Any, version: str = "0.3") -> dict[str, Any]:
    document = copy.deepcopy(COFFEE_SHOP)
    document["format_version"] = version
    document["constraints"] = [{"id": "c", "metric": metric, "op": ">=", "value": value}]
    return document


def issues_of(document: dict[str, Any]) -> list[tuple[str, str]]:
    return [(issue.code, issue.path) for issue in load_document(document).issues]


def test_the_rate_units_are_1_per_s_min_h_and_d() -> None:
    assert units_of(Dimension.RATE) == ("1/s", "1/min", "1/h", "1/d")
    assert units_of(Dimension.TIME) == ("s", "min", "h", "d")


@pytest.mark.parametrize(
    ("text", "per_second"),
    [("30 1/h", 30 / 3600), ("0.5 1/min", 0.5 / 60), ("2 1/s", 2.0), ("48 1/d", 48 / 86400)],
)
def test_a_rate_is_read_in_items_per_second(text: str, per_second: float) -> None:
    assert parse_quantity(text, Dimension.RATE) == Quantity(per_second, Dimension.RATE)


def test_a_throughput_constraint_takes_a_rate_with_its_unit() -> None:
    result = load_document(shop("exit.throughput", "30 1/h"))
    assert result.issues == ()
    assert result.model is not None
    (constraint,) = result.model.constraints
    assert constraint.value == Quantity(30 / 3600, Dimension.RATE)
    assert constraint.value.unit == "1/s"


@pytest.mark.parametrize("version", ["0.1", "0.3"])
def test_a_plain_number_of_items_per_second_still_passes(version: str) -> None:
    assert issues_of(shop("exit.throughput", 0.008333, version)) == []


@pytest.mark.parametrize("version", ["0.0", "0.1", "0.2"])
def test_a_rate_unit_in_an_older_file_is_e100(version: str) -> None:
    (issue,) = load_document(shop("exit.throughput", "30 1/h", version)).issues
    assert (issue.code, issue.path) == ("E100", "/constraints/0/value")
    assert issue.message == (
        f"The rate '30 1/h' has a rate unit, which arrived in format version 0.3, but this "
        f"file is format version {version}, which has none."
    )
    assert issue.hint == (
        "Set 'format_version' to \"0.3\", or write the rate as a plain number of items per "
        "second (30 per hour is 0.008333)."
    )


@pytest.mark.parametrize(
    ("metric", "value", "message", "hint"),
    [
        (
            "till.wait.mean",
            "30 1/h",
            "The 'value' of constraint 'c' is a rate, 30 per hour, but 'till.wait.mean' is "
            "measured in time, so a time such as '5 min' is expected.",
            "Write a time with its unit, as in '5 min'.",
        ),
        (
            "till.utilization",
            "30 1/h",
            "The 'value' of constraint 'c' is a rate, 30 per hour, but 'till.utilization' is "
            "a plain number, so a plain number is expected.",
            "Write a plain number with no unit.",
        ),
        (
            "exit.throughput",
            "1 h",
            "The 'value' of constraint 'c' is a time, 1 h, but 'exit.throughput' is a rate, "
            "so a rate such as '30 1/h' or a plain number of items per second is expected.",
            "Write a rate with its unit, as in '30 1/h', or a plain number of items per second.",
        ),
    ],
)
def test_a_value_of_the_wrong_kind_is_e123(
    metric: str, value: str, message: str, hint: str
) -> None:
    (issue,) = load_document(shop(metric, value)).issues
    assert (issue.code, issue.path) == ("E123", "/constraints/0/value")
    assert (issue.message, issue.hint) == (message, hint)


def test_a_rate_where_a_time_is_expected_is_e140() -> None:
    document = shop("exit.throughput", 0.008)
    document["components"][1]["params"]["service"]["mean"] = "30 1/h"
    (issue,) = load_document(document).issues
    assert (issue.code, issue.path) == ("E140", "/components/1/params/service/mean")
    assert "wrong kind of unit: a time is expected" in issue.message


@pytest.mark.parametrize("text", ["30 1/m", "30 /h", "30 1/hour", "30 per hour", "30 1/H"])
def test_a_rate_that_breaks_the_grammar_is_e141(text: str) -> None:
    (issue,) = load_document(shop("exit.throughput", text)).issues
    assert (issue.code, issue.path) == ("E141", "/constraints/0/value")


@pytest.mark.parametrize("value", ["30 1/h", 30 / 3600])
def test_a_search_judges_a_rate_constraint_in_items_per_second(value: Any) -> None:
    """The experiment manager compares a constraint with the mean in SI units: a rate
    written "30 1/h" is judged as 30/3600 items per second, as the plain number is."""
    document = shop("exit.throughput", value)
    document["parameters"]["tills"].update({"min": 1, "max": 3})
    document["objectives"] = [{"id": "wait", "metric": "till.wait.mean", "sense": "minimize"}]
    document["experiments"][0]["search"] = {"objective": "wait", "budget": 3}
    result = load_document(document)
    assert result.issues == () and result.model is not None
    model = result.model
    assert model.experiments[0].search is not None
    judge = search_module._Judge(model, model.experiments[0].search, 0.95)
    at = {"exit.throughput": MetricEstimate(Estimate(0.01, 0.0, 30), "1/s")}
    assert judge.margins(at) == [pytest.approx(30 / 3600 - 0.01, abs=1e-15)]
