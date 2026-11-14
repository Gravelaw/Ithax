"""The meaning pass (spec 1 "Validation", pass 2). Part A (AKS-89): identifiers, engines,
settings that name components, and connections. Part B (AKS-90): parameters, the values of
settings and distributions, data references, experiments and metric names.

Spec 1 "Validation": the checks across the model follow on a model that loads. Each
function here takes a ``Model`` that ``ithax.model.loading`` built without an error, so
every component, connection, experiment, scenario, objective, constraint and variable sits
at the same index as in the file, and every path below points into the file.

Rule groups, one function each, each returning ``list[Issue]``:

- ``engine_issues``: E102, the installed-adapter lookup of spec 1 "Top-level keys". The
  loader calls it before building, since a model of a domain no engine handles cannot be
  built. The installed engines are passed in: ``ithax.engines.registry`` discovers them,
  and the model layer does not import the engines package at module level.
- ``identifier_issues``: E110 (duplicate), E111 (pattern), E112 (reserved), spec 1
  "Identifiers".
- ``setting_issues``: E124 (a ``pool`` or ``target`` that names an unknown component or
  one of the wrong type), E125 (more than one ``schedule`` or ``failure`` on one target),
  and the keys of a branch's ``weights`` against its ``routes`` (E121, E122).
- ``connection_issues``: E130 (unknown component or port), E131 (output port not
  connected), E132 (output port connected more than once) and E161 (a branch route that
  is not in ``routes``), spec 1 "Components and ports".

Part B, the value half (spec 1: "units of the right dimension, parameters within allowed
ranges"):

- ``parameter_issues``: E151, a parameter's ``value`` or a scenario's value for it outside
  its ``min`` and ``max``, or a ``min`` above the ``max``.
- ``reference_issues``: E150 (a ``{"$param": id}`` that names no parameter) and E152 (a
  parameter whose ``type`` does not fit the setting or field that refers to it).
- ``range_issues``: E123 for a number or time below the smallest value its setting takes
  (the catalogue's ``minimum``), a branch with no routes, weights that are all zero, and a
  shift that does not end after it starts or ends after its ``period``.
- ``distribution_issues``: E160 for distribution fields that are inconsistent (spec 1
  "Distributions" and its E160 row).
- ``data_issues``: E162 for an ``empirical`` ``data`` reference against the project's
  ``DataIndex`` (``ithax.model.data``).
- ``experiment_issues``: E170 (an experiment or its search with a value out of range),
  E171 (a search that names an unknown objective, a parameter without ``min`` and ``max``,
  no parameter at all or one parameter twice, or that sits in an experiment listing
  scenarios) and E150 (a search variable that is not a parameter).
- ``metric_issues``: E174 (an objective or constraint that names a metric spec 2 does not
  define) and E123 (a constraint ``value`` of the wrong kind for its metric).
- ``program_issues``: E175 (an ``optimization`` coefficient that names no variable;
  AKS-108).

A value that comes from a parameter is checked for every value the model gives that
parameter: its ``value``, its ``min`` and ``max`` (the range a search explores) and each
scenario's value. A check that fails names the case.

``meaning_pass`` runs every group except ``engine_issues``. E120 to E123, E140, E141, E150
for a scenario, E160 for a distribution that cannot be read, and a connection end that is
not ``<id>.<port>`` (E130) are reported by the loader, because a value of the wrong kind
cannot be built.
"""

from __future__ import annotations

import itertools
import math
import re
from collections import deque
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from ithax.model.catalogue import (
    DISTRIBUTIONS,
    MEASURE_KINDS,
    MODEL_METRICS,
    PROCESS_TYPES,
    FieldKind,
    FieldSpec,
    MeasureKind,
    SettingKind,
    SettingSpec,
)
from ithax.model.data import EMPTY_DATA_INDEX, DataColumn, DataIndex, fits_in_seconds
from ithax.model.issues import Issue, pointer
from ithax.model.model import (
    Component,
    Distribution,
    Endpoint,
    Experiment,
    IndexedProgram,
    Model,
    ParameterValue,
    ParamRef,
    Scalar,
    SettingValue,
)
from ithax.model.units import Dimension, Quantity

__all__ = [
    "IDENTIFIER_PATTERN",
    "RESERVED_COMPONENT_IDS",
    "RESERVED_SCENARIO_ID",
    "InstalledEngine",
    "clipping_issues",
    "connection_issues",
    "data_issues",
    "distribution_issues",
    "distribution_mean",
    "engine_issues",
    "experiment_issues",
    "failure_capacity_issues",
    "flow_rates",
    "identifier_issues",
    "load_issues",
    "meaning_pass",
    "metric_issues",
    "parameter_issues",
    "program_issues",
    "range_issues",
    "reference_issues",
    "setting_issues",
    "unreachable_issues",
]

Segment = str | int

# Spec 1 "Identifiers". Matched with ``fullmatch``: ``$`` would also match before a final
# newline.
IDENTIFIER_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,63}")

# Spec 1 "Identifiers": reserved ids and why.
RESERVED_COMPONENT_IDS: dict[str, str] = {
    "model": "'model' is the prefix of metrics of the whole model, such as 'model.wip.mean'",
    "optimizer": "'optimizer' is the random-stream key of the simulation-based search",
}
RESERVED_SCENARIO_ID = "default"
_DEFAULT_REASON = "'default' is the id of the scenario an experiment has when it lists no scenarios"

# Spec 2 "Block reference", "Targets": a server (or pool) takes at most one of each.
_ONE_PER_TARGET: dict[str, str] = {
    "schedule": "a server or resource pool may have only one schedule",
    "failure": "a server may have only one failure",
}


# --- E102: which engine runs the model ------------------------------------------------------


@dataclass(frozen=True)
class InstalledEngine:
    """An installed engine adapter as engine selection sees it: its name (spec 1
    ``run.engine``) and the domains its ``capabilities()`` include.

    Every Phase 1 domain has an adapter from M5 (``simpy`` for ``process``, ``highs`` for
    ``optimization``), so the model layer's stand-in, which had no name, is gone
    (AKS-108).
    """

    name: str
    domains: tuple[str, ...]


def engine_issues(
    domain: str,
    engine: str | None,
    installed: Sequence[InstalledEngine],
) -> list[Issue]:
    """E102 unless exactly one installed engine runs a model of ``domain``.

    Spec 1 "Top-level keys": the one installed adapter whose capabilities include the
    model's ``domain``; if there are several and ``run.engine`` is absent, or none, the
    issue is E102. With ``run.engine``, the adapter of that name is chosen, and E102 is
    raised when no adapter of that name handles the domain. ``engine`` is ``run.engine``,
    or ``None`` when the file has none.
    """
    handling = [item for item in installed if domain in item.domains]
    if not handling:
        offered = sorted({name for item in installed for name in item.domains})
        return [
            _issue(
                "E102",
                ("domain",),
                f"The model's 'domain' is {_quote(domain)}, and no installed engine handles it.",
                f"Set 'domain' to {_words(offered)}."
                if offered
                else "Install an engine for this domain.",
            )
        ]
    names = [item.name for item in handling]
    if engine is not None:
        chosen = [item for item in handling if item.name == engine]
        if len(chosen) == 1:
            return []
        return [
            _issue(
                "E102",
                ("run", "engine"),
                f"The 'engine' in 'run' is {_quote(engine)}, but "
                + (
                    f"no installed engine of that name handles the domain {_quote(domain)}."
                    if not chosen
                    else f"several installed engines of that name handle the domain "
                    f"{_quote(domain)}."
                ),
                f"Name one of: {_words(names)}.",
            )
        ]
    if len(handling) == 1:
        return []
    return [
        _issue(
            "E102",
            ("run", "engine"),
            f"Several installed engines handle the domain {_quote(domain)} "
            f"({_words(names)}), and 'run' names no 'engine' to choose one.",
            f"Add 'engine' to 'run', naming one of: {_words(names)}.",
        )
    ]


# --- E110, E111, E112: identifiers ------------------------------------------------------------


@dataclass(frozen=True)
class _Entry:
    """One identifier in a list where ids must be unique."""

    identifier: str
    at: tuple[Segment, ...]
    component: str | None
    # How the message names the place, as in "The 'id' of component 2".
    label: str
    # How a later duplicate names this entry, as in "component 2".
    short: str


def identifier_issues(model: Model) -> list[Issue]:
    """E111 for an id that does not match ``IDENTIFIER_PATTERN``, E112 for a reserved id,
    and E110 for each later use of an id within one list.

    The lists (spec 1 "Identifiers"): components, parameters, experiments, the scenarios
    of one experiment, objectives, constraints, variables and the routes of one branch.
    Parameter ids are object keys, so a repeat is already E100 when the file is read.
    """
    issues: list[Issue] = []
    components = [
        _Entry(
            item.id,
            ("components", index, "id"),
            item.id,
            f"The 'id' of component {index + 1}",
            f"component {index + 1}",
        )
        for index, item in enumerate(model.components)
    ]
    issues += _identifier_list(components, "each component needs its own id")
    issues += _reserved(components, RESERVED_COMPONENT_IDS)
    for index, component in enumerate(model.components):
        issues += _route_issues(index, component)
    parameters = [
        _Entry(name, ("parameters", name), None, "The id of a parameter", f"parameter {name}")
        for name in model.parameters
    ]
    issues += _identifier_list(parameters, "each parameter needs its own id")
    issues += _identifier_list(
        _numbered(
            [item.id for item in model.experiments], ("experiments",), "experiment", "experiment"
        ),
        "each experiment needs its own id",
    )
    for index, experiment in enumerate(model.experiments):
        if experiment.default_scenario_added:
            continue
        where = f"of experiment {_quote(experiment.id)}"
        scenarios = [
            _Entry(
                item.id,
                ("experiments", index, "scenarios", number, "id"),
                None,
                f"The 'id' of scenario {number + 1} {where}",
                f"scenario {number + 1}",
            )
            for number, item in enumerate(experiment.scenarios)
        ]
        issues += _identifier_list(scenarios, f"each scenario {where} needs its own id")
        issues += _reserved(scenarios, {RESERVED_SCENARIO_ID: _DEFAULT_REASON})
    issues += _identifier_list(
        _numbered(
            [item.id for item in model.objectives], ("objectives",), "objective", "objective"
        ),
        "each objective needs its own id",
    )
    declared = model.declared
    constraints = (
        [item.id for item in declared.constraints]
        if declared is not None
        else [item.id for item in model.constraints]
    )
    issues += _identifier_list(
        _numbered(constraints, ("constraints",), "constraint", "constraint"),
        "each constraint needs its own id",
    )
    if declared is not None:
        # Declared ids, not the expanded names (`ship[north,city]`), which are no
        # identifiers (spec 2 "Indexed problems").
        issues += _identifier_list(
            _numbered(
                [item.id for item in declared.variables],
                ("variables",),
                "variable",
                "variable",
            ),
            "each variable needs its own id",
        )
        issues += _index_identifier_issues(declared)
    return issues


def _index_identifier_issues(declared: IndexedProgram) -> list[Issue]:
    """E111 for a set or table id or a set member that is not an identifier, and E110 for a
    member repeated in one set (spec 1 "Identifiers"; AKS-123). Set and table ids are
    object keys, so a repeat is already E100."""
    issues = _identifier_list(
        [
            _Entry(name, ("sets", name), None, "The id of a set", f"set {name}")
            for name in declared.sets
        ],
        "each set needs its own id",
    )
    issues += _identifier_list(
        [
            _Entry(name, ("tables", name), None, "The id of a table", f"table {name}")
            for name in declared.tables
        ],
        "each table needs its own id",
    )
    for name, members in declared.sets.items():
        issues += _identifier_list(
            [
                _Entry(
                    member,
                    ("sets", name, position),
                    None,
                    f"Member {position + 1} of the set {_quote(name)}",
                    f"member {position + 1}",
                )
                for position, member in enumerate(members)
            ],
            f"each member of the set {_quote(name)} must differ",
            hint="Remove the repeated member, or rename it.",
        )
    return issues


