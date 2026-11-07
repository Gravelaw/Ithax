"""Shared helpers for the process adapter's tests (AKS-98): small models built through the
real loader, and a block that records what reaches it."""

from collections.abc import Callable, Mapping, Sequence
from typing import Any

import pytest
import simpy

from lcsim.engines.process.blocks import Block, Context, Item
from lcsim.engines.process.replication import Outcome, run_replication
from lcsim.engines.process.statistics import TimeWeighted, Window
from lcsim.engines.process.translate import engine_input
from lcsim.model.loading import load_document
from lcsim.model.model import Model
from lcsim.model.streams import generator_for

ModelMaker = Callable[..., Model]
ContextMaker = Callable[[float, float], Context]


def model_document(
    components: Sequence[Mapping[str, Any]],
    connections: Sequence[tuple[str, str]],
    *,
    length: str = "1200 s",
    warmup: str = "0 s",
    replications: int = 2,
    seed: int = 1,
    scenarios: Sequence[Mapping[str, Any]] | None = None,
    parameters: Mapping[str, Any] | None = None,
    record_interval: str | None = None,
) -> dict[str, Any]:
    experiment: dict[str, Any] = {
        "id": "e",
        "length": length,
        "warmup": warmup,
        "replications": replications,
        "seed": seed,
    }
    if record_interval is not None:
        experiment["record_interval"] = record_interval
    if scenarios is not None:
        experiment["scenarios"] = list(scenarios)
    return {
        "format_version": "0.1",
        "meta": {"name": "Test"},
        "domain": "process",
        "parameters": dict(parameters or {}),
        "components": [dict(component) for component in components],
        "connections": [{"from": origin, "to": to} for origin, to in connections],
        "experiments": [experiment],
        "run": {"target": "local", "fidelity": "standard"},
    }


@pytest.fixture
def make_model() -> ModelMaker:
    """Loads a model from components and connections; fails on any error issue."""

    def make(
        components: Sequence[Mapping[str, Any]],
        connections: Sequence[tuple[str, str]],
        **experiment: Any,
    ) -> Model:
        result = load_document(model_document(components, connections, **experiment))
        assert result.model is not None, [issue.as_dict() for issue in result.issues]
        return result.model

    return make


def constant(value: str) -> dict[str, str]:
    return {"dist": "constant", "value": value}


def line(
    interarrival: Mapping[str, Any], service: Mapping[str, Any], capacity: Any = 1
) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    """A source, one server and a sink: ``arrivals`` → ``till`` → ``exit``."""
    return (
        [
            {"id": "arrivals", "type": "source", "params": {"interarrival": interarrival}},
            {
                "id": "till",
                "type": "server",
                "params": {"capacity": capacity, "service": service},
            },
            {"id": "exit", "type": "sink", "params": {}},
        ],
        [("arrivals.out", "till.in"), ("till.out", "exit.in")],
    )


@pytest.fixture
def make_context() -> ContextMaker:
    """A fresh SimPy environment with the observed period from ``warmup`` to ``end``."""

    def make(warmup: float, end: float) -> Context:
        window = Window(warmup, end)
        return Context(env=simpy.Environment(), window=window, wip=TimeWeighted(window))

    return make


class Recorder(Block):
    """A test block: records each item and when it arrived; refuses items when closed, and
    reports ``queued`` waiting items (AKS-99)."""

    def configure(self, settings: Mapping[str, Any]) -> None:
        self.open = bool(settings.get("open", True))
        self.queued = int(settings.get("queued", 0))
        self.items: list[Item] = []
        self.times: list[float] = []

    def accepts(self) -> bool:
        return self.open

    def waiting_items(self) -> int:
        return self.queued

    def receive(self, item: Item) -> None:
        self.items.append(item)
        self.times.append(self.now)


def recorder(
    context: Context, *, open: bool = True, queued: int = 0, name: str = "recorder"
) -> Recorder:
    return Recorder(name, {"open": open, "queued": queued}, context, generator_for(0, 0, name))


def outcome_of_model(model: Model) -> Outcome:
    """Replication 0 of the model's experiment ``e``, run through the engine input."""
    outcome = run_replication(engine_input(model, "e"), 0, 0, lambda: False)
    assert outcome is not None
    return outcome


def metrics_of_model(model: Model) -> dict[str, float]:
    """Each metric of replication 0 of the model's experiment ``e``, by name."""
    return {metric: value for metric, value, _ in outcome_of_model(model).rows}


def series_of_model(model: Model) -> dict[str, list[tuple[float, float]]]:
    """Each time series of replication 0 of the model's experiment ``e``, by name."""
    series: dict[str, list[tuple[float, float]]] = {}
    for metric, time, value, _ in outcome_of_model(model).series:
        series.setdefault(metric, []).append((time, value))
    return series
