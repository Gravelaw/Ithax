"""The five write and run tools (spec 4 "MCP tools", "How the server runs and answers" and
"Limits"; AKS-134).

Driven through the MCP SDK's in-memory client, as an assistant would call them, against the
real M6 application served in process, or against a stub where the test needs to see the
requests themselves. Each tool sends the request spec 4 names and returns its answer; every
refusal the service gives (E180, E181 with the current model and revision, E184, E185,
E186, E188, a 422 with its issues) and the MCP server's own run limit (E194) are results
marked ``isError``, never protocol errors. Runs are kept short (a few replications of a few
hours); the runs that must stay unfinished are long and are cancelled at the end.
"""

import json
import math
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import anyio
import httpx2
import jsonschema
import pytest
from mcp import Client
from mcp_support import (
    NO_START,
    ROOT,
    Recorded,
    StubService,
    in_process_service,
    payload,
    run,
    spec_4_tool_rows,
)

from ithax.mcp.client import ServiceClient
from ithax.mcp.limits import MAX_UNFINISHED_RUNS, RUN_LIMIT
from ithax.mcp.tools import MAX_DEPTH, TOOLS, check_arguments, run_tool, tool_named
from ithax.model.edits import EDIT_KINDS
from ithax.service.discovery import ServiceInfo

FINAL = ("done", "failed", "cancelled")

#: The coffee shop of spec 1, built by edits; the experiment is short so the tests are fast.
COFFEE_SHOP_EDITS: list[dict[str, Any]] = [
    {
        "edit": "add_component",
        "id": "arrivals",
        "type": "source",
        "params": {"interarrival": {"dist": "exponential", "mean": "2 min"}},
    },
    {
        "edit": "add_component",
        "id": "till",
        "type": "server",
        "params": {"capacity": 1, "service": {"dist": "exponential", "mean": "1.5 min"}},
    },
    {"edit": "add_component", "id": "exit", "type": "sink", "params": {}},
    {"edit": "connect", "from": "arrivals.out", "to": "till.in"},
    {"edit": "connect", "from": "till.out", "to": "exit.in"},
    {
        "edit": "set_experiment",
        "id": "base",
        "length": "20 h",
        "warmup": "1 h",
        "replications": 3,
        "seed": 12345,
    },
]

#: An experiment that keeps a run unfinished for far longer than any test waits.
LONG = {"edit": "set_experiment", "id": "long", "length": "100000 h", "replications": 30}


