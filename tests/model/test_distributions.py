"""Distribution sampling (spec 1 "Distributions"; AKS-96).

The M2 acceptance row "Every distribution passes the sampling test": 20,000 samples from
one stream; the sample mean lies within four standard errors of the theoretical mean,
standard error = theoretical standard deviation / √20000, with the theoretical mean and sd
spec 1 lists for each distribution. Also: every sampled time below 0 s is set to 0 s (the
AKS-96 reading of M1 owner item 9), parameters are resolved as validation resolves them,
and an ``empirical`` with ``data`` samples the column a run read into it, and cannot be
sampled before (E162; the sampling test against the copied column is in
``tests/runs/test_snapshots.py``, AKS-113).
"""

import copy
import json
import math
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy
import pytest

from ithax.model.catalogue import DISTRIBUTIONS
from ithax.model.distributions import (
    DataNotReadError,
    Sampler,
    sampler_for,
    sampler_from_numbers,
)
from ithax.model.issues import Issue
from ithax.model.loading import build_document
from ithax.model.model import DataRef, Distribution, Model, ParamRef, Scalar
from ithax.model.streams import generator_for
from ithax.model.units import Dimension, Quantity
from ithax.model.validation import distribution_mean

ROOT = Path(__file__).resolve().parents[2]
COFFEE_SHOP: dict[str, Any] = json.loads(
    (ROOT / "examples" / "coffee_shop.json").read_text(encoding="utf-8")
)
SAMPLES = 20_000
SEED = 12345


def seconds(value: float) -> Quantity:
    return Quantity(float(value), Dimension.TIME)


def dist(name: str, values: tuple[Scalar, ...] | None = None, **fields: Scalar) -> Distribution:
    return Distribution(name, MappingProxyType(dict(fields)), values=values)


def model_of(document: dict[str, Any]) -> Model:
    result = build_document(document, seed_source=lambda: 7)
    assert result.issues == (), [issue.as_dict() for issue in result.issues]
    assert result.model is not None
    return result.model


MODEL = model_of(copy.deepcopy(COFFEE_SHOP))


def draw(sampler: Sampler, component_id: str, count: int = SAMPLES) -> numpy.ndarray:
    """``count`` samples from one stream, the stream of ``component_id`` in replication 0."""
    rng = generator_for(SEED, 0, component_id)
    return numpy.array([sampler(rng) for _ in range(count)])


def _weibull_moments(shape: float, scale: float) -> tuple[float, float]:
    first = math.gamma(1 + 1 / shape)
    second = math.gamma(1 + 2 / shape)
    return scale * first, scale * math.sqrt(second - first**2)


def _triangular_sd(a: float, b: float, c: float) -> float:
    return math.sqrt((a * a + b * b + c * c - a * b - a * c - b * c) / 18)


_EMPIRICAL = (30.0, 60.0, 60.0, 120.0, 45.0)
_EMPIRICAL_MEAN = sum(_EMPIRICAL) / len(_EMPIRICAL)
_EMPIRICAL_SD = math.sqrt(sum((x - _EMPIRICAL_MEAN) ** 2 for x in _EMPIRICAL) / len(_EMPIRICAL))

# One case per `dist` of spec 1: the distribution (fields in SI seconds) and its theoretical
# mean and standard deviation as spec 1 "Distributions" lists them for the sampling test.
CASES: Mapping[str, tuple[Distribution, float, float]] = {
    "constant": (dist("constant", value=seconds(75)), 75.0, 0.0),
    "exponential": (dist("exponential", mean=seconds(90)), 90.0, 90.0),
    "uniform": (dist("uniform", min=seconds(30), max=seconds(90)), 60.0, 60 / math.sqrt(12)),
    "triangular": (
        dist("triangular", min=seconds(30), mode=seconds(60), max=seconds(150)),
        80.0,
        _triangular_sd(30, 60, 150),
    ),
    # mean ≥ 5 sd, so clipping at zero is negligible (spec 1).
    "normal": (dist("normal", mean=seconds(100), sd=seconds(20)), 100.0, 20.0),
    "lognormal": (dist("lognormal", mean=seconds(90), sd=seconds(30)), 90.0, 30.0),
    "weibull": (dist("weibull", shape=1.5, scale=seconds(60)), *_weibull_moments(1.5, 60.0)),
    "empirical": (
        dist("empirical", values=tuple(seconds(x) for x in _EMPIRICAL)),
        _EMPIRICAL_MEAN,
        _EMPIRICAL_SD,
    ),
}


def test_the_cases_cover_every_distribution_of_spec_1() -> None:
    assert set(CASES) == set(DISTRIBUTIONS)
    assert len(CASES) == 8


