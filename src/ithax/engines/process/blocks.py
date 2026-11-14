"""The process blocks on SimPy: ``source``, ``server``, ``delay``, ``branch``, ``queue``,
``batch``, ``unbatch``, ``store`` and ``sink`` (spec 2 "Block reference").

SimPy schedules every event: a source is a SimPy process that waits one interarrival time
between items, and a service or a delay is a SimPy timeout whose callback ends it. The
blocks keep their own queues and counts, and the bookkeeping of
``ithax.engines.process.statistics``.

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
release, and neither does a store, whose item took its unit of stock on arrival. A queue
does not ``send``: it offers its next item and, when refused, waits in the
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
time when that service starts, a delay draws each time when the item arrives, a
``probability`` branch draws once per item when it arrives, and a store draws each lead
time when it places the order.

Settings arrive as the process adapter's engine input holds them
(``ithax.engines.process.translate``): SI floats, whole numbers, words, and distributions
as objects of resolved numbers.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Callable, Generator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, ClassVar

import numpy
import simpy

from ithax.engines.process.statistics import Tally, TimeWeighted, Window
from ithax.model.distributions import Sampler, sampler_from_numbers

__all__ = [
    "BLOCK_TYPES",
    "TRANSFER_CHECK_STEPS",
    "Batch",
    "Block",
    "Branch",
    "Context",
    "Delay",
    "Failure",
    "Item",
    "Queue",
    "ResourcePool",
    "Schedule",
    "Server",
    "Sink",
    "Source",
    "Stopped",
    "Store",
    "Transfers",
    "Unbatch",
    "Units",
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


#: Spec 2 "Zero-time loops" (#74; M2-5, M4-14): a replication stops when more than this many
#: events and same-instant transfer steps happen at one simulated instant.
INSTANT_STEP_LIMIT = 1_000_000


class ZeroTimeLoop(Exception):
    """More than ``INSTANT_STEP_LIMIT`` steps happened at the instant ``at`` (seconds)."""

    def __init__(self, at: float) -> None:
        super().__init__(at)
        self.at = at


class InstantCounter:
    """Counts the steps (events run and transfer steps) at the current simulated instant,
    from 0 each time the clock moves, and raises ``ZeroTimeLoop`` past the limit: items
    circling blocks that take no time would otherwise run until the run's time limit."""

    def __init__(self, env: simpy.Environment) -> None:
        self._env = env
        self._now = env.now
        self._count = 0

    def tick(self) -> None:
        """One more step at the current instant."""
        now = self._env.now
        if now != self._now:
            self._now, self._count = now, 0
        self._count += 1
        if self._count > INSTANT_STEP_LIMIT:
            raise ZeroTimeLoop(float(now))


def _never() -> bool:
    return False


class Transfers:
    """Same-instant steps of moving items, run one after another in the order they are
    asked for, rather than nested.

    Items can circle blocks that take no time (a branch routed back to itself) for very
    long, or forever, within one SimPy event, so ``should_stop`` is asked every
    ``TRANSFER_CHECK_STEPS`` steps here too; when it says yes, ``Stopped`` is raised."""

    def __init__(
        self, should_stop: Callable[[], bool] = _never, counter: InstantCounter | None = None
    ) -> None:
        self._should_stop = should_stop
        self._counter = counter
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
                if self._counter is not None:
                    self._counter.tick()
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

    def bind(self, blocks: Mapping[str, Block]) -> None:
        """Finds the blocks its settings name (a server's ``pool``, a schedule's or failure's
        ``target``), once every block exists and before any starts; most name none."""

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


@dataclass(eq=False)
class _Hold:
    """One item holding a unit of a server: its order of seizing and of starting service,
    when its service ends, and its state (spec 2 "Pool" and "Failure")."""

    item: Item
    seized: int
    #: ``reserved`` (holds the server unit, its service not begun), ``serving``,
    #: ``suspended`` (by a failure) or ``finished`` (waiting to move on).
    state: str = "reserved"
    started: int = 0
    ends: float = 0.0
    remaining: float = 0.0
    #: Bumped to cancel the end of service already scheduled.
    timer: int = 0
    #: On the failed unit.
    broken: bool = False
    #: Holds a pool unit.
    granted: bool = False


