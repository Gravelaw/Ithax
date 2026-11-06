"""Model loading: typed objects, SI conversion and defaults (AKS-88).

Spec 1 "Model file", "Top-level keys", "Units", "Quantities", "Parameters", "Components
and ports", "Distributions", "Experiments", "Versioning"; spec 2 "Block reference" and
"Mathematical optimization in the model file". Each test names the rule it checks.
"""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from lcsim.model.issues import Issue
from lcsim.model.loading import (
    SEED_LIMIT,
    LoadResult,
    ModelLoadError,
    load_document,
    load_model,
    load_text,
)
from lcsim.model.model import (
    Component,
    Connection,
    DataRef,
    Distribution,
    Endpoint,
    Experiment,
    LinearConstraint,
    LinearObjective,
    LinearProgram,
    Meta,
    MetricConstraint,
    MetricObjective,
    Model,
    Parameter,
    ParamRef,
    RunSettings,
    Scenario,
    Search,
    Variable,
)
from lcsim.model.units import Dimension, Quantity

ROOT = Path(__file__).resolve().parents[2]
COFFEE_SHOP_PATH = ROOT / "examples" / "coffee_shop.json"
COFFEE_SHOP: dict[str, Any] = json.loads(COFFEE_SHOP_PATH.read_text(encoding="utf-8"))
TIME = Dimension.TIME


def minutes(value: float) -> Quantity:
    return Quantity(value * 60.0, TIME)


def hours(value: float) -> Quantity:
    return Quantity(value * 3600.0, TIME)


# Spec 2 "Mathematical optimization in the model file", the product mix example.
PRODUCT_MIX: dict[str, Any] = {
    "format_version": "0.1",
    "meta": {"name": "Product mix"},
    "domain": "optimization",
    "variables": [
        {"id": "chairs", "type": "continuous", "lower": 0},
        {"id": "tables", "type": "continuous", "lower": 0},
    ],
    "objective": {"sense": "maximize", "linear": {"chairs": 45, "tables": 80}},
    "constraints": [
        {"id": "wood", "linear": {"chairs": 5, "tables": 20}, "op": "<=", "rhs": 400},
        {"id": "labour", "linear": {"chairs": 10, "tables": 15}, "op": "<=", "rhs": 450},
    ],
}


def coffee() -> dict[str, Any]:
    return copy.deepcopy(COFFEE_SHOP)


def model_of(document: object) -> Model:
    result = load_document(document, seed_source=lambda: 7)
    assert result.issues == (), [issue.as_dict() for issue in result.issues]
    assert result.model is not None
    return result.model


def only_issue(document: object) -> Issue:
    result = load_document(document, seed_source=lambda: 7)
    assert result.model is None
    assert len(result.issues) == 1, [issue.as_dict() for issue in result.issues]
    return result.issues[0]


def with_component(component: dict[str, Any]) -> dict[str, Any]:
    """The coffee shop with one more component (not connected; graph checks are AKS-89)."""
    document = coffee()
    document["components"].append(component)
    return document


def settings_of(component: dict[str, Any]) -> Component:
    model = model_of(with_component(component))
    return model.components[-1]


# --- the coffee shop, spec 1 "A minimal example" ----------------------------------------


def test_coffee_shop_loads_with_no_issue() -> None:
    # Spec 1 acceptance, M1 row 1 (the loader's part; AKS-93 adds the other examples).
    model = load_model(COFFEE_SHOP_PATH)
    assert isinstance(model, Model)
    assert model.format_version == "0.1"
    assert model.meta == Meta(name="Coffee shop", description=None, author=None, template=None)
    assert model.domain == "process"


def test_coffee_shop_components_are_typed_and_in_si() -> None:
    model = model_of(coffee())
    arrivals, till, exit_ = model.components
    assert arrivals == Component(
        id="arrivals",
        type="source",
        settings={"interarrival": Distribution("exponential", {"mean": Quantity(120.0, TIME)})},
        label=None,
        ui=None,
    )
    assert till.settings == {
        "capacity": ParamRef("tills"),
        "service": Distribution("exponential", {"mean": Quantity(90.0, TIME)}),
    }
    assert exit_.settings == {}
    assert exit_.type == "sink"


def test_coffee_shop_parameters_connections_and_run() -> None:
    model = model_of(coffee())
    assert model.parameters == {
        "tills": Parameter(id="tills", type="integer", value=1, min=1, max=5, description=None)
    }
    assert model.connections == (
        Connection(Endpoint("arrivals", "out"), Endpoint("till", "in")),
        Connection(Endpoint("till", "out"), Endpoint("exit", "in")),
    )
    assert model.run == RunSettings(target="local", fidelity="standard", engine=None)
    assert model.program is None
    assert model.objectives == ()
    assert model.constraints == ()


def test_coffee_shop_experiment_in_si_with_defaults_filled() -> None:
    (experiment,) = model_of(coffee()).experiments
    assert experiment == Experiment(
        id="base",
        length=hours(200),
        warmup=hours(10),
        replications=30,
        seed=12345,
        seed_chosen=False,
        scenarios=(Scenario(id="default", set={}),),
        confidence=0.95,
        record_interval=hours(1),  # length / 200
        search=None,
    )


