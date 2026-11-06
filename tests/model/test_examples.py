"""The three example models in ``examples/`` (spec 1 acceptance, M1 row 1; AKS-93).

Spec 1 "Acceptance tests": "The three example models in `examples/` load with zero
issues". Spec 2 "Reference values from the prototype" sets the targets for the two files
written fresh at M1 (proposed default, owner to confirm): three-machine line, weld
utilization 0.85 to 0.92 and the other stations below 0.70; warehouse, throughput within
1% of 60 per hour and pack utilization 0.75 to 0.85; M2 blocks only.

The targets are checked here by closed-form queueing arithmetic only (guide rule 7):
utilization = arrival rate x mean service time / capacity; the mean wait of an M/M/1
station is rho / (1 - rho) x mean service time and of an M/M/c station Erlang C /
(c / s - rate). Burke's theorem makes each station of these open lines see Poisson
arrivals, so the per-station formulas hold. The models are run at M2.
"""

import json
import math
from fractions import Fraction
from pathlib import Path

import pytest

from lcsim.model.loading import load_model, load_text
from lcsim.model.model import Component, Distribution, Model
from lcsim.model.units import Dimension, Quantity
from lcsim.model.validation import distribution_mean, flow_rates, meaning_pass

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = ROOT / "examples"
EXAMPLES = sorted(EXAMPLES_DIR.glob("*.json"))
TIME = Dimension.TIME

# Spec 2 "Detailed specification": "The prototype exercised `source`, `server`, `delay`,
# `branch` with the `probability` rule, and `sink`" -- the M2 blocks.
M2_BLOCKS = {"source", "server", "delay", "branch", "sink"}

PER_HOUR = Fraction(1, 3600)  # one item per hour, in items per second


def minutes(value: float) -> Quantity:
    return Quantity(value * 60.0, TIME)


def hours(value: float) -> Quantity:
    return Quantity(value * 3600.0, TIME)


def exponential(mean_minutes: float) -> Distribution:
    return Distribution("exponential", {"mean": minutes(mean_minutes)})


def model(name: str) -> Model:
    return load_model(EXAMPLES_DIR / f"{name}.json")


def by_id(loaded: Model) -> dict[str, Component]:
    return {component.id: component for component in loaded.components}


def chain(loaded: Model) -> list[tuple[str, str]]:
    return [
        (f"{c.origin.component}.{c.origin.port}", f"{c.destination.component}.{c.destination.port}")
        for c in loaded.connections
    ]


def mean_of(loaded: Model, component: Component, setting: str) -> Fraction:
    distribution = component.settings[setting]
    assert isinstance(distribution, Distribution)
    mean = distribution_mean(loaded, distribution)
    assert mean is not None
    return mean


def capacity(component: Component) -> int:
    value = component.settings["capacity"]
    assert isinstance(value, int)
    return value


def utilization(loaded: Model, server: str) -> Fraction:
    """rho = arrival rate x mean service time / capacity, the rate propagated as for W201."""
    rate = flow_rates(loaded)[server]
    assert rate is not None
    component = by_id(loaded)[server]
    return rate * mean_of(loaded, component, "service") / capacity(component)


def mm1_wait(rho: Fraction, service: Fraction) -> Fraction:
    return rho / (1 - rho) * service


def erlang_c(servers: int, offered: Fraction) -> Fraction:
    """Probability of waiting in M/M/c with offered load ``offered`` = rate x service."""
    top = offered**servers / math.factorial(servers) * servers / (servers - offered)
    below = sum(offered**k / math.factorial(k) for k in range(servers))
    return top / (below + top)


# --- every example ------------------------------------------------------------------------------


def test_the_examples_are_the_three_the_guide_names() -> None:
    # Build guide "Repository layout": coffee_shop.json, three_machine_line.json, warehouse.json.
    assert [path.name for path in EXAMPLES] == [
        "coffee_shop.json",
        "three_machine_line.json",
        "warehouse.json",
    ]


@pytest.mark.parametrize("path", EXAMPLES, ids=[path.stem for path in EXAMPLES])
def test_every_example_loads_with_zero_issues(path: Path) -> None:
    # Spec 1 acceptance, M1 row 1: no error and no warning, through the whole validator.
    result = load_text(path.read_bytes())
    assert result.issues == ()
    assert result.model is not None
    assert meaning_pass(result.model) == []
    assert isinstance(load_model(path), Model)


