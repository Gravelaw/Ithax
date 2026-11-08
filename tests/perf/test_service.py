"""Spec 3 "Performance targets" (proposed, measured on the low tier; M6 measured, the owner
confirms; AKS-114), and two costs the M6 close asks for.

Run with ``taskset -c 0-3 pytest -m perf`` (guide "Performance measurement protocol").

- **Service ready within 5 seconds of start.** A real ``python -m lcsim.service`` process
  is started three times on the same folders (the first start detects the hardware and
  stores the tier; later starts read it). "Ready" is the first ``200`` from
  ``GET /v1/system``, timed from just before the process is started.
- **Validation of a 200-component model within 200 milliseconds.** A source, 198 servers in
  a line and a sink, written with ``PUT .../model``; ``POST .../validate`` is timed over
  loopback HTTP, from request to response, 20 times after one untimed call. The whole
  request is timed (schema pass, meaning pass, the adapter's ``validate``, the HTTP round
  trip), since that is what the canvas waits for.
- **Under 300 MB of memory when idle.** The resident memory of the service and every
  process it started (``/proc``) after 5 s with no request, once just after it is ready and
  once after the coffee shop's own 30-replication experiment has run through it (the run's
  worker has ended by then, so only the service is left).
- **A search's cost** (M5 "Left", "Search cost"): the machine-count search
  (``benchmarks/machine_count/model.json``) through the local target, as shipped (budget 10,
  five candidates, the exhaustive path) and at the default budget of 50 (``budget`` removed)
  with ``tills`` from 1 to 50, so that 50 candidates are searched.
- **The distribution fit's cost** (AKS-113): ``fit_column`` on deterministic triangular
  columns (``scipy.stats.triang.ppf`` at evenly spaced quantiles, no random numbers) of
  1,000 to 1,048,576 values (the import's record limit), with each family timed alone.

Each check records its measurements with ``perf_record`` and asserts its target where spec 3
names one.
"""

import copy
import itertools
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx2
import numpy
import pytest
import scipy.stats

from lcsim.model import fit
from lcsim.runs.limits import process_tree_memory, system_memory
from lcsim.runs.targets import LocalTarget
from lcsim.service.discovery import read_service_file
from perf.test_three_machine_line import TreeMemorySampler, max_rss_bytes, mib, usable_cores

pytestmark = pytest.mark.perf

ROOT = Path(__file__).resolve().parents[2]
COFFEE_SHOP = ROOT / "examples" / "coffee_shop.json"
MACHINE_COUNT = ROOT / "benchmarks" / "machine_count" / "model.json"

READY_TARGET_S = 5.0
VALIDATE_TARGET_S = 0.2
IDLE_TARGET_BYTES = 300 * 10**6
IDLE_WAIT_S = 5.0
RECORD_LIMIT = 1_048_576


def machine() -> dict[str, Any]:
    memory = system_memory()
    return {
        "cpu_count": os.cpu_count(),
        "affinity_cores": usable_cores(),
        "memory_gib": None if memory is None else round(memory / 2**30, 2),
        "python": platform.python_version(),
        "platform": platform.platform(),
    }


class Service:
    """A ``python -m lcsim.service`` process on ``folder``, and an HTTP client for it."""

    def __init__(self, folder: Path) -> None:
        self.config_dir = folder / "config"
        self.started = time.perf_counter()
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "lcsim.service",
                "--config-dir",
                str(self.config_dir),
                "--data-dir",
                str(folder / "data"),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.ready_s = self._wait_until_ready()

    def _wait_until_ready(self) -> float:
        deadline = self.started + 60
        while time.perf_counter() < deadline:
            assert self.process.poll() is None, self.process.communicate()
            info = read_service_file(self.config_dir)
            if info is not None:
                self.client = httpx2.Client(
                    base_url=f"http://127.0.0.1:{info.port}",
                    headers={"Authorization": f"Bearer {info.token}"},
                    trust_env=False,
                    timeout=600,
                )
                try:
                    if self.client.get("/v1/system").status_code == 200:
                        return time.perf_counter() - self.started
                except httpx2.TransportError:
                    pass
            time.sleep(0.005)
        raise AssertionError("the service did not answer within 60 s")

    def idle_memory(self) -> int | None:
        time.sleep(IDLE_WAIT_S)
        return process_tree_memory(self.process.pid)

    def stop(self) -> None:
        self.client.close()
        self.process.terminate()
        self.process.communicate(timeout=60)


