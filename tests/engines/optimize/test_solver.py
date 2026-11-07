"""The HiGHS solve through Pyomo (AKS-108; ``docs/research/spec-2-solver-layer.md``).

Every claim of the research note's Decision that the adapter relies on is checked here
against the installed Pyomo and HiGHS: the status mapping, the second solve with presolve
off, duals for continuous problems only, slacks per ``op``, the tolerance for "tight", and
what happens to a variable no objective or constraint uses.
"""

import math
from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from pyomo.contrib.solver.common.results import TerminationCondition
from pyomo.contrib.solver.common.util import NoDualsError

from lcsim.engines.optimize import solver
from lcsim.engines.optimize.solver import (
    TIGHT_TOLERANCE,
    Outcome,
    SolverStopped,
    is_tight,
    solve,
    solver_version,
)
from lcsim.model.model import LinearConstraint, LinearObjective, LinearProgram, Variable


def program(
    variables: Sequence[tuple[str, str, float | None, float | None]],
    sense: str,
    objective: Mapping[str, float],
    constraints: Sequence[tuple[str, Mapping[str, float], str, float]] = (),
) -> LinearProgram:
    return LinearProgram(
        variables=tuple(Variable(*item) for item in variables),  # type: ignore[arg-type]
        objective=LinearObjective(sense, objective),  # type: ignore[arg-type]
        constraints=tuple(LinearConstraint(*item) for item in constraints),  # type: ignore[arg-type]
    )


PRODUCT_MIX = program(
    [("chairs", "continuous", 0, None), ("tables", "continuous", 0, None)],
    "maximize",
    {"chairs": 45, "tables": 80},
    [
        ("wood", {"chairs": 5, "tables": 20}, "<=", 400),
        ("labour", {"chairs": 10, "tables": 15}, "<=", 450),
    ],
)
DIET = program(
    [("x", "continuous", 0, None), ("y", "continuous", 0, None)],
    "minimize",
    {"x": 0.6, "y": 1},
    [("a", {"x": 2, "y": 4}, ">=", 8), ("b", {"x": 5, "y": 1}, ">=", 10)],
)
KNAPSACK = program(
    [(name, "binary", None, None) for name in "abcd"],
    "maximize",
    {"a": 10, "b": 13, "c": 8, "d": 7},
    [("weight", {"a": 5, "b": 6, "c": 4, "d": 3}, "<=", 10)],
)
COSTS = [[9, 2, 7], [6, 4, 3], [5, 8, 1]]
ASSIGNMENT = program(
    [(f"x_{r}_{c}", "binary", None, None) for r in range(3) for c in range(3)],
    "minimize",
    {f"x_{r}_{c}": COSTS[r][c] for r in range(3) for c in range(3)},
    [(f"row_{r}", {f"x_{r}_{c}": 1 for c in range(3)}, "==", 1) for r in range(3)]
    + [(f"col_{c}", {f"x_{r}_{c}": 1 for r in range(3)}, "==", 1) for c in range(3)],
)


def close(value: float | None, expected: float) -> bool:
    return value is not None and math.isclose(value, expected, rel_tol=1e-9, abs_tol=1e-9)


# --- optimal ---------------------------------------------------------------------------------


def test_the_product_mix_is_optimal_at_24_and_14_with_duals_1_and_4() -> None:
    outcome = solve(PRODUCT_MIX)
    assert outcome.status == "optimal"
    assert close(outcome.objective, 2200)
    assert close(outcome.values["chairs"], 24) and close(outcome.values["tables"], 14)
    # Both constraints bind; the wood slack is not exactly 0 (the note saw 5.7e-14).
    assert set(outcome.slacks) == {"wood", "labour"}
    assert all(abs(slack) <= TIGHT_TOLERANCE for slack in outcome.slacks.values())
    # Unique optimum (spec 2): both duals positive, and d objective / d rhs.
    assert outcome.duals is not None
    assert close(outcome.duals["wood"], 1) and close(outcome.duals["labour"], 4)


def test_the_diet_is_optimal_at_16_9_and_10_9_with_duals_11_45_and_1_45() -> None:
    outcome = solve(DIET)
    assert outcome.status == "optimal"
    assert close(outcome.objective, 98 / 45)
    assert close(outcome.values["x"], 16 / 9) and close(outcome.values["y"], 10 / 9)
    assert outcome.duals is not None
    assert close(outcome.duals["a"], 11 / 45) and close(outcome.duals["b"], 1 / 45)
    assert all(abs(slack) <= TIGHT_TOLERANCE for slack in outcome.slacks.values())


