"""The application factory (spec 3 "Architecture" and "Endpoints"; AKS-110).

The full route table test against spec 3 is AKS-114's ``tests/service/test_routes.py``;
this checks the routes AKS-110 to AKS-113 and AKS-119 add and that FastAPI adds none of its
own.
"""

from fastapi import FastAPI
from starlette.websockets import WebSocket

from ithax.service.app import ROUTERS, create_app, route_table
from ithax.service.config import ServiceConfig

AKS_110_ROUTES = {
    ("GET", "/v1/system"),
    ("GET", "/v1/engines"),
    ("GET", "/v1/schema"),
    ("GET", "/v1/schema/components/{type}"),
    ("GET", "/v1/templates"),
    ("GET", "/v1/templates/{tid}"),
    ("GET", "/v1/projects"),
    ("POST", "/v1/projects"),
    ("POST", "/v1/projects/open"),
}

AKS_111_ROUTES = {
    ("GET", "/v1/projects/{pid}/model"),
    ("PUT", "/v1/projects/{pid}/model"),
    ("POST", "/v1/projects/{pid}/model/edits"),
    ("POST", "/v1/projects/{pid}/validate"),
    ("GET", "/v1/projects/{pid}/events"),
}

AKS_112_ROUTES = {
    ("POST", "/v1/projects/{pid}/runs"),
    ("GET", "/v1/projects/{pid}/runs"),
    ("GET", "/v1/runs/{rid}"),
    ("POST", "/v1/runs/{rid}/cancel"),
    ("GET", "/v1/runs/{rid}/events"),
    ("GET", "/v1/runs/{rid}/summary"),
    ("GET", "/v1/runs/{rid}/tables/{name}"),
}

AKS_113_ROUTES = {
    ("POST", "/v1/projects/{pid}/data"),
    ("GET", "/v1/projects/{pid}/data"),
    ("DELETE", "/v1/projects/{pid}/data/{file}"),
    ("POST", "/v1/projects/{pid}/data/{file}/fit"),
}

AKS_119_ROUTES = {
    ("GET", "/v1/settings"),
    ("PUT", "/v1/settings"),
    ("GET", "/v1/ui/{path}"),
}
AKS_138_ROUTES = {("GET", "/v1/projects/{pid}/export")}


def test_the_app_has_the_aks_110_to_aks_113_aks_119_and_aks_138_routes_and_nothing_else(
    app: FastAPI,
) -> None:
    assert route_table(app) == (
        AKS_110_ROUTES
        | AKS_111_ROUTES
        | AKS_112_ROUTES
        | AKS_113_ROUTES
        | AKS_119_ROUTES
        | AKS_138_ROUTES
    )


def test_every_path_starts_with_v1(app: FastAPI) -> None:
    assert all(path.startswith("/v1/") for _, path in route_table(app))


def test_there_is_one_router_per_area() -> None:
    assert [router.prefix for router in ROUTERS] == [
        "/v1",
        "/v1/settings",
        "/v1",
        "/v1/templates",
        "/v1/projects",
        "/v1/projects",
        "/v1",
        "/v1/projects",
        "/v1/projects",
        "/v1/ui",
    ]


def test_a_websocket_route_is_listed_as_get(config: ServiceConfig) -> None:
    app = create_app(config)

    @app.websocket("/v1/test/events")
    async def events(websocket: WebSocket) -> None:  # pragma: no cover - never connected
        await websocket.close()

    assert ("GET", "/v1/test/events") in route_table(app)


def test_two_apps_do_not_share_state(config: ServiceConfig, tmp_path: object) -> None:
    first = create_app(config)
    second = create_app(config)
    assert first.state.service is not second.state.service
    assert first.title == "lcsim engine service"
