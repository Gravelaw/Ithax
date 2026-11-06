"""The three example models run end to end through the process adapter (spec 2 acceptance
row "The three example models run end to end", M2; AKS-99 and AKS-101).

Two parts:

- A smoke test (AKS-99): each example's own experiment, shortened to 5 h with 30 min of
  warm-up and 2 replications, through ``translate``, ``run`` and ``collect``, checking the
  shape of both tables.
- The M2 gate (AKS-101): each example's own experiment, unchanged (seed 12345, 30
  replications), measured against the spec 2 targets of "Reference values from the
  prototype": the three-machine line's weld utilization from 0.85 to 0.92 with the other
  stations below 0.70; the warehouse's throughput within 1% of 60 per hour with pack
  utilization from 0.75 to 0.85; and the coffee shop against M/M/1 theory. Each run takes
  about 1.5 to 3 s with 4 workers, so the gate stays in ``bash scripts/check.sh``.

The across-replication mean and 95% half-width follow spec 2 "Statistic definitions":
t(0.975, n - 1) x sample sd / sqrt(n), with t from ``scipy.stats.t.ppf``. The experiment
manager that will compute them for every run arrives at M3, so they are computed here.
``MEASURED`` pins the values written in spec 2's table, so the spec and the adapter cannot
drift apart silently.
"""

import json
import math
import os
import statistics
import threading
from collections.abc import Mapping, Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from scipy.stats import t

from lcsim.engines.process.adapter import ProcessAdapter
from lcsim.model.catalogue import PROCESS_TYPES
from lcsim.model.loading import load_document

EXAMPLES = Path(__file__).resolve().parents[3] / "examples"
NAMES = ["coffee_shop.json", "three_machine_line.json", "warehouse.json"]
# Results do not depend on the number of workers (tests/engines/process/test_runner.py).
WORKERS = min(4, os.cpu_count() or 1)
CONFIDENCE = 0.95
SE_LIMIT = 3.0  # the spec 2 benchmark pass rule, used for the coffee shop's theory check

MINUTE = 60.0
PER_HOUR = 1 / 3600


