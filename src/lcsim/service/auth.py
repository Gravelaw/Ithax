"""The token, the hardening rules and the client header (spec 3 "Service rules").

``Hardening`` is ASGI middleware around the whole application. For every HTTP request and
WebSocket upgrade it checks, in this order:

1. ``Host`` is ``127.0.0.1:<port>`` or ``localhost:<port>``, else 403 with E183;
2. for a WebSocket, an ``Origin``, when present, is one of the allowed origins (none until
   M9), else the upgrade is refused before it is accepted (the server answers 403);
3. for HTTP, ``Authorization: Bearer <token>`` carries the service's token, else 401 with
   E182 and ``WWW-Authenticate: Bearer``.

It also keeps the lifetime's account: an HTTP request and an open WebSocket each hold the
service. No CORS headers are ever added.

WebSockets cannot carry headers from a webview, so a WebSocket route calls
``authenticate_websocket`` first: it accepts the connection and waits for the first text
message ``{"token": "..."}``; none within the time limit (5 s), or a wrong one, closes the
connection with 1008 and the reason ``E182``.

``request_client`` reads ``X-Client`` (``ui``, ``mcp`` or ``script``; ``script`` when
absent; another value is 400 with E184).
"""

from __future__ import annotations

import asyncio
import json
import secrets
from typing import Literal, get_args

from starlette.datastructures import Headers
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocket, WebSocketDisconnect

from lcsim.model.issues import Issue
from lcsim.service.errors import REFUSED, TOKEN, error_response, malformed
from lcsim.service.lifetime import Lifetime

__all__ = [
    "CLIENTS",
    "POLICY_VIOLATION",
    "Client",
    "Hardening",
    "authenticate_websocket",
    "bearer_token",
    "host_allowed",
    "request_client",
    "token_matches",
]

#: The WebSocket close code for a connection without the token (RFC 6455: policy
#: violation).
POLICY_VIOLATION = 1008

Client = Literal["ui", "mcp", "script"]

#: Spec 3 "Client header": the values of ``X-Client``.
CLIENTS: tuple[Client, ...] = get_args(Client)

_LOCAL_HOSTS = ("127.0.0.1", "localhost")


def host_allowed(host: str | None, port: int) -> bool:
    """Whether a ``Host`` header names this service: ``127.0.0.1:<port>`` or
    ``localhost:<port>`` (the name in any letter case)."""
    if host is None:
        return False
    name, separator, given_port = host.rpartition(":")
    return bool(separator) and name.lower() in _LOCAL_HOSTS and given_port == str(port)


def bearer_token(authorization: str | None) -> str | None:
    """The token of an ``Authorization: Bearer <token>`` header (the scheme in any letter
    case), or ``None``."""
    if authorization is None:
        return None
    scheme, _, token = authorization.strip().partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def token_matches(given: str | None, expected: str) -> bool:
    """Whether ``given`` is the service's token, compared in constant time."""
    if given is None:
        return False
    return secrets.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


class Hardening:
    """ASGI middleware applying the ``Host``, ``Origin`` and token rules, and holding the
    lifetime for each request and WebSocket."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        port: int,
        token: str,
        allowed_origins: frozenset[str],
        lifetime: Lifetime,
    ) -> None:
        self.app = app
        self.port = port
        self.token = token
        self.allowed_origins = allowed_origins
        self.lifetime = lifetime

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        kind = scope["type"]
        if kind not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        if not host_allowed(headers.get("host"), self.port):
            await self._refuse(
                scope,
                receive,
                send,
                f"The request names the host '{headers.get('host', '')}'; this service "
                f"answers only 127.0.0.1:{self.port} and localhost:{self.port}.",
            )
            return
        if kind == "websocket":
            origin = headers.get("origin")
            if origin is not None and origin not in self.allowed_origins:
                await self._refuse(scope, receive, send, "")
                return
            with self.lifetime.hold():
                await self.app(scope, receive, send)
            return
        if not token_matches(bearer_token(headers.get("authorization")), self.token):
            response = error_response(
                401,
                TOKEN,
                "The request has no token, or not this service's token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return
        with self.lifetime.hold():
            await self.app(scope, receive, send)

    @staticmethod
    async def _refuse(scope: Scope, receive: Receive, send: Send, message: str) -> None:
        if scope["type"] == "websocket":
            # Closing before accepting refuses the upgrade; the server answers 403.
            await WebSocket(scope, receive, send).close(code=POLICY_VIOLATION, reason=REFUSED)
            return
        await error_response(403, REFUSED, message)(scope, receive, send)


async def authenticate_websocket(websocket: WebSocket, token: str, timeout_s: float) -> bool:
    """Accept ``websocket`` and check its first message, ``{"token": "..."}``.

    Returns ``True`` when the token is the service's. Otherwise, or when no text message
    arrives within ``timeout_s`` seconds, closes the connection with 1008 and the reason
    ``E182`` and returns ``False``; a client that leaves first also gives ``False``.
    """
    await websocket.accept()
    try:
        text = await asyncio.wait_for(websocket.receive_text(), timeout_s)
    except TimeoutError:
        text = None
    except WebSocketDisconnect:
        return False
    except KeyError:
        # A binary frame: Starlette's receive_text finds no "text" in the message.
        text = None
    given: str | None = None
    if text is not None:
        try:
            message = json.loads(text)
        except ValueError:
            message = None
        if isinstance(message, dict) and isinstance(message.get("token"), str):
            given = message["token"]
    if token_matches(given, token):
        return True
    await websocket.close(code=POLICY_VIOLATION, reason=TOKEN)
    return False


def request_client(connection: HTTPConnection) -> Client:
    """The ``X-Client`` of a request: ``ui``, ``mcp`` or ``script``, and ``script`` when
    the header is absent. Another value raises 400 with E184."""
    value = connection.headers.get("x-client")
    if value is None:
        return "script"
    if value in CLIENTS:
        return value
    raise malformed(
        [
            Issue(
                code="E184",
                component=None,
                path="",
                message=f"The X-Client header is '{value}', which is not ui, mcp or script.",
                hint="Send X-Client: ui, mcp or script, or leave the header out.",
            )
        ]
    )
