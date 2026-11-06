"""The meaning-pass warnings (AKS-91): W200, W201 and W202.

Spec 1 "Validation" (how flow rates for W201 are propagated, and where they are not),
"Distributions" (the theoretical means of the sampling test; a `normal` is clipped at
zero), "Validation issues" (the W rows; warnings do not block a run); spec 2 "Block
reference" for the blocks that change or stop a flow. Each test names the rule it checks.
"""

import copy
import itertools
import json
import math
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from lcsim.model.issues import Issue
from lcsim.model.loading import build_document, load_document
from lcsim.model.model import Distribution, Model
from lcsim.model.units import Dimension, Quantity
from lcsim.model.validation import (
    clipping_issues,
    distribution_mean,
    flow_rates,
    load_issues,
    meaning_pass,
    unreachable_issues,
)

ROOT = Path(__file__).resolve().parents[2]
COFFEE_SHOP: dict[str, Any] = json.loads(
    (ROOT / "examples" / "coffee_shop.json").read_text(encoding="utf-8")
)
FIXTURES = Path(__file__).parent / "fixtures" / "issues"
EXCEPTION_TEXT = ("Traceback", "Exception", "Error")

MINUTE = 60


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


def exponential(mean: str | dict[str, str]) -> dict[str, Any]:
    return {"dist": "exponential", "mean": mean}


def source(name: str, mean: str = "2 min", **params: Any) -> dict[str, Any]:
    return {
        "id": name,
        "type": "source",
        "params": {"interarrival": exponential(mean), **params},
    }


def server(name: str, mean: str = "1.5 min", capacity: Any = 1, **params: Any) -> dict[str, Any]:
    return {
        "id": name,
        "type": "server",
        "params": {"capacity": capacity, "service": exponential(mean), **params},
    }


def block(name: str, kind: str, **params: Any) -> dict[str, Any]:
    return {"id": name, "type": kind, "params": params}


def sink(name: str = "exit") -> dict[str, Any]:
    return block(name, "sink")


def link(origin: str, destination: str) -> dict[str, str]:
    return {"from": origin, "to": destination}


def chain(*names: str) -> list[dict[str, str]]:
    """Connections from each named port ``a.out`` to the next block's ``in``."""
    return [
        link(origin, f"{after.split('.')[0]}.in") for origin, after in itertools.pairwise(names)
    ]


def process(
    components: list[dict[str, Any]],
    connections: list[dict[str, str]],
    **parameters: dict[str, Any],
) -> dict[str, Any]:
    """A process model with the coffee shop's experiment."""
    document = coffee()
    document["components"] = components
    document["connections"] = connections
    document["parameters"] = parameters
    return document


def with_service(service: dict[str, Any]) -> dict[str, Any]:
    document = coffee()
    document["components"][1]["params"]["service"] = service
    return document


def with_scenarios(document: dict[str, Any], *scenarios: dict[str, Any]) -> dict[str, Any]:
    document["experiments"][0]["scenarios"] = list(scenarios)
    return document


def per_minute(rate: Fraction | None) -> Fraction | None:
    return None if rate is None else rate * MINUTE


def assert_plain(issue: Issue) -> None:
    """Spec 1: a message names the component and key in plain language, no exception text."""
    assert issue.severity == "warning"
    for text in (issue.message, issue.hint):
        assert text
        assert not any(word in text for word in EXCEPTION_TEXT), text


# --- the examples and the fixtures --------------------------------------------------------------


GROUPS: list[Callable[[Model], list[Issue]]] = [unreachable_issues, load_issues, clipping_issues]


@pytest.mark.parametrize("group", GROUPS, ids=[group.__name__ for group in GROUPS])
def test_the_coffee_shop_raises_no_warning(group: Callable[[Model], list[Issue]]) -> None:
    assert group(built(coffee())) == []


@pytest.mark.parametrize("code", ["W200", "W201", "W202"])
def test_a_warning_fixture_loads_with_its_warning_and_no_error(code: str) -> None:
    """Spec 1 "Validation issues": warnings do not block a run, so the model loads."""
    (fixture,) = FIXTURES.glob(f"{code}_*.json")
    result = load_document(json.loads(fixture.read_text(encoding="utf-8")))
    assert result.model is not None
    assert [issue.code for issue in result.issues] == [code]