def test_model_is_immutable() -> None:
    model = model_of(coffee())
    with pytest.raises(AttributeError):
        model.domain = "x"  # type: ignore[misc]
    with pytest.raises(TypeError):
        model.parameters["x"] = model.parameters["tills"]  # type: ignore[index]
    with pytest.raises(TypeError):
        model.components[0].settings["x"] = 1  # type: ignore[index]


def test_model_component_lookup() -> None:
    model = model_of(coffee())
    till = model.component("till")
    assert till is not None
    assert till.type == "server"
    assert model.component("nowhere") is None


def test_component_ports_follow_the_catalogue() -> None:
    model = model_of(coffee())
    arrivals, till, exit_ = model.components
    assert (arrivals.input_ports, arrivals.output_ports) == ((), ("out",))
    assert (till.input_ports, till.output_ports) == (("in",), ("out",))
    assert (exit_.input_ports, exit_.output_ports) == (("in",), ())


def test_branch_output_ports_are_its_routes() -> None:
    branch = settings_of(
        {
            "id": "split",
            "type": "branch",
            "params": {"routes": ["a", "b"], "rule": "probability", "weights": {"a": 1, "b": 3}},
        }
    )
    assert branch.input_ports == ("in",)
    assert branch.output_ports == ("a", "b")
    assert branch.settings["routes"] == ("a", "b")
    assert branch.settings["weights"] == {"a": 1, "b": 3}


# --- format versions (spec 1 "Versioning") --------------------------------------------------


def test_a_lower_minor_loads_with_defaults_filled_in_memory() -> None:
    document = coffee()
    document["format_version"] = "0.0"
    del document["run"]
    del document["experiments"][0]["warmup"]
    model = model_of(document)
    assert model.format_version == "0.0"
    assert model.run == RunSettings(target="local", fidelity="standard", engine=None)
    assert model.experiments[0].warmup == Quantity(0.0, TIME)


def test_schema_issues_stop_loading() -> None:
    document = coffee()
    document["format_version"] = "0.2"
    issue = only_issue(document)
    assert issue.code == "E101"
    document = coffee()
    del document["meta"]
    assert only_issue(document).code == "E100"


# --- experiments (spec 1 "Experiments") -----------------------------------------------------


def experiment_of(experiment: dict[str, Any], **parameters: Any) -> Experiment:
    document = coffee()
    document["experiments"] = [experiment]
    document["parameters"].update(parameters)
    return model_of(document).experiments[0]


def test_every_experiment_default() -> None:
    chosen: list[int] = []

    def seed() -> int:
        chosen.append(424242)
        return 424242

    document = coffee()
    document["experiments"] = [{"id": "plain", "length": "2 d"}]
    result = load_document(document, seed_source=seed)
    assert result.model is not None
    experiment = result.model.experiments[0]
    assert experiment.length == Quantity(172_800.0, TIME)
    assert experiment.warmup == Quantity(0.0, TIME)
    assert experiment.replications == 30
    assert experiment.seed == 424242
    assert experiment.seed_chosen is True
    assert chosen == [424242]
    assert experiment.scenarios == (Scenario(id="default", set={}),)
    assert experiment.confidence == 0.95
    assert experiment.record_interval == Quantity(172_800.0 / 200, TIME)
    assert experiment.search is None


def test_the_default_seed_is_random_and_in_range() -> None:
    document = coffee()
    del document["experiments"][0]["seed"]
    seeds = set()
    for _ in range(5):
        model = load_model_text(json.dumps(document))
        experiment = model.experiments[0]
        assert experiment.seed_chosen is True
        assert 0 <= experiment.seed < 2**63
        seeds.add(experiment.seed)
    assert len(seeds) > 1


def load_model_text(text: str) -> Model:
    result = load_text(text)
    assert result.model is not None, result.issues
    return result.model


def test_given_experiment_fields_are_kept() -> None:
    experiment = experiment_of(
        {
            "id": "full",
            "length": "10 h",
            "warmup": "30 min",
            "replications": 5,
            "seed": -3,
            "confidence": 0.9,
            "record_interval": "6 min",
            "scenarios": [{"id": "two", "set": {"tills": 2}}],
        }
    )
    assert experiment.length == hours(10)
    assert experiment.warmup == minutes(30)
    assert experiment.replications == 5
    assert experiment.seed == -3
    assert experiment.seed_chosen is False
    assert experiment.confidence == 0.9
    assert experiment.record_interval == minutes(6)
    assert experiment.scenarios == (Scenario(id="two", set={"tills": 2}),)


def test_an_empty_scenario_list_gets_the_default_scenario() -> None:
    experiment = experiment_of({"id": "e", "length": "1 h", "scenarios": []})
    assert experiment.scenarios == (Scenario(id="default", set={}),)


def test_scenario_values_follow_the_parameter_type() -> None:
    experiment = experiment_of(
        {
            "id": "e",
            "length": "1 h",
            "scenarios": [{"id": "s", "set": {"tills": 2.0, "rate": 0.5, "gap": "3 min"}}],
        },
        rate={"value": 1, "type": "number"},
        gap={"value": "2 min", "type": "quantity"},
    )
    (scenario,) = experiment.scenarios
    assert scenario.set == {"tills": 2, "rate": 0.5, "gap": minutes(3)}
    assert isinstance(scenario.set["tills"], int)


