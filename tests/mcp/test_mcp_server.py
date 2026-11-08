"""``python -m lcsim.mcp``: the MCP server over stdio (spec 4 "How the server runs and
answers"; AKS-115).

``main`` and the stdio loop run in process here, so coverage sees them; one test runs the
module as a real process through the SDK's stdio client, as an assistant starts it, and
lets it start the engine service on demand.
"""

import io
import json
import sys
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp import Client, StdioServerParameters
from mcp.server import Server
from mcp.types import TextContent
from mcp_support import in_process_service

from lcsim import __version__
from lcsim.mcp import __main__ as entry
from lcsim.mcp.client import ServiceClient
from lcsim.mcp.server import INSTRUCTIONS, SERVER_NAME, build_server, main, serve_stdio
from lcsim.service.config import default_config_dir, default_data_dir
from lcsim.service.discovery import probe, read_service_file


def test_the_module_entry_point_is_main() -> None:
    assert entry.main is main


@pytest.fixture
def clients(monkeypatch: pytest.MonkeyPatch) -> list[ServiceClient]:
    """Every service client ``main`` makes."""
    made: list[ServiceClient] = []

    def make(config_dir: Path, data_dir: Path) -> ServiceClient:
        made.append(ServiceClient(config_dir, data_dir))
        return made[-1]

    monkeypatch.setattr("lcsim.mcp.server.ServiceClient", make)
    return made


def test_main_builds_a_server_for_the_folders_given_and_serves_it(
    tmp_path: Path, clients: list[ServiceClient]
) -> None:
    served: list[Server[Any]] = []

    async def serve(server: Server[Any]) -> None:
        served.append(server)

    config_dir, data_dir = tmp_path / "config", tmp_path / "data"
    status = main(["--config-dir", str(config_dir), "--data-dir", str(data_dir)], serve=serve)
    assert status == 0
    [server] = served
    assert server.name == SERVER_NAME == "lcsim"
    assert server.version == __version__
    assert server.instructions == INSTRUCTIONS
    [client] = clients
    assert (client.config_dir, client.data_dir) == (config_dir.resolve(), data_dir.resolve())


def test_main_uses_the_per_user_folders_by_default(clients: list[ServiceClient]) -> None:
    async def serve(server: Server[Any]) -> None:
        pass

    assert main([], serve=serve) == 0
    [client] = clients
    assert client.config_dir == default_config_dir().resolve()
    assert client.data_dir == default_data_dir().resolve()


def test_main_serves_over_stdio_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    served: list[Server[Any]] = []

    async def serve(server: Server[Any]) -> None:
        served.append(server)

    monkeypatch.setattr("lcsim.mcp.server.serve_stdio", serve)
    assert main(["--config-dir", "c", "--data-dir", "d"]) == 0
    assert len(served) == 1


def test_main_help_names_the_program(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as stopped:
        main(["--help"])
    assert stopped.value.code == 0
    assert "python -m lcsim.mcp" in capsys.readouterr().out


def test_serve_stdio_answers_json_rpc_lines(tmp_path: Path) -> None:
    """The stdio loop in process, with the handshake era's three messages and a list."""
    lines = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    stdin = io.StringIO("".join(json.dumps(line) + "\n" for line in lines))
    stdout = io.StringIO()
    server = build_server(ServiceClient(tmp_path / "c", tmp_path / "d"))

    async def serve() -> None:
        await serve_stdio(server, stdin=anyio.wrap_file(stdin), stdout=anyio.wrap_file(stdout))

    anyio.run(serve)
    answers = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert [answer["id"] for answer in answers] == [1, 2]
    assert answers[0]["result"]["protocolVersion"] == "2025-06-18"
    assert answers[0]["result"]["serverInfo"]["name"] == "lcsim"
    assert len(answers[1]["result"]["tools"]) == 6


def stdio_parameters(config_dir: Path, data_dir: Path) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "lcsim.mcp", "--config-dir", str(config_dir), "--data-dir", str(data_dir)],
    )


def test_python_dash_m_lcsim_mcp_starts_the_service_on_demand(tmp_path: Path) -> None:
    config_dir, data_dir = tmp_path / "config", tmp_path / "data"
    seen: dict[str, Any] = {}

    async def session() -> None:
        async with Client(stdio_parameters(config_dir, data_dir)) as mcp_client:
            listed = await mcp_client.list_tools()
            seen["tools"] = [tool.name for tool in listed.tools]
            # No service until a tool needs one.
            seen["before"] = read_service_file(config_dir)
            result = await mcp_client.call_tool("list_engines", {})
            seen["error"] = result.is_error
            [block] = result.content
            assert isinstance(block, TextContent)
            seen["engines"] = json.loads(block.text)
            seen["during"] = read_service_file(config_dir)
            projects = await mcp_client.call_tool("list_projects", {})
            seen["projects"] = projects.structured_content, projects.content

    try:
        anyio.run(session)
        assert seen["before"] is None
        assert seen["error"] is False
        assert {engine["name"] for engine in seen["engines"]} == {"highs", "simpy"}
        assert seen["during"] is not None
        # The service outlives the MCP server that started it (spec 3 "Lifetime").
        info = read_service_file(config_dir)
        assert info is not None and info == seen["during"] and probe(info)
        assert len(seen["tools"]) == 6
    finally:
        stop_started(config_dir)


def stop_started(config_dir: Path) -> None:
    """Stop the service a separate MCP server process started, found by its pid."""
    import os
    import signal
    import time

    info = read_service_file(config_dir)
    if info is None:
        return
    os.kill(info.pid, signal.SIGTERM)
    deadline = time.monotonic() + 60
    while probe(info):
        assert time.monotonic() < deadline, "the service did not stop"
        time.sleep(0.05)


def test_python_dash_m_lcsim_mcp_uses_a_running_service(tmp_path: Path) -> None:
    config_dir, data_dir = tmp_path / "config", tmp_path / "data"
    with in_process_service(config_dir, data_dir) as info:

        async def session() -> list[Any]:
            async with Client(stdio_parameters(config_dir, data_dir), mode="legacy") as client:
                result = await client.call_tool("list_templates", {})
                [block] = result.content
                assert isinstance(block, TextContent)
                return [result.is_error, json.loads(block.text)]

        assert anyio.run(session) == [False, []]
        assert read_service_file(config_dir) == info
