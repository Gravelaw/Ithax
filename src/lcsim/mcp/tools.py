"""The MCP tools: one registry, one argument check, one way of turning answers into tool
results (spec 4 "MCP tools" and "How the server runs and answers"; AKS-115).

Each tool is a ``ToolSpec``: its name, a summary, its inputs as spec 4's table names them,
one worked example (arguments and an abridged result, written into the description, since
"the assistant sees nothing else"), and ``calls``, which makes the tool's request or
requests to the service through ``ServiceClient`` and returns the answer to report. AKS-134
adds the write and run tools to ``TOOLS`` the same way; a tool that makes several requests
(``get_results``) returns the answer it composes from them.

``run_tool`` is the one path from a call to a result:

1. ``check_arguments``: an input missing, unknown or of the wrong kind is an E184 issue at
   ``/<input>`` (the service's code for a malformed request, its ``path`` pointing into the
   arguments as the service's points into a request body), and no request is sent;
2. the tool's ``calls``; a service that cannot be reached is ``ServiceUnavailable``, E193;
3. the answer as a result: its body as JSON text, and the same object as
   ``structuredContent`` when it is a JSON object; marked ``isError`` for a status of 400
   or above, the service's body unchanged.

Errors are data (spec 4): every one of these is a tool result, never a protocol error.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from mcp.types import CallToolResult, TextContent, Tool

from lcsim.mcp.client import Answer, ServiceClient, ServiceUnavailable
from lcsim.model.issues import Issue, pointer

__all__ = [
    "KINDS",
    "MALFORMED",
    "TOOLS",
    "Input",
    "ToolSpec",
    "check_arguments",
    "result_of",
    "run_tool",
    "tool_named",
]

#: Spec 1 code for a malformed request, used for a tool call's inputs as the service uses
#: it for a request body (spec 3 "Status codes and errors").
MALFORMED = "E184"


def _valid_unicode(text: str) -> bool:
    """Whether ``text`` can be written as UTF-8: no lone surrogate (``"\\ud800"``), which a
    JSON escape can carry but no request, path or result can hold (spec 3 treats such text
    in a request as E184)."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


#: The kinds an input may have: the JSON Schema type the input schema declares, the words
#: an issue uses, and the check. AKS-134 adds the kinds its inputs need here.
KINDS: Mapping[str, tuple[str, str, Callable[[object], bool]]] = {
    "text": (
        "string",
        "text",
        lambda value: isinstance(value, str) and _valid_unicode(value),
    ),
}

#: The error answer's status from which a result is marked ``isError``.
_ERROR_STATUS = 400


@dataclass(frozen=True)
class Input:
    """One input of a tool: its name, kind (a key of ``KINDS``), description and whether
    it is required."""

    name: str
    kind: str
    description: str
    required: bool = False


Calls = Callable[[ServiceClient, Mapping[str, Any]], Answer]


@dataclass(frozen=True)
class ToolSpec:
    """One MCP tool. ``description`` is ``summary`` with the worked example appended."""

    name: str
    summary: str
    inputs: tuple[Input, ...]
    example_arguments: Mapping[str, object]
    example_result: str
    calls: Calls

    @property
    def description(self) -> str:
        arguments = json.dumps(self.example_arguments)
        return f"{self.summary}\n\nExample: {arguments} returns {self.example_result}"

    def input_schema(self) -> dict[str, Any]:
        """The input schema: the declared inputs and no others."""
        schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                item.name: {"type": KINDS[item.kind][0], "description": item.description}
                for item in self.inputs
            },
            "additionalProperties": False,
        }
        required = [item.name for item in self.inputs if item.required]
        if required:
            schema["required"] = required
        return schema

    def tool(self) -> Tool:
        """The tool as ``tools/list`` shows it."""
        return Tool(name=self.name, description=self.description, input_schema=self.input_schema())


def _shown(name: str) -> str:
    """``name`` as an issue can show it: unchanged, or with a lone surrogate written as its
    escape, so the issue can be sent."""
    if _valid_unicode(name):
        return name
    return name.encode("utf-8", "backslashreplace").decode("utf-8")


def _problem(name: str, message: str, hint: str) -> Issue:
    return Issue(code=MALFORMED, component=None, path=pointer(name), message=message, hint=hint)