class Units(Block):
    """A block with units whose number can change over time: a server or a pool.

    ``capacity`` is the nominal number of units. A ``schedule`` sets ``scheduled`` (capped
    at ``capacity``) and a ``failure`` counts ``failed`` units; the available capacity is
    the scheduled capacity minus the failed units, at least 0 (spec 2 "Schedule" and
    "Failure"). Without either, it is ``capacity`` for ever and the statistics are computed
    exactly as before the two blocks existed, so no result changes.

    With either, ``utilization`` is the time-integral of the busy units, counted at each
    instant up to the available capacity, over the time-integral of that capacity; NaN when
    nothing is available over the whole period. ``busy`` counts the busy units. A rise of
    the available capacity runs ``on_rise`` as a transfer step, so waiting items start at
    that instant."""

    def _setup_units(self, capacity: int, on_rise: Callable[[], None]) -> None:
        self.capacity = capacity
        self.busy = 0
        self._on_rise = on_rise
        self.scheduled = capacity
        self.failed = 0
        self.has_schedule = False
        self.has_failure = False
        window = self.context.window
        self.available_units = TimeWeighted(window, float(capacity))
        self.scheduled_units = TimeWeighted(window, float(capacity))
        self.up = TimeWeighted(window, 1.0)
        self.counted_busy = TimeWeighted(window)
        self.busy_units = TimeWeighted(window)

    @property
    def available(self) -> int:
        """The units that may hold an item now."""
        return max(0, min(self.scheduled, self.capacity) - self.failed)

    @property
    def varies(self) -> bool:
        """Whether a schedule or a failure changes the block's capacity."""
        return self.has_schedule or self.has_failure

    def track(self) -> None:
        """Records the capacity statistics after a change, when a schedule or failure acts."""
        if not self.varies:
            return
        now = self.now
        available = self.available
        self.available_units.set(now, available)
        self.scheduled_units.set(now, min(self.scheduled, self.capacity))
        self.up.set(now, 1.0 if self.failed < self.capacity else 0.0)
        self.counted_busy.set(now, min(self.busy, available))

    def set_scheduled(self, capacity: int) -> None:
        """The scheduled capacity becomes ``capacity`` now (spec 2 "Schedule")."""
        before = self.available
        self.scheduled = capacity
        self.track()
        if self.available > before:
            self.context.transfers.run(self._on_rise)

    def utilization(self) -> float:
        """Spec 2 ``<server>.utilization`` and ``<pool>.utilization``."""
        if not self.varies:
            return self.busy_units.mean() / self.capacity
        available = self.available_units.integral()
        return self.counted_busy.integral() / available if available > 0.0 else math.nan

    def utilization_level(self) -> float:
        """The ``utilization`` time-series value now: busy units over ``capacity``, or, with
        a schedule or failure, busy units up to the available ones over those, 0 when none
        is available."""
        busy = self.busy
        if not self.varies:
            return busy / self.capacity
        available = self.available
        return min(busy, available) / available if available > 0 else 0.0


