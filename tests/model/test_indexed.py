"""Indexed optimization models: sets, tables, ``over``, ``for`` and ``terms`` (format 0.2).

Spec 1 "Top-level keys" ("Indexed optimization"), "Versioning", "Identifiers" and the
E100, E175 to E178 rows of "Validation issues"; spec 2 "Mathematical optimization in the
model file" ("Indexed problems": the expansion into the flat layout). AKS-123.
"""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from ithax.model.indexed import expanded_name
from ithax.model.issues import Issue
from ithax.model.loading import load_document
from ithax.model.migration import FORMAT_VERSION
from ithax.model.model import (
    IndexedConstraint,
    IndexedObjective,
    IndexedVariable,
    LinearConstraint,
    LinearObjective,
    LinearProgram,
    Model,
    Table,
    TableRef,
    Term,
    Variable,
)
from ithax.model.schema import schema_pass

ROOT = Path(__file__).resolve().parents[2]
TRANSPORT = ROOT / "benchmarks" / "transport" / "model.json"
PRODUCT_MIX = ROOT / "benchmarks" / "product_mix" / "model.json"
DEPOTS = ("north", "centre", "south")
CUSTOMERS = ("city", "harbour", "park", "market")


def transport() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(TRANSPORT.read_text(encoding="utf-8"))
    return loaded


def product_mix() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(PRODUCT_MIX.read_text(encoding="utf-8"))
    return loaded


def model_of(document: dict[str, Any]) -> Model:
    result = load_document(document)
    assert result.issues == (), [issue.as_dict() for issue in result.issues]
    assert result.model is not None
    return result.model


def issues_of(document: dict[str, Any]) -> list[Issue]:
    result = load_document(document)
    assert result.model is None
    return list(result.issues)


def codes_at(document: dict[str, Any]) -> list[tuple[str, str]]:
    return [(issue.code, issue.path) for issue in issues_of(document)]


# --- the version ---------------------------------------------------------------------------


def test_the_reader_is_format_0_2() -> None:
    assert FORMAT_VERSION == "0.2"


def test_the_transport_benchmark_is_format_0_2_and_loads() -> None:
    document = transport()
    assert document["format_version"] == "0.2"
    model_of(document)


@pytest.mark.parametrize(
    ("place", "key"),
    [
        ((), "sets"),
        ((), "tables"),
        (("variables", 0), "over"),
        (("objective",), "terms"),
        (("constraints", 0), "for"),
        (("constraints", 0), "terms"),
    ],
)
def test_a_0_2_key_in_a_0_1_file_is_e100_with_a_hint_to_set_0_2(
    place: tuple[str | int, ...], key: str
) -> None:
    document = transport()
    document["format_version"] = "0.1"
    path = "/" + "/".join([*map(str, place), key])
    issues = [issue for issue in schema_pass(document) if issue.path == path]
    assert len(issues) == 1, [issue.as_dict() for issue in schema_pass(document)]
    [issue] = issues
    assert issue.code == "E100"
    assert f"'{key}'" in issue.message
    assert "0.2" in issue.message and "0.1" in issue.message
    assert '"0.2"' in issue.hint


def test_a_0_1_file_reports_every_0_2_key_and_nothing_else() -> None:
    document = transport()
    document["format_version"] = "0.0"
    paths = [issue.path for issue in schema_pass(document)]
    assert paths == [
        "/constraints/0/for",
        "/constraints/0/terms",
        "/constraints/1/for",
        "/constraints/1/terms",
        "/objective/terms",
        "/sets",
        "/tables",
        "/variables/0/over",
    ]


def test_a_0_2_key_of_the_other_domain_is_reported_once_as_the_other_domains() -> None:
    document = json.loads((ROOT / "examples" / "coffee_shop.json").read_text(encoding="utf-8"))
    document["sets"] = {"depots": ["north"]}
    [issue] = schema_pass(document)
    assert (issue.code, issue.path) == ("E100", "/sets")
    assert "belongs to the 'optimization' domain" in issue.message