@pytest.mark.parametrize("name", list(CASES))
def test_every_distribution_passes_the_sampling_test(name: str) -> None:
    """Spec 1 acceptance, M2: within four standard errors of the theoretical mean."""
    distribution, mean, sd = CASES[name]
    samples = draw(sampler_for(MODEL, distribution), name)
    assert samples.shape == (SAMPLES,)
    standard_error = sd / math.sqrt(SAMPLES)
    assert abs(samples.mean() - mean) <= 4 * standard_error, (samples.mean(), mean, sd)
    if name == "constant":
        assert (samples == 75.0).all()  # sd 0: the samples equal the value exactly
    if name == "normal":
        assert (samples >= 0).all()
    if name == "empirical":
        assert set(samples.tolist()) == set(_EMPIRICAL)


@pytest.mark.parametrize("name", list(CASES))
def test_the_theoretical_mean_agrees_with_validation(name: str) -> None:
    """The means the test uses are those validation uses for W201 (spec 1)."""
    distribution, mean, _ = CASES[name]
    validated = distribution_mean(MODEL, distribution)
    assert validated is not None
    assert float(validated) == pytest.approx(mean, rel=1e-6)


@pytest.mark.parametrize("name", list(CASES))
def test_a_sample_is_a_python_float(name: str) -> None:
    distribution, _, _ = CASES[name]
    value = sampler_for(MODEL, distribution)(generator_for(SEED, 0, name))
    assert type(value) is float


def test_the_same_stream_gives_the_same_samples() -> None:
    sampler = sampler_for(MODEL, CASES["lognormal"][0])
    assert draw(sampler, "till", 50).tolist() == draw(sampler, "till", 50).tolist()


def test_exponential_mean_is_the_scale() -> None:
    """Spec 1: ``mean`` is 1/rate, sampled as the scale."""
    rng, reference = generator_for(SEED, 0, "x"), generator_for(SEED, 0, "x")
    sampler = sampler_for(MODEL, dist("exponential", mean=seconds(90)))
    assert [sampler(rng) for _ in range(5)] == reference.exponential(90.0, 5).tolist()


def test_lognormal_uses_the_mean_and_sd_of_the_variable() -> None:
    """Spec 1: σ² = ln(1 + sd²/mean²), μ = ln(mean) - σ²/2."""
    sigma2 = math.log(1 + 30.0**2 / 90.0**2)
    mu = math.log(90.0) - sigma2 / 2
    rng, reference = generator_for(SEED, 0, "x"), generator_for(SEED, 0, "x")
    sampler = sampler_for(MODEL, dist("lognormal", mean=seconds(90), sd=seconds(30)))
    expected = reference.lognormal(mu, math.sqrt(sigma2), 5).tolist()
    assert [sampler(rng) for _ in range(5)] == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize(
    ("mean", "sd", "sigma2"),
    [
        (1e-200, 1e-200, math.log(2)),  # sd² and mean² underflow to 0 if squared
        (1e200, 1e200, math.log(2)),  # sd² and mean² overflow to inf if squared
        (1e-200, 1e200, 800 * math.log(10)),  # sd/mean = 1e400 overflows a float
        (1e200, 1e-200, 0.0),  # σ² = ln(1 + 1e-800) is 0 to double precision
    ],
)
def test_lognormal_parameters_hold_at_extreme_magnitudes(
    mean: float, sd: float, sigma2: float
) -> None:
    """Any positive finite mean and sd pass E160, so the conversion must not break down
    (review of PR #15)."""
    rng, reference = generator_for(SEED, 0, "x"), generator_for(SEED, 0, "x")
    sampler = sampler_for(MODEL, dist("lognormal", mean=seconds(mean), sd=seconds(sd)))
    mu = math.log(mean) - sigma2 / 2
    expected = reference.lognormal(mu, math.sqrt(sigma2), 3).tolist()
    assert [sampler(rng) for _ in range(3)] == pytest.approx(expected, rel=1e-9)


def test_weibull_shape_is_a_plain_number_and_scale_a_time() -> None:
    rng, reference = generator_for(SEED, 0, "x"), generator_for(SEED, 0, "x")
    sampler = sampler_for(MODEL, dist("weibull", shape=2, scale=seconds(60)))
    expected = (60.0 * reference.weibull(2.0, 5)).tolist()
    assert [sampler(rng) for _ in range(5)] == pytest.approx(expected, rel=1e-12)


def test_a_uniform_or_triangular_with_min_equal_to_max_gives_that_value() -> None:
    """Spec 1 allows a ``min`` equal to the ``max``; numpy's triangular refuses it."""
    rng = generator_for(SEED, 0, "x")
    uniform = sampler_for(MODEL, dist("uniform", min=seconds(40), max=seconds(40)))
    triangular = sampler_for(
        MODEL, dist("triangular", min=seconds(40), mode=seconds(40), max=seconds(40))
    )
    assert {uniform(rng) for _ in range(100)} == {40.0}
    assert {triangular(rng) for _ in range(100)} == {40.0}


