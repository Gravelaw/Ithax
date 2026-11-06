"""The ``branch`` block (spec 2 "Block reference", "Branch rules" and "Blocking"; AKS-99).

``probability`` draws one uniform number per item from the branch's own stream and takes
the first route whose running sum of weights exceeds it times the total; ``shortest_queue``
draws nothing and takes the route whose next block has the fewest waiting items, the
earliest on a tie. The route is chosen when the item arrives; a refused item stays at the
branch until space frees.
"""

import math
from collections.abc import Generator, Mapping, Sequence
from time import monotonic
from typing import Any

import pytest
import simpy
from conftest import ContextMaker, ModelMaker, Recorder, recorder

from lcsim.engines.process.blocks import BLOCK_TYPES, Block, Branch, Context, Item, Server
from lcsim.engines.process.replication import run_replication
from lcsim.engines.process.translate import engine_input
from lcsim.model.catalogue import PROCESS_TYPES
from lcsim.model.streams import generator_for


def branch(
    context: Context,
    routes: Sequence[str],
    rule: str,
    weights: Mapping[str, float] | None = None,
) -> Branch:
    settings: dict[str, Any] = {"routes": list(routes), "rule": rule}
    if weights is not None:
        settings["weights"] = dict(weights)
    return Branch("check", settings, context, generator_for(5, 0, "check"))


def wire(context: Context, block: Branch, **queued: int) -> dict[str, Recorder]:
    outs = {
        route: recorder(context, queued=queued.get(route, 0), name=route) for route in block.routes
    }
    for route, out in outs.items():
        block.connect(route, out)
    return outs


def send(context: Context, block: Block, count: int) -> list[Item]:
    items = [Item(created=0.0, arrived=0.0) for _ in range(count)]
    for item in items:
        block.receive(item)
    return items


def test_the_branch_type_is_registered() -> None:
    assert BLOCK_TYPES["branch"] is Branch


def test_output_ports_are_the_routes(make_context: ContextMaker) -> None:
    context = make_context(0.0, 1.0)
    block = branch(context, ["direct", "inspect"], "shortest_queue")
    assert block.ports() == ("direct", "inspect")
    block.connect("direct", recorder(context))
    with pytest.raises(ValueError, match="'check' has no output port 'out'"):
        block.connect("out", recorder(context))
    assert block.accepts()
    assert block.waiting_items() == 0
    assert block.metrics() == {}
    assert tuple(block.metrics()) == PROCESS_TYPES["branch"].metrics


def test_probability_follows_the_stream_draw_by_draw(make_context: ContextMaker) -> None:
    context = make_context(0.0, 1.0)
    block = branch(context, ["a", "b", "c"], "probability", {"a": 1.0, "b": 2.0, "c": 1.0})
    outs = wire(context, block)
    items = send(context, block, 2000)
    stream = generator_for(5, 0, "check")
    expected: dict[str, list[Item]] = {"a": [], "b": [], "c": []}
    for item in items:
        u = stream.random() * 4.0
        expected["a" if u < 1.0 else "b" if u < 3.0 else "c"].append(item)
    for route, out in outs.items():
        assert out.items == expected[route], route


def test_probability_splits_by_weight_over_sum(make_context: ContextMaker) -> None:
    """20,000 items, weights 0.3 and 0.7: each count within four standard errors."""
    context = make_context(0.0, 1.0)
    block = branch(context, ["a", "b"], "probability", {"a": 0.3, "b": 0.7})
    outs = wire(context, block)
    n = 20_000
    send(context, block, n)
    error = math.sqrt(n * 0.3 * 0.7)
    assert abs(len(outs["a"].items) - 0.3 * n) <= 4 * error
    assert len(outs["a"].items) + len(outs["b"].items) == n


def test_a_route_of_weight_zero_is_never_taken_but_each_item_draws(
    make_context: ContextMaker,
) -> None:
    context = make_context(0.0, 1.0)
    block = branch(context, ["a", "b", "c"], "probability", {"a": 0.0, "b": 5.0, "c": 0.0})
    outs = wire(context, block)
    send(context, block, 500)
    assert len(outs["b"].items) == 500
    stream = generator_for(5, 0, "check")
    stream.random(500)
    assert block.rng.random() == stream.random()  # one draw per item


def test_shortest_queue_takes_the_fewest_waiting_items(make_context: ContextMaker) -> None:
    context = make_context(0.0, 1.0)
    block = branch(context, ["a", "b", "c"], "shortest_queue")
    outs = wire(context, block, a=3, b=1, c=2)
    send(context, block, 1)
    assert [len(outs[route].items) for route in "abc"] == [0, 1, 0]


def test_shortest_queue_ties_go_to_the_earliest_route(make_context: ContextMaker) -> None:
    context = make_context(0.0, 1.0)
    block = branch(context, ["a", "b", "c"], "shortest_queue")
    outs = wire(context, block, a=2, b=1, c=1)
    send(context, block, 3)
    assert [len(outs[route].items) for route in "abc"] == [0, 3, 0]


def test_shortest_queue_draws_nothing_and_ignores_weights(make_context: ContextMaker) -> None:
    context = make_context(0.0, 1.0)
    block = branch(context, ["a", "b"], "shortest_queue", {"a": 0.0, "b": 1.0})
    outs = wire(context, block)
    before = block.rng.bit_generator.state
    send(context, block, 100)
    assert block.rng.bit_generator.state == before
    assert len(outs["a"].items) == 100  # both count 0: the earliest route


