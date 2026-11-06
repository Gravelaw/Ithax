"""Blocking and ``queue_capacity`` (spec 2 "Blocking", "Source when blocked" and
"Statistic definitions"; AKS-99).

A server with ``queue_capacity`` accepts an item while a unit is free or fewer than
``queue_capacity`` items wait. A server whose finished item is refused keeps it on its unit,
which stays busy; a source discards; a delay and a branch keep the item. Blocked items move
as soon as space frees, in the order they were refused. Every case below is computed by
hand, event by event, with constant times.
"""

from collections.abc import Generator, Sequence
from itertools import pairwise
from typing import Any

import numpy
import pytest
import simpy
from conftest import ContextMaker, ModelMaker, constant, recorder

from lcsim.engines.process.blocks import Context, Item, Server
from lcsim.engines.process.replication import run_replication
from lcsim.engines.process.translate import engine_input
from lcsim.model.streams import generator_for


def never() -> bool:
    return False


def metrics_of(
    make_model: ModelMaker, components: Any, connections: Any, **experiment: Any
) -> dict[str, float]:
    engine = engine_input(make_model(components, connections, **experiment), "e")
    outcome = run_replication(engine, 0, 0, never)
    assert outcome is not None
    return {metric: value for metric, value, _ in outcome.rows}


def source(interarrival: str, **settings: Any) -> dict[str, Any]:
    return {
        "id": "arrivals",
        "type": "source",
        "params": {"interarrival": constant(interarrival), **settings},
    }


def server(name: str, service: str, **settings: Any) -> dict[str, Any]:
    return {
        "id": name,
        "type": "server",
        "params": {"capacity": 1, "service": constant(service), **settings},
    }


def sink(name: str = "exit") -> dict[str, Any]:
    return {"id": name, "type": "sink", "params": {}}


def constant_s(seconds: float) -> dict[str, object]:
    return {"dist": "constant", "value": seconds}


def stream(name: str) -> numpy.random.Generator:
    return generator_for(7, 0, name)


def block_server(context: Context, **settings: Any) -> Server:
    settings.setdefault("capacity", 1)
    settings.setdefault("service", {"dist": "constant", "value": 10.0})
    return Server("till", settings, context, generator_for(7, 0, "till"))


def feed(context: Context, block: Server, times: Sequence[float]) -> list[Item]:
    items = [Item(created=time, arrived=time) for time in times]

    def run() -> Generator[simpy.Event, Any, None]:
        for item in items:
            yield context.env.timeout(item.created - context.env.now)
            block.receive(item)

    context.env.process(run())
    return items


@pytest.mark.parametrize(
    ("capacity", "queue_capacity", "busy", "waiting", "accepts"),
    [
        (1, None, 1, 50, True),  # no queue_capacity: unlimited
        (1, 0, 0, 0, True),  # a free unit
        (1, 0, 1, 0, False),
        (2, 0, 1, 0, True),
        (1, 1, 1, 0, True),
        (1, 1, 1, 1, False),
        (2, 3, 2, 2, True),
        (2, 3, 2, 3, False),
    ],
)
def test_a_server_accepts_while_a_unit_is_free_or_its_queue_has_room(
    make_context: ContextMaker,
    capacity: int,
    queue_capacity: int | None,
    busy: int,
    waiting: int,
    accepts: bool,
) -> None:
    settings: dict[str, Any] = {"capacity": capacity}
    if queue_capacity is not None:
        settings["queue_capacity"] = queue_capacity
    block = block_server(make_context(0.0, 1.0), **settings)
    block.busy = busy
    block.waiting.extend(Item(0.0, 0.0) for _ in range(waiting))
    assert block.accepts() is accepts
    assert block.waiting_items() == waiting


