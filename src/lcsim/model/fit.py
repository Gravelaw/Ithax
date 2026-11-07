"""Fitting the spec 1 distributions to a column of numbers (spec 3
``POST .../data/{file}/fit``; research note ``docs/research/spec-3-distribution-fit.md``;
AKS-113).

``fit_column(values, unit)`` returns the candidates best first. Each is a spec 1
distribution object in spec 1's parameterisation, its time fields written as quantities in
the column's unit (plain numbers when the column has none; a Weibull ``shape`` is always
one), and its fit score, the Kolmogorov-Smirnov statistic from 0 (best) to 1.

The fit is ``scipy.stats`` maximum likelihood (guide rule 7: no estimator, optimiser or
iteration is written here). What this module adds:

- **Which families.** A column whose values are all equal is ``constant`` alone. Otherwise
  ``exponential`` (values not negative, mean above zero), ``uniform``, ``triangular``,
  ``normal``, and ``lognormal`` and ``weibull`` (values above zero). ``empirical`` is not
  fitted: the column itself is its ``data``.
- **A change of unit.** The values are divided by their largest absolute value before the
  fit, and the fitted location and scale multiplied back. That is exact for these families
  (shapes and the statistic do not change) and keeps scipy's optimiser in range for
  columns such as 10⁻³⁰⁰ or 10³⁰⁰ seconds, which it otherwise fits wrongly.
- **The mapping** to spec 1's fields, and for the lognormal the closed-form mean and sd of
  the variable from the fitted sigma and mu.
- **Checks.** A family whose fit raises, warns its way to a value that is not finite, or
  gives fields spec 1 would refuse (E160: ``sd``, ``shape``, ``scale`` or a positive
  ``mean`` not above zero, ``min`` > ``mode`` or ``mode`` > ``max``) is left out.
"""

from __future__ import annotations

import logging
import math
import warnings
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import numpy
import scipy.stats

from lcsim.model.data import fits_in_seconds

__all__ = ["SCORE", "Candidate", "fit_column"]

_log = logging.getLogger(__name__)

#: The name of the fit score (spec 3: ``"ks"``, the Kolmogorov-Smirnov statistic).
SCORE = "ks"

Values = numpy.ndarray[Any, numpy.dtype[numpy.float64]]


@dataclass(frozen=True)
class Candidate:
    """One fitted distribution: a spec 1 distribution object and its score."""

    distribution: Mapping[str, Any]
    score: float

    def as_dict(self) -> dict[str, Any]:
        """The candidate as the API writes it."""
        return {"distribution": dict(self.distribution), "score": self.score}


@dataclass(frozen=True)
class _Family:
    """A spec 1 distribution fitted by a scipy family: how to fit it (``fit`` takes the
    scaled values) and how its fitted parameters, with the scale factor, give spec 1's
    fields as floats in the column's unit; ``None`` for fields spec 1 would refuse."""

    scipy_name: str
    fit: Callable[[Values], tuple[float, ...]]
    fields: Callable[[tuple[float, ...], float], dict[str, float] | None]
    positive: bool = False  # values above zero
    not_negative: bool = False  # values from zero, with a mean above zero


def _exponential(params: tuple[float, ...], factor: float) -> dict[str, float] | None:
    _loc, scale = params
    return {"mean": scale * factor}


def _uniform(params: tuple[float, ...], factor: float) -> dict[str, float] | None:
    loc, scale = params
    return {"min": loc * factor, "max": (loc + scale) * factor}


def _triangular(params: tuple[float, ...], factor: float) -> dict[str, float] | None:
    shape, loc, scale = params
    return {
        "min": loc * factor,
        "mode": (loc + shape * scale) * factor,
        "max": (loc + scale) * factor,
    }


def _normal(params: tuple[float, ...], factor: float) -> dict[str, float] | None:
    loc, scale = params
    return {"mean": loc * factor, "sd": scale * factor}


def _lognormal(params: tuple[float, ...], factor: float) -> dict[str, float] | None:
    # scipy: s = sigma and scale = exp(mu); the variable's mean is exp(mu + sigma^2 / 2)
    # and its sd mean * sqrt(exp(sigma^2) - 1).
    sigma, _loc, scale = params
    mean = scale * factor * math.exp(sigma * sigma / 2)
    return {"mean": mean, "sd": mean * math.sqrt(math.expm1(sigma * sigma))}


def _weibull(params: tuple[float, ...], factor: float) -> dict[str, float] | None:
    shape, _loc, scale = params
    return {"shape": shape, "scale": scale * factor}


