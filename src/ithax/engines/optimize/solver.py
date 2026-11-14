"""HiGHS through Pyomo: the one module that calls Pyomo (spec 2 "Optimization"; AKS-108).

Pyomo calls its ``pyomo.contrib.solver`` interface a development preview whose API may
change, so every call to Pyomo and through it to HiGHS is here, as the research note
``docs/research/spec-2-solver-layer.md`` decided. HiGHS runs in this process through the
``highspy`` extension module; no executable and no subprocess are involved.

``solve(program)`` builds a Pyomo model of a ``LinearProgram`` and solves it with
``SolverFactory("highs")`` from ``pyomo.contrib.solver.common.factory``, called with
``load_solutions=False`` and ``raise_exception_on_nonoptimal_result=False`` so that no
outcome raises. The termination condition decides the status:

- ``convergenceCriteriaSatisfied``: ``optimal``; the variables are loaded, and the
  objective, each constraint's slack and, for a program with no ``integer`` or ``binary``
  variable, each constraint's dual are read;
- ``provenInfeasible`` or ``locallyInfeasible``: ``infeasible``;
- ``unbounded``: ``unbounded``;
- ``infeasibleOrUnbounded``: one more solve with HiGHS's ``presolve`` ``off``, mapped the
  same way;
- anything else, and ``infeasibleOrUnbounded`` again: ``SolverStopped`` naming the
  condition, which the run target reports as E190 (spec 2 has no fourth status).

A slack is ``rhs`` minus the left-hand side for ``<=``, the left-hand side minus ``rhs``
for ``>=``, and minus the gap between them for ``==``; a constraint is tight when the
slack is within ``TIGHT_TOLERANCE`` of zero. Values are reported as HiGHS gives them, not
rounded.

Two cases never reach HiGHS, because Pyomo cannot express them: a constraint with no
terms, whose left-hand side is the constant 0, is judged here (a violated one makes the
program ``infeasible``), and a program with no variables is ``optimal`` with objective 0
when every constraint holds. Every variable enters the objective, with coefficient 0 when
the objective does not name it, so that HiGHS gives a value to a variable that nothing
else uses (Pyomo would leave it unset).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

import pyomo.environ as pyo
from pyomo.contrib.solver.common.factory import SolverFactory
from pyomo.contrib.solver.common.results import Results, TerminationCondition

from ithax.model.model import LinearConstraint, LinearProgram

__all__ = [
    "TIGHT_TOLERANCE",
    "Outcome",
    "SolverStopped",
    "Status",
    "is_tight",
    "solve",
    "solver_version",
]

#: Spec 2 "Mathematical optimization in the model file": a constraint is tight when its
#: slack is at most this far from 0; at least as loose as HiGHS 1.15.1's default primal
#: (1e-7) and MIP (1e-6) feasibility tolerances (rule-5 reading, owner to confirm).
TIGHT_TOLERANCE = 1e-6

#: The ``summary.json`` statuses of spec 2.
Status = Literal["optimal", "infeasible", "unbounded"]

# Pyomo ships no type information, so its objects are typed through these names.
_PyomoModel: TypeAlias = pyo.ConcreteModel
_PyomoResults: TypeAlias = Results

_SOLVER = "highs"
_PRESOLVE_OFF: dict[str, object] = {"presolve": "off"}
_STATUSES: dict[TerminationCondition, Status] = {
    TerminationCondition.convergenceCriteriaSatisfied: "optimal",
    TerminationCondition.provenInfeasible: "infeasible",
    TerminationCondition.locallyInfeasible: "infeasible",
    TerminationCondition.unbounded: "unbounded",
}
_SENSES = {"minimize": pyo.minimize, "maximize": pyo.maximize}
_DOMAINS = {"continuous": pyo.Reals, "integer": pyo.Integers, "binary": pyo.Binary}


class SolverStopped(Exception):
    """HiGHS ended without an optimal, infeasible or unbounded answer; ``condition`` is
    the name of Pyomo's termination condition."""

    def __init__(self, condition: str) -> None:
        self.condition = condition
        super().__init__(f"HiGHS ended with the termination condition {condition}")


@dataclass(frozen=True)
class Outcome:
    """What a solve found. For ``optimal``: the objective, each variable's value and each
    constraint's slack, by id, and the duals by constraint id for a program with only
    continuous variables (``None`` otherwise). For ``infeasible`` and ``unbounded``: no
    objective, no values, no slacks and no duals (the point HiGHS holds for an unbounded
    program is not an optimum)."""

    status: Status
    objective: float | None
    values: dict[str, float]
    slacks: dict[str, float]
    duals: dict[str, float] | None


def is_tight(slack: float) -> bool:
    """Whether a constraint with ``slack`` is tight: ``|slack| <= TIGHT_TOLERANCE``."""
    return abs(slack) <= TIGHT_TOLERANCE


