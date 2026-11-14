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


def test_a_store_stops_the_rate_propagation(
    make_model: ModelMaker,
) -> None:
    """Spec 1 "Validation": W201 is skipped for every server downstream of a store (AKS-106).
    Arrivals every 60 s into an empty store with ``reorder_point`` 0 that orders one unit at
    a time (lead time 120 s), then a server of service 90 s, 1,200 s. Since #72 the store
    reviews its textbook position at every demand: the 0 s review and each of the 20
    arrivals (each waits, bringing the position to 0) order one unit, 21 orders. So the
    store passes the source's rate on, 120 s late: items 0 and 1 at 120 s (two
    deliveries), item k at 60(k + 1) s, and the server, loaded at 1.5, falls behind. Its
    starts are at 120 + 90j s, so 11 items finish before the end (210 + 90j s, j = 0 to 10)
    and its queue reaches 7 (19 arrived and 12 started, at 1,140 s). W201 is still skipped
    here, as spec 1 says; #73 revisits a store's propagation."""
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
    assert metrics["shelf.orders"] == 21 / 1200  # twice at 0 s, then at 60, ..., 1,140 s
    assert metrics["shelf.stockouts"] == 20.0
    assert metrics["till.queue_length.max"] == 7.0
    assert metrics["exit.count"] == 11.0


def test_a_schedule_stops_the_rate_because_its_server_serves_less(
    make_model: ModelMaker,
) -> None:
    """Spec 1 "Validation": a schedule stops the rate at its target, which is not checked
    (AKS-107). Arrivals every 60 s into a server of service 40 s on shift over [0, 100) of
    every 200 s, 1,200 s. Its nominal load is 2/3, but on shift it starts at most three
    items a period (at 200k, 200k + 40 and 200k + 80 s; only two in the first, which has two
    arrivals), so 17 of the 20 items leave, not the 20 a propagated rate would give."""
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
    assert rates["till"] == Fraction(1, 60)
    assert rates["exit"] is None
    assert load_issues(model) == []
    metrics = metrics_of_model(model)
    assert metrics["arrivals.created"] == 20.0
    assert metrics["exit.count"] == 17.0
    assert metrics["till.queue_length.max"] >= 3.0


def test_a_failure_stops_the_rate_at_its_server_and_one_on_a_scheduled_pool(
    make_model: ModelMaker,
) -> None:
    """A failure stops the rate at its target, and a schedule on a pool stops it at every
    server of that pool; neither server is checked (spec 1 "Validation")."""
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
    assert rates["till"] == Fraction(1, 60)
    assert rates["pack"] is None and rates["exit"] is None
    assert load_issues(model) == []
    metrics = metrics_of_model(model)
    assert metrics["exit.count"] < metrics["arrivals.created"]
    assert metrics["pack.availability"] == 600 / 1200
