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
- **The histogram** of the column for the Data screen's chart (spec 3 fit note; AKS-120):
  Sturges' rule, at most ``MAX_BINS`` bins of equal width from the smallest value to the
  largest, worked out in units of the largest absolute value so every edge is finite.
  Counting values into bins is a closed-form summary, not a solver (guide rule 7).
- **One gate.** A family whose fit raises is left out. Every candidate, the ``constant``
  one included, then passes one gate, ``_admitted``: it is loaded in a minimal model by the
  model layer, and left out if loading reports an error, such as a field that is not a
  finite number of seconds (E141) or fields spec 1 refuses (E160) (Codex on PR #37).
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

from ithax.model.loading import load_document
from ithax.model.migration import FORMAT_VERSION

__all__ = ["MAX_BINS", "SCORE", "Candidate", "fit_column", "histogram", "histogram_bins"]

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
        constant = Candidate({"dist": "constant", "value": _field("value", low, unit)}, 0.0)
        return [constant] if _admitted(constant, unit) else []
    factor = max(abs(low), abs(high))
    scaled = column / factor
    candidates: list[Candidate] = []
    for name, family in _FAMILIES.items():
        if family.positive and low <= 0:
            continue
        if family.not_negative and (low < 0 or float(column.mean()) <= 0):
            continue
        candidate = _candidate(name, family, scaled, factor, unit)
        if candidate is not None and _admitted(candidate, unit):
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
    if fields is None or not 0.0 <= score <= 1.0:
        return None
    distribution: dict[str, Any] = {"dist": name}
    distribution.update({key: _field(key, value, unit) for key, value in fields.items()})
    return Candidate(distribution, score)


def _score(scipy_name: str, scaled: Values, params: tuple[float, ...]) -> float:
    """The Kolmogorov-Smirnov statistic of ``scaled`` against the fitted family."""
    result = scipy.stats.kstest(scaled, getattr(scipy.stats, scipy_name).cdf, args=params)
    return float(result.statistic)


def _admitted(candidate: Candidate, unit: str | None) -> bool:
    """The one gate every candidate passes, whatever path made it (Codex on PR #37): the
    candidate is written into a minimal model, in the time setting of a source, and loaded
    by the model layer itself, which applies the rules it would meet in the user's model
    (E123, E140 and E141 for each field, so every time a finite number of seconds; E160
    for the fields that must agree). A candidate of a column without a unit is checked
    with its plain numbers read as seconds, the only way they could become a time."""
    distribution = dict(candidate.distribution)
    if unit is None:
        distribution = {
            key: value if key == "dist" or key in _PLAIN else _field(key, value, "s")
            for key, value in distribution.items()
        }
    document = {
        **_GATE_MODEL,
        "components": [
            {"id": "gate", "type": "source", "params": {"interarrival": distribution}},
            {"id": "exit", "type": "sink", "params": {}},
        ],
    }
    issues = load_document(document).issues
    return not any(issue.severity == "error" for issue in issues)


# The model the gate loads a candidate in: valid as it is, with a source whose
# `interarrival` is the candidate.
_GATE_MODEL: Mapping[str, Any] = MappingProxyType(
    {
        "format_version": FORMAT_VERSION,
        "meta": {"name": "Fit gate"},
        "domain": "process",
        "parameters": {},
        "connections": [{"from": "gate.out", "to": "exit.in"}],
        "experiments": [{"id": "base", "length": "8 h", "replications": 2, "seed": 0}],
        "run": {"target": "local", "fidelity": "standard"},
    }
)


def _field(key: str, value: float, unit: str | None) -> float | str:
    """A field as spec 1 writes it: a quantity in ``unit`` for a time, else a number."""
    if unit is None or key in _PLAIN:
        return value
    return f"{float(value)!r} {unit}"


#: The most bins a histogram has (spec 3 fit note).
MAX_BINS = 50


def histogram_bins(count: int) -> int:
    """Sturges' rule for ``count`` values, ``ceil(log2(count)) + 1``, at most ``MAX_BINS``;
    worked out on whole numbers, so it is exact for any count."""
    return min(MAX_BINS, (count - 1).bit_length() + 1)


def histogram(values: Values) -> dict[str, list[Any]]:
    """``{edges, counts}``: ``values`` (finite, at least one) counted in bins of equal width
    from the smallest to the largest; a bin holds its lower edge and not its upper one, the
    last bin both. A column whose values are all equal has one bin, both edges its value.
    The edges are found in units of the largest absolute value, so none overflows."""
    low = float(numpy.min(values))
    high = float(numpy.max(values))
    if low == high:
        return {"edges": [low, high], "counts": [int(values.size)]}
    largest = max(abs(low), abs(high))
    scaled_edges = numpy.linspace(low / largest, high / largest, histogram_bins(values.size) + 1)
    counts, _ = numpy.histogram(values / largest, bins=scaled_edges)
    edges = [float(edge) * largest for edge in scaled_edges]
    edges[0], edges[-1] = low, high
    return {"edges": edges, "counts": [int(count) for count in counts]}
