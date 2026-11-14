"""The finding rules of spec 4 "Finding rules" (AKS-117).

Spec 4's acceptance row "Each finding rule fires on its `_fires` fixture and is silent on its
`_silent` fixture" (M8), with the wording of spec 4's patterns as the research note
``docs/research/spec-4-findings-wording.md`` reads them, the thresholds as an input with
spec 4's defaults, n_required and its rounding, and the same findings for the same input.

The fixtures are real runs (``tests/findings/make_fixtures.py``); cases no example
exercises are made here by editing a copy of a fixture's summary or model, as each test
says.
"""

import json
from typing import Any

import pytest
from findings_support import Run, read_run

from ithax.findings import (
    DEFAULT_THRESHOLDS,
    RULES,
    Finding,
    Thresholds,
    find,
    n_required,
)
from ithax.findings.rules import key_metrics

LINE_WAIT = (
    "The estimates for weld.wait.mean are still uncertain: weld.wait.mean is 15.7 min plus or "
    "minus 2.09 min. About 60 replications would be needed for a 10% interval."
)


def rules_of(found: list[Finding]) -> list[str]:
    return [item.rule for item in found]


def texts(found: list[Finding], rule: str) -> list[str]:
    return [item.text for item in found if item.rule == rule]


# --- the acceptance row --------------------------------------------------------------------


@pytest.mark.parametrize("rule", RULES)
def test_each_rule_fires_on_its_fires_fixture(rule: str) -> None:
    summary, model = read_run(f"{rule}_fires")
    assert rule in rules_of(find(summary, model))


@pytest.mark.parametrize("rule", RULES)
def test_each_rule_is_silent_on_its_silent_fixture(rule: str) -> None:
    summary, model = read_run(f"{rule}_silent")
    assert rule not in rules_of(find(summary, model))


def test_the_rules_are_the_five_of_spec_4() -> None:
    assert RULES == (
        "bottleneck",
        "unstable",
        "idle_capacity",
        "not_enough_runs",
        "optimization_result",
    )


def test_the_three_machine_line_fires_bottleneck_and_not_enough_runs() -> None:
    summary, model = read_run("bottleneck_fires")
    found = find(summary, model)
    assert [item.as_dict() for item in found] == [
        {
            "rule": "bottleneck",
            "severity": "info",
            "component": "weld",
            "scenario": "default",
            "text": "weld is the bottleneck: busy 90% of the time, with an average wait of "
            "15.7 min.",
            "evidence": {
                "weld.utilization": summary["scenarios"]["default"]["metrics"]["weld.utilization"][
                    "mean"
                ],
                "weld.wait.mean": summary["scenarios"]["default"]["metrics"]["weld.wait.mean"][
                    "mean"
                ],
            },
        },
        {
            "rule": "not_enough_runs",
            "severity": "warning",
            "component": None,
            "scenario": "default",
            "text": LINE_WAIT,
            "evidence": {
                "weld.wait.mean": summary["scenarios"]["default"]["metrics"]["weld.wait.mean"],
                "n_required": 60,
            },
        },
    ]


def test_the_coffee_shop_fires_nothing() -> None:
    summary, model = read_run("bottleneck_silent")
    assert find(summary, model) == []


def test_the_fixtures_hold_the_measured_values_logged_in_decisions() -> None:
    """The utilizations and half-widths recorded in docs/DECISIONS.md (AKS-117) and spec 4."""
    line = read_run("bottleneck_fires")[0]["scenarios"]["default"]["metrics"]
    assert round(line["weld.utilization"]["mean"], 3) == 0.901
    assert round(
        100 * line["weld.wait.mean"]["half_width"] / line["weld.wait.mean"]["mean"], 1
    ) == (13.3)
    shop = read_run("bottleneck_silent")[0]["scenarios"]["default"]["metrics"]
    assert round(shop["till.utilization"]["mean"], 3) == 0.749
    assert round(
        100 * shop["till.wait.mean"]["half_width"] / shop["till.wait.mean"]["mean"], 1
    ) == (3.7)


# --- thresholds ----------------------------------------------------------------------------


