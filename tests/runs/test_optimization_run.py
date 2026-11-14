"""An optimization model through the experiment manager and the ``local`` run target
(AKS-108).

Spec 3 ``POST .../runs``: an ``optimization`` model has no experiments and is started
without an ``experiment_id``. The run folder and manifest rules of spec 1 apply unchanged;
``summary.json`` is spec 1 "Run folder and results" ("Optimization"): ``model``, the
adapter's ``solution``, ``fidelity_label`` and ``warnings``.
"""

import copy
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from dummy_adapters import IterationLimitedAdapter

import ithax
from ithax.engines.optimize.adapter import HighsAdapter
from ithax.model.loading import load_document
from ithax.model.model import Model
from ithax.runs.manager import RunOutcome, run_experiment
from ithax.runs.manifest import MANIFEST_KEYS, read_manifest
from ithax.runs.targets import LocalTarget, RunRefused

PRODUCT_MIX: dict[str, Any] = {
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
        {"id": "labour", "linear": {"chairs": 10, "tables": 15}, "op": "<=", "rhs": 450},
    ],
}
COFFEE_SHOP = Path(__file__).resolve().parents[2] / "examples" / "coffee_shop.json"


def file_bytes(document: Mapping[str, Any]) -> bytes:
    return (json.dumps(document, indent=3) + " ").encode("utf-8")


def load(document: Mapping[str, Any]) -> Model:
    result = load_document(document)
    assert result.issues == ()
    assert result.model is not None
    return result.model


def tree(folder: Path) -> list[str]:
    return sorted(str(path.relative_to(folder)) for path in folder.rglob("*"))


def summary_of(folder: Path) -> dict[str, Any]:
    summary: dict[str, Any] = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    return summary


# --- the experiment manager ------------------------------------------------------------------


def test_the_manager_runs_an_optimization_model_without_an_experiment(tmp_path: Path) -> None:
    outcome = run_experiment(HighsAdapter(), load(PRODUCT_MIX), None, tmp_path)
    assert outcome.state == "done" and outcome.issues == ()
    assert outcome.summary is not None
    assert list(outcome.summary) == [
        "model",
        "status",
        "objective",
        "variables",
        "constraints",
        "fidelity_label",
        "warnings",
    ]
    assert outcome.summary["model"] == "Product mix"
    assert outcome.summary["status"] == "optimal"
    assert outcome.summary["objective"] == pytest.approx(2200, rel=1e-12)
    assert outcome.summary["fidelity_label"] == "Standard"
    assert outcome.summary["warnings"] == []