_FAMILIES: Mapping[str, _Family] = MappingProxyType(
    {
        "exponential": _Family(
            "expon", lambda x: scipy.stats.expon.fit(x, floc=0), _exponential, not_negative=True
        ),
        "uniform": _Family("uniform", lambda x: scipy.stats.uniform.fit(x), _uniform),
        "triangular": _Family("triang", lambda x: scipy.stats.triang.fit(x), _triangular),
        "normal": _Family("norm", lambda x: scipy.stats.norm.fit(x), _normal),
        "lognormal": _Family(
            "lognorm", lambda x: scipy.stats.lognorm.fit(x, floc=0), _lognormal, positive=True
        ),
        "weibull": _Family(
            "weibull_min",
            lambda x: scipy.stats.weibull_min.fit(x, floc=0),
            _weibull,
            positive=True,
        ),
    }
)

# Fields spec 1 requires above zero, by distribution (E160).
_ABOVE_ZERO: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "exponential": ("mean",),
        "normal": ("sd",),
        "lognormal": ("mean", "sd"),
        "weibull": ("shape", "scale"),
    }
)
# Fields that are plain numbers whatever the column's unit.
_PLAIN = frozenset({"shape"})


def fit_column(values: Sequence[float] | Values, unit: str | None) -> list[Candidate]:
    """The spec 1 distributions fitted to ``values`` (at least one finite number), best
    first, ties in spec 1 order; time fields in ``unit`` (``None``: plain numbers).
    ``ValueError`` for no values or a value that is not finite (a programming error: the
    column index holds only finite numbers)."""
    column = numpy.asarray(values, dtype=numpy.float64)
    if column.size == 0 or not numpy.all(numpy.isfinite(column)):
        raise ValueError("a fit needs at least one value, and every value finite")
    low, high = float(numpy.min(column)), float(numpy.max(column))
    if low == high:
        return [Candidate({"dist": "constant", "value": _field("value", low, unit)}, 0.0)]
    factor = max(abs(low), abs(high))
    scaled = column / factor
    candidates: list[Candidate] = []
    for name, family in _FAMILIES.items():
        if family.positive and low <= 0:
            continue
        if family.not_negative and (low < 0 or float(column.mean()) <= 0):
            continue
        candidate = _candidate(name, family, scaled, factor, unit)
        if candidate is not None:
            candidates.append(candidate)
    order = {name: number for number, name in enumerate(_FAMILIES)}
    candidates.sort(key=lambda item: (item.score, order[str(item.distribution["dist"])]))
    return candidates


def _candidate(
    name: str, family: _Family, scaled: Values, factor: float, unit: str | None
) -> Candidate | None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # scipy warns on degenerate fits; the checks decide
        try:
            params = tuple(float(value) for value in family.fit(scaled))
            fields = family.fields(params, factor)
            score = _score(family.scipy_name, scaled, params)
        except Exception:  # a fit that fails is left out, never an error (research note)
            _log.info("The %s fit of a column failed.", name, exc_info=True)
            return None
    if fields is None or not _agrees(name, fields, unit) or not 0.0 <= score <= 1.0:
        return None
    distribution: dict[str, Any] = {"dist": name}
    distribution.update({key: _field(key, value, unit) for key, value in fields.items()})
    return Candidate(distribution, score)


def _score(scipy_name: str, scaled: Values, params: tuple[float, ...]) -> float:
    """The Kolmogorov-Smirnov statistic of ``scaled`` against the fitted family."""
    result = scipy.stats.kstest(scaled, getattr(scipy.stats, scipy_name).cdf, args=params)
    return float(result.statistic)


def _agrees(name: str, fields: Mapping[str, float], unit: str | None) -> bool:
    """Whether spec 1 takes ``fields`` for ``name``: finite, each time field a finite
    number of seconds in ``unit`` (E141 otherwise; Codex on PR #37), the positive fields
    above zero, and ``min`` ≤ ``mode`` ≤ ``max`` (E160)."""
    if not all(math.isfinite(value) for value in fields.values()):
        return False
    if unit is not None and not all(
        fits_in_seconds(value, unit) for key, value in fields.items() if key not in _PLAIN
    ):
        return False
    if any(fields[key] <= 0 for key in _ABOVE_ZERO.get(name, ())):
        return False
    ordered = [fields[key] for key in ("min", "mode", "max") if key in fields]
    return ordered == sorted(ordered)


def _field(key: str, value: float, unit: str | None) -> float | str:
    """A field as spec 1 writes it: a quantity in ``unit`` for a time, else a number."""
    if unit is None or key in _PLAIN:
        return value
    return f"{float(value)!r} {unit}"