def test_the_meaning_pass_runs_the_warnings_last() -> None:
    document = with_service({"dist": "normal", "mean": "3 min", "sd": "2 min"})
    document["components"].append(sink("spare"))
    document["components"][0]["params"]["interarrival"] = exponential("2 min")
    issues = meaning_pass(built(document))
    assert [issue.code for issue in issues] == ["W200", "W201", "W202"]


# --- W200: reachable from a source --------------------------------------------------------------


def test_w200_a_block_no_source_reaches() -> None:
    document = coffee()
    document["components"].append(sink("spare"))
    (issue,) = unreachable_issues(built(document))
    assert codes([issue]) == [("W200", "/components/3")]
    assert issue.component == "spare"
    assert "'spare'" in issue.message
    assert_plain(issue)


def test_w200_names_each_unreached_block_but_not_a_reached_one() -> None:
    document = coffee()
    document["components"] += [block("rework", "delay", time=exponential("1 min"))]
    document["connections"].append(link("rework.out", "exit.in"))
    assert codes(unreachable_issues(built(document))) == [("W200", "/components/3")]


def test_w200_blocks_without_an_in_port_are_never_named() -> None:
    document = coffee()
    document["components"] += [
        block("staff", "resource_pool", capacity=1),
        block(
            "rota",
            "schedule",
            target="till",
            shifts=[{"start": "0 h", "end": "8 h", "capacity": 1}],
        ),
        block(
            "breakdowns",
            "failure",
            target="till",
            time_to_failure=exponential("1 h"),
            time_to_repair=exponential("5 min"),
        ),
        source("idle"),
    ]
    document["connections"].append(link("idle.out", "exit.in"))
    assert unreachable_issues(built(document)) == []


def test_w200_reached_through_branch_routes_and_a_loop() -> None:
    components = [
        source("arrivals"),
        server("till"),
        block(
            "check",
            "branch",
            routes=["again", "done"],
            rule="probability",
            weights={"again": 1, "done": 9},
        ),
        sink(),
    ]
    connections = [
        link("arrivals.out", "till.in"),
        link("till.out", "check.in"),
        link("check.again", "till.in"),
        link("check.done", "exit.in"),
    ]
    assert unreachable_issues(built(process(components, connections))) == []


def test_w200_a_model_without_a_source_names_every_block_with_an_in_port() -> None:
    components = [server("till"), sink()]
    issues = unreachable_issues(built(process(components, chain("till.out", "exit"))))
    assert codes(issues) == [("W200", "/components/0"), ("W200", "/components/1")]


def test_w200_a_connection_with_a_wrong_end_reaches_nothing() -> None:
    document = coffee()
    document["connections"][0] = link("arrivals.out", "till.inn")  # E130
    model = built(document)
    assert codes(unreachable_issues(model)) == [
        ("W200", "/components/1"),
        ("W200", "/components/2"),
    ]


def test_w200_follows_the_first_connection_of_an_output_port() -> None:
    """Spec 1: an output port connects to exactly one input port; a second is E132."""
    document = coffee()
    document["components"].append(sink("spare"))
    document["connections"].append(link("till.out", "spare.in"))
    assert codes(unreachable_issues(built(document))) == [("W200", "/components/3")]


def test_w200_a_repeated_id_is_named_once() -> None:
    document = coffee()
    document["components"].append(sink("exit"))  # E110
    assert unreachable_issues(built(document)) == []


def test_w200_optimization_models_have_no_components() -> None:
    model = built(
        {
            "format_version": "0.1",
            "meta": {"name": "Tiny"},
            "domain": "optimization",
            "variables": [{"id": "x", "type": "continuous", "lower": 0}],
            "objective": {"sense": "maximize", "linear": {"x": 1}},
            "constraints": [{"id": "cap", "linear": {"x": 1}, "op": "<=", "rhs": 4}],
        }
    )
    assert unreachable_issues(model) == []
    assert load_issues(model) == []
    assert clipping_issues(model) == []


# --- distribution means: spec 1 "Distributions", sampling test section ---------------------------


