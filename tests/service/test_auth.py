"""The token, the hardening rules, the WebSocket token message and ``X-Client``
(spec 3 "Service rules"; AKS-110 acceptance: 401 without token, WebSocket closed with 1008
without a token message, Host and Origin rejection)."""

import dataclasses
import json
import time

import pytest
from fastapi import FastAPI, Request
from starlette.testclient import TestClient
from starlette.websockets import WebSocket, WebSocketDisconnect

from ithax.service.app import create_app
from ithax.service.auth import (
    CLIENTS,
    POLICY_VIOLATION,
    authenticate_websocket,
    bearer_token,
    host_allowed,
    origin_allowed,
    request_client,
    token_matches,
)
from ithax.service.config import ServiceConfig
from service.service_support import AUTH, BASE_URL, PORT, TOKEN, WS_URL, assert_error

# --- HTTP: the token ----------------------------------------------------------------


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer wrong-token"},
        {"Authorization": f"Basic {TOKEN}"},
        {"Authorization": "Bearer"},
        {"Authorization": TOKEN},
    ],
    ids=["none", "wrong", "other-scheme", "empty", "no-scheme"],
)
def test_a_request_without_the_token_is_401_with_e182(
    app: FastAPI, headers: dict[str, str]
) -> None:
    with TestClient(app, base_url=BASE_URL) as client:
        response = client.get("/v1/system", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert_error(response.json(), "E182")
    assert response.json()["issues"] == []


def test_every_route_needs_the_token_even_an_unknown_one(app: FastAPI) -> None:
    with TestClient(app, base_url=BASE_URL) as client:
        for method, path in [
            ("GET", "/v1/system"),
            ("GET", "/v1/engines"),
            ("GET", "/v1/schema"),
            ("GET", "/v1/projects"),
            ("POST", "/v1/projects"),
            ("GET", "/v1/nothing"),
        ]:
            assert client.request(method, path).status_code == 401, path


def test_the_scheme_may_be_written_in_any_case(app: FastAPI) -> None:
    with TestClient(app, base_url=BASE_URL) as client:
        response = client.get("/v1/system", headers={"Authorization": f"bearer {TOKEN}"})
    assert response.status_code == 200


def test_bearer_token_reads_the_header() -> None:
    assert bearer_token(f"Bearer {TOKEN}") == TOKEN
    assert bearer_token(f"  BEARER   {TOKEN} ") == TOKEN
    assert bearer_token(None) is None
    assert bearer_token("Bearer ") is None
    assert bearer_token(f"Token {TOKEN}") is None


def test_token_matches_compares_exactly() -> None:
    assert token_matches(TOKEN, TOKEN)
    assert not token_matches(TOKEN + "x", TOKEN)
    assert not token_matches(None, TOKEN)
    assert not token_matches("", TOKEN)


# --- HTTP: the Host check -------------------------------------------------------------


@pytest.mark.parametrize(
    "host",
    [
        "evil.example",
        f"evil.example:{PORT}",
        "127.0.0.1",
        "localhost",
        f"127.0.0.1:{PORT + 1}",
        f"192.168.1.5:{PORT}",
        f"[::1]:{PORT}",
        "",
    ],
)
def test_a_request_with_another_host_is_403_with_e183(app: FastAPI, host: str) -> None:
    with TestClient(app, base_url=BASE_URL, headers=AUTH) as client:
        response = client.get("/v1/system", headers={"Host": host})
    assert response.status_code == 403
    assert_error(response.json(), "E183")


def test_the_host_is_checked_before_the_token(app: FastAPI) -> None:
    with TestClient(app, base_url="http://evil.example") as client:
        response = client.get("/v1/system")
    assert response.status_code == 403
    assert_error(response.json(), "E183")


@pytest.mark.parametrize("host", [f"127.0.0.1:{PORT}", f"localhost:{PORT}", f"LocalHost:{PORT}"])
def test_both_local_names_with_the_port_are_allowed(app: FastAPI, host: str) -> None:
    with TestClient(app, base_url=BASE_URL, headers=AUTH) as client:
        assert client.get("/v1/system", headers={"Host": host}).status_code == 200


def test_host_allowed() -> None:
    assert host_allowed(f"127.0.0.1:{PORT}", PORT)
    assert host_allowed(f"localhost:{PORT}", PORT)
    assert not host_allowed(None, PORT)
    assert not host_allowed("127.0.0.1", PORT)
    assert not host_allowed(f"127.0.0.2:{PORT}", PORT)
    assert not host_allowed(f"127.0.0.1:0{PORT}", PORT)


# --- no CORS --------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["GET", "OPTIONS"])
def test_no_cors_headers_are_sent(client: TestClient, method: str) -> None:
    headers = {
        "Origin": "http://evil.example",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization",
    }
    for with_token in (True, False):
        sent = dict(headers)
        if not with_token:
            sent["Authorization"] = ""
        response = client.request(method, "/v1/system", headers=sent)
        assert not [name for name in response.headers if name.lower().startswith("access-control")]


# --- WebSocket: Host, Origin and the token message -----------------------------------
# Starlette's TestClient joins a WebSocket URL with ws://testserver, not with base_url,
# so every WebSocket test names the service's own address in full.


def websocket_app(config: ServiceConfig) -> FastAPI:
    """The product app plus a test-only WebSocket route that uses the token helper."""
    app = create_app(config)

    @app.websocket("/v1/test/socket")
    async def socket(websocket: WebSocket) -> None:
        if await authenticate_websocket(websocket, config.token, config.websocket_auth_timeout_s):
            await websocket.send_json({"type": "hello"})
            await websocket.close()

    return app


@pytest.fixture
def quick(config: ServiceConfig) -> ServiceConfig:
    return dataclasses.replace(config, websocket_auth_timeout_s=0.2)


def test_a_websocket_with_the_token_message_is_served(quick: ServiceConfig) -> None:
    with TestClient(websocket_app(quick), base_url=BASE_URL) as client:
        with client.websocket_connect(f"{WS_URL}/v1/test/socket") as socket:
            socket.send_text(json.dumps({"token": TOKEN}))
            assert socket.receive_json() == {"type": "hello"}


def test_a_websocket_without_a_token_message_is_closed_with_1008(quick: ServiceConfig) -> None:
    with TestClient(websocket_app(quick), base_url=BASE_URL) as client:
        with client.websocket_connect(f"{WS_URL}/v1/test/socket") as socket:
            started = time.monotonic()
            with pytest.raises(WebSocketDisconnect) as closed:
                socket.receive_text()
    assert closed.value.code == POLICY_VIOLATION == 1008
    assert closed.value.reason == "E182"
    assert time.monotonic() - started < 2


@pytest.mark.parametrize(
    "message",
    [
        json.dumps({"token": "wrong"}),
        json.dumps({"token": 5}),
        json.dumps([TOKEN]),
        "not json",
        TOKEN,
    ],
    ids=["wrong", "not-text", "array", "not-json", "bare-token"],
)
def test_a_websocket_with_a_wrong_token_message_is_closed_with_1008(
    quick: ServiceConfig, message: str
) -> None:
    with TestClient(websocket_app(quick), base_url=BASE_URL) as client:
        with client.websocket_connect(f"{WS_URL}/v1/test/socket") as socket:
            socket.send_text(message)
            with pytest.raises(WebSocketDisconnect) as closed:
                socket.receive_text()
    assert closed.value.code == 1008
    assert closed.value.reason == "E182"


def test_a_binary_first_message_is_closed_with_1008(quick: ServiceConfig) -> None:
    with TestClient(websocket_app(quick), base_url=BASE_URL) as client:
        with client.websocket_connect(f"{WS_URL}/v1/test/socket") as socket:
            socket.send_bytes(json.dumps({"token": TOKEN}).encode())
            with pytest.raises(WebSocketDisconnect) as closed:
                socket.receive_text()
    assert closed.value.code == 1008


def test_a_client_that_leaves_before_its_token_ends_the_helper(quick: ServiceConfig) -> None:
    results: list[bool] = []
    app = create_app(quick)

    @app.websocket("/v1/test/leaving")
    async def leaving(websocket: WebSocket) -> None:
        results.append(await authenticate_websocket(websocket, TOKEN, 5.0))

    with TestClient(app, base_url=BASE_URL) as client:
        with client.websocket_connect(f"{WS_URL}/v1/test/leaving") as socket:
            socket.close()
    assert results == [False]


def test_a_websocket_with_an_origin_is_refused_before_it_is_accepted(
    quick: ServiceConfig,
) -> None:
    with TestClient(websocket_app(quick), base_url=BASE_URL) as client:
        with pytest.raises(WebSocketDisconnect) as refused:
            with client.websocket_connect(
                f"{WS_URL}/v1/test/socket", headers={"Origin": "http://evil.example"}
            ):
                pass  # pragma: no cover - the upgrade is refused
    assert refused.value.code == 1008
    assert refused.value.reason == "E183"


def test_an_allowed_origin_passes(quick: ServiceConfig) -> None:
    allowed = dataclasses.replace(quick, allowed_origins=frozenset({"tauri://localhost"}))
    with TestClient(websocket_app(allowed), base_url=BASE_URL) as client:
        with client.websocket_connect(
            f"{WS_URL}/v1/test/socket", headers={"Origin": "tauri://localhost"}
        ) as socket:
            socket.send_text(json.dumps({"token": TOKEN}))
            assert socket.receive_json() == {"type": "hello"}


@pytest.mark.parametrize(
    "origin",
    [f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}", f"http://LocalHost:{PORT}"],
)
def test_the_interface_s_own_origin_passes(quick: ServiceConfig, origin: str) -> None:
    """Spec 3 "Hardening" (AKS-119): the interface is served by the service, so its origin
    is the service's own."""
    with TestClient(websocket_app(quick), base_url=BASE_URL) as client:
        with client.websocket_connect(
            f"{WS_URL}/v1/test/socket", headers={"Origin": origin}
        ) as socket:
            socket.send_text(json.dumps({"token": TOKEN}))
            assert socket.receive_json() == {"type": "hello"}


@pytest.mark.parametrize(
    "origin",
    [
        f"http://127.0.0.1:{PORT + 1}",
        f"https://127.0.0.1:{PORT}",
        f"http://127.0.0.2:{PORT}",
        "http://127.0.0.1",
        f"http://127.0.0.1:{PORT}/",
        f"ws://127.0.0.1:{PORT}",
        "null",
        "",
    ],
)
def test_another_origin_is_refused(quick: ServiceConfig, origin: str) -> None:
    with TestClient(websocket_app(quick), base_url=BASE_URL) as client:
        with pytest.raises(WebSocketDisconnect) as refused:
            with client.websocket_connect(f"{WS_URL}/v1/test/socket", headers={"Origin": origin}):
                pass  # pragma: no cover - the upgrade is refused
    assert refused.value.reason == "E183"


@pytest.mark.parametrize(
    ("origin", "allowed"),
    [
        (f"http://127.0.0.1:{PORT}", True),
        (f"http://LOCALHOST:{PORT}", True),
        (f"HTTP://localhost:{PORT}", False),
        (f"http://localhost:0{PORT}", False),
        (f"http://user@localhost:{PORT}", False),
        (None, False),
    ],
)
def test_origin_allowed_names_only_the_service_s_own_origin(
    origin: str | None, allowed: bool
) -> None:
    assert origin_allowed(origin, PORT) is allowed


# --- The interface's files need no token ---------------------------------------------


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_the_interface_s_files_need_no_token(app: FastAPI, method: str) -> None:
    with TestClient(app, base_url=BASE_URL) as client:
        response = client.request(method, "/v1/ui/index.html")
    # No interface folder in this config: not found, not refused for want of a token.
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("method", "path"),
    [("POST", "/v1/ui/index.html"), ("GET", "/v1/ui"), ("GET", "/v1/uix/a"), ("GET", "/ui/a")],
)
def test_only_reads_under_v1_ui_skip_the_token(app: FastAPI, method: str, path: str) -> None:
    with TestClient(app, base_url=BASE_URL) as client:
        response = client.request(method, path)
    assert response.status_code == 401
    assert_error(response.json(), "E182")


