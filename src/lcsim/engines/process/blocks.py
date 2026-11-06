"""The process blocks on SimPy: ``source``, ``server`` and ``sink`` (spec 2 "Block reference").

SimPy schedules every event: a source is a SimPy process that waits one interarrival time
between items, and a service is a SimPy timeout whose callback ends it. The blocks keep
their own queues and counts, and the bookkeeping of ``lcsim.engines.process.statistics``.

Wiring: every block is a ``Block``. ``receive(item)`` hands it an item at the current
time, and ``accepts()`` says whether it can take one now; a block with output ports
connects each to the block that ``connect(port, target)`` names. A new block type (such as
``delay`` or ``branch``, AKS-99) is one more subclass in ``BLOCK_TYPES``.

Random numbers come only from the component's own stream (spec 1 "Random streams"): a
source draws each interarrival time after creating an item, a server draws each service
time when that service starts.

Settings arrive as the process adapter's engine input holds them
(``lcsim.engines.process.translate``): SI floats, whole numbers, words, and distributions
as objects of resolved numbers.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Generator, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, ClassVar

import numpy
import simpy

from lcsim.engines.process.statistics import Tally, TimeWeighted, Window
from lcsim.model.distributions import Sampler, sampler_from_numbers

__all__ = [
    "BLOCK_TYPES",
    "Block",
    "Context",
    "Item",
    "Server",
    "Sink",
    "Source",
    "sampler_from_json",
]


@dataclass
class Item:
    """One item: when it was created, and when it arrived at the block now holding it."""

    created: float
    arrived: float


@dataclass(frozen=True)
class Context:
    """What every block of one replication shares: the SimPy environment, the observed
    period, and the model's work in progress (``model.wip.mean``)."""

    env: simpy.Environment
    window: Window
    wip: TimeWeighted


# The keys of a distribution object that are not named fields.
_DIST_KEYS = frozenset({"dist", "values"})


def sampler_from_json(distribution: Mapping[str, Any]) -> Sampler:
    """The sampler of a distribution as the engine input holds it: ``dist``, its named
    fields as SI floats, and ``values`` for an ``empirical``."""
    fields = {name: float(value) for name, value in distribution.items() if name not in _DIST_KEYS}
    values = distribution.get("values")
    return sampler_from_numbers(
        str(distribution["dist"]),
        fields,
        [float(value) for value in values] if values is not None else None,
    )


class Block:
    """One component of a replication."""

    #: The output ports of the type; a branch's come from its routes.
    outputs: ClassVar[tuple[str, ...]] = ()

    def __init__(
        self,
        component_id: str,
        settings: Mapping[str, Any],
        context: Context,
        rng: numpy.random.Generator,
    ) -> None:
        self.id = component_id
        self.context = context
        self.rng = rng
        self.targets: dict[str, Block] = {}
        self.configure(settings)

    def configure(self, settings: Mapping[str, Any]) -> None:
        """Reads the component's settings; a block without settings reads none."""

    def connect(self, port: str, target: Block) -> None:
        """Connects output port ``port`` to ``target``."""
        if port not in self.outputs:
            raise ValueError(f"'{self.id}' has no output port '{port}'")
        self.targets[port] = target

    def target(self, port: str) -> Block:
        """The block output port ``port`` is connected to."""
        try:
            return self.targets[port]
        except KeyError:
            raise ValueError(f"output port '{self.id}.{port}' is not connected") from None

    def start(self) -> None:
        """Starts the block's own processes at time 0; most blocks have none."""

    def accepts(self) -> bool:
        """Whether the block can take an item now."""
        return True

    def receive(self, item: Item) -> None:
        """Takes ``item`` at the current time."""
        raise NotImplementedError(f"'{self.id}' has no input port")

    def metrics(self) -> dict[str, float]:
        """This replication's value of each of the type's metrics, by measure."""
        return {}

    @property
    def now(self) -> float:
        """The current simulation time."""
        return float(self.context.env.now)


