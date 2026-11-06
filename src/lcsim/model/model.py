"""The typed model: what ``lcsim.model.loading`` builds from a model file.

Every value is converted at load (guide "Conventions", Units): a quantity is a
``lcsim.model.units.Quantity`` holding an SI float, a plain number stays an ``int`` or
``float``, and a ``{"$param": "id"}`` reference is a ``ParamRef``, so that experiments and
optimizers can change the parameter and every use follows (spec 1 "What the prototype
changed", item 3). No unit string is held anywhere in these objects.

Every object is frozen and every mapping is read-only. Experiment defaults of spec 1
"Experiments" are filled in; settings a component leaves out stay absent, and the catalogue
(``lcsim.model.catalogue``) states the spec's default for each optional setting.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, TypeAlias

from lcsim.model.catalogue import PROCESS_TYPES, output_ports
from lcsim.model.units import Quantity

__all__ = [
    "Component",
    "Connection",
    "DataRef",
    "Distribution",
    "Endpoint",
    "Experiment",
    "JsonValue",
    "LinearConstraint",
    "LinearObjective",
    "LinearProgram",
    "Meta",
    "MetricConstraint",
    "MetricObjective",
    "Model",
    "ParamRef",
    "Parameter",
    "ParameterType",
    "ParameterValue",
    "RunSettings",
    "Scalar",
    "Scenario",
    "Search",
    "SettingValue",
    "Variable",
]

JsonValue: TypeAlias = bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"] | None


@dataclass(frozen=True)
class ParamRef:
    """A ``{"$param": "id"}`` reference to the parameter ``parameter``."""

    parameter: str


# A number or quantity a setting takes: written out, or a parameter reference.
Scalar: TypeAlias = int | float | Quantity | ParamRef


@dataclass(frozen=True)
class DataRef:
    """An ``empirical`` distribution's ``data`` reference: a column of a file in ``data/``."""

    file: str
    column: str


@dataclass(frozen=True)
class Distribution:
    """A distribution of spec 1 "Distributions", with its fields converted.

    ``fields`` holds the named fields (``mean``, ``min``, ``shape`` ...). An ``empirical``
    distribution has no named fields and holds either ``values`` or ``data``.
    """

    dist: str
    fields: Mapping[str, Scalar]
    values: tuple[Scalar, ...] | None = None
    data: DataRef | None = None


# A component setting: a scalar, a distribution, an identifier, an array of settings
# (`routes`, `shifts`) or an object of settings (`weights`, one shift).
SettingValue: TypeAlias = (
    Scalar | Distribution | str | tuple["SettingValue", ...] | Mapping[str, "SettingValue"]
)


@dataclass(frozen=True)
class Component:
    """A block: ``settings`` is its converted ``params`` object; ``ui`` is never read by an
    engine (spec 1 "Components and ports")."""

    id: str
    type: str
    settings: Mapping[str, SettingValue]
    label: str | None
    ui: Mapping[str, JsonValue] | None

    @property
    def input_ports(self) -> tuple[str, ...]:
        """The input ports of this component's type."""
        return PROCESS_TYPES[self.type].inputs

    @property
    def output_ports(self) -> tuple[str, ...]:
        """The output ports: fixed by the type, or one per route of a branch."""
        block = PROCESS_TYPES[self.type]
        routes = self.settings.get(block.outputs_from) if block.outputs_from else None
        names = (
            tuple(name for name in routes if isinstance(name, str))
            if isinstance(routes, tuple)
            else ()
        )
        return output_ports(block, names)


@dataclass(frozen=True)
class Endpoint:
    """One end of a connection, written ``"<component id>.<port>"``."""

    component: str
    port: str


@dataclass(frozen=True)
class Connection:
    """A directed link from an output port (``from``) to an input port (``to``)."""

    origin: Endpoint
    destination: Endpoint


ParameterType: TypeAlias = Literal["integer", "number", "quantity"]
# A parameter's value: an int for `integer`, a number for `number`, a Quantity for
# `quantity`.
ParameterValue: TypeAlias = int | float | Quantity