@pytest.mark.parametrize("holder", [("constraints", 0), ("objective",)])
def test_a_constraint_or_objective_with_neither_linear_nor_terms_is_e100(
    holder: tuple[str | int, ...],
) -> None:
    document = product_mix()
    target: Any = document
    for segment in holder:
        target = target[segment]
    del target["linear"]
    [issue] = schema_pass(document)
    path = "/" + "/".join(map(str, holder)) + "/linear"
    assert (issue.code, issue.path) == ("E100", path)
    assert "'linear'" in issue.message and "'terms'" in issue.hint


def test_terms_alone_need_no_linear_in_0_2() -> None:
    model = model_of(transport())
    assert model.declared is not None
    assert model.declared.objective.linear == {}


def test_the_new_keys_have_their_json_types_checked() -> None:
    document = transport()
    document["sets"]["depots"] = "north"
    document["tables"]["cost"] = {"values": 3}
    document["constraints"][0]["terms"][0] = {"coefficient": 2}
    paths = {(issue.code, issue.path) for issue in schema_pass(document)}
    assert paths == {
        ("E100", "/sets/depots"),
        ("E100", "/tables/cost/over"),
        ("E100", "/constraints/0/terms/0/variable"),
    }


# --- the declared program and its expansion ----------------------------------------------


def test_the_declared_program_is_kept_as_written() -> None:
    declared = model_of(transport()).declared
    assert declared is not None
    assert declared.sets == {"depots": DEPOTS, "customers": CUSTOMERS}
    assert declared.tables["supply"] == Table(
        over=("depots",), values={("north",): 300, ("centre",): 200, ("south",): 250}
    )
    assert declared.tables["cost"].values[("centre", "harbour")] == 3
    assert declared.variables == (
        IndexedVariable(
            id="ship", type="continuous", lower=0, upper=None, over=("depots", "customers")
        ),
    )
    assert declared.objective == IndexedObjective(
        sense="minimize", linear={}, terms=(Term("ship", TableRef("cost")),)
    )
    assert declared.constraints[0] == IndexedConstraint(
        id="supply",
        over=("depots",),
        linear={},
        terms=(Term("ship", 1),),
        op="<=",
        rhs=TableRef("supply"),
    )


def test_the_transport_plan_expands_into_the_flat_layout() -> None:
    program = model_of(transport()).program
    assert program is not None
    names = [f"ship[{depot},{customer}]" for depot in DEPOTS for customer in CUSTOMERS]
    assert [variable.id for variable in program.variables] == names
    assert all(
        variable == Variable(variable.id, "continuous", 0, None) for variable in program.variables
    )
    costs = [4, 6, 9, 5, 7, 3, 5, 8, 6, 8, 4, 3]
    assert program.objective == LinearObjective("minimize", dict(zip(names, costs, strict=True)))
    assert [constraint.id for constraint in program.constraints] == [
        "supply[north]",
        "supply[centre]",
        "supply[south]",
        "demand[city]",
        "demand[harbour]",
        "demand[park]",
        "demand[market]",
    ]
    assert program.constraints[1] == LinearConstraint(
        "supply[centre]", {f"ship[centre,{customer}]": 1 for customer in CUSTOMERS}, "<=", 200
    )
    assert program.constraints[4] == LinearConstraint(
        "demand[harbour]", {f"ship[{depot},harbour]": 1 for depot in DEPOTS}, ">=", 220
    )


def test_a_flat_model_expands_to_itself_and_declares_no_sets() -> None:
    model = model_of(product_mix())
    assert model.program == LinearProgram(
        variables=(
            Variable("chairs", "continuous", 0, None),
            Variable("tables", "continuous", 0, None),
        ),
        objective=LinearObjective("maximize", {"chairs": 45, "tables": 80}),
        constraints=(
            LinearConstraint("wood", {"chairs": 5, "tables": 20}, "<=", 400),
            LinearConstraint("labour", {"chairs": 10, "tables": 15}, "<=", 450),
        ),
    )
    assert model.declared is not None
    assert model.declared.sets == {} and model.declared.tables == {}
    assert [variable.over for variable in model.declared.variables] == [(), ()]


