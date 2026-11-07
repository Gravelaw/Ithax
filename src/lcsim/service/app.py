"""The application factory (spec 3 "Architecture" and "Service rules").

``create_app(config)`` builds the one FastAPI application: the hardening middleware
(``Host``, ``Origin``, token, lifetime), spec 3's error bodies, and one router per area.
A later area adds its router to ``ROUTERS``. The app has no ``/docs``, ``/redoc`` or
``/openapi.json`` and no telemetry (research note
``docs/research/spec-3-service-framework-check.md``), so its routes are exactly the
routers' and nothing leaves the machine.

When ``config.on_idle`` is set, the app's lifespan watches the lifetime and calls it once
the service has been idle for ``config.idle_timeout_s`` (spec 3 "Lifetime").
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

from fastapi import APIRouter, FastAPI
from fastapi.routing import iter_route_contexts
from starlette.routing import WebSocketRoute

from lcsim import __version__
from lcsim.engines.registry import installed_adapters
from lcsim.service import engines, projects, system, templates
from lcsim.service.auth import Hardening
from lcsim.service.config import ServiceConfig
from lcsim.service.errors import install_error_handlers
from lcsim.service.hardware import active_tier, detect_hardware
from lcsim.service.lifetime import Lifetime, watch
from lcsim.service.projects_store import ProjectRegistry
from lcsim.service.state import ServiceState

__all__ = ["ROUTERS", "create_app", "route_table"]

#: The routers of the API, one per area (spec 3 "Endpoints").
ROUTERS: tuple[APIRouter, ...] = (
    system.router,
    engines.router,
    templates.router,
    projects.router,
)

# FastAPI's built-in telemetry, all off: no spans, metrics or logs, and no exporter even if
# OTEL_* variables are set (research note, "FastAPI is confirmed").
_NO_TELEMETRY = {
    "tracing": False,
    "metrics": False,
    "logs": False,
    "operation_spans": False,
    "auto_configure": False,
}


def create_app(config: ServiceConfig) -> FastAPI:
    """The service's application for ``config``."""
    hardware = config.hardware if config.hardware is not None else detect_hardware()
    lifetime = Lifetime(config.idle_timeout_s, config.clock)
    state = ServiceState(
        config=config,
        lifetime=lifetime,
        hardware=hardware,
        tier=active_tier(config.config_dir, hardware),
        adapters=installed_adapters() if config.adapters is None else config.adapters,
        projects=ProjectRegistry(config.config_dir, config.data_dir),
    )

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        task = None
        if config.on_idle is not None:
            task = asyncio.create_task(watch(lifetime, config.idle_check_s, config.on_idle))
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(
        title="lcsim engine service",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
        telemetry=_NO_TELEMETRY,  # type: ignore[arg-type]
    )
    app.state.service = state
    install_error_handlers(app)
    app.add_middleware(
        Hardening,
        port=config.port,
        token=config.token,
        allowed_origins=config.allowed_origins,
        lifetime=lifetime,
    )
    for router in ROUTERS:
        app.include_router(router)
    return app


def route_table(app: FastAPI) -> set[tuple[str, str]]:
    """The app's routes as ``(method, path)`` pairs, as spec 3 "Endpoints" writes them
    (``GET /v1/system``); a WebSocket route is ``GET``, the method of its upgrade, as the
    table writes ``GET /v1/runs/{rid}/events``. FastAPI keeps an included router as one
    entry of ``app.routes``; this lists the routes inside it. ``HEAD``, which Starlette
    adds to every ``GET``, is left out."""
    table: set[tuple[str, str]] = set()
    for context in iter_route_contexts(app.routes):
        path = context.path
        assert path is not None
        if isinstance(context.original_route, WebSocketRoute):
            table.add(("GET", path))
            continue
        for method in context.methods or ():
            if method != "HEAD":
                table.add((method, path))
    return table
