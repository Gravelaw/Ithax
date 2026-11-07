"""Fitting the spec 1 distributions to a column (spec 3 ``POST .../data/{file}/fit``;
research note ``docs/research/spec-3-distribution-fit.md``; AKS-113).

``fit_column(values, unit)`` wraps ``scipy.stats`` maximum likelihood (guide rule 7: no
estimator of its own) and returns candidates best first, each a spec 1 distribution object
in spec 1's parameterisation and its Kolmogorov-Smirnov statistic.
"""

import math
import warnings

import numpy
import pytest
import scipy.stats

from lcsim.model import fit
from lcsim.model.distributions import sampler_from_numbers
from lcsim.model.fit import SCORE, Candidate, fit_column
from lcsim.model.streams import generator_for
from lcsim.model.units import Dimension, parse_quantity

FAMILIES = ("exponential", "uniform", "triangular", "normal", "lognormal", "weibull")


def sample(dist: str, count: int, **fields: float) -> numpy.ndarray:
    """``count`` values from the product's own sampler, through a spec 1 stream."""
    sampler = sampler_from_numbers(dist, fields)
    rng = generator_for(7, 0, "fit")
    return numpy.array([sampler(rng) for _ in range(count)])


def by_name(candidates: list[Candidate]) -> dict[str, Candidate]:
    return {str(candidate.distribution["dist"]): candidate for candidate in candidates}


def seconds(text: object) -> float:
    assert isinstance(text, str)
    return parse_quantity(text, Dimension.TIME).magnitude


def test_the_score_is_named() -> None:
    assert SCORE == "ks"


def test_exponential_data_ranks_the_exponential_first_with_its_mean() -> None:
    values = sample("exponential", 4000, mean=2.0)
    candidates = fit_column(values, None)
    assert str(candidates[0].distribution["dist"]) in ("exponential", "weibull")
    found = by_name(candidates)
    assert set(found) == set(FAMILIES)
    exponential = found["exponential"].distribution
    assert exponential == {"dist": "exponential", "mean": pytest.approx(values.mean())}
    assert found["exponential"].score < 0.05
    assert found["uniform"].score > found["exponential"].score
    scores = [candidate.score for candidate in candidates]
    assert scores == sorted(scores)
    assert all(0.0 <= score <= 1.0 for score in scores)


def test_each_family_is_in_spec_1_parameterisation() -> None:
    values = sample("lognormal", 4000, mean=3.0, sd=1.5)
    found = by_name(fit_column(values, None))
    normal = found["normal"].distribution
    assert normal["mean"] == pytest.approx(values.mean())
    assert normal["sd"] == pytest.approx(values.std())  # MLE: the population sd
    uniform = found["uniform"].distribution
    assert uniform["min"] == pytest.approx(values.min())
    assert uniform["max"] == pytest.approx(values.max())
    triangular = found["triangular"].distribution
    assert triangular["min"] <= triangular["mode"] <= triangular["max"]
    lognormal = found["lognormal"].distribution
    assert lognormal["mean"] == pytest.approx(3.0, rel=0.05)
    assert lognormal["sd"] == pytest.approx(1.5, rel=0.1)
    # The same sigma and mu as scipy's own fit, converted by spec 1's formulas.
    s, _, scale = scipy.stats.lognorm.fit(values, floc=0)
    assert lognormal["mean"] == pytest.approx(scale * math.exp(s * s / 2), rel=1e-6)
    weibull = found["weibull"].distribution
    assert set(weibull) == {"dist", "shape", "scale"}
    assert list(by_name(fit_column(values, None))) == [
        str(c.distribution["dist"]) for c in fit_column(values, None)
    ]


def test_a_weibull_fit_recovers_shape_and_scale() -> None:
    values = sample("weibull", 4000, shape=1.5, scale=3.0)
    weibull = by_name(fit_column(values, None))["weibull"]
    assert weibull.distribution["shape"] == pytest.approx(1.5, rel=0.06)
    assert weibull.distribution["scale"] == pytest.approx(3.0, rel=0.05)
    assert weibull.score < 0.03


def test_time_fields_are_quantities_in_the_column_unit() -> None:
    values = sample("weibull", 2000, shape=1.2, scale=2.0)
    found = by_name(fit_column(values, "min"))
    exponential = found["exponential"].distribution
    assert isinstance(exponential["mean"], str) and exponential["mean"].endswith(" min")
    assert seconds(exponential["mean"]) == pytest.approx(values.mean() * 60)
    weibull = found["weibull"].distribution
    assert isinstance(weibull["shape"], float)  # always a plain number
    assert isinstance(weibull["scale"], str) and weibull["scale"].endswith(" min")
    for candidate in found.values():
        for key, value in candidate.distribution.items():
            if key not in ("dist", "shape"):
                seconds(value)  # spec 1 reads every time field back