def _numbered(
    identifiers: Sequence[str], at: tuple[Segment, ...], noun: str, short: str
) -> list[_Entry]:
    return [
        _Entry(
            identifier,
            (*at, index, "id"),
            None,
            f"The 'id' of {noun} {index + 1}",
            f"{short} {index + 1}",
        )
        for index, identifier in enumerate(identifiers)
    ]


def _route_issues(index: int, component: Component) -> list[Issue]:
    """E111 and E110 for the routes of a branch: each route names an output port."""
    block = PROCESS_TYPES[component.type]
    if block.outputs_from is None:
        return []
    routes = component.settings[block.outputs_from]  # required, so present when built
    assert isinstance(routes, tuple)
    entries = [
        _Entry(
            route,
            ("components", index, "params", block.outputs_from, number),
            component.id,
            f"Route {number + 1} in the '{block.outputs_from}' of {_quote(component.id)}",
            f"route {number + 1}",
        )
        for number, route in enumerate(routes)
        if isinstance(route, str)
    ]
    return _identifier_list(
        entries,
        f"each route of {_quote(component.id)} names its own output port",
        hint="Remove the repeated route, or rename it.",
    )


def _identifier_list(
    entries: Sequence[_Entry], rule: str, *, hint: str = "Rename one of them."
) -> list[Issue]:
    issues: list[Issue] = []
    first: dict[str, _Entry] = {}
    for entry in entries:
        if IDENTIFIER_PATTERN.fullmatch(entry.identifier) is None:
            issues.append(
                _issue(
                    "E111",
                    entry.at,
                    f"{entry.label} is {_quote(entry.identifier)}, which is not a valid "
                    "identifier: an identifier starts with a lower-case letter from a to z "
                    "and holds only lower-case letters, digits and underscores, 64 "
                    "characters at most.",
                    "Use lower-case letters, digits and '_', starting with a letter, as in "
                    "'till_2'.",
                    entry.component,
                )
            )
        earlier = first.setdefault(entry.identifier, entry)
        if earlier is not entry:
            issues.append(
                _issue(
                    "E110",
                    entry.at,
                    f"{entry.label} is {_quote(entry.identifier)}, which {earlier.short} "
                    f"already uses; {rule}.",
                    hint,
                    entry.component,
                )
            )
    return issues


def _reserved(entries: Sequence[_Entry], reserved: dict[str, str]) -> list[Issue]:
    return [
        _issue(
            "E112",
            entry.at,
            f"{entry.label} is {_quote(entry.identifier)}, which is reserved: "
            f"{reserved[entry.identifier]}.",
            "Choose another id.",
            entry.component,
        )
        for entry in entries
        if entry.identifier in reserved
    ]


# --- E124, E125 and a branch's weights: settings that name things -----------------------------


def setting_issues(model: Model) -> list[Issue]:
    """Settings that name other components or other settings' entries.

    - E124: a setting that names a component (``pool`` of a server, ``target`` of a
      schedule or failure) names an unknown id, or a component of a type the setting does
      not take (spec 2 "Block reference").
    - E125: a server or pool is the ``target`` of more than one ``schedule``, or a server
      of more than one ``failure`` (spec 2 "Targets"); reported at each later one.
    - E121 for a ``weights`` key that is not one of the branch's ``routes``, and E122 for
      a route without a weight (spec 2: ``weights`` is an object keyed by route).
    """
    issues: list[Issue] = []
    by_id = _first_by_id(model.components)
    # (type of the naming block, target id) -> the first component naming it.
    targeted: dict[tuple[str, str], Component] = {}
    for index, component in enumerate(model.components):
        block = PROCESS_TYPES[component.type]
        for spec in block.settings:
            name = component.settings.get(spec.name)
            if spec.refers_to and isinstance(name, str):
                at = ("components", index, "params", spec.name)
                target = by_id.get(name)
                kinds = _words([f"a {kind}" for kind in spec.refers_to], quote=False)
                if target is None:
                    issues.append(
                        _issue(
                            "E124",
                            at,
                            f"The '{spec.name}' setting of {_quote(component.id)} names "
                            f"{_quote(name)}, but no component has that id.",
                            f"Name {kinds} that is in the model, or add one called {_quote(name)}.",
                            component.id,
                        )
                    )
                    continue
                if target.type not in spec.refers_to:
                    issues.append(
                        _issue(
                            "E124",
                            at,
                            f"The '{spec.name}' setting of {_quote(component.id)} names "
                            f"{_quote(name)}, which is a {target.type}; it must name {kinds}.",
                            f"Name {kinds} instead of {_quote(name)}.",
                            component.id,
                        )
                    )
                    continue
                if component.type in _ONE_PER_TARGET and spec.name == "target":
                    earlier = targeted.setdefault((component.type, name), component)
                    if earlier is not component:
                        issues.append(
                            _issue(
                                "E125",
                                at,
                                f"The 'target' of {_quote(component.id)} is {_quote(name)}, "
                                f"which the {component.type} {_quote(earlier.id)} already "
                                f"targets; {_ONE_PER_TARGET[component.type]}.",
                                f"Combine them into {_quote(earlier.id)}, or remove "
                                f"{_quote(component.id)}.",
                                component.id,
                            )
                        )
            if spec.keyed_by is not None:
                issues += _keyed_issues(index, component, spec.name, spec.keyed_by)
    return issues


def _keyed_issues(index: int, component: Component, setting: str, keyed_by: str) -> list[Issue]:
    """E121 for a key of ``setting`` that is not an entry of ``keyed_by``; E122 for an
    entry with no key. Nothing when ``setting`` is absent (the loader reports it missing
    where it is required)."""
    values = component.settings.get(setting)
    entries = component.settings.get(keyed_by)
    if not isinstance(values, Mapping) or not isinstance(entries, tuple):
        return []
    keys = list(values)
    names = [entry for entry in dict.fromkeys(entries) if isinstance(entry, str)]
    at = ("components", index, "params", setting)
    issues = [
        _issue(
            "E121",
            (*at, key),
            f"The '{setting}' of {_quote(component.id)} has a key {_quote(key)}, which is "
            f"not one of its '{keyed_by}' ({_words(names)})."
            if names
            else f"The '{setting}' of {_quote(component.id)} has a key {_quote(key)}, but "
            f"its '{keyed_by}' is empty.",
            f"Remove {_quote(key)} from '{setting}', or add it to '{keyed_by}'.",
            component.id,
        )
        for key in keys
        if key not in names
    ]
    issues += [
        _issue(
            "E122",
            (*at, name),
            f"The '{setting}' of {_quote(component.id)} has no entry for {_quote(name)}, "
            f"which is one of its '{keyed_by}'.",
            f"Add {_quote(name)} to '{setting}'.",
            component.id,
        )
        for name in names
        if name not in keys
    ]
    return issues


# --- E130, E131, E132, E161: connections --------------------------------------------------------


def connection_issues(model: Model) -> list[Issue]:
    """Spec 1 "Components and ports": every output port connects to exactly one input port;
    an input port accepts any number of connections.

    - E130: a connection end names an unknown component, a ``from`` end names a port that
      is not an output port of its component, or a ``to`` end one that is not an input
      port.
    - E161: the ``from`` end names a branch and a port that is not in its ``routes``
      (instead of E130).
    - E132: an output port named by the ``from`` end of an earlier connection; reported
      at each later connection.
    - E131: an output port that no connection names, at the component (spec 1's example
      path ``/components/1``), or at the route's entry in ``routes`` for a branch.

    A connection whose ``from`` end is valid connects that output port, whatever its
    ``to`` end says, so a wrong ``to`` end gives one issue (a wrong ``from`` end also leaves
    the port it meant unconnected, E131).
    """
    issues: list[Issue] = []
    by_id = _first_by_id(model.components)
    connected: dict[tuple[str, str], int] = {}
    for index, connection in enumerate(model.connections):
        origin = connection.origin
        if _end_issue(issues, index, "from", origin, by_id):
            key = (origin.component, origin.port)
            first = connected.setdefault(key, index)
            if first != index:
                issues.append(
                    _issue(
                        "E132",
                        ("connections", index, "from"),
                        f"The 'from' end of connection {index + 1} is "
                        f"{_quote(_text(origin))}, which connection {first + 1} already "
                        "connects; an output port connects to exactly one input port.",
                        "Remove one of the two connections; to send items several ways, "
                        "put a branch after the port.",
                    )
                )
        _end_issue(issues, index, "to", connection.destination, by_id)
    for index, component in enumerate(model.components):
        if by_id[component.id] is not component:
            continue  # a repeated id (E110): its ports are the first component's
        block = PROCESS_TYPES[component.type]
        for port in dict.fromkeys(component.output_ports):
            if (component.id, port) in connected:
                continue
            if block.outputs_from is None:
                issues.append(
                    _issue(
                        "E131",
                        ("components", index),
                        f"The {_quote(port)} port of {_quote(component.id)} is not connected "
                        "to anything.",
                        "Connect it to another block or to a sink.",
                        component.id,
                    )
                )
            else:
                number = component.output_ports.index(port)
                issues.append(
                    _issue(
                        "E131",
                        ("components", index, "params", block.outputs_from, number),
                        f"The route {_quote(port)} of {_quote(component.id)} is not "
                        f"connected to anything; each entry of '{block.outputs_from}' is an "
                        "output port.",
                        f"Connect {_quote(_text(Endpoint(component.id, port)))} to another "
                        f"block, or remove {_quote(port)} from '{block.outputs_from}'.",
                        component.id,
                    )
                )
    return issues


def _end_issue(
    issues: list[Issue],
    index: int,
    key: str,
    end: Endpoint,
    by_id: dict[str, Component],
) -> bool:
    """Append the issue of one connection end, if any; true when the end is valid."""
    at = ("connections", index, key)
    opening = f"The '{key}' end of connection {index + 1} is {_quote(_text(end))}"
    component = by_id.get(end.component)
    if component is None:
        issues.append(
            _issue(
                "E130",
                at,
                f"{opening}, but no component has the id {_quote(end.component)}.",
                _known_ids_hint(list(by_id)),
            )
        )
        return False
    block = PROCESS_TYPES[component.type]
    if key == "from":
        ports, direction = component.output_ports, "output"
    else:
        ports, direction = component.input_ports, "input"
    if end.port in ports:
        return True
    if key == "from" and block.outputs_from is not None:
        issues.append(
            _issue(
                "E161",
                at,
                f"{opening}, but {_quote(end.port)} is not one of the "
                f"'{block.outputs_from}' of {_quote(component.id)}.",
                f"Use one of its routes ({_words(list(ports))}), or add {_quote(end.port)} "
                f"to its '{block.outputs_from}'."
                if ports
                else f"Add {_quote(end.port)} to the '{block.outputs_from}' of "
                f"{_quote(component.id)}.",
            )
        )
        return False
    issues.append(
        _issue(
            "E130",
            at,
            f"{opening}, but {_quote(component.id)} (a {component.type}) has no {direction} "
            f"port {_quote(end.port)}.",
            f"Use {_words(list(ports))}, the {direction} port{'s' if len(ports) > 1 else ''} "
            f"of a {component.type}."
            if ports
            else f"A {component.type} has no {direction} port; connect another block.",
        )
    )
    return False


# --- part B: values the model gives its parameters ---------------------------------------------

