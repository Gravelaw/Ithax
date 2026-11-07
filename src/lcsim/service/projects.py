"""``/v1/projects``: list, create and open projects (spec 3 "Endpoints").

The project folder and the registry are ``lcsim.service.projects_store``; this module is
the HTTP side. ``POST /v1/projects`` takes ``{name, template?, domain?, path?}``: without
``template`` the project holds the default model of ``domain`` (``process`` by default);
a ``template`` is 404 with E185 until the templates arrive (M10).
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from lcsim.model.issues import Issue
from lcsim.service.errors import NOT_FOUND, ServiceError, malformed
from lcsim.service.paths import canonical, fully_qualified
from lcsim.service.projects_store import Domain
from lcsim.service.state import ServiceState, service_state

__all__ = ["CreateProject", "OpenProject", "router"]

router = APIRouter(prefix="/v1/projects")

State = Annotated[ServiceState, Depends(service_state)]


class CreateProject(BaseModel):
    """The body of ``POST /v1/projects``."""

    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1)
    template: str | None = None
    domain: Domain = "process"
    path: str | None = None


class OpenProject(BaseModel):
    """The body of ``POST /v1/projects/open``."""

    model_config = ConfigDict(extra="forbid", strict=True)

    path: str


def _absolute(path: str) -> Path:
    """``path`` as its canonical path; 400 with E184 when it is not fully qualified."""
    if not fully_qualified(path):
        raise malformed(
            [
                Issue(
                    code="E184",
                    component=None,
                    path="/path",
                    message=f"The request field 'path' is '{path}', which is not a full path.",
                    hint="Give the folder's full path, with its drive on Windows (C:\\...) "
                    "or its share (\\\\server\\share\\...).",
                )
            ]
        )
    return canonical(path)


@router.get("")
def list_projects(state: State) -> list[dict[str, Any]]:
    """The registered projects, in the order registered."""
    return state.projects.entries()


@router.post("")
def create_project(body: CreateProject, state: State) -> dict[str, Any]:
    """Create a project and register it."""
    folder = None if body.path is None else _absolute(body.path)
    if body.template is not None:
        raise ServiceError(
            404,
            NOT_FOUND,
            f"There is no template '{body.template}'; the templates arrive with M10.",
        )
    return state.projects.create(body.name, body.domain, folder)


@router.post("/open")
def open_project(body: OpenProject, state: State) -> dict[str, Any]:
    """Register an existing project folder."""
    return state.projects.open(_absolute(body.path))