def test_a_blocked_unit_stays_busy_until_its_item_moves(make_context: ContextMaker) -> None:
    """Service 10 s; the next block refuses until 25 s. The item finished at 10 s holds the
    unit until 25 s; the second item, waiting since 1 s, starts at 25 s."""
    context = make_context(0.0, 50.0)
    block = block_server(context)
    out = recorder(context, open=False)
    block.connect("out", out)
    first, second = feed(context, block, [0.0, 1.0])

    def reopen() -> Generator[simpy.Event, Any, None]:
        yield context.env.timeout(25.0)
        out.open = True
        out.space_freed()

    context.env.process(reopen())
    context.env.run(until=50.0)
    assert out.items == [first, second]
    assert out.times == [25.0, 35.0]
    metrics = block.metrics()
    assert metrics["utilization"] == 35 / 50  # busy, serving or holding, over [0, 35)
    assert metrics["wait.mean"] == (0 + 24) / 2
    assert metrics["queue_length.mean"] == 24 / 50  # the second waits over [1, 25)


def test_space_freed_moves_blocked_items_first_in_first_out(make_context: ContextMaker) -> None:
    """Two upstream servers blocked on one full server: the one refused first moves first,
    when the full server's unit frees; the other waits for the next free unit."""
    context = make_context(0.0, 1000.0)
    full = block_server(context, queue_capacity=0, service={"dist": "constant", "value": 100.0})
    out = recorder(context)
    full.connect("out", out)
    first_up = Server("up1", {"capacity": 1, "service": constant_s(20.0)}, context, stream("up1"))
    second_up = Server("up2", {"capacity": 1, "service": constant_s(10.0)}, context, stream("up2"))
    first_up.connect("out", full)
    second_up.connect("out", full)
    occupier = Item(0.0, 0.0)
    full.receive(occupier)  # busy over [0, 100)
    a, b = Item(0.0, 0.0), Item(0.0, 0.0)
    second_up.receive(b)  # finishes at 10 s, refused first
    first_up.receive(a)  # finishes at 20 s, refused second
    context.env.run(until=1000.0)
    assert out.items == [occupier, b, a]
    assert out.times == [100.0, 200.0, 300.0]
    # Each upstream unit is busy while it holds its blocked item.
    assert second_up.metrics()["utilization"] == 100 / 1000
    assert first_up.metrics()["utilization"] == 200 / 1000


def test_a_source_facing_a_full_server_discards(make_model: ModelMaker) -> None:
    """Arrivals every 60 s from 0; service 90 s; ``queue_capacity`` 0; 600 s. Items at 0,
    120, 240, 360 and 480 s are served; those at 60, 180, 300, 420 and 540 s find the unit
    busy and are discarded."""
    metrics = metrics_of(
        make_model,
        [source("60 s"), server("till", "90 s", queue_capacity=0), sink()],
        [("arrivals.out", "till.in"), ("till.out", "exit.in")],
        length="600 s",
    )
    assert metrics["arrivals.created"] == 10.0
    assert metrics["arrivals.discarded"] == 5 / 600
    assert metrics["exit.count"] == 5.0
    assert metrics["till.utilization"] == 450 / 600
    assert metrics["till.wait.mean"] == 0.0
    assert metrics["till.queue_length.max"] == 0.0
    assert metrics["model.wip.mean"] == 450 / 600  # a discarded item is never in WIP


