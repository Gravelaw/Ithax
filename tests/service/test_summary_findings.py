"""Findings in the run summary, end to end through the service (spec 3 ``GET
/v1/runs/{rid}/summary``; spec 4 "Finding rules"; AKS-135).

The M8 gate: the M1 three-machine line fires ``bottleneck`` and ``not_enough_runs`` and the
coffee shop fires neither, each run unchanged (its own experiment, seed 12345) through the
service with the product's process adapter. The thresholds come from ``finding_thresholds``
in ``settings.json``, read at each summary, so changing one changes which findings fire on
the same run; a value that cannot be used is W220 in ``issues`` and its default is used.
The rules read the run folder's copy of the model, never the project's current model.

Each example runs once (about 4 s on 4 cores); every threshold case reads that run again.
"""

import json
import time
from pathlib import Path
from typing import Any

from starlette.testclient import TestClient

from lcsim.findings import find
from lcsim.model.loading import load_document
from lcsim.service.config import ServiceConfig
from lcsim.service.hardware import SETTINGS_FILE
from lcsim.strict_json import read_json_file

Json = dict[str, Any]

ROOT = Path(__file__).resolve().parents[2]
TIMEOUT_S = 300.0

WELD_BOTTLENECK = "weld is the bottleneck: busy 90% of the time, with an average wait of 15.7 min."
WELD_NOT_ENOUGH_RUNS = (
    "The estimates for weld.wait.mean are still uncertain: weld.wait.mean is 15.7 min plus or "
    "minus 2.09 min. About 60 replications would be needed for a 10% interval."
)


def example(name: str) -> Json:
    document = read_json_file(ROOT / "examples" / f"{name}.json")
    assert isinstance(document, dict)
    return document


def run_example(client: TestClient, name: str) -> tuple[str, str]:
    """Runs ``examples/<name>.json`` unchanged in a new project; its project and run ids."""
    created = client.post("/v1/projects", json={"name": name})
    assert created.status_code == 200, created.text
    pid: str = created.json()["id"]
    put = client.put(f"/v1/projects/{pid}/model", content=json.dumps(example(name)))
    assert put.status_code == 200 and put.json()["issues"] == [], put.text
    started = client.post(f"/v1/projects/{pid}/runs", json={"experiment_id": "base"})
    assert started.status_code == 202, started.text
    rid: str = started.json()["run_id"]
    deadline = time.monotonic() + TIMEOUT_S
    while (state := client.get(f"/v1/runs/{rid}").json()["state"]) not in (
        "done",
        "failed",
        "cancelled",
    ):
        assert time.monotonic() < deadline, f"the run {rid} did not finish"
        time.sleep(0.05)
    assert state == "done"
    return pid, rid


def summary(client: TestClient, rid: str) -> Json:
    response = client.get(f"/v1/runs/{rid}/summary")
    assert response.status_code == 200, response.text
    body: Json = response.json()
    assert set(body) == {"summary", "findings", "issues"}
    return body


def rules(body: Json) -> list[tuple[str, str | None]]:
    return [(item["rule"], item["component"]) for item in body["findings"]]


def set_thresholds(config: ServiceConfig, thresholds: object | None) -> None:
    """Writes ``finding_thresholds`` into ``settings.json``, keeping its other keys (the
    tier the service stored at its first start); ``None`` removes it."""
    path = config.config_dir / SETTINGS_FILE
    settings = json.loads(path.read_text(encoding="utf-8"))
    assert "tier" in settings
    settings.pop("finding_thresholds", None)
    if thresholds is not None:
        settings["finding_thresholds"] = thresholds
    path.write_text(json.dumps(settings), encoding="utf-8")


def run_files(client: TestClient, pid: str, rid: str) -> tuple[Json, Json]:
    project = client.get("/v1/projects").json()
    [folder] = [Path(item["path"]) for item in project if item["id"] == pid]
    run = folder / "runs" / rid
    summary_file = read_json_file(run / "summary.json")
    model_file = read_json_file(run / "model.json")
    assert isinstance(summary_file, dict) and isinstance(model_file, dict)
    return summary_file, model_file