def test_the_interface_s_files_keep_the_host_check(app: FastAPI) -> None:
    with TestClient(app, base_url="http://evil.example") as client:
        response = client.get("/v1/ui/index.html")
    assert response.status_code == 403
    assert_error(response.json(), "E183")


def test_a_websocket_with_another_host_is_refused(quick: ServiceConfig) -> None:
    with TestClient(websocket_app(quick), base_url=BASE_URL) as client:
        with pytest.raises(WebSocketDisconnect) as refused:
            with client.websocket_connect("ws://evil.example/v1/test/socket"):
                pass  # pragma: no cover - the upgrade is refused
    assert refused.value.reason == "E183"


def test_an_open_websocket_holds_the_lifetime(quick: ServiceConfig) -> None:
    app = websocket_app(quick)
    lifetime = app.state.service.lifetime
    with TestClient(app, base_url=BASE_URL) as client:
        with client.websocket_connect(f"{WS_URL}/v1/test/socket") as socket:
            assert lifetime.holds == 1
            socket.send_text(json.dumps({"token": TOKEN}))
            socket.receive_json()
    assert lifetime.holds == 0


# --- X-Client ---------------------------------------------------------------------------


def client_app(config: ServiceConfig) -> FastAPI:
    app = create_app(config)

    @app.get("/v1/test/client")
    def which(request: Request) -> dict[str, str]:
        return {"client": request_client(request)}

    return app