def test_the_default_thresholds_are_spec_4s() -> None:
    assert Thresholds() == DEFAULT_THRESHOLDS
    assert DEFAULT_THRESHOLDS.bottleneck_utilization == 0.85
    assert DEFAULT_THRESHOLDS.idle_utilization == 0.30
    assert DEFAULT_THRESHOLDS.relative_half_width == 0.10
    assert DEFAULT_THRESHOLDS.min_time_s == 60.0
    assert DEFAULT_THRESHOLDS.min_rate_per_s == 1 / 3600


@pytest.mark.parametrize(
    ("name", "thresholds", "rule", "fires"),
    [
        ("bottleneck_fires", Thresholds(bottleneck_utilization=0.95), "bottleneck", False),
        ("bottleneck_silent", Thresholds(bottleneck_utilization=0.70), "bottleneck", True),
        ("idle_capacity_fires", Thresholds(idle_utilization=0.20), "idle_capacity", False),
        ("idle_capacity_silent", Thresholds(idle_utilization=0.80), "idle_capacity", True),
        ("not_enough_runs_fires", Thresholds(relative_half_width=0.15), "not_enough_runs", False),
        ("not_enough_runs_fires", Thresholds(min_time_s=1000.0), "not_enough_runs", False),
        ("not_enough_runs_silent", Thresholds(relative_half_width=0.03), "not_enough_runs", True),
    ],
)
def test_changing_a_threshold_changes_the_outcome(
    name: str, thresholds: Thresholds, rule: str, fires: bool
) -> None:
    summary, model = read_run(name)
    assert (rule in rules_of(find(summary, model))) is not fires
    assert (rule in rules_of(find(summary, model, thresholds))) is fires


@pytest.mark.parametrize(
    "changes",
    [
        {"bottleneck_utilization": 1.5},
        {"bottleneck_utilization": -0.1},
        {"idle_utilization": 1.01},
        {"relative_half_width": 0.0},
        {"min_time_s": -1.0},
        {"min_rate_per_s": float("nan")},
        {"bottleneck_utilization": True},
    ],
)
def test_a_threshold_out_of_range_is_refused(changes: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="threshold"):
        Thresholds(**changes)


# --- bottleneck ----------------------------------------------------------------------------


def test_bottleneck_at_exactly_the_threshold_fires() -> None:
    summary, model = read_run("bottleneck_fires")
    utilization = summary["scenarios"]["default"]["metrics"]["weld.utilization"]["mean"]
    assert "bottleneck" in rules_of(find(summary, model, Thresholds(utilization)))
    above = Thresholds(bottleneck_utilization=min(1.0, utilization + 1e-9))
    assert "bottleneck" not in rules_of(find(summary, model, above))


def test_a_utilization_tie_goes_to_the_longest_mean_wait_then_the_first_server() -> None:
    summary, model = read_run("bottleneck_fires")
    metrics = summary["scenarios"]["default"]["metrics"]
    metrics["cut.utilization"]["mean"] = metrics["weld.utilization"]["mean"]
    metrics["cut.wait.mean"]["mean"] = 2000.0
    found = [item for item in find(summary, model) if item.rule == "bottleneck"]
    assert [item.component for item in found] == ["cut"]
    metrics["cut.wait.mean"]["mean"] = metrics["weld.wait.mean"]["mean"]
    found = [item for item in find(summary, model) if item.rule == "bottleneck"]
    assert [item.component for item in found] == ["cut"]
    metrics["cut.wait.mean"]["mean"] = None
    found = [item for item in find(summary, model) if item.rule == "bottleneck"]
    assert [item.component for item in found] == ["weld"]


def test_a_bottleneck_without_a_measured_wait_says_only_how_busy_it_is() -> None:
    summary, model = read_run("bottleneck_fires")
    summary["scenarios"]["default"]["metrics"]["weld.wait.mean"]["mean"] = None
    found = [item for item in find(summary, model) if item.rule == "bottleneck"]
    assert found[0].text == "weld is the bottleneck: busy 90% of the time."
    assert found[0].evidence == {
        "weld.utilization": summary["scenarios"]["default"]["metrics"]["weld.utilization"]["mean"],
        "weld.wait.mean": None,
    }


def without_a_queue(server: str) -> Any:
    def change(document: dict[str, Any]) -> None:
        component = next(item for item in document["components"] if item["id"] == server)
        component["params"]["queue_capacity"] = 0

    return change