def test_a_triangular_with_the_mode_at_an_end_samples() -> None:
    samples = draw(
        sampler_for(MODEL, dist("triangular", min=seconds(0), mode=seconds(0), max=seconds(60))),
        "x",
        2000,
    )
    assert samples.min() >= 0 and samples.max() <= 60


def test_an_empirical_with_one_value_gives_that_value() -> None:
    sampler = sampler_for(MODEL, dist("empirical", values=(seconds(12),)))
    assert set(draw(sampler, "x", 100).tolist()) == {12.0}


def test_empirical_values_have_equal_probability() -> None:
    sampler = sampler_for(MODEL, dist("empirical", values=(seconds(1), seconds(2), seconds(3))))
    samples = draw(sampler, "x")
    for value in (1.0, 2.0, 3.0):
        share = (samples == value).mean()
        # binomial sd of a share of 1/3 over 20,000 draws is about 0.0033
        assert abs(share - 1 / 3) < 4 * math.sqrt((1 / 3) * (2 / 3) / SAMPLES)


def test_plain_numbers_are_taken_as_they_are() -> None:
    """A distribution of a dimensionless setting holds plain numbers (spec 1 "Quantities")."""
    rng = generator_for(SEED, 0, "x")
    assert sampler_for(MODEL, dist("constant", value=3))(rng) == 3.0
    assert sampler_for(MODEL, dist("empirical", values=(2.5,)))(rng) == 2.5


# --- Negative times are set to 0 s (AKS-96 reading of M1 owner item 9) ------------------------


def test_a_constant_below_zero_gives_zero() -> None:
    sampler = sampler_for(MODEL, dist("constant", value=seconds(-60)))
    samples = draw(sampler, "x", 100)
    assert set(samples.tolist()) == {0.0}
    assert all(math.copysign(1.0, value) == 1.0 for value in samples)  # +0.0, not -0.0


def test_a_uniform_reaching_below_zero_is_clipped() -> None:
    """``uniform`` from -1 min to 1 min: about half the samples are 0 s, none below."""
    sampler = sampler_for(MODEL, dist("uniform", min=seconds(-60), max=seconds(60)))
    samples = draw(sampler, "x")
    assert samples.min() == 0.0
    assert samples.max() > 0.0
    share = (samples == 0.0).mean()
    assert abs(share - 0.5) < 4 * math.sqrt(0.25 / SAMPLES)
    # mean of max(U, 0) for U uniform on [-60, 60] is 15 s; sd is √(1500 - 225) s
    assert abs(samples.mean() - 15.0) <= 4 * math.sqrt(1275.0) / math.sqrt(SAMPLES)


def test_an_empirical_holding_negative_values_is_clipped() -> None:
    sampler = sampler_for(MODEL, dist("empirical", values=(seconds(-30), seconds(-1), seconds(60))))
    samples = draw(sampler, "x")
    assert set(samples.tolist()) == {0.0, 60.0}
    assert abs((samples == 0.0).mean() - 2 / 3) < 4 * math.sqrt((2 / 9) / SAMPLES)


def test_a_triangular_reaching_below_zero_is_clipped() -> None:
    sampler = sampler_for(
        MODEL, dist("triangular", min=seconds(-60), mode=seconds(0), max=seconds(60))
    )
    samples = draw(sampler, "x", 2000)
    assert samples.min() == 0.0 and samples.max() > 0.0


def test_a_normal_with_mean_zero_is_clipped() -> None:
    sampler = sampler_for(MODEL, dist("normal", mean=seconds(0), sd=seconds(10)))
    samples = draw(sampler, "x")
    assert samples.min() == 0.0
    assert abs((samples == 0.0).mean() - 0.5) < 4 * math.sqrt(0.25 / SAMPLES)


# --- Parameters ----------------------------------------------------------------------------------


def _with_service_parameter() -> Model:
    document = copy.deepcopy(COFFEE_SHOP)
    document["parameters"]["service_mean"] = {
        "value": "90 s",
        "type": "quantity",
        "min": "30 s",
        "max": "5 min",
    }
    document["components"][1]["params"]["service"] = {
        "dist": "constant",
        "value": {"$param": "service_mean"},
    }
    return model_of(document)


def test_a_parameter_is_resolved_at_its_value() -> None:
    model = _with_service_parameter()
    till = model.component("till")
    assert till is not None
    service = till.settings["service"]
    assert isinstance(service, Distribution)
    assert service.fields["value"] == ParamRef("service_mean")
    assert sampler_for(model, service)(generator_for(SEED, 0, "till")) == 90.0


