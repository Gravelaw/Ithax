"""The HiGHS adapter's engine input, ``engine/input.json`` (AKS-108).

``write_input`` writes the model's linear program (spec 2 "Mathematical optimization in
the model file") in the model file's own layout, with every number as a float, since HiGHS
works in floats; ``meta`` and ``run`` are left out, so changing them leaves the file
byte-equal. ``read_input`` reads it back as a ``LinearProgram``.

A whole number too large for a float (the loader accepts any JSON integer) raises
``OverflowError``, which fails the run with E190.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from ithax.model.model import (
    LinearConstraint,
    LinearObjective,
    LinearProgram,
    Model,
    Variable,
)
from ithax.strict_json import encode_json, read_json_object_file

__all__ = ["INPUT_FILE", "read_input", "write_input"]

#: The engine input, relative to ``workdir``.
INPUT_FILE = Path("input.json")


def _linear(linear: Mapping[str, int | float]) -> dict[str, float]:
    return {name: float(value) for name, value in linear.items()}


def _bound(value: int | float | None) -> float | None:
    return None if value is None else float(value)


def write_input(model: Model, workdir: Path) -> Path:
    """Writes ``model``'s program to ``workdir/input.json`` and returns the path.

    A model that is not an optimization model raises ``ValueError``.
    """
    program = model.program
    if program is None:
        raise ValueError(f"model {model.meta.name!r} is not an optimization model")
    document = {
        "variables": [
            {
                "id": variable.id,
                "type": variable.type,
                "lower": _bound(variable.lower),
                "upper": _bound(variable.upper),
            }
            for variable in program.variables
        ],
        "objective": {
            "sense": program.objective.sense,
            "linear": _linear(program.objective.linear),
        },
        "constraints": [
            {
                "id": constraint.id,
                "linear": _linear(constraint.linear),
                "op": constraint.op,
                "rhs": float(constraint.rhs),
            }
            for constraint in program.constraints
        ],
    }
    data = encode_json(document)
    workdir.mkdir(parents=True, exist_ok=True)
    path = workdir / INPUT_FILE
    path.write_bytes(data)
    return path


def read_input(workdir: Path) -> LinearProgram:
    """The program ``write_input`` wrote to ``workdir``."""
    document = read_json_object_file(workdir / INPUT_FILE)
    return LinearProgram(
        variables=tuple(
            Variable(id=item["id"], type=item["type"], lower=item["lower"], upper=item["upper"])
            for item in document["variables"]
        ),
        objective=LinearObjective(
            sense=document["objective"]["sense"],
            linear=MappingProxyType(dict(document["objective"]["linear"])),
        ),
        constraints=tuple(
            LinearConstraint(
                id=item["id"],
                linear=MappingProxyType(dict(item["linear"])),
                op=item["op"],
                rhs=item["rhs"],
            )
            for item in document["constraints"]
        ),
    )
