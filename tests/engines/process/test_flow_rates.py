"""The W201 flow rates against the blocks that now run (spec 1 "Validation"; AKS-105,
AKS-106).

Validation propagates a mean rate from each source: a batch divides it by ``size``, an
unbatch multiplies it by the size of what it receives, and a loss point (a discarding
``queue``, a source feeding a block that can refuse an item) stops it, since less than the
offered rate gets through. A store stops it too: what passes depends on its orders. These
tests run deterministic models in the adapter and check
the rates the blocks really pass against ``flow_rates``.
"""

from fractions import Fraction
from itertools import pairwise
from typing import Any

import pytest
from conftest import ModelMaker, constant, metrics_of_model

from ithax.model.validation import flow_rates, load_issues


def source() -> dict[str, Any]:
    return {"id": "arrivals", "type": "source", "params": {"interarrival": constant("60 s")}}


def sink() -> dict[str, Any]:
    return {"id": "exit", "type": "sink", "params": {}}


def chain(*names: str) -> list[tuple[str, str]]:
    return [(f"{origin}.out", f"{destination}.in") for origin, destination in pairwise(names)]


def test_a_batch_divides_the_rate_by_its_size(make_model: ModelMaker) -> None:
    """Arrivals every 60 s into a batch of 5, 3,000 s: batches leave at 240, 540, ...,
    2,940 s, 10 of them, one every 300 s, as validation says."""
    components = [source(), {"id": "pack", "type": "batch", "params": {"size": 5}}, sink()]
    model = make_model(components, chain("arrivals", "pack", "exit"), length="3000 s")
    assert flow_rates(model)["exit"] == Fraction(1, 300)
    metrics = metrics_of_model(model)
    assert metrics["exit.count"] == 10.0
    assert metrics["exit.throughput"] == 10 / 3000


def test_an_unbatch_multiplies_it_back(make_model: ModelMaker) -> None:
    components = [
        source(),
        {"id": "pack", "type": "batch", "params": {"size": 5}},
        {"id": "unpack", "type": "unbatch", "params": {}},
        sink(),
    ]
    model = make_model(components, chain("arrivals", "pack", "unpack", "exit"), length="3000 s")
    assert flow_rates(model)["exit"] == Fraction(1, 60)
    metrics = metrics_of_model(model)
    assert metrics["exit.count"] == 50.0  # every item created reaches the sink
    assert metrics["exit.throughput"] == 50 / 3000


def test_a_server_after_a_batch_is_loaded_by_batches(make_model: ModelMaker) -> None:
    """A batch of 5 every 300 s into a server of service 299 s: validation finds it
    loaded below its capacity (no W201), and the server keeps up in the run."""
    components = [
        source(),
        {"id": "pack", "type": "batch", "params": {"size": 5}},
        {"id": "till", "type": "server", "params": {"capacity": 1, "service": constant("299 s")}},
        sink(),
    ]
    model = make_model(components, chain("arrivals", "pack", "till", "exit"), length="3000 s")
    assert load_issues(model) == []
    metrics = metrics_of_model(model)
    assert metrics["till.wait.mean"] == 0.0
    assert metrics["till.queue_length.max"] == 0.0


@pytest.mark.parametrize(
    "middle",
    [
        {"id": "line", "type": "queue", "params": {"capacity": 1}},
        {"id": "line", "type": "queue", "params": {"capacity": 1, "on_full": "discard"}},
    ],
    ids=["a source feeding a queue", "a discarding queue"],
)
def test_a_loss_point_stops_the_rate_because_less_gets_through(
    make_model: ModelMaker, middle: dict[str, Any]
) -> None:
    """Arrivals every 60 s, a queue of 1, a server of service 150 s with ``queue_capacity``
    0, 600 s: of 10 items only 3 reach the sink, so no rate can be passed on."""
    components = [
        source(),
        middle,
        {
            "id": "till",
            "type": "server",
            "params": {"capacity": 1, "service": constant("150 s"), "queue_capacity": 0},
        },
        sink(),
    ]
    model = make_model(components, chain("arrivals", "line", "till", "exit"), length="600 s")
    rates = flow_rates(model)
    assert rates["till"] is None and rates["exit"] is None
    metrics = metrics_of_model(model)
    assert metrics["exit.count"] == 3.0
    assert metrics["arrivals.discarded"] + metrics["line.discarded"] > 0.0


def test_a_source_feeding_a_batch_is_not_a_loss_point(make_model: ModelMaker) -> None:
    """A batch always accepts, so its source never discards and the rate goes on."""
    components = [
        source(),
        {"id": "pack", "type": "batch", "params": {"size": 2}},
        {
            "id": "till",
            "type": "server",
            "params": {"capacity": 1, "service": constant("1000 s"), "queue_capacity": 0},
        },
        sink(),
    ]
    model = make_model(components, chain("arrivals", "pack", "till", "exit"), length="3000 s")
    assert flow_rates(model)["till"] == Fraction(1, 120)
    assert metrics_of_model(model)["arrivals.discarded"] == 0.0


