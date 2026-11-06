"""Distribution samplers (spec 1 "Distributions").

``sampler_for`` turns a loaded ``Distribution`` into a ``Sampler``: a function that takes
one of the generators of ``lcsim.model.streams`` and returns one sample, a float in SI
units. Parameter references are resolved when the sampler is made, as
``lcsim.model.validation.distribution_mean`` resolves them: ``values`` (a scenario's
``set``) replaces the ``value`` of the parameters it names. The model has been validated,
so the fields agree (E160) and every reference names a parameter (E150).

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

from lcsim.model.model import DataRef, Distribution, Model, ParameterValue, ParamRef, Scalar
from lcsim.model.units import Quantity

__all__ = ["DataNotYetSupportedError", "Sampler", "sampler_for"]

# One sample from the generator given, in SI units, never below 0.
Sampler: TypeAlias = Callable[[numpy.random.Generator], float]


class DataNotYetSupportedError(Exception):
    """An ``empirical`` with ``data`` cannot be sampled until the import endpoint (M6).

    Carries a spec 1 code, a message and a hint, so the caller turns it into an issue with
    ``lcsim.model.issues.Issue.from_problem``. E162 is the code validation already gives
    every ``data`` reference until M6 (spec 1 "Distributions").
    """

    code: ClassVar[str] = "E162"

    def __init__(self, data: DataRef) -> None:
        self.data = data
        self.message = (
            f"the 'empirical' distribution reads column '{data.column}' of '{data.file}', "
            "and sampling from imported data is not available until milestone M6 "
            "(the import endpoint)."
        )
        self.hint = "Write the values inline with 'values' for now."
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

    Raises ``DataNotYetSupportedError`` (E162) for an ``empirical`` with ``data``, and
    ``ValueError`` for a ``dist`` spec 1 does not list, which loading never builds.
    """
    overrides = values or {}

    def number(scalar: Scalar) -> float:
        if isinstance(scalar, ParamRef):
            return _magnitude(
                overrides.get(scalar.parameter, model.parameters[scalar.parameter].value)
            )
        return _magnitude(scalar)

    fields = {name: number(scalar) for name, scalar in distribution.fields.items()}
    name = distribution.dist
    if name == "empirical":
        if distribution.data is not None:
            raise DataNotYetSupportedError(distribution.data)
        return _empirical([number(scalar) for scalar in distribution.values or ()])
    maker = _MAKERS.get(name)
    if maker is None:
        raise ValueError(f"no sampler for distribution {name!r}")
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


def _lognormal(fields: Mapping[str, float]) -> Sampler:
    # The mean and sd of the variable itself: σ² = ln(1 + sd²/mean²), μ = ln(mean) - σ²/2.
    mean, sd = fields["mean"], fields["sd"]
    sigma2 = math.log1p(sd * sd / (mean * mean))
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