# What a setting or distribution field takes: a whole number, a plain number or a time.
Expects = Literal["integer", "number", "quantity"]

# The parameter types that fit each, and how a message names it (spec 1 "Parameters": an
# `integer` is a whole number, a `number` a plain number, a `quantity` a time).
_FITS: dict[Expects, tuple[str, ...]] = {
    "integer": ("integer",),
    "number": ("integer", "number"),
    "quantity": ("quantity",),
}
_TAKES: dict[Expects, str] = {
    "integer": "a whole number",
    "number": "a plain number",
    "quantity": "a time",
}


@dataclass(frozen=True)
class _Case:
    """Values of parameters that a check is made with: ``values`` replaces the ``value``
    of the parameters it names; ``text`` says so in a message ("" for none)."""

    values: Mapping[str, ParameterValue]
    text: str


# Joint cases are made for at most this many parameters at once (2**12 = 4,096 cases);
# above it, only all at their lowest and all at their highest bound.
_JOINT_LIMIT = 12


def _cases(model: Model, names: Sequence[str]) -> list[_Case]:
    """Every case in which the parameters ``names`` take a value the model gives them:
    each at its ``value``; then each scenario that sets any of them; then each at its
    ``min`` and at its ``max``; then, for two or more parameters, every combination of
    their bounds, since a search varies them together (spec 2 "Simulation-based
    optimization"). Without parameters, the one case of the written values.

    The checks that use these cases are linear inequalities in the values (a minimum,
    an order, an end within a period) or "not all zero" over values that are each at
    least zero; each fails somewhere in a box of values only if it fails at a corner, so
    the corners stand for the whole search range. A parameter named twice is one value.
    """
    if not names:
        return [_Case({}, "")]
    shown = _words(names, last="and")
    cases = [
        _Case(
            {},
            f" with the parameter {shown} at its 'value'"
            if len(names) == 1
            else f" with the parameters {shown} at their 'value'",
        )
    ]
    for experiment in model.experiments:
        if experiment.default_scenario_added:
            continue
        for scenario in experiment.scenarios:
            changed = {name: scenario.set[name] for name in names if name in scenario.set}
            if changed:
                cases.append(
                    _Case(
                        changed,
                        f" in scenario {_quote(scenario.id)} of experiment {_quote(experiment.id)}",
                    )
                )
    for name in names:
        parameter = model.parameters[name]
        for bound, value in (("min", parameter.min), ("max", parameter.max)):
            if value is not None:
                cases.append(
                    _Case({name: value}, f" with the parameter {_quote(name)} at its '{bound}'")
                )
    if len(names) > 1:
        cases += _corners(model, names)
    return cases


def _corners(model: Model, names: Sequence[str]) -> list[_Case]:
    """The cases with every parameter of ``names`` at one of its bounds together; a
    parameter without a bound stays at its ``value``."""
    options: list[list[tuple[str, ParameterValue]]] = []
    for name in names:
        parameter = model.parameters[name]
        bounds = [
            (bound, value)
            for bound, value in (("min", parameter.min), ("max", parameter.max))
            if value is not None
        ]
        options.append(bounds or [("value", parameter.value)])
    if len(names) <= _JOINT_LIMIT:
        combinations = list(itertools.product(*options))
    else:
        combinations = [
            tuple(choice[0] for choice in options),
            tuple(choice[-1] for choice in options),
        ]
    return [
        _Case(
            {name: value for name, (_, value) in zip(names, chosen, strict=True)},
            " with "
            + _words(
                [
                    f"{_quote(name)} at its '{bound}'"
                    for name, (bound, _) in zip(names, chosen, strict=True)
                ],
                quote=False,
                last="and",
            ),
        )
        for chosen in combinations
    ]


def _magnitude(value: int | float | Quantity) -> int | float:
    return value.magnitude if isinstance(value, Quantity) else value


def _resolve(model: Model, scalar: Scalar, case: _Case) -> int | float:
    if isinstance(scalar, ParamRef):
        value = case.values.get(scalar.parameter, model.parameters[scalar.parameter].value)
        return _magnitude(value)
    return _magnitude(scalar)


def _first_failure(
    model: Model,
    scalars: Sequence[Scalar],
    holds: Callable[[list[int | float]], bool],
) -> tuple[list[int | float], str] | None:
    """The values of ``scalars`` and the case's text for the first case in which
    ``holds`` is false, or ``None`` when it holds in every case."""
    names = list(
        dict.fromkeys(scalar.parameter for scalar in scalars if isinstance(scalar, ParamRef))
    )
    for case in _cases(model, names):
        numbers = [_resolve(model, scalar, case) for scalar in scalars]
        if not holds(numbers):
            return numbers, case.text
    return None


# --- E151: parameter values within min and max -------------------------------------------------


def parameter_issues(model: Model) -> list[Issue]:
    """E151: a parameter's ``value``, or a scenario's value for it, below its ``min`` or
    above its ``max`` (spec 1 "Parameters"); a ``min`` above the ``max`` is E151 at the
    ``min``, and that parameter's values are then not compared with them."""
    issues: list[Issue] = []
    usable: set[str] = set()
    for name, parameter in model.parameters.items():
        low, high = parameter.min, parameter.max
        if low is not None and high is not None and _magnitude(low) > _magnitude(high):
            issues.append(
                _issue(
                    "E151",
                    ("parameters", name, "min"),
                    f"The 'min' of parameter {_quote(name)} is {_value_text(low)}, which is "
                    f"above its 'max', {_value_text(high)}.",
                    "Make 'min' no larger than 'max'.",
                )
            )
            continue
        usable.add(name)
        problem = _outside(parameter.value, low, high)
        if problem:
            issues.append(
                _issue(
                    "E151",
                    ("parameters", name, "value"),
                    f"The 'value' of parameter {_quote(name)} is "
                    f"{_value_text(parameter.value)}, {problem}.",
                    f"Set the 'value' of {_quote(name)} within its range, or change the range.",
                )
            )
    for index, experiment in enumerate(model.experiments):
        if experiment.default_scenario_added:
            continue
        for number, scenario in enumerate(experiment.scenarios):
            for name, value in scenario.set.items():
                parameter = model.parameters[name]
                problem = _outside(value, parameter.min, parameter.max) if name in usable else ""
                if problem:
                    issues.append(
                        _issue(
                            "E151",
                            ("experiments", index, "scenarios", number, "set", name),
                            f"Scenario {_quote(scenario.id)} of experiment "
                            f"{_quote(experiment.id)} sets {_quote(name)} to "
                            f"{_value_text(value)}, {problem}.",
                            f"Set {_quote(name)} within its range in this scenario, or change "
                            "the parameter's range.",
                        )
                    )
    return issues


def _outside(value: ParameterValue, low: ParameterValue | None, high: ParameterValue | None) -> str:
    """How ``value`` lies outside ``low`` to ``high``, or "" when it does not."""
    if low is not None and _magnitude(value) < _magnitude(low):
        return f"below its 'min', {_value_text(low)}"
    if high is not None and _magnitude(value) > _magnitude(high):
        return f"above its 'max', {_value_text(high)}"
    return ""


# --- the numbers and times of component settings -----------------------------------------------


@dataclass(frozen=True)
class _Slot:
    """One number or time a component's setting or distribution field holds."""

    at: tuple[Segment, ...]
    where: str  # as in "the 'capacity' setting of 'till'"
    component: str
    value: Scalar
    expects: Expects
    spec: SettingSpec | None  # the setting, for its minimum; None for a distribution field


@dataclass(frozen=True)
class _Use:
    """One distribution a component's setting holds."""

    at: tuple[Segment, ...]
    where: str
    component: str
    distribution: Distribution
    dimension: Dimension


def _setting_values(
    index: int, component: Component
) -> tuple[
    list[_Slot], list[_Use], list[tuple[SettingSpec, SettingValue, tuple[Segment, ...], str]]
]:
    """The slots and distributions of a component, and every setting value with its spec,
    path and description (for the checks on arrays and objects)."""
    slots: list[_Slot] = []
    uses: list[_Use] = []
    values: list[tuple[SettingSpec, SettingValue, tuple[Segment, ...], str]] = []

    def walk(
        spec: SettingSpec, value: SettingValue, at: tuple[Segment, ...], where: str, one: bool
    ) -> None:
        values.append((spec, value, at, where))
        if spec.many and not one:
            assert isinstance(value, tuple)
            for number, item in enumerate(value):
                walk(spec, item, (*at, number), f"item {number + 1} of {where}", True)
            return
        if spec.kind is SettingKind.NUMBER or spec.kind is SettingKind.QUANTITY:
            assert isinstance(value, int | float | Quantity | ParamRef)
            expects: Expects = (
                "quantity"
                if spec.kind is SettingKind.QUANTITY
                else "integer"
                if spec.integer
                else "number"
            )
            slots.append(_Slot(at, where, component.id, value, expects, spec))
        elif spec.kind is SettingKind.DISTRIBUTION:
            assert isinstance(value, Distribution) and spec.dimension is not None
            uses.append(_Use(at, where, component.id, value, spec.dimension))
            slots.extend(_field_slots(at, where, component.id, value, spec.dimension))
        elif spec.kind is SettingKind.OBJECT:
            assert isinstance(value, Mapping)
            if spec.values is not None:
                for key, item in value.items():
                    walk(
                        spec.values,
                        item,
                        (*at, key),
                        f"the {spec.values.name} of {_quote(key)} in {where}",
                        False,
                    )
            else:
                for field in spec.fields:
                    if field.name in value:
                        walk(
                            field,
                            value[field.name],
                            (*at, field.name),
                            f"the '{field.name}' of {where}",
                            False,
                        )

    block = PROCESS_TYPES[component.type]
    for spec in block.settings:
        if spec.name in component.settings:
            walk(
                spec,
                component.settings[spec.name],
                ("components", index, "params", spec.name),
                f"the '{spec.name}' setting of {_quote(component.id)}",
                False,
            )
    return slots, uses, values


def _field_slots(
    at: tuple[Segment, ...],
    where: str,
    component: str,
    distribution: Distribution,
    dimension: Dimension,
) -> Iterator[_Slot]:
    spec = DISTRIBUTIONS[distribution.dist]
    kinds = {field.name: field.kind for form in spec.forms for field in form}
    for name, value in distribution.fields.items():
        plain = kinds[name] is FieldKind.NUMBER or dimension is Dimension.DIMENSIONLESS
        yield _Slot(
            (*at, name),
            f"the '{name}' field of {where}",
            component,
            value,
            "number" if plain else "quantity",
            None,
        )
    for number, value in enumerate(distribution.values or ()):
        yield _Slot(
            (*at, "values", number),
            f"value {number + 1} of the 'values' field of {where}",
            component,
            value,
            "number" if dimension is Dimension.DIMENSIONLESS else "quantity",
            None,
        )


def _fits(model: Model, value: Scalar, expects: Expects) -> bool:
    """False for a reference to an unknown parameter or one of a type that does not fit."""
    if not isinstance(value, ParamRef):
        return True
    parameter = model.parameters.get(value.parameter)
    return parameter is not None and parameter.type in _FITS[expects]


# --- E150, E152: parameter references in components -------------------------------------------


