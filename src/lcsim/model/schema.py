"""The model file's JSON Schema and the schema pass (spec 1 "Validation", pass 1).

The schema (``schema.json`` beside this module, JSON Schema draft 2020-12, no ``format``
keyword) checks only structure: the top-level keys and the JSON type of each top-level
value, and that every component, connection, parameter and experiment entry is an object
with its required keys of the right JSON type. Unknown keys are an error everywhere except
inside a component's ``ui`` object. Which keys are required, and the shape of
``constraints``, depend on ``domain``; a key of the other domain is an error. Everything
about values (identifier patterns, quantities, numbers, settings, enumerated words) is left
to the meaning pass, so that it reports its specific codes.

``schema_pass`` reports:

- E101 when ``format_version`` is not a version this reader opens (spec 1 "Versioning"). A
  file of another version may follow another schema, so nothing else is reported for it.
- E100 for each schema problem: a wrong JSON type, a missing required key, an unknown key,
  or a key that belongs to the other domain.

Messages are written here, in plain language, and name the key and the component; the
validator's own messages are never shown (research note ``spec-1-schema-and-units.md``).
``model_schema`` returns the schema, for ``GET /v1/schema`` (spec 3 "Endpoints").
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Mapping, Sequence
from functools import cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from lcsim.model.issues import Issue, pointer

__all__ = ["FORMAT_VERSION", "model_schema", "schema_pass"]

# The format version this reader writes and reads (spec 1 "Versioning"): it opens any file
# with the same major version and a minor version no higher than this one.
FORMAT_VERSION = "0.1"

# MAJOR.MINOR: two ASCII decimal integers without leading zeros.
_VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")

Segment = str | int

_INDEX = re.compile(r"[0-9]+")


@cache
def _schema() -> Mapping[str, Any]:
    text = resources.files("lcsim.model").joinpath("schema.json").read_text(encoding="utf-8")
    loaded: dict[str, Any] = json.loads(text)
    return loaded


@cache
def _validator() -> Draft202012Validator:
    return Draft202012Validator(_schema())


def model_schema() -> dict[str, Any]:
    """The model file's JSON Schema (draft 2020-12), as a fresh copy the caller may change."""
    return copy.deepcopy(dict(_schema()))


def _domain_keys() -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    """From the schema: which domain owns each domain-only key, and each domain's keys.

    A domain branch of the schema forbids, with ``{"not": {}}``, the keys that belong to
    another domain; those keys are owned by the domains that do not forbid them.
    """
    schema = _schema()
    forbidden: dict[str, set[str]] = {}
    for branch in schema["allOf"]:
        domain = branch["if"]["properties"]["domain"]["const"]
        forbidden[domain] = {
            key for key, rule in branch["then"]["properties"].items() if rule == {"not": {}}
        }
    owner = {
        key: next(domain for domain in forbidden if key not in forbidden[domain])
        for keys in forbidden.values()
        for key in keys
    }
    allowed = {
        domain: tuple(key for key in schema["properties"] if key not in keys)
        for domain, keys in forbidden.items()
    }
    return owner, allowed


_KEY_OWNER, _DOMAIN_KEYS = _domain_keys()


def schema_pass(document: object) -> list[Issue]:
    """Check a parsed model file against the schema; return its E100 and E101 issues.

    ``document`` is the file as parsed from JSON. An empty list means the file passed.
    Issues are sorted by ``path``, with array indexes in numeric order.
    """
    if isinstance(document, dict):
        version_issue = _version_issue(document)
        if version_issue is not None:
            return [version_issue]
    errors = list(_validator().iter_errors(_without_huge_integers(document)))
    # A key of the other domain is reported once; what is inside it is not judged.
    misplaced = [list(error.absolute_path) for error in errors if error.validator == "not"]
    issues: list[Issue] = []
    for error in errors:
        at = list(error.absolute_path)
        if any(len(at) > len(key) and at[: len(key)] == key for key in misplaced):
            continue
        for issue in _issues_from_error(error, document):
            if issue not in issues:
                issues.append(issue)
    return sorted(issues, key=lambda issue: _sort_key(issue.path))


# Integers longer than this many bits (about 4,200 decimal digits) are replaced before
# validation: jsonschema formats the offending value with repr() when it builds an error,
# and Python refuses to print an integer of more than 4,300 digits.
_HUGE_INTEGER_BITS = 14_000


