"""Spec 3 acceptance, M6: "A run survives a client disconnect" (AKS-112).

A real service process (``gated_service.py``: ``python -m lcsim.service`` with the test
adapter ``gated`` installed) runs the coffee shop. The test starts the run over HTTP and
watches it over the events WebSocket; the run waits for a ``GO`` file in its workdir, so it
is certainly unfinished when the test drops both clients. The test then lets it end and,
with new connections, finds it ``done`` with a full run folder. Every wait is on a condition
with a generous timeout.
"""

import json
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx2
import pytest
from websockets.sync.client import connect

from lcsim.runs.manifest import read_manifest
from lcsim.service.discovery import ServiceInfo, read_service_file
from service.run_adapters import GO_FILE, WAITING

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = Path(__file__).resolve().parent / "gated_service.py"
TIMEOUT_S = 120.0


def wait_until(condition: Callable[[], object], timeout_s: float = TIMEOUT_S) -> None:
    deadline = time.monotonic() + timeout_s
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.05)


@pytest.fixture
def service(tmp_path: Path) -> Iterator[ServiceInfo]:
    config_dir = tmp_path / "config"
    process = subprocess.Popen(
        [
            sys.executable,
            str(LAUNCHER),
            "--config-dir",
            str(config_dir),
            "--data-dir",
            str(tmp_path / "data"),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_until(lambda: read_service_file(config_dir) is not None or process.poll() is not None)
        info = read_service_file(config_dir)
        assert info is not None, process.communicate()
        yield info
    finally:
        process.terminate()
        try:
            process.communicate(timeout=60)
        except subprocess.TimeoutExpired:  # pragma: no cover - only when the test fails
            process.kill()
            process.communicate()


def http(info: ServiceInfo) -> httpx2.Client:
    return httpx2.Client(
        base_url=f"http://127.0.0.1:{info.port}",
        headers={"Authorization": f"Bearer {info.token}", "X-Client": "mcp"},
        trust_env=False,
        timeout=30,
    )


def test_a_run_survives_a_client_disconnect(service: ServiceInfo) -> None:
    model: dict[str, Any] = json.loads((ROOT / "examples" / "coffee_shop.json").read_text())
    model["experiments"][0].update(length="2 h", warmup="0 s", replications=2)
    model["run"]["engine"] = "gated"
    first = http(service)
    pid = first.post("/v1/projects", json={"name": "Coffee shop"}).json()["id"]
    assert first.put(f"/v1/projects/{pid}/model", content=json.dumps(model)).status_code == 200
    response = first.post(f"/v1/projects/{pid}/runs", json={"experiment_id": "base"})
    assert response.status_code == 202, response.text
    rid = response.json()["run_id"]
    with connect(f"ws://127.0.0.1:{service.port}/v1/runs/{rid}/events") as socket:
        socket.send(json.dumps({"token": service.token}))
        assert json.loads(socket.recv(timeout=30))["type"] == "state"
        assert json.loads(socket.recv(timeout=30))["type"] == "progress"
        wait_until(lambda: first.get(f"/v1/runs/{rid}").json()["message"] == WAITING)
    # Both clients have left; the run is still running, waiting for GO.
    first.close()
    second = http(service)
    project = Path(second.get("/v1/projects").json()[0]["path"])
    folder = project / "runs" / rid
    assert read_manifest(folder)["state"] == "running"
    (folder / "engine" / GO_FILE).write_text("")

    def state() -> str:
        found: str = second.get(f"/v1/runs/{rid}").json()["state"]
        return found

    wait_until(lambda: state() in ("done", "failed", "cancelled"))
    assert state() == "done"
    for name in ("model.json", "manifest.json", "summary.json", "log.txt", "engine"):
        assert (folder / name).exists(), name
    for name in ("replications", "timeseries"):
        assert (folder / "tables" / f"{name}.parquet").is_file()
    manifest = read_manifest(folder)
    assert manifest["client"] == "mcp"
    assert manifest["project_id"] == pid
    assert second.get(f"/v1/runs/{rid}/summary").json()["findings"] == []
    second.close()