def mean_of(
    distribution: dict[str, Any], model: Model | None = None, **values: Any
) -> Fraction | None:
    document = with_service(distribution)
    model = model or built(document)
    service = model.components[1].settings["service"]
    assert isinstance(service, Distribution)
    return distribution_mean(model, service, values or None)


def phi(z: float) -> float:
    return math.exp(-z * z / 2) / math.sqrt(2 * math.pi)


def big_phi(z: float) -> float:
    return 0.5 * math.erfc(-z / math.sqrt(2))


@pytest.mark.parametrize(
    ("distribution", "seconds"),
    [
        ({"dist": "constant", "value": "2 min"}, 120),
        ({"dist": "exponential", "mean": "1.5 min"}, 90),
        ({"dist": "uniform", "min": "1 min", "max": "2 min"}, 90),
        ({"dist": "uniform", "min": "1 min", "max": "1 min"}, 60),
        ({"dist": "triangular", "min": "1 min", "mode": "2 min", "max": "6 min"}, 180),
        ({"dist": "lognormal", "mean": "3 min", "sd": "1 min"}, 180),
        ({"dist": "weibull", "shape": 2, "scale": "2 min"}, 120 * math.gamma(1.5)),
        ({"dist": "weibull", "shape": 1, "scale": "2 min"}, 120),
        ({"dist": "empirical", "values": ["1 min", "2 min", "6 min"]}, 180),
        # mean ≥ 5 sd, as in the sampling test: clipping at zero is negligible.
        ({"dist": "normal", "mean": "10 min", "sd": "2 min"}, 600),
    ],
)
def test_the_mean_of_each_distribution_is_its_theoretical_mean(
    distribution: dict[str, Any], seconds: float
) -> None:
    mean = mean_of(distribution)
    assert mean is not None
    # A normal at mean = 5 sd is above `mean` by one part in 10^8.
    assert float(mean) == pytest.approx(seconds, rel=1e-7)


def test_the_mean_of_exact_distributions_is_exact() -> None:
    assert mean_of({"dist": "uniform", "min": "1 min", "max": "2 min"}) == Fraction(90)
    assert mean_of({"dist": "empirical", "values": ["1 s", "2 s"]}) == Fraction(3, 2)
    assert mean_of({"dist": "triangular", "min": "0 s", "mode": "1 s", "max": "1 s"}) == Fraction(
        2, 3
    )


@pytest.mark.parametrize(("mean", "sd"), [(60.0, 60.0), (90.0, 60.0), (0.0, 60.0), (-60.0, 30.0)])
def test_a_normal_mean_is_that_of_its_samples_clipped_at_zero(mean: float, sd: float) -> None:
    """Spec 1 "Distributions": negative samples are set to zero, which raises the mean;
    E[max(X, 0)] = mean·Φ(mean/sd) + sd·φ(mean/sd)."""
    expected = mean * big_phi(mean / sd) + sd * phi(mean / sd)
    result = mean_of({"dist": "normal", "mean": f"{mean} s", "sd": f"{sd} s"})
    assert result is not None
    assert float(result) == pytest.approx(expected, rel=1e-12)
    assert float(result) >= max(mean, 0.0)


def test_a_normal_mean_far_below_zero_is_zero() -> None:
    assert mean_of({"dist": "normal", "mean": "-1e300 s", "sd": "1e-300 s"}) == 0


def test_the_mean_of_a_parameter_fed_distribution_follows_the_given_values() -> None:
    document = with_service({"dist": "exponential", "mean": {"$param": "service"}})
    document["parameters"]["service"] = {"value": "1 min", "type": "quantity"}
    model = built(document)
    assert mean_of({}, model) == Fraction(60)
    assert mean_of({}, model, service=Quantity(120.0, Dimension.TIME)) == Fraction(120)