def test_a_scenario_value_replaces_the_parameter_value() -> None:
    """As ``distribution_mean`` takes ``values``: a scenario's ``set`` for its parameters."""
    model = _with_service_parameter()
    till = model.component("till")
    assert till is not None
    service = till.settings["service"]
    assert isinstance(service, Distribution)
    sampler = sampler_for(model, service, {"service_mean": seconds(120)})
    assert sampler(generator_for(SEED, 0, "till")) == 120.0


def test_a_parameter_in_empirical_values_is_resolved() -> None:
    sampler = sampler_for(MODEL, dist("empirical", values=(ParamRef("tills"),)))
    assert sampler(generator_for(SEED, 0, "x")) == 1.0
    sampler = sampler_for(MODEL, dist("empirical", values=(ParamRef("tills"),)), {"tills": 4})
    assert sampler(generator_for(SEED, 0, "x")) == 4.0


# --- `empirical` with `data` (M6, AKS-113) ---------------------------------------------------


def test_empirical_with_data_not_read_cannot_be_sampled() -> None:
    distribution = Distribution(
        "empirical", MappingProxyType({}), data=DataRef("times.csv", "minutes")
    )
    with pytest.raises(DataNotReadError) as raised:
        sampler_for(MODEL, distribution)
    problem = raised.value
    assert problem.code == "E162"
    assert "'times.csv'" in problem.message and "'minutes'" in problem.message
    assert "M6" not in problem.message
    assert problem.hint
    issue = Issue.from_problem(
        problem,
        where="the 'service' setting of 'till'",
        path="/components/1/params/service/data",
        component="till",
    )
    assert issue.code == "E162"
    assert issue.severity == "error"
    assert issue.message.startswith("In the 'service' setting of 'till', ")
    assert "Traceback" not in issue.message and "Error" not in issue.message


def test_empirical_with_data_samples_the_values_a_run_read() -> None:
    """A run target puts the column's values, in seconds, beside the reference."""
    distribution = Distribution(
        "empirical",
        MappingProxyType({}),
        values=(60.0, 120.0, -5.0),
        data=DataRef("times.csv", "minutes"),
    )
    sampler = sampler_for(MODEL, distribution)
    rng = generator_for(SEED, 0, "x")
    drawn = {sampler(rng) for _ in range(200)}
    assert drawn == {60.0, 120.0, 0.0}  # a value below 0 s is 0 s


def test_an_unknown_distribution_is_refused() -> None:
    """Loading never builds one (E160); a sampler for one is a programming error."""
    with pytest.raises(ValueError, match="'gamma'"):
        sampler_for(MODEL, dist("gamma", shape=2))


@pytest.mark.parametrize(
    ("distribution", "fields", "values"),
    [
        (dist("constant", value=seconds(90)), {"value": 90.0}, None),
        (dist("exponential", mean=seconds(90)), {"mean": 90.0}, None),
        (dist("uniform", min=seconds(10), max=seconds(20)), {"min": 10.0, "max": 20.0}, None),
        (
            dist("triangular", min=seconds(1), mode=seconds(2), max=seconds(4)),
            {"min": 1.0, "mode": 2.0, "max": 4.0},
            None,
        ),
        (dist("normal", mean=seconds(60), sd=seconds(5)), {"mean": 60.0, "sd": 5.0}, None),
        (dist("lognormal", mean=seconds(60), sd=seconds(5)), {"mean": 60.0, "sd": 5.0}, None),
        (dist("weibull", shape=2, scale=seconds(60)), {"shape": 2.0, "scale": 60.0}, None),
        (dist("empirical", values=(seconds(1), seconds(-2), seconds(3))), {}, [1.0, -2.0, 3.0]),
    ],
)
def test_a_sampler_from_resolved_numbers_draws_as_sampler_for(
    distribution: Distribution, fields: dict[str, float], values: list[float] | None
) -> None:
    """AKS-98: the engine input holds SI floats; its samplers draw as the model's do."""
    from_model, from_numbers = (
        sampler_for(MODEL, distribution),
        sampler_from_numbers(distribution.dist, fields, values),
    )
    first, second = generator_for(SEED, 0, "till"), generator_for(SEED, 0, "till")
    assert [from_model(first) for _ in range(50)] == [from_numbers(second) for _ in range(50)]


def test_a_sampler_from_numbers_refuses_an_unknown_distribution_or_no_values() -> None:
    with pytest.raises(ValueError, match="'gamma'"):
        sampler_from_numbers("gamma", {"shape": 2.0})
    with pytest.raises(ValueError, match="at least one value"):
        sampler_from_numbers("empirical", {}, [])
    with pytest.raises(ValueError, match="at least one value"):
        sampler_from_numbers("empirical", {})
