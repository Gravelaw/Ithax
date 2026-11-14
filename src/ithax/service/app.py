"""The application factory (spec 3 "Architecture" and "Service rules").

``create_app(config)`` builds the one FastAPI application: the hardening middleware
(``Host``, ``Origin``, token, lifetime), spec 3's error bodies, and one router per area.
A later area adds its router to ``ROUTERS``. The app has no ``/docs``, ``/redoc`` or
``/openapi.json`` and no telemetry (research note
``docs/research/spec-3-service-framework-check.md``), so its routes are exactly the
routers' and nothing leaves the machine.

The lifespan also starts the runs (``RunService.start``: E191 for orphaned runs, every
project's run index) and stops them when the service stops (``RunService.stop``: E191 for
unfinished runs; AKS-112).

When ``config.on_idle`` is set, the app's lifespan watches the lifetime and calls it once
the service has been idle for ``config.idle_timeout_s`` (spec 3 "Lifetime"), counted from
when it starts serving at the earliest.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
from collections.abc import AsyncIterator

from fastapi import APIRouter, FastAPI
from fastapi.routing import iter_route_contexts
from starlette.concurrency import run_in_threadpool
from starlette.routing import WebSocketRoute

from ithax import __version__
from ithax.engines.registry import installed_adapters
from ithax.service import (
    data,
    engines,
    export,
    interface_files,
    models,
    projects,
    runs,
    settings,
    system,
    templates,
)
from ithax.service.auth import Hardening
from ithax.service.config import ServiceConfig
from ithax.service.data_store import DataStore
from ithax.service.errors import AsciiJSONResponse, install_error_handlers
from ithax.service.events import ProjectEvents
from ithax.service.hardware import active_tier, detect_hardware, tier_workers
from ithax.service.lifetime import Lifetime, watch
from ithax.service.model_store import ModelStore
from ithax.service.projects_store import ProjectRegistry
from ithax.service.run_service import RunService
from ithax.service.run_settings import read_run_settings
from ithax.service.settings_store import SettingsStore
from ithax.service.state import ServiceState

__all__ = ["ROUTERS", "create_app", "route_table", "table_path"]

#: The routers of the API, one per area (spec 3 "Endpoints").
ROUTERS: tuple[APIRouter, ...] = (
    system.router,
    settings.router,
    engines.router,
    templates.router,
    projects.router,
    models.router,
    runs.router,
    data.router,
    export.router,
    interface_files.router,
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
    adapters = installed_adapters() if config.adapters is None else config.adapters
    registry = ProjectRegistry(config.config_dir, config.data_dir)
    events = ProjectEvents()
    tier = active_tier(config.config_dir, hardware)
    model_store = ModelStore(registry, adapters, events)
    state = ServiceState(
        config=config,
        lifetime=lifetime,
        hardware=hardware,
        tier=tier,
        adapters=adapters,
        projects=registry,
        models=model_store,
        events=events,
        runs=RunService(
            projects=registry,
            models=model_store,
            events=events,
            adapters=adapters,
            lifetime=lifetime,
            settings=read_run_settings(config.config_dir),
            workers=tier_workers(tier, hardware.cores),
            config_dir=config.config_dir,
        ),
        data=DataStore(model_store),
        settings=SettingsStore(config.config_dir, hardware),
    )

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # The idle count starts when serving starts: building the app and starting the
        # server are not idle time, and on a slow machine they could use up a short limit,
        # so the service would exit at its first check (CI on PR #35).
        await run_in_threadpool(state.runs.start)
        lifetime.touch()
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
            await run_in_threadpool(state.runs.stop)

    app = FastAPI(
        title="lcsim engine service",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
        # Every body is ASCII JSON, so no text a client sent can stop it being sent.
        default_response_class=AsciiJSONResponse,
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


_CONVERTER = re.compile(r"\{(\w+):\w+\}")


def table_path(path: str) -> str:
    """A route's path as spec 3's table writes it: a parameter without its converter, so
    ``/v1/ui/{path:path}`` is ``/v1/ui/{path}`` (AKS-119)."""
    return _CONVERTER.sub(r"{\1}", path)


def route_table(app: FastAPI) -> set[tuple[str, str]]:
    """The app's routes as ``(method, path)`` pairs, as spec 3 "Endpoints" writes them
    (``GET /v1/system``); a WebSocket route is ``GET``, the method of its upgrade, as the
    table writes ``GET /v1/runs/{rid}/events``. FastAPI keeps an included router as one
    entry of ``app.routes``; this lists the routes inside it. ``HEAD``, which Starlette
    adds to every ``GET``, is left out."""
    table: set[tuple[str, str]] = set()
    for context in iter_route_contexts(app.routes):
        assert context.path is not None
        path = table_path(context.path)
        if isinstance(context.original_route, WebSocketRoute):
            table.add(("GET", path))
            continue
        for method in context.methods or ():
            if method != "HEAD":
                table.add((method, path))
    return table
