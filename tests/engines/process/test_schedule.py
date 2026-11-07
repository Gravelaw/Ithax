"""The ``schedule`` block (spec 2 "Block reference", "Schedule" and "Statistic
definitions"; AKS-107).

A schedule sets the capacity of its target over time: the sum of the shifts covering the
time within each ``period``, 0 where none does, never more than the target's own
``capacity``. A unit holding an item when the capacity falls finishes it, then stops.
``utilization`` is busy time, counted at each instant up to the available capacity, over the
integral of that capacity; ``scheduled_fraction`` is the integral of the scheduled capacity
over the nominal capacity times the period. Every case below is computed by hand, event by
event, with constant times.
"""

from collections.abc import Sequence
from itertools import pairwise
from typing import Any

from conftest import (
    ContextMaker,
    ModelMaker,
    constant,
    metrics_of_model,
    model_document,
    recorder,
    series_of_model,
)

from lcsim.engines.process.blocks import BLOCK_TYPES, Item, Schedule, Server, Unbatch
from lcsim.engines.process.replication import run_replication
from lcsim.engines.process.translate import engine_input
from lcsim.model.catalogue import PROCESS_TYPES
from lcsim.model.loading import load_document
from lcsim.model.streams import generator_for


def source(interarrival: str = "100 s", **settings: Any) -> dict[str, Any]:
    return {
        "id": "arrivals",
        "type": "source",
        "params": {"interarrival": constant(interarrival), **settings},
    }


def server(capacity: int = 1, service: str = "80 s", **settings: Any) -> dict[str, Any]:
    return {
        "id": "till",
        "type": "server",
        "params": {"capacity": capacity, "service": constant(service), **settings},
    }


def shift(start: str, end: str, capacity: int) -> dict[str, Any]:
    return {"start": start, "end": end, "capacity": capacity}


def schedule(
    shifts: Sequence[dict[str, Any]], period: str | None = "400 s", target: str = "till"
) -> dict[str, Any]:
    params: dict[str, Any] = {"target": target, "shifts": list(shifts)}
    if period is not None:
        params["period"] = period
    return {"id": "rota", "type": "schedule", "params": params}


def sink() -> dict[str, Any]:
    return {"id": "exit", "type": "sink", "params": {}}


LINE = [("arrivals.out", "till.in"), ("till.out", "exit.in")]


def test_the_schedule_type_is_registered_without_metrics() -> None:
    assert BLOCK_TYPES["schedule"] is Schedule
    assert PROCESS_TYPES["schedule"].metrics == ()


def shift_end_line(make_model: ModelMaker, **experiment: Any) -> Any:
    """Items every 100 s from 50 s, service 180 s, into a server of 1 on shift over
    [0, 100) of every 400 s, run for 400 s."""
    experiment.setdefault("length", "400 s")
    components = [
        source(first_arrival="50 s"),
        server(service="180 s"),
        schedule([shift("0 s", "100 s", 1)]),
        sink(),
    ]
    return make_model(components, LINE, **experiment)


def test_a_service_crossing_the_shift_end_finishes_and_utilization_stays_at_most_1(
    make_model: ModelMaker,
) -> None:
    """The PR #1 review case. The item of 50 s serves 50 to 230 s although the capacity
    falls to 0 at 100 s: the unit finishes it, then stops. The items of 150, 250 and 350 s
    find no capacity and wait. Busy time counted at most the available capacity is 50 s
    (50 to 100), over 100 s available: 0.5. Uncapped it would be 180/100 = 1.8."""
    metrics = metrics_of_model(shift_end_line(make_model))
    assert metrics["till.utilization"] == 0.5
    assert metrics["till.utilization"] <= 1.0
    assert metrics["till.scheduled_fraction"] == 100 / 400
    assert metrics["exit.count"] == 1.0
    assert metrics["exit.cycle_time.mean"] == 180.0
    assert metrics["till.wait.mean"] == 0.0
    # Waiting: 1 from 150, 2 from 250, 3 from 350.
    assert metrics["till.queue_length.mean"] == (100 + 2 * 100 + 3 * 50) / 400
    assert metrics["till.queue_length.max"] == 3.0
    assert metrics["till.availability"] == 1.0


def test_utilization_and_its_time_series_count_at_most_the_available_capacity(
    make_model: ModelMaker,
) -> None:
    """Samples every 50 s, after the events of their instant: 0 before the first item,
    1 while the unit serves on shift, then 0 while no capacity is available, though the
    unit is still finishing its item until 230 s."""
    series = series_of_model(shift_end_line(make_model, record_interval="50 s"))
    assert series["till.utilization"] == [
        (0.0, 0.0),
        (50.0, 1.0),
        (100.0, 0.0),
        (150.0, 0.0),
        (200.0, 0.0),
        (250.0, 0.0),
        (300.0, 0.0),
        (350.0, 0.0),
    ]


