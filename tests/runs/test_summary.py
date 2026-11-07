"""Building ``summary.json`` (spec 1 "Run folder and results"; AKS-102):
``lcsim.runs.summary``."""

import copy
import json
import math
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from lcsim.engines.adapter import Results
from lcsim.model.issues import Issue
from lcsim.model.loading import load_document
from lcsim.model.model import Model
from lcsim.runs.statistics import across_replications, paired_differences
from lcsim.runs.summary import build_summary, fidelity_label, format_length

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
NAN = math.nan


def coffee_shop(**experiment: Any) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (EXAMPLES / "coffee_shop.json").read_text(encoding="utf-8")
    )
    document["experiments"][0].update(experiment)
    return document


def load(document: dict[str, Any]) -> Model:
    result = load_document(document)
    assert result.errors == (), [issue.code for issue in result.errors]
    assert result.model is not None
    return result.model


def replications(rows: list[tuple[str, int, str, float, str]]) -> pa.Table:
    names = ["scenario", "replication", "metric", "value", "unit"]
    return pa.table({name: [row[i] for row in rows] for i, name in enumerate(names)})


def timeseries(rows: list[tuple[str, int, str, float, float]]) -> pa.Table:
    names = ["scenario", "replication", "metric", "time_s", "value"]
    columns: dict[str, list[Any]] = {name: [row[i] for row in rows] for i, name in enumerate(names)}
    columns["unit"] = ["1"] * len(rows)
    return pa.table(columns)


def rising(scenario: str, reps: int = 2) -> list[tuple[str, int, str, float, float]]:
    """A ``model.wip`` series that doubles between the halves in every replication, with
    a little spread, observed from 10 h."""
    return [
        (scenario, rep, "model.wip", 36000.0 + 3600.0 * k, (1.0 if k < 2 else 2.0) + rep / 100)
        for rep in range(reps)
        for k in range(4)
    ]


# ---------------------------------------------------------------------------------------
# The fidelity label


@pytest.mark.parametrize(
    ("seconds", "text"),
    [
        (720000.0, "200 h"),
        (360000.0, "100 h"),
        (3600000.0, "1000 h"),
        (172800.0, "2 d"),
        (120.0, "2 min"),
        (90.0, "90 s"),
        (1.5, "1.5 s"),
        (29.0, "29 s"),
    ],
)
def test_format_length_takes_the_largest_whole_unit(seconds: float, text: str) -> None:
    assert format_length(seconds) == text


def test_the_fidelity_label_of_spec_1() -> None:
    assert (
        fidelity_label("standard", 30, 720000.0, 0.95)
        == "Standard: 30 replications of 200 h, 95% confidence"
    )
    assert (
        fidelity_label("standard", 2, 172800.0, 0.975)
        == "Standard: 2 replications of 2 d, 97.5% confidence"
    )
    assert fidelity_label("standard", 10, 90.0, 0.99).endswith("90 s, 99% confidence")


# ---------------------------------------------------------------------------------------
# A process run

ROWS = [
    ("default", 0, "till.wait.mean", 250.0, "s"),
    ("default", 0, "till.utilization", 0.74, "1"),
    ("default", 1, "till.wait.mean", NAN, "s"),
    ("default", 1, "till.utilization", 0.76, "1"),
    ("default", 2, "till.wait.mean", 290.0, "s"),
    ("default", 2, "till.utilization", 0.75, "1"),
]


def test_a_process_summary_has_the_spec_1_layout() -> None:
    model = load(coffee_shop(replications=3))
    table = replications(ROWS)
    results = Results(tables={"replications": table}, warnings=[])
    summary = build_summary(model, "base", results)
    assert list(summary) == [
        "model",
        "experiment",
        "fidelity",
        "fidelity_label",
        "replications",
        "confidence",
        "scenarios",
        "differences",
        "warnings",
    ]
    assert summary["model"] == "Coffee shop"
    assert summary["experiment"] == "base"
    assert summary["fidelity"] == "standard"
    assert summary["fidelity_label"] == "Standard: 3 replications of 200 h, 95% confidence"
    assert summary["replications"] == 3
    assert summary["confidence"] == 0.95
    assert list(summary["scenarios"]) == ["default"]
    default = summary["scenarios"]["default"]
    assert list(default) == ["set", "metrics"]
    assert default["set"] == {}
    expected = across_replications(table, ["default"], 0.95)["default"]
    assert default["metrics"] == {metric: item.as_dict() for metric, item in expected.items()}
    assert default["metrics"]["till.wait.mean"]["n"] == 2
    assert summary["differences"] == []
    assert summary["warnings"] == []
    # Valid JSON: no NaN anywhere.
    json.dumps(summary, allow_nan=False)


