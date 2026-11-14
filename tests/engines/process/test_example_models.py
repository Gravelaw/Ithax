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
- The theory gate (#75, M13): the three-machine line and the warehouse, each at its own
  experiment with 300 replications in place of 30, against the closed-form values in its
  ``meta.description``, at the spec 2 benchmark pass rule (3 standard errors). Marked
  ``benchmark``: the two runs take about 40 s with 4 workers.

Each example runs through the experiment manager (``ithax.runs.manager.run_experiment``,
AKS-102), and the across-replication mean and 95% half-width are the manager's
(``ithax.runs.statistics.estimate``): t(0.975, n - 1) x sample sd / sqrt(n), with t from
``scipy.stats.t.ppf`` (spec 2 "Statistic definitions"). ``MEASURED`` pins the values written
in spec 2's table, so the spec and the adapter cannot drift apart silently. The warm-up
check is silent on all three (spec 2; the coffee shop is the AKS-102 acceptance case).
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

from ithax.engines.process.adapter import ProcessAdapter
from ithax.model.catalogue import PROCESS_TYPES
from ithax.model.loading import load_document
from ithax.runs.manager import run_experiment
from ithax.runs.statistics import estimate as across

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
    """The manager's mean of the replication values and its half-width (spec 2
    "Statistic definitions", across replications); every value here is finite."""
    found = across(values, confidence)
    assert found.mean is not None and found.half_width is not None and found.n == len(values)
    return found.mean, found.half_width


def standard_error(values: Sequence[float]) -> float:
    return statistics.stdev(values) / math.sqrt(len(values))


def run_example(name: str, workdir: Path) -> tuple[dict[str, list[float]], dict[str, Any]]:
    """Runs the example's own first experiment, unchanged, through the experiment manager,
    and returns each metric's replication values in replication order and the summary."""
    document = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    result = load_document(document)
    assert result.issues == ()
    model = result.model
    assert model is not None
    outcome = run_experiment(
        ProcessAdapter(), model, model.experiments[0].id, workdir, workers=WORKERS
    )
    assert outcome.state == "done"
    assert outcome.results is not None and outcome.summary is not None
    values: dict[str, list[float]] = {}
    for row in outcome.results.tables["replications"].to_pylist():
        values.setdefault(row["metric"], []).append(row["value"])
    return values, outcome.summary


@pytest.fixture(scope="module")
def runs(
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, tuple[dict[str, list[float]], dict[str, Any]]]:
    """The three examples, each run once for the whole module."""
    return {name: run_example(name, tmp_path_factory.mktemp(name)) for name in NAMES}


@pytest.fixture(scope="module")
def measured(
    runs: Mapping[str, tuple[dict[str, list[float]], dict[str, Any]]],
) -> dict[str, dict[str, list[float]]]:
    """Each example's replication values by metric."""
    return {name: values for name, (values, _) in runs.items()}


@pytest.mark.parametrize("name", NAMES)
def test_the_warmup_check_is_silent_on_each_example(
    name: str, runs: Mapping[str, tuple[dict[str, list[float]], dict[str, Any]]]
) -> None:
    """No W210 (spec 2 warm-up check; the research note found all three silent at seed
    12345); for the coffee shop this is an AKS-102 acceptance check."""
    assert runs[name][1]["warnings"] == []


@pytest.mark.parametrize("name", NAMES)
def test_the_summary_holds_the_manager_statistics(
    name: str, runs: Mapping[str, tuple[dict[str, list[float]], dict[str, Any]]]
) -> None:
    values, summary = runs[name]
    assert summary["fidelity_label"].startswith("Standard: 30 replications of ")
    metrics = summary["scenarios"]["default"]["metrics"]
    assert list(metrics) == list(values)
    for metric, sample in values.items():
        mean, half_width = mean_and_half_width(sample)
        assert metrics[metric]["mean"] == mean and metrics[metric]["half_width"] == half_width
        assert metrics[metric]["n"] == 30


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
# The other two files are gated on their theory at 300 replications, below (#75): at 30, of
# their 14 such checks at least one falls beyond 3 standard errors in 7% of runs of a
# correct engine (the line's paint wait does at seed 12345, -3.32; at 300 it is -1.19).
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


# ---------------------------------------------------------------------------------------
# The theory gate (#75): the line and the warehouse at 300 replications

THEORY_REPLICATIONS = 300

# Each file's meta.description, in SI units. Every station sees Poisson arrivals (Burke's
# theorem; a constant transfer or inspection shifts a Poisson stream and keeps it Poisson,
# and the warehouse's two Bernoulli-split streams are independent before they merge at
# pack), so each server is M/M/c: utilization lambda E(S) / c, and mean wait
# rho / (1 - rho) x E(S) for one server; Erlang C 4/9 x E(S) / (c - a) = 8/9 min for pick.
THEORY: dict[str, dict[str, Fraction]] = {
    "three_machine_line.json": {
        "cut.utilization": Fraction(3, 5),
        "weld.utilization": Fraction(9, 10),
        "paint.utilization": Fraction(1, 2),
        "cut.wait.mean": Fraction(108),  # 1.8 min
        "weld.wait.mean": Fraction(972),  # 16.2 min
        "paint.wait.mean": Fraction(60),  # 1.0 min
        "exit.cycle_time.mean": Fraction(1500),  # 3.0 + 18.0 + 2 + 2.0 min
        "exit.throughput": Fraction(1, 120),  # 30 per hour
    },
    "warehouse.json": {
        "pick.utilization": Fraction(2, 3),
        "pack.utilization": Fraction(4, 5),
        "pick.wait.mean": Fraction(160, 3),  # 8/9 min
        "pack.wait.mean": Fraction(192),  # 3.2 min
        "dispatch.cycle_time.mean": Fraction(120) + Fraction(160, 3) + 60 + 240,  # 7.889 min
        "dispatch.throughput": Fraction(1, 60),  # 60 per hour
    },
}


def run_long(name: str, workdir: Path) -> dict[str, list[float]]:
    """The example's own first experiment with 300 replications; each metric's values."""
    document = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    document["experiments"][0]["replications"] = THEORY_REPLICATIONS
    model = load_document(document).model
    assert model is not None
    outcome = run_experiment(
        ProcessAdapter(), model, model.experiments[0].id, workdir, workers=WORKERS
    )
    assert outcome.state == "done" and outcome.results is not None
    values: dict[str, list[float]] = {}
    for row in outcome.results.tables["replications"].to_pylist():
        values.setdefault(row["metric"], []).append(row["value"])
    return values


@pytest.fixture(scope="module")
def long_runs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict[str, list[float]]]:
    """The line and the warehouse at 300 replications, each run once for the module."""
    return {name: run_long(name, tmp_path_factory.mktemp(name)) for name in THEORY}


