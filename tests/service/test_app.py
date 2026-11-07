"""The application factory (spec 3 "Architecture" and "Endpoints"; AKS-110).

The full route table test against spec 3 is AKS-114's ``tests/service/test_routes.py``;
this checks the routes AKS-110 adds and that FastAPI adds none of its own.
"""

from fastapi import FastAPI
from starlette.websockets import WebSocket

from lcsim.service.app import ROUTERS, create_app, route_table
from lcsim.service.config import ServiceConfig

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


def test_the_app_has_the_aks_110_routes_and_nothing_else(app: FastAPI) -> None:
    assert route_table(app) == AKS_110_ROUTES


def test_every_path_starts_with_v1(app: FastAPI) -> None:
    assert all(path.startswith("/v1/") for _, path in route_table(app))


def test_there_is_one_router_per_area() -> None:
    assert [router.prefix for router in ROUTERS] == ["/v1", "/v1", "/v1/templates", "/v1/projects"]


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