def test_a_unit_busy_when_capacity_falls_finishes_then_stops(make_model: ModelMaker) -> None:
    """A server of 2 on shifts of 2 over [0, 100) and 1 over [100, 300), every 300 s;
    items at 0, 10, 20 and 30 s, service 150 s, run for 400 s. Items 0 and 1 serve 0 to 150
    and 10 to 160; the capacity falls to 1 at 100, so when item 0 ends at 150 one unit
    still holds an item and nothing starts; item 2 starts at 160 (wait 140). At 300 the
    capacity is 2 again and item 3 starts (wait 270).

    Busy units at most the available capacity: 10 + 2 x 90 + 50 + 10 + 140 + 2 x 10 + 90 =
    500 over 2 x 100 + 200 + 2 x 100 = 600 available."""
    components = [
        source("10 s", max_items=4),
        server(capacity=2, service="150 s"),
        schedule([shift("0 s", "100 s", 2), shift("100 s", "300 s", 1)], period="300 s"),
        sink(),
    ]
    metrics = metrics_of_model(make_model(components, LINE, length="400 s"))
    assert metrics["till.wait.mean"] == (0 + 0 + 140 + 270) / 4
    assert metrics["till.utilization"] == 500 / 600
    assert metrics["till.scheduled_fraction"] == 600 / (2 * 400)
    assert metrics["exit.count"] == 3.0


def test_overlapping_shifts_add_up_and_never_exceed_the_nominal_capacity(
    make_model: ModelMaker,
) -> None:
    """Shifts of 1 over [0, 200) and 1 over [100, 300) every 400 s on a server of 2 give
    1, 2, 1 and 0 over the four 100 s quarters; a shift of 3 on a server of 1 gives 1."""
    overlapping = [
        source(max_items=1),
        server(capacity=2),
        schedule([shift("0 s", "200 s", 1), shift("100 s", "300 s", 1)]),
        sink(),
    ]
    metrics = metrics_of_model(make_model(overlapping, LINE, length="400 s"))
    assert metrics["till.scheduled_fraction"] == (100 + 200 + 100) / (2 * 400)
    over = [
        source("10 s", max_items=3),
        server(capacity=1, service="100 s"),
        schedule([shift("0 s", "400 s", 3)]),
        sink(),
    ]
    metrics = metrics_of_model(make_model(over, LINE, length="400 s"))
    assert metrics["till.scheduled_fraction"] == 1.0
    # One unit only: the items of 0, 10 and 20 s start at 0, 100 and 200 s.
    assert metrics["till.wait.mean"] == (0 + 90 + 180) / 3
    assert metrics["till.utilization"] == 300 / 400


def test_the_default_period_is_24_hours_and_the_shift_list_repeats(
    make_model: ModelMaker,
) -> None:
    """A shift of 1 over [0 h, 1 h), no ``period``; items every 12 h from 0, service 30 min,
    run for 48 h. Item 0 serves at once; item 1 (12 h) waits for the shift of the next day.
    At 24 h the capacity change (scheduled at 1 h) runs before item 2's arrival (scheduled
    at 12 h), so item 1 starts first and item 2 waits 30 min. Item 3 (36 h) waits beyond
    the end."""
    components = [
        source("12 h"),
        server(service="30 min"),
        schedule([shift("0 h", "1 h", 1)], period=None),
        sink(),
    ]
    model = make_model(components, LINE, length="48 h")
    assert engine_input(model, "e")["scenarios"][0]["components"][2]["settings"]["period"] == (
        86_400.0
    )
    metrics = metrics_of_model(model)
    assert metrics["till.wait.mean"] == (0 + 12 * 3600 + 1800) / 3
    assert metrics["till.scheduled_fraction"] == 2 / 48
    assert metrics["till.utilization"] == 3 * 1800 / (2 * 3600)


def test_the_capacity_at_time_0_applies_before_the_first_item(make_model: ModelMaker) -> None:
    """A shift over [100, 200) only: the item of 0 s waits until 100 s."""
    components = [
        source(max_items=1),
        server(),
        schedule([shift("100 s", "200 s", 1)]),
        sink(),
    ]
    metrics = metrics_of_model(make_model(components, LINE, length="400 s"))
    assert metrics["till.wait.mean"] == 100.0
    assert metrics["till.utilization"] == 80 / 100


def test_the_warm_up_boundary(make_model: ModelMaker) -> None:
    """With warm-up at 100 s, the shift end, nothing is available in the observed period:
    utilization is undefined (NaN) and the scheduled fraction 0."""
    metrics = metrics_of_model(shift_end_line(make_model, warmup="100 s"))
    assert metrics["till.utilization"] != metrics["till.utilization"]
    assert metrics["till.scheduled_fraction"] == 0.0
    assert metrics["exit.count"] == 1.0  # the item finishing at 230 s