@pytest.mark.parametrize("path", EXAMPLES, ids=[path.stem for path in EXAMPLES])
def test_every_example_uses_m2_blocks_only(path: Path) -> None:
    loaded = load_model(path)
    assert loaded.domain == "process"
    assert {component.type for component in loaded.components} <= M2_BLOCKS


@pytest.mark.parametrize("path", EXAMPLES, ids=[path.stem for path in EXAMPLES])
def test_every_example_experiment_has_a_fixed_seed_and_a_warmup(path: Path) -> None:
    # Spec 1 "What the prototype changed", item 4: experiments carry a `seed`.
    loaded = load_model(path)
    assert loaded.experiments
    for experiment in loaded.experiments:
        assert not experiment.seed_chosen
        assert experiment.warmup.magnitude > 0
        assert experiment.replications == 30


@pytest.mark.parametrize("path", EXAMPLES, ids=[path.stem for path in EXAMPLES])
def test_every_example_file_is_valid_utf8_json(path: Path) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["format_version"] == "0.1"


# --- three_machine_line.json --------------------------------------------------------------------


def test_three_machine_line_structure() -> None:
    loaded = model("three_machine_line")
    assert loaded.meta.name == "Three-machine line"
    assert [(c.id, c.type) for c in loaded.components] == [
        ("arrivals", "source"),
        ("cut", "server"),
        ("weld", "server"),
        ("transfer", "delay"),
        ("paint", "server"),
        ("exit", "sink"),
    ]
    assert chain(loaded) == [
        ("arrivals.out", "cut.in"),
        ("cut.out", "weld.in"),
        ("weld.out", "transfer.in"),
        ("transfer.out", "paint.in"),
        ("paint.out", "exit.in"),
    ]
    assert loaded.parameters == {}


def test_three_machine_line_settings() -> None:
    components = by_id(model("three_machine_line"))
    assert components["arrivals"].settings == {"interarrival": exponential(2)}
    assert components["cut"].settings == {"capacity": 1, "service": exponential(1.2)}
    assert components["weld"].settings == {"capacity": 1, "service": exponential(1.8)}
    assert components["transfer"].settings == {
        "time": Distribution("constant", {"value": minutes(2)})
    }
    assert components["paint"].settings == {"capacity": 1, "service": exponential(1)}
    assert components["exit"].settings == {}


def test_three_machine_line_experiment() -> None:
    (experiment,) = model("three_machine_line").experiments
    assert experiment.id == "base"
    assert experiment.length == hours(100)
    assert experiment.warmup == hours(20)
    assert experiment.seed == 12345


def test_three_machine_line_meets_the_spec_2_utilization_targets() -> None:
    loaded = model("three_machine_line")
    assert flow_rates(loaded)["exit"] == 30 * PER_HOUR
    rho = {server: utilization(loaded, server) for server in ("cut", "weld", "paint")}
    assert rho == {"cut": Fraction(3, 5), "weld": Fraction(9, 10), "paint": Fraction(1, 2)}
    # Spec 2 target: weld 0.85 to 0.92, the other stations below 0.70.
    assert Fraction(85, 100) <= rho["weld"] <= Fraction(92, 100)
    assert rho["cut"] < Fraction(7, 10)
    assert rho["paint"] < Fraction(7, 10)
    # Spec 4 "Finding rules": `bottleneck` needs the weld station to be the single highest
    # and at least 0.85; `idle_capacity` (below 0.30) must not fire on any station.
    assert max(rho, key=rho.__getitem__) == "weld"
    assert sorted(rho.values())[-2] < rho["weld"]
    assert min(rho.values()) >= Fraction(3, 10)


