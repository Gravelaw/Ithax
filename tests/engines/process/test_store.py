"""The ``store`` block (spec 2 "Block reference", "Store" and "Statistic definitions";
AKS-106).

Each item arriving takes one unit of stock and leaves at once; an item finding the stock at
zero waits, first in first out, until a delivery, and counts as a stock-out when it
arrives. After every withdrawal, and once at time 0, the store reviews its stock: when the
stock on hand plus on order is at or below ``reorder_point`` it places one order of
``order_quantity``, delivered after a ``lead_time`` drawn from the store's own stream.
Every case below is computed by hand, event by event, with constant times.
"""

from itertools import pairwise
from typing import Any

import pytest
import simpy
from conftest import (
    ContextMaker,
    ModelMaker,
    constant,
    metrics_of_model,
    model_document,
    recorder,
    series_of_model,
)

from ithax.engines.process.blocks import (
    BLOCK_TYPES,
    Context,
    Item,
    Stopped,
    Store,
    Transfers,
    Unbatch,
    sampler_from_json,
)
from ithax.engines.process.replication import run_replication
from ithax.engines.process.statistics import TimeWeighted, Window
from ithax.engines.process.translate import engine_input
from ithax.model.catalogue import PROCESS_TYPES
from ithax.model.loading import load_document
from ithax.model.streams import generator_for


def source(interarrival: str = "60 s", **settings: Any) -> dict[str, Any]:
    return {
        "id": "arrivals",
        "type": "source",
        "params": {"interarrival": constant(interarrival), **settings},
    }


def store(
    initial: int, reorder_point: int, order_quantity: int, lead_time: str, name: str = "shelf"
) -> dict[str, Any]:
    return {
        "id": name,
        "type": "store",
        "params": {
            "initial": initial,
            "reorder_point": reorder_point,
            "order_quantity": order_quantity,
            "lead_time": constant(lead_time),
        },
    }


def sink() -> dict[str, Any]:
    return {"id": "exit", "type": "sink", "params": {}}


LINE = [("arrivals.out", "shelf.in"), ("shelf.out", "exit.in")]


def block_store(context: Context, **settings: Any) -> Store:
    settings.setdefault("initial", 2)
    settings.setdefault("reorder_point", 0)
    settings.setdefault("order_quantity", 1)
    settings.setdefault("lead_time", {"dist": "constant", "value": 100.0})
    return Store("shelf", settings, context, generator_for(7, 0, "shelf"))


def depletion_line(make_model: ModelMaker, **experiment: Any) -> Any:
    """Arrivals every 60 s from 0 into a store of 2 with ``reorder_point`` 1,
    ``order_quantity`` 2 and a lead time of 150 s, then a sink, for 600 s."""
    experiment.setdefault("length", "600 s")
    return make_model([source(), store(2, 1, 2, "150 s"), sink()], LINE, **experiment)


def test_the_store_type_is_registered_with_its_metrics() -> None:
    assert BLOCK_TYPES["store"] is Store
    assert PROCESS_TYPES["store"].metrics == ("stock.mean", "stockouts", "orders")


def test_stock_depletes_reorders_and_releases_waiting_items(make_model: ModelMaker) -> None:
    """Item i arrives at 60i s. Item 0 leaves 1 on hand, at the reorder point: order 1 at
    0 s, due at 150 s. Item 1 takes the last unit (1 on hand plus 2 on order is above 1).
    Item 2 (120 s) finds none: a stock-out. At 150 s the delivery of 2 releases item 2,
    leaving 1, at the reorder point: order 2, due at 300 s. Item 3 (180 s) takes the last
    unit; item 4 (240 s) is a stock-out. At 300 s the delivery (scheduled at 150 s) runs
    before item 5's arrival (scheduled at 240 s): item 4 takes a unit, leaving 1, order 3
    due at 450 s; item 5 takes the other. Items 6 and 7 are stock-outs; at 450 s both are
    released in order, item 6 leaving 1 (order 4, due at 600 s, the end, so it never
    arrives), item 7 leaving 0 with 2 on order. Items 8 and 9 are stock-outs."""
    metrics = metrics_of_model(depletion_line(make_model))
    assert metrics["shelf.orders"] == 4 / 600  # at 0, 150, 300 and 450 s
    assert metrics["shelf.stockouts"] == 6.0  # items 2, 4, 6, 7, 8 and 9
    # On hand: 1 over [0, 60), 1 over [150, 180), 0 otherwise (each delivery is taken at
    # its instant).
    assert metrics["shelf.stock.mean"] == (60 + 30) / 600
    assert metrics["exit.count"] == 8.0  # items 0 to 7
    assert metrics["exit.cycle_time.mean"] == (0 + 0 + 30 + 0 + 60 + 0 + 90 + 30) / 8
    assert metrics["arrivals.discarded"] == 0.0  # a store always accepts


