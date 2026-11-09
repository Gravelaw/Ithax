"""The transport benchmark's optimum, proved by LP duality (spec 2 "Benchmark definitions",
"How the M10 transport file reads the table"; AKS-123).

A plan is optimal for a linear program when it is feasible, a dual solution is feasible,
and the two objective values are equal (the weak and strong duality theorems; Hitchcock
1941 and Dantzig 1951 for the transportation problem; any LP text, such as Hillier and
Lieberman, chapter 6). For "minimize Σ c_ij x_ij, Σ_j x_ij ≤ s_i, Σ_i x_ij ≥ d_j, x ≥ 0"
the dual is "maximize Σ u_i s_i + Σ v_j d_j, u ≤ 0, v ≥ 0, u_i + v_j ≤ c_ij". Complementary
slackness holds when every used route has reduced cost c_ij - u_i - v_j = 0, and the
optimum is unique when every unused route's reduced cost is positive (the plan is then the
only point where the dual's equalities can hold with zero objective gap). This test checks
those sums from the benchmark's own files, with exact integers; it solves nothing.
"""

import json
from pathlib import Path
from typing import Any

CASE = Path(__file__).resolve().parents[2] / "benchmarks" / "transport"
# The dual prices stated in spec 2: supply limits (north, centre, south), demand limits
# (city, harbour, park, market).
U = {"north": 0, "centre": -3, "south": -2}
V = {"city": 4, "harbour": 6, "park": 6, "market": 5}


def files() -> tuple[dict[str, Any], dict[str, float]]:
    model = json.loads((CASE / "model.json").read_text(encoding="utf-8"))
    rows = json.loads((CASE / "expected.json").read_text(encoding="utf-8"))
    return model, {row["metric"]: row["value"] for row in rows}


def plan_and_data() -> tuple[dict[tuple[str, str], int], dict[str, Any], int]:
    model, expected = files()
    tables = model["tables"]
    plan = {
        (depot, customer): int(expected[f"variables.ship[{depot},{customer}]"])
        for depot in model["sets"]["depots"]
        for customer in model["sets"]["customers"]
    }
    return plan, tables, int(expected["objective"])


def test_the_plan_meets_every_limit_and_costs_the_expected_objective() -> None:
    plan, tables, objective = plan_and_data()
    assert all(amount >= 0 for amount in plan.values())
    for depot, supply in tables["supply"]["values"].items():
        assert sum(amount for (d, _), amount in plan.items() if d == depot) <= supply
    for customer, demand in tables["demand"]["values"].items():
        assert sum(amount for (_, c), amount in plan.items() if c == customer) >= demand
    cost = tables["cost"]["values"]
    assert sum(cost[d][c] * amount for (d, c), amount in plan.items()) == objective == 2690


def test_the_dual_prices_are_feasible_and_their_value_equals_the_plans_cost() -> None:
    plan, tables, objective = plan_and_data()
    cost = tables["cost"]["values"]
    assert all(u <= 0 for u in U.values()) and all(v >= 0 for v in V.values())
    reduced = {(d, c): cost[d][c] - U[d] - V[c] for (d, c) in plan}
    assert all(value >= 0 for value in reduced.values())
    dual = sum(U[d] * s for d, s in tables["supply"]["values"].items()) + sum(
        V[c] * q for c, q in tables["demand"]["values"].items()
    )
    assert dual == objective == 2690


def test_complementary_slackness_holds_and_the_optimum_is_unique() -> None:
    plan, tables, _ = plan_and_data()
    cost = tables["cost"]["values"]
    reduced = {(d, c): cost[d][c] - U[d] - V[c] for (d, c) in plan}
    used = {route for route, amount in plan.items() if amount > 0}
    assert all(reduced[route] == 0 for route in used)
    assert sorted(reduced[route] for route in plan if route not in used) == [2, 3, 4, 4, 6, 6]
    # A supply limit with a non-zero price is tight; north's price is 0 and it has 30 left.
    for depot, supply in tables["supply"]["values"].items():
        shipped = sum(amount for (d, _), amount in plan.items() if d == depot)
        assert U[depot] == 0 or shipped == supply
    assert sum(amount for (d, _), amount in plan.items() if d == "north") == 270