def reference_issues(model: Model) -> list[Issue]:
    """E150 for a ``{"$param": id}`` in a component that names no parameter; E152 for one
    whose parameter's ``type`` does not fit what the setting or field takes (spec 1
    "Parameters": an ``integer`` is a whole number, a ``number`` a plain number, a
    ``quantity`` a time). A whole number fits where a plain number is taken."""
    issues: list[Issue] = []
    for index, component in enumerate(model.components):
        slots, _, _ = _setting_values(index, component)
        for slot in slots:
            if not isinstance(slot.value, ParamRef):
                continue
            name = slot.value.parameter
            parameter = model.parameters.get(name)
            if parameter is None:
                issues.append(
                    _issue(
                        "E150",
                        slot.at,
                        f"{_sentence(slot.where)} refers to the parameter {_quote(name)}, "
                        "which is not in 'parameters'.",
                        f"Add a parameter {_quote(name)} to 'parameters', or correct the name.",
                        slot.component,
                    )
                )
            elif parameter.type not in _FITS[slot.expects]:
                types = _words(_FITS[slot.expects])
                issues.append(
                    _issue(
                        "E152",
                        slot.at,
                        f"{_sentence(slot.where)} refers to the parameter {_quote(name)}, "
                        f"whose 'type' is {_quote(parameter.type)}; this place takes "
                        f"{_TAKES[slot.expects]}, so the parameter's 'type' must be {types}.",
                        f"Change the 'type' of {_quote(name)} to {types}, or refer to another "
                        "parameter.",
                        slot.component,
                    )
                )
    return issues


# --- E123: the smallest values settings take --------------------------------------------------


def range_issues(model: Model) -> list[Issue]:
    """E123 for a setting value outside the range its place takes (spec 1 E123: a value
    that is not of the kind its place takes; the readings are in the catalogue):

    - a number or time below the setting's ``minimum`` (or not above it, for an exclusive
      minimum), such as a ``capacity`` of 0;
    - an array with fewer entries than ``min_items`` (a branch with no ``routes``);
    - an object keyed by another setting whose values are all zero (``weights``: a route
      is chosen with probability weight/sum, spec 2 "Branch rules");
    - a shift that does not end after it starts, or ends after the schedule's ``period``
      (spec 2 "Schedule": start and end lie within ``period``).

    A value from a parameter is checked for every value the model gives the parameter;
    a reference with E150 or E152 is skipped.
    """
    issues: list[Issue] = []
    for index, component in enumerate(model.components):
        slots, _, values = _setting_values(index, component)
        for slot in slots:
            spec = slot.spec
            if spec is None or spec.minimum is None or not _fits(model, slot.value, slot.expects):
                continue
            minimum, exclusive = spec.minimum, spec.exclusive_minimum
            failure = _first_failure(model, [slot.value], _at_least(minimum, exclusive))
            if failure is not None:
                shown = _shown(failure[0][0], slot.expects)
                bound = _shown(minimum, slot.expects)
                rule = f"above {bound}" if exclusive else f"at least {bound}"
                issues.append(
                    _issue(
                        "E123",
                        slot.at,
                        f"{_sentence(slot.where)} is {shown}{failure[1]}; it must be {rule}.",
                        f"Use a value {rule}.",
                        slot.component,
                    )
                )
        for spec, value, at, where in values:
            if spec.many and isinstance(value, tuple) and len(value) < spec.min_items:
                issues.append(
                    _issue(
                        "E123",
                        at,
                        f"{_sentence(where)} is empty; it needs at least {spec.min_items} "
                        f"entr{'y' if spec.min_items == 1 else 'ies'}.",
                        f"Add an entry to '{spec.name}'.",
                        component.id,
                    )
                )
            if spec.keyed_by is not None and isinstance(value, Mapping) and value:
                issues += _all_zero(model, component.id, spec, value, at, where)
        if component.type == "schedule":
            issues += _shift_issues(model, index, component)
    return issues


def _at_least(minimum: int | float, exclusive: bool) -> Callable[[list[int | float]], bool]:
    """A test that one number is at least ``minimum``, or above it when ``exclusive``."""
    if exclusive:
        return lambda numbers: numbers[0] > minimum
    return lambda numbers: numbers[0] >= minimum


def _all_zero(
    model: Model,
    component: str,
    spec: SettingSpec,
    value: Mapping[str, SettingValue],
    at: tuple[Segment, ...],
    where: str,
) -> list[Issue]:
    weights = list(value.values())
    if not all(
        isinstance(item, int | float | ParamRef) and _fits(model, item, "number")
        for item in weights
    ):
        return []
    scalars = [item for item in weights if isinstance(item, int | float | ParamRef)]
    # A negative weight has its own issue; this one is about weights that add up to zero.
    failure = _first_failure(
        # `any`, not `sum`: a weight may be an integer too large to convert to a float.
        model,
        scalars,
        lambda numbers: any(n < 0 for n in numbers) or any(n > 0 for n in numbers),
    )
    if failure is None:
        return []
    return [
        _issue(
            "E123",
            at,
            f"Every value in {where} is 0{failure[1]}; at least one must be above 0, since "
            f"each of the '{spec.keyed_by}' is chosen in proportion to its "
            f"{spec.values.name if spec.values else 'value'}.",
            "Give at least one route a weight above 0.",
            component,
        )
    ]


def _shift_issues(model: Model, index: int, component: Component) -> list[Issue]:
    period_spec = PROCESS_TYPES["schedule"].setting("period")
    assert period_spec is not None and isinstance(period_spec.default, Quantity)
    assert period_spec.minimum is not None
    period = component.settings.get("period", period_spec.default)
    shifts = component.settings["shifts"]
    assert isinstance(period, Quantity | ParamRef) and isinstance(shifts, tuple)
    issues: list[Issue] = []
    period_bad = _fits(model, period, "quantity") and (
        _first_failure(
            model, [period], _at_least(period_spec.minimum, period_spec.exclusive_minimum)
        )
        is not None
    )
    for number, shift in enumerate(shifts):
        assert isinstance(shift, Mapping)
        start, end = shift["start"], shift["end"]
        assert isinstance(start, Quantity | ParamRef) and isinstance(end, Quantity | ParamRef)
        if not all(_fits(model, item, "quantity") for item in (start, end, period)):
            continue
        at = ("components", index, "params", "shifts", number, "end")
        where = f"item {number + 1} of the 'shifts' setting of {_quote(component.id)}"
        failure = _first_failure(model, [start, end], lambda times: times[0] < times[1])
        if failure is not None:
            (begin, finish), case = failure
            issues.append(
                _issue(
                    "E123",
                    at,
                    f"In {where}, the 'end' ({_time_text(finish)}) is not after the 'start' "
                    f"({_time_text(begin)}){case}.",
                    "Make each shift end after it starts; split a shift that runs past the "
                    "end of the period into two.",
                    component.id,
                )
            )
            continue
        if period_bad:
            continue  # a `period` not above 0 s has its own issue
        failure = _first_failure(model, [end, period], lambda times: times[0] <= times[1])
        if failure is not None:
            (finish, length), case = failure
            issues.append(
                _issue(
                    "E123",
                    at,
                    f"In {where}, the 'end' ({_time_text(finish)}) is after the end of the "
                    f"schedule's 'period' ({_time_text(length)}){case}; a shift lies within "
                    "the period.",
                    "End the shift within the period, or lengthen 'period'.",
                    component.id,
                )
            )
    return issues


# --- E160: distribution fields ------------------------------------------------------------------


def distribution_issues(model: Model) -> list[Issue]:
    """E160 for distribution fields that are inconsistent (spec 1 "Distributions" and
    its E160 row): a field that must be above zero and is not (``sd``, ``shape``,
    ``scale``, the ``mean`` of an exponential or lognormal), fields out of order (a
    ``min`` above the ``max``, a triangular ``mode`` outside ``min`` to ``max``), and an
    empty ``values``. A distribution with a reference that has E150 or E152 is skipped."""
    issues: list[Issue] = []
    for index, component in enumerate(model.components):
        slots, uses, _ = _setting_values(index, component)
        for use in uses:
            mine = [slot for slot in slots if slot.at[: len(use.at)] == use.at]
            if not all(_fits(model, slot.value, slot.expects) for slot in mine):
                continue
            issues += _distribution_issues(model, use)
    return issues


def _bound_issue(
    model: Model, use: _Use, field: FieldSpec, value: Scalar, plain: set[str], named: str
) -> list[Issue]:
    """E160 for a field that must be above zero (``positive``) or not below it
    (``nonnegative``, #69) and is not, in the first case that fails."""
    if field.positive:
        failure = _first_failure(model, [value], lambda numbers: numbers[0] > 0)
        problem, hint = "it must be greater than zero.", f"Use a '{field.name}' above zero."
    else:
        failure = _first_failure(model, [value], lambda numbers: numbers[0] >= 0)
        problem = "a time cannot be below zero, and every sample below zero would be set to 0 s."
        hint = f"Use a '{field.name}' of 0 s or more."
    if failure is None:
        return []
    shown = _shown(failure[0][0], "number" if field.name in plain else "quantity")
    return [
        _issue(
            "E160",
            (*use.at, field.name),
            f"The '{field.name}' of {named} is {shown}{failure[1]}; {problem}",
            hint,
            use.component,
        )
    ]


def _distribution_issues(model: Model, use: _Use) -> list[Issue]:
    distribution = use.distribution
    spec = DISTRIBUTIONS[distribution.dist]
    fields = distribution.fields
    plain = {
        field.name
        for form in spec.forms
        for field in form
        if field.kind is FieldKind.NUMBER or use.dimension is Dimension.DIMENSIONLESS
    }
    named = f"the '{spec.name}' distribution in {use.where}"
    issues: list[Issue] = []
    for form in spec.forms:
        for field in form:
            if field.name in fields and (field.positive or field.nonnegative):
                issues.extend(_bound_issue(model, use, field, fields[field.name], plain, named))
    ordered = [name for name in spec.ordered if name in fields]
    failure = _first_failure(
        model,
        [fields[name] for name in ordered],
        lambda numbers: all(a <= b for a, b in itertools.pairwise(numbers)),
    )
    if failure is not None:
        numbers, case = failure
        text = {
            name: _shown(number, "number" if name in plain else "quantity")
            for name, number in zip(ordered, numbers, strict=True)
        }
        # The first pair out of order: (min, max), (min, mode) or (mode, max).
        low, high = next(
            pair
            for pair, (first, second) in zip(
                itertools.pairwise(ordered), itertools.pairwise(numbers), strict=True
            )
            if first > second
        )
        if high == "mode":
            key, problem = "mode", f"the 'mode' ({text['mode']}) is below the 'min' ({text['min']})"
        elif low == "mode":
            key, problem = "mode", f"the 'mode' ({text['mode']}) is above the 'max' ({text['max']})"
        else:
            key, problem = low, f"the '{low}' ({text[low]}) is above the '{high}' ({text[high]})"
        issues.append(
            _issue(
                "E160",
                (*use.at, key),
                f"In {named}, {problem}{case}.",
                "Order the fields so that " + " ≤ ".join(f"'{name}'" for name in ordered) + ".",
                use.component,
            )
        )
    if distribution.values is not None and not distribution.values:
        issues.append(
            _issue(
                "E160",
                (*use.at, "values"),
                f"The 'values' of {named} is empty; an empirical distribution samples from at "
                "least one value.",
                "List at least one value, or use 'data' to name a column of an imported file.",
                use.component,
            )
        )
    return issues


# --- E162: data references ----------------------------------------------------------------------