def test_the_knapsack_takes_b_and_c_and_has_no_duals() -> None:
    outcome = solve(KNAPSACK)
    assert outcome.status == "optimal"
    assert outcome.objective == 21
    assert outcome.values == {"a": 0, "b": 1, "c": 1, "d": 0}
    assert outcome.duals is None  # an integer program: NoDualsError is not passed on
    assert outcome.slacks == {"weight": 0}


def test_the_assignment_costs_9() -> None:
    outcome = solve(ASSIGNMENT)
    assert outcome.status == "optimal"
    assert outcome.objective == 9
    chosen = {name for name, value in outcome.values.items() if value == 1}
    assert chosen == {"x_0_1", "x_1_0", "x_2_2"}
    assert set(outcome.values.values()) == {0, 1}
    assert outcome.slacks == {f"{kind}_{i}": 0 for kind in ("row", "col") for i in range(3)}


def test_a_slack_per_op() -> None:
    # rhs minus the left-hand side for <=, the reverse for >=, minus the gap for ==.
    outcome = solve(
        program(
            [("x", "continuous", 0, 10), ("y", "integer", 0, 10)],
            "maximize",
            {"x": 1, "y": 1},
            [
                ("cap", {"x": 1}, "<=", 7.5),  # binds: slack 0
                ("room", {"x": 1, "y": 1}, "<=", 30),  # 30 - 17.5
                ("floor", {"y": 1}, ">=", 4),  # 10 - 4
                ("pin", {"y": 2}, "==", 20),  # 20 - 20
            ],
        )
    )
    assert outcome.status == "optimal"
    assert outcome.values == {"x": 7.5, "y": 10}
    assert outcome.slacks == {"cap": 0, "room": 12.5, "floor": 6, "pin": 0}


def test_a_variable_nothing_uses_still_gets_a_value_within_its_bounds() -> None:
    # Without the zero terms Pyomo leaves such a variable's value None (seen in probing).
    outcome = solve(
        program(
            [
                ("x", "continuous", 1, 10),
                ("idle", "continuous", 2, 3),
                ("free", "continuous", None, None),
                ("count", "integer", -4.5, -1.2),
            ],
            "minimize",
            {"x": 1},
        )
    )
    assert outcome.status == "optimal"
    assert outcome.values["x"] == 1
    assert 2 <= outcome.values["idle"] <= 3
    assert math.isfinite(outcome.values["free"])
    assert outcome.values["count"] in (-4, -3, -2)


def test_an_objective_with_no_terms_is_zero() -> None:
    outcome = solve(program([("x", "continuous", 0, 1)], "maximize", {}))
    assert (outcome.status, outcome.objective) == ("optimal", 0)


def test_a_binary_variable_keeps_to_0_and_1_whatever_its_bounds() -> None:
    outcome = solve(program([("x", "binary", -3, 5)], "maximize", {"x": 1}))
    assert outcome.values == {"x": 1}


# --- constraints with no terms and programs with no variables --------------------------------


def test_a_constraint_with_no_terms_is_judged_without_the_solver() -> None:
    held = solve(
        program(
            [("x", "continuous", 0, 1)],
            "maximize",
            {"x": 1},
            [("empty_le", {}, "<=", 2), ("empty_ge", {}, ">=", -1), ("empty_eq", {}, "==", 0)],
        )
    )
    assert held.status == "optimal" and held.objective == 1
    assert held.slacks == {"empty_le": 2, "empty_ge": 1, "empty_eq": 0}


