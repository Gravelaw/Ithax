"""Distribution samplers (spec 1 "Distributions").

``sampler_for`` turns a loaded ``Distribution`` into a ``Sampler``: a function that takes
one of the generators of ``ithax.model.streams`` and returns one sample, a float in SI
units. Parameter references are resolved when the sampler is made, as
``ithax.model.validation.distribution_mean`` resolves them: ``values`` (a scenario's
``set``) replaces the ``value`` of the parameters it names. The model has been validated,
so the fields agree (E160) and every reference names a parameter (E150).

``sampler_from_numbers`` makes the same sampler from fields already resolved to SI floats,
as an engine's own input holds them (the process adapter's ``engine/input.json``).

An ``empirical`` with ``data`` samples the column a run target read into the distribution's
``values``, in seconds, beside its ``data`` reference (``ithax.runs.snapshots``; AKS-113);
one whose column has not been read raises ``DataNotReadError`` (E162).

Every distribution setting in Phase 1 is a time, and every sample below 0 s is set to 0 s,
whatever the distribution (spec 1 "Distributions", proposed default, owner to confirm).

Sampling uses numpy's ``Generator`` methods, one draw per call; no numerical method is
written here (guide rule 7).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
from typing import ClassVar, TypeAlias

import numpy

from ithax.model.model import DataRef, Distribution, Model, ParameterValue, ParamRef, Scalar
from ithax.model.units import Quantity

__all__ = ["DataNotReadError", "Sampler", "sampler_for", "sampler_from_numbers"]

# One sample from the generator given, in SI units, never below 0.
Sampler: TypeAlias = Callable[[numpy.random.Generator], float]


class DataNotReadError(Exception):
    """An ``empirical`` with ``data`` whose column has not been read: only a run target
    reads it, from the bytes of the file it hashes (spec 1 "Distributions"; AKS-113).

    Carries a spec 1 code, a message and a hint, so the caller turns it into an issue with
    ``ithax.model.issues.Issue.from_problem``. E162 is the code of a data reference that
    cannot be used.
    """

    code: ClassVar[str] = "E162"

    def __init__(self, data: DataRef) -> None:
        self.data = data
        self.message = (
            f"the 'empirical' distribution reads column '{data.column}' of '{data.file}', "
            "which has not been read: a run reads it from the project's data/ folder."
        )
        self.hint = "Start the model as a run, or write the values inline with 'values'."
        super().__init__(self.message)


def _clip(sample: float) -> float:
    """A sampled time below 0 s is 0 s; ``max(0.0, -0.0)`` is ``0.0``, never ``-0.0``."""
    return max(0.0, float(sample))


def _magnitude(value: ParameterValue) -> float:
    return value.magnitude if isinstance(value, Quantity) else float(value)


def sampler_for(
    model: Model,
    distribution: Distribution,
    values: Mapping[str, ParameterValue] | None = None,
) -> Sampler:
    """The sampler of ``distribution``, with its parameter references resolved.

    Raises ``DataNotReadError`` (E162) for an ``empirical`` with ``data`` whose column has
    not been read into its ``values``, and
    ``ValueError`` for a ``dist`` spec 1 does not list, which loading never builds.
    """
    overrides = values or {}

    def number(scalar: Scalar) -> float:
        if isinstance(scalar, ParamRef):
            return _magnitude(
                overrides.get(scalar.parameter, model.parameters[scalar.parameter].value)
            )
        return _magnitude(scalar)

    if distribution.data is not None and distribution.values is None:
        raise DataNotReadError(distribution.data)
    fields = {name: number(scalar) for name, scalar in distribution.fields.items()}
    listed = (
        [number(scalar) for scalar in distribution.values]
        if distribution.values is not None
        else None
    )
    return sampler_from_numbers(distribution.dist, fields, listed)


def sampler_from_numbers(
    dist: str,
    fields: Mapping[str, float],
    values: Sequence[float] | None = None,
) -> Sampler:
    """The sampler of distribution ``dist`` whose named ``fields`` (and, for an
    ``empirical``, ``values``) are already SI floats, with no parameter reference.

    Raises ``ValueError`` for a ``dist`` spec 1 does not list, and for an ``empirical``
    without ``values``.
    """
    if dist == "empirical":
        if not values:
            raise ValueError("an 'empirical' distribution needs at least one value")
        return _empirical(values)
    maker = _MAKERS.get(dist)
    if maker is None:
        raise ValueError(f"no sampler for distribution {dist!r}")
    return maker(fields)


def _constant(fields: Mapping[str, float]) -> Sampler:
    value = _clip(fields["value"])
    return lambda rng: value


def _exponential(fields: Mapping[str, float]) -> Sampler:
    scale = fields["mean"]  # `mean` is 1/rate, sampled as the scale
    return lambda rng: _clip(rng.exponential(scale))


def _uniform(fields: Mapping[str, float]) -> Sampler:
    low, high = fields["min"], fields["max"]
    return lambda rng: _clip(rng.uniform(low, high))


def _triangular(fields: Mapping[str, float]) -> Sampler:
    low, mode, high = fields["min"], fields["mode"], fields["max"]
    if low == high:  # allowed by spec 1; numpy's triangular refuses left == right
        value = _clip(low)
        return lambda rng: value
    return lambda rng: _clip(rng.triangular(low, mode, high))


def _normal(fields: Mapping[str, float]) -> Sampler:
    mean, sd = fields["mean"], fields["sd"]
    return lambda rng: _clip(rng.normal(mean, sd))


def _log1p_square(log_ratio: float) -> float:
    """ln(1 + r²) for r = exp(``log_ratio``), without forming r² when it would overflow."""
    if log_ratio <= 0:
        return math.log1p(math.exp(2 * log_ratio))
    return 2 * log_ratio + math.log1p(math.exp(-2 * log_ratio))


def _lognormal(fields: Mapping[str, float]) -> Sampler:
    # The mean and sd of the variable itself: σ² = ln(1 + sd²/mean²), μ = ln(mean) - σ²/2.
    # Computed from ln(sd/mean) so that no square or ratio underflows or overflows for any
    # positive finite mean and sd: with r = sd/mean, ln(1 + r²) = log1p(r²) for r ≤ 1 and
    # 2·ln r + log1p(1/r²) for r > 1.
    mean, sd = fields["mean"], fields["sd"]
    sigma2 = _log1p_square(math.log(sd) - math.log(mean))
    mu = math.log(mean) - sigma2 / 2
    sigma = math.sqrt(sigma2)
    return lambda rng: _clip(rng.lognormal(mu, sigma))


def _weibull(fields: Mapping[str, float]) -> Sampler:
    # numpy draws the one-parameter Weibull (scale 1); the scale multiplies it.
    shape, scale = fields["shape"], fields["scale"]
    return lambda rng: _clip(scale * rng.weibull(shape))


def _empirical(values: Sequence[float]) -> Sampler:
    # Equal probability, with replacement; loading guarantees at least one value (E160).
    table = tuple(_clip(value) for value in values)
    count = len(table)
    return lambda rng: table[int(rng.integers(count))]


_MAKERS: Mapping[str, Callable[[Mapping[str, float]], Sampler]] = MappingProxyType(
    {
        "constant": _constant,
        "exponential": _exponential,
        "uniform": _uniform,
        "triangular": _triangular,
        "normal": _normal,
        "lognormal": _lognormal,
        "weibull": _weibull,
    }
)
