"""Quantities: parse "number unit" strings and convert them to SI at load.

Spec 1 "Units" and "Quantities". A quantity is written as a JSON number, exactly one space
(U+0020) and a Phase 1 unit symbol, as in ``"1.5 min"``. The grammar is checked here
first; pint is used only to tell a known unit of the wrong dimension (E140) from an
unreadable string (E141), and to convert. This module is the only place that imports
pint, and no unit string leaves it: a parsed value is a ``Quantity`` holding an SI float.

The errors raised here are the conditions behind spec 1 issue codes E123, E140 and E141.
They carry the code, a plain-language message that quotes the value, and a hint. The
validation pass that calls these functions knows the component and the setting, and turns
each error into an issue object with ``component`` and ``path`` filled.
"""

from __future__ import annotations

import decimal
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from fractions import Fraction
from functools import cache
from types import MappingProxyType
from typing import ClassVar

import pint

from ithax.strict_json import is_finite_real, is_number

__all__ = [
    "PHASE_1_UNITS",
    "UNIT_SIZES",
    "Dimension",
    "Quantity",
    "QuantityDimensionError",
    "QuantityError",
    "QuantityKindError",
    "QuantityParseError",
    "in_unit",
    "parse_quantity",
    "quantity_dimension",
    "read_number",
    "read_quantity",
    "si_symbol",
    "units_of",
]


class Dimension(Enum):
    """The kind of value a setting or result holds."""

    TIME = "time"
    RATE = "rate"  # items per unit of time (#77; format 0.3)
    DIMENSIONLESS = "dimensionless"


# SI symbol per dimension, as written in the `unit` column of the results tables
# (spec 1 "Tables for the process domain": an SI symbol or `1`).
_SI_SYMBOL: Mapping[Dimension, str] = MappingProxyType(
    {Dimension.TIME: "s", Dimension.RATE: "1/s", Dimension.DIMENSIONLESS: "1"}
)

# Each dimension as pint states it: base dimension to exponent. Written out rather than
# asked of pint, because pint 0.25 cannot give the dimensionality of "dimensionless".
_PINT_DIMENSIONALITY: Mapping[Dimension, Mapping[str, float]] = MappingProxyType(
    {Dimension.TIME: {"[time]": 1}, Dimension.RATE: {"[time]": -1}, Dimension.DIMENSIONLESS: {}}
)

# Spec 1 "Quantities": the Phase 1 units, written exactly as listed; case matters. The
# rate units arrived in format 0.3 (#77), for a constraint on a rate.
PHASE_1_UNITS: Mapping[str, Dimension] = MappingProxyType(
    {
        "s": Dimension.TIME,
        "min": Dimension.TIME,
        "h": Dimension.TIME,
        "d": Dimension.TIME,
        "1/s": Dimension.RATE,
        "1/min": Dimension.RATE,
        "1/h": Dimension.RATE,
        "1/d": Dimension.RATE,
    }
)

# Each Phase 1 unit's size in SI units, exactly: a minute is 60 s, a rate per hour 1/3600
# per second. Every conversion of a quantity to or from a unit goes through these (#77,
# review of PR #165): a float product such as 1e308 x 3600 overflows, an exact one does
# not, and a test checks that pint agrees with each size.
UNIT_SIZES: Mapping[str, Fraction] = MappingProxyType(
    {
        "s": Fraction(1),
        "min": Fraction(60),
        "h": Fraction(3600),
        "d": Fraction(86400),
        "1/s": Fraction(1),
        "1/min": Fraction(1, 60),
        "1/h": Fraction(1, 3600),
        "1/d": Fraction(1, 86400),
    }
)

# How each dimension is named in messages and hints.
_EXPECTED: Mapping[Dimension, str] = MappingProxyType(
    {
        Dimension.TIME: "a time",
        Dimension.RATE: "a rate",
        Dimension.DIMENSIONLESS: "a plain number with no unit",
    }
)

# The hint given with each error, by the dimension the setting expects.
_HINT: Mapping[Dimension, str] = MappingProxyType(
    {
        Dimension.TIME: "Write a number, one space and one of the units s, min, h or d, "
        "as in '1.5 min'.",
        Dimension.RATE: "Write a number, one space and one of the units 1/s, 1/min, 1/h or "
        "1/d, as in '30 1/h'.",
        Dimension.DIMENSIONLESS: "Remove the unit and write the number alone, as in 3.",
    }
)