class Source(Block):
    """Creates one item, waits one interarrival time, repeats. The first item is created at
    ``first_arrival`` (0 s when absent); after ``max_items`` items the source stops. An
    item the next block cannot accept is discarded and counted (spec 2 "Source when
    blocked")."""

    outputs = ("out",)

    def configure(self, settings: Mapping[str, Any]) -> None:
        self.interarrival = sampler_from_json(settings["interarrival"])
        self.first_arrival = float(settings.get("first_arrival", 0.0))
        max_items = settings.get("max_items")
        self.max_items: int | None = None if max_items is None else int(max_items)
        self.created = 0
        self.discarded = 0

    def start(self) -> None:
        self.context.env.process(self._create())

    def _create(self) -> Generator[simpy.Event, Any, None]:
        env = self.context.env
        if self.first_arrival > 0.0:
            yield env.timeout(self.first_arrival)
        made = 0
        while True:
            self._make_one()
            made += 1
            if self.max_items is not None and made >= self.max_items:
                return
            yield env.timeout(self.interarrival(self.rng))

    def _make_one(self) -> None:
        now = self.now
        observed = self.context.window.observes(now)
        if observed:
            self.created += 1
        out = self.target("out")
        if out.accepts():
            self.context.wip.add(now, 1)
            out.receive(Item(created=now, arrived=now))
        elif observed:
            self.discarded += 1

    def metrics(self) -> dict[str, float]:
        return {
            "created": float(self.created),
            "discarded": self.discarded / self.context.window.period,
        }


class Server(Block):
    """Items wait in the server's own queue, then hold one unit of capacity for one service
    time; ``discipline`` ``fifo`` (default) or ``lifo`` picks the next waiting item."""

    outputs = ("out",)

    def configure(self, settings: Mapping[str, Any]) -> None:
        self.capacity = int(settings["capacity"])
        self.service = sampler_from_json(settings["service"])
        discipline = settings.get("discipline", "fifo")
        if discipline not in ("fifo", "lifo"):
            raise ValueError(f"'{self.id}' has discipline {discipline!r}")
        self._next: Callable[[], Item] = (
            self._waiting_first if discipline == "fifo" else self._waiting_last
        )
        self.waiting: deque[Item] = deque()
        self.busy = 0
        window = self.context.window
        self.queue_length = TimeWeighted(window)
        self.busy_units = TimeWeighted(window)
        self.waits = Tally()

    def _waiting_first(self) -> Item:
        return self.waiting.popleft()

    def _waiting_last(self) -> Item:
        return self.waiting.pop()

    def receive(self, item: Item) -> None:
        item.arrived = self.now
        if self.busy < self.capacity:
            self._begin(item)
        else:
            self.waiting.append(item)
            self.queue_length.set(self.now, len(self.waiting))

    def _begin(self, item: Item) -> None:
        now = self.now
        if self.context.window.observes(now):
            self.waits.observe(now - item.arrived)
        self.busy += 1
        self.busy_units.set(now, self.busy)
        done = self.context.env.timeout(self.service(self.rng))
        done.callbacks.append(lambda _event: self._end(item))

    def _end(self, item: Item) -> None:
        # The item leaves before its unit is released (spec 2 "Blocking").
        self.target("out").receive(item)
        self.busy -= 1
        self.busy_units.set(self.now, self.busy)
        if self.waiting:
            following = self._next()
            self.queue_length.set(self.now, len(self.waiting))
            self._begin(following)

    def metrics(self) -> dict[str, float]:
        # No schedule or failure until M4: availability and scheduled fraction are 1, and
        # the busy count never exceeds the capacity, so utilization never exceeds 1.
        return {
            "wait.mean": self.waits.mean(),
            "utilization": self.busy_units.mean() / self.capacity,
            "availability": 1.0,
            "scheduled_fraction": 1.0,
            "queue_length.mean": self.queue_length.mean(),
            "queue_length.max": self.queue_length.maximum(),
        }


class Sink(Block):
    """Removes the item and records its statistics."""

    def configure(self, settings: Mapping[str, Any]) -> None:
        self.count = 0
        self.cycle_times = Tally()

    def receive(self, item: Item) -> None:
        now = self.now
        self.context.wip.add(now, -1)
        if self.context.window.observes(now):
            self.count += 1
            self.cycle_times.observe(now - item.created)

    def metrics(self) -> dict[str, float]:
        return {
            "throughput": self.count / self.context.window.period,
            "cycle_time.mean": self.cycle_times.mean(),
            "count": float(self.count),
        }


#: The block types the process adapter runs, by spec 2 type name.
BLOCK_TYPES: Mapping[str, type[Block]] = MappingProxyType(
    {"source": Source, "server": Server, "sink": Sink}
)
