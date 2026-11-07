"""What a running service holds, shared by its routers.

``create_app`` builds one ``ServiceState`` and keeps it on ``app.state.service``; a route
reads it with ``service_state`` (a FastAPI dependency: ``Depends(service_state)``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from starlette.requests import HTTPConnection

from lcsim.engines.adapter import EngineAdapter
from lcsim.service.config import ServiceConfig
from lcsim.service.events import ProjectEvents
from lcsim.service.hardware import Hardware, TierName
from lcsim.service.lifetime import Lifetime
from lcsim.service.model_store import ModelStore
from lcsim.service.projects_store import ProjectRegistry
from lcsim.service.run_service import RunService

__all__ = ["ServiceState", "service_state"]


@dataclass(frozen=True)
class ServiceState:
    """The configuration, lifetime, hardware and active tier, the installed adapters,
    the project registry, the projects' models, the project events and the runs of one
    service."""

    config: ServiceConfig
    lifetime: Lifetime
    hardware: Hardware
    tier: TierName
    adapters: Mapping[str, EngineAdapter]
    projects: ProjectRegistry
    models: ModelStore
    events: ProjectEvents
    runs: RunService


def service_state(connection: HTTPConnection) -> ServiceState:
    """The state of the service answering ``connection``."""
    state = connection.app.state.service
    assert isinstance(state, ServiceState)
    return state
