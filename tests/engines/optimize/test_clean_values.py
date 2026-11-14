"""Clean solver values (#76; M5-12; ``docs/research/m13-solver-values.md``).

HiGHS reports an integer or binary variable to within its integrality tolerance, as -0.0
for a variable at zero, and its floating-point arithmetic leaves continuous answers a few
units in the last place off: 24.000000000000004 chairs, a slack of 5.7e-14, a dual of
0.9999999999999996: one or two units in the last place (ulps) of the numbers they come
from. ``solve`` reports an integer or binary variable rounded to its whole number, and any
other value within ``NOISE_ULPS`` ulps of a whole number, measured at the size of the
numbers it is computed from (a slack's ``rhs`` and terms), as that number; never -0.0. A
fraction above that noise is kept, however large the value (review of PR #164).
"""

import json
import math
from pathlib import Path
from typing import Literal

import pytest

from ithax.engines.optimize.solver import NOISE_ULPS, Outcome, clean, solve
from ithax.model.loading import load_document
from ithax.model.model import LinearObjective, LinearProgram, Variable

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
        (-0.0, 0.0),
        (2200.0000000000005, 2200.0),
    ],
)
def test_noise_is_cleaned(raw: float, expected: float) -> None:
    assert clean(raw) == expected and plain(clean(raw))


def test_a_slack_is_cleaned_at_the_size_of_its_constraint() -> None:
    """The product mix's wood slack, 400 - 400.00000000000006: one ulp of 400, though 256
    ulps of 1."""
    assert clean(5.684341886080802e-14, 400.0) == 0.0
    assert clean(5.684341886080802e-14) == 5.684341886080802e-14


@pytest.mark.parametrize(
    "value",
    [
        98 / 45,
        16 / 9,
        0.5,
        1e-7,
        -1e-7,
        1 + 1e-12,
        1e6 + 1e-2,
        3.0,
        -2.5,
        1e9 + 0.25,  # review of PR #164: a meant fraction of a large value
        1e12 + 0.25,
    ],
)
def test_a_value_that_is_not_noise_is_kept(value: float) -> None:
    assert clean(value) == value


def test_noise_is_a_few_units_in_the_last_place() -> None:
    """64 ulps: the product mix's noise is 1 or 2, and 64 ulps of a value is about 1.4e-14
    of it, far below any fraction a model means."""
    assert NOISE_ULPS == 64


def test_a_large_fractional_optimum_is_kept() -> None:
    """Review of PR #164: x fixed at 1,000,000,000.25 is reported so, and so is the
    objective, not snapped to 1,000,000,000 against its bounds."""
    value = 1e9 + 0.25
    program = LinearProgram(
        variables=(Variable("x", "continuous", value, value),),
        objective=LinearObjective("minimize", {"x": 1}),
        constraints=(),
    )
    outcome = solve(program)
    assert outcome.values == {"x": value}
    assert outcome.objective == value


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
