"""Spec 3 acceptance, M6: "The app works with outbound network blocked" (AKS-114; spec 0
principle 6, "Works offline").

A real service process (``offline_service.py``: ``python -m lcsim.service`` with the network
guard of ``offline_guard.py``) serves on ``127.0.0.1``. The guard refuses, in the service
and in every process the service spawns for a run, any connection, datagram or name lookup
that is not loopback, and writes each attempt to a file. Over loopback HTTP the test then
goes through the cycle a user makes: create a project, write the coffee shop and edit its
experiment, validate, run it with two replications, and read the run's summary and both
tables. It asserts the cycle completes, that the guard was on in the service and in at
least one run worker (each process writes an ``armed-<pid>`` file), and that no process
attempted a network operation.

The guard is an audit hook (PEP 578), installed by the launcher at import, which the
spawned workers import again as their main module; an audit hook catches every
``socket.connect`` and lookup whatever library makes it, which a monkeypatched
``socket.socket`` would not in a child process. The two tests below it show the guard does
refuse what it should, in a fresh process, since an audit hook cannot be removed from the
process that installs it.
"""

import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx2
import pytest

from lcsim.service.discovery import ServiceInfo, read_service_file
from service.offline_guard import FOLDER_VARIABLE

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"
LAUNCHER = Path(__file__).resolve().parent / "offline_service.py"
TIMEOUT_S = 120.0


def wait_until(condition: Callable[[], object], timeout_s: float = TIMEOUT_S) -> None:
    deadline = time.monotonic() + timeout_s
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.05)


@pytest.fixture
def guard_folder(tmp_path: Path) -> Path:
    return tmp_path / "guard"


@pytest.fixture
def offline_service(tmp_path: Path, guard_folder: Path) -> Iterator[ServiceInfo]:
    config_dir = tmp_path / "config"
    environment = {**os.environ, FOLDER_VARIABLE: str(guard_folder)}
    process = subprocess.Popen(
        [
            sys.executable,
            str(LAUNCHER),
            "--config-dir",
            str(config_dir),
            "--data-dir",
            str(tmp_path / "data"),
        ],
        env=environment,
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
        headers={"Authorization": f"Bearer {info.token}", "X-Client": "script"},
        trust_env=False,
        timeout=30,
    )


def test_the_app_works_with_outbound_network_blocked(
    offline_service: ServiceInfo, guard_folder: Path
) -> None:
    client = http(offline_service)
    created = client.post("/v1/projects", json={"name": "Coffee shop"})
    assert created.status_code == 200, created.text
    pid = created.json()["id"]
    model: dict[str, Any] = json.loads((ROOT / "examples" / "coffee_shop.json").read_text())
    written = client.put(f"/v1/projects/{pid}/model", content=json.dumps(model))
    assert written.status_code == 200, written.text
    edit = {
        "edit": "set_experiment",
        "id": "base",
        "length": "2 h",
        "warmup": "0 s",
        "replications": 2,
    }
    edited = client.post(f"/v1/projects/{pid}/model/edits", json={"edits": [edit]})
    assert edited.status_code == 200, edited.text
    assert edited.json()["model"]["experiments"][0]["replications"] == 2
    validated = client.post(f"/v1/projects/{pid}/validate")
    assert validated.status_code == 200, validated.text
    assert [i for i in validated.json()["issues"] if i["severity"] == "error"] == []
    started = client.post(f"/v1/projects/{pid}/runs", json={"experiment_id": "base"})
    assert started.status_code == 202, started.text
    rid = started.json()["run_id"]

    def state() -> str:
        found: str = client.get(f"/v1/runs/{rid}").json()["state"]
        return found

    wait_until(lambda: state() in ("done", "failed", "cancelled"))
    assert state() == "done", client.get(f"/v1/runs/{rid}").json()
    summary = client.get(f"/v1/runs/{rid}/summary")
    assert summary.status_code == 200, summary.text
    metrics = summary.json()["summary"]["scenarios"]["default"]["metrics"]
    assert metrics["till.wait.mean"]["n"] == 2
    rows = client.get(f"/v1/runs/{rid}/tables/replications")
    assert rows.status_code == 200 and len(rows.json()) > 0
    csv = client.get(f"/v1/runs/{rid}/tables/timeseries", params={"format": "csv"})
    assert csv.status_code == 200 and csv.text.count("\n") > 1
    client.close()

    armed = {int(path.name.removeprefix("armed-")) for path in guard_folder.glob("armed-*")}
    assert offline_service.pid in armed, "the guard was not on in the service"
    assert len(armed - {offline_service.pid}) >= 1, "the guard was not on in any run worker"
    attempts = {path.name: path.read_text() for path in guard_folder.glob("violations-*")}
    assert attempts == {}, attempts


GUARD_CHECK = """
import socket, sys
from pathlib import Path
from service.offline_guard import BlockedNetwork, install
folder = Path(sys.argv[1])
install(folder)
results = []
for name, attempt in [
    ("connect", lambda: socket.socket().connect(("192.0.2.1", 80))),
    ("lookup", lambda: socket.getaddrinfo("example.com", 443)),
    ("datagram", lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(
        b"x", ("192.0.2.1", 53))),
]:
    try:
        attempt()
        results.append(name + " allowed")
    except BlockedNetwork:
        results.append(name + " blocked")
local = socket.socket()
local.bind(("127.0.0.1", 0))
local.listen()
socket.create_connection(local.getsockname(), timeout=1).close()
socket.getaddrinfo("localhost", 80)
results.append("loopback allowed")
print(",".join(results))
"""


def test_the_guard_refuses_what_is_not_loopback_and_records_it(tmp_path: Path) -> None:
    finished = subprocess.run(
        [sys.executable, "-c", GUARD_CHECK, str(tmp_path)],
        cwd=TESTS,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert finished.returncode == 0, finished.stderr
    assert finished.stdout.strip().split(",") == [
        "connect blocked",
        "lookup blocked",
        "datagram blocked",
        "loopback allowed",
    ]
    (record,) = tmp_path.glob("violations-*.txt")
    logged = record.read_text().splitlines()
    assert [line.split(" ", 1)[0] for line in logged] == [
        "socket.connect",
        "socket.getaddrinfo",
        "socket.sendto",
    ]
    assert len(list(tmp_path.glob("armed-*"))) == 1


def test_the_launcher_installs_the_guard_only_when_its_variable_is_set(tmp_path: Path) -> None:
    check = (
        "import runpy, sys; sys.argv = ['x']; "
        f"runpy.run_path({str(LAUNCHER)!r}, run_name='__mp_main__')"
    )
    armed = {**os.environ, FOLDER_VARIABLE: str(tmp_path / "on")}
    unarmed = {name: value for name, value in os.environ.items() if name != FOLDER_VARIABLE}
    for env in (armed, unarmed):
        finished = subprocess.run(
            [sys.executable, "-c", check],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert finished.returncode == 0, finished.stderr
    # Imported as a worker's main module (`__mp_main__`), the launcher armed the guard and
    # did not start a service; without the variable it armed nothing.
    assert len(list((tmp_path / "on").glob("armed-*"))) == 1
    assert sorted(path.name for path in tmp_path.iterdir()) == ["on"]