def test_whole_number_floats_count_as_integers() -> None:
    experiment = experiment_of({"id": "e", "length": "1 h", "replications": 4.0, "seed": 9.0})
    assert experiment.replications == 4
    assert isinstance(experiment.replications, int)
    assert isinstance(experiment.seed, int)


def test_search_defaults() -> None:
    experiment = experiment_of(
        {"id": "e", "length": "1 h", "search": {"objective": "wait"}},
        rate={"value": 1, "type": "number", "min": 0},
        gap={"value": "2 min", "type": "quantity", "min": "1 min", "max": "5 min"},
    )
    # `variables` defaults to every parameter with both `min` and `max`, in file order.
    assert experiment.search == Search(
        objective="wait", budget=50, variables=("tills", "gap"), replications=10
    )


def test_search_given() -> None:
    experiment = experiment_of(
        {
            "id": "e",
            "length": "1 h",
            "search": {"objective": "o", "budget": 3, "variables": ["tills"], "replications": 4},
        }
    )
    assert experiment.search == Search(
        objective="o", budget=3, variables=("tills",), replications=4
    )


# --- parameters (spec 1 "Parameters") -------------------------------------------------------


def test_parameters_of_each_type() -> None:
    document = coffee()
    document["parameters"] = {
        "tills": {"value": 2.0, "type": "integer", "min": 1, "max": 5},
        "rate": {"value": 0.5, "type": "number", "description": "share"},
        "gap": {"value": "2 min", "type": "quantity", "min": "1 min", "max": "1 h"},
    }
    parameters = model_of(document).parameters
    assert parameters["tills"] == Parameter("tills", "integer", 2, 1, 5, None)
    assert isinstance(parameters["tills"].value, int)
    assert parameters["rate"] == Parameter("rate", "number", 0.5, None, None, "share")
    assert parameters["gap"] == Parameter("gap", "quantity", minutes(2), minutes(1), hours(1), None)


@pytest.mark.parametrize(
    ("entry", "key", "code"),
    [
        ({"value": 1, "type": "int"}, "type", "E123"),
        ({"value": 1, "type": 3}, "type", "E123"),
        ({"value": 1.5, "type": "integer"}, "value", "E123"),
        ({"value": "2 min", "type": "number"}, "value", "E123"),
        ({"value": 2, "type": "quantity"}, "value", "E123"),
        ({"value": "2 m", "type": "quantity"}, "value", "E140"),
        ({"value": "2min", "type": "quantity"}, "value", "E141"),
        ({"value": 1, "type": "integer", "min": "a"}, "min", "E123"),
        ({"value": 1, "type": "integer", "max": True}, "max", "E123"),
    ],
)
def test_parameter_value_errors(entry: dict[str, Any], key: str, code: str) -> None:
    document = coffee()
    document["parameters"]["p"] = entry
    issue = only_issue(document)
    assert issue.code == code
    assert issue.path == f"/parameters/p/{key}"
    assert issue.component is None
    assert "'p'" in issue.message
    assert f"'{key}'" in issue.message


# --- settings: numbers, quantities, $param (spec 1 "Quantities", "Parameters") -----------


def test_param_reference_is_accepted_where_a_number_or_quantity_is_taken() -> None:
    document = with_component(
        {
            "id": "line",
            "type": "source",
            "params": {
                "interarrival": {"dist": "uniform", "min": {"$param": "lo"}, "max": "3 min"},
                "first_arrival": {"$param": "gap"},
                "max_items": {"$param": "tills"},
            },
        }
    )
    document["parameters"]["lo"] = {"value": "1 min", "type": "quantity"}
    document["parameters"]["gap"] = {"value": "5 min", "type": "quantity"}
    line = model_of(document).components[-1]
    assert line.settings == {
        "interarrival": Distribution("uniform", {"min": ParamRef("lo"), "max": minutes(3)}),
        "first_arrival": ParamRef("gap"),
        "max_items": ParamRef("tills"),
    }


def test_param_reference_in_object_settings() -> None:
    document = with_component(
        {
            "id": "split",
            "type": "branch",
            "params": {
                "routes": ["a", "b"],
                "rule": "probability",
                "weights": {"a": {"$param": "share"}, "b": 1},
            },
        }
    )
    document["parameters"]["share"] = {"value": 0.5, "type": "number"}
    split = model_of(document).components[-1]
    assert split.settings["weights"] == {"a": ParamRef("share"), "b": 1}


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ({"$param": 5}, "E123"),  # not a reference: the id is not text
        ({"$param": "tills", "x": 1}, "E123"),  # not a reference: another key
        ("2 min", "E123"),
        (2.5, "E123"),  # capacity takes a whole number
        (True, "E123"),
    ],
)
def test_number_setting_errors(value: object, code: str) -> None:
    document = coffee()
    document["components"][1]["params"]["capacity"] = value
    issue = only_issue(document)
    assert issue.code == code
    assert issue.path == "/components/1/params/capacity"
    assert issue.component == "till"
    assert "'till'" in issue.message
    assert "'capacity'" in issue.message


@pytest.mark.parametrize(
    ("value", "code"),
    [("5 m", "E140"), ("2min", "E141"), (5, "E123"), (None, "E141"), ({"$param": 1}, "E141")],
)
def test_quantity_setting_errors(value: object, code: str) -> None:
    document = coffee()
    document["components"][0]["params"]["first_arrival"] = value
    issue = only_issue(document)
    assert issue.code == code
    assert issue.path == "/components/0/params/first_arrival"
    assert issue.component == "arrivals"
    assert "'arrivals'" in issue.message
    assert "'first_arrival'" in issue.message


