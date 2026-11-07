"""The run endpoints (spec 3 "Endpoints", "Service rules", "Progress events"; AKS-112):
``POST``/``GET /v1/projects/{pid}/runs``, ``GET /v1/runs/{rid}``, ``POST .../cancel``,
``GET .../events`` (WebSocket), ``GET .../summary`` and ``GET .../tables/{name}``, with the
run queue, the run limits, E191 recovery and the project ``run`` events.

Most runs use ``GatedAdapter`` (``run_adapters.py``), which waits for a ``GO`` file in its
workdir, so a test decides when each run ends; the search, the optimization model and the
coffee shop run through the product's own adapters. Every wait is on a condition with a
generous timeout, never on a fixed time.
"""

import concurrent.futures
import dataclasses
import json
import sqlite3
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from lcsim.engines.adapter import EngineAdapter
from lcsim.engines.optimize.adapter import HighsAdapter
from lcsim.engines.process.adapter import ProcessAdapter
from lcsim.runs.lock import LOCK_FILE, RunLock, take_lock
from lcsim.runs.manifest import MANIFEST_FILE, read_manifest, write_manifest
from lcsim.runs.targets import LocalTarget
from lcsim.service.app import create_app
from lcsim.service.config import ServiceConfig
from lcsim.service.errors import ServiceError
from lcsim.service.hardware import SETTINGS_FILE, tier_workers
from lcsim.service.projects_store import PROJECT_FILE
from lcsim.service.state import ServiceState
from service.run_adapters import GO_FILE, RUN_RECORD, WAITING, GatedAdapter
from service.service_support import AUTH, BASE_URL, TOKEN, WS_URL, assert_error

Json = dict[str, Any]

ROOT = Path(__file__).resolve().parents[2]
TIMEOUT_S = 120.0
FINAL = ("done", "failed", "cancelled")


def shop(engine: str = "gated") -> Json:
    """The coffee shop, short: 2 replications of 2 h."""
    model: Json = json.loads((ROOT / "examples" / "coffee_shop.json").read_text())
    model["experiments"][0].update(length="2 h", warmup="0 s", replications=2)
    model["run"]["engine"] = engine
    return model


def search_model() -> Json:
    """The machine-count benchmark, small: tills 1 or 2, 2 replications of 2 h."""
    model: Json = json.loads((ROOT / "benchmarks" / "machine_count" / "model.json").read_text())
    model["parameters"]["tills"]["max"] = 2
    model["experiments"][0].update(length="2 h", warmup="0 s", replications=2)
    model["experiments"][0]["search"].update(budget=2, replications=2)
    model["run"] = {"target": "local", "fidelity": "standard", "engine": "simpy"}
    return model


def product_mix() -> Json:
    model: Json = json.loads((ROOT / "benchmarks" / "product_mix" / "model.json").read_text())
    return model


@pytest.fixture
def run_config(config: ServiceConfig) -> ServiceConfig:
    adapters: dict[str, EngineAdapter] = {
        "gated": GatedAdapter(),
        "simpy": ProcessAdapter(),
        "highs": HighsAdapter(),
    }
    return dataclasses.replace(config, adapters=adapters, websocket_auth_timeout_s=1.0)


def write_settings(config: ServiceConfig, **settings: object) -> None:
    config.config_dir.mkdir(parents=True, exist_ok=True)
    (config.config_dir / SETTINGS_FILE).write_text(json.dumps(settings))


@pytest.fixture
def client(run_config: ServiceConfig) -> Iterator[TestClient]:
    with TestClient(create_app(run_config), base_url=BASE_URL, headers=AUTH) as test_client:
        yield test_client


def state_of(client: TestClient) -> ServiceState:
    app = client.app
    assert isinstance(app, FastAPI)
    state = app.state.service
    assert isinstance(state, ServiceState)
    return state


def project(client: TestClient, model: Json | None = None, domain: str = "process") -> str:
    response = client.post("/v1/projects", json={"name": "Shop", "domain": domain})
    assert response.status_code == 200, response.text
    pid: str = response.json()["id"]
    if model is not None:
        put = client.put(f"/v1/projects/{pid}/model", content=json.dumps(model))
        assert put.status_code == 200, put.text
    return pid


def folder_of(client: TestClient, pid: str) -> Path:
    return state_of(client).projects.folder(pid)


def run_folder(client: TestClient, pid: str, rid: str) -> Path:
    return folder_of(client, pid) / "runs" / rid


def start(client: TestClient, pid: str, body: Json | None = None, **headers: str) -> str:
    response = client.post(
        f"/v1/projects/{pid}/runs",
        json={"experiment_id": "base"} if body is None else body,
        headers=headers,
    )
    assert response.status_code == 202, response.text
    body_out = response.json()
    assert set(body_out) == {"run_id"}
    rid: str = body_out["run_id"]
    return rid


def get_run(client: TestClient, rid: str) -> Json:
    response = client.get(f"/v1/runs/{rid}")
    assert response.status_code == 200, response.text
    run: Json = response.json()
    return run


def wait_until(condition: Callable[[], object], timeout_s: float = TIMEOUT_S) -> None:
    deadline = time.monotonic() + timeout_s
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.02)


def wait_state(client: TestClient, rid: str, *states: str) -> Json:
    found: Json = {}

    def reached() -> bool:
        found.update(get_run(client, rid))
        return found["state"] in states

    wait_until(reached)
    return found


def release(client: TestClient, pid: str, rid: str) -> None:
    (run_folder(client, pid, rid) / "engine" / GO_FILE).write_text("")


def waiting(client: TestClient, rid: str) -> Json:
    """Waits until the gated run is running and has reported its progress."""
    found: Json = {}

    def reported() -> bool:
        found.update(get_run(client, rid))
        return bool(found["state"] == "running" and found["message"] == WAITING)

    wait_until(reported)
    return found