@pytest.fixture
def service(tmp_path: Path) -> Iterator[Service]:
    running = Service(tmp_path)
    try:
        yield running
    finally:
        running.stop()


def test_the_service_is_ready_within_5_seconds_and_idles_under_300_mb(
    tmp_path: Path, perf_record: Callable[[dict[str, Any]], None]
) -> None:
    ready: list[float] = []
    idle: list[int | None] = []
    for _ in range(3):
        started = Service(tmp_path)
        try:
            ready.append(started.ready_s)
            idle.append(started.idle_memory())
        finally:
            started.stop()
    record = {
        "check": "service ready (first 200 from GET /v1/system), three starts",
        "ready_s": [round(value, 3) for value in ready],
        "ready_target_s": READY_TARGET_S,
        "idle_tree_mib": [mib(value) for value in idle],
        "idle_target_mib": mib(IDLE_TARGET_BYTES),
        "peak_rss_children_mib": mib(max_rss_bytes("children")),
        **machine(),
    }
    perf_record(record)
    assert max(ready) < READY_TARGET_S, record
    assert all(value is not None and value < IDLE_TARGET_BYTES for value in idle), record


def line_model(components: int) -> dict[str, Any]:
    """A source, ``components - 2`` servers in a line and a sink."""
    servers = [f"s{number}" for number in range(1, components - 1)]
    names = ["arrivals", *servers, "exit"]
    service = {"dist": "exponential", "mean": "1 min"}
    return {
        "format_version": "0.1",
        "meta": {"name": f"{components} components"},
        "domain": "process",
        "parameters": {},
        "components": [
            {
                "id": "arrivals",
                "type": "source",
                "params": {"interarrival": {"dist": "exponential", "mean": "2 min"}},
            },
            *(
                {"id": name, "type": "server", "params": {"capacity": 1, "service": dict(service)}}
                for name in servers
            ),
            {"id": "exit", "type": "sink", "params": {}},
        ],
        "connections": [
            {"from": f"{left}.out", "to": f"{right}.in"}
            for left, right in itertools.pairwise(names)
        ],
        "experiments": [{"id": "base", "length": "8 h", "warmup": "0 s", "replications": 30}],
        "run": {"target": "local", "fidelity": "standard"},
    }


def test_validation_of_a_200_component_model_is_within_200_ms(
    service: Service, perf_record: Callable[[dict[str, Any]], None]
) -> None:
    model = line_model(200)
    assert len(model["components"]) == 200
    client = service.client
    pid = client.post("/v1/projects", json={"name": "Line"}).json()["id"]
    written = client.put(f"/v1/projects/{pid}/model", content=json.dumps(model))
    assert written.status_code == 200, written.text
    first = client.post(f"/v1/projects/{pid}/validate")
    assert first.status_code == 200
    assert [issue for issue in first.json()["issues"] if issue["severity"] == "error"] == []
    times: list[float] = []
    for _ in range(20):
        started = time.perf_counter()
        response = client.post(f"/v1/projects/{pid}/validate")
        times.append(time.perf_counter() - started)
        assert response.status_code == 200
    record = {
        "check": "POST .../validate of a 200-component model over loopback HTTP, 20 calls",
        "median_s": round(statistics.median(times), 4),
        "max_s": round(max(times), 4),
        "min_s": round(min(times), 4),
        "target_s": VALIDATE_TARGET_S,
        "issues": len(first.json()["issues"]),
        "model_bytes": len(json.dumps(model)),
        **machine(),
    }
    perf_record(record)
    assert max(times) < VALIDATE_TARGET_S, record


