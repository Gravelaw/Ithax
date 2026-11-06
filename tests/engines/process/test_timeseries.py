"""The ``timeseries`` table (spec 1 "Tables for the ``process`` domain"; spec 2 "Statistic
definitions"; AKS-99).

Per server ``<server>.queue_length`` and ``<server>.utilization``, and ``model.wip``,
sampled at k times ``record_interval`` from 0 s while before the end, through warm-up. A sample
is the value after every event due at its instant. Sampling adds no event and draws no
random number, so the ``replications`` rows are the same without it.
"""

import threading
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest
from conftest import ModelMaker, constant, line

from lcsim.engines.process.replication import Outcome, TimeSeries, run_replication
from lcsim.engines.process.runner import TIMESERIES_SCHEMA, run_all, timeseries_table
from lcsim.engines.process.translate import engine_input, read_input, write_input


def never() -> bool:
    return False


def outcome_of(engine: dict[str, Any], scenario: int = 0, replication: int = 0) -> Outcome:
    outcome = run_replication(engine, scenario, replication, never)
    assert outcome is not None
    return outcome


def series_of(outcome: Outcome) -> dict[str, list[tuple[float, float]]]:
    series: dict[str, list[tuple[float, float]]] = {}
    for metric, time, value, unit in outcome.series:
        assert unit == "1"
        series.setdefault(metric, []).append((time, value))
    return series


def deterministic(make_model: ModelMaker, **experiment: Any) -> dict[str, Any]:
    components, connections = line(constant("2 min"), constant("1 min"))
    return engine_input(make_model(components, connections, **experiment), "e")


def test_the_metrics_are_queue_length_and_utilization_per_server_then_wip(
    make_model: ModelMaker,
) -> None:
    series = series_of(outcome_of(deterministic(make_model, length="20 min")))
    assert list(series) == ["till.queue_length", "till.utilization", "model.wip"]


def test_by_default_200_samples_from_zero_and_none_at_the_end(make_model: ModelMaker) -> None:
    """``record_interval`` defaults to ``length`` / 200: 6 s for 20 min."""
    series = series_of(outcome_of(deterministic(make_model, length="20 min")))
    for samples in series.values():
        assert [time for time, _ in samples] == [6.0 * k for k in range(200)]


def test_samples_are_taken_through_warm_up(make_model: ModelMaker) -> None:
    engine = deterministic(make_model, length="20 min", warmup="10 min", record_interval="5 min")
    times = [time for time, _ in series_of(outcome_of(engine))["model.wip"]]
    assert times == [0.0, 300.0, 600.0, 900.0]


def test_an_interval_that_does_not_divide_the_length(make_model: ModelMaker) -> None:
    engine = deterministic(make_model, length="100 s", record_interval="30 s")
    times = [time for time, _ in series_of(outcome_of(engine))["model.wip"]]
    assert times == [0.0, 30.0, 60.0, 90.0]


def test_a_sample_is_the_value_after_the_events_of_its_instant(make_model: ModelMaker) -> None:
    """Arrivals every 2 min from 0, service 1 min, samples every 30 s: the item made at 0 s
    is in service at the 0 s sample, the departure at 60 s has happened at the 60 s
    sample, and the arrival at 120 s at the 120 s sample. Each 120 s: 1, 1, 0, 0."""
    engine = deterministic(make_model, length="20 min", record_interval="30 s")
    series = series_of(outcome_of(engine))
    pattern = [1.0, 1.0, 0.0, 0.0] * 10
    assert [value for _, value in series["till.utilization"]] == pattern
    assert [value for _, value in series["model.wip"]] == pattern
    assert [value for _, value in series["till.queue_length"]] == [0.0] * 40


def test_queue_length_and_utilization_are_numbers_waiting_and_busy_over_capacity(
    make_model: ModelMaker,
) -> None:
    """Arrivals every 60 s, service 90 s, capacity 2, 600 s, samples every 100 s. Item i
    arrives at 60i; at most two overlap, so it starts at once and ends at 60i + 90. At
    300 s item 5 has just arrived and item 4 is still in service: 2 busy units."""
    components, connections = line(constant("60 s"), constant("90 s"), capacity=2)
    model = make_model(components, connections, length="600 s", record_interval="100 s")
    series = series_of(outcome_of(engine_input(model, "e")))
    in_service = []
    for t in (0.0, 100.0, 200.0, 300.0, 400.0, 500.0):
        in_service.append(sum(1 for i in range(10) if 60 * i <= t < 60 * i + 90))
    assert [value for _, value in series["till.utilization"]] == [n / 2 for n in in_service]
    assert [value for _, value in series["model.wip"]] == [float(n) for n in in_service]
    assert in_service == [1, 1, 2, 2, 1, 2]


