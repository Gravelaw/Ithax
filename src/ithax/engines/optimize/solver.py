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
slack is within ``TIGHT_TOLERANCE`` of zero.

Values are cleaned of solver noise (#76; ``docs/research/m13-solver-values.md``): an
``integer`` or ``binary`` variable is reported rounded to its whole number (HiGHS keeps it
within its integrality tolerance of one), and every other number, a continuous value, the
objective, a slack or a dual, within ``NOISE_ULPS`` units in the last place of a whole
number is reported as that number, the units measured at the size of the numbers it is
computed from (a slack's ``rhs`` and terms, the objective's terms); no number is -0.0. The
slacks and the objective are read at the values reported, so they agree with them.

Two cases never reach HiGHS, because Pyomo cannot express them: a constraint with no
terms, whose left-hand side is the constant 0, is judged here (a violated one makes the
program ``infeasible``), and a program with no variables is ``optimal`` with objective 0
when every constraint holds. Every variable enters the objective, with coefficient 0 when
the objective does not name it, so that HiGHS gives a value to a variable that nothing
else uses (Pyomo would leave it unset).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

import pyomo.environ as pyo
from pyomo.contrib.solver.common.factory import SolverFactory
from pyomo.contrib.solver.common.results import Results, TerminationCondition

from ithax.model.model import LinearConstraint, LinearProgram

__all__ = [
    "NOISE_ULPS",
    "TIGHT_TOLERANCE",
    "Outcome",
    "SolverStopped",
    "Status",
    "clean",
    "is_tight",
    "solve",
    "solver_version",
]

#: Spec 2 "Mathematical optimization in the model file": a constraint is tight when its
#: slack is at most this far from 0; at least as loose as HiGHS 1.15.1's default primal
#: (1e-7) and MIP (1e-6) feasibility tolerances (rule-5 reading, owner to confirm).
TIGHT_TOLERANCE = 1e-6

#: How many units in the last place (ulps) from a whole number a number is taken as
#: floating-point noise (#76): HiGHS's arithmetic leaves the product mix 1 or 2 ulps off.
#: 64 ulps is about 1.4e-14 of a value, so a fraction a model means is kept, however large
#: the value (review of PR #164: 1,000,000,000.25 is not 1,000,000,000).
NOISE_ULPS = 64

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


def clean(value: float, scale: float = 0.0) -> float:
    """``value`` without floating-point noise: the nearest whole number when within
    ``NOISE_ULPS`` ulps of it, an ulp taken at ``max(1, |value|, |scale|)``, where
    ``scale`` is the size of the numbers ``value`` was computed from (a slack of 5.7e-14
    is 1 ulp of its constraint's 400); otherwise ``value``. Never -0.0."""
    whole = round(value)
    if abs(value - whole) <= NOISE_ULPS * math.ulp(max(1.0, abs(value), abs(scale))):
        return float(whole)  # float(0) is 0.0, so a -0.0 becomes 0.0
    return value


def _size(coefficients: Mapping[str, Any], values: Mapping[str, float], *more: float) -> float:
    """The largest magnitude among ``more`` and the terms coefficient x value."""
    terms = [abs(float(c) * values[name]) for name, c in coefficients.items()]
    return max([0.0, *(abs(x) for x in more), *terms])


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
        cleaned = {
            item.id: clean(constant[item.id], float(item.rhs)) for item in program.constraints
        }
        return Outcome("optimal", 0.0, {}, cleaned, dict.fromkeys(constant, 0.0))
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
    values = _reported_values(program, built)
    slacks = {
        item.id: clean(_slack(item, built, constant), _size(item.linear, values, float(item.rhs)))
        for item in program.constraints
    }
    duals: dict[str, float] | None = None
    if continuous:
        # An integer program has none: get_duals() raises NoDualsError for it.
        found = loader.get_duals()
        duals = {
            item.id: clean(float(found[built.constraints[item.id]])) if item.linear else 0.0
            for item in program.constraints
        }
    objective = clean(
        float(pyo.value(built.model.objective)), _size(program.objective.linear, values)
    )
    return Outcome("optimal", objective, values, slacks, duals)


def _reported_values(program: LinearProgram, built: _Built) -> dict[str, float]:
    """Each variable's value as reported (#76): an integer or binary one rounded, any other
    cleaned; set back into the Pyomo model, so the slacks and the objective are read at
    the values reported."""
    values: dict[str, float] = {}
    for variable in program.variables:
        var = built.variables[variable.id]
        raw = float(pyo.value(var))
        value = float(round(raw)) if variable.type != "continuous" else clean(raw)
        var.set_value(value, skip_validation=True)
        values[variable.id] = value
    return values


def _slack(constraint: LinearConstraint, built: _Built, constant: Mapping[str, float]) -> float:
    if not constraint.linear:
        return constant[constraint.id]
    data = built.constraints[constraint.id]
    if constraint.op == "<=":
        return float(data.uslack())
    if constraint.op == ">=":
        return float(data.lslack())
    return float(data.slack())