@dataclass(frozen=True)
class Parameter:
    """A named value that experiments and optimizers may change (spec 1 "Parameters")."""

    id: str
    type: ParameterType
    value: ParameterValue
    min: ParameterValue | None
    max: ParameterValue | None
    description: str | None


@dataclass(frozen=True)
class Scenario:
    """A named set of parameter values; ``set`` maps parameter id to value."""

    id: str
    set: Mapping[str, ParameterValue]


@dataclass(frozen=True)
class Search:
    """An experiment's simulation-based search (spec 1 "Experiments"), defaults filled."""

    objective: str
    budget: int
    variables: tuple[str, ...]
    replications: int


@dataclass(frozen=True)
class Experiment:
    """An experiment with every default of spec 1 "Experiments" filled in.

    ``seed_chosen`` is true when the file gave no ``seed`` and the loader chose one at
    random; the manifest records the seed either way. ``default_scenario_added`` is true
    when the file listed no scenarios and the loader added the one ``default`` scenario
    (spec 1 "Experiments"); a ``default`` scenario the file lists itself is E112.
    """

    id: str
    length: Quantity
    warmup: Quantity
    replications: int
    seed: int
    seed_chosen: bool
    scenarios: tuple[Scenario, ...]
    default_scenario_added: bool
    confidence: float
    record_interval: Quantity
    search: Search | None


Sense: TypeAlias = Literal["minimize", "maximize"]


@dataclass(frozen=True)
class MetricObjective:
    """A ``process`` objective: optimize the metric ``metric`` (spec 1 "Metric names")."""

    id: str
    metric: str
    sense: Sense


@dataclass(frozen=True)
class MetricConstraint:
    """A ``process`` constraint on a metric. ``value`` is a plain number, or a time
    quantity for a metric measured in time."""

    id: str
    metric: str
    op: Literal["<=", ">="]
    value: int | float | Quantity


@dataclass(frozen=True)
class Variable:
    """An ``optimization`` decision variable; a bound left out is ``None`` (no bound)."""

    id: str
    type: Literal["continuous", "integer", "binary"]
    lower: int | float | None
    upper: int | float | None


@dataclass(frozen=True)
class LinearObjective:
    """The ``optimization`` objective: ``linear`` maps variable id to coefficient."""

    sense: Sense
    linear: Mapping[str, int | float]


@dataclass(frozen=True)
class LinearConstraint:
    """An ``optimization`` constraint: the sum of ``linear`` ``op`` ``rhs``."""

    id: str
    linear: Mapping[str, int | float]
    op: Literal["<=", ">=", "=="]
    rhs: int | float


@dataclass(frozen=True)
class LinearProgram:
    """The ``optimization`` domain's content (spec 2 "Mathematical optimization")."""

    variables: tuple[Variable, ...]
    objective: LinearObjective
    constraints: tuple[LinearConstraint, ...]


@dataclass(frozen=True)
class RunSettings:
    """The ``run`` object, defaults ``local`` and ``standard`` filled.

    ``target`` and ``fidelity`` are kept as written: a target or fidelity this build does
    not offer is refused when a run starts (E172, E173), not when the file loads.
    """

    target: JsonValue
    fidelity: JsonValue
    engine: str | None


@dataclass(frozen=True)
class Meta:
    """The ``meta`` object."""

    name: str
    description: str | None
    author: str | None
    template: str | None


@dataclass(frozen=True)
class Model:
    """A loaded model file.

    A ``process`` model has ``components``, ``connections``, ``experiments`` and optional
    ``objectives`` and ``constraints``, and ``program`` is ``None``. An ``optimization``
    model has ``program`` and empty process fields.
    """

    format_version: str
    meta: Meta
    domain: str
    parameters: Mapping[str, Parameter]
    components: tuple[Component, ...]
    connections: tuple[Connection, ...]
    experiments: tuple[Experiment, ...]
    objectives: tuple[MetricObjective, ...]
    constraints: tuple[MetricConstraint, ...]
    program: LinearProgram | None
    run: RunSettings

    def component(self, component_id: str) -> Component | None:
        """The component with id ``component_id``, or ``None``."""
        return next((item for item in self.components if item.id == component_id), None)