def check_arguments(spec: ToolSpec, arguments: Mapping[str, object]) -> list[Issue]:
    """The E184 issues of ``arguments`` for ``spec``: each unknown input (in name order),
    then each declared input missing or of the wrong kind (in declaration order)."""
    declared = {item.name: item for item in spec.inputs}
    names = ", ".join(f"'{name}'" for name in declared)
    takes = f"the inputs of {spec.name} are {names}" if names else f"{spec.name} takes no inputs"
    unknown = [_shown(name) for name in sorted(arguments) if name not in declared]
    problems = [
        _problem(name, f"{spec.name} has no input '{name}'.", f"Leave '{name}' out; {takes}.")
        for name in unknown
    ]
    for item in spec.inputs:
        _, words, accepts = KINDS[item.kind]
        if item.name not in arguments:
            if item.required:
                problems.append(
                    _problem(
                        item.name,
                        f"{spec.name} needs '{item.name}'.",
                        f"Add '{item.name}': {item.description}",
                    )
                )
        elif not accepts(arguments[item.name]):
            problems.append(
                _problem(
                    item.name,
                    f"The input '{item.name}' of {spec.name} must be {words}.",
                    f"Give '{item.name}' as {words}: {item.description}",
                )
            )
    return problems


def result_of(body: object, *, is_error: bool) -> CallToolResult:
    """A tool result holding ``body``: its JSON text, and the same object as structured
    content when it is a JSON object."""
    text = json.dumps(body, ensure_ascii=False)
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content=body if isinstance(body, dict) else None,
        is_error=is_error,
    )


def run_tool(
    spec: ToolSpec, client: ServiceClient, arguments: Mapping[str, Any] | None
) -> CallToolResult:
    """Call ``spec`` with ``arguments`` (``None`` as none) and return its result."""
    given: Mapping[str, Any] = arguments or {}
    problems = check_arguments(spec, given)
    if problems:
        message = f"The inputs of {spec.name} are not as its input schema says."
        body = {
            "error": {"code": MALFORMED, "message": message},
            "issues": [issue.as_dict() for issue in problems],
        }
        return result_of(body, is_error=True)
    try:
        answer = spec.calls(client, given)
    except ServiceUnavailable as unavailable:
        return result_of(unavailable.body(), is_error=True)
    return result_of(answer.body, is_error=answer.status >= _ERROR_STATUS)


def _segment(value: str) -> str:
    """``value`` as one percent-encoded path segment, so no input can name another route."""
    return quote(value, safe="")


def _get(path: str) -> Calls:
    """A tool that sends ``GET path``."""
    return lambda client, arguments: client.request("GET", path)


def _get_schema(client: ServiceClient, arguments: Mapping[str, Any]) -> Answer:
    if "component_type" in arguments:
        return client.request(
            "GET", f"/v1/schema/components/{_segment(arguments['component_type'])}"
        )
    return client.request("GET", "/v1/schema")


def _get_model(client: ServiceClient, arguments: Mapping[str, Any]) -> Answer:
    return client.request("GET", f"/v1/projects/{_segment(arguments['project_id'])}/model")


def _validate_model(client: ServiceClient, arguments: Mapping[str, Any]) -> Answer:
    return client.request("POST", f"/v1/projects/{_segment(arguments['project_id'])}/validate")


_PROJECT_ID = Input(
    "project_id",
    "text",
    "The project's id, the 'id' list_projects gives for it.",
    required=True,
)
_EXAMPLE_PID = "6f1c2a4e-8d3b-4c55-9a70-2b9e1d4f7c08"

LIST_TEMPLATES = ToolSpec(
    name="list_templates",
    summary=(
        "List the ready-made templates a new project can start from (GET /v1/templates). "
        "Returns an array of template.json objects, each with at least id, title and "
        "summary. An empty array is a normal answer: no templates are installed yet."
    ),
    inputs=(),
    example_arguments={},
    example_result="[]",
    calls=_get("/v1/templates"),
)

GET_SCHEMA = ToolSpec(
    name="get_schema",
    summary=(
        "Read the model file format (GET /v1/schema), or, with component_type, one block "
        "type's settings, ports, metrics and behaviour (GET "
        "/v1/schema/components/{component_type}). Ask for one type at a time: the whole "
        "schema is long. Each setting gives its kind, whether it is required and any "
        "default; list_engines names the installed types. Behaviour defaults, from the "
        "engine's block reference: a server's queue is unlimited, first in first out, "
        "unless queue_capacity or discipline says otherwise; a source whose next block "
        "cannot take an item discards it (counted in <source>.discarded), arrivals are "
        "never delayed; a full queue with on_full 'block' (the default) holds items "
        "upstream, with 'discard' it drops them; a failure takes one unit of its target and "
        "an item in service resumes with its remaining time after repair (preempt-resume); "
        "a schedule's capacity is 0 outside its listed shifts, and a unit busy when it "
        "falls finishes its item first; a server with a pool takes its own unit first, "
        "then one pool unit, and its service starts when it holds both."
    ),
    inputs=(
        Input(
            "component_type",
            "text",
            "A block type such as 'server'; leave out for the whole model schema.",
        ),
    ),
    example_arguments={"component_type": "server"},
    example_result=(
        '{"type": "server", "domain": "process", "engine": "simpy", "description": "Items '
        "wait in the server's own queue, then hold one unit of capacity for one service "
        'time.", "inputs": ["in"], "outputs": ["out"], "outputs_from": null, "settings": '
        '[{"name": "capacity", "kind": "number", "required": true, "integer": true, '
        '"minimum": 1}, {"name": "service", "kind": "distribution", "required": true, '
        '"dimension": "time"}, ...], "metrics": ["wait.mean", "utilization", ...]}'
    ),
    calls=_get_schema,
)

