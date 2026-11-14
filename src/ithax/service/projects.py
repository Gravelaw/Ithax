"""``/v1/projects``: list, create and open projects (spec 3 "Endpoints").

The project folder and the registry are ``ithax.service.projects_store``; this module is
the HTTP side. ``POST /v1/projects`` takes ``{name, template?, domain?, path?}``: without
``template`` the project holds the default model of ``domain`` (``process`` by default);
with one it holds the template's model, named after the project, with ``meta.template``
the template's id (AKS-122): an unknown template is 404 with E185, and a ``domain`` that
differs from the template model's is 400 with E184 at ``/domain``.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ithax.model.issues import Issue
from ithax.service.errors import malformed
from ithax.service.paths import canonical, fully_qualified
from ithax.service.projects_store import Domain
from ithax.service.state import ServiceState, service_state
from ithax.service.templates import find_template

__all__ = ["CreateProject", "OpenProject", "router"]

router = APIRouter(prefix="/v1/projects")

State = Annotated[ServiceState, Depends(service_state)]


def _unicode(value: str | None) -> str | None:
    """``value`` when it is valid Unicode, which the project files are written in; a lone
    surrogate (a JSON escape such as ``"\\ud800"`` can carry one) is refused (E184,
    review of PR #35)."""
    if value is not None:
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("not valid Unicode") from None
    return value


class CreateProject(BaseModel):
    """The body of ``POST /v1/projects``."""

    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1)
    template: str | None = None
    domain: Domain | None = None
    path: str | None = None

    _writable = field_validator("name", "template", "path")(lambda value: _unicode(value))


class OpenProject(BaseModel):
    """The body of ``POST /v1/projects/open``."""

    model_config = ConfigDict(extra="forbid", strict=True)

    path: str

    _writable = field_validator("path")(lambda value: _unicode(value))


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


def _template_model(state: ServiceState, body: CreateProject) -> dict[str, Any]:
    """The model of a project made from ``body.template``: the template's model with
    ``meta.name`` the project's name and ``meta.template`` the template's id."""
    assert body.template is not None
    package = find_template(state, body.template)
    model = copy.deepcopy(dict(package.model))
    if body.domain is not None and body.domain != model["domain"]:
        raise malformed(
            [
                Issue(
                    code="E184",
                    component=None,
                    path="/domain",
                    message=f"The request field 'domain' is '{body.domain}', but the template "
                    f"'{package.id}' is a '{model['domain']}' model.",
                    hint="Leave 'domain' out when starting from a template, or give the "
                    "template's own.",
                )
            ]
        )
    model["meta"] = {**model["meta"], "name": body.name, "template": package.id}
    return model


@router.post("")
def create_project(body: CreateProject, state: State) -> dict[str, Any]:
    """Create a project, from nothing or from a template, and register it."""
    if body.domain is None and "domain" in body.model_fields_set:
        # Optional only so that a template's model can set it; null is not a domain.
        raise malformed(
            [
                Issue(
                    code="E184",
                    component=None,
                    path="/domain",
                    message="The request field 'domain' is null, which is not a domain.",
                    hint="Give 'process' or 'optimization', or leave 'domain' out.",
                )
            ]
        )
    folder = None if body.path is None else _absolute(body.path)
    if body.template is None:
        return state.projects.create(body.name, body.domain or "process", folder)
    model = _template_model(state, body)
    return state.projects.create(body.name, model["domain"], folder, model)


@router.post("/open")
def open_project(body: OpenProject, state: State) -> dict[str, Any]:
    """Register an existing project folder."""
    return state.projects.open(_absolute(body.path))
