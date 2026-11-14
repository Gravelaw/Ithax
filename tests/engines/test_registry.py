"""Engine discovery and selection (AKS-97).

Spec 1 "Engine contract" (v0.4 and AKS-97): entry points in group ``ithax.engines`` are
listed without importing them, then each is loaded inside a guard; one that fails is left
out and logged, never fatal; two with the same name are both left out and logged; the
entry-point name equals the class ``name``. Spec 1 "Top-level keys": the adapter for a
``domain`` and ``run.engine``, with E102 at ``/domain`` or ``/run/engine``.

Discovery is tested with stand-in entry points: ``entry_points`` in the registry module is
replaced, so no package is installed for a test. One test reads the real installed
metadata, which ``pip install -e`` writes from ``pyproject.toml``.
"""

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from importlib.metadata import EntryPoint, entry_points
from pathlib import Path

import pytest

from ithax.engines import registry
from ithax.engines.adapter import Capabilities, EngineAdapter, Progress, Results
from ithax.engines.process.adapter import ProcessAdapter
from ithax.engines.registry import (
    ENTRY_POINT_GROUP,
    Selection,
    installed_adapters,
    installed_engines,
    load_adapters,
    select_adapter,
)
from ithax.model.catalogue import PROCESS_TYPES
from ithax.model.issues import Issue
from ithax.model.validation import InstalledEngine

PROCESS_CLASS = "ithax.engines.process.adapter:ProcessAdapter"


class DummyAdapter:
    """A minimal adapter; subclasses set ``name`` and ``domains``."""

    name = "dummy"
    version = "1.0"
    domains: tuple[str, ...] = ("process",)

    def capabilities(self) -> Capabilities:
        return Capabilities(
            domains=self.domains,
            component_types={},
            hardware=(),
            parallel_modes=(),
            licence="MIT",
            invocation="process",
        )

    def validate(self, model: object) -> list[Issue]:
        return []

    def translate(self, model: object, experiment_id: str | None, workdir: Path) -> None:
        return None

    def run(
        self,
        workdir: Path,
        on_progress: Callable[[Progress], None],
        cancel: object,
        workers: int,
    ) -> None:
        return None

    def collect(self, workdir: Path) -> Results:
        return Results({}, [])


class SalabimAdapter(DummyAdapter):
    name = "salabim"


class HighsAdapter(DummyAdapter):
    name = "highs"
    domains = ("optimization",)


@dataclass
class FakeEntryPoint:
    """An entry point whose ``load`` returns ``target``, or raises it; loads are counted."""

    name: str
    target: object
    value: str = "fake_engine:Adapter"
    group: str = ENTRY_POINT_GROUP
    loads: list[str] = field(default_factory=list)

    def load(self) -> object:
        self.loads.append(self.name)
        if isinstance(self.target, BaseException):
            raise self.target
        return self.target


@pytest.fixture
def installed(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[object]]:
    """The entry points the registry sees; a test appends to this list."""
    points: list[object] = []
    groups: list[str] = []

    def entry_points(*, group: str) -> list[object]:
        groups.append(group)
        return points

    monkeypatch.setattr(registry, "entry_points", entry_points)
    yield points
    assert set(groups) <= {ENTRY_POINT_GROUP}


@pytest.fixture
def fresh_cache() -> Iterator[None]:
    installed_adapters.cache_clear()
    yield
    installed_adapters.cache_clear()


def warnings_in(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "ithax.engines.registry" and record.levelno == logging.WARNING
    ]


# --- discovery ----------------------------------------------------------------------------


def test_the_group_is_ithax_engines() -> None:
    assert ENTRY_POINT_GROUP == "ithax.engines"


def test_a_dummy_adapter_is_found(installed: list[object]) -> None:
    installed.append(FakeEntryPoint("dummy", DummyAdapter))
    adapters = load_adapters()
    assert list(adapters) == ["dummy"]
    assert isinstance(adapters["dummy"], DummyAdapter)
    assert isinstance(adapters["dummy"], EngineAdapter)


def test_a_real_entry_point_is_imported_by_its_value(installed: list[object]) -> None:
    installed.append(EntryPoint("simpy", PROCESS_CLASS, ENTRY_POINT_GROUP))
    adapters = load_adapters()
    assert isinstance(adapters["simpy"], ProcessAdapter)


def test_adapters_are_listed_by_name(installed: list[object]) -> None:
    installed += [FakeEntryPoint("salabim", SalabimAdapter), FakeEntryPoint("dummy", DummyAdapter)]
    assert list(load_adapters()) == ["dummy", "salabim"]


def test_no_entry_points_give_no_adapters(installed: list[object]) -> None:
    assert load_adapters() == {}