# --- distributions (spec 1 "Distributions") -------------------------------------------------


def distribution_of(raw: dict[str, Any]) -> Distribution:
    document = coffee()
    document["components"][1]["params"]["service"] = raw
    value = model_of(document).components[1].settings["service"]
    assert isinstance(value, Distribution)
    return value


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"dist": "constant", "value": "1 h"}, Distribution("constant", {"value": hours(1)})),
        (
            {"dist": "exponential", "mean": "90 s"},
            Distribution("exponential", {"mean": Quantity(90.0, TIME)}),
        ),
        (
            {"dist": "uniform", "min": "1 min", "max": "2 min"},
            Distribution("uniform", {"min": minutes(1), "max": minutes(2)}),
        ),
        (
            {"dist": "triangular", "min": "1 min", "mode": "2 min", "max": "4 min"},
            Distribution("triangular", {"min": minutes(1), "mode": minutes(2), "max": minutes(4)}),
        ),
        (
            {"dist": "normal", "mean": "10 min", "sd": "1 min"},
            Distribution("normal", {"mean": minutes(10), "sd": minutes(1)}),
        ),
        (
            {"dist": "lognormal", "mean": "10 min", "sd": "1 min"},
            Distribution("lognormal", {"mean": minutes(10), "sd": minutes(1)}),
        ),
        (
            {"dist": "weibull", "shape": 1.5, "scale": "1 h"},
            Distribution("weibull", {"shape": 1.5, "scale": hours(1)}),
        ),
        (
            {"dist": "empirical", "values": ["1 min", "2 min", {"$param": "gap"}]},
            Distribution("empirical", {}, values=(minutes(1), minutes(2), ParamRef("gap"))),
        ),
        (
            {"dist": "empirical", "data": {"file": "times.csv", "column": "repair"}},
            Distribution("empirical", {}, data=DataRef(file="times.csv", column="repair")),
        ),
    ],
)
def test_each_distribution_loads(raw: dict[str, Any], expected: Distribution) -> None:
    assert distribution_of(raw) == expected


@pytest.mark.parametrize(
    ("raw", "key", "code"),
    [
        ("2 min", None, "E160"),
        ({"mean": "2 min"}, "dist", "E160"),
        ({"dist": "gamma", "mean": "2 min"}, "dist", "E160"),
        ({"dist": 3, "mean": "2 min"}, "dist", "E160"),
        ({"dist": "exponential"}, "mean", "E160"),
        ({"dist": "exponential", "mean": "2 min", "rate": 3}, "rate", "E160"),
        ({"dist": "empirical"}, "values", "E160"),
        (
            {"dist": "empirical", "values": ["1 min"], "data": {"file": "f", "column": "c"}},
            "data",
            "E160",
        ),
        ({"dist": "empirical", "values": "1 min"}, "values", "E160"),
        ({"dist": "empirical", "data": {"file": "f"}}, "data", "E160"),
        ({"dist": "empirical", "data": {"file": "f", "column": 3}}, "data", "E160"),
        ({"dist": "empirical", "data": "f.csv"}, "data", "E160"),
        ({"dist": "exponential", "mean": "2 m"}, "mean", "E140"),
        ({"dist": "exponential", "mean": 2}, "mean", "E123"),
        ({"dist": "weibull", "shape": "2 min", "scale": "1 h"}, "shape", "E123"),
        ({"dist": "empirical", "values": ["1 min", "x"]}, "values/1", "E141"),
    ],
)
def test_distribution_errors(raw: object, key: str | None, code: str) -> None:
    document = coffee()
    document["components"][1]["params"]["service"] = raw
    issue = only_issue(document)
    assert issue.code == code
    base = "/components/1/params/service"
    assert issue.path == (base if key is None else f"{base}/{key}")
    assert issue.component == "till"
    assert "'till'" in issue.message
    assert "'service'" in issue.message
    if key is not None:
        assert f"'{key.split('/')[0]}'" in issue.message


def test_empty_values_load_and_are_left_to_the_meaning_pass() -> None:
    # Spec 1 E160 "empty `values`" is a meaning-pass check (AKS-90), not a loading error.
    assert distribution_of({"dist": "empirical", "values": []}) == Distribution(
        "empirical", {}, values=()
    )


# --- component types and settings (spec 2 "Block reference") ------------------------------


