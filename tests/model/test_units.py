"""Tests for the quantity layer (spec 1 "Units" and "Quantities"; AKS-86)."""

import math
import random
from dataclasses import FrozenInstanceError

import pytest

from ithax.model.units import (
    PHASE_1_UNITS,
    Dimension,
    Quantity,
    QuantityDimensionError,
    QuantityError,
    QuantityKindError,
    QuantityParseError,
    parse_quantity,
    read_number,
    read_quantity,
    si_symbol,
    units_of,
)

TIME = Dimension.TIME
DIMENSIONLESS = Dimension.DIMENSIONLESS

# Seconds per Phase 1 unit, written out independently of the units library.
SECONDS_PER_UNIT = {"s": 1.0, "min": 60.0, "h": 3600.0, "d": 86400.0}


# --- parse_quantity: values -------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("1.5 min", 90.0),
        ("2 h", 7200.0),
        ("1 d", 86400.0),
        ("30 s", 30.0),
        ("2 min", 120.0),
        ("200 h", 720000.0),
        ("3 d", 259200.0),
        ("0 s", 0.0),
        ("1e3 s", 1000.0),
        ("1E3 s", 1000.0),
        ("2.5e-1 min", 15.0),
        ("1e+2 s", 100.0),
        ("-2 min", -120.0),
        ("0.5 h", 1800.0),
    ],
)
def test_parse_quantity_converts_time_to_seconds(text: str, seconds: float) -> None:
    quantity = parse_quantity(text, TIME)
    assert quantity.magnitude == seconds
    assert type(quantity.magnitude) is float
    assert quantity.dimension is TIME
    assert quantity.unit == "s"


def test_integer_input_gives_a_float_magnitude() -> None:
    # pint returns an int for "2 min"; spec 1 says internal time is a float.
    assert type(parse_quantity("2 min", TIME).magnitude) is float


def test_negative_zero_is_stored_as_zero() -> None:
    quantity = parse_quantity("-0 s", TIME)
    assert quantity.magnitude == 0.0
    assert math.copysign(1.0, quantity.magnitude) == 1.0


def test_conversion_equals_the_plain_factor_for_many_values() -> None:
    rng = random.Random(86)
    numbers = ["0", "1", "1.5", "0.1", "0.2", "0.3", "7", "59.999", "1e-3", "123456.789"]
    numbers += [f"{rng.uniform(0, 1000):.6f}" for _ in range(500)]
    for number in numbers:
        for unit, factor in SECONDS_PER_UNIT.items():
            got = parse_quantity(f"{number} {unit}", TIME).magnitude
            assert got == float(number) * factor, f"{number} {unit}"


# --- parse_quantity: E141 ---------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "2min",  # no space
        "2  min",  # two spaces
        " 2 min",  # leading space
        "2 min ",  # trailing space
        "2\tmin",  # tab, not U+0020
        "2\u00a0min",  # no-break space
        "2 min\n",  # trailing newline
        "2 minutes",  # pint knows it, same dimension, not a Phase 1 symbol
        "2 mins",
        "2 ms",  # a time, but not a Phase 1 unit
        "2 hr",
        "2 day",
        "2 cd",  # centi-day for pint: a time candidate, so not E140
        "2 * min",  # an expression
        "2 min / min",
        "2 m*s",
        "nan s",
        "inf s",
        "+2 s",
        ".5 s",
        "2. s",
        "02 s",
        "-.5 s",
        "0x10 s",
        "1_000 s",
        "\uff12 s",  # full-width digit
        "\u0662 s",  # Arabic-Indic digit
        "2 x",  # unknown unit
        "2 (",
        "2 ",
        " min",
        "min",
        "2",
        "",
        "2 s s",
        "1e400 s",  # overflows to infinity
        "1e308 d",  # finite number, infinite in seconds
    ],
)
def test_unreadable_strings_are_e141(text: str) -> None:
    with pytest.raises(QuantityParseError) as caught:
        parse_quantity(text, TIME)
    assert caught.value.code == "E141"
    assert caught.value.value == text