def test_a_shift_start_with_many_items_waiting_starts_them_in_order(
    make_context: ContextMaker,
) -> None:
    """400 items wait at a server of 400 units scheduled at 0 until 50 s; when the shift
    starts they all start at that instant, first in first out."""
    context = make_context(0.0, 1000.0)
    till = Server(
        "till",
        {"capacity": 400, "service": {"dist": "constant", "value": 10.0}},
        context,
        generator_for(7, 0, "till"),
    )
    rota = Schedule(
        "rota",
        {
            "target": "till",
            "period": 100.0,
            "shifts": [{"start": 50.0, "end": 100.0, "capacity": 400}],
        },
        context,
        generator_for(7, 0, "rota"),
    )
    blocks = {"till": till, "rota": rota}
    for block in blocks.values():
        block.bind(blocks)
    out = recorder(context)
    till.connect("out", out)
    rota.start()
    unpack = Unbatch("unpack", {}, context, generator_for(7, 0, "unpack"))
    unpack.connect("out", till)
    items = tuple(Item(0.0, 0.0) for _ in range(400))
    context.transfers.run(lambda: unpack.receive(Item(0.0, 0.0, contents=items)))
    assert till.waiting_items() == 400
    context.env.run(until=70.0)
    assert out.items == list(items)
    assert out.times == [60.0] * 400


def test_a_shift_start_at_the_end_of_a_long_blocked_line_does_not_recurse(
    make_context: ContextMaker,
) -> None:
    """A line of 400 servers of one unit, ``queue_capacity`` 0 and 0 s service, ends in a
    server scheduled from 500 s. Items fill the line and block; when the shift starts the
    whole line moves one place at that instant through transfer steps."""
    context = make_context(0.0, 2000.0)
    servers = [
        Server(
            f"s{index}",
            {"capacity": 1, "queue_capacity": 0, "service": {"dist": "constant", "value": 0.0}},
            context,
            generator_for(7, 0, f"s{index}"),
        )
        for index in range(400)
    ]
    last = Server(
        "last",
        {"capacity": 1, "queue_capacity": 0, "service": {"dist": "constant", "value": 1.0}},
        context,
        generator_for(7, 0, "last"),
    )
    rota = Schedule(
        "rota",
        {
            "target": "last",
            "period": 2000.0,
            "shifts": [{"start": 500.0, "end": 2000.0, "capacity": 1}],
        },
        context,
        generator_for(7, 0, "rota"),
    )
    blocks = {"last": last, "rota": rota, **{block.id: block for block in servers}}
    for block in blocks.values():
        block.bind(blocks)
    rota.start()
    out = recorder(context)
    for current, following in pairwise([*servers, last]):
        current.connect("out", following)
    last.connect("out", out)
    for index in range(400):
        context.env.timeout(float(index)).callbacks.append(
            lambda _event: context.transfers.run(lambda: servers[0].receive(Item(0.0, 0.0)))
        )
    context.env.run(until=499.0)
    assert sum(block.busy for block in servers) == 400
    context.env.run(until=500.5)
    assert sum(block.busy for block in servers) == 399 and last.busy == 1
    assert out.items == []
    context.env.run(until=501.5)
    assert len(out.items) == 1
    assert sum(block.busy for block in servers) == 398


def test_a_schedule_with_a_tiny_period_can_still_be_stopped() -> None:
    """A schedule changing every 0.5 s over a long run makes many events; ``should_stop``
    is asked between them and the run stops."""
    document = model_document(
        [
            source(max_items=1),
            server(),
            schedule([shift("0 s", "0.5 s", 1)], period="1 s"),
            sink(),
        ],
        LINE,
        length="100000 s",
    )
    result = load_document(document)
    assert result.model is not None
    asked: list[int] = []

    def should_stop() -> bool:
        asked.append(1)
        return len(asked) > 3

    assert run_replication(engine_input(result.model, "e"), 0, 0, should_stop) is None
    assert len(asked) == 4


def test_a_schedule_draws_nothing_so_other_streams_are_unchanged(
    make_model: ModelMaker,
) -> None:
    """A schedule always at full capacity leaves an exponential model's results equal,
    the server's statistics included."""
    plain = [source(), server(), sink()]
    plain[0]["params"]["interarrival"] = {"dist": "exponential", "mean": "60 s"}
    plain[1]["params"]["service"] = {"dist": "exponential", "mean": "50 s"}
    scheduled = [*plain[:2], schedule([shift("0 s", "400 s", 1)]), plain[2]]
    before = metrics_of_model(make_model(plain, LINE, length="3600 s"))
    after = metrics_of_model(make_model(scheduled, LINE, length="3600 s"))
    assert after.keys() == before.keys()
    for metric, value in before.items():
        if metric == "till.utilization":
            assert abs(after[metric] - value) < 1e-12
        else:
            assert after[metric] == value, metric


def test_a_schedule_has_no_levels_or_metrics(make_context: ContextMaker) -> None:
    context = make_context(0.0, 10.0)
    rota = Schedule(
        "rota",
        {"target": "till", "period": 10.0, "shifts": [{"start": 0.0, "end": 5.0, "capacity": 1}]},
        context,
        generator_for(7, 0, "rota"),
    )
    assert rota.metrics() == {} and rota.levels() == {} and rota.ports() == ()