def test_every_block_type_loads() -> None:
    document = coffee()
    document["components"] += [
        {"id": "wait", "type": "delay", "params": {"time": {"dist": "constant", "value": "1 s"}}},
        {
            "id": "split",
            "type": "branch",
            "params": {"routes": ["a", "b"], "rule": "shortest_queue"},
        },
        {
            "id": "buffer",
            "type": "queue",
            "params": {"capacity": 2, "discipline": "lifo", "on_full": "discard"},
        },
        {"id": "group", "type": "batch", "params": {"size": 5, "timeout": "10 min"}},
        {"id": "ungroup", "type": "unbatch", "params": {}},
        {
            "id": "stock",
            "type": "store",
            "params": {
                "initial": 100,
                "reorder_point": 30,
                "order_quantity": 100,
                "lead_time": {"dist": "constant", "value": "123 min"},
            },
        },
        {"id": "staff", "type": "resource_pool", "params": {"capacity": 1}},
        {
            "id": "shifts",
            "type": "schedule",
            "params": {
                "target": "till",
                "shifts": [{"start": "0 h", "end": "8 h", "capacity": 1}],
                "period": "1 d",
            },
        },
        {
            "id": "breakdown",
            "type": "failure",
            "params": {
                "target": "till",
                "time_to_failure": {"dist": "exponential", "mean": "100 min"},
                "time_to_repair": {"dist": "exponential", "mean": "25 min"},
            },
        },
    ]
    document["components"][1]["params"].update(
        {"queue_capacity": 0, "discipline": "fifo", "pool": "staff"}
    )
    model = model_of(document)
    by_id = {component.id: component for component in model.components}
    assert by_id["till"].settings["pool"] == "staff"
    assert by_id["till"].settings["queue_capacity"] == 0
    assert by_id["split"].settings == {"routes": ("a", "b"), "rule": "shortest_queue"}
    assert by_id["buffer"].settings == {"capacity": 2, "discipline": "lifo", "on_full": "discard"}
    assert by_id["group"].settings == {"size": 5, "timeout": minutes(10)}
    assert by_id["ungroup"].settings == {}
    assert by_id["stock"].settings["lead_time"] == Distribution("constant", {"value": minutes(123)})
    assert by_id["staff"].settings == {"capacity": 1}
    assert by_id["shifts"].settings == {
        "target": "till",
        "shifts": ({"start": hours(0), "end": hours(8), "capacity": 1},),
        "period": hours(24),
    }
    assert by_id["breakdown"].settings["time_to_repair"] == Distribution(
        "exponential", {"mean": minutes(25)}
    )
    assert [component.type for component in model.components][3:] == [
        "delay",
        "branch",
        "queue",
        "batch",
        "unbatch",
        "store",
        "resource_pool",
        "schedule",
        "failure",
    ]


def test_label_and_ui_are_kept() -> None:
    document = coffee()
    document["components"][2]["label"] = "Exit door"
    document["components"][2]["ui"] = {"x": 10, "y": [1, 2]}
    exit_ = model_of(document).components[2]
    assert exit_.label == "Exit door"
    assert exit_.ui == {"x": 10, "y": [1, 2]}


def test_unknown_component_type() -> None:
    issue = only_issue(with_component({"id": "robot", "type": "robot", "params": {"x": 1}}))
    assert issue.code == "E120"
    assert issue.path == "/components/3/type"
    assert issue.component == "robot"
    assert "'robot'" in issue.message


def test_unknown_setting() -> None:
    document = coffee()
    document["components"][2]["params"]["speed"] = 3
    issue = only_issue(document)
    assert issue.code == "E121"
    assert issue.path == "/components/2/params/speed"
    assert issue.component == "exit"
    assert "'speed'" in issue.message
    assert "'exit'" in issue.message


def test_missing_required_setting() -> None:
    document = coffee()
    del document["components"][1]["params"]["service"]
    issue = only_issue(document)
    assert issue.code == "E122"
    assert issue.path == "/components/1/params/service"
    assert issue.component == "till"
    assert "'service'" in issue.message
    assert "'till'" in issue.message


def test_weights_are_required_for_the_probability_rule_only() -> None:
    issue = only_issue(
        with_component(
            {"id": "split", "type": "branch", "params": {"routes": ["a"], "rule": "probability"}}
        )
    )
    assert issue.code == "E122"
    assert issue.path == "/components/3/params/weights"
    assert "'weights'" in issue.message
    settings_of(
        {"id": "split", "type": "branch", "params": {"routes": ["a"], "rule": "shortest_queue"}}
    )


@pytest.mark.parametrize(
    ("component", "key", "code"),
    [
        (
            {
                "type": "server",
                "params": {
                    "capacity": 1,
                    "service": {"dist": "constant", "value": "1 s"},
                    "discipline": "priority",
                },
            },
            "discipline",
            "E123",
        ),
        (
            {
                "type": "server",
                "params": {
                    "capacity": 1,
                    "service": {"dist": "constant", "value": "1 s"},
                    "pool": 3,
                },
            },
            "pool",
            "E123",
        ),
        ({"type": "branch", "params": {"routes": "a", "rule": "shortest_queue"}}, "routes", "E123"),
        (
            {"type": "branch", "params": {"routes": ["a", 2], "rule": "shortest_queue"}},
            "routes/1",
            "E123",
        ),
        (
            {"type": "branch", "params": {"routes": ["a"], "rule": "probability", "weights": [1]}},
            "weights",
            "E123",
        ),
        (
            {
                "type": "branch",
                "params": {"routes": ["a"], "rule": "probability", "weights": {"a": "1 s"}},
            },
            "weights/a",
            "E123",
        ),
        (
            {"type": "schedule", "params": {"target": "till", "shifts": {"start": "0 h"}}},
            "shifts",
            "E123",
        ),
        ({"type": "schedule", "params": {"target": "till", "shifts": [3]}}, "shifts/0", "E123"),
        (
            {
                "type": "schedule",
                "params": {"target": "till", "shifts": [{"start": "0 h", "end": "8 h"}]},
            },
            "shifts/0/capacity",
            "E122",
        ),
        (
            {
                "type": "schedule",
                "params": {
                    "target": "till",
                    "shifts": [{"start": "0 h", "end": "8 h", "capacity": 1, "x": 1}],
                },
            },
            "shifts/0/x",
            "E121",
        ),
        (
            {
                "type": "schedule",
                "params": {
                    "target": "till",
                    "shifts": [{"start": "0 m", "end": "8 h", "capacity": 1}],
                },
            },
            "shifts/0/start",
            "E140",
        ),
        ({"type": "queue", "params": {"capacity": 1, "on_full": "drop"}}, "on_full", "E123"),
    ],
)
def test_setting_shape_errors(component: dict[str, Any], key: str, code: str) -> None:
    issue = only_issue(with_component({"id": "extra", **component}))
    assert issue.code == code
    assert issue.path == f"/components/3/params/{key}"
    assert issue.component == "extra"
    assert "'extra'" in issue.message
    assert f"'{key.split('/')[0]}'" in issue.message


