"""The ``resource_pool`` block and a server's ``pool`` (spec 2 "Block reference", "Pool" and
"Statistic definitions"; AKS-107).

A server with ``pool`` takes one of its own units first, then asks the pool for a unit; its
item's wait and service begin when it holds both, and both are released together when the
item moves on. Pool units go to the items asking, across every server, first come first
served. Every case below is computed by hand, event by event, with constant times.
"""

from collections.abc import Generator
from itertools import pairwise
from typing import Any

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

from lcsim.engines.process.blocks import (
    BLOCK_TYPES,
    Context,
    Item,
    ResourcePool,
    Server,
    Unbatch,
)
from lcsim.engines.process.replication import run_replication
from lcsim.engines.process.translate import engine_input
from lcsim.model.catalogue import PROCESS_TYPES
from lcsim.model.loading import load_document
from lcsim.model.streams import generator_for


def source(name: str = "arrivals", interarrival: str = "60 s", **settings: Any) -> dict[str, Any]:
    return {
        "id": name,
        "type": "source",
        "params": {"interarrival": constant(interarrival), **settings},
    }


def server(
    name: str = "till", capacity: int = 2, service: str = "100 s", **settings: Any
) -> dict[str, Any]:
    return {
        "id": name,
        "type": "server",
        "params": {"capacity": capacity, "service": constant(service), **settings},
    }


def pool(capacity: int = 1, name: str = "staff") -> dict[str, Any]:
    return {"id": name, "type": "resource_pool", "params": {"capacity": capacity}}


def sink(name: str = "exit") -> dict[str, Any]:
    return {"id": name, "type": "sink", "params": {}}


LINE = [("arrivals.out", "till.in"), ("till.out", "exit.in")]


def pooled_line(make_model: ModelMaker, **experiment: Any) -> Any:
    """Arrivals every 60 s from 0 into a server of 2 units with service 100 s and a pool of
    1, for 400 s: one item at a time is in service."""
    experiment.setdefault("length", "400 s")
    return make_model([source(), server(pool="staff"), pool(), sink()], LINE, **experiment)


def test_the_pool_type_is_registered_with_its_metric() -> None:
    assert BLOCK_TYPES["resource_pool"] is ResourcePool
    assert PROCESS_TYPES["resource_pool"].metrics == ("utilization",)


def test_service_begins_only_when_the_server_unit_and_the_pool_unit_are_held(
    make_model: ModelMaker,
) -> None:
    """Items at 0, 60, ..., 360 s. Item 0 serves 0 to 100; item 1 takes the second server
    unit at 60 and waits for the pool until 100, serving to 200; item 2 takes a unit at 120
    and serves 200 to 300; item 3 arrives at 180 to find both units held, takes one at
    200 and serves 300 to 400, the end. At 300 item 2's end (scheduled at 200) runs before
    item 5's arrival (scheduled at 240), so item 4 takes the freed unit first.

    Waiting, not in service (an item holding a server unit while it waits for the pool
    counts): 1 over [60, 100), 1 over [120, 180), 2 over [180, 200), 1 over [200, 240),
    2 over [240, 360), 3 over [360, 400). One server unit is busy the whole time."""
    metrics = metrics_of_model(pooled_line(make_model))
    assert metrics["till.wait.mean"] == (0 + 40 + 80 + 120) / 4
    assert metrics["till.queue_length.mean"] == (40 + 60 + 2 * 20 + 40 + 2 * 120 + 3 * 40) / 400
    assert metrics["till.queue_length.max"] == 3.0
    assert metrics["till.utilization"] == 400 / (2 * 400)
    assert metrics["staff.utilization"] == 1.0
    assert metrics["till.availability"] == 1.0
    assert metrics["till.scheduled_fraction"] == 1.0
    assert metrics["exit.count"] == 3.0
    assert metrics["exit.cycle_time.mean"] == (100 + 140 + 180) / 3


def test_the_warm_up_boundary(make_model: ModelMaker) -> None:
    """With warm-up at 100 s, item 1's service starting at exactly 100 s counts; the pool
    is busy over the whole observed period."""
    metrics = metrics_of_model(pooled_line(make_model, warmup="100 s"))
    assert metrics["till.wait.mean"] == (40 + 80 + 120) / 3
    assert metrics["staff.utilization"] == 1.0
    assert metrics["till.queue_length.mean"] == (60 + 2 * 20 + 40 + 2 * 120 + 3 * 40) / 300


