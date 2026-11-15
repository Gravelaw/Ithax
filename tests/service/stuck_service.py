"""``python tests/service/stuck_service.py [service options]``: the service of
``python -m ithax.service``, its application wrapped so that a request to ``/test/stuck``
never gets an answer (#158). The marker file ``ITHAX_TEST_STUCK_MARKER`` names is written
once such a request is in the application.

The wrapping is a test's: the product has no such route. Everything happens in the
``__main__`` block, so a run's worker, started with ``spawn``, does nothing here but import.
"""

import asyncio
import os
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

MARKER_VARIABLE = "ITHAX_TEST_STUCK_MARKER"
STUCK_PATH = "/test/stuck"

Scope = dict[str, Any]
App = Callable[[Scope, Any, Any], Awaitable[None]]


class Stuck:
    """An ASGI application that holds every ``STUCK_PATH`` request open and passes the rest
    to ``app``."""

    def __init__(self, app: App, marker: Path) -> None:
        self.app = app
        self.marker = marker

    async def __call__(self, scope: Scope, receive: Any, send: Any) -> None:
        if scope["type"] == "http" and scope["path"] == STUCK_PATH:
            self.marker.write_text("in", encoding="utf-8")
            await asyncio.Event().wait()  # never set: only a cancel ends it
        await self.app(scope, receive, send)


if __name__ == "__main__":
    from fastapi import FastAPI

    from ithax.service import main as service_main
    from ithax.service.config import ServiceConfig

    marker = Path(os.environ[MARKER_VARIABLE])
    namespace = vars(service_main)
    create_app = namespace["create_app"]

    def stuck_app(config: ServiceConfig) -> FastAPI:
        # uvicorn takes any ASGI application; the type is FastAPI's for the patch only.
        return Stuck(create_app(config), marker)  # type: ignore[return-value]

    namespace["create_app"] = stuck_app
    raise SystemExit(service_main.main(sys.argv[1:]))
