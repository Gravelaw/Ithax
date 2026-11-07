"""The sixteen model edits of spec 3 "Model edits", as pure functions on a model document.

The interface, the MCP server and scripts change a model through one mechanism: a batch
of edits, applied in order, all or nothing. This module applies a batch to the model file
as parsed JSON (a ``dict``) and never touches a file; the service saves the result.

``check_edits`` checks the shape of a batch, which does not depend on the model: each edit
is an object whose key ``edit`` names its kind, with the fields of its kind and no others,
each of the right JSON kind. A problem is an E184 issue at ``/edits/<n>`` or
``/edits/<n>/<field>`` (spec 1 "Validation issues": a malformed request).

``apply_edits`` applies a well-shaped batch to a copy of a model that passes the schema
pass. It returns the new model, or, when an edit cannot be applied, one E180 issue at
``/edits/<n>`` and no model. An edit cannot be applied in the cases spec 3 lists: an
unknown or duplicate component id, an unknown type, an unknown parameter, experiment or
scenario named by an edit that needs it, a parameter still referenced, a new parameter
without ``value`` and ``type``, a ``path`` that names nothing it may change, and a batch
whose result would not pass the schema pass (the E180 is then at the edit after the last
one that left the model passing). Everything else is applied and left to the meaning pass
to report, such as a component id that does not match the identifier pattern or a
connection to an unknown port.

An ``id`` names the first component, experiment or scenario with that id. JSON Pointers
(RFC 6901) address an array entry by an index without leading zeros; setting at ``-`` or at
the array's length appends.
"""

from __future__ import annotations

import copy
import math
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from lcsim.model.catalogue import BlockType
from lcsim.model.issues import Issue, pointer
from lcsim.model.schema import schema_pass

__all__ = [
    "EDIT_KINDS",
    "EditOutcome",
    "apply_edits",
    "check_edits",
    "first_non_finite",
    "parse_pointer",
]

# The JSON kind each field takes.
_TEXT = "text"
_OBJECT = "object"
_POINTER = "pointer"
_LABEL = "label"
_ANY = "any"

_KIND_WORDS = {
    _TEXT: "text",
    _OBJECT: "a JSON object",
    _POINTER: "a JSON Pointer such as '/service/mean'",
    _LABEL: "text, or null to remove the label",
}

# The experiment fields of spec 1 "Experiments" other than `id`.
_EXPERIMENT_FIELDS = (
    "length",
    "warmup",
    "replications",
    "seed",
    "scenarios",
    "confidence",
    "record_interval",
    "search",
)

# Per kind: its required fields, then its optional fields, each with its JSON kind.
_FIELDS: dict[str, tuple[dict[str, str], dict[str, str]]] = {
    "add_component": ({"id": _TEXT, "type": _TEXT, "params": _OBJECT}, {"ui": _OBJECT}),
    "remove_component": ({"id": _TEXT}, {}),
    "rename_component": ({"id": _TEXT, "new_id": _TEXT}, {}),
    "set_setting": ({"id": _TEXT, "path": _POINTER, "value": _ANY}, {}),
    "connect": ({"from": _TEXT, "to": _TEXT}, {}),
    "disconnect": ({"from": _TEXT}, {}),
    "set_parameter": (
        {"id": _TEXT},
        {"value": _ANY, "type": _ANY, "min": _ANY, "max": _ANY},
    ),
    "remove_parameter": ({"id": _TEXT}, {}),
    "set_experiment": ({"id": _TEXT}, dict.fromkeys(_EXPERIMENT_FIELDS, _ANY)),
    "remove_experiment": ({"id": _TEXT}, {}),
    "set_scenario": ({"experiment_id": _TEXT, "id": _TEXT, "set": _OBJECT}, {}),
    "remove_scenario": ({"experiment_id": _TEXT, "id": _TEXT}, {}),
    "set_path": ({"path": _POINTER, "value": _ANY}, {}),
    "remove_path": ({"path": _POINTER}, {}),
    "set_ui": ({"id": _TEXT, "ui": _OBJECT}, {}),
    "set_label": ({"id": _TEXT, "label": _LABEL}, {}),
}

#: The sixteen edit kinds, in the order of spec 3's table.
EDIT_KINDS: tuple[str, ...] = tuple(_FIELDS)