def test_pool_units_go_first_come_first_served_across_servers(make_model: ModelMaker) -> None:
    """A pool of 1 shared by ``a`` (2 units) and ``b`` (1 unit), service 100 s on both. ``a``
    gets items at 0 and 30 s, ``b`` one at 10 s. Item a0 serves 0 to 100; b0 asks the pool
    at 10 and a1 at 30, so when a0 releases the pool at 100 it goes to b0 (100 to 200),
    not to a1 on the server just freed; a1 serves 200 to 300."""
    components = [
        source("in_a", "30 s", max_items=2),
        source("in_b", "1000 s", first_arrival="10 s", max_items=1),
        server("a", capacity=2, pool="staff"),
        server("b", capacity=1, pool="staff"),
        pool(),
        sink("out_a"),
        sink("out_b"),
    ]
    connections = [
        ("in_a.out", "a.in"),
        ("in_b.out", "b.in"),
        ("a.out", "out_a.in"),
        ("b.out", "out_b.in"),
    ]
    metrics = metrics_of_model(make_model(components, connections, length="400 s"))
    assert metrics["a.wait.mean"] == (0 + 170) / 2
    assert metrics["b.wait.mean"] == 90.0
    assert metrics["staff.utilization"] == 300 / 400
    assert metrics["out_b.cycle_time.mean"] == 190.0
    assert metrics["out_a.cycle_time.mean"] == (100 + 270) / 2


def test_a_finished_item_refused_downstream_keeps_its_pool_unit(make_model: ModelMaker) -> None:
    """A pool of 1 shared by ``a`` (service 50 s, into ``slow``, 1 unit, ``queue_capacity``
    0, service 300 s) and ``b`` (service 50 s, into a sink). Item a0 serves 0 to 50 and
    moves to ``slow`` (50 to 350); a1 (arrived 10) serves 50 to 100, then is refused and
    holds both its units until ``slow`` frees at 350. b0 arrives at 120 and gets the pool
    only then: wait 230 s, serving 350 to 400."""
    components = [
        source("in_a", "10 s", max_items=2),
        source("in_b", "1000 s", first_arrival="120 s", max_items=1),
        server("a", capacity=1, service="50 s", pool="staff"),
        server("slow", capacity=1, service="300 s", queue_capacity=0),
        server("b", capacity=1, service="50 s", pool="staff"),
        pool(),
        sink("out_a"),
        sink("out_b"),
    ]
    connections = [
        ("in_a.out", "a.in"),
        ("a.out", "slow.in"),
        ("slow.out", "out_a.in"),
        ("in_b.out", "b.in"),
        ("b.out", "out_b.in"),
    ]
    metrics = metrics_of_model(make_model(components, connections, length="600 s"))
    assert metrics["b.wait.mean"] == 230.0
    assert metrics["a.wait.mean"] == (0 + 40) / 2
    # Busy pool units: a0 over [0, 50), a1 over [50, 350) (blocked from 100), b0 [350, 400).
    assert metrics["staff.utilization"] == 400 / 600
    # A blocked unit is busy (spec 2 "Blocking").
    assert metrics["a.utilization"] == 350 / 600
    assert metrics["out_b.count"] == 1.0
    assert metrics["in_a.discarded"] == 0.0