def test_the_three_machine_line_fires_bottleneck_and_not_enough_runs(
    client: TestClient, config: ServiceConfig
) -> None:
    pid, rid = run_example(client, "three_machine_line")
    body = summary(client, rid)
    assert body["issues"] == []
    assert rules(body) == [("bottleneck", "weld"), ("not_enough_runs", None)]
    bottleneck, not_enough = body["findings"]
    metrics = body["summary"]["scenarios"]["default"]["metrics"]
    weld_utilization = metrics["weld.utilization"]["mean"]
    wait = metrics["weld.wait.mean"]
    # The measured values of the DECISIONS M8 entry (seed 12345, 30 replications of 100 h
    # with 20 h of warm-up), the same as AKS-117's fixture.
    assert round(weld_utilization, 3) == 0.901
    assert round(wait["mean"], 1) == 941.5 and round(wait["half_width"], 1) == 125.5
    assert round(wait["half_width"] / wait["mean"], 3) == 0.133
    assert bottleneck == {
        "rule": "bottleneck",
        "severity": "info",
        "component": "weld",
        "scenario": "default",
        "text": WELD_BOTTLENECK,
        "evidence": {"weld.utilization": weld_utilization, "weld.wait.mean": wait["mean"]},
    }
    assert not_enough == {
        "rule": "not_enough_runs",
        "severity": "warning",
        "component": None,
        "scenario": "default",
        "text": WELD_NOT_ENOUGH_RUNS,
        "evidence": {"weld.wait.mean": wait, "n_required": 60},
    }
    # Fixed rules: the same run gives the same findings, and they are find() of the run
    # folder's summary.json and model.json.
    assert summary(client, rid) == body
    summary_file, model_file = run_files(client, pid, rid)
    loaded = load_document(model_file)
    assert loaded.model is not None
    assert [item.as_dict() for item in find(summary_file, loaded.model)] == body["findings"]

    # Changing a threshold changes which findings fire, on the same run.
    set_thresholds(config, {"bottleneck_utilization": 0.95})
    assert rules(summary(client, rid)) == [("not_enough_runs", None)]
    set_thresholds(config, {"relative_half_width": 0.15})
    assert rules(summary(client, rid)) == [("bottleneck", "weld")]
    set_thresholds(config, {"bottleneck_utilization": 0.95, "relative_half_width": 0.15})
    assert summary(client, rid)["findings"] == []
    set_thresholds(config, {"idle_utilization": 0.5})
    assert rules(summary(client, rid)) == [
        ("bottleneck", "weld"),
        ("idle_capacity", "paint"),
        ("not_enough_runs", None),
    ]
    set_thresholds(config, {"relative_half_width": 0.05})
    narrower = summary(client, rid)["findings"][1]
    assert narrower["text"].endswith("would be needed for a 5% interval.")
    # Removing the thresholds gives the defaults again.
    set_thresholds(config, None)
    assert summary(client, rid) == body


def test_the_coffee_shop_fires_neither_and_its_findings_read_the_run_s_model(
    client: TestClient, config: ServiceConfig
) -> None:
    pid, rid = run_example(client, "coffee_shop")
    body = summary(client, rid)
    assert body["findings"] == [] and body["issues"] == []
    metrics = body["summary"]["scenarios"]["default"]["metrics"]
    wait = metrics["till.wait.mean"]
    # The measured values of the DECISIONS M8 entry (seed 12345, 30 replications of 200 h
    # with 10 h of warm-up), the same as AKS-117's fixture.
    assert round(metrics["till.utilization"]["mean"], 3) == 0.749
    assert round(wait["mean"], 1) == 267.6 and round(wait["half_width"], 2) == 9.79
    assert round(wait["half_width"] / wait["mean"], 3) == 0.037

    # Lower thresholds make each rule fire on the same run.
    set_thresholds(config, {"bottleneck_utilization": 0.7})
    fired = summary(client, rid)
    assert rules(fired) == [("bottleneck", "till")]
    assert fired["findings"][0]["text"] == (
        "till is the bottleneck: busy 75% of the time, with an average wait of 4.46 min."
    )
    set_thresholds(config, {"relative_half_width": 0.03})
    assert rules(summary(client, rid)) == [("not_enough_runs", None)]

    # The rules read the run folder's model: replacing the project's model with another
    # (no till at all) changes nothing for the run already made.
    set_thresholds(config, {"bottleneck_utilization": 0.7})
    put = client.put(f"/v1/projects/{pid}/model", content=json.dumps(example("three_machine_line")))
    assert put.status_code == 200, put.text
    assert summary(client, rid) == fired

    # A threshold that cannot be used is W220 in issues, and its default is used.
    set_thresholds(config, {"bottleneck_utilization": 7, "relative_half_width": 0.03})
    refused = summary(client, rid)
    assert [(item["code"], item["path"]) for item in refused["issues"]] == [
        ("W220", "/finding_thresholds/bottleneck_utilization")
    ]
    assert refused["issues"][0]["severity"] == "warning"
    assert rules(refused) == [("not_enough_runs", None)]
