"""The JSON Schema and the schema pass (spec 1 "Validation", "Top-level keys", "Versioning").

AKS-87: E100 and E101. Each test names the spec 1 rule it checks.
"""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from lcsim.model import schema as schema_module
from lcsim.model.issues import Issue
from lcsim.model.schema import FORMAT_VERSION, model_schema, schema_pass

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = sorted((ROOT / "examples").glob("*.json"))
FIXTURES = Path(__file__).parent / "fixtures" / "issues"

COFFEE_SHOP: dict[str, Any] = json.loads(
    (ROOT / "examples" / "coffee_shop.json").read_text(encoding="utf-8")
)

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

# Every top-level key of spec 1 "Top-level keys", in table order.
TOP_LEVEL_KEYS = [
    "format_version",
    "meta",
    "domain",
    "parameters",
    "components",
    "connections",
    "experiments",
    "objectives",
    "constraints",
    "variables",
    "objective",
    "run",
]
PROCESS_ONLY = ["components", "connections", "experiments", "objectives"]
OPTIMIZATION_ONLY = ["variables", "objective"]


def coffee() -> dict[str, Any]:
    return copy.deepcopy(COFFEE_SHOP)


def product_mix() -> dict[str, Any]:
    return copy.deepcopy(PRODUCT_MIX)


def only(issues: list[Issue]) -> Issue:
    assert len(issues) == 1, [issue.as_dict() for issue in issues]
    return issues[0]


def summary(issues: list[Issue]) -> list[tuple[str, str]]:
    return [(issue.code, issue.path) for issue in issues]


# --- the schema itself -----------------------------------------------------------------


def test_schema_is_valid_draft_2020_12() -> None:
    schema = model_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)


def test_schema_uses_no_format_keyword() -> None:
    # Spec 1 "Validation": the schema uses no `format` keyword.
    def keywords(node: Any) -> set[str]:
        found: set[str] = set()
        if isinstance(node, dict):
            for key, value in node.items():
                found.add(key)
                if key not in {"properties", "$defs"}:
                    found |= keywords(value)
                else:
                    for child in value.values():
                        found |= keywords(child)
        elif isinstance(node, list):
            for child in node:
                found |= keywords(child)
        return found

    assert "format" not in keywords(model_schema())
    # Nor any pattern: identifiers are plain strings in the schema (spec 1 "Validation").
    assert "pattern" not in keywords(model_schema())
    assert "patternProperties" not in keywords(model_schema())
    assert "enum" not in keywords(model_schema())


def test_schema_top_level_keys_are_the_spec_1_table() -> None:
    assert list(model_schema()["properties"]) == TOP_LEVEL_KEYS
    assert model_schema()["required"] == ["format_version", "meta", "domain"]


def test_model_schema_returns_a_fresh_copy() -> None:
    first = model_schema()
    first["properties"].clear()
    assert list(model_schema()["properties"]) == TOP_LEVEL_KEYS


def test_format_version_is_the_spec_1_example_version() -> None:
    assert FORMAT_VERSION == "0.1"
    assert COFFEE_SHOP["format_version"] == FORMAT_VERSION


# --- files that pass ---------------------------------------------------------------------


@pytest.mark.parametrize("example", EXAMPLES, ids=[path.stem for path in EXAMPLES])
def test_examples_pass_the_schema_pass(example: Path) -> None:
    assert schema_pass(json.loads(example.read_text(encoding="utf-8"))) == []


def test_product_mix_passes() -> None:
    assert schema_pass(product_mix()) == []


def test_every_optional_key_passes_when_well_formed() -> None:
    document = coffee()
    document["meta"].update(
        {"description": "One till", "author": "Owner", "template": "coffee_shop"}
    )
    document["parameters"]["tills"]["description"] = "Number of tills"
    document["components"][1]["label"] = "Till"
    document["components"][1]["ui"] = {"x": 120, "y": 40}
    document["experiments"][0].update(
        {
            "scenarios": [{"id": "two", "set": {"tills": 2}}],
            "confidence": 0.9,
            "record_interval": "1 h",
            "search": {
                "objective": "wait",
                "budget": 20,
                "variables": ["tills"],
                "replications": 5,
            },
        }
    )
    document["objectives"] = [{"id": "wait", "metric": "till.wait.mean", "sense": "minimize"}]
    document["constraints"] = [
        {"id": "util", "metric": "till.utilization", "op": "<=", "value": 0.85}
    ]
    document["run"]["engine"] = "simpy"
    assert schema_pass(document) == []


