"""The ``source`` block (spec 2 "Block reference"; AKS-98).

Creates one item, waits one interarrival time, repeats; the first item at
``first_arrival`` (0 s when absent); stops after ``max_items``; discards an item the next
block cannot accept and counts it; ``created`` and ``discarded`` count after warm-up, and
``discarded`` is a rate.
"""

import itertools
from typing import Any

import pytest
from conftest import ContextMaker, recorder

from lcsim.engines.process.blocks import Context, Item, Source
from lcsim.model.catalogue import PROCESS_TYPES
from lcsim.model.streams import generator_for


def source(context: Context, settings: dict[str, Any], component_id: str = "arrivals") -> Source:
    return Source(component_id, settings, context, generator_for(7, 0, component_id))


def constant(seconds: float) -> dict[str, object]:
    return {"dist": "constant", "value": seconds}


def test_the_first_item_is_created_at_time_zero(make_context: ContextMaker) -> None:
    context = make_context(0.0, 35.0)
    block, sink = source(context, {"interarrival": constant(10.0)}), recorder(context)
    block.connect("out", sink)
    block.start()
    context.env.run(until=35.0)
    assert sink.times == [0.0, 10.0, 20.0, 30.0]
    assert [item.created for item in sink.items] == sink.times
    assert block.created == 4


def test_first_arrival_delays_the_first_item(make_context: ContextMaker) -> None:
    context = make_context(0.0, 30.0)
    block = source(context, {"interarrival": constant(10.0), "first_arrival": 5.0})
    sink = recorder(context)
    block.connect("out", sink)
    block.start()
    context.env.run(until=30.0)
    assert sink.times == [5.0, 15.0, 25.0]


def test_max_items_stops_the_source(make_context: ContextMaker) -> None:
    context = make_context(0.0, 100.0)
    block = source(context, {"interarrival": constant(10.0), "max_items": 2})
    sink = recorder(context)
    block.connect("out", sink)
    block.start()
    context.env.run(until=100.0)
    assert sink.times == [0.0, 10.0]


def test_interarrival_times_come_from_the_source_s_own_stream_in_order(
    make_context: ContextMaker,
) -> None:
    context = make_context(0.0, 10_000.0)
    exponential = {"dist": "exponential", "mean": 60.0}
    block = source(context, {"interarrival": exponential, "max_items": 20})
    sink = recorder(context)
    block.connect("out", sink)
    block.start()
    context.env.run(until=10_000.0)
    stream = generator_for(7, 0, "arrivals")
    # One draw after each item but the last: max_items items need max_items - 1 draws.
    expected = list(itertools.accumulate((stream.exponential(60.0) for _ in range(19)), initial=0))
    assert sink.times == pytest.approx(expected, rel=0, abs=1e-9)


def test_created_counts_items_made_from_the_end_of_warm_up(make_context: ContextMaker) -> None:
    context = make_context(20.0, 40.0)
    block, sink = source(context, {"interarrival": constant(10.0)}), recorder(context)
    block.connect("out", sink)
    block.start()
    context.env.run(until=40.0)
    assert sink.times == [0.0, 10.0, 20.0, 30.0]
    assert block.metrics() == {"created": 2.0, "discarded": 0.0}
    assert context.wip.value == 4  # every item made is in the system


def test_an_item_the_next_block_refuses_is_discarded_and_never_counts_as_wip(
    make_context: ContextMaker,
) -> None:
    context = make_context(15.0, 55.0)
    block, closed = source(context, {"interarrival": constant(10.0)}), recorder(context, open=False)
    block.connect("out", closed)
    block.start()
    context.env.run(until=55.0)
    assert closed.items == []
    # Items at 0, 10, 20, 30, 40, 50; those from 20 on are observed: four, over 40 s.
    assert block.metrics() == {"created": 4.0, "discarded": 4 / 40}
    assert context.wip.value == 0
    assert context.wip.mean() == 0.0


def test_the_source_reports_its_type_s_metrics(make_context: ContextMaker) -> None:
    block = source(make_context(0.0, 1.0), {"interarrival": constant(1.0)})
    assert tuple(block.metrics()) == PROCESS_TYPES["source"].metrics


def test_a_source_has_no_input(make_context: ContextMaker) -> None:
    context = make_context(0.0, 1.0)
    block = source(context, {"interarrival": constant(1.0)})
    with pytest.raises(NotImplementedError, match="'arrivals' has no input port"):
        block.receive(Item(created=0.0, arrived=0.0))


def test_an_unconnected_or_unknown_port_is_refused(make_context: ContextMaker) -> None:
    context = make_context(0.0, 1.0)
    block = source(context, {"interarrival": constant(1.0)})
    with pytest.raises(ValueError, match=r"'arrivals\.out' is not connected"):
        block.target("out")
    with pytest.raises(ValueError, match="'arrivals' has no output port 'in'"):
        block.connect("in", recorder(context))