def test_scenarios_their_sets_in_si_and_differences() -> None:
    document = coffee_shop(
        replications=3,
        scenarios=[{"id": "one", "set": {"tills": 1}}, {"id": "two", "set": {"tills": 2}}],
    )
    document["parameters"]["walk"] = {"value": "1 min", "type": "quantity"}
    document["experiments"][0]["scenarios"][1]["set"]["walk"] = "2 min"
    model = load(document)
    # Scenario two waits 200 s less in every replication; utilization is unchanged.
    rows = [
        (scenario, rep, metric, value + (shift if unit == "s" else 0.0), unit)
        for scenario, shift in (("one", 0.0), ("two", -200.0))
        for _, rep, metric, value, unit in ROWS
    ]
    table = replications(rows)
    summary = build_summary(model, "base", Results(tables={"replications": table}, warnings=[]))
    assert list(summary["scenarios"]) == ["one", "two"]
    assert summary["scenarios"]["one"]["set"] == {"tills": 1}
    assert summary["scenarios"]["two"]["set"] == {"tills": 2, "walk": 120.0}
    expected = paired_differences(table, ["one", "two"], 0.95)
    assert summary["differences"] == [pair.as_dict() for pair in expected]
    wait = summary["differences"][0]["metrics"]["till.wait.mean"]
    assert wait == {"mean": -200.0, "half_width": 0.0, "unit": "s", "n": 2, "separated": True}


def test_w210_follows_the_given_and_the_adapter_warnings() -> None:
    model = load(coffee_shop(replications=2))
    given = Issue("W201", "till", "/components/1", "Given.", "Hint.")
    from_adapter = Issue("W202", "till", "/components/1", "Adapter.", "Hint.")
    results = Results(
        tables={
            "replications": replications(ROWS[:4]),
            "timeseries": timeseries(rising("default")),
        },
        warnings=[from_adapter],
    )
    summary = build_summary(model, "base", results, [given])
    codes = [warning["code"] for warning in summary["warnings"]]
    assert codes == ["W201", "W202", "W210"]
    w210 = summary["warnings"][2]
    assert w210["path"] == "/experiments/0/warmup"
    # d-bar 1 on a mean of 1.505: 66%.
    assert "model.wip in scenario default changed by 66% of its mean" in w210["message"]


def test_samples_before_warmup_are_not_checked() -> None:
    # The rising series lies before a 20 h warm-up, so nothing is observed.
    model = load(coffee_shop(replications=2, warmup="20 h"))
    results = Results(tables={"timeseries": timeseries(rising("default"))}, warnings=[])
    assert build_summary(model, "base", results)["warnings"] == []


def test_the_experiment_index_names_the_w210_path() -> None:
    document = coffee_shop(replications=2)
    second = copy.deepcopy(document["experiments"][0])
    second["id"] = "later"
    document["experiments"].append(second)
    model = load(document)
    results = Results(tables={"timeseries": timeseries(rising("default"))}, warnings=[])
    summary = build_summary(model, "later", results)
    assert summary["experiment"] == "later"
    assert summary["warnings"][0]["path"] == "/experiments/1/warmup"


def test_tables_left_out_give_empty_metrics_and_no_check() -> None:
    model = load(coffee_shop(replications=2))
    summary = build_summary(model, "base", Results(tables={}, warnings=[]))
    assert summary["scenarios"] == {"default": {"set": {}, "metrics": {}}}
    assert summary["warnings"] == []


def test_a_search_experiment_is_not_checked_for_warmup() -> None:
    """Spec 2: a search's candidates are decided at M5."""
    document = coffee_shop(replications=2, search={"objective": "wait"})
    document["objectives"] = [{"id": "wait", "metric": "till.wait.mean", "sense": "minimize"}]
    model = load(document)
    results = Results(tables={"timeseries": timeseries(rising("default"))}, warnings=[])
    assert build_summary(model, "base", results)["warnings"] == []


def test_a_process_summary_needs_a_known_experiment() -> None:
    model = load(coffee_shop())
    results = Results(tables={}, warnings=[])
    with pytest.raises(ValueError, match="no experiment 'nope'"):
        build_summary(model, "nope", results)
    with pytest.raises(ValueError, match="no experiment None"):
        build_summary(model, None, results)


def test_a_fidelity_that_is_not_text_is_refused() -> None:
    document = coffee_shop()
    document["run"]["fidelity"] = 5
    model = load(document)
    with pytest.raises(ValueError, match="fidelity 5"):
        build_summary(model, "base", Results(tables={}, warnings=[]))


# ---------------------------------------------------------------------------------------
# An optimization run


def test_an_optimization_summary_is_the_solution_with_label_and_warnings() -> None:
    model = load(
        {
            "format_version": "0.1",
            "meta": {"name": "Product mix"},
            "domain": "optimization",
            "variables": [
                {"id": "chairs", "type": "continuous", "lower": 0},
                {"id": "tables", "type": "continuous", "lower": 0},
            ],
            "objective": {"sense": "maximize", "linear": {"chairs": 45, "tables": 80}},
            "constraints": [
                {"id": "wood", "linear": {"chairs": 5, "tables": 20}, "op": "<=", "rhs": 400},
            ],
        }
    )
    solution = {
        "status": "optimal",
        "objective": 2200,
        "variables": {"chairs": 24, "tables": 14},
        "constraints": {"wood": {"tight": True, "slack": 0}},
    }
    warning = Issue("W201", None, "", "Adapter.", "Hint.")
    summary = build_summary(model, None, Results(tables={}, warnings=[warning], solution=solution))
    assert summary == {
        "model": "Product mix",
        **solution,
        "fidelity_label": "Standard",
        "warnings": [warning.as_dict()],
    }
    assert list(summary) == [
        "model",
        "status",
        "objective",
        "variables",
        "constraints",
        "fidelity_label",
        "warnings",
    ]