def test_a_bottleneck_without_a_queue_of_its_own_says_only_how_busy_it_is() -> None:
    """Spec 4 (AKS-125): a server with ``queue_capacity`` 0 has no queue of its own, its
    items wait in the block before it, so the text gives no wait (the three-machine-line
    template said "with an average wait of 0 s"); the evidence still holds its wait."""
    summary, model = read_run("bottleneck_fires", without_a_queue("weld"))
    found = [item for item in find(summary, model) if item.rule == "bottleneck"]
    assert found[0].text == "weld is the bottleneck: busy 90% of the time."
    metrics = summary["scenarios"]["default"]["metrics"]
    assert found[0].evidence == {
        "weld.utilization": metrics["weld.utilization"]["mean"],
        "weld.wait.mean": metrics["weld.wait.mean"]["mean"],
    }
    summary, model = read_run("bottleneck_fires", without_a_queue("cut"))
    assert texts(find(summary, model), "bottleneck")[0].endswith(
        "with an average wait of 15.7 min."
    )


def test_a_server_without_a_utilization_is_not_judged() -> None:
    summary, model = read_run("bottleneck_fires")
    summary["scenarios"]["default"]["metrics"]["weld.utilization"]["mean"] = None
    del summary["scenarios"]["default"]["metrics"]["paint.utilization"]
    assert "bottleneck" not in rules_of(find(summary, model))
    assert key_metrics(summary["scenarios"]["default"]["metrics"], model)[-1] == "cut.wait.mean"


def add_failure(target: str) -> Any:
    def change(document: dict[str, Any]) -> None:
        document["components"].append(
            {
                "id": "breakdown",
                "type": "failure",
                "params": {
                    "target": target,
                    "time_to_failure": {"dist": "exponential", "mean": "100 h"},
                    "time_to_repair": {"dist": "exponential", "mean": "1 h"},
                },
            }
        )

    return change


def add_schedule(target: str) -> Any:
    def change(document: dict[str, Any]) -> None:
        document["components"].append(
            {
                "id": "shift",
                "type": "schedule",
                "params": {
                    "target": target,
                    "shifts": [{"start": "0 h", "end": "16 h", "capacity": 1}],
                },
            }
        )

    return change


def test_a_bottleneck_whose_capacity_varies_is_busy_of_the_time_it_was_available() -> None:
    summary, model = read_run("bottleneck_fires", add_failure("weld"))
    assert texts(find(summary, model), "bottleneck") == [
        "weld is the bottleneck: busy 90% of the time it was available, with an average wait "
        "of 15.7 min."
    ]
    summary, model = read_run("bottleneck_fires", add_schedule("weld"))
    assert texts(find(summary, model), "bottleneck")[0].startswith(
        "weld is the bottleneck: busy 90% of the time it was available,"
    )


# --- unstable ------------------------------------------------------------------------------


def test_unstable_restates_w201_for_the_server() -> None:
    summary, model = read_run("unstable_fires")
    found = [item for item in find(summary, model) if item.rule == "unstable"]
    w201 = next(issue for issue in summary["warnings"] if issue["code"] == "W201")
    assert [item.as_dict() for item in found] == [
        {
            "rule": "unstable",
            "severity": "warning",
            "component": "till",
            "scenario": None,
            "text": "till cannot keep up. Work arrives faster than it can be done, so the "
            "queue will keep growing.",
            "evidence": {"warning": "W201", "path": w201["path"], "message": w201["message"]},
        }
    ]


def test_unstable_reads_w201_and_computes_nothing() -> None:
    """One computation, not two (spec 4): with the W201 removed from the summary the rule is
    silent, and with a W201 added to a stable run it fires."""
    summary, model = read_run("unstable_fires")
    summary["warnings"] = [issue for issue in summary["warnings"] if issue["code"] != "W201"]
    assert "unstable" not in rules_of(find(summary, model))
    summary, model = read_run("unstable_silent")
    issue = {
        "code": "W201",
        "severity": "warning",
        "component": "till",
        "path": "/components/1",
        "message": "m",
        "hint": "h",
    }
    summary["warnings"] = [issue, dict(issue), {**issue, "component": None}]
    assert texts(find(summary, model), "unstable") == [
        "till cannot keep up. Work arrives faster than it can be done, so the queue will keep "
        "growing."
    ]


