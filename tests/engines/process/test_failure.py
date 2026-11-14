"""The ``failure`` block (spec 2 "Block reference", "Failure" and "Statistic definitions";
AKS-107).

One failure block is one alternating process on its target server: a ``time_to_failure``
drawn from the failure block's own stream at time 0 and after each repair, on calendar
time, then one unit fails and a ``time_to_repair`` is drawn. An available unit holding no
item fails first; otherwise the item in service that started last is suspended and resumes
after the repair with its remaining service time (preempt-resume). ``availability`` is the
time at least one unit is not failed over the period. Every case below is computed by hand,
event by event, with constant times unless it says otherwise.
"""

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

from ithax.engines.process.blocks import BLOCK_TYPES, Failure, Item, Server, sampler_from_json
from ithax.engines.process.replication import run_replication
from ithax.engines.process.translate import engine_input
from ithax.model.catalogue import PROCESS_TYPES
from ithax.model.loading import load_document
from ithax.model.streams import generator_for


def source(name: str = "arrivals", interarrival: str = "200 s", **settings: Any) -> dict[str, Any]:
    return {
        "id": name,
        "type": "source",
        "params": {"interarrival": constant(interarrival), **settings},
    }


def server(
    name: str = "till", capacity: int = 1, service: str = "100 s", **settings: Any
) -> dict[str, Any]:
    return {
        "id": name,
        "type": "server",
        "params": {"capacity": capacity, "service": constant(service), **settings},
    }


def failure(
    up: Any = "60 s", down: Any = "20 s", target: str = "till", name: str = "breakdown"
) -> dict[str, Any]:
    return {
        "id": name,
        "type": "failure",
        "params": {
            "target": target,
            "time_to_failure": constant(up) if isinstance(up, str) else up,
            "time_to_repair": constant(down) if isinstance(down, str) else down,
        },
    }


def sink(name: str = "exit") -> dict[str, Any]:
    return {"id": name, "type": "sink", "params": {}}


LINE = [("arrivals.out", "till.in"), ("till.out", "exit.in")]


def test_the_failure_type_is_registered_without_metrics() -> None:
    assert BLOCK_TYPES["failure"] is Failure
    assert PROCESS_TYPES["failure"].metrics == ()


def preempt_line(make_model: ModelMaker, **experiment: Any) -> Any:
    """Items at 0 and 200 s, service 100 s; failures 60 s after each repair, repairs 20 s
    after each failure; 400 s."""
    experiment.setdefault("length", "400 s")
    return make_model([source(), server(), failure(), sink()], LINE, **experiment)


def test_an_item_in_service_is_suspended_and_resumes_with_its_remaining_time(
    make_model: ModelMaker,
) -> None:
    """Failures at 60, 140, 220, 300 and 380 s, each repaired 20 s later (the last at
    400 s, the end). Item 0 serves 0 to 60, is suspended with 40 s left, and resumes 80 to
    120. The failure at 140 finds the unit idle. Item 1 serves 200 to 220 (80 s left), 240
    to 300 (20 s left) and 320 to 340. Neither wait counts the suspensions; nothing waits
    in the queue."""
    metrics = metrics_of_model(preempt_line(make_model))
    assert metrics["exit.count"] == 2.0
    assert metrics["exit.cycle_time.mean"] == (120 + 140) / 2
    assert metrics["till.availability"] == (400 - 5 * 20) / 400
    # In service 60 + 40 + 20 + 60 + 20 = 200 s, over 300 s available.
    assert metrics["till.utilization"] == 200 / 300
    assert metrics["till.wait.mean"] == 0.0
    assert metrics["till.queue_length.mean"] == 0.0
    assert metrics["till.queue_length.max"] == 0.0
    assert metrics["till.scheduled_fraction"] == 1.0


def test_the_warm_up_boundary(make_model: ModelMaker) -> None:
    """From 100 s: failed over [140, 160), [220, 240), [300, 320) and [380, 400)."""
    metrics = metrics_of_model(preempt_line(make_model, warmup="100 s"))
    assert metrics["till.availability"] == (300 - 4 * 20) / 300
    # In service 100 to 120, 200 to 220, 240 to 300, 320 to 340.
    assert metrics["till.utilization"] == (20 + 20 + 60 + 20) / 220


def test_the_time_series_counts_busy_units_over_available_ones(make_model: ModelMaker) -> None:
    """Samples every 50 s after their instant's events: 1 in service; at 100 the resumed
    item; 0 at 150 while the unit is failed and idle (0 over 0 is written 0)."""
    series = series_of_model(preempt_line(make_model, record_interval="50 s"))
    assert series["till.utilization"] == [
        (0.0, 1.0),
        (50.0, 1.0),
        (100.0, 1.0),
        (150.0, 0.0),
        (200.0, 1.0),
        (250.0, 1.0),
        (300.0, 0.0),
        (350.0, 0.0),
    ]


