"""The tool list and the six read tools (spec 4 "MCP tools" and "How the server runs and
answers"; AKS-115). The five write and run tools are in ``test_mcp_write_tools.py``
(AKS-134).

Driven through the MCP SDK's in-memory client (``Client(server)``), as an assistant would
call them, against the real M6 application served in process, or against a stub where the
test needs to see the requests themselves. Each tool calls the endpoint spec 4's table
names, read from the spec when the test runs, and returns its response; a refusal, an
input problem and a service that cannot be reached are results marked ``isError`` that
hold spec 1 issue objects, never protocol errors.
"""

import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx2
import pytest
from mcp import Client, MCPError
from mcp_support import (
    NO_START,
    ROOT,
    StubService,
    in_process_service,
    payload,
    run,
    spec_4_tool_rows,
)

from lcsim.mcp.client import ServiceClient
from lcsim.mcp.tools import TOOLS, check_arguments, run_tool, tool_named
from lcsim.service.discovery import ServiceInfo

COFFEE_SHOP = ROOT / "examples" / "coffee_shop.json"
READ_TOOLS = {
    "list_templates",
    "get_schema",
    "list_projects",
    "get_model",
    "validate_model",
    "list_engines",
}
WRITE_TOOLS = {"create_model", "edit_model", "run_model", "get_run_status", "get_results"}
ALL_TOOLS = READ_TOOLS | WRITE_TOOLS


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


def new_project(http: httpx2.Client, name: str = "Coffee shop") -> str:
    response = http.post("/v1/projects", json={"name": name})
    assert response.status_code == 200
    return str(response.json()["id"])


# --- the tool list ---------------------------------------------------------------------------


def test_the_server_lists_the_eleven_tools_in_the_order_of_spec_4() -> None:
    # Was test_the_server_lists_the_six_read_tools (AKS-115); AKS-134 adds the other five.
    async def check(mcp_client: Client) -> None:
        listed = await mcp_client.list_tools()
        assert {tool.name for tool in listed.tools} == ALL_TOOLS
        assert len(ALL_TOOLS) == 11
        assert [tool.name for tool in listed.tools] == [spec.name for spec in TOOLS]
        assert [tool.name for tool in listed.tools] == list(spec_4_tool_rows())

    run(check, ServiceClient(Path("unused-config"), Path("unused-data"), command=NO_START))


def test_every_tool_has_the_inputs_spec_4_names() -> None:
    rows = spec_4_tool_rows()
    assert set(rows) == ALL_TOOLS
    for spec in TOOLS:
        inputs, _ = rows[spec.name]
        named = re.findall(r"`(\w+)`", inputs)
        optional = re.findall(r"optional `(\w+)`", inputs)
        declared = {item.name: item.required for item in spec.inputs}
        if inputs == "none":
            assert declared == {}, spec.name
        else:
            assert set(declared) == set(named), spec.name
            assert {name for name, required in declared.items() if not required} == set(optional), (
                spec.name
            )


def test_every_input_schema_allows_only_the_declared_inputs() -> None:
    for spec in TOOLS:
        schema = spec.input_schema()
        assert schema["type"] == "object" and schema["additionalProperties"] is False
        assert set(schema["properties"]) == {item.name for item in spec.inputs}
        assert schema.get("required", []) == [item.name for item in spec.inputs if item.required]
        for item in spec.inputs:
            assert schema["properties"][item.name]["description"] == item.description


def test_every_description_names_its_endpoint_and_carries_one_worked_example() -> None:
    rows = spec_4_tool_rows()
    for spec in TOOLS:
        description = spec.tool().description
        assert description is not None
        assert description.count("Example: ") == 1, spec.name
        for method, path in rows[spec.name][1]:
            written = (
                path.replace("{pid}", "{project_id}")
                .replace("{type}", "{component_type}")
                .replace("{rid}", "{run_id}")
            )
            assert f"{method} {written}" in description, (spec.name, method, path)
        # The example's arguments are valid arguments for the tool.
        assert check_arguments(spec, spec.example_arguments) == [], spec.name
        assert json.dumps(spec.example_arguments) in description


