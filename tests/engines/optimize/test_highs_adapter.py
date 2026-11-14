"""The HiGHS adapter for the ``optimization`` domain (AKS-108).

Spec 1 "Engine adapter interface": the five methods, declared through the ``ithax.engines``
entry point ``highs``, with HiGHS's licence (MIT) and ``in-process`` invocation. Spec 2
"Mathematical optimization in the model file": the ``summary.json`` layout that
``collect`` returns as ``Results.solution``.
"""

import copy
import json
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

import ithax
from ithax.engines.adapter import Capabilities, EngineAdapter, Progress
from ithax.engines.optimize import adapter as adapter_module
from ithax.engines.optimize.adapter import INPUT_FILE, SOLUTION_FILE, HighsAdapter
from ithax.engines.optimize.solver import SolverStopped, solver_version
from ithax.engines.optimize.translate import read_input, write_input
from ithax.engines.registry import installed_adapters, select_adapter
from ithax.model.loading import load_document
from ithax.model.model import Model

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


def load(document: Mapping[str, Any]) -> Model:
    result = load_document(document)
    assert result.issues == (), [issue.as_dict() for issue in result.issues]
    assert result.model is not None
    return result.model


def solved(document: Mapping[str, Any], workdir: Path) -> dict[str, Any]:
    adapter = HighsAdapter()
    adapter.translate(load(document), None, workdir)
    adapter.run(workdir, lambda progress: None, threading.Event(), 1)
    solution = adapter.collect(workdir).solution
    assert solution is not None
    return solution


# --- declaration ------------------------------------------------------------------------------


def test_the_adapter_declares_the_optimization_domain_mit_and_in_process() -> None:
    adapter = HighsAdapter()
    assert isinstance(adapter, EngineAdapter)
    assert adapter.name == "highs"
    assert adapter.version == ithax.__version__
    assert adapter.capabilities() == Capabilities(
        domains=("optimization",),
        component_types={},
        hardware=(),
        parallel_modes=(),
        licence="MIT",
        invocation="in-process",
    )


def test_the_adapter_is_installed_through_its_entry_point() -> None:
    # pip install -e writes the entry points of pyproject.toml into the metadata.
    adapters = installed_adapters()
    assert isinstance(adapters["highs"], HighsAdapter)
    selection = select_adapter("optimization", None)
    assert selection.issues == () and isinstance(selection.adapter, HighsAdapter)
    assert isinstance(select_adapter("optimization", "highs").adapter, HighsAdapter)


def test_validate_adds_no_checks() -> None:
    assert HighsAdapter().validate(load(PRODUCT_MIX)) == []


# --- translate ---------------------------------------------------------------------------------


def test_translate_writes_the_program_with_floats(tmp_path: Path) -> None:
    HighsAdapter().translate(load(PRODUCT_MIX), None, tmp_path)
    written = json.loads((tmp_path / INPUT_FILE).read_text(encoding="utf-8"))
    assert written == {
        "variables": [
            {"id": "chairs", "type": "continuous", "lower": 0.0, "upper": None},
            {"id": "tables", "type": "continuous", "lower": 0.0, "upper": None},
        ],
        "objective": {"sense": "maximize", "linear": {"chairs": 45.0, "tables": 80.0}},
        "constraints": [
            {"id": "wood", "linear": {"chairs": 5.0, "tables": 20.0}, "op": "<=", "rhs": 400.0},
            {"id": "labour", "linear": {"chairs": 10.0, "tables": 15.0}, "op": "<=", "rhs": 450.0},
        ],
    }
    assert all(isinstance(value, float) for value in written["objective"]["linear"].values())


def test_read_input_gives_back_the_program(tmp_path: Path) -> None:
    model = load(PRODUCT_MIX)
    write_input(model, tmp_path)
    assert read_input(tmp_path) == model.program


def test_meta_and_run_do_not_change_the_input(tmp_path: Path) -> None:
    write_input(load(PRODUCT_MIX), tmp_path / "a")
    other = copy.deepcopy(PRODUCT_MIX)
    other["meta"] = {"name": "Renamed", "description": "Another text"}
    other["run"] = {"target": "local", "fidelity": "standard", "engine": "highs"}
    write_input(load(other), tmp_path / "b")
    assert (tmp_path / "a" / INPUT_FILE).read_bytes() == (tmp_path / "b" / INPUT_FILE).read_bytes()


