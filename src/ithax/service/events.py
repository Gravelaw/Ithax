"""The project events broadcaster behind ``GET /v1/projects/{pid}/events`` (spec 3
"Endpoints", "External edits"; the route is in ``ithax.service.models``).

``ProjectEvents`` sends each event of a project to every listener of that project. A
listener lives in the event loop that serves its WebSocket; events are published from any
thread (the routes that write the model run in FastAPI's thread pool, and the run driver
of AKS-112 in its own threads) and reach each listener's loop through
``call_soon_threadsafe``, in the order they were published. Two kinds are published:

- ``model_written(pid, revision, client)``: ``{"type": "model", "revision", "client"}``,
  on every write of the model (AKS-111);
- ``run_changed(pid, run_id, state)``: ``{"type": "run", "run_id", "state"}``, when a run
  is created (``queued``) and on every run state change (``ithax.service.run_service``,
  AKS-112).

The WebSocket first checks the token message (``authenticate_websocket``), then sends
``{"type": "model", "revision": N, "client": null}`` with the current revision, then every
later event. A project the service does not know (E185), or one it cannot read (E186), is
closed with 1008 and that code as the reason, after the token (AKS-111, owner to confirm).
What the client sends after its token is read and ignored, so that its leaving is seen.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Iterator, Mapping
from typing import Any

from starlette.websockets import WebSocket

__all__ = ["Event", "Listener", "ProjectEvents", "forward", "until_closed"]

Event = Mapping[str, Any]


class Listener:
    """One listener of one project: the events published to it, in order, read with
    ``next`` in the event loop it was made in."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        self._queue: asyncio.Queue[Event] = asyncio.Queue()

    def deliver(self, event: Event) -> None:
        """Queue ``event`` from any thread; dropped when the listener's loop has closed."""
        with contextlib.suppress(RuntimeError):
            self.loop.call_soon_threadsafe(self._queue.put_nowait, event)

    async def next(self) -> Event:
        """The next event."""
        return await self._queue.get()


class ProjectEvents:
    """The listeners of every project, and publishing to them; safe from any thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._listeners: dict[str, list[Listener]] = {}

    @contextlib.contextmanager
    def listen(self, pid: str) -> Iterator[Listener]:
        """Listen to project ``pid`` while the block runs; called in an event loop."""
        listener = Listener(asyncio.get_running_loop())
        with self._lock:
            self._listeners.setdefault(pid, []).append(listener)
        try:
            yield listener
        finally:
            with self._lock:
                remaining = [item for item in self._listeners[pid] if item is not listener]
                if remaining:
                    self._listeners[pid] = remaining
                else:
                    del self._listeners[pid]

    def listeners(self, pid: str) -> int:
        """How many listeners project ``pid`` has."""
        with self._lock:
            return len(self._listeners.get(pid, ()))

    def publish(self, pid: str, event: Event) -> None:
        """Send ``event`` to every listener of project ``pid``."""
        with self._lock:
            listeners = list(self._listeners.get(pid, ()))
        for listener in listeners:
            listener.deliver(event)

    def model_written(self, pid: str, revision: int, client: str) -> None:
        """A write of the model of ``pid``, now at ``revision``, by ``client``."""
        self.publish(pid, {"type": "model", "revision": revision, "client": client})

    def run_changed(self, pid: str, run_id: str, state: str) -> None:
        """A run of ``pid`` that has moved to ``state`` (AKS-112)."""
        self.publish(pid, {"type": "run", "run_id": run_id, "state": state})


async def until_closed(websocket: WebSocket) -> None:
    """Read and ignore what the client sends, until it leaves."""
    while (await websocket.receive())["type"] != "websocket.disconnect":
        pass


async def forward(websocket: WebSocket, listener: Listener, revision: int) -> None:
    """Send ``listener``'s events until the client leaves, leaving out a ``model`` event
    the first message already covered (a write between listening and reading the
    revision)."""
    leaving = asyncio.ensure_future(until_closed(websocket))
    try:
        while True:
            getting = asyncio.ensure_future(listener.next())
            await asyncio.wait({leaving, getting}, return_when=asyncio.FIRST_COMPLETED)
            if leaving.done():
                getting.cancel()
                return
            event = getting.result()
            if event["type"] == "model" and event["revision"] <= revision:
                continue
            await websocket.send_json(dict(event))
    finally:
        leaving.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await leaving
