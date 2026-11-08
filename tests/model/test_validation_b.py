"""The meaning pass, part B (AKS-90): parameters, references, ranges, distributions, data
references, experiments and metric names.

Spec 1 "Parameters", "Quantities", "Distributions", "Experiments", "Metric names",
"Validation issues" (E123, E150 to E152, E160, E162, E170, E171, E174); spec 2 "Block
reference" and "Statistic definitions". Each test names the rule it checks.
"""

import copy
import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from lcsim.model.data import DataColumn, DataFile, DataIndex
from lcsim.model.data_files import ColumnType
from lcsim.model.issues import Issue
from lcsim.model.loading import ModelLoadError, build_document, load_document, load_model, load_text
from lcsim.model.model import Model
from lcsim.model.validation import (
    data_issues,
    distribution_issues,
    experiment_issues,
    meaning_pass,
    metric_issues,
    parameter_issues,
    range_issues,
    reference_issues,
)

ROOT = Path(__file__).resolve().parents[2]
COFFEE_SHOP: dict[str, Any] = json.loads(
    (ROOT / "examples" / "coffee_shop.json").read_text(encoding="utf-8")
)
SERVICE = "/components/1/params/service"
CAPACITY = "/components/1/params/capacity"

CONTENT = b"minutes,count\n1.5,3\n2.0,4\n"
DIGEST = hashlib.sha256(CONTENT).hexdigest()


def coffee() -> dict[str, Any]:
    return copy.deepcopy(COFFEE_SHOP)


def built(document: object) -> Model:
    """The model of ``document`` built without the meaning pass; building must succeed."""
    result = build_document(document, seed_source=lambda: 7)
    assert result.issues == (), [issue.as_dict() for issue in result.issues]
    assert result.model is not None
    return result.model


def codes(issues: list[Issue]) -> list[tuple[str, str]]:
    return [(issue.code, issue.path) for issue in issues]


def till(**params: Any) -> dict[str, Any]:
    """The coffee shop with the till's params updated."""
    document = coffee()
    document["components"][1]["params"].update(params)
    return document


def with_service(service: dict[str, Any]) -> dict[str, Any]:
    return till(service=service)


def with_parameters(document: dict[str, Any], **parameters: dict[str, Any]) -> dict[str, Any]:
    document["parameters"].update(parameters)
    return document


def with_scenarios(document: dict[str, Any], *scenarios: dict[str, Any]) -> dict[str, Any]:
    document["experiments"][0]["scenarios"] = list(scenarios)
    return document


def added(document: dict[str, Any], *components: dict[str, Any]) -> dict[str, Any]:
    """``document`` with components that need no connection (a pool, a schedule) added."""
    document["components"] += list(components)
    return document


def schedule(shifts: list[dict[str, Any]], **params: Any) -> dict[str, Any]:
    return {
        "id": "rota",
        "type": "schedule",
        "params": {"target": "till", "shifts": shifts, **params},
    }


def with_branch(params: dict[str, Any], routes: list[str]) -> dict[str, Any]:
    """The coffee shop with a branch 'split' between the till and the exit."""
    document = coffee()
    document["components"].insert(2, {"id": "split", "type": "branch", "params": params})
    document["connections"] = [
        {"from": "arrivals.out", "to": "till.in"},
        {"from": "till.out", "to": "split.in"},
        *({"from": f"split.{route}", "to": "exit.in"} for route in routes),
    ]
    return document


def only(issues: list[Issue], code: str, path: str) -> Issue:
    """The one issue in ``issues``, which has ``code`` and ``path``."""
    assert codes(issues) == [(code, path)], [issue.as_dict() for issue in issues]
    return issues[0]


# --- every rule group passes the examples -----------------------------------------------------


GROUPS: list[Callable[[Model], list[Issue]]] = [
    parameter_issues,
    reference_issues,
    range_issues,
    distribution_issues,
    data_issues,
    experiment_issues,
    metric_issues,
]


@pytest.mark.parametrize("group", GROUPS, ids=[group.__name__ for group in GROUPS])
def test_the_coffee_shop_passes_every_part_b_group(group: Callable[[Model], list[Issue]]) -> None:
    assert group(built(coffee())) == []


def machine_count() -> dict[str, Any]:
    """Spec 2 benchmark "Machine count": the coffee shop with a search over `tills`."""
    document = coffee()
    document["objectives"] = [{"id": "wait", "metric": "till.wait.mean", "sense": "minimize"}]
    document["constraints"] = [
        {"id": "busy", "metric": "till.utilization", "op": ">=", "value": 0.35}
    ]
    document["experiments"][0]["search"] = {"objective": "wait", "budget": 10}
    return document


def test_the_machine_count_benchmark_model_loads_with_zero_issues() -> None:
    result = load_document(machine_count())
    assert result.issues == ()
    assert result.model is not None
    assert result.model.experiments[0].search is not None
    assert result.model.experiments[0].search.variables == ("tills",)


# --- E151: parameter values within min and max (spec 1 "Parameters") -------------------------


def test_a_value_above_max_is_e151_at_value() -> None:
    document = coffee()
    document["parameters"]["tills"]["value"] = 7
    issue = only(parameter_issues(built(document)), "E151", "/parameters/tills/value")
    assert issue.message == "The 'value' of parameter 'tills' is 7, above its 'max', 5."
    assert issue.component is None


def test_a_value_below_min_is_e151() -> None:
    document = coffee()
    document["parameters"]["tills"]["value"] = 0
    issue = only(parameter_issues(built(document)), "E151", "/parameters/tills/value")
    assert "below its 'min', 1" in issue.message


@pytest.mark.parametrize(
    ("bounds", "value", "flagged"),
    [
        ({"min": 1}, 0, True),
        ({"min": 1}, 99, False),
        ({"max": 5}, 6, True),
        ({"max": 5}, -9, False),
        ({}, -9, False),
        ({"min": 1, "max": 5}, 1, False),
        ({"min": 1, "max": 5}, 5, False),
    ],
)
def test_one_sided_and_inclusive_bounds(bounds: dict[str, int], value: int, flagged: bool) -> None:
    document = coffee()
    document["parameters"]["tills"] = {"value": value, "type": "integer", **bounds}
    issues = parameter_issues(built(document))
    assert codes(issues) == ([("E151", "/parameters/tills/value")] if flagged else [])


def test_min_above_max_is_one_e151_at_min() -> None:
    document = coffee()
    document["parameters"]["tills"] = {"value": 9, "type": "integer", "min": 5, "max": 1}
    with_scenarios(document, {"id": "busy", "set": {"tills": 9}})
    issue = only(parameter_issues(built(document)), "E151", "/parameters/tills/min")
    assert issue.message == "The 'min' of parameter 'tills' is 5, which is above its 'max', 1."