def test_translate_takes_no_experiment(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no experiments"):
        HighsAdapter().translate(load(PRODUCT_MIX), "base", tmp_path)


def test_translate_refuses_a_process_model(tmp_path: Path) -> None:
    coffee = json.loads(
        (Path(__file__).resolve().parents[3] / "examples" / "coffee_shop.json").read_text("utf-8")
    )
    with pytest.raises(ValueError, match="not an optimization model"):
        HighsAdapter().translate(load(coffee), None, tmp_path)


def test_a_number_too_large_for_a_float_stops_translate(tmp_path: Path) -> None:
    # The loader accepts any JSON integer; HiGHS works in floats. The run fails with E190.
    document = copy.deepcopy(PRODUCT_MIX)
    document["constraints"][0]["rhs"] = 10**400
    with pytest.raises(OverflowError):
        HighsAdapter().translate(load(document), None, tmp_path)


# --- run and collect ----------------------------------------------------------------------------


def test_the_product_mix_solution_has_the_spec_2_layout(tmp_path: Path) -> None:
    solution = solved(PRODUCT_MIX, tmp_path)
    assert list(solution) == ["status", "objective", "variables", "constraints"]
    assert solution["status"] == "optimal"
    assert solution["objective"] == pytest.approx(2200, rel=1e-12)
    assert solution["variables"] == pytest.approx({"chairs": 24, "tables": 14}, rel=1e-12)
    assert list(solution["constraints"]) == ["wood", "labour"]
    for item in solution["constraints"].values():
        assert list(item) == ["tight", "slack"]
        assert item["tight"] is True and abs(item["slack"]) <= 1e-6


def test_a_constraint_with_room_is_not_tight(tmp_path: Path) -> None:
    document = copy.deepcopy(PRODUCT_MIX)
    document["constraints"].append(
        {"id": "space", "linear": {"chairs": 1, "tables": 1}, "op": "<=", "rhs": 100}
    )
    solution = solved(document, tmp_path)
    assert solution["constraints"]["space"] == {"tight": False, "slack": pytest.approx(62)}


def test_the_engine_output_also_holds_the_duals_and_the_solver(tmp_path: Path) -> None:
    solved(PRODUCT_MIX, tmp_path)
    output = json.loads((tmp_path / SOLUTION_FILE).read_text(encoding="utf-8"))
    assert output["solver"] == {"name": "HiGHS", "version": solver_version()}
    assert output["duals"] == pytest.approx({"wood": 1, "labour": 4}, rel=1e-12)


def test_an_integer_program_records_no_duals(tmp_path: Path) -> None:
    document = copy.deepcopy(PRODUCT_MIX)
    document["variables"][0]["type"] = "integer"
    solution = solved(document, tmp_path)
    assert solution["status"] == "optimal"
    assert json.loads((tmp_path / SOLUTION_FILE).read_text(encoding="utf-8"))["duals"] is None


def test_an_infeasible_model(tmp_path: Path) -> None:
    document = copy.deepcopy(PRODUCT_MIX)
    document["constraints"].append(
        {"id": "demand", "linear": {"chairs": 1}, "op": ">=", "rhs": 100}
    )
    assert solved(document, tmp_path) == {
        "status": "infeasible",
        "objective": None,
        "variables": {},
        "constraints": {},
    }


def test_an_unbounded_model(tmp_path: Path) -> None:
    document = copy.deepcopy(PRODUCT_MIX)
    document["constraints"] = [document["constraints"][0]]
    document["constraints"][0]["linear"] = {"chairs": 5, "tables": -20}
    assert solved(document, tmp_path) == {
        "status": "unbounded",
        "objective": None,
        "variables": {},
        "constraints": {},
    }


def test_run_reports_progress_from_0_to_1(tmp_path: Path) -> None:
    adapter = HighsAdapter()
    adapter.translate(load(PRODUCT_MIX), None, tmp_path)
    reports: list[Progress] = []
    adapter.run(tmp_path, reports.append, threading.Event(), 4)
    assert [report.fraction for report in reports] == [0.0, 1.0]
    assert reports[0].message == "Solving with HiGHS"
    assert reports[1].message == "Solved: optimal"


def test_a_cancel_before_the_solve_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = HighsAdapter()
    adapter.translate(load(PRODUCT_MIX), None, tmp_path)

    def no_solve(*args: object, **kwargs: object) -> None:
        raise AssertionError("solved after a cancel")

    monkeypatch.setattr(adapter_module, "solve", no_solve)
    cancel = threading.Event()
    cancel.set()
    adapter.run(tmp_path, lambda progress: None, cancel, 1)
    assert not (tmp_path / SOLUTION_FILE).exists()


def test_a_cancel_during_the_solve_writes_nothing(tmp_path: Path) -> None:
    # The solve cannot be interrupted (engine gap); a cancel during it is honoured after.
    adapter = HighsAdapter()
    adapter.translate(load(PRODUCT_MIX), None, tmp_path)
    cancel = threading.Event()
    adapter.run(tmp_path, lambda progress: cancel.set(), cancel, 1)
    assert not (tmp_path / SOLUTION_FILE).exists()


def test_a_rerun_removes_the_old_solution_first(tmp_path: Path) -> None:
    solved(PRODUCT_MIX, tmp_path)
    cancel = threading.Event()
    HighsAdapter().run(tmp_path, lambda progress: cancel.set(), cancel, 1)
    assert not (tmp_path / SOLUTION_FILE).exists()


def test_a_solver_that_stops_raises_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = HighsAdapter()
    adapter.translate(load(PRODUCT_MIX), None, tmp_path)

    def stopped(*args: object, **kwargs: object) -> None:
        raise SolverStopped("iterationLimit")

    monkeypatch.setattr(adapter_module, "solve", stopped)
    with pytest.raises(SolverStopped, match="iterationLimit"):
        adapter.run(tmp_path, lambda progress: None, threading.Event(), 1)
    assert not (tmp_path / SOLUTION_FILE).exists()


def test_collect_without_a_solution_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        HighsAdapter().collect(tmp_path)


def test_collect_returns_no_tables_and_no_warnings(tmp_path: Path) -> None:
    solved(PRODUCT_MIX, tmp_path)
    results = HighsAdapter().collect(tmp_path)
    assert results.tables == {} and results.warnings == []


# --- an indexed model (AKS-123) ----------------------------------------------------------------

TRANSPORT_FILE = Path(__file__).resolve().parents[3] / "benchmarks" / "transport" / "model.json"


def transport() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(TRANSPORT_FILE.read_text(encoding="utf-8"))
    return loaded


def test_translate_writes_an_indexed_model_expanded_into_the_flat_layout(tmp_path: Path) -> None:
    """Spec 2 "Indexed problems": the adapter sees the flat layout, so its input file holds
    the twelve routes and the seven limits by their expanded names; no sets or tables."""
    write_input(load(transport()), tmp_path)
    document = json.loads((tmp_path / INPUT_FILE).read_text(encoding="utf-8"))
    assert set(document) == {"variables", "objective", "constraints"}
    assert [item["id"] for item in document["variables"]][:2] == [
        "ship[north,city]",
        "ship[north,harbour]",
    ]
    assert len(document["variables"]) == 12
    assert document["constraints"][0] == {
        "id": "supply[north]",
        "linear": {
            "ship[north,city]": 1.0,
            "ship[north,harbour]": 1.0,
            "ship[north,park]": 1.0,
            "ship[north,market]": 1.0,
        },
        "op": "<=",
        "rhs": 300.0,
    }
    assert read_input(tmp_path) == load(transport()).program


def test_an_indexed_model_solves_to_the_benchmark_plan_by_expanded_names(tmp_path: Path) -> None:
    solution = solved(transport(), tmp_path)
    assert solution["status"] == "optimal"
    assert solution["objective"] == pytest.approx(2690)
    assert solution["variables"]["ship[north,city]"] == pytest.approx(180)
    assert solution["variables"]["ship[centre,harbour]"] == pytest.approx(200)
    assert solution["constraints"]["supply[north]"] == {"tight": False, "slack": pytest.approx(30)}
    assert solution["constraints"]["supply[centre]"]["tight"]