# Spec 3 `set_experiment`: a new experiment starts from the `base` experiment of a new
# project.
_NEW_EXPERIMENT = {"length": "8 h", "warmup": "0 s", "replications": 30}

# The top-level keys `set_path` and `remove_path` reach, and those they reach only in an
# `optimization` model; `/experiments/<n>/search` is reached too.
_REACHED = ("meta", "run", "objectives", "constraints")
_REACHED_OPTIMIZATION = ("variables", "objective")

_INDEX = re.compile(r"0|[1-9][0-9]*")
_ESCAPE = re.compile(r"~(?![01])")

Model = dict[str, Any]


@dataclass(frozen=True)
class EditOutcome:
    """The result of a batch: the new model, or ``None`` with the issues that stop it
    (E184 for a badly shaped batch, one E180 for an edit that cannot be applied)."""

    model: Model | None
    issues: tuple[Issue, ...]


class _Rejected(Exception):
    """An edit that cannot be applied, with what to tell the user."""

    def __init__(self, message: str, hint: str) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


# --- shape ---------------------------------------------------------------------------


def parse_pointer(text: str) -> list[str] | None:
    """The segments of the JSON Pointer ``text`` (RFC 6901), or ``None`` when it is not
    one: it is ``""`` or starts with ``/``, and each ``~`` is followed by ``0`` or ``1``."""
    if text and not text.startswith("/"):
        return None
    if _ESCAPE.search(text):
        return None
    if not text:
        return []
    return [part.replace("~1", "/").replace("~0", "~") for part in text[1:].split("/")]


def first_non_finite(value: object) -> str | None:
    """The JSON Pointer of the first number in ``value`` that JSON cannot hold (an
    infinity or NaN, as Python reads ``1e400``), or ``None`` when there is none."""
    if isinstance(value, float):
        return None if math.isfinite(value) else ""
    entries: Iterator[tuple[str | int, object]]
    if isinstance(value, dict):
        entries = iter(value.items())
    elif isinstance(value, list):
        entries = iter(enumerate(value))
    else:
        return None
    for key, item in entries:
        inner = first_non_finite(item)
        if inner is not None:
            return pointer(key) + inner
    return None


def _shape_issue(path: str, message: str, hint: str) -> Issue:
    return Issue(code="E184", component=None, path=path, message=message, hint=hint)


def _field_issue(index: int, name: str, kind: str, value: object) -> Issue | None:
    """An E184 issue when ``value`` is not of ``kind``, or holds a number JSON cannot
    hold, which could not be saved."""
    place = first_non_finite(value)
    if place is not None:
        where = f" (at '{place}')" if place else ""
        return _shape_issue(
            pointer("edits", index, name),
            f"In edit {index}, the field '{name}' holds a number too large to store{where}.",
            "Write a number a 64-bit float can hold, below about 1.8e308.",
        )
    if kind == _ANY:
        return None
    if kind == _OBJECT:
        fits = isinstance(value, dict)
    elif kind == _LABEL:
        fits = value is None or isinstance(value, str)
    elif kind == _POINTER:
        fits = isinstance(value, str) and parse_pointer(value) is not None
    else:
        fits = isinstance(value, str)
    if fits:
        return None
    return _shape_issue(
        pointer("edits", index, name),
        f"In edit {index}, the field '{name}' must be {_KIND_WORDS[kind]}.",
        'Spec 3 "Model edits" says what each field of an edit takes.',
    )


def _edit_shape_issues(index: int, edit: object) -> list[Issue]:
    if not isinstance(edit, dict):
        return [
            _shape_issue(
                pointer("edits", index),
                f"Edit {index} is not a JSON object.",
                'Write each edit as an object such as {"edit": "set_label", "id": "till", '
                '"label": "Till"}.',
            )
        ]
    kind = edit.get("edit")
    if not isinstance(kind, str) or kind not in _FIELDS:
        named = f"'{kind}'" if isinstance(kind, str) else "nothing"
        return [
            _shape_issue(
                pointer("edits", index, "edit"),
                f"Edit {index} names {named} as its kind, which is not an edit.",
                f"Set 'edit' to one of: {', '.join(EDIT_KINDS)}.",
            )
        ]
    required, optional = _FIELDS[kind]
    issues: list[Issue] = []
    for name in required:
        if name not in edit:
            issues.append(
                _shape_issue(
                    pointer("edits", index, name),
                    f"Edit {index} ({kind}) has no '{name}'.",
                    f"Add '{name}'; a {kind} edit needs {', '.join(repr(f) for f in required)}.",
                )
            )
    fields = {**required, **optional}
    for name, value in edit.items():
        if name == "edit":
            continue
        if name not in fields:
            issues.append(
                _shape_issue(
                    pointer("edits", index, name),
                    f"Edit {index} ({kind}) has the field '{name}', which a {kind} edit "
                    "does not take.",
                    f"Remove it; a {kind} edit takes {', '.join(repr(f) for f in fields)}.",
                )
            )
            continue
        issue = _field_issue(index, name, fields[name], value)
        if issue is not None:
            issues.append(issue)
    return issues


