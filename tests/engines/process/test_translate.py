"""The process adapter's engine input, ``engine/input.json`` (spec 1 "Division of labour";
AKS-98).

The resolved model with SI floats, the experiment, and each scenario's resolved settings;
no ``ui``, ``label`` or ``meta``, so changing them leaves the file byte-equal (spec 1
"Components and ports": ``ui`` is never read by an engine; the M1 "Left" item).
"""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from conftest import ModelMaker, constant, line, model_document

from lcsim.engines.process.translate import (
    INPUT_FILE,
    engine_input,
    read_input,
    resolve_setting,
    write_input,
)
from lcsim.model.distributions import DataNotYetSupportedError
from lcsim.model.loading import build_document, load_document
from lcsim.model.model import Distribution, Model, ParamRef, SettingValue
from lcsim.model.units import Dimension, Quantity

ROOT = Path(__file__).resolve().parents[3]
COFFEE_SHOP: dict[str, Any] = json.loads(
    (ROOT / "examples" / "coffee_shop.json").read_text(encoding="utf-8")
)


def load(document: dict[str, Any]) -> Model:
    result = load_document(document)
    assert result.model is not None, [issue.as_dict() for issue in result.issues]
    return result.model


def test_the_coffee_shop_input_holds_the_resolved_model_in_si_units() -> None:
    assert engine_input(load(copy.deepcopy(COFFEE_SHOP)), "base") == {
        "input_version": 1,
        "experiment": {
            "id": "base",
            "length": 720_000.0,
            "warmup": 36_000.0,
            "replications": 30,
            "seed": 12345,
            "record_interval": 3_600.0,
        },
        "connections": [
            {"from": "arrivals.out", "to": "till.in"},
            {"from": "till.out", "to": "exit.in"},
        ],
        "scenarios": [
            {
                "id": "default",
                "components": [
                    {
                        "id": "arrivals",
                        "type": "source",
                        "settings": {"interarrival": {"dist": "exponential", "mean": 120.0}},
                    },
                    {
                        "id": "till",
                        "type": "server",
                        "settings": {
                            "capacity": 1,
                            "service": {"dist": "exponential", "mean": 90.0},
                            "discipline": "fifo",
                        },
                    },
                    {"id": "exit", "type": "sink", "settings": {}},
                ],
            }
        ],
    }


def test_changing_ui_label_or_meta_leaves_the_input_byte_equal(tmp_path: Path) -> None:
    plain = copy.deepcopy(COFFEE_SHOP)
    dressed = copy.deepcopy(COFFEE_SHOP)
    for index, component in enumerate(dressed["components"]):
        component["ui"] = {"x": 100 * index, "y": -7.5, "colour": "teal", "notes": [1, None]}
        component["label"] = f"Block {index}"
    dressed["meta"] = {"name": "Renamed", "description": "Moved around", "author": "Someone"}
    write_input(load(plain), "base", tmp_path / "plain")
    write_input(load(dressed), "base", tmp_path / "dressed")
    first = (tmp_path / "plain" / INPUT_FILE).read_bytes()
    assert first == (tmp_path / "dressed" / INPUT_FILE).read_bytes()
    assert b"ui" not in first.replace(b"input_version", b"")
    assert b"Block" not in first and b"Coffee" not in first