def test_optional_optimization_keys_pass() -> None:
    document = product_mix()
    document["variables"].append({"id": "desks", "type": "integer", "lower": 0, "upper": 9})
    document["parameters"] = {"budget": {"value": 1000, "type": "number"}}
    document["run"] = {"target": "local", "fidelity": "standard"}
    assert schema_pass(document) == []


@pytest.mark.parametrize("key", ["parameters", "objectives", "constraints", "run"])
def test_keys_that_are_not_required_may_be_left_out(key: str) -> None:
    document = coffee()
    document.pop(key, None)
    assert schema_pass(document) == []


# --- `ui` (spec 1 "Components and ports", "Top-level keys") ----------------------------


def test_component_ui_accepts_any_content() -> None:
    document = coffee()
    document["components"][0]["ui"] = {
        "x": 10,
        "y": -4.5,
        "collapsed": True,
        "colour": None,
        "notes": ["any", {"nested": {"deep": [1, 2]}}],
    }
    assert schema_pass(document) == []


def test_component_ui_must_be_an_object() -> None:
    document = coffee()
    document["components"][0]["ui"] = "top left"
    issue = only(schema_pass(document))
    assert (issue.code, issue.path, issue.component) == ("E100", "/components/0/ui", "arrivals")
    assert issue.message == "'ui' in component 'arrivals' must be an object, not text."


def test_component_settings_are_not_checked_by_the_schema() -> None:
    # Unknown or missing settings inside `params` are E121 and E122, meaning pass.
    document = coffee()
    document["components"][1]["params"] = {"speed": "fast", "capacity": True}
    assert schema_pass(document) == []


def test_values_left_to_the_meaning_pass_take_any_json_value() -> None:
    # Quantities, numbers, identifiers' values and enumerations are meaning-pass checks
    # (E123, E141, E150-E152, E170-E173), so the schema accepts any JSON value there.
    document = coffee()
    document["parameters"]["tills"].update({"value": "two", "min": None, "max": [5]})
    document["experiments"][0].update(
        {
            "length": True,
            "warmup": {"a": 1},
            "replications": "30",
            "seed": None,
            "confidence": "high",
            "record_interval": [],
        }
    )
    document["run"] = {"target": "moon", "fidelity": "extreme"}
    document["domain"] = "process"
    assert schema_pass(document) == []


@pytest.mark.parametrize("value", [5, None, True, [], {}])
def test_enumerated_words_take_any_json_value(value: object) -> None:
    # A parameter's `type`, `sense`, `op`, `run.target` and `run.fidelity` are checked by
    # the meaning pass and the run checks (E152, E172, E173 and others), never as E100.
    document = coffee()
    document["parameters"]["tills"]["type"] = value
    document["objectives"] = [{"id": "w", "metric": "till.wait.mean", "sense": value}]
    document["constraints"] = [{"id": "u", "metric": "till.utilization", "op": value, "value": 1}]
    document["run"] = {"target": value, "fidelity": value}
    assert schema_pass(document) == []
    document = product_mix()
    document["variables"][0]["type"] = value
    document["objective"]["sense"] = value
    document["constraints"][0]["op"] = value
    assert schema_pass(document) == []


# --- E100: wrong JSON type -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "shown"),
    [([], "an array"), ("x", "text"), (1, "a number"), (None, "null"), (True, "true")],
)
def test_document_that_is_not_an_object(value: object, shown: str) -> None:
    issue = only(schema_pass(value))
    assert (issue.code, issue.path, issue.component) == ("E100", "", None)
    assert issue.message == f"The model file must be a JSON object, not {shown}."