def test_several_issues_are_all_reported_in_document_order() -> None:
    document = coffee()
    document["components"][0]["params"]["interarrival"]["mean"] = "2 m"
    document["components"][1]["params"]["speed"] = 1
    document["experiments"][0]["length"] = "200"
    result = load_document(document)
    assert result.model is None
    assert [(issue.code, issue.path) for issue in result.issues] == [
        ("E140", "/components/0/params/interarrival/mean"),
        ("E121", "/components/1/params/speed"),
        ("E141", "/experiments/0/length"),
    ]


# --- connections ------------------------------------------------------------------------------


@pytest.mark.parametrize("endpoint", ["arrivals", ".out", "arrivals.", ""])
def test_a_connection_end_without_component_and_port(endpoint: str) -> None:
    document = coffee()
    document["connections"][0]["from"] = endpoint
    issue = only_issue(document)
    assert issue.code == "E130"
    assert issue.path == "/connections/0/from"
    assert "'from'" in issue.message


def test_a_connection_end_splits_at_the_first_dot() -> None:
    document = coffee()
    document["connections"][0]["to"] = "till.in.extra"
    model = model_of(document)
    assert model.connections[0].destination == Endpoint("till", "in.extra")


# --- experiments, objectives and constraints: value errors ---------------------------------


@pytest.mark.parametrize(
    ("change", "path", "code"),
    [
        ({"length": 200}, "/experiments/0/length", "E123"),
        ({"length": "200 m"}, "/experiments/0/length", "E140"),
        ({"warmup": "x"}, "/experiments/0/warmup", "E141"),
        ({"replications": "30"}, "/experiments/0/replications", "E123"),
        ({"replications": 2.5}, "/experiments/0/replications", "E123"),
        ({"seed": 1.5}, "/experiments/0/seed", "E123"),
        ({"seed": None}, "/experiments/0/seed", "E123"),
        ({"confidence": "95%"}, "/experiments/0/confidence", "E123"),
        ({"record_interval": 3}, "/experiments/0/record_interval", "E123"),
        (
            {"scenarios": [{"id": "s", "set": {"tills": "2 min"}}]},
            "/experiments/0/scenarios/0/set/tills",
            "E123",
        ),
        (
            {"scenarios": [{"id": "s", "set": {"nobody": 2}}]},
            "/experiments/0/scenarios/0/set/nobody",
            "E150",
        ),
        ({"search": {"objective": "o", "budget": 1.5}}, "/experiments/0/search/budget", "E123"),
        (
            {"search": {"objective": "o", "replications": "x"}},
            "/experiments/0/search/replications",
            "E123",
        ),
    ],
)
def test_experiment_value_errors(change: dict[str, Any], path: str, code: str) -> None:
    document = coffee()
    document["experiments"][0].update(change)
    issue = only_issue(document)
    assert issue.code == code
    assert issue.path == path
    assert issue.component is None
    assert "'base'" in issue.message
    key = path.split("/")[-1]
    assert f"'{key}'" in issue.message


def test_a_scenario_naming_a_parameter_with_a_bad_type_is_not_reported_twice() -> None:
    document = coffee()
    document["parameters"]["tills"]["type"] = "int"
    document["experiments"][0]["scenarios"] = [{"id": "s", "set": {"tills": 2}}]
    issue = only_issue(document)
    assert issue.path == "/parameters/tills/type"


def test_metric_objectives_and_constraints() -> None:
    document = coffee()
    document["objectives"] = [{"id": "wait", "metric": "till.wait.mean", "sense": "minimize"}]
    document["constraints"] = [
        {"id": "util", "metric": "till.utilization", "op": ">=", "value": 0.35},
        {"id": "short", "metric": "till.wait.mean", "op": "<=", "value": "5 min"},
    ]
    model = model_of(document)
    assert model.objectives == (
        MetricObjective(id="wait", metric="till.wait.mean", sense="minimize"),
    )
    assert model.constraints == (
        MetricConstraint(id="util", metric="till.utilization", op=">=", value=0.35),
        MetricConstraint(id="short", metric="till.wait.mean", op="<=", value=minutes(5)),
    )