@pytest.mark.parametrize(
    "distribution",
    [
        {"dist": "exponential", "mean": "0 s"},
        {"dist": "exponential", "mean": {"$param": "nothing"}},  # E150
        {"dist": "exponential", "mean": {"$param": "tills"}},  # E152
        {"dist": "uniform", "min": "2 min", "max": "1 min"},
        {"dist": "triangular", "min": "1 min", "mode": "3 min", "max": "2 min"},
        {"dist": "normal", "mean": "1 min", "sd": "0 s"},
        {"dist": "lognormal", "mean": "1 min", "sd": "0 s"},
        {"dist": "lognormal", "mean": "0 s", "sd": "1 s"},
        {"dist": "weibull", "shape": 0, "scale": "1 min"},
        {"dist": "weibull", "shape": 1, "scale": "0 s"},
        {"dist": "weibull", "shape": 0.001, "scale": "1 min"},  # Γ(1001) overflows
        {"dist": "weibull", "shape": 0.5, "scale": "1e308 s"},  # the mean is not finite
        {"dist": "empirical", "values": []},
        {"dist": "empirical", "values": ["1 min", {"$param": "nothing"}]},  # E150
        {"dist": "empirical", "data": {"file": "times.csv", "column": "minutes"}},
    ],
)
def test_a_mean_that_cannot_be_known_is_none(distribution: dict[str, Any]) -> None:
    """Fields that are inconsistent (E160), references that do not fit (E150, E152), a
    mean that overflows, and a `data` column, which the model layer does not read."""
    assert mean_of(distribution) is None


# --- W201: rates propagated from sources ------------------------------------------------------


def test_w201_the_coffee_shop_rates() -> None:
    rates = flow_rates(built(coffee()))
    assert rates == {"till": Fraction(1, 120), "exit": Fraction(1, 120)}


def test_w201_a_server_that_cannot_keep_up() -> None:
    document = with_service(exponential("2.5 min"))
    (issue,) = load_issues(built(document))
    assert codes([issue]) == [("W201", "/components/1")]
    assert issue.component == "till"
    assert issue.message == (
        "The mean arrival rate at 'till' (30 per hour) times its mean service time "
        "(2.5 min) is 1.25, which is at least its 'capacity' of 1, and its queue is "
        "unlimited, so the queue will grow without limit."
    )
    assert_plain(issue)


def test_w201_a_load_equal_to_the_capacity_is_reported() -> None:
    """Spec 1 W201: "at least its capacity"; compared exactly, not in floating point."""
    document = with_service(exponential("0.1 min"))
    document["components"][0]["params"]["interarrival"] = exponential("0.1 min")
    assert codes(load_issues(built(document))) == [("W201", "/components/1")]


def test_w201_a_server_with_a_limited_queue_is_not_checked() -> None:
    document = with_service(exponential("5 min"))
    document["components"][1]["params"]["queue_capacity"] = 10
    assert load_issues(built(document)) == []


def test_w201_more_capacity_keeps_up() -> None:
    document = with_service(exponential("2.5 min"))
    document["parameters"]["tills"]["value"] = 2
    assert load_issues(built(document)) == []


def test_w201_checks_each_scenario_and_names_the_first_that_fails() -> None:
    document = with_service(exponential("2.5 min"))
    document["parameters"]["tills"]["value"] = 2
    with_scenarios(
        document,
        {"id": "two", "set": {"tills": 2}},
        {"id": "one", "set": {"tills": 1}},
    )
    (issue,) = load_issues(built(document))
    assert issue.message.endswith(
        "so the queue will grow without limit in scenario 'one' of experiment 'base'."
    )


def test_w201_the_search_range_of_a_parameter_is_not_checked() -> None:
    """A search tries values the modeller expects to be poor (DECISIONS, AKS-91): only
    the parameter's `value` and each scenario's value are runs the experiments make."""
    document = with_service(exponential("2.5 min"))
    document["parameters"]["tills"].update(value=2, min=1)
    assert load_issues(built(document)) == []


def test_w201_a_parameter_fed_arrival_rate() -> None:
    document = coffee()
    document["components"][0]["params"]["interarrival"] = exponential({"$param": "gap"})
    document["parameters"]["gap"] = {"value": "1 min", "type": "quantity"}
    assert codes(load_issues(built(document))) == [("W201", "/components/1")]
    document["parameters"]["gap"]["value"] = "3 min"
    assert load_issues(built(document)) == []


