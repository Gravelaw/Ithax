"""Records which routes the request tests reach (AKS-114, spec 3 "Endpoints": "each row also
has at least one request test").

``install`` wraps the application that the transport of every Starlette ``TestClient``
calls (``starlette.testclient._TestClientTransport``, which carries both HTTP requests and
WebSocket sessions) in ``RecordingApp``; ``client.app`` stays the application itself, which
several tests check is a ``FastAPI``. ``RecordingApp`` passes every ASGI call through
unchanged and, when the call ends, records the route the router chose:
``(method, path template)`` for HTTP, and ``("GET", path template)`` for a WebSocket, as
spec 3's table writes its WebSocket rows.
A request counts only when the router matched it to a route that has its method, so one
refused by the hardening middleware (401, 403, a bad ``X-Client``), one to an unknown path
(404) and one with another method (405) are not counted. The route's ``path`` is the full
template (``/v1/projects/{pid}/model``), which FastAPI puts on ``scope["route"]``; were that
to change, the recorded set would no longer equal the table and the test would fail, never
pass by default; and were Starlette's transport to change, nothing would be recorded and
the test would fail the same way.

``tests/service/conftest.py`` installs the recorder for the whole session, keeps track of
whether every service test was collected, and moves the coverage test to the end of the
session. With ``LCSIM_ROUTE_RECORD`` set (the coverage test's own fallback run) the session
writes what it recorded to that file when it ends.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from starlette import testclient
from starlette.routing import WebSocketRoute
from starlette.types import ASGIApp, Receive, Scope, Send

__all__ = [
    "INCOMPLETE",
    "RECORDED",
    "RECORD_FILE_VARIABLE",
    "RecordingApp",
    "install",
    "read_record",
    "write_record",
]

#: The environment variable naming the file a fallback session writes its record to.
RECORD_FILE_VARIABLE = "LCSIM_ROUTE_RECORD"

#: The ``(method, path template)`` pairs recorded in this session.
RECORDED: set[tuple[str, str]] = set()

#: Why this session's record cannot stand for every request test (a service test module
#: not collected, a service test deselected); empty when every one runs.
INCOMPLETE: list[str] = []


def matched_route(scope: Scope) -> tuple[str, str] | None:
    """The ``(method, path template)`` the router chose for ``scope``, or ``None`` when it
    chose no route that takes the request's method."""
    route = scope.get("route")
    path = getattr(route, "path", None)
    if not isinstance(path, str):
        return None
    if scope["type"] == "websocket":
        return ("GET", path) if isinstance(route, WebSocketRoute) else None
    methods = getattr(route, "methods", None) or ()
    method = scope.get("method")
    if scope["type"] != "http" or method not in methods:
        return None
    return (str(method), path)


class RecordingApp:
    """An ASGI app that runs ``app`` and records the route of each HTTP request and
    WebSocket."""

    def __init__(self, app: ASGIApp, sink: set[tuple[str, str]]) -> None:
        self._app = app
        self._sink = sink

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await self._app(scope, receive, send)
        finally:
            if scope["type"] in ("http", "websocket"):
                route = matched_route(scope)
                if route is not None:
                    self._sink.add(route)


def install(patch: Any, sink: set[tuple[str, str]] = RECORDED) -> None:
    """Makes every ``TestClient`` created from now on record into ``sink``; ``patch`` is a
    ``pytest.MonkeyPatch``, which undoes it."""
    transport = testclient._TestClientTransport
    original: Callable[..., None] = transport.__init__

    def recording_init(self: Any, app: ASGIApp, *args: Any, **kwargs: Any) -> None:
        original(self, RecordingApp(app, sink), *args, **kwargs)

    patch.setattr(transport, "__init__", recording_init)


def write_record(path: Path, routes: set[tuple[str, str]]) -> None:
    path.write_text(json.dumps(sorted(routes)), encoding="utf-8")


def read_record(path: Path) -> set[tuple[str, str]]:
    return {(method, route) for method, route in json.loads(path.read_text(encoding="utf-8"))}