@pytest.mark.parametrize("text", ["5 m", "2 Min", "2 kg", "3 degC", "1 %", "4 cps", "2 kat"])
def test_known_unit_of_another_dimension_is_e140(text: str) -> None:
    # "2 Min" is a megainch to pint: case matters, and it is a length.
    with pytest.raises(QuantityDimensionError) as caught:
        parse_quantity(text, TIME)
    assert caught.value.code == "E140"
    assert caught.value.value == text


@pytest.mark.parametrize("text", ["2 s", "1.5 min", "2 h", "1 d"])
def test_time_unit_where_dimensionless_is_expected_is_e140(text: str) -> None:
    with pytest.raises(QuantityDimensionError) as caught:
        parse_quantity(text, DIMENSIONLESS)
    assert caught.value.code == "E140"


def test_dimensionless_has_no_phase_1_unit() -> None:
    with pytest.raises(QuantityParseError):
        parse_quantity("2 percent", DIMENSIONLESS)  # known, dimensionless, not Phase 1


def test_grammar_is_checked_before_dimension() -> None:
    # A length unit written without the space breaks the grammar first: E141, not E140.
    with pytest.raises(QuantityParseError):
        parse_quantity("5m", TIME)


# --- error objects: code, message, hint ---------------------------------------------------


def test_errors_share_a_base_class_with_a_code() -> None:
    for error_type, code in [
        (QuantityParseError, "E141"),
        (QuantityDimensionError, "E140"),
        (QuantityKindError, "E123"),
    ]:
        assert issubclass(error_type, QuantityError)
        assert error_type.code == code


@pytest.mark.parametrize(
    ("value", "expected", "error_type"),
    [
        ("2min", TIME, QuantityParseError),
        ("5 m", TIME, QuantityDimensionError),
        ("2 s", DIMENSIONLESS, QuantityDimensionError),
        ("1e400 s", TIME, QuantityParseError),
    ],
)
def test_messages_are_plain_language_and_quote_the_value(
    value: str, expected: Dimension, error_type: type[QuantityError]
) -> None:
    with pytest.raises(error_type) as caught:
        parse_quantity(value, expected)
    error = caught.value
    assert f"'{value}'" in error.message
    assert error.hint
    assert str(error) == error.message
    for leak in ("Error", "Traceback", "pint", "Undefined", "dimensionality"):
        assert leak not in error.message
        assert leak not in error.hint


def test_time_hints_name_the_phase_1_units() -> None:
    with pytest.raises(QuantityParseError) as caught:
        parse_quantity("2 minutes", TIME)
    assert "s, min, h or d" in caught.value.hint


def test_dimensionless_hint_says_to_remove_the_unit() -> None:
    with pytest.raises(QuantityDimensionError) as caught:
        parse_quantity("2 s", DIMENSIONLESS)
    assert "Remove the unit" in caught.value.hint


# --- read_quantity and read_number: E123 -------------------------------------------------


def test_read_quantity_parses_strings() -> None:
    assert read_quantity("1.5 min", TIME) == Quantity(90.0, TIME)


@pytest.mark.parametrize("value", [2, 2.5, 0, -1, float("nan")])
def test_plain_number_where_a_quantity_is_expected_is_e123(value: float) -> None:
    with pytest.raises(QuantityKindError) as caught:
        read_quantity(value, TIME)
    assert caught.value.code == "E123"
    assert "time" in caught.value.message
    assert "s, min, h or d" in caught.value.hint


@pytest.mark.parametrize("value", [True, False, None, [], ["2 min"], {}, {"value": 2}])
def test_other_json_values_where_a_quantity_is_expected_are_e141(value: object) -> None:
    with pytest.raises(QuantityParseError) as caught:
        read_quantity(value, TIME)
    assert caught.value.code == "E141"


@pytest.mark.parametrize("value", [0, 3, -4, 2.5, 1e-9])
def test_read_number_returns_plain_numbers_unchanged(value: float) -> None:
    result = read_number(value)
    assert result == value
    assert type(result) is type(value)