@pytest.mark.parametrize(
    ("warmup", "orders", "stockouts", "area"),
    [
        # At 120 s: item 2's stock-out (at the warm-up) counts; the orders at 150, 300 and
        # 450 s count; on hand 1 over [150, 180).
        ("120 s", 3, 6, 30),
        # At 150 s: item 2's stock-out (120 s) does not count although it is released at
        # 150 s; the order at exactly 150 s counts.
        ("150 s", 3, 5, 30),
        # At 30 s: the order at 0 s does not count; on hand 1 over [30, 60) and
        # [150, 180).
        ("30 s", 3, 6, 60),
    ],
)
def test_the_warm_up_boundary(
    make_model: ModelMaker, warmup: str, orders: int, stockouts: int, area: float
) -> None:
    """Spec 2 "Statistic definitions": orders count when placed and stock-outs when the
    item arrives, at or after warm-up; stock is integrated over the observed period."""
    metrics = metrics_of_model(depletion_line(make_model, warmup=warmup))
    period = 600 - float(warmup.split()[0])
    assert metrics["shelf.orders"] == orders / period
    assert metrics["shelf.stockouts"] == float(stockouts)
    assert metrics["shelf.stock.mean"] == area / period


def test_an_empty_store_orders_at_time_0(make_model: ModelMaker) -> None:
    """A store of 0 with ``reorder_point`` 0 and ``order_quantity`` 3 (lead time 100 s)
    reviews at 0 s, before the first arrival: order 1 at 0 s, due at 100 s. Items 0 and 1
    are stock-outs, released at 100 s in order (3 → 2 → 1). Item 2 (120 s) takes the last
    unit: order 2, due at 220 s. Item 3 (180 s) is a stock-out, released at 220 s (3 → 2);
    item 4 (240 s) leaves 1. The run ends at 300 s."""
    model = make_model([source(), store(0, 0, 3, "100 s"), sink()], LINE, length="300 s")
    metrics = metrics_of_model(model)
    assert metrics["shelf.orders"] == 2 / 300
    assert metrics["shelf.stockouts"] == 3.0
    # On hand 0 over [0, 100), 1 over [100, 120), 0 over [120, 220), 2 over [220, 240),
    # 1 over [240, 300).
    assert metrics["shelf.stock.mean"] == (20 + 40 + 60) / 300
    assert metrics["exit.count"] == 5.0
    assert metrics["exit.cycle_time.mean"] == (100 + 40 + 0 + 40 + 0) / 5


def test_the_time_0_review_orders_only_at_or_below_the_reorder_point(
    make_model: ModelMaker,
) -> None:
    """With no arrival before the end (the first at 100 s, the run 50 s), only the 0 s
    review can order: a store of 0 with ``reorder_point`` 0 orders once, a store of 1 does
    not."""
    late = source(first_arrival="100 s")
    empty = make_model([late, store(0, 0, 3, "100 s"), sink()], LINE, length="50 s")
    assert metrics_of_model(empty)["shelf.orders"] == 1 / 50
    stocked = make_model([late, store(1, 0, 3, "100 s"), sink()], LINE, length="50 s")
    assert metrics_of_model(stocked)["shelf.orders"] == 0.0


def test_several_orders_can_be_outstanding(make_model: ModelMaker) -> None:
    """A store of 6, ``reorder_point`` 5, ``order_quantity`` 2, lead time 1,000 s: items 0,
    2 and 4 each bring the stock on hand plus on order down to 5 (5 + 0, 3 + 2, 1 + 4), so
    three orders are outstanding by 240 s; none arrives before the end at 600 s. Item 5
    takes the last unit; items 6 to 9 are stock-outs."""
    model = make_model([source(), store(6, 5, 2, "1000 s"), sink()], LINE, length="600 s")
    metrics = metrics_of_model(model)
    assert metrics["shelf.orders"] == 3 / 600
    assert metrics["shelf.stockouts"] == 4.0
    assert metrics["shelf.stock.mean"] == 60 * (5 + 4 + 3 + 2 + 1) / 600