def test_the_manager_refuses_an_experiment_id_for_an_optimization_model(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="has no experiments, but 'base' was given"):
        run_experiment(HighsAdapter(), load(PRODUCT_MIX), "base", tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_the_manager_needs_an_experiment_id_for_a_process_model(tmp_path: Path) -> None:
    from ithax.engines.process.adapter import ProcessAdapter

    coffee = json.loads(COFFEE_SHOP.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="none was given"):
        run_experiment(ProcessAdapter(), load(coffee), None, tmp_path)


def test_the_manager_refuses_an_unoffered_fidelity(tmp_path: Path) -> None:
    document = copy.deepcopy(PRODUCT_MIX)
    document["run"] = {"target": "local", "fidelity": "sketch"}
    outcome = run_experiment(HighsAdapter(), load(document), None, tmp_path)
    assert outcome.state == "refused"
    assert [issue.code for issue in outcome.issues] == ["E173"]
    assert outcome == RunOutcome("refused", outcome.issues, None, None)


# --- the local target ------------------------------------------------------------------------


def test_a_local_run_of_the_product_mix_writes_the_full_run_folder(tmp_path: Path) -> None:
    model_file = file_bytes(PRODUCT_MIX)
    run = LocalTarget(tmp_path / "runs").create(model_file)
    assert run.state == "queued"
    assert run.execute() == "done"
    folder = run.folder
    assert tree(folder) == [
        "engine",
        "engine/input.json",
        "engine/output",
        "engine/output/solution.json",
        "log.txt",
        "manifest.json",
        "model.json",
        "summary.json",
    ]
    assert (folder / "model.json").read_bytes() == model_file
    manifest = read_manifest(folder)
    assert list(manifest) == list(MANIFEST_KEYS)
    assert manifest["state"] == "done" and manifest["fraction"] == 1.0
    assert manifest["experiment_id"] is None
    assert manifest["scenario_ids"] == []
    assert manifest["seed"] is None
    assert manifest["engine"] == {"name": "highs", "version": ithax.__version__}
    assert manifest["target"] == "local" and manifest["client"] == "script"
    summary = summary_of(folder)
    assert summary["model"] == "Product mix"
    assert summary["status"] == "optimal"
    assert summary["objective"] == pytest.approx(2200, rel=1e-12)
    assert summary["variables"] == pytest.approx({"chairs": 24, "tables": 14}, rel=1e-12)
    assert {name: item["tight"] for name, item in summary["constraints"].items()} == {
        "wood": True,
        "labour": True,
    }
    assert summary["fidelity_label"] == "Standard" and summary["warnings"] == []


@pytest.mark.parametrize(
    ("change", "status"),
    [
        ({"id": "demand", "linear": {"chairs": 1}, "op": ">=", "rhs": 100}, "infeasible"),
        (None, "unbounded"),
    ],
)
def test_infeasible_and_unbounded_runs_are_done_with_their_status(
    tmp_path: Path, change: dict[str, Any] | None, status: str
) -> None:
    document = copy.deepcopy(PRODUCT_MIX)
    if change is None:
        document["constraints"] = [
            {"id": "wood", "linear": {"chairs": 5, "tables": -20}, "op": "<=", "rhs": 400}
        ]
    else:
        document["constraints"].append(change)
    run = LocalTarget(tmp_path / "runs").create(file_bytes(document))
    assert run.execute() == "done"
    assert summary_of(run.folder) == {
        "model": "Product mix",
        "status": status,
        "objective": None,
        "variables": {},
        "constraints": {},
        "fidelity_label": "Standard",
        "warnings": [],
    }


def test_a_repeat_gives_an_identical_summary(tmp_path: Path) -> None:
    local = LocalTarget(tmp_path / "runs")
    first = local.create(file_bytes(PRODUCT_MIX))
    second = local.create(file_bytes(PRODUCT_MIX))
    assert first.execute() == "done" and second.execute() == "done"
    assert summary_of(first.folder) == summary_of(second.folder)
    assert (first.folder / "engine" / "output" / "solution.json").read_bytes() == (
        second.folder / "engine" / "output" / "solution.json"
    ).read_bytes()


def test_an_experiment_id_for_an_optimization_model_creates_nothing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="has no experiments"):
        LocalTarget(tmp_path / "runs").create(file_bytes(PRODUCT_MIX), "base")
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize(
    ("change", "code", "path"),
    [
        (
            {"run": {"target": "local", "fidelity": "standard", "engine": "glpk"}},
            "E102",
            "/run/engine",
        ),
        ({"run": {"target": "local", "fidelity": "sketch"}}, "E173", "/run/fidelity"),
        ({"run": {"target": "cluster", "fidelity": "standard"}}, "E172", "/run/target"),
        (
            {"objective": {"sense": "maximize", "linear": {"desks": 1}}},
            "E175",
            "/objective/linear/desks",
        ),
    ],
)
def test_a_refused_optimization_run_creates_nothing(
    tmp_path: Path, change: dict[str, Any], code: str, path: str
) -> None:
    document = {**copy.deepcopy(PRODUCT_MIX), **change}
    with pytest.raises(RunRefused) as refused:
        LocalTarget(tmp_path / "runs").create(file_bytes(document))
    assert [(issue.code, issue.path) for issue in refused.value.issues] == [(code, path)]
    assert not (tmp_path / "runs").exists()


def test_a_solver_that_stops_fails_the_run_with_e190(tmp_path: Path) -> None:
    adapter = IterationLimitedAdapter()
    run = LocalTarget(tmp_path / "runs", adapters={"highs": adapter}).create(
        file_bytes(PRODUCT_MIX)
    )
    assert run.execute() == "failed"
    manifest = read_manifest(run.folder)
    assert manifest["error"]["code"] == "E190"
    assert manifest["error"]["message"] == (
        "The engine 'highs' stopped with an error, so the run failed."
    )
    log = (run.folder / "log.txt").read_text(encoding="utf-8")
    assert "HiGHS ended with the termination condition iterationLimit" in log
    assert not (run.folder / "summary.json").exists()
