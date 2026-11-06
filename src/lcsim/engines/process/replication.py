"""One replication of one scenario, from the engine input alone.

``run_replication(engine_input, scenario, replication, should_stop)`` builds the blocks of
the scenario on a fresh SimPy environment, gives each component its own stream
``<seed>:<replication>:<component id>`` (spec 1 "Random streams"; the scenario does not
enter the key, so scenarios share streams), starts the sources in component order, and
runs every event due before the end of the run. An event due exactly at the end does not
run (spec 2 "Simultaneous events"): the loop stops when the next event is not before the
end, as ``env.run(until=length)`` does, since nothing scheduled after its call can be due
before its stop event at that instant.

The loop asks ``should_stop`` every ``STOP_CHECK_EVENTS`` events and returns ``None`` when
it says yes. Otherwise it returns the rows of the ``replications`` table for this
replication: ``(metric, value, unit)`` in component order, each type's metrics in spec 2
order, then ``model.wip.mean``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any, TypeAlias

import simpy

from lcsim.engines.process.blocks import BLOCK_TYPES, Block, Context
from lcsim.engines.process.statistics import TimeWeighted, Window
from lcsim.model.catalogue import MEASURE_KINDS, PROCESS_TYPES, MeasureKind
from lcsim.model.streams import generator_for

__all__ = ["STOP_CHECK_EVENTS", "UNITS", "Row", "build_blocks", "run_replication"]

#: One row of the ``replications`` table without its scenario and replication.
Row: TypeAlias = tuple[str, float, str]

#: How many events run between two calls of ``should_stop``.
STOP_CHECK_EVENTS = 1024

#: The ``unit`` of each kind of measure (spec 1 "Tables for the ``process`` domain").
UNITS: Mapping[MeasureKind, str] = MappingProxyType(
    {MeasureKind.TIME: "s", MeasureKind.RATE: "1/s", MeasureKind.NUMBER: "1"}
)


def build_blocks(
    scenario: Mapping[str, Any],
    connections: list[Mapping[str, str]],
    context: Context,
    seed: int,
    replication: int,
) -> list[Block]:
    """The scenario's blocks, connected, each with its own stream."""
    blocks: dict[str, Block] = {}
    for component in scenario["components"]:
        component_id = component["id"]
        block_type = BLOCK_TYPES[component["type"]]
        blocks[component_id] = block_type(
            component_id,
            component["settings"],
            context,
            generator_for(seed, replication, component_id),
        )
    for connection in connections:
        origin, port = connection["from"].split(".", 1)
        destination = connection["to"].split(".", 1)[0]
        blocks[origin].connect(port, blocks[destination])
    return list(blocks.values())


def run_replication(
    engine_input: Mapping[str, Any],
    scenario: int,
    replication: int,
    should_stop: Callable[[], bool],
) -> list[Row] | None:
    """Runs replication ``replication`` of the scenario at index ``scenario``."""
    experiment = engine_input["experiment"]
    window = Window(warmup=float(experiment["warmup"]), end=float(experiment["length"]))
    env = simpy.Environment()
    context = Context(env=env, window=window, wip=TimeWeighted(window))
    blocks = build_blocks(
        engine_input["scenarios"][scenario],
        engine_input["connections"],
        context,
        int(experiment["seed"]),
        replication,
    )
    for block in blocks:
        block.start()
    events = 0
    while env.peek() < window.end:
        if events % STOP_CHECK_EVENTS == 0 and should_stop():
            return None
        env.step()
        events += 1
    rows: list[Row] = []
    components = engine_input["scenarios"][scenario]["components"]
    for component, block in zip(components, blocks, strict=True):
        measures = block.metrics()
        for measure in PROCESS_TYPES[component["type"]].metrics:
            unit = UNITS[MEASURE_KINDS[measure]]
            rows.append((f"{block.id}.{measure}", measures[measure], unit))
    rows.append(("model.wip.mean", context.wip.mean(), UNITS[MEASURE_KINDS["wip.mean"]]))
    return rows
