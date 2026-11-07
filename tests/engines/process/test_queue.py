"""The ``queue`` block (spec 2 "Block reference", "Blocking" and "Statistic definitions";
AKS-105).

A standalone buffer of ``capacity`` items with a ``discipline`` (``fifo`` by default, or
``lifo``). With ``on_full`` ``block`` (the default) a full queue refuses an item, so a
server upstream stays blocked and a source discards; with ``discard`` it takes the item and
throws it away, counted in ``<queue>.discarded``. An item moves on as soon as the next block
accepts it; one that passes straight through waits 0 s and is never counted as waiting.
Every case below is computed by hand, event by event, with constant times.
"""

from collections.abc import Generator
from itertools import pairwise
from typing import Any

import pytest
import simpy
from conftest import (
    ContextMaker,
    ModelMaker,
    constant,
    metrics_of_model,
    recorder,
    series_of_model,
)

from lcsim.engines.process.blocks import BLOCK_TYPES, Context, Item, Queue, Stopped, Transfers
from lcsim.engines.process.statistics import TimeWeighted, Window
from lcsim.model.catalogue import PROCESS_TYPES
from lcsim.model.streams import generator_for


def source(interarrival: str) -> dict[str, Any]:
    return {"id": "arrivals", "type": "source", "params": {"interarrival": constant(interarrival)}}


def queue(name: str = "line", **settings: Any) -> dict[str, Any]:
    return {"id": name, "type": "queue", "params": settings}


def server(name: str, service: str, **settings: Any) -> dict[str, Any]:
    return {
        "id": name,
        "type": "server",
        "params": {"capacity": 1, "service": constant(service), **settings},
    }


def sink() -> dict[str, Any]:
    return {"id": "exit", "type": "sink", "params": {}}


LOSS_CONNECTIONS = [("arrivals.out", "line.in"), ("line.out", "till.in"), ("till.out", "exit.in")]


def loss_line(make_model: ModelMaker, **queue_settings: Any) -> Any:
    """Arrivals every 60 s from 0 into a queue, then a server (service 150 s,
    ``queue_capacity`` 0), then a sink, for 600 s: the queue, loss benchmark made
    deterministic."""
    queue_settings.setdefault("capacity", 2)
    experiment = {"length": "600 s"}
    experiment.update(queue_settings.pop("experiment", {}))
    return make_model(
        [
            source("60 s"),
            queue(**queue_settings),
            server("till", "150 s", queue_capacity=0),
            sink(),
        ],
        LOSS_CONNECTIONS,
        **experiment,
    )


def block_queue(context: Context, **settings: Any) -> Queue:
    settings.setdefault("capacity", 2)
    return Queue("line", settings, context, generator_for(7, 0, "line"))


def test_the_queue_type_is_registered_with_its_metrics() -> None:
    assert BLOCK_TYPES["queue"] is Queue
    assert PROCESS_TYPES["queue"].metrics == (
        "queue_length.mean",
        "queue_length.max",
        "wait.mean",
        "discarded",
    )


def test_a_full_queue_makes_its_source_discard(make_model: ModelMaker) -> None:
    """Item i arrives at 60i s. Item 0 goes straight to the server ([0, 150)). Items 1 and 2
    wait. At 150 s item 1 moves ([150, 300)) and item 3 joins at 180 s, so the queue is full
    when item 4 arrives at 240 s: the source discards it. At 300 s the server's end
    (scheduled at 150 s) runs before the arrival (scheduled at 240 s): item 2 moves
    ([300, 450)), then item 5 joins. Items 6 and 7 are discarded; at 450 s item 3 moves
    ([450, 600)); item 8 joins at 480 s; item 9 is discarded."""
    metrics = metrics_of_model(loss_line(make_model))
    assert metrics["arrivals.created"] == 10.0
    assert metrics["arrivals.discarded"] == 4 / 600  # items 4, 6, 7 and 9
    assert metrics["line.discarded"] == 0.0  # a blocking queue discards nothing itself
    assert metrics["exit.count"] == 3.0  # items 0, 1 and 2 at 150, 300 and 450 s
    assert metrics["exit.cycle_time.mean"] == (150 + 240 + 330) / 3
    # Waits of the items that left the queue: items 0 to 3.
    assert metrics["line.wait.mean"] == (0 + 90 + 180 + 270) / 4
    # Waiting: 1 over [60, 120), 2 over [120, 150), 1 over [150, 180), 2 over [180, 450),
    # 1 over [450, 480), 2 over [480, 600).
    assert metrics["line.queue_length.mean"] == (60 + 60 + 30 + 540 + 30 + 240) / 600
    assert metrics["line.queue_length.max"] == 2.0
    assert metrics["till.utilization"] == 1.0
    assert metrics["till.wait.mean"] == 0.0
    # Items 0, 1, 2, 3, 5 and 8 are in the system from arrival to the sink or the end.
    present = [150, 300 - 60, 450 - 120, 600 - 180, 600 - 300, 600 - 480]
    assert metrics["model.wip.mean"] == sum(present) / 600