def test_the_theory_is_the_one_each_file_states() -> None:
    """The gate's values are the ones in each file's ``meta.description``, at the decimals
    written there (minutes, utilizations and per-hour throughput)."""
    for name, theory in THEORY.items():
        text = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))["meta"]["description"]
        for metric, value in theory.items():
            if metric.endswith(".utilization"):
                written = f"{float(value):.3f}".rstrip("0").rstrip(".")
            elif metric.endswith(".throughput"):
                written = f"{float(value) * 3600:g} per hour"
            else:
                written = f"{float(value) / MINUTE:.3f}".rstrip("0") + " min"
                written = written.replace(". min", ".0 min")
            assert written in text, (name, metric, written)


@pytest.mark.benchmark
@pytest.mark.parametrize(
    ("name", "metric"), [(name, metric) for name, theory in THEORY.items() for metric in theory]
)
def test_each_example_agrees_with_its_theory_at_300_replications(
    name: str, metric: str, long_runs: Mapping[str, Mapping[str, Sequence[float]]]
) -> None:
    """Spec 2 benchmark pass rule: |mean - theory| <= 3 standard errors (#75; at seed 12345
    every one of the 14 lies within 2, the largest the line's cut wait at +1.70)."""
    sample = long_runs[name][metric]
    assert len(sample) == THEORY_REPLICATIONS
    mean = statistics.fmean(sample)
    deviation = (mean - float(THEORY[name][metric])) / standard_error(sample)
    assert abs(deviation) <= SE_LIMIT, (metric, mean, deviation)
