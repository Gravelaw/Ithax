"""What a running service holds, shared by its routers.

``create_app`` builds one ``ServiceState`` and keeps it on ``app.state.service``; a route
reads it with ``service_state`` (a FastAPI dependency: ``Depends(service_state)``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from starlette.requests import HTTPConnection

from ithax.engines.adapter import EngineAdapter
from ithax.service.config import ServiceConfig
from ithax.service.data_store import DataStore
from ithax.service.events import ProjectEvents
from ithax.service.hardware import Hardware, TierName
from ithax.service.lifetime import Lifetime
from ithax.service.model_store import ModelStore
from ithax.service.projects_store import ProjectRegistry
from ithax.service.run_service import RunService
from ithax.service.settings_store import SettingsStore

__all__ = ["ServiceState", "service_state"]


@dataclass(frozen=True)
class ServiceState:
    """The configuration, lifetime, hardware and active tier, the installed adapters,
    the project registry, the projects' models, the project events, the runs, the
    imported data and the settings file of one service."""

    config: ServiceConfig
    lifetime: Lifetime
    hardware: Hardware
    tier: TierName
    adapters: Mapping[str, EngineAdapter]
    projects: ProjectRegistry
    models: ModelStore
    events: ProjectEvents
    runs: RunService
    data: DataStore
    settings: SettingsStore


def service_state(connection: HTTPConnection) -> ServiceState:
    """The state of the service answering ``connection``."""
    state = connection.app.state.service
    assert isinstance(state, ServiceState)
    return state
