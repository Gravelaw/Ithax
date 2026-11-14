"""Clean solver values (#76; M5-12; ``docs/research/m13-solver-values.md``).

HiGHS reports an integer or binary variable to within its integrality tolerance, as -0.0
for a variable at zero, and its floating-point arithmetic leaves continuous answers a few
units in the last place off: 24.000000000000004 chairs, a slack of 5.7e-14, a dual of
0.9999999999999996. ``solve`` reports an integer or binary variable rounded to its whole
number, and any other value within ``NOISE`` (scaled by the value's size, at least 1) of
a whole number as that number, never -0.0; the slacks and objective are read at the
values reported.
"""

import json
import math
from pathlib import Path
from typing import Literal

import pytest

from ithax.engines.optimize.solver import NOISE, Outcome, clean, solve
from ithax.model.loading import load_document

ROOT = Path(__file__).resolve().parents[3]


Kind = Literal["continuous", "integer", "binary"]


def solved(relative: str) -> tuple[dict[str, Kind], Outcome]:
    document = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    model = load_document(document).model
    assert model is not None and model.program is not None
    types = {variable.id: variable.type for variable in model.program.variables}
    return types, solve(model.program)


def plain(value: float) -> bool:
    """Not -0.0."""
    return not (value == 0 and math.copysign(1.0, value) < 0)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (24.000000000000004, 24.0),
        (13.999999999999998, 14.0),
        (0.9999999999999996, 1.0),
        (5.684341886080802e-14, 0.0),
        (-0.0, 0.0),
        (2200.0000000000005, 2200.0),
        (1e12 + 0.0001, 1e12),  # within 1e-9 of its size
    ],
)
def test_noise_is_cleaned(raw: float, expected: float) -> None:
    assert clean(raw) == expected and plain(clean(raw))


@pytest.mark.parametrize(
    "value",
    [98 / 45, 16 / 9, 0.5, 1e-7, -1e-7, 1 + 1e-8, 1e6 + 1e-2, 3.0, -2.5],
)
def test_a_value_that_is_not_noise_is_kept(value: float) -> None:
    assert clean(value) == value


def test_noise_is_far_below_the_solver_s_feasibility_tolerance() -> None:
    """1e-9: well above floating-point noise (about 1e-16 of the value per operation),
    well below HiGHS 1.15.1's primal feasibility tolerance of 1e-7."""
    assert NOISE == 1e-9


def test_the_product_mix_reports_24_14_and_2200_exactly() -> None:
    _, outcome = solved("benchmarks/product_mix/model.json")
    assert outcome.objective == 2200.0
    assert outcome.values == {"chairs": 24.0, "tables": 14.0}
    assert outcome.slacks == {"wood": 0.0, "labour": 0.0}
    assert outcome.duals == {"wood": 1.0, "labour": 4.0}


@pytest.mark.parametrize(
    "relative",
    [
        "benchmarks/assignment/model.json",
        "benchmarks/knapsack/model.json",
        "templates/staff_rota/model.json",
        "templates/transport_plan/model.json",
        "benchmarks/diet/model.json",
    ],
)
def test_integer_values_are_whole_and_no_value_is_minus_zero(relative: str) -> None:
    """HiGHS gives -0.0 for assignment cells and rota shifts at zero, and a transport dual
    of -0.0; each is reported as 0.0, and every integer or binary value is whole."""
    types, outcome = solved(relative)
    values = outcome.values
    numbers = [*values.values(), *outcome.slacks.values()]
    numbers += list((outcome.duals or {}).values())
    assert outcome.objective is not None
    assert all(plain(number) for number in [outcome.objective, *numbers])
    assert all(values[name].is_integer() for name, kind in types.items() if kind != "continuous")