@pytest.mark.parametrize(
    ("key", "entry", "path", "code"),
    [
        (
            "objectives",
            {"id": "o", "metric": "till.wait.mean", "sense": "least"},
            "/objectives/0/sense",
            "E123",
        ),
        (
            "constraints",
            {"id": "c", "metric": "till.utilization", "op": "<", "value": 1},
            "/constraints/0/op",
            "E123",
        ),
        (
            "constraints",
            {"id": "c", "metric": "till.utilization", "op": "==", "value": 1},
            "/constraints/0/op",
            "E123",
        ),
        (
            "constraints",
            {"id": "c", "metric": "till.utilization", "op": "<=", "value": True},
            "/constraints/0/value",
            "E141",
        ),
        (
            "constraints",
            {"id": "c", "metric": "till.wait.mean", "op": "<=", "value": "5 m"},
            "/constraints/0/value",
            "E140",
        ),
    ],
)
def test_objective_and_constraint_errors(
    key: str, entry: dict[str, Any], path: str, code: str
) -> None:
    document = coffee()
    document[key] = [entry]
    issue = only_issue(document)
    assert issue.code == code
    assert issue.path == path
    assert f"'{entry['id']}'" in issue.message
    assert f"'{path.split('/')[-1]}'" in issue.message


def test_run_settings_are_kept_as_written() -> None:
    # Spec 1 "Run targets": a file naming `remote` or `cluster` still loads; E172 and E173
    # are run codes, raised when a run starts, not by loading.
    document = coffee()
    document["run"] = {"target": "cluster", "fidelity": 5, "engine": "simpy"}
    assert model_of(document).run == RunSettings(target="cluster", fidelity=5, engine="simpy")


# --- the optimization domain (spec 2 "Mathematical optimization in the model file") -------


def test_product_mix_loads() -> None:
    model = model_of(copy.deepcopy(PRODUCT_MIX))
    assert model.domain == "optimization"
    assert model.components == ()
    assert model.experiments == ()
    assert model.program == LinearProgram(
        variables=(
            Variable(id="chairs", type="continuous", lower=0, upper=None),
            Variable(id="tables", type="continuous", lower=0, upper=None),
        ),
        objective=LinearObjective(sense="maximize", linear={"chairs": 45, "tables": 80}),
        constraints=(
            LinearConstraint(id="wood", linear={"chairs": 5, "tables": 20}, op="<=", rhs=400),
            LinearConstraint(id="labour", linear={"chairs": 10, "tables": 15}, op="<=", rhs=450),
        ),
    )
    assert model.run == RunSettings(target="local", fidelity="standard", engine=None)


def test_optimization_variable_types_and_equality() -> None:
    document = copy.deepcopy(PRODUCT_MIX)
    document["variables"] = [
        {"id": "a", "type": "binary"},
        {"id": "b", "type": "integer", "lower": -1, "upper": 4.5},
    ]
    document["objective"] = {"sense": "minimize", "linear": {"a": 1, "b": 2}}
    document["constraints"] = [{"id": "one", "linear": {"a": 1, "b": 1}, "op": "==", "rhs": 1}]
    program = model_of(document).program
    assert program is not None
    assert program.variables == (
        Variable("a", "binary", None, None),
        Variable("b", "integer", -1, 4.5),
    )
    assert program.constraints[0].op == "=="
    assert program.objective.sense == "minimize"


@pytest.mark.parametrize(
    ("change", "path", "code"),
    [
        ({"variables": [{"id": "x", "type": "real"}]}, "/variables/0/type", "E123"),
        (
            {"variables": [{"id": "x", "type": "continuous", "lower": "0"}]},
            "/variables/0/lower",
            "E123",
        ),
        (
            {"variables": [{"id": "x", "type": "continuous", "upper": None}]},
            "/variables/0/upper",
            "E123",
        ),
        ({"objective": {"sense": "max", "linear": {}}}, "/objective/sense", "E123"),
        (
            {"objective": {"sense": "maximize", "linear": {"chairs": "45"}}},
            "/objective/linear/chairs",
            "E123",
        ),
        (
            {"constraints": [{"id": "c", "linear": {"chairs": 1}, "op": "=", "rhs": 1}]},
            "/constraints/0/op",
            "E123",
        ),
        (
            {"constraints": [{"id": "c", "linear": {"chairs": []}, "op": "<=", "rhs": 1}]},
            "/constraints/0/linear/chairs",
            "E123",
        ),
        (
            {"constraints": [{"id": "c", "linear": {}, "op": "<=", "rhs": "1 h"}]},
            "/constraints/0/rhs",
            "E123",
        ),
    ],
)
def test_optimization_value_errors(change: dict[str, Any], path: str, code: str) -> None:
    document = copy.deepcopy(PRODUCT_MIX)
    document.update(change)
    issue = only_issue(document)
    assert issue.code == code
    assert issue.path == path
    assert issue.component is None
    assert f"'{path.split('/')[-1]}'" in issue.message


def test_optimization_parameters_load() -> None:
    document = copy.deepcopy(PRODUCT_MIX)
    document["parameters"] = {"wood": {"value": 400, "type": "number"}}
    assert model_of(document).parameters["wood"].value == 400


# --- domains (spec 1 "Top-level keys") ------------------------------------------------------


def test_an_unknown_domain_is_e102() -> None:
    document = {"format_version": "0.1", "meta": {"name": "x"}, "domain": "physics"}
    issue = only_issue(document)
    assert issue.code == "E102"
    assert issue.path == "/domain"
    assert "'physics'" in issue.message
    assert "'domain'" in issue.message