def test_the_service_idles_under_300_mb_after_a_run(
    service: Service, perf_record: Callable[[dict[str, Any]], None]
) -> None:
    client = service.client
    after_start = service.idle_memory()
    pid = client.post("/v1/projects", json={"name": "Coffee shop"}).json()["id"]
    written = client.put(f"/v1/projects/{pid}/model", content=COFFEE_SHOP.read_text())
    assert written.status_code == 200, written.text
    with TreeMemorySampler() as sampler:
        started = time.perf_counter()
        rid = client.post(f"/v1/projects/{pid}/runs", json={"experiment_id": "base"}).json()[
            "run_id"
        ]
        while client.get(f"/v1/runs/{rid}").json()["state"] not in ("done", "failed"):
            time.sleep(0.05)
        run_s = time.perf_counter() - started
    assert client.get(f"/v1/runs/{rid}").json()["state"] == "done"
    after_run = service.idle_memory()
    workers = client.get("/v1/system").json()["workers"]
    record = {
        "check": "service idle memory (service and its processes), coffee shop run between",
        "idle_after_start_mib": mib(after_start),
        "idle_after_run_mib": mib(after_run),
        "target_mib": mib(IDLE_TARGET_BYTES),
        "coffee_shop_run_s": round(run_s, 2),
        "run_tree_peak_mib": mib(sampler.peak),
        "workers": workers,
        **machine(),
    }
    perf_record(record)
    assert after_start is not None and after_start < IDLE_TARGET_BYTES, record
    assert after_run is not None and after_run < IDLE_TARGET_BYTES, record


def search_summary(folder: Path, model: dict[str, Any]) -> tuple[float, dict[str, Any], Any]:
    workers = usable_cores()
    with TreeMemorySampler() as sampler:
        started = time.perf_counter()
        run = LocalTarget(folder, workers=workers).create(json.dumps(model).encode(), "base")
        state = run.execute()
        wall_s = time.perf_counter() - started
    assert state == "done"
    summary = json.loads((run.folder / "summary.json").read_text(encoding="utf-8"))
    return wall_s, summary["search"], sampler.peak


@pytest.mark.parametrize(("budget", "tills_max"), [(10, 5), (None, 50)])
def test_the_cost_of_a_machine_count_search(
    tmp_path: Path,
    perf_record: Callable[[dict[str, Any]], None],
    budget: int | None,
    tills_max: int,
) -> None:
    model: dict[str, Any] = json.loads(MACHINE_COUNT.read_text(encoding="utf-8"))
    model = copy.deepcopy(model)
    model["parameters"]["tills"]["max"] = tills_max
    search = model["experiments"][0]["search"]
    if budget is None:
        del search["budget"]
    wall_s, found, peak = search_summary(tmp_path / "runs", model)
    candidates = found["candidates"]
    confirmed = sum(1 for candidate in candidates if candidate["confirmed"])
    search_replications = int(search.get("replications", 10))
    confirm_replications = int(model["experiments"][0]["replications"])
    replications = len(candidates) * search_replications + confirmed * confirm_replications
    record = {
        "check": "machine-count search through the local target",
        "budget": search.get("budget", 50),
        "tills": [1, tills_max],
        "candidates": len(candidates),
        "confirmed": confirmed,
        "replications": replications,
        "best_tills": found["best"]["set"]["tills"],
        "wall_s": round(wall_s, 2),
        "s_per_replication": round(wall_s / replications, 4),
        "workers": usable_cores(),
        "peak_rss_tree_mib": mib(peak),
        **machine(),
    }
    perf_record(record)
    assert found["best"]["set"]["tills"] == 2, record


def triangular_column(size: int) -> numpy.ndarray[Any, numpy.dtype[numpy.float64]]:
    quantiles = (numpy.arange(size, dtype=numpy.float64) + 0.5) / size
    values: numpy.ndarray[Any, numpy.dtype[numpy.float64]] = scipy.stats.triang.ppf(
        quantiles, 0.3, loc=1.0, scale=4.0
    )
    return values


@pytest.mark.parametrize("size", [1_000, 10_000, 100_000, RECORD_LIMIT])
def test_the_cost_of_the_distribution_fit(
    size: int, perf_record: Callable[[dict[str, Any]], None]
) -> None:
    column = triangular_column(size)
    started = time.perf_counter()
    candidates = fit.fit_column(column, "min")
    whole_s = time.perf_counter() - started
    factor = float(numpy.max(numpy.abs(column)))
    families: dict[str, float] = {}
    for name, family in fit._FAMILIES.items():
        started = time.perf_counter()
        fit._candidate(name, family, column / factor, factor, "min")
        families[name] = round(time.perf_counter() - started, 3)
    record = {
        "check": "fit_column on a triangular column",
        "values": size,
        "whole_fit_s": round(whole_s, 3),
        "family_s": families,
        "slowest": max(families, key=lambda name: families[name]),
        "best": candidates[0].distribution["dist"],
        "peak_rss_self_mib": mib(max_rss_bytes("self")),
        **machine(),
    }
    perf_record(record)
    assert candidates[0].distribution["dist"] == "triangular", record
