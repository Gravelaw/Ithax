"""One replication, end to end from the engine input (spec 2 "Statistic definitions" and
"Simultaneous events"; spec 1 "Random streams"; AKS-98).

Deterministic models whose every statistic is computed by hand: constant interarrival and
service times, with and without warm-up, including events at the warm-up instant and at
the end of the run.
"""

import math
from typing import Any

import pytest
import simpy
from conftest import ModelMaker, constant, line

from lcsim.engines.process.blocks import Context
from lcsim.engines.process.replication import (
    build_blocks,
    run_replication,
)
from lcsim.engines.process.statistics import TimeWeighted, Window
from lcsim.engines.process.translate import engine_input
from lcsim.model.streams import generator_for


def never() -> bool:
    return False


def metrics_of(engine: dict[str, Any], scenario: int = 0, replication: int = 0) -> dict[str, float]:
    rows = run_replication(engine, scenario, replication, never)
    assert rows is not None
    return {metric: value for metric, value, _ in rows}


def deterministic(
    make_model: ModelMaker, gap: str, service: str, **experiment: Any
) -> dict[str, Any]:
    components, connections = line(constant(gap), constant(service))
    return engine_input(make_model(components, connections, **experiment), "e")


def overlap(start: float, stop: float, low: float, high: float) -> float:
    """The length of [start, stop) inside [low, high)."""
    return max(0.0, min(stop, high) - max(start, low))


def test_rows_name_every_metric_in_order_with_its_unit(make_model: ModelMaker) -> None:
    rows = run_replication(deterministic(make_model, "2 min", "1 min"), 0, 0, never)
    assert rows is not None
    assert [(metric, unit) for metric, _, unit in rows] == [
        ("arrivals.created", "1"),
        ("arrivals.discarded", "1/s"),
        ("till.wait.mean", "s"),
        ("till.utilization", "1"),
        ("till.availability", "1"),
        ("till.scheduled_fraction", "1"),
        ("till.queue_length.mean", "1"),
        ("till.queue_length.max", "1"),
        ("exit.throughput", "1/s"),
        ("exit.cycle_time.mean", "s"),
        ("exit.count", "1"),
        ("model.wip.mean", "1"),
    ]
    assert all(isinstance(value, float) for _, value, _ in rows)


def test_a_server_half_busy_without_warm_up(make_model: ModelMaker) -> None:
    """Arrivals every 2 min from 0, service 1 min, 20 min: items at 0, 120, ..., 1080 s."""
    metrics = metrics_of(deterministic(make_model, "2 min", "1 min", length="20 min"))
    assert metrics == {
        "arrivals.created": 10.0,
        "arrivals.discarded": 0.0,
        "till.wait.mean": 0.0,
        "till.utilization": 0.5,
        "till.availability": 1.0,
        "till.scheduled_fraction": 1.0,
        "till.queue_length.mean": 0.0,
        "till.queue_length.max": 0.0,
        "exit.throughput": 10 / 1200,
        "exit.cycle_time.mean": 60.0,
        "exit.count": 10.0,
        "model.wip.mean": 0.5,
    }


def test_a_server_half_busy_after_warm_up(make_model: ModelMaker) -> None:
    """The same with 5 min of warm-up: the period is [300, 1200) s. Items created at 360 to
    1080 s count (7); the item from 240 s reaches the sink at exactly 300 s and counts
    (8 at the sink); each item is in the system for 60 s."""
    engine = deterministic(make_model, "2 min", "1 min", length="20 min", warmup="5 min")
    metrics = metrics_of(engine)
    assert metrics["arrivals.created"] == 7.0
    assert metrics["till.wait.mean"] == 0.0
    assert metrics["till.utilization"] == 7 * 60 / 900
    assert metrics["exit.count"] == 8.0
    assert metrics["exit.throughput"] == 8 / 900
    assert metrics["exit.cycle_time.mean"] == 60.0
    assert metrics["model.wip.mean"] == 7 * 60 / 900
    assert metrics["till.queue_length.max"] == 0.0


def growing_waits(warmup: float) -> dict[str, float]:
    """Arrivals every 60 s from 0, service 90 s, one server, 600 s. Item i arrives at 60i
    and starts at 90i, so it waits 30i; it leaves at 90(i + 1). Items 0 to 9 arrive; 0 to 6
    start; 0 to 5 leave (item 6 would leave at 630 s)."""
    length = 600.0
    arrivals = [60.0 * i for i in range(10)]
    starts = [90.0 * i for i in range(7)]
    departures = [90.0 * (i + 1) for i in range(6)]
    waits = [start - arrivals[i] for i, start in enumerate(starts) if start >= warmup]
    cycles = [done - arrivals[i] for i, done in enumerate(departures) if done >= warmup]
    queued = sum(
        overlap(arrivals[i], starts[i] if i < len(starts) else length, warmup, length)
        for i in range(10)
    )
    present = sum(
        overlap(arrivals[i], departures[i] if i < len(departures) else length, warmup, length)
        for i in range(10)
    )
    period = length - warmup
    return {
        "till.wait.mean": sum(waits) / len(waits),
        "till.queue_length.mean": queued / period,
        "exit.count": float(len(cycles)),
        "exit.cycle_time.mean": sum(cycles) / len(cycles),
        "model.wip.mean": present / period,
        "arrivals.created": float(sum(time >= warmup for time in arrivals)),
    }


