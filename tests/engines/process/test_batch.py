"""The ``batch`` block (spec 2 "Block reference", "Batch timeout" and "Statistic
definitions"; AKS-105).

A batch collects ``size`` items and releases them as one unit, whose creation time is its
first item's. With ``timeout``, a partial batch is released when the timeout has elapsed
since its first item arrived. A batch always accepts: a formed batch the next block refuses
waits for space while the next one collects. ``<batch>.wait.mean`` runs from an item's
arrival at the batch to the moment its batch moves on, over items whose batch moves on after
warm-up. Every case below is computed by hand, event by event, with constant times.
"""

from collections.abc import Generator, Sequence
from typing import Any

import pytest
import simpy
from conftest import ContextMaker, ModelMaker, constant, metrics_of_model, recorder

from lcsim.engines.process.blocks import BLOCK_TYPES, Batch, Context, Item
from lcsim.model.catalogue import PROCESS_TYPES
from lcsim.model.streams import generator_for


def source(interarrival: str) -> dict[str, Any]:
    return {"id": "arrivals", "type": "source", "params": {"interarrival": constant(interarrival)}}


def batch(**settings: Any) -> dict[str, Any]:
    return {"id": "pack", "type": "batch", "params": settings}


def sink() -> dict[str, Any]:
    return {"id": "exit", "type": "sink", "params": {}}


def unbatch() -> dict[str, Any]:
    return {"id": "unpack", "type": "unbatch", "params": {}}


def block_batch(context: Context, **settings: Any) -> Batch:
    settings.setdefault("size", 2)
    return Batch("pack", settings, context, generator_for(7, 0, "pack"))


def feed(context: Context, block: Batch, times: Sequence[float]) -> list[Item]:
    """Sends one item to ``block`` at each of ``times``; returns the items."""
    items = [Item(created=time, arrived=time) for time in times]

    def run() -> Generator[simpy.Event, Any, None]:
        for item in items:
            yield context.env.timeout(item.created - context.env.now)
            block.receive(item)

    context.env.process(run())
    return items


def test_the_batch_type_is_registered_with_its_metric() -> None:
    assert BLOCK_TYPES["batch"] is Batch
    assert PROCESS_TYPES["batch"].metrics == ("wait.mean",)


def test_a_batch_collects_size_items_and_releases_them_as_one(
    make_context: ContextMaker,
) -> None:
    """Size 3, items at 0, 10, 30, 40, 50 and 60 s: batches leave at 30 and 60 s, each as
    one unit holding its items in arrival order, created when its first item was."""
    context = make_context(0.0, 100.0)
    block = block_batch(context, size=3)
    out = recorder(context)
    block.connect("out", out)
    items = feed(context, block, [0.0, 10.0, 30.0, 40.0, 50.0, 60.0])
    context.env.run(until=100.0)
    assert out.times == [30.0, 60.0]
    first, second = out.items
    assert first.contents == tuple(items[:3]) and second.contents == tuple(items[3:])
    assert (first.created, second.created) == (0.0, 40.0)
    assert first.count() == 3
    assert block.metrics()["wait.mean"] == (30 + 20 + 0 + 20 + 10 + 0) / 6


def test_a_batch_cycle_time_is_its_first_item_s(make_model: ModelMaker) -> None:
    """Arrivals every 60 s from 0 into a batch of 3 and straight to a sink, 600 s: batches
    of items (0, 1, 2), (3, 4, 5) and (6, 7, 8) reach the sink at 120, 300 and 480 s. The
    sink counts each batch once, with the cycle time of its first item; the items leave work
    in progress when their batch reaches the sink."""
    components = [source("60 s"), batch(size=3), sink()]
    connections = [("arrivals.out", "pack.in"), ("pack.out", "exit.in")]
    metrics = metrics_of_model(make_model(components, connections, length="600 s"))
    assert metrics["exit.count"] == 3.0
    assert metrics["exit.throughput"] == 3 / 600
    assert metrics["exit.cycle_time.mean"] == 120.0
    assert metrics["pack.wait.mean"] == (120 + 60 + 0) / 3
    # Each batch's items are present for 120, 60 and 0 s; item 9 from 540 s to the end.
    assert metrics["model.wip.mean"] == (3 * (120 + 60 + 0) + 60) / 600


def test_items_after_an_unbatch_keep_their_own_cycle_times(make_model: ModelMaker) -> None:
    """The same arrivals through a batch of 3 and an unbatch: the sink counts 9 items, each
    with its own cycle time, equal to its wait at the batch."""
    components = [source("60 s"), batch(size=3), unbatch(), sink()]
    connections = [
        ("arrivals.out", "pack.in"),
        ("pack.out", "unpack.in"),
        ("unpack.out", "exit.in"),
    ]
    metrics = metrics_of_model(make_model(components, connections, length="600 s"))
    assert metrics["exit.count"] == 9.0
    assert metrics["exit.throughput"] == 9 / 600
    assert metrics["exit.cycle_time.mean"] == 60.0
    assert metrics["pack.wait.mean"] == 60.0
    assert metrics["arrivals.discarded"] == 0.0
    assert metrics["model.wip.mean"] == (3 * (120 + 60 + 0) + 60) / 600