# --- idle_capacity -------------------------------------------------------------------------


def test_idle_capacity_says_how_idle_the_server_is() -> None:
    summary, model = read_run("idle_capacity_fires")
    found = [item for item in find(summary, model) if item.rule == "idle_capacity"]
    assert [item.as_dict() for item in found] == [
        {
            "rule": "idle_capacity",
            "severity": "info",
            "component": "till",
            "scenario": "default",
            "text": "till is idle 75% of the time.",
            "evidence": {
                "till.utilization": summary["scenarios"]["default"]["metrics"]["till.utilization"][
                    "mean"
                ]
            },
        }
    ]


def test_a_server_with_a_schedule_is_never_idle_capacity() -> None:
    summary, model = read_run("idle_capacity_fires", add_schedule("till"))
    assert "idle_capacity" not in rules_of(find(summary, model))


def test_a_server_on_a_scheduled_pool_is_never_idle_capacity() -> None:
    def pooled(document: dict[str, Any]) -> None:
        document["components"].append(
            {"id": "staff", "type": "resource_pool", "params": {"capacity": 3}}
        )
        document["components"][1]["params"]["pool"] = "staff"
        add_schedule("staff")(document)

    summary, model = read_run("idle_capacity_fires", pooled)
    assert "idle_capacity" not in rules_of(find(summary, model))


def test_an_idle_server_with_a_failure_is_idle_of_the_time_it_was_available() -> None:
    summary, model = read_run("idle_capacity_fires", add_failure("till"))
    assert texts(find(summary, model), "idle_capacity") == [
        "till is idle 75% of the time it was available."
    ]


def test_idle_capacity_below_not_at_the_threshold() -> None:
    summary, model = read_run("idle_capacity_fires")
    utilization = summary["scenarios"]["default"]["metrics"]["till.utilization"]["mean"]
    assert "idle_capacity" not in rules_of(
        find(summary, model, Thresholds(idle_utilization=utilization))
    )


# --- not_enough_runs -----------------------------------------------------------------------


def test_the_key_metrics_are_spec_4s_in_order() -> None:
    summary, model = read_run("bottleneck_fires")
    metrics = summary["scenarios"]["default"]["metrics"]
    assert key_metrics(metrics, model) == [
        "exit.throughput",
        "exit.cycle_time.mean",
        "weld.wait.mean",
    ]
    summary, model = read_run("optimization_result_fires")
    metrics = summary["scenarios"]["default"]["metrics"]
    assert key_metrics(metrics, model) == [
        "till.wait.mean",
        "till.utilization",
        "exit.throughput",
        "exit.cycle_time.mean",
    ]


def test_not_enough_runs_lists_every_uncertain_metric_and_names_the_widest() -> None:
    summary, model = read_run("not_enough_runs_fires")
    metrics = summary["scenarios"]["default"]["metrics"]
    metrics["exit.cycle_time.mean"]["half_width"] = 0.12 * metrics["exit.cycle_time.mean"]["mean"]
    metrics["exit.throughput"]["half_width"] = 0.21 * metrics["exit.throughput"]["mean"]
    metrics["exit.throughput"]["n"] = 20
    found = [item for item in find(summary, model) if item.rule == "not_enough_runs"]
    assert len(found) == 1
    assert found[0].text == (
        "The estimates for exit.throughput, exit.cycle_time.mean and weld.wait.mean are still "
        "uncertain: exit.throughput is 30 per hour plus or minus 6.3 per hour. About 90 "
        "replications would be needed for a 10% interval."
    )
    assert found[0].evidence["n_required"] == 90
    assert list(found[0].evidence) == [
        "exit.throughput",
        "exit.cycle_time.mean",
        "weld.wait.mean",
        "n_required",
    ]


