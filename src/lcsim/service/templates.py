"""``/v1/templates``: the template gallery (spec 3 "Endpoints"; spec 4 "Template package").

The templates arrive at M10. Until then ``GET /v1/templates`` is an empty array and
``GET /v1/templates/{tid}`` is 404 with E185 for every id.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from lcsim.service.errors import NOT_FOUND, ServiceError

__all__ = ["router"]

router = APIRouter(prefix="/v1/templates")


@router.get("")
def list_templates() -> list[dict[str, Any]]:
    """Every installed template's ``template.json``: none before M10."""
    return []


@router.get("/{tid}")
def get_template(tid: str) -> dict[str, Any]:
    """One template's ``template.json``, ``lesson.md`` and ``expected.json``."""
    raise ServiceError(
        404, NOT_FOUND, f"There is no template '{tid}'; the templates arrive with M10."
    )