# --- reading text and files ------------------------------------------------------------------


def test_load_text_accepts_str_and_bytes() -> None:
    text = COFFEE_SHOP_PATH.read_text(encoding="utf-8")
    for given in (text, text.encode("utf-8"), b"\xef\xbb\xbf" + text.encode("utf-8")):
        result = load_text(given, seed_source=lambda: 1)
        assert isinstance(result, LoadResult)
        assert result.issues == ()
        assert result.model == model_of(coffee())


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("{", "not valid JSON"),
        ("", "not valid JSON"),
        ('{"a": NaN}', "'NaN'"),
        ('{"a": Infinity}', "'Infinity'"),
        ('{"a": -Infinity}', "'-Infinity'"),
        (b"\xff\xfe{}", "UTF-8"),
        ("[" * 200_000 + "]" * 200_000, "nested too deeply"),
        ('{"a": ' + "9" * 5000 + "}", "too many digits"),
    ],
)
def test_text_that_is_not_json(text: str | bytes, fragment: str) -> None:
    result = load_text(text)
    assert result.model is None
    (issue,) = result.issues
    assert issue.code == "E100"
    assert issue.path == ""
    assert fragment in issue.message
    assert "Error" not in issue.message
    assert "Traceback" not in issue.message


def test_a_syntax_error_names_line_and_column() -> None:
    issue = load_text('{\n  "a": 1\n  "b": 2\n}').issues[0]
    assert "line 3" in issue.message
    assert "column 3" in issue.message


def test_a_duplicate_key_is_e100_at_that_key() -> None:
    text = COFFEE_SHOP_PATH.read_text(encoding="utf-8").replace(
        '"tills": {"value": 1,', '"tills": {"value": 1, "value": 2,'
    )
    result = load_text(text)
    assert result.model is None
    (issue,) = result.issues
    assert issue.code == "E100"
    assert issue.path == "/parameters/tills/value"
    assert "'value'" in issue.message


def test_duplicate_keys_in_arrays_and_at_top_level() -> None:
    result = load_text('{"meta": 1, "meta": 2, "x": [{"k": 1, "k": 2}]}')
    assert [(issue.code, issue.path) for issue in result.issues] == [
        ("E100", "/meta"),
        ("E100", "/x/0/k"),
    ]


def test_a_non_object_file_is_a_schema_issue() -> None:
    result = load_text("[1, 2]")
    assert result.model is None
    assert [issue.code for issue in result.issues] == ["E100"]


def test_load_model_raises_with_the_issues(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    document = coffee()
    document["components"][1]["params"]["speed"] = 1
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ModelLoadError) as caught:
        load_model(path)
    assert [issue.code for issue in caught.value.issues] == ["E121"]
    assert "E121" in str(caught.value)


def test_load_model_accepts_a_string_path_and_a_seed_source(tmp_path: Path) -> None:
    path = tmp_path / "m.json"
    document = coffee()
    del document["experiments"][0]["seed"]
    path.write_text(json.dumps(document), encoding="utf-8")
    model = load_model(str(path), seed_source=lambda: 99)
    assert model.experiments[0].seed == 99


def test_load_model_lets_a_missing_file_raise(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_model(tmp_path / "absent.json")


def test_load_result_errors_and_warnings() -> None:
    error = Issue("E121", "till", "/components/1/params/x", "m", "h")
    warning = Issue("W202", "till", "/components/1/params/service", "m", "h")
    result = LoadResult(model=None, issues=(error, warning))
    assert result.errors == (error,)
    assert result.warnings == (warning,)


def test_a_replaced_object_with_duplicates_is_not_reported() -> None:
    # The first "x" (with its own duplicate "k") is replaced by the second "x"; only the
    # duplicate "x" is in the document.
    result = load_text('{"x": {"k": 1, "k": 2}, "x": 5, "y": [{}, {}, {}]}')
    assert [(issue.code, issue.path) for issue in result.issues] == [("E100", "/x")]


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        (None, "null"),
        (True, "true"),
        (False, "false"),
        (10**30, "a very large whole number"),
        (7, "7"),
        (1.5, "1.5"),
        ([1], "an array"),
        ({"a": 1}, "an object"),
        ("lilo", "'lilo'"),
    ],
)
def test_a_wrong_word_is_quoted_plainly(value: object, shown: str) -> None:
    document = coffee()
    document["components"][1]["params"]["discipline"] = value
    issue = only_issue(document)
    assert issue.code == "E123"
    assert f", {shown} is not allowed" in issue.message
    assert "'fifo' or 'lifo'" in issue.message


def test_loading_does_not_change_the_document() -> None:
    document = coffee()
    document["experiments"].append({"id": "plain", "length": "1 h"})
    before = copy.deepcopy(document)
    model_of(document)
    assert document == before


def test_a_deeply_nested_ui_loads() -> None:
    nested: dict[str, Any] = {}
    for _ in range(20_000):
        nested = {"n": nested}
    document = coffee()
    document["components"][0]["ui"] = nested
    model = model_of(document)
    assert model.components[0].ui == nested


def test_seed_limit_fits_a_signed_64_bit_integer() -> None:
    assert SEED_LIMIT == 2**63
