"""``GET /v1/projects/{pid}/events``, the project events WebSocket, and the broadcaster
behind it (spec 3 "Endpoints", "External edits"; AKS-111).

Every write sends ``{"type": "model", "revision", "client"}`` to the project's listeners;
the run endpoints (AKS-112) send ``{"type": "run", "run_id", "state"}`` through the same
broadcaster.
"""

import asyncio
import dataclasses
import json
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from ithax.service.app import create_app
from ithax.service.config import ServiceConfig
from ithax.service.events import ProjectEvents
from ithax.service.state import ServiceState
from service.service_support import AUTH, BASE_URL, TOKEN, WS_URL

Json = dict[str, Any]

LABEL = {"edits": [{"edit": "set_label", "id": "x", "label": None}]}


@pytest.fixture
def quick(config: ServiceConfig) -> ServiceConfig:
    return dataclasses.replace(config, websocket_auth_timeout_s=0.5)


@pytest.fixture
def client(quick: ServiceConfig) -> Iterator[TestClient]:
    with TestClient(create_app(quick), base_url=BASE_URL, headers=AUTH) as test_client:
        yield test_client


def state_of(client: TestClient) -> ServiceState:
    app = client.app
    assert isinstance(app, FastAPI)
    state = app.state.service
    assert isinstance(state, ServiceState)
    return state


def new_project(client: TestClient) -> str:
    pid = client.post("/v1/projects", json={"name": "Shop"}).json()["id"]
    assert isinstance(pid, str)
    return pid


def model_of(client: TestClient, pid: str) -> Json:
    model: Json = client.get(f"/v1/projects/{pid}/model").json()["model"]
    return model


def wait_until(condition: Any, timeout_s: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_s
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.01)


def test_a_listener_gets_the_revision_then_one_event_per_write(client: TestClient) -> None:
    pid = new_project(client)
    with client.websocket_connect(f"{WS_URL}/v1/projects/{pid}/events") as socket:
        socket.send_text(json.dumps({"token": TOKEN}))
        assert socket.receive_json() == {"type": "model", "revision": 0, "client": None}
        model = model_of(client, pid)
        response = client.put(
            f"/v1/projects/{pid}/model", content=json.dumps(model), headers={"X-Client": "ui"}
        )
        assert response.status_code == 200
        assert socket.receive_json() == {"type": "model", "revision": 1, "client": "ui"}
        edits = {"edits": [{"edit": "set_path", "path": "/meta/name", "value": "B"}]}
        assert client.post(f"/v1/projects/{pid}/model/edits", json=edits).status_code == 200
        assert socket.receive_json() == {"type": "model", "revision": 2, "client": "script"}
        response = client.post(
            f"/v1/projects/{pid}/model/edits", json=edits, headers={"X-Client": "mcp"}
        )
        assert response.status_code == 200
        assert socket.receive_json() == {"type": "model", "revision": 3, "client": "mcp"}


def test_a_refused_write_sends_no_event(client: TestClient) -> None:
    pid = new_project(client)
    with client.websocket_connect(f"{WS_URL}/v1/projects/{pid}/events") as socket:
        socket.send_text(json.dumps({"token": TOKEN}))
        assert socket.receive_json()["revision"] == 0
        assert client.post(f"/v1/projects/{pid}/model/edits", json=LABEL).status_code == 400
        assert client.put(f"/v1/projects/{pid}/model", content="{").status_code == 400
        stale = client.put(
            f"/v1/projects/{pid}/model",
            content=json.dumps(model_of(client, pid)),
            params={"base_revision": 5},
        )
        assert stale.status_code == 409
        assert (
            client.put(
                f"/v1/projects/{pid}/model", content=json.dumps(model_of(client, pid))
            ).status_code
            == 200
        )
        assert socket.receive_json() == {"type": "model", "revision": 1, "client": "script"}


def test_a_listener_hears_only_its_own_project(client: TestClient) -> None:
    mine, other = new_project(client), new_project(client)
    with client.websocket_connect(f"{WS_URL}/v1/projects/{mine}/events") as socket:
        socket.send_text(json.dumps({"token": TOKEN}))
        assert socket.receive_json()["revision"] == 0
        client.put(f"/v1/projects/{other}/model", content=json.dumps(model_of(client, other)))
        client.put(f"/v1/projects/{mine}/model", content=json.dumps(model_of(client, mine)))
        assert socket.receive_json() == {"type": "model", "revision": 1, "client": "script"}


def test_two_listeners_both_hear_a_write(client: TestClient) -> None:
    pid = new_project(client)
    url = f"{WS_URL}/v1/projects/{pid}/events"
    with client.websocket_connect(url) as first, client.websocket_connect(url) as second:
        for socket in (first, second):
            socket.send_text(json.dumps({"token": TOKEN}))
            assert socket.receive_json()["revision"] == 0
        client.put(f"/v1/projects/{pid}/model", content=json.dumps(model_of(client, pid)))
        for socket in (first, second):
            assert socket.receive_json()["revision"] == 1


