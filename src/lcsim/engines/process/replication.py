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
it says yes. Otherwise it returns an ``Outcome``: the rows of the ``replications`` table
for this replication, ``(metric, value, unit)`` in component order, each type's metrics in
spec 2 order, then ``model.wip.mean``; and the rows of the ``timeseries`` table,
``(metric, time_s, value, unit)``.

Time series (spec 2 "Statistic definitions"): ``TimeSeries`` records each block's
``levels()`` and ``model.wip`` at k times ``record_interval`` for every k with that time
before the end, from 0 s; a time short of the end by less than ``ROUNDING`` times the interval
counts as the end. The loop records a sample once the next event is due after its time, so
a sample is the value after every event due at its instant; samples left when no event is
due before the end are recorded after the loop. Recording schedules no event and draws no
random number, so it cannot change any other result.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
from typing import Any, NamedTuple, TypeAlias

import simpy

from lcsim.engines.process.blocks import BLOCK_TYPES, Block, Context
from lcsim.engines.process.statistics import TimeWeighted, Window
from lcsim.model.catalogue import MEASURE_KINDS, PROCESS_TYPES, MeasureKind
from lcsim.model.streams import generator_for

__all__ = [
    "ROUNDING",
    "STOP_CHECK_EVENTS",
    "UNITS",
    "Outcome",
    "Row",
    "SeriesRow",
    "TimeSeries",
    "build_blocks",
    "run_replication",
]

#: One row of the ``replications`` table without its scenario and replication.
Row: TypeAlias = tuple[str, float, str]

#: One row of the ``timeseries`` table without its scenario and replication.
SeriesRow: TypeAlias = tuple[str, float, float, str]


class Outcome(NamedTuple):
    """What one replication gives: its ``replications`` and ``timeseries`` rows."""

    rows: list[Row]
    series: list[SeriesRow]


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


#: The ``unit`` of every time-series value: each is a number of items or a fraction.
SERIES_UNIT = UNITS[MeasureKind.NUMBER]


#: A sample time short of the end by less than this fraction of ``record_interval`` counts
#: as the end (spec 2 "Statistic definitions"): 200 times (29 s / 200) is just below 29 s.
ROUNDING = 1e-9


class TimeSeries:
    """The samples of one replication's time-persistent statistics."""

    def __init__(self, blocks: Sequence[Block], context: Context, interval: float) -> None:
        self._blocks = blocks
        self._context = context
        self._interval = interval
        self._last = context.window.end - ROUNDING * interval
        self._count = 0
        #: The time of the next sample, k times the interval (multiplied, not summed, so
        #: that no rounding error builds up); infinite when no sample is left. The first,
        #: at 0 s, is always taken.
        self.next_time = 0.0
        # Samples by metric, in the order the metrics first appear.
        self._samples: dict[str, list[tuple[float, float]]] = {}

    def record(self, time: float) -> None:
        """Records every metric's value now, as the sample at ``time``."""
        for block in self._blocks:
            for measure, value in block.levels().items():
                self._samples.setdefault(f"{block.id}.{measure}", []).append((time, value))
        self._samples.setdefault("model.wip", []).append((time, self._context.wip.value))

    def advance(self) -> None:
        """Records the next sample and moves on to the one after."""
        self.record(self.next_time)
        self._count += 1
        following = self._count * self._interval
        self.next_time = following if following < self._last else math.inf

    def rows(self) -> list[SeriesRow]:
        """The rows, by metric, then time."""
        return [
            (metric, time, value, SERIES_UNIT)
            for metric, samples in self._samples.items()
            for time, value in samples
        ]


def run_replication(
    engine_input: Mapping[str, Any],
    scenario: int,
    replication: int,
    should_stop: Callable[[], bool],
) -> Outcome | None:
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
    series = TimeSeries(blocks, context, float(experiment["record_interval"]))
    for block in blocks:
        block.start()
    events = 0
    while env.peek() < window.end:
        if events % STOP_CHECK_EVENTS == 0 and should_stop():
            return None
        while series.next_time < env.peek():
            series.advance()
        env.step()
        events += 1
    while series.next_time < window.end:
        series.advance()
    rows: list[Row] = []
    components = engine_input["scenarios"][scenario]["components"]
    for component, block in zip(components, blocks, strict=True):
        measures = block.metrics()
        for measure in PROCESS_TYPES[component["type"]].metrics:
            unit = UNITS[MEASURE_KINDS[measure]]
            rows.append((f"{block.id}.{measure}", measures[measure], unit))
    rows.append(("model.wip.mean", context.wip.mean(), UNITS[MEASURE_KINDS["wip.mean"]]))
    return Outcome(rows, series.rows())
