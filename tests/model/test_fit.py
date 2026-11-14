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

from ithax.model import fit
from ithax.model.distributions import sampler_from_numbers
from ithax.model.fit import SCORE, Candidate, fit_column
from ithax.model.streams import generator_for
from ithax.model.units import Dimension, parse_quantity

FAMILIES = ("exponential", "uniform", "triangular", "normal", "lognormal", "weibull")
#: For these columns scipy's triangular fit puts `min` below zero (-2.39 for the exponential
#: column of 4,000, -0.0004 for the Weibull one), which spec 1 refuses since #69 (E160), so
#: the gate leaves the triangular out.
WITHOUT_TRIANGULAR = set(FAMILIES) - {"triangular"}


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
    assert set(found) == WITHOUT_TRIANGULAR
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
    # The triangular's fitted `min` is below zero here too (E160 since #69).
    assert set(by_name(fit_column(with_zero, None))) == {"exponential", "uniform", "normal"}
    negative = sample("normal", 500, mean=0.5, sd=1.0) - 1.0
    # A uniform and a triangular of negative values have a `min` below zero (E160, #69); a
    # normal may have a negative mean, and W202 is a warning.
    assert set(by_name(fit_column(negative, None))) == {"normal"}


@pytest.mark.parametrize("size", [1e-300, 1e300])
def test_tiny_and_huge_columns_are_fitted_after_a_change_of_unit(size: float) -> None:
    values = sample("weibull", 1000, shape=1.5, scale=1.0) * size
    found = by_name(fit_column(values, None))
    assert set(found) == WITHOUT_TRIANGULAR
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


def test_a_field_that_would_overflow_in_seconds_is_left_out() -> None:
    """Every candidate's time fields read back as spec 1 quantities (Codex on PR #37)."""
    values = numpy.array([1e306, 2e306, 4e306, 8e306])
    for candidate in fit_column(values, "d"):
        for key, value in candidate.distribution.items():
            if key not in ("dist", "shape"):
                seconds(value)
    assert fit_column(values, "s")  # in seconds every field fits


def test_a_constant_column_that_overflows_in_seconds_gives_no_candidate() -> None:
    """The constant path goes through the same final gate as every family (Codex on PR
    #37, second round)."""
    assert fit_column(numpy.full(3, 1e308), "min") == []
    assert fit_column(numpy.full(3, 1e308), "s") == [
        Candidate({"dist": "constant", "value": "1e+308 s"}, 0.0)
    ]


def test_no_family_survives_when_every_field_would_overflow_in_seconds() -> None:
    values = numpy.array([1e306, 2e306, 4e306, 8e306])
    assert fit_column(values, "d") == []
    assert {str(c.distribution["dist"]) for c in fit_column(values, "s")} >= {"uniform", "normal"}


COLUMNS = {
    "exponential": sample("exponential", 300, mean=2.0),
    "lognormal": sample("lognormal", 300, mean=3.0, sd=2.0),
    "normal around zero": sample("normal", 300, mean=0.5, sd=1.0) - 1.0,
    "two values": numpy.array([1.0, 2.0]),
    "constant": numpy.full(4, 7.0),
    "tiny": sample("weibull", 300, shape=1.5, scale=1.0) * 1e-300,
    "huge": sample("weibull", 300, shape=1.5, scale=1.0) * 1e300,
    "near the limit in days": numpy.array([1e303, 2e303, 3e303]),
}


