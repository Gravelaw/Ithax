"""The engine adapter interface of spec 1 "Engine adapter interface" (AKS-97).

``CancelToken`` and ``EngineAdapter`` are protocols; ``Capabilities``, ``Progress`` and
``Results`` are the values that cross the interface. Spec 1 "Engine contract" and "Engine
licence rule" name what ``Capabilities`` lists; "Division of labour" names the parallel
modes and the ``Results`` fields.
"""

import multiprocessing
import threading
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType

import pyarrow as pa
import pytest

from ithax.engines.adapter import (
    INVOCATIONS,
    PARALLEL_MODES,
    CancelToken,
    Capabilities,
    EngineAdapter,
    Progress,
    Results,
    Table,
)
from ithax.engines.process.adapter import ProcessAdapter
from ithax.model.catalogue import PROCESS_TYPES
from ithax.model.issues import Issue


def capabilities(**changes: object) -> Capabilities:
    fields: dict[str, object] = {
        "domains": ("process",),
        "component_types": {"server": PROCESS_TYPES["server"]},
        "hardware": (),
        "parallel_modes": ("replications",),
        "licence": "MIT",
        "invocation": "in-process",
    }
    fields.update(changes)
    return Capabilities(**fields)  # type: ignore[arg-type]


# --- CancelToken --------------------------------------------------------------------------


def test_the_local_target_token_is_a_cancel_token() -> None:
    # Spec 1: the local target supplies a multiprocessing.Event.
    event = multiprocessing.Event()
    assert isinstance(event, CancelToken)
    assert event.is_set() is False
    event.set()
    assert event.is_set() is True
    assert isinstance(threading.Event(), CancelToken)


def test_an_object_without_is_set_is_not_a_cancel_token() -> None:
    assert not isinstance(object(), CancelToken)


# --- EngineAdapter ------------------------------------------------------------------------


def test_the_process_adapter_provides_the_protocol() -> None:
    assert isinstance(ProcessAdapter(), EngineAdapter)


def test_a_class_missing_a_method_is_not_an_adapter() -> None:
    class NoCollect:
        name = "partial"
        version = "1"

        def capabilities(self) -> Capabilities:
            return capabilities()

        def validate(self, model: object) -> list[Issue]:
            return []

        def translate(self, model: object, experiment_id: str | None, workdir: Path) -> None:
            return None

        def run(self, workdir: Path, on_progress: object, cancel: object, workers: int) -> None:
            return None

    assert not isinstance(NoCollect(), EngineAdapter)


# --- Capabilities -------------------------------------------------------------------------


def test_the_parallel_modes_and_invocations_are_the_spec_words() -> None:
    assert PARALLEL_MODES == ("replications", "threads", "processes", "gpu")
    assert INVOCATIONS == ("process", "in-process")


def test_capabilities_keep_every_field() -> None:
    made = capabilities(hardware=("gpu",), parallel_modes=("replications", "gpu"))
    assert made.domains == ("process",)
    assert made.component_types == {"server": PROCESS_TYPES["server"]}
    assert made.hardware == ("gpu",)
    assert made.parallel_modes == ("replications", "gpu")
    assert made.licence == "MIT"
    assert made.invocation == "in-process"


def test_capabilities_hold_a_read_only_copy_of_the_component_types() -> None:
    types = {"server": PROCESS_TYPES["server"]}
    made = capabilities(component_types=types)
    types["sink"] = PROCESS_TYPES["sink"]
    assert list(made.component_types) == ["server"]
    assert isinstance(made.component_types, MappingProxyType)
    with pytest.raises(TypeError):
        made.component_types["sink"] = PROCESS_TYPES["sink"]  # type: ignore[index]


def test_capabilities_are_frozen_and_compare_by_value() -> None:
    made = capabilities()
    assert made == capabilities()
    assert made != capabilities(licence="BSD-3-Clause")
    with pytest.raises(FrozenInstanceError):
        made.licence = "GPL-3.0-only"  # type: ignore[misc]


@pytest.mark.parametrize("modes", [("cluster",), ("replications", "fibres")])
def test_an_unknown_parallel_mode_is_refused(modes: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="parallel mode"):
        capabilities(parallel_modes=modes)


@pytest.mark.parametrize("invocation", ["subprocess", "", "IN-PROCESS"])
def test_an_unknown_invocation_is_refused(invocation: str) -> None:
    with pytest.raises(ValueError, match="invocation"):
        capabilities(invocation=invocation)


def test_a_licence_is_required() -> None:
    with pytest.raises(ValueError, match="licence"):
        capabilities(licence="")


# --- Progress -----------------------------------------------------------------------------


def test_progress_has_fraction_message_and_optional_metrics() -> None:
    plain = Progress(0.25, "Scenario 1 of 2, replication 12 of 30")
    assert (plain.fraction, plain.message, plain.metrics) == (
        0.25,
        "Scenario 1 of 2, replication 12 of 30",
        None,
    )
    live = Progress(fraction=1, message="Done", metrics={"till.wait.mean": 273.3})
    assert live.metrics == {"till.wait.mean": 273.3}


@pytest.mark.parametrize("fraction", [0.0, 0.5, 1.0])
def test_progress_takes_a_fraction_from_0_to_1(fraction: float) -> None:
    assert Progress(fraction, "x").fraction == fraction


@pytest.mark.parametrize("fraction", [-0.01, 1.01, float("nan"), float("inf")])
def test_progress_refuses_a_fraction_outside_0_to_1(fraction: float) -> None:
    with pytest.raises(ValueError, match="fraction"):
        Progress(fraction, "x")


# --- Results ------------------------------------------------------------------------------


def test_table_is_the_pyarrow_table() -> None:
    assert Table is pa.Table


def test_results_hold_tables_warnings_and_no_solution_by_default() -> None:
    table = pa.table(
        {
            "scenario": ["default"],
            "replication": pa.array([0], pa.int64()),
            "metric": ["till.wait.mean"],
            "value": pa.array([273.3], pa.float64()),
            "unit": ["s"],
        }
    )
    warning = Issue("W210", None, "", "Results were still changing.", "Lengthen 'warmup'.")
    results = Results({"replications": table}, [warning])
    assert results.tables["replications"].equals(table)
    assert results.warnings == [warning]
    assert results.solution is None


def test_results_carry_an_optimization_solution() -> None:
    solution = {"status": "optimal", "objective": 2200.0, "variables": {}, "constraints": {}}
    results = Results(tables={}, warnings=[], solution=solution)
    assert results.solution == solution