def test_a_discarding_queue_counts_its_own_discards(make_model: ModelMaker) -> None:
    """The same line with ``on_full`` ``discard``: the queue always accepts, so the source
    discards nothing, and the queue throws away items 4, 6, 7 and 9 instead."""
    metrics = metrics_of_model(loss_line(make_model, on_full="discard"))
    assert metrics["arrivals.discarded"] == 0.0
    assert metrics["line.discarded"] == 4 / 600
    assert metrics["exit.count"] == 3.0
    assert metrics["line.wait.mean"] == (0 + 90 + 180 + 270) / 4
    assert metrics["line.queue_length.max"] == 2.0
    present = [150, 300 - 60, 450 - 120, 600 - 180, 600 - 300, 600 - 480]
    assert metrics["model.wip.mean"] == sum(present) / 600  # a discarded item leaves WIP


def test_lifo_passes_on_the_latest_waiting_item(make_model: ModelMaker) -> None:
    """Capacity 3, ``lifo``. Item 0 is served [0, 150). At 150 s items 1 and 2 wait: item 2
    moves ([150, 300)). Items 3 and 4 join. At 300 s item 4 moves ([300, 450)), then item 5
    joins, filling the queue (1, 3, 5); items 6 and 7 are discarded by the source. At 450 s
    item 5 moves ([450, 600)); item 8 joins; item 9 is discarded."""
    model = loss_line(make_model, capacity=3, discipline="lifo")
    metrics = metrics_of_model(model)
    assert metrics["arrivals.discarded"] == 3 / 600
    assert metrics["exit.count"] == 3.0  # items 0, 2 and 4
    assert metrics["exit.cycle_time.mean"] == (150 + 180 + 210) / 3
    assert metrics["line.wait.mean"] == (0 + 30 + 60 + 150) / 4
    assert metrics["line.queue_length.max"] == 3.0


def test_fifo_is_the_default_discipline(make_model: ModelMaker) -> None:
    assert metrics_of_model(loss_line(make_model)) == metrics_of_model(
        loss_line(make_model, discipline="fifo", on_full="block")
    )


def test_an_item_passing_straight_through_waits_zero_and_is_never_counted_waiting(
    make_model: ModelMaker,
) -> None:
    """A queue feeding a delay: the delay always accepts, so every item moves at once."""
    components = [
        source("60 s"),
        queue(capacity=1),
        {"id": "walk", "type": "delay", "params": {"time": constant("10 s")}},
        sink(),
    ]
    connections = [("arrivals.out", "line.in"), ("line.out", "walk.in"), ("walk.out", "exit.in")]
    metrics = metrics_of_model(make_model(components, connections, length="300 s"))
    assert metrics["line.wait.mean"] == 0.0
    assert metrics["line.queue_length.mean"] == 0.0
    assert metrics["line.queue_length.max"] == 0.0
    assert metrics["exit.count"] == 5.0