def test_a_position_below_the_reorder_point_orders_at_every_withdrawal(
    make_model: ModelMaker,
) -> None:
    """A "falls to" read as "at or below": a store of 3 with ``reorder_point`` 5 and
    ``order_quantity`` 1 (lead time 1,000 s) orders at the 0 s review (3 + 0) and after
    each of items 0, 1 and 2 (2 + 1, 1 + 2, 0 + 3), one order each time. Items 3 and 4 find
    no stock and withdraw nothing, so they trigger no review."""
    model = make_model([source(), store(3, 5, 1, "1000 s"), sink()], LINE, length="300 s")
    metrics = metrics_of_model(model)
    assert metrics["shelf.orders"] == 4 / 300
    assert metrics["shelf.stockouts"] == 2.0


def test_waiting_items_are_released_first_in_first_out(make_context: ContextMaker) -> None:
    """Three items reach an empty store at 0, 1 and 2 s; the order placed at the 0 s review
    arrives at 100 s with 2 units: the first two move on at 100 s in arrival order and the
    third waits for the next order (placed at 100 s, after the second withdrawal)."""
    context = make_context(0.0, 300.0)
    block = block_store(context, initial=0, reorder_point=0, order_quantity=2)
    out = recorder(context)
    block.connect("out", out)
    block.start()
    items = [Item(float(index), float(index)) for index in range(3)]

    def arrive() -> Any:
        for item in items:
            block.receive(item)
            yield context.env.timeout(1.0)

    context.env.process(arrive())
    context.env.run(until=150.0)
    assert out.items == items[:2]
    assert out.times == [100.0, 100.0]
    assert block.waiting_items() == 1
    context.env.run(until=250.0)
    assert out.items == items
    assert out.times == [100.0, 100.0, 200.0]
    assert block.metrics()["stockouts"] == 3.0
    # At 0 s and at 100 s, after the second withdrawal; at 200 s item 2 leaves 1 on hand.
    assert block.metrics()["orders"] == 2 / 300


def test_a_store_always_accepts_and_counts_items_waiting_for_stock(
    make_context: ContextMaker,
) -> None:
    """``shortest_queue`` reads a store's waiting items: those waiting for stock. An item
    that has its unit but is refused downstream waits in the next block's line instead."""
    context = make_context(0.0, 10.0)
    block = block_store(context, initial=1)
    out = recorder(context, open=False)
    block.connect("out", out)
    for _ in range(3):
        assert block.accepts()
        block.receive(Item(0.0, 0.0))
    assert block.waiting_items() == 2
    assert len(out.blocked) == 1


def test_an_item_refused_downstream_keeps_its_unit_and_waits(make_model: ModelMaker) -> None:
    """Arrivals every 60 s into a store of 10 (no reorder at ``reorder_point`` 0 before the
    end), then a server of service 100 s with ``queue_capacity`` 0, 400 s. Every item takes
    a unit when it arrives (10 → 3 by 360 s); items refused by the busy server wait at the
    store in order and move as it frees: the server serves [0, 100), [100, 200),
    [200, 300), [300, 400). Nothing is discarded."""
    components = [
        source(),
        store(10, 0, 5, "1000 s"),
        {
            "id": "till",
            "type": "server",
            "params": {"capacity": 1, "service": constant("100 s"), "queue_capacity": 0},
        },
        sink(),
    ]
    connections = [("arrivals.out", "shelf.in"), ("shelf.out", "till.in"), ("till.out", "exit.in")]
    metrics = metrics_of_model(make_model(components, connections, length="400 s"))
    assert metrics["arrivals.discarded"] == 0.0
    assert metrics["shelf.stockouts"] == 0.0
    assert metrics["shelf.orders"] == 0.0
    # On hand 9, 8, ..., 4 over 60 s each from 0 s, and 3 over [360, 400).
    assert metrics["shelf.stock.mean"] == (60 * (9 + 8 + 7 + 6 + 5 + 4) + 40 * 3) / 400
    assert metrics["till.utilization"] == 1.0
    assert metrics["exit.count"] == 3.0  # at 100, 200 and 300 s
    assert metrics["exit.cycle_time.mean"] == (100 + 140 + 180) / 3