def test_a_source_facing_a_queue_of_one_discards_when_it_is_full(make_model: ModelMaker) -> None:
    """Arrivals every 60 s, service 90 s, ``queue_capacity`` 1, 600 s. A departure due at
    the same instant as an arrival was scheduled first, so it runs first. Item i arrives at
    60i. Starts (end): 0 (90), 1 at 90 (180), 2 at 180 (270), 3 at 270 (360), 5 at 360
    (450), 6 at 450 (540), 8 at 540 (630). Item 4 (240 s) finds 3 waiting; item 7 (420 s)
    finds 6 waiting: both discarded. Item 9 arrives at 540, just after 8 starts, and waits."""
    metrics = metrics_of(
        make_model,
        [source("60 s"), server("till", "90 s", queue_capacity=1), sink()],
        [("arrivals.out", "till.in"), ("till.out", "exit.in")],
        length="600 s",
    )
    arrivals = {i: 60.0 * i for i in range(10)}
    starts = {0: 0.0, 1: 90.0, 2: 180.0, 3: 270.0, 5: 360.0, 6: 450.0, 8: 540.0}
    waiting = sum(starts.get(i, 600.0) - arrivals[i] for i in (1, 2, 3, 5, 6, 8, 9))
    assert metrics["arrivals.discarded"] == 2 / 600
    assert metrics["exit.count"] == 6.0  # ends at 90, 180, 270, 360, 450 and 540 s
    assert metrics["till.wait.mean"] == pytest.approx(
        sum(starts[i] - arrivals[i] for i in starts) / len(starts), rel=1e-12
    )
    assert metrics["till.queue_length.mean"] == pytest.approx(waiting / 600, rel=1e-12)
    assert metrics["till.queue_length.max"] == 1.0
    assert metrics["till.utilization"] == 1.0  # busy from 0 s to the end


def two_servers(make_model: ModelMaker) -> dict[str, float]:
    return metrics_of(
        make_model,
        [source("60 s"), server("a", "10 s"), server("b", "100 s", queue_capacity=0), sink()],
        [("arrivals.out", "a.in"), ("a.out", "b.in"), ("b.out", "exit.in")],
        length="400 s",
    )


def test_a_full_server_blocks_the_server_upstream(make_model: ModelMaker) -> None:
    """Arrivals every 60 s from 0 into a (service 10 s), then b (service 100 s,
    ``queue_capacity`` 0), 400 s. Item 0: a [0, 10), b [10, 110). Item 1: a from 60, done at
    70, refused, holds a's unit until b frees at 110; b [110, 210). Item 2 (120 s): a
    [120, 130), held until 210; b [210, 310). Item 3 (180 s) waits in a's queue until 210:
    a [210, 220), held until 310; b [310, 410). Item 4 (240 s) waits until 310: a
    [310, 320), held to the end. Items 5 (300 s) and 6 (360 s) wait in a's queue."""
    metrics = two_servers(make_model)
    assert metrics["arrivals.discarded"] == 0.0  # a's queue is unlimited
    # a's unit is busy, serving or holding, over [0, 10), [60, 110), [120, 400).
    assert metrics["a.utilization"] == 340 / 400
    assert metrics["b.utilization"] == 390 / 400
    assert metrics["a.wait.mean"] == (0 + 0 + 0 + 30 + 70) / 5
    assert metrics["b.wait.mean"] == 0.0  # an item reaches b when it moves
    # a's queue: item 3 [180, 210), 4 [240, 310), 5 [300, 400), 6 [360, 400).
    assert metrics["a.queue_length.mean"] == 240 / 400
    assert metrics["a.queue_length.max"] == 2.0
    assert metrics["b.queue_length.max"] == 0.0
    assert metrics["exit.count"] == 3.0  # at 110, 210 and 310 s
    assert metrics["exit.cycle_time.mean"] == (110 + 150 + 190) / 3
    present = [110, 210 - 60, 310 - 120, 400 - 180, 400 - 240, 400 - 300, 400 - 360]
    assert metrics["model.wip.mean"] == sum(present) / 400