def test_a_constant_column_gives_constant_alone() -> None:
    assert fit_column(numpy.full(20, 3.0), "s") == [
        Candidate({"dist": "constant", "value": "3.0 s"}, 0.0)
    ]
    assert fit_column(numpy.array([5.0]), None) == [
        Candidate({"dist": "constant", "value": 5.0}, 0.0)
    ]


def test_zero_or_negative_values_leave_out_the_positive_families() -> None:
    with_zero = numpy.concatenate([sample("exponential", 500, mean=2.0), [0.0]])
    assert set(by_name(fit_column(with_zero, None))) == {
        "exponential",
        "uniform",
        "triangular",
        "normal",
    }
    negative = sample("normal", 500, mean=0.5, sd=1.0) - 1.0
    assert set(by_name(fit_column(negative, None))) == {"uniform", "triangular", "normal"}


@pytest.mark.parametrize("size", [1e-300, 1e300])
def test_tiny_and_huge_columns_are_fitted_after_a_change_of_unit(size: float) -> None:
    values = sample("weibull", 1000, shape=1.5, scale=1.0) * size
    found = by_name(fit_column(values, None))
    assert set(found) == set(FAMILIES)
    weibull = found["weibull"].distribution
    assert weibull["shape"] == pytest.approx(1.5, rel=0.15)
    assert weibull["scale"] == pytest.approx(size, rel=0.15)
    # numpy's own std overflows at 1e300, so it is taken in units of `size`.
    assert found["normal"].distribution["sd"] == pytest.approx(
        (values / size).std() * size, rel=1e-6
    )
    for candidate in found.values():
        assert all(
            math.isfinite(value)
            for value in candidate.distribution.values()
            if isinstance(value, float)
        )


def test_two_values_still_give_candidates() -> None:
    found = by_name(fit_column(numpy.array([1.0, 2.0]), None))
    assert found["uniform"].distribution == {"dist": "uniform", "min": 1.0, "max": 2.0}
    assert found["normal"].distribution == {"dist": "normal", "mean": 1.5, "sd": 0.5}


def test_a_family_whose_fit_fails_is_left_out(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*args: object, **kwargs: object) -> tuple[float, ...]:
        raise scipy.stats.FitError("no fit")

    monkeypatch.setattr(scipy.stats.triang, "fit", broken)
    found = by_name(fit_column(sample("exponential", 300, mean=1.0), None))
    assert "triangular" not in found and "exponential" in found


def test_a_family_whose_fields_spec_1_would_refuse_is_left_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A normal fit with a zero sd (E160) or a non-finite field is not offered.
    monkeypatch.setattr(scipy.stats.norm, "fit", lambda *a, **k: (1.0, 0.0))
    monkeypatch.setattr(scipy.stats.weibull_min, "fit", lambda *a, **k: (math.inf, 0.0, 1.0))
    found = by_name(fit_column(sample("exponential", 300, mean=1.0), None))
    assert "normal" not in found and "weibull" not in found


def test_a_lognormal_whose_mean_overflows_is_left_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scipy.stats.lognorm, "fit", lambda *a, **k: (40.0, 0.0, 1.0))
    found = by_name(fit_column(sample("exponential", 300, mean=1.0), None))
    assert "lognormal" not in found


def test_a_score_that_is_not_finite_leaves_the_family_out(monkeypatch: pytest.MonkeyPatch) -> None:
    real = fit._score

    def score(name: str, *args: object) -> float:
        return math.nan if name == "uniform" else real(name, *args)  # type: ignore[arg-type]

    monkeypatch.setattr(fit, "_score", score)
    found = by_name(fit_column(sample("exponential", 300, mean=1.0), None))
    assert "uniform" not in found


def test_scipy_warnings_never_escape() -> None:
    values = numpy.array([1.0, 1.0, 1.0, 1.0000000001])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        fit_column(values, None)


def test_the_fit_is_deterministic() -> None:
    values = sample("triangular", 500, min=1.0, mode=2.0, max=4.0)
    assert fit_column(values, "h") == fit_column(values, "h")


@pytest.mark.parametrize("values", [[], [1.0, math.nan], [math.inf]])
def test_values_that_are_not_finite_are_a_programming_error(values: list[float]) -> None:
    with pytest.raises(ValueError):
        fit_column(numpy.array(values), None)


def test_a_candidate_is_a_mapping_and_a_float() -> None:
    candidate = fit_column(numpy.array([1.0, 2.0, 4.0]), None)[0]
    assert isinstance(candidate.score, float)
    assert candidate.as_dict() == {
        "distribution": candidate.distribution,
        "score": candidate.score,
    }