def test_expanded_name() -> None:
    assert expanded_name("ship", ()) == "ship"
    assert expanded_name("ship", ("north", "city")) == "ship[north,city]"


def rota() -> dict[str, Any]:
    """A staff rota in the shape AKS-140 will need: integer staff per pattern covering the
    needs of each day, a table over patterns and days."""
    return {
        "format_version": "0.2",
        "meta": {"name": "Rota"},
        "domain": "optimization",
        "sets": {"patterns": ["early", "late"], "days": ["mon", "tue", "wed"]},
        "tables": {
            "works": {
                "over": ["patterns", "days"],
                "values": {
                    "early": {"mon": 1, "tue": 1, "wed": 0},
                    "late": {"mon": 0, "tue": 1, "wed": 1},
                },
            },
            "need": {"over": ["days"], "values": {"mon": 3, "tue": 5, "wed": 2}},
            "wage": {"over": [], "values": 100},
        },
        "variables": [
            {"id": "staff", "type": "integer", "lower": 0, "over": ["patterns"]},
            {"id": "agency", "type": "integer", "lower": 0, "upper": 4},
        ],
        "objective": {
            "sense": "minimize",
            "linear": {"agency": 150},
            "terms": [{"variable": "staff", "coefficient": {"$table": "wage"}}],
        },
        "constraints": [
            {
                "id": "cover",
                "for": ["days"],
                "linear": {"agency": 1},
                "terms": [{"variable": "staff", "coefficient": {"$table": "works"}}],
                "op": ">=",
                "rhs": {"$table": "need"},
            },
            {
                "id": "fair",
                "linear": {"staff[early]": 1},
                "terms": [{"variable": "staff", "coefficient": -1}],
                "op": "<=",
                "rhs": 1,
            },
            {
                "id": "agency_cap",
                "for": ["days"],
                "terms": [{"variable": "agency", "coefficient": 2}],
                "op": "<=",
                "rhs": 8,
            },
        ],
    }


def test_a_rota_expands_with_tables_over_bound_and_summed_sets() -> None:
    program = model_of(rota()).program
    assert program is not None
    assert [variable.id for variable in program.variables] == [
        "staff[early]",
        "staff[late]",
        "agency",
    ]
    assert program.variables[2] == Variable("agency", "integer", 0, 4)
    assert program.objective == LinearObjective(
        "minimize", {"agency": 150, "staff[early]": 100, "staff[late]": 100}
    )
    cover = {constraint.id: constraint for constraint in program.constraints}
    assert cover["cover[mon]"] == LinearConstraint(
        "cover[mon]", {"agency": 1, "staff[early]": 1, "staff[late]": 0}, ">=", 3
    )
    assert cover["cover[tue]"].linear == {"agency": 1, "staff[early]": 1, "staff[late]": 1}
    assert cover["cover[wed]"].rhs == 2
    # Coefficients of one variable from `linear` and a term add up; a sum to 0 is kept.
    assert cover["fair"] == LinearConstraint(
        "fair", {"staff[early]": 0, "staff[late]": -1}, "<=", 1
    )
    # A variable with no sets in a constraint with `for` appears in each of its copies.
    assert [cover[f"agency_cap[{day}]"].linear for day in ("mon", "tue", "wed")] == [
        {"agency": 2}
    ] * 3


def test_the_rota_solves_through_the_adapter_names(tmp_path: Path) -> None:
    from ithax.engines.optimize.adapter import HighsAdapter
    from ithax.runs.manager import run_experiment

    outcome = run_experiment(HighsAdapter(), model_of(rota()), None, tmp_path / "run")
    assert outcome.state == "done"
    summary = outcome.summary
    assert summary is not None
    assert summary["status"] == "optimal"
    # Three early and two late cover 3, 5 and 2 people at 500; the agency costs more.
    assert summary["objective"] == pytest.approx(500)
    assert set(summary["variables"]) == {"staff[early]", "staff[late]", "agency"}
    assert set(summary["constraints"]) >= {"cover[mon]", "fair", "agency_cap[wed]"}