def test_items_arriving_together_and_all_moving_on_are_never_counted_waiting(
    make_context: ContextMaker,
) -> None:
    """Three items reach an empty queue at one instant, within one transfer step, and the
    next block takes them all: none is ever counted as waiting, even for no time."""
    context = make_context(0.0, 10.0)
    block = block_queue(context, capacity=3)
    out = recorder(context)
    block.connect("out", out)
    items = [Item(0.0, 0.0) for _ in range(3)]

    def arrive() -> None:
        for item in items:
            block.receive(item)

    context.transfers.run(arrive)
    assert out.items == items
    metrics = block.metrics()
    assert metrics["queue_length.max"] == 0.0
    assert metrics["wait.mean"] == 0.0


def test_items_arriving_together_are_not_discarded_while_they_can_move_on(
    make_model: ModelMaker,
) -> None:
    """Review of PR #27: arrivals every 60 s into a batch of 3, an unbatch, a discarding
    queue of 1 and a sink, 600 s. Each batch's three items reach the queue at one instant
    (120, 300 and 480 s); the sink takes each at once, so the queue is never full and
    nothing is discarded."""
    components = [
        source("60 s"),
        {"id": "pack", "type": "batch", "params": {"size": 3}},
        {"id": "unpack", "type": "unbatch", "params": {}},
        queue(capacity=1, on_full="discard"),
        sink(),
    ]
    connections = [
        ("arrivals.out", "pack.in"),
        ("pack.out", "unpack.in"),
        ("unpack.out", "line.in"),
        ("line.out", "exit.in"),
    ]
    metrics = metrics_of_model(make_model(components, connections, length="600 s"))
    assert metrics["line.discarded"] == 0.0
    assert metrics["exit.count"] == 9.0
    assert metrics["line.queue_length.max"] == 0.0
    assert metrics["line.wait.mean"] == 0.0


def test_a_queue_whose_items_can_move_on_is_not_full(make_context: ContextMaker) -> None:
    """Within one transfer step a full queue of one whose item the next block would take
    still accepts: the item moves on first."""
    context = make_context(0.0, 10.0)
    block = block_queue(context, capacity=1)
    out = recorder(context)
    block.connect("out", out)
    first, second = Item(0.0, 0.0), Item(0.0, 0.0)
    seen: list[bool] = []

    def arrive() -> None:
        block.receive(first)
        seen.append(block.accepts())
        block.receive(second)

    context.transfers.run(arrive)
    assert seen == [True]
    assert out.items == [first, second]


def test_a_full_queue_feeding_itself_holds_its_item(make_context: ContextMaker) -> None:
    """A queue of one whose ``out`` leads back to its own ``in`` is full with one item, so
    it refuses that item and holds it, without asking itself again and again."""
    context = make_context(0.0, 10.0)
    block = block_queue(context, capacity=1)
    block.connect("out", block)
    block.receive(Item(0.0, 0.0))
    assert block.waiting_items() == 1 and len(block.blocked) == 1
    assert not block.accepts()


@pytest.mark.parametrize(
    "settings", [{"capacity": 2}, {"capacity": 1, "on_full": "discard"}], ids=["block", "discard"]
)
def test_a_queue_feeding_itself_can_still_be_stopped(settings: dict[str, Any]) -> None:
    """Review of PR #27: a queue whose ``out`` leads back to its own ``in`` with room for
    the item circles it forever at one instant. Each pass must be a transfer step, so the
    replication's ``should_stop`` is asked and the loop ends with ``Stopped``."""
    asked: list[int] = []

    def should_stop() -> bool:
        asked.append(1)
        return True

    window = Window(0.0, 10.0)
    context = Context(
        env=simpy.Environment(),
        window=window,
        wip=TimeWeighted(window),
        transfers=Transfers(should_stop),
    )
    block = Queue("line", settings, context, generator_for(7, 0, "line"))
    block.connect("out", block)
    with pytest.raises(Stopped):
        block.receive(Item(0.0, 0.0))
    assert asked == [1]


