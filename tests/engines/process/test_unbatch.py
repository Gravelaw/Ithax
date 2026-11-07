"""The ``unbatch`` block (spec 2 "Block reference" and "Batch timeout"; AKS-105).

An unbatch splits whatever it receives into the units it holds, one level of batching, and
sends them on at once in the order the batch collected them; a single item passes through
unchanged. It always accepts: items the next block refuses wait at the unbatch, in order,
until space frees there.
"""

from typing import Any

from conftest import ContextMaker, ModelMaker, constant, metrics_of_model, recorder

from lcsim.engines.process.blocks import BLOCK_TYPES, Batch, Context, Item, Unbatch
from lcsim.model.catalogue import PROCESS_TYPES
from lcsim.model.streams import generator_for


def block_unbatch(context: Context) -> Unbatch:
    return Unbatch("unpack", {}, context, generator_for(7, 0, "unpack"))


def test_the_unbatch_type_is_registered_without_metrics(make_context: ContextMaker) -> None:
    assert BLOCK_TYPES["unbatch"] is Unbatch
    assert PROCESS_TYPES["unbatch"].metrics == ()
    block = block_unbatch(make_context(0.0, 1.0))
    assert block.metrics() == {} and block.levels() == {}


def test_a_batch_is_split_into_its_items_in_order(make_context: ContextMaker) -> None:
    context = make_context(0.0, 10.0)
    block = block_unbatch(context)
    out = recorder(context)
    block.connect("out", out)
    items = (Item(0.0, 0.0), Item(1.0, 1.0), Item(2.0, 2.0))
    block.receive(Item(0.0, 2.0, contents=items))
    assert out.items == list(items)
    assert out.times == [0.0, 0.0, 0.0]


def test_a_single_item_passes_through(make_context: ContextMaker) -> None:
    context = make_context(0.0, 10.0)
    block = block_unbatch(context)
    out = recorder(context)
    block.connect("out", out)
    item = Item(0.0, 0.0)
    block.receive(item)
    assert out.items == [item]


def test_nested_batches_are_split_one_level(make_context: ContextMaker) -> None:
    """Pairs batched in threes: the unbatch passes on three pairs."""
    context = make_context(0.0, 10.0)
    pairs = Batch("pairs", {"size": 2}, context, generator_for(7, 0, "pairs"))
    sixes = Batch("sixes", {"size": 3}, context, generator_for(7, 0, "sixes"))
    block = block_unbatch(context)
    out = recorder(context)
    pairs.connect("out", sixes)
    sixes.connect("out", block)
    block.connect("out", out)
    for _ in range(6):
        pairs.receive(Item(0.0, 0.0))
    assert [unit.count() for unit in out.items] == [2, 2, 2]


def test_refused_items_wait_at_the_unbatch_in_order(make_model: ModelMaker) -> None:
    """Arrivals every 100 s into a batch of 3, an unbatch, then a server (service 50 s,
    ``queue_capacity`` 0), 600 s. Items 0 to 2 reach the unbatch at 200 s: item 0 is served
    [200, 250), item 1 [250, 300), item 2 [300, 350). Items 3 to 5 arrive together at 500 s:
    item 3 [500, 550), item 4 [550, 600); item 5 waits. Nothing is discarded."""
    components: list[dict[str, Any]] = [
        {"id": "arrivals", "type": "source", "params": {"interarrival": constant("100 s")}},
        {"id": "pack", "type": "batch", "params": {"size": 3}},
        {"id": "unpack", "type": "unbatch", "params": {}},
        {
            "id": "till",
            "type": "server",
            "params": {"capacity": 1, "service": constant("50 s"), "queue_capacity": 0},
        },
        {"id": "exit", "type": "sink", "params": {}},
    ]
    connections = [
        ("arrivals.out", "pack.in"),
        ("pack.out", "unpack.in"),
        ("unpack.out", "till.in"),
        ("till.out", "exit.in"),
    ]
    metrics = metrics_of_model(make_model(components, connections, length="600 s"))
    assert metrics["arrivals.discarded"] == 0.0
    assert metrics["exit.count"] == 4.0  # at 250, 300, 350 and 550 s
    assert metrics["exit.cycle_time.mean"] == (250 + 200 + 150 + 250) / 4
    assert metrics["till.utilization"] == 250 / 600
    assert metrics["pack.wait.mean"] == (200 + 100 + 0 + 200 + 100 + 0) / 6


def test_an_unbatch_always_accepts(make_context: ContextMaker) -> None:
    context = make_context(0.0, 10.0)
    block = block_unbatch(context)
    block.connect("out", recorder(context, open=False))
    block.receive(Item(0.0, 0.0, contents=(Item(0.0, 0.0), Item(0.0, 0.0))))
    assert block.accepts()
    assert block.waiting_items() == 0
