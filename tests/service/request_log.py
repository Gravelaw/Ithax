"""A request log taken at the service, for spec 3's acceptance row "Every interface action is
reproducible by API: the end-to-end request log contains only documented `/v1` routes"
(AKS-121).

``RequestLog`` wraps the whole application, outside the hardening middleware, so every HTTP
request and WebSocket that reaches the service is logged, whatever sent it and whatever the
answer: one JSON line per call, ``{type, method, path, status, route, client}``, appended to
a file when the call ends. ``route`` is the ``[method, path template]`` the router matched,
as spec 3's endpoint table writes it (``route_recorder.matched_route``), or ``null`` when it
matched none (a 401 or 403 from the hardening rules, an unknown path, another method);
``status`` is the HTTP status, ``101`` for an accepted WebSocket and ``403`` for one closed
before it was accepted; ``client`` is the ``X-Client`` header, or ``null``.

The log is a test's, never the product's: ``logged_service.py`` starts the service of
``python -m lcsim.service`` with it, and the pointer-only end-to-end test
(``ui/e2e/pointer-only.spec.ts``) starts that. ``python tests/service/request_log.py <log>``
checks a log: every call must have matched a row of the endpoint table, read from spec 3 as
``tests/service/test_routes.py`` reads it, and none may have been answered with a status of
400 or above (a 404 among them). It prints what it found as JSON and exits 1 on any problem
or an empty log.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.route_recorder import matched_route

__all__ = ["LOG_FILE_VARIABLE", "RequestLog", "check", "main", "read_log"]

#: The environment variable naming the log file of ``logged_service.py``.
LOG_FILE_VARIABLE = "LCSIM_TEST_REQUEST_LOG"


def _client(scope: Scope) -> str | None:
    for name, value in scope.get("headers", ()):
        if name.lower() == b"x-client":
            return bytes(value).decode("latin-1")
    return None


class RequestLog:
    """An ASGI app that runs ``app`` and appends one line per HTTP request or WebSocket to
    ``path``."""

    def __init__(self, app: ASGIApp, path: Path) -> None:
        self._app = app
        self._path = path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return
        status: int | None = None

        async def sending(message: Message) -> None:
            nonlocal status
            if status is None:
                kind = message["type"]
                if kind in ("http.response.start", "websocket.http.response.start"):
                    status = int(message["status"])
                elif kind == "websocket.accept":
                    status = 101
                elif kind == "websocket.close":
                    status = 403
            await send(message)

        try:
            await self._app(scope, receive, sending)
        finally:
            route = matched_route(scope)
            entry = {
                "type": scope["type"],
                "method": scope.get("method", "GET"),
                "path": scope["path"],
                "status": status,
                "route": None if route is None else list(route),
                "client": _client(scope),
            }
            with self._path.open("a", encoding="utf-8") as log:
                log.write(json.dumps(entry) + "\n")


def read_log(path: Path) -> list[dict[str, Any]]:
    """The entries of the log at ``path``, in the order the calls ended."""
    text = path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line]


def check(entries: Iterable[dict[str, Any]], table: set[tuple[str, str]]) -> dict[str, Any]:
    """What ``entries`` show against ``table``: the count, the calls per route and per
    client, and the problems (a call that matched no row of the table, or answered with no
    status or a status of 400 or above)."""
    entries = list(entries)
    problems: list[str] = []
    routes: Counter[str] = Counter()
    clients: Counter[str] = Counter()
    for entry in entries:
        call = f"{entry['method']} {entry['path']} -> {entry['status']}"
        route = entry["route"]
        if route is None or (route[0], route[1]) not in table:
            problems.append(f"{call}: not a route of spec 3's endpoint table")
        else:
            routes[f"{route[0]} {route[1]}"] += 1
        status = entry["status"]
        if status is None or status >= 400:
            problems.append(f"{call}: refused or unanswered")
        clients[str(entry["client"])] += 1
    if not entries:
        problems.append("the log is empty")
    return {
        "requests": len(entries),
        "clients": dict(sorted(clients.items())),
        "routes": dict(sorted(routes.items())),
        "problems": problems,
    }


def main(argv: Sequence[str]) -> int:
    """Checks the log named by ``argv[0]`` against spec 3's endpoint table."""
    from service.test_routes import spec_table

    found = check(read_log(Path(argv[0])), spec_table())
    print(json.dumps(found, indent=2))
    return 1 if found["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