def test_three_machine_line_waits_and_cycle_time() -> None:
    loaded = model("three_machine_line")
    components = by_id(loaded)
    minute = Fraction(60)
    waits = {
        server: mm1_wait(
            utilization(loaded, server), mean_of(loaded, components[server], "service")
        )
        for server in ("cut", "weld", "paint")
    }
    assert waits == {
        "cut": Fraction(18, 10) * minute,
        "weld": Fraction(162, 10) * minute,
        "paint": 1 * minute,
    }
    sojourn = sum(
        waits[server] + mean_of(loaded, components[server], "service")
        for server in ("cut", "weld", "paint")
    )
    cycle_time = sojourn + mean_of(loaded, components["transfer"], "time")
    assert cycle_time == 25 * minute


def test_three_machine_line_description_states_the_arithmetic() -> None:
    description = model("three_machine_line").meta.description
    assert description is not None
    for text in ("0.60", "0.90", "0.50", "16.2 min", "25.0 min", "30 per hour"):
        assert text in description


# --- warehouse.json -----------------------------------------------------------------------------


def test_warehouse_structure() -> None:
    loaded = model("warehouse")
    assert loaded.meta.name == "Warehouse"
    assert [(c.id, c.type) for c in loaded.components] == [
        ("orders", "source"),
        ("pick", "server"),
        ("check", "branch"),
        ("inspection", "delay"),
        ("pack", "server"),
        ("dispatch", "sink"),
    ]
    assert chain(loaded) == [
        ("orders.out", "pick.in"),
        ("pick.out", "check.in"),
        ("check.direct", "pack.in"),
        ("check.inspect", "inspection.in"),
        ("inspection.out", "pack.in"),
        ("pack.out", "dispatch.in"),
    ]
    assert loaded.parameters == {}


def test_warehouse_settings() -> None:
    components = by_id(model("warehouse"))
    assert components["orders"].settings == {"interarrival": exponential(1)}
    assert components["pick"].settings == {"capacity": 3, "service": exponential(2)}
    assert components["check"].settings == {
        "routes": ("direct", "inspect"),
        "rule": "probability",
        "weights": {"direct": 4, "inspect": 1},
    }
    assert components["inspection"].settings == {
        "time": Distribution("constant", {"value": minutes(5)})
    }
    assert components["pack"].settings == {"capacity": 1, "service": exponential(0.8)}
    assert components["dispatch"].settings == {}


def test_warehouse_experiment() -> None:
    (experiment,) = model("warehouse").experiments
    assert experiment.id == "base"
    assert experiment.length == hours(200)
    assert experiment.warmup == hours(10)
    assert experiment.seed == 12345


def test_warehouse_meets_the_spec_2_targets() -> None:
    loaded = model("warehouse")
    rates = flow_rates(loaded)
    # No block loses items and every server is stable, so the long-run throughput is the
    # arrival rate: 60 per hour, inside the 1% target band.
    assert rates["dispatch"] == 60 * PER_HOUR
    assert rates["inspection"] == 12 * PER_HOUR
    assert rates["pack"] == 60 * PER_HOUR
    rho = {server: utilization(loaded, server) for server in ("pick", "pack")}
    assert rho == {"pick": Fraction(2, 3), "pack": Fraction(4, 5)}
    assert Fraction(75, 100) <= rho["pack"] <= Fraction(85, 100)


def test_warehouse_waits_and_cycle_time() -> None:
    loaded = model("warehouse")
    components = by_id(loaded)
    minute = Fraction(60)
    rate = Fraction(1, 60)  # one order per minute, per second
    pick_service = mean_of(loaded, components["pick"], "service")
    pick_c = erlang_c(3, rate * pick_service)
    assert pick_c == Fraction(4, 9)
    pick_wait = pick_c / (3 / pick_service - rate)
    assert pick_wait == Fraction(8, 9) * minute
    pack_service = mean_of(loaded, components["pack"], "service")
    pack_wait = mm1_wait(utilization(loaded, "pack"), pack_service)
    assert pack_wait == Fraction(32, 10) * minute
    inspection = Fraction(1, 5) * mean_of(loaded, components["inspection"], "time")
    cycle_time = pick_wait + pick_service + inspection + pack_wait + pack_service
    assert cycle_time == Fraction(71, 9) * minute


def test_warehouse_description_states_the_arithmetic() -> None:
    description = model("warehouse").meta.description
    assert description is not None
    for text in ("60 per hour", "0.667", "0.80", "4/9", "0.889 min", "3.2 min", "7.889 min"):
        assert text in description