def test_the_largest_n_required_is_reported_even_when_the_widest_has_fewer_values() -> None:
    summary, model = read_run("not_enough_runs_fires")
    metrics = summary["scenarios"]["default"]["metrics"]
    metrics["exit.cycle_time.mean"]["half_width"] = 0.13 * metrics["exit.cycle_time.mean"]["mean"]
    metrics["exit.cycle_time.mean"]["n"] = 100
    found = [item for item in find(summary, model) if item.rule == "not_enough_runs"]
    assert "weld.wait.mean is 15.7 min" in found[0].text
    assert found[0].evidence["n_required"] == n_required(
        100, metrics["exit.cycle_time.mean"]["half_width"], metrics["exit.cycle_time.mean"]["mean"]
    )
    assert "About 170 replications" in found[0].text


def test_not_enough_runs_ignores_small_means_and_undefined_values() -> None:
    summary, model = read_run("not_enough_runs_fires")
    metrics = summary["scenarios"]["default"]["metrics"]
    # a wait below 60 s, a throughput below 1 per hour and an undefined half-width
    metrics["weld.wait.mean"]["mean"] = 59.9
    metrics["exit.throughput"]["mean"] = 0.9 / 3600
    metrics["exit.throughput"]["half_width"] = 0.5 / 3600
    metrics["exit.cycle_time.mean"]["half_width"] = None
    assert "not_enough_runs" not in rules_of(find(summary, model))
    metrics["exit.throughput"]["mean"] = 1 / 3600
    assert texts(find(summary, model), "not_enough_runs") == [
        "The estimates for exit.throughput are still uncertain: exit.throughput is 1 per hour "
        "plus or minus 0.5 per hour. About 750 replications would be needed for a 10% "
        "interval."
    ]


def test_a_key_metric_in_another_unit_has_no_floor() -> None:
    summary, model = read_run("optimization_result_fires")
    metrics = summary["scenarios"]["default"]["metrics"]
    metrics["till.utilization"]["half_width"] = 0.05
    assert texts(find(summary, model), "not_enough_runs") == [
        "The estimates for till.utilization are still uncertain: till.utilization is 37.4% "
        "plus or minus 5%. About 60 replications would be needed for a 10% interval."
    ]
    metrics["till.utilization"]["mean"] = 0.0
    assert "not_enough_runs" not in rules_of(find(summary, model))


def test_the_interval_named_follows_the_threshold() -> None:
    summary, model = read_run("not_enough_runs_silent")
    found = texts(find(summary, model, Thresholds(relative_half_width=0.025)), "not_enough_runs")
    assert found == [
        "The estimates for exit.cycle_time.mean and till.wait.mean are still uncertain: "
        "till.wait.mean is 4.46 min plus or minus 0.163 min. About 70 replications would be needed "
        "for a 2.5% interval."
    ]


def test_one_finding_per_scenario() -> None:
    summary, model = read_run("not_enough_runs_scenarios")
    found = [item for item in find(summary, model) if item.rule == "not_enough_runs"]
    assert [item.scenario for item in found] == ["now", "slower"]
    assert all("till.wait.mean" in item.text for item in found)


def test_common_random_numbers_separate_the_close_scenarios_so_the_pair_is_silent() -> None:
    summary, model = read_run("not_enough_runs_scenarios")
    pair = summary["differences"][0]
    assert (pair["scenario"], pair["against"]) == ("slower", "now")
    assert pair["metrics"]["till.wait.mean"]["separated"] is True
    assert not [item for item in find(summary, model) if "cannot be told apart" in item.text]


def unseparated(summary: dict[str, Any], metric: str, half_width: float) -> None:
    pair = summary["differences"][0]["metrics"][metric]
    pair.update({"mean": 2.0, "half_width": half_width, "separated": False})


def test_two_scenarios_that_cannot_be_told_apart() -> None:
    """The real run's difference, edited to include zero with a half-width of 40 s, above 10%
    of the smaller of the two mean waits (25.1 s)."""
    summary, model = read_run("not_enough_runs_scenarios")
    unseparated(summary, "till.wait.mean", 40.0)
    found = [item for item in find(summary, model) if "cannot be told apart" in item.text]
    assert [item.as_dict() for item in found] == [
        {
            "rule": "not_enough_runs",
            "severity": "warning",
            "component": None,
            "scenario": "slower",
            "text": "now and slower cannot be told apart on till.wait.mean yet.",
            "evidence": {
                "scenarios": ["now", "slower"],
                "till.wait.mean": summary["differences"][0]["metrics"]["till.wait.mean"],
            },
        }
    ]
    unseparated(summary, "exit.cycle_time.mean", 40.0)
    found = [item for item in find(summary, model) if "cannot be told apart" in item.text]
    assert found[0].text == (
        "now and slower cannot be told apart on exit.cycle_time.mean and till.wait.mean yet."
    )