def data_issues(model: Model, data: DataIndex = EMPTY_DATA_INDEX) -> list[Issue]:
    """E162 for an ``empirical`` distribution's ``data`` reference (spec 1
    "Distributions") that names a file not in the project's ``data/`` folder (not in
    ``data``, the column index), a file that is now missing from the folder or whose
    SHA-256 differs from the one recorded at import, or a column the file does not have.
    ``data`` defaults to an empty index: nothing imported."""
    issues: list[Issue] = []
    current: dict[str, str | None] = {}
    for index, component in enumerate(model.components):
        _, uses, _ = _setting_values(index, component)
        for use in uses:
            reference = use.distribution.data
            if reference is None:
                continue
            at = (*use.at, "data")
            entry = data.file(reference.file)
            if entry is None:
                files = sorted(data.files)
                issues.append(
                    _issue(
                        "E162",
                        (*at, "file"),
                        f"In {use.where}, the 'file' of the data reference is "
                        f"{_quote(reference.file)}, which is not in the project's data/ "
                        "folder.",
                        f"Name one of the imported files{_listed(files)}."
                        if files
                        else "Import the file into the project first, or list the values "
                        "with 'values'.",
                        use.component,
                    )
                )
                continue
            if reference.file not in current:
                current[reference.file] = data.current_sha256(reference.file)
            digest = current[reference.file]
            if digest != entry.sha256:
                problem = (
                    "is listed in the project's data index but is missing from its data/ folder"
                    if digest is None
                    else "has changed since it was imported (its SHA-256 differs from the "
                    "one recorded then)"
                )
                issues.append(
                    _issue(
                        "E162",
                        (*at, "file"),
                        f"In {use.where}, the 'file' of the data reference is "
                        f"{_quote(reference.file)}, which {problem}.",
                        "Import the file again, so that its columns are read afresh.",
                        use.component,
                    )
                )
            column = entry.column(reference.column)
            if column is not None:
                issues.extend(_column_issues(use, at, reference.column, column))
            else:
                columns = [column.name for column in entry.columns]
                issues.append(
                    _issue(
                        "E162",
                        (*at, "column"),
                        f"In {use.where}, the 'column' of the data reference is "
                        f"{_quote(reference.column)}, which is not a column of "
                        f"{_quote(reference.file)}.",
                        f"Name one of its columns{_listed(columns)}."
                        if columns
                        else f"{_quote(reference.file)} has no columns; import a file with "
                        "the values.",
                        use.component,
                    )
                )
    return issues


def _column_issues(
    use: _Use, at: tuple[Segment, ...], name: str, column: DataColumn
) -> list[Issue]:
    """E162 for a column that does not hold numbers, that declares no unit for the time the
    setting takes, or whose largest value is not a finite number of seconds in its unit
    (spec 1 "Distributions"; AKS-113, Codex on PR #37)."""
    problem, hint = None, ""
    if column.type != "number":
        problem = "holds text" if column.type == "text" else "holds no values"
        problem += ", but an empirical distribution samples numbers"
        hint = "Name a column of numbers, or import the file again with its numbers."
    elif column.unit is None:
        # Every distribution setting in Phase 1 is a time (spec 1 "Distributions").
        problem = "holds plain numbers, but the setting takes a time"
        hint = (
            "Import the file again, declaring the column's time unit (s, min, h or d), or "
            "name a column that has one."
        )
    elif column.largest is not None and not fits_in_seconds(column.largest, column.unit):
        # The check an inline quantity goes through, on the column's largest value
        # (spec 1 "Quantities"; Codex on PR #37).
        problem = (
            f"holds a value too large to be a time in seconds (the largest is "
            f"{column.largest!r} {column.unit})"
        )
        hint = "Declare a smaller unit when importing the file, or remove the value."
    if problem is None:
        return []
    return [
        _issue(
            "E162",
            (*at, "column"),
            f"In {use.where}, the 'column' of the data reference is {_quote(name)}, which "
            f"{problem}.",
            hint,
            use.component,
        )
    ]


# --- E170, E171: experiments ----------------------------------------------------------------------


def experiment_issues(model: Model) -> list[Issue]:
    """Spec 1 "Experiments".

    - E170: ``length`` not above 0 s, ``warmup`` below 0 s or not less than ``length``,
      ``replications`` below 2, ``confidence`` outside (0, 1), ``record_interval`` not
      above 0 s, a search ``budget`` below 1 or search ``replications`` below 2.
    - E171: ``search.objective`` that is not the id of an objective in ``objectives``; a
      search variable that is a parameter without both ``min`` and ``max``; a search with
      no variables (none listed, or no parameter with both ``min`` and ``max``); a search
      variable named a second time (at the repeat); a search in an experiment that lists
      scenarios, at ``scenarios`` (AKS-109, owner to confirm).
    - E150: a search variable that is not a parameter (a reference to an unknown
      parameter).
    """
    issues: list[Issue] = []
    objectives = [objective.id for objective in model.objectives]
    for index, experiment in enumerate(model.experiments):
        issues += _experiment_values(index, experiment)
        search = experiment.search
        if search is None:
            continue
        name = _quote(experiment.id)
        search_at = ("experiments", index, "search")
        if search.objective not in objectives:
            issues.append(
                _issue(
                    "E171",
                    (*search_at, "objective"),
                    f"The 'objective' of the search of experiment {name} is "
                    f"{_quote(search.objective)}, which is not the id of an objective in "
                    "'objectives'.",
                    f"Name one of the objectives{_listed(objectives)}."
                    if objectives
                    else "Add an objective to 'objectives' and name its id here.",
                )
            )
        if not search.variables:
            issues.append(
                _issue(
                    "E171",
                    (*search_at, "variables"),
                    f"The search of experiment {name} has no parameters to vary: its "
                    "'variables' is empty, or, when it lists none, no parameter has both a "
                    "'min' and a 'max'.",
                    "Give a parameter a 'min' and a 'max', and list it in 'variables'.",
                )
            )
        if not experiment.default_scenario_added:
            issues.append(
                _issue(
                    "E171",
                    ("experiments", index, "scenarios"),
                    f"Experiment {name} has a search and also lists scenarios; a search runs "
                    "its own candidates from the parameters' values, not scenarios.",
                    "Move the scenarios to an experiment without a search, or remove 'scenarios'.",
                )
            )
        for number, variable in enumerate(search.variables):
            parameter = model.parameters.get(variable)
            opening = (
                f"Variable {number + 1} in the 'variables' of the search of experiment {name} "
                f"is {_quote(variable)}"
            )
            first = search.variables.index(variable)
            if first < number:
                issues.append(
                    _issue(
                        "E171",
                        (*search_at, "variables", number),
                        f"{opening}, which variable {first + 1} already names; the search "
                        "varies each parameter once.",
                        f"Remove the repeated {_quote(variable)} from 'variables'.",
                    )
                )
            elif parameter is None:
                issues.append(
                    _issue(
                        "E150",
                        (*search_at, "variables", number),
                        f"{opening}, which is not a parameter.",
                        f"Add a parameter {_quote(variable)} to 'parameters', or correct the name.",
                    )
                )
            elif parameter.min is None or parameter.max is None:
                issues.append(
                    _issue(
                        "E171",
                        (*search_at, "variables", number),
                        f"{opening}, a parameter without both a 'min' and a 'max'; the search "
                        "varies each variable between the two.",
                        f"Give {_quote(variable)} a 'min' and a 'max', or remove it from "
                        "'variables'.",
                    )
                )
    return issues


def _experiment_values(index: int, experiment: Experiment) -> list[Issue]:
    """E170 for the values of one experiment and of its search."""
    issues: list[Issue] = []
    at = ("experiments", index)
    name = _quote(experiment.id)

    def e170(key: str, text: str, hint: str, *, search: bool = False) -> None:
        path = (*at, "search", key) if search else (*at, key)
        owner = f"the search of experiment {name}" if search else f"experiment {name}"
        issues.append(_issue("E170", path, f"The '{key}' of {owner} {text}.", hint))

    length = experiment.length.magnitude
    warmup = experiment.warmup.magnitude
    if length <= 0:
        e170(
            "length",
            f"is {_time_text(length)}; it must be above 0 s",
            "Use a length above 0 s.",
        )
    elif warmup < 0:
        e170(
            "warmup",
            f"is {_time_text(warmup)}; it must be at least 0 s",
            "Use a warm-up of 0 s or more.",
        )
    elif warmup >= length:
        e170(
            "warmup",
            f"is {_time_text(warmup)}, which is not less than its 'length', "
            f"{_time_text(length)}; no time would be observed after the warm-up",
            "Shorten 'warmup', or lengthen 'length'.",
        )
    if length > 0 and experiment.record_interval.magnitude <= 0:
        e170(
            "record_interval",
            f"is {_time_text(experiment.record_interval.magnitude)}; it must be above 0 s",
            "Use a recording interval above 0 s, or leave it out (default: 'length' / 200).",
        )
    if experiment.replications < 2:
        e170(
            "replications",
            f"is {_number_text(experiment.replications)}; it must be at least 2, so that "
            "a confidence interval can be given",
            "Use at least 2 replications; the default is 30.",
        )
    if not 0 < experiment.confidence < 1:
        e170(
            "confidence",
            f"is {_number_text(experiment.confidence)}; it must lie between 0 and 1, both excluded",
            "Use a level such as 0.95, the default.",
        )
    search = experiment.search
    if search is None:
        return issues
    if search.budget < 1:
        e170(
            "budget",
            f"is {_number_text(search.budget)}; it must be at least 1 candidate",
            "Use a budget of at least 1; the default is 50.",
            search=True,
        )
    if search.replications < 2:
        e170(
            "replications",
            f"is {_number_text(search.replications)}; it must be at least 2",
            "Use at least 2 replications per candidate; the default is 10.",
            search=True,
        )
    return issues


# --- E174: metric names ---------------------------------------------------------------------------


def metric_issues(model: Model) -> list[Issue]:
    """Spec 1 "Metric names": ``<component id>.<measure>``, or ``model.<measure>`` for the
    whole model, where the measure is one spec 2 "Statistic definitions" defines for the
    component's type (``MEASURE_KINDS``).

    - E174: an objective's or constraint's ``metric`` that is not such a name: no dot, an
      unknown component, or a measure its type does not report.
    - E123: a constraint's ``value`` of the wrong kind: a time quantity is needed for a
      metric measured in time, and a plain number for any other (a rate such as
      throughput is a plain number of items per second; Phase 1 has no rate unit).
    """
    issues: list[Issue] = []
    by_id = _first_by_id(model.components)
    for index, objective in enumerate(model.objectives):
        problem = _metric_problem(objective.metric, by_id)
        if problem is not None:
            issues.append(
                _metric_issue(
                    ("objectives", index), "objective", objective.id, objective.metric, problem
                )
            )
    for index, constraint in enumerate(model.constraints):
        problem = _metric_problem(constraint.metric, by_id)
        if problem is not None:
            issues.append(
                _metric_issue(
                    ("constraints", index), "constraint", constraint.id, constraint.metric, problem
                )
            )
            continue
        kind = MEASURE_KINDS[constraint.metric.partition(".")[2]]
        is_time = isinstance(constraint.value, Quantity)
        if is_time == (kind is MeasureKind.TIME):
            continue
        measured = {
            MeasureKind.TIME: "is measured in time, so a time such as '5 min' is expected",
            MeasureKind.RATE: "is a rate, written as a plain number of items per second "
            "(Phase 1 has no rate unit)",
            MeasureKind.NUMBER: "is a plain number, so a plain number is expected",
        }[kind]
        given = (
            f"a time, {_time_text(constraint.value.magnitude)}"
            if isinstance(constraint.value, Quantity)
            else f"the plain number {_number_text(constraint.value)}"
        )
        issues.append(
            _issue(
                "E123",
                ("constraints", index, "value"),
                f"The 'value' of constraint {_quote(constraint.id)} is {given}, but "
                f"{_quote(constraint.metric)} {measured}.",
                "Write a time with its unit, as in '5 min'."
                if kind is MeasureKind.TIME
                else "Write a plain number with no unit.",
            )
        )
    return issues


