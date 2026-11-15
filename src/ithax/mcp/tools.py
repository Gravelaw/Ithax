"""The MCP tools: one registry, one argument check, one way of turning answers into tool
results (spec 4 "MCP tools", "How the server runs and answers" and "Limits"; AKS-115 for
the six read tools, AKS-134 for the five write and run tools).

Each tool is a ``ToolSpec``: its name, a summary, its inputs as spec 4's table names them,
one worked example (arguments and an abridged result, written into the description, since
"the assistant sees nothing else"), and ``calls``, which makes the tool's request or
requests to the service through ``ServiceClient`` and returns the answer to report. A tool
that makes several requests (``get_results``) returns the answer it composes from them, or
the first refusal unchanged; ``run_model`` starts its run through the client's
``started_runs`` (``ithax.mcp.limits``), which applies spec 4's two-run limit.

``run_tool`` is the one path from a call to a result:

1. ``check_arguments``: an input missing, unknown or of the wrong kind is an E184 issue at
   ``/<input>`` (the service's code for a malformed request, its ``path`` pointing into the
   arguments as the service's points into a request body), and no request is sent;
2. the tool's ``calls``; a service that cannot be reached is ``ServiceUnavailable``, E193,
   and a run refused by the limit is ``RunLimitReached``, E194;
3. the answer as a result: its body as JSON text, and the same object as
   ``structuredContent`` when it is a JSON object; marked ``isError`` for a status of 400
   or above, the service's body unchanged.

Errors are data (spec 4): every one of these is a tool result, never a protocol error.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from mcp.types import CallToolResult, TextContent, Tool

from ithax.mcp.client import Answer, ServiceClient, ServiceUnavailable
from ithax.mcp.limits import RunLimitReached, segment
from ithax.model.edits import edit_schemas
from ithax.model.issues import Issue, pointer
from ithax.model.migration import FORMAT_VERSION
from ithax.strict_json import is_whole, json_text

__all__ = [
    "KINDS",
    "MALFORMED",
    "MAX_DEPTH",
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


#: How deep the value of an ``edits`` input may nest: far more than any model needs (a shift
#: of a schedule is six levels down), and well within what a request body can be encoded
#: with (spec 4 "How the server runs and answers"; AKS-134).
MAX_DEPTH = 100


def _is_text(value: object) -> bool:
    return isinstance(value, str) and _valid_unicode(value)


def _is_texts(value: object) -> bool:
    return isinstance(value, list) and all(_is_text(item) for item in value)


def _sendable(value: object) -> bool:
    """Whether ``value`` can be sent as a request body: every number finite (JSON has no
    ``NaN`` or infinity, and the client encodes with ``allow_nan=False``) and no more than
    ``MAX_DEPTH`` levels of arrays and objects. Walked without recursion, so a deep value
    is refused rather than failing the walk."""
    pending: list[tuple[object, int]] = [(value, 1)]
    while pending:
        item, depth = pending.pop()
        if isinstance(item, float) and not math.isfinite(item):
            return False
        if isinstance(item, (list, dict)):
            if depth > MAX_DEPTH:
                return False
            children = item.values() if isinstance(item, dict) else item
            pending.extend((child, depth + 1) for child in children)
    return True


#: The kinds an input may have: the JSON Schema the input schema declares for it, the words
#: an issue uses, and the check (spec 4 "How the server runs and answers").
KINDS: Mapping[str, tuple[Mapping[str, Any], str, Callable[[object], bool]]] = {
    "text": ({"type": "string"}, "text", _is_text),
    "whole number": ({"type": "integer"}, "a whole number", is_whole),
    "texts": (
        {"type": "array", "items": {"type": "string"}},
        "an array of text",
        _is_texts,
    ),
    "edits": (
        # Each kind typed (#98), from the table the service checks edits against.
        {"type": "array", "items": {"oneOf": edit_schemas()}},
        f"an array of edits whose numbers are finite, nested at most {MAX_DEPTH} levels deep",
        lambda value: isinstance(value, list) and _sendable(value),
    ),
}

#: The error answer's status from which a result is marked ``isError``.
_ERROR_STATUS = 400


def refused(answer: Answer) -> bool:
    """Whether a result is marked ``isError``: an answer with an error status."""
    return answer.status >= _ERROR_STATUS


def refused_or_saved_with_errors(answer: Answer) -> bool:
    """``refused``, or a write saved with an error among its issues, so that the model
    cannot run as saved (#98, Reviewer B finding 8)."""
    if refused(answer):
        return True
    issues = answer.body.get("issues", []) if isinstance(answer.body, dict) else []
    return isinstance(issues, list) and any(
        isinstance(issue, dict) and issue.get("severity") == "error" for issue in issues
    )


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
    #: Whether an answer's result is marked ``isError``.
    is_error: Callable[[Answer], bool] = refused

    @property
    def description(self) -> str:
        arguments = json_text(self.example_arguments, ascii_only=True)
        return f"{self.summary}\n\nExample: {arguments} returns {self.example_result}"

    def input_schema(self) -> dict[str, Any]:
        """The input schema: the declared inputs and no others."""
        schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                item.name: {**KINDS[item.kind][0], "description": item.description}
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
    text = json_text(body)
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
    except (ServiceUnavailable, RunLimitReached) as refusal:
        return result_of(refusal.body(), is_error=True)
    return result_of(answer.body, is_error=spec.is_error(answer))


_segment = segment


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
        "Returns an array of every installed template's template.json, in id order, each "
        "with id, title, summary, audience, concepts, minutes, experiment (the experiment "
        "its lesson runs; null for an optimization model), origin, licence and exercise. "
        "Start a project from one with create_model and its id as template_id. An empty "
        "array means no template is installed."
    ),
    inputs=(),
    example_arguments={},
    example_result=(
        '[{"id": "coffee_shop", "title": "Coffee shop queue", "summary": "Customers arrive '
        'at random at a coffee shop with one till. ...", "audience": "Students", "concepts": '
        '["arrivals", "service", "waiting", ...], "minutes": 15, "experiment": "base", ...}, '
        '{"id": "machine_breakdowns", ...}, {"id": "three_machine_line", ...}]'
    ),
    calls=_get("/v1/templates"),
)

