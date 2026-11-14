"""The model of a project through the API (spec 3 "Endpoints", "Revision", "Model edits";
AKS-111):

- ``GET /v1/projects/{pid}/model``: ``{model, revision}``;
- ``PUT /v1/projects/{pid}/model``: the body is a whole model file, ``?base_revision=N``
  optional; saved when it passes the schema pass; ``{model, revision, issues}``;
- ``POST /v1/projects/{pid}/model/edits``: ``{edits, base_revision?}``; the same response;
- ``POST /v1/projects/{pid}/validate``: ``{revision, issues}`` of the schema pass, the
  meaning pass and the adapter's ``validate``;
- ``GET /v1/projects/{pid}/events``: the project events WebSocket
  (``ithax.service.events``).

The work is ``ithax.service.model_store``'s; this module is the HTTP side. A write's
``client`` is its ``X-Client`` (``script`` when absent).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool
from starlette.websockets import WebSocket

from ithax.service.auth import POLICY_VIOLATION, Client, authenticate_websocket, request_client
from ithax.service.errors import ServiceError
from ithax.service.events import forward
from ithax.service.model_store import base_revision
from ithax.service.state import ServiceState, service_state

__all__ = ["EditBatch", "router"]

router = APIRouter(prefix="/v1/projects")

State = Annotated[ServiceState, Depends(service_state)]
ClientName = Annotated[Client, Depends(request_client)]


class EditBatch(BaseModel):
    """The body of ``POST .../model/edits``; the edits' own shape is checked by
    ``ithax.model.edits.check_edits``, which says more than a type error would."""

    model_config = ConfigDict(extra="forbid", strict=True)

    edits: Any
    base_revision: int | None = None


@router.get("/{pid}/model")
def get_model(pid: str, state: State) -> dict[str, Any]:
    """The model file and its revision."""
    return state.models.read(pid)


@router.put("/{pid}/model")
async def put_model(pid: str, request: Request, state: State, client: ClientName) -> dict[str, Any]:
    """Save a whole model file."""
    base = base_revision(request.query_params.get("base_revision"))
    body = await request.body()
    written = await run_in_threadpool(state.models.put, pid, body, base, client)
    return written.body()


@router.post("/{pid}/model/edits")
def post_edits(pid: str, batch: EditBatch, state: State, client: ClientName) -> dict[str, Any]:
    """Apply a batch of edits and save the result."""
    return state.models.edit(pid, batch.edits, batch.base_revision, client).body()


@router.post("/{pid}/validate")
def validate(pid: str, state: State) -> dict[str, Any]:
    """The validation issues of the saved model."""
    return state.models.validate(pid)


@router.websocket("/{pid}/events")
async def project_events(websocket: WebSocket, pid: str, state: State) -> None:
    """The events of project ``pid``: its current revision, then every write (and every
    run state change, AKS-112)."""
    config = state.config
    if not await authenticate_websocket(websocket, config.token, config.websocket_auth_timeout_s):
        return
    # Listening starts before the revision is read, so no write between the two is lost.
    with state.events.listen(pid) as listener:
        try:
            revision = await run_in_threadpool(state.models.revision, pid)
        except ServiceError as refused:
            await websocket.close(code=POLICY_VIOLATION, reason=refused.code)
            return
        await websocket.send_json({"type": "model", "revision": revision, "client": None})
        await forward(websocket, listener, revision)