@pytest.mark.parametrize(
    ("key", "value", "expected", "shown"),
    [
        ("format_version", 0.1, "text", "a number"),
        ("meta", "Coffee shop", "an object", "text"),
        ("domain", ["process"], "text", "an array"),
        ("parameters", [], "an object", "an array"),
        ("components", {}, "an array", "an object"),
        ("connections", None, "an array", "null"),
        ("experiments", False, "an array", "false"),
        ("objectives", {}, "an array", "an object"),
        ("constraints", "none", "an array", "text"),
        ("run", "local", "an object", "text"),
    ],
)
def test_top_level_value_of_the_wrong_type(
    key: str, value: object, expected: str, shown: str
) -> None:
    document = coffee()
    document[key] = value
    issues = schema_pass(document)
    issue = only(issues)
    assert (issue.code, issue.path, issue.component) == ("E100", f"/{key}", None)
    assert issue.message == f"'{key}' must be {expected}, not {shown}."
    assert issue.hint == f"Change '{key}' to {expected}."


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("meta", "name"), 5, "'name' in 'meta' must be text, not a number."),
        (("components", 1, "id"), 2, "'id' in component 2 must be text, not a number."),
        (("components", 1, "type"), None, "'type' in component 'till' must be text, not null."),
        (("components", 2), "exit", "Component 3 must be an object, not text."),
        (("connections", 0, "from"), ["arrivals", "out"], None),
        (("connections", 1), [], "Connection 2 must be an object, not an array."),
        (("parameters", "tills"), 1, "Parameter 'tills' must be an object, not a number."),
        (("meta", "template"), [], "'template' in 'meta' must be text, not an array."),
        (("experiments", 0, "id"), 1, "'id' in experiment 1 must be text, not a number."),
        (("experiments", 0, "scenarios"), {}, None),
        (("run", "engine"), 1, "'engine' in 'run' must be text, not a number."),
    ],
)
def test_entry_value_of_the_wrong_type(
    path: tuple[str | int, ...], value: object, message: str | None
) -> None:
    document = coffee()
    parent: Any = document
    for part in path[:-1]:
        parent = parent[part]
    parent[path[-1]] = value
    issue = only(schema_pass(document))
    assert issue.code == "E100"
    assert issue.path == "/" + "/".join(str(part) for part in path)
    if message is not None:
        assert issue.message == message


def test_component_issue_names_the_component() -> None:
    document = coffee()
    document["components"][1]["label"] = 7
    issue = only(schema_pass(document))
    assert issue.component == "till"
    assert issue.message == "'label' in component 'till' must be text, not a number."


def test_component_without_a_usable_id_has_no_component() -> None:
    document = coffee()
    document["components"][1]["id"] = 2
    issue = only(schema_pass(document))
    assert issue.component is None


def test_nested_entries_are_described_from_the_top() -> None:
    document = coffee()
    document["experiments"][0]["scenarios"] = [{"id": "two", "set": []}]
    issue = only(schema_pass(document))
    assert issue.path == "/experiments/0/scenarios/0/set"
    assert issue.message == (
        "'set' in scenario 'two' in experiment 'base' must be an object, not an array."
    )


def test_list_item_of_the_wrong_type_inside_an_entry() -> None:
    document = coffee()
    document["experiments"][0]["search"] = {"objective": "wait", "variables": ["tills", 3]}
    issue = only(schema_pass(document))
    assert issue.path == "/experiments/0/search/variables/1"
    assert issue.message == (
        "Item 2 of 'variables' in 'search' in experiment 'base' must be text, not a number."
    )


def test_list_entry_without_an_id_is_numbered() -> None:
    document = coffee()
    document["experiments"][0]["scenarios"] = [{"set": {}}]
    issue = only(schema_pass(document))
    assert issue.path == "/experiments/0/scenarios/0/id"
    assert issue.message == ("Scenario 1 in experiment 'base' is missing the required key 'id'.")


# --- E100: missing required key ------------------------------------------------------------