GET_SCHEMA = ToolSpec(
    name="get_schema",
    summary=(
        "Read the model file format (GET /v1/schema), or, with component_type, one block "
        "type's settings, ports, metrics and behaviour (GET "
        "/v1/schema/components/{component_type}). Ask for one type at a time: the whole "
        "schema is long. Each setting gives its kind, whether it is required and any "
        "default; any number or time setting, a distribution's fields included, may "
        'instead be a parameter, {"$param": "<id>"} (set_parameter), which scenarios and an '
        "experiment's search change. list_engines names the installed types. Behaviour "
        "defaults, from the "
        "engine's block reference: a server's queue is unlimited, first in first out, "
        "unless queue_capacity or discipline says otherwise; a source whose next block "
        "cannot take an item discards it (counted in <source>.discarded), arrivals are "
        "never delayed; a full queue with on_full 'block' (the default) holds items "
        "upstream, with 'discard' it drops them; a failure takes one unit of its target and "
        "an item in service resumes with its remaining time after repair (preempt-resume); "
        "a schedule's capacity is 0 outside its listed shifts, and a unit busy when it "
        "falls finishes its item first; a server with a pool takes its own unit first, "
        "then one pool unit, and its service starts when it holds both. The whole schema "
        "names the allowed words: a sense is minimize or maximize; an op is '<=' or '>=', "
        "and also '==' in an optimization model; a variable's type is continuous, integer "
        "or binary. A search, compactly: parameters "
        '{"tills": {"value": 1, "type": "integer", "min": 1, "max": 5}}, objectives '
        '[{"id": "wait", "metric": "till.wait.mean", "sense": "minimize"}], constraints '
        '[{"id": "busy", "metric": "till.utilization", "op": ">=", "value": 0.35}] and, in '
        'an experiment, search {"objective": "wait", "budget": 10}. An optimization model '
        '(domain optimization), compactly: variables [{"id": "chairs", "type": '
        '"continuous", "lower": 0}, ...], objective {"sense": "maximize", "linear": '
        '{"chairs": 45, "tables": 80}} and constraints [{"id": "wood", "linear": '
        '{"chairs": 5, "tables": 20}, "op": "<=", "rhs": 400}, ...].'
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
        "available, opened, template, lesson_step}; id is the project_id the other tools "
        "take, and a project whose folder cannot be read has available false. opened, "
        "template and lesson_step are the interface's notes, null until known."
    ),
    inputs=(),
    example_arguments={},
    example_result=(
        f'[{{"id": "{_EXAMPLE_PID}", "name": "Coffee shop", "created": '
        '"2026-11-08T09:30:00.000Z", "layout_version": 1, "model_revision": 3, "path": '
        f'"/home/me/.local/share/ithax/projects/{_EXAMPLE_PID}", "available": true, '
        '"opened": "2026-11-08T10:02:00.000Z", "template": "coffee_shop", "lesson_step": null}]'
    ),
    calls=_get("/v1/projects"),
)