def test_a_full_queue_blocks_the_server_upstream(make_model: ModelMaker) -> None:
    """Arrivals every 60 s into server a (service 10 s), a queue of capacity 1, then server
    b (service 100 s, ``queue_capacity`` 0), 400 s. Item 0: a [0, 10), b [10, 110). Item 1:
    a [60, 70), waits in the queue until 110, b [110, 210). Item 2: a [120, 130), waits
    until 210, b [210, 310). Item 3: a [180, 190), refused by the full queue, holds a's unit;
    at 210 s it moves into the queue and waits until 310, b [310, 410). Item 4: a
    [240, 250), held until 310, then waits in the queue. Item 5 (300 s) waits in a's queue
    until 310: a [310, 320), then held to the end. Item 6 (360 s) waits in a's queue."""
    components = [source("60 s"), server("a", "10 s"), queue(capacity=1)]
    components += [server("b", "100 s", queue_capacity=0), sink()]
    connections = [
        ("arrivals.out", "a.in"),
        ("a.out", "line.in"),
        ("line.out", "b.in"),
        ("b.out", "exit.in"),
    ]
    metrics = metrics_of_model(make_model(components, connections, length="400 s"))
    assert metrics["arrivals.discarded"] == 0.0  # a's own queue is unlimited
    assert metrics["line.discarded"] == 0.0
    # a's unit is busy, serving or holding, over [0, 10), [60, 70), [120, 130), [180, 210),
    # [240, 400).
    assert metrics["a.utilization"] == (10 + 10 + 10 + 30 + 160) / 400
    assert metrics["a.wait.mean"] == (0 + 0 + 0 + 0 + 0 + 10) / 6
    assert metrics["b.utilization"] == 390 / 400
    assert metrics["line.wait.mean"] == (0 + 40 + 80 + 100) / 4
    # The queue holds item 1 over [70, 110), item 2 over [130, 210), item 3 over
    # [210, 310), item 4 over [310, 400).
    assert metrics["line.queue_length.mean"] == (40 + 80 + 100 + 90) / 400
    assert metrics["line.queue_length.max"] == 1.0
    assert metrics["exit.count"] == 3.0
    assert metrics["exit.cycle_time.mean"] == (110 + 150 + 190) / 3


def test_the_warm_up_boundary(make_model: ModelMaker) -> None:
    """The loss line with 300 s of warm-up: the source creates items 5 to 9 after it (item
    5 at exactly 300 s counts) and discards 6, 7 and 9; items 2 and 3 leave the queue at
    300 and 450 s; the queue holds 2 over [300, 450), 1 over [450, 480), 2 over
    [480, 600). Its maximum takes the 2 held at the end of warm-up."""
    metrics = metrics_of_model(loss_line(make_model, experiment={"warmup": "300 s"}))
    assert metrics["arrivals.created"] == 5.0
    assert metrics["arrivals.discarded"] == 3 / 300
    assert metrics["line.wait.mean"] == (180 + 270) / 2
    assert metrics["line.queue_length.mean"] == (300 + 30 + 240) / 300
    assert metrics["line.queue_length.max"] == 2.0
    assert metrics["exit.count"] == 2.0  # items 1 and 2, at 300 and 450 s


def test_discards_before_warm_up_are_not_counted(make_model: ModelMaker) -> None:
    """With ``discard`` and 250 s of warm-up only the discards at 360, 420 and 540 s count;
    the one at 240 s does not."""
    model = loss_line(make_model, on_full="discard", experiment={"warmup": "250 s"})
    assert metrics_of_model(model)["line.discarded"] == 3 / 350


def test_a_queue_no_item_leaves_has_no_wait(make_model: ModelMaker) -> None:
    """Items leave the queue only at 150 s and later; with the run ending at 100 s no item
    leaves after warm-up, so the mean wait is NaN (spec 2 "Statistic definitions")."""
    metrics = metrics_of_model(
        loss_line(make_model, experiment={"warmup": "50 s", "length": "100 s"})
    )
    assert metrics["line.wait.mean"] != metrics["line.wait.mean"]  # NaN
    assert metrics["line.queue_length.mean"] == 40 / 50  # item 1 waits over [60, 100)


def test_the_time_series_of_a_queue_is_its_queue_length(make_model: ModelMaker) -> None:
    """Spec 2 "Statistic definitions": every time-persistent statistic has a series; the
    queue's is ``<queue>.queue_length``, the value after the events of each instant."""
    series = series_of_model(loss_line(make_model, experiment={"record_interval": "100 s"}))
    assert list(series) == [
        "line.queue_length",
        "till.queue_length",
        "till.utilization",
        "model.wip",
    ]
    assert series["line.queue_length"] == [
        (0.0, 0.0),
        (100.0, 1.0),
        (200.0, 2.0),
        (300.0, 2.0),
        (400.0, 2.0),
        (500.0, 2.0),
    ]


