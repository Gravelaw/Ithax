"""The benchmark harness (spec 2 "Benchmarks" and "Benchmark definitions"; AKS-100).

Each folder ``benchmarks/<case>/`` holds ``model.json`` (a fixed ``seed``) and
``expected.json``, a list of ``{metric, value, method, source, milestone}``. The test marked
``benchmark`` runs every case whose milestone is not later than the current one
(``conftest.CURRENT_MILESTONE``) through its engine adapter in ``tmp_path`` and checks each
known answer:

- ``three_se``: |estimate - known| <= 3 x SE, the estimate being the mean of the
  replication values and SE their sample standard deviation (n - 1) over sqrt(n);
- ``exact`` and ``sig_figs_4``: estimate and known answer equal to four significant figures.

An optimization case (AKS-108) has no experiment: it runs once through the HiGHS adapter,
must end ``optimal``, and each row's ``metric`` names the ``objective`` or a variable as
``variables.<id>`` of the solution, one value, judged by ``sig_figs_4``.

A search case (AKS-109: the machine count) runs its experiment's search through the
experiment manager (``run_experiment``). A row ``search.best.<variable>`` is the best
candidate's value, one value judged by ``sig_figs_4``; a row
``search.candidates[<variable>=<value>].<metric>`` is the replication values of that
candidate's confirmation (read with the adapter's ``collect`` from its ``confirm-<n>``
folder), judged like any simulated metric, so it exists only for a confirmed candidate.

At M2 the experiment manager does not exist yet, so the estimate and its standard error are
computed here from the adapter's ``replications`` table (the issue's Agent notes).

The test marked ``benchmark_coverage`` (run by hand, ``pytest -m benchmark_coverage -s``)
runs each case for 20 consecutive seeds from its fixed seed and asserts at least 19 pass:
the evidence spec 2's seed-change rule asks for.
"""

import copy
import json
import math
import os
import re
import statistics
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from lcsim.engines.registry import select_adapter
from lcsim.model.catalogue import MODEL_METRICS, PROCESS_TYPES
from lcsim.model.loading import load_document
from lcsim.model.model import Model
from lcsim.runs.manager import run_experiment
from lcsim.runs.search import combination_count, combinations

ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = ROOT / "benchmarks"
CASES = sorted(path.parent.name for path in BENCHMARKS.glob("*/model.json"))

METHODS = frozenset({"three_se", "exact", "sig_figs_4"})
ROW_KEYS = frozenset({"metric", "value", "method", "source", "milestone"})
SE_LIMIT = 3.0
COVERAGE_SEEDS = 20
COVERAGE_PASSES = 19
# Results do not depend on the number of workers (spec 1 "Random streams"; tested in
# tests/engines/process/test_runner.py), so any count gives the same table.
WORKERS = min(4, os.cpu_count() or 1)

# Spec 2 "Benchmark definitions": the five M2 cases and the blocks the prototype exercised.
M2_CASES = {"mm1", "mm2", "tandem", "delay", "branch"}
# The four M5 linear and integer programs (AKS-108).
M5_OPTIMIZATION_CASES = {"product_mix", "knapsack", "assignment", "diet"}
# The M5 simulation-based search (AKS-109).
M5_SEARCH_CASES = {"machine_count"}
M2_BLOCKS = {"source", "server", "delay", "branch", "sink"}
# Spec 2 acceptance row "Every block has a unit test and appears in a benchmark": M2 for
# the five prototype blocks, M4 for the rest.
BLOCK_MILESTONES = {block: "M2" for block in M2_BLOCKS} | {
    block: "M4"
    for block in ("queue", "batch", "unbatch", "store", "resource_pool", "schedule", "failure")
}

# Spec 2 "Benchmark definitions": "Stochastic cases use 100 replications of 200 hours with
# 10 hours of warm-up unless stated"; the cases that state their own, as (replications,
# length in hours, warm-up in hours).
STANDARD_SETTINGS = (100, 200, 10)
STATED_SETTINGS = {
    "store_deterministic": (2, 1000, 100),
    "schedule_deterministic": (2, 204, 12),
    # Spec 2 "Benchmark definitions": "The coffee shop", whose experiment is 30 replications
    # of 200 h with 10 h of warm-up.
    "machine_count": (30, 200, 10),
}

