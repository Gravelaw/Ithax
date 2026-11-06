"""The ``sink`` block (spec 2 "Block reference" and "Statistic definitions"; AKS-98).

Removes the item and records its statistics: ``count`` and ``throughput`` count items
reaching the sink after warm-up (from the warm-up instant on), ``cycle_time.mean`` is the
time from creation to the sink over those items, and the item stops counting as work in
progress.
"""

import math

import pytest
from conftest import ContextMaker, recorder

from lcsim.engines.process.blocks import Context, Item, Sink
from lcsim.model.catalogue import PROCESS_TYPES
from lcsim.model.streams import generator_for


def sink(context: Context) -> Sink:
    return Sink("exit", {}, context, generator_for(7, 0, "exit"))


def arrive(context: Context, block: Sink, at: float, created: float) -> None:
    def deliver(_event: object) -> None:
        block.receive(Item(created=created, arrived=created))

    context.env.timeout(at).callbacks.append(deliver)


def test_items_reaching_the_sink_after_warm_up_are_counted(make_context: ContextMaker) -> None:
    context = make_context(10.0, 50.0)
    context.wip.set(0.0, 3.0)  # three items in the system from the start
    block = sink(context)
    arrive(context, block, at=5.0, created=0.0)  # before warm-up: not counted
    arrive(context, block, at=10.0, created=4.0)  # at the warm-up instant: counted
    arrive(context, block, at=30.0, created=2.0)
    context.env.run(until=50.0)
    assert block.metrics() == {"throughput": 2 / 40, "cycle_time.mean": 17.0, "count": 2.0}
    assert context.wip.value == 0.0
    # Work in progress over [10, 50): 1 item until 30, then none.
    assert context.wip.mean() == 20 / 40


def test_a_sink_no_item_reaches_has_no_cycle_time(make_context: ContextMaker) -> None:
    block = sink(make_context(0.0, 10.0))
    metrics = block.metrics()
    assert metrics["count"] == 0.0
    assert metrics["throughput"] == 0.0
    assert math.isnan(metrics["cycle_time.mean"])


def test_the_sink_reports_its_type_s_metrics(make_context: ContextMaker) -> None:
    assert tuple(sink(make_context(0.0, 1.0)).metrics()) == PROCESS_TYPES["sink"].metrics


def test_a_sink_has_no_output(make_context: ContextMaker) -> None:
    context = make_context(0.0, 1.0)
    with pytest.raises(ValueError, match="'exit' has no output port 'out'"):
        sink(context).connect("out", recorder(context))


def test_a_block_type_without_metrics_reports_none(make_context: ContextMaker) -> None:
    assert recorder(make_context(0.0, 1.0)).metrics() == {}