def solver_version() -> str:
    """HiGHS's version, as ``1.15.1``."""
    return ".".join(str(part) for part in SolverFactory(_SOLVER).version())


@dataclass(frozen=True)
class _Built:
    """A Pyomo model of a program, with its variables and its constraints that have terms,
    by id."""

    model: _PyomoModel
    variables: dict[str, Any]
    constraints: dict[str, Any]


def _constant_slack(constraint: LinearConstraint) -> float:
    """The slack of a constraint with no terms, whose left-hand side is 0."""
    rhs = float(constraint.rhs)
    if constraint.op == "<=":
        return rhs
    if constraint.op == ">=":
        return -rhs
    return -abs(rhs)


def _holds(constraint: LinearConstraint) -> bool:
    """Whether a constraint with no terms holds: ``0 op rhs``, exactly."""
    if constraint.op == "<=":
        return 0 <= constraint.rhs
    if constraint.op == ">=":
        return 0 >= constraint.rhs
    return constraint.rhs == 0


def _pyomo_model(program: LinearProgram) -> _Built:
    model = pyo.ConcreteModel()
    variables: dict[str, Any] = {}
    for variable in program.variables:
        var = pyo.Var(
            domain=_DOMAINS[variable.type],
            bounds=(
                None if variable.lower is None else float(variable.lower),
                None if variable.upper is None else float(variable.upper),
            ),
        )
        model.add_component(f"v_{len(variables)}", var)
        variables[variable.id] = var
    coefficients = program.objective.linear
    model.objective = pyo.Objective(
        expr=pyo.quicksum(
            float(coefficients.get(name, 0)) * var for name, var in variables.items()
        ),
        sense=_SENSES[program.objective.sense],
    )
    constraints: dict[str, Any] = {}
    for constraint in program.constraints:
        if not constraint.linear:
            continue
        body = pyo.quicksum(
            float(coefficient) * variables[name] for name, coefficient in constraint.linear.items()
        )
        rhs = float(constraint.rhs)
        if constraint.op == "<=":
            expression = body <= rhs
        elif constraint.op == ">=":
            expression = body >= rhs
        else:
            expression = body == rhs
        component = pyo.Constraint(expr=expression)
        model.add_component(f"c_{len(constraints)}", component)
        constraints[constraint.id] = component
    return _Built(model, variables, constraints)


def _solve_once(model: _PyomoModel, options: Mapping[str, object]) -> _PyomoResults:
    """One HiGHS solve of ``model`` with HiGHS options ``options``; Pyomo's results."""
    opt = SolverFactory(_SOLVER)
    if not opt.available():
        raise SolverStopped("unavailable")
    return opt.solve(
        model,
        load_solutions=False,
        raise_exception_on_nonoptimal_result=False,
        tee=False,
        solver_options=dict(options),
    )


def _status(results: _PyomoResults) -> Status | None:
    return _STATUSES.get(results.termination_condition)


def _nothing(status: Status) -> Outcome:
    return Outcome(status, None, {}, {}, None)


def solve(program: LinearProgram, *, options: Mapping[str, object] | None = None) -> Outcome:
    """Solves ``program`` with HiGHS; ``options`` are HiGHS options for every solve (the
    adapter passes none). ``SolverStopped`` when HiGHS gives no answer of the three."""
    if not all(_holds(item) for item in program.constraints if not item.linear):
        return _nothing("infeasible")
    continuous = all(variable.type == "continuous" for variable in program.variables)
    constant = {item.id: _constant_slack(item) for item in program.constraints if not item.linear}
    if not program.variables:
        return Outcome("optimal", 0.0, {}, constant, dict.fromkeys(constant, 0.0))
    built = _pyomo_model(program)
    given = dict(options or {})
    results = _solve_once(built.model, given)
    if results.termination_condition == TerminationCondition.infeasibleOrUnbounded:
        results = _solve_once(built.model, {**given, **_PRESOLVE_OFF})
    status = _status(results)
    if status is None:
        raise SolverStopped(results.termination_condition.name)
    if status != "optimal":
        return _nothing(status)
    loader = results.solution_loader
    loader.load_vars()
    values = {name: float(pyo.value(var)) for name, var in built.variables.items()}
    slacks: dict[str, float] = {}
    for constraint in program.constraints:
        if not constraint.linear:
            slacks[constraint.id] = constant[constraint.id]
            continue
        data = built.constraints[constraint.id]
        if constraint.op == "<=":
            slacks[constraint.id] = float(data.uslack())
        elif constraint.op == ">=":
            slacks[constraint.id] = float(data.lslack())
        else:
            slacks[constraint.id] = float(data.slack())
    duals: dict[str, float] | None = None
    if continuous:
        # An integer program has none: get_duals() raises NoDualsError for it.
        found = loader.get_duals()
        duals = {
            item.id: float(found[built.constraints[item.id]]) if item.linear else 0.0
            for item in program.constraints
        }
    return Outcome("optimal", float(results.incumbent_objective), values, slacks, duals)