def test_an_idle_unit_fails_first_then_the_item_that_started_service_last(
    make_model: ModelMaker,
) -> None:
    """A server of 2, service 100 s, items at 0 and 30 s; failures 20 s after each repair,
    repairs 50 s after each failure, run for 200 s. At 20 one unit is idle, so it fails and
    item 0 goes on (0 to 100). Item 1 waits from 30 until the repair at 70 (wait 40) and
    serves from 70. At 90 no unit is idle: item 1, which started last, is suspended with
    80 s left and resumes at 140, ending at 220, after the end; item 0 is not touched and
    leaves at 100. (Suspending item 0 instead would let both leave, at 150 and 170.) At
    160 the unit idle since 100 fails. A unit is always up, so availability is 1.

    Busy units at most the available capacity: 20 + 50 + 2 x 20 + 10 + 20 + 40 = 180;
    available 2, 1, 2, 1, 2, 1 over [0, 20), [20, 70), [70, 90), [90, 140), [140, 160),
    [160, 200): 260."""
    components = [
        source(interarrival="30 s", max_items=2),
        server(capacity=2),
        failure("20 s", "50 s"),
        sink(),
    ]
    metrics = metrics_of_model(make_model(components, LINE, length="200 s"))
    assert metrics["till.availability"] == 1.0
    assert metrics["till.wait.mean"] == (0 + 40) / 2
    assert metrics["exit.count"] == 1.0
    assert metrics["exit.cycle_time.mean"] == 100.0
    assert metrics["till.utilization"] == 180 / 260
    assert metrics["till.queue_length.mean"] == 40 / 200


def test_a_blocked_unit_that_fails_still_passes_its_item_on(make_model: ModelMaker) -> None:
    """``a`` (1 unit, service 10 s) feeds ``b`` (1 unit, ``queue_capacity`` 0, service
    100 s); items every 30 s from 0; ``a`` fails at 50 s, repaired at 150 s. Item 0 serves
    at ``a`` 0 to 10 and at ``b`` 10 to 110. Item 1 serves at ``a`` 30 to 40 and is refused.
    At 50 the unit holding it fails; the item still moves to ``b`` at 110, and the failed
    unit takes nothing until 150: item 2 (arrived 60) waits 90 s, serves 150 to 160 and is
    refused until ``b`` frees at 210, after the end."""
    components = [
        source(interarrival="30 s", max_items=3),
        server("a", service="10 s"),
        server("b", service="100 s", queue_capacity=0),
        failure("50 s", "100 s", target="a"),
        sink(),
    ]
    connections = [("arrivals.out", "a.in"), ("a.out", "b.in"), ("b.out", "exit.in")]
    metrics = metrics_of_model(make_model(components, connections, length="200 s"))
    assert metrics["a.wait.mean"] == (0 + 0 + 90) / 3
    assert metrics["b.wait.mean"] == 0.0
    assert metrics["a.availability"] == 100 / 200
    # Busy (in service or blocked) at most the available units: [0, 10), [30, 50) and
    # [150, 200) while up; nothing counts while failed. Available 100 s.
    assert metrics["a.utilization"] == (10 + 20 + 50) / 100
    assert metrics["exit.count"] == 1.0
    assert metrics["arrivals.discarded"] == 0.0


def test_a_unit_off_shift_still_fails_on_calendar_time(make_model: ModelMaker) -> None:
    """A shift over [0, 100) every 200 s; the unit fails at 150 s, off shift, and is
    repaired at 250 s, so the next shift has no unit until 250. The item of 210 s waits
    40 s and serves 250 to 270. Available: 100 over [0, 100) and 50 over [250, 300)."""
    components = [
        source(interarrival="1000 s", first_arrival="210 s"),
        server(service="20 s"),
        failure("150 s", "100 s"),
        {
            "id": "rota",
            "type": "schedule",
            "params": {
                "target": "till",
                "period": "200 s",
                "shifts": [{"start": "0 s", "end": "100 s", "capacity": 1}],
            },
        },
        sink(),
    ]
    metrics = metrics_of_model(make_model(components, LINE, length="300 s"))
    assert metrics["till.wait.mean"] == 40.0
    assert metrics["till.scheduled_fraction"] == 200 / 300
    assert metrics["till.availability"] == 200 / 300
    assert metrics["till.utilization"] == 20 / 150