def test_get_schema_states_the_behaviour_defaults_of_spec_2() -> None:
    description = tool_named("get_schema").tool().description or ""
    for phrase in (
        "unlimited, first in first out",
        "discards",
        "on_full",
        "preempt-resume",
        "0 outside",
        "its own unit first",
    ):
        assert phrase in description, phrase


def test_tool_named_finds_each_tool_and_refuses_another() -> None:
    for spec in TOOLS:
        assert tool_named(spec.name) is spec
    with pytest.raises(KeyError):
        tool_named("run_shell")


# --- each tool calls the endpoint spec 4 names ------------------------------------------------


@pytest.mark.parametrize("name", sorted(READ_TOOLS))
def test_each_tool_calls_the_endpoint_spec_4_names(name: str, folders: tuple[Path, Path]) -> None:
    stub = StubService(folders[0])
    stub.start()
    client = ServiceClient(*folders, command=NO_START)
    _, calls = spec_4_tool_rows()[name]
    cases: list[tuple[dict[str, object], tuple[str, str]]] = []
    for method, path in calls:
        arguments: dict[str, object] = {}
        if "{pid}" in path:
            arguments["project_id"] = "6f1c2a4e/../x y"
            path = path.replace("{pid}", quote("6f1c2a4e/../x y", safe=""))
        if "{type}" in path:
            arguments["component_type"] = "server"
            path = path.replace("{type}", "server")
        cases.append((arguments, (method, path)))

    async def check(mcp_client: Client) -> None:
        for arguments, expected in cases:
            stub.requests.clear()
            stub.answer(200, {"answer": name})
            result = await mcp_client.call_tool(name, arguments)
            assert not result.is_error
            assert payload(result) == {"answer": name}
            assert [(r.method, r.path) for r in stub.requests] == [expected]
            assert all(r.headers["X-Client"] == "mcp" for r in stub.requests)

    try:
        run(check, client)
    finally:
        stub.stop()


# --- the read tools against the real service ---------------------------------------------------


def test_list_templates_returns_the_installed_templates(
    client: ServiceClient, http: httpx2.Client
) -> None:
    async def check(mcp_client: Client) -> None:
        result = await mcp_client.call_tool("list_templates", {})
        assert not result.is_error
        listed = payload(result)
        assert listed == http.get("/v1/templates").json()
        assert {
            "clinic_patient_flow",
            "coffee_shop",
            "inventory_reorder_point",
            "machine_breakdowns",
            "three_machine_line",
            "transport_plan",
            "warehouse_pick_pack",
        } <= {item["id"] for item in listed}
        assert all({"id", "title", "summary"} <= set(item) for item in listed)

    run(check, client)


def test_get_schema_returns_the_composed_schema_or_one_type(
    client: ServiceClient, http: httpx2.Client
) -> None:
    async def check(mcp_client: Client) -> None:
        whole = await mcp_client.call_tool("get_schema", {})
        assert not whole.is_error
        assert payload(whole) == http.get("/v1/schema").json()
        server = await mcp_client.call_tool("get_schema", {"component_type": "server"})
        assert not server.is_error
        assert payload(server) == http.get("/v1/schema/components/server").json()

    run(check, client)


def test_get_schema_of_an_unknown_type_is_the_services_e185_as_data(
    client: ServiceClient,
) -> None:
    async def check(mcp_client: Client) -> None:
        result = await mcp_client.call_tool("get_schema", {"component_type": "conveyor"})
        assert result.is_error
        body = payload(result)
        assert body["error"]["code"] == "E185" and "conveyor" in body["error"]["message"]
        assert body["issues"] == []

    run(check, client)