LIST_PROJECTS = ToolSpec(
    name="list_projects",
    summary=(
        "List the projects the service knows, in the order they were registered (GET "
        "/v1/projects). Each is {id, name, created, layout_version, model_revision, path, "
        "available}; id is the project_id the other tools take, and a project whose folder "
        "cannot be read has available false."
    ),
    inputs=(),
    example_arguments={},
    example_result=(
        f'[{{"id": "{_EXAMPLE_PID}", "name": "Coffee shop", "created": '
        '"2026-11-08T09:30:00.000Z", "layout_version": 1, "model_revision": 3, "path": '
        f'"/home/me/.local/share/lcsim/projects/{_EXAMPLE_PID}", "available": true}}]'
    ),
    calls=_get("/v1/projects"),
)

GET_MODEL = ToolSpec(
    name="get_model",
    summary=(
        "Read a project's model file and its revision (GET "
        "/v1/projects/{project_id}/model). Returns {model, revision}; send the revision as "
        "base_revision when changing the model, so a change the user made meanwhile is not "
        "overwritten."
    ),
    inputs=(_PROJECT_ID,),
    example_arguments={"project_id": _EXAMPLE_PID},
    example_result=(
        '{"model": {"format_version": "0.1", "meta": {"name": "Coffee shop"}, "domain": '
        '"process", "parameters": {}, "components": [...], "connections": [...], '
        '"experiments": [{"id": "base", "length": "8 h", "warmup": "0 s", "replications": '
        '30}], "run": {"target": "local", "fidelity": "standard"}}, "revision": 3}'
    ),
    calls=_get_model,
)

VALIDATE_MODEL = ToolSpec(
    name="validate_model",
    summary=(
        "Check a project's saved model as a run would: the schema, the meaning of every "
        "setting and connection, then the engine's own check (POST "
        "/v1/projects/{project_id}/validate). Returns {revision, issues}; each issue has "
        "code (E... an error, W... a warning), severity, component, path (a JSON Pointer "
        "into the model), message and hint. Errors block a run, warnings do not; an empty "
        "issues list means the model can run. Fix what the hint says, then validate again."
    ),
    inputs=(_PROJECT_ID,),
    example_arguments={"project_id": _EXAMPLE_PID},
    example_result=(
        '{"revision": 1, "issues": [{"code": "E122", "severity": "error", "component": '
        '"till", "path": "/components/0/params/capacity", "message": "Component \'till\' '
        "is missing the required setting 'capacity'.\", \"hint\": \"Add 'capacity' to the "
        "'params' of 'till'.\"}]}"
    ),
    calls=_validate_model,
)

LIST_ENGINES = ToolSpec(
    name="list_engines",
    summary=(
        "List the installed engines and what each can do (GET /v1/engines): name, version, "
        "the model domains it runs (process or optimization), its block types, hardware, "
        "parallel modes, licence and how it is invoked."
    ),
    inputs=(),
    example_arguments={},
    example_result=(
        '[{"name": "highs", "domains": ["optimization"], "component_types": [], ...}, '
        '{"name": "simpy", "domains": ["process"], "component_types": ["source", "server", '
        '"delay", "branch", "queue", "batch", "unbatch", "store", "resource_pool", '
        '"schedule", "failure", "sink"], "parallel_modes": ["replications"], ...}]'
    ),
    calls=_get("/v1/engines"),
)

#: The tools, in the order ``tools/list`` gives them (spec 4 "MCP tools").
TOOLS: tuple[ToolSpec, ...] = (
    LIST_TEMPLATES,
    GET_SCHEMA,
    LIST_PROJECTS,
    GET_MODEL,
    VALIDATE_MODEL,
    LIST_ENGINES,
)

_BY_NAME = {spec.name: spec for spec in TOOLS}


def tool_named(name: str) -> ToolSpec:
    """The tool called ``name``; ``KeyError`` when there is none."""
    return _BY_NAME[name]