def test_a_burst_from_an_unbatch(make_model: ModelMaker) -> None:
    """Arrivals every 60 s into a batch of 5 and an unbatch, then a store of 3 with
    ``reorder_point`` 0, ``order_quantity`` 5 and lead time 100 s, 600 s. At 240 s items 0
    to 4 reach the store together: 0, 1 and 2 take the 3 units (order at 240 s, due at
    340 s), 3 and 4 are stock-outs, released at 340 s. At 540 s items 5 to 9 arrive: 5, 6
    and 7 take the 3 units left (order at 540 s), 8 and 9 are stock-outs."""
    components = [
        source(),
        {"id": "pack", "type": "batch", "params": {"size": 5}},
        {"id": "unpack", "type": "unbatch", "params": {}},
        store(3, 0, 5, "100 s"),
        sink(),
    ]
    connections = [
        ("arrivals.out", "pack.in"),
        ("pack.out", "unpack.in"),
        ("unpack.out", "shelf.in"),
        ("shelf.out", "exit.in"),
    ]
    metrics = metrics_of_model(make_model(components, connections, length="600 s"))
    assert metrics["shelf.orders"] == 2 / 600
    assert metrics["shelf.stockouts"] == 4.0
    # On hand 3 over [0, 240) and [340, 540), 0 otherwise.
    assert metrics["shelf.stock.mean"] == (3 * 240 + 3 * 200) / 600
    assert metrics["exit.count"] == 8.0
    cycle = [240, 180, 120, 340 - 180, 340 - 240, 240, 180, 120]
    assert metrics["exit.cycle_time.mean"] == sum(cycle) / 8


def test_a_burst_through_a_long_chain_of_stores_does_not_recurse(
    make_context: ContextMaker,
) -> None:
    """An unbatch of 400 items into a line of 400 stores of 400, then a block that takes
    everything: every item gets through at the same instant, in order, without nesting one
    call per store."""
    context = make_context(0.0, 10.0)
    unpack = Unbatch("unpack", {}, context, generator_for(7, 0, "unpack"))
    stores = [
        Store(
            f"s{index}",
            {
                "initial": 400,
                "reorder_point": 0,
                "order_quantity": 1,
                "lead_time": {"dist": "constant", "value": 1.0},
            },
            context,
            generator_for(7, 0, f"s{index}"),
        )
        for index in range(400)
    ]
    out = recorder(context)
    unpack.connect("out", stores[0])
    for current, following in pairwise(stores):
        current.connect("out", following)
    stores[-1].connect("out", out)
    items = tuple(Item(0.0, 0.0) for _ in range(400))
    context.transfers.run(lambda: unpack.receive(Item(0.0, 0.0, contents=items)))
    assert out.items == list(items)
    assert all(block.waiting_items() == 0 for block in stores)


def test_a_delivery_releasing_many_items_into_a_chain_does_not_recurse(
    make_context: ContextMaker,
) -> None:
    """400 items wait at an empty store; one delivery of 400 releases them all into a line
    of 400 stores of 400 at the same instant."""
    context = make_context(0.0, 10.0)
    first = block_store(
        context,
        initial=0,
        reorder_point=0,
        order_quantity=400,
        lead_time={"dist": "constant", "value": 1.0},
    )
    stores = [
        Store(
            f"s{index}",
            {
                "initial": 400,
                "reorder_point": 0,
                "order_quantity": 1,
                "lead_time": {"dist": "constant", "value": 100.0},
            },
            context,
            generator_for(7, 0, f"s{index}"),
        )
        for index in range(400)
    ]
    out = recorder(context)
    first.connect("out", stores[0])
    for current, following in pairwise(stores):
        current.connect("out", following)
    stores[-1].connect("out", out)
    first.start()
    items = [Item(0.0, 0.0) for _ in range(400)]
    for item in items:
        first.receive(item)
    context.env.run(until=5.0)
    assert out.items == items
    assert out.times == [1.0] * 400