def test_run_state_changes_reach_the_project_listeners(client: TestClient) -> None:
    """AKS-112 publishes run state changes through the same broadcaster, from any thread."""
    pid = new_project(client)
    with client.websocket_connect(f"{WS_URL}/v1/projects/{pid}/events") as socket:
        socket.send_text(json.dumps({"token": TOKEN}))
        socket.receive_json()
        worker = threading.Thread(
            target=state_of(client).events.run_changed, args=(pid, "r1", "running")
        )
        worker.start()
        worker.join()
        assert socket.receive_json() == {"type": "run", "run_id": "r1", "state": "running"}


def test_an_unknown_project_is_closed_with_1008_and_e185(client: TestClient) -> None:
    with client.websocket_connect(f"{WS_URL}/v1/projects/nope/events") as socket:
        socket.send_text(json.dumps({"token": TOKEN}))
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()
    assert (closed.value.code, closed.value.reason) == (1008, "E185")


def test_a_listener_without_the_token_is_closed_with_1008_and_e182(client: TestClient) -> None:
    pid = new_project(client)
    with client.websocket_connect(f"{WS_URL}/v1/projects/{pid}/events") as socket:
        socket.send_text(json.dumps({"token": "wrong"}))
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()
    assert (closed.value.code, closed.value.reason) == (1008, "E182")
    assert state_of(client).events.listeners(pid) == 0


def test_a_listener_holds_the_service_and_leaving_unsubscribes(client: TestClient) -> None:
    pid = new_project(client)
    state = state_of(client)
    with client.websocket_connect(f"{WS_URL}/v1/projects/{pid}/events") as socket:
        socket.send_text(json.dumps({"token": TOKEN}))
        socket.receive_json()
        assert state.events.listeners(pid) == 1
        assert state.lifetime.holds >= 1
    wait_until(lambda: state.events.listeners(pid) == 0)
    wait_until(lambda: state.lifetime.holds == 0)
    # A write after the listener left reaches nobody and is still saved.
    assert (
        client.put(
            f"/v1/projects/{pid}/model", content=json.dumps(model_of(client, pid))
        ).status_code
        == 200
    )


def test_a_write_between_listening_and_reading_the_revision_is_sent_once(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = new_project(client)
    models = state_of(client).models
    body = json.dumps(model_of(client, pid)).encode("utf-8")
    read_revision = models.revision

    def raced(project: str) -> int:
        models.put(project, body, None, "ui")
        return read_revision(project)

    monkeypatch.setattr(models, "revision", raced)
    with client.websocket_connect(f"{WS_URL}/v1/projects/{pid}/events") as socket:
        socket.send_text(json.dumps({"token": TOKEN}))
        assert socket.receive_json() == {"type": "model", "revision": 1, "client": None}
        client.put(f"/v1/projects/{pid}/model", content=body)
        assert socket.receive_json() == {"type": "model", "revision": 2, "client": "script"}


def test_messages_from_the_listener_are_ignored(client: TestClient) -> None:
    pid = new_project(client)
    with client.websocket_connect(f"{WS_URL}/v1/projects/{pid}/events") as socket:
        socket.send_text(json.dumps({"token": TOKEN}))
        socket.receive_json()
        socket.send_text("hello")
        client.put(f"/v1/projects/{pid}/model", content=json.dumps(model_of(client, pid)))
        assert socket.receive_json()["revision"] == 1


# --- the broadcaster on its own ----------------------------------------------------------


def test_publishing_with_no_listener_does_nothing() -> None:
    events = ProjectEvents()
    events.model_written("p", 1, "ui")
    events.run_changed("p", "r", "done")
    assert events.listeners("p") == 0


def test_a_listener_receives_events_in_order_and_from_threads() -> None:
    events = ProjectEvents()

    async def listen() -> list[Any]:
        with events.listen("p") as listener:
            assert events.listeners("p") == 1
            threads = [
                threading.Thread(target=events.model_written, args=("p", n, "script"))
                for n in (1, 2)
            ]
            for thread in threads:
                thread.start()
                thread.join()
            events.model_written("q", 9, "ui")
            return [await listener.next(), await listener.next()]

    received = asyncio.run(listen())
    assert [event["revision"] for event in received] == [1, 2]
    assert events.listeners("p") == 0


def test_an_event_for_a_listener_whose_loop_has_closed_is_dropped() -> None:
    events = ProjectEvents()
    loop = asyncio.new_event_loop()
    held: list[Any] = []

    async def subscribe() -> None:
        listening = events.listen("p")
        listening.__enter__()
        held.append(listening)

    loop.run_until_complete(subscribe())
    loop.close()
    events.model_written("p", 1, "ui")
    assert events.listeners("p") == 1