def test_each_scenario_resolves_its_own_parameter_values(make_model: ModelMaker) -> None:
    components, connections = line(
        {"dist": "exponential", "mean": {"$param": "gap"}},
        {"dist": "uniform", "min": "30 s", "max": {"$param": "longest"}},
        capacity={"$param": "tills"},
    )
    model = make_model(
        components,
        connections,
        parameters={
            "tills": {"value": 1, "type": "integer", "min": 1, "max": 3},
            "gap": {"value": "2 min", "type": "quantity"},
            "longest": {"value": "1 min", "type": "quantity"},
        },
        scenarios=[
            {"id": "one", "set": {}},
            {"id": "two", "set": {"tills": 2, "gap": "3 min", "longest": "90 s"}},
        ],
    )
    scenarios = engine_input(model, "e")["scenarios"]
    assert [scenario["id"] for scenario in scenarios] == ["one", "two"]
    one, two = (
        {component["id"]: component["settings"] for component in scenario["components"]}
        for scenario in scenarios
    )
    assert one["till"]["capacity"] == 1 and two["till"]["capacity"] == 2
    assert isinstance(two["till"]["capacity"], int)
    assert one["arrivals"]["interarrival"] == {"dist": "exponential", "mean": 120.0}
    assert two["arrivals"]["interarrival"] == {"dist": "exponential", "mean": 180.0}
    assert one["till"]["service"] == {"dist": "uniform", "min": 30.0, "max": 60.0}
    assert two["till"]["service"] == {"dist": "uniform", "min": 30.0, "max": 90.0}


def test_optional_settings_are_kept_and_defaults_filled(make_model: ModelMaker) -> None:
    components, connections = line(constant("1 min"), constant("30 s"))
    components[0]["params"].update({"first_arrival": "5 min", "max_items": 3})
    components[1]["params"]["discipline"] = "lifo"
    settings = {
        component["id"]: component["settings"]
        for component in engine_input(make_model(components, connections), "e")["scenarios"][0][
            "components"
        ]
    }
    assert settings["arrivals"] == {
        "interarrival": {"dist": "constant", "value": 60.0},
        "first_arrival": 300.0,
        "max_items": 3,
    }
    assert settings["till"]["discipline"] == "lifo"


def test_empirical_values_and_weibull_fields_are_floats(make_model: ModelMaker) -> None:
    components, connections = line(
        {"dist": "empirical", "values": ["1 min", "2 min"]},
        {"dist": "weibull", "shape": 2, "scale": "1 min"},
    )
    components_out = engine_input(make_model(components, connections), "e")["scenarios"][0][
        "components"
    ]
    assert components_out[0]["settings"]["interarrival"] == {
        "dist": "empirical",
        "values": [60.0, 120.0],
    }
    service = components_out[1]["settings"]["service"]
    assert service == {"dist": "weibull", "shape": 2.0, "scale": 60.0}
    assert isinstance(service["shape"], float)


def test_arrays_and_objects_of_settings_resolve_entry_by_entry() -> None:
    """The shapes of a branch's ``routes`` and ``weights`` (AKS-99) resolve already."""
    model = load(copy.deepcopy(COFFEE_SHOP))
    assert resolve_setting(model, ("a", "b"), {}) == ["a", "b"]
    weights: dict[str, SettingValue] = {"a": ParamRef("tills"), "b": 0.5}
    assert resolve_setting(model, weights, {"tills": 3}) == {"a": 3, "b": 0.5}
    assert resolve_setting(model, Quantity(2.0, Dimension.TIME), {}) == 2.0


def test_input_is_written_inside_workdir_only(tmp_path: Path) -> None:
    workdir = tmp_path / "runs" / "r1" / "engine"
    path = write_input(load(copy.deepcopy(COFFEE_SHOP)), "base", workdir)
    assert path == workdir / INPUT_FILE
    assert sorted(item.name for item in tmp_path.rglob("*") if item.is_file()) == [INPUT_FILE]
    text = path.read_text(encoding="utf-8")
    assert text.endswith("}\n")
    assert read_input(workdir) == json.loads(text)


def test_an_input_of_another_layout_version_is_refused(tmp_path: Path) -> None:
    (tmp_path / INPUT_FILE).write_text(json.dumps({"input_version": 99}), encoding="utf-8")
    with pytest.raises(ValueError, match="not a version 1 input"):
        read_input(tmp_path)


def test_an_unknown_experiment_is_refused() -> None:
    with pytest.raises(ValueError, match="no experiment 'other'"):
        engine_input(load(copy.deepcopy(COFFEE_SHOP)), "other")