@pytest.mark.parametrize(
    "value",
    [
        "2 min",  # a quantity where a number is expected
        "5 m",
        "2",  # a number written as a string
        "abc",
        True,
        None,
        [3],
        {},
        float("nan"),
        float("inf"),
        -float("inf"),
    ],
)
def test_anything_but_a_finite_json_number_where_a_number_is_expected_is_e123(
    value: object,
) -> None:
    with pytest.raises(QuantityKindError) as caught:
        read_number(value)
    assert caught.value.code == "E123"
    assert caught.value.hint


@pytest.mark.parametrize(
    "value", [10**309, -(10**309), 10**5000, 2**64 + 1], ids=["1e309", "-1e309", "1e5000", "2^64+1"]
)
def test_read_number_returns_very_large_integers_unchanged(value: int) -> None:
    # math.isfinite(10**309) would raise OverflowError; an int is always finite.
    assert read_number(value) == value


@pytest.mark.parametrize("value", [10**309, 10**5000], ids=["1e309", "1e5000"])
def test_very_large_integer_where_a_quantity_is_expected_is_e123(value: int) -> None:
    # repr(10**5000) raises ValueError (integer string limit); the message must not.
    with pytest.raises(QuantityKindError) as caught:
        read_quantity(value, TIME)
    assert caught.value.message.startswith("a very large integer is a plain number")


def test_integers_up_to_64_bits_are_quoted_in_the_e123_message() -> None:
    with pytest.raises(QuantityKindError) as caught:
        read_quantity(2**64 - 1, TIME)
    assert caught.value.message.startswith(f"{2**64 - 1} is a plain number")
    with pytest.raises(QuantityKindError) as caught:
        read_quantity(2**64, TIME)
    assert caught.value.message.startswith("a very large integer is a plain number")


def test_read_number_message_for_a_quantity_names_the_quantity() -> None:
    with pytest.raises(QuantityKindError) as caught:
        read_number("2 min")
    assert "'2 min'" in caught.value.message
    assert "Remove the unit" in caught.value.hint


# --- Quantity, Dimension, si_symbol, units_of ---------------------------------------------


def test_si_symbol() -> None:
    assert si_symbol(TIME) == "s"
    assert si_symbol(DIMENSIONLESS) == "1"


def test_every_dimension_has_an_si_symbol_and_hints() -> None:
    for dimension in Dimension:
        assert si_symbol(dimension)
        with pytest.raises(QuantityError) as caught:
            parse_quantity("2 x", dimension)
        assert caught.value.hint
        assert caught.value.message


def test_quantity_carries_its_si_unit() -> None:
    assert Quantity(90.0, TIME).unit == "s"
    assert Quantity(0.5, DIMENSIONLESS).unit == "1"


def test_quantity_is_immutable_and_comparable() -> None:
    quantity = Quantity(1.0, TIME)
    assert quantity == Quantity(1.0, TIME)
    assert quantity != Quantity(1.0, DIMENSIONLESS)
    with pytest.raises(FrozenInstanceError):
        quantity.magnitude = 2.0  # type: ignore[misc]


def test_phase_1_units() -> None:
    rate = Dimension.RATE
    assert dict(PHASE_1_UNITS) == {
        "s": TIME,
        "min": TIME,
        "h": TIME,
        "d": TIME,
        "1/s": rate,
        "1/min": rate,
        "1/h": rate,
        "1/d": rate,
    }
    assert units_of(TIME) == ("s", "min", "h", "d")
    assert units_of(DIMENSIONLESS) == ()


def test_pint_does_not_leak_out_of_the_module() -> None:
    import ithax.model.units as units

    public = [getattr(units, name) for name in units.__all__]
    assert all("pint" not in getattr(type(obj), "__module__", "") for obj in public)
    assert all("pint" not in getattr(obj, "__module__", "") for obj in public)


def test_only_the_units_module_imports_pint() -> None:
    from pathlib import Path

    import ithax

    src = Path(ithax.__file__).resolve().parent
    importers = sorted(
        str(path.relative_to(src))
        for path in src.rglob("*.py")
        if "import pint" in path.read_text(encoding="utf-8")
        or "from pint" in path.read_text(encoding="utf-8")
    )
    assert importers == ["model/units.py"]
