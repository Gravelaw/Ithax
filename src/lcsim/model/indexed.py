"""Expanding an indexed ``optimization`` model into the flat layout (spec 2 "Mathematical
optimization in the model file", "Indexed problems"; spec 1 "Indexed optimization"; AKS-123).

A variable declared ``over`` sets stands for one variable per combination of their members,
named by ``expanded_name``: ``ship[north,city]``. A constraint declared ``for`` sets stands
for one constraint per combination, named the same way. A term adds its variable times its
coefficient (a plain number, or a table's value at the members of the table's sets), summed
over the variable's sets that the constraint's ``for`` does not name; a set the ``for``
names takes the constraint's member. Combinations follow the members' order, the first set
outermost; coefficients of one variable from ``linear`` and from terms add up.

``expand`` assumes a declaration the loader has checked (every set, table and variable a
term or ``$table`` names exists, every table is complete and every index is bound); the
loader reports the codes E175 to E178 before it expands. Nothing here solves anything: the
expansion is bookkeeping, and HiGHS solves the flat program (guide rule 7).
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator, Mapping, Sequence
from types import MappingProxyType

from lcsim.model.model import (
    IndexedProgram,
    LinearConstraint,
    LinearObjective,
    LinearProgram,
    TableRef,
    Term,
    Variable,
)

__all__ = ["combinations", "expand", "expanded_name"]


def expanded_name(identifier: str, members: Sequence[str]) -> str:
    """``identifier`` for no members; else ``identifier[member,member]``."""
    return f"{identifier}[{','.join(members)}]" if members else identifier


def combinations(
    sets: Mapping[str, tuple[str, ...]], over: Sequence[str]
) -> Iterator[dict[str, str]]:
    """Each combination of members of the sets ``over``, as set id to member, the first
    set outermost; one empty combination for no sets."""
    for members in itertools.product(*(sets[name] for name in over)):
        yield dict(zip(over, members, strict=True))


def _coefficient(
    program: IndexedProgram, coefficient: int | float | TableRef, binding: Mapping[str, str]
) -> int | float:
    if not isinstance(coefficient, TableRef):
        return coefficient
    table = program.tables[coefficient.table]
    return table.values[tuple(binding[name] for name in table.over)]


def _linear(
    program: IndexedProgram,
    linear: Mapping[str, int | float],
    terms: Sequence[Term],
    bound: Mapping[str, str],
) -> Mapping[str, int | float]:
    """``linear`` plus every term, with the sets of ``bound`` fixed to its members."""
    coefficients: dict[str, int | float] = dict(linear)
    over = {variable.id: variable.over for variable in reversed(program.variables)}
    for term in terms:
        sets = over[term.variable]
        free = [name for name in sets if name not in bound]
        for combination in combinations(program.sets, free):
            binding = {**bound, **combination}
            name = expanded_name(term.variable, [binding[item] for item in sets])
            value = _coefficient(program, term.coefficient, binding)
            coefficients[name] = coefficients.get(name, 0) + value
    return MappingProxyType(coefficients)


def expand(program: IndexedProgram) -> LinearProgram:
    """The flat program ``program`` declares (spec 2 "Indexed problems")."""
    variables = tuple(
        Variable(
            id=expanded_name(variable.id, list(combination.values())),
            type=variable.type,
            lower=variable.lower,
            upper=variable.upper,
        )
        for variable in program.variables
        for combination in combinations(program.sets, variable.over)
    )
    objective = LinearObjective(
        sense=program.objective.sense,
        linear=_linear(program, program.objective.linear, program.objective.terms, {}),
    )
    constraints = tuple(
        LinearConstraint(
            id=expanded_name(constraint.id, list(combination.values())),
            linear=_linear(program, constraint.linear, constraint.terms, combination),
            op=constraint.op,
            rhs=_coefficient(program, constraint.rhs, combination),
        )
        for constraint in program.constraints
        for combination in combinations(program.sets, constraint.over)
    )
    return LinearProgram(variables=variables, objective=objective, constraints=constraints)
