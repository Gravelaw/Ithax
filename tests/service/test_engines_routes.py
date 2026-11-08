"""``GET /v1/engines``, ``GET /v1/schema`` and ``GET /v1/schema/components/{type}``
(spec 3 "Endpoints"; spec 1 "Engine adapter interface"; AKS-110)."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from starlette.testclient import TestClient

from lcsim.engines.registry import installed_adapters
from lcsim.model.catalogue import PROCESS_TYPES, SettingKind, SettingSpec
from lcsim.model.schema import model_schema
from lcsim.model.units import Dimension, Quantity
from lcsim.service.engines import (
    COMPONENT_TYPES_KEY,
    composed_schema,
    describe_component,
    describe_engine,
    describe_setting,
)
from service.service_support import assert_error

EXAMPLES = sorted((Path(__file__).resolve().parents[2] / "examples").glob("*.json"))


def test_engines_lists_the_installed_adapters(client: TestClient) -> None:
    response = client.get("/v1/engines")
    assert response.status_code == 200
    engines = response.json()
    assert [engine["name"] for engine in engines] == ["highs", "simpy"]
    simpy = engines[1]
    assert simpy == {
        "name": "simpy",
        "version": installed_adapters()["simpy"].version,
        "domains": ["process"],
        "component_types": list(PROCESS_TYPES),
        "hardware": [],
        "parallel_modes": ["replications"],
        "licence": "MIT",
        "invocation": "in-process",
    }
    assert engines[0]["domains"] == ["optimization"]
    assert engines[0]["component_types"] == []
    assert engines[0] == describe_engine(installed_adapters()["highs"])


def test_the_schema_is_spec_1s_with_the_component_types(client: TestClient) -> None:
    schema = client.get("/v1/schema").json()
    static = model_schema()
    types = schema.pop(COMPONENT_TYPES_KEY)
    assert schema == static
    assert list(types) == list(PROCESS_TYPES)
    assert types["server"] == client.get("/v1/schema/components/server").json()


def test_the_composed_schema_is_a_valid_schema_that_accepts_what_spec_1s_accepts() -> None:
    schema = composed_schema(installed_adapters())
    Draft202012Validator.check_schema(schema)
    composed = Draft202012Validator(schema)
    static = Draft202012Validator(model_schema())
    assert EXAMPLES
    for example in EXAMPLES:
        document = json.loads(example.read_text(encoding="utf-8"))
        assert list(composed.iter_errors(document)) == []
    broken = {"format_version": "0.1", "domain": "process", "extra": 1}
    assert len(list(composed.iter_errors(broken))) == len(list(static.iter_errors(broken)))


@pytest.mark.parametrize("type_name", list(PROCESS_TYPES))
def test_every_process_type_is_described(client: TestClient, type_name: str) -> None:
    response = client.get(f"/v1/schema/components/{type_name}")
    assert response.status_code == 200
    described = response.json()
    block = PROCESS_TYPES[type_name]
    assert described["type"] == type_name
    assert described["domain"] == "process"
    assert described["engine"] == "simpy"
    assert described["description"] == block.description
    assert described["description"].endswith(".")
    assert described["inputs"] == list(block.inputs)
    assert described["outputs"] == list(block.outputs)
    assert described["outputs_from"] == block.outputs_from
    assert [setting["name"] for setting in described["settings"]] == [
        spec.name for spec in block.settings
    ]
    assert described["metrics"] == list(block.metrics)


def test_a_server_is_described_in_full(client: TestClient) -> None:
    server = client.get("/v1/schema/components/server").json()
    assert server["settings"] == [
        {"name": "capacity", "kind": "number", "required": True, "integer": True, "minimum": 1},
        {"name": "service", "kind": "distribution", "required": True, "dimension": "time"},
        {
            "name": "queue_capacity",
            "kind": "number",
            "required": False,
            "integer": True,
            "minimum": 0,
        },
        {
            "name": "discipline",
            "kind": "identifier",
            "required": False,
            "choices": ["fifo", "lifo"],
            "default": "fifo",
        },
        {"name": "pool", "kind": "identifier", "required": False, "refers_to": ["resource_pool"]},
    ]
    assert server["inputs"] == ["in"]
    assert server["outputs"] == ["out"]
    assert server["outputs_from"] is None


def test_nested_and_quantity_settings_are_described(client: TestClient) -> None:
    schedule = {
        s["name"]: s for s in client.get("/v1/schema/components/schedule").json()["settings"]
    }
    assert schedule["period"]["default"] == "86400 s"
    assert schedule["period"]["exclusive_minimum"] is True
    assert [field["name"] for field in schedule["shifts"]["fields"]] == ["start", "end", "capacity"]
    assert schedule["shifts"]["many"] is True
    branch = {s["name"]: s for s in client.get("/v1/schema/components/branch").json()["settings"]}
    assert branch["weights"]["keyed_by"] == "routes"
    assert branch["weights"]["values"]["name"] == "weight"
    assert branch["weights"]["required_when"] == ["rule", "probability"]
    assert branch["routes"]["min_items"] == 1
    assert client.get("/v1/schema/components/branch").json()["outputs_from"] == "routes"


def test_a_fractional_quantity_default_keeps_its_digits() -> None:
    spec = SettingSpec(
        "wait",
        SettingKind.QUANTITY,
        False,
        dimension=Dimension.TIME,
        default=Quantity(1.5, Dimension.TIME),
    )
    assert describe_setting(spec)["default"] == "1.5 s"


def test_an_unknown_component_type_is_404_with_e185(client: TestClient) -> None:
    response = client.get("/v1/schema/components/conveyor")
    assert response.status_code == 404
    assert_error(response.json(), "E185")
    assert "'conveyor'" in response.json()["error"]["message"]


def test_describe_component_names_its_engine_and_domain() -> None:
    described = describe_component("sink", PROCESS_TYPES["sink"], "simpy", "process")
    assert described["engine"] == "simpy"
    assert described["settings"] == []


def test_a_type_two_adapters_declare_is_described_once_by_the_first() -> None:
    adapters = installed_adapters()
    doubled = {"another": adapters["simpy"], "simpy": adapters["simpy"]}
    schema = composed_schema(doubled)
    assert list(schema[COMPONENT_TYPES_KEY]) == list(PROCESS_TYPES)
    assert {entry["engine"] for entry in schema[COMPONENT_TYPES_KEY].values()} == {"another"}