def shortened(name: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    document["experiments"][0].update({"length": "5 h", "warmup": "30 min", "replications": 2})
    return document


@pytest.mark.parametrize("name", NAMES)
def test_each_example_runs_end_to_end(name: str, tmp_path: Path) -> None:
    document = shortened(name)
    model = load_document(document).model
    assert model is not None
    adapter = ProcessAdapter()
    adapter.translate(model, document["experiments"][0]["id"], tmp_path)
    adapter.run(tmp_path, lambda progress: None, threading.Event(), 1)
    results = adapter.collect(tmp_path)
    assert list(results.tables) == ["replications", "timeseries"]

    replications = results.tables["replications"].to_pylist()
    expected = [
        f"{component.id}.{measure}"
        for component in model.components
        for measure in PROCESS_TYPES[component.type].metrics
    ] + ["model.wip.mean"]
    assert [row["metric"] for row in replications] == expected * 2
    assert all(math.isfinite(row["value"]) for row in replications)
    sinks = [row for row in replications if row["metric"].endswith(".count")]
    assert all(row["value"] > 0 for row in sinks)

    servers = [component.id for component in model.components if component.type == "server"]
    series = results.tables["timeseries"].to_pylist()
    metrics = [
        f"{server}.{measure}" for server in servers for measure in ("queue_length", "utilization")
    ]
    expected_series = [metric for metric in [*metrics, "model.wip"] for _ in range(200)]
    assert [row["metric"] for row in series] == expected_series * 2


# ---------------------------------------------------------------------------------------
# The M2 gate: each example's own experiment, measured against the spec 2 targets


def mean_and_half_width(
    values: Sequence[float], confidence: float = CONFIDENCE
) -> tuple[float, float]:
    """The mean of the replication values and its half-width, t(1 - (1 - confidence)/2,
    n - 1) x sample sd / sqrt(n) (spec 2 "Statistic definitions", across replications)."""
    n = len(values)
    if n < 2:
        raise ValueError(f"{n} replication values; a half-width needs 2")
    quantile = float(t.ppf(1 - (1 - confidence) / 2, n - 1))
    return statistics.fmean(values), quantile * statistics.stdev(values) / math.sqrt(n)


def standard_error(values: Sequence[float]) -> float:
    return statistics.stdev(values) / math.sqrt(len(values))


def run_example(name: str, workdir: Path) -> dict[str, list[float]]:
    """Runs the example's own first experiment, unchanged, and returns each metric's
    replication values in replication order."""
    document = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    result = load_document(document)
    assert result.issues == ()
    model = result.model
    assert model is not None
    adapter = ProcessAdapter()
    adapter.translate(model, model.experiments[0].id, workdir)
    adapter.run(workdir, lambda progress: None, threading.Event(), WORKERS)
    values: dict[str, list[float]] = {}
    for row in adapter.collect(workdir).tables["replications"].to_pylist():
        values.setdefault(row["metric"], []).append(row["value"])
    return values


@pytest.fixture(scope="module")
def measured(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict[str, list[float]]]:
    """The three examples, each run once for the whole module."""
    return {name: run_example(name, tmp_path_factory.mktemp(name)) for name in NAMES}


def estimate(values: Mapping[str, Sequence[float]], metric: str) -> float:
    return mean_and_half_width(values[metric])[0]


@pytest.mark.parametrize("name", NAMES)
def test_each_example_runs_its_own_experiment_of_30_replications(
    name: str, measured: Mapping[str, Mapping[str, Sequence[float]]]
) -> None:
    document = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    experiment = document["experiments"][0]
    assert (experiment["seed"], experiment["replications"]) == (12345, 30)
    values = measured[name]
    assert all(len(sample) == 30 for sample in values.values())
    assert all(math.isfinite(value) for sample in values.values() for value in sample)


def test_three_machine_line_meets_its_spec_2_targets(
    measured: Mapping[str, Mapping[str, Sequence[float]]],
) -> None:
    """Weld utilization from 0.85 to 0.92; cut and paint below 0.70."""
    values = measured["three_machine_line.json"]
    assert 0.85 <= estimate(values, "weld.utilization") <= 0.92
    assert estimate(values, "cut.utilization") < 0.70
    assert estimate(values, "paint.utilization") < 0.70


def test_warehouse_meets_its_spec_2_targets(
    measured: Mapping[str, Mapping[str, Sequence[float]]],
) -> None:
    """Throughput within 1% of 60 per hour; pack utilization from 0.75 to 0.85."""
    values = measured["warehouse.json"]
    target = 60 * PER_HOUR
    assert abs(estimate(values, "dispatch.throughput") - target) <= 0.01 * target
    assert 0.75 <= estimate(values, "pack.utilization") <= 0.85


# The coffee shop against M/M/1 theory (arrivals mean 2 min, service mean 1.5 min), in SI
# units, with the spec 2 benchmark pass rule: |estimate - theory| <= 3 standard errors.
# The other two files are compared with their theory in spec 2's table and in
# docs/DECISIONS.md (AKS-101), but not gated on it: their targets are the gate, and of
# their 14 such checks at 30 replications at least one falls beyond 3 standard errors in 7%
# of runs of a correct engine (the line's paint wait does at seed 12345; seeds 1, 2 and 7
# do not).
COFFEE_SHOP_THEORY: dict[str, Fraction] = {
    "till.wait.mean": Fraction(270),
    "till.utilization": Fraction(3, 4),
    "till.queue_length.mean": Fraction(9, 4),
    "exit.cycle_time.mean": Fraction(360),
    "exit.throughput": Fraction(1, 120),
    "model.wip.mean": Fraction(3),
}


@pytest.mark.parametrize("metric", list(COFFEE_SHOP_THEORY))
def test_coffee_shop_agrees_with_m_m_1_theory(
    metric: str, measured: Mapping[str, Mapping[str, Sequence[float]]]
) -> None:
    sample = measured["coffee_shop.json"][metric]
    deviation = abs(statistics.fmean(sample) - float(COFFEE_SHOP_THEORY[metric]))
    assert deviation <= SE_LIMIT * standard_error(sample), (metric, statistics.fmean(sample))


# The values written in spec 2 "Reference values from the prototype" (AKS-101): metric,
# display scale (the SI value is divided by it), decimals, mean and half-width as written.
MEASURED: dict[str, list[tuple[str, float, int, float, float]]] = {
    "three_machine_line.json": [
        ("weld.utilization", 1.0, 3, 0.901, 0.011),
        ("cut.utilization", 1.0, 3, 0.600, 0.007),
        ("paint.utilization", 1.0, 3, 0.495, 0.006),
        ("weld.wait.mean", MINUTE, 2, 15.69, 2.09),
        ("paint.wait.mean", MINUTE, 3, 0.951, 0.030),
        ("exit.cycle_time.mean", MINUTE, 2, 24.48, 2.11),
        ("exit.throughput", PER_HOUR, 2, 30.01, 0.25),
    ],
    "warehouse.json": [
        ("dispatch.throughput", PER_HOUR, 2, 59.99, 0.20),
        ("pack.utilization", 1.0, 3, 0.799, 0.004),
        ("pick.utilization", 1.0, 3, 0.666, 0.003),
        ("pack.wait.mean", MINUTE, 2, 3.17, 0.15),
        ("pick.wait.mean", MINUTE, 3, 0.875, 0.026),
        ("dispatch.cycle_time.mean", MINUTE, 2, 7.84, 0.16),
    ],
}


@pytest.mark.parametrize(
    ("name", "row"), [(name, row) for name, rows in MEASURED.items() for row in rows]
)
def test_the_values_in_spec_2_are_the_measured_ones(
    name: str,
    row: tuple[str, float, int, float, float],
    measured: Mapping[str, Mapping[str, Sequence[float]]],
) -> None:
    metric, scale, decimals, mean, half_width = row
    found_mean, found_half_width = mean_and_half_width(measured[name][metric])
    assert round(found_mean / scale, decimals) == mean
    assert round(found_half_width / scale, decimals) == half_width


def test_the_weld_wait_half_width_is_13_percent_of_its_mean(
    measured: Mapping[str, Mapping[str, Sequence[float]]],
) -> None:
    """Spec 2 records it for spec 4's ``not_enough_runs`` (10% threshold), checked at M8."""
    mean, half_width = mean_and_half_width(measured["three_machine_line.json"]["weld.wait.mean"])
    assert round(100 * half_width / mean, 1) == 13.3


def test_mean_and_half_width_uses_the_t_quantile() -> None:
    # 1, 2, 3: mean 2, sample sd 1, n 3; t(0.975, 2) = 4.302652729749464.
    mean, half_width = mean_and_half_width([1.0, 2.0, 3.0])
    assert mean == 2.0
    assert half_width == pytest.approx(4.302652729749464 / math.sqrt(3), rel=1e-12)
    # 30 replications: t(0.975, 29) = 2.045229642132703.
    sample = [float(value) for value in range(30)]
    expected = 2.045229642132703 * statistics.stdev(sample) / math.sqrt(30)
    assert mean_and_half_width(sample)[1] == pytest.approx(expected, rel=1e-12)
    # 99%: t(0.995, 2) = 9.924843200918276.
    assert mean_and_half_width([1.0, 2.0, 3.0], 0.99)[1] == pytest.approx(
        9.924843200918276 / math.sqrt(3), rel=1e-12
    )


def test_mean_and_half_width_needs_two_values() -> None:
    with pytest.raises(ValueError, match="a half-width needs 2"):
        mean_and_half_width([1.0])