class Server(Units):
    """Items wait in the server's own queue, then hold one unit of capacity for one service
    time; ``discipline`` ``fifo`` (default) or ``lifo`` picks the next waiting item. With
    ``queue_capacity`` the server accepts an item only while a unit is available or fewer
    than that many items wait; a finished item the next block refuses keeps its unit busy.

    With ``pool`` an item that takes a unit then asks the pool for one of its units; its
    wait and service begin when it holds both, and it releases both when it moves on (spec
    2 "Pool"). While it waits for the pool unit it counts as waiting, not busy.

    A ``failure`` takes one unit (``fail``): an available unit holding no item if there is
    one, otherwise the unit of the item in service that started last, which is suspended
    with its remaining service time and resumes at the repair (``repair``); otherwise a unit
    holding a finished item, which still moves on; otherwise a unit whose item waits for the
    pool, whose service then begins only at the repair (spec 2 "Failure")."""

    outputs = ("out",)

    def configure(self, settings: Mapping[str, Any]) -> None:
        self.service = sampler_from_json(settings["service"])
        queue_capacity = settings.get("queue_capacity")
        self.queue_capacity: int | None = None if queue_capacity is None else int(queue_capacity)
        discipline = settings.get("discipline", "fifo")
        if discipline not in DISCIPLINES:
            raise ValueError(f"'{self.id}' has discipline {discipline!r}")
        self._next: Callable[[], Item] = (
            self._waiting_first if discipline == "fifo" else self._waiting_last
        )
        pool = settings.get("pool")
        self.pool_id: str | None = None if pool is None else str(pool)
        self.pool: ResourcePool | None = None
        self.waiting: deque[Item] = deque()
        # Units holding an item, and items holding a unit whose service has not begun; the
        # busy units (``utilization``) are those in service or holding a finished item.
        self.held = 0
        self.reserved = 0
        self._seized = 0
        self._started = 0
        self._finished = 0
        # Holds in service by start order, and holds waiting for the pool by seizing order.
        self._serving: dict[int, _Hold] = {}
        self._reserving: dict[int, _Hold] = {}
        # Holds on a failed unit, oldest failure first.
        self._broken: deque[_Hold] = deque()
        self._setup_units(int(settings["capacity"]), self._capacity_rose)
        self.queue_length = TimeWeighted(self.context.window)
        self.waits = Tally()

    def bind(self, blocks: Mapping[str, Block]) -> None:
        if self.pool_id is not None:
            pool = blocks[self.pool_id]
            assert isinstance(pool, ResourcePool)  # validation checks the type (E124)
            self.pool = pool

    def _waiting_first(self) -> Item:
        return self.waiting.popleft()

    def _waiting_last(self) -> Item:
        return self.waiting.pop()

    def accepts(self) -> bool:
        return (
            self.queue_capacity is None
            or self.held < self.available
            or len(self.waiting) < self.queue_capacity
        )

    def waiting_items(self) -> int:
        return len(self.waiting) + self.reserved

    def _note_queue(self) -> None:
        """Records the number waiting when it has changed."""
        waiting = len(self.waiting) + self.reserved
        if waiting != self.queue_length.value:
            self.queue_length.set(self.now, waiting)

    def receive(self, item: Item) -> None:
        item.arrived = self.now
        if not self.waiting and self.held < self.available:
            self._seize(item)
        else:
            self.waiting.append(item)
        self._note_queue()

    def _seize(self, item: Item) -> None:
        """The item takes a unit, then a pool unit when the server has a pool."""
        self.held += 1
        self._seized += 1
        hold = _Hold(item, self._seized)
        if self.pool is None or self.pool.take(self, hold):
            hold.granted = self.pool is not None
            self._begin(hold)
        else:
            self.reserved += 1
            self._reserving[hold.seized] = hold

    def pool_granted(self, hold: _Hold) -> None:
        """The pool has given ``hold`` its unit; its service begins unless its server unit
        has failed meanwhile, and then begins at the repair."""
        hold.granted = True
        if hold.broken:
            return
        del self._reserving[hold.seized]
        self.reserved -= 1
        self._note_queue()
        self._begin(hold)

    def _begin(self, hold: _Hold) -> None:
        now = self.now
        if self.context.window.observes(now):
            self.waits.observe(now - hold.item.arrived)
        self.busy += 1
        self.busy_units.set(now, self.busy)
        self._started += 1
        hold.started = self._started
        hold.state = "serving"
        self._serving[hold.started] = hold
        self.track()
        self._serve(hold, self.service(self.rng))

    def _serve(self, hold: _Hold, duration: float) -> None:
        hold.ends = self.now + duration
        hold.timer += 1
        timer = hold.timer

        def done(_event: simpy.Event) -> None:
            if hold.timer == timer:  # not suspended since
                self._end(hold)

        self.context.env.timeout(duration).callbacks.append(done)

    def _end(self, hold: _Hold) -> None:
        # The item leaves before its unit is released (spec 2 "Blocking"); a refused item
        # keeps the unit until it moves.
        del self._serving[hold.started]
        hold.state = "finished"
        self._finished += 1
        self.send(hold.item, self.target("out"), self._release)

    def _release(self) -> None:
        self._finished -= 1
        self.busy -= 1
        self.busy_units.set(self.now, self.busy)
        self.held -= 1
        if self.pool is not None:
            self.pool.release()
        self.track()
        self._fill()
        self.space_freed()

    def _fill(self) -> None:
        """Waiting items take units while units are available."""
        while self.waiting and self.held < self.available:
            self._seize(self._next())
            self._note_queue()

    def _capacity_rose(self) -> None:
        self._fill()
        self.space_freed()

    def fail(self) -> None:
        """One unit fails now (spec 2 "Failure")."""
        before = self.available
        self.failed += 1
        if self.held >= before:  # no available unit is free
            if self._serving:
                hold = self._serving.pop(max(self._serving))
                hold.timer += 1  # cancels its end
                hold.remaining = hold.ends - self.now
                hold.state = "suspended"
                hold.broken = True
                self.busy -= 1
                self.busy_units.set(self.now, self.busy)
                self._broken.append(hold)
            elif not self._finished and self._reserving:
                hold = self._reserving.pop(max(self._reserving))
                hold.broken = True
                self._broken.append(hold)
            # Otherwise the unit holds a finished item, which still moves on.
        self.track()

    def repair(self) -> None:
        """The failed unit that failed first is repaired now; the item it held goes on."""
        before = self.available
        self.failed -= 1
        if self._broken:
            hold = self._broken.popleft()
            hold.broken = False
            if hold.state == "suspended":
                hold.state = "serving"
                self.busy += 1
                self.busy_units.set(self.now, self.busy)
                self._serving[hold.started] = hold
                self._serve(hold, hold.remaining)
            elif hold.granted:  # it got its pool unit while its server unit was failed
                self.reserved -= 1
                self._note_queue()
                self._begin(hold)
            else:
                self._reserving[hold.seized] = hold
        self.track()
        if self.available > before:
            self.context.transfers.run(self._capacity_rose)

    def metrics(self) -> dict[str, float]:
        return {
            "wait.mean": self.waits.mean(),
            "utilization": self.utilization(),
            "availability": self.up.mean() if self.has_failure else 1.0,
            "scheduled_fraction": (
                self.scheduled_units.integral() / (self.capacity * self.context.window.period)
                if self.has_schedule
                else 1.0
            ),
            "queue_length.mean": self.queue_length.mean(),
            "queue_length.max": self.queue_length.maximum(),
        }

    def levels(self) -> dict[str, float]:
        # Units holding a refused item are busy (spec 2 "Blocking").
        return {
            "queue_length": float(len(self.waiting) + self.reserved),
            "utilization": self.utilization_level(),
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

    Every onward move is a step of the replication's ``Transfers``, and ``accepts`` only
    reads the queue, so no call nests one level per block. A queue full only because its
    offer to the next block is still due at this instant decides about an arriving item
    after that offer: a blocking queue refuses it, and it moves in at the same instant when
    the offer frees space (spec 2 "Blocking"); a discarding queue holds it until then
    (``_arrivals``) and discards it only if the queue is still full with its offer refused.

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
        # Items that reached a discarding queue while it was full with its offer still due,
        # oldest first, waiting for that offer before the queue decides about them.
        self._arrivals: deque[Item] = deque()
        # An offer to the next block is due among the transfers (``pending``); the queue's
        # step waits in the next block's ``blocked`` line (``stalled``); a decision about
        # ``_arrivals`` is due among the transfers (``deciding``).
        self._pending = False
        self._stalled = False
        self._deciding = False
        self.queue_length = TimeWeighted(self.context.window)
        self.waits = Tally()
        self.discarded = 0

    def accepts(self) -> bool:
        return self.discards or len(self.waiting) < self.capacity

    def waiting_items(self) -> int:
        return len(self.waiting) + len(self._arrivals)

    def receive(self, item: Item) -> None:
        item.arrived = self.now
        if self._arrivals:
            self._arrivals.append(item)  # behind the items not yet decided about
        elif len(self.waiting) < self.capacity:
            self._enter(item)
        elif self._stalled:
            assert self.discards  # a blocking queue refuses when full (``accepts``)
            self._discard(item)
        else:
            # Full, but the offer to the next block has not been tried yet; a blocking
            # queue refuses here (``accepts``).
            assert self.discards
            self._arrivals.append(item)
            self._decide_later()

    def _enter(self, item: Item) -> None:
        self.waiting.append(item)
        if self._stalled:
            self.queue_length.set(self.now, len(self.waiting))
        elif not self._pending:
            self._pending = True
            self.context.transfers.run(self._offer)

    def _discard(self, item: Item) -> None:
        now = self.now
        self.context.wip.add(now, -item.count())
        if self.context.window.observes(now):
            self.discarded += 1

    def _decide_later(self) -> None:
        if not self._deciding:
            self._deciding = True
            self.context.transfers.run(self._decide)

    def _decide(self) -> None:
        """After the offer that was due: each held item enters while there is room; with the
        queue full and its offer refused it is discarded; with an offer due again it waits
        for that one."""
        self._deciding = False
        while self._arrivals:
            if len(self.waiting) < self.capacity:
                self._enter(self._arrivals.popleft())
            elif self._stalled:
                self._discard(self._arrivals.popleft())
            else:
                assert self._pending  # held units always have a step due to move them
                self._decide_later()
                return

    def _offer(self) -> None:
        """Moves on the units held now while the next block accepts them; when it refuses,
        waits in its ``blocked`` line. A unit arriving meanwhile (a queue that feeds itself)
        gets an offer of its own, so an endless zero-time loop still reaches
        ``should_stop``."""
        self._pending = False
        target = self.target("out")
        for _ in range(len(self.waiting)):
            if self._stalled:
                break
            if target.accepts():
                self._take()
            else:
                self._stalled = True
                self.queue_length.set(self.now, len(self.waiting))
                target.blocked.append(self._pull)

    def _pull(self) -> None:
        """The step in the next block's ``blocked`` line: space has freed there."""
        self._stalled = False
        self._take()
        if self.waiting and not self._pending:
            self._pending = True
            self.context.transfers.run(self._offer)

    def _take(self) -> None:
        """Moves the unit the discipline picks to the next block, which accepts it now."""
        now = self.now
        item = self.waiting.pop() if self.lifo else self.waiting.popleft()
        self.queue_length.set(now, min(self.queue_length.value, len(self.waiting)))
        if self.context.window.observes(now):
            self.waits.observe(now - item.arrived)
        self.target("out").receive(item)
        self.context.transfers.run(self.space_freed)

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


class Store(Block):
    """Stock of one kind, drawn one unit per item (spec 2 "Block reference" and "Store").

    Each item arriving takes one unit of stock and is sent on at once; an item the next
    block refuses keeps its unit and waits in that block's ``blocked`` line. An item that
    finds the stock at zero is a stock-out, counted when it arrives, and waits, first in
    first out, for a delivery. The store reviews its inventory position, the textbook one
    (stock on hand plus on order minus the items waiting for stock; #72, owner decision
    D12), at time 0 (``start``) and at every demand, whether the item takes a unit or
    waits: when the position is at or below ``reorder_point``, it places one order of
    ``order_quantity``, drawing its lead time from the store's own stream then; several
    orders may be outstanding. A delivery leaves the position as it was (units come off
    order, and each waiting item it serves takes one of them), so it reviews nothing. It
    always accepts.

    A delivery runs as one ``Transfers`` step: it adds the units and withdraws one for each
    waiting item it can serve, in order, and their moves on are later steps, so no call
    nests one level per block downstream."""

    outputs = ("out",)

    def configure(self, settings: Mapping[str, Any]) -> None:
        self.reorder_point = int(settings["reorder_point"])
        self.order_quantity = int(settings["order_quantity"])
        self.lead_time = sampler_from_json(settings["lead_time"])
        self.on_hand = int(settings["initial"])
        self.on_order = 0
        # Items waiting for stock, oldest first.
        self.waiting: deque[Item] = deque()
        self.stock = TimeWeighted(self.context.window, float(self.on_hand))
        self.stockouts = 0
        self.orders = 0

    def start(self) -> None:
        self._review()

    def waiting_items(self) -> int:
        return len(self.waiting)

    def receive(self, item: Item) -> None:
        item.arrived = self.now
        if self.on_hand > 0:
            self._take_unit()
            self._review()
            self.send(item, self.target("out"), _nothing)
        else:
            if self.context.window.observes(self.now):
                self.stockouts += 1
            self.waiting.append(item)
            self._review()

    def _take_unit(self) -> None:
        self.on_hand -= 1
        self.stock.set(self.now, self.on_hand)

    def position(self) -> int:
        """The inventory position: on hand plus on order minus the items waiting for stock
        (#72)."""
        return self.on_hand + self.on_order - len(self.waiting)

    def _review(self) -> None:
        if self.position() > self.reorder_point:
            return
        self.on_order += self.order_quantity
        if self.context.window.observes(self.now):
            self.orders += 1
        delivery = self.context.env.timeout(self.lead_time(self.rng))
        delivery.callbacks.append(lambda _event: self.context.transfers.run(self._deliver))

    def _deliver(self) -> None:
        self.on_order -= self.order_quantity
        self.on_hand += self.order_quantity
        self.stock.set(self.now, self.on_hand)
        while self.waiting and self.on_hand > 0:
            item = self.waiting.popleft()
            self._take_unit()
            self.send(item, self.target("out"), _nothing)

    def metrics(self) -> dict[str, float]:
        return {
            "stock.mean": self.stock.mean(),
            "stockouts": float(self.stockouts),
            "orders": self.orders / self.context.window.period,
        }

    def levels(self) -> dict[str, float]:
        return {"stock": float(self.on_hand)}


class ResourcePool(Units):
    """Shared units that servers name in their ``pool`` (spec 2 "Pool"). A server's item
    asks for a unit with ``take``; it gets one at once when nobody is waiting and a unit is
    available, and otherwise waits in ``line``, first come first served across servers.
    ``release`` gives the unit back; the next item in line gets it in a transfer step.
    ``utilization`` is over the pool's units, as a server's; a schedule may change them."""

    def configure(self, settings: Mapping[str, Any]) -> None:
        # ``busy`` counts the units held.
        self.line: deque[tuple[Server, _Hold]] = deque()
        self._granting = False
        self._setup_units(int(settings["capacity"]), self._capacity_rose)

    def take(self, server: Server, hold: _Hold) -> bool:
        """Whether ``hold`` gets a unit now; otherwise it joins the line."""
        if not self.line and self.busy < self.available:
            self._hold_one()
            return True
        self.line.append((server, hold))
        return False

    def _hold_one(self) -> None:
        self.busy += 1
        self.busy_units.set(self.now, self.busy)
        self.track()

    def release(self) -> None:
        """A unit comes back now."""
        self.busy -= 1
        self.busy_units.set(self.now, self.busy)
        self.track()
        if self.line and not self._granting:
            self._granting = True
            self.context.transfers.run(self._capacity_rose)

    def _capacity_rose(self) -> None:
        """Gives units to the line, in order, while units are available."""
        self._granting = False
        while self.line and self.busy < self.available:
            server, hold = self.line.popleft()
            self._hold_one()
            server.pool_granted(hold)

    def metrics(self) -> dict[str, float]:
        return {"utilization": self.utilization()}

    def levels(self) -> dict[str, float]:
        return {"utilization": self.utilization_level()}


class Schedule(Block):
    """Sets the scheduled capacity of its ``target``, a server or a pool, over time (spec 2
    "Schedule"): the sum of the ``shifts`` covering the time within each ``period``, 0
    where none does. The capacity at time 0 is set when the blocks are bound, before any
    event; each later change is a SimPy timeout of this block's process. SimPy's resource
    capacity cannot change, so the adapter does this itself (the M2 "Engine gap")."""

    def configure(self, settings: Mapping[str, Any]) -> None:
        self.target_id = str(settings["target"])
        self.period = float(settings["period"])
        shifts = [
            (float(shift["start"]), float(shift["end"]), int(shift["capacity"]))
            for shift in settings["shifts"]
        ]
        cuts = sorted(
            {0.0}
            | {start for start, _, _ in shifts}
            | {end for _, end, _ in shifts if end < self.period}
        )
        # (offset within the period, capacity from there), merging equal neighbours.
        self.segments: list[tuple[float, int]] = []
        for cut in cuts:
            capacity = sum(units for start, end, units in shifts if start <= cut < end)
            if not self.segments or self.segments[-1][1] != capacity:
                self.segments.append((cut, capacity))
        self.subject: Units | None = None

    def bind(self, blocks: Mapping[str, Block]) -> None:
        subject = blocks[self.target_id]
        assert isinstance(subject, Units)  # validation checks the type (E124)
        self.subject = subject
        subject.has_schedule = True
        subject.set_scheduled(self.segments[0][1])

    def start(self) -> None:
        if len(self.segments) > 1:
            self.context.env.process(self._run())

    def _run(self) -> Generator[simpy.Event, Any, None]:
        env = self.context.env
        assert self.subject is not None
        cycle = 0.0
        index = 0
        while True:
            index += 1
            if index == len(self.segments):
                index = 0
                cycle += self.period
            offset, capacity = self.segments[index]
            yield env.timeout(cycle + offset - env.now)
            self.subject.set_scheduled(capacity)


class Failure(Block):
    """Fails one unit of its ``target`` server at a time (spec 2 "Failure"): a
    ``time_to_failure`` drawn from this block's own stream at time 0 and after each repair,
    on calendar time, then a ``time_to_repair`` drawn at the failure."""

    def configure(self, settings: Mapping[str, Any]) -> None:
        self.target_id = str(settings["target"])
        self.time_to_failure = sampler_from_json(settings["time_to_failure"])
        self.time_to_repair = sampler_from_json(settings["time_to_repair"])
        self.subject: Server | None = None

    def bind(self, blocks: Mapping[str, Block]) -> None:
        subject = blocks[self.target_id]
        assert isinstance(subject, Server)  # validation checks the type (E124)
        self.subject = subject
        subject.has_failure = True

    def start(self) -> None:
        self.context.env.process(self._run())

    def _run(self) -> Generator[simpy.Event, Any, None]:
        env = self.context.env
        assert self.subject is not None
        while True:
            yield env.timeout(self.time_to_failure(self.rng))
            self.subject.fail()
            yield env.timeout(self.time_to_repair(self.rng))
            self.subject.repair()


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
        "store": Store,
        "resource_pool": ResourcePool,
        "schedule": Schedule,
        "failure": Failure,
        "sink": Sink,
    }
)