@pytest.fixture
def folders(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "config", tmp_path / "data"


@pytest.fixture
def service(folders: tuple[Path, Path]) -> Iterator[ServiceInfo]:
    with in_process_service(*folders) as info:
        yield info


@pytest.fixture
def client(folders: tuple[Path, Path], service: ServiceInfo) -> ServiceClient:
    return ServiceClient(*folders, command=NO_START)


@pytest.fixture
def http(service: ServiceInfo) -> Iterator[httpx2.Client]:
    with httpx2.Client(
        base_url=f"http://127.0.0.1:{service.port}",
        headers={"Authorization": f"Bearer {service.token}"},
        trust_env=False,
        timeout=30,
    ) as http_client:
        yield http_client


@pytest.fixture
def stub(folders: tuple[Path, Path]) -> Iterator[StubService]:
    service = StubService(folders[0])
    service.start()
    try:
        yield service
    finally:
        service.stop()


async def call(mcp_client: Client, name: str, arguments: dict[str, Any]) -> tuple[bool, Any]:
    """Whether the result is marked ``isError``, and its JSON."""
    result = await mcp_client.call_tool(name, arguments)
    return bool(result.is_error), payload(result)


async def new_coffee_shop(mcp_client: Client) -> str:
    """A project holding the short coffee shop, made through the tools."""
    error, project = await call(mcp_client, "create_model", {"name": "Coffee shop"})
    assert not error, project
    pid = str(project["id"])
    error, edited = await call(
        mcp_client,
        "edit_model",
        {"project_id": pid, "edits": COFFEE_SHOP_EDITS, "base_revision": 0},
    )
    assert not error and edited["issues"] == [], edited
    return pid


async def finished(mcp_client: Client, run_id: str) -> dict[str, Any]:
    """The run once ``get_run_status`` shows a final state."""
    deadline = time.monotonic() + 120
    while True:
        error, status = await call(mcp_client, "get_run_status", {"run_id": run_id})
        assert not error, status
        if status["state"] in FINAL:
            return dict(status)
        assert time.monotonic() < deadline, status
        await anyio.sleep(0.1)


def cancel_all(http: httpx2.Client, pid: str) -> None:
    """Cancel every unfinished run of ``pid``, so the service stops quickly."""
    for item in http.get(f"/v1/projects/{pid}/runs").json():
        if item["state"] not in FINAL:
            http.post(f"/v1/runs/{item['run_id']}/cancel")


def example_json(name: str) -> Any:
    """The worked example result of ``name``, which these tools give as complete JSON."""
    return json.loads(tool_named(name).example_result)


# --- each tool sends the request spec 4 names ---------------------------------------------


def respond_to(recorded: Recorded) -> tuple[int, bytes, dict[str, str]]:
    """A stand-in answer of the right status and shape for each write or run request."""
    if recorded.method == "POST" and recorded.path.endswith("/runs"):
        return 202, b'{"run_id": "20261108T093012-K7QM2X"}', {}
    if "/tables/" in recorded.path:
        return 200, b"[]", {}
    if recorded.path.endswith("/summary"):
        return 200, b'{"summary": {}, "findings": []}', {}
    if recorded.method == "GET" and recorded.path.startswith("/v1/runs/"):
        return 200, b'{"state": "done"}', {}
    return 200, b"{}", {}


SENT: list[tuple[str, dict[str, Any], list[tuple[str, str, Any]]]] = [
    (
        "create_model",
        {"name": "Coffee shop"},
        [("POST", "/v1/projects", {"name": "Coffee shop"})],
    ),
    (
        "create_model",
        {"name": "Plan", "template_id": "product_mix", "domain": "optimization"},
        [
            (
                "POST",
                "/v1/projects",
                {"name": "Plan", "template": "product_mix", "domain": "optimization"},
            )
        ],
    ),
    (
        "edit_model",
        {"project_id": "p/../x y", "edits": [{"edit": "disconnect", "from": "a.out"}]},
        [
            (
                "POST",
                "/v1/projects/p%2F..%2Fx%20y/model/edits",
                {"edits": [{"edit": "disconnect", "from": "a.out"}]},
            )
        ],
    ),
    (
        "edit_model",
        {"project_id": "p", "edits": [], "base_revision": 3},
        [("POST", "/v1/projects/p/model/edits", {"edits": [], "base_revision": 3})],
    ),
    ("run_model", {"project_id": "p"}, [("POST", "/v1/projects/p/runs", {})]),
    (
        "run_model",
        {"project_id": "q", "experiment_id": "base"},
        [("POST", "/v1/projects/q/runs", {"experiment_id": "base"})],
    ),
    ("get_run_status", {"run_id": "r 1/.."}, [("GET", "/v1/runs/r%201%2F..", None)]),
    ("get_results", {"run_id": "r"}, [("GET", "/v1/runs/r/summary", None)]),
    (
        "get_results",
        {"run_id": "r", "tables": ["timeseries", "replications", "timeseries", "a?b"]},
        [
            ("GET", "/v1/runs/r/summary", None),
            ("GET", "/v1/runs/r/tables/timeseries?format=json", None),
            ("GET", "/v1/runs/r/tables/replications?format=json", None),
            ("GET", "/v1/runs/r/tables/a%3Fb?format=json", None),
        ],
    ),
]


@pytest.mark.parametrize(("name", "arguments", "expected"), SENT)
def test_each_write_and_run_tool_sends_the_request_spec_4_names(
    name: str,
    arguments: dict[str, Any],
    expected: list[tuple[str, str, Any]],
    folders: tuple[Path, Path],
    stub: StubService,
) -> None:
    stub.respond = respond_to
    client = ServiceClient(*folders, command=NO_START)

    async def check(mcp_client: Client) -> None:
        result = await mcp_client.call_tool(name, arguments)
        assert not result.is_error, payload(result)
        sent = [(r.method, r.path, json.loads(r.body) if r.body else None) for r in stub.requests]
        assert sent == expected
        for recorded in stub.requests:
            assert recorded.headers["X-Client"] == "mcp"
            if recorded.body:
                assert recorded.headers["Content-Type"] == "application/json"
        # The endpoints spec 4's table names for the tool, and no others.
        _, calls = spec_4_tool_rows()[name]
        assert {method for method, _, _ in expected} == {method for method, _ in calls}
        templates = {path.split("{")[0] for _, path in calls}
        assert all(any(path.startswith(t) for t in templates) for _, path, _ in expected)

    run(check, client)


def test_get_results_composes_the_summary_and_the_tables(
    folders: tuple[Path, Path], stub: StubService
) -> None:
    finding = {"rule": "bottleneck", "text": "till is the bottleneck."}
    issue = {"code": "W220", "path": "/finding_thresholds/x"}
    stub.answer(200, {"summary": {"replications": 2}, "findings": [finding], "issues": [issue]})
    stub.answer(200, [{"metric": "till.wait.mean", "value": 1.0}])
    client = ServiceClient(*folders, command=NO_START)

    async def check(mcp_client: Client) -> None:
        error, body = await call(mcp_client, "get_results", {"run_id": "r", "tables": ["x"]})
        assert not error
        assert body == {
            "summary": {"replications": 2},
            "findings": [finding],
            "issues": [issue],
            "tables": {"x": [{"metric": "till.wait.mean", "value": 1.0}]},
        }

    run(check, client)


def test_get_results_returns_the_first_refusal_unchanged(
    folders: tuple[Path, Path], stub: StubService
) -> None:
    client = ServiceClient(*folders, command=NO_START)
    refusal = {"error": {"code": "E185", "message": "There is no table 'b'."}, "issues": []}

    async def check(mcp_client: Client) -> None:
        # The summary refused: no table is asked for.
        stub.answer(409, {"error": {"code": "E188", "message": "Not done."}, "issues": []})
        error, body = await call(mcp_client, "get_results", {"run_id": "r", "tables": ["a"]})
        assert error and body["error"]["code"] == "E188"
        assert [r.path for r in stub.requests] == ["/v1/runs/r/summary"]
        # A table refused: its answer, and the tables after it are not asked for.
        stub.requests.clear()
        stub.answer(200, {"summary": {}, "findings": []})
        stub.answer(200, [])
        stub.answer(404, refusal)
        error, body = await call(
            mcp_client, "get_results", {"run_id": "r", "tables": ["a", "b", "c"]}
        )
        assert error and body == refusal
        assert len(stub.requests) == 3

    run(check, client)


def test_get_results_passes_on_a_summary_that_is_not_an_object(
    folders: tuple[Path, Path], stub: StubService
) -> None:
    # The service always answers an object; anything else is passed on as it came.
    client = ServiceClient(*folders, command=NO_START)
    stub.answer(200, ["unexpected"])

    async def check(mcp_client: Client) -> None:
        error, body = await call(mcp_client, "get_results", {"run_id": "r", "tables": ["a"]})
        assert not error and body == ["unexpected"]
        assert len(stub.requests) == 1

    run(check, client)


# --- inputs ------------------------------------------------------------------------------


def deep(levels: int) -> list[Any]:
    value: list[Any] = []
    for _ in range(levels - 1):
        value = [value]
    return value


INPUT_PROBLEMS: list[tuple[str, dict[str, Any], list[str]]] = [
    ("create_model", {}, ["/name"]),
    ("create_model", {"name": "x", "path": "/tmp/x"}, ["/path"]),
    ("create_model", {"name": "x", "domain": 1}, ["/domain"]),
    ("create_model", {"name": "x", "template_id": None}, ["/template_id"]),
    ("edit_model", {"project_id": "p"}, ["/edits"]),
    ("edit_model", {"project_id": "p", "edits": {"edit": "x"}}, ["/edits"]),
    ("edit_model", {"project_id": "p", "edits": [{"value": math.nan}]}, ["/edits"]),
    ("edit_model", {"project_id": "p", "edits": [{"value": [math.inf]}]}, ["/edits"]),
    ("edit_model", {"project_id": "p", "edits": [{"v": {"w": -math.inf}}]}, ["/edits"]),
    ("edit_model", {"project_id": "p", "edits": deep(MAX_DEPTH + 1)}, ["/edits"]),
    ("edit_model", {"project_id": "p", "edits": [], "base_revision": True}, ["/base_revision"]),
    ("edit_model", {"project_id": "p", "edits": [], "base_revision": 3.0}, ["/base_revision"]),
    ("edit_model", {"project_id": "p", "edits": [], "base_revision": "3"}, ["/base_revision"]),
    ("run_model", {"experiment_id": "base"}, ["/project_id"]),
    ("run_model", {"project_id": "p", "experiment_id": 1}, ["/experiment_id"]),
    ("run_model", {"project_id": "p", "target": "local"}, ["/target"]),
    ("get_run_status", {"run_id": 7}, ["/run_id"]),
    ("get_results", {"run_id": "r", "tables": "replications"}, ["/tables"]),
    ("get_results", {"run_id": "r", "tables": [1]}, ["/tables"]),
    ("get_results", {"run_id": "r", "tables": ["\ud800"]}, ["/tables"]),
    ("get_results", {"tables": []}, ["/run_id"]),
]


def test_input_problems_of_the_write_and_run_tools_are_e184_and_nothing_is_sent(
    folders: tuple[Path, Path], stub: StubService
) -> None:
    client = ServiceClient(*folders, command=NO_START)
    for name, arguments, paths in INPUT_PROBLEMS:
        # run_tool directly: a JSON client cannot send NaN or an infinity at all.
        result = run_tool(tool_named(name), client, arguments)
        assert result.is_error, (name, arguments)
        body = payload(result)
        assert body["error"]["code"] == "E184", (name, arguments)
        assert [issue["path"] for issue in body["issues"]] == paths, (name, arguments)
        assert all(issue["hint"] for issue in body["issues"])
        # The result itself can be sent as JSON.
        result.model_dump_json()
    assert stub.requests == [] and stub.probes == 0


def test_the_kinds_accept_what_the_service_takes() -> None:
    edit_model = tool_named("edit_model")
    nested = deep(MAX_DEPTH)
    for arguments in (
        {"project_id": "p", "edits": [], "base_revision": 0},
        {"project_id": "p", "edits": [{"value": 1e308, "n": -(2**70), "x": None, "b": False}]},
        {"project_id": "p", "edits": nested},
        {"project_id": "p", "edits": [{"label": "café", "big": 10**400}]},
    ):
        assert check_arguments(edit_model, arguments) == [], arguments
    assert check_arguments(tool_named("get_results"), {"run_id": "r", "tables": []}) == []
    [problem] = check_arguments(edit_model, {"project_id": "p", "edits": [math.nan]})
    assert problem.message == (
        "The input 'edits' of edit_model must be an array of edits whose numbers are finite, "
        f"nested at most {MAX_DEPTH} levels deep."
    )


def test_text_in_an_edit_that_is_not_valid_unicode_is_the_services_e184(
    client: ServiceClient, http: httpx2.Client
) -> None:
    # The client sends it escaped; the service refuses it at its field (spec 3).
    pid = http.post("/v1/projects", json={"name": "x"}).json()["id"]

    async def check(mcp_client: Client) -> None:
        error, body = await call(
            mcp_client,
            "edit_model",
            {
                "project_id": pid,
                "edits": [{"edit": "add_component", "id": "\ud800", "type": "sink", "params": {}}],
            },
        )
        assert error and body["error"]["code"] == "E184"
        assert body["issues"][0]["path"] == "/edits/0/id"

    run(check, client)


# --- create_model -------------------------------------------------------------------------


def test_create_model_makes_a_project_the_other_tools_find(
    client: ServiceClient, http: httpx2.Client
) -> None:
    async def check(mcp_client: Client) -> None:
        error, project = await call(mcp_client, "create_model", {"name": "Coffee shop"})
        assert not error
        assert set(project) == set(example_json("create_model"))
        assert project["name"] == "Coffee shop" and project["model_revision"] == 0
        # Under the user data folder: create_model takes no path.
        assert Path(project["path"]).parent == client.data_dir / "projects"
        assert http.get("/v1/projects").json() == [project]
        error, model = await call(mcp_client, "get_model", {"project_id": project["id"]})
        assert not error and model["revision"] == 0
        assert model["model"]["domain"] == "process"
        assert model["model"]["experiments"] == [
            {"id": "base", "length": "8 h", "warmup": "0 s", "replications": 30}
        ]

    run(check, client)


def test_create_model_of_an_optimization_model(client: ServiceClient) -> None:
    async def check(mcp_client: Client) -> None:
        error, project = await call(
            mcp_client, "create_model", {"name": "Plan", "domain": "optimization"}
        )
        assert not error
        error, model = await call(mcp_client, "get_model", {"project_id": project["id"]})
        assert not error and model["model"]["domain"] == "optimization"
        assert "experiments" not in model["model"]

    run(check, client)


def test_create_model_from_a_template_copies_its_model(client: ServiceClient) -> None:
    """AKS-122: a template_id starts the project from that template's model, named after
    the project; validate_model finds nothing to report."""

    async def check(mcp_client: Client) -> None:
        error, project = await call(
            mcp_client, "create_model", {"name": "My line", "template_id": "three_machine_line"}
        )
        assert not error
        error, model = await call(mcp_client, "get_model", {"project_id": project["id"]})
        assert not error
        assert model["model"]["meta"]["name"] == "My line"
        assert model["model"]["meta"]["template"] == "three_machine_line"
        assert "buffer" in [item["id"] for item in model["model"]["components"]]
        error, checked = await call(mcp_client, "validate_model", {"project_id": project["id"]})
        assert not error and checked["issues"] == []

    run(check, client)


def test_create_model_refusals_are_data(client: ServiceClient, http: httpx2.Client) -> None:
    async def check(mcp_client: Client) -> None:
        error, body = await call(
            mcp_client, "create_model", {"name": "x", "template_id": "no_such_template"}
        )
        assert error and body["error"]["code"] == "E185" and "no_such_template" in str(body)
        error, body = await call(
            mcp_client,
            "create_model",
            {"name": "x", "template_id": "coffee_shop", "domain": "optimization"},
        )
        assert error and body["error"]["code"] == "E184"
        assert [issue["path"] for issue in body["issues"]] == ["/domain"]
        error, body = await call(mcp_client, "create_model", {"name": ""})
        assert error and body["error"]["code"] == "E184"
        assert [issue["path"] for issue in body["issues"]] == ["/name"]
        error, body = await call(mcp_client, "create_model", {"name": "x", "domain": "fluids"})
        assert error and body["error"]["code"] == "E184"
        assert [issue["path"] for issue in body["issues"]] == ["/domain"]
        # Nothing was created by a refusal.
        assert http.get("/v1/projects").json() == []

    run(check, client)


# --- edit_model ---------------------------------------------------------------------------


def test_edit_model_returns_the_model_its_revision_and_its_issues(
    client: ServiceClient, http: httpx2.Client
) -> None:
    async def check(mcp_client: Client) -> None:
        pid = await new_coffee_shop(mcp_client)
        expected = http.get(f"/v1/projects/{pid}/model").json()
        assert expected["revision"] == 1
        # An edit that applies but leaves an error is saved and returns the issue; the
        # result is marked isError, since the model cannot run as saved (#98).
        error, body = await call(
            mcp_client,
            "edit_model",
            {
                "project_id": pid,
                "edits": [{"edit": "set_setting", "id": "till", "path": "/capacity", "value": 0}],
            },
        )
        assert error
        assert body["revision"] == 2 and body["model"]["components"][1]["params"]["capacity"] == 0
        assert [(issue["code"], issue["path"]) for issue in body["issues"]] == [
            ("E123", "/components/1/params/capacity")
        ]
        assert body == {**http.get(f"/v1/projects/{pid}/model").json(), "issues": body["issues"]}

    run(check, client)


def test_the_edit_model_example_applies_with_no_issues(
    client: ServiceClient, http: httpx2.Client
) -> None:
    # The worked example: two servers sharing a pool, a daily rota, a night shift split
    # at the period end (AKS-131 note in docs/research/spec-2-prior-art.md; daily since
    # #73, so that it loads with no W201).
    spec = tool_named("edit_model")
    arguments = dict(spec.example_arguments)
    edits = arguments["edits"]
    assert isinstance(edits, list)
    pools = [e for e in edits if e.get("type") == "resource_pool"]
    pooled = [e for e in edits if e.get("type") == "server" and "pool" in e["params"]]
    [rota] = [e for e in edits if e.get("type") == "schedule"]
    assert len(pools) == 1 and len(pooled) == 2
    assert {e["params"]["pool"] for e in pooled} == {pools[0]["id"]}
    assert rota["params"]["period"] == "24 h" and rota["params"]["target"] == pools[0]["id"]
    shifts = rota["params"]["shifts"]
    assert {"start": "22 h", "end": "24 h", "capacity": 1} in shifts
    assert {"start": "0 h", "end": "6 h", "capacity": 1} in shifts

    async def check(mcp_client: Client) -> None:
        error, project = await call(mcp_client, "create_model", {"name": "Workshop"})
        assert not error
        error, body = await call(
            mcp_client, "edit_model", {**arguments, "project_id": project["id"]}
        )
        assert not error, body
        assert body["revision"] == 1 and body["issues"] == []
        error, checked = await call(mcp_client, "validate_model", {"project_id": project["id"]})
        assert not error and checked["issues"] == []

    run(check, client)


def test_edit_model_refusals_are_data(client: ServiceClient, http: httpx2.Client) -> None:
    async def check(mcp_client: Client) -> None:
        pid = await new_coffee_shop(mcp_client)
        current = http.get(f"/v1/projects/{pid}/model").json()
        # E180: an edit that cannot be applied; nothing is saved.
        error, body = await call(
            mcp_client,
            "edit_model",
            {"project_id": pid, "edits": [{"edit": "remove_component", "id": "oven"}]},
        )
        assert error and body["error"]["code"] == "E180"
        assert [(i["code"], i["path"]) for i in body["issues"]] == [("E180", "/edits/0")]
        # E181: a stale revision; the current model and revision come with it.
        error, body = await call(
            mcp_client,
            "edit_model",
            {"project_id": pid, "edits": COFFEE_SHOP_EDITS[:1], "base_revision": 0},
        )
        assert error and body["error"]["code"] == "E181"
        assert body["model"] == current["model"] and body["revision"] == current["revision"]
        # E184: an edit of the wrong shape, at its field.
        error, body = await call(
            mcp_client,
            "edit_model",
            {"project_id": pid, "edits": [{"edit": "disconnect", "from": "till.out", "x": 1}]},
        )
        assert error and body["error"]["code"] == "E184"
        assert body["issues"][0]["path"].startswith("/edits/0")
        # E185: an unknown project.
        error, body = await call(
            mcp_client,
            "edit_model",
            {"project_id": "no-such-project", "edits": COFFEE_SHOP_EDITS[:1]},
        )
        assert error and body["error"]["code"] == "E185"
        # An empty batch is malformed (spec 3: "edits holds at least one edit").
        error, body = await call(mcp_client, "edit_model", {"project_id": pid, "edits": []})
        assert error and body["error"]["code"] == "E184"
        assert http.get(f"/v1/projects/{pid}/model").json() == current
        # E186: a model.json changed outside the service so that it fails the schema pass.
        model_file = Path(http.get("/v1/projects").json()[0]["path"]) / "model.json"
        model_file.write_text('{"format_version": "0.1"}', encoding="utf-8")
        error, body = await call(
            mcp_client,
            "edit_model",
            {"project_id": pid, "edits": [{"edit": "disconnect", "from": "till.out"}]},
        )
        assert error and body["error"]["code"] == "E186" and body["issues"]

    run(check, client)


# --- run_model, get_run_status and get_results ----------------------------------------------


def test_a_run_from_start_to_results(client: ServiceClient, http: httpx2.Client) -> None:
    async def check(mcp_client: Client) -> None:
        pid = await new_coffee_shop(mcp_client)
        error, started = await call(
            mcp_client, "run_model", {"project_id": pid, "experiment_id": "base"}
        )
        assert not error and set(started) == set(example_json("run_model")) == {"run_id"}
        rid = started["run_id"]
        status = await finished(mcp_client, rid)
        assert set(status) == set(example_json("get_run_status"))
        assert status["state"] == "done" and status["fraction"] == 1.0
        assert status == http.get(f"/v1/runs/{rid}").json()
        assert status["project_id"] == pid and status["experiment_id"] == "base"
        error, results = await call(
            mcp_client, "get_results", {"run_id": rid, "tables": ["replications"]}
        )
        assert not error
        summary = http.get(f"/v1/runs/{rid}/summary").json()
        rows = http.get(f"/v1/runs/{rid}/tables/replications").json()
        assert results == {**summary, "tables": {"replications": rows}}
        metrics = results["summary"]["scenarios"]["default"]["metrics"]
        for name in ("till.wait.mean", "till.utilization"):
            assert set(metrics[name]) == {"mean", "half_width", "unit", "n"}
            assert metrics[name]["n"] == 3
        assert results["summary"]["confidence"] == 0.95
        assert len(rows) == 3 * len(metrics)
        # The run was recorded as the MCP server's (spec 3 "Client header").
        manifest = Path(http.get("/v1/projects").json()[0]["path"]) / "runs" / rid
        assert json.loads((manifest / "manifest.json").read_text())["client"] == "mcp"
        # The experiment's seed makes a second run give the same summary.
        error, again = await call(
            mcp_client, "run_model", {"project_id": pid, "experiment_id": "base"}
        )
        assert not error
        assert (await finished(mcp_client, again["run_id"]))["state"] == "done"
        error, repeated = await call(mcp_client, "get_results", {"run_id": again["run_id"]})
        assert not error and repeated == {**summary, "tables": {}}

    run(check, client)


def test_run_model_of_an_optimization_model(client: ServiceClient, http: httpx2.Client) -> None:
    product_mix = json.loads((ROOT / "benchmarks/product_mix/model.json").read_text())

    async def check(mcp_client: Client) -> None:
        error, project = await call(
            mcp_client, "create_model", {"name": "Product mix", "domain": "optimization"}
        )
        assert not error
        pid = project["id"]
        assert http.put(f"/v1/projects/{pid}/model", json=product_mix).status_code == 200
        error, started = await call(mcp_client, "run_model", {"project_id": pid})
        assert not error
        assert (await finished(mcp_client, started["run_id"]))["state"] == "done"
        error, results = await call(mcp_client, "get_results", {"run_id": started["run_id"]})
        assert not error and results["tables"] == {}
        # Clean values (#76): HiGHS gives 24.000000000000004 chairs and a wood slack of
        # 5.7e-14; the tools pass on what the adapter reports.
        assert results["summary"]["objective"] == 2200.0
        assert results["summary"]["variables"] == {"chairs": 24.0, "tables": 14.0}
        slacks = {name: item["slack"] for name, item in results["summary"]["constraints"].items()}
        assert slacks == {"wood": 0.0, "labour": 0.0}
        # An optimization run has no tables.
        error, body = await call(
            mcp_client, "get_results", {"run_id": started["run_id"], "tables": ["replications"]}
        )
        assert error and body["error"]["code"] == "E185"

    run(check, client)


def test_get_results_returns_the_findings_of_the_service(
    client: ServiceClient, http: httpx2.Client, folders: tuple[Path, Path]
) -> None:
    """The M1 three-machine line, unchanged, through the tools (AKS-135): get_results carries
    the service's findings, bottleneck and not_enough_runs, as its description's example
    shows them, and the W220 issue of a threshold that cannot be used."""
    line = json.loads((ROOT / "examples" / "three_machine_line.json").read_text())

    async def check(mcp_client: Client) -> None:
        error, project = await call(mcp_client, "create_model", {"name": "Line"})
        assert not error
        pid = project["id"]
        assert http.put(f"/v1/projects/{pid}/model", json=line).status_code == 200
        error, started = await call(
            mcp_client, "run_model", {"project_id": pid, "experiment_id": "base"}
        )
        assert not error
        rid = started["run_id"]
        assert (await finished(mcp_client, rid))["state"] == "done"
        error, results = await call(mcp_client, "get_results", {"run_id": rid})
        assert not error
        assert results == {**http.get(f"/v1/runs/{rid}/summary").json(), "tables": {}}
        assert results["issues"] == []
        bottleneck, not_enough = results["findings"]
        example = tool_named("get_results").example_result
        for finding in (bottleneck, not_enough):
            # The description's worked example shows these two findings' text and keys.
            assert json.dumps(finding["text"]) in example
            assert list(finding) == [
                "rule",
                "severity",
                "component",
                "scenario",
                "text",
                "evidence",
            ]
        assert (bottleneck["rule"], bottleneck["component"]) == ("bottleneck", "weld")
        assert (not_enough["rule"], not_enough["evidence"]["n_required"]) == ("not_enough_runs", 60)
        # A threshold the user set that cannot be used: W220, and its default is used.
        settings_file = folders[0] / "settings.json"
        settings = json.loads(settings_file.read_text())
        settings["finding_thresholds"] = {"bottleneck_utilization": 2, "relative_half_width": 0.15}
        settings_file.write_text(json.dumps(settings))
        error, results = await call(mcp_client, "get_results", {"run_id": rid})
        assert not error
        assert [(item["rule"], item["component"]) for item in results["findings"]] == [
            ("bottleneck", "weld")
        ]
        assert [(item["code"], item["path"]) for item in results["issues"]] == [
            ("W220", "/finding_thresholds/bottleneck_utilization")
        ]

    run(check, client)


def test_run_model_of_a_search_experiment(client: ServiceClient) -> None:
    # Simulation-based optimization (spec 2) through the same tool (M5 "Left").
    search_edits = [
        {"edit": "set_parameter", "id": "tills", "value": 1, "type": "integer", "min": 1, "max": 2},
        {"edit": "set_setting", "id": "till", "path": "/capacity", "value": {"$param": "tills"}},
        {
            "edit": "set_path",
            "path": "/objectives",
            "value": [{"id": "wait", "metric": "till.wait.mean", "sense": "minimize"}],
        },
        {
            "edit": "set_experiment",
            "id": "base",
            "replications": 2,
            "length": "10 h",
            "search": {"objective": "wait", "budget": 2, "replications": 2},
        },
    ]

    async def check(mcp_client: Client) -> None:
        pid = await new_coffee_shop(mcp_client)
        error, edited = await call(
            mcp_client, "edit_model", {"project_id": pid, "edits": search_edits}
        )
        assert not error and edited["issues"] == [], edited
        error, started = await call(
            mcp_client, "run_model", {"project_id": pid, "experiment_id": "base"}
        )
        assert not error
        assert (await finished(mcp_client, started["run_id"]))["state"] == "done"
        error, results = await call(mcp_client, "get_results", {"run_id": started["run_id"]})
        assert not error
        search = results["summary"]["search"]
        assert search["status"] == "feasible"
        assert search["best"]["set"] == {"tills": 2}

    run(check, client)


def test_run_model_refusals_are_data(client: ServiceClient, http: httpx2.Client) -> None:
    async def check(mcp_client: Client) -> None:
        pid = await new_coffee_shop(mcp_client)
        # A process model needs an experiment, and one it has.
        error, body = await call(mcp_client, "run_model", {"project_id": pid})
        assert error and body["error"]["code"] == "E184"
        assert [i["path"] for i in body["issues"]] == ["/experiment_id"]
        error, body = await call(
            mcp_client, "run_model", {"project_id": pid, "experiment_id": "nope"}
        )
        assert error and body["error"]["code"] == "E184"
        # 422: a model with errors does not run, and its issues say why.
        await call(
            mcp_client,
            "edit_model",
            {
                "project_id": pid,
                "edits": [{"edit": "set_setting", "id": "till", "path": "/capacity", "value": 0}],
            },
        )
        error, body = await call(
            mcp_client, "run_model", {"project_id": pid, "experiment_id": "base"}
        )
        assert error and body["error"]["code"] == "E123"
        assert ("E123", "/components/1/params/capacity") in {
            (i["code"], i["path"]) for i in body["issues"]
        }
        # An unknown project, and an optimization model given an experiment.
        error, body = await call(
            mcp_client, "run_model", {"project_id": "nope", "experiment_id": "base"}
        )
        assert error and body["error"]["code"] == "E185"
        error, plan = await call(
            mcp_client, "create_model", {"name": "Plan", "domain": "optimization"}
        )
        # A plan with decisions: an empty one is E179 before its experiment is looked at.
        product_mix = json.loads((ROOT / "benchmarks/product_mix/model.json").read_text())
        assert http.put(f"/v1/projects/{plan['id']}/model", json=product_mix).status_code == 200
        error, body = await call(
            mcp_client, "run_model", {"project_id": plan["id"], "experiment_id": "base"}
        )
        assert error and body["error"]["code"] == "E184"
        # Nothing ran.
        assert http.get(f"/v1/projects/{pid}/runs").json() == []
        # An unknown run.
        for name in ("get_run_status", "get_results"):
            error, body = await call(mcp_client, name, {"run_id": "20261108T000000-AAAAAA"})
            assert error and body["error"]["code"] == "E185", name

    run(check, client)


def test_results_of_a_run_that_is_not_done_are_the_services_e188(
    client: ServiceClient, http: httpx2.Client
) -> None:
    async def check(mcp_client: Client) -> None:
        pid = await new_coffee_shop(mcp_client)
        await call(mcp_client, "edit_model", {"project_id": pid, "edits": [LONG]})
        error, started = await call(
            mcp_client, "run_model", {"project_id": pid, "experiment_id": "long"}
        )
        assert not error
        try:
            error, status = await call(mcp_client, "get_run_status", {"run_id": started["run_id"]})
            assert not error and status["state"] in ("queued", "running")
            error, body = await call(mcp_client, "get_results", {"run_id": started["run_id"]})
            assert error and body["error"]["code"] == "E188"
        finally:
            cancel_all(http, pid)
        assert (await finished(mcp_client, started["run_id"]))["state"] == "cancelled"

    run(check, client)


# --- the run limit (spec 4 "Limits") -------------------------------------------------------


def test_a_third_unfinished_run_of_a_project_is_refused_with_e194(
    client: ServiceClient, http: httpx2.Client
) -> None:
    async def check(mcp_client: Client) -> None:
        pid = await new_coffee_shop(mcp_client)
        await call(mcp_client, "edit_model", {"project_id": pid, "edits": [LONG]})
        other = await new_coffee_shop(mcp_client)
        await call(mcp_client, "edit_model", {"project_id": other, "edits": [LONG]})
        long_run = {"project_id": pid, "experiment_id": "long"}
        try:
            started = []
            for _ in range(MAX_UNFINISHED_RUNS):
                error, body = await call(mcp_client, "run_model", long_run)
                assert not error, body
                started.append(body["run_id"])
            error, body = await call(mcp_client, "run_model", long_run)
            assert error
            assert body["error"]["code"] == RUN_LIMIT == "E194"
            assert body["run_ids"] == started
            [issue] = body["issues"]
            assert issue["code"] == "E194" and issue["path"] == "/project_id"
            assert issue["component"] is None and issue["hint"]
            assert issue["message"] == body["error"]["message"]
            assert all(rid in issue["message"] for rid in started)
            # Nothing was sent to start it.
            assert len(http.get(f"/v1/projects/{pid}/runs").json()) == 2
            # Another project has its own count.
            error, body = await call(
                mcp_client, "run_model", {"project_id": other, "experiment_id": "long"}
            )
            assert not error
            # A run that ends frees its place: a queued run is cancelled at once.
            cancelled = http.post(f"/v1/runs/{started[1]}/cancel").json()
            assert cancelled["state"] == "cancelled"
            error, newer = await call(mcp_client, "run_model", long_run)
            assert not error, newer
            error, body = await call(mcp_client, "run_model", long_run)
            assert error and body["run_ids"] == [started[0], newer["run_id"]]
        finally:
            cancel_all(http, pid)
            cancel_all(http, other)

    run(check, client)


def test_runs_this_mcp_server_did_not_start_do_not_count(
    client: ServiceClient, http: httpx2.Client
) -> None:
    async def check(mcp_client: Client) -> None:
        pid = await new_coffee_shop(mcp_client)
        await call(mcp_client, "edit_model", {"project_id": pid, "edits": [LONG]})
        try:
            for _ in range(2):
                answer = http.post(f"/v1/projects/{pid}/runs", json={"experiment_id": "long"})
                assert answer.status_code == 202
            error, body = await call(
                mcp_client, "run_model", {"project_id": pid, "experiment_id": "long"}
            )
            assert not error, body
        finally:
            cancel_all(http, pid)

    run(check, client)


def test_the_limit_asks_the_service_and_forgets_what_it_no_longer_finds(
    folders: tuple[Path, Path], stub: StubService
) -> None:
    client = ServiceClient(*folders, command=NO_START)
    spec = tool_named("run_model")
    arguments = {"project_id": "p", "experiment_id": "base"}
    started = {"r1", "r2"}

    # Two runs started.
    stub.answer(202, {"run_id": "r1"})
    assert not run_tool(spec, client, arguments).is_error
    stub.answer(200, {"state": "queued"})
    stub.answer(202, {"run_id": "r2"})
    assert not run_tool(spec, client, arguments).is_error
    assert set(client.started_runs.tracked("p")) == started
    # r1 is gone (404) and r2 is done: both are forgotten, and a third run starts.
    stub.requests.clear()
    stub.answer(404, {"error": {"code": "E185", "message": "No run."}, "issues": []})
    stub.answer(200, {"state": "done"})
    stub.answer(202, {"run_id": "r3"})
    assert not run_tool(spec, client, arguments).is_error
    assert [r.path for r in stub.requests] == [
        "/v1/runs/r1",
        "/v1/runs/r2",
        "/v1/projects/p/runs",
    ]
    assert client.started_runs.tracked("p") == ("r3",)
    # An answer that is not a state the service gives does not count as unfinished.
    stub.answer(200, {"state": None})
    stub.answer(202, {"run_id": "r4"})
    assert not run_tool(spec, client, arguments).is_error
    assert client.started_runs.tracked("p") == ("r4",)
    # A 202 without a run id records nothing; neither does a refusal.
    stub.answer(200, {"state": "running"})
    stub.answer(202, {})
    assert not run_tool(spec, client, arguments).is_error
    stub.answer(200, {"state": "running"})
    stub.answer(422, {"error": {"code": "E122", "message": "x"}, "issues": []})
    assert run_tool(spec, client, arguments).is_error
    assert client.started_runs.tracked("p") == ("r4",)


def test_a_refused_status_check_is_the_result_and_no_run_starts(
    folders: tuple[Path, Path], stub: StubService
) -> None:
    client = ServiceClient(*folders, command=NO_START)
    spec = tool_named("run_model")
    arguments = {"project_id": "p", "experiment_id": "base"}
    stub.answer(202, {"run_id": "r1"})
    assert not run_tool(spec, client, arguments).is_error
    failure = {"error": {"code": "E187", "message": "The service failed."}, "issues": []}
    stub.answer(500, failure)
    stub.requests.clear()
    result = run_tool(spec, client, arguments)
    assert result.is_error and payload(result) == failure
    assert [r.path for r in stub.requests] == ["/v1/runs/r1"]
    # The run is still counted: its state is not known.
    assert client.started_runs.tracked("p") == ("r1",)
    # No service: E193, and still no run.
    stub.stop()
    stub.requests.clear()
    result = run_tool(spec, client, arguments)
    assert result.is_error and payload(result)["error"]["code"] == "E193"
    assert stub.requests == []


def test_two_calls_at_once_cannot_both_pass_the_limit(
    folders: tuple[Path, Path], stub: StubService
) -> None:
    client = ServiceClient(*folders, command=NO_START)
    spec = tool_named("run_model")
    arguments = {"project_id": "p", "experiment_id": "base"}
    made: list[str] = []
    lock = threading.Lock()

    def respond(recorded: Recorded) -> tuple[int, bytes, dict[str, str]]:
        if recorded.method == "POST":
            with lock:
                made.append(f"r{len(made) + 1}")
                return 202, json.dumps({"run_id": made[-1]}).encode(), {}
        # Every status check is slow, so two calls without the lock would overlap.
        time.sleep(0.3)
        return 200, b'{"state": "running"}', {}

    stub.respond = respond
    assert not run_tool(spec, client, arguments).is_error
    results: list[Any] = []

    def call_once() -> None:
        results.append(run_tool(spec, client, arguments))

    threads = [threading.Thread(target=call_once) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert sorted(bool(result.is_error) for result in results) == [False, True]
    assert made == ["r1", "r2"]
    [refused] = [payload(result) for result in results if result.is_error]
    assert refused["error"]["code"] == "E194" and refused["run_ids"] == ["r1", "r2"]


# --- descriptions --------------------------------------------------------------------------


def test_the_write_and_run_descriptions_say_what_an_assistant_needs() -> None:
    def described(name: str) -> str:
        return tool_named(name).tool().description or ""

    for phrase in ("template_id", "domain", "get_model", "edit_model", "base"):
        assert phrase in described("create_model"), phrase
    for phrase in ("E180", "E181", "base_revision", "seed", "/edits/", "period"):
        assert phrase in described("edit_model"), phrase
    for phrase in ("experiment_id", "search", "E194", "get_run_status", "seed", "E192"):
        assert phrase in described("run_model"), phrase
    for phrase in ("queued", "running", "done", "failed", "cancelled", "fraction"):
        assert phrase in described("get_run_status"), phrase
    for phrase in ("half_width", "confidence", "quantile", "seconds", "E188", "replications"):
        assert phrase in described("get_results"), phrase


def test_the_descriptions_say_an_experiment_s_length_includes_its_warm_up() -> None:
    """The first real-assistant trial (AKS-116) read "200 hours after a 10-hour warm-up" as
    length 200 h, which measures 190 h, and found it only from the arrival count."""

    def described(name: str) -> str:
        return tool_named(name).tool().description or ""

    for name in ("create_model", "edit_model"):
        assert "length includes the warmup" in described(name), name
    assert "length 210 h and warmup 10 h" in described("edit_model")


def test_the_edit_model_description_says_validate_model_adds_the_engine_s_check() -> None:
    """The trial's assistant ran without validate_model, reading edit_model's issues as the
    whole check; they are loading's (spec 3), and validate_model adds the engine's."""
    text = tool_named("edit_model").tool().description or ""
    assert "validate_model" in text
    assert "the engine's own check" in text


def test_the_descriptions_name_the_parameter_reference() -> None:
    """The M10 trial of "How many machines?" (AKS-125) tried five spellings of a parameter in
    the till's capacity, each E123, and gave up: no description named spec 1's
    ``{"$param": "<id>"}``."""
    for name in ("edit_model", "get_schema"):
        assert '{"$param": "<id>"}' in (tool_named(name).tool().description or ""), name


#: The longest tool description the trial's Claude Code CLI took whole: it ran with
#: ``CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH`` 4096 (AKS-116), and a longer description would
#: be cut, losing its worked example, which comes last.
MAX_DESCRIPTION = 4096


def test_every_description_fits_the_trial_assistant_s_limit() -> None:
    for spec in TOOLS:
        assert len(spec.tool().description or "") <= MAX_DESCRIPTION, spec.name


# --- typed edits and isError on an invalid save (#98, Reviewer B finding 8) ------------------


def test_a_save_with_only_warnings_is_not_an_error(client: ServiceClient) -> None:
    """A warning is to read, not to fix: the result is not marked isError (#98)."""

    async def check(mcp_client: Client) -> None:
        pid = await new_coffee_shop(mcp_client)
        clipping = {"dist": "normal", "mean": "2 min", "sd": "1 min"}  # 2.3% below 0: W202
        error, body = await call(
            mcp_client,
            "edit_model",
            {
                "project_id": pid,
                "edits": [
                    {
                        "edit": "set_setting",
                        "id": "arrivals",
                        "path": "/interarrival",
                        "value": clipping,
                    }
                ],
            },
        )
        assert [issue["code"] for issue in body["issues"]] == ["W202"]
        assert not error

    run(check, client)


def test_the_edit_model_description_says_an_invalid_save_is_an_error() -> None:
    description = tool_named("edit_model").description
    assert "marked as an error" in description and "still saved" in description


def edits_schema() -> dict[str, Any]:
    schema = tool_named("edit_model").input_schema()["properties"]["edits"]
    assert schema["type"] == "array"
    items: dict[str, Any] = schema["items"]
    return items


def test_each_edit_kind_is_typed_in_the_input_schema() -> None:
    """Reviewer B finding 8: the edits were typed only as objects. Each kind is now its own
    object: 'edit' is that kind, its fields are listed, the required ones required, and no
    other field is allowed (the table of ``ithax.model.edits``, which the service checks)."""
    kinds = edits_schema()["oneOf"]
    assert [kind["properties"]["edit"]["const"] for kind in kinds] == list(EDIT_KINDS)
    by_kind = {kind["properties"]["edit"]["const"]: kind for kind in kinds}
    assert by_kind["add_component"]["required"] == ["edit", "id", "type", "params"]
    assert set(by_kind["add_component"]["properties"]) == {"edit", "id", "type", "params", "ui"}
    assert by_kind["set_label"]["properties"]["label"] == {"type": ["string", "null"]}
    assert by_kind["connect"]["properties"]["from"] == {"type": "string"}
    assert all(kind["additionalProperties"] is False for kind in kinds)


@pytest.mark.parametrize(
    "edit",
    [
        *tool_named("edit_model").example_arguments["edits"],  # type: ignore[misc]
        {"edit": "set_label", "id": "till", "label": None},
        {"edit": "set_experiment", "id": "base", "length": "210 h", "warmup": "10 h"},
        {"edit": "set_path", "path": "/meta/description", "value": "A shop"},
    ],
)
def test_the_edits_the_service_takes_fit_the_schema(edit: dict[str, Any]) -> None:
    jsonschema.validate(edit, edits_schema())


@pytest.mark.parametrize(
    "edit",
    [
        {"edit": "add_component", "id": "till", "type": "server"},  # no params
        {"edit": "connect", "from": "a.out", "to": "b.in", "extra": 1},
        {"edit": "teleport", "id": "till"},
        {"edit": "set_label", "id": "till", "label": 3},
        {"id": "till"},
    ],
)
def test_edits_the_service_refuses_do_not_fit_the_schema(edit: dict[str, Any]) -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(edit, edits_schema())


# --- the descriptions Reviewer B asked for (#98, recommendation 10) ----------------------------

TEMPLATES_ROOT = Path(__file__).resolve().parents[2] / "templates"


def test_every_example_result_is_at_the_reader_s_format_version() -> None:
    """The examples showed format_version 0.1 while a new project is written at the
    reader's version."""
    import re

    from ithax.model.migration import FORMAT_VERSION

    for spec in TOOLS:
        for version in re.findall(r'"format_version": "([0-9.]+)"', spec.description):
            assert version == FORMAT_VERSION, spec.name


def test_get_schema_shows_a_search_and_an_optimization_model_compactly() -> None:
    """Each fragment is the shipped template's own, so the example cannot drift."""
    description = tool_named("get_schema").description
    search = json.loads((TEMPLATES_ROOT / "how_many_machines" / "model.json").read_text())
    plan = json.loads((TEMPLATES_ROOT / "product_mix" / "model.json").read_text())
    for fragment in (
        search["parameters"],
        search["objectives"],
        search["constraints"],
        search["experiments"][0]["search"],
        plan["objective"],
        plan["constraints"][0],
        plan["variables"][0],
    ):
        assert json.dumps(fragment) in description, fragment
    for words in ("minimize or maximize", "continuous, integer or binary", "'=='"):
        assert words in description


def test_get_results_defines_separated() -> None:
    assert "separated" in tool_named("get_results").description


def test_edit_model_says_how_set_path_treats_a_list_index() -> None:
    description = tool_named("edit_model").description
    assert "index from 0" in description and "'-'" in description


def test_get_results_gives_at_most_50_variables_and_constraints(
    folders: tuple[Path, Path], stub: StubService
) -> None:
    """#82, owner option A on #181: the one exception to "a tool's result is the response
    body". A large optimization's answer keeps the first 50 variables and constraints (with
    their duals) in the summary's order, which is the model's, and the first 50 of its
    finding's evidence, and says how many there are and where the rest are."""
    names = [f"x{n:03d}" for n in range(60)]
    rows = [f"c{n:03d}" for n in range(55)]
    summary = {
        "status": "optimal",
        "objective": 1.0,
        "variables": dict.fromkeys(names, 1.0),
        "constraints": {row: {"tight": True, "slack": 0.0} for row in rows},
        "duals": dict.fromkeys(rows, 0.5),
        "warnings": [],
    }
    evidence = {"status": "optimal", "objective": 1.0, "variables": dict.fromkeys(names, 1.0)}
    finding = {
        "rule": "optimization_result",
        "text": "Best found: ...",
        "evidence": {**evidence, "tight": rows},
    }
    other = {"rule": "bottleneck", "text": "till is the bottleneck.", "evidence": {"x": 1}}
    stub.answer(200, {"summary": summary, "findings": [finding, other], "issues": []})
    client = ServiceClient(*folders, command=NO_START)

    async def check(mcp_client: Client) -> None:
        error, body = await call(mcp_client, "get_results", {"run_id": "r"})
        assert not error
        cut = body["summary"]
        assert list(cut["variables"]) == names[:50]
        assert list(cut["constraints"]) == rows[:50]
        assert list(cut["duals"]) == rows[:50]
        assert cut["cut_short"] == {
            "variables": {"shown": 50, "total": 60},
            "constraints": {"shown": 50, "total": 55},
            "note": "This answer holds the first 50 of 60 variables and the first 50 of 55 "
            "constraints, in the model's order. GET /v1/runs/r/summary and the project's "
            "export hold every value.",
        }
        [cut_finding, kept] = body["findings"]
        assert list(cut_finding["evidence"]["variables"]) == names[:50]
        assert cut_finding["evidence"]["tight"] == rows[:50]
        assert cut_finding["evidence"]["cut_short"] == {
            "variables": {"shown": 50, "total": 60},
            "tight": {"shown": 50, "total": 55},
        }
        assert kept == other
        assert {key: cut[key] for key in ("status", "objective", "warnings")} == {
            key: summary[key] for key in ("status", "objective", "warnings")
        }

    run(check, client)


def test_get_results_of_a_small_optimization_is_the_response_body(
    folders: tuple[Path, Path], stub: StubService
) -> None:
    summary = {"status": "optimal", "variables": {"a": 1.0}, "constraints": {}, "duals": {}}
    answer = {"summary": summary, "findings": [], "issues": []}
    stub.answer(200, answer)
    client = ServiceClient(*folders, command=NO_START)

    async def check(mcp_client: Client) -> None:
        error, body = await call(mcp_client, "get_results", {"run_id": "r"})
        assert not error
        assert body == {**answer, "tables": {}}

    run(check, client)


def test_a_note_names_only_what_was_cut() -> None:
    from ithax.mcp.tools import _cut_summary

    summary = {"variables": {"a": 1.0}, "constraints": {f"c{n}": {} for n in range(51)}}
    cut = _cut_summary(summary, "/v1/runs/r")
    assert cut["variables"] == {"a": 1.0}
    assert cut["cut_short"] == {
        "constraints": {"shown": 50, "total": 51},
        "note": "This answer holds the first 50 of 51 constraints, in the model's order. "
        "GET /v1/runs/r/summary and the project's export hold every value.",
    }