def test_a_pair_needs_a_half_width_above_the_share_of_the_smaller_mean() -> None:
    summary, model = read_run("not_enough_runs_scenarios")
    smaller = summary["scenarios"]["now"]["metrics"]["till.wait.mean"]["mean"]
    unseparated(summary, "till.wait.mean", 0.1 * smaller)
    assert not [item for item in find(summary, model) if "cannot be told apart" in item.text]
    unseparated(summary, "till.wait.mean", 0.1 * smaller * 1.001)
    assert [item for item in find(summary, model) if "cannot be told apart" in item.text]


def test_a_pair_is_not_judged_on_small_means_or_undefined_values() -> None:
    summary, model = read_run("not_enough_runs_scenarios")
    unseparated(summary, "till.wait.mean", 100.0)
    summary["scenarios"]["now"]["metrics"]["till.wait.mean"]["mean"] = 50.0
    assert not [item for item in find(summary, model) if "cannot be told apart" in item.text]
    summary["scenarios"]["now"]["metrics"]["till.wait.mean"]["mean"] = None
    assert not [item for item in find(summary, model) if "cannot be told apart" in item.text]
    summary, model = read_run("not_enough_runs_scenarios")
    unseparated(summary, "till.wait.mean", 100.0)
    summary["differences"][0]["metrics"]["till.wait.mean"]["half_width"] = None
    assert not [item for item in find(summary, model) if "cannot be told apart" in item.text]


@pytest.mark.parametrize(
    ("n", "half_width", "mean", "share", "required"),
    [
        (30, 125.5, 941.482, 0.1, 60),  # the three-machine line: 53.3 rounds up to 60
        (10, 20.0, 100.0, 0.1, 40),  # exactly 40 stays 40
        (10, 20.000001, 100.0, 0.1, 50),  # just above 40 goes to 50
        (10, 812.76, 2500.0, 0.1, 110),  # Kelton et al.: 105.7, run as 110
        (10, 11.0, 100.0, 0.1, 20),
        (30, 9.786, 267.631, 0.025, 70),
    ],
)
def test_n_required_rounds_up_to_the_next_10(
    n: int, half_width: float, mean: float, share: float, required: int
) -> None:
    assert n_required(n, half_width, mean, share) == required


def test_n_required_uses_the_share_as_written() -> None:
    """0.1 and 0.2 are not exact in binary; n_required reads them as the decimals written,
    so 10 x (0.2 / 0.1)^2 is 40, not just above it."""
    assert n_required(10, 0.2, 1.0, 0.1) == 40


# --- optimization_result -------------------------------------------------------------------


def search_finding(summary: dict[str, Any], run: Run) -> Finding:
    found = [item for item in find(summary, run[1]) if item.rule == "optimization_result"]
    assert len(found) == 1
    return found[0]


def test_optimization_result_of_a_search() -> None:
    run = read_run("optimization_result_fires")
    summary = run[0]
    found = search_finding(summary, run)
    assert found.as_dict() == {
        "rule": "optimization_result",
        "severity": "info",
        "component": None,
        "scenario": "default",
        "text": "Best found: tills = 2. till.wait.mean improved from 4.46 min to 14.6 s. It is "
        "clearly better than the next best setting tried.",
        "evidence": {
            "status": "feasible",
            "best": {"tills": 2},
            "metric": "till.wait.mean",
            "before": summary["search"]["objective"]["before"],
            "after": summary["search"]["objective"]["after"],
            "separated": True,
        },
    }


def test_a_search_whose_best_cannot_be_told_from_the_runner_up_says_so() -> None:
    run = read_run("optimization_result_fires")
    run[0]["search"]["separated"] = False
    assert search_finding(run[0], run).text.endswith(
        "The next best setting tried cannot be told apart from it yet."
    )