@pytest.mark.parametrize("key", ["format_version", "meta", "domain"])
def test_missing_required_top_level_key(key: str) -> None:
    document = coffee()
    del document[key]
    issue = only(schema_pass(document))
    assert (issue.code, issue.path, issue.component) == ("E100", f"/{key}", None)
    assert issue.message == f"The model file is missing the required key '{key}'."
    assert issue.hint == f"Add '{key}' to the model file."


@pytest.mark.parametrize("key", ["components", "connections", "experiments"])
def test_missing_key_required_for_process(key: str) -> None:
    document = coffee()
    del document[key]
    issue = only(schema_pass(document))
    assert (issue.code, issue.path) == ("E100", f"/{key}")
    assert issue.message == f"The model file is missing the required key '{key}'."


@pytest.mark.parametrize("key", ["variables", "objective"])
def test_missing_key_required_for_optimization(key: str) -> None:
    document = product_mix()
    del document[key]
    issue = only(schema_pass(document))
    assert (issue.code, issue.path) == ("E100", f"/{key}")


def test_constraints_are_optional_for_optimization() -> None:
    document = product_mix()
    del document["constraints"]
    assert schema_pass(document) == []


@pytest.mark.parametrize(
    ("entry", "key", "where"),
    [
        (("meta",), "name", "'meta'"),
        (("components", 1), "id", "Component 2"),
        (("components", 1), "type", "Component 'till'"),
        (("components", 2), "params", "Component 'exit'"),
        (("connections", 0), "from", "Connection 1"),
        (("connections", 1), "to", "Connection 2"),
        (("parameters", "tills"), "value", "Parameter 'tills'"),
        (("parameters", "tills"), "type", "Parameter 'tills'"),
        (("experiments", 0), "id", "Experiment 1"),
        (("experiments", 0), "length", "Experiment 'base'"),
    ],
)
def test_missing_required_key_in_an_entry(
    entry: tuple[str | int, ...], key: str, where: str
) -> None:
    document = coffee()
    parent: Any = document
    for part in entry:
        parent = parent[part]
    del parent[key]
    issue = only(schema_pass(document))
    expected_path = "/" + "/".join(str(part) for part in (*entry, key))
    assert (issue.code, issue.path) == ("E100", expected_path)
    assert issue.message == f"{where} is missing the required key '{key}'."
    if entry[0] == "components" and key != "id":
        assert issue.component == parent["id"]


def test_several_missing_keys_give_one_issue_each() -> None:
    document = coffee()
    document["connections"][0] = {}
    issues = schema_pass(document)
    assert summary(issues) == [("E100", "/connections/0/from"), ("E100", "/connections/0/to")]


@pytest.mark.parametrize(
    ("entry", "required"),
    [
        ("objectives", {"id": "wait", "metric": "till.wait.mean", "sense": "minimize"}),
        ("constraints", {"id": "u", "metric": "till.utilization", "op": "<=", "value": 0.8}),
    ],
)
def test_objective_and_constraint_entries_need_all_their_keys(
    entry: str, required: dict[str, Any]
) -> None:
    for key in required:
        document = coffee()
        item = dict(required)
        del item[key]
        document[entry] = [item]
        issue = only(schema_pass(document))
        assert issue.path == f"/{entry}/0/{key}"


@pytest.mark.parametrize(
    ("entry", "required"),
    [
        ("variables", {"id": "x", "type": "continuous"}),
        ("constraints", {"id": "c", "linear": {"x": 1}, "op": "<=", "rhs": 1}),
    ],
)
def test_optimization_entries_need_all_their_keys(entry: str, required: dict[str, Any]) -> None:
    for key in required:
        document = product_mix()
        item = dict(required)
        del item[key]
        document[entry] = [item]
        issue = only(schema_pass(document))
        assert issue.path == f"/{entry}/0/{key}"


@pytest.mark.parametrize("key", ["sense", "linear"])
def test_optimization_objective_needs_sense_and_linear(key: str) -> None:
    document = product_mix()
    del document["objective"][key]
    issue = only(schema_pass(document))
    assert issue.path == f"/objective/{key}"
    assert issue.message == f"'objective' is missing the required key '{key}'."


