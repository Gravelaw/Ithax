"""The process blocks on SimPy: ``source``, ``server``, ``delay``, ``branch``, ``queue``,
``batch``, ``unbatch`` and ``sink`` (spec 2 "Block reference").

SimPy schedules every event: a source is a SimPy process that waits one interarrival time
between items, and a service or a delay is a SimPy timeout whose callback ends it. The
blocks keep their own queues and counts, and the bookkeeping of
``lcsim.engines.process.statistics``.

Wiring: every block is a ``Block``. ``receive(item)`` hands it an item at the current
time, and ``accepts()`` says whether it can take one now; a block with output ports
connects each to the block that ``connect(port, target)`` names. A new block type is one
more subclass in ``BLOCK_TYPES``.

Blocking (spec 2 "Blocking"): a server with ``queue_capacity`` and a full ``queue`` with
``on_full`` ``block`` refuse an item; every other block always accepts. A block passes an
item on with ``send(item, target, then)``: when ``target`` accepts, it
receives the item and ``then()`` runs at the same instant; otherwise the move waits in the
target's ``blocked`` line, first in, first out, and runs as soon as the target calls
``space_freed()``, at that same instant. A server's ``then`` releases its unit, so a unit
holding a refused item stays busy; a delay, a branch, a batch and an unbatch have nothing to
release. A queue does not ``send``: it offers its next item and, when refused, waits in the
target's ``blocked`` line with a step that takes the item its discipline picks at the
moment space frees. A source does not send either: it discards an item its next block
refuses (spec 2 "Source when blocked").

Batches (spec 2 "Batch timeout"): a batch is an ``Item`` whose ``contents`` are the units it
collected, in arrival order, and whose ``created`` is its first unit's; it moves as one
unit. An unbatch passes on the contents of what it receives, one level, or a single item as
it is. A sink counts a batch once, and every item a batch holds leaves work in progress with
it, as at a queue that discards it.

Offers and ``then`` steps go through the replication's ``Transfers``, which runs them one
after another, first in, first out, instead of nested: a branch routed back to itself, or a
long line of blocked servers freeing at one instant, would otherwise nest one call per pass
and overflow Python's stack. A move out of ``blocked`` takes its item at once, so the
target's ``accepts()`` is always read against what it holds.

Random numbers come only from the component's own stream (spec 1 "Random streams"): a
source draws each interarrival time after creating an item, a server draws each service
time when that service starts, a delay draws each time when the item arrives, and a
``probability`` branch draws once per item when it arrives.

Settings arrive as the process adapter's engine input holds them
(``lcsim.engines.process.translate``): SI floats, whole numbers, words, and distributions
as objects of resolved numbers.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Generator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, ClassVar

import numpy
import simpy

from lcsim.engines.process.statistics import Tally, TimeWeighted, Window
from lcsim.model.distributions import Sampler, sampler_from_numbers

__all__ = [
    "BLOCK_TYPES",
    "TRANSFER_CHECK_STEPS",
    "Batch",
    "Block",
    "Branch",
    "Context",
    "Delay",
    "Item",
    "Queue",
    "Server",
    "Sink",
    "Source",
    "Stopped",
    "Transfers",
    "Unbatch",
    "sampler_from_json",
]


@dataclass
class Item:
    """One unit moving through the model: when it was created, when it arrived at the block
    now holding it, and, for a batch, the units it holds in the order the batch collected
    them (empty for a single item). A batch's ``created`` is its first unit's."""

    created: float
    arrived: float
    contents: tuple[Item, ...] = ()

    def count(self) -> int:
        """The number of items the unit is: 1 for a single item, the items of every unit
        it holds for a batch."""
        return sum(part.count() for part in self.contents) if self.contents else 1


#: How many transfer steps run between two calls of a ``Transfers``' ``should_stop``.
TRANSFER_CHECK_STEPS = 1024


class Stopped(Exception):
    """Raised out of a ``Transfers`` whose ``should_stop`` said yes."""


def _never() -> bool:
    return False


class Transfers:
    """Same-instant steps of moving items, run one after another in the order they are
    asked for, rather than nested.

    Items can circle blocks that take no time (a branch routed back to itself) for very
    long, or forever, within one SimPy event, so ``should_stop`` is asked every
    ``TRANSFER_CHECK_STEPS`` steps here too; when it says yes, ``Stopped`` is raised."""

    def __init__(self, should_stop: Callable[[], bool] = _never) -> None:
        self._should_stop = should_stop
        self._pending: deque[Callable[[], None]] = deque()
        self._running = False
        self._steps = 0

    def run(self, step: Callable[[], None]) -> None:
        """Runs ``step`` now, or after the steps already asked for when called from one."""
        self._pending.append(step)
        if self._running:
            return
        self._running = True
        try:
            while self._pending:
                self._steps += 1
                if self._steps % TRANSFER_CHECK_STEPS == 0 and self._should_stop():
                    raise Stopped
                self._pending.popleft()()
        finally:
            self._running = False


@dataclass(frozen=True)
class Context:
    """What every block of one replication shares: the SimPy environment, the observed
    period, the model's work in progress (``model.wip.mean``) and the item transfers."""

    env: simpy.Environment
    window: Window
    wip: TimeWeighted
    transfers: Transfers = field(default_factory=Transfers)


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