def test_a_search_with_no_runner_up_says_nothing_of_one() -> None:
    run = read_run("optimization_result_fires")
    run[0]["search"]["candidates"][0]["feasible"] = False
    run[0]["search"]["separated"] = False
    assert search_finding(run[0], run).text == (
        "Best found: tills = 2. The starting values break a constraint; till.wait.mean went "
        "from 4.46 min to 14.6 s."
    )


def test_a_search_whose_starting_values_are_best() -> None:
    run = read_run("optimization_result_fires")
    search = run[0]["search"]
    search["best"]["set"] = dict(search["candidates"][0]["set"])
    search["objective"]["after"] = search["objective"]["before"]
    search["candidates"][1]["feasible"] = False
    search["separated"] = False
    assert search_finding(run[0], run).text == (
        "Best found: the starting values, tills = 1. No setting tried improved till.wait.mean, "
        "which is 4.46 min."
    )


def test_an_infeasible_search() -> None:
    run = read_run("optimization_result_fires")
    search = run[0]["search"]
    search["status"] = "infeasible"
    search["best"]["set"] = dict(search["candidates"][0]["set"])
    found = search_finding(run[0], run)
    assert found.severity == "warning"
    assert found.text == (
        "No setting tried meets every constraint. With the starting values, tills = 1, "
        "till.wait.mean is 4.46 min."
    )


def test_a_search_whose_mean_is_undefined_or_worse() -> None:
    run = read_run("optimization_result_fires")
    search = run[0]["search"]
    search["objective"]["before"] = None
    assert "till.wait.mean went from not defined to 14.6 s." in search_finding(run[0], run).text
    search["objective"]["before"] = 10.0
    assert "till.wait.mean went from 10 s to 14.6 s." in search_finding(run[0], run).text


def test_a_maximizing_search_improves_upward() -> None:
    def maximize(document: dict[str, Any]) -> None:
        document["objectives"][0].update({"metric": "till.utilization", "sense": "maximize"})

    run = read_run("optimization_result_fires", maximize)
    search = run[0]["search"]
    search["objective"].update({"metric": "till.utilization", "before": 0.5, "after": 0.6})
    assert "till.utilization improved from 50% to 60%." in search_finding(run[0], run).text


def test_the_sense_is_the_searched_objectives_not_another_on_the_same_metric() -> None:
    """Review of PR #42: two objectives may name one metric; the sense is that of the
    objective the experiment's search names, here the second."""

    def rival(document: dict[str, Any]) -> None:
        document["objectives"].insert(
            0, {"id": "long_wait", "metric": "till.wait.mean", "sense": "maximize"}
        )

    run = read_run("optimization_result_fires", rival)
    assert "till.wait.mean improved from 4.46 min to 14.6 s." in search_finding(run[0], run).text


def test_a_search_over_a_quantity_shows_it_in_display_units() -> None:
    def quantity_variable(document: dict[str, Any]) -> None:
        document["parameters"]["service_mean"] = {
            "value": "1.5 min",
            "type": "quantity",
            "min": "1 min",
            "max": "2 min",
        }
        document["experiments"][0]["search"]["variables"] = ["tills", "service_mean"]

    run = read_run("optimization_result_fires", quantity_variable)
    run[0]["search"]["best"]["set"] = {"tills": 2, "service_mean": 72.0}
    assert search_finding(run[0], run).text.startswith(
        "Best found: tills = 2, service_mean = 1.2 min."
    )


def program_finding(summary: dict[str, Any], run: Run) -> Finding:
    found = find(summary, run[1])
    assert rules_of(found) == ["optimization_result"]
    return found[0]


def test_optimization_result_of_a_mathematical_optimization() -> None:
    run = read_run("optimization_result_program")
    summary = run[0]
    assert program_finding(summary, run).as_dict() == {
        "rule": "optimization_result",
        "severity": "info",
        "component": None,
        "scenario": None,
        "text": "Best found: chairs = 24, tables = 14. The objective is 2,200, with wood and "
        "labour tight.",
        "evidence": {
            "status": "optimal",
            "objective": 2200.0,
            "variables": summary["variables"],
            "tight": ["wood", "labour"],
        },
    }


