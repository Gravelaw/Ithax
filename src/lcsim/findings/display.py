"""How a finding's text shows numbers (spec 4 "Finding rules": "Evidence values are in SI
units as in `summary.json`; the text uses display units"; research note
``docs/research/spec-4-findings-wording.md``, decision 6; AKS-117, owner to confirm).

- A time is shown in the largest Phase 1 unit it reaches (``s``, ``min``, ``h``, ``d``),
  and a half-width in the unit of its mean, so "15.7 min plus or minus 2.09 min".
- A rate (``1/s``) is shown per hour.
- A fraction metric (``utilization``, ``availability``, ``scheduled_fraction``) is a
  percentage; any other plain number is shown as it is.
- Numbers have three significant figures (four for an optimization's values), never an
  exponent, with a comma between thousands.
"""

from __future__ import annotations

import math

__all__ = ["figures", "percent", "quantity", "value_text"]

# Phase 1 time units, largest first, with their length in seconds (spec 1 "Quantities").
_TIME_UNITS = (("d", 86_400.0), ("h", 3_600.0), ("min", 60.0))

# Metrics measured as a share of something, shown as percentages (spec 2 "Statistic
# definitions").
_FRACTIONS = (".utilization", ".availability", ".scheduled_fraction")


def figures(value: float, digits: int = 3) -> str:
    """``value`` to ``digits`` significant figures, without an exponent: 15.6914 is "15.7",
    2200 is "2,200" and 13.999999999999998 to four figures is "14"."""
    if value == 0:
        return "0"
    places = digits - 1 - math.floor(math.log10(abs(value)))
    rounded = round(value, places)
    # Rounding can carry into the next power of ten (9.996 is 10.0); recount the places.
    places = max(digits - 1 - math.floor(math.log10(abs(rounded))), 0)
    text = f"{rounded:,.{places}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def percent(fraction: float) -> str:
    """A fraction as a whole percentage, a half rounding up: 0.900985 is "90%"."""
    return f"{math.floor(fraction * 100 + 0.5)}%"


def _time_unit(seconds: float) -> tuple[str, float]:
    for symbol, size in _TIME_UNITS:
        if abs(seconds) >= size:
            return symbol, size
    return "s", 1.0


def quantity(value: float, unit: str, *, like: float | None = None) -> str:
    """A value in SI units as the text shows it: a time (``s``) in the largest unit that
    ``like`` (default: the value itself) reaches, a rate (``1/s``) per hour, anything else
    as a plain number."""
    if unit == "s":
        symbol, size = _time_unit(value if like is None else like)
        return f"{figures(value / size)} {symbol}"
    if unit == "1/s":
        return f"{figures(value * 3600)} per hour"
    return figures(value)


def value_text(metric: str, value: float, unit: str, *, like: float | None = None) -> str:
    """A metric's value as the text shows it: a fraction metric as a percentage to three
    figures ("90.1%"), otherwise as ``quantity`` shows it."""
    if unit == "1" and metric.endswith(_FRACTIONS):
        return f"{figures(value * 100)}%"
    return quantity(value, unit, like=like)
