"""The ``process`` type catalogue and the distribution table, kept as data.

Spec 1 "Validation": component type descriptions (settings, ports) come from the adapter's
``Capabilities``; until the process adapter exists (M2) the model layer carries the
``process`` type catalogue from spec 2 "Block reference", and at M2 the adapter's
``capabilities()`` must equal it (tested). This module is that catalogue. It holds only
data; the loader (``lcsim.model.loading``) and the meaning pass read it.

Sources, all binding text:

- spec 2 "Block reference": the twelve types, their ports and settings, and the rules that
  apply across blocks (`discipline` `fifo` by default, `on_full` `block` by default,
  `period` 24 h by default);
- spec 1 "Components and ports": a source has only `out`, a sink only `in`, a branch one
  output port per entry of `routes`;
- spec 1 "Distributions": the eight distributions and their fields;
- spec 2 "Statistic definitions": the metrics each type reports (spec 1 "Metric names",
  E174), and what each is measured in (a time, a rate per second, or a plain number);
- the smallest value each number or time setting takes, and the distribution fields that
  must be above zero or in order (spec 1 "Distributions", E160), read by the meaning pass.

Where spec 2 leaves a setting's kind open, the simplest reading is taken and recorded in
``docs/DECISIONS.md`` (2026-11-06 · M1, AKS-88): counts, capacities and stock levels are
whole numbers; `first_arrival` and `timeout` are time quantities; a branch's output port
is named by its route. The smallest values are readings of the same kind (AKS-90): a
capacity, size, order quantity or `max_items` is at least 1, since a smaller one never
passes an item; a `queue_capacity`, stock level or shift capacity is at least 0; a weight
is at least 0; `first_arrival` is at least 0 s; `timeout` and `period` are above 0 s; a
branch has at least one route.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from lcsim.model.units import Dimension, Quantity

__all__ = [
    "DATA_FIELDS",
    "DISTRIBUTIONS",
    "DOMAINS",
    "MEASURE_KINDS",
    "MODEL_METRICS",
    "PROCESS_TYPES",
    "BlockType",
    "DistributionSpec",
    "FieldKind",
    "FieldSpec",
    "MeasureKind",
    "SettingKind",
    "SettingSpec",
    "output_ports",
]

# Spec 1 "Top-level keys": the Phase 1 values of `domain`.
DOMAINS: tuple[str, ...] = ("process", "optimization")


class SettingKind(Enum):
    """What a setting takes (spec 1 "Components and ports"; spec 2 "Block reference")."""

    NUMBER = "number"  # a plain JSON number, or a {"$param": id} reference
    QUANTITY = "quantity"  # a quantity of `dimension`, or a {"$param": id} reference
    DISTRIBUTION = "distribution"  # a distribution object of spec 1 "Distributions"
    IDENTIFIER = "identifier"  # a name: a component, a route, or a word from `choices`
    OBJECT = "object"  # an object with fixed `fields`, or keyed by another setting


@dataclass(frozen=True)
class SettingSpec:
    """One setting of a component type, or one field of an object setting."""

    name: str
    kind: SettingKind
    required: bool
    # QUANTITY and DISTRIBUTION: the dimension of the value (of each field of a
    # distribution that is not a plain number).
    dimension: Dimension | None = None
    # NUMBER: whether only whole numbers are allowed.
    integer: bool = False
    # Any kind: the setting is an array of values of this kind.
    many: bool = False
    # IDENTIFIER: the words allowed; empty means any identifier.
    choices: tuple[str, ...] = ()
    # IDENTIFIER: the component types the name must refer to; empty for none.
    refers_to: tuple[str, ...] = ()
    # OBJECT with fixed keys: one spec per key.
    fields: tuple[SettingSpec, ...] = ()
    # OBJECT keyed by the entries of another setting (`weights` by `routes`), with each
    # value described by `values`.
    keyed_by: str | None = None
    values: SettingSpec | None = None
    # Not required in general, but required when the setting named first holds the word
    # named second (`weights` when `rule` is `probability`).
    required_when: tuple[str, str] | None = None
    # NUMBER and QUANTITY: the smallest value allowed (in SI units for a quantity), or
    # None; with `exclusive_minimum`, the value must be above it.
    minimum: int | float | None = None
    exclusive_minimum: bool = False
    # `many`: the fewest entries allowed.
    min_items: int = 0
    # The default the spec states for an optional setting, if any; the loader leaves an
    # absent setting absent, and the engine applies this.
    default: str | Quantity | None = None


@dataclass(frozen=True)
class BlockType:
    """One component type of the ``process`` domain."""

    name: str
    inputs: tuple[str, ...]
    # Fixed output ports; empty when there are none or when they come from a setting.
    outputs: tuple[str, ...]
    # The setting whose entries name the output ports (`routes` for a branch), or None.
    outputs_from: str | None
    settings: tuple[SettingSpec, ...]
    # Metric names after `<component id>.` (spec 2 "Statistic definitions").
    metrics: tuple[str, ...]
    # One sentence on what the type does, from spec 2 "Block reference" (its Behaviour
    # column), served by GET /v1/schema/components/{type} (spec 3; AKS-110).
    description: str = ""

    def setting(self, name: str) -> SettingSpec | None:
        """The setting called ``name``, or ``None`` when the type has no such setting."""
        return next((spec for spec in self.settings if spec.name == name), None)


def output_ports(block: BlockType, routes: Sequence[str]) -> tuple[str, ...]:
    """The output ports of a component of ``block``; ``routes`` are its route entries.

    Spec 1 "Components and ports": a branch has one output port per entry of its
    ``routes`` setting, named by the entry. Other types have fixed ports.
    """
    if block.outputs_from is not None:
        return tuple(routes)
    return block.outputs


def _number(
    name: str, *, required: bool = True, integer: bool = True, minimum: int = 0
) -> SettingSpec:
    return SettingSpec(name, SettingKind.NUMBER, required, integer=integer, minimum=minimum)


def _time(
    name: str,
    *,
    required: bool = True,
    default: Quantity | None = None,
    above_zero: bool = False,
) -> SettingSpec:
    return SettingSpec(
        name,
        SettingKind.QUANTITY,
        required,
        dimension=Dimension.TIME,
        default=default,
        minimum=0,
        exclusive_minimum=above_zero,
    )


def _distribution(name: str) -> SettingSpec:
    return SettingSpec(name, SettingKind.DISTRIBUTION, True, dimension=Dimension.TIME)


def _word(name: str, choices: tuple[str, ...], default: str | None) -> SettingSpec:
    required = default is None
    return SettingSpec(name, SettingKind.IDENTIFIER, required, choices=choices, default=default)


def _reference(name: str, refers_to: tuple[str, ...], *, required: bool = True) -> SettingSpec:
    return SettingSpec(name, SettingKind.IDENTIFIER, required, refers_to=refers_to)


_DISCIPLINE = ("fifo", "lifo")

# Spec 2 "Statistic definitions", by component type.
_SERVER_METRICS = (
    "wait.mean",
    "utilization",
    "availability",
    "scheduled_fraction",
    "queue_length.mean",
    "queue_length.max",
)

PROCESS_TYPES: Mapping[str, BlockType] = MappingProxyType(
    {
        block.name: block
        for block in (
            BlockType(
                "source",
                inputs=(),
                outputs=("out",),
                outputs_from=None,
                settings=(
                    _distribution("interarrival"),
                    _time("first_arrival", required=False),
                    _number("max_items", required=False, minimum=1),
                ),
                metrics=("created", "discarded"),
                description=(
                    "Creates one item, waits one interarrival time, and repeats; the first item "
                    "arrives at first_arrival, and the source stops after max_items items."
                ),
            ),
            BlockType(
                "server",
                inputs=("in",),
                outputs=("out",),
                outputs_from=None,
                settings=(
                    _number("capacity", minimum=1),
                    _distribution("service"),
                    # Absent: the server's queue is unlimited (spec 2 "Server queue").
                    _number("queue_capacity", required=False),
                    _word("discipline", _DISCIPLINE, "fifo"),
                    _reference("pool", ("resource_pool",), required=False),
                ),
                metrics=_SERVER_METRICS,
                description=(
                    "Items wait in the server's own queue, then hold one unit of capacity for one "
                    "service time."
                ),
            ),
            BlockType(
                "delay",
                inputs=("in",),
                outputs=("out",),
                outputs_from=None,
                settings=(_distribution("time"),),
                metrics=(),
                description=(
                    "Holds each item for the sampled time, with no queue and no capacity limit."
                ),
            ),
            BlockType(
                "branch",
                inputs=("in",),
                outputs=(),
                outputs_from="routes",
                settings=(
                    SettingSpec("routes", SettingKind.IDENTIFIER, True, many=True, min_items=1),
                    _word("rule", ("probability", "shortest_queue"), None),
                    SettingSpec(
                        "weights",
                        SettingKind.OBJECT,
                        False,
                        keyed_by="routes",
                        values=_number("weight", integer=False),
                        required_when=("rule", "probability"),
                    ),
                ),
                metrics=(),
                description=(
                    "Sends each item down one of its routes, by probability or to the shortest "
                    "queue."
                ),
            ),
            BlockType(
                "queue",
                inputs=("in",),
                outputs=("out",),
                outputs_from=None,
                settings=(
                    _number("capacity", minimum=1),
                    _word("discipline", _DISCIPLINE, "fifo"),
                    _word("on_full", ("block", "discard"), "block"),
                ),
                metrics=("queue_length.mean", "queue_length.max", "wait.mean", "discarded"),
                description=("A standalone buffer, for use ahead of a batch or branch."),
            ),
            BlockType(
                "batch",
                inputs=("in",),
                outputs=("out",),
                outputs_from=None,
                settings=(
                    _number("size", minimum=1),
                    _time("timeout", required=False, above_zero=True),
                ),
                metrics=("wait.mean",),
                description=("Collects size items and releases them as one."),
            ),
            BlockType(
                "unbatch",
                inputs=("in",),
                outputs=("out",),
                outputs_from=None,
                settings=(),
                metrics=(),
                description=("Splits a batch back into its items."),
            ),
            BlockType(
                "store",
                inputs=("in",),
                outputs=("out",),
                outputs_from=None,
                settings=(
                    _number("initial"),
                    _number("reorder_point"),
                    _number("order_quantity", minimum=1),
                    _distribution("lead_time"),
                ),
                metrics=("stock.mean", "stockouts", "orders"),
                description=(
                    "Each arriving item takes one unit of stock and leaves at once, or waits for a"
                    " delivery when stock is zero; an order of order_quantity is placed when stock"
                    " on hand plus on order falls to reorder_point."
                ),
            ),
            BlockType(
                "resource_pool",
                inputs=(),
                outputs=(),
                outputs_from=None,
                settings=(_number("capacity", minimum=1),),
                metrics=("utilization",),
                description=("Shared staff or tools; servers name it in their pool setting."),
            ),
            BlockType(
                "schedule",
                inputs=(),
                outputs=(),
                outputs_from=None,
                settings=(
                    _reference("target", ("server", "resource_pool")),
                    SettingSpec(
                        "shifts",
                        SettingKind.OBJECT,
                        True,
                        many=True,
                        fields=(_time("start"), _time("end"), _number("capacity")),
                    ),
                    _time(
                        "period",
                        required=False,
                        default=Quantity(86_400.0, Dimension.TIME),
                        above_zero=True,
                    ),
                ),
                metrics=(),
                description=("Changes the capacity of a server or pool over time."),
            ),
            BlockType(
                "failure",
                inputs=(),
                outputs=(),
                outputs_from=None,
                settings=(
                    _reference("target", ("server",)),
                    _distribution("time_to_failure"),
                    _distribution("time_to_repair"),
                ),
                metrics=(),
                description=(
                    "Takes a server out of service at random and returns it after repair."
                ),
            ),
            BlockType(
                "sink",
                inputs=("in",),
                outputs=(),
                outputs_from=None,
                settings=(),
                metrics=("throughput", "cycle_time.mean", "count"),
                description=("Removes the item and records its statistics."),
            ),
        )
    }
)

# Spec 2 "Statistic definitions": metrics of the whole model, named `model.<metric>`.
MODEL_METRICS: tuple[str, ...] = ("wip.mean",)


class MeasureKind(Enum):
    """What a metric is measured in (spec 2 "Statistic definitions"; spec 1 "Metric
    names": a constraint's `value` is a time quantity for a metric measured in time)."""

    TIME = "time"  # a time, in seconds
    RATE = "rate"  # items per unit of time, in SI units: per second
    NUMBER = "number"  # a fraction, a count or a number of items


# Spec 2 "Statistic definitions": every measure (a metric name after `<component id>.`)
# and what it is measured in. Throughput, orders and discards are "divided by the
# period", so they are rates; Phase 1 has no rate unit, so a constraint on one is a plain
# number of items per second (AKS-90, owner to confirm).
MEASURE_KINDS: Mapping[str, MeasureKind] = MappingProxyType(
    {
        "wait.mean": MeasureKind.TIME,
        "cycle_time.mean": MeasureKind.TIME,
        "throughput": MeasureKind.RATE,
        "orders": MeasureKind.RATE,
        "discarded": MeasureKind.RATE,
        "utilization": MeasureKind.NUMBER,
        "availability": MeasureKind.NUMBER,
        "scheduled_fraction": MeasureKind.NUMBER,
        "queue_length.mean": MeasureKind.NUMBER,
        "queue_length.max": MeasureKind.NUMBER,
        "stock.mean": MeasureKind.NUMBER,
        "stockouts": MeasureKind.NUMBER,
        "created": MeasureKind.NUMBER,
        "count": MeasureKind.NUMBER,
        "wip.mean": MeasureKind.NUMBER,
    }
)


class FieldKind(Enum):
    """What a field of a distribution takes (spec 1 "Distributions")."""

    QUANTITY = "quantity"  # a quantity of the setting's dimension (a plain number if none)
    NUMBER = "number"  # a plain number, whatever the setting's dimension
    DATA = "data"  # a {"file": ..., "column": ...} reference into the project's data/


@dataclass(frozen=True)
class FieldSpec:
    """One field of a distribution; ``many`` for an array of values (at least one).

    ``positive``: the field must be above zero (spec 1 E160: "``sd``, ``shape``,
    ``scale`` or the ``mean`` of a positive distribution not greater than zero").
    """

    name: str
    kind: FieldKind
    many: bool = False
    positive: bool = False


@dataclass(frozen=True)
class DistributionSpec:
    """One distribution. ``forms`` lists the field sets it may be written with: every
    distribution has one, except ``empirical``, which takes ``values`` or ``data``."""

    name: str
    forms: tuple[tuple[FieldSpec, ...], ...]
    # Fields whose values must not decrease in this order (E160: `min` above `max`, or
    # a triangular `mode` outside `min` to `max`).
    ordered: tuple[str, ...] = ()

    def field_names(self) -> tuple[str, ...]:
        """Every field name of every form, in spec order."""
        return tuple(field.name for form in self.forms for field in form)


def _quantities(*names: str, positive: tuple[str, ...] = ()) -> tuple[FieldSpec, ...]:
    return tuple(FieldSpec(name, FieldKind.QUANTITY, positive=name in positive) for name in names)


DISTRIBUTIONS: Mapping[str, DistributionSpec] = MappingProxyType(
    {
        spec.name: spec
        for spec in (
            DistributionSpec("constant", (_quantities("value"),)),
            # The positive distributions: exponential, lognormal and weibull.
            DistributionSpec("exponential", (_quantities("mean", positive=("mean",)),)),
            DistributionSpec("uniform", (_quantities("min", "max"),), ordered=("min", "max")),
            DistributionSpec(
                "triangular",
                (_quantities("min", "mode", "max"),),
                ordered=("min", "mode", "max"),
            ),
            DistributionSpec("normal", (_quantities("mean", "sd", positive=("sd",)),)),
            DistributionSpec("lognormal", (_quantities("mean", "sd", positive=("mean", "sd")),)),
            DistributionSpec(
                "weibull",
                (
                    (
                        FieldSpec("shape", FieldKind.NUMBER, positive=True),
                        FieldSpec("scale", FieldKind.QUANTITY, positive=True),
                    ),
                ),
            ),
            DistributionSpec(
                "empirical",
                (
                    (FieldSpec("values", FieldKind.QUANTITY, many=True),),
                    (FieldSpec("data", FieldKind.DATA),),
                ),
            ),
        )
    }
)

# Spec 1 "Distributions", `empirical` with `data`: the keys of the data reference.
DATA_FIELDS: tuple[str, ...] = ("file", "column")