def test_a_term_on_a_constraint_without_for_sums_over_every_set() -> None:
    document = transport()
    document["constraints"].append(
        {"id": "total", "terms": [{"variable": "ship", "coefficient": 2}], "op": "<=", "rhs": 1500}
    )
    program = model_of(document).program
    assert program is not None
    total = program.constraints[-1]
    assert total.id == "total"
    assert total.linear == {f"ship[{d},{c}]": 2 for d in DEPOTS for c in CUSTOMERS}


def test_linear_may_name_an_expanded_variable() -> None:
    document = transport()
    document["constraints"].append(
        {"id": "closed", "linear": {"ship[north,park]": 1}, "op": "==", "rhs": 0}
    )
    program = model_of(document).program
    assert program is not None
    assert program.constraints[-1] == LinearConstraint("closed", {"ship[north,park]": 1}, "==", 0)


def test_linear_naming_an_indexed_variable_by_its_declared_id_is_e175() -> None:
    document = transport()
    document["objective"]["linear"] = {"ship": 1}
    [issue] = issues_of(document)
    assert (issue.code, issue.path) == ("E175", "/objective/linear/ship")


def test_e175_on_linear_points_at_the_declared_constraint() -> None:
    document = transport()
    document["constraints"][1]["linear"] = {"truck": 1}
    [issue] = issues_of(document)
    assert (issue.code, issue.path) == ("E175", "/constraints/1/linear/truck")


# --- issues found while building -----------------------------------------------------------


def test_a_term_naming_no_variable_is_e175_at_its_variable() -> None:
    document = transport()
    document["objective"]["terms"][0]["variable"] = "shipped"
    [issue] = issues_of(document)
    assert (issue.code, issue.path, issue.component) == (
        "E175",
        "/objective/terms/0/variable",
        None,
    )
    assert "'shipped'" in issue.message and "'ship'" in issue.hint


@pytest.mark.parametrize(
    ("change", "path"),
    [
        (lambda d: d["variables"][0]["over"].__setitem__(1, "shops"), "/variables/0/over/1"),
        (lambda d: d["constraints"][0]["for"].__setitem__(0, "plants"), "/constraints/0/for/0"),
        (lambda d: d["tables"]["cost"]["over"].__setitem__(0, "plants"), "/tables/cost/over/0"),
        (
            lambda d: d["objective"]["terms"][0].__setitem__("coefficient", {"$table": "price"}),
            "/objective/terms/0/coefficient",
        ),
        (
            lambda d: d["constraints"][1].__setitem__("rhs", {"$table": "orders"}),
            "/constraints/1/rhs",
        ),
    ],
)
def test_an_unknown_set_or_table_is_e176_only(change: Any, path: str) -> None:
    document = transport()
    change(document)
    issues = issues_of(document)
    assert [(issue.code, issue.path) for issue in issues] == [("E176", path)], [
        issue.as_dict() for issue in issues
    ]
    assert issues[0].hint


def test_e176_with_no_sets_or_tables_says_so() -> None:
    document = transport()
    del document["tables"]
    issues = issues_of(document)
    assert {issue.code for issue in issues} == {"E176"}
    assert all("no tables" in issue.hint for issue in issues)


def test_an_empty_set_is_e177() -> None:
    document = transport()
    document["sets"]["customers"] = []
    issues = codes_at(document)
    assert ("E177", "/sets/customers") in issues
    assert {code for code, _ in issues} == {"E177"}


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (
            lambda d: d["tables"]["cost"]["values"]["south"].pop("market"),
            ("E177", "/tables/cost/values/south"),
        ),
        (
            lambda d: d["tables"]["cost"]["values"]["south"].__setitem__("mall", 2),
            ("E177", "/tables/cost/values/south/mall"),
        ),
        (
            lambda d: d["tables"]["cost"]["values"].__setitem__("south", 3),
            ("E177", "/tables/cost/values/south"),
        ),
        (
            lambda d: d["tables"]["supply"]["values"].__setitem__("north", {"x": 1}),
            ("E177", "/tables/supply/values/north"),
        ),
        (
            lambda d: d["tables"]["supply"].__setitem__("values", [300]),
            ("E177", "/tables/supply/values"),
        ),
        (
            lambda d: d["tables"]["supply"]["values"].__setitem__("north", "300"),
            ("E123", "/tables/supply/values/north"),
        ),
        (
            lambda d: d["tables"]["supply"]["values"].__setitem__("north", True),
            ("E123", "/tables/supply/values/north"),
        ),
    ],
)
def test_table_values_that_do_not_match_their_sets(change: Any, expected: tuple[str, str]) -> None:
    document = transport()
    change(document)
    assert codes_at(document) == [expected]