# The JSON number grammar (spec 1 "Quantities"), then exactly one U+0020, then a unit
# token with no whitespace. ASCII only: `[0-9]`, not `\d`, so other digits never match.
_QUANTITY = re.compile(
    r"(?P<number>-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?) (?P<unit>[^\s]+)"
)


@dataclass(frozen=True)
class Quantity:
    """A value converted to SI at load: ``magnitude`` in SI units of ``dimension``."""

    magnitude: float
    dimension: Dimension

    @property
    def unit(self) -> str:
        """The SI symbol of the magnitude, for the results ``unit`` column."""
        return si_symbol(self.dimension)


class QuantityError(ValueError):
    """A setting value that is not a valid quantity or number; carries a spec 1 code."""

    code: ClassVar[str]

    def __init__(self, value: object, message: str, hint: str) -> None:
        super().__init__(message)
        self.value = value  # the value as written in the model file
        self.message = message
        self.hint = hint


class QuantityParseError(QuantityError):
    """E141: Quantity cannot be parsed."""

    code = "E141"


class QuantityDimensionError(QuantityError):
    """E140: Quantity has the wrong kind of unit."""

    code = "E140"


class QuantityKindError(QuantityError):
    """E123: a quantity where a plain number is expected, or the reverse."""

    code = "E123"


def si_symbol(dimension: Dimension) -> str:
    """The SI unit symbol of ``dimension``: ``s`` for time, ``1`` for dimensionless."""
    return _SI_SYMBOL[dimension]


def units_of(dimension: Dimension) -> tuple[str, ...]:
    """The Phase 1 unit symbols of ``dimension``, in spec order (empty if none)."""
    return tuple(symbol for symbol, dim in PHASE_1_UNITS.items() if dim is dimension)


def quantity_dimension(text: str) -> Dimension | None:
    """The dimension of the Phase 1 unit ``text`` is written in, when ``text`` follows the
    grammar with a Phase 1 unit (``"30 1/h"`` is a rate); ``None`` otherwise."""
    match = _QUANTITY.fullmatch(text)
    return None if match is None else PHASE_1_UNITS.get(match.group("unit"))


def parse_quantity(text: str, expected: Dimension) -> Quantity:
    """Parse a quantity string such as ``"1.5 min"`` and convert it to SI.

    Raises ``QuantityDimensionError`` (E140) when the grammar holds and the unit is a
    Phase 1 unit of another dimension (``"30 1/h"`` for a time), or one the units library
    knows with no reading of the ``expected`` dimension (``"5 m"`` for a time). Raises
    ``QuantityParseError`` (E141) for any other string that breaks the spec 1 grammar,
    including a known unit of the right dimension that is not a Phase 1 unit (``"2 ms"``),
    and for a number whose SI value is not finite.
    """
    match = _QUANTITY.fullmatch(text)
    if match is None:
        raise _unreadable(text, expected)
    number, unit = match.group("number"), match.group("unit")
    if PHASE_1_UNITS.get(unit) is not expected:
        if unit in PHASE_1_UNITS or _known_only_in_other_dimensions(unit, expected):
            raise QuantityDimensionError(
                text,
                f"'{text}' has the wrong kind of unit: {_EXPECTED[expected]} is expected.",
                _HINT[expected],
            )
        raise _unreadable(text, expected)
    magnitude = _si_magnitude(number, unit)
    if not math.isfinite(magnitude):
        raise QuantityParseError(
            text,
            f"'{text}' is too large to be read as a quantity.",
            "Use a smaller number or a larger unit.",
        )
    # "-0 s" is stored as 0.0, so that equal times compare and print the same.
    return Quantity(magnitude + 0.0, expected)


def _si_magnitude(number: str, unit: str) -> float:
    """The written ``number`` in ``unit`` in SI units (seconds for a time, per second for a
    rate), possibly infinite. A number that is a finite float is converted by pint, as
    always. One beyond a float may still have a finite SI value in a unit below 1 (``"1e309
    1/h"`` is about 2.8e305 per second), so it is scaled exactly (review of PR #165)."""
    written = float(number)
    if math.isfinite(written):
        return float(_registry().Quantity(written, unit).to_base_units().magnitude)
    size = UNIT_SIZES[unit]
    with decimal.localcontext() as context:
        context.traps[decimal.Overflow] = False  # beyond the context: Infinity, then E141
        try:
            exact = Decimal(number) * Decimal(size.numerator) / Decimal(size.denominator)
        except decimal.InvalidOperation:
            # An exponent beyond decimal's own range ("1e99999999999999999999 s"): far
            # beyond a float in any unit, so E141, never a raise (review of PR #165).
            return math.copysign(math.inf, written)
        return float(exact)