def test_a_schedule_on_a_pool_changes_its_capacity(make_model: ModelMaker) -> None:
    """A pool of 2 with a schedule of 1 over [0, 100) and 2 over [100, 200), every 200 s;
    a server of 2 units, service 150 s, items at 0 and 10 s. Item 0 serves 0 to 150; item 1
    waits for the second pool unit until 100 and serves 100 to 250. Busy pool units, at
    most the available capacity: 100 + 2 x 50 + 50 + 50 = 300 over 100 + 200 + 100 = 400
    available."""
    components = [
        source(interarrival="10 s", max_items=2),
        server(service="150 s", pool="staff"),
        pool(2),
        {
            "id": "rota",
            "type": "schedule",
            "params": {
                "target": "staff",
                "period": "200 s",
                "shifts": [
                    {"start": "0 s", "end": "100 s", "capacity": 1},
                    {"start": "100 s", "end": "200 s", "capacity": 2},
                ],
            },
        },
        sink(),
    ]
    model = make_model(components, LINE, length="300 s", record_interval="50 s")
    metrics = metrics_of_model(model)
    assert metrics["till.wait.mean"] == (0 + 90) / 2
    assert metrics["staff.utilization"] == 300 / 400
    # The server's own capacity has no schedule.
    assert metrics["till.scheduled_fraction"] == 1.0
    assert metrics["till.utilization"] == (150 + 150) / (2 * 300)
    # Busy units, at most the available capacity, over the available capacity; samples
    # after the events of their instant.
    assert series_of_model(model)["staff.utilization"] == [
        (0.0, 1.0),
        (50.0, 1.0),
        (100.0, 1.0),
        (150.0, 0.5),
        (200.0, 1.0),
        (250.0, 0.0),
    ]


def test_the_pool_s_time_series_without_a_schedule(make_model: ModelMaker) -> None:
    """Busy pool units over its capacity; the server's ``queue_length`` counts the item
    waiting for the pool."""
    series = series_of_model(pooled_line(make_model, record_interval="100 s"))
    assert series["staff.utilization"] == [(t, 1.0) for t in (0.0, 100.0, 200.0, 300.0)]
    assert series["till.queue_length"] == [(0.0, 0.0), (100.0, 0.0), (200.0, 1.0), (300.0, 2.0)]
    assert series["till.utilization"] == [(t, 0.5) for t in (0.0, 100.0, 200.0, 300.0)]
    assert list(series) == [
        "till.queue_length",
        "till.utilization",
        "staff.utilization",
        "model.wip",
    ]


def blocks_with_a_pool(
    context: Context, capacity: int = 2, pool_capacity: int = 1, queue_capacity: int | None = None
) -> tuple[Server, ResourcePool]:
    settings: dict[str, Any] = {
        "capacity": capacity,
        "service": {"dist": "constant", "value": 100.0},
        "pool": "staff",
    }
    if queue_capacity is not None:
        settings["queue_capacity"] = queue_capacity
    till = Server("till", settings, context, generator_for(7, 0, "till"))
    staff = ResourcePool(
        "staff", {"capacity": pool_capacity}, context, generator_for(7, 0, "staff")
    )
    blocks = {"till": till, "staff": staff}
    for block in blocks.values():
        block.bind(blocks)
    till.connect("out", recorder(context))
    return till, staff


def test_waiting_items_and_accepts_of_a_pooled_server(make_context: ContextMaker) -> None:
    """``shortest_queue`` counts an item holding a server unit while it waits for the pool;
    ``queue_capacity`` counts only the items waiting for a server unit."""
    context = make_context(0.0, 1000.0)
    till, staff = blocks_with_a_pool(context, queue_capacity=1)
    assert till.accepts() and till.waiting_items() == 0
    context.transfers.run(lambda: till.receive(Item(0.0, 0.0)))  # in service
    context.transfers.run(lambda: till.receive(Item(0.0, 0.0)))  # holds a unit, waits
    assert till.waiting_items() == 1
    assert till.accepts()  # no item waits for a server unit yet
    context.transfers.run(lambda: till.receive(Item(0.0, 0.0)))  # waits for a unit
    assert till.waiting_items() == 2
    assert not till.accepts()
    assert staff.waiting_items() == 0 and staff.ports() == ()
    assert till.levels() == {"queue_length": 2.0, "utilization": 0.5}
    assert staff.levels() == {"utilization": 1.0}


def test_a_burst_into_a_pooled_server_starts_in_arrival_order(
    make_context: ContextMaker,
) -> None:
    """400 items from an unbatch at one instant into a server of 400 units with a pool of
    400: all start at once, in order, without nesting a call per item."""
    context = make_context(0.0, 1000.0)
    till, staff = blocks_with_a_pool(context, capacity=400, pool_capacity=400)
    out = recorder(context, name="out")
    till.connect("out", out)
    unpack = Unbatch("unpack", {}, context, generator_for(7, 0, "unpack"))
    unpack.connect("out", till)
    items = tuple(Item(0.0, 0.0) for _ in range(400))
    context.transfers.run(lambda: unpack.receive(Item(0.0, 0.0, contents=items)))
    assert till.busy == 400 and till.waiting_items() == 0
    assert staff.levels() == {"utilization": 1.0}
    context.env.run(until=200.0)
    assert out.items == list(items)
    assert out.times == [100.0] * 400


