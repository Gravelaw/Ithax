"""``/v1/templates``: the template gallery (spec 3 "Endpoints"; spec 4 "Template package").

The service serves the packages of ``ServiceConfig.templates_dir``, read at each request
(AKS-122, owner to confirm). A package with any issue (E195, or its model's own) is not
served, and its issues are logged. ``GET /v1/templates`` is the served packages'
``template.json`` objects in ``id`` order; ``GET /v1/templates/{tid}`` is
``{template, lesson, expected}``; an id that is not a served package is 404 with E185, with
the package's issues when its folder exists. ``find_template`` is shared with
``POST /v1/projects``, which copies a template's model.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from lcsim.model.validation import IDENTIFIER_PATTERN
from lcsim.service.errors import NOT_FOUND, ServiceError
from lcsim.service.state import ServiceState, service_state
from lcsim.templates import TemplatePackage, load_package, package_folders

__all__ = ["find_template", "router", "served_templates"]

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/templates")

State = Annotated[ServiceState, Depends(service_state)]


def _load(state: ServiceState, folder: Path) -> TemplatePackage | ServiceError:
    result = load_package(folder, adapters=state.adapters)
    if result.package is not None:
        return result.package
    _log.warning(
        "The template '%s' cannot be served: %s",
        folder.name,
        "; ".join(f"{issue.code} at '{issue.path}': {issue.message}" for issue in result.issues),
    )
    return ServiceError(
        404,
        NOT_FOUND,
        f"The template '{folder.name}' cannot be used; its issues are listed.",
        result.issues,
    )


def served_templates(state: ServiceState) -> list[TemplatePackage]:
    """The packages the service serves, in ``id`` order."""
    root = state.config.templates_dir
    if root is None:
        return []
    loaded = [_load(state, folder) for folder in package_folders(root)]
    return [package for package in loaded if isinstance(package, TemplatePackage)]


def find_template(state: ServiceState, tid: str) -> TemplatePackage:
    """The served package ``tid``; 404 with E185 otherwise (with the package's issues
    when its folder exists). An id that is not an identifier names no folder, so nothing
    outside the templates folder is ever read."""
    root = state.config.templates_dir
    if root is None or IDENTIFIER_PATTERN.fullmatch(tid) is None or not (root / tid).is_dir():
        raise ServiceError(404, NOT_FOUND, f"There is no template '{tid}'.")
    loaded = _load(state, root / tid)
    if isinstance(loaded, ServiceError):
        raise loaded
    return loaded


@router.get("")
def list_templates(state: State) -> list[dict[str, Any]]:
    """Every served template's ``template.json``, in ``id`` order."""
    return [dict(package.template) for package in served_templates(state)]


@router.get("/{tid}")
def get_template(tid: str, state: State) -> dict[str, Any]:
    """One template's ``template.json``, ``lesson.md`` text and ``expected.json``."""
    package = find_template(state, tid)
    return {
        "template": dict(package.template),
        "lesson": package.lesson_text,
        "expected": list(package.expected_document),
    }