def in_unit(si: float | Fraction, unit: str) -> float | None:
    """A value in SI units expressed in the Phase 1 unit ``unit``: seconds in minutes,
    a rate per second per hour. Exact, so a finite result is the correctly rounded one,
    as a float division or product gives; ``None`` when ``si`` is not finite or the result
    is beyond the range of a float (1e308 per second is 3.6e311 per hour). Every
    conversion from SI to a unit for a message or a display goes through here (review of
    PR #165)."""
    if isinstance(si, float) and not math.isfinite(si):
        return None
    try:
        return float(Fraction(si) / UNIT_SIZES[unit])
    except OverflowError:
        return None


def read_quantity(value: object, expected: Dimension) -> Quantity:
    """Read a setting value that must be a quantity of the ``expected`` dimension.

    ``value`` is a JSON value from the model file, after any ``{"$param": ...}``
    reference has been resolved. A string is parsed with ``parse_quantity``. A plain JSON
    number raises ``QuantityKindError`` (E123). Any other value (true, false, null, an
    array or an object) raises ``QuantityParseError`` (E141).
    """
    if isinstance(value, str):
        return parse_quantity(value, expected)
    if is_number(value):
        raise QuantityKindError(
            value,
            f"{_number_text(value)} is a plain number, but {_EXPECTED[expected]} with a unit "
            "is expected.",
            _HINT[expected],
        )
    raise _unreadable(value, expected)


def read_number(value: object) -> int | float:
    """Read a setting value that must be a plain number (a count, probability or capacity).

    ``value`` is a JSON value from the model file, after any ``{"$param": ...}``
    reference has been resolved. A finite JSON number is returned unchanged, so an
    integer stays an ``int``. Anything else raises ``QuantityKindError`` (E123): a
    quantity such as ``"2 min"``, any other string, true, false, null, an array, an
    object, or a non-finite float.
    """
    # An int is always finite: is_finite_real never converts it to a float, which would
    # overflow for an integer above about 1.8e308, such as 10**309.
    if is_finite_real(value):
        return value
    if isinstance(value, str):
        message = f"'{value}' is text, but a plain number with no unit is expected."
    else:
        message = f"{_json_repr(value)} is not a number; a plain number with no unit is expected."
    raise QuantityKindError(value, message, _HINT[Dimension.DIMENSIONLESS])


def _number_text(value: int | float) -> str:
    # repr of an int with more than 4,300 digits raises ValueError (Python's integer
    # string limit), and a long one would swamp the message.
    if isinstance(value, int) and value.bit_length() > 64:
        return "a very large integer"
    return repr(value)


def _json_repr(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "an array"
    if isinstance(value, dict):
        return "an object"
    return repr(value)


def _unreadable(value: object, expected: Dimension) -> QuantityParseError:
    shown = f"'{value}'" if isinstance(value, str) else _json_repr(value)
    return QuantityParseError(
        value,
        f"{shown} cannot be read as a quantity; {_EXPECTED[expected]} is expected.",
        _HINT[expected],
    )


def _known_only_in_other_dimensions(unit: str, expected: Dimension) -> bool:
    """True when pint knows ``unit`` and none of its readings has the expected dimension.

    ``parse_unit_name`` returns every (prefix, name, suffix) reading of a single unit
    name, and nothing for an expression such as ``m*s``. Some names have several readings
    (``cd`` is candela or centi-day); if any reading has the expected dimension, the unit
    is the right kind but not a Phase 1 unit, which is E141, not E140.
    """
    registry = _registry()
    readings = registry.parse_unit_name(unit)
    if not readings:
        return False
    target = _PINT_DIMENSIONALITY[expected]
    return all(dict(registry.get_dimensionality(name)) != target for _, name, _ in readings)


@cache
def _registry() -> pint.UnitRegistry:  # type: ignore[type-arg,unused-ignore]
    # pint 0.25 (Python 3.11) declares UnitRegistry generic and pint 0.26 does not, so
    # the ignore covers the missing type argument on 0.25 and is unused on 0.26.
    # One registry per process: building one takes about 0.14 s (research note).
    return pint.UnitRegistry()
