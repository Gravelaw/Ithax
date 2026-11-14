"""``expected.json``'s layout and the pass rules a run is judged by (spec 4 "Template
package", spec 2 "Benchmarks"; AKS-122)."""

from typing import Any

import pytest

from ithax.templates.expected import (
    Estimate,
    ExpectedRow,
    four_figures,
    judge,
    read_rows,
    summary_estimates,
)

ROW: dict[str, Any] = {
    "metric": "till.wait.mean",
    "value": 270.0,
    "method": "three_se",
    "source": "theory",
    "reference": "M/M/1",
}


def test_a_row_is_read_with_run_template_by_default() -> None:
    rows, problems = read_rows([ROW, {**ROW, "value": 1, "run": "exercise"}])
    assert problems == ()
    assert rows == (
        ExpectedRow("till.wait.mean", 270.0, "three_se", "theory", "M/M/1", "template"),
        ExpectedRow("till.wait.mean", 1.0, "three_se", "theory", "M/M/1", "exercise"),
    )


@pytest.mark.parametrize("document", [None, {}, [], "rows"])
def test_expected_json_is_an_array_of_rows(document: object) -> None:
    rows, problems = read_rows(document)
    assert rows == ()
    assert [problem.path for problem in problems] == [""]


@pytest.mark.parametrize(
    ("row", "path"),
    [
        ("row", "/1"),
        ({**ROW, "tolerance": 1}, "/1/tolerance"),
        ({key: value for key, value in ROW.items() if key != "source"}, "/1/source"),
        ({**ROW, "metric": " "}, "/1/metric"),
        ({**ROW, "value": True}, "/1/value"),
        ({**ROW, "value": 10**400}, "/1/value"),
        ({**ROW, "value": "270 s"}, "/1/value"),
        ({**ROW, "method": "relative"}, "/1/method"),
        ({**ROW, "source": "textbook"}, "/1/source"),
        ({**ROW, "reference": ""}, "/1/reference"),
        ({**ROW, "run": "changed"}, "/1/run"),
    ],
)
def test_each_layout_problem_is_at_its_place(row: object, path: str) -> None:
    rows, problems = read_rows([ROW, row])
    assert len(rows) == 1
    assert [problem.path for problem in problems] == [path]
    assert problems[0].message and problems[0].hint


SUMMARY: dict[str, Any] = {
    "replications": 30,
    "confidence": 0.95,
    "scenarios": {
        "default": {
            "set": {},
            "metrics": {
                "till.wait.mean": {"mean": 267.63, "half_width": 9.7858, "unit": "s", "n": 30},
                "till.utilization": {"mean": 0.75, "half_width": 0.0, "unit": "1", "n": 30},
                "exit.cycle_time.mean": {"mean": None, "half_width": None, "unit": "s", "n": 0},
                "store.stockouts": {"mean": 0.0, "half_width": None, "unit": "1", "n": 1},
            },
        }
    },
}


def test_a_process_summary_gives_the_default_scenario_s_metrics() -> None:
    estimates = summary_estimates(SUMMARY)
    assert estimates["till.wait.mean"] == Estimate(267.63, 9.7858, 30, 0.95)
    assert estimates["exit.cycle_time.mean"] == Estimate(None, None, 0, 0.95)


def test_a_search_summary_gives_its_best_values() -> None:
    summary = {**SUMMARY, "search": {"best": {"set": {"tills": 2}}}}
    assert summary_estimates(summary)["search.best.tills"] == Estimate(2.0, None, 1, None)


def test_an_optimization_summary_gives_its_objective_and_variables() -> None:
    summary = {
        "model": "Mix",
        "status": "optimal",
        "objective": 2200.0000000001,
        "variables": {"chairs": 24.000000000000004, "tables": 14},
    }
    estimates = summary_estimates(summary)
    assert set(estimates) == {"objective", "variables.chairs", "variables.tables"}
    assert estimates["variables.tables"] == Estimate(14.0, None, 1, None)


def row(metric: str, value: float, method: str = "three_se") -> ExpectedRow:
    return ExpectedRow(metric, value, method, "theory", "x")  # type: ignore[arg-type]


def test_three_se_passes_within_three_standard_errors() -> None:
    estimates = summary_estimates(SUMMARY)
    # t(0.975, 29) = 2.045229642132703; the standard error is 9.7858 / t = 4.7847.
    passed = judge(row("till.wait.mean", 270.0), estimates)
    assert passed.passed and passed.se == pytest.approx(4.78471, rel=1e-5)
    assert "passed" in passed.message()
    failed = judge(row("till.wait.mean", 267.63 + 3.01 * 4.78471), estimates)
    assert not failed.passed
    assert "failed" in failed.message()
    assert judge(row("till.utilization", 0.75), estimates).passed
    assert not judge(row("till.utilization", 0.7500001), estimates).passed


def test_exact_and_sig_figs_4_compare_four_significant_figures() -> None:
    estimates = summary_estimates(SUMMARY)
    assert judge(row("till.utilization", 0.75004, "exact"), estimates).passed
    assert not judge(row("till.utilization", 0.7506, "exact"), estimates).passed
    single = {"objective": Estimate(2200.0000001, None, 1, None)}
    assert judge(row("objective", 2200, "sig_figs_4"), single).passed
    assert not judge(row("objective", 2201, "sig_figs_4"), single).passed
    assert four_figures(162 / 11) == 14.73


@pytest.mark.parametrize(
    ("judged", "problem"),
    [
        (row("till.queue_length.mean", 2.25), "not reported by the run"),
        (row("exit.cycle_time.mean", 360.0), "the run's mean is undefined"),
        (row("till.wait.mean", 270.0, "sig_figs_4"), "30 values; sig_figs_4 takes one"),
        (row("store.stockouts", 0.0), "the run gives no standard error"),
    ],
)
def test_a_row_that_cannot_be_judged_fails_and_says_why(judged: ExpectedRow, problem: str) -> None:
    result = judge(judged, summary_estimates(SUMMARY))
    assert not result.passed
    assert result.problem == problem
    assert result.message() == f"{judged.metric} (template): {problem}"
