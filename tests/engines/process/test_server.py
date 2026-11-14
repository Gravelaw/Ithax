"""The ``server`` block (spec 2 "Block reference" and "Statistic definitions"; AKS-98).

Items wait in the server's own queue, unlimited and first in, first out by default
(``lifo`` takes the latest), then hold one unit of capacity for one service time, drawn
from the server's own stream when the service starts. ``wait.mean`` covers items whose
service starts after warm-up; ``utilization`` is busy time over capacity times the period;
``queue_length`` counts waiting items, not those in service.
"""

import math
from collections.abc import Generator, Sequence
from typing import Any

import pytest
import simpy
from conftest import ContextMaker, Recorder, recorder

from ithax.engines.process.blocks import Context, Item, Server
from ithax.model.catalogue import PROCESS_TYPES
from ithax.model.streams import generator_for


def constant(seconds: float) -> dict[str, object]:
    return {"dist": "constant", "value": seconds}


def server(context: Context, **settings: Any) -> tuple[Server, Recorder]:
    settings.setdefault("capacity", 1)
    settings.setdefault("service", constant(10.0))
    block = Server("till", settings, context, generator_for(7, 0, "till"))
    out = recorder(context)
    block.connect("out", out)
    return block, out


def feed(context: Context, block: Server, times: Sequence[float]) -> list[Item]:
    """Sends one item to ``block`` at each of ``times``; returns the items."""
    items = [Item(created=time, arrived=time) for time in times]

    def run() -> Generator[simpy.Event, Any, None]:
        for item in items:
            yield context.env.timeout(item.created - context.env.now)
            block.receive(item)

    context.env.process(run())
    return items


def test_items_are_served_first_in_first_out(make_context: ContextMaker) -> None:
    context = make_context(0.0, 100.0)
    block, out = server(context)
    items = feed(context, block, [0.0, 2.0, 4.0])
    context.env.run(until=100.0)
    assert out.items == items
    assert out.times == [10.0, 20.0, 30.0]
    assert block.waits.count == 3
    assert block.metrics()["wait.mean"] == (0 + 8 + 16) / 3


def test_lifo_serves_the_latest_waiting_item_first(make_context: ContextMaker) -> None:
    context = make_context(0.0, 100.0)
    block, out = server(context, discipline="lifo")
    first, second, third = feed(context, block, [0.0, 1.0, 2.0])
    context.env.run(until=100.0)
    assert out.items == [first, third, second]
    assert out.times == [10.0, 20.0, 30.0]
    assert block.metrics()["wait.mean"] == (0 + 8 + 19) / 3


def test_capacity_two_serves_two_items_at_once(make_context: ContextMaker) -> None:
    context = make_context(0.0, 40.0)
    block, out = server(context, capacity=2)
    feed(context, block, [0.0, 0.0, 0.0])
    context.env.run(until=40.0)
    assert out.times == [10.0, 10.0, 20.0]
    metrics = block.metrics()
    assert metrics["wait.mean"] == 10 / 3
    # Busy units: 2 over [0, 10), 1 over [10, 20); capacity 2 over 40 s.
    assert metrics["utilization"] == 30 / 80
    assert metrics["queue_length.mean"] == 10 / 40
    assert metrics["queue_length.max"] == 1.0


def test_service_times_come_from_the_server_s_own_stream_when_service_starts(
    make_context: ContextMaker,
) -> None:
    context = make_context(0.0, 100_000.0)
    block, out = server(context, service={"dist": "exponential", "mean": 50.0})
    feed(context, block, [0.0] * 10)
    context.env.run(until=100_000.0)
    stream = generator_for(7, 0, "till")
    finish, expected = 0.0, []
    for _ in range(10):
        finish += stream.exponential(50.0)
        expected.append(finish)
    assert out.times == pytest.approx(expected, rel=0, abs=1e-9)


def test_statistics_count_only_the_observed_period(make_context: ContextMaker) -> None:
    # Service 10 s; items at 0, 2, 4 start at 0, 10 and 20. Warm-up ends at 10.
    context = make_context(10.0, 40.0)
    block, out = server(context)
    feed(context, block, [0.0, 2.0, 4.0])
    context.env.run(until=40.0)
    metrics = block.metrics()
    # Services starting at 10 (the warm-up instant) and 20 count: waits 8 and 16.
    assert metrics["wait.mean"] == 12.0
    # Busy over [10, 30) of the 30 s period.
    assert metrics["utilization"] == 20 / 30
    # Waiting: 1 over [10, 20) (the item from 4); the item from 2 leaves the queue at 10.
    assert metrics["queue_length.mean"] == 10 / 30
    # Two items waited before 10, but at 10 one starts: the value held from 10 is 1.
    assert metrics["queue_length.max"] == 1.0
    assert out.times == [10.0, 20.0, 30.0]


def test_a_server_with_no_service_started_after_warm_up_has_no_wait(
    make_context: ContextMaker,
) -> None:
    context = make_context(5.0, 50.0)
    block, _ = server(context, service=constant(100.0))
    feed(context, block, [0.0, 1.0])
    context.env.run(until=50.0)
    metrics = block.metrics()
    assert math.isnan(metrics["wait.mean"])
    assert metrics["utilization"] == 1.0
    assert metrics["queue_length.mean"] == 1.0


def test_the_server_reports_its_type_s_metrics(make_context: ContextMaker) -> None:
    block, _ = server(make_context(0.0, 1.0))
    metrics = block.metrics()
    assert tuple(metrics) == PROCESS_TYPES["server"].metrics
    assert metrics["availability"] == 1.0
    assert metrics["scheduled_fraction"] == 1.0


def test_an_unknown_discipline_is_refused(make_context: ContextMaker) -> None:
    with pytest.raises(ValueError, match="'till' has discipline 'priority'"):
        server(make_context(0.0, 1.0), discipline="priority")