def _metric_problem(metric: str, by_id: Mapping[str, Component]) -> str | None:
    """Why ``metric`` is not a metric name, or ``None`` when it is one."""
    prefix, dot, measure = metric.partition(".")
    if not dot or not prefix or not measure:
        return (
            "which is not a metric name: a metric is written as a component id, a dot and a "
            "measure, as in 'till.wait.mean'"
        )
    if prefix == "model":
        if measure in MODEL_METRICS:
            return None
        return f"but the whole model reports only {_words(['model.' + m for m in MODEL_METRICS])}"
    component = by_id.get(prefix)
    if component is None:
        return f"but no component has the id {_quote(prefix)}"
    metrics = PROCESS_TYPES[component.type].metrics
    if measure in metrics:
        return None
    if not metrics:
        return f"but {_quote(prefix)} is a {component.type}, which reports no metrics"
    return (
        f"but {_quote(prefix)} is a {component.type}, which reports only "
        f"{_words([f'{prefix}.{m}' for m in metrics])}"
    )


def _metric_issue(
    at: tuple[Segment, ...], noun: str, identifier: str, metric: str, problem: str
) -> Issue:
    return _issue(
        "E174",
        (*at, "metric"),
        f"The 'metric' of {noun} {_quote(identifier)} is {_quote(metric)}, {problem}.",
        "Name a metric that spec 2 'Statistic definitions' defines for that component's "
        "type, such as '<server>.wait.mean' or '<sink>.throughput'.",
    )


# --- the warnings: W200, W201, W202 (W203 below) ----------------------------------------------

# A flow into a block: the mean rate, per second, of the units arriving, by what each unit
# holds. ``()`` is one item; ``(5,)`` a batch of 5 items; ``(2, 3)`` a batch of 3 batches
# of 2 (the last size is the outermost). Rates are exact fractions, so that "at least its
# capacity" is decided exactly; every step is closed-form arithmetic (guide rule 7).
_Flow = dict[tuple[int, ...], Fraction]


@dataclass(frozen=True)
class _Graph:
    """The connection graph the warnings walk."""

    # (index in the file, component) for the first component of each id.
    nodes: tuple[tuple[int, Component], ...]
    by_id: Mapping[str, Component]
    # (component id, output port) -> the id of the component that port feeds. Only the
    # first connection from a port counts (a second is E132), and only one whose two ends
    # are valid (E130, E161 otherwise).
    feeds: Mapping[tuple[str, str], str]
    # The ``schedule`` and the ``failure`` blocks of each target id, in file order (#73).
    schedules: Mapping[str, tuple[Component, ...]]
    failures: Mapping[str, tuple[Component, ...]]


def _graph(model: Model) -> _Graph:
    by_id = _first_by_id(model.components)
    nodes = tuple(
        (index, component)
        for index, component in enumerate(model.components)
        if by_id[component.id] is component
    )
    feeds: dict[tuple[str, str], str] = {}
    seen: set[tuple[str, str]] = set()
    for connection in model.connections:
        origin, destination = connection.origin, connection.destination
        start = by_id.get(origin.component)
        if start is None or origin.port not in start.output_ports:
            continue
        key = (origin.component, origin.port)
        if key in seen:
            continue
        seen.add(key)
        end = by_id.get(destination.component)
        if end is not None and destination.port in end.input_ports:
            feeds[key] = destination.component
    changers: dict[str, dict[str, list[Component]]] = {"schedule": {}, "failure": {}}
    for _, component in nodes:
        target = component.settings.get("target")
        if component.type in changers and isinstance(target, str) and target in by_id:
            changers[component.type].setdefault(target, []).append(component)
    return _Graph(
        nodes,
        by_id,
        feeds,
        {name: tuple(found) for name, found in changers["schedule"].items()},
        {name: tuple(found) for name, found in changers["failure"].items()},
    )


def _successors(graph: _Graph) -> dict[str, list[tuple[str, str]]]:
    """For each component id, its (output port, component fed) pairs."""
    successors: dict[str, list[tuple[str, str]]] = {
        component.id: [] for _, component in graph.nodes
    }
    for (origin, port), destination in graph.feeds.items():
        successors[origin].append((port, destination))
    return successors


def _run_cases(model: Model) -> list[_Case]:
    """The cases a warning is checked in: the parameters at their ``value``, then each
    scenario that sets a parameter. Unlike the errors, not at ``min`` and ``max``: a
    search tries values the modeller may expect to be poor (DECISIONS, AKS-91)."""
    cases = [_Case({}, "")]
    for experiment in model.experiments:
        if experiment.default_scenario_added:
            continue
        cases += [
            _Case(
                scenario.set,
                f" in scenario {_quote(scenario.id)} of experiment {_quote(experiment.id)}",
            )
            for scenario in experiment.scenarios
            if scenario.set
        ]
    return cases


def _exact(model: Model, value: Scalar, expects: Expects, case: _Case) -> Fraction | None:
    """``value`` in the case, as an exact fraction; ``None`` for a reference with E150 or
    E152."""
    if not _fits(model, value, expects):
        return None
    return Fraction(_resolve(model, value, case))


def _field_expects(distribution: Distribution, name: str, dimension: Dimension) -> Expects:
    spec = DISTRIBUTIONS[distribution.dist]
    kind = next(field.kind for form in spec.forms for field in form if field.name == name)
    plain = kind is FieldKind.NUMBER or dimension is Dimension.DIMENSIONLESS
    return "number" if plain else "quantity"


def _fields(
    model: Model, distribution: Distribution, dimension: Dimension, case: _Case
) -> dict[str, Fraction] | None:
    """The named fields of ``distribution`` in the case; ``None`` if one cannot be read."""
    fields: dict[str, Fraction] = {}
    for name, value in distribution.fields.items():
        number = _exact(model, value, _field_expects(distribution, name, dimension), case)
        if number is None:
            return None
        fields[name] = number
    return fields


def _normal_below_zero(mean: float, sd: float) -> float:
    """P(X < 0) for X normal with ``mean`` and ``sd``: Φ(-mean/sd)."""
    return 0.5 * math.erfc(mean / sd / math.sqrt(2))


def _clipped_normal_mean(mean: float, sd: float) -> float:
    """E[max(X, 0)] for X normal with ``mean`` and ``sd``: mean·Φ(z) + sd·φ(z), z =
    mean/sd. The closed form of the mean of a normal clipped at zero (spec 1
    "Distributions": negative samples are set to zero)."""
    z = mean / sd
    density = math.exp(-z * z / 2) / math.sqrt(2 * math.pi)
    return mean * 0.5 * math.erfc(-z / math.sqrt(2)) + sd * density


def _mean(
    model: Model, distribution: Distribution, dimension: Dimension, case: _Case
) -> Fraction | None:
    fields = _fields(model, distribution, dimension, case)
    if fields is None:
        return None
    values: list[Fraction] = []
    for value in distribution.values or ():
        number = _exact(model, value, _field_expects(distribution, "values", dimension), case)
        if number is None:
            return None
        values.append(number)
    try:
        return _theoretical_mean(distribution, fields, values)
    except (OverflowError, ValueError):
        return None  # a mean beyond the range of a float (a weibull's gamma function)


def _theoretical_mean(
    distribution: Distribution, fields: Mapping[str, Fraction], values: Sequence[Fraction]
) -> Fraction | None:
    """The theoretical means of spec 1 "Distributions" (the sampling test); ``None`` for
    fields that are inconsistent (E160) and for a ``data`` column, which is not read."""
    name = distribution.dist
    mean: Fraction | float | None = None
    if name == "constant":
        mean = fields["value"]
    elif name == "exponential":
        mean = fields["mean"] if fields["mean"] > 0 else None
    elif name == "uniform":
        low, high = fields["min"], fields["max"]
        mean = (low + high) / 2 if low <= high else None
    elif name == "triangular":
        low, mode, high = fields["min"], fields["mode"], fields["max"]
        mean = (low + mode + high) / 3 if low <= mode <= high else None
    elif name == "normal":
        if fields["sd"] > 0:
            mean = _clipped_normal_mean(float(fields["mean"]), float(fields["sd"]))
    elif name == "lognormal":
        mean = fields["mean"] if fields["mean"] > 0 and fields["sd"] > 0 else None
    elif name == "weibull":
        shape, scale = fields["shape"], fields["scale"]
        if shape > 0 and scale > 0:
            mean = float(scale) * math.gamma(1 + 1 / float(shape))
    elif values:  # empirical with `values`; with `data` the column is not read here
        mean = sum(values, Fraction(0)) / len(values)
    if isinstance(mean, float):
        return Fraction(mean) if math.isfinite(mean) else None
    return mean


def distribution_mean(
    model: Model,
    distribution: Distribution,
    values: Mapping[str, ParameterValue] | None = None,
    *,
    dimension: Dimension = Dimension.TIME,
) -> Fraction | None:
    """The theoretical mean of ``distribution`` in SI units, as spec 1 "Distributions"
    gives it for the sampling test, with ``values`` replacing the ``value`` of the
    parameters it names. A ``normal`` is sampled clipped at zero, so its mean is that of
    the clipped variable, mean·Φ(mean/sd) + sd·φ(mean/sd), which is ``mean`` to within
    one part in 10⁷ when ``mean`` ≥ 5 ``sd``.

    ``None`` when the mean cannot be known: inconsistent fields (E160), a reference with
    E150 or E152, a mean beyond the range of a float, or an ``empirical`` ``data`` column
    (the model layer reads no values). Phase 1 distributions are times, so ``dimension``
    is a time unless stated.
    """
    return _mean(model, distribution, dimension, _Case(values or {}, ""))


# --- W200: reachable from a source ---------------------------------------------------------------


def unreachable_issues(model: Model) -> list[Issue]:
    """W200 for each component with an input port that no chain of connections reaches
    from a ``source`` (spec 1 "Validation issues"). A connection counts when both its ends
    are valid and it is the first from its output port."""
    graph = _graph(model)
    successors = _successors(graph)
    stack = [component.id for _, component in graph.nodes if component.type == "source"]
    reached: set[str] = set()
    while stack:
        for _, destination in successors[stack.pop()]:
            if destination not in reached:
                reached.add(destination)
                stack.append(destination)
    return [
        _issue(
            "W200",
            ("components", index),
            f"{_quote(component.id)} (a {component.type}) cannot be reached from any source: "
            "no chain of connections leads from a source to its 'in' port, so no item will "
            "arrive there.",
            "Connect it to a source, or to a block that a source reaches; or remove it.",
            component.id,
        )
        for index, component in graph.nodes
        if component.input_ports and component.id not in reached
    ]


# --- W201: mean arrival rate times mean service time against capacity --------------------------


def _admits_less(component: Component) -> bool:
    """A block that can refuse an item: a ``queue``, or a server with a ``queue_capacity``.
    A source feeding one is a loss point (spec 1 "Validation")."""
    return component.type == "queue" or (
        component.type == "server" and "queue_capacity" in component.settings
    )