def events_of(client: TestClient, rid: str) -> Any:
    socket = client.websocket_connect(f"{WS_URL}/v1/runs/{rid}/events")
    return socket


def read_until_closed(socket: Any) -> tuple[list[Json], int]:
    events: list[Json] = []
    while True:
        message = socket.receive()
        if message["type"] == "websocket.close":
            return events, message["code"]
        events.append(json.loads(message["text"]))


# --- POST /v1/projects/{pid}/runs --------------------------------------------------------


def test_a_run_is_accepted_with_202_and_reaches_done_with_a_full_run_folder(
    client: TestClient,
) -> None:
    pid = project(client, shop())
    rid = start(client, pid, None, **{"X-Client": "ui"})
    waiting(client, rid)
    release(client, pid, rid)
    run = wait_state(client, rid, *FINAL)
    assert run["state"] == "done"
    folder = run_folder(client, pid, rid)
    for name in ("model.json", "manifest.json", "summary.json", "log.txt", "engine"):
        assert (folder / name).exists(), name
    assert (folder / "tables" / "replications.parquet").is_file()
    assert not (folder / LOCK_FILE).exists()
    manifest = read_manifest(folder)
    assert manifest["client"] == "ui"
    assert manifest["project_id"] == pid
    assert manifest["target"] == "local"
    assert manifest["experiment_id"] == "base"
    record = json.loads((folder / "engine" / RUN_RECORD).read_text())
    hardware = state_of(client).hardware
    assert record["workers"] == tier_workers(state_of(client).tier, hardware.cores)
    model_bytes = (folder_of(client, pid) / "model.json").read_bytes()
    assert (folder / "model.json").read_bytes() == model_bytes


def test_a_run_without_x_client_records_script(client: TestClient) -> None:
    pid = project(client, shop())
    rid = start(client, pid)
    waiting(client, rid)
    assert read_manifest(run_folder(client, pid, rid))["client"] == "script"
    release(client, pid, rid)
    assert wait_state(client, rid, *FINAL)["state"] == "done"


@pytest.mark.parametrize(
    ("body", "path"),
    [
        ({}, "/experiment_id"),
        ({"experiment_id": "nope"}, "/experiment_id"),
        ({"experiment_id": 5}, "/experiment_id"),
        ({"experiment_id": "base", "extra": 1}, "/extra"),
        ({"experiment_id": "base", "target": ["local"]}, "/target"),
        ([1, 2], ""),
    ],
)
def test_a_bad_run_request_is_400_with_e184_and_creates_nothing(
    client: TestClient, body: object, path: str
) -> None:
    pid = project(client, shop())
    response = client.post(f"/v1/projects/{pid}/runs", json=body)
    assert response.status_code == 400, response.text
    assert_error(response.json(), "E184")
    assert [issue["path"] for issue in response.json()["issues"]] == [path]
    assert list((folder_of(client, pid) / "runs").iterdir()) == []