def branch_model(weights: dict[str, Any], rule: str = "probability") -> dict[str, Any]:
    params: dict[str, Any] = {"routes": ["a", "b"], "rule": rule}
    if weights:
        params["weights"] = weights
    components = [
        source("arrivals", "1 min"),
        block("split", "branch", **params),
        server("serve_a", "3 min"),
        server("serve_b", "1.5 min"),
        sink(),
    ]
    connections = [
        link("arrivals.out", "split.in"),
        link("split.a", "serve_a.in"),
        link("split.b", "serve_b.in"),
        link("serve_a.out", "exit.in"),
        link("serve_b.out", "exit.in"),
    ]
    return process(components, connections)


def test_w201_a_probability_branch_multiplies_by_weight_over_total() -> None:
    model = built(branch_model({"a": 1, "b": 3}))
    rates = flow_rates(model)
    assert per_minute(rates["serve_a"]) == Fraction(1, 4)
    assert per_minute(rates["serve_b"]) == Fraction(3, 4)
    assert per_minute(rates["exit"]) == 1  # merges add
    # serve_a: 0.25 x 3 = 0.75; serve_b: 0.75 x 1.5 = 1.125.
    assert codes(load_issues(model)) == [("W201", "/components/3")]


def test_w201_branch_weights_from_parameters() -> None:
    document = branch_model({"a": {"$param": "share"}, "b": 1})
    document["parameters"]["share"] = {"value": 3, "type": "number"}
    rates = flow_rates(built(document))
    assert per_minute(rates["serve_a"]) == Fraction(3, 4)


@pytest.mark.parametrize(
    "weights",
    [
        {"a": 0, "b": 0},  # E123
        {"a": -1, "b": 2},  # E123
        {"a": 1},  # E122
        {"a": {"$param": "nothing"}, "b": 1},  # E150
    ],
)
def test_w201_weights_that_cannot_be_used_stop_the_flow(weights: dict[str, Any]) -> None:
    rates = flow_rates(built(branch_model(weights)))
    assert rates["serve_a"] is None and rates["serve_b"] is None and rates["exit"] is None


def test_w201_merges_add() -> None:
    components = [
        source("north", "4 min"),
        source("south", "4 min"),
        server("till", "2.5 min"),
        sink(),
    ]
    connections = [
        link("north.out", "till.in"),
        link("south.out", "till.in"),
        link("till.out", "exit.in"),
    ]
    model = built(process(components, connections))
    assert per_minute(flow_rates(model)["till"]) == Fraction(1, 2)
    assert codes(load_issues(model)) == [("W201", "/components/2")]


def batch_model(*middle: dict[str, Any], service: str = "1.5 min") -> dict[str, Any]:
    components = [source("arrivals", "1 min"), *middle, server("till", service), sink()]
    names = ["arrivals.out", *(f"{item['id']}.out" for item in middle), "till.out", "exit"]
    return process(components, chain(*names))


def test_w201_a_batch_divides_by_its_size() -> None:
    model = built(batch_model(block("pack", "batch", size=5), service="4 min"))
    assert per_minute(flow_rates(model)["till"]) == Fraction(1, 5)
    assert load_issues(model) == []  # 0.2 x 4 = 0.8
    model = built(batch_model(block("pack", "batch", size=5), service="5 min"))
    assert codes(load_issues(model)) == [("W201", "/components/2")]  # 0.2 x 5 = 1


def test_w201_an_unbatch_multiplies_by_the_size_of_what_it_receives() -> None:
    model = built(batch_model(block("pack", "batch", size=5), block("unpack", "unbatch")))
    assert per_minute(flow_rates(model)["till"]) == 1
    assert codes(load_issues(model)) == [("W201", "/components/3")]


def test_w201_an_unbatch_of_single_items_leaves_the_rate() -> None:
    model = built(batch_model(block("unpack", "unbatch"), service="0.5 min"))
    assert per_minute(flow_rates(model)["till"]) == 1


def test_w201_nested_batches_unbatch_one_level() -> None:
    model = built(
        batch_model(
            block("pairs", "batch", size=2),
            block("sixes", "batch", size=3),
            block("unpack", "unbatch"),
        )
    )
    assert per_minute(flow_rates(model)["till"]) == Fraction(1, 2)