@pytest.mark.parametrize("key", ["target", "fidelity"])
def test_run_needs_target_and_fidelity_when_present(key: str) -> None:
    document = coffee()
    del document["run"][key]
    issue = only(schema_pass(document))
    assert issue.path == f"/run/{key}"


def test_search_needs_an_objective() -> None:
    document = coffee()
    document["experiments"][0]["search"] = {"budget": 10}
    issue = only(schema_pass(document))
    assert issue.path == "/experiments/0/search/objective"


def test_scenario_needs_id_and_set() -> None:
    document = coffee()
    document["experiments"][0]["scenarios"] = [{"id": "two"}]
    issue = only(schema_pass(document))
    assert issue.path == "/experiments/0/scenarios/0/set"


# --- E100: unknown key -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("entry", "where", "allowed"),
    [
        ((), "The model file", None),
        (("meta",), "'meta'", "name, description, author, template"),
        (("components", 1), "Component 'till'", "id, type, params, label, ui"),
        (("connections", 0), "Connection 1", "from, to"),
        (("parameters", "tills"), "Parameter 'tills'", "value, type, min, max, description"),
        (
            ("experiments", 0),
            "Experiment 'base'",
            "id, length, warmup, replications, seed, scenarios, confidence, record_interval, "
            "search",
        ),
        (("run",), "'run'", "target, fidelity, engine"),
    ],
)
def test_unknown_key(entry: tuple[str | int, ...], where: str, allowed: str | None) -> None:
    document = coffee()
    parent: Any = document
    for part in entry:
        parent = parent[part]
    parent["colour"] = "red"
    issue = only(schema_pass(document))
    expected_path = "/" + "/".join(str(part) for part in (*entry, "colour"))
    assert (issue.code, issue.path) == ("E100", expected_path)
    assert issue.message == f"{where} has an unknown key 'colour'."
    if allowed is not None:
        assert issue.hint == (
            f"Remove 'colour' or correct its spelling. The keys allowed here are: {allowed}."
        )


def test_unknown_top_level_key_hint_lists_the_keys_of_the_model_domain() -> None:
    document = coffee()
    document["notes"] = "x"
    issue = only(schema_pass(document))
    assert issue.hint == (
        "Remove 'notes' or correct its spelling. The keys allowed here are: format_version, "
        "meta, domain, parameters, components, connections, experiments, objectives, "
        "constraints, run."
    )
    document = product_mix()
    document["notes"] = "x"
    issue = only(schema_pass(document))
    assert issue.hint == (
        "Remove 'notes' or correct its spelling. The keys allowed here are: format_version, "
        "meta, domain, parameters, constraints, variables, objective, run."
    )


@pytest.mark.parametrize(
    ("entry", "item"),
    [
        ("objectives", {"id": "w", "metric": "till.wait.mean", "sense": "minimize"}),
        ("constraints", {"id": "u", "metric": "till.utilization", "op": "<=", "value": 0.8}),
    ],
)
def test_unknown_key_in_objective_or_constraint(entry: str, item: dict[str, Any]) -> None:
    document = coffee()
    document[entry] = [{**item, "weight": 1}]
    issue = only(schema_pass(document))
    assert issue.path == f"/{entry}/0/weight"


def test_unknown_keys_in_nested_experiment_objects() -> None:
    document = coffee()
    document["experiments"][0]["scenarios"] = [{"id": "two", "set": {"tills": 2}, "name": "x"}]
    document["experiments"][0]["search"] = {"objective": "wait", "method": "tpe"}
    issues = schema_pass(document)
    assert summary(issues) == [
        ("E100", "/experiments/0/scenarios/0/name"),
        ("E100", "/experiments/0/search/method"),
    ]


def test_unknown_keys_in_optimization_entries() -> None:
    document = product_mix()
    document["variables"][0]["start"] = 1
    document["objective"]["name"] = "profit"
    document["constraints"][0]["metric"] = "x"
    issues = schema_pass(document)
    assert summary(issues) == [
        ("E100", "/constraints/0/metric"),
        ("E100", "/objective/name"),
        ("E100", "/variables/0/start"),
    ]