def _rename_project(client: ServiceClient, arguments: Mapping[str, Any]) -> Answer:
    return client.request(
        "PATCH",
        f"/v1/projects/{_segment(arguments['project_id'])}",
        {"name": arguments["name"]},
    )


def _remove_project(client: ServiceClient, arguments: Mapping[str, Any]) -> Answer:
    return client.request("POST", f"/v1/projects/{_segment(arguments['project_id'])}/remove")


RENAME_PROJECT = ToolSpec(
    name="rename_project",
    summary=(
        "Give a project a new name (PATCH /v1/projects/{project_id} with {name}). Only the "
        "name the projects are listed by changes: the folder, the id and the model stay as "
        "they are. Returns the project as list_projects lists it."
    ),
    inputs=(_PROJECT_ID, Input("name", "text", "The new name, not empty.", required=True)),
    example_arguments={"project_id": _EXAMPLE_PID, "name": "Corner café"},
    example_result=(
        f'{{"id": "{_EXAMPLE_PID}", "name": "Corner café", "created": '
        '"2026-11-08T09:30:00.000Z", "layout_version": 1, "model_revision": 3, "path": '
        f'"/home/me/.local/share/ithax/projects/{_EXAMPLE_PID}", "available": true, '
        '"opened": null, "template": "coffee_shop", "lesson_step": null}'
    ),
    calls=_rename_project,
)