@pytest.mark.parametrize(("op", "rhs"), [("<=", -1), (">=", 0.5), ("==", 1e-9)])
def test_a_violated_constraint_with_no_terms_makes_the_program_infeasible(
    op: str, rhs: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_solver(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("the solver was called")

    monkeypatch.setattr(solver, "_solve_once", no_solver)
    outcome = solve(
        program([("x", "continuous", 0, 1)], "maximize", {"x": 1}, [("c", {}, op, rhs)])
    )
    assert outcome == Outcome("infeasible", None, {}, {}, None)


def test_a_program_with_no_variables_is_optimal_at_zero_without_the_solver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # HiGHS through Pyomo answers "unknown" for a model with no variables (seen in probing).
    def no_solver(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("the solver was called")

    monkeypatch.setattr(solver, "_solve_once", no_solver)
    outcome = solve(program([], "minimize", {}, [("c", {}, "<=", 1)]))
    assert outcome.status == "optimal"
    assert (outcome.objective, outcome.values, outcome.slacks) == (0, {}, {"c": 1})
    assert outcome.duals == {"c": 0}


# --- infeasible and unbounded ----------------------------------------------------------------


@pytest.mark.parametrize("kind", ["continuous", "integer"])
def test_an_infeasible_program(kind: str) -> None:
    outcome = solve(
        program(
            [("x", kind, None, None)],
            "minimize",
            {"x": 1},
            [("low", {"x": 1}, ">=", 2), ("high", {"x": 1}, "<=", 1)],
        )
    )
    assert outcome == Outcome("infeasible", None, {}, {}, None)


def test_bounds_that_cross_are_infeasible() -> None:
    outcome = solve(program([("x", "continuous", 3, 1)], "minimize", {"x": 1}))
    assert outcome.status == "infeasible"


def test_an_unbounded_linear_program() -> None:
    outcome = solve(
        program(
            [("x", "continuous", None, None), ("y", "continuous", None, None)],
            "maximize",
            {"x": 1, "y": 1},
            [("c", {"x": 1, "y": -1}, "<=", 1)],
        )
    )
    assert outcome == Outcome("unbounded", None, {}, {}, None)


UNBOUNDED_INTEGERS = program(
    [("x", "integer", None, None), ("y", "integer", None, None)],
    "maximize",
    {"x": 1, "y": 1},
    [("c", {"x": 1, "y": -1}, "<=", 1)],
)


def test_an_unbounded_integer_program_is_settled_by_a_second_solve_without_presolve() -> None:
    # The first solve leaves it open; the adapter's second solve with presolve off says
    # unbounded (docs/research/spec-2-solver-layer.md).
    first = solver._solve_once(solver._pyomo_model(UNBOUNDED_INTEGERS).model, {})
    assert first.termination_condition == TerminationCondition.infeasibleOrUnbounded
    assert solve(UNBOUNDED_INTEGERS).status == "unbounded"


def test_still_infeasible_or_unbounded_after_the_second_solve_stops_the_solver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    real = solver._solve_once

    def open_ended(model: Any, options: dict[str, object]) -> Any:
        calls.append(dict(options))
        results = real(model, options)
        results.termination_condition = TerminationCondition.infeasibleOrUnbounded
        return results

    monkeypatch.setattr(solver, "_solve_once", open_ended)
    with pytest.raises(SolverStopped, match="infeasibleOrUnbounded") as stopped:
        solve(PRODUCT_MIX)
    assert stopped.value.condition == "infeasibleOrUnbounded"
    assert calls == [{}, {"presolve": "off"}]


@pytest.mark.parametrize(
    ("options", "condition"),
    [
        ({"simplex_iteration_limit": 0, "presolve": "off"}, "iterationLimit"),
        ({"time_limit": 0.0}, "maxTimeLimit"),
    ],
)
def test_any_other_ending_stops_the_solver_with_its_name(
    options: dict[str, object], condition: str
) -> None:
    with pytest.raises(SolverStopped) as stopped:
        solve(PRODUCT_MIX, options=options)
    assert stopped.value.condition == condition
    assert str(stopped.value) == f"HiGHS ended with the termination condition {condition}"


def test_an_integer_program_has_no_duals_from_pyomo() -> None:
    # The reason duals are read for continuous programs only.
    built = solver._pyomo_model(KNAPSACK)
    results = solver._solve_once(built.model, {})
    results.solution_loader.load_vars()
    with pytest.raises(NoDualsError):
        results.solution_loader.get_duals()


def test_a_solver_that_is_not_available_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    class Unavailable:
        def available(self) -> bool:
            return False

    monkeypatch.setattr(solver, "SolverFactory", lambda name: Unavailable())
    with pytest.raises(SolverStopped, match="unavailable"):
        solve(PRODUCT_MIX)


# --- tight, version ---------------------------------------------------------------------------


def test_tight_means_a_slack_within_one_millionth() -> None:
    assert TIGHT_TOLERANCE == 1e-6
    assert is_tight(0.0) and is_tight(1e-6) and is_tight(-1e-6) and is_tight(5.7e-14)
    assert not is_tight(1.0000001e-6) and not is_tight(-2e-6) and not is_tight(12.5)


def test_the_solver_version_is_highs_own() -> None:
    from importlib.metadata import version

    # highspy's version is HiGHS's (1.15.1 for both).
    assert solver_version() == version("highspy")