def test_a_request_body_that_is_not_json_is_400_with_e184(client: TestClient) -> None:
    pid = project(client, shop())
    response = client.post(
        f"/v1/projects/{pid}/runs", content=b"{nope", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
    assert_error(response.json(), "E184")


def test_an_optimization_model_runs_without_a_body_and_has_no_tables(
    client: TestClient,
) -> None:
    pid = project(client, product_mix(), domain="optimization")
    response = client.post(f"/v1/projects/{pid}/runs")
    assert response.status_code == 202, response.text
    rid = response.json()["run_id"]
    run = wait_state(client, rid, *FINAL)
    assert run["state"] == "done"
    assert run["experiment_id"] is None
    summary = client.get(f"/v1/runs/{rid}/summary").json()
    assert summary["summary"]["objective"] == pytest.approx(2200)
    assert summary["findings"] == []
    for name in ("replications", "timeseries"):
        response = client.get(f"/v1/runs/{rid}/tables/{name}")
        assert response.status_code == 404
        assert_error(response.json(), "E185")


def test_an_experiment_id_for_an_optimization_model_is_400(client: TestClient) -> None:
    pid = project(client, product_mix(), domain="optimization")
    response = client.post(f"/v1/projects/{pid}/runs", json={"experiment_id": "base"})
    assert response.status_code == 400
    assert_error(response.json(), "E184")
    assert response.json()["issues"][0]["path"] == "/experiment_id"


def test_a_model_with_errors_is_422_listing_the_issues_and_creates_nothing(
    client: TestClient,
) -> None:
    model = shop()
    model["components"][1]["params"]["service"]["mean"] = "-1 min"
    model["connections"].pop()
    pid = project(client, model)
    response = client.post(f"/v1/projects/{pid}/runs", json={"experiment_id": "base"})
    assert response.status_code == 422, response.text
    body = response.json()
    assert_error(body, body["issues"][0]["code"])
    errors = [issue for issue in body["issues"] if issue["severity"] == "error"]
    assert body["error"]["code"] == errors[0]["code"]
    assert len(errors) >= 2
    assert list((folder_of(client, pid) / "runs").iterdir()) == []


def test_a_target_in_the_request_overrides_the_files(client: TestClient) -> None:
    model = shop()
    model["run"]["target"] = "cluster"
    pid = project(client, model)
    refused = client.post(f"/v1/projects/{pid}/runs", json={"experiment_id": "base"})
    assert refused.status_code == 422
    assert_error(refused.json(), "E172")
    assert refused.json()["issues"][0]["path"] == "/run/target"
    rid = start(client, pid, {"experiment_id": "base", "target": "local"})
    waiting(client, rid)
    assert read_manifest(run_folder(client, pid, rid))["target"] == "local"
    client.post(f"/v1/runs/{rid}/cancel")
    wait_state(client, rid, *FINAL)


@pytest.mark.parametrize("target", ["remote", "cluster", "moon"])
def test_an_unavailable_target_in_the_request_is_422_with_e172(
    client: TestClient, target: str
) -> None:
    pid = project(client, shop())
    response = client.post(
        f"/v1/projects/{pid}/runs", json={"experiment_id": "base", "target": target}
    )
    assert response.status_code == 422
    assert_error(response.json(), "E172")
    issue = response.json()["issues"][0]
    assert issue["path"] == "/target"
    assert target in issue["message"]
    assert list((folder_of(client, pid) / "runs").iterdir()) == []


def test_runs_of_an_unknown_project_are_404(client: TestClient) -> None:
    for response in (
        client.post("/v1/projects/nope/runs", json={"experiment_id": "base"}),
        client.get("/v1/projects/nope/runs"),
    ):
        assert response.status_code == 404
        assert_error(response.json(), "E185")


def test_runs_of_a_project_that_cannot_be_read_are_400_with_e186(client: TestClient) -> None:
    pid = project(client, shop())
    (folder_of(client, pid) / PROJECT_FILE).write_text("{")
    for response in (
        client.post(f"/v1/projects/{pid}/runs", json={"experiment_id": "base"}),
        client.get(f"/v1/projects/{pid}/runs"),
    ):
        assert response.status_code == 400
        assert_error(response.json(), "E186")


def test_a_model_json_that_cannot_be_used_is_400_with_e186(client: TestClient) -> None:
    pid = project(client, shop())
    (folder_of(client, pid) / "model.json").write_text("{")
    response = client.post(f"/v1/projects/{pid}/runs", json={"experiment_id": "base"})
    assert response.status_code == 400
    assert_error(response.json(), "E186")


# --- GET /v1/projects/{pid}/runs and GET /v1/runs/{rid} ---------------------------------


def test_the_runs_of_a_project_are_listed_in_the_order_accepted(client: TestClient) -> None:
    pid = project(client, shop())
    other = project(client, shop())
    first = start(client, pid)
    second = start(client, pid)
    start(client, other)
    runs = client.get(f"/v1/projects/{pid}/runs").json()
    assert [run["run_id"] for run in runs] == [first, second]
    for run in runs:
        assert set(run) == {
            "run_id",
            "project_id",
            "experiment_id",
            "state",
            "fraction",
            "message",
            "created",
            "started",
            "ended",
            "error",
        }
        assert run["project_id"] == pid
    assert runs[1]["state"] == "queued"
    assert runs[1]["fraction"] == 0
    assert runs[1]["message"] == ""


def test_a_run_shows_its_state_progress_and_timings(client: TestClient) -> None:
    pid = project(client, shop())
    rid = start(client, pid)
    run = waiting(client, rid)
    assert run["fraction"] == 0.5
    assert run["started"] is not None
    assert run["ended"] is None
    assert run["error"] is None
    release(client, pid, rid)
    done = wait_state(client, rid, *FINAL)
    assert done["fraction"] == 1.0
    assert done["ended"] is not None


@pytest.mark.parametrize("rid", ["nope", "20261107T120000-AAAAAA", "20261107t120000-aaaaaa"])
def test_an_unknown_run_is_404_on_every_run_route(client: TestClient, rid: str) -> None:
    project(client, shop())
    for response in (
        client.get(f"/v1/runs/{rid}"),
        client.post(f"/v1/runs/{rid}/cancel"),
        client.get(f"/v1/runs/{rid}/summary"),
        client.get(f"/v1/runs/{rid}/tables/replications"),
    ):
        assert response.status_code == 404, response.text
        assert_error(response.json(), "E185")


def test_a_run_folder_of_an_unregistered_project_is_not_found(
    client: TestClient, tmp_path: Path
) -> None:
    pid = project(client, shop())
    rid = start(client, pid)
    client.post(f"/v1/runs/{rid}/cancel")
    wait_state(client, rid, *FINAL)
    # The project moves to another folder: its old folder's runs are no longer found.
    copy = tmp_path / "moved"
    copy.mkdir()
    (copy / PROJECT_FILE).write_text((folder_of(client, pid) / PROJECT_FILE).read_text())
    (copy / "model.json").write_text((folder_of(client, pid) / "model.json").read_text())
    (folder_of(client, pid) / PROJECT_FILE).unlink()
    opened = client.post("/v1/projects/open", json={"path": str(copy)})
    assert opened.status_code == 200, opened.text
    response = client.get(f"/v1/runs/{rid}")
    assert response.status_code == 404
    assert_error(response.json(), "E185")


def test_a_run_whose_manifest_cannot_be_read_is_404_and_not_listed(client: TestClient) -> None:
    pid = project(client, shop())
    rid = start(client, pid)
    client.post(f"/v1/runs/{rid}/cancel")
    wait_state(client, rid, *FINAL)
    (run_folder(client, pid, rid) / MANIFEST_FILE).write_text("[]")
    response = client.get(f"/v1/runs/{rid}")
    assert response.status_code == 404
    assert_error(response.json(), "E185")
    assert client.get(f"/v1/projects/{pid}/runs").json() == []


def test_a_lost_index_is_rebuilt_from_the_run_folders(client: TestClient) -> None:
    pid = project(client, shop())
    first = start(client, pid)
    second = start(client, pid)
    for rid in (second, first):
        client.post(f"/v1/runs/{rid}/cancel")
        wait_state(client, rid, *FINAL)
    index = folder_of(client, pid) / "index.sqlite"
    assert index.is_file()
    index.write_bytes(b"not a database at all, not even close" * 100)
    assert [run["run_id"] for run in client.get(f"/v1/projects/{pid}/runs").json()] == [
        first,
        second,
    ]
    index.unlink()
    assert get_run(client, second)["state"] == "cancelled"


# --- POST /v1/runs/{rid}/cancel ----------------------------------------------------------


def test_cancelling_a_queued_run_ends_it_at_once(client: TestClient) -> None:
    pid = project(client, shop())
    first = start(client, pid)
    second = start(client, pid)
    waiting(client, first)
    response = client.post(f"/v1/runs/{second}/cancel")
    assert response.status_code == 200
    assert response.json()["state"] == "cancelled"
    assert response.json()["run_id"] == second
    client.post(f"/v1/runs/{first}/cancel")
    assert wait_state(client, first, *FINAL)["state"] == "cancelled"
    assert read_manifest(run_folder(client, pid, second))["started"] is None


def test_cancelling_a_running_run_is_accepted_and_ends_it_cancelled(client: TestClient) -> None:
    pid = project(client, shop())
    rid = start(client, pid)
    waiting(client, rid)
    response = client.post(f"/v1/runs/{rid}/cancel")
    assert response.status_code == 200
    assert response.json()["state"] in ("running", "cancelled")
    again = client.post(f"/v1/runs/{rid}/cancel")
    assert again.status_code in (200, 409)
    run = wait_state(client, rid, *FINAL)
    assert run["state"] == "cancelled"
    assert not (run_folder(client, pid, rid) / "summary.json").exists()


def test_cancelling_a_run_that_has_ended_is_409_with_e188(client: TestClient) -> None:
    pid = project(client, shop())
    rid = start(client, pid)
    waiting(client, rid)
    release(client, pid, rid)
    wait_state(client, rid, *FINAL)
    response = client.post(f"/v1/runs/{rid}/cancel")
    assert response.status_code == 409
    assert_error(response.json(), "E188")
    assert get_run(client, rid)["state"] == "done"


# --- GET .../summary and GET .../tables/{name} ------------------------------------------


@pytest.fixture
def done_run(client: TestClient) -> str:
    """A run that is done: the run endpoints show ``done`` only once it has left the live
    feed (CI on PR #36), which the fixture also checks."""
    pid = project(client, shop())
    rid = start(client, pid)
    waiting(client, rid)
    release(client, pid, rid)
    assert wait_state(client, rid, *FINAL)["state"] == "done"
    wait_until(lambda: state_of(client).runs.feed.snapshot(rid) is None)
    return rid


@pytest.fixture
def slow_final(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Widens the gap between the manifest saying ``done`` and the run leaving the live
    feed, as a slow runner does (CI on PR #36)."""
    feed = state_of(client).runs.feed
    original = feed.state

    def state(run_id: str, new: str) -> None:
        if new in FINAL:
            time.sleep(1.0)
        original(run_id, new)

    monkeypatch.setattr(feed, "state", state)


@pytest.mark.usefixtures("slow_final")
def test_done_run_is_not_live_even_when_the_run_leaves_the_feed_slowly(
    client: TestClient, done_run: str
) -> None:
    assert state_of(client).runs.feed.snapshot(done_run) is None
    with events_of(client, done_run) as socket:
        socket.send_text(json.dumps({"token": TOKEN}))
        events, code = read_until_closed(socket)
    assert events == [
        {"type": "state", "state": "done"},
        {"type": "progress", "fraction": 1.0, "message": ""},
    ]
    assert code == 1000


def test_a_stream_opened_while_a_run_is_finishing_sends_done_exactly_once(
    client: TestClient, slow_unlock: None
) -> None:
    """Opened while the manifest is final but the run is not yet published (its lock is
    still being removed): the stream starts from the live ``running`` and ends with
    ``done`` once."""
    pid = project(client, shop())
    rid = start(client, pid)
    waiting(client, rid)
    release(client, pid, rid)
    folder = run_folder(client, pid, rid)
    wait_until(lambda: read_manifest(folder)["state"] == "done")
    with events_of(client, rid) as socket:
        socket.send_text(json.dumps({"token": TOKEN}))
        events, code = read_until_closed(socket)
    assert code == 1000
    states = [event for event in events if event["type"] == "state"]
    assert states[-1] == {"type": "state", "state": "done"}
    assert states.count({"type": "state", "state": "done"}) == 1
    assert not (folder / LOCK_FILE).exists()


def test_the_summary_is_summary_json_with_no_findings_yet(
    client: TestClient, done_run: str
) -> None:
    response = client.get(f"/v1/runs/{done_run}/summary")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"summary", "findings"}
    assert body["findings"] == []
    assert body["summary"]["experiment"] == "base"
    assert body["summary"]["scenarios"]["default"]["metrics"]["till.wait.mean"]["n"] == 1


def test_a_table_as_json_is_one_object_per_row_with_nan_as_null(
    client: TestClient, done_run: str
) -> None:
    for query in ("", "?format=json"):
        response = client.get(f"/v1/runs/{done_run}/tables/replications{query}")
        assert response.status_code == 200
        assert response.json() == [
            {
                "scenario": "default",
                "replication": 0,
                "metric": "till.wait.mean",
                "value": 12.5,
                "unit": "s",
            },
            {
                "scenario": "default",
                "replication": 1,
                "metric": "till.wait.mean",
                "value": None,
                "unit": "s",
            },
        ]
    timeseries = client.get(f"/v1/runs/{done_run}/tables/timeseries").json()
    assert timeseries[0]["time_s"] == 0.0


def test_a_table_as_csv_has_a_header_and_an_empty_field_for_nan(
    client: TestClient, done_run: str
) -> None:
    response = client.get(f"/v1/runs/{done_run}/tables/replications?format=csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.text.splitlines() == [
        "scenario,replication,metric,value,unit",
        "default,0,till.wait.mean,12.5,s",
        "default,1,till.wait.mean,,s",
    ]


@pytest.mark.parametrize("value", ["xml", "JSON", ""])
def test_another_table_format_is_400_with_e184(
    client: TestClient, done_run: str, value: str
) -> None:
    response = client.get(f"/v1/runs/{done_run}/tables/replications?format={value}")
    assert response.status_code == 400
    assert_error(response.json(), "E184")


@pytest.mark.parametrize("name", ["summary", "Replications", "...", "replications.parquet"])
def test_another_table_name_is_404(client: TestClient, done_run: str, name: str) -> None:
    response = client.get(f"/v1/runs/{done_run}/tables/{name}")
    assert response.status_code == 404
    assert_error(response.json(), "E185")


def test_a_table_file_that_cannot_be_read_is_404(client: TestClient, done_run: str) -> None:
    pid = get_run(client, done_run)["project_id"]
    (run_folder(client, pid, done_run) / "tables" / "timeseries.parquet").write_text("x")
    response = client.get(f"/v1/runs/{done_run}/tables/timeseries")
    assert response.status_code == 404
    assert_error(response.json(), "E185")
    (run_folder(client, pid, done_run) / "summary.json").write_text("{")
    response = client.get(f"/v1/runs/{done_run}/summary")
    assert response.status_code == 404
    assert_error(response.json(), "E185")


def test_the_summary_and_tables_of_a_run_not_done_are_409_with_e188(client: TestClient) -> None:
    pid = project(client, shop())
    rid = start(client, pid)
    waiting(client, rid)
    for response in (
        client.get(f"/v1/runs/{rid}/summary"),
        client.get(f"/v1/runs/{rid}/tables/replications"),
        client.get(f"/v1/runs/{rid}/tables/replications?format=csv"),
    ):
        assert response.status_code == 409
        assert_error(response.json(), "E188")
    client.post(f"/v1/runs/{rid}/cancel")
    wait_state(client, rid, *FINAL)


# --- The run queue and the run limits ---------------------------------------------------


def test_a_second_run_waits_in_queued_until_the_first_ends(client: TestClient) -> None:
    pid = project(client, shop())
    first = start(client, pid)
    second = start(client, pid)
    waiting(client, first)
    assert get_run(client, second)["state"] == "queued"
    release(client, pid, first)
    wait_state(client, first, *FINAL)
    waiting(client, second)
    release(client, pid, second)
    assert wait_state(client, second, *FINAL)["state"] == "done"


def test_concurrent_requests_start_in_the_order_they_were_accepted(client: TestClient) -> None:
    pids = [project(client, shop()) for _ in range(2)]
    with concurrent.futures.ThreadPoolExecutor(6) as pool:
        rids = list(pool.map(lambda n: start(client, pids[n % 2]), range(6)))
    # One run at a time: each starts only after the one before it has ended, and the order
    # in which they start is the order of acceptance, which the lists and the manifests'
    # "created" times show.
    started: list[str] = []
    for _ in rids:
        wait_until(lambda: any(get_run(client, rid)["state"] == "running" for rid in rids))
        running = [rid for rid in rids if get_run(client, rid)["state"] == "running"]
        assert len(running) == 1
        current = running[0]
        started.append(current)
        waiting(client, current)
        release(client, get_run(client, current)["project_id"], current)
        wait_state(client, current, *FINAL)
    assert sorted(started) == sorted(rids)
    created = [get_run(client, rid)["created"] for rid in started]
    assert created == sorted(created)
    for pid in pids:
        listed = [run["run_id"] for run in client.get(f"/v1/projects/{pid}/runs").json()]
        assert listed == [rid for rid in started if rid in listed]
        assert len(listed) == 3


def locate(client: TestClient, rid: str) -> Path:
    run = get_run(client, rid)
    return run_folder(client, run["project_id"], rid)


def test_max_concurrent_runs_from_the_settings_lets_two_run_at_once(
    run_config: ServiceConfig,
) -> None:
    write_settings(run_config, max_concurrent_runs=2)
    with TestClient(create_app(run_config), base_url=BASE_URL, headers=AUTH) as client:
        pid = project(client, shop())
        rids = [start(client, pid) for _ in range(3)]
        waiting(client, rids[0])
        waiting(client, rids[1])
        assert get_run(client, rids[2])["state"] == "queued"
        for rid in rids:
            client.post(f"/v1/runs/{rid}/cancel")
            wait_state(client, rid, *FINAL)


def test_a_run_over_its_time_limit_fails_with_e192(run_config: ServiceConfig) -> None:
    write_settings(run_config, run_time_limit_s=0.5)
    with TestClient(create_app(run_config), base_url=BASE_URL, headers=AUTH) as client:
        pid = project(client, shop())
        rid = start(client, pid)
        run = wait_state(client, rid, *FINAL)
        assert run["state"] == "failed"
        assert run["error"]["code"] == "E192"
        assert "0.5 s" in run["error"]["message"]


def test_a_run_holds_the_service_until_it_ends(client: TestClient) -> None:
    lifetime = state_of(client).lifetime
    pid = project(client, shop())
    rid = start(client, pid)
    waiting(client, rid)
    assert lifetime.holds >= 1
    release(client, pid, rid)
    wait_state(client, rid, *FINAL)
    wait_until(lambda: lifetime.holds == 0)


# --- Progress events --------------------------------------------------------------------


def test_events_mid_run_start_with_state_and_progress_then_follow_to_done(
    client: TestClient,
) -> None:
    pid = project(client, shop())
    rid = start(client, pid)
    waiting(client, rid)
    with events_of(client, rid) as socket:
        socket.send_text(json.dumps({"token": TOKEN}))
        assert socket.receive_json() == {"type": "state", "state": "running"}
        assert socket.receive_json() == {"type": "progress", "fraction": 0.5, "message": WAITING}
        release(client, pid, rid)
        events, code = read_until_closed(socket)
    assert code == 1000
    assert events[-1] == {"type": "state", "state": "done"}
    assert [event for event in events if event["type"] == "state"] == [events[-1]]
    assert {"type": "progress", "fraction": 0.9, "message": "Finishing"} in events


def test_events_after_done_send_the_final_state_and_progress_and_close(
    client: TestClient, done_run: str
) -> None:
    with events_of(client, done_run) as socket:
        socket.send_text(json.dumps({"token": TOKEN}))
        events, code = read_until_closed(socket)
    assert events == [
        {"type": "state", "state": "done"},
        {"type": "progress", "fraction": 1.0, "message": ""},
    ]
    assert code == 1000


def test_events_of_a_queued_run_follow_it_through_cancel(client: TestClient) -> None:
    pid = project(client, shop())
    first = start(client, pid)
    second = start(client, pid)
    with events_of(client, second) as socket:
        socket.send_text(json.dumps({"token": TOKEN}))
        assert socket.receive_json() == {"type": "state", "state": "queued"}
        assert socket.receive_json() == {"type": "progress", "fraction": 0.0, "message": ""}
        client.post(f"/v1/runs/{second}/cancel")
        events, code = read_until_closed(socket)
    assert events == [{"type": "state", "state": "cancelled"}]
    assert code == 1000
    client.post(f"/v1/runs/{first}/cancel")
    wait_state(client, first, *FINAL)


def test_events_of_an_unknown_run_close_with_1008_and_e185(client: TestClient) -> None:
    with events_of(client, "20261107T120000-AAAAAA") as socket:
        socket.send_text(json.dumps({"token": TOKEN}))
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()
    assert closed.value.code == 1008
    assert closed.value.reason == "E185"


def test_events_without_the_token_close_with_1008_and_e182(
    client: TestClient, done_run: str
) -> None:
    with events_of(client, done_run) as socket:
        socket.send_text(json.dumps({"token": "wrong"}))
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()
    assert closed.value.code == 1008
    assert closed.value.reason == "E182"


def test_a_watcher_that_leaves_does_not_stop_the_run(client: TestClient) -> None:
    pid = project(client, shop())
    rid = start(client, pid)
    waiting(client, rid)
    with events_of(client, rid) as socket:
        socket.send_text(json.dumps({"token": TOKEN}))
        socket.receive_json()
    release(client, pid, rid)
    assert wait_state(client, rid, *FINAL)["state"] == "done"


def test_project_events_carry_every_run_state_change(client: TestClient) -> None:
    pid = project(client, shop())
    with client.websocket_connect(f"{WS_URL}/v1/projects/{pid}/events") as socket:
        socket.send_text(json.dumps({"token": TOKEN}))
        assert socket.receive_json()["type"] == "model"
        rid = start(client, pid)
        waiting(client, rid)
        release(client, pid, rid)
        seen = [socket.receive_json() for _ in range(3)]
    assert seen == [
        {"type": "run", "run_id": rid, "state": "queued"},
        {"type": "run", "run_id": rid, "state": "running"},
        {"type": "run", "run_id": rid, "state": "done"},
    ]


# --- Search and optimization runs -------------------------------------------------------


def test_a_search_runs_through_the_api_and_its_progress_messages_reach_the_stream(
    client: TestClient,
) -> None:
    pid = project(client, search_model())
    rid = start(client, pid)
    with events_of(client, rid) as socket:
        socket.send_text(json.dumps({"token": TOKEN}))
        events, code = read_until_closed(socket)
    assert code == 1000
    assert events[-1] == {"type": "state", "state": "done"}
    messages = [event["message"] for event in events if event["type"] == "progress"]
    assert any(message.startswith("Search, candidate ") for message in messages)
    assert any(message.startswith("Confirmation, candidate ") for message in messages)
    fractions = [event["fraction"] for event in events if event["type"] == "progress"]
    assert fractions == sorted(fractions)
    summary = client.get(f"/v1/runs/{rid}/summary").json()["summary"]
    assert "search" in summary
    assert "optimizer" in read_manifest(run_folder(client, pid, rid))


# --- Recovery, shutdown -----------------------------------------------------------------


def orphan(folder: Path, rid: str, state: str) -> Path:
    """A run folder whose manifest says ``state`` and whose process is gone."""
    run = folder / "runs" / rid
    (run / "engine").mkdir(parents=True)
    manifest = {
        "run_id": rid,
        "project_id": None,
        "experiment_id": "base",
        "scenario_ids": ["default"],
        "state": state,
        "created": "2026-11-07T10:00:00.000Z",
        "started": None,
        "ended": None,
        "target": "local",
        "host": "h",
        "client": "script",
        "engine": {"name": "gated", "version": "1"},
        "generator": {"name": "PCG64DXSM", "numpy_version": "2"},
        "product_version": "0",
        "format_version": "0.1",
        "seed": 1,
        "fraction": 0.25,
        "data_files": [],
    }
    write_manifest(run, manifest)
    (run / LOCK_FILE).write_text("")
    return run


def test_orphaned_runs_are_failed_with_e191_when_the_service_starts(
    run_config: ServiceConfig,
) -> None:
    with TestClient(create_app(run_config), base_url=BASE_URL, headers=AUTH) as client:
        pid = project(client, shop())
        folder = folder_of(client, pid)
    running = orphan(folder, "20261107T100000-AAAAAA", "running")
    queued = orphan(folder, "20261107T100001-BBBBBB", "queued")
    broken = folder / "runs" / "20261107T100002-CCCCCC"
    broken.mkdir()
    (broken / MANIFEST_FILE).write_text("{")
    held = orphan(folder, "20261107T100003-DDDDDD", "running")
    lock = take_lock(held / LOCK_FILE)
    try:
        with TestClient(create_app(run_config), base_url=BASE_URL, headers=AUTH) as client:
            for run in (running, queued):
                manifest = read_manifest(run)
                assert manifest["state"] == "failed"
                assert manifest["error"]["code"] == "E191"
                assert not (run / LOCK_FILE).exists()
            assert read_manifest(held)["state"] == "running"
            assert (broken / MANIFEST_FILE).read_text() == "{"
            listed = [run["run_id"] for run in client.get(f"/v1/projects/{pid}/runs").json()]
            assert listed == [running.name, queued.name, held.name]
            assert get_run(client, running.name)["error"]["code"] == "E191"
    finally:
        lock.release()


def test_a_project_opened_later_is_recovered_when_first_used(
    client: TestClient, tmp_path: Path
) -> None:
    folder = tmp_path / "elsewhere"
    pid = project(client, shop())
    source = folder_of(client, pid)
    folder.mkdir()
    for name in (PROJECT_FILE, "model.json"):
        (folder / name).write_text((source / name).read_text())
    (source / PROJECT_FILE).unlink()
    run = orphan(folder, "20261107T100000-AAAAAA", "running")
    assert client.post("/v1/projects/open", json={"path": str(folder)}).status_code == 200
    assert get_run(client, run.name)["state"] == "failed"
    assert read_manifest(run)["error"]["code"] == "E191"


def test_a_service_that_stops_marks_its_unfinished_runs_failed_with_e191(
    run_config: ServiceConfig,
) -> None:
    with TestClient(create_app(run_config), base_url=BASE_URL, headers=AUTH) as client:
        pid = project(client, shop())
        first = start(client, pid)
        second = start(client, pid)
        waiting(client, first)
        folder = folder_of(client, pid)
    for rid in (first, second):
        manifest = read_manifest(folder / "runs" / rid)
        assert manifest["state"] == "failed", rid
        assert manifest["error"]["code"] == "E191"
        assert not (folder / "runs" / rid / LOCK_FILE).exists()


# --- Edges ------------------------------------------------------------------------------


def test_a_summary_holding_nan_is_404_not_500(client: TestClient, done_run: str) -> None:
    pid = get_run(client, done_run)["project_id"]
    (run_folder(client, pid, done_run) / "summary.json").write_text('{"mean": NaN}')
    response = client.get(f"/v1/runs/{done_run}/summary")
    assert response.status_code == 404
    assert_error(response.json(), "E185")


def test_text_that_is_not_valid_unicode_in_a_run_request_is_400(client: TestClient) -> None:
    pid = project(client, shop())
    for field in ("experiment_id", "target"):
        body = '{"' + field + '": "\\ud800"}'
        response = client.post(
            f"/v1/projects/{pid}/runs",
            content=body.encode(),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400, response.text
        assert_error(response.json(), "E184")
        assert response.json()["issues"][0]["path"] == f"/{field}"
    assert list((folder_of(client, pid) / "runs").iterdir()) == []


def test_a_project_that_cannot_be_read_does_not_hide_other_projects_runs(
    client: TestClient,
) -> None:
    broken = project(client, shop())
    pid = project(client, shop())
    rid = start(client, pid)
    client.post(f"/v1/runs/{rid}/cancel")
    wait_state(client, rid, *FINAL)
    (folder_of(client, broken) / PROJECT_FILE).unlink()
    assert get_run(client, rid)["state"] == "cancelled"


def test_events_close_with_1008_when_the_run_vanishes_after_it_was_found(
    client: TestClient, done_run: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs = state_of(client).runs

    def vanished(rid: str) -> Json:
        raise ServiceError(404, "E185", "gone")

    monkeypatch.setattr(runs, "run", vanished)
    with events_of(client, done_run) as socket:
        socket.send_text(json.dumps({"token": TOKEN}))
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_json()
    assert closed.value.code == 1008
    assert closed.value.reason == "E185"


def test_a_stop_that_cannot_wait_for_its_runs_says_so(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    pid = project(client, shop())
    rid = start(client, pid)
    waiting(client, rid)
    state_of(client).runs.stop(timeout_s=0)
    assert "still ending" in caplog.text
    run = wait_state(client, rid, *FINAL)
    assert run["state"] == "failed"
    assert run["error"]["code"] == "E191"


def test_a_run_folder_the_index_lacks_is_found_and_added(client: TestClient) -> None:
    pid = project(client, shop())
    rid = start(client, pid)
    client.post(f"/v1/runs/{rid}/cancel")
    wait_state(client, rid, *FINAL)
    index = folder_of(client, pid) / "index.sqlite"
    with sqlite3.connect(index) as connection:
        connection.execute("DELETE FROM runs")
    connection.close()
    assert get_run(client, rid)["state"] == "cancelled"
    assert [run["run_id"] for run in client.get(f"/v1/projects/{pid}/runs").json()] == [rid]


def test_a_table_cell_json_has_no_word_for_is_sent_as_text(
    client: TestClient, done_run: str
) -> None:
    pid = get_run(client, done_run)["project_id"]
    table = pa.table({"when": pa.array([0], pa.timestamp("s")), "unit": ["s"]})
    pq.write_table(table, run_folder(client, pid, done_run) / "tables" / "timeseries.parquet")
    rows = client.get(f"/v1/runs/{done_run}/tables/timeseries").json()
    assert rows == [{"when": "1970-01-01 00:00:00", "unit": "s"}]


#: Values json.loads takes but no response may carry (review of PR #36).
POISONED = ["1e999", "-1e999", "NaN", "-Infinity", '"\\ud800"']


@pytest.mark.parametrize("value", POISONED)
def test_a_manifest_that_cannot_be_written_back_is_404_everywhere_not_500(
    client: TestClient, done_run: str, value: str
) -> None:
    pid = get_run(client, done_run)["project_id"]
    path = run_folder(client, pid, done_run) / MANIFEST_FILE
    manifest = json.loads(path.read_text())
    path.write_text(json.dumps(manifest).replace('"fraction": 1.0', f'"fraction": {value}'))
    assert f'"fraction": {value}' in path.read_text()
    for response in (
        client.get(f"/v1/runs/{done_run}"),
        client.post(f"/v1/runs/{done_run}/cancel"),
        client.get(f"/v1/runs/{done_run}/summary"),
        client.get(f"/v1/runs/{done_run}/tables/replications"),
        client.get(f"/v1/runs/{done_run}/tables/replications?format=csv"),
    ):
        assert response.status_code == 404, response.text
        assert_error(response.json(), "E185")
    listed = client.get(f"/v1/projects/{pid}/runs")
    assert listed.status_code == 200
    assert listed.json() == []


@pytest.mark.parametrize("value", POISONED)
def test_a_summary_that_cannot_be_written_back_is_404_not_500(
    client: TestClient, done_run: str, value: str
) -> None:
    pid = get_run(client, done_run)["project_id"]
    (run_folder(client, pid, done_run) / "summary.json").write_text(f'{{"mean": {value}}}')
    response = client.get(f"/v1/runs/{done_run}/summary")
    assert response.status_code == 404, response.text
    assert_error(response.json(), "E185")
    assert client.get(f"/v1/runs/{done_run}").status_code == 200


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("fraction", 10**400),
        ("fraction", -1),
        ("fraction", 1.5),
        ("fraction", True),
        ("fraction", "1"),
        ("fraction", None),
        ("seed", 10**400),
        ("seed", -1),
        ("seed", 2**63),
        ("seed", 1.5),
        ("seed", True),
        ("seed", "1"),
        ("started", 5),
        ("ended", 10**400),
        ("experiment_id", 7),
        ("project_id", 7),
    ],
)
def test_a_manifest_field_of_another_kind_or_out_of_range_is_404(
    client: TestClient, done_run: str, key: str, value: object
) -> None:
    """Review of PR #36: every number read from disk is typed and bounded."""
    pid = get_run(client, done_run)["project_id"]
    path = run_folder(client, pid, done_run) / MANIFEST_FILE
    manifest = json.loads(path.read_text())
    manifest[key] = value
    path.write_text(json.dumps(manifest))
    for response in (
        client.get(f"/v1/runs/{done_run}"),
        client.get(f"/v1/runs/{done_run}/summary"),
        client.get(f"/v1/runs/{done_run}/tables/replications"),
    ):
        assert response.status_code == 404, response.text
        assert_error(response.json(), "E185")
    assert client.get(f"/v1/projects/{pid}/runs").json() == []


# --- The finishing order (CI on PR #36) -------------------------------------------------


@pytest.fixture
def slow_unlock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Widens the gap between the manifest turning final and ``worker.lock`` going away."""
    original = RunLock.release

    def release(self: RunLock, *, remove: bool = False) -> None:
        if remove:
            time.sleep(1.0)
        original(self, remove=remove)

    monkeypatch.setattr(RunLock, "release", release)


@pytest.mark.usefixtures("slow_unlock")
@pytest.mark.parametrize("ending", ["done", "cancelled"])
def test_a_final_state_is_visible_only_once_the_run_has_finished(
    client: TestClient, ending: str
) -> None:
    """Whoever sees the final state (the run endpoints, the run's events, the project's
    events) finds the run folder final: no ``worker.lock``, its queue place free and the
    run gone from the live feed."""
    pid = project(client, shop())
    with client.websocket_connect(f"{WS_URL}/v1/projects/{pid}/events") as project_socket:
        project_socket.send_text(json.dumps({"token": TOKEN}))
        project_socket.receive_json()
        rid = start(client, pid)
        waiting(client, rid)
        with events_of(client, rid) as socket:
            socket.send_text(json.dumps({"token": TOKEN}))
            if ending == "done":
                release(client, pid, rid)
            else:
                client.post(f"/v1/runs/{rid}/cancel")
            run = wait_state(client, rid, *FINAL)
            folder = run_folder(client, pid, rid)
            assert run["state"] == ending
            assert not (folder / LOCK_FILE).exists()
            assert state_of(client).runs.feed.snapshot(rid) is None
            assert state_of(client).runs.queue.running == 0
            events, _code = read_until_closed(socket)
        assert events[-1] == {"type": "state", "state": ending}
        assert not (folder / LOCK_FILE).exists()
        seen = [project_socket.receive_json() for _ in range(3)]
    assert seen[-1] == {"type": "run", "run_id": rid, "state": ending}
    assert not (folder / LOCK_FILE).exists()


@pytest.mark.usefixtures("slow_unlock")
def test_a_finishing_run_is_shown_as_it_was_until_it_has_finished(client: TestClient) -> None:
    """In the gap the manifest is final but the run endpoints still show ``running``, with
    no end time or error, and the summary is not yet readable."""
    pid = project(client, shop())
    rid = start(client, pid)
    waiting(client, rid)
    release(client, pid, rid)
    folder = run_folder(client, pid, rid)
    wait_until(lambda: read_manifest(folder)["state"] == "done")
    if (folder / LOCK_FILE).exists():  # inside the 1 s gap
        run = get_run(client, rid)
        assert run["state"] == "running"
        assert run["ended"] is None
        assert run["error"] is None
        assert client.get(f"/v1/runs/{rid}/summary").status_code == 409
    assert wait_state(client, rid, *FINAL)["state"] == "done"


def test_the_finishing_hooks_ignore_runs_they_do_not_know(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """Defensive paths: a run this service does not drive, and a job that returned
    without a final state (logged)."""
    runs = state_of(client).runs
    pid = project(client, shop())
    local = LocalTarget(folder_of(client, pid) / "runs", adapters=runs.adapters)
    run = local.create(json.dumps(shop()).encode(), "base")
    runs._on_state(run, "running")
    runs._publish_final(run.run_id, "done")
    runs._finished(run)
    assert "returned without reaching a final state" in caplog.text
    run.cancel()