MILESTONE = re.compile(r"^M(\d+)$")


@dataclass(frozen=True)
class Expected:
    """One row of ``expected.json``."""

    metric: str
    value: float
    method: str
    source: str
    milestone: str


@dataclass(frozen=True)
class Check:
    """The outcome of one known answer: the estimate, its standard error and the verdict.

    ``problem`` says why no estimate could be judged (a missing metric, a NaN value, too
    few replications); it is empty when the estimate was judged.
    """

    metric: str
    method: str
    known: float
    estimate: float
    se: float
    passed: bool
    problem: str = ""

    def message(self, case: str) -> str:
        """A failure line naming the case, the metric, the estimate, the SE and the
        deviation in standard errors."""
        if self.problem:
            return f"{case}: {self.metric}: {self.problem}"
        deviation = abs(self.estimate - self.known)
        if self.method == "three_se":
            in_se = deviation / self.se if self.se > 0 else math.inf
            return (
                f"{case}: {self.metric}: estimate {self.estimate!r}, known {self.known!r}, "
                f"SE {self.se!r}, deviation {in_se:.2f} SE (limit {SE_LIMIT:g})"
            )
        return (
            f"{case}: {self.metric}: estimate {self.estimate!r}, known {self.known!r}, "
            f"SE {self.se!r}, not equal to four significant figures "
            f"({four_figures(self.estimate)!r} against {four_figures(self.known)!r})"
        )


def milestone_number(milestone: str) -> int:
    """The number of a milestone name such as ``M2`` or ``M10``."""
    match = MILESTONE.match(milestone)
    if match is None:
        raise ValueError(f"not a milestone name: {milestone!r}")
    return int(match.group(1))


def is_due(milestone: str, current: str) -> bool:
    """Whether a case of ``milestone`` runs at ``current``: not when it is later."""
    return milestone_number(milestone) <= milestone_number(current)