def test_a_plugin_that_fails_to_import_is_left_out_and_logged(
    installed: list[object], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    installed += [
        EntryPoint("broken", "ithax_engine_that_is_not_installed:Adapter", ENTRY_POINT_GROUP),
        FakeEntryPoint("dummy", DummyAdapter),
    ]
    assert list(load_adapters()) == ["dummy"]
    [message] = warnings_in(caplog)
    assert "'broken'" in message
    assert "ithax_engine_that_is_not_installed:Adapter" in message
    assert "left out" in message
    assert "ModuleNotFoundError" in caplog.text


@pytest.mark.parametrize(
    "error", [ImportError("no engine"), SyntaxError("bad plugin"), RuntimeError("boom")]
)
def test_any_error_while_importing_is_not_fatal(
    installed: list[object], caplog: pytest.LogCaptureFixture, error: Exception
) -> None:
    installed += [FakeEntryPoint("broken", error), FakeEntryPoint("dummy", DummyAdapter)]
    assert list(load_adapters()) == ["dummy"]
    assert len(warnings_in(caplog)) == 1


def test_an_adapter_that_fails_to_start_is_left_out(
    installed: list[object], caplog: pytest.LogCaptureFixture
) -> None:
    class Unstartable(DummyAdapter):
        name = "unstartable"

        def __init__(self) -> None:
            raise RuntimeError("needs a licence server")

    installed.append(FakeEntryPoint("unstartable", Unstartable))
    assert load_adapters() == {}
    [message] = warnings_in(caplog)
    assert "'unstartable'" in message


def test_an_adapter_whose_capabilities_fail_is_left_out(
    installed: list[object], caplog: pytest.LogCaptureFixture
) -> None:
    class Failing(DummyAdapter):
        name = "failing"

        def capabilities(self) -> Capabilities:
            raise RuntimeError("engine not found on PATH")

    installed.append(FakeEntryPoint("failing", Failing))
    assert load_adapters() == {}
    assert len(warnings_in(caplog)) == 1


def test_capabilities_of_the_wrong_type_are_left_out(
    installed: list[object], caplog: pytest.LogCaptureFixture
) -> None:
    class Wrong(DummyAdapter):
        name = "wrong"

        def capabilities(self) -> Capabilities:
            return {"domains": ["process"]}  # type: ignore[return-value]

    installed.append(FakeEntryPoint("wrong", Wrong))
    assert load_adapters() == {}
    [message] = warnings_in(caplog)
    assert "'wrong'" in message
    assert "Capabilities" in message


@pytest.mark.parametrize("target", [object, (lambda: 42), str])
def test_an_object_that_is_not_an_adapter_is_left_out(
    installed: list[object], caplog: pytest.LogCaptureFixture, target: object
) -> None:
    installed.append(FakeEntryPoint("odd", target))
    assert load_adapters() == {}
    [message] = warnings_in(caplog)
    assert "EngineAdapter" in message


def test_a_version_that_is_not_text_is_left_out(
    installed: list[object], caplog: pytest.LogCaptureFixture
) -> None:
    class Numbered(DummyAdapter):
        version = 2  # type: ignore[assignment]

    installed.append(FakeEntryPoint("dummy", Numbered))
    assert load_adapters() == {}
    assert "EngineAdapter" in warnings_in(caplog)[0]


def test_a_name_that_differs_from_the_entry_point_is_left_out_and_logged(
    installed: list[object], caplog: pytest.LogCaptureFixture
) -> None:
    # Spec 1 "Engine contract" (AKS-97): the entry-point name must equal the class name,
    # since run.engine names the adapter; otherwise the adapter is left out.
    installed += [FakeEntryPoint("simpy", SalabimAdapter), FakeEntryPoint("dummy", DummyAdapter)]
    assert list(load_adapters()) == ["dummy"]
    [message] = warnings_in(caplog)
    assert "'simpy'" in message
    assert "'salabim'" in message


def test_two_entry_points_with_one_name_are_both_left_out_unimported(
    installed: list[object], caplog: pytest.LogCaptureFixture
) -> None:
    first = FakeEntryPoint("dummy", DummyAdapter, value="first_engine:Adapter")
    second = FakeEntryPoint("dummy", DummyAdapter, value="second_engine:Adapter")
    installed += [first, second, FakeEntryPoint("salabim", SalabimAdapter)]
    assert list(load_adapters()) == ["salabim"]
    assert first.loads == second.loads == []
    [message] = warnings_in(caplog)
    assert "'dummy'" in message
    assert "first_engine:Adapter" in message
    assert "second_engine:Adapter" in message


def test_three_entry_points_with_one_name_are_logged_once(
    installed: list[object], caplog: pytest.LogCaptureFixture
) -> None:
    installed += [FakeEntryPoint("dummy", DummyAdapter, value=f"e{n}:A") for n in range(3)]
    assert load_adapters() == {}
    assert len(warnings_in(caplog)) == 1


def test_the_installed_process_adapter_is_discovered() -> None:
    # The real metadata, written by ``pip install -e`` from pyproject.toml.
    [point] = [p for p in entry_points(group=ENTRY_POINT_GROUP) if p.name == "simpy"]
    assert point.value == PROCESS_CLASS
    adapters = load_adapters()
    assert isinstance(adapters["simpy"], ProcessAdapter)


def test_the_installed_optimization_adapter_is_discovered() -> None:
    # AKS-108: the product's second adapter, by its own entry point.
    from ithax.engines.optimize.adapter import HighsAdapter as RealHighsAdapter

    [point] = [p for p in entry_points(group=ENTRY_POINT_GROUP) if p.name == "highs"]
    assert point.value == "ithax.engines.optimize.adapter:HighsAdapter"
    adapters = load_adapters()
    assert list(adapters) == ["highs", "simpy"]
    assert isinstance(adapters["highs"], RealHighsAdapter)


# --- installed adapters, once per process ---------------------------------------------------


def test_installed_adapters_are_discovered_once(installed: list[object], fresh_cache: None) -> None:
    point = FakeEntryPoint("dummy", DummyAdapter)
    installed.append(point)
    first = installed_adapters()
    installed.append(FakeEntryPoint("salabim", SalabimAdapter))
    assert installed_adapters() is first
    assert list(first) == ["dummy"]
    assert point.loads == ["dummy"]
    with pytest.raises(TypeError):
        first["salabim"] = SalabimAdapter()  # type: ignore[index]


def test_installed_engines_default_to_the_installed_adapters(
    installed: list[object], fresh_cache: None
) -> None:
    installed.append(FakeEntryPoint("dummy", DummyAdapter))
    assert installed_engines() == (InstalledEngine("dummy", ("process",)),)


def test_installed_engines_are_the_adapters_with_no_stand_in() -> None:
    # The model layer's stand-in for optimization is gone (AKS-108).
    adapters: dict[str, EngineAdapter] = {"simpy": ProcessAdapter()}
    assert installed_engines(adapters) == (InstalledEngine("simpy", ("process",)),)
    adapters["highs"] = HighsAdapter()
    assert installed_engines(adapters) == (
        InstalledEngine("highs", ("optimization",)),
        InstalledEngine("simpy", ("process",)),
    )
    assert installed_engines({}) == ()


# --- selection (spec 1 "Top-level keys") ------------------------------------------------------


def test_the_one_adapter_for_the_domain_is_selected() -> None:
    simpy = ProcessAdapter()
    selection = select_adapter("process", None, {"simpy": simpy})
    assert selection == Selection(simpy, ())
    assert select_adapter("process", "simpy", {"simpy": simpy}).adapter is simpy


def test_an_optimization_model_without_its_adapter_is_e102_at_domain() -> None:
    # No stand-in any more (AKS-108): with no optimization adapter, nothing runs it.
    selection = select_adapter("optimization", None, {"simpy": ProcessAdapter()})
    assert selection.adapter is None
    assert [(issue.code, issue.path) for issue in selection.issues] == [("E102", "/domain")]
    [issue] = select_adapter("optimization", "highs", {}).issues
    assert (issue.code, issue.path) == ("E102", "/domain")
    highs = HighsAdapter()
    assert select_adapter("optimization", "highs", {"highs": highs}) == Selection(highs, ())


def test_run_engine_chooses_among_several_adapters() -> None:
    salabim = SalabimAdapter()
    adapters: dict[str, EngineAdapter] = {"simpy": ProcessAdapter(), "salabim": salabim}
    assert select_adapter("process", "salabim", adapters).adapter is salabim


def test_several_adapters_and_no_run_engine_is_e102_at_run_engine() -> None:
    adapters: dict[str, EngineAdapter] = {"simpy": ProcessAdapter(), "salabim": SalabimAdapter()}
    selection = select_adapter("process", None, adapters)
    assert selection.adapter is None
    [issue] = selection.issues
    assert (issue.code, issue.path) == ("E102", "/run/engine")


def test_an_unknown_run_engine_is_e102_at_run_engine() -> None:
    selection = select_adapter("process", "highs", {"simpy": ProcessAdapter()})
    assert selection.adapter is None
    [issue] = selection.issues
    assert (issue.code, issue.path) == ("E102", "/run/engine")
    assert issue.hint == "Name one of: 'simpy'."


def test_no_adapter_for_the_domain_is_e102_at_domain() -> None:
    [issue] = select_adapter("process", None, {}).issues
    assert (issue.code, issue.path) == ("E102", "/domain")
    [issue] = select_adapter("physics", None, {"simpy": ProcessAdapter()}).issues
    assert (issue.code, issue.path) == ("E102", "/domain")


def test_duplicates_left_out_leave_no_engine_for_the_domain(
    installed: list[object],
) -> None:
    # Spec 1 "Engine contract": duplicates are left out; if no single engine remains, E102.
    installed += [FakeEntryPoint("simpy", ProcessAdapter, value=f"e{n}:A") for n in range(2)]
    [issue] = select_adapter("process", None, load_adapters()).issues
    assert (issue.code, issue.path) == ("E102", "/domain")


def test_selection_defaults_to_the_installed_adapters() -> None:
    selection = select_adapter("process", None)
    assert isinstance(selection.adapter, ProcessAdapter)
    assert selection.adapter.capabilities().component_types == PROCESS_TYPES