def test_a_scenario_value_outside_the_range_is_e151_at_the_scenario() -> None:
    document = with_scenarios(
        coffee(), {"id": "few", "set": {"tills": 2}}, {"id": "many", "set": {"tills": 6}}
    )
    path = "/experiments/0/scenarios/1/set/tills"
    issue = only(parameter_issues(built(document)), "E151", path)
    assert issue.message == (
        "Scenario 'many' of experiment 'base' sets 'tills' to 6, above its 'max', 5."
    )


def test_quantity_parameters_compare_and_show_times() -> None:
    document = with_parameters(
        coffee(), service_mean={"value": "2 h", "type": "quantity", "min": "1 min", "max": "90 min"}
    )
    issue = only(parameter_issues(built(document)), "E151", "/parameters/service_mean/value")
    assert issue.message == (
        "The 'value' of parameter 'service_mean' is 2 h, above its 'max', 90 min."
    )


def test_number_parameters_show_fractions() -> None:
    document = with_parameters(
        coffee(), share={"value": 1.25, "type": "number", "min": 0, "max": 1}
    )
    issue = only(parameter_issues(built(document)), "E151", "/parameters/share/value")
    assert "is 1.25, above its 'max', 1." in issue.message


# --- E150, E152: parameter references in components (spec 1 "Parameters") ---------------------


def test_a_reference_to_an_unknown_parameter_is_e150_at_the_setting() -> None:
    issue = only(reference_issues(built(till(capacity={"$param": "staff"}))), "E150", CAPACITY)
    assert issue.component == "till"
    assert issue.message == (
        "The 'capacity' setting of 'till' refers to the parameter 'staff', which is not in "
        "'parameters'."
    )


@pytest.mark.parametrize(
    ("service", "path"),
    [
        ({"dist": "exponential", "mean": {"$param": "m"}}, f"{SERVICE}/mean"),
        ({"dist": "weibull", "shape": {"$param": "m"}, "scale": "1 min"}, f"{SERVICE}/shape"),
        ({"dist": "empirical", "values": ["1 min", {"$param": "m"}]}, f"{SERVICE}/values/1"),
    ],
)
def test_e150_inside_a_distribution(service: dict[str, Any], path: str) -> None:
    issue = only(reference_issues(built(with_service(service))), "E150", path)
    assert issue.component == "till"
    assert "'m'" in issue.message


def test_e150_in_weights_and_shifts() -> None:
    document = with_branch(
        {"routes": ["a", "b"], "rule": "probability", "weights": {"a": 1, "b": {"$param": "w"}}},
        ["a", "b"],
    )
    added(document, schedule([{"start": "0 h", "end": "8 h", "capacity": {"$param": "c"}}]))
    issues = reference_issues(built(document))
    assert codes(issues) == [
        ("E150", "/components/2/params/weights/b"),
        ("E150", "/components/4/params/shifts/0/capacity"),
    ]
    assert issues[0].message.startswith("The weight of 'b' in the 'weights' setting of 'split'")
    assert issues[1].message.startswith(
        "The 'capacity' of item 1 of the 'shifts' setting of 'rota'"
    )


@pytest.mark.parametrize(
    ("parameter_type", "value", "fits"),
    [("integer", 2, True), ("number", 2.5, False), ("quantity", "2 min", False)],
)
def test_a_whole_number_setting_takes_only_an_integer_parameter(
    parameter_type: str, value: Any, fits: bool
) -> None:
    document = with_parameters(coffee(), tills={"value": value, "type": parameter_type})
    issues = reference_issues(built(document))
    assert codes(issues) == ([] if fits else [("E152", CAPACITY)])


def test_e152_names_the_type_and_what_the_place_takes() -> None:
    document = with_parameters(coffee(), tills={"value": 2.5, "type": "number"})
    issue = only(reference_issues(built(document)), "E152", CAPACITY)
    assert issue.component == "till"
    assert issue.message == (
        "The 'capacity' setting of 'till' refers to the parameter 'tills', whose 'type' is "
        "'number'; this place takes a whole number, so the parameter's 'type' must be "
        "'integer'."
    )


@pytest.mark.parametrize(
    ("parameter_type", "value", "fits"),
    [("integer", 2, True), ("number", 0.5, True), ("quantity", "2 min", False)],
)
def test_a_plain_number_place_takes_integer_or_number_parameters(
    parameter_type: str, value: Any, fits: bool
) -> None:
    # A weight is a plain number; so is a weibull `shape`.
    document = with_parameters(coffee(), w={"value": value, "type": parameter_type})
    document = with_branch(
        {"routes": ["a", "b"], "rule": "probability", "weights": {"a": {"$param": "w"}, "b": 1}},
        ["a", "b"],
    )
    document["parameters"]["w"] = {"value": value, "type": parameter_type}
    issues = reference_issues(built(document))
    assert codes(issues) == ([] if fits else [("E152", "/components/2/params/weights/a")])
    service = {"dist": "weibull", "shape": {"$param": "w"}, "scale": "1 min"}
    document = with_parameters(with_service(service), w={"value": value, "type": parameter_type})
    issues = reference_issues(built(document))
    assert codes(issues) == ([] if fits else [("E152", f"{SERVICE}/shape")])
    if not fits:
        assert "'integer' or 'number'" in issues[0].message


@pytest.mark.parametrize(
    ("parameter_type", "value", "fits"),
    [("quantity", "2 min", True), ("integer", 2, False), ("number", 2.0, False)],
)
def test_a_time_place_takes_only_a_quantity_parameter(
    parameter_type: str, value: Any, fits: bool
) -> None:
    service = {"dist": "exponential", "mean": {"$param": "m"}}
    document = with_parameters(with_service(service), m={"value": value, "type": parameter_type})
    document["components"][0]["params"]["first_arrival"] = {"$param": "m"}
    issues = reference_issues(built(document))
    expected = [
        ("E152", "/components/0/params/first_arrival"),
        ("E152", f"{SERVICE}/mean"),
    ]
    assert codes(issues) == ([] if fits else expected)
    if not fits:
        assert "takes a time" in issues[0].message


# --- E123: the smallest values settings take ---------------------------------------------------

EXPONENTIAL = {"dist": "exponential", "mean": "10 min"}