def test_a_store_feeding_itself_can_still_be_stopped() -> None:
    """A store whose ``out`` leads back to its own ``in``, with a lead time of 0 s, circles
    one item forever at 0 s: each pass takes a unit and each delivery is a new event. The
    replication's ``should_stop`` is still asked, and the run stops."""
    document = model_document(
        [source(max_items=1), store(1, 0, 1, "0 s")],
        [("arrivals.out", "shelf.in"), ("shelf.out", "shelf.in")],
        length="10 s",
    )
    result = load_document(document)
    assert result.model is not None
    asked: list[int] = []

    def should_stop() -> bool:
        asked.append(1)
        return len(asked) > 3

    assert run_replication(engine_input(result.model, "e"), 0, 0, should_stop) is None
    assert len(asked) == 4


def test_a_circling_store_stops_inside_one_event(make_context: ContextMaker) -> None:
    """A store of 10,000 feeding itself circles one item 10,000 times inside one event;
    each pass is a transfer step, so ``should_stop`` is asked there too."""
    window = Window(0.0, 10.0)
    context = Context(
        env=simpy.Environment(),
        window=window,
        wip=TimeWeighted(window),
        transfers=Transfers(lambda: True),
    )
    block = block_store(context, initial=10_000)
    block.connect("out", block)
    with pytest.raises(Stopped):
        context.transfers.run(lambda: block.receive(Item(0.0, 0.0)))


def test_lead_times_come_from_the_store_s_own_stream(
    make_context: ContextMaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec 1 "Random streams": the store draws each lead time when it places the order,
    from ``<seed>:<replication>:<store id>``. Three orders placed at 0 s arrive at the
    first three draws of that stream."""
    context = make_context(0.0, 1000.0)
    lead = {"dist": "exponential", "mean": 50.0}
    block = block_store(context, initial=3, reorder_point=2, order_quantity=1, lead_time=lead)
    block.connect("out", recorder(context))
    block.start()  # 3 is above 2: no order
    for _ in range(3):
        block.receive(Item(0.0, 0.0))  # 2 + 0, 1 + 1, 0 + 2: an order after each
    deliveries: list[float] = []
    deliver = block._deliver

    def recording() -> None:
        deliveries.append(block.now)
        deliver()

    monkeypatch.setattr(block, "_deliver", recording)
    context.env.run(until=1000.0)
    rng = generator_for(7, 0, "shelf")
    draw = sampler_from_json(lead)
    assert sorted(deliveries) == sorted(draw(rng) for _ in range(3))
    assert block.metrics()["orders"] == 3 / 1000


def test_the_store_s_draws_leave_other_streams_unchanged(make_model: ModelMaker) -> None:
    """Common random numbers: two models differing only in the store's lead time (constant
    or exponential) create exactly the same arrivals, since the store draws from its own
    stream only."""

    def model(lead_time: dict[str, str]) -> Any:
        components = [
            {
                "id": "arrivals",
                "type": "source",
                "params": {"interarrival": {"dist": "exponential", "mean": "60 s"}},
            },
            {
                "id": "shelf",
                "type": "store",
                "params": {
                    "initial": 5,
                    "reorder_point": 2,
                    "order_quantity": 5,
                    "lead_time": lead_time,
                },
            },
            sink(),
        ]
        return make_model(components, LINE, length="36000 s")

    fixed = metrics_of_model(model(constant("600 s")))
    drawn = metrics_of_model(model({"dist": "exponential", "mean": "600 s"}))
    assert fixed["arrivals.created"] == drawn["arrivals.created"] > 0
    assert fixed["shelf.orders"] > 0 and drawn["shelf.orders"] > 0


def test_the_time_series_of_a_store_is_its_stock(make_model: ModelMaker) -> None:
    """Spec 2 "Statistic definitions": the store's time-persistent statistic is its stock on
    hand, ``<store>.stock``, the value after the events of each instant."""
    model = make_model(
        [source(), store(0, 0, 3, "100 s"), sink()], LINE, length="300 s", record_interval="50 s"
    )
    series = series_of_model(model)
    assert list(series) == ["shelf.stock", "model.wip"]
    assert series["shelf.stock"] == [
        (0.0, 0.0),
        (50.0, 0.0),
        (100.0, 1.0),
        (150.0, 0.0),
        (200.0, 0.0),
        (250.0, 1.0),
    ]


def test_the_store_s_levels_and_metrics_before_any_event(make_context: ContextMaker) -> None:
    block = block_store(make_context(0.0, 10.0), initial=4)
    assert block.levels() == {"stock": 4.0}
    assert block.metrics() == {"stock.mean": 4.0, "stockouts": 0.0, "orders": 0.0}