def check_edits(edits: object) -> list[Issue]:
    """The E184 issues of a batch's shape, in order; empty when it is well shaped."""
    if not isinstance(edits, list) or not edits:
        return [
            _shape_issue(
                "/edits",
                "The request field 'edits' must be a list holding at least one edit.",
                'Send {"edits": [ ... ]} with one object per edit.',
            )
        ]
    issues: list[Issue] = []
    for index, edit in enumerate(edits):
        issues.extend(_edit_shape_issues(index, edit))
    return issues


# --- finding things ------------------------------------------------------------------


def _first(items: object, ident: str) -> dict[str, Any] | None:
    """The first object of the list ``items`` whose ``id`` is ``ident``."""
    if not isinstance(items, list):
        return None
    return next(
        (item for item in items if isinstance(item, dict) and item.get("id") == ident), None
    )


def _component(model: Model, ident: str) -> dict[str, Any]:
    found = _first(model.get("components"), ident)
    if found is None:
        raise _Rejected(
            f"The model has no component '{ident}'.",
            "Name a component by its id; GET the model to see them.",
        )
    return found


def _experiment(model: Model, ident: str) -> dict[str, Any]:
    found = _first(model.get("experiments"), ident)
    if found is None:
        raise _Rejected(
            f"The model has no experiment '{ident}'.",
            "Name an experiment by its id, or create it first with set_experiment.",
        )
    return found


def _component_of(end: str) -> str | None:
    """The component part of a connection end ``<id>.<port>``, or ``None`` without a dot."""
    name, dot, _ = end.partition(".")
    return name if dot else None


# --- pointers ------------------------------------------------------------------------


def _show(segments: Sequence[str]) -> str:
    return pointer(*segments)


def _child(container: object, segment: str) -> tuple[bool, object]:
    """Whether ``container`` holds ``segment``, and the value there."""
    if isinstance(container, dict):
        return (segment in container, container.get(segment))
    if isinstance(container, list) and _INDEX.fullmatch(segment):
        position = int(segment)
        if position < len(container):
            return (True, container[position])
    return (False, None)


def _parent(root: object, segments: Sequence[str], where: str) -> object:
    """The container that holds the last of ``segments``; every earlier one must exist."""
    if not segments:
        raise _Rejected(
            f"The path {where} names no setting or key, so it cannot be changed.",
            "Give a path with at least one segment, such as '/capacity'.",
        )
    node = root
    for depth, segment in enumerate(segments[:-1]):
        exists, node = _child(node, segment)
        if not exists:
            missing = _show(segments[: depth + 1])
            raise _Rejected(
                f"The path {where} cannot be followed: '{missing}' does not exist.",
                "Every segment of a path but the last must already exist; set the parent first.",
            )
    if not isinstance(node, (dict, list)):
        raise _Rejected(
            f"The path {where} cannot be followed: '{_show(segments[:-1])}' is not an "
            "object or a list.",
            "A path can only go into objects and lists.",
        )
    return node


def _set_at(root: object, segments: Sequence[str], value: object, where: str) -> None:
    container = _parent(root, segments, where)
    last = segments[-1]
    if isinstance(container, dict):
        container[last] = copy.deepcopy(value)
        return
    assert isinstance(container, list)
    if last == "-" or last == str(len(container)):
        container.append(copy.deepcopy(value))
        return
    exists, _ = _child(container, last)
    if not exists:
        raise _Rejected(
            f"The path {where} names the entry '{last}' of a list of {len(container)}.",
            "Use an index of an existing entry, or '-' to add one at the end.",
        )
    container[int(last)] = copy.deepcopy(value)