def test_a_delay_holds_a_refused_item(make_model: ModelMaker) -> None:
    """Arrivals every 50 s into a delay of 10 s, then b (service 100 s,
    ``queue_capacity`` 0), 300 s. Item 0 reaches b at 10 s ([10, 110)). Item 1 leaves the
    delay's time at 60 s and is refused. At 110 s b's end (scheduled at 10 s) runs before
    item 2's delay end (scheduled at 100 s): item 1 moves ([110, 210)), then item 2 is
    refused. Item 3 is refused at 160 s. At 210 s item 2, refused before item 3, moves."""
    components = [
        source("50 s"),
        {"id": "walk", "type": "delay", "params": {"time": constant("10 s")}},
        server("b", "100 s", queue_capacity=0),
        sink(),
    ]
    connections = [("arrivals.out", "walk.in"), ("walk.out", "b.in"), ("b.out", "exit.in")]
    metrics = metrics_of(make_model, components, connections, length="300 s")
    assert metrics["arrivals.discarded"] == 0.0  # a delay always accepts
    assert metrics["b.utilization"] == 290 / 300
    assert metrics["exit.count"] == 2.0  # items 0 and 1, at 110 and 210 s
    assert metrics["exit.cycle_time.mean"] == (110 + 160) / 2
    present = [110, 210 - 50, 300 - 100, 300 - 150, 300 - 200, 300 - 250]
    assert metrics["model.wip.mean"] == sum(present) / 300


def test_a_branch_keeps_a_refused_item_so_its_source_never_discards(
    make_model: ModelMaker,
) -> None:
    """Arrivals every 50 s into a branch sending everything to b (service 100 s,
    ``queue_capacity`` 0), 300 s. Items wait at the branch: b serves item 0 [0, 100),
    item 1 [100, 200), item 2 [200, 300). Without the branch the source would discard."""
    components = [
        source("50 s"),
        {
            "id": "check",
            "type": "branch",
            "params": {"routes": ["a", "b"], "rule": "probability", "weights": {"a": 0, "b": 1}},
        },
        server("b", "100 s", queue_capacity=0),
        sink("exit"),
        sink("other"),
    ]
    connections = [
        ("arrivals.out", "check.in"),
        ("check.a", "other.in"),
        ("check.b", "b.in"),
        ("b.out", "exit.in"),
    ]
    metrics = metrics_of(make_model, components, connections, length="300 s")
    assert metrics["arrivals.created"] == 6.0
    assert metrics["arrivals.discarded"] == 0.0
    assert metrics["other.count"] == 0.0
    assert metrics["exit.count"] == 2.0
    assert metrics["b.utilization"] == 1.0
    assert metrics["exit.cycle_time.mean"] == (100 + 150) / 2
    present = [100, 200 - 50] + [300 - 50.0 * i for i in range(2, 6)]
    assert metrics["model.wip.mean"] == sum(present) / 300

    direct = metrics_of(
        make_model,
        [source("50 s"), server("b", "100 s", queue_capacity=0), sink()],
        [("arrivals.out", "b.in"), ("b.out", "exit.in")],
        length="300 s",
    )
    assert direct["arrivals.discarded"] == 3 / 300  # items at 50, 150 and 250 s


def test_a_long_blocked_line_frees_without_recursing(make_model: ModelMaker) -> None:
    """400 servers in a line, each ``queue_capacity`` 0 and 1 s of service, the last
    10,000 s; arrivals every second. Item 0 reaches the last server at 399 s and leaves at
    10,399 s; by then every server holds a blocked item, and that one departure moves an
    item through all 400 at one instant, one after another rather than nested (review of
    PR #18)."""
    count = 400
    components: list[dict[str, Any]] = [source("1 s")]
    for i in range(count):
        service = "10000 s" if i == count - 1 else "1 s"
        components.append(server(f"s{i}", service, queue_capacity=0))
    components.append(sink())
    names = ["arrivals", *(f"s{i}" for i in range(count)), "exit"]
    connections = [(f"{a}.out", f"{b}.in") for a, b in pairwise(names)]
    metrics = metrics_of(make_model, components, connections, length="20000 s")
    assert metrics["exit.count"] == 1.0
    assert metrics[f"s{count - 1}.utilization"] == (20000 - 399) / 20000
    # Every server upstream is busy, serving or holding, from its first item to the end.
    assert metrics["s0.utilization"] == 1.0