def test_a_long_chain_of_pooled_servers_frees_without_recursion(
    make_context: ContextMaker,
) -> None:
    """A line of 400 servers of one unit, ``queue_capacity`` 0, all sharing a pool of 400,
    with a closed block at the end: 400 items fill it and block. When the end opens, every
    item moves on at that instant through transfer steps, without nesting."""
    context = make_context(0.0, 1000.0)
    staff = ResourcePool("staff", {"capacity": 400}, context, generator_for(7, 0, "staff"))
    servers = [
        Server(
            f"s{index}",
            {
                "capacity": 1,
                "queue_capacity": 0,
                "service": {"dist": "constant", "value": 0.0},
                "pool": "staff",
            },
            context,
            generator_for(7, 0, f"s{index}"),
        )
        for index in range(400)
    ]
    blocks = {"staff": staff, **{block.id: block for block in servers}}
    for block in blocks.values():
        block.bind(blocks)
    end = recorder(context, open=False, name="end")
    for current, following in pairwise(servers):
        current.connect("out", following)
    servers[-1].connect("out", end)

    def feed() -> Generator[simpy.Event, Any, None]:
        for _ in range(400):
            context.transfers.run(lambda: servers[0].receive(Item(0.0, 0.0)))
            yield context.env.timeout(1.0)

    context.env.process(feed())
    context.env.run(until=500.0)
    assert sum(block.busy for block in servers) == 400
    end.open = True
    context.transfers.run(end.space_freed)
    context.env.run(until=600.0)
    assert len(end.items) == 400


def test_a_loop_through_a_pooled_server_can_still_be_stopped() -> None:
    """A pooled server with 0 s service routed back to itself circles one item forever at
    0 s; the replication's ``should_stop`` is still asked and the run stops."""
    document = model_document(
        [source(max_items=1), server(capacity=1, service="0 s", pool="staff"), pool()],
        [("arrivals.out", "till.in"), ("till.out", "till.in")],
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


def test_a_pool_draws_nothing_so_other_streams_are_unchanged(make_model: ModelMaker) -> None:
    """Common random numbers: adding a pool of ample capacity to a server with exponential
    times changes no result of the other components."""
    exponential = {"dist": "exponential", "mean": "50 s"}
    plain = [source(), server(capacity=1), sink()]
    plain[0]["params"]["interarrival"] = {"dist": "exponential", "mean": "60 s"}
    plain[1]["params"]["service"] = exponential
    pooled = [dict(component) for component in plain]
    pooled[1] = {**plain[1], "params": {**plain[1]["params"], "pool": "staff"}}
    pooled.insert(2, pool(5))
    before = metrics_of_model(make_model(plain, LINE, length="3600 s"))
    after = metrics_of_model(make_model(pooled, LINE, length="3600 s"))
    assert {key: value for key, value in after.items() if not key.startswith("staff.")} == before


def test_a_pool_with_no_capacity_over_the_period_has_no_utilization(
    make_model: ModelMaker,
) -> None:
    """A pool whose only shift has capacity 0 is never available: its utilization is
    undefined (NaN), the pooled server's items wait for ever, and its time series is 0."""
    components = [
        source(max_items=1),
        server(pool="staff"),
        pool(),
        {
            "id": "rota",
            "type": "schedule",
            "params": {
                "target": "staff",
                "period": "100 s",
                "shifts": [{"start": "0 s", "end": "100 s", "capacity": 0}],
            },
        },
        sink(),
    ]
    model = make_model(components, LINE, length="300 s", record_interval="100 s")
    metrics = metrics_of_model(model)
    assert metrics["staff.utilization"] != metrics["staff.utilization"]  # NaN
    assert metrics["till.wait.mean"] != metrics["till.wait.mean"]  # no service started
    assert metrics["till.queue_length.mean"] == 1.0
    assert series_of_model(model)["staff.utilization"] == [(0.0, 0.0), (100.0, 0.0), (200.0, 0.0)]
