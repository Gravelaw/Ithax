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
template (``/v1/projects/{pid}/model``), which FastAPI puts on ``scope["route"]``, written
as the table writes it (``ithax.service.app.table_path``: ``{path:path}`` is ``{path}``); were that
to change, the recorded set would no longer equal the table and the test would fail, never
pass by default; and were Starlette's transport to change, nothing would be recorded and
the test would fail the same way.

``tests/service/conftest.py`` installs the recorder for the whole session, keeps track of
whether every service test was collected, and moves the coverage test to the end of the
session. With ``ITHAX_ROUTE_RECORD`` set (the coverage test's own fallback run) the session
writes what it recorded to that file when it ends.

Under pytest-xdist (#99, P1) each worker records only its own requests. The controller (the
plugin ``tests/xdist_routes.py``) gives every worker a folder, ``workerinput[RECORD_DIR_KEY]``;
each worker writes its record there when its session ends (``write_worker_record``), noting
whether its coverage test handed the check over (``DEFERRED``), and the controller checks the
union once every worker has finished (``read_worker_records``).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from starlette import testclient
from starlette.routing import WebSocketRoute
from starlette.types import ASGIApp, Receive, Scope, Send

from ithax.service.app import table_path
from xdist_routes import RECORD_DIR_KEY

__all__ = [
    "DEFERRED",
    "INCOMPLETE",
    "RECORDED",
    "RECORD_DIR_KEY",
    "RECORD_FILE_VARIABLE",
    "RecordingApp",
    "install",
    "read_record",
    "read_worker_records",
    "write_record",
    "write_worker_record",
]

#: The environment variable naming the file a fallback session writes its record to.
RECORD_FILE_VARIABLE = "ITHAX_ROUTE_RECORD"

#: The ``(method, path template)`` pairs recorded in this session.
RECORDED: set[tuple[str, str]] = set()


#: The coverage tests of this session that handed their check to the controller.
DEFERRED: list[str] = []

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
    path = table_path(path)
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


def write_worker_record(
    folder: Path, worker: str, routes: set[tuple[str, str]], deferred: list[str]
) -> None:
    """Writes one pytest-xdist worker's record into the controller's ``folder``."""
    record = {"routes": sorted(routes), "deferred": deferred}
    (folder / f"{worker}.json").write_text(json.dumps(record), encoding="utf-8")


def read_worker_records(folder: Path) -> tuple[int, set[tuple[str, str]], list[str]]:
    """The number of worker records in ``folder``, the union of their routes, and every
    coverage test that handed its check over."""
    routes: set[tuple[str, str]] = set()
    deferred: list[str] = []
    files = sorted(folder.glob("*.json"))
    for path in files:
        record = json.loads(path.read_text(encoding="utf-8"))
        routes |= {(method, route) for method, route in record["routes"]}
        deferred.extend(record["deferred"])
    return len(files), routes, deferred
