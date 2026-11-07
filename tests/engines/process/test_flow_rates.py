"""The W201 flow rates against the blocks that now run (spec 1 "Validation"; AKS-105).

Validation propagates a mean rate from each source: a batch divides it by ``size``, an
unbatch multiplies it by the size of what it receives, and a loss point (a discarding
``queue``, a source feeding a block that can refuse an item) stops it, since less than the
offered rate gets through. These tests run deterministic models in the adapter and check
the rates the blocks really pass against ``flow_rates``.
"""

from fractions import Fraction
from itertools import pairwise
from typing import Any

import pytest
from conftest import ModelMaker, constant, metrics_of_model

from lcsim.model.validation import flow_rates, load_issues


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