@pytest.mark.parametrize("warmup", [0.0, 250.0, 270.0])
def test_waits_that_grow_are_computed_exactly(make_model: ModelMaker, warmup: float) -> None:
    engine = deterministic(make_model, "60 s", "90 s", length="600 s", warmup=f"{warmup:g} s")
    metrics = metrics_of(engine)
    expected = growing_waits(warmup)
    for metric, value in expected.items():
        assert metrics[metric] == pytest.approx(value, rel=1e-12), metric
    assert metrics["till.utilization"] == 1.0
    # At most three items wait: e.g. from 480 s, items 6, 7 and 8.
    assert metrics["till.queue_length.max"] == 3.0
    assert metrics["exit.throughput"] == expected["exit.count"] / (600.0 - warmup)


def test_the_hand_computed_growing_waits() -> None:
    """The arithmetic above, written out for no warm-up."""
    expected = growing_waits(0.0)
    assert expected["till.wait.mean"] == 90.0  # (0 + 30 + ... + 180) / 7
    assert expected["exit.cycle_time.mean"] == 165.0  # (90 + 120 + ... + 240) / 6
    assert expected["till.queue_length.mean"] == 990 / 600
    assert expected["model.wip.mean"] == 1590 / 600


def test_an_event_due_exactly_at_the_end_does_not_run(make_model: ModelMaker) -> None:
    """Arrivals every 100 s and service 100 s over 1000 s: the arrival due at 1000 s is not
    made, and the item served from 900 s does not reach the sink at 1000 s."""
    metrics = metrics_of(deterministic(make_model, "100 s", "100 s", length="1000 s"))
    assert metrics["arrivals.created"] == 10.0
    assert metrics["exit.count"] == 9.0
    assert metrics["till.utilization"] == 1.0
    assert metrics["model.wip.mean"] == 1.0


def test_a_mean_over_no_items_is_nan(make_model: ModelMaker) -> None:
    """The one service starts at 0 s, before warm-up ends; no item reaches the sink."""
    engine = deterministic(
        make_model, "1000 s", "5000 s", length="2000 s", warmup="500 s", replications=2
    )
    metrics = metrics_of(engine)
    assert math.isnan(metrics["till.wait.mean"])
    assert math.isnan(metrics["exit.cycle_time.mean"])
    assert metrics["exit.count"] == 0.0
    assert metrics["exit.throughput"] == 0.0
    assert metrics["till.queue_length.mean"] == 1000 / 1500


def test_each_component_draws_from_its_own_stream(make_model: ModelMaker) -> None:
    components, connections = line(
        {"dist": "exponential", "mean": "2 min"}, {"dist": "exponential", "mean": "1 min"}
    )
    engine = engine_input(make_model(components, connections, seed=99), "e")
    window = Window(0.0, 10.0)
    context = Context(env=simpy.Environment(), window=window, wip=TimeWeighted(window))
    blocks = build_blocks(engine["scenarios"][0], engine["connections"], context, 99, 3)
    for block in blocks:
        assert block.rng.random() == generator_for(99, 3, block.id).random()


def test_scenarios_share_streams_and_replications_do_not(make_model: ModelMaker) -> None:
    """Common random numbers: the source makes the same items in both scenarios, which
    differ only in the till's capacity; each replication has its own streams."""
    components, connections = line(
        {"dist": "exponential", "mean": "2 min"},
        {"dist": "exponential", "mean": "1.5 min"},
        capacity={"$param": "tills"},
    )
    model = make_model(
        components,
        connections,
        length="10 h",
        parameters={"tills": {"value": 1, "type": "integer"}},
        scenarios=[{"id": "one", "set": {}}, {"id": "two", "set": {"tills": 2}}],
    )
    engine = engine_input(model, "e")
    one, two = metrics_of(engine, 0, 0), metrics_of(engine, 1, 0)
    assert one["arrivals.created"] == two["arrivals.created"]
    assert two["till.wait.mean"] < one["till.wait.mean"]
    assert metrics_of(engine, 0, 1)["arrivals.created"] != one["arrivals.created"]
    assert metrics_of(engine, 0, 0) == one  # a replication repeats exactly


def test_should_stop_ends_the_replication_without_rows(make_model: ModelMaker) -> None:
    engine = deterministic(make_model, "1 s", "0.5 s", length="1 d")
    calls: list[int] = []

    def stop_on_second_check() -> bool:
        calls.append(1)
        return len(calls) == 2

    assert run_replication(engine, 0, 0, stop_on_second_check) is None
    # The first check is before the first event, the second after STOP_CHECK_EVENTS.
    assert len(calls) == 2