def server(context: Context, name: str) -> Server:
    return Server(
        name,
        {"capacity": 1, "service": {"dist": "constant", "value": 10.0}, "discipline": "fifo"},
        context,
        generator_for(5, 0, name),
    )


def test_shortest_queue_counts_a_server_s_queue_not_its_units(
    make_context: ContextMaker,
) -> None:
    """A server's waiting items are its queue: a busy unit with an empty queue counts 0.
    Item 1 goes to a (into service; a still counts 0), item 2 to a (ties go to a; a's queue
    is 1), items 3 and 4 to b (into service, then b's queue is 1), item 5 to a (1 and 1)."""
    context = make_context(0.0, 100.0)
    block = branch(context, ["a", "b"], "shortest_queue")
    servers = {name: server(context, name) for name in ("a", "b")}
    for name, target in servers.items():
        block.connect(name, target)
        target.connect("out", recorder(context, name=f"{name}_out"))
    send(context, block, 5)
    assert servers["a"].busy == 1 and len(servers["a"].waiting) == 2
    assert servers["b"].busy == 1 and len(servers["b"].waiting) == 1


def test_a_refused_item_waits_at_the_branch(make_context: ContextMaker) -> None:
    """The route is chosen on arrival: both items wait for route a, which reopens at 5 s,
    even though route b is open throughout."""
    context = make_context(0.0, 100.0)
    block = branch(context, ["a", "b"], "probability", {"a": 1.0, "b": 0.0})
    outs = wire(context, block)
    outs["a"].open = False
    items = send(context, block, 2)
    assert outs["a"].items == [] and outs["b"].items == []

    def reopen() -> Generator[simpy.Event, Any, None]:
        yield context.env.timeout(5.0)
        outs["a"].open = True
        outs["a"].space_freed()

    context.env.process(reopen())
    context.env.run(until=100.0)
    assert outs["a"].items == items
    assert outs["a"].times == [5.0, 5.0]


def test_an_unknown_rule_is_refused(make_context: ContextMaker) -> None:
    with pytest.raises(ValueError, match="'check' has rule 'attribute'"):
        branch(make_context(0.0, 1.0), ["a"], "attribute")


def test_huge_weights_split_by_weight_over_sum(make_context: ContextMaker) -> None:
    """Weights of 1e308 each are valid, but their plain sum overflows to infinity: the
    weights are scaled by the largest before summing, so the split stays even (review of
    PR #18)."""
    context = make_context(0.0, 1.0)
    block = branch(context, ["a", "b"], "probability", {"a": 1e308, "b": 1e308})
    outs = wire(context, block)
    n = 20_000
    send(context, block, n)
    assert abs(len(outs["a"].items) - n / 2) <= 4 * math.sqrt(n / 4)


def test_a_branch_looping_to_itself_does_not_recurse(make_model: ModelMaker) -> None:
    """A branch whose route leads straight back to it, weighted 9999 to 1: thousands of
    passes at one instant run one after another, not nested (review of PR #18)."""
    components = [
        {
            "id": "arrivals",
            "type": "source",
            "params": {"interarrival": {"dist": "constant", "value": "1 min"}},
        },
        {
            "id": "check",
            "type": "branch",
            "params": {
                "routes": ["again", "out"],
                "rule": "probability",
                "weights": {"again": 9999, "out": 1},
            },
        },
        {"id": "exit", "type": "sink", "params": {}},
    ]
    connections = [
        ("arrivals.out", "check.in"),
        ("check.again", "check.in"),
        ("check.out", "exit.in"),
    ]
    engine = engine_input(make_model(components, connections, length="10 min"), "e")
    outcome = run_replication(engine, 0, 0, lambda: False)
    assert outcome is not None
    metrics = {metric: value for metric, value, _ in outcome.rows}
    # Every item leaves at the instant it arrives: ten items, 0 to 540 s.
    assert metrics["exit.count"] == 10.0
    assert metrics["exit.cycle_time.mean"] == 0.0


def test_an_endless_zero_time_loop_can_still_be_stopped(make_model: ModelMaker) -> None:
    """A ``shortest_queue`` branch whose first route leads back to itself: the branch and
    the sink both count 0 waiting items, so the tie always takes the loop and the item
    never leaves that instant. The transfers ask ``should_stop`` as events do, so the
    replication still stops when asked (review of PR #18)."""
    components = [
        {
            "id": "arrivals",
            "type": "source",
            "params": {"interarrival": {"dist": "constant", "value": "1 min"}},
        },
        {
            "id": "check",
            "type": "branch",
            "params": {"routes": ["again", "out"], "rule": "shortest_queue"},
        },
        {"id": "exit", "type": "sink", "params": {}},
    ]
    connections = [
        ("arrivals.out", "check.in"),
        ("check.again", "check.in"),
        ("check.out", "exit.in"),
    ]
    engine = engine_input(make_model(components, connections, length="10 min"), "e")
    calls: list[int] = []

    def stop_on_third_check() -> bool:
        calls.append(1)
        return len(calls) == 3

    started = monotonic()
    assert run_replication(engine, 0, 0, stop_on_third_check) is None
    assert len(calls) == 3
    assert monotonic() - started < 1.0