def test_block_types_not_built_yet_are_refused(make_model: ModelMaker) -> None:
    components, connections = line(constant("1 min"), constant("30 s"))
    components.insert(
        2,
        {
            "id": "stock",
            "type": "store",
            "params": {
                "initial": 5,
                "reorder_point": 1,
                "order_quantity": 5,
                "lead_time": constant("1 h"),
            },
        },
    )
    connections = [
        ("arrivals.out", "till.in"),
        ("till.out", "stock.in"),
        ("stock.out", "exit.in"),
    ]
    with pytest.raises(NotImplementedError, match=r"'store' blocks yet \(component 'stock'\).*M4"):
        engine_input(make_model(components, connections), "e")


def test_queue_batch_and_unbatch_translate(make_model: ModelMaker) -> None:
    """``queue``, ``batch`` and ``unbatch`` run since AKS-105, with the catalogue's
    defaults filled in (``fifo``, ``block``)."""
    components, _ = line(constant("1 min"), constant("30 s"))
    components[1:1] = [
        {"id": "buffer", "type": "queue", "params": {"capacity": 3}},
        {"id": "pack", "type": "batch", "params": {"size": 2, "timeout": "5 min"}},
        {"id": "unpack", "type": "unbatch", "params": {}},
    ]
    connections = [
        ("arrivals.out", "buffer.in"),
        ("buffer.out", "pack.in"),
        ("pack.out", "unpack.in"),
        ("unpack.out", "till.in"),
        ("till.out", "exit.in"),
    ]
    settings = {
        component["id"]: component["settings"]
        for component in engine_input(make_model(components, connections), "e")["scenarios"][0][
            "components"
        ]
    }
    assert settings["buffer"] == {"capacity": 3, "discipline": "fifo", "on_full": "block"}
    assert settings["pack"] == {"size": 2, "timeout": 300.0}
    assert settings["unpack"] == {}


def test_the_m2_block_types_and_queue_capacity_translate(make_model: ModelMaker) -> None:
    """``delay``, ``branch`` and a server's ``queue_capacity`` run since AKS-99."""
    components, connections = line(constant("1 min"), constant("30 s"))
    components[1]["params"]["queue_capacity"] = 0
    components[2:2] = [
        {"id": "walk", "type": "delay", "params": {"time": constant("1 min")}},
        {
            "id": "check",
            "type": "branch",
            "params": {"routes": ["a", "b"], "rule": "shortest_queue"},
        },
        {"id": "side", "type": "sink", "params": {}},
    ]
    connections = [
        ("arrivals.out", "till.in"),
        ("till.out", "walk.in"),
        ("walk.out", "check.in"),
        ("check.a", "exit.in"),
        ("check.b", "side.in"),
    ]
    settings = {
        component["id"]: component["settings"]
        for component in engine_input(make_model(components, connections), "e")["scenarios"][0][
            "components"
        ]
    }
    assert settings["till"]["queue_capacity"] == 0
    assert settings["walk"] == {"time": {"dist": "constant", "value": 60.0}}
    assert settings["check"] == {"routes": ["a", "b"], "rule": "shortest_queue"}


def test_a_server_s_pool_is_refused_until_m4(make_model: ModelMaker) -> None:
    components, connections = line(constant("1 min"), constant("30 s"))
    components[1]["params"]["pool"] = "staff"
    components.append({"id": "staff", "type": "resource_pool", "params": {"capacity": 1}})
    with pytest.raises(NotImplementedError, match=r"'pool' setting yet.*M4"):
        engine_input(make_model(components, connections), "e")


def test_an_empirical_with_data_cannot_be_translated_before_m6() -> None:
    """Validation reports E162 first; building alone gives a model that holds the data."""
    components, connections = line(
        constant("1 min"), {"dist": "empirical", "data": {"file": "t.csv", "column": "m"}}
    )
    built = build_document(model_document(components, connections), seed_source=lambda: 1)
    assert built.model is not None
    service = built.model.components[1].settings["service"]
    assert isinstance(service, Distribution) and service.data is not None
    with pytest.raises(DataNotYetSupportedError) as raised:
        engine_input(built.model, "e")
    assert raised.value.code == "E162"
