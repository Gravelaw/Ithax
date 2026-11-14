"""``python -m ithax.mcp``: the MCP server over stdio (spec 4 "MCP server", "MCP tools" and
"How the server runs and answers"; AKS-115).

``build_server`` makes the low-level SDK ``Server`` for one ``ServiceClient``: ``tools/list``
gives each tool of ``ithax.mcp.tools.TOOLS`` with its input schema and description, and
``tools/call`` runs the named tool through ``run_tool`` in a worker thread, since the service
client blocks while it waits for the service. A tool name the server does not have is the
only protocol error (``INVALID_PARAMS``), as the MCP specification lists unknown tools; every
other failure is a tool result (``ithax.mcp.tools``). The SDK answers clients of both
protocol eras, the ``initialize`` handshake and 2026-07-28 (``docs/research/spec-4-mcp.md``).

``main`` reads ``--config-dir`` and ``--data-dir`` (the service's folders, the per-user ones
of spec 3 "Discovery" by default), makes the client and serves stdio until the assistant
closes the stream. The service is not started until a tool needs it.
"""

from __future__ import annotations

import argparse
import functools
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

import anyio
import anyio.to_thread
from mcp import MCPError
from mcp.server import Server, ServerRequestContext
from mcp.server.stdio import stdio_server
from mcp.types import (
    INVALID_PARAMS,
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
)

from ithax import __version__
from ithax.mcp.client import ServiceClient
from ithax.mcp.tools import TOOLS, ToolSpec, run_tool
from ithax.service.config import default_config_dir, default_data_dir

__all__ = ["INSTRUCTIONS", "SERVER_NAME", "build_server", "main", "serve_stdio"]

#: The server's name in the MCP handshake and discovery.
SERVER_NAME = "lcsim"

#: What the server tells a connecting assistant about all its tools.
INSTRUCTIONS = (
    "lcsim builds and runs simulation and optimization models. Every tool calls the local "
    "lcsim engine service, which this server starts when needed. Results are JSON. A "
    "result marked as an error holds {error: {code, message}, issues}: each issue has a "
    "code, a path, a message and a hint saying how to fix it; read them and correct the "
    "call or the model rather than giving up."
)

Serve = Callable[[Server[Any]], Awaitable[None]]


def build_server(client: ServiceClient, tools: Sequence[ToolSpec] = TOOLS) -> Server[Any]:
    """The MCP server whose tools are ``tools``, each calling the service through
    ``client``."""
    by_name = {spec.name: spec for spec in tools}
    listed = ListToolsResult(tools=[spec.tool() for spec in tools])

    async def list_tools(
        ctx: ServerRequestContext[Any], params: PaginatedRequestParams | None
    ) -> ListToolsResult:
        return listed

    async def call_tool(
        ctx: ServerRequestContext[Any], params: CallToolRequestParams
    ) -> CallToolResult:
        spec = by_name.get(params.name)
        if spec is None:
            raise MCPError(INVALID_PARAMS, f"Unknown tool: {params.name}")
        call = functools.partial(run_tool, spec, client, params.arguments)
        return await anyio.to_thread.run_sync(call)

    return Server(
        SERVER_NAME,
        version=__version__,
        instructions=INSTRUCTIONS,
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


async def serve_stdio(
    server: Server[Any],
    stdin: anyio.AsyncFile[str] | None = None,
    stdout: anyio.AsyncFile[str] | None = None,
) -> None:
    """Serve ``server`` over the process's standard streams (or the ones given) until
    the input ends."""
    async with stdio_server(stdin, stdout) as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def _arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m ithax.mcp",
        description=(
            "Serve the lcsim MCP tools over stdio; the engine service is started when a "
            "tool needs it."
        ),
    )
    parser.add_argument("--config-dir", type=Path, help="the service's configuration folder")
    parser.add_argument("--data-dir", type=Path, help="the service's user data folder")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None, *, serve: Serve | None = None) -> int:
    """Serve the MCP tools until the assistant closes the stream; return the exit status.
    ``serve`` replaces the stdio loop (tests)."""
    arguments = _arguments(argv)
    client = ServiceClient(
        arguments.config_dir or default_config_dir(), arguments.data_dir or default_data_dir()
    )
    anyio.run(serve or serve_stdio, build_server(client))
    return 0