def test_several_unknown_keys_give_one_issue_each() -> None:
    document = coffee()
    document["components"][0].update({"colour": "red", "size": 3})
    issues = schema_pass(document)
    assert summary(issues) == [
        ("E100", "/components/0/colour"),
        ("E100", "/components/0/size"),
    ]
    assert all(issue.component == "arrivals" for issue in issues)


def test_unknown_key_with_characters_that_need_escaping() -> None:
    document = coffee()
    document["components"][0]["a/b~c"] = 1
    issue = only(schema_pass(document))
    assert issue.path == "/components/0/a~1b~0c"
    assert "'a/b~c'" in issue.message


def test_ui_at_top_level_is_an_unknown_key() -> None:
    # Spec 1 places `ui` on components only; the top-level table has no `ui`.
    document = coffee()
    document["ui"] = {"zoom": 1}
    issue = only(schema_pass(document))
    assert issue.path == "/ui"


# --- E100: a key that belongs to the other domain -----------------------------------------


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("variables", [{"id": "x", "type": "continuous"}]),
        ("objective", {"sense": "maximize", "linear": {"x": 1}}),
    ],
)
def test_optimization_key_in_a_process_model(key: str, value: object) -> None:
    document = coffee()
    document[key] = value
    issue = only(schema_pass(document))
    assert (issue.code, issue.path, issue.component) == ("E100", f"/{key}", None)
    assert issue.message == (
        f"The key '{key}' belongs to the 'optimization' domain, but this model's domain is "
        "'process'."
    )
    assert issue.hint == (
        f"Remove '{key}', or change 'domain' if the model is meant for the 'optimization' domain."
    )


@pytest.mark.parametrize("key", PROCESS_ONLY)
def test_process_key_in_an_optimization_model(key: str) -> None:
    document = product_mix()
    document[key] = coffee().get(key, [])
    issue = only(schema_pass(document))
    assert (issue.code, issue.path) == ("E100", f"/{key}")
    assert issue.message == (
        f"The key '{key}' belongs to the 'process' domain, but this model's domain is "
        "'optimization'."
    )


def test_other_domain_key_is_reported_once_even_when_its_content_is_wrong() -> None:
    document = coffee()
    document["variables"] = [{"bad": 1}, 2]
    issue = only(schema_pass(document))
    assert issue.path == "/variables"


def test_process_constraint_shape_in_an_optimization_model() -> None:
    document = product_mix()
    document["constraints"] = [{"id": "u", "metric": "till.utilization", "op": "<=", "value": 1}]
    issues = schema_pass(document)
    assert summary(issues) == [
        ("E100", "/constraints/0/linear"),
        ("E100", "/constraints/0/metric"),
        ("E100", "/constraints/0/rhs"),
        ("E100", "/constraints/0/value"),
    ]


def test_optimization_constraint_shape_in_a_process_model() -> None:
    document = coffee()
    document["constraints"] = [{"id": "c", "linear": {"x": 1}, "op": "<=", "rhs": 1}]
    issues = schema_pass(document)
    assert summary(issues) == [
        ("E100", "/constraints/0/linear"),
        ("E100", "/constraints/0/metric"),
        ("E100", "/constraints/0/rhs"),
        ("E100", "/constraints/0/value"),
    ]


@pytest.mark.parametrize("domain", ["physics", "", "Process"])
def test_unknown_domain_is_left_to_the_meaning_pass(domain: str) -> None:
    # "No single engine for this domain" is E102, a meaning-pass code; the schema checks
    # only that every key is a Phase 1 key of the right JSON type.
    document = coffee()
    document["domain"] = domain
    document["variables"] = [{"id": "x", "type": "continuous"}]
    assert schema_pass(document) == []
    del document["components"]
    assert schema_pass(document) == []


# --- E101: format_version (spec 1 "Versioning") -------------------------------------------