@pytest.mark.parametrize("value", CLIENTS)
def test_x_client_is_read(config: ServiceConfig, value: str) -> None:
    with TestClient(client_app(config), base_url=BASE_URL, headers=AUTH) as client:
        assert client.get("/v1/test/client", headers={"X-Client": value}).json() == {
            "client": value
        }


def test_a_request_without_x_client_is_a_script(config: ServiceConfig) -> None:
    with TestClient(client_app(config), base_url=BASE_URL, headers=AUTH) as client:
        assert client.get("/v1/test/client").json() == {"client": "script"}


def test_another_x_client_is_400_with_e184(config: ServiceConfig) -> None:
    with TestClient(client_app(config), base_url=BASE_URL, headers=AUTH) as client:
        response = client.get("/v1/test/client", headers={"X-Client": "browser"})
    assert response.status_code == 400
    assert_error(response.json(), "E184")
    assert "'browser'" in response.json()["issues"][0]["message"]


@pytest.mark.parametrize(("method", "path"), [("GET", "/v1/system"), ("POST", "/v1/projects")])
def test_every_product_route_refuses_another_x_client(
    client: TestClient, method: str, path: str
) -> None:
    """Review of PR #34: the header is checked for every request, not only by routes that
    read it, so a bad value never reaches a product route."""
    response = client.request(method, path, headers={"X-Client": "browser"}, json={"name": "P"})
    assert response.status_code == 400
    assert_error(response.json(), "E184")
    assert client.get("/v1/projects").json() == []


def test_x_client_is_checked_after_the_token(app: FastAPI) -> None:
    with TestClient(app, base_url=BASE_URL) as client:
        response = client.get("/v1/system", headers={"X-Client": "browser"})
    assert response.status_code == 401


def test_request_client_alone_refuses_another_value() -> None:
    """Without the middleware (a route mounted elsewhere), the helper still refuses."""
    from starlette.requests import Request as StarletteRequest

    from ithax.service.errors import ServiceError

    scope = {"type": "http", "method": "GET", "path": "/", "headers": [(b"x-client", b"robot")]}
    with pytest.raises(ServiceError) as refused:
        request_client(StarletteRequest(scope))
    assert (refused.value.status, refused.value.code) == (400, "E184")