def _nothing() -> None:
    """What a block without capacity does once an item it sent has moved."""


class Block:
    """One component of a replication."""

    #: The output ports of the type; a branch's come from its routes (``ports()``).
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
        # Moves of items this block refused, waiting for space, oldest first.
        self.blocked: deque[Callable[[], None]] = deque()
        self.configure(settings)

    def configure(self, settings: Mapping[str, Any]) -> None:
        """Reads the component's settings; a block without settings reads none."""

    def ports(self) -> tuple[str, ...]:
        """The block's output ports."""
        return self.outputs

    def connect(self, port: str, target: Block) -> None:
        """Connects output port ``port`` to ``target``."""
        if port not in self.ports():
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

    def waiting_items(self) -> int:
        """The items waiting in the block's queue (spec 2 "Branch rules"): 0 for a block
        without a queue."""
        return 0

    def send(self, item: Item, target: Block, then: Callable[[], None]) -> None:
        """Moves ``item`` to ``target`` and runs ``then``, now if ``target`` accepts it,
        otherwise as soon as ``target`` frees space (spec 2 "Blocking")."""
        transfers = self.context.transfers

        def move() -> None:
            target.receive(item)
            transfers.run(then)

        def offer() -> None:
            if target.accepts():
                move()
            else:
                target.blocked.append(move)

        transfers.run(offer)

    def space_freed(self) -> None:
        """Moves the items this block refused, oldest first, while it accepts."""
        while self.blocked and self.accepts():
            self.blocked.popleft()()

    def metrics(self) -> dict[str, float]:
        """This replication's value of each of the type's metrics, by measure."""
        return {}

    def levels(self) -> dict[str, float]:
        """The values of the block's time-persistent statistics now, by measure, for the
        ``timeseries`` table (spec 2 "Statistic definitions")."""
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
    time; ``discipline`` ``fifo`` (default) or ``lifo`` picks the next waiting item. With
    ``queue_capacity`` the server accepts an item only while a unit is free or fewer than
    that many items wait; a finished item the next block refuses keeps its unit busy."""

    outputs = ("out",)

    def configure(self, settings: Mapping[str, Any]) -> None:
        self.capacity = int(settings["capacity"])
        self.service = sampler_from_json(settings["service"])
        queue_capacity = settings.get("queue_capacity")
        self.queue_capacity: int | None = None if queue_capacity is None else int(queue_capacity)
        discipline = settings.get("discipline", "fifo")
        if discipline not in DISCIPLINES:
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

    def accepts(self) -> bool:
        return (
            self.queue_capacity is None
            or self.busy < self.capacity
            or len(self.waiting) < self.queue_capacity
        )

    def waiting_items(self) -> int:
        return len(self.waiting)

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
        # The item leaves before its unit is released (spec 2 "Blocking"); a refused item
        # keeps the unit until it moves.
        self.send(item, self.target("out"), self._release)

    def _release(self) -> None:
        self.busy -= 1
        self.busy_units.set(self.now, self.busy)
        if self.waiting:
            following = self._next()
            self.queue_length.set(self.now, len(self.waiting))
            self._begin(following)
        self.space_freed()

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

    def levels(self) -> dict[str, float]:
        # Units holding a refused item are busy (spec 2 "Blocking").
        return {
            "queue_length": float(len(self.waiting)),
            "utilization": self.busy / self.capacity,
        }


class Delay(Block):
    """Holds each item for a time drawn when it arrives; no queue and no capacity limit, so
    it always accepts. An item the next block refuses stays until space frees there."""

    outputs = ("out",)

    def configure(self, settings: Mapping[str, Any]) -> None:
        self.time = sampler_from_json(settings["time"])

    def receive(self, item: Item) -> None:
        done = self.context.env.timeout(self.time(self.rng))
        done.callbacks.append(lambda _event: self.send(item, self.target("out"), _nothing))


#: The disciplines of spec 2 "Discipline".
DISCIPLINES = ("fifo", "lifo")


#: The ``on_full`` words of a ``queue`` (spec 2 "Block reference").
ON_FULL = ("block", "discard")


#: The branch rules of spec 2 "Branch rules".
BRANCH_RULES = ("probability", "shortest_queue")


class Branch(Block):
    """Sends each item down one route, chosen when the item arrives (spec 2 "Branch
    rules"); one output port per route. It always accepts; an item its route's block
    refuses waits at the branch until space frees there."""

    def configure(self, settings: Mapping[str, Any]) -> None:
        self.routes = tuple(str(route) for route in settings["routes"])
        self.rule = str(settings["rule"])
        if self.rule not in BRANCH_RULES:
            raise ValueError(f"'{self.id}' has rule {self.rule!r}")
        weights = [float((settings.get("weights") or {}).get(route, 0.0)) for route in self.routes]
        # Running sums of the weights in route order; ``shortest_queue`` ignores them. The
        # weights are divided by the largest first, which keeps every ratio, so that the
        # sum of valid finite weights (two of 1e308) cannot overflow to infinity.
        largest = max(weights)
        self._sums: list[float] = []
        total = 0.0
        for weight in weights:
            total += weight / largest if largest > 0.0 else 0.0
            self._sums.append(total)

    def ports(self) -> tuple[str, ...]:
        return self.routes

    def receive(self, item: Item) -> None:
        route = self._by_weight() if self.rule == "probability" else self._shortest()
        self.send(item, self.target(route), _nothing)

    def _by_weight(self) -> str:
        """One draw u in [0, 1): the first route whose running sum of weights exceeds u
        times the total. A float u below 1 times a positive total stays below the total,
        so when no earlier route qualifies the last does, and its weight is above 0."""
        point = self.rng.random() * self._sums[-1]
        for route, running in zip(self.routes[:-1], self._sums[:-1], strict=True):
            if point < running:
                return route
        return self.routes[-1]

    def _shortest(self) -> str:
        """The route whose next block has the fewest waiting items; the earliest on a tie."""
        return min(self.routes, key=lambda route: self.target(route).waiting_items())


class Queue(Block):
    """A standalone buffer of ``capacity`` units. An item moves on as soon as the next block
    accepts it, so one passing straight through waits 0 s and is never counted as waiting;
    the others wait, and ``discipline`` ``fifo`` (default) or ``lifo`` picks the one that
    moves when space frees. When full, ``on_full`` ``block`` (default) refuses an item, and
    ``discard`` takes it and throws it away, counted in ``discarded``.

    ``queue_length`` records the units that could not move on at once: it rises only while
    the queue's offer waits in the next block's ``blocked`` line, so after every instant it
    equals the number of units held."""

    outputs = ("out",)

    def configure(self, settings: Mapping[str, Any]) -> None:
        self.capacity = int(settings["capacity"])
        discipline = settings.get("discipline", "fifo")
        if discipline not in DISCIPLINES:
            raise ValueError(f"'{self.id}' has discipline {discipline!r}")
        self.lifo = discipline == "lifo"
        on_full = settings.get("on_full", "block")
        if on_full not in ON_FULL:
            raise ValueError(f"'{self.id}' has on_full {on_full!r}")
        self.discards = on_full == "discard"
        self.waiting: deque[Item] = deque()
        # An offer to the next block is due or waiting in its ``blocked`` line (``offering``);
        # it waits there (``stalled``).
        self._offering = False
        self._stalled = False
        self.queue_length = TimeWeighted(self.context.window)
        self.waits = Tally()
        self.discarded = 0

    def accepts(self) -> bool:
        return self.discards or len(self.waiting) < self.capacity

    def waiting_items(self) -> int:
        return len(self.waiting)

    def receive(self, item: Item) -> None:
        now = self.now
        if len(self.waiting) >= self.capacity:
            assert self.discards  # a blocking queue refuses when full (``accepts``)
            self.context.wip.add(now, -item.count())
            if self.context.window.observes(now):
                self.discarded += 1
            return
        item.arrived = now
        self.waiting.append(item)
        if self._stalled:
            self.queue_length.set(now, len(self.waiting))
        elif not self._offering:
            self._offering = True
            self.context.transfers.run(self._offer)

    def _offer(self) -> None:
        target = self.target("out")
        if target.accepts():
            self._pull()
        else:
            self._stalled = True
            self.queue_length.set(self.now, len(self.waiting))
            target.blocked.append(self._pull)

    def _pull(self) -> None:
        """Moves the unit the discipline picks to the next block, which accepts it now."""
        now = self.now
        self._offering = self._stalled = False
        item = self.waiting.pop() if self.lifo else self.waiting.popleft()
        self.queue_length.set(now, min(self.queue_length.value, len(self.waiting)))
        if self.context.window.observes(now):
            self.waits.observe(now - item.arrived)
        self.target("out").receive(item)
        transfers = self.context.transfers
        if self.waiting:
            self._offering = True
            transfers.run(self._offer)
        transfers.run(self.space_freed)

    def metrics(self) -> dict[str, float]:
        return {
            "queue_length.mean": self.queue_length.mean(),
            "queue_length.max": self.queue_length.maximum(),
            "wait.mean": self.waits.mean(),
            "discarded": self.discarded / self.context.window.period,
        }

    def levels(self) -> dict[str, float]:
        return {"queue_length": self.queue_length.value}


class Batch(Block):
    """Collects ``size`` units and releases them as one batch, created when its first unit
    was. With ``timeout``, a batch still collecting when that time has passed since its
    first unit arrived is released as it is. It always accepts: a formed batch the next
    block refuses waits for space there while the next batch collects. Each unit's wait
    runs from its arrival to the moment its batch moves on."""

    outputs = ("out",)

    def configure(self, settings: Mapping[str, Any]) -> None:
        self.size = int(settings["size"])
        timeout = settings.get("timeout")
        self.timeout: float | None = None if timeout is None else float(timeout)
        self.collecting: list[Item] = []
        # Batches formed so far: a timeout releases only the batch it was started for.
        self._formed = 0
        self.waits = Tally()

    def receive(self, item: Item) -> None:
        item.arrived = self.now
        self.collecting.append(item)
        if len(self.collecting) == 1 and self.timeout is not None:
            batch = self._formed
            timer = self.context.env.timeout(self.timeout)
            timer.callbacks.append(lambda _event: self._expire(batch))
        if len(self.collecting) >= self.size:
            self._release()

    def _expire(self, batch: int) -> None:
        if batch == self._formed:  # still collecting, so it holds at least its first unit
            self._release()

    def _release(self) -> None:
        parts = tuple(self.collecting)
        arrivals = [part.arrived for part in parts]
        self.collecting = []
        self._formed += 1
        unit = Item(created=parts[0].created, arrived=self.now, contents=parts)

        def moved() -> None:
            now = self.now
            if self.context.window.observes(now):
                for arrived in arrivals:
                    self.waits.observe(now - arrived)

        self.send(unit, self.target("out"), moved)

    def metrics(self) -> dict[str, float]:
        return {"wait.mean": self.waits.mean()}


class Unbatch(Block):
    """Splits whatever it receives into the units it holds, one level of batching, and
    sends them on in order; a single item passes through. It always accepts; units the next
    block refuses wait here, in order, until space frees there."""

    outputs = ("out",)

    def receive(self, item: Item) -> None:
        target = self.target("out")
        for part in item.contents or (item,):
            self.send(part, target, _nothing)


class Sink(Block):
    """Removes the unit and records its statistics; a batch counts once, with its own
    creation time, and every item it holds leaves work in progress."""

    def configure(self, settings: Mapping[str, Any]) -> None:
        self.count = 0
        self.cycle_times = Tally()

    def receive(self, item: Item) -> None:
        now = self.now
        self.context.wip.add(now, -item.count())
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
    {
        "source": Source,
        "server": Server,
        "delay": Delay,
        "branch": Branch,
        "queue": Queue,
        "batch": Batch,
        "unbatch": Unbatch,
        "sink": Sink,
    }
)