def _outputs(
    model: Model, graph: _Graph, component: Component, inflow: _Flow | None, case: _Case
) -> dict[str, _Flow | None]:
    """The flow out of each output port of ``component``, given the flow into it.

    Spec 1 "Validation": a probability branch multiplies by weight/total, a batch divides
    by ``size``, an unbatch multiplies by it; a shortest-queue branch, a store, a batch
    with a ``timeout``, and a loss point (a discarding ``queue``, a source feeding a block
    that can refuse an item) give a flow that cannot be propagated (``None``). A server
    passes its flow on, with a schedule or failure too (#73), as it does when overloaded.
    """
    ports = component.output_ports
    settings = component.settings
    if component.type == "source":
        fed = graph.feeds.get((component.id, "out"))
        interarrival = settings["interarrival"]
        assert isinstance(interarrival, Distribution)
        mean = _mean(model, interarrival, Dimension.TIME, case)
        if (fed is not None and _admits_less(graph.by_id[fed])) or mean is None or mean <= 0:
            return {"out": None}
        return {"out": {(): 1 / mean}}
    if inflow is None or not inflow:
        return {port: inflow for port in ports}  # nothing known, or nothing arrives
    stops = (
        component.type == "store"
        or (component.type == "queue" and settings.get("on_full") == "discard")
        or (component.type == "batch" and "timeout" in settings)
        or (component.type == "branch" and settings.get("rule") != "probability")
    )
    if stops:
        return {port: None for port in ports}
    if component.type == "batch":
        size = _exact(model, _scalar(settings["size"]), "integer", case)
        if size is None or size < 1:
            return {"out": None}
        whole = int(size)
        return {"out": {(*held, whole): rate / whole for held, rate in inflow.items()}}
    if component.type == "unbatch":
        flow: _Flow = {}
        for held, rate in inflow.items():
            inner, count = (held[:-1], held[-1]) if held else ((), 1)
            flow[inner] = flow.get(inner, Fraction(0)) + rate * count
        return {"out": flow}
    if component.type == "branch":
        return _branch_outputs(model, component, inflow, case)
    return {port: inflow for port in ports}  # server, delay, blocking queue


def _scalar(value: SettingValue) -> Scalar:
    assert isinstance(value, int | float | Quantity | ParamRef)
    return value


def _branch_outputs(
    model: Model, component: Component, inflow: _Flow, case: _Case
) -> dict[str, _Flow | None]:
    """A probability branch sends weight/total of the flow down each route."""
    routes = list(dict.fromkeys(component.output_ports))
    weights = component.settings.get("weights")
    shares: dict[str, Fraction] = {}
    for route in routes:
        weight = weights.get(route) if isinstance(weights, Mapping) else None
        number = None if weight is None else _exact(model, _scalar(weight), "number", case)
        if number is None or number < 0:
            return {route: None for route in routes}
        shares[route] = number
    total = sum(shares.values(), Fraction(0))
    if total <= 0:
        return {route: None for route in routes}
    return {
        route: {held: rate * share / total for held, rate in inflow.items()}
        for route, share in shares.items()
    }


def _inflows(model: Model, graph: _Graph, case: _Case) -> dict[str, _Flow | None]:
    """The flow into every component, propagated from the sources in topological order
    (Kahn's algorithm). Merges add. A block on a loop, or after one, is never reached by
    the order and gets ``None``: a rate on a loop would need the traffic equations
    solved, which is a linear system (guide rule 7)."""
    successors = _successors(graph)
    waiting = {component.id: 0 for _, component in graph.nodes}
    for destination in graph.feeds.values():
        waiting[destination] += 1
    inflow: dict[str, _Flow | None] = {component.id: {} for _, component in graph.nodes}
    ready = deque(component.id for _, component in graph.nodes if waiting[component.id] == 0)
    done: set[str] = set()
    while ready:
        name = ready.popleft()
        done.add(name)
        outputs = _outputs(model, graph, graph.by_id[name], inflow[name], case)
        for port, destination in successors[name]:
            out, current = outputs[port], inflow[destination]
            if out is None or current is None:
                inflow[destination] = None
            else:
                for held, rate in out.items():
                    current[held] = current.get(held, Fraction(0)) + rate
            waiting[destination] -= 1
            if waiting[destination] == 0:
                ready.append(destination)
    return {name: flow if name in done else None for name, flow in inflow.items()}


def _total(flow: _Flow | None) -> Fraction | None:
    return None if flow is None else sum(flow.values(), Fraction(0))


def flow_rates(
    model: Model, values: Mapping[str, ParameterValue] | None = None
) -> dict[str, Fraction | None]:
    """The mean arrival rate, in units per second, at each component with an input port,
    with ``values`` replacing the ``value`` of the parameters they name (spec 1
    "Validation", W201). A batch counts as one unit. ``None`` where the rate cannot be
    propagated: after a shortest-queue branch, a store, a batch with a ``timeout``, a loss
    point, on or after a loop, or after a value that cannot be read. A component no source
    reaches has rate 0."""
    graph = _graph(model)
    inflow = _inflows(model, graph, _Case(values or {}, ""))
    return {
        component.id: _total(inflow[component.id])
        for _, component in graph.nodes
        if component.input_ports
    }


def load_issues(model: Model) -> list[Issue]:
    """W201 for a server whose mean arrival rate times its mean service time is at least
    its mean available capacity while its queue is unlimited (no ``queue_capacity``), so
    the queue will grow without limit (spec 1 "Validation issues"); and for a pool whose
    servers together need at least its mean capacity while one of them has an unlimited
    queue (#73).

    The rate is propagated by ``flow_rates``. The mean available capacity is the
    ``capacity``, or under a schedule and failures its time average (``_mean_capacity``);
    a server or pool whose rate or capacity cannot be known is not checked. Each is
    checked with the parameters at their ``value`` and in each scenario; the first case
    that fails is named.
    """
    graph = _graph(model)
    found: dict[int, Issue] = {}
    for case in _run_cases(model):
        inflow = _inflows(model, graph, case)
        for index, component in graph.nodes:
            if index in found:
                continue
            issue = None
            if component.type == "server":
                issue = _load_issue(model, graph, index, component, inflow[component.id], case)
            elif component.type == "resource_pool":
                issue = _pool_load_issue(model, graph, index, component, inflow, case)
            if issue is not None:
                found[index] = issue
    return [found[index] for index in sorted(found)]


def _schedule_segments(
    model: Model, schedule: Component, nominal: Fraction, case: _Case
) -> list[tuple[Fraction, Fraction]] | None:
    """The scheduled capacity as (share of the time, capacity) pieces over the first
    ``period`` of the run, or over the longest experiment when that is shorter (a day
    shift in a run of one shift is never off): the sum of the shifts covering each
    instant, at most ``nominal`` (spec 2 "Schedule"). ``None`` when a value cannot be read
    or the shifts do not lie within a period above 0 s (E123 then)."""
    period_spec = PROCESS_TYPES["schedule"].setting("period")
    assert period_spec is not None and isinstance(period_spec.default, Quantity)
    period = _exact(
        model, _scalar(schedule.settings.get("period", period_spec.default)), "quantity", case
    )
    shifts = schedule.settings["shifts"]
    assert isinstance(shifts, tuple)
    spans: list[tuple[Fraction, Fraction, Fraction]] = []
    for shift in shifts:
        assert isinstance(shift, Mapping)
        start = _exact(model, _scalar(shift["start"]), "quantity", case)
        end = _exact(model, _scalar(shift["end"]), "quantity", case)
        units = _exact(model, _scalar(shift["capacity"]), "integer", case)
        if period is None or start is None or end is None or units is None:
            return None
        if not 0 <= start < end <= period or units < 0:
            return None
        spans.append((start, end, units))
    if period is None or period <= 0:
        return None
    lengths = [Fraction(experiment.length.magnitude) for experiment in model.experiments]
    horizon = min(period, max(lengths)) if lengths else period
    cuts = {e for s, f, _ in spans for e in (s, f) if e < horizon}
    edges = sorted({Fraction(0), horizon, *cuts})
    return [
        (
            (high - low) / horizon,
            min(nominal, sum((u for s, f, u in spans if s <= low < f), Fraction(0))),
        )
        for low, high in itertools.pairwise(edges)
    ]


def _down_shares(model: Model, failures: Sequence[Component], case: _Case) -> list[Fraction]:
    """For each failure block, the share of time its one unit is down: mean repair time
    over mean time to failure plus mean repair time, an alternating renewal process on
    calendar time (spec 2 "Failure"). Empty when a mean cannot be known."""
    shares: list[Fraction] = []
    for failure in failures:
        up, down = (failure.settings[name] for name in ("time_to_failure", "time_to_repair"))
        assert isinstance(up, Distribution) and isinstance(down, Distribution)
        up_mean = _mean(model, up, Dimension.TIME, case)
        down_mean = _mean(model, down, Dimension.TIME, case)
        if up_mean is None or down_mean is None or up_mean + down_mean <= 0:
            return []
        shares.append(down_mean / (up_mean + down_mean))
    return shares


def _mean_capacity(
    model: Model, graph: _Graph, component: Component, case: _Case
) -> tuple[Fraction, bool] | None:
    """The mean available capacity of a server or pool, and whether a schedule or failure
    reduced it from ``capacity`` (#73): the time average over the schedule's period of
    E[max(scheduled - failed units, 0)], the failures independent of the schedule and of
    each other, each taking one unit at a time (spec 2 "Schedule", "Failure"). ``None``
    when it cannot be known, or when two schedules target the same block."""
    nominal = _exact(model, _scalar(component.settings["capacity"]), "integer", case)
    schedules = graph.schedules.get(component.id, ())
    failures = graph.failures.get(component.id, ())
    if nominal is None or nominal < 1 or len(schedules) > 1:
        return None
    segments = [(Fraction(1), nominal)]
    if schedules:
        found = _schedule_segments(model, schedules[0], nominal, case)
        if found is None:
            return None
        segments = found
    shares = _down_shares(model, failures, case)
    if len(shares) != len(failures):
        return None
    failed = {0: Fraction(1)}  # the distribution of the number of failed units
    for share in shares:
        step: dict[int, Fraction] = {}
        for count, chance in failed.items():
            step[count] = step.get(count, Fraction(0)) + chance * (1 - share)
            step[count + 1] = step.get(count + 1, Fraction(0)) + chance * share
        failed = step
    mean = sum(
        (
            part * chance * max(units - count, Fraction(0))
            for part, units in segments
            for count, chance in failed.items()
        ),
        Fraction(0),
    )
    return mean, bool(schedules or failures)


def _capacity_text(graph: _Graph, component: Component, mean: Fraction) -> str:
    changers = [*graph.schedules.get(component.id, ()), *graph.failures.get(component.id, ())]
    if not changers:
        return f"its 'capacity' of {_figures(mean)}"
    names = ", ".join(f"{changer.type} {_quote(changer.id)}" for changer in changers)
    return f"its mean available capacity of {_figures(mean)} (under {names})"


def _load_issue(
    model: Model,
    graph: _Graph,
    index: int,
    component: Component,
    inflow: _Flow | None,
    case: _Case,
) -> Issue | None:
    settings = component.settings
    rate = _total(inflow)
    if "queue_capacity" in settings or rate is None or rate == 0:
        # No item arrives: no queue, even where a schedule leaves no unit (review of #159).
        return None
    capacity = _mean_capacity(model, graph, component, case)
    service = settings["service"]
    assert isinstance(service, Distribution)
    mean = _mean(model, service, Dimension.TIME, case)
    if capacity is None or mean is None or rate * mean < capacity[0]:
        return None
    name = _quote(component.id)
    return _issue(
        "W201",
        ("components", index),
        f"The mean arrival rate at {name} ({_figures(rate * 3600)} per hour) times its mean "
        f"service time ({_duration(mean)}) is {_figures(rate * mean)}, which is at least "
        f"{_capacity_text(graph, component, capacity[0])}, and its queue is "
        f"unlimited, so the queue will grow without limit{case.text}.",
        f"Raise the 'capacity' of {name}, shorten its service time, or send less work to it.",
        component.id,
    )