def component_with(type_name: str, params: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """The coffee shop with one more component of ``type_name`` holding ``params`` (and
    the type's other required settings); returns the document and its index."""
    base: dict[str, dict[str, Any]] = {
        "source": {"interarrival": EXPONENTIAL},
        "server": {"capacity": 1, "service": EXPONENTIAL},
        "queue": {"capacity": 1},
        "batch": {"size": 2},
        "store": {"initial": 5, "reorder_point": 1, "order_quantity": 5, "lead_time": EXPONENTIAL},
        "resource_pool": {"capacity": 1},
        "schedule": {"target": "till", "shifts": [{"start": "0 h", "end": "8 h", "capacity": 1}]},
    }
    document = coffee()
    component = {"id": "extra", "type": type_name, "params": {**base[type_name], **params}}
    document["components"].append(component)
    index = len(document["components"]) - 1
    if PORTS[type_name][1]:
        document["connections"].append({"from": f"extra.{PORTS[type_name][1]}", "to": "exit.in"})
    if PORTS[type_name][0]:
        # Feed it from a second source, so that nothing is left unconnected.
        document["components"].append(
            {"id": "feed", "type": "source", "params": {"interarrival": EXPONENTIAL}}
        )
        document["connections"].append({"from": "feed.out", "to": f"extra.{PORTS[type_name][0]}"})
    return document, index


# (input port, output port) of each type component_with adds.
PORTS = {
    "source": ("", "out"),
    "server": ("in", "out"),
    "queue": ("in", "out"),
    "batch": ("in", "out"),
    "store": ("in", "out"),
    "resource_pool": ("", ""),
    "schedule": ("", ""),
}


@pytest.mark.parametrize(
    ("type_name", "setting", "bad", "good", "message"),
    [
        ("source", "first_arrival", "-5 min", "0 s", "is -5 min; it must be at least 0 s."),
        ("source", "max_items", 0, 1, "is 0; it must be at least 1."),
        ("server", "capacity", 0, 1, "is 0; it must be at least 1."),
        ("server", "queue_capacity", -1, 0, "is -1; it must be at least 0."),
        ("queue", "capacity", 0, 1, "is 0; it must be at least 1."),
        ("batch", "size", 0, 1, "is 0; it must be at least 1."),
        ("batch", "timeout", "0 s", "90 s", "is 0 s; it must be above 0 s."),
        ("store", "initial", -1, 0, "is -1; it must be at least 0."),
        ("store", "reorder_point", -2, 0, "is -2; it must be at least 0."),
        ("store", "order_quantity", 0, 1, "is 0; it must be at least 1."),
        ("resource_pool", "capacity", 0, 1, "is 0; it must be at least 1."),
        ("schedule", "period", "0 h", "8 h", "is 0 s; it must be above 0 s."),
    ],
)
def test_a_setting_below_its_minimum_is_e123(
    type_name: str, setting: str, bad: Any, good: Any, message: str
) -> None:
    document, index = component_with(type_name, {setting: bad})
    issue = only(range_issues(built(document)), "E123", f"/components/{index}/params/{setting}")
    assert issue.component == "extra"
    assert issue.message == f"The '{setting}' setting of 'extra' {message}"
    document, _ = component_with(type_name, {setting: good})
    assert range_issues(built(document)) == []


def test_a_shift_capacity_below_zero_is_e123_and_zero_is_allowed() -> None:
    shift = {"start": "0 h", "end": "8 h", "capacity": -1}
    document = added(coffee(), schedule([shift]))
    issue = only(range_issues(built(document)), "E123", "/components/3/params/shifts/0/capacity")
    assert issue.message == (
        "The 'capacity' of item 1 of the 'shifts' setting of 'rota' is -1; it must be at least 0."
    )
    shift["capacity"] = 0
    assert range_issues(built(added(coffee(), schedule([shift])))) == []


def test_a_negative_weight_is_e123() -> None:
    document = with_branch(
        {"routes": ["a", "b"], "rule": "probability", "weights": {"a": -0.5, "b": 1}}, ["a", "b"]
    )
    issue = only(range_issues(built(document)), "E123", "/components/2/params/weights/a")
    assert issue.message == (
        "The weight of 'a' in the 'weights' setting of 'split' is -0.5; it must be at least 0."
    )


def test_a_zero_weight_is_allowed_when_another_is_above_zero() -> None:
    document = with_branch(
        {"routes": ["a", "b"], "rule": "probability", "weights": {"a": 0, "b": 1}}, ["a", "b"]
    )
    assert range_issues(built(document)) == []


def test_weights_that_are_all_zero_are_e123_at_weights() -> None:
    document = with_branch(
        {"routes": ["a", "b"], "rule": "probability", "weights": {"a": 0, "b": 0.0}}, ["a", "b"]
    )
    issue = only(range_issues(built(document)), "E123", "/components/2/params/weights")
    assert issue.component == "split"
    assert issue.message == (
        "Every value in the 'weights' setting of 'split' is 0; at least one must be above 0, "
        "since each of the 'routes' is chosen in proportion to its weight."
    )


def test_all_zero_is_not_reported_beside_a_negative_weight() -> None:
    document = with_branch(
        {"routes": ["a", "b"], "rule": "probability", "weights": {"a": -1, "b": 0}}, ["a", "b"]
    )
    assert codes(range_issues(built(document))) == [("E123", "/components/2/params/weights/a")]


def test_all_zero_weights_from_a_parameter_name_the_case() -> None:
    document = with_branch(
        {"routes": ["a"], "rule": "probability", "weights": {"a": {"$param": "w"}}}, ["a"]
    )
    document["parameters"]["w"] = {"value": 1, "type": "number"}
    with_scenarios(document, {"id": "off", "set": {"w": 0}})
    issue = only(range_issues(built(document)), "E123", "/components/2/params/weights")
    assert "is 0 in scenario 'off' of experiment 'base';" in issue.message


def test_all_zero_skips_weights_with_a_reference_problem() -> None:
    document = with_branch(
        {"routes": ["a"], "rule": "probability", "weights": {"a": {"$param": "w"}}}, ["a"]
    )
    assert range_issues(built(document)) == []  # E150 is reference_issues'


def test_a_branch_with_no_routes_is_e123_at_routes() -> None:
    document = with_branch({"routes": [], "rule": "shortest_queue"}, [])
    issue = only(range_issues(built(document)), "E123", "/components/2/params/routes")
    assert issue.component == "split"
    assert issue.message == "The 'routes' setting of 'split' is empty; it needs at least 1 entry."
    # The whole meaning pass reports no other error: an empty branch has no output port.
    # The exit, which only the branch fed, cannot be reached from the source (W200).
    assert codes(meaning_pass(built(document))) == [
        ("E123", "/components/2/params/routes"),
        ("W200", "/components/3"),
    ]


def test_empty_weights_are_not_all_zero() -> None:
    # No weights at all: the missing routes are E122 (setting_issues), not this check.
    document = with_branch({"routes": ["a"], "rule": "probability", "weights": {}}, ["a"])
    assert range_issues(built(document)) == []


@pytest.mark.parametrize(
    ("shift", "params", "message"),
    [
        (
            {"start": "8 h", "end": "8 h", "capacity": 1},
            {},
            "In item 1 of the 'shifts' setting of 'rota', the 'end' (8 h) is not after the "
            "'start' (8 h).",
        ),
        (
            {"start": "9 h", "end": "1 h", "capacity": 1},
            {},
            "In item 1 of the 'shifts' setting of 'rota', the 'end' (1 h) is not after the "
            "'start' (9 h).",
        ),
        (
            {"start": "20 h", "end": "25 h", "capacity": 1},
            {},
            "In item 1 of the 'shifts' setting of 'rota', the 'end' (25 h) is after the end of "
            "the schedule's 'period' (1 d); a shift lies within the period.",
        ),
        (
            {"start": "0 h", "end": "13 h", "capacity": 1},
            {"period": "12 h"},
            "In item 1 of the 'shifts' setting of 'rota', the 'end' (13 h) is after the end of "
            "the schedule's 'period' (12 h); a shift lies within the period.",
        ),
    ],
)
def test_a_shift_must_end_after_it_starts_and_within_the_period(
    shift: dict[str, Any], params: dict[str, Any], message: str
) -> None:
    document = added(coffee(), schedule([shift], **params))
    issue = only(range_issues(built(document)), "E123", "/components/3/params/shifts/0/end")
    assert issue.component == "rota"
    assert issue.message == message


@pytest.mark.parametrize(
    ("shift", "params"),
    [
        ({"start": "0 h", "end": "24 h", "capacity": 1}, {}),
        ({"start": "16 h", "end": "1 d", "capacity": 1}, {}),
        ({"start": "0 h", "end": "7 d", "capacity": 1}, {"period": "7 d"}),
    ],
)
def test_a_shift_may_end_at_the_end_of_the_period(
    shift: dict[str, Any], params: dict[str, Any]
) -> None:
    assert range_issues(built(added(coffee(), schedule([shift], **params)))) == []


def test_shift_checks_resolve_parameters_and_skip_a_bad_reference() -> None:
    shift = {"start": "0 h", "end": {"$param": "close"}, "capacity": 1}
    document = added(coffee(), schedule([shift]))
    document["parameters"]["close"] = {"value": "8 h", "type": "quantity", "max": "30 h"}
    issue = only(range_issues(built(document)), "E123", "/components/3/params/shifts/0/end")
    assert "(30 h) is after the end of the schedule's 'period' (1 d) with the parameter " in (
        issue.message
    )
    assert "'close' at its 'max'" in issue.message
    document["parameters"]["close"] = {"value": 8, "type": "integer"}
    assert range_issues(built(document)) == []  # E152 is reference_issues'


def test_a_parameter_below_the_minimum_names_its_min() -> None:
    document = coffee()
    document["parameters"]["tills"]["min"] = 0
    issue = only(range_issues(built(document)), "E123", CAPACITY)
    assert issue.message == (
        "The 'capacity' setting of 'till' is 0 with the parameter 'tills' at its 'min'; it "
        "must be at least 1."
    )


def test_a_parameter_below_the_minimum_at_its_value() -> None:
    document = coffee()
    document["parameters"]["tills"] = {"value": 0, "type": "integer"}
    issue = only(range_issues(built(document)), "E123", CAPACITY)
    assert "is 0 with the parameter 'tills' at its 'value';" in issue.message


def test_a_parameter_below_the_minimum_in_a_scenario() -> None:
    document = coffee()
    document["parameters"]["tills"] = {"value": 1, "type": "integer"}
    with_scenarios(
        document, {"id": "two", "set": {"tills": 2}}, {"id": "none", "set": {"tills": 0}}
    )
    issue = only(range_issues(built(document)), "E123", CAPACITY)
    assert "is 0 in scenario 'none' of experiment 'base';" in issue.message


def test_one_issue_per_place_even_when_several_cases_fail() -> None:
    document = coffee()
    document["parameters"]["tills"] = {"value": 0, "type": "integer", "min": -1, "max": 0}
    issues = range_issues(built(document))
    assert codes(issues) == [("E123", CAPACITY)]
    assert "at its 'value'" in issues[0].message  # the first case


def test_range_checks_skip_a_reference_with_e150_or_e152() -> None:
    assert range_issues(built(till(capacity={"$param": "staff"}))) == []
    document = with_parameters(coffee(), tills={"value": -2.5, "type": "number"})
    assert range_issues(built(document)) == []


# --- E160: distribution fields (spec 1 "Distributions") ----------------------------------------


@pytest.mark.parametrize(
    ("service", "field", "shown"),
    [
        ({"dist": "exponential", "mean": "0 min"}, "mean", "0 s"),
        ({"dist": "exponential", "mean": "-2 min"}, "mean", "-2 min"),
        ({"dist": "normal", "mean": "5 min", "sd": "0 s"}, "sd", "0 s"),
        ({"dist": "lognormal", "mean": "0 s", "sd": "1 min"}, "mean", "0 s"),
        ({"dist": "lognormal", "mean": "5 min", "sd": "-1 min"}, "sd", "-1 min"),
        ({"dist": "weibull", "shape": 0, "scale": "1 min"}, "shape", "0"),
        ({"dist": "weibull", "shape": -1.5, "scale": "1 min"}, "shape", "-1.5"),
        ({"dist": "weibull", "shape": 2, "scale": "0 s"}, "scale", "0 s"),
    ],
)
def test_a_field_that_must_be_above_zero_is_e160(
    service: dict[str, Any], field: str, shown: str
) -> None:
    issues = distribution_issues(built(with_service(service)))
    issue = only(issues, "E160", f"{SERVICE}/{field}")
    assert issue.component == "till"
    assert issue.message == (
        f"The '{field}' of the '{service['dist']}' distribution in the 'service' setting of "
        f"'till' is {shown}; it must be greater than zero."
    )


@pytest.mark.parametrize(
    "service",
    [
        {"dist": "constant", "value": "0 s"},
        {"dist": "normal", "mean": "0 s", "sd": "1 min"},
        {"dist": "normal", "mean": "-1 min", "sd": "1 min"},
        {"dist": "uniform", "min": "2 min", "max": "2 min"},
        {"dist": "triangular", "min": "1 min", "mode": "1 min", "max": "1 min"},
        {"dist": "empirical", "values": ["0 s"]},
    ],
)
def test_fields_spec_1_does_not_restrict_pass(service: dict[str, Any]) -> None:
    # Only `sd`, `shape`, `scale` and the `mean` of a positive distribution must be above
    # zero, and only a `min` above the `max` is out of order; W202 (AKS-91) covers a normal
    # that clips.
    assert distribution_issues(built(with_service(service))) == []


def test_uniform_min_above_max_is_e160_at_min() -> None:
    service = {"dist": "uniform", "min": "3 min", "max": "90 s"}
    issue = only(distribution_issues(built(with_service(service))), "E160", f"{SERVICE}/min")
    assert issue.message == (
        "In the 'uniform' distribution in the 'service' setting of 'till', the 'min' (3 min) "
        "is above the 'max' (90 s)."
    )


@pytest.mark.parametrize(
    ("values", "text"),
    [
        (("2 min", "1 min", "3 min"), "the 'mode' (1 min) is below the 'min' (2 min)"),
        (("1 min", "4 min", "3 min"), "the 'mode' (4 min) is above the 'max' (3 min)"),
        (("5 min", "4 min", "3 min"), "the 'mode' (4 min) is below the 'min' (5 min)"),
        (("5 min", "6 min", "3 min"), "the 'mode' (6 min) is above the 'max' (3 min)"),
    ],
)
def test_triangular_fields_out_of_order_are_e160_at_mode(
    values: tuple[str, str, str], text: str
) -> None:
    service = dict(zip(("min", "mode", "max"), values, strict=True), dist="triangular")
    issue = only(distribution_issues(built(with_service(service))), "E160", f"{SERVICE}/mode")
    assert issue.message == (
        f"In the 'triangular' distribution in the 'service' setting of 'till', {text}."
    )


def test_an_empty_values_is_e160() -> None:
    service = {"dist": "empirical", "values": []}
    issue = only(distribution_issues(built(with_service(service))), "E160", f"{SERVICE}/values")
    assert issue.message.startswith(
        "The 'values' of the 'empirical' distribution in the 'service' setting of 'till' is empty"
    )


def test_distribution_checks_resolve_parameters() -> None:
    service = {"dist": "exponential", "mean": {"$param": "m"}}
    document = with_service(service)
    document["parameters"]["m"] = {"value": "2 min", "type": "quantity", "min": "0 s"}
    issue = only(distribution_issues(built(document)), "E160", f"{SERVICE}/mean")
    assert "is 0 s with the parameter 'm' at its 'min'; it must be greater than zero." in (
        issue.message
    )
    service = {"dist": "uniform", "min": {"$param": "low"}, "max": {"$param": "high"}}
    document = with_service(service)
    document["parameters"]["low"] = {"value": "1 min", "type": "quantity"}
    document["parameters"]["high"] = {"value": "2 min", "type": "quantity"}
    with_scenarios(document, {"id": "flip", "set": {"low": "3 min"}})
    issue = only(distribution_issues(built(document)), "E160", f"{SERVICE}/min")
    assert issue.message.endswith(
        "the 'min' (3 min) is above the 'max' (2 min) in scenario 'flip' of experiment 'base'."
    )


def test_several_parameters_at_their_value_are_named_together() -> None:
    service = {"dist": "uniform", "min": {"$param": "low"}, "max": {"$param": "high"}}
    document = with_service(service)
    document["parameters"]["low"] = {"value": "3 min", "type": "quantity"}
    document["parameters"]["high"] = {"value": "2 min", "type": "quantity"}
    issue = only(distribution_issues(built(document)), "E160", f"{SERVICE}/min")
    assert issue.message.endswith("with the parameters 'low' and 'high' at their 'value'.")


def test_distribution_checks_skip_a_distribution_with_a_reference_problem() -> None:
    service = {"dist": "uniform", "min": "3 min", "max": {"$param": "high"}}
    assert distribution_issues(built(with_service(service))) == []


def test_distributions_in_every_kind_of_setting_are_checked() -> None:
    document = coffee()
    document["components"][0]["params"]["interarrival"] = {"dist": "exponential", "mean": "0 s"}
    issue = only(
        distribution_issues(built(document)), "E160", "/components/0/params/interarrival/mean"
    )
    assert issue.component == "arrivals"


# --- E162: data references (spec 1 "Distributions", `empirical` with `data`) --------------------


def with_data(file: str = "times.csv", column: str = "minutes") -> dict[str, Any]:
    return with_service({"dist": "empirical", "data": {"file": file, "column": column}})


def index(folder: Path, *files: DataFile) -> DataIndex:
    return DataIndex(folder, {entry.name: entry for entry in files})


def times(sha256: str = DIGEST, columns: tuple[DataColumn, ...] | None = None) -> DataFile:
    return DataFile(
        "times.csv",
        columns if columns is not None else (DataColumn("minutes", "min"), DataColumn("count")),
        sha256,
    )


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    (tmp_path / "times.csv").write_bytes(CONTENT)
    return tmp_path


def test_with_nothing_imported_a_data_reference_is_e162_at_file() -> None:
    issue = only(data_issues(built(with_data())), "E162", f"{SERVICE}/data/file")
    assert issue.component == "till"
    assert issue.message == (
        "In the 'service' setting of 'till', the 'file' of the data reference is 'times.csv', "
        "which is not in the project's data/ folder."
    )
    assert issue.hint.startswith("Import the file")


def test_a_reference_to_an_imported_file_and_column_passes(folder: Path) -> None:
    model = built(with_data())
    assert data_issues(model, index(folder, times())) == []


def test_a_column_of_plain_numbers_for_a_time_is_e162_at_column(folder: Path) -> None:
    """Every distribution setting in Phase 1 is a time, so a column needs a declared time
    unit (spec 1 "Distributions", AKS-113)."""
    issue = only(
        data_issues(built(with_data(column="count")), index(folder, times())),
        "E162",
        f"{SERVICE}/data/column",
    )
    assert issue.component == "till"
    assert issue.message == (
        "In the 'service' setting of 'till', the 'column' of the data reference is 'count', "
        "which holds plain numbers, but the setting takes a time."
    )
    assert "unit" in issue.hint


def test_a_column_whose_values_overflow_in_seconds_is_e162_at_column(folder: Path) -> None:
    """The check inline quantities go through (spec 1 "Quantities": a value whose SI value
    is not a finite float), applied to the column's largest value (Codex on PR #37)."""
    columns = (DataColumn("minutes", "min", "number", 1e308),)
    issue = only(
        data_issues(built(with_data()), index(folder, times(columns=columns))),
        "E162",
        f"{SERVICE}/data/column",
    )
    assert "too large" in issue.message and "seconds" in issue.message
    fits = (DataColumn("minutes", "s", "number", 1e308),)
    assert data_issues(built(with_data()), index(folder, times(columns=fits))) == []


@pytest.mark.parametrize("kind", ["text", "empty"])
def test_a_column_that_does_not_hold_numbers_is_e162_at_column(
    folder: Path, kind: ColumnType
) -> None:
    columns = (DataColumn("minutes", "min", kind),)
    issue = only(
        data_issues(built(with_data()), index(folder, times(columns=columns))),
        "E162",
        f"{SERVICE}/data/column",
    )
    expected = "holds text" if kind == "text" else "holds no values"
    assert expected in issue.message


def test_a_file_not_in_the_index_lists_the_imported_files(folder: Path) -> None:
    issue = only(
        data_issues(built(with_data("other.csv")), index(folder, times())),
        "E162",
        f"{SERVICE}/data/file",
    )
    assert issue.hint == "Name one of the imported files: 'times.csv'."


def test_a_file_in_the_folder_but_not_in_the_index_is_e162(folder: Path) -> None:
    (folder / "loose.csv").write_bytes(CONTENT)
    issues = data_issues(built(with_data("loose.csv")), index(folder, times()))
    assert codes(issues) == [("E162", f"{SERVICE}/data/file")]


def test_an_unknown_column_is_e162_at_column(folder: Path) -> None:
    issue = only(
        data_issues(built(with_data(column="hours")), index(folder, times())),
        "E162",
        f"{SERVICE}/data/column",
    )
    assert issue.message == (
        "In the 'service' setting of 'till', the 'column' of the data reference is 'hours', "
        "which is not a column of 'times.csv'."
    )
    assert issue.hint == "Name one of its columns: 'minutes' or 'count'."


def test_an_unknown_column_of_a_file_without_columns(folder: Path) -> None:
    issue = only(
        data_issues(built(with_data()), index(folder, times(columns=()))),
        "E162",
        f"{SERVICE}/data/column",
    )
    assert "has no columns" in issue.hint


def test_a_file_missing_from_the_folder_is_e162(tmp_path: Path) -> None:
    issue = only(
        data_issues(built(with_data()), index(tmp_path, times())), "E162", f"{SERVICE}/data/file"
    )
    assert "is listed in the project's data index but is missing from its data/ folder" in (
        issue.message
    )


def test_a_changed_file_is_e162(folder: Path) -> None:
    (folder / "times.csv").write_bytes(CONTENT + b"9.0,1\n")
    issue = only(
        data_issues(built(with_data()), index(folder, times())), "E162", f"{SERVICE}/data/file"
    )
    assert "has changed since it was imported (its SHA-256 differs" in issue.message
    assert issue.hint == "Import the file again, so that its columns are read afresh."


def test_a_changed_file_and_an_unknown_column_are_two_issues(folder: Path) -> None:
    stale = times(sha256="0" * 64)
    issues = data_issues(built(with_data(column="hours")), index(folder, stale))
    assert codes(issues) == [("E162", f"{SERVICE}/data/file"), ("E162", f"{SERVICE}/data/column")]


def test_each_file_is_hashed_once_per_pass(folder: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    document = with_data()
    document["components"][0]["params"]["interarrival"] = {
        "dist": "empirical",
        "data": {"file": "times.csv", "column": "minutes"},
    }
    data = index(folder, times())
    calls: list[str] = []
    original = DataIndex.current_sha256

    def counted(self: DataIndex, name: str) -> str | None:
        calls.append(name)
        return original(self, name)

    monkeypatch.setattr(DataIndex, "current_sha256", counted)
    assert data_issues(built(document), data) == []
    assert calls == ["times.csv"]


def test_the_loader_passes_the_data_index_to_the_meaning_pass(folder: Path) -> None:
    data = index(folder, times())
    document = with_data()
    assert codes(list(load_document(document).issues)) == [("E162", f"{SERVICE}/data/file")]
    assert load_document(document, data=data).issues == ()
    text = json.dumps(document)
    assert load_text(text, data=data).issues == ()
    path = folder / "model.json"
    path.write_text(text, encoding="utf-8")
    assert load_model(path, data=data).components[1].id == "till"
    with pytest.raises(ModelLoadError) as caught:
        load_model(path)
    assert [issue.code for issue in caught.value.issues] == ["E162"]


# --- E170, E171: experiments (spec 1 "Experiments") ----------------------------------------------


def experiment(**fields: Any) -> dict[str, Any]:
    document = coffee()
    document["experiments"][0].update(fields)
    for key in [key for key, value in fields.items() if value is None]:
        del document["experiments"][0][key]
    return document


@pytest.mark.parametrize(
    ("fields", "key", "message"),
    [
        (
            {"warmup": "200 h"},
            "warmup",
            "The 'warmup' of experiment 'base' is 200 h, which is not less than its 'length', "
            "200 h; no time would be observed after the warm-up.",
        ),
        (
            {"warmup": "9 d"},
            "warmup",
            "The 'warmup' of experiment 'base' is 9 d, which is not less than its 'length', "
            "200 h; no time would be observed after the warm-up.",
        ),
        (
            {"warmup": "-1 h"},
            "warmup",
            "The 'warmup' of experiment 'base' is -1 h; it must be at least 0 s.",
        ),
        (
            {"length": "0 s", "warmup": None},
            "length",
            "The 'length' of experiment 'base' is 0 s; it must be above 0 s.",
        ),
        (
            {"length": "-2 h", "warmup": "1 h"},
            "length",
            "The 'length' of experiment 'base' is -2 h; it must be above 0 s.",
        ),
        (
            {"replications": 1},
            "replications",
            "The 'replications' of experiment 'base' is 1; it must be at least 2, so that a "
            "confidence interval can be given.",
        ),
        (
            {"confidence": 1},
            "confidence",
            "The 'confidence' of experiment 'base' is 1; it must lie between 0 and 1, both "
            "excluded.",
        ),
        (
            {"confidence": 0.0},
            "confidence",
            "The 'confidence' of experiment 'base' is 0; it must lie between 0 and 1, both "
            "excluded.",
        ),
        (
            {"confidence": 1.5},
            "confidence",
            "The 'confidence' of experiment 'base' is 1.5; it must lie between 0 and 1, both "
            "excluded.",
        ),
        (
            {"record_interval": "0 s"},
            "record_interval",
            "The 'record_interval' of experiment 'base' is 0 s; it must be above 0 s.",
        ),
    ],
)
def test_an_experiment_value_out_of_range_is_e170(
    fields: dict[str, Any], key: str, message: str
) -> None:
    issue = only(experiment_issues(built(experiment(**fields))), "E170", f"/experiments/0/{key}")
    assert issue.component is None
    assert issue.message == message


@pytest.mark.parametrize(
    "fields",
    [
        {"warmup": "199 h"},
        {"warmup": None},
        {"replications": 2},
        {"confidence": 0.5},
        {"confidence": 0.999},
        {"record_interval": "1 s"},
    ],
)
def test_experiment_values_in_range_pass(fields: dict[str, Any]) -> None:
    assert experiment_issues(built(experiment(**fields))) == []


def test_a_bad_length_is_reported_once() -> None:
    # The default record_interval (length / 200) is not reported beside the length.
    issues = experiment_issues(built(experiment(length="0 s", warmup=None)))
    assert codes(issues) == [("E170", "/experiments/0/length")]


def test_several_values_out_of_range_give_one_issue_each() -> None:
    document = experiment(warmup="300 h", replications=0, confidence=2)
    assert codes(experiment_issues(built(document))) == [
        ("E170", "/experiments/0/warmup"),
        ("E170", "/experiments/0/replications"),
        ("E170", "/experiments/0/confidence"),
    ]


@pytest.mark.parametrize(
    ("search", "key", "message"),
    [
        (
            {"budget": 0},
            "budget",
            "The 'budget' of the search of experiment 'base' is 0; it must be at least 1 "
            "candidate.",
        ),
        (
            {"replications": 1},
            "replications",
            "The 'replications' of the search of experiment 'base' is 1; it must be at least 2.",
        ),
    ],
)
def test_a_search_value_out_of_range_is_e170(
    search: dict[str, Any], key: str, message: str
) -> None:
    document = machine_count()
    document["experiments"][0]["search"].update(search)
    path = f"/experiments/0/search/{key}"
    issue = only(experiment_issues(built(document)), "E170", path)
    assert issue.message == message


def test_a_search_naming_an_unknown_objective_is_e171() -> None:
    document = machine_count()
    document["experiments"][0]["search"]["objective"] = "cost"
    issue = only(experiment_issues(built(document)), "E171", "/experiments/0/search/objective")
    assert issue.message == (
        "The 'objective' of the search of experiment 'base' is 'cost', which is not the id of "
        "an objective in 'objectives'."
    )
    assert issue.hint == "Name one of the objectives: 'wait'."
    del document["objectives"]
    issue = only(experiment_issues(built(document)), "E171", "/experiments/0/search/objective")
    assert issue.hint == "Add an objective to 'objectives' and name its id here."


@pytest.mark.parametrize("missing", ["min", "max"])
def test_a_search_variable_without_min_and_max_is_e171(missing: str) -> None:
    document = machine_count()
    del document["parameters"]["tills"][missing]
    document["experiments"][0]["search"]["variables"] = ["tills"]
    issue = only(experiment_issues(built(document)), "E171", "/experiments/0/search/variables/0")
    assert issue.message == (
        "Variable 1 in the 'variables' of the search of experiment 'base' is 'tills', a "
        "parameter without both a 'min' and a 'max'; the search varies each variable between "
        "the two."
    )


def test_a_search_variable_that_is_not_a_parameter_is_e150() -> None:
    document = machine_count()
    document["experiments"][0]["search"]["variables"] = ["tills", "staff"]
    issue = only(experiment_issues(built(document)), "E150", "/experiments/0/search/variables/1")
    assert issue.message == (
        "Variable 2 in the 'variables' of the search of experiment 'base' is 'staff', which is "
        "not a parameter."
    )


@pytest.mark.parametrize("listed", [True, False])
def test_a_search_with_no_variables_is_e171(listed: bool) -> None:
    document = machine_count()
    if listed:
        document["experiments"][0]["search"]["variables"] = []
    else:
        # None listed, and no parameter has both a min and a max to make the default.
        del document["parameters"]["tills"]["max"]
    issue = only(experiment_issues(built(document)), "E171", "/experiments/0/search/variables")
    assert issue.message.startswith("The search of experiment 'base' has no parameters to vary")


def test_a_search_variable_named_twice_is_e171_at_the_repeat() -> None:
    """A repeated `search.variables` entry (M1 leftover; AKS-109, owner to confirm)."""
    document = machine_count()
    document["parameters"]["staff"] = {"value": 2, "type": "integer", "min": 1, "max": 3}
    document["experiments"][0]["search"]["variables"] = ["tills", "staff", "tills"]
    issue = only(experiment_issues(built(document)), "E171", "/experiments/0/search/variables/2")
    assert issue.message == (
        "Variable 3 in the 'variables' of the search of experiment 'base' is 'tills', which "
        "variable 1 already names; the search varies each parameter once."
    )
    assert issue.hint == "Remove the repeated 'tills' from 'variables'."
    assert issue.component is None


def test_a_search_in_an_experiment_with_scenarios_is_e171() -> None:
    """A search runs its own candidates, not scenarios (AKS-109, owner to confirm)."""
    document = machine_count()
    document["experiments"][0]["scenarios"] = [{"id": "two", "set": {"tills": 2}}]
    issue = only(experiment_issues(built(document)), "E171", "/experiments/0/scenarios")
    assert issue.message == (
        "Experiment 'base' has a search and also lists scenarios; a search runs its own "
        "candidates from the parameters' values, not scenarios."
    )
    assert issue.hint == (
        "Move the scenarios to an experiment without a search, or remove 'scenarios'."
    )
    # An empty list is the default scenario, as without the key.
    document["experiments"][0]["scenarios"] = []
    assert experiment_issues(built(document)) == []


def test_experiments_are_checked_each_at_its_own_index() -> None:
    document = coffee()
    document["experiments"].append({"id": "short", "length": "1 h", "warmup": "2 h"})
    assert codes(experiment_issues(built(document))) == [("E170", "/experiments/1/warmup")]


# --- E174 and constraint values: metric names (spec 1 "Metric names") ---------------------------


def objectives(*metrics: str) -> dict[str, Any]:
    document = coffee()
    document["objectives"] = [
        {"id": f"o{number}", "metric": metric, "sense": "minimize"}
        for number, metric in enumerate(metrics)
    ]
    return document


def test_metrics_spec_2_defines_pass() -> None:
    document = objectives(
        "till.wait.mean",
        "till.utilization",
        "till.queue_length.max",
        "arrivals.created",
        "arrivals.discarded",
        "exit.throughput",
        "exit.cycle_time.mean",
        "exit.count",
        "model.wip.mean",
    )
    assert metric_issues(built(document)) == []


@pytest.mark.parametrize(
    ("metric", "problem"),
    [
        ("counter.wait.mean", "but no component has the id 'counter'"),
        (
            "exit.wait.mean",
            "but 'exit' is a sink, which reports only 'exit.throughput', "
            "'exit.cycle_time.mean' or 'exit.count'",
        ),
        ("till.wait", "but 'till' is a server, which reports only 'till.wait.mean'"),
        ("model.throughput", "but the whole model reports only 'model.wip.mean'"),
        ("utilization", "which is not a metric name"),
        ("till.", "which is not a metric name"),
        (".wait.mean", "which is not a metric name"),
    ],
)
def test_an_objective_naming_an_undefined_metric_is_e174(metric: str, problem: str) -> None:
    issue = only(metric_issues(built(objectives(metric))), "E174", "/objectives/0/metric")
    assert issue.component is None
    assert issue.message.startswith(f"The 'metric' of objective 'o0' is '{metric}', {problem}")


def test_a_type_without_metrics_says_so() -> None:
    document = objectives("pause.wait.mean")
    document["components"].insert(
        2, {"id": "pause", "type": "delay", "params": {"time": EXPONENTIAL}}
    )
    document["connections"] = [
        {"from": "arrivals.out", "to": "till.in"},
        {"from": "till.out", "to": "pause.in"},
        {"from": "pause.out", "to": "exit.in"},
    ]
    issue = only(metric_issues(built(document)), "E174", "/objectives/0/metric")
    assert "but 'pause' is a delay, which reports no metrics." in issue.message


def constraint(metric: str, value: Any) -> dict[str, Any]:
    document = coffee()
    document["constraints"] = [{"id": "c", "metric": metric, "op": "<=", "value": value}]
    return document


def test_a_constraint_naming_an_undefined_metric_is_e174_only() -> None:
    issue = only(
        metric_issues(built(constraint("till.speed", "5 min"))), "E174", "/constraints/0/metric"
    )
    assert issue.message.startswith("The 'metric' of constraint 'c' is 'till.speed'")


@pytest.mark.parametrize(
    ("metric", "value"),
    [
        ("till.wait.mean", "5 min"),
        ("exit.cycle_time.mean", "1 h"),
        ("till.utilization", 0.85),
        ("till.queue_length.mean", 3),
        ("exit.throughput", 0.008),
        ("model.wip.mean", 10),
    ],
)
def test_constraint_values_of_the_right_kind_pass(metric: str, value: Any) -> None:
    assert metric_issues(built(constraint(metric, value))) == []


@pytest.mark.parametrize(
    ("metric", "value", "message"),
    [
        (
            "till.wait.mean",
            5,
            "The 'value' of constraint 'c' is the plain number 5, but 'till.wait.mean' is "
            "measured in time, so a time such as '5 min' is expected.",
        ),
        (
            "till.utilization",
            "5 min",
            "The 'value' of constraint 'c' is a time, 5 min, but 'till.utilization' is a plain "
            "number, so a plain number is expected.",
        ),
        (
            "exit.throughput",
            "1 h",
            "The 'value' of constraint 'c' is a time, 1 h, but 'exit.throughput' is a rate, "
            "written as a plain number of items per second (Phase 1 has no rate unit).",
        ),
    ],
)
def test_a_constraint_value_of_the_wrong_kind_is_e123(
    metric: str, value: Any, message: str
) -> None:
    issue = only(metric_issues(built(constraint(metric, value))), "E123", "/constraints/0/value")
    assert issue.message == message


def test_a_repeated_component_id_resolves_to_the_first() -> None:
    document = objectives("till.wait.mean")
    document["components"].append({"id": "till", "type": "sink", "params": {}})
    assert metric_issues(built(document)) == []


# --- the whole pass ---------------------------------------------------------------------------


def test_the_meaning_pass_runs_every_part_b_group() -> None:
    document = coffee()
    document["parameters"]["tills"]["value"] = 9  # E151
    document["parameters"]["late"] = {"value": "1 h", "type": "quantity"}
    document["components"][0]["params"]["first_arrival"] = {"$param": "gone"}  # E150
    document["components"][1]["params"]["service"] = {
        "dist": "normal",
        "mean": "1 min",
        "sd": "0 s",
    }
    document["components"][2] = {"id": "exit", "type": "sink", "params": {}}
    document["experiments"][0]["replications"] = 1  # E170
    document["objectives"] = [{"id": "o", "metric": "exit.wait.mean", "sense": "minimize"}]
    issues = meaning_pass(built(document))
    assert codes(issues) == [
        ("E151", "/parameters/tills/value"),
        ("E150", "/components/0/params/first_arrival"),
        ("E160", f"{SERVICE}/sd"),
        ("E170", "/experiments/0/replications"),
        ("E174", "/objectives/0/metric"),
    ]
    # The loader runs it, so the file gives no model.
    result = load_document(document)
    assert result.model is None
    assert codes(list(result.issues)) == codes(issues)


def test_messages_hold_no_exception_text() -> None:
    document = machine_count()
    document["parameters"]["tills"]["value"] = 9
    document["experiments"][0]["search"]["objective"] = "x"
    document["components"][1]["params"]["service"] = {"dist": "uniform", "min": "2 s", "max": "1 s"}
    for issue in meaning_pass(built(document)):
        assert "Error" not in issue.message and "Traceback" not in issue.message
        assert issue.hint


def test_a_long_list_in_a_hint_shows_the_first_twelve(folder: Path) -> None:
    names = [f"f{number:02}.csv" for number in range(13)]
    data = DataIndex(folder, {name: DataFile(name, (), DIGEST) for name in names})
    issue = only(data_issues(built(with_data()), data), "E162", f"{SERVICE}/data/file")
    assert issue.hint.startswith("Name one of the imported files, such as 'f00.csv', ")
    assert issue.hint.endswith(" or 'f11.csv'.")
    assert "f12.csv" not in issue.hint


# --- review of PR #9 ------------------------------------------------------------------------


def two_weights(a: Any, b: Any) -> dict[str, Any]:
    return with_branch(
        {"routes": ["a", "b"], "rule": "probability", "weights": {"a": a, "b": b}}, ["a", "b"]
    )


def test_weights_too_large_for_a_float_do_not_raise() -> None:
    document = two_weights(10**309, 1.0)
    assert load_document(document).issues == ()
    assert range_issues(built(two_weights(10**309, 0))) == []


def test_parameters_that_a_search_varies_together_are_checked_together() -> None:
    document = two_weights({"$param": "x"}, {"$param": "y"})
    for name in ("x", "y"):
        document["parameters"][name] = {"value": 1, "type": "number", "min": 0, "max": 1}
    issue = only(range_issues(built(document)), "E123", "/components/2/params/weights")
    assert issue.message.startswith(
        "Every value in the 'weights' setting of 'split' is 0 with 'x' at its 'min' and 'y' "
        "at its 'min';"
    )
    document["parameters"]["y"]["min"] = 0.5
    assert range_issues(built(document)) == []


def test_joint_bounds_of_distribution_fields() -> None:
    service = {"dist": "uniform", "min": {"$param": "low"}, "max": {"$param": "high"}}
    document = with_service(service)
    document["parameters"]["low"] = {
        "value": "1 min",
        "type": "quantity",
        "min": "0 s",
        "max": "3 min",
    }
    document["parameters"]["high"] = {"value": "4 min", "type": "quantity", "min": "2 min"}
    issue = only(distribution_issues(built(document)), "E160", f"{SERVICE}/min")
    assert issue.message.endswith(
        "the 'min' (3 min) is above the 'max' (2 min) with 'low' at its 'max' and 'high' at "
        "its 'min'."
    )


def test_a_parameter_without_bounds_stays_at_its_value_in_joint_cases() -> None:
    service = {"dist": "uniform", "min": {"$param": "low"}, "max": {"$param": "high"}}
    document = with_service(service)
    document["parameters"]["low"] = {"value": "1 min", "type": "quantity"}
    document["parameters"]["high"] = {"value": "4 min", "type": "quantity", "min": "2 min"}
    assert distribution_issues(built(document)) == []


def test_a_parameter_named_twice_is_one_value() -> None:
    # `min` and `max` both from one parameter can never be out of order.
    service = {"dist": "uniform", "min": {"$param": "t"}, "max": {"$param": "t"}}
    document = with_service(service)
    document["parameters"]["t"] = {
        "value": "1 min",
        "type": "quantity",
        "min": "0 s",
        "max": "9 min",
    }
    assert distribution_issues(built(document)) == []


def test_many_parameters_are_checked_at_all_lowest_and_all_highest_bounds() -> None:
    routes = [f"r{number}" for number in range(13)]  # one more than the joint limit
    document = with_branch(
        {
            "routes": routes,
            "rule": "probability",
            "weights": {route: {"$param": route} for route in routes},
        },
        routes,
    )
    for route in routes:
        document["parameters"][route] = {"value": 1, "type": "number", "min": 0, "max": 1}
    issue = only(range_issues(built(document)), "E123", "/components/2/params/weights")
    assert "with 'r0' at its 'min', 'r1' at its 'min'," in issue.message
    assert issue.message.count("at its 'min'") == 13