def _is_huge_integer(value: object) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value.bit_length() > _HUGE_INTEGER_BITS
    )


def _without_huge_integers(document: object) -> object:
    """``document``, or a copy with every very large integer replaced by 0.

    The copy keeps every key and JSON type, so the schema reports the same problems at the
    same paths; messages name a number's kind, never its value. Both walks use an explicit
    stack, so a deeply nested file cannot exhaust Python's recursion limit here.
    """
    stack: list[object] = [document]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
        elif _is_huge_integer(value):
            break
    else:
        return document
    holder: list[object] = [document]
    work: list[tuple[dict[Any, object] | list[object], Any]] = [(holder, 0)]
    while work:
        container, key = work.pop()
        value = container[key]
        if isinstance(value, dict):
            copied_dict = dict(value)
            container[key] = copied_dict
            work.extend((copied_dict, name) for name in copied_dict)
        elif isinstance(value, list):
            copied_list = list(value)
            container[key] = copied_list
            work.extend((copied_list, index) for index in range(len(copied_list)))
        elif _is_huge_integer(value):
            container[key] = 0
    return holder[0]


def _version_issue(document: Mapping[str, Any]) -> Issue | None:
    """E101 for a ``format_version`` string this reader cannot open; ``None`` otherwise.

    A missing or non-string ``format_version`` is left to the schema (E100).
    """
    version = document.get("format_version")
    if not isinstance(version, str):
        return None
    reader_major, reader_minor = FORMAT_VERSION.split(".")
    match = _VERSION.fullmatch(version)
    if match is None:
        message = (
            f"'format_version' is '{version}', which is not of the form MAJOR.MINOR, "
            f"such as '{FORMAT_VERSION}'."
        )
        hint = (
            f"Write the format version as two whole numbers with a dot, as in '{FORMAT_VERSION}'."
        )
    else:
        # The parts are compared as digit strings, never converted with int(): Python
        # refuses to convert a string of more than 4,300 digits. Without leading zeros,
        # a longer digit string is the larger number.
        major, minor = match.group(1), match.group(2)
        if major == reader_major and (len(minor), minor) <= (len(reader_minor), reader_minor):
            return None
        message = (
            f"'format_version' is '{version}', but this program reads format versions "
            f"{reader_major}.0 to {FORMAT_VERSION}."
        )
        if major == reader_major:
            hint = (
                "The file was written by a newer version of the program; "
                "update the program to open it."
            )
        else:
            hint = (
                "The file uses another major version of the format, which this program "
                "cannot read or convert. Open it with a version of the program that reads it."
            )
    return Issue(code="E101", component=None, path="/format_version", message=message, hint=hint)


def _issues_from_error(error: ValidationError, document: object) -> list[Issue]:
    """Plain-language E100 issues for one validator error; its own message is never used."""
    at: list[Segment] = list(error.absolute_path)
    instance = error.instance
    where = _describe(at, document, capital=True)
    place = _describe(at, document, capital=False)
    if error.validator == "additionalProperties" and isinstance(instance, dict):
        known = list(error.schema.get("properties", {})) if isinstance(error.schema, dict) else []
        allowed = ", ".join(_allowed_keys(at, known, document))
        return [
            _issue(
                [*at, key],
                document,
                f"{where} has an unknown key '{key}'.",
                f"Remove '{key}' or correct its spelling. The keys allowed here are: {allowed}.",
            )
            for key in instance
            if key not in known
        ]
    if error.validator == "required" and isinstance(instance, dict):
        required = error.validator_value if isinstance(error.validator_value, list) else []
        return [
            _issue(
                [*at, key],
                document,
                f"{where} is missing the required key '{key}'.",
                f"Add '{key}' to {place}.",
            )
            for key in required
            if key not in instance
        ]
    if error.validator == "type":
        expected = "a JSON object" if not at else _expected_type(error.validator_value)
        return [
            _issue(
                at,
                document,
                f"{where} must be {expected}, not {_json_kind(instance)}.",
                f"Change {place} to {expected}.",
            )
        ]
    if error.validator == "not" and len(at) == 1 and isinstance(document, dict):
        key = str(at[0])
        owner = _KEY_OWNER[key]
        return [
            _issue(
                at,
                document,
                f"The key '{key}' belongs to the '{owner}' domain, but this model's domain is "
                f"'{document['domain']}'.",
                f"Remove '{key}', or change 'domain' if the model is meant for the '{owner}' "
                "domain.",
            )
        ]
    # Not reached with the shipped schema; kept so that a schema change can never show a
    # validator's own message to a user.
    return [
        _issue(
            at,
            document,
            f"{where} does not fit the model format.",
            "Correct this value; the model format is described in spec 1.",
        )
    ]