@pytest.mark.parametrize("column", sorted(COLUMNS))
@pytest.mark.parametrize("unit", ["s", "min", "h", "d"])
def test_every_candidate_validates_when_written_into_a_model(column: str, unit: str) -> None:
    """Property: whatever the column, every candidate is a distribution the model takes as
    it is, with no E123, E140, E141 or E16x for its fields."""
    from ithax.model.loading import load_document

    for candidate in fit_column(COLUMNS[column], unit):
        document = {
            "format_version": "0.1",
            "meta": {"name": "Fit"},
            "domain": "process",
            "parameters": {},
            "components": [
                {
                    "id": "arrivals",
                    "type": "source",
                    "params": {"interarrival": dict(candidate.distribution)},
                },
                {"id": "exit", "type": "sink", "params": {}},
            ],
            "connections": [{"from": "arrivals.out", "to": "exit.in"}],
            "experiments": [{"id": "base", "length": "8 h", "replications": 2, "seed": 1}],
            "run": {"target": "local", "fidelity": "standard"},
        }
        issues = load_document(document).issues
        bad = [
            issue
            for issue in issues
            if issue.code in ("E123", "E140", "E141", "E160", "E161", "E162")
        ]
        assert bad == [], (candidate, bad)


# --- The histogram of the fit response (spec 3 fit note; AKS-120) ---------------------


def test_the_histogram_uses_sturges_bins_from_the_smallest_to_the_largest_value() -> None:
    values = numpy.array([float(value) for value in range(1, 301)])
    found = fit.histogram(values)
    # ceil(log2(300)) + 1 = 10 bins of equal width from 1 to 300.
    assert len(found["counts"]) == 10
    assert len(found["edges"]) == 11
    assert found["edges"][0] == 1.0 and found["edges"][-1] == 300.0
    widths = numpy.diff(found["edges"])
    assert numpy.allclose(widths, widths[0])
    assert sum(found["counts"]) == 300
    assert all(isinstance(count, int) for count in found["counts"])
    assert all(isinstance(edge, float) for edge in found["edges"])


def test_a_bin_holds_its_lower_edge_and_the_last_also_its_upper_edge() -> None:
    found = fit.histogram(numpy.array([0.0, 1.0, 1.0, 2.0]))
    # ceil(log2(4)) + 1 = 3 bins: [0, 2/3), [2/3, 4/3), [4/3, 2].
    assert found["counts"] == [1, 2, 1]
    assert found["edges"][0] == 0.0 and found["edges"][-1] == 2.0


def test_the_histogram_has_at_most_fifty_bins() -> None:
    values = numpy.linspace(0.0, 1.0, 2**60 // 2**40)  # 1,048,576 values: 21 bins
    assert len(fit.histogram(values)["counts"]) == 21
    assert fit.histogram_bins(2**60) == 50
    assert fit.histogram_bins(1) == 1
    assert fit.histogram_bins(2) == 2


def test_a_constant_column_has_one_bin_at_its_value() -> None:
    assert fit.histogram(numpy.array([2.5, 2.5, 2.5])) == {"edges": [2.5, 2.5], "counts": [3]}


def test_a_single_value_has_one_bin() -> None:
    assert fit.histogram(numpy.array([-4.0])) == {"edges": [-4.0, -4.0], "counts": [1]}


@pytest.mark.parametrize(
    "values",
    [
        [-1.7976931348623157e308, 1.7976931348623157e308],
        [1e-300, 3e-300, 2e-300],
        [-5.0, -1.0, -3.0],
    ],
)
def test_every_edge_is_finite_and_ordered(values: list[float]) -> None:
    found = fit.histogram(numpy.array(values))
    edges = found["edges"]
    assert all(math.isfinite(edge) for edge in edges)
    assert edges == sorted(edges)
    assert edges[0] == min(values) and edges[-1] == max(values)
    assert sum(found["counts"]) == len(values)


def test_a_candidate_with_a_bound_below_zero_is_left_out() -> None:
    """#69: the gate refuses what the model refuses, so a fit is never offered that would
    set samples to 0 s. A triangular fitted to values from 1 to 3 has its bounds there."""
    values = sample("triangular", 2000, min=1.0, mode=2.0, max=3.0)
    triangular = by_name(fit_column(values, None))["triangular"].distribution
    assert float(triangular["min"]) >= 0
    assert not fit._admitted(
        Candidate({"dist": "triangular", "min": -1.0, "mode": 1.0, "max": 2.0}, 0.1), None
    )
    assert not fit._admitted(Candidate({"dist": "constant", "value": -1.0}, 0.0), None)