def test_an_item_finishing_after_its_shift_resumes_at_the_repair(
    make_model: ModelMaker,
) -> None:
    """A shift over [0, 100) every 400 s; the item of 50 s (service 100 s) is still being
    finished when its unit fails at 120 s with 30 s left; it resumes at the repair, 170 s,
    off shift, and ends at 200 s. The next failure, at 290 s, is repaired at 340 s."""
    components = [
        source(interarrival="1000 s", first_arrival="50 s"),
        server(),
        failure("120 s", "50 s"),
        {
            "id": "rota",
            "type": "schedule",
            "params": {
                "target": "till",
                "period": "400 s",
                "shifts": [{"start": "0 s", "end": "100 s", "capacity": 1}],
            },
        },
        sink(),
    ]
    metrics = metrics_of_model(make_model(components, LINE, length="400 s"))
    assert metrics["exit.cycle_time.mean"] == 150.0
    assert metrics["till.utilization"] == 50 / 100
    assert metrics["till.availability"] == 300 / 400


def test_an_item_waiting_for_the_pool_on_a_failed_unit_starts_after_the_repair(
    make_model: ModelMaker,
) -> None:
    """A pool of 1 shared by ``a`` and ``b`` (1 unit each, service 15 s at ``a`` and 100 s
    at ``b``). Item b0 holds the pool 0 to 100; a0 takes ``a``'s unit at 10 and waits for
    the pool. ``a`` fails at 20 with no item in service, so the unit whose item waits for
    the pool fails. a0 gets the pool at 100 but starts only at the repair, 120 (wait
    110 s), and ends at 135, before the next failure at 140 finds the unit idle."""
    components = [
        source("in_a", "1000 s", first_arrival="10 s"),
        source("in_b", "1000 s"),
        server("a", service="15 s", pool="staff"),
        server("b", service="100 s", pool="staff"),
        {"id": "staff", "type": "resource_pool", "params": {"capacity": 1}},
        failure("20 s", "100 s", target="a"),
        sink("out_a"),
        sink("out_b"),
    ]
    connections = [
        ("in_a.out", "a.in"),
        ("in_b.out", "b.in"),
        ("a.out", "out_a.in"),
        ("b.out", "out_b.in"),
    ]
    metrics = metrics_of_model(make_model(components, connections, length="200 s"))
    assert metrics["a.wait.mean"] == 110.0
    assert metrics["out_a.cycle_time.mean"] == 125.0
    # The pool is held by b0 over [0, 100) and by a0 over [100, 135).
    assert metrics["staff.utilization"] == 135 / 200
    # a0 waits, holding a's unit, from 10 to 120.
    assert metrics["a.queue_length.mean"] == 110 / 200


def test_a_unit_repaired_before_its_item_gets_the_pool_goes_back_to_waiting(
    make_model: ModelMaker,
) -> None:
    """A pool of 1 shared by ``a`` (2 units, service 15 s) and ``b`` (service 100 s); b0
    holds the pool 0 to 100. a0 (10 s) and a1 (15 s) take ``a``'s units and wait for the
    pool. Failures 20 s after each repair, repairs 30 s after each failure. At 20 no unit of
    ``a`` is free and none serves, so a1's unit fails (the later of the two waiting); at 50
    it is repaired and a1 goes on waiting for the pool. At 70 a1's unit fails again. At 100
    b0's end (scheduled at 0) runs before the repair (scheduled at 70): the pool goes to
    a0, first in line, which serves 100 to 115; then the repair puts a1 back to waiting,
    and a1 gets the pool at 115 and serves to 130. The failure at 130 runs before a1's end
    (scheduled at 115) and finds a unit free."""
    components = [
        source("in_a", "5 s", first_arrival="10 s", max_items=2),
        source("in_b", "1000 s"),
        server("a", capacity=2, service="15 s", pool="staff"),
        server("b", service="100 s", pool="staff"),
        {"id": "staff", "type": "resource_pool", "params": {"capacity": 1}},
        failure("20 s", "30 s", target="a"),
        sink("out_a"),
        sink("out_b"),
    ]
    connections = [
        ("in_a.out", "a.in"),
        ("in_b.out", "b.in"),
        ("a.out", "out_a.in"),
        ("b.out", "out_b.in"),
    ]
    metrics = metrics_of_model(make_model(components, connections, length="200 s"))
    assert metrics["a.wait.mean"] == (90 + 100) / 2
    assert metrics["out_a.cycle_time.mean"] == (105 + 115) / 2
    assert metrics["a.queue_length.mean"] == (90 + 100) / 200
    assert metrics["staff.utilization"] == 130 / 200