def test_a_table_over_no_sets_holds_one_number() -> None:
    document = transport()
    document["tables"]["unit"] = {"over": [], "values": {"x": 1}}
    assert codes_at(document) == [("E177", "/tables/unit/values")]
    document["tables"]["unit"] = {"over": [], "values": 2}
    model_of(document)


def unbound_coefficient(document: dict[str, Any]) -> None:
    """A term in `supply` (for depots) on a variable with no sets, whose coefficient table
    is over customers: nothing binds the customer."""
    document["variables"].append({"id": "extra", "type": "continuous", "lower": 0})
    document["constraints"][0]["terms"].append(
        {"variable": "extra", "coefficient": {"$table": "demand"}}
    )


@pytest.mark.parametrize(
    ("change", "path"),
    [
        (lambda d: d["variables"][0]["over"].__setitem__(1, "depots"), "/variables/0/over/1"),
        (lambda d: d["constraints"][0]["for"].append("depots"), "/constraints/0/for/1"),
        (lambda d: d["tables"]["cost"]["over"].__setitem__(1, "depots"), "/tables/cost/over/1"),
        (
            lambda d: d["constraints"][1].__setitem__("rhs", {"$table": "supply"}),
            "/constraints/1/rhs",
        ),
        (unbound_coefficient, "/constraints/0/terms/1/coefficient"),
    ],
)
def test_an_index_that_cannot_be_bound_is_e178(change: Any, path: str) -> None:
    document = transport()
    change(document)
    codes = codes_at(document)
    assert ("E178", path) in codes
    assert {code for code, _ in codes} == {"E178"}, codes


def test_a_table_coefficient_bound_by_the_term_variable_is_allowed() -> None:
    document = transport()
    # cost is over depots and customers: depots from `for`, customers from ship's `over`.
    document["constraints"][0]["terms"][0]["coefficient"] = {"$table": "cost"}
    model_of(document)


@pytest.mark.parametrize(
    "value", [{"$table": 3}, {"$table": "cost", "x": 1}, {"table": "cost"}, "cost", True, [1]]
)
def test_a_coefficient_that_is_neither_a_number_nor_a_table_reference_is_e123(
    value: object,
) -> None:
    document = transport()
    document["objective"]["terms"][0]["coefficient"] = value
    assert codes_at(document) == [("E123", "/objective/terms/0/coefficient")]


@pytest.mark.parametrize("value", [{"$table": 3}, "supply", None])
def test_an_rhs_that_is_neither_a_number_nor_a_table_reference_is_e123(value: object) -> None:
    document = transport()
    document["constraints"][0]["rhs"] = value
    assert codes_at(document) == [("E123", "/constraints/0/rhs")]


def test_a_broken_declaration_does_not_cascade() -> None:
    """A variable whose set is unknown gives E176 there only, not E178 for each term."""
    document = transport()
    document["variables"][0]["over"] = ["depots", "shops"]
    assert codes_at(document) == [("E176", "/variables/0/over/1")]
    document = transport()
    document["tables"]["cost"]["over"] = ["depots", "shops"]
    assert codes_at(document) == [("E176", "/tables/cost/over/1")]
    document = transport()
    document["constraints"][0]["for"] = ["depots", "depots"]
    assert codes_at(document) == [("E178", "/constraints/0/for/1")]


# --- identifiers (the meaning pass) ---------------------------------------------------------


