"""The run endpoints (spec 3 "Endpoints", "Progress events"; AKS-112):

- ``POST /v1/projects/{pid}/runs``: ``{experiment_id?, target?}`` (no body is ``{}``);
  202 with ``{run_id}``;
- ``GET /v1/projects/{pid}/runs``: the project's runs in the order accepted;
- ``GET /v1/runs/{rid}``: the run's state, progress and timings;
- ``POST /v1/runs/{rid}/cancel``: the run after the cancel; 409 with E188 once it has ended;
- ``GET /v1/runs/{rid}/events``: the run's progress events (WebSocket);
- ``GET /v1/runs/{rid}/summary``: ``{summary, findings}``;
- ``GET /v1/runs/{rid}/tables/{name}``: ``replications`` or ``timeseries``, as JSON rows or
  CSV.

The work is ``lcsim.service.run_service``'s; this module is the HTTP and WebSocket side. A
run's ``client`` is the request's ``X-Client`` (``script`` when absent).

The events stream, after the token message: a run that cannot be found closes with 1008 and
``E185``; otherwise a ``state`` and a ``progress`` event taken at one instant, then every
later change, and after the final state a close with 1000. A run that is already final, or
that this service does not drive, sends its state and progress from its manifest and closes.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, field_validator
from starlette.concurrency import run_in_threadpool
from starlette.websockets import WebSocket

from lcsim.runs.states import FINAL_STATES
from lcsim.service.auth import POLICY_VIOLATION, Client, authenticate_websocket, request_client
from lcsim.service.errors import ServiceError
from lcsim.service.events import Listener, until_closed
from lcsim.service.run_feed import Snapshot, progress_event, state_event
from lcsim.service.state import ServiceState, service_state

__all__ = ["NORMAL_CLOSURE", "StartRun", "router"]

router = APIRouter(prefix="/v1")

State = Annotated[ServiceState, Depends(service_state)]
ClientName = Annotated[Client, Depends(request_client)]

#: The WebSocket close code once the run has ended (RFC 6455: normal closure).
NORMAL_CLOSURE = 1000


def _unicode(value: str | None) -> str | None:
    """``value`` when it is valid Unicode, which the run's files are written in; a lone
    surrogate is refused (E184)."""
    if value is not None:
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("not valid Unicode") from None
    return value


class StartRun(BaseModel):
    """The body of ``POST /v1/projects/{pid}/runs``."""

    model_config = ConfigDict(extra="forbid", strict=True)

    experiment_id: str | None = None
    target: str | None = None

    _writable = field_validator("experiment_id", "target")(lambda value: _unicode(value))


@router.post("/projects/{pid}/runs", status_code=202)
def start_run(
    pid: str, state: State, client: ClientName, body: StartRun | None = None
) -> dict[str, Any]:
    """Start a run of the project's model."""
    request = StartRun() if body is None else body
    rid = state.runs.submit(pid, request.experiment_id, request.target, client)
    return {"run_id": rid}


@router.get("/projects/{pid}/runs")
def list_runs(pid: str, state: State) -> list[dict[str, Any]]:
    """The project's runs, in the order accepted."""
    return state.runs.runs(pid)


@router.get("/runs/{rid}")
def get_run(rid: str, state: State) -> dict[str, Any]:
    """The run's state, progress and timings."""
    return state.runs.run(rid)


@router.post("/runs/{rid}/cancel")
def cancel_run(rid: str, state: State) -> dict[str, Any]:
    """Cancel the run."""
    return state.runs.cancel(rid)


@router.get("/runs/{rid}/summary")
def get_summary(rid: str, state: State) -> dict[str, Any]:
    """``summary.json`` and the findings (M8)."""
    return state.runs.summary(rid)


@router.get("/runs/{rid}/tables/{name}", response_model=None)
def get_table(
    rid: str, name: str, request: Request, state: State
) -> list[dict[str, Any]] | Response:
    """Table rows, as JSON or CSV."""
    table = state.runs.table(rid, name, request.query_params.get("format"))
    if table.rows is not None:
        return table.rows
    assert table.text is not None
    return Response(content=table.text.encode("utf-8"), media_type="text/csv; charset=utf-8")


async def _follow(websocket: WebSocket, listener: Listener) -> None:
    """Send the run's changes until its final state, then close; stop when the client
    leaves."""
    leaving = asyncio.ensure_future(until_closed(websocket))
    try:
        while True:
            getting = asyncio.ensure_future(listener.next())
            await asyncio.wait({leaving, getting}, return_when=asyncio.FIRST_COMPLETED)
            if leaving.done():
                getting.cancel()
                return
            event = getting.result()
            await websocket.send_json(dict(event))
            if event["type"] == "state" and event["state"] in FINAL_STATES:
                await websocket.close(code=NORMAL_CLOSURE)
                return
    finally:
        leaving.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await leaving


@router.websocket("/runs/{rid}/events")
async def run_events(websocket: WebSocket, rid: str, state: State) -> None:
    """The run's progress events."""
    config = state.config
    if not await authenticate_websocket(websocket, config.token, config.websocket_auth_timeout_s):
        return
    try:
        await run_in_threadpool(state.runs.find, rid)
    except ServiceError as refused:
        await websocket.close(code=POLICY_VIOLATION, reason=refused.code)
        return
    # Listening takes the snapshot, so no change between the two is lost or repeated.
    with state.runs.feed.listen(rid) as (snapshot, listener):
        live = snapshot is not None
        if snapshot is None:
            try:
                view = await run_in_threadpool(state.runs.run, rid)
            except ServiceError as refused:
                await websocket.close(code=POLICY_VIOLATION, reason=refused.code)
                return
            snapshot = Snapshot(view["state"], view["fraction"], view["message"])
        await websocket.send_json(dict(state_event(snapshot.state)))
        await websocket.send_json(dict(progress_event(snapshot.fraction, snapshot.message)))
        if not live or snapshot.state in FINAL_STATES:
            await websocket.close(code=NORMAL_CLOSURE)
            return
        await _follow(websocket, listener)