def test_a_mathematical_optimization_lists_only_the_variables_not_at_0() -> None:
    """Spec 4 (AKS-125): "Best found" names the variables that are not 0, then how many are
    (a -0 from the solver is 0); the evidence keeps every value."""
    run = read_run("optimization_result_program")
    run[0]["variables"]["tables"] = -0.0
    found = program_finding(run[0], run)
    assert found.text.startswith("Best found: chairs = 24, and 1 other at 0. The objective is")
    assert found.evidence["variables"] == {"chairs": run[0]["variables"]["chairs"], "tables": -0.0}
    run[0]["variables"]["chairs"] = 0.0
    assert program_finding(run[0], run).text.startswith(
        "Best found: every variable at 0. The objective is"
    )

    def a_third_variable(document: dict[str, Any]) -> None:
        document["variables"].append({"id": "stools", "type": "continuous", "lower": 0})

    run = read_run("optimization_result_program", a_third_variable)
    run[0]["variables"].update({"chairs": 0.0, "stools": 0.0})
    assert program_finding(run[0], run).text.startswith(
        "Best found: tables = 14, and 2 others at 0. The objective is"
    )


def test_a_mathematical_optimization_with_no_tight_constraint() -> None:
    run = read_run("optimization_result_program")
    run[0]["constraints"]["wood"]["tight"] = False
    run[0]["constraints"]["labour"]["tight"] = False
    assert program_finding(run[0], run).text == (
        "Best found: chairs = 24, tables = 14. The objective is 2,200; no constraint is tight."
    )
    run[0]["constraints"]["labour"]["tight"] = True
    assert program_finding(run[0], run).text.endswith("with labour tight.")


def test_a_mathematical_optimization_without_constraints() -> None:
    def no_constraints(document: dict[str, Any]) -> None:
        document["constraints"] = []

    run = read_run("optimization_result_program", no_constraints)
    run[0]["constraints"] = {}
    assert program_finding(run[0], run).text == (
        "Best found: chairs = 24, tables = 14. The objective is 2,200."
    )


@pytest.mark.parametrize(
    ("status", "text"),
    [
        ("infeasible", "No values meet every constraint: the problem is infeasible."),
        (
            "unbounded",
            "The objective can be improved without limit: a bound or a constraint is missing.",
        ),
    ],
)
def test_a_mathematical_optimization_with_no_optimum(status: str, text: str) -> None:
    run = read_run("optimization_result_program")
    run[0].update({"status": status, "objective": None, "variables": {}, "constraints": {}})
    found = program_finding(run[0], run)
    assert (found.severity, found.text) == ("warning", text)
    assert found.evidence == {"status": status}


# --- the finding object and determinism ----------------------------------------------------


def test_same_input_same_findings_in_a_fixed_order() -> None:
    for name in ("unstable_fires", "not_enough_runs_scenarios", "optimization_result_fires"):
        summary, model = read_run(name)
        first = [item.as_dict() for item in find(summary, model)]
        second = [item.as_dict() for item in find(*read_run(name))]
        assert first == second
        assert json.loads(json.dumps(first)) == first


def test_the_order_is_optimization_then_unstable_then_each_scenario() -> None:
    summary, model = read_run("unstable_fires")
    assert rules_of(find(summary, model)) == ["unstable", "bottleneck"]
    summary, model = read_run("not_enough_runs_scenarios")
    unseparated(summary, "till.wait.mean", 40.0)
    found = find(summary, model)
    assert [(item.rule, item.scenario) for item in found] == [
        ("not_enough_runs", "now"),
        ("not_enough_runs", "slower"),
        ("not_enough_runs", "slower"),
    ]
    assert "cannot be told apart" in found[-1].text


def test_findings_do_not_change_their_input() -> None:
    summary, model = read_run("optimization_result_fires")
    before = json.dumps(summary, sort_keys=True)
    find(summary, model)
    assert json.dumps(summary, sort_keys=True) == before


def test_a_finding_is_frozen_and_its_dict_has_spec_4s_keys() -> None:
    summary, model = read_run("idle_capacity_fires")
    found = find(summary, model)[0]
    assert list(found.as_dict()) == [
        "rule",
        "severity",
        "component",
        "scenario",
        "text",
        "evidence",
    ]
    with pytest.raises(AttributeError):
        found.text = "changed"  # type: ignore[misc]