def _remove_at(root: object, segments: Sequence[str], where: str) -> None:
    container = _parent(root, segments, where)
    exists, _ = _child(container, segments[-1])
    if not exists:
        raise _Rejected(
            f"The path {where} does not exist, so there is nothing to remove.",
            "GET the model to see what it holds.",
        )
    if isinstance(container, dict):
        del container[segments[-1]]
    else:
        assert isinstance(container, list)
        del container[int(segments[-1])]


def _reached(model: Model, segments: Sequence[str]) -> bool:
    """Whether ``set_path`` and ``remove_path`` may change what ``segments`` name."""
    if not segments:
        return False
    head = segments[0]
    if head in _REACHED:
        return True
    if head in _REACHED_OPTIMIZATION:
        return model.get("domain") == "optimization"
    return head == "experiments" and len(segments) >= 3 and segments[2] == "search"


def _reach(model: Model, path: str) -> list[str]:
    segments = parse_pointer(path)
    assert segments is not None  # check_edits checked the pointer
    if not _reached(model, segments):
        extra = (
            ", and in an optimization model /variables and /objective"
            if model.get("domain") != "optimization"
            else ", /variables and /objective"
        )
        raise _Rejected(
            f"The path '{path}' is not one set_path and remove_path may change.",
            "They change what lies under /meta, /run, /objectives, /constraints and "
            f"/experiments/<n>/search{extra}; use the other edits for the rest.",
        )
    return segments


# --- the edits -----------------------------------------------------------------------


def _add_component(model: Model, edit: Mapping[str, Any], types: Mapping[str, BlockType]) -> None:
    ident = edit["id"]
    if _first(model.get("components"), ident) is not None:
        raise _Rejected(
            f"The model already has a component '{ident}'.",
            "Choose an id no other component has.",
        )
    if edit["type"] not in types:
        raise _Rejected(
            f"There is no component type '{edit['type']}' for this model.",
            f"Use one of: {', '.join(types)}."
            if types
            else "This model's domain has no component types.",
        )
    added: dict[str, Any] = {"id": ident, "type": edit["type"], "params": edit["params"]}
    if "ui" in edit:
        added["ui"] = edit["ui"]
    model.setdefault("components", []).append(copy.deepcopy(added))


def _remove_component(model: Model, edit: Mapping[str, Any], _types: object) -> None:
    ident = edit["id"]
    found = _component(model, ident)
    model["components"].remove(found)
    model["connections"] = [
        connection
        for connection in model.get("connections", [])
        if ident not in (_component_of(connection["from"]), _component_of(connection["to"]))
    ]


def _renamed_end(end: str, old: str, new: str) -> str:
    return new + end[len(old) :] if _component_of(end) == old else end


def _rename_component(
    model: Model, edit: Mapping[str, Any], types: Mapping[str, BlockType]
) -> None:
    old, new = edit["id"], edit["new_id"]
    found = _component(model, old)
    if new == old:
        return
    if _first(model["components"], new) is not None:
        raise _Rejected(
            f"The model already has a component '{new}', so '{old}' cannot take that id.",
            "Choose an id no other component has.",
        )
    found["id"] = new
    for connection in model.get("connections", []):
        connection["from"] = _renamed_end(connection["from"], old, new)
        connection["to"] = _renamed_end(connection["to"], old, new)
    for item in model["components"]:
        block = types.get(item["type"])
        if block is None:
            continue
        params = item["params"]
        for spec in block.settings:
            if not spec.refers_to or spec.name not in params:
                continue
            value = params[spec.name]
            if value == old:
                params[spec.name] = new
            elif isinstance(value, list):
                params[spec.name] = [new if entry == old else entry for entry in value]
    for key in ("objectives", "constraints"):
        entries = model.get(key)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            metric = entry.get("metric") if isinstance(entry, dict) else None
            if isinstance(metric, str) and metric.startswith(old + "."):
                entry["metric"] = new + metric[len(old) :]


def _set_setting(model: Model, edit: Mapping[str, Any], _types: object) -> None:
    found = _component(model, edit["id"])
    segments = parse_pointer(edit["path"])
    assert segments is not None
    where = f"'{edit['path']}' in the settings of '{edit['id']}'"
    _set_at(found["params"], segments, edit["value"], where)