def test_list_projects_get_model_and_validate_model(
    client: ServiceClient, http: httpx2.Client
) -> None:
    pid = new_project(http)
    coffee_shop = json.loads(COFFEE_SHOP.read_text(encoding="utf-8"))
    assert http.put(f"/v1/projects/{pid}/model", json=coffee_shop).status_code == 200

    async def check(mcp_client: Client) -> None:
        projects = await mcp_client.call_tool("list_projects", {})
        assert not projects.is_error
        assert payload(projects) == http.get("/v1/projects").json()
        assert [project["id"] for project in payload(projects)] == [pid]
        model = await mcp_client.call_tool("get_model", {"project_id": pid})
        assert not model.is_error
        assert payload(model) == {"model": coffee_shop, "revision": 1}
        validated = await mcp_client.call_tool("validate_model", {"project_id": pid})
        assert not validated.is_error
        assert payload(validated) == {"revision": 1, "issues": []}

    run(check, client)


def test_validate_model_returns_the_issues_with_codes_and_hints(
    client: ServiceClient, http: httpx2.Client
) -> None:
    pid = new_project(http)
    edits = {"edits": [{"edit": "add_component", "id": "till", "type": "server", "params": {}}]}
    assert http.post(f"/v1/projects/{pid}/model/edits", json=edits).status_code == 200

    async def check(mcp_client: Client) -> None:
        result = await mcp_client.call_tool("validate_model", {"project_id": pid})
        # Validation issues are the answer, not a failure of the tool.
        assert not result.is_error
        body = payload(result)
        assert body["revision"] == 1
        codes = {(issue["code"], issue["path"]) for issue in body["issues"]}
        assert ("E122", "/components/0/params/capacity") in codes
        assert all(issue["hint"] and issue["component"] == "till" for issue in body["issues"])

    run(check, client)


def test_get_model_of_an_unknown_project_is_the_services_e185_as_data(
    client: ServiceClient,
) -> None:
    async def check(mcp_client: Client) -> None:
        for project_id in ("no-such-project", "..", "a/b", "%2e%2e"):
            result = await mcp_client.call_tool("get_model", {"project_id": project_id})
            assert result.is_error, project_id
            assert payload(result)["error"]["code"] == "E185", project_id

    run(check, client)


def test_list_engines_returns_the_installed_adapters(
    client: ServiceClient, http: httpx2.Client
) -> None:
    async def check(mcp_client: Client) -> None:
        result = await mcp_client.call_tool("list_engines", {})
        assert not result.is_error
        engines = payload(result)
        assert engines == http.get("/v1/engines").json()
        assert {engine["name"] for engine in engines} == {"highs", "simpy"}

    run(check, client)


def test_a_client_of_the_handshake_era_gets_the_same_answers(
    client: ServiceClient, http: httpx2.Client
) -> None:
    async def check(mcp_client: Client) -> None:
        assert mcp_client.protocol_version == "2025-11-25"
        listed = await mcp_client.list_tools()
        assert {tool.name for tool in listed.tools} == ALL_TOOLS
        result = await mcp_client.call_tool("list_engines", {})
        assert payload(result) == http.get("/v1/engines").json()

    run(check, client, mode="legacy")


def test_the_modern_era_is_negotiated_by_default(client: ServiceClient) -> None:
    async def check(mcp_client: Client) -> None:
        assert mcp_client.protocol_version == "2026-07-28"
        assert mcp_client.server_info is not None and mcp_client.server_info.name == "lcsim"

    run(check, client)


# --- inputs: problems are E184 issues at the input, and nothing is sent -----------------------


