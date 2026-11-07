"""Running an adapter through ``validate``, ``translate``, ``run`` and ``collect`` and
building the summary (spec 1 "Division of labour"; AKS-102): ``lcsim.runs.manager``.

The run folder, manifest, job states and worker are AKS-103's; this checks only the
manager's own path, in a given ``workdir``.
"""

import json
import threading
from pathlib import Path
from typing import Any

import pytest

from lcsim.engines.adapter import Progress
from lcsim.engines.process.adapter import ProcessAdapter
from lcsim.model.issues import Issue
from lcsim.model.loading import load_document
from lcsim.model.model import Model
from lcsim.runs.manager import (
    OFFERED_FIDELITIES,
    RunOutcome,
    fidelity_issues,
    run_experiment,
)
from lcsim.runs.summary import build_summary

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def coffee_shop(**changes: Any) -> dict[str, Any]:
    """The coffee shop, shortened to 5 h with 30 min of warm-up and 2 replications."""
    document: dict[str, Any] = json.loads(
        (EXAMPLES / "coffee_shop.json").read_text(encoding="utf-8")
    )
    document["experiments"][0].update({"length": "5 h", "warmup": "30 min", "replications": 2})
    document["experiments"][0].update(changes)
    return document


def load(document: dict[str, Any]) -> Model:
    result = load_document(document)
    assert result.errors == ()
    assert result.model is not None
    return result.model


class WarningAdapter(ProcessAdapter):
    """The process adapter with engine-specific issues from ``validate``."""

    def __init__(self, *issues: Issue) -> None:
        self.issues = list(issues)

    def validate(self, model: Model) -> list[Issue]:
        return list(self.issues)


def test_a_run_returns_its_results_and_summary(tmp_path: Path) -> None:
    model = load(coffee_shop())
    reports: list[Progress] = []
    outcome = run_experiment(
        ProcessAdapter(), model, "base", tmp_path / "engine", on_progress=reports.append
    )
    assert outcome.state == "done" and outcome.issues == ()
    assert outcome.results is not None and outcome.summary is not None
    assert list(outcome.results.tables) == ["replications", "timeseries"]
    assert outcome.summary == build_summary(model, "base", outcome.results)
    assert outcome.summary["fidelity_label"] == "Standard: 2 replications of 5 h, 95% confidence"
    assert outcome.summary["scenarios"]["default"]["metrics"]["till.utilization"]["n"] == 2
    assert [report.fraction for report in reports] == [0.5, 1.0]
    # The adapter wrote only inside the workdir it was given.
    assert sorted(path.name for path in tmp_path.iterdir()) == ["engine"]


def test_the_defaults_run_in_this_process(tmp_path: Path) -> None:
    outcome = run_experiment(ProcessAdapter(), load(coffee_shop()), "base", tmp_path)
    assert outcome.state == "done"


def test_validate_warnings_come_first_in_the_summary(tmp_path: Path) -> None:
    warning = Issue("W300", "till", "/components/1", "An engine warning.", "A hint.")
    model = load(coffee_shop())
    outcome = run_experiment(WarningAdapter(warning), model, "base", tmp_path)
    assert outcome.state == "done"
    assert outcome.issues == (warning,)
    assert outcome.summary is not None
    assert outcome.summary["warnings"][0] == warning.as_dict()


def test_validate_errors_refuse_the_run(tmp_path: Path) -> None:
    error = Issue("E300", "till", "/components/1", "The engine cannot run this.", "A hint.")
    warning = Issue("W300", "till", "/components/1", "An engine warning.", "A hint.")
    outcome = run_experiment(WarningAdapter(warning, error), load(coffee_shop()), "base", tmp_path)
    assert outcome == RunOutcome("refused", (warning, error), None, None)
    assert not any(tmp_path.iterdir())


def test_a_fidelity_not_offered_is_e173(tmp_path: Path) -> None:
    assert OFFERED_FIDELITIES == ("standard",)
    document = coffee_shop()
    document["run"]["fidelity"] = "sketch"
    model = load(document)
    issues = fidelity_issues(model)
    assert [issue.as_dict() for issue in issues] == [
        {
            "code": "E173",
            "severity": "error",
            "component": None,
            "path": "/run/fidelity",
            "message": 'The fidelity "sketch" is not offered by this engine; Phase 1 engines '
            'offer "standard" only.',
            "hint": "Set 'fidelity' in 'run' to \"standard\".",
        }
    ]
    outcome = run_experiment(ProcessAdapter(), model, "base", tmp_path)
    assert outcome == RunOutcome("refused", tuple(issues), None, None)
    assert fidelity_issues(load(coffee_shop())) == []


def test_a_cancelled_run_is_not_collected(tmp_path: Path) -> None:
    cancel = threading.Event()
    cancel.set()
    outcome = run_experiment(ProcessAdapter(), load(coffee_shop()), "base", tmp_path, cancel=cancel)
    assert outcome == RunOutcome("cancelled", (), None, None)


def test_a_search_experiment_waits_for_m5(tmp_path: Path) -> None:
    document = coffee_shop(search={"objective": "wait"})
    document["objectives"] = [{"id": "wait", "metric": "till.wait.mean", "sense": "minimize"}]
    with pytest.raises(NotImplementedError, match="M5"):
        run_experiment(ProcessAdapter(), load(document), "base", tmp_path)


def test_an_unknown_experiment_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no experiment 'nope'"):
        run_experiment(ProcessAdapter(), load(coffee_shop()), "nope", tmp_path)
