"""Helpers for the MCP server tests (spec 4 "MCP tools"; AKS-115).

This folder has no ``__init__.py`` and no ``conftest.py``: a package named ``mcp`` here would
shadow the MCP SDK, and a second top-level ``conftest`` module would clash with the one in
``tests/engines/process``. Test modules import these helpers by name.

- ``in_process_service``: the real M6 application served by uvicorn on ``127.0.0.1`` in a
  thread, with ``service.json`` written in a temporary configuration folder, as a real
  service writes it, so the MCP server finds it the way it finds any service.
- ``StubService``: a stand-in HTTP server that answers the spec 3 probe and replays scripted
  answers, recording every other request with its headers, for what a real service cannot
  show (the headers sent, a refused connection, a stale token, an answer that is not JSON).
- ``stop_service``: stops a service the MCP server started as a process, so no test leaves
  one running.
- ``run``, ``payload``, ``spec_4_tool_rows``: drive a server through the SDK's in-memory
  client, read a result's JSON, and read spec 4's "MCP tools" table (AKS-115; shared with
  the write and run tools of AKS-134).
"""

from __future__ import annotations

import contextlib
import json
import re
import subprocess
import sys
import threading
import time
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import anyio
import uvicorn
from mcp import Client
from mcp.types import CallToolResult, TextContent

from lcsim.mcp.client import ServiceClient
from lcsim.mcp.server import build_server
from lcsim.service.app import create_app
from lcsim.service.config import ServiceConfig, new_token
from lcsim.service.discovery import (
    ServiceInfo,
    probe,
    read_service_file,
    remove_service_file,
    write_service_file,
)
from lcsim.service.hardware import Hardware
from lcsim.service.main import bind_local

TIMEOUT_S = 60.0

ROOT = Path(__file__).resolve().parents[2]
SPEC_4 = ROOT / "docs" / "specs" / "4-content-and-ai.md"

#: A start command that fails at once, for clients that must find a running service.
NO_START = [sys.executable, "-c", "raise SystemExit(3)"]


def spec_4_tool_rows() -> dict[str, tuple[str, list[tuple[str, str]]]]:
    """The "MCP tools" table of spec 4, in its row order: tool name to its Input cell and
    the endpoints of its Calls cell."""
    text = SPEC_4.read_text(encoding="utf-8")
    section = text[text.index("### MCP tools") : text.index("Behaviour an assistant can rely on")]
    rows: dict[str, tuple[str, list[tuple[str, str]]]] = {}
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        match = re.fullmatch(r"`(\w+)`", cells[0]) if len(cells) == 4 else None
        if match:
            calls = re.findall(r"`(GET|POST|PUT|DELETE) (/v1/[^`?]*)", cells[3])
            rows[match.group(1)] = (cells[1], calls)
    return rows


def run(test: Callable[[Client], Awaitable[None]], client: ServiceClient, **options: Any) -> None:
    """Run ``test`` with an in-memory MCP client connected to a server for ``client``."""

    async def main() -> None:
        async with Client(build_server(client), **options) as mcp_client:
            await test(mcp_client)

    anyio.run(main)


def payload(result: CallToolResult) -> Any:
    """The JSON a result carries in its one text block; also its structured content when
    that is an object."""
    [block] = result.content
    assert isinstance(block, TextContent)
    value = json.loads(block.text)
    if isinstance(value, dict):
        assert result.structured_content == value
    else:
        assert result.structured_content is None
    return value


def wait_until(condition: Callable[[], object], timeout_s: float = TIMEOUT_S) -> None:
    deadline = time.monotonic() + timeout_s
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.02)


