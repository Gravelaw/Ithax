"""The meaning pass, part A (AKS-89): engines, identifiers, settings and connections.

Spec 1 "Top-level keys" (engine lookup), "Identifiers", "Components and ports",
"Validation issues"; spec 2 "Block reference" (``pool``, ``target``, ``routes``,
``weights``) and its "Targets" rule. Each test names the rule it checks.
"""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from lcsim.model.catalogue import DOMAINS
from lcsim.model.issues import Issue
from lcsim.model.loading import (
    ModelLoadError,
    build_document,
    load_document,
    load_model,
    load_text,
)
from lcsim.model.model import Model
from lcsim.model.validation import (
    IDENTIFIER_PATTERN,
    RESERVED_COMPONENT_IDS,
    RESERVED_SCENARIO_ID,
    STAND_IN_ENGINES,
    InstalledEngine,
    connection_issues,
    engine_issues,
    identifier_issues,
    meaning_pass,
    setting_issues,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = sorted((ROOT / "examples").glob("*.json"))
COFFEE_SHOP: dict[str, Any] = json.loads(
    (ROOT / "examples" / "coffee_shop.json").read_text(encoding="utf-8")
)

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

SHIFTS = [{"start": "0 h", "end": "8 h", "capacity": 1}]
EXPONENTIAL = {"dist": "exponential", "mean": "10 min"}


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


def with_components(*components: dict[str, Any]) -> dict[str, Any]:
    document = coffee()
    document["components"] += list(components)
    return document


def schedule(name: str, target: str) -> dict[str, Any]:
    return {"id": name, "type": "schedule", "params": {"target": target, "shifts": SHIFTS}}


def failure(name: str, target: str) -> dict[str, Any]:
    return {
        "id": name,
        "type": "failure",
        "params": {
            "target": target,
            "time_to_failure": EXPONENTIAL,
            "time_to_repair": EXPONENTIAL,
        },
    }


def branch(
    routes: list[str], *, rule: str = "shortest_queue", weights: dict[str, Any] | None = None
) -> dict[str, Any]:
    params: dict[str, Any] = {"routes": routes, "rule": rule}
    if weights is not None:
        params["weights"] = weights
    return {"id": "split", "type": "branch", "params": params}


def with_branch(component: dict[str, Any], routes: list[str]) -> dict[str, Any]:
    """The coffee shop with ``component`` (a branch called 'split') between the till and
    the exit, each of ``routes`` connected to the exit."""
    document = coffee()
    document["components"].insert(2, component)
    document["connections"] = [
        {"from": "arrivals.out", "to": "till.in"},
        {"from": "till.out", "to": "split.in"},
        *({"from": f"split.{route}", "to": "exit.in"} for route in routes),
    ]
    return document


# --- examples ---------------------------------------------------------------------------------


@pytest.mark.parametrize("path", EXAMPLES, ids=[path.stem for path in EXAMPLES])
def test_every_example_loads_with_zero_issues(path: Path) -> None:
    result = load_document(json.loads(path.read_text(encoding="utf-8")))
    assert result.issues == ()
    assert result.model is not None
    assert meaning_pass(result.model) == []


def test_the_product_mix_passes_the_meaning_pass() -> None:
    result = load_document(PRODUCT_MIX)
    assert result.issues == ()
    assert result.model is not None


# --- E102: engine lookup (spec 1 "Top-level keys") ----------------------------------------------


# The engines a Phase 1 install has from M2: the discovered process adapter ``simpy`` and the
# model layer's stand-in for ``optimization`` (until M5).
PHASE_1_ENGINES = (InstalledEngine("simpy", ("process",)), *STAND_IN_ENGINES)


def test_a_stand_in_remains_for_optimization_only() -> None:
    # Spec 1 "Top-level keys": from M2 the process adapter is discovered; the stand-in for
    # optimization stays until M5.
    assert STAND_IN_ENGINES == (InstalledEngine(None, ("optimization",)),)
    assert set(DOMAINS) == {"process", "optimization"}


@pytest.mark.parametrize("domain", DOMAINS)
def test_one_engine_runs_each_phase_1_domain(domain: str) -> None:
    assert engine_issues(domain, None, PHASE_1_ENGINES) == []


def test_a_stand_in_accepts_any_engine_name() -> None:
    # A stand-in has no adapter name, so run.engine cannot be checked for optimization
    # before M5.
    assert engine_issues("optimization", "highs", STAND_IN_ENGINES) == []
    document = copy.deepcopy(PRODUCT_MIX)
    document["run"] = {"target": "local", "fidelity": "standard", "engine": "highs"}
    assert load_document(document).issues == ()


def test_run_engine_is_checked_for_process_from_m2() -> None:
    # The loader's default engines are the discovered adapters (the installed entry point
    # ``simpy``) and the optimization stand-in.
    document = coffee()
    document["run"]["engine"] = "simpy"
    assert load_document(document).issues == ()
    document["run"]["engine"] = "salabim"
    result = load_document(document)
    assert result.model is None
    [issue] = result.issues
    assert (issue.code, issue.path, issue.component) == ("E102", "/run/engine", None)
    assert "'salabim'" in issue.message
    assert issue.hint == "Name one of: 'simpy'."


def test_the_loader_takes_the_engines_it_is_given() -> None:
    [issue] = load_document(coffee(), engines=()).issues
    assert (issue.code, issue.path) == ("E102", "/domain")
    assert issue.hint == "Install an engine for this domain."
    [issue] = build_document(coffee(), engines=TWO_PROCESS_ENGINES).issues
    assert (issue.code, issue.path) == ("E102", "/run/engine")
    text = json.dumps(coffee())
    assert load_text(text, engines=PHASE_1_ENGINES).model is not None


def test_load_model_takes_the_engines_it_is_given(tmp_path: Path) -> None:
    path = tmp_path / "coffee.json"
    path.write_text(json.dumps(coffee()), encoding="utf-8")
    assert load_model(path, engines=PHASE_1_ENGINES).meta.name == "Coffee shop"
    with pytest.raises(ModelLoadError) as raised:
        load_model(path, engines=STAND_IN_ENGINES)
    assert [issue.code for issue in raised.value.issues] == ["E102"]


def test_no_engine_for_the_domain() -> None:
    [issue] = engine_issues("physics", None, PHASE_1_ENGINES)
    assert (issue.code, issue.path, issue.component) == ("E102", "/domain", None)
    assert "'domain'" in issue.message
    assert "'physics'" in issue.message
    assert issue.hint == "Set 'domain' to 'optimization' or 'process'."


def test_no_engine_installed_at_all() -> None:
    [issue] = engine_issues("process", None, ())
    assert issue.code == "E102"
    assert issue.hint == "Install an engine for this domain."


TWO_PROCESS_ENGINES = (
    InstalledEngine("simpy", ("process",)),
    InstalledEngine("salabim", ("process", "agents")),
    InstalledEngine("highs", ("optimization",)),
)


def test_several_engines_and_no_run_engine() -> None:
    [issue] = engine_issues("process", None, TWO_PROCESS_ENGINES)
    assert (issue.code, issue.path) == ("E102", "/run/engine")
    assert "'engine'" in issue.message
    assert "('simpy' or 'salabim')" in issue.message
    assert issue.hint == "Add 'engine' to 'run', naming one of: 'simpy' or 'salabim'."


def test_run_engine_chooses_among_several() -> None:
    assert engine_issues("process", "salabim", TWO_PROCESS_ENGINES) == []
    assert engine_issues("agents", None, TWO_PROCESS_ENGINES) == []
    assert engine_issues("optimization", "highs", TWO_PROCESS_ENGINES) == []


@pytest.mark.parametrize("name", ["highs", "nothing"])
def test_run_engine_that_does_not_handle_the_domain(name: str) -> None:
    [issue] = engine_issues("process", name, TWO_PROCESS_ENGINES)
    assert (issue.code, issue.path) == ("E102", "/run/engine")
    assert f"'{name}'" in issue.message
    assert "no installed engine of that name handles the domain 'process'" in issue.message
    assert issue.hint == "Name one of: 'simpy' or 'salabim'."


def test_run_engine_naming_two_installed_engines() -> None:
    twins = (InstalledEngine("simpy", ("process",)), InstalledEngine("simpy", ("process",)))
    [issue] = engine_issues("process", "simpy", twins)
    assert issue.code == "E102"
    assert "several installed engines of that name" in issue.message


def test_several_stand_ins_without_names() -> None:
    stand_ins = (InstalledEngine(None, ("process",)), InstalledEngine(None, ("process",)))
    [issue] = engine_issues("process", None, stand_ins)
    assert issue.message == (
        "Several installed engines handle the domain 'process', and 'run' names no "
        "'engine' to choose one."
    )
    assert issue.hint == "Add 'engine' to 'run'."
    [issue] = engine_issues("process", "simpy", stand_ins)
    assert issue.hint == "Remove 'engine' from 'run'."


def test_the_loader_reports_e102_before_building() -> None:
    document = coffee()
    document["domain"] = "physics"
    document["components"][0]["type"] = "robot"  # not reported: nothing is built
    result = load_document(document)
    assert result.model is None
    assert codes(list(result.issues)) == [("E102", "/domain")]


# --- E110, E111, E112: identifiers (spec 1 "Identifiers") ----------------------------------------


@pytest.mark.parametrize("identifier", ["a", "door", "t_2", "a" * 64, "z9_"])
def test_valid_identifiers(identifier: str) -> None:
    assert IDENTIFIER_PATTERN.fullmatch(identifier)
    document = coffee()
    document["components"][2]["id"] = identifier
    document["connections"][1]["to"] = f"{identifier}.in"
    assert load_document(document).issues == ()


@pytest.mark.parametrize(
    "identifier",
    ["Till", "1till", "_till", "till-2", "a" * 65, "", "till\n", "tíll", "till 2", "ti.ll"],
)
def test_an_identifier_off_the_pattern_is_e111(identifier: str) -> None:
    document = coffee()
    document["components"][2]["id"] = identifier
    issues = identifier_issues(built(document))
    assert codes(issues) == [("E111", "/components/2/id")]
    [issue] = issues
    assert issue.component == identifier
    assert f"'{identifier}'" in issue.message
    assert "'id'" in issue.message
    assert "component 3" in issue.message


def test_reserved_component_ids_are_e112() -> None:
    assert set(RESERVED_COMPONENT_IDS) == {"model", "optimizer"}
    for identifier in RESERVED_COMPONENT_IDS:
        document = coffee()
        document["components"][2]["id"] = identifier
        [issue] = identifier_issues(built(document))
        assert (issue.code, issue.path, issue.component) == (
            "E112",
            "/components/2/id",
            identifier,
        )
        assert f"'{identifier}'" in issue.message
        assert "reserved" in issue.message


def test_a_reserved_word_in_another_case_is_only_e111() -> None:
    document = coffee()
    document["components"][2]["id"] = "Model"
    assert [issue.code for issue in identifier_issues(built(document))] == ["E111"]


def test_reserved_component_ids_are_allowed_elsewhere() -> None:
    document = coffee()
    document["experiments"][0]["id"] = "model"
    document["parameters"]["optimizer"] = {"value": 1, "type": "integer"}
    assert identifier_issues(built(document)) == []


def test_a_repeated_component_id_is_e110_at_each_later_use() -> None:
    document = with_components(
        {"id": "exit", "type": "sink", "params": {}},
        {"id": "exit", "type": "sink", "params": {}},
    )
    issues = identifier_issues(built(document))
    assert codes(issues) == [("E110", "/components/3/id"), ("E110", "/components/4/id")]
    assert issues[0].component == "exit"
    assert issues[1].message == (
        "The 'id' of component 5 is 'exit', which component 3 already uses; each component "
        "needs its own id."
    )


def test_a_repeated_invalid_id_is_e111_and_e110() -> None:
    document = coffee()
    document["components"][1]["id"] = "Exit"
    document["components"][2]["id"] = "Exit"
    assert codes(identifier_issues(built(document))) == [
        ("E111", "/components/1/id"),
        ("E111", "/components/2/id"),
        ("E110", "/components/2/id"),
    ]


def test_ids_need_only_be_unique_within_their_list() -> None:
    document = coffee()
    document["experiments"][0]["id"] = "till"
    document["parameters"]["till"] = {"value": 1, "type": "integer"}
    document["objectives"] = [{"id": "till", "metric": "till.wait.mean", "sense": "minimize"}]
    document["constraints"] = [
        {"id": "till", "metric": "till.utilization", "op": "<=", "value": 0.9}
    ]
    assert identifier_issues(built(document)) == []


def test_a_parameter_id_off_the_pattern() -> None:
    document = coffee()
    document["parameters"]["Tills"] = document["parameters"].pop("tills")
    [issue] = identifier_issues(built(document))
    assert (issue.code, issue.path, issue.component) == ("E111", "/parameters/Tills", None)
    assert "'Tills'" in issue.message


def test_experiment_ids() -> None:
    document = coffee()
    document["experiments"].append(copy.deepcopy(document["experiments"][0]))
    document["experiments"].append(dict(document["experiments"][0], id="Long run"))
    issues = identifier_issues(built(document))
    assert codes(issues) == [("E110", "/experiments/1/id"), ("E111", "/experiments/2/id")]
    assert "experiment 1 already uses" in issues[0].message


SCENARIOS = [{"id": "one", "set": {"tills": 1}}, {"id": "two", "set": {"tills": 2}}]


def test_scenario_ids_are_unique_within_one_experiment() -> None:
    document = coffee()
    document["experiments"][0]["scenarios"] = [*copy.deepcopy(SCENARIOS), {"id": "one", "set": {}}]
    issues = identifier_issues(built(document))
    assert codes(issues) == [("E110", "/experiments/0/scenarios/2/id")]
    assert "of experiment 'base'" in issues[0].message
    assert "scenario 1 already uses" in issues[0].message


def test_two_experiments_may_reuse_scenario_ids() -> None:
    document = coffee()
    document["experiments"][0]["scenarios"] = copy.deepcopy(SCENARIOS)
    document["experiments"].append(dict(document["experiments"][0], id="other"))
    assert identifier_issues(built(document)) == []


def test_a_scenario_id_off_the_pattern() -> None:
    document = coffee()
    document["experiments"][0]["scenarios"] = [{"id": "Two tills", "set": {"tills": 2}}]
    assert codes(identifier_issues(built(document))) == [("E111", "/experiments/0/scenarios/0/id")]


def test_a_scenario_the_file_calls_default_is_e112() -> None:
    assert RESERVED_SCENARIO_ID == "default"
    document = coffee()
    document["experiments"][0]["scenarios"] = [{"id": "default", "set": {}}]
    issues = identifier_issues(built(document))
    assert codes(issues) == [("E112", "/experiments/0/scenarios/0/id")]
    assert issues[0].component is None
    assert "'default'" in issues[0].message


@pytest.mark.parametrize("scenarios", [None, []])
def test_the_added_default_scenario_is_not_e112(scenarios: list[Any] | None) -> None:
    document = coffee()
    if scenarios is not None:
        document["experiments"][0]["scenarios"] = scenarios
    model = built(document)
    assert model.experiments[0].default_scenario_added is True
    assert model.experiments[0].scenarios[0].id == "default"
    assert identifier_issues(model) == []


def test_a_listed_scenario_is_not_added() -> None:
    document = coffee()
    document["experiments"][0]["scenarios"] = copy.deepcopy(SCENARIOS)
    assert built(document).experiments[0].default_scenario_added is False


def test_objective_and_constraint_ids_of_a_process_model() -> None:
    document = coffee()
    objective = {"id": "wait", "metric": "till.wait.mean", "sense": "minimize"}
    constraint = {"id": "Busy", "metric": "till.utilization", "op": "<=", "value": 0.9}
    document["objectives"] = [objective, dict(objective)]
    document["constraints"] = [constraint]
    assert codes(identifier_issues(built(document))) == [
        ("E110", "/objectives/1/id"),
        ("E111", "/constraints/0/id"),
    ]


def test_variable_and_constraint_ids_of_an_optimization_model() -> None:
    document = copy.deepcopy(PRODUCT_MIX)
    document["variables"][1]["id"] = "chairs"
    document["constraints"][1]["id"] = "wood"
    document["variables"].append({"id": "Desks", "type": "integer"})
    issues = identifier_issues(built(document))
    assert codes(issues) == [
        ("E110", "/constraints/1/id"),
        ("E110", "/variables/1/id"),
        ("E111", "/variables/2/id"),
    ]
    assert all(issue.component is None for issue in issues)
    assert "each variable needs its own id" in issues[1].message


def test_branch_routes_are_identifiers_unique_within_the_branch() -> None:
    document = with_branch(branch(["a", "Big", "a"]), ["a", "Big"])
    issues = identifier_issues(built(document))
    assert codes(issues) == [
        ("E111", "/components/2/params/routes/1"),
        ("E110", "/components/2/params/routes/2"),
    ]
    assert all(issue.component == "split" for issue in issues)
    assert all("'routes'" in issue.message and "'split'" in issue.message for issue in issues)
    assert issues[1].hint == "Remove the repeated route, or rename it."


def test_two_branches_may_share_route_names() -> None:
    document = with_branch(branch(["a", "b"]), ["a", "b"])
    other = branch(["a"])
    other["id"] = "split_2"
    document["components"].append(other)
    document["connections"] += [
        {"from": "split_2.a", "to": "exit.in"},
    ]
    assert identifier_issues(built(document)) == []


# --- E124, E125, weights: settings that name things (spec 2 "Block reference") --------------------


def with_pool(pool: str) -> dict[str, Any]:
    document = with_components({"id": "staff", "type": "resource_pool", "params": {"capacity": 1}})
    document["components"][1]["params"]["pool"] = pool
    return document


def test_a_pool_that_names_a_resource_pool() -> None:
    assert setting_issues(built(with_pool("staff"))) == []


def test_a_pool_that_names_no_component_is_e124() -> None:
    [issue] = setting_issues(built(with_pool("staf")))
    assert (issue.code, issue.path, issue.component) == (
        "E124",
        "/components/1/params/pool",
        "till",
    )
    assert (
        issue.message == "The 'pool' setting of 'till' names 'staf', but no component has that id."
    )
    assert issue.hint == "Name a resource_pool that is in the model, or add one called 'staf'."


def test_a_pool_that_names_a_component_of_another_type_is_e124() -> None:
    [issue] = setting_issues(built(with_pool("exit")))
    assert (issue.code, issue.path) == ("E124", "/components/1/params/pool")
    assert issue.message == (
        "The 'pool' setting of 'till' names 'exit', which is a sink; it must name a resource_pool."
    )


@pytest.mark.parametrize(
    ("component", "target", "fits"),
    [
        (schedule, "till", True),
        (schedule, "staff", True),
        (schedule, "exit", False),
        (schedule, "nobody", False),
        (failure, "till", True),
        (failure, "staff", False),
        (failure, "arrivals", False),
        (failure, "nobody", False),
    ],
)
def test_targets(component: Any, target: str, fits: bool) -> None:
    document = with_components(
        {"id": "staff", "type": "resource_pool", "params": {"capacity": 1}},
        component("rule", target),
    )
    issues = setting_issues(built(document))
    if fits:
        assert issues == []
    else:
        [issue] = issues
        assert (issue.code, issue.path, issue.component) == (
            "E124",
            "/components/4/params/target",
            "rule",
        )
        assert f"'{target}'" in issue.message
        assert "'target'" in issue.message


def test_a_schedule_target_lists_both_types() -> None:
    [issue] = setting_issues(built(with_components(schedule("rule", "exit"))))
    assert issue.message.endswith("it must name a server or a resource_pool.")


def test_two_schedules_on_one_server_are_e125() -> None:
    document = with_components(
        schedule("day", "till"), schedule("night", "till"), schedule("weekend", "till")
    )
    issues = setting_issues(built(document))
    assert codes(issues) == [
        ("E125", "/components/4/params/target"),
        ("E125", "/components/5/params/target"),
    ]
    assert [issue.component for issue in issues] == ["night", "weekend"]
    assert issues[0].message == (
        "The 'target' of 'night' is 'till', which the schedule 'day' already targets; a "
        "server or resource pool may have only one schedule."
    )
    assert issues[0].hint == "Combine them into 'day', or remove 'night'."


def test_two_schedules_on_one_pool_are_e125() -> None:
    document = with_components(
        {"id": "staff", "type": "resource_pool", "params": {"capacity": 2}},
        schedule("day", "staff"),
        schedule("night", "staff"),
    )
    assert codes(setting_issues(built(document))) == [("E125", "/components/5/params/target")]


def test_two_failures_on_one_server_are_e125() -> None:
    document = with_components(failure("wear", "till"), failure("jam", "till"))
    [issue] = setting_issues(built(document))
    assert (issue.code, issue.component) == ("E125", "jam")
    assert issue.message.endswith("a server may have only one failure.")


def test_one_schedule_and_one_failure_per_target_are_allowed() -> None:
    document = with_components(
        {"id": "staff", "type": "resource_pool", "params": {"capacity": 2}},
        schedule("day", "till"),
        failure("wear", "till"),
        schedule("rota", "staff"),
    )
    assert setting_issues(built(document)) == []


def test_a_wrong_target_does_not_count_towards_e125() -> None:
    document = with_components(schedule("day", "nobody"), schedule("night", "nobody"))
    assert [issue.code for issue in setting_issues(built(document))] == ["E124", "E124"]


def test_weights_keyed_by_the_routes() -> None:
    document = with_branch(
        branch(["a", "b"], rule="probability", weights={"a": 1, "b": 3}), ["a", "b"]
    )
    assert setting_issues(built(document)) == []


def test_a_weight_for_no_route_is_e121_and_a_route_without_weight_e122() -> None:
    document = with_branch(
        branch(["a", "b"], rule="probability", weights={"a": 1, "c": 3}), ["a", "b"]
    )
    issues = setting_issues(built(document))
    assert codes(issues) == [
        ("E121", "/components/2/params/weights/c"),
        ("E122", "/components/2/params/weights/b"),
    ]
    assert all(issue.component == "split" for issue in issues)
    assert issues[0].message == (
        "The 'weights' of 'split' has a key 'c', which is not one of its 'routes' ('a' or 'b')."
    )
    assert issues[1].message == (
        "The 'weights' of 'split' has no entry for 'b', which is one of its 'routes'."
    )


def test_weights_with_no_routes() -> None:
    document = with_components(branch([], rule="probability", weights={"a": 1}))
    [issue] = setting_issues(built(document))
    assert issue.code == "E121"
    assert issue.message.endswith("but its 'routes' is empty.")


def test_a_repeated_route_needs_one_weight() -> None:
    document = with_branch(branch(["a", "a"], rule="probability", weights={"a": 1}), ["a"])
    assert setting_issues(built(document)) == []


def test_no_weights_for_shortest_queue() -> None:
    document = with_branch(branch(["a", "b"]), ["a", "b"])
    assert setting_issues(built(document)) == []


# --- E130, E131, E132, E161: connections (spec 1 "Components and ports") -------------------------


def test_the_coffee_shop_connections() -> None:
    assert connection_issues(built(coffee())) == []


def test_an_unknown_component_is_e130_and_leaves_the_port_unconnected() -> None:
    document = coffee()
    document["connections"][1]["from"] = "tll.out"
    issues = connection_issues(built(document))
    assert codes(issues) == [("E130", "/connections/1/from"), ("E131", "/components/1")]
    assert issues[0].component is None
    assert issues[0].message == (
        "The 'from' end of connection 2 is 'tll.out', but no component has the id 'tll'."
    )
    assert issues[0].hint == (
        "Correct the id; the model's components are 'arrivals', 'till' and 'exit'."
    )


def test_an_unknown_destination_still_connects_the_output() -> None:
    document = coffee()
    document["connections"][1]["to"] = "exti.in"
    assert codes(connection_issues(built(document))) == [("E130", "/connections/1/to")]


def test_many_components_are_not_listed_in_the_hint() -> None:
    document = with_components(
        *({"id": f"sink_{index}", "type": "sink", "params": {}} for index in range(10))
    )
    document["connections"][1]["to"] = "nowhere.in"
    [issue] = connection_issues(built(document))
    assert issue.hint == "Correct the id to one of the model's components."


@pytest.mark.parametrize(
    ("key", "end", "fragment", "hint"),
    [
        ("from", "till.in", "has no output port 'in'", "Use 'out', the output port of a server."),
        ("to", "exit.out", "has no input port 'out'", "Use 'in', the input port of a sink."),
        (
            "from",
            "exit.out",
            "'exit' (a sink) has no output port 'out'",
            "A sink has no output port; connect another block.",
        ),
        (
            "to",
            "arrivals.in",
            "'arrivals' (a source) has no input port 'in'",
            "A source has no input port; connect another block.",
        ),
    ],
)
def test_a_port_the_component_does_not_have_is_e130(
    key: str, end: str, fragment: str, hint: str
) -> None:
    document = coffee()
    document["connections"].append({"from": "till.out", "to": "exit.in"} | {key: end})
    if key == "from":
        document["connections"][-1]["to"] = "till.in"
    issues = [issue for issue in connection_issues(built(document)) if issue.code == "E130"]
    [issue] = issues
    assert issue.path == f"/connections/2/{key}"
    assert fragment in issue.message
    assert issue.hint == hint


def test_a_connection_in_a_model_without_components() -> None:
    document = coffee()
    document["components"] = []
    document["connections"] = [{"from": "arrivals.out", "to": "till.in"}]
    issues = connection_issues(built(document))
    assert codes(issues) == [("E130", "/connections/0/from"), ("E130", "/connections/0/to")]
    assert issues[0].hint == "Add the component, or remove the connection."


def test_a_port_on_a_component_without_ports() -> None:
    document = with_components({"id": "staff", "type": "resource_pool", "params": {"capacity": 1}})
    document["connections"].append({"from": "till.out", "to": "staff.in"})
    issues = connection_issues(built(document))
    assert ("E130", "/connections/2/to") in codes(issues)


def test_a_branch_route_named_as_a_destination_is_e130() -> None:
    # A route is an output port; the branch's only input port is 'in'.
    document = with_branch(branch(["a", "b"]), ["a", "b"])
    document["connections"][3]["to"] = "split.a"
    [issue] = connection_issues(built(document))
    assert (issue.code, issue.path) == ("E130", "/connections/3/to")
    assert issue.message.endswith("but 'split' (a branch) has no input port 'a'.")
    assert issue.hint == "Use 'in', the input port of a branch."


def test_a_branch_lists_its_routes_when_a_port_is_wrong() -> None:
    document = with_branch(branch(["a", "b", "c"]), ["a", "b", "c"])
    document["connections"].append({"from": "split.d", "to": "exit.in"})
    [issue] = connection_issues(built(document))
    assert (issue.code, issue.path, issue.component) == ("E161", "/connections/5/from", None)
    assert issue.message == (
        "The 'from' end of connection 6 is 'split.d', but 'd' is not one of the 'routes' "
        "of 'split'."
    )
    assert issue.hint == "Use one of its routes ('a', 'b' or 'c'), or add 'd' to its 'routes'."


def test_a_branch_input_port_named_as_a_source_is_e161() -> None:
    document = with_branch(branch(["a"]), ["a"])
    document["connections"].append({"from": "split.in", "to": "exit.in"})
    assert codes(connection_issues(built(document))) == [("E161", "/connections/3/from")]


def test_a_branch_with_no_routes() -> None:
    document = with_branch(branch([]), ["a"])
    [issue] = connection_issues(built(document))
    assert issue.code == "E161"
    assert issue.hint == "Add 'a' to the 'routes' of 'split'."


def test_a_second_connection_from_one_output_is_e132() -> None:
    document = with_components(
        {"id": "side", "type": "sink", "params": {}},
        {"id": "back", "type": "sink", "params": {}},
    )
    document["connections"] += [
        {"from": "till.out", "to": "side.in"},
        {"from": "till.out", "to": "back.in"},
    ]
    issues = connection_issues(built(document))
    assert codes(issues) == [("E132", "/connections/2/from"), ("E132", "/connections/3/from")]
    assert issues[1].message == (
        "The 'from' end of connection 4 is 'till.out', which connection 2 already connects; "
        "an output port connects to exactly one input port."
    )


def test_an_input_accepts_any_number_of_connections() -> None:
    document = with_branch(branch(["a", "b", "c"]), ["a", "b", "c"])
    assert connection_issues(built(document)) == []


def test_an_unconnected_output_is_e131_at_the_component() -> None:
    document = coffee()
    del document["connections"][0]
    [issue] = connection_issues(built(document))
    assert (issue.code, issue.path, issue.component) == ("E131", "/components/0", "arrivals")
    assert issue.message == "The 'out' port of 'arrivals' is not connected to anything."
    assert issue.hint == "Connect it to another block or to a sink."


def test_an_unconnected_route_is_e131_at_its_entry() -> None:
    document = with_branch(branch(["a", "b", "b"]), ["a"])
    issues = connection_issues(built(document))
    assert codes(issues) == [("E131", "/components/2/params/routes/1")]
    assert issues[0].message == (
        "The route 'b' of 'split' is not connected to anything; each entry of 'routes' is "
        "an output port."
    )
    assert issues[0].hint == "Connect 'split.b' to another block, or remove 'b' from 'routes'."


def test_blocks_without_ports_need_no_connections() -> None:
    document = with_components(
        {"id": "staff", "type": "resource_pool", "params": {"capacity": 1}},
        schedule("day", "till"),
        failure("wear", "till"),
    )
    assert connection_issues(built(document)) == []


def test_a_repeated_component_id_is_checked_once() -> None:
    document = with_components(
        {"id": "till", "type": "server", "params": {"capacity": 1, "service": EXPONENTIAL}}
    )
    assert connection_issues(built(document)) == []


# --- the pass and the loader ------------------------------------------------------------------


def test_meaning_pass_runs_every_rule_group_in_order() -> None:
    document = with_components(schedule("day", "nobody"))
    document["components"][2]["id"] = "Exit"
    document["connections"][1]["to"] = "Exit.in"
    document["connections"].append({"from": "till.out", "to": "Exit.in"})
    assert codes(meaning_pass(built(document))) == [
        ("E111", "/components/2/id"),
        ("E124", "/components/3/params/target"),
        ("E132", "/connections/2/from"),
    ]


def test_load_document_reports_the_meaning_pass_and_gives_no_model() -> None:
    document = coffee()
    del document["connections"][1]
    result = load_document(document)
    assert result.model is None
    # The exit is now cut off from the source, which the meaning pass also warns of.
    assert codes(list(result.issues)) == [("E131", "/components/1"), ("W200", "/components/2")]
    assert codes(list(result.errors)) == [("E131", "/components/1")]


def test_build_document_skips_the_meaning_pass() -> None:
    document = coffee()
    del document["connections"][1]
    result = build_document(document)
    assert result.issues == ()
    assert result.model is not None


def test_load_model_raises_with_meaning_pass_issues(tmp_path: Path) -> None:
    document = coffee()
    document["components"][2]["id"] = "optimizer"
    document["connections"][1]["to"] = "optimizer.in"
    path = tmp_path / "model.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ModelLoadError) as caught:
        load_model(path)
    assert [issue.code for issue in caught.value.issues] == ["E112"]


def test_meaning_pass_issues_follow_no_building_issue() -> None:
    # A file that does not build gets no meaning pass: its model does not exist.
    document = coffee()
    document["components"][1]["params"]["speed"] = 1
    del document["connections"][1]
    assert codes(list(load_document(document).issues)) == [("E121", "/components/1/params/speed")]