def _issue(path: Sequence[Segment], document: object, message: str, hint: str) -> Issue:
    return Issue(
        code="E100",
        component=_component_id(path, document),
        path=pointer(*path),
        message=message,
        hint=hint,
    )


def _allowed_keys(at: Sequence[Segment], known: list[str], document: object) -> list[str]:
    """The keys allowed in the object at ``at``; at top level, those of the model's domain."""
    if not at and isinstance(document, dict):
        domain = document.get("domain")
        if isinstance(domain, str) and domain in _DOMAIN_KEYS:
            return list(_DOMAIN_KEYS[domain])
    return known


def _component_id(path: Sequence[Segment], document: object) -> str | None:
    """The id of the component the path lies in, when it has a string id."""
    if len(path) < 2 or path[0] != "components" or not isinstance(path[1], int):
        return None
    item = _value_at(path[:2], document)
    if isinstance(item, dict) and isinstance(item.get("id"), str):
        component: str = item["id"]
        return component
    return None


# Entries named by a noun and their id rather than "item n of ...": the top-level lists,
# and the scenarios of an experiment.
_NOUNS = {
    "components": "component",
    "connections": "connection",
    "experiments": "experiment",
    "objectives": "objective",
    "constraints": "constraint",
    "variables": "variable",
}


def _describe(path: Sequence[Segment], document: object, *, capital: bool) -> str:
    """The place ``path`` names, in plain language: "component 'till'", "'set' in ..."."""
    text = _place(list(path), document)
    return text[0].upper() + text[1:] if capital else text


def _place(path: list[Segment], document: object) -> str:
    if not path:
        return "the model file"
    *parent, last = path
    if isinstance(last, int):
        container = parent[-1] if parent else None
        noun = None
        if len(path) == 2 and isinstance(container, str):
            noun = _NOUNS.get(container)
        elif len(path) == 4 and path[0] == "experiments" and container == "scenarios":
            noun = "scenario"
        if noun is None:
            return f"item {last + 1} of {_place(parent, document)}"
        item = _value_at(path, document)
        ident = item.get("id") if isinstance(item, dict) else None
        text = f"{noun} '{ident}'" if isinstance(ident, str) else f"{noun} {last + 1}"
        if len(path) > 2:
            text += f" in {_place(path[:-2], document)}"
        return text
    if parent == ["parameters"]:
        return f"parameter '{last}'"
    text = f"'{last}'"
    if parent:
        text += f" in {_place(parent, document)}"
    return text


def _value_at(path: Sequence[Segment], document: object) -> object:
    value: object = document
    for segment in path:
        if isinstance(segment, int) and isinstance(value, list) and segment < len(value):
            value = value[segment]
        elif isinstance(segment, str) and isinstance(value, dict) and segment in value:
            value = value[segment]
        else:
            return None
    return value


_TYPE_NAMES = {
    "object": "an object",
    "array": "an array",
    "string": "text",
    "number": "a number",
    "integer": "a whole number",
    "boolean": "true or false",
    "null": "null",
}


def _expected_type(validator_value: object) -> str:
    names = validator_value if isinstance(validator_value, list) else [validator_value]
    return " or ".join(_TYPE_NAMES.get(str(name), str(name)) for name in names)


def _json_kind(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dict):
        return "an object"
    if isinstance(value, list):
        return "an array"
    if isinstance(value, str):
        return "text"
    return "a number"


def _sort_key(path: str) -> tuple[tuple[int, int, str, str], ...]:
    """Sort key for a JSON Pointer: array indexes in numeric order, keys by name.

    A segment of ASCII digits sorts as a number, compared by length and then by text
    after leading zeros are dropped, so a key of any length needs no int() conversion
    (Python refuses to convert more than 4,300 digits). Object keys made of digits sort
    the same way; they never share a parent with an array index.
    """
    parts = path.split("/")[1:] if path else []
    key: list[tuple[int, int, str, str]] = []
    for part in parts:
        if _INDEX.fullmatch(part):
            digits = part.lstrip("0") or "0"
            key.append((0, len(digits), digits, part))
        else:
            key.append((1, 0, part, ""))
    return tuple(key)