@contextlib.contextmanager
def in_process_service(config_dir: Path, data_dir: Path) -> Iterator[ServiceInfo]:
    """The M6 application served on a port the operating system chose, with
    ``service.json`` naming it; stopped and its file removed on exit."""
    sock = bind_local()
    port = sock.getsockname()[1]
    config = ServiceConfig(
        config_dir=config_dir,
        data_dir=data_dir,
        port=port,
        token=new_token(),
        hardware=Hardware(cores=4, memory=8 * 1024**3, graphics=None),
    )
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(config), ws="websockets-sansio", lifespan="on", log_level="warning"
        )
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    info = ServiceInfo(port=port, token=config.token, pid=0, started="2026-11-08T00:00:00Z")
    try:
        wait_until(lambda: server.started)
        write_service_file(config.config_dir, info)
        yield info
    finally:
        server.should_exit = True
        thread.join(TIMEOUT_S)
        sock.close()
        remove_service_file(config.config_dir, info)


@dataclass(frozen=True)
class Recorded:
    """One request the stub received (the probes are counted, not recorded)."""

    method: str
    path: str
    headers: dict[str, str]
    body: bytes


#: A scripted answer that closes the connection without sending a response.
DROP = "drop"

#: A scripted answer that sends a 404 whose body stops short of its ``Content-Length``.
TRUNCATED = "truncated"


@dataclass
class StubService:
    """An HTTP server on ``127.0.0.1`` that answers ``GET /v1/system`` with 200 when the
    token is right and every other request with the next scripted answer (``200`` and
    ``{}`` when none is left), or drops it for ``DROP``. When ``respond`` is set, it
    answers every request but the probe instead, from the request (AKS-134)."""

    config_dir: Path
    token: str = "stub-token-0123456789"
    answers: list[tuple[int, bytes, dict[str, str]] | str] = field(default_factory=list)
    requests: list[Recorded] = field(default_factory=list)
    probes: int = 0
    respond: Callable[[Recorded], tuple[int, bytes, dict[str, str]]] | None = None
    _server: ThreadingHTTPServer | None = None
    _thread: threading.Thread | None = None

    def start(self) -> ServiceInfo:
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                pass

            def _answer(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                if self.path == "/v1/system":
                    stub.probes += 1
                    ok = self.headers.get("Authorization") == f"Bearer {stub.token}"
                    self._send(200 if ok else 401, b"{}", {})
                    return
                recorded = Recorded(self.command, self.path, dict(self.headers), body)
                stub.requests.append(recorded)
                if stub.respond is not None:
                    self._send(*stub.respond(recorded))
                    return
                answer = stub.answers.pop(0) if stub.answers else (200, b"{}", {})
                if answer == DROP:
                    self.close_connection = True
                    return
                if answer == TRUNCATED:
                    self.close_connection = True
                    self.send_response(404)
                    self.send_header("Content-Length", "100")
                    self.end_headers()
                    self.wfile.write(b'{"err')
                    return
                assert not isinstance(answer, str)
                self._send(*answer)

            def _send(self, status: int, body: bytes, headers: dict[str, str]) -> None:
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = do_POST = do_PUT = do_DELETE = _answer

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        info = ServiceInfo(
            port=self._server.server_address[1],
            token=self.token,
            pid=0,
            started="2026-11-08T00:00:00Z",
        )
        write_service_file(self.config_dir, info)
        return info

    def answer(self, status: int, body: object, headers: dict[str, str] | None = None) -> None:
        """Queue an answer whose body is ``body`` as JSON, or as it is when bytes."""
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.answers.append((status, raw, headers or {}))

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            assert self._thread is not None
            self._thread.join(TIMEOUT_S)
            self._server = None


def stop_service(config_dir: Path, process: subprocess.Popen[bytes] | None) -> None:
    """Stop the service ``process`` (one the MCP server started) and wait until it has
    ended and no longer answers.

    It is not asserted that its ``service.json`` is gone: on SIGTERM uvicorn shuts the
    service down and then raises the signal again, which ends the process before
    ``lcsim.service.main`` removes the file (found by AKS-115; the MCP server copes, since
    the probe of a stale file fails and a new service overwrites it)."""
    if process is None:
        return
    info = read_service_file(config_dir)
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(TIMEOUT_S)
    except subprocess.TimeoutExpired:  # pragma: no cover - only when the test fails
        process.kill()
        process.wait(TIMEOUT_S)
    if info is not None and info.pid == process.pid:
        assert not probe(info), "the service still answers"