def test_w201_batched_and_single_items_merge() -> None:
    components = [
        source("loose", "1 min"),
        source("packed", "1 min"),
        block("pack", "batch", size=4),
        block("unpack", "unbatch"),
        server("till", "0.1 min"),
        sink(),
    ]
    connections = [
        link("loose.out", "unpack.in"),
        link("packed.out", "pack.in"),
        link("pack.out", "unpack.in"),
        link("unpack.out", "till.in"),
        link("till.out", "exit.in"),
    ]
    rates = flow_rates(built(process(components, connections)))
    assert per_minute(rates["unpack"]) == Fraction(5, 4)
    assert per_minute(rates["till"]) == 2


def test_w201_a_batch_size_from_a_parameter() -> None:
    document = batch_model(block("pack", "batch", size={"$param": "size"}))
    document["parameters"]["size"] = {"value": 4, "type": "integer"}
    assert per_minute(flow_rates(built(document))["till"]) == Fraction(1, 4)


def test_w201_a_blocking_queue_passes_the_rate_on() -> None:
    model = built(
        batch_model(
            block("wait", "delay", time=exponential("1 min")),
            block("line", "queue", capacity=5),
            service="2 min",
        )
    )
    assert per_minute(flow_rates(model)["till"]) == 1
    assert codes(load_issues(model)) == [("W201", "/components/3")]


SKIPS: dict[str, list[dict[str, Any]]] = {
    "a store": [
        block(
            "stock",
            "store",
            initial=10,
            reorder_point=2,
            order_quantity=10,
            lead_time=exponential("1 h"),
        )
    ],
    "a batch with a timeout": [block("pack", "batch", size=1, timeout="10 min")],
    "a discarding queue": [
        block("wait", "delay", time=exponential("1 min")),
        block("line", "queue", capacity=5, on_full="discard"),
    ],
    "a source feeding a queue": [block("line", "queue", capacity=5)],
    "a source feeding a server with a limited queue": [
        server("first", "0.5 min", queue_capacity=3)
    ],
    "a block with an unknown batch size": [block("pack", "batch", size={"$param": "nothing"})],
}


@pytest.mark.parametrize("middle", list(SKIPS))
def test_w201_is_skipped_downstream_of_a_block_that_stops_the_rate(middle: str) -> None:
    """Spec 1 "Validation": stores, timeouts and loss points stop the propagation; so does
    a value that cannot be read."""
    model = built(batch_model(*SKIPS[middle], service="5 min"))
    assert flow_rates(model)["till"] is None
    assert load_issues(model) == []


def test_w201_is_skipped_after_a_shortest_queue_branch() -> None:
    model = built(branch_model({}, rule="shortest_queue"))
    assert flow_rates(model)["serve_b"] is None
    assert load_issues(model) == []


@pytest.mark.parametrize(
    "extra",
    [
        block(
            "rota",
            "schedule",
            target="till",
            shifts=[{"start": "0 h", "end": "8 h", "capacity": 1}],
        ),
        block(
            "breakdowns",
            "failure",
            target="till",
            time_to_failure=exponential("1 h"),
            time_to_repair=exponential("5 min"),
        ),
    ],
    ids=["schedule", "failure"],
)
def test_w201_is_skipped_at_and_after_a_server_with_a_schedule_or_failure(
    extra: dict[str, Any],
) -> None:
    document = with_service(exponential("5 min"))
    document["components"][2:2] = [server("after", "5 min")]
    document["connections"] = chain("arrivals.out", "till.out", "after.out", "exit")
    document["components"].append(extra)
    model = built(document)
    assert flow_rates(model)["after"] is None
    assert load_issues(model) == []


def test_w201_is_skipped_at_a_server_whose_pool_has_a_schedule() -> None:
    document = with_service(exponential("5 min"))
    document["components"][1]["params"]["pool"] = "staff"
    document["components"] += [
        block("staff", "resource_pool", capacity=1),
        block(
            "rota",
            "schedule",
            target="staff",
            shifts=[{"start": "0 h", "end": "8 h", "capacity": 1}],
        ),
    ]
    model = built(document)
    assert flow_rates(model)["exit"] is None
    assert load_issues(model) == []