def test_a_timeout_releases_a_partial_batch(make_model: ModelMaker) -> None:
    """Size 3, timeout 90 s, arrivals every 60 s: each batch starts with one item, gets a
    second 60 s later and is released at 90 s, as a pair. Pairs leave at 90, 210, 330, 450
    and 570 s."""
    components = [source("60 s"), batch(size=3, timeout="90 s"), unbatch(), sink()]
    connections = [
        ("arrivals.out", "pack.in"),
        ("pack.out", "unpack.in"),
        ("unpack.out", "exit.in"),
    ]
    metrics = metrics_of_model(make_model(components, connections, length="600 s"))
    assert metrics["exit.count"] == 10.0
    assert metrics["pack.wait.mean"] == (90 + 30) / 2
    assert metrics["exit.cycle_time.mean"] == (90 + 30) / 2


def test_a_batch_filled_before_its_timeout_cancels_that_timeout(
    make_context: ContextMaker,
) -> None:
    """Size 2, timeout 100 s, items every 40 s: the first batch fills at 40 s. The second
    starts at 80 s; the first batch's timeout, due at 100 s, must not release it, so it
    fills at 120 s. Batches leave at 40, 120 and 200 s."""
    context = make_context(0.0, 210.0)
    block = block_batch(context, size=2, timeout=100.0)
    out = recorder(context)
    block.connect("out", out)
    feed(context, block, [0.0, 40.0, 80.0, 120.0, 160.0, 200.0])
    context.env.run(until=210.0)
    assert out.times == [40.0, 120.0, 200.0]
    assert [unit.count() for unit in out.items] == [2, 2, 2]


def test_a_batch_of_one_with_a_timeout_leaves_at_once(make_context: ContextMaker) -> None:
    context = make_context(0.0, 100.0)
    block = block_batch(context, size=1, timeout=5.0)
    out = recorder(context)
    block.connect("out", out)
    feed(context, block, [0.0, 2.0])
    context.env.run(until=100.0)
    assert out.times == [0.0, 2.0]
    assert block.metrics()["wait.mean"] == 0.0


def test_without_a_timeout_a_partial_batch_waits_to_the_end(make_context: ContextMaker) -> None:
    """Items still collecting at the end are not counted in the wait."""
    context = make_context(0.0, 1000.0)
    block = block_batch(context, size=3)
    out = recorder(context)
    block.connect("out", out)
    feed(context, block, [0.0, 10.0])
    context.env.run(until=1000.0)
    assert out.items == []
    assert block.waits.count == 0
    assert block.metrics()["wait.mean"] != block.metrics()["wait.mean"]  # NaN


@pytest.mark.parametrize(
    ("warmup", "expected"), [(0.0, (10 + 0 + 200 + 0) / 4), (50.0, 100.0), (300.0, 100.0)]
)
def test_waits_count_for_batches_that_move_on_after_warm_up(
    make_context: ContextMaker, warmup: float, expected: float
) -> None:
    """Size 2, items at 0, 10, 100 and 300 s: batches leave at 10 and 300 s. Only a batch
    leaving at or after warm-up counts, with every item it holds, even one that arrived
    before warm-up (the item at 100 s, for a warm-up of 300 s)."""
    context = make_context(warmup, 400.0)
    block = block_batch(context, size=2)
    block.connect("out", recorder(context))
    feed(context, block, [0.0, 10.0, 100.0, 300.0])
    context.env.run(until=400.0)
    assert block.metrics()["wait.mean"] == expected


def test_a_refused_batch_waits_while_the_next_collects(make_model: ModelMaker) -> None:
    """Arrivals every 60 s into a batch of 2, then a server (service 200 s,
    ``queue_capacity`` 0), 600 s. Batch (0, 1) forms at 60 s and is served [60, 260). Batch
    (2, 3) forms at 180 s and is refused; it waits at the batch while (4, 5) collects and
    forms at 300 s, also refused. At 260 s (2, 3) moves ([260, 460)); at 460 s (4, 5) moves.
    The source never discards: a batch always accepts. Each item's wait ends when its batch
    moves on."""
    components = [
        source("60 s"),
        batch(size=2),
        {
            "id": "till",
            "type": "server",
            "params": {"capacity": 1, "service": constant("200 s"), "queue_capacity": 0},
        },
        sink(),
    ]
    connections = [("arrivals.out", "pack.in"), ("pack.out", "till.in"), ("till.out", "exit.in")]
    metrics = metrics_of_model(make_model(components, connections, length="600 s"))
    assert metrics["arrivals.discarded"] == 0.0
    assert metrics["pack.wait.mean"] == (60 + 0 + 140 + 80 + 220 + 160) / 6
    assert metrics["till.utilization"] == 540 / 600
    assert metrics["exit.count"] == 2.0  # batches at 260 and 460 s
    assert metrics["exit.cycle_time.mean"] == (260 + 340) / 2


def test_a_batch_has_no_time_series(make_context: ContextMaker) -> None:
    """Its one statistic, ``wait.mean``, is not time-persistent."""
    assert block_batch(make_context(0.0, 1.0)).levels() == {}