def test_input_problems_are_e184_issues_and_no_request_is_sent(folders: tuple[Path, Path]) -> None:
    stub = StubService(folders[0])
    stub.start()
    client = ServiceClient(*folders, command=NO_START)

    async def check(mcp_client: Client) -> None:
        cases: list[tuple[str, dict[str, Any], list[str]]] = [
            ("get_model", {}, ["/project_id"]),
            ("get_model", {"project_id": 7}, ["/project_id"]),
            ("get_model", {"project_id": None}, ["/project_id"]),
            ("validate_model", {"project_id": "p", "model": {}}, ["/model"]),
            ("get_schema", {"component_type": ["server"]}, ["/component_type"]),
            ("list_engines", {"verbose": True}, ["/verbose"]),
            ("validate_model", {"projectId": "p"}, ["/projectId", "/project_id"]),
        ]
        for name, arguments, paths in cases:
            result = await mcp_client.call_tool(name, arguments)
            assert result.is_error, (name, arguments)
            body = payload(result)
            assert body["error"]["code"] == "E184"
            assert name in body["error"]["message"]
            assert [issue["path"] for issue in body["issues"]] == paths, (name, arguments)
            for issue in body["issues"]:
                assert issue["code"] == "E184" and issue["severity"] == "error"
                assert issue["component"] is None and issue["message"] and issue["hint"]
                assert f"'{issue['path'][1:]}'" in issue["message"]
        assert stub.requests == [] and stub.probes == 0

    try:
        run(check, client)
    finally:
        stub.stop()


def test_check_arguments_names_each_problem_in_order() -> None:
    spec = tool_named("get_model")
    problems = check_arguments(spec, {"zeta": 1, "alpha": 2})
    assert [issue.path for issue in problems] == ["/alpha", "/zeta", "/project_id"]
    assert "get_model has no input 'alpha'" in problems[0].message
    assert "needs 'project_id'" in problems[2].message
    wrong = check_arguments(spec, {"project_id": 1.5})
    assert [issue.message for issue in wrong] == [
        "The input 'project_id' of get_model must be text."
    ]
    assert "~1" in check_arguments(spec, {"project_id": "p", "a/b": 1})[0].path


def test_text_that_is_not_valid_unicode_is_an_e184_issue_not_a_crash(
    folders: tuple[Path, Path],
) -> None:
    # A JSON escape can carry a lone surrogate; it cannot go into a path or a result.
    client = ServiceClient(*folders, command=NO_START)
    spec = tool_named("get_model")
    value = run_tool(spec, client, {"project_id": "\ud800"})
    assert value.is_error
    assert [issue["path"] for issue in payload(value)["issues"]] == ["/project_id"]
    key = run_tool(spec, client, {"project_id": "p", "a\ud800": 1})
    assert key.is_error
    [issue] = payload(key)["issues"]
    assert issue["path"] == "/a\\ud800" and "'a\\ud800'" in issue["message"]
    # Both results can be sent as JSON.
    value.model_dump_json()
    key.model_dump_json()
    # Text outside ASCII is valid and passes.
    assert check_arguments(spec, {"project_id": "café"}) == []


# --- a service that cannot be reached, and an unknown tool --------------------------------------


def test_a_service_that_cannot_be_started_is_an_e193_result(folders: tuple[Path, Path]) -> None:
    client = ServiceClient(*folders, command=[sys.executable, "-c", "raise SystemExit(1)"])

    async def check(mcp_client: Client) -> None:
        result = await mcp_client.call_tool("list_projects", {})
        assert result.is_error
        body = payload(result)
        assert body["error"]["code"] == "E193"
        [issue] = body["issues"]
        assert issue["code"] == "E193" and issue["path"] == "" and issue["hint"]
        assert issue["message"] == body["error"]["message"]

    run(check, client)


def test_an_unknown_tool_is_a_protocol_error() -> None:
    async def check(mcp_client: Client) -> None:
        with pytest.raises(MCPError, match="run_shell"):
            await mcp_client.call_tool("run_shell", {"command": "ls"})

    run(check, ServiceClient(Path("unused-config"), Path("unused-data"), command=NO_START))


def test_a_call_without_arguments_is_a_call_with_none(folders: tuple[Path, Path]) -> None:
    stub = StubService(folders[0])
    stub.start()
    client = ServiceClient(*folders, command=NO_START)

    async def check(mcp_client: Client) -> None:
        stub.answer(200, [])
        result = await mcp_client.call_tool("list_engines")
        assert not result.is_error and payload(result) == []
        missing = await mcp_client.call_tool("get_model")
        assert missing.is_error and payload(missing)["issues"][0]["path"] == "/project_id"

    try:
        run(check, client)
    finally:
        stub.stop()