@pytest.mark.parametrize("version", ["1.0", "2.5", "10.0"])
def test_unknown_major_version(version: str) -> None:
    document = coffee()
    document["format_version"] = version
    issue = only(schema_pass(document))
    assert (issue.code, issue.severity, issue.path, issue.component) == (
        "E101",
        "error",
        "/format_version",
        None,
    )
    assert issue.message == (
        f"'format_version' is '{version}', but this program reads format versions 0.0 to 0.1."
    )


@pytest.mark.parametrize("version", ["0.2", "0.10", "0.99"])
def test_minor_version_above_the_reader(version: str) -> None:
    document = coffee()
    document["format_version"] = version
    issue = only(schema_pass(document))
    assert (issue.code, issue.path) == ("E101", "/format_version")
    assert "newer version of the program" in issue.hint


@pytest.mark.parametrize("version", ["0.0", "0.1"])
def test_own_major_and_a_minor_not_above_the_reader_pass(version: str) -> None:
    document = coffee()
    document["format_version"] = version
    assert schema_pass(document) == []


@pytest.mark.parametrize(
    "version",
    ["0", "0.1.0", "v0.1", "0.01", "00.1", " 0.1", "0.1 ", "", "0.x", "0,1", "\u0660.\u0661"],
)
def test_version_not_of_the_form_major_minor(version: str) -> None:
    document = coffee()
    document["format_version"] = version
    issue = only(schema_pass(document))
    assert (issue.code, issue.path) == ("E101", "/format_version")
    assert issue.message == (
        f"'format_version' is '{version}', which is not of the form MAJOR.MINOR, such as '0.1'."
    )


def test_unsupported_version_stops_the_schema_pass() -> None:
    # A file of an unknown version may follow another schema, so its keys are not judged.
    document = coffee()
    document["format_version"] = "1.0"
    document["new_key"] = 1
    del document["meta"]
    issue = only(schema_pass(document))
    assert issue.code == "E101"


@pytest.mark.parametrize(
    ("version", "hint_part"),
    [
        ("0." + "1" * 5000, "newer version of the program"),
        ("1" * 5000 + ".0", "another major version"),
        ("0." + "0" * 5000, "two whole numbers"),
        ("0." + "0" * 4999 + "1", "two whole numbers"),
    ],
)
def test_very_long_version_numbers_are_compared_without_overflow(
    version: str, hint_part: str
) -> None:
    # Python refuses int() on more than 4,300 digits; the version is compared as text.
    document = coffee()
    document["format_version"] = version
    issue = only(schema_pass(document))
    assert (issue.code, issue.path) == ("E101", "/format_version")
    assert hint_part in issue.hint


def test_version_that_is_not_text_is_e100() -> None:
    document = coffee()
    document["format_version"] = 1
    issue = only(schema_pass(document))
    assert (issue.code, issue.path) == ("E100", "/format_version")


# --- whole-file behaviour ------------------------------------------------------------------


def test_every_problem_is_reported_sorted_by_path_with_numeric_indexes() -> None:
    document = coffee()
    document["notes"] = 1
    document["components"].extend([{"id": f"c{n}", "type": "sink", "params": {}} for n in range(9)])
    document["components"][10]["size"] = 2
    document["components"][2]["colour"] = 1
    document["components"][0]["colour"] = 1
    del document["experiments"][0]["length"]
    issues = schema_pass(document)
    assert summary(issues) == [
        ("E100", "/components/0/colour"),
        ("E100", "/components/2/colour"),
        ("E100", "/components/10/size"),
        ("E100", "/experiments/0/length"),
        ("E100", "/notes"),
    ]
    assert [issue.component for issue in issues] == ["arrivals", "exit", "c7", None, None]


def test_schema_pass_does_not_change_the_document() -> None:
    document = coffee()
    document["colour"] = "red"
    before = copy.deepcopy(document)
    schema_pass(document)
    assert document == before


def test_every_message_is_plain_language() -> None:
    document = coffee()
    document["notes"] = 1
    document["meta"] = []
    document["components"][0]["id"] = 1
    del document["connections"][0]["to"]
    document["variables"] = []
    for issue in schema_pass(document):
        assert "jsonschema" not in issue.message
        assert "is not of type" not in issue.message
        assert "unexpected" not in issue.message
        assert issue.message.endswith(".")
        assert issue.hint.endswith(".")