def test_set_and_table_ids_and_members_follow_the_identifier_pattern() -> None:
    document = transport()
    document["sets"]["Depots"] = document["sets"].pop("depots")
    document["variables"][0]["over"][0] = "Depots"
    document["constraints"][0]["for"][0] = "Depots"
    document["tables"]["supply"]["over"][0] = "Depots"
    document["tables"]["cost"]["over"][0] = "Depots"
    document["tables"]["Cost"] = document["tables"].pop("cost")
    document["objective"]["terms"][0]["coefficient"] = {"$table": "Cost"}
    document["sets"]["customers"][0] = "City"
    for table in ("demand",):
        document["tables"][table]["values"]["City"] = document["tables"][table]["values"].pop(
            "city"
        )
    for row in document["tables"]["Cost"]["values"].values():
        row["City"] = row.pop("city")
    assert sorted(codes_at(document)) == [
        ("E111", "/sets/Depots"),
        ("E111", "/sets/customers/0"),
        ("E111", "/tables/Cost"),
    ]


def test_a_member_repeated_in_one_set_is_e110() -> None:
    document = transport()
    document["sets"]["depots"].append("north")
    assert ("E110", "/sets/depots/3") in codes_at(document)


def test_a_set_and_a_table_may_share_an_id() -> None:
    document = transport()
    document["sets"]["supply"] = ["a"]
    model_of(document)


def test_declared_variable_and_constraint_ids_are_checked_not_expanded_names() -> None:
    document = transport()
    document["variables"].append({"id": "ship", "type": "continuous"})
    document["constraints"][1]["id"] = "supply"
    assert sorted(codes_at(document)) == [
        ("E110", "/constraints/1/id"),
        ("E110", "/variables/1/id"),
    ]


def test_the_expanded_model_keeps_its_declaration_under_copy() -> None:
    model = model_of(copy.deepcopy(transport()))
    assert model.declared is not None
    assert model.program is not None
    assert len(model.program.variables) == 12


def test_a_hint_lists_at_most_twelve_names() -> None:
    document = transport()
    document["sets"] |= {f"set_{n}": ["a"] for n in range(12)}
    document["variables"][0]["over"][1] = "shops"
    [issue] = issues_of(document)
    assert issue.code == "E176"
    assert issue.hint == "Correct the name to one of the sets, or add a set 'shops' to 'sets'."


@pytest.mark.parametrize("holder", [("objective",), ("constraints", 2)])
def test_coefficients_too_large_to_add_are_e123_not_an_exception(
    holder: tuple[str | int, ...],
) -> None:
    """Review of PR #53: a whole number too large for a float in `linear`, plus a float term
    coefficient for the same variable, raised OverflowError while loading."""
    document = transport()
    document["variables"].append({"id": "x", "type": "continuous", "lower": 0})
    document["constraints"].append({"id": "cap", "linear": {"x": 1}, "op": "<=", "rhs": 5})
    target: Any = document
    for segment in holder:
        target = target[segment]
    target["linear"] = {"x": 10**400}
    target.setdefault("terms", []).append({"variable": "x", "coefficient": 1.0})
    position = len(target["terms"]) - 1
    path = "/" + "/".join(map(str, holder)) + f"/terms/{position}/coefficient"
    [issue] = issues_of(document)
    assert (issue.code, issue.path) == ("E123", path)
    assert "'x'" in issue.message and "too large" in issue.message


@pytest.mark.parametrize("holder", [("objective",), ("constraints", 2)])
def test_coefficients_whose_float_sum_is_not_finite_are_e123(
    holder: tuple[str | int, ...],
) -> None:
    """Review of PR #53: two float coefficients of 1e308 for one variable add to infinity
    without raising, so the sum is checked to be finite."""
    document = transport()
    document["variables"].append({"id": "x", "type": "continuous", "lower": 0})
    document["constraints"].append({"id": "cap", "linear": {"x": 1}, "op": "<=", "rhs": 5})
    target: Any = document
    for segment in holder:
        target = target[segment]
    target["linear"] = {"x": 1e308}
    target.setdefault("terms", []).append({"variable": "x", "coefficient": 1e308})
    position = len(target["terms"]) - 1
    path = "/" + "/".join(map(str, holder)) + f"/terms/{position}/coefficient"
    [issue] = issues_of(document)
    assert (issue.code, issue.path) == ("E123", path)