def test_times_come_from_the_failure_s_own_stream_in_event_order(
    make_model: ModelMaker,
) -> None:
    """Spec 1 "Random streams": the failure block draws ``time_to_failure`` at time 0 and
    after each repair, and ``time_to_repair`` at each failure, from
    ``<seed>:<replication>:<failure id>``. The availability equals the one computed from
    those draws in that order."""
    up = {"dist": "exponential", "mean": "100 s"}
    down = {"dist": "exponential", "mean": "25 s"}
    components = [source(max_items=1), server(), failure(up, down), sink()]
    metrics = metrics_of_model(make_model(components, LINE, length="10000 s", seed=5))
    rng = generator_for(5, 0, "breakdown")
    draw_up = sampler_from_json({"dist": "exponential", "mean": 100.0})
    draw_down = sampler_from_json({"dist": "exponential", "mean": 25.0})
    time, failed = 0.0, 0.0
    while True:
        time += draw_up(rng)
        if time >= 10_000:
            break
        repair = time + draw_down(rng)
        failed += min(repair, 10_000) - time
        time = repair
        if time >= 10_000:
            break
    assert abs(metrics["till.availability"] - (10_000 - failed) / 10_000) < 1e-12


def test_a_failure_s_draws_leave_other_streams_unchanged(make_model: ModelMaker) -> None:
    """Common random numbers: a failure that never fires within the run leaves every
    result equal; one that fires leaves the source's arrivals equal."""
    plain = [source(), server(), sink()]
    plain[0]["params"]["interarrival"] = {"dist": "exponential", "mean": "60 s"}
    plain[1]["params"]["service"] = {"dist": "exponential", "mean": "50 s"}
    never = [*plain[:2], failure("100000 s", "1 s"), plain[2]]
    often = [*plain[:2], failure({"dist": "exponential", "mean": "300 s"}, "30 s"), plain[2]]
    before = metrics_of_model(make_model(plain, LINE, length="3600 s"))
    unfired = metrics_of_model(make_model(never, LINE, length="3600 s"))
    fired = metrics_of_model(make_model(often, LINE, length="3600 s"))
    for metric, value in before.items():
        if metric == "till.utilization":
            assert abs(unfired[metric] - value) < 1e-12
        else:
            assert unfired[metric] == value, metric
    assert fired["arrivals.created"] == before["arrivals.created"]
    assert fired["till.availability"] < 1.0


def test_a_failure_with_tiny_times_can_still_be_stopped() -> None:
    document = model_document(
        [source(max_items=1), server(), failure("0.5 s", "0.5 s"), sink()],
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


def test_a_repair_at_the_end_of_a_long_blocked_line_does_not_recurse(
    make_context: ContextMaker,
) -> None:
    """A line of 400 servers of one unit, ``queue_capacity`` 0 and 0 s service, ends in a
    server that fails at 0 s and is repaired at 500 s (and, with a time to failure of 0 s,
    fails again at once, suspending the item it took). Items fill the line and block; at
    the repair the whole line moves one place at that instant through transfer steps."""
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
    breakdown = Failure(
        "breakdown",
        {
            "target": "last",
            "time_to_failure": {"dist": "constant", "value": 0.0},
            "time_to_repair": {"dist": "constant", "value": 500.0},
        },
        context,
        generator_for(7, 0, "breakdown"),
    )
    blocks: dict[str, Any] = {"last": last, "breakdown": breakdown}
    blocks.update({block.id: block for block in servers})
    for block in blocks.values():
        block.bind(blocks)
    breakdown.start()
    out = recorder(context)
    for current, following in pairwise([*servers, last]):
        current.connect("out", following)
    last.connect("out", out)
    for index in range(400):
        context.env.timeout(1.0 + index).callbacks.append(
            lambda _event: context.transfers.run(lambda: servers[0].receive(Item(0.0, 0.0)))
        )
    context.env.run(until=499.0)
    assert sum(block.busy for block in servers) == 400
    context.env.run(until=500.5)
    assert sum(block.busy for block in servers) == 399
    assert last.waiting_items() == 0 and out.items == []


def test_a_failure_has_no_levels_or_metrics(make_context: ContextMaker) -> None:
    context = make_context(0.0, 10.0)
    breakdown = Failure(
        "breakdown",
        {
            "target": "till",
            "time_to_failure": {"dist": "constant", "value": 1.0},
            "time_to_repair": {"dist": "constant", "value": 1.0},
        },
        context,
        generator_for(7, 0, "breakdown"),
    )
    assert breakdown.metrics() == {} and breakdown.levels() == {} and breakdown.ports() == ()