def _connect(model: Model, edit: Mapping[str, Any], _types: object) -> None:
    connections = model.setdefault("connections", [])
    kept: list[dict[str, Any]] = []
    replaced = False
    for connection in connections:
        if connection["from"] != edit["from"]:
            kept.append(connection)
        elif not replaced:
            connection["to"] = edit["to"]
            kept.append(connection)
            replaced = True
    if not replaced:
        kept.append({"from": edit["from"], "to": edit["to"]})
    model["connections"] = kept


def _disconnect(model: Model, edit: Mapping[str, Any], _types: object) -> None:
    model["connections"] = [
        connection
        for connection in model.get("connections", [])
        if connection["from"] != edit["from"]
    ]


def _set_parameter(model: Model, edit: Mapping[str, Any], _types: object) -> None:
    ident = edit["id"]
    parameters = model.setdefault("parameters", {})
    fields = {name: edit[name] for name in ("value", "type", "min", "max") if name in edit}
    if ident not in parameters and not ("value" in fields and "type" in fields):
        raise _Rejected(
            f"The model has no parameter '{ident}', and a new parameter needs both "
            "'value' and 'type'.",
            "Give 'value' and 'type' (integer, number or quantity) to create it.",
        )
    parameters.setdefault(ident, {}).update(copy.deepcopy(fields))


def _references(value: object, ident: str) -> bool:
    """Whether ``value`` holds ``{"$param": ident}`` anywhere."""
    if isinstance(value, dict):
        if list(value) == ["$param"]:
            return bool(value["$param"] == ident)
        return any(_references(item, ident) for item in value.values())
    if isinstance(value, list):
        return any(_references(item, ident) for item in value)
    return False


def _parameter_uses(model: Model, ident: str) -> Iterator[str]:
    """Where the parameter ``ident`` is used, in plain language."""
    for item in model.get("components", []):
        for name, value in item["params"].items():
            if _references(value, ident):
                yield f"'{item['id']}' (its '{name}' setting)"
    for experiment in model.get("experiments", []):
        scenarios = experiment.get("scenarios")
        for scenario in scenarios if isinstance(scenarios, list) else ():
            if isinstance(scenario, dict) and ident in scenario.get("set", {}):
                yield f"the scenario '{scenario['id']}' of '{experiment['id']}'"
        search = experiment.get("search")
        variables = search.get("variables") if isinstance(search, dict) else None
        if isinstance(variables, list) and ident in variables:
            yield f"the search of '{experiment['id']}'"


def _remove_parameter(model: Model, edit: Mapping[str, Any], _types: object) -> None:
    ident = edit["id"]
    parameters = model.get("parameters", {})
    if ident not in parameters:
        raise _Rejected(
            f"The model has no parameter '{ident}'.",
            "Name a parameter by its id; GET the model to see them.",
        )
    use = next(_parameter_uses(model, ident), None)
    if use is not None:
        raise _Rejected(
            f"The parameter '{ident}' is used by {use}, so it cannot be removed.",
            "Replace each use with a value first, then remove the parameter.",
        )
    del parameters[ident]


def _set_experiment(model: Model, edit: Mapping[str, Any], _types: object) -> None:
    ident = edit["id"]
    fields = {name: value for name, value in edit.items() if name not in ("edit", "id")}
    found = _first(model.get("experiments"), ident)
    if found is None:
        found = {"id": ident, **_NEW_EXPERIMENT}
        model.setdefault("experiments", []).append(found)
    found.update(copy.deepcopy(fields))


def _remove_experiment(model: Model, edit: Mapping[str, Any], _types: object) -> None:
    model["experiments"].remove(_experiment(model, edit["id"]))


def _scenarios(experiment: dict[str, Any]) -> list[Any]:
    scenarios = experiment.setdefault("scenarios", [])
    if not isinstance(scenarios, list):
        raise _Rejected(
            f"The 'scenarios' of the experiment '{experiment['id']}' is not a list.",
            "Set it to a list with set_experiment first.",
        )
    return scenarios


def _set_scenario(model: Model, edit: Mapping[str, Any], _types: object) -> None:
    experiment = _experiment(model, edit["experiment_id"])
    parameters = model.get("parameters", {})
    unknown = [name for name in edit["set"] if name not in parameters]
    if unknown:
        raise _Rejected(
            f"The scenario '{edit['id']}' sets '{unknown[0]}', which is not a parameter of "
            "the model.",
            "Create the parameter with set_parameter first, or remove it from 'set'.",
        )
    scenarios = _scenarios(experiment)
    found = _first(scenarios, edit["id"])
    if found is None:
        scenarios.append({"id": edit["id"], "set": copy.deepcopy(edit["set"])})
    else:
        found["set"] = copy.deepcopy(edit["set"])