REMOVE_PROJECT = ToolSpec(
    name="remove_project",
    summary=(
        "Take a project off the list the service keeps (POST "
        "/v1/projects/{project_id}/remove). Nothing is deleted: the project's folder and its "
        "files are kept, and the user can open the folder again from the app. Returns {id, "
        "path}. Ask the user before removing a project they did not ask to remove."
    ),
    inputs=(_PROJECT_ID,),
    example_arguments={"project_id": _EXAMPLE_PID},
    example_result=(
        f'{{"id": "{_EXAMPLE_PID}", "path": "/home/me/.local/share/ithax/projects/{_EXAMPLE_PID}"}}'
    ),
    calls=_remove_project,
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
        '{"model": {"format_version": "'
        + FORMAT_VERSION
        + '", "meta": {"name": "Coffee shop"}, "domain": '
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


def _create_model(client: ServiceClient, arguments: Mapping[str, Any]) -> Answer:
    body: dict[str, Any] = {"name": arguments["name"]}
    if "template_id" in arguments:
        body["template"] = arguments["template_id"]
    if "domain" in arguments:
        body["domain"] = arguments["domain"]
    return client.request("POST", "/v1/projects", body)


def _edit_model(client: ServiceClient, arguments: Mapping[str, Any]) -> Answer:
    body: dict[str, Any] = {"edits": arguments["edits"]}
    if "base_revision" in arguments:
        body["base_revision"] = arguments["base_revision"]
    path = f"/v1/projects/{_segment(arguments['project_id'])}/model/edits"
    return client.request("POST", path, body)


def _run_model(client: ServiceClient, arguments: Mapping[str, Any]) -> Answer:
    body: dict[str, Any] = {}
    if "experiment_id" in arguments:
        body["experiment_id"] = arguments["experiment_id"]
    return client.started_runs.start(client, arguments["project_id"], body)


def _get_run_status(client: ServiceClient, arguments: Mapping[str, Any]) -> Answer:
    return client.request("GET", f"/v1/runs/{_segment(arguments['run_id'])}")


#: The most variables and constraints ``get_results`` gives of an optimization (#82, owner
#: option A on #181): the one exception to "a tool's result is the response body".
SHOWN = 50


def _first(items: object) -> object:
    """The first ``SHOWN`` of a mapping or list; anything else unchanged."""
    if isinstance(items, dict):
        return dict(list(items.items())[:SHOWN])
    if isinstance(items, list):
        return items[:SHOWN]
    return items


def _counts(items: object) -> dict[str, int] | None:
    """``{shown, total}`` of a mapping or list longer than ``SHOWN``; otherwise ``None``."""
    if isinstance(items, dict | list) and len(items) > SHOWN:
        return {"shown": SHOWN, "total": len(items)}
    return None


def _cut_summary(summary: dict[str, Any], run: str) -> dict[str, Any]:
    """An optimization summary with at most ``SHOWN`` variables and constraints (and duals),
    and ``cut_short`` saying how many there are and where the rest are."""
    counts = {key: _counts(summary.get(key)) for key in ("variables", "constraints")}
    if not any(counts.values()):
        return summary
    cut = {
        key: _first(value) if key in ("variables", "constraints", "duals") else value
        for key, value in summary.items()
    }
    shown = {key: count for key, count in counts.items() if count}
    parts = [f"the first {SHOWN} of {count['total']} {key}" for key, count in shown.items()]
    cut["cut_short"] = {
        **shown,
        "note": f"This answer holds {' and '.join(parts)}, in the model's order. "
        f"GET {run}/summary and the project's export hold every value.",
    }
    return cut


def _cut_finding(finding: object) -> object:
    """An ``optimization_result`` finding whose evidence holds at most ``SHOWN`` variables and
    tight constraints, and ``cut_short`` with how many there are."""
    if not isinstance(finding, dict) or finding.get("rule") != "optimization_result":
        return finding
    evidence = finding.get("evidence")
    if not isinstance(evidence, dict):
        return finding
    counts = {key: _counts(evidence.get(key)) for key in ("variables", "tight")}
    if not any(counts.values()):
        return finding
    cut = {key: _first(value) if key in counts else value for key, value in evidence.items()}
    cut["cut_short"] = {key: count for key, count in counts.items() if count}
    return {**finding, "evidence": cut}


def _cut_short(body: dict[str, Any], run: str) -> dict[str, Any]:
    """The summary's answer, a large optimization's cut to ``SHOWN`` of each (#82)."""
    summary, findings = body.get("summary"), body.get("findings")
    cut = dict(body)
    if isinstance(summary, dict):
        cut["summary"] = _cut_summary(summary, run)
    if isinstance(findings, list):
        cut["findings"] = [_cut_finding(finding) for finding in findings]
    return cut


def _get_results(client: ServiceClient, arguments: Mapping[str, Any]) -> Answer:
    """The summary's answer with ``tables`` added, one request per table named (each
    once, in the order first named); the first refusal unchanged. A large optimization's
    is cut short (``_cut_short``)."""
    run = f"/v1/runs/{_segment(arguments['run_id'])}"
    summary = client.request("GET", f"{run}/summary")
    if summary.status >= _ERROR_STATUS or not isinstance(summary.body, dict):
        return summary
    tables: dict[str, object] = {}
    for name in dict.fromkeys(arguments.get("tables", ())):
        answer = client.request("GET", f"{run}/tables/{_segment(name)}?format=json")
        if answer.status >= _ERROR_STATUS:
            return answer
        tables[name] = answer.body
    return Answer(status=summary.status, body={**_cut_short(summary.body, run), "tables": tables})


_RUN_ID = Input(
    "run_id",
    "text",
    "The run's id, the 'run_id' run_model returned.",
    required=True,
)
_EXAMPLE_RID = "20261108T093012-K7QM2X"

CREATE_MODEL = ToolSpec(
    name="create_model",
    summary=(
        "Start a new project and its model (POST /v1/projects), from nothing or from a "
        "template (template_id, an id list_templates gives). Returns the new project as "
        "list_projects lists it; its id is the project_id the other tools take. With a "
        "template the model is a copy of the template's, named after the project, with its "
        "components, parameters and experiments; leave domain out, since the template sets "
        "it (a different domain is refused, E184). Without a "
        "template the model is empty: no components and one experiment, base (length 8 h, "
        "warmup 0 s, 30 replications); an experiment's length includes the warmup, so "
        "results are measured over length minus warmup. domain is 'process' (the default, "
        "simulation) or "
        "'optimization', which starts a mathematical model with no variables or "
        "constraints instead (it does not run until it has a variable: E179); a model's "
        "domain cannot be changed by edits. Then read the "
        "model with get_model and build it with edit_model; the user sees it on the canvas."
    ),
    inputs=(
        Input("name", "text", "The project's name, shown to the user.", required=True),
        Input(
            "template_id",
            "text",
            "The id of a template to start from (list_templates); leave out to start empty.",
        ),
        Input(
            "domain",
            "text",
            "'process' (the default) or 'optimization'; leave out for a process model.",
        ),
    ),
    example_arguments={"name": "Coffee shop"},
    example_result=(
        f'{{"id": "{_EXAMPLE_PID}", "name": "Coffee shop", "created": '
        '"2026-11-08T09:30:00.000Z", "layout_version": 1, "model_revision": 0, "path": '
        f'"/home/me/.local/share/ithax/projects/{_EXAMPLE_PID}", "available": true, '
        '"opened": null, "template": "coffee_shop", "lesson_step": null}'
    ),
    calls=_create_model,
)

#: The worked example of edit_model: two servers sharing a pool of staff, on a daily rota
#: whose night shift is split at the period end (``docs/research/spec-2-prior-art.md``).
#: Their load, 20/75 + 25/75 = 0.6, is below the rota's mean of 1 over a day and of 0.75
#: over a new project's 8 h run, so it loads with no W201 (#73).
_EXAMPLE_EDITS: list[dict[str, Any]] = [
    {
        "edit": "add_component",
        "id": "arrivals",
        "type": "source",
        "params": {"interarrival": {"dist": "exponential", "mean": "75 min"}},
    },
    {"edit": "add_component", "id": "staff", "type": "resource_pool", "params": {"capacity": 2}},
    {
        "edit": "add_component",
        "id": "cutting",
        "type": "server",
        "params": {
            "capacity": 1,
            "service": {"dist": "exponential", "mean": "20 min"},
            "pool": "staff",
        },
    },
    {
        "edit": "add_component",
        "id": "sewing",
        "type": "server",
        "params": {
            "capacity": 1,
            "service": {"dist": "exponential", "mean": "25 min"},
            "pool": "staff",
        },
    },
    {
        "edit": "add_component",
        "id": "rota",
        "type": "schedule",
        "params": {
            "target": "staff",
            "period": "24 h",
            "shifts": [
                {"start": "8 h", "end": "16 h", "capacity": 2},
                {"start": "22 h", "end": "24 h", "capacity": 1},
                {"start": "0 h", "end": "6 h", "capacity": 1},
            ],
        },
    },
    {"edit": "add_component", "id": "exit", "type": "sink", "params": {}},
    {"edit": "connect", "from": "arrivals.out", "to": "cutting.in"},
    {"edit": "connect", "from": "cutting.out", "to": "sewing.in"},
    {"edit": "connect", "from": "sewing.out", "to": "exit.in"},
]

EDIT_MODEL = ToolSpec(
    name="edit_model",
    summary=(
        "Change a project's model by a batch of edits, applied in order and saved together "
        "(POST /v1/projects/{project_id}/model/edits). Each edit is an object whose 'edit' "
        "names its kind: add_component {id, type, params, ui?}; remove_component {id}; "
        "rename_component {id, new_id}; set_setting {id, path, value}, path a JSON Pointer "
        "into the component's params such as /service/mean; connect {from, to} and "
        "disconnect {from}, naming ports such as 'arrivals.out' and 'till.in'; "
        "set_parameter {id, value?, type?, min?, max?} and remove_parameter {id}, a "
        'setting using a parameter as {"$param": "<id>"}; '
        "set_experiment {id, and any experiment fields such as length, warmup, "
        "replications, seed, search}, where length includes the warmup (results cover "
        "length minus warmup: 200 h measured after a 10 h warm-up is length 210 h and "
        "warmup 10 h), and remove_experiment {id}; set_scenario "
        "{experiment_id, id, set} and remove_scenario {experiment_id, id}; set_path {path, "
        "value} and remove_path {path}, a JSON Pointer on the whole model for /meta, /run, "
        "/objectives, /constraints, /experiments/<n>/search and, in an optimization model, "
        "/variables, /objective, /sets and /tables, a list entry named by its index from 0 "
        "(set_path with '-' adds one at the end, remove_path closes the gap); set_ui {id, "
        "ui}; set_label {id, label}. "
        "get_schema gives each block type's settings. A batch that applies is saved and "
        "returns "
        "{model, revision, issues}: the issues are the checks made on loading the model, "
        "errors to fix before a run and warnings to read; with an error the result is "
        "marked as an error, though the batch is still saved. validate_model adds the "
        "engine's own check. An edit that cannot be applied (an unknown or duplicate "
        "component id, an unknown type, parameter or experiment, a path whose parent does "
        "not exist) is refused with E180 at /edits/<n> and nothing is saved. Send "
        "base_revision, the revision get_model or the last edit_model returned: if the user "
        "changed the model meanwhile nothing is applied, and the refusal, E181, carries the "
        "current model and revision. Keep batches small. Randomness is set by an "
        "experiment's seed (set_experiment), never per component; each component draws "
        "from its own stream. The example: two servers sharing a pool of two staff on a "
        "daily rota; the night shift is split at the period end (22 h to 24 h, 0 h to 6 h), "
        "since no shift crosses it."
    ),
    inputs=(
        _PROJECT_ID,
        Input(
            "edits",
            "edits",
            "The edits, applied in order; each an object whose 'edit' names its kind.",
            required=True,
        ),
        Input(
            "base_revision",
            "whole number",
            "The model's revision these edits were written against (from get_model or the "
            "last edit_model); leave out to apply them to whatever is saved.",
        ),
    ),
    example_arguments={"project_id": _EXAMPLE_PID, "edits": _EXAMPLE_EDITS, "base_revision": 0},
    example_result=(
        '{"model": {"format_version": "'
        + FORMAT_VERSION
        + '", "meta": {"name": "Workshop"}, "domain": '
        '"process", "parameters": {}, "components": [{"id": "arrivals", "type": "source", '
        '...}, {"id": "staff", "type": "resource_pool", "params": {"capacity": 2}}, ...], '
        '"connections": [{"from": "arrivals.out", "to": "cutting.in"}, ...], "experiments": '
        '[{"id": "base", "length": "8 h", "warmup": "0 s", "replications": 30}], "run": '
        '{"target": "local", "fidelity": "standard"}}, "revision": 1, "issues": []}'
    ),
    calls=_edit_model,
    is_error=refused_or_saved_with_errors,
)

RUN_MODEL = ToolSpec(
    name="run_model",
    summary=(
        "Start a run of a project's saved model (POST /v1/projects/{project_id}/runs). It "
        "returns at once with {run_id}; the run waits its turn in the service's queue. For "
        "a process model name the experiment to run (experiment_id, such as 'base'); an "
        "optimization model has no experiments, so leave experiment_id out. An experiment "
        "with a search (simulation-based optimization) runs the same way. The model is "
        "checked first: a model with errors is refused with status 422 and its issues, and "
        "nothing runs (validate_model shows them beforehand). Then poll get_run_status "
        "until the state is done, failed or cancelled, and read get_results. Every run is "
        "bounded by the service's time and memory limits (10 minutes and half the memory "
        "by default); a run beyond them fails with E192. At most two runs of a project "
        "started through this server may be unfinished (queued or running) at once; a "
        "third is refused with E194, which lists their run_ids. For results that repeat "
        "exactly, set the experiment's seed with edit_model first."
    ),
    inputs=(
        _PROJECT_ID,
        Input(
            "experiment_id",
            "text",
            "The id of the experiment to run: required for a process model, left out for an "
            "optimization model.",
        ),
    ),
    example_arguments={"project_id": _EXAMPLE_PID, "experiment_id": "base"},
    example_result=f'{{"run_id": "{_EXAMPLE_RID}"}}',
    calls=_run_model,
)

GET_RUN_STATUS = ToolSpec(
    name="get_run_status",
    summary=(
        "Read a run's state and progress (GET /v1/runs/{run_id}). Returns {run_id, "
        "project_id, experiment_id, engine, state, fraction, message, created, started, "
        "ended, error}: engine is {name, version} of the engine that ran; state is "
        "queued, running, done, failed or cancelled; fraction goes from 0 to 1; error is "
        "null unless the run failed, and then an issue with its code (E190 "
        "the engine failed, E191 the service restarted, E192 the run exceeded its time or "
        "memory limit, E196 items circle blocks that take no time). Poll every few "
        "seconds until the state is done, failed or "
        "cancelled; results exist only for done."
    ),
    inputs=(_RUN_ID,),
    example_arguments={"run_id": _EXAMPLE_RID},
    example_result=(
        f'{{"run_id": "{_EXAMPLE_RID}", "project_id": "{_EXAMPLE_PID}", "experiment_id": '
        '"base", "engine": {"name": "simpy", "version": "4.1.2"}, "state": "running", '
        '"fraction": 0.4, "message": "", "created": '
        '"2026-11-08T09:30:12.418Z", "started": "2026-11-08T09:30:12.420Z", "ended": null, '
        '"error": null}'
    ),
    calls=_get_run_status,
)

GET_RESULTS = ToolSpec(
    name="get_results",
    summary=(
        "Read a finished run's results (GET /v1/runs/{run_id}/summary, plus GET "
        "/v1/runs/{run_id}/tables/{name}?format=json for each name in tables). Returns "
        "{summary, findings, issues, tables}. In summary, scenarios.<scenario>.metrics maps "
        "each metric, such as 'weld.wait.mean' or 'weld.utilization', to {mean, half_width, "
        "unit, n}, in SI units (times in seconds, rates per second): mean plus or minus "
        "half_width is the confidence interval at summary.confidence over n replications, "
        "half_width being t times the standard deviation over the square root of n, with t "
        "the Student t quantile at (1 + confidence) / 2 for n - 1 degrees of freedom. A "
        "plain run has the one scenario 'default'. A search run adds summary.search (status, "
        "the best values in best.set, the objective before and after, and separated: true "
        "when the best is told apart from the next best setting at the confidence, its "
        "paired difference excluding zero), and its metrics are the best candidate's. An "
        "optimization run's summary holds status, objective, variables and constraints "
        "instead, and it has no tables; when it has more than 50 variables or 50 "
        "constraints, this answer holds the first 50 of each, in the model's order (and of "
        "the optimization_result finding's evidence), and summary.cut_short gives the "
        "totals: GET /v1/runs/{run_id}/summary holds every value. findings are short "
        "statements in plain language made from the summary by fixed rules, so the same run "
        "always gives the same findings; read them first and pass them on. Each is {rule, "
        "severity, component, scenario, text, evidence}: rule is bottleneck (the busiest "
        "server, when busy at least 85% of the time), unstable (a server that cannot keep "
        "up), idle_capacity (a server busy under 30% of the time), not_enough_runs (an "
        "interval wider than 10% of its mean: the result is not yet reliable, and the text "
        "says about how many replications would be needed) or optimization_result (the best "
        "values found); severity is info or warning; component and scenario are null when "
        "the finding is not about one; text is in display units, ready to show the user; "
        "evidence holds the summary values it rests on, in SI units. An empty findings list "
        "means no rule fired. 85%, 30% and 10% are default thresholds, which the user can "
        "change in the service's settings; issues lists a W220 warning for each one that "
        "could not be used (its default was used instead), and is usually empty. tables "
        "is optional and long: 'replications' gives one row per scenario, replication and "
        "metric, 'timeseries' the sampled values over time; ask for one only when the "
        "summary is not enough. A run that is "
        "not done is refused with E188, an unknown table with E185."
    ),
    inputs=(
        _RUN_ID,
        Input(
            "tables",
            "texts",
            "Table names to include: 'replications' and/or 'timeseries'; leave out for none.",
        ),
    ),
    example_arguments={"run_id": _EXAMPLE_RID},
    example_result=(
        '{"summary": {"model": "Three-machine line", "experiment": "base", "fidelity": '
        '"standard", "fidelity_label": "Standard: 30 replications of 100 h, 95% confidence", '
        '"replications": 30, "confidence": 0.95, "scenarios": {"default": {"set": {}, '
        '"metrics": {"weld.wait.mean": {"mean": 941.5, "half_width": 125.5, "unit": "s", '
        '"n": 30}, "weld.utilization": {"mean": 0.901, "half_width": 0.011, "unit": "1", '
        '"n": 30}, ...}}}, "differences": [], "warnings": []}, "findings": [{"rule": '
        '"bottleneck", "severity": "info", "component": "weld", "scenario": "default", '
        '"text": "weld is the bottleneck: busy 90% of the time, with an average wait of 15.7 '
        'min.", "evidence": {"weld.utilization": 0.901, "weld.wait.mean": 941.5}}, {"rule": '
        '"not_enough_runs", "severity": "warning", "component": null, "scenario": "default", '
        '"text": "The estimates for weld.wait.mean are still uncertain: weld.wait.mean is '
        "15.7 min plus or minus 2.09 min. About 60 replications would be needed for a 10% "
        'interval.", "evidence": {"weld.wait.mean": {"mean": 941.5, "half_width": 125.5, '
        '"unit": "s", "n": 30}, "n_required": 60}}], "issues": [], "tables": {}}'
    ),
    calls=_get_results,
)

#: The tools, in the order ``tools/list`` gives them (spec 4 "MCP tools").
TOOLS: tuple[ToolSpec, ...] = (
    LIST_TEMPLATES,
    GET_SCHEMA,
    LIST_PROJECTS,
    CREATE_MODEL,
    RENAME_PROJECT,
    REMOVE_PROJECT,
    GET_MODEL,
    EDIT_MODEL,
    VALIDATE_MODEL,
    RUN_MODEL,
    GET_RUN_STATUS,
    GET_RESULTS,
    LIST_ENGINES,
)

_BY_NAME = {spec.name: spec for spec in TOOLS}


def tool_named(name: str) -> ToolSpec:
    """The tool called ``name``; ``KeyError`` when there is none."""
    return _BY_NAME[name]
