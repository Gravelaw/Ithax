"""The request log of the pointer-only end-to-end test (``request_log.py``, AKS-121): it logs
every call that reaches the service, the refused ones too, and its check passes a log of
documented routes only and fails anything else."""

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from fastapi import FastAPI
from starlette.testclient import TestClient

from lcsim.service.discovery import probe, read_service_file
from service.endpoint_table import spec_table
from service.request_log import LOG_FILE_VARIABLE, RequestLog, check, read_log
from service.service_support import AUTH, BASE_URL, TOKEN, WS_URL

ROOT = Path(__file__).resolve().parents[2]


def logged(app: FastAPI, log: Path) -> TestClient:
    return TestClient(RequestLog(app, log), base_url=BASE_URL, headers=AUTH)


def test_every_call_is_logged_with_its_route_status_and_client(
    app: FastAPI, tmp_path: Path
) -> None:
    log = tmp_path / "requests.jsonl"
    with logged(app, log) as client:
        assert client.get("/v1/system", headers={"X-Client": "ui"}).status_code == 200
        made = client.post("/v1/projects", json={"name": "Logged", "domain": "process"})
        pid = made.json()["id"]
        assert client.get(f"/v1/projects/{pid}/model").status_code == 200
        assert client.get("/v1/nowhere").status_code == 404
        assert (
            client.get("/v1/system", headers={"Authorization": "Bearer wrong"}).status_code == 401
        )
        assert client.delete("/v1/system").status_code == 405
        with client.websocket_connect(f"{WS_URL}/v1/projects/{pid}/events") as socket:
            socket.send_text(json.dumps({"token": TOKEN}))
            assert socket.receive_json()["type"] == "model"
    entries = read_log(log)
    assert [(entry["method"], entry["path"], entry["status"]) for entry in entries] == [
        ("GET", "/v1/system", 200),
        ("POST", "/v1/projects", 200),
        ("GET", f"/v1/projects/{pid}/model", 200),
        ("GET", "/v1/nowhere", 404),
        ("GET", "/v1/system", 401),
        ("DELETE", "/v1/system", 405),
        ("GET", f"/v1/projects/{pid}/events", 101),
    ]
    assert [entry["route"] for entry in entries] == [
        ["GET", "/v1/system"],
        ["POST", "/v1/projects"],
        ["GET", "/v1/projects/{pid}/model"],
        None,
        None,
        None,
        ["GET", "/v1/projects/{pid}/events"],
    ]
    assert entries[0]["client"] == "ui"
    assert entries[1]["client"] is None
    assert entries[-1]["type"] == "websocket"


def test_the_check_passes_documented_routes_and_names_everything_else(
    app: FastAPI, tmp_path: Path
) -> None:
    log = tmp_path / "requests.jsonl"
    with logged(app, log) as client:
        client.get("/v1/system")
        client.get("/v1/settings")
        client.get("/v1/engines")
    found = check(read_log(log), spec_table())
    assert found["problems"] == []
    assert found["requests"] == 3
    assert found["routes"] == {
        "GET /v1/engines": 1,
        "GET /v1/settings": 1,
        "GET /v1/system": 1,
    }

    with logged(app, log) as client:
        client.get("/favicon.ico")
        client.get("/v1/system", headers={"Authorization": "Bearer wrong"})
    found = check(read_log(log), spec_table())
    assert found["problems"] == [
        "GET /favicon.ico -> 404: not a route of spec 3's endpoint table",
        "GET /favicon.ico -> 404: refused or unanswered",
        "GET /v1/system -> 401: not a route of spec 3's endpoint table",
        "GET /v1/system -> 401: refused or unanswered",
    ]
    assert check([], spec_table())["problems"] == ["the log is empty"]
    # A matched route that is not a row, and a refused answer on a row, are both named.
    other = {"type": "http", "method": "GET", "path": "/v1/x", "status": 200, "client": None}
    assert check([{**other, "route": ["GET", "/v1/test/x"]}], spec_table())["problems"] == [
        "GET /v1/x -> 200: not a route of spec 3's endpoint table"
    ]
    refused = {**other, "path": "/v1/system", "status": 409, "route": ["GET", "/v1/system"]}
    assert check([refused], spec_table())["problems"] == [
        "GET /v1/system -> 409: refused or unanswered"
    ]


def test_the_command_line_check_exits_by_what_it_found(tmp_path: Path) -> None:
    good = tmp_path / "good.jsonl"
    entry = {
        "type": "http",
        "method": "GET",
        "path": "/v1/system",
        "status": 200,
        "route": ["GET", "/v1/system"],
        "client": "ui",
    }
    good.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({**entry, "route": None, "status": 404}) + "\n", encoding="utf-8")
    script = str(ROOT / "tests" / "service" / "request_log.py")
    passed = subprocess.run(
        [sys.executable, script, str(good)], capture_output=True, text=True, check=False
    )
    assert passed.returncode == 0, passed.stderr
    assert json.loads(passed.stdout)["routes"] == {"GET /v1/system": 1}
    failed = subprocess.run(
        [sys.executable, script, str(bad)], capture_output=True, text=True, check=False
    )
    assert failed.returncode == 1
    assert len(json.loads(failed.stdout)["problems"]) == 2


def test_the_logged_service_logs_what_reaches_it_and_stops_cleanly(tmp_path: Path) -> None:
    log = tmp_path / "requests.jsonl"
    config_dir = tmp_path / "config"
    process = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "tests" / "service" / "logged_service.py"),
            "--config-dir",
            str(config_dir),
            "--data-dir",
            str(tmp_path / "data"),
        ],
        env={**os.environ, LOG_FILE_VARIABLE: str(log)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 60
        info = None
        while info is None or not probe(info):
            assert process.poll() is None, process.communicate()
            assert time.monotonic() < deadline, "the logged service did not answer within 60 s"
            info = read_service_file(config_dir)
            time.sleep(0.05)
        request = urllib.request.Request(
            f"http://127.0.0.1:{info.port}/v1/system",
            headers={"Authorization": f"Bearer {info.token}", "X-Client": "ui"},
        )
        direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with direct.open(request, timeout=30) as answer:
            assert answer.status == 200
    finally:
        process.terminate()
        process.communicate(timeout=60)
    assert not (config_dir / "service.json").exists()
    system = [entry for entry in read_log(log) if entry["client"] == "ui"]
    assert system == [
        {
            "type": "http",
            "method": "GET",
            "path": "/v1/system",
            "status": 200,
            "route": ["GET", "/v1/system"],
            "client": "ui",
        }
    ]
