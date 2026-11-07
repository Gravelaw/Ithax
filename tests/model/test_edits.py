"""The sixteen model edits as pure functions on a model document (spec 3 "Model edits";
AKS-111). The request tests of the same edits are ``tests/service/test_models.py``."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from lcsim.model.catalogue import PROCESS_TYPES, BlockType, SettingKind, SettingSpec
from lcsim.model.edits import (
    EDIT_KINDS,
    EditOutcome,
    apply_edits,
    check_edits,
    first_non_finite,
)
from lcsim.model.loading import load_document

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "edits"


def shop() -> dict[str, Any]:
    """A process model that loads with no issues and uses every kind of reference: a
    ``$param``, a pool, a schedule and a failure target, a scenario, an objective and a
    constraint (shared with ``tests/service/test_models.py``)."""
    loaded: dict[str, Any] = json.loads((FIXTURES / "shop.json").read_text(encoding="utf-8"))
    return loaded


def plan() -> dict[str, Any]:
    """An optimization model that loads with no issues."""
    loaded: dict[str, Any] = json.loads((FIXTURES / "plan.json").read_text(encoding="utf-8"))
    return loaded


def apply(model: dict[str, Any], *edits: dict[str, Any]) -> EditOutcome:
    return apply_edits(model, list(edits), PROCESS_TYPES)


def applied(model: dict[str, Any], *edits: dict[str, Any]) -> dict[str, Any]:
    outcome = apply(model, *edits)
    assert outcome.issues == ()
    assert outcome.model is not None
    return outcome.model


def rejected(model: dict[str, Any], *edits: dict[str, Any]) -> dict[str, Any]:
    """The one E180 issue of a batch that cannot be applied, as a dict."""
    outcome = apply(model, *edits)
    assert outcome.model is None
    assert len(outcome.issues) == 1
    issue = outcome.issues[0]
    assert issue.code == "E180" and issue.severity == "error"
    assert issue.component is None
    return issue.as_dict()


def component(model: dict[str, Any], cid: str) -> dict[str, Any]:
    [found] = [item for item in model["components"] if item["id"] == cid]
    assert isinstance(found, dict)
    return found


def test_the_fixtures_load_with_no_issues() -> None:
    for model in (shop(), plan()):
        result = load_document(model)
        assert result.issues == ()


def test_there_are_sixteen_edit_kinds_in_spec_order() -> None:
    assert EDIT_KINDS == (
        "add_component",
        "remove_component",
        "rename_component",
        "set_setting",
        "connect",
        "disconnect",
        "set_parameter",
        "remove_parameter",
        "set_experiment",
        "remove_experiment",
        "set_scenario",
        "remove_scenario",
        "set_path",
        "remove_path",
        "set_ui",
        "set_label",
    )


def test_applying_edits_leaves_the_given_model_unchanged() -> None:
    model = shop()
    before = copy.deepcopy(model)
    applied(model, {"edit": "set_label", "id": "till", "label": "Counter"})
    rejected(
        model,
        {"edit": "set_label", "id": "till", "label": "x"},
        {"edit": "remove_component", "id": "pump"},
    )
    assert model == before


# --- the shape of a batch (E184) -----------------------------------------------------


def shape(edits: object) -> list[tuple[str, str]]:
    issues = check_edits(edits)
    assert all(issue.code == "E184" and issue.component is None for issue in issues)
    return [(issue.path, issue.message) for issue in issues]


def test_a_well_formed_batch_has_no_shape_issues() -> None:
    assert shape([{"edit": "set_label", "id": "till", "label": None}]) == []
    assert shape([{"edit": "set_parameter", "id": "p", "value": [1], "min": None}]) == []
    assert shape([{"edit": "set_experiment", "id": "e", "seed": 1, "search": "x"}]) == []


@pytest.mark.parametrize(
    ("edits", "path"),
    [
        ({"edit": "set_ui"}, "/edits"),
        ([], "/edits"),
        (["connect"], "/edits/0"),
        ([{"id": "till"}], "/edits/0/edit"),
        ([{"edit": 3}], "/edits/0/edit"),
        ([{"edit": "move_component", "id": "till"}], "/edits/0/edit"),
        ([{"edit": "remove_component"}], "/edits/0/id"),
        ([{"edit": "remove_component", "id": "till", "force": True}], "/edits/0/force"),
        ([{"edit": "remove_component", "id": 7}], "/edits/0/id"),
        ([{"edit": "add_component", "id": "a", "type": "sink", "params": []}], "/edits/0/params"),
        ([{"edit": "set_ui", "id": "a", "ui": None}], "/edits/0/ui"),
        ([{"edit": "set_label", "id": "a", "label": 5}], "/edits/0/label"),
        ([{"edit": "set_label", "id": "a"}], "/edits/0/label"),
        ([{"edit": "set_scenario", "experiment_id": "base", "id": "s", "set": 1}], "/edits/0/set"),
        ([{"edit": "set_setting", "id": "a", "path": "capacity", "value": 1}], "/edits/0/path"),
        ([{"edit": "set_path", "path": "/meta/~2", "value": 1}], "/edits/0/path"),
        ([{"edit": "remove_path", "path": "/meta~"}], "/edits/0/path"),
        ([{"edit": "set_parameter", "id": "p", "description": "x"}], "/edits/0/description"),
        ([{"edit": "set_experiment", "id": "e", "name": "x"}], "/edits/0/name"),
        ([{"edit": "connect", "from": "a.out"}], "/edits/0/to"),
        ([{"edit": "set_setting", "id": "a", "path": "/x"}], "/edits/0/value"),
    ],
)
def test_a_badly_shaped_edit_is_e184_at_its_place(edits: object, path: str) -> None:
    issues = shape(edits)
    assert [where for where, _ in issues] == [path]
    assert all(message for _, message in issues)


@pytest.mark.parametrize(
    ("edit", "path"),
    [
        ({"edit": "set_ui", "id": "a", "ui": {"x": float("inf")}}, "/edits/0/ui"),
        ({"edit": "set_path", "path": "/meta/x", "value": [1, float("nan")]}, "/edits/0/value"),
        ({"edit": "set_parameter", "id": "p", "value": float("-inf")}, "/edits/0/value"),
    ],
)
def test_a_number_json_cannot_hold_is_e184(edit: dict[str, Any], path: str) -> None:
    [(where, message)] = shape([edit])
    assert where == path
    assert "too large" in message


def test_first_non_finite_finds_the_place() -> None:
    assert first_non_finite({"a": [1, {"b": float("inf")}]}) == "/a/1/b"
    assert first_non_finite({"a": [1, 2.5, "x", None, True]}) is None
    assert first_non_finite(float("nan")) == ""


def test_every_shape_problem_of_a_batch_is_listed() -> None:
    issues = shape(
        [
            {"edit": "set_label", "id": "till", "label": "ok"},
            {"edit": "connect", "from": 1, "to": 2, "via": "x"},
        ]
    )
    assert [where for where, _ in issues] == ["/edits/1/from", "/edits/1/to", "/edits/1/via"]


def test_apply_reports_shape_problems_and_applies_nothing() -> None:
    outcome = apply_edits(shop(), [{"edit": "nope"}], PROCESS_TYPES)
    assert outcome.model is None
    assert [issue.code for issue in outcome.issues] == ["E184"]


def test_shape_messages_name_the_field_and_kind() -> None:
    [(_, message)] = shape([{"edit": "remove_component", "id": 7}])
    assert "'id'" in message and "text" in message
    [(_, message)] = shape([{"edit": "fly"}])
    assert "'fly'" in message


# --- add_component and remove_component ----------------------------------------------


def test_add_component_appends_the_component() -> None:
    model = applied(
        shop(),
        {
            "edit": "add_component",
            "id": "wait",
            "type": "delay",
            "params": {"time": {"dist": "constant", "value": "1 min"}},
            "ui": {"x": 1},
        },
        {"edit": "add_component", "id": "bin", "type": "sink", "params": {}},
    )
    assert model["components"][-2:] == [
        {
            "id": "wait",
            "type": "delay",
            "params": {"time": {"dist": "constant", "value": "1 min"}},
            "ui": {"x": 1},
        },
        {"id": "bin", "type": "sink", "params": {}},
    ]


def test_add_component_with_an_id_that_is_taken_is_e180() -> None:
    issue = rejected(shop(), {"edit": "add_component", "id": "till", "type": "sink", "params": {}})
    assert issue["path"] == "/edits/0"
    assert "'till'" in issue["message"]


def test_add_component_of_an_unknown_type_is_e180() -> None:
    issue = rejected(
        shop(),
        {"edit": "set_label", "id": "till", "label": "x"},
        {"edit": "add_component", "id": "pump", "type": "pump", "params": {}},
    )
    assert issue["path"] == "/edits/1"
    assert "'pump'" in issue["message"]
    assert "server" in issue["hint"]


def test_add_component_in_an_optimization_model_has_no_types() -> None:
    outcome = apply_edits(
        plan(), [{"edit": "add_component", "id": "a", "type": "sink", "params": {}}], {}
    )
    assert [issue.code for issue in outcome.issues] == ["E180"]
    assert "no component types" in outcome.issues[0].hint


def test_add_component_with_a_bad_id_is_applied_for_the_meaning_pass() -> None:
    model = applied(shop(), {"edit": "add_component", "id": "Bin 2", "type": "sink", "params": {}})
    assert [issue.code for issue in load_document(model).errors] == ["E111"]


def test_remove_component_removes_it_and_its_connections() -> None:
    model = applied(shop(), {"edit": "remove_component", "id": "till"})
    assert [item["id"] for item in model["components"]] == [
        "arrivals",
        "staff",
        "shifts",
        "breakdown",
        "exit",
    ]
    assert model["connections"] == []
    # What still names it is the meaning pass's to report.
    codes = {issue.code for issue in load_document(model).issues}
    assert {"E124", "E174", "E131"} <= codes


def test_remove_component_keeps_other_connections() -> None:
    model = applied(shop(), {"edit": "remove_component", "id": "exit"})
    assert model["connections"] == [{"from": "arrivals.out", "to": "till.in"}]


def test_remove_component_of_an_unknown_id_is_e180() -> None:
    issue = rejected(shop(), {"edit": "remove_component", "id": "pump"})
    assert "'pump'" in issue["message"]


# --- rename_component ----------------------------------------------------------------


def test_rename_component_rewrites_every_reference() -> None:
    model = applied(shop(), {"edit": "rename_component", "id": "till", "new_id": "counter"})
    assert component(model, "counter")["label"] == "Till"
    assert model["connections"] == [
        {"from": "arrivals.out", "to": "counter.in"},
        {"from": "counter.out", "to": "exit.in"},
    ]
    assert component(model, "breakdown")["params"]["target"] == "counter"
    assert model["objectives"][0]["metric"] == "counter.wait.mean"
    assert model["constraints"][0]["metric"] == "counter.utilization"
    assert load_document(model).issues == ()


def test_rename_component_rewrites_pool_and_schedule_targets() -> None:
    model = applied(shop(), {"edit": "rename_component", "id": "staff", "new_id": "crew"})
    assert component(model, "till")["params"]["pool"] == "crew"
    assert component(model, "shifts")["params"]["target"] == "crew"
    assert load_document(model).issues == ()


def test_rename_component_leaves_other_names_alone() -> None:
    model = shop()
    model["components"].append({"id": "tillx", "type": "sink", "params": {}})
    model["connections"].append({"from": "nodot", "to": "tillx.in"})
    model["objectives"].append({"id": "x", "metric": "tillx.count", "sense": "maximize"})
    model["components"][4]["params"]["target"] = 5
    renamed = applied(model, {"edit": "rename_component", "id": "till", "new_id": "counter"})
    assert renamed["connections"][2:] == [{"from": "nodot", "to": "tillx.in"}]
    assert renamed["objectives"][1]["metric"] == "tillx.count"
    assert component(renamed, "breakdown")["params"]["target"] == 5


def test_rename_component_rewrites_a_list_of_references() -> None:
    watcher = BlockType(
        "watcher",
        inputs=(),
        outputs=(),
        outputs_from=None,
        settings=(
            SettingSpec("targets", SettingKind.IDENTIFIER, True, many=True, refers_to=("server",)),
        ),
        metrics=(),
    )
    model = shop()
    model["components"].append(
        {"id": "eye", "type": "watcher", "params": {"targets": ["till", "exit"]}}
    )
    model["components"].append({"id": "odd", "type": "unknown", "params": {}})
    renamed = apply_edits(
        model,
        [{"edit": "rename_component", "id": "till", "new_id": "counter"}],
        {**PROCESS_TYPES, "watcher": watcher},
    )
    assert renamed.model is not None
    assert component(renamed.model, "eye")["params"]["targets"] == ["counter", "exit"]


def test_rename_component_survives_objectives_that_are_not_a_list() -> None:
    model = applied(
        shop(),
        {"edit": "set_path", "path": "/objectives", "value": "odd"},
        {"edit": "set_path", "path": "/constraints", "value": ["odd", {"id": "x", "metric": 3}]},
        {"edit": "rename_component", "id": "till", "new_id": "counter"},
        {"edit": "set_path", "path": "/objectives", "value": []},
        {"edit": "set_path", "path": "/constraints", "value": []},
    )
    assert model["objectives"] == [] and model["constraints"] == []
    assert component(model, "counter")["type"] == "server"


def test_rename_component_to_its_own_id_changes_nothing() -> None:
    assert applied(shop(), {"edit": "rename_component", "id": "till", "new_id": "till"}) == shop()


def test_rename_component_of_an_unknown_id_is_e180() -> None:
    issue = rejected(shop(), {"edit": "rename_component", "id": "pump", "new_id": "p"})
    assert "'pump'" in issue["message"]


def test_rename_component_to_a_taken_id_is_e180() -> None:
    issue = rejected(shop(), {"edit": "rename_component", "id": "till", "new_id": "exit"})
    assert "'exit'" in issue["message"]


# --- set_setting -----------------------------------------------------------------------


def test_set_setting_replaces_a_value_inside_params() -> None:
    model = applied(
        shop(), {"edit": "set_setting", "id": "till", "path": "/service/mean", "value": "2 min"}
    )
    assert component(model, "till")["params"]["service"] == {"dist": "exponential", "mean": "2 min"}


def test_set_setting_may_create_the_last_segment() -> None:
    model = applied(
        shop(), {"edit": "set_setting", "id": "till", "path": "/queue_capacity", "value": 5}
    )
    assert component(model, "till")["params"]["queue_capacity"] == 5


def test_set_setting_addresses_arrays_by_index() -> None:
    shift = {"start": "8 h", "end": "16 h", "capacity": 2}
    model = applied(
        shop(),
        {"edit": "set_setting", "id": "shifts", "path": "/shifts/0/capacity", "value": 3},
        {"edit": "set_setting", "id": "shifts", "path": "/shifts/-", "value": shift},
        {"edit": "set_setting", "id": "shifts", "path": "/shifts/2", "value": shift},
        {
            "edit": "set_setting",
            "id": "shifts",
            "path": "/shifts/1",
            "value": {**shift, "capacity": 4},
        },
    )
    shifts = component(model, "shifts")["params"]["shifts"]
    assert [item["capacity"] for item in shifts] == [3, 4, 2]


def test_set_setting_unescapes_pointer_segments() -> None:
    model = applied(shop(), {"edit": "set_setting", "id": "exit", "path": "/a~1b~0c", "value": 1})
    assert component(model, "exit")["params"] == {"a/b~c": 1}


def test_set_setting_of_an_unknown_component_is_e180() -> None:
    issue = rejected(shop(), {"edit": "set_setting", "id": "pump", "path": "/capacity", "value": 1})
    assert "'pump'" in issue["message"]


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/arrival/mean",
        "/capacity/x",
        "/shifts/5",
        "/shifts/01",
        "/shifts/x",
        "/shifts/-/capacity",
        "/shifts/1/capacity",
    ],
)
def test_set_setting_whose_parent_does_not_exist_is_e180(path: str) -> None:
    issue = rejected(
        shop(),
        {
            "edit": "set_setting",
            "id": "shifts" if "shifts" in path else "till",
            "path": path,
            "value": 1,
        },
    )
    assert issue["path"] == "/edits/0"
    assert issue["message"] and issue["hint"]


# --- connect and disconnect ----------------------------------------------------------


def test_connect_adds_a_connection() -> None:
    model = shop()
    model["connections"].pop()
    connected = applied(model, {"edit": "connect", "from": "till.out", "to": "exit.in"})
    assert connected["connections"] == shop()["connections"]


def test_connect_replaces_the_connection_from_the_same_port() -> None:
    model = shop()
    model["connections"].append({"from": "till.out", "to": "staff.in"})
    model["components"].append({"id": "bin", "type": "sink", "params": {}})
    connected = applied(model, {"edit": "connect", "from": "till.out", "to": "bin.in"})
    assert connected["connections"] == [
        {"from": "arrivals.out", "to": "till.in"},
        {"from": "till.out", "to": "bin.in"},
    ]


def test_connect_to_an_unknown_port_is_applied_for_the_meaning_pass() -> None:
    model = applied(shop(), {"edit": "connect", "from": "till.out", "to": "pump.in"})
    assert "E130" in {issue.code for issue in load_document(model).issues}


def test_connect_in_an_optimization_model_fails_the_schema_and_is_e180() -> None:
    outcome = apply_edits(plan(), [{"edit": "connect", "from": "a.out", "to": "b.in"}], {})
    assert outcome.model is None
    [issue] = outcome.issues
    assert issue.code == "E180" and issue.path == "/edits/0"
    assert "schema" in issue.message


def test_disconnect_removes_the_connection_from_a_port() -> None:
    model = applied(shop(), {"edit": "disconnect", "from": "till.out"})
    assert model["connections"] == [{"from": "arrivals.out", "to": "till.in"}]


def test_disconnect_of_a_port_with_no_connection_changes_nothing() -> None:
    assert applied(shop(), {"edit": "disconnect", "from": "exit.out"}) == shop()


# --- parameters ------------------------------------------------------------------------


def test_set_parameter_changes_the_fields_given() -> None:
    model = applied(shop(), {"edit": "set_parameter", "id": "tills", "value": 2, "max": 4})
    assert model["parameters"]["tills"] == {"value": 2, "type": "integer", "min": 1, "max": 4}


def test_set_parameter_with_a_new_id_creates_it() -> None:
    model = applied(
        shop(),
        {
            "edit": "set_parameter",
            "id": "speed",
            "type": "quantity",
            "value": "1 min",
            "min": "0 s",
        },
    )
    assert model["parameters"]["speed"] == {"value": "1 min", "type": "quantity", "min": "0 s"}


def test_set_parameter_creates_the_parameters_object() -> None:
    model = plan()
    created = apply_edits(
        model, [{"edit": "set_parameter", "id": "k", "value": 1, "type": "number"}], {}
    )
    assert created.model is not None
    assert created.model["parameters"] == {"k": {"value": 1, "type": "number"}}


@pytest.mark.parametrize("fields", [{}, {"value": 1}, {"type": "integer"}])
def test_a_new_parameter_without_value_and_type_is_e180(fields: dict[str, Any]) -> None:
    issue = rejected(shop(), {"edit": "set_parameter", "id": "speed", **fields})
    assert "'speed'" in issue["message"]


def test_remove_parameter_removes_an_unused_parameter() -> None:
    model = shop()
    model["experiments"][0]["scenarios"] = []
    removed = applied(model, {"edit": "remove_parameter", "id": "spare"})
    assert list(removed["parameters"]) == ["tills"]


def test_remove_parameter_of_an_unknown_id_is_e180() -> None:
    issue = rejected(shop(), {"edit": "remove_parameter", "id": "speed"})
    assert "'speed'" in issue["message"]


def test_remove_parameter_used_by_a_setting_is_e180() -> None:
    issue = rejected(shop(), {"edit": "remove_parameter", "id": "tills"})
    assert "'staff'" in issue["message"] and "'capacity'" in issue["message"]


def test_remove_parameter_used_deep_in_a_setting_is_e180() -> None:
    model = applied(
        shop(),
        {
            "edit": "set_setting",
            "id": "shifts",
            "path": "/shifts/0/capacity",
            "value": {"$param": "spare"},
        },
    )
    model["experiments"][0]["scenarios"] = []
    issue = rejected(model, {"edit": "remove_parameter", "id": "spare"})
    assert "'shifts'" in issue["message"]


def test_remove_parameter_used_by_a_scenario_is_e180() -> None:
    issue = rejected(shop(), {"edit": "remove_parameter", "id": "spare"})
    assert "'more'" in issue["message"]


def test_remove_parameter_used_by_a_search_is_e180() -> None:
    model = shop()
    model["experiments"][0]["scenarios"] = "odd"
    model["experiments"].append(
        {"id": "find", "length": "8 h", "search": {"objective": "wait", "variables": ["spare"]}}
    )
    model["experiments"].append(
        {"id": "odd", "length": "8 h", "search": {"objective": "wait", "variables": 3}}
    )
    issue = rejected(model, {"edit": "remove_parameter", "id": "spare"})
    assert "'find'" in issue["message"]


def test_a_param_lookalike_is_not_a_reference() -> None:
    model = shop()
    model["components"][-1]["params"] = {
        "note": {"$param": "spare", "also": 1},
        "list": [{"$param": 3}],
    }
    removed = applied(
        model,
        {"edit": "set_experiment", "id": "base", "scenarios": [{"id": "x", "set": {}}, "odd"]},
        {"edit": "remove_parameter", "id": "spare"},
        {"edit": "set_experiment", "id": "base", "scenarios": []},
    )
    assert "spare" not in removed["parameters"]


# --- experiments and scenarios ---------------------------------------------------------


def test_set_experiment_changes_the_fields_given() -> None:
    model = applied(shop(), {"edit": "set_experiment", "id": "base", "replications": 20, "seed": 7})
    assert model["experiments"][0]["replications"] == 20
    assert model["experiments"][0]["seed"] == 7
    assert model["experiments"][0]["length"] == "8 h"


def test_set_experiment_with_a_new_id_starts_from_the_base_defaults() -> None:
    model = applied(shop(), {"edit": "set_experiment", "id": "long", "length": "40 h"})
    assert model["experiments"][1] == {
        "id": "long",
        "length": "40 h",
        "warmup": "0 s",
        "replications": 30,
    }
    assert applied(shop(), {"edit": "set_experiment", "id": "plain"})["experiments"][1] == {
        "id": "plain",
        "length": "8 h",
        "warmup": "0 s",
        "replications": 30,
    }


def test_set_experiment_that_breaks_the_schema_is_e180() -> None:
    issue = rejected(shop(), {"edit": "set_experiment", "id": "base", "scenarios": 3})
    assert "schema" in issue["message"]


def test_remove_experiment_removes_it() -> None:
    model = applied(
        shop(),
        {"edit": "set_experiment", "id": "long"},
        {"edit": "remove_experiment", "id": "base"},
    )
    assert [item["id"] for item in model["experiments"]] == ["long"]


def test_remove_experiment_of_an_unknown_id_is_e180() -> None:
    issue = rejected(shop(), {"edit": "remove_experiment", "id": "long"})
    assert "'long'" in issue["message"]


def test_set_scenario_adds_or_replaces_a_scenario() -> None:
    model = applied(
        shop(),
        {"edit": "set_scenario", "experiment_id": "base", "id": "more", "set": {"spare": 4}},
        {"edit": "set_scenario", "experiment_id": "base", "id": "fewer", "set": {"tills": 1}},
    )
    assert model["experiments"][0]["scenarios"] == [
        {"id": "more", "set": {"spare": 4}},
        {"id": "fewer", "set": {"tills": 1}},
    ]


def test_set_scenario_creates_the_scenarios_list() -> None:
    model = applied(
        shop(),
        {"edit": "set_experiment", "id": "long"},
        {"edit": "set_scenario", "experiment_id": "long", "id": "two", "set": {"tills": 2}},
    )
    assert model["experiments"][1]["scenarios"] == [{"id": "two", "set": {"tills": 2}}]


def test_set_scenario_in_an_unknown_experiment_is_e180() -> None:
    issue = rejected(
        shop(), {"edit": "set_scenario", "experiment_id": "long", "id": "two", "set": {}}
    )
    assert "'long'" in issue["message"]


def test_set_scenario_naming_an_unknown_parameter_is_e180() -> None:
    issue = rejected(
        shop(), {"edit": "set_scenario", "experiment_id": "base", "id": "two", "set": {"speed": 1}}
    )
    assert "'speed'" in issue["message"]


def test_scenarios_that_are_not_a_list_cannot_take_a_scenario() -> None:
    model = shop()
    model["experiments"][0]["scenarios"] = "odd"
    issue = rejected(
        model, {"edit": "set_scenario", "experiment_id": "base", "id": "two", "set": {}}
    )
    assert "'base'" in issue["message"]
    issue = rejected(model, {"edit": "remove_scenario", "experiment_id": "base", "id": "more"})
    assert "'more'" in issue["message"]


def test_remove_scenario_removes_it() -> None:
    model = applied(shop(), {"edit": "remove_scenario", "experiment_id": "base", "id": "more"})
    assert model["experiments"][0]["scenarios"] == []


def test_remove_scenario_in_an_unknown_experiment_is_e180() -> None:
    issue = rejected(shop(), {"edit": "remove_scenario", "experiment_id": "long", "id": "more"})
    assert "'long'" in issue["message"]


def test_remove_scenario_the_experiment_does_not_have_is_e180() -> None:
    issue = rejected(shop(), {"edit": "remove_scenario", "experiment_id": "base", "id": "less"})
    assert "'less'" in issue["message"]


# --- set_path and remove_path ----------------------------------------------------------


def test_set_path_sets_values_under_the_keys_it_reaches() -> None:
    model = applied(
        shop(),
        {"edit": "set_path", "path": "/meta/description", "value": "A shop"},
        {"edit": "set_path", "path": "/run/fidelity", "value": "standard"},
        {"edit": "set_path", "path": "/objectives/0/sense", "value": "maximize"},
        {
            "edit": "set_path",
            "path": "/constraints/-",
            "value": {"id": "q", "metric": "till.queue_length.max", "op": "<=", "value": 5},
        },
        {
            "edit": "set_path",
            "path": "/experiments/0/search",
            "value": {"objective": "wait", "budget": 3},
        },
        {"edit": "set_path", "path": "/experiments/0/search/budget", "value": 4},
    )
    assert model["meta"] == {"name": "Shop", "description": "A shop"}
    assert model["objectives"][0]["sense"] == "maximize"
    assert model["constraints"][1]["id"] == "q"
    assert model["experiments"][0]["search"] == {"objective": "wait", "budget": 4}


def test_set_path_reaches_variables_and_objective_in_an_optimization_model() -> None:
    outcome = apply_edits(
        plan(),
        [
            {"edit": "set_path", "path": "/variables/0/upper", "value": 12},
            {
                "edit": "set_path",
                "path": "/variables/-",
                "value": {"id": "chairs", "type": "integer"},
            },
            {"edit": "set_path", "path": "/objective/linear/chairs", "value": 1},
        ],
        {},
    )
    assert outcome.model is not None
    assert outcome.model["variables"][0]["upper"] == 12
    assert outcome.model["objective"]["linear"] == {"desks": 3, "chairs": 1}
    assert load_document(outcome.model).issues == ()


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/",
        "/domain",
        "/components/0/id",
        "/parameters/tills",
        "/experiments/0/length",
        "/experiments/x/search",
        "/experiments/0",
        "/variables",
        "/objective/sense",
        "/format_version",
    ],
)
def test_set_path_outside_the_keys_it_reaches_is_e180(path: str) -> None:
    issue = rejected(shop(), {"edit": "set_path", "path": path, "value": 1})
    assert issue["message"] and issue["hint"]


def test_set_path_whose_parent_does_not_exist_is_e180() -> None:
    issue = rejected(shop(), {"edit": "set_path", "path": "/meta/extra/name", "value": "x"})
    assert "'/meta/extra/name'" in issue["message"]


def test_set_path_that_breaks_the_schema_is_e180_with_the_schema_issue() -> None:
    issue = rejected(
        shop(),
        {"edit": "set_label", "id": "till", "label": "x"},
        {"edit": "set_path", "path": "/meta/name", "value": 5},
    )
    assert issue["path"] == "/edits/1"
    assert "/meta/name" in issue["message"]


def test_a_batch_that_passes_the_schema_in_the_end_is_applied() -> None:
    model = applied(
        shop(),
        {"edit": "remove_path", "path": "/meta"},
        {"edit": "set_path", "path": "/meta", "value": {"name": "New"}},
    )
    assert model["meta"] == {"name": "New"}


def test_the_schema_rejection_names_the_edit_after_the_last_passing_state() -> None:
    issue = rejected(
        shop(),
        {"edit": "remove_path", "path": "/meta"},
        {"edit": "set_path", "path": "/meta", "value": {"name": "New"}},
        {"edit": "set_path", "path": "/run", "value": 1},
        {"edit": "set_label", "id": "till", "label": "x"},
    )
    assert issue["path"] == "/edits/2"


def test_remove_path_removes_a_key_or_entry() -> None:
    model = applied(
        shop(),
        {"edit": "remove_path", "path": "/constraints/0"},
        {"edit": "remove_path", "path": "/objectives"},
        {"edit": "remove_path", "path": "/run"},
    )
    assert model["constraints"] == []
    assert "objectives" not in model and "run" not in model


@pytest.mark.parametrize(
    "path", ["/meta/author", "/constraints/3", "/constraints/-", "/meta/name/x", "/domain"]
)
def test_remove_path_of_a_path_that_does_not_exist_or_is_out_of_reach_is_e180(path: str) -> None:
    issue = rejected(shop(), {"edit": "remove_path", "path": path})
    assert issue["message"] and issue["hint"]


def test_remove_path_that_breaks_the_schema_is_e180() -> None:
    outcome = apply_edits(plan(), [{"edit": "remove_path", "path": "/objective"}], {})
    assert [issue.code for issue in outcome.issues] == ["E180"]


# --- set_ui and set_label --------------------------------------------------------------


def test_set_ui_replaces_the_ui_object() -> None:
    model = applied(
        shop(),
        {"edit": "set_ui", "id": "till", "ui": {"x": 50}},
        {"edit": "set_ui", "id": "exit", "ui": {}},
    )
    assert component(model, "till")["ui"] == {"x": 50}
    assert component(model, "exit")["ui"] == {}


def test_set_ui_of_an_unknown_component_is_e180() -> None:
    issue = rejected(shop(), {"edit": "set_ui", "id": "pump", "ui": {}})
    assert "'pump'" in issue["message"]


def test_set_label_sets_or_removes_the_label() -> None:
    model = applied(
        shop(),
        {"edit": "set_label", "id": "exit", "label": "Door"},
        {"edit": "set_label", "id": "till", "label": None},
    )
    assert component(model, "exit")["label"] == "Door"
    assert "label" not in component(model, "till")
    assert applied(shop(), {"edit": "set_label", "id": "exit", "label": None}) == shop()


def test_set_label_of_an_unknown_component_is_e180() -> None:
    issue = rejected(shop(), {"edit": "set_label", "id": "pump", "label": "x"})
    assert "'pump'" in issue["message"]


def test_the_first_component_with_an_id_is_the_one_edited() -> None:
    model = shop()
    model["components"].append({"id": "till", "type": "sink", "params": {}})
    edited = applied(model, {"edit": "set_label", "id": "till", "label": "First"})
    assert edited["components"][2]["label"] == "First"
    assert "label" not in edited["components"][-1]


# --- no edit raises, whatever shape the model is in (review of PR #35) ------------------

# One plausible edit of each kind, against the names of the shop model.
EVERY_KIND: list[dict[str, Any]] = [
    {"edit": "add_component", "id": "bin", "type": "sink", "params": {}},
    {"edit": "remove_component", "id": "till"},
    {"edit": "rename_component", "id": "till", "new_id": "counter"},
    {"edit": "set_setting", "id": "till", "path": "/capacity", "value": 2},
    {"edit": "connect", "from": "till.out", "to": "exit.in"},
    {"edit": "disconnect", "from": "till.out"},
    {"edit": "set_parameter", "id": "tills", "value": 2},
    {"edit": "remove_parameter", "id": "spare"},
    {"edit": "set_experiment", "id": "base", "replications": 5},
    {"edit": "remove_experiment", "id": "base"},
    {"edit": "set_scenario", "experiment_id": "base", "id": "more", "set": {"spare": 1}},
    {"edit": "remove_scenario", "experiment_id": "base", "id": "more"},
    {"edit": "set_path", "path": "/objectives/0/sense", "value": "maximize"},
    {"edit": "remove_path", "path": "/constraints/0"},
    {"edit": "set_ui", "id": "till", "ui": {"x": 1}},
    {"edit": "set_label", "id": "till", "label": "Till"},
]

_BROKEN_VALUES: list[object] = ["absent", None, "text", [], {}, [None, 3, "x"]]


def _broken_models() -> list[tuple[str, dict[str, Any]]]:
    """The shop and plan models with one collection, or one entry's collection, absent
    or set to a value of the wrong kind."""
    places: list[tuple[str, ...]] = [
        ("components",),
        ("connections",),
        ("parameters",),
        ("experiments",),
        ("objectives",),
        ("constraints",),
        ("meta",),
        ("run",),
        ("components", "2"),
        ("components", "2", "params"),
        ("components", "2", "type"),
        ("components", "2", "id"),
        ("components", "4", "params", "target"),
        ("connections", "0"),
        ("connections", "0", "from"),
        ("connections", "0", "to"),
        ("parameters", "spare"),
        ("experiments", "0"),
        ("experiments", "0", "id"),
        ("experiments", "0", "scenarios"),
        ("experiments", "0", "scenarios", "0"),
        ("experiments", "0", "scenarios", "0", "id"),
        ("experiments", "0", "scenarios", "0", "set"),
        ("experiments", "0", "search"),
        ("objectives", "0"),
        ("objectives", "0", "metric"),
    ]
    models: list[tuple[str, dict[str, Any]]] = []
    for place in places:
        for value in _BROKEN_VALUES:
            model = shop()
            parent: Any = model
            for segment in place[:-1]:
                parent = parent[int(segment)] if isinstance(parent, list) else parent[segment]
            last = place[-1]
            key: Any = int(last) if isinstance(parent, list) else last
            if value == "absent" and isinstance(parent, dict):
                parent.pop(key, None)
            elif value == "absent":
                del parent[key]
            else:
                parent[key] = copy.deepcopy(value)
            models.append(("/" + "/".join(place) + f"={value!r}", model))
    for key in ("variables", "objective", "constraints", "meta"):
        for value in _BROKEN_VALUES:
            model = plan()
            if value == "absent":
                del model[key]
            else:
                model[key] = copy.deepcopy(value)
            models.append((f"plan /{key}={value!r}", model))
    return models


BROKEN = _broken_models()


@pytest.mark.parametrize("kind", EVERY_KIND, ids=[edit["edit"] for edit in EVERY_KIND])
def test_no_edit_raises_on_a_model_of_any_shape(kind: dict[str, Any]) -> None:
    """Every kind, on models with each collection absent, null or of the wrong kind, is
    applied or rejected with E180; none raises (the review of PR #35 found
    ``remove_experiment`` and ``remove_parameter`` raising, which the API turned into 500)."""
    assert [edit["edit"] for edit in EVERY_KIND] == list(EDIT_KINDS)
    for name, model in BROKEN:
        outcome = apply_edits(model, [kind], PROCESS_TYPES)
        assert outcome.model is not None or [issue.code for issue in outcome.issues] == ["E180"], (
            name
        )


def test_remove_experiment_in_an_optimization_model_is_e180() -> None:
    outcome = apply_edits(plan(), [{"edit": "remove_experiment", "id": "base"}], {})
    assert [issue.code for issue in outcome.issues] == ["E180"]
    assert "'base'" in outcome.issues[0].message


def test_a_null_scenario_set_does_not_stop_removing_a_parameter() -> None:
    model = applied(
        shop(),
        {"edit": "set_experiment", "id": "base", "scenarios": [{"id": "s", "set": None}]},
        {"edit": "remove_parameter", "id": "spare"},
        {"edit": "set_experiment", "id": "base", "scenarios": []},
    )
    assert "spare" not in model["parameters"]


def test_an_edit_that_fails_unexpectedly_is_e180_without_exception_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import lcsim.model.edits as edits

    def broken(*_args: object) -> None:
        raise KeyError("secret detail")

    monkeypatch.setitem(edits._APPLY, "set_label", broken)
    outcome = apply(shop(), {"edit": "set_label", "id": "till", "label": "x"})
    assert outcome.model is None
    [issue] = outcome.issues
    assert issue.code == "E180" and issue.path == "/edits/0"
    assert "secret" not in issue.message and "KeyError" not in issue.message


def test_set_parameter_on_a_parameter_that_is_not_an_object_is_e180() -> None:
    model = shop()
    model["parameters"]["spare"] = 5
    issue = rejected(model, {"edit": "set_parameter", "id": "spare", "value": 1})
    assert "'spare'" in issue["message"]