def test_a_blocking_queue_accepts_only_while_it_has_room(make_context: ContextMaker) -> None:
    context = make_context(0.0, 10.0)
    block = block_queue(context)
    block.connect("out", recorder(context, open=False))
    assert block.accepts()
    block.receive(Item(0.0, 0.0))
    assert block.accepts() and block.waiting_items() == 1
    block.receive(Item(0.0, 0.0))
    assert not block.accepts() and block.waiting_items() == 2


def test_a_discarding_queue_always_accepts(make_context: ContextMaker) -> None:
    context = make_context(0.0, 10.0)
    block = block_queue(context, capacity=1, on_full="discard")
    block.connect("out", recorder(context, open=False))
    for _ in range(3):
        assert block.accepts()
        block.receive(Item(0.0, 0.0))
    assert block.waiting_items() == 1
    assert block.metrics()["discarded"] == 2 / 10


def test_items_wait_until_the_next_block_frees_space(make_context: ContextMaker) -> None:
    """Three items at 0 s into a closed block that opens at 5 s: all three move at 5 s, in
    arrival order, each having waited 5 s."""
    context = make_context(0.0, 10.0)
    block = block_queue(context, capacity=3)
    out = recorder(context, open=False)
    block.connect("out", out)
    items = [Item(0.0, 0.0) for _ in range(3)]
    for item in items:
        block.receive(item)

    def reopen() -> Generator[simpy.Event, Any, None]:
        yield context.env.timeout(5.0)
        out.open = True
        out.space_freed()

    context.env.process(reopen())
    context.env.run(until=10.0)
    assert out.items == items
    assert out.times == [5.0, 5.0, 5.0]
    metrics = block.metrics()
    assert metrics["wait.mean"] == 5.0
    assert metrics["queue_length.mean"] == 3 * 5 / 10
    assert metrics["queue_length.max"] == 3.0
    assert block.levels() == {"queue_length": 0.0}


def test_space_in_the_queue_frees_the_upstream_block(make_context: ContextMaker) -> None:
    """A full queue of one, closed downstream: a second item offered by another block waits
    in the queue's blocked line and moves in when the first item leaves."""
    context = make_context(0.0, 10.0)
    block = block_queue(context, capacity=1)
    out = recorder(context, open=False)
    block.connect("out", out)
    up = recorder(context, name="up")
    first, second = Item(0.0, 0.0), Item(0.0, 0.0)
    block.receive(first)
    up.send(second, block, lambda: None)
    assert block.waiting_items() == 1 and len(block.blocked) == 1
    out.open = True
    out.space_freed()
    assert out.items == [first, second]
    assert block.waiting_items() == 0 and not block.blocked


def test_a_long_line_of_full_queues_frees_without_recursing(make_context: ContextMaker) -> None:
    """2,000 full queues of one in a line, each refusing the one before: when the last
    block opens every item moves at the same instant, without nesting one call per queue."""
    context = make_context(0.0, 10.0)
    blocks = [
        Queue(f"q{index}", {"capacity": 1}, context, generator_for(7, 0, f"q{index}"))
        for index in range(2000)
    ]
    out = recorder(context, open=False)
    for current, following in pairwise(blocks):
        current.connect("out", following)
    blocks[-1].connect("out", out)
    for block in reversed(blocks):
        block.receive(Item(0.0, 0.0))
    assert all(block.waiting_items() == 1 for block in blocks)
    out.open = True
    context.transfers.run(out.space_freed)
    assert len(out.items) == 2000
    assert all(block.waiting_items() == 0 for block in blocks)


@pytest.mark.parametrize(("setting", "value"), [("discipline", "priority"), ("on_full", "drop")])
def test_unknown_words_are_refused(make_context: ContextMaker, setting: str, value: str) -> None:
    with pytest.raises(ValueError, match=f"'line' has {setting} {value!r}"):
        block_queue(make_context(0.0, 10.0), **{setting: value})