def _pool_load_issue(
    model: Model,
    graph: _Graph,
    index: int,
    pool: Component,
    inflow: Mapping[str, _Flow | None],
    case: _Case,
) -> Issue | None:
    """W201 for a pool whose servers' loads (mean arrival rate times mean service time)
    add up to at least its mean capacity while one of them has an unlimited queue: each
    item holds a pool unit for its service (spec 2 "Pool"; #73)."""
    servers = [
        component
        for _, component in graph.nodes
        if component.type == "server" and component.settings.get("pool") == pool.id
    ]
    if not servers or all("queue_capacity" in server.settings for server in servers):
        return None
    load = arrivals = Fraction(0)
    for server in servers:
        rate = _total(inflow[server.id])
        service = server.settings["service"]
        assert isinstance(service, Distribution)
        mean = _mean(model, service, Dimension.TIME, case)
        if rate is None or mean is None:
            return None
        load += rate * mean
        arrivals += rate
    capacity = _mean_capacity(model, graph, pool, case)
    if capacity is None or arrivals == 0 or load < capacity[0]:
        # No item reaches the pool's servers: no queue (review of #159).
        return None
    name = _quote(pool.id)
    users = ", ".join(_quote(server.id) for server in servers)
    return _issue(
        "W201",
        ("components", index),
        f"The servers that use the pool {name} ({users}) together need {_figures(load)} of "
        f"its units on average (each server's mean arrival rate times its mean service "
        f"time, added up), which is at least "
        f"{_capacity_text(graph, pool, capacity[0])}, so their queues will grow "
        f"without limit{case.text}.",
        f"Raise the 'capacity' of {name}, shorten the servers' service times, or send less "
        "work to them.",
        pool.id,
    )


# --- W202: a normal distribution clipped at zero ------------------------------------------------


#: W202's bound (#69, M2-1): a ``normal`` with more than this share of its samples below
#: zero, that is with ``mean`` below about 2.326 times ``sd``, is reported.
CLIPPED_SHARE = 0.01


def clipping_issues(model: Model) -> list[Issue]:
    """W202 for a ``normal`` distribution with more than ``CLIPPED_SHARE`` (1%) of its
    samples below zero, which are set to zero (spec 1 "Distributions"; #69). Checked with
    the parameters at their ``value`` and in each scenario; the first case that fails is
    named. A normal with an ``sd`` not above zero (E160) or a reference with E150 or E152
    is not checked."""
    issues: list[Issue] = []
    cases = _run_cases(model)
    for index, component in enumerate(model.components):
        _, uses, _ = _setting_values(index, component)
        for use in uses:
            if use.distribution.dist != "normal":
                continue
            for case in cases:
                fields = _fields(model, use.distribution, use.dimension, case)
                if fields is None:
                    break
                mean, sd = fields["mean"], fields["sd"]
                if sd <= 0 or _normal_below_zero(float(mean), float(sd)) <= CLIPPED_SHARE:
                    continue
                issues.append(_clipping_issue(use, float(mean), float(sd), case))
                break
    return issues


def _clipping_issue(use: _Use, mean: float, sd: float, case: _Case) -> Issue:
    below = 100 * _normal_below_zero(mean, sd)
    share = f"{below:.0f}" if below >= 10 else f"{below:.2g}"
    # Not a Fraction: with `mean` and `sd` near the largest float, the clipped mean is
    # infinite (review of PR #10).
    raised = _duration(_clipped_normal_mean(mean, sd), 3)
    return _issue(
        "W202",
        use.at,
        f"The 'normal' distribution in {use.where} has a 'mean' ({_duration(mean, 3)}) "
        f"and an 'sd' ({_duration(sd, 3)}){case.text} that put about {share}% of its "
        f"samples below zero; they are set to zero, which raises its mean to {raised}.",
        "Use a 'mean' of at least 2.33 times the 'sd', or a distribution that is never "
        "negative, such as 'lognormal' with the same mean and sd.",
        use.component,
    )


# --- W203: a failure on a server of capacity above 1 ---------------------------------------------


def failure_capacity_issues(model: Model) -> list[Issue]:
    """W203 (#84; D13, M4-34) for a ``failure`` whose target server has a ``capacity``
    above 1: one failure block takes one unit down at a time (spec 2 "Failure"), so the
    other units keep working while it is down. Checked with the parameters at their
    ``value`` and in each scenario; the first case that fails is named. A target that is
    not a server, or a capacity that cannot be read, is not checked (an error says so)."""
    servers = {
        component.id: component
        for component in reversed(model.components)
        if component.type == "server"
    }
    cases = _run_cases(model)
    issues: list[Issue] = []
    for index, component in enumerate(model.components):
        target = component.settings.get("target") if component.type == "failure" else None
        server = servers.get(target) if isinstance(target, str) else None
        if server is None:
            continue
        for case in cases:
            capacity = _exact(model, _scalar(server.settings["capacity"]), "integer", case)
            if capacity is None or capacity <= 1:
                continue
            issues.append(_failure_capacity_issue(index, component, server, capacity, case))
            break
    return issues


def _failure_capacity_issue(
    index: int, failure: Component, server: Component, capacity: Fraction, case: _Case
) -> Issue:
    name = _quote(server.id)
    return _issue(
        "W203",
        ("components", index, "params", "target"),
        f"The 'target' of failure {_quote(failure.id)} is {name}, whose 'capacity' is "
        f"{_figures(capacity)}{case.text}: a failure takes one unit down at a time, so the "
        "other units keep working while it is down.",
        f"To have each unit fail on its own, split {name} into servers of capacity 1, each "
        "with its own failure; one failure per unit is planned for Phase 2.",
        failure.id,
    )


# --- the pass --------------------------------------------------------------------------------


# --- E175: optimization coefficients ------------------------------------------------------------


def program_issues(model: Model) -> list[Issue]:
    """E175 for each coefficient of an ``optimization`` model's objective or constraints
    that names no variable in ``variables`` (AKS-108), at the coefficient's key, in file
    order: the objective's first, then each constraint's. A ``process`` model has none.
    """
    program = model.program
    declared = model.declared
    if program is None or declared is None:
        return []
    # A `linear` key names a variable of the flat program: an expanded name for an indexed
    # variable (spec 2 "Indexed problems"); paths point into the declared constraints.
    ids = [variable.id for variable in program.variables]
    known = set(ids)
    owners: list[tuple[tuple[Segment, ...], str, Mapping[str, int | float]]] = [
        (("objective",), "the objective", declared.objective.linear)
    ]
    owners += [
        (("constraints", index), f"constraint {_quote(constraint.id)}", constraint.linear)
        for index, constraint in enumerate(declared.constraints)
    ]
    issues: list[Issue] = []
    for at, owner, linear in owners:
        for name in linear:
            if name in known:
                continue
            if not ids:
                hint = f"Add a variable {_quote(name)} to 'variables'."
            elif len(ids) > _LISTED_IDS:
                hint = (
                    f"Correct the name to one of the variables, or add a variable {_quote(name)}."
                )
            else:
                hint = (
                    f"Correct the name to one of the variables, {_words(ids)}, or add a "
                    f"variable {_quote(name)}."
                )
            issues.append(
                _issue(
                    "E175",
                    (*at, "linear", name),
                    f"The coefficient of {_quote(name)} in {owner} names no variable in "
                    "'variables'.",
                    hint,
                )
            )
    return issues


def meaning_pass(model: Model, data: DataIndex = EMPTY_DATA_INDEX) -> list[Issue]:
    """The meaning pass: part A (identifiers, settings that name things, connections),
    then part B (parameters, references, ranges, distributions, data, experiments,
    metrics), then the warnings (W200, W201, W202, W203). ``data`` is the project's data index
    (default: nothing imported).

    E102 is not here: the loader checks it before building (``engine_issues``).
    """
    return [
        *identifier_issues(model),
        *setting_issues(model),
        *connection_issues(model),
        *parameter_issues(model),
        *reference_issues(model),
        *range_issues(model),
        *distribution_issues(model),
        *data_issues(model, data),
        *experiment_issues(model),
        *metric_issues(model),
        *program_issues(model),
        *unreachable_issues(model),
        *load_issues(model),
        *clipping_issues(model),
        *failure_capacity_issues(model),
    ]


# --- helpers ---------------------------------------------------------------------------------


def _first_by_id(components: Sequence[Component]) -> dict[str, Component]:
    """Components by id; with a repeated id (E110), the first of them."""
    by_id: dict[str, Component] = {}
    for component in components:
        by_id.setdefault(component.id, component)
    return by_id


# A hint lists the model's component ids only when there are this many or fewer.
_LISTED_IDS = 12


def _known_ids_hint(ids: Sequence[str]) -> str:
    if not ids:
        return "Add the component, or remove the connection."
    if len(ids) > _LISTED_IDS:
        return "Correct the id to one of the model's components."
    return f"Correct the id; the model's components are {_words(ids, last='and')}."


def _listed(names: Sequence[str]) -> str:
    """``: 'a' or 'b'`` for a short list; ``, such as 'a', ... or 'l'`` for a long one."""
    if len(names) > _LISTED_IDS:
        return f", such as {_words(names[:_LISTED_IDS])}"
    return f": {_words(names)}"


def _text(end: Endpoint) -> str:
    return f"{end.component}.{end.port}"


def _quote(text: str) -> str:
    return f"'{text}'"


def _sentence(text: str) -> str:
    """``text`` with its first letter in upper case, to open a sentence."""
    return text[:1].upper() + text[1:]


def _number_text(value: int | float) -> str:
    """A number as a message shows it: ``3``, ``0.95``; never a long one."""
    if isinstance(value, int):
        return "a very large whole number" if value.bit_length() > 64 else str(value)
    if value.is_integer() and abs(value) < 1e15:
        return str(int(value))
    return repr(value)


# Phase 1 time units, largest first, with their length in seconds.
_TIME_UNITS = (("d", 86_400), ("h", 3_600), ("min", 60))


def _time_text(seconds: int | float) -> str:
    """A time in seconds as a message shows it, in the largest unit that holds it
    exactly: ``8 h``, ``90 s``, ``-5 min``."""
    for unit, length in _TIME_UNITS:
        count = seconds / length
        if abs(seconds) >= length and float(count).is_integer():
            return f"{_number_text(count)} {unit}"
    return f"{_number_text(seconds)} s"


def _figures(value: Fraction, digits: int = 4) -> str:
    """An exact number as a message shows it, to ``digits`` significant figures."""
    try:
        return f"{float(value):.{digits}g}"
    except OverflowError:
        return "a very large number"


def _duration(seconds: Fraction | float, digits: int = 4) -> str:
    """A time in seconds, to ``digits`` significant figures, in the largest Phase 1 unit
    it reaches: ``2.5 min``, ``1.53 h``, ``45 s``; beyond the range of a float (the
    clipped mean of a normal whose fields are near it), ``a very long time``. A
    ``Fraction`` here is always a mean of finite floats, so its conversion cannot
    overflow."""
    value = float(seconds)
    if not math.isfinite(value):
        return "a very long time"
    for unit, length in _TIME_UNITS:
        if abs(value) >= length:
            return f"{value / length:.{digits}g} {unit}"
    return f"{value:.{digits}g} s"


def _shown(value: int | float, expects: Expects) -> str:
    return _time_text(value) if expects == "quantity" else _number_text(value)


def _value_text(value: ParameterValue) -> str:
    if isinstance(value, Quantity):
        return _time_text(value.magnitude)
    return _number_text(value)


def _words(words: Sequence[str], *, quote: bool = True, last: str = "or") -> str:
    """``'a', 'b' or 'c'``; callers never pass an empty list."""
    shown = [_quote(word) if quote else word for word in words]
    if len(shown) == 1:
        return shown[0]
    return ", ".join(shown[:-1]) + f" {last} " + shown[-1]


def _issue(
    code: str,
    at: Sequence[Segment],
    message: str,
    hint: str,
    component: str | None = None,
) -> Issue:
    return Issue(code, component, pointer(*at), message, hint)
