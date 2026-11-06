"""The meaning pass, part A: identifiers, engines, settings that name components, and
connections (spec 1 "Validation", pass 2; AKS-89).

Spec 1 "Validation": the checks across the model follow on a model that loads. Each
function here takes a ``Model`` that ``lcsim.model.loading`` built without an error, so
every component, connection, experiment, scenario, objective, constraint and variable sits
at the same index as in the file, and every path below points into the file.

Rule groups, one function each, each returning ``list[Issue]``:

- ``engine_issues``: E102, the installed-adapter lookup of spec 1 "Top-level keys". The
  loader calls it before building, since a model of a domain no engine handles cannot be
  built.
- ``identifier_issues``: E110 (duplicate), E111 (pattern), E112 (reserved), spec 1
  "Identifiers".
- ``setting_issues``: E124 (a ``pool`` or ``target`` that names an unknown component or
  one of the wrong type), E125 (more than one ``schedule`` or ``failure`` on one target),
  and the keys of a branch's ``weights`` against its ``routes`` (E121, E122).
- ``connection_issues``: E130 (unknown component or port), E131 (output port not
  connected), E132 (output port connected more than once) and E161 (a branch route that
  is not in ``routes``), spec 1 "Components and ports".

``meaning_pass`` runs the last three. E120 to E123 and a connection end that is not
``<id>.<port>`` (E130) are reported by the loader, because a value of the wrong kind cannot
be built.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from lcsim.model.catalogue import DOMAINS, PROCESS_TYPES
from lcsim.model.issues import Issue, pointer
from lcsim.model.model import Component, Endpoint, Model

__all__ = [
    "IDENTIFIER_PATTERN",
    "RESERVED_COMPONENT_IDS",
    "RESERVED_SCENARIO_ID",
    "STAND_IN_ENGINES",
    "InstalledEngine",
    "connection_issues",
    "engine_issues",
    "identifier_issues",
    "meaning_pass",
    "setting_issues",
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

    ``name`` is ``None`` for a model-layer stand-in: until an adapter exists for a domain
    (M2 for ``process``, M5 for ``optimization``), the model layer stands in for it (spec
    1 "Validation"). A stand-in has no adapter name, so ``run.engine`` cannot be checked
    against it and any name is accepted.
    """

    name: str | None
    domains: tuple[str, ...]


# One stand-in per Phase 1 domain, until the adapters are discovered (M2, spec 1 "Engine
# contract").
STAND_IN_ENGINES: tuple[InstalledEngine, ...] = tuple(
    InstalledEngine(None, (domain,)) for domain in DOMAINS
)


def engine_issues(
    domain: str,
    engine: str | None,
    installed: Sequence[InstalledEngine] = STAND_IN_ENGINES,
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
    names = [item.name for item in handling if item.name is not None]
    if engine is not None:
        chosen = [item for item in handling if item.name is None or item.name == engine]
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
                f"Name one of: {_words(names)}." if names else "Remove 'engine' from 'run'.",
            )
        ]
    if len(handling) == 1:
        return []
    return [
        _issue(
            "E102",
            ("run", "engine"),
            f"Several installed engines handle the domain {_quote(domain)}"
            + (f" ({_words(names)})" if names else "")
            + ", and 'run' names no 'engine' to choose one.",
            f"Add 'engine' to 'run', naming one of: {_words(names)}."
            if names
            else "Add 'engine' to 'run'.",
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
    constraints = (
        [item.id for item in model.program.constraints]
        if model.program is not None
        else [item.id for item in model.constraints]
    )
    issues += _identifier_list(
        _numbered(constraints, ("constraints",), "constraint", "constraint"),
        "each constraint needs its own id",
    )
    if model.program is not None:
        issues += _identifier_list(
            _numbered(
                [item.id for item in model.program.variables],
                ("variables",),
                "variable",
                "variable",
            ),
            "each variable needs its own id",
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


# --- the pass --------------------------------------------------------------------------------


def meaning_pass(model: Model) -> list[Issue]:
    """Part A of the meaning pass: identifiers, settings that name things, connections.

    E102 is not here: the loader checks it before building (``engine_issues``).
    """
    return [*identifier_issues(model), *setting_issues(model), *connection_issues(model)]


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


def _text(end: Endpoint) -> str:
    return f"{end.component}.{end.port}"


def _quote(text: str) -> str:
    return f"'{text}'"


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