# --- the fallback for a validator keyword the schema pass does not expect -------------------


def test_unexpected_validator_error_still_becomes_a_plain_issue() -> None:
    error = ValidationError(
        "raw validator text", validator="minimum", path=["experiments", 0, "replications"]
    )
    issues = schema_module._issues_from_error(error, coffee())
    issue = only(issues)
    assert (issue.code, issue.path) == ("E100", "/experiments/0/replications")
    assert issue.message == ("'replications' in experiment 'base' does not fit the model format.")
    assert "raw validator text" not in issue.message


def test_fallback_for_a_path_the_document_does_not_have() -> None:
    error = ValidationError("raw", validator="minimum", path=["components", 7, "x"])
    issue = only(schema_module._issues_from_error(error, coffee()))
    assert (issue.path, issue.component) == ("/components/7/x", None)
    assert issue.message == "'x' in component 8 does not fit the model format."


def test_object_keys_of_many_digits_sort_without_overflow() -> None:
    # A JSON key may be any string; one of more than 4,300 digits must not break sorting.
    document = coffee()
    long_key = "9" * 5000
    document["components"][0].update({long_key: 1, "10": 1, "9": 1, "010": 1})
    issues = schema_pass(document)
    assert [issue.path.rsplit("/", 1)[1] for issue in issues] == ["9", "010", "10", long_key]


HUGE = 10**5000  # more digits than Python will print (its limit is 4,300)


def put(document: dict[str, Any], path: tuple[str | int, ...], value: object) -> None:
    parent: Any = document
    for part in path[:-1]:
        parent = parent[part]
    if isinstance(parent, list) and path[-1] == len(parent):
        parent.append(value)
    else:
        parent[path[-1]] = value


@pytest.mark.parametrize(
    ("path", "value", "expected"),
    [
        (("meta", "name"), HUGE, [("E100", "/meta/name")]),
        (("components", 3), HUGE, [("E100", "/components/3")]),
        (("components", 0, "id"), -HUGE, [("E100", "/components/0/id")]),
        (("variables",), [{"id": "x", "type": "c", "lower": HUGE}], [("E100", "/variables")]),
        (("experiments", 0, "length"), HUGE, []),
        (("components", 0, "ui"), {"x": [HUGE]}, []),
    ],
    ids=["wrong-type", "list-item", "negative", "other-domain-key", "untyped", "in-ui"],
)
def test_very_large_integers_are_reported_not_raised(
    path: tuple[str | int, ...], value: object, expected: list[tuple[str, str]]
) -> None:
    # jsonschema prints the offending value when it builds an error; a very large integer
    # would make that raise, so the schema pass validates a copy without such integers.
    document = coffee()
    put(document, path, value)
    before = copy.deepcopy(document)
    issues = schema_pass(document)
    assert summary(issues) == expected
    assert document == before
    if expected and expected[0][1] != "/variables":
        assert issues[0].message.endswith("not a number.")


@pytest.mark.parametrize("document", [HUGE, [HUGE]], ids=["integer", "array"])
def test_very_large_integer_as_the_whole_file(document: object) -> None:
    issue = only(schema_pass(document))
    assert (issue.code, issue.path) == ("E100", "")


def test_document_without_large_integers_is_validated_as_it_is() -> None:
    document = coffee()
    assert schema_module._without_huge_integers(document) is document


def test_many_broken_entries_give_one_issue_per_problem() -> None:
    # jsonschema reports a `required` failure once per missing key, each naming every
    # missing key; the schema pass keeps one issue per problem (linear, found in review).
    document = coffee()
    document["components"] = [{} for _ in range(2000)]
    issues = schema_pass(document)
    assert len(issues) == 6000
    assert len(set(issues)) == 6000
    assert summary(issues[:3]) == [
        ("E100", "/components/0/id"),
        ("E100", "/components/0/params"),
        ("E100", "/components/0/type"),
    ]
    assert issues[-1].path == "/components/1999/type"