def test_a_store_stops_the_rate_because_its_orders_set_what_gets_through(
    make_model: ModelMaker,
) -> None:
    """Spec 1 "Validation": W201 is skipped for every server downstream of a store (AKS-106).
    Arrivals every 60 s into an empty store with ``reorder_point`` 0 that orders one unit at
    a time (lead time 120 s), then a server of service 90 s, 1,200 s. Passed on, the
    source's rate would load the server at 1.5 and raise W201; but the store lets one item
    through per delivery, at 120, 240, ..., 1,080 s, so the server keeps up: no item waits.
    Every one of the 20 arrivals finds no stock."""
    components = [
        source(),
        {
            "id": "shelf",
            "type": "store",
            "params": {
                "initial": 0,
                "reorder_point": 0,
                "order_quantity": 1,
                "lead_time": constant("120 s"),
            },
        },
        {"id": "till", "type": "server", "params": {"capacity": 1, "service": constant("90 s")}},
        sink(),
    ]
    model = make_model(components, chain("arrivals", "shelf", "till", "exit"), length="1200 s")
    rates = flow_rates(model)
    assert rates["shelf"] == Fraction(1, 60)
    assert rates["till"] is None and rates["exit"] is None
    assert load_issues(model) == []
    metrics = metrics_of_model(model)
    assert metrics["shelf.orders"] == 10 / 1200  # at 0, 120, ..., 1,080 s
    assert metrics["shelf.stockouts"] == 20.0
    assert metrics["till.wait.mean"] == 0.0
    assert metrics["till.queue_length.max"] == 0.0
    assert metrics["exit.count"] == 9.0  # at 210, 330, ..., 1,170 s


def test_a_schedule_is_checked_against_the_server_s_mean_capacity(
    make_model: ModelMaker,
) -> None:
    """Spec 1 "Validation" (#73, M4-40): a server under a schedule is checked against its
    mean scheduled capacity, and its rate is passed on. Arrivals every 60 s into a server
    of service 40 s on shift over [0, 100) of every 200 s, 1,200 s: a mean capacity of 1/2
    against a load of 2/3, so W201. The engine agrees: on shift it starts at most three
    items a period (at 200k, 200k + 40 and 200k + 80 s; only two in the first, which has
    two arrivals), so 17 of the 20 items leave and the queue grows."""
    components = [
        source(),
        {"id": "till", "type": "server", "params": {"capacity": 1, "service": constant("40 s")}},
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
    model = make_model(components, chain("arrivals", "till", "exit"), length="1200 s")
    rates = flow_rates(model)
    assert rates["till"] == rates["exit"] == Fraction(1, 60)
    assert [(issue.code, issue.component) for issue in load_issues(model)] == [("W201", "till")]
    metrics = metrics_of_model(model)
    assert metrics["arrivals.created"] == 20.0
    assert metrics["exit.count"] == 17.0
    assert metrics["till.queue_length.max"] >= 3.0


def test_a_failure_and_a_scheduled_pool_are_checked_against_their_mean_capacity(
    make_model: ModelMaker,
) -> None:
    """Spec 1 "Validation" (#73): a failure down 100 s after each 100 s leaves ``pack`` a
    mean capacity of 1/2, and the schedule leaves the pool ``staff`` 1/2, each against a
    load of 2/3 (one item per 60 s, 40 s each): W201 at both. The engine agrees: fewer
    items leave than arrive, and ``pack`` is available half the time."""
    components = [
        source(),
        {
            "id": "till",
            "type": "server",
            "params": {"capacity": 1, "service": constant("40 s"), "pool": "staff"},
        },
        {"id": "pack", "type": "server", "params": {"capacity": 1, "service": constant("40 s")}},
        {"id": "staff", "type": "resource_pool", "params": {"capacity": 1}},
        {
            "id": "rota",
            "type": "schedule",
            "params": {
                "target": "staff",
                "period": "200 s",
                "shifts": [{"start": "0 s", "end": "100 s", "capacity": 1}],
            },
        },
        {
            "id": "breakdown",
            "type": "failure",
            "params": {
                "target": "pack",
                "time_to_failure": constant("100 s"),
                "time_to_repair": constant("100 s"),
            },
        },
        sink(),
    ]
    model = make_model(components, chain("arrivals", "till", "pack", "exit"), length="1200 s")
    rates = flow_rates(model)
    assert rates["till"] == rates["pack"] == rates["exit"] == Fraction(1, 60)
    assert [(issue.code, issue.component) for issue in load_issues(model)] == [
        ("W201", "pack"),
        ("W201", "staff"),
    ]
    metrics = metrics_of_model(model)
    assert metrics["exit.count"] < metrics["arrivals.created"]
    assert metrics["pack.availability"] == 600 / 1200