def _remove_scenario(model: Model, edit: Mapping[str, Any], _types: object) -> None:
    experiment = _experiment(model, edit["experiment_id"])
    scenarios = experiment.get("scenarios")
    found = _first(scenarios, edit["id"])
    if found is None:
        raise _Rejected(
            f"The experiment '{experiment['id']}' has no scenario '{edit['id']}'.",
            "Name a scenario by its id; GET the model to see them.",
        )
    assert isinstance(scenarios, list)
    scenarios.remove(found)


def _set_path(model: Model, edit: Mapping[str, Any], _types: object) -> None:
    segments = _reach(model, edit["path"])
    _set_at(model, segments, edit["value"], f"'{edit['path']}'")


def _remove_path(model: Model, edit: Mapping[str, Any], _types: object) -> None:
    segments = _reach(model, edit["path"])
    _remove_at(model, segments, f"'{edit['path']}'")


def _set_ui(model: Model, edit: Mapping[str, Any], _types: object) -> None:
    _component(model, edit["id"])["ui"] = copy.deepcopy(edit["ui"])


def _set_label(model: Model, edit: Mapping[str, Any], _types: object) -> None:
    found = _component(model, edit["id"])
    if edit["label"] is None:
        found.pop("label", None)
    else:
        found["label"] = edit["label"]


_Apply = Callable[[Model, Mapping[str, Any], Mapping[str, BlockType]], None]

_APPLY: dict[str, _Apply] = {
    "add_component": _add_component,
    "remove_component": _remove_component,
    "rename_component": _rename_component,
    "set_setting": _set_setting,
    "connect": _connect,
    "disconnect": _disconnect,
    "set_parameter": _set_parameter,
    "remove_parameter": _remove_parameter,
    "set_experiment": _set_experiment,
    "remove_experiment": _remove_experiment,
    "set_scenario": _set_scenario,
    "remove_scenario": _remove_scenario,
    "set_path": _set_path,
    "remove_path": _remove_path,
    "set_ui": _set_ui,
    "set_label": _set_label,
}

assert tuple(_APPLY) == EDIT_KINDS


def _rejection(index: int, message: str, hint: str) -> EditOutcome:
    issue = Issue(
        code="E180",
        component=None,
        path=pointer("edits", index),
        message=f"Edit {index} cannot be applied: {message}",
        hint=hint,
    )
    return EditOutcome(None, (issue,))


def apply_edits(
    model: Mapping[str, Any],
    edits: Sequence[Any],
    component_types: Mapping[str, BlockType],
) -> EditOutcome:
    """Apply ``edits`` in order to a copy of ``model``, all or nothing.

    ``model`` is a model file that passes the schema pass; it is not changed.
    ``component_types`` are the component types the model's domain offers, by name (the
    installed adapters'), for ``add_component`` and for the settings ``rename_component``
    rewrites.
    """
    shape = check_edits(edits)
    if shape:
        return EditOutcome(None, tuple(shape))
    result: Model = copy.deepcopy(dict(model))
    for index, edit in enumerate(edits):
        try:
            _APPLY[edit["edit"]](result, edit, component_types)
        except _Rejected as rejected:
            return _rejection(index, rejected.message, rejected.hint)
    schema = schema_pass(result)
    if not schema:
        return EditOutcome(result, ())
    first = schema[0]
    where = f" at '{first.path}'" if first.path else ""
    return _rejection(
        _schema_culprit(model, edits, component_types),
        f"the model would no longer match the schema{where}: {first.message}",
        first.hint,
    )


def _schema_culprit(
    model: Mapping[str, Any],
    edits: Sequence[Any],
    component_types: Mapping[str, BlockType],
) -> int:
    """The edit after the last one that left ``model`` passing the schema pass, found by
    applying the batch again; only a batch whose result fails it is replayed."""
    replay: Model = copy.deepcopy(dict(model))
    last_passing = -1
    for index, edit in enumerate(edits):
        _APPLY[edit["edit"]](replay, edit, component_types)
        if not schema_pass(replay):
            last_passing = index
    return last_passing + 1