def test_w201_a_pool_without_a_schedule_does_not_stop_the_rate() -> None:
    document = with_service(exponential("5 min"))
    document["components"][1]["params"]["pool"] = "staff"
    document["components"].append(block("staff", "resource_pool", capacity=1))
    assert codes(load_issues(built(document))) == [("W201", "/components/1")]


def test_w201_is_skipped_on_a_loop_and_after_it() -> None:
    """A rate on a loop needs the traffic equations solved, which the model layer does not
    do (guide rule 7): every block on or after a loop is skipped."""
    components = [
        source("arrivals", "1 min"),
        server("till", "5 min"),
        block(
            "check",
            "branch",
            routes=["again", "done"],
            rule="probability",
            weights={"again": 1, "done": 9},
        ),
        server("after", "5 min"),
        sink(),
    ]
    connections = [
        link("arrivals.out", "till.in"),
        link("till.out", "check.in"),
        link("check.again", "till.in"),
        link("check.done", "after.in"),
        link("after.out", "exit.in"),
    ]
    model = built(process(components, connections))
    rates = flow_rates(model)
    assert rates["till"] is None and rates["after"] is None
    assert load_issues(model) == []


def test_w201_a_merge_with_one_unknown_input_is_skipped() -> None:
    components = [
        source("arrivals", "1 min"),
        source("other", "1 min"),
        block("line", "queue", capacity=3),
        server("till", "5 min"),
        sink(),
    ]
    connections = [
        link("arrivals.out", "till.in"),
        link("other.out", "line.in"),
        link("line.out", "till.in"),
        link("till.out", "exit.in"),
    ]
    model = built(process(components, connections))
    assert flow_rates(model)["till"] is None
    assert load_issues(model) == []


@pytest.mark.parametrize(
    "interarrival",
    [
        {"dist": "constant", "value": "0 s"},
        {"dist": "uniform", "min": "-2 min", "max": "-1 min"},
        {"dist": "empirical", "data": {"file": "times.csv", "column": "minutes"}},
        {"dist": "exponential", "mean": {"$param": "tills"}},  # E152
    ],
)
def test_w201_a_source_without_a_positive_known_mean_stops_the_rate(
    interarrival: dict[str, Any],
) -> None:
    document = with_service(exponential("5 min"))
    document["components"][0]["params"]["interarrival"] = interarrival
    model = built(document)
    assert flow_rates(model)["till"] is None
    assert load_issues(model) == []


def test_w201_a_source_with_max_items_is_still_checked() -> None:
    """Spec 1 propagates from every source; `max_items` is not a reason to skip (DECISIONS,
    AKS-91)."""
    document = with_service(exponential("5 min"))
    document["components"][0]["params"]["max_items"] = 100
    assert codes(load_issues(built(document))) == [("W201", "/components/1")]


@pytest.mark.parametrize(
    ("change", "value"),
    [
        ("service", {"dist": "empirical", "data": {"file": "t.csv", "column": "c"}}),
        ("service", {"dist": "exponential", "mean": {"$param": "nothing"}}),
        ("capacity", {"$param": "nothing"}),
        ("capacity", 0),
    ],
)
def test_w201_a_server_whose_service_or_capacity_is_unknown_is_skipped(
    change: str, value: Any
) -> None:
    document = coffee()
    document["components"][0]["params"]["interarrival"] = exponential("1 s")
    document["components"][1]["params"][change] = value
    assert load_issues(built(document)) == []


def test_w201_an_unreached_server_has_no_arrivals() -> None:
    document = coffee()
    document["components"].insert(2, server("spare", "1 h"))
    document["connections"].append(link("spare.out", "exit.in"))
    model = built(document)
    assert flow_rates(model)["spare"] == 0
    assert load_issues(model) == []


def test_w201_a_zero_service_time_never_warns() -> None:
    document = with_service({"dist": "constant", "value": "0 s"})
    document["components"][0]["params"]["interarrival"] = {"dist": "constant", "value": "1e-300 s"}
    assert load_issues(built(document)) == []