def test_sampling_changes_no_other_result(make_model: ModelMaker, monkeypatch: Any) -> None:
    """A stochastic model with a branch, a delay and blocking: the ``replications`` rows are
    the same with samples every second and with sampling switched off."""
    components = [
        {
            "id": "arrivals",
            "type": "source",
            "params": {"interarrival": {"dist": "exponential", "mean": "1 min"}},
        },
        {
            "id": "check",
            "type": "branch",
            "params": {"routes": ["a", "b"], "rule": "probability", "weights": {"a": 1, "b": 2}},
        },
        {
            "id": "a",
            "type": "server",
            "params": {
                "capacity": 1,
                "service": {"dist": "exponential", "mean": "2 min"},
                "queue_capacity": 1,
            },
        },
        {
            "id": "walk",
            "type": "delay",
            "params": {"time": {"dist": "uniform", "min": "0 s", "max": "2 min"}},
        },
        {
            "id": "b",
            "type": "server",
            "params": {"capacity": 1, "service": {"dist": "exponential", "mean": "0.5 min"}},
        },
        {"id": "exit", "type": "sink", "params": {}},
    ]
    connections = [
        ("arrivals.out", "check.in"),
        ("check.a", "a.in"),
        ("check.b", "walk.in"),
        ("walk.out", "b.in"),
        ("a.out", "b.in"),
        ("b.out", "exit.in"),
    ]
    model = make_model(
        components, connections, length="10 h", warmup="1 h", record_interval="1 s", seed=3
    )
    engine = engine_input(model, "e")
    sampled = outcome_of(engine)
    assert len(sampled.series) == 5 * 36_000
    monkeypatch.setattr(TimeSeries, "record", lambda self, time: None)
    unsampled = outcome_of(engine)
    assert unsampled.series == []
    assert unsampled.rows == sampled.rows
    rows = dict((metric, value) for metric, value, _ in sampled.rows)
    assert rows["arrivals.discarded"] == 0.0
    assert rows["a.utilization"] > 0.5


def test_the_table_has_the_spec_columns_in_order(make_model: ModelMaker, tmp_path: Path) -> None:
    components, connections = line(constant("2 min"), constant("1 min"))
    model = make_model(
        components,
        connections,
        length="20 min",
        record_interval="10 min",
        replications=2,
        parameters={"tills": {"value": 1, "type": "integer"}},
        scenarios=[{"id": "one", "set": {}}, {"id": "two", "set": {"tills": 2}}],
    )
    write_input(model, "e", tmp_path)
    engine = read_input(tmp_path)
    done = run_all(tmp_path, engine, lambda progress: None, threading.Event(), 1)
    assert done is not None
    table = timeseries_table(engine, dict(reversed(list(done.items()))))
    assert table.schema == TIMESERIES_SCHEMA
    assert table.schema == pa.schema(
        [
            ("scenario", pa.string()),
            ("replication", pa.int64()),
            ("metric", pa.string()),
            ("time_s", pa.float64()),
            ("value", pa.float64()),
            ("unit", pa.string()),
        ]
    )
    rows = [
        (row["scenario"], row["replication"], row["metric"], row["time_s"])
        for row in table.to_pylist()
    ]
    per_replication = [
        (metric, time)
        for metric in ("till.queue_length", "till.utilization", "model.wip")
        for time in (0.0, 600.0)
    ]
    assert rows == [
        (scenario, replication, metric, time)
        for scenario in ("one", "two")
        for replication in (0, 1)
        for metric, time in per_replication
    ]
    assert set(table["unit"].to_pylist()) == {"1"}


@pytest.mark.parametrize("length", ["1 h", "200 h", "7 d", "29 s", "13.7 s"])
def test_the_default_interval_gives_200_samples(make_model: ModelMaker, length: str) -> None:
    components, connections = line(constant("1 h"), constant("1 min"))
    engine = engine_input(make_model(components, connections, length=length), "e")
    times = [time for time, _ in series_of(outcome_of(engine))["model.wip"]]
    # For 29 s and 13.7 s, 200 times (length / 200) rounds to just below the length: that
    # time counts as the end.
    assert len(times) == 200
    assert times[-1] < engine["experiment"]["length"]


def test_a_huge_interval_still_samples_at_zero(make_model: ModelMaker) -> None:
    engine = deterministic(make_model, length="1 s", record_interval="100000 d")
    assert [time for time, _ in series_of(outcome_of(engine))["model.wip"]] == [0.0]
