"""The ``delay`` block (spec 2 "Block reference" and "Blocking"; AKS-99).

Holds each item for a time drawn from the delay's own stream when the item arrives; no
queue and no capacity limit, so it always accepts and counts no waiting items. An item the
next block refuses stays in the delay, past its time, until space frees there.
"""

from collections.abc import Generator, Sequence
from typing import Any

import pytest
import simpy
from conftest import ContextMaker, Recorder, recorder

from ithax.engines.process.blocks import BLOCK_TYPES, Context, Delay, Item
from ithax.model.catalogue import PROCESS_TYPES
from ithax.model.streams import generator_for


def delay(context: Context, time: dict[str, Any], *, open: bool = True) -> tuple[Delay, Recorder]:
    block = Delay("walk", {"time": time}, context, generator_for(7, 0, "walk"))
    out = recorder(context, open=open)
    block.connect("out", out)
    return block, out


def feed(context: Context, block: Delay, times: Sequence[float]) -> list[Item]:
    items = [Item(created=time, arrived=time) for time in times]

    def run() -> Generator[simpy.Event, Any, None]:
        for item in items:
            yield context.env.timeout(item.created - context.env.now)
            block.receive(item)

    context.env.process(run())
    return items


def test_the_delay_type_is_registered() -> None:
    assert BLOCK_TYPES["delay"] is Delay


def test_each_item_is_held_for_the_sampled_time(make_context: ContextMaker) -> None:
    context = make_context(0.0, 100.0)
    block, out = delay(context, {"dist": "constant", "value": 30.0})
    items = feed(context, block, [0.0, 5.0, 50.0])
    context.env.run(until=100.0)
    assert out.items == items
    assert out.times == [30.0, 35.0, 80.0]


def test_there_is_no_capacity_limit(make_context: ContextMaker) -> None:
    """A thousand items at once all leave after the one delay time."""
    context = make_context(0.0, 100.0)
    block, out = delay(context, {"dist": "constant", "value": 10.0})
    feed(context, block, [0.0] * 1000)
    assert block.accepts()
    assert block.waiting_items() == 0
    context.env.run(until=100.0)
    assert out.times == [10.0] * 1000


def test_times_come_from_the_delay_s_own_stream_when_an_item_arrives(
    make_context: ContextMaker,
) -> None:
    """Items at 0, 100, 200, ...: the n-th draw of the stream is the n-th item's time."""
    context = make_context(0.0, 100_000.0)
    block, out = delay(context, {"dist": "exponential", "mean": 20.0})
    feed(context, block, [100.0 * n for n in range(50)])
    context.env.run(until=100_000.0)
    stream = generator_for(7, 0, "walk")
    expected = sorted(100.0 * n + stream.exponential(20.0) for n in range(50))
    assert sorted(out.times) == pytest.approx(expected, rel=0, abs=1e-9)


def test_a_refused_item_stays_in_the_delay_until_space_frees(
    make_context: ContextMaker,
) -> None:
    context = make_context(0.0, 100.0)
    block, out = delay(context, {"dist": "constant", "value": 10.0}, open=False)
    first, second = feed(context, block, [0.0, 1.0])
    context.env.run(until=50.0)
    assert out.items == []

    def reopen() -> Generator[simpy.Event, Any, None]:
        yield context.env.timeout(10.0)
        out.open = True
        out.space_freed()

    context.env.process(reopen())
    context.env.run(until=100.0)
    # Both move at 60 s, in the order they were refused.
    assert out.items == [first, second]
    assert out.times == [60.0, 60.0]


def test_the_delay_has_no_metrics(make_context: ContextMaker) -> None:
    block, _ = delay(make_context(0.0, 1.0), {"dist": "constant", "value": 1.0})
    assert block.metrics() == {}
    assert tuple(block.metrics()) == PROCESS_TYPES["delay"].metrics
    assert block.levels() == {}