def read_case(case: str) -> tuple[dict[str, Any], list[Expected]]:
    """The model document and the expected rows of ``benchmarks/<case>/``."""
    folder = BENCHMARKS / case
    document: dict[str, Any] = json.loads((folder / "model.json").read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = json.loads((folder / "expected.json").read_text("utf-8"))
    return document, [Expected(**row) for row in rows]


def case_milestone(expected: Sequence[Expected]) -> str:
    """The latest milestone of a case's rows: the case runs once all of them are due."""
    return max((row.milestone for row in expected), key=milestone_number)


def load(document: object) -> Model:
    """The loaded model; a benchmark file must load with zero issues."""
    result = load_document(document)
    assert result.issues == (), [issue.code for issue in result.issues]
    assert result.model is not None
    return result.model


def is_optimization(document: Mapping[str, Any]) -> bool:
    """Whether a case is an optimization model (no experiment, no seed)."""
    return bool(document["domain"] == "optimization")


def is_search(document: Mapping[str, Any]) -> bool:
    """Whether a case's experiment has a search."""
    return any("search" in experiment for experiment in document.get("experiments", []))


def candidate_label(values: Mapping[str, Any]) -> str:
    """``<variable>=<value>`` for each variable, joined by commas: ``tills=2``."""
    return ",".join(f"{name}={value:g}" for name, value in values.items())


def search_values(
    adapter: Any, model: Model, experiment_id: str, workdir: Path
) -> dict[str, list[float]]:
    """Runs the search and returns ``search.best.<variable>`` (one value each) and each
    confirmed candidate's replication values as
    ``search.candidates[<label>].<metric>``."""
    outcome = run_experiment(adapter, model, experiment_id, workdir, workers=WORKERS)
    assert outcome.state == "done" and outcome.summary is not None
    found = outcome.summary["search"]
    values = {f"search.best.{name}": [float(v)] for name, v in found["best"]["set"].items()}
    for index, candidate in enumerate(found["candidates"]):
        if not candidate["confirmed"]:
            continue
        table = adapter.collect(workdir / f"confirm-{index:03d}").tables["replications"]
        label = candidate_label(candidate["set"])
        for row in table.to_pylist():
            key = f"search.candidates[{label}].{row['metric']}"
            values.setdefault(key, []).append(row["value"])
    return values


def solution_values(solution: Mapping[str, Any]) -> dict[str, list[float]]:
    """An optimization solution as one value per metric: ``objective`` and
    ``variables.<id>``; empty unless the status is ``optimal``, so every row then fails
    as not reported."""
    if solution["status"] != "optimal":
        return {}
    values = {"objective": [float(solution["objective"])]}
    values.update({f"variables.{name}": [float(v)] for name, v in solution["variables"].items()})
    return values


def run_case(
    document: Mapping[str, Any], workdir: Path, seed: int | None = None
) -> dict[str, list[float]]:
    """Runs the case's one experiment in ``workdir`` (with ``seed`` in place of the file's
    when given) and returns each metric's replication values, in replication order. An
    optimization case is solved once, with no seed, and gives ``solution_values``."""
    if seed is not None:
        document = copy.deepcopy(dict(document))
        document["experiments"][0]["seed"] = seed
    model = load(document)
    selection = select_adapter(model.domain, model.run.engine)
    assert selection.issues == () and selection.adapter is not None
    adapter = selection.adapter
    if model.program is not None:
        adapter.translate(model, None, workdir)
        adapter.run(workdir, lambda progress: None, threading.Event(), WORKERS)
        solution = adapter.collect(workdir).solution
        assert solution is not None
        return solution_values(solution)
    if model.experiments[0].search is not None:
        return search_values(adapter, model, model.experiments[0].id, workdir)
    adapter.translate(model, model.experiments[0].id, workdir)
    adapter.run(workdir, lambda progress: None, threading.Event(), WORKERS)
    rows = adapter.collect(workdir).tables["replications"].to_pylist()
    values: dict[str, list[float]] = {}
    for row in rows:
        values.setdefault(row["metric"], []).append(row["value"])
    return values


def four_figures(value: float) -> float:
    """``value`` rounded to four significant figures."""
    return float(f"{value:.3e}")


def check(expected: Expected, values: Mapping[str, Sequence[float]]) -> Check:
    """Judges one known answer against the replication values of its metric."""
    if expected.method not in METHODS:
        raise ValueError(f"unknown method {expected.method!r} for {expected.metric}")
    sample = values.get(expected.metric)
    nan = math.nan

    def unjudged(problem: str) -> Check:
        return Check(expected.metric, expected.method, expected.value, nan, nan, False, problem)

    if sample is None:
        return unjudged("not reported by the adapter")
    if any(math.isnan(value) for value in sample):
        return unjudged(f"{sum(map(math.isnan, sample))} of {len(sample)} values are NaN")
    if expected.method == "sig_figs_4":
        # An optimization result: one value, no standard error.
        if len(sample) != 1:
            return unjudged(f"{len(sample)} values; an optimization result has one")
        passed = four_figures(sample[0]) == four_figures(expected.value)
        return Check(expected.metric, expected.method, expected.value, sample[0], 0.0, passed)
    if len(sample) < 2:
        return unjudged(f"{len(sample)} replication values; a standard error needs 2")
    estimate = statistics.fmean(sample)
    se = statistics.stdev(sample) / math.sqrt(len(sample))
    if expected.method == "three_se":
        passed = abs(estimate - expected.value) <= SE_LIMIT * se
    else:
        passed = four_figures(estimate) == four_figures(expected.value)
    return Check(expected.metric, expected.method, expected.value, estimate, se, passed)


def failures(
    case: str, expected: Sequence[Expected], values: Mapping[str, Sequence[float]]
) -> list[str]:
    """The failure lines of every known answer of a case that does not pass."""
    checks = [check(row, values) for row in expected]
    return [result.message(case) for result in checks if not result.passed]


def emitted_metrics(model: Model) -> set[str]:
    """Every metric the process adapter reports for ``model`` (spec 1 "Metric names"), or
    for an optimization model the ``objective`` and each ``variables.<id>``."""
    if model.program is not None:
        return {"objective"} | {f"variables.{v.id}" for v in model.program.variables}
    metrics = {
        f"{component.id}.{measure}"
        for component in model.components
        for measure in PROCESS_TYPES[component.type].metrics
    } | {f"model.{measure}" for measure in MODEL_METRICS}
    search = model.experiments[0].search if model.experiments else None
    if search is None:
        return metrics
    # Only a search that takes the exhaustive path lists its combinations (a range may be
    # far too large to list).
    count = combination_count(model, search)
    fits = count is not None and count <= search.budget
    found = (combinations(model, search) or []) if fits else []
    labels = [candidate_label(dict(zip(search.variables, item, strict=True))) for item in found]
    return (
        metrics
        | {f"search.best.{name}" for name in search.variables}
        | {f"search.candidates[{label}].{metric}" for label in labels for metric in metrics}
    )


# ---------------------------------------------------------------------------------------
# The gates


@pytest.mark.benchmark
@pytest.mark.parametrize("case", CASES)
def test_benchmark(case: str, tmp_path: Path, current_milestone: str) -> None:
    document, expected = read_case(case)
    milestone = case_milestone(expected)
    if not is_due(milestone, current_milestone):
        pytest.skip(f"{case} is a {milestone} case; the build is at {current_milestone}")
    found = failures(case, expected, run_case(document, tmp_path))
    assert not found, "\n".join(found)


@pytest.mark.benchmark_coverage
@pytest.mark.parametrize("case", CASES)
def test_benchmark_coverage(case: str, tmp_path: Path, current_milestone: str) -> None:
    """Spec 2 seed-change rule: 20 consecutive seeds from the fixed one, 19 must pass."""
    document, expected = read_case(case)
    milestone = case_milestone(expected)
    if not is_due(milestone, current_milestone):
        pytest.skip(f"{case} is a {milestone} case; the build is at {current_milestone}")
    if is_optimization(document):
        pytest.skip(f"{case} is an optimization case: it has no seed to vary")
    first = int(document["experiments"][0]["seed"])
    failed: dict[int, list[str]] = {}
    for seed in range(first, first + COVERAGE_SEEDS):
        found = failures(case, expected, run_case(document, tmp_path / str(seed), seed))
        print(f"{case} seed {seed}: {'fail' if found else 'pass'}")
        if found:
            failed[seed] = found
    passed = COVERAGE_SEEDS - len(failed)
    print(f"{case}: {passed} of {COVERAGE_SEEDS} seeds from {first} pass")
    detail = "\n".join(f"seed {seed}: {line}" for seed, lines in failed.items() for line in lines)
    assert passed >= COVERAGE_PASSES, f"{case}: {passed} of {COVERAGE_SEEDS} pass\n{detail}"


# ---------------------------------------------------------------------------------------
# The benchmark files


def test_the_five_m2_cases_exist() -> None:
    assert M2_CASES <= set(CASES)


def test_every_case_with_stated_settings_exists() -> None:
    assert set(STATED_SETTINGS) <= set(CASES)


def test_the_m5_search_case_exists() -> None:
    """Spec 2 "Benchmark definitions": machine count (simulation-based)."""
    assert {case for case in CASES if is_search(read_case(case)[0])} == M5_SEARCH_CASES


def test_a_candidate_label_names_each_variable_and_value() -> None:
    assert candidate_label({"tills": 2}) == "tills=2"
    assert candidate_label({"tills": 2, "delay": 90.0}) == "tills=2,delay=90"


def test_the_four_m5_optimization_cases_exist() -> None:
    """Spec 2 "Benchmark definitions": product mix, knapsack, assignment and diet."""
    assert M5_OPTIMIZATION_CASES <= set(CASES)
    found = {case for case in CASES if is_optimization(read_case(case)[0])}
    assert found == M5_OPTIMIZATION_CASES


@pytest.mark.parametrize("case", CASES)
def test_each_model_loads_with_zero_issues_and_the_spec_2_settings(case: str) -> None:
    """100 replications of 200 h with 10 h of warm-up unless the case states its own, a
    fixed seed, one scenario; an optimization case has no experiment."""
    document, _ = read_case(case)
    model = load(document)
    if is_optimization(document):
        assert model.experiments == () and model.program is not None
        return
    assert len(model.experiments) == 1
    experiment = model.experiments[0]
    replications, length, warmup = STATED_SETTINGS.get(case, STANDARD_SETTINGS)
    assert experiment.replications == replications
    assert experiment.length.magnitude == length * 3600
    assert experiment.warmup.magnitude == warmup * 3600
    assert not experiment.seed_chosen
    assert experiment.seed == document["experiments"][0]["seed"]
    assert [scenario.id for scenario in experiment.scenarios] == ["default"]


@pytest.mark.parametrize("case", CASES)
def test_each_expected_row_is_well_formed_and_names_an_emitted_metric(case: str) -> None:
    document, expected = read_case(case)
    rows = json.loads((BENCHMARKS / case / "expected.json").read_text(encoding="utf-8"))
    assert rows and all(set(row) == ROW_KEYS for row in rows)
    emitted = emitted_metrics(load(document))
    for row in expected:
        assert row.metric in emitted, row.metric
        assert row.method in METHODS
        assert isinstance(row.value, float) and math.isfinite(row.value)
        assert row.source.strip()
        milestone_number(row.milestone)
    assert len({row.metric for row in expected}) == len(expected)
    if case in M2_CASES:
        assert {row.milestone for row in expected} == {"M2"}
        assert {row.method for row in expected} == {"three_se"}
    if is_optimization(document):
        assert {row.method for row in expected} == {"sig_figs_4"}
        assert "objective" in {row.metric for row in expected}
    else:
        # A search's best is one value, judged as an optimization result.
        one_value = {row.metric for row in expected if row.method == "sig_figs_4"}
        assert all(metric.startswith("search.best.") for metric in one_value)
    if is_search(document):
        assert {row.metric for row in expected if row.method == "sig_figs_4"}


def test_every_m2_block_appears_in_an_m2_benchmark() -> None:
    """Spec 2 acceptance row "Every block has a unit test and appears in a benchmark", M2
    for the five prototype blocks."""
    types = {
        component["type"] for case in M2_CASES for component in read_case(case)[0]["components"]
    }
    assert M2_BLOCKS <= types


def test_every_block_type_appears_in_a_benchmark_at_or_before_its_milestone() -> None:
    """The same row for every type of the catalogue: each appears in a case whose
    milestone is not later than the block's (all twelve by M4, AKS-107)."""
    assert set(BLOCK_MILESTONES) == set(PROCESS_TYPES)
    found: dict[str, set[str]] = {}
    for case in CASES:
        document, expected = read_case(case)
        milestone = case_milestone(expected)
        for component in document.get("components", []):
            found.setdefault(component["type"], set()).add(milestone)
    for block, milestone in BLOCK_MILESTONES.items():
        assert any(is_due(case, milestone) for case in found.get(block, ())), block


# ---------------------------------------------------------------------------------------
# The harness itself


def row(method: str = "three_se", value: float = 10.0) -> Expected:
    return Expected("x.wait.mean", value, method, "a formula", "M2")


def test_milestone_numbers_compare_as_numbers() -> None:
    assert milestone_number("M2") == 2
    assert milestone_number("M10") == 10
    assert is_due("M2", "M2") and is_due("M1", "M2")
    assert not is_due("M4", "M2")
    assert not is_due("M10", "M2") and is_due("M10", "M10")
    for bad in ("m2", "M", "M2a", "2"):
        with pytest.raises(ValueError, match="not a milestone name"):
            milestone_number(bad)


def test_a_case_runs_once_its_latest_row_is_due() -> None:
    rows = [
        row(),
        Expected("y", 1.0, "three_se", "s", "M10"),
        Expected("z", 1.0, "exact", "s", "M4"),
    ]
    assert case_milestone(rows) == "M10"


def test_three_se_passes_at_the_limit_and_fails_beyond_it() -> None:
    # Values 9, 11 (mean 10, sample sd sqrt(2), SE 1) and the known answer 3 SE away.
    values = {"x.wait.mean": [9.0, 11.0]}
    at_limit = check(row(value=13.0), values)
    assert at_limit.passed and at_limit.estimate == 10.0 and at_limit.se == 1.0
    beyond = check(row(value=13.5), values)
    assert not beyond.passed
    assert beyond.message("mm1") == (
        "mm1: x.wait.mean: estimate 10.0, known 13.5, SE 1.0, deviation 3.50 SE (limit 3)"
    )


def test_three_se_with_no_spread_passes_only_on_the_answer() -> None:
    assert check(row(value=10.0), {"x.wait.mean": [10.0, 10.0]}).passed
    off = check(row(value=10.5), {"x.wait.mean": [10.0, 10.0]})
    assert not off.passed and "deviation inf SE" in off.message("c")


def test_a_missing_metric_nan_values_or_one_value_fail() -> None:
    missing = check(row(), {})
    assert not missing.passed
    assert missing.message("c") == "c: x.wait.mean: not reported by the adapter"
    nan = check(row(), {"x.wait.mean": [1.0, math.nan, math.nan]})
    assert not nan.passed and nan.message("c") == "c: x.wait.mean: 2 of 3 values are NaN"
    one = check(row(), {"x.wait.mean": [10.0]})
    assert not one.passed and "a standard error needs 2" in one.message("c")


def test_exact_compares_four_significant_figures() -> None:
    known = 115.71428571428571
    assert check(row("exact", known), {"x.wait.mean": [115.7, 115.74]}).passed
    off = check(row("exact", known), {"x.wait.mean": [115.8, 115.8]})
    assert not off.passed
    assert "not equal to four significant figures (115.8 against 115.7)" in off.message("c")


def test_sig_figs_4_compares_the_one_optimization_value() -> None:
    known = 98 / 45  # the diet's 2.178
    exact = check(Expected("objective", known, "sig_figs_4", "s", "M5"), {"objective": [known]})
    assert exact.passed
    passed = check(Expected("objective", known, "sig_figs_4", "s", "M5"), {"objective": [2.1778]})
    assert passed.passed and passed.estimate == 2.1778 and passed.se == 0.0
    off = check(Expected("objective", known, "sig_figs_4", "s", "M5"), {"objective": [2.179]})
    assert not off.passed
    assert "(2.179 against 2.178)" in off.message("diet")
    zero = Expected("variables.a", 0.0, "sig_figs_4", "s", "M5")
    assert check(zero, {"variables.a": [0.0]}).passed
    assert check(zero, {"variables.a": [-0.0]}).passed
    assert not check(zero, {"variables.a": [1e-12]}).passed
    two = check(zero, {"variables.a": [0.0, 0.0]})
    assert not two.passed and "2 values; an optimization result has one" in two.message("c")


def test_a_solution_gives_one_value_per_metric_only_when_optimal() -> None:
    solution = {
        "status": "optimal",
        "objective": 21.0,
        "variables": {"b": 1.0, "c": 1},
        "constraints": {},
    }
    assert solution_values(solution) == {
        "objective": [21.0],
        "variables.b": [1.0],
        "variables.c": [1.0],
    }
    infeasible: dict[str, Any] = {
        "status": "infeasible",
        "objective": None,
        "variables": {},
        "constraints": {},
    }
    assert solution_values(infeasible) == {}
    [line] = failures("knapsack", [Expected("objective", 21.0, "sig_figs_4", "s", "M5")], {})
    assert line == "knapsack: objective: not reported by the adapter"


def test_an_unknown_method_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown method 'two_se'"):
        check(row("two_se"), {"x.wait.mean": [1.0, 2.0]})


def test_failures_lists_only_the_failing_rows() -> None:
    values = {"x.wait.mean": [9.0, 11.0]}
    rows = [row(value=10.0), row(value=20.0)]
    assert failures("c", rows, values) == [
        "c: x.wait.mean: estimate 10.0, known 20.0, SE 1.0, deviation 10.00 SE (limit 3)"
    ]


def test_a_seed_override_leaves_the_file_unchanged(tmp_path: Path) -> None:
    """The coverage run replaces the seed in a copy; a short run keeps the test fast."""
    document, _ = read_case("mm1")
    short = copy.deepcopy(document)
    short["experiments"][0].update({"length": "2 h", "warmup": "0 s", "replications": 2})
    first = run_case(short, tmp_path / "a", seed=7)
    again = run_case(short, tmp_path / "b", seed=7)
    other = run_case(short, tmp_path / "c", seed=8)
    assert short["experiments"][0]["seed"] == document["experiments"][0]["seed"]
    assert first == again and first != other
    assert len(first["server.wait.mean"]) == 2