def test_w201_shows_very_large_and_very_small_values_without_failing() -> None:
    document = with_service({"dist": "constant", "value": "1e300 s"})
    document["components"][0]["params"]["interarrival"] = {"dist": "constant", "value": "1e-300 s"}
    (issue,) = load_issues(built(document))
    assert "a very large number" in issue.message
    assert_plain(issue)


def test_w201_a_huge_whole_capacity_keeps_up() -> None:
    document = coffee()
    document["parameters"]["tills"].update(value=10**400, max=10**401)
    assert load_issues(built(document)) == []


def test_w201_a_repeated_id_is_checked_once() -> None:
    document = with_service(exponential("5 min"))
    document["components"].append(server("till", "1 s"))  # E110; E131 on its out port
    assert codes(load_issues(built(document))) == [("W201", "/components/1")]


# --- W202: a normal distribution clipped at zero --------------------------------------------------


def test_w202_a_normal_that_clips_two_percent_or_more() -> None:
    document = with_service({"dist": "normal", "mean": "1.5 min", "sd": "1 min"})
    (issue,) = clipping_issues(built(document))
    assert codes([issue]) == [("W202", "/components/1/params/service")]
    assert issue.component == "till"
    assert issue.message == (
        "The 'normal' distribution in the 'service' setting of 'till' has a 'mean' (1.5 min) "
        "less than twice its 'sd' (1 min), so about 6.7% of its samples are below zero; "
        "they are set to zero, which raises its mean to 1.53 min."
    )
    assert_plain(issue)


def test_w202_a_mean_of_exactly_twice_the_sd_is_not_reported() -> None:
    """Spec 1 W202: `mean` below twice `sd`; at exactly twice, 2.3% of samples clip."""
    document = with_service({"dist": "normal", "mean": "2 min", "sd": "1 min"})
    assert clipping_issues(built(document)) == []


def test_w202_in_every_setting_that_holds_a_distribution() -> None:
    normal = {"dist": "normal", "mean": "1 min", "sd": "1 min"}
    document = coffee()
    document["components"][0]["params"]["interarrival"] = normal
    document["components"].append(
        block(
            "breakdowns",
            "failure",
            target="till",
            time_to_failure=normal,
            time_to_repair=exponential("1 min"),
        )
    )
    issues = clipping_issues(built(document))
    assert codes(issues) == [
        ("W202", "/components/0/params/interarrival"),
        ("W202", "/components/3/params/time_to_failure"),
    ]
    assert [issue.component for issue in issues] == ["arrivals", "breakdowns"]


def test_w202_a_parameter_fed_sd_in_a_scenario() -> None:
    document = with_service({"dist": "normal", "mean": "3 min", "sd": {"$param": "spread"}})
    document["parameters"]["spread"] = {
        "value": "1 min",
        "type": "quantity",
        "min": "1 min",
        "max": "5 min",
    }
    assert clipping_issues(built(document)) == []  # the search range is not checked
    with_scenarios(document, {"id": "wide", "set": {"spread": "2 min"}})
    (issue,) = clipping_issues(built(document))
    assert issue.message.startswith(
        "The 'normal' distribution in the 'service' setting of 'till' has a 'mean' (3 min) "
        "less than twice its 'sd' (2 min) in scenario 'wide' of experiment 'base', so"
    )


@pytest.mark.parametrize(
    "service",
    [
        {"dist": "normal", "mean": "1 min", "sd": "0 s"},  # E160
        {"dist": "normal", "mean": "1 min", "sd": {"$param": "tills"}},  # E152
        {"dist": "normal", "mean": {"$param": "nothing"}, "sd": "1 min"},  # E150
        {"dist": "lognormal", "mean": "1 min", "sd": "5 min"},
    ],
)
def test_w202_not_for_an_unusable_normal_or_another_distribution(service: dict[str, Any]) -> None:
    assert clipping_issues(built(with_service(service))) == []


def test_w202_a_normal_with_a_negative_mean_clips_most_samples() -> None:
    document = with_service({"dist": "normal", "mean": "-1 min", "sd": "1 min"})
    (issue,) = clipping_issues(built(document))
    assert "about 84% of its samples are below zero" in issue.message
