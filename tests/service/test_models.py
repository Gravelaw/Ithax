"""``GET`` and ``PUT /v1/projects/{pid}/model``, ``POST .../model/edits`` and
``POST .../validate`` (spec 3 "Endpoints", "Revision", "Model edits"; AKS-111).

Every edit kind has a request test that applies it and one for each case in which it
cannot be applied (E180); the pure functions behind them are tested in
``tests/model/test_edits.py``.
"""

import dataclasses
import json
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from ithax.engines.process.adapter import ProcessAdapter
from ithax.model.edits import EDIT_KINDS
from ithax.model.issues import Issue
from ithax.model.model import Model
from ithax.service import projects_store
from ithax.service.app import create_app
from ithax.service.config import ServiceConfig
from ithax.service.projects_store import MODEL_FILE, PROJECT_FILE
from service.service_support import AUTH, BASE_URL, assert_error

FIXTURES = Path(__file__).resolve().parents[1] / "model" / "fixtures" / "edits"

Json = dict[str, Any]


def shop() -> Json:
    loaded: Json = json.loads((FIXTURES / "shop.json").read_text(encoding="utf-8"))
    return loaded


def plan() -> Json:
    loaded: Json = json.loads((FIXTURES / "plan.json").read_text(encoding="utf-8"))
    return loaded


def new_project(client: TestClient, domain: str = "process") -> str:
    response = client.post("/v1/projects", json={"name": "Shop", "domain": domain})
    assert response.status_code == 200
    pid = response.json()["id"]
    assert isinstance(pid, str)
    return pid


def folder(client: TestClient, pid: str) -> Path:
    [project] = [item for item in client.get("/v1/projects").json() if item["id"] == pid]
    return Path(project["path"])


def on_disk(client: TestClient, pid: str) -> tuple[Json, int]:
    """The model and revision as the project folder holds them."""
    where = folder(client, pid)
    model: Json = json.loads((where / MODEL_FILE).read_text(encoding="utf-8"))
    revision = json.loads((where / PROJECT_FILE).read_text(encoding="utf-8"))["model_revision"]
    assert isinstance(revision, int)
    return model, revision


def put(client: TestClient, pid: str, model: object, **params: str | int) -> httpx2.Response:
    content = model if isinstance(model, (str, bytes)) else json.dumps(model)
    return client.put(f"/v1/projects/{pid}/model", content=content, params=params)


def edit(
    client: TestClient,
    pid: str,
    *edits: Json,
    base_revision: int | None = None,
    headers: dict[str, str] | None = None,
) -> httpx2.Response:
    body: Json = {"edits": list(edits)}
    if base_revision is not None:
        body["base_revision"] = base_revision
    return client.post(f"/v1/projects/{pid}/model/edits", json=body, headers=headers)


def seeded(client: TestClient, model: Json | None = None) -> str:
    """A project holding the shop model, at revision 1."""
    pid = new_project(client)
    response = put(client, pid, shop() if model is None else model)
    assert response.status_code == 200
    assert response.json()["revision"] == 1
    return pid


def component(model: Json, cid: str) -> Json:
    [found] = [item for item in model["components"] if item["id"] == cid]
    assert isinstance(found, dict)
    return found


# --- GET .../model ---------------------------------------------------------------------


def test_get_model_returns_the_new_projects_model_at_revision_0(client: TestClient) -> None:
    pid = new_project(client)
    response = client.get(f"/v1/projects/{pid}/model")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"model", "revision"}
    assert body["revision"] == 0
    assert body["model"] == on_disk(client, pid)[0]
    assert body["model"]["domain"] == "process"


def test_get_model_of_an_unknown_project_is_404_with_e185(client: TestClient) -> None:
    for response in (
        client.get("/v1/projects/nope/model"),
        put(client, "nope", shop()),
        edit(client, "nope", {"edit": "set_label", "id": "a", "label": None}),
        client.post("/v1/projects/nope/validate"),
    ):
        assert response.status_code == 404
        assert_error(response.json(), "E185")


def test_a_project_whose_project_json_cannot_be_read_is_400_with_e186(
    client: TestClient,
) -> None:
    pid = new_project(client)
    (folder(client, pid) / PROJECT_FILE).write_text("{", encoding="utf-8")
    for response in (
        client.get(f"/v1/projects/{pid}/model"),
        put(client, pid, shop()),
        edit(client, pid, {"edit": "set_label", "id": "a", "label": None}),
        client.post(f"/v1/projects/{pid}/validate"),
    ):
        assert response.status_code == 400
        assert_error(response.json(), "E186")


def test_a_model_json_that_is_not_json_is_400_with_e186(client: TestClient) -> None:
    pid = new_project(client)
    (folder(client, pid) / MODEL_FILE).write_text("{not json", encoding="utf-8")
    response = client.get(f"/v1/projects/{pid}/model")
    assert response.status_code == 400
    body = response.json()
    assert_error(body, "E186")
    assert [issue["code"] for issue in body["issues"]] == ["E100"]
    response = edit(client, pid, {"edit": "set_label", "id": "a", "label": None})
    assert response.status_code == 400
    assert_error(response.json(), "E186")


def test_a_missing_model_json_is_400_with_e186(client: TestClient) -> None:
    pid = new_project(client)
    (folder(client, pid) / MODEL_FILE).unlink()
    for response in (
        client.get(f"/v1/projects/{pid}/model"),
        client.post(f"/v1/projects/{pid}/validate"),
    ):
        assert response.status_code == 400
        assert_error(response.json(), "E186")


# --- PUT .../model ---------------------------------------------------------------------


def test_put_saves_a_model_that_passes_and_increments_the_revision(client: TestClient) -> None:
    pid = new_project(client)
    response = put(client, pid, shop())
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"model", "revision", "issues"}
    assert body == {"model": shop(), "revision": 1, "issues": []}
    assert on_disk(client, pid) == (shop(), 1)
    assert client.get(f"/v1/projects/{pid}/model").json() == {"model": shop(), "revision": 1}
    assert [item["model_revision"] for item in client.get("/v1/projects").json()] == [1]
    # Written through a temporary file and a rename: nothing else is left behind.
    assert sorted(path.name for path in folder(client, pid).iterdir()) == [
        "data",
        "model.json",
        "project.json",
        "runs",
    ]


def test_put_with_a_schema_failure_is_400_and_saves_nothing(client: TestClient) -> None:
    pid = new_project(client)
    before = on_disk(client, pid)
    broken = shop()
    del broken["meta"]
    for content, code in (
        (broken, "E100"),
        ("{not json", "E100"),
        ('{"format_version": "0.1", "format_version": "0.1"}', "E100"),
        ({**shop(), "format_version": "9.0"}, "E101"),
        ([1, 2], "E100"),
    ):
        response = put(client, pid, content)
        assert response.status_code == 400
        body = response.json()
        assert_error(body, code)
        assert body["issues"] and all(issue["code"] == code for issue in body["issues"])
        assert on_disk(client, pid) == before


def test_put_with_a_number_json_cannot_hold_is_400_with_e100(client: TestClient) -> None:
    pid = new_project(client)
    text = json.dumps(shop()).replace('"ui": {"x": 10', '"ui": {"x": 1e400')
    assert "1e400" in text
    response = put(client, pid, text)
    assert response.status_code == 400
    body = response.json()
    assert_error(body, "E100")
    assert [issue["path"] for issue in body["issues"]] == ["/components/2/ui/x"]
    assert on_disk(client, pid)[1] == 0
    assert client.get(f"/v1/projects/{pid}/model").status_code == 200


def test_write_json_never_writes_a_number_json_cannot_hold(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        projects_store.write_json(tmp_path / "x.json", {"x": float("nan")})
    assert list(tmp_path.iterdir()) == []


def test_put_with_meaning_errors_saves_and_returns_them(client: TestClient) -> None:
    pid = new_project(client)
    model = shop()
    component(model, "till")["type"] = "pump"
    response = put(client, pid, model)
    assert response.status_code == 200
    body = response.json()
    assert body["revision"] == 1
    assert "E120" in [issue["code"] for issue in body["issues"]]
    assert all(
        set(issue) == {"code", "severity", "component", "path", "message", "hint"}
        for issue in body["issues"]
    )
    assert on_disk(client, pid) == (model, 1)


def test_put_reads_the_body_as_a_model_file_whatever_its_content_type(client: TestClient) -> None:
    pid = new_project(client)
    text = "﻿" + json.dumps(shop())
    response = client.put(
        f"/v1/projects/{pid}/model",
        content=text.encode("utf-8"),
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 200
    assert on_disk(client, pid) == (shop(), 1)
    # Saved as JSON indented by two spaces.
    saved = (folder(client, pid) / MODEL_FILE).read_text(encoding="utf-8")
    assert saved == json.dumps(shop(), indent=2, ensure_ascii=False) + "\n"


def test_put_with_the_current_base_revision_is_saved(client: TestClient) -> None:
    pid = new_project(client)
    response = put(client, pid, shop(), base_revision=0)
    assert response.status_code == 200
    assert response.json()["revision"] == 1


def test_put_with_a_stale_base_revision_is_409_with_e181(client: TestClient) -> None:
    pid = seeded(client)
    changed = shop()
    changed["meta"]["name"] = "Other"
    response = put(client, pid, changed, base_revision=0)
    assert response.status_code == 409
    body = response.json()
    assert set(body) == {"error", "issues", "model", "revision"}
    assert body["error"]["code"] == "E181"
    assert body["error"]["message"]
    assert body["issues"] == []
    assert body["model"] == shop()
    assert body["revision"] == 1
    assert on_disk(client, pid) == (shop(), 1)


@pytest.mark.parametrize("value", ["one", "1.5", "", "-"])
def test_put_with_a_base_revision_that_is_not_a_whole_number_is_e184(
    client: TestClient, value: str
) -> None:
    pid = new_project(client)
    response = put(client, pid, shop(), base_revision=value)
    assert response.status_code == 400
    body = response.json()
    assert_error(body, "E184")
    assert "base_revision" in body["issues"][0]["message"]
    assert on_disk(client, pid)[1] == 0


def test_put_may_change_the_domain(client: TestClient) -> None:
    """The owner design review's M6 gap: no edit changes ``domain``; a project chooses it
    at creation (AKS-110) and changes it only with a whole-model PUT."""
    pid = new_project(client)
    response = put(client, pid, plan())
    assert response.status_code == 200
    assert response.json()["issues"] == []
    assert on_disk(client, pid) == (plan(), 1)
    pid = new_project(client, "optimization")
    assert client.get(f"/v1/projects/{pid}/model").json()["model"]["domain"] == "optimization"


def test_a_failed_write_leaves_the_model_and_revision(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = seeded(client)

    def refuse(*_args: object) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(os, "replace", refuse)
    changed = shop()
    changed["meta"]["name"] = "Other"
    response = put(client, pid, changed)
    assert response.status_code == 400
    assert_error(response.json(), "E186")
    assert "denied" not in response.text
    monkeypatch.undo()
    assert on_disk(client, pid) == (shop(), 1)


def test_two_writes_with_the_same_base_revision_cannot_both_pass(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Writes to one project are serialized: the second waits for the first, then finds
    the revision moved. Reading the revision is slowed so that both would pass the check
    without the lock."""
    pid = seeded(client)
    slow_read = projects_store.read_project

    def slowly(where: Path) -> object:
        record = slow_read(where)
        time.sleep(0.2)
        return record

    monkeypatch.setattr("ithax.service.model_store.read_project", slowly)
    statuses: list[int] = []

    def write(name: str) -> None:
        changed = shop()
        changed["meta"]["name"] = name
        statuses.append(put(client, pid, changed, base_revision=1).status_code)

    threads = [threading.Thread(target=write, args=(name,)) for name in ("A", "B")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(statuses) == [200, 409]
    model, revision = on_disk(client, pid)
    assert revision == 2
    assert model["meta"]["name"] in ("A", "B")


# --- POST .../model/edits: one request test per kind ---------------------------------

Check = Callable[[Json], None]


def _added(model: Json) -> None:
    assert component(model, "bin") == {"id": "bin", "type": "sink", "params": {}, "ui": {"x": 5}}


def _removed(model: Json) -> None:
    assert [item["id"] for item in model["components"]].count("exit") == 0
    assert model["connections"] == [{"from": "arrivals.out", "to": "till.in"}]


def _renamed(model: Json) -> None:
    assert component(model, "counter")["label"] == "Till"
    assert {"from": "arrivals.out", "to": "counter.in"} in model["connections"]
    assert component(model, "breakdown")["params"]["target"] == "counter"
    assert model["objectives"][0]["metric"] == "counter.wait.mean"
    assert model["constraints"][0]["metric"] == "counter.utilization"


def _setting(model: Json) -> None:
    assert component(model, "till")["params"]["service"]["mean"] == "2 min"


def _connected(model: Json) -> None:
    assert model["connections"][1] == {"from": "till.out", "to": "bin.in"}
    assert len(model["connections"]) == 2


def _disconnected(model: Json) -> None:
    assert model["connections"] == [{"from": "arrivals.out", "to": "till.in"}]


def _parameter(model: Json) -> None:
    assert model["parameters"]["speed"] == {"value": "1 min", "type": "quantity"}


def _parameter_removed(model: Json) -> None:
    assert list(model["parameters"]) == ["tills"]


def _experiment(model: Json) -> None:
    assert model["experiments"][1] == {
        "id": "long",
        "length": "40 h",
        "warmup": "0 s",
        "replications": 30,
    }


def _experiment_removed(model: Json) -> None:
    assert [item["id"] for item in model["experiments"]] == ["long"]


def _scenario(model: Json) -> None:
    assert model["experiments"][0]["scenarios"][-1] == {"id": "two", "set": {"tills": 2}}


def _scenario_removed(model: Json) -> None:
    assert model["experiments"][0]["scenarios"] == []


def _path(model: Json) -> None:
    assert model["meta"]["description"] == "A small shop"


def _path_removed(model: Json) -> None:
    assert "constraints" not in model


def _ui(model: Json) -> None:
    assert component(model, "till")["ui"] == {"x": 300, "y": 40}


def _label(model: Json) -> None:
    assert "label" not in component(model, "till")
    assert component(model, "exit")["label"] == "Door"


BIN = {"edit": "add_component", "id": "bin", "type": "sink", "params": {}}

APPLIED: list[tuple[str, list[Json], Check]] = [
    ("add_component", [{**BIN, "ui": {"x": 5}}], _added),
    ("remove_component", [{"edit": "remove_component", "id": "exit"}], _removed),
    (
        "rename_component",
        [{"edit": "rename_component", "id": "till", "new_id": "counter"}],
        _renamed,
    ),
    (
        "set_setting",
        [{"edit": "set_setting", "id": "till", "path": "/service/mean", "value": "2 min"}],
        _setting,
    ),
    ("connect", [BIN, {"edit": "connect", "from": "till.out", "to": "bin.in"}], _connected),
    ("disconnect", [{"edit": "disconnect", "from": "till.out"}], _disconnected),
    (
        "set_parameter",
        [{"edit": "set_parameter", "id": "speed", "value": "1 min", "type": "quantity"}],
        _parameter,
    ),
    (
        "remove_parameter",
        [
            {"edit": "remove_scenario", "experiment_id": "base", "id": "more"},
            {"edit": "remove_parameter", "id": "spare"},
        ],
        _parameter_removed,
    ),
    ("set_experiment", [{"edit": "set_experiment", "id": "long", "length": "40 h"}], _experiment),
    (
        "remove_experiment",
        [{"edit": "set_experiment", "id": "long"}, {"edit": "remove_experiment", "id": "base"}],
        _experiment_removed,
    ),
    (
        "set_scenario",
        [{"edit": "set_scenario", "experiment_id": "base", "id": "two", "set": {"tills": 2}}],
        _scenario,
    ),
    (
        "remove_scenario",
        [{"edit": "remove_scenario", "experiment_id": "base", "id": "more"}],
        _scenario_removed,
    ),
    (
        "set_path",
        [{"edit": "set_path", "path": "/meta/description", "value": "A small shop"}],
        _path,
    ),
    ("remove_path", [{"edit": "remove_path", "path": "/constraints"}], _path_removed),
    ("set_ui", [{"edit": "set_ui", "id": "till", "ui": {"x": 300, "y": 40}}], _ui),
    (
        "set_label",
        [
            {"edit": "set_label", "id": "till", "label": None},
            {"edit": "set_label", "id": "exit", "label": "Door"},
        ],
        _label,
    ),
]


def test_every_edit_kind_has_a_request_test() -> None:
    assert [kind for kind, _, _ in APPLIED] == list(EDIT_KINDS)
    assert all(edits[-1]["edit"] == kind for kind, edits, _ in APPLIED)


@pytest.mark.parametrize(("kind", "edits", "check"), APPLIED, ids=[case[0] for case in APPLIED])
def test_an_edit_is_applied_saved_and_counted_as_a_write(
    client: TestClient, kind: str, edits: list[Json], check: Check
) -> None:
    pid = seeded(client)
    response = edit(client, pid, *edits, base_revision=1)
    assert response.status_code == 200, response.json()
    body = response.json()
    assert set(body) == {"model", "revision", "issues"}
    assert body["revision"] == 2
    check(body["model"])
    assert on_disk(client, pid) == (body["model"], 2)
    assert all(issue["severity"] in ("error", "warning") for issue in body["issues"])


def test_set_path_reaches_variables_and_objective_in_an_optimization_model(
    client: TestClient,
) -> None:
    pid = seeded(client, plan())
    response = edit(
        client,
        pid,
        {"edit": "set_path", "path": "/variables/-", "value": {"id": "chairs", "type": "integer"}},
        {"edit": "set_path", "path": "/objective/linear/chairs", "value": 2},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["issues"] == []
    assert body["model"]["objective"]["linear"] == {"desks": 3, "chairs": 2}


def test_an_edit_batch_with_meaning_errors_is_saved_with_them(client: TestClient) -> None:
    pid = seeded(client)
    response = edit(
        client, pid, {"edit": "add_component", "id": "Bin 2", "type": "sink", "params": {}}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["revision"] == 2
    assert [issue["code"] for issue in body["issues"] if issue["severity"] == "error"] == ["E111"]
    assert on_disk(client, pid)[1] == 2


# --- POST .../model/edits: E180, E181, E184, E186 ------------------------------------


REJECTED: list[tuple[str, list[Json]]] = [
    (
        "add_component: duplicate id",
        [{"edit": "add_component", "id": "till", "type": "sink", "params": {}}],
    ),
    (
        "add_component: unknown type",
        [{"edit": "add_component", "id": "pump", "type": "pump", "params": {}}],
    ),
    ("remove_component: unknown id", [{"edit": "remove_component", "id": "pump"}]),
    ("rename_component: unknown id", [{"edit": "rename_component", "id": "pump", "new_id": "p"}]),
    (
        "rename_component: duplicate id",
        [{"edit": "rename_component", "id": "till", "new_id": "exit"}],
    ),
    (
        "set_setting: unknown id",
        [{"edit": "set_setting", "id": "pump", "path": "/capacity", "value": 1}],
    ),
    (
        "set_setting: no parent",
        [{"edit": "set_setting", "id": "till", "path": "/arrival/mean", "value": 1}],
    ),
    (
        "set_parameter: new without value and type",
        [{"edit": "set_parameter", "id": "speed", "value": 1}],
    ),
    ("remove_parameter: unknown", [{"edit": "remove_parameter", "id": "speed"}]),
    ("remove_parameter: referenced", [{"edit": "remove_parameter", "id": "tills"}]),
    ("set_experiment: schema", [{"edit": "set_experiment", "id": "base", "scenarios": 3}]),
    ("remove_experiment: unknown", [{"edit": "remove_experiment", "id": "long"}]),
    (
        "set_scenario: unknown experiment",
        [{"edit": "set_scenario", "experiment_id": "long", "id": "s", "set": {}}],
    ),
    (
        "set_scenario: unknown parameter",
        [{"edit": "set_scenario", "experiment_id": "base", "id": "s", "set": {"speed": 1}}],
    ),
    (
        "remove_scenario: unknown experiment",
        [{"edit": "remove_scenario", "experiment_id": "long", "id": "more"}],
    ),
    (
        "remove_scenario: unknown scenario",
        [{"edit": "remove_scenario", "experiment_id": "base", "id": "less"}],
    ),
    ("set_path: no parent", [{"edit": "set_path", "path": "/meta/extra/name", "value": "x"}]),
    ("set_path: out of reach", [{"edit": "set_path", "path": "/domain", "value": "optimization"}]),
    ("set_path: schema", [{"edit": "set_path", "path": "/meta/name", "value": 5}]),
    ("remove_path: missing", [{"edit": "remove_path", "path": "/meta/author"}]),
    ("remove_path: out of reach", [{"edit": "remove_path", "path": "/components/0"}]),
    ("set_ui: unknown id", [{"edit": "set_ui", "id": "pump", "ui": {}}]),
    ("set_label: unknown id", [{"edit": "set_label", "id": "pump", "label": "x"}]),
]


def test_every_edit_kind_with_a_rejection_case_has_its_request_test() -> None:
    kinds = {edits[-1]["edit"] for _, edits in REJECTED}
    # connect is rejected only when it breaks the schema (an optimization model, below);
    # disconnect never is.
    assert kinds == set(EDIT_KINDS) - {"connect", "disconnect"}


@pytest.mark.parametrize(("case", "edits"), REJECTED, ids=[case for case, _ in REJECTED])
def test_an_edit_that_cannot_be_applied_is_400_with_e180_and_nothing_is_saved(
    client: TestClient, case: str, edits: list[Json]
) -> None:
    pid = seeded(client)
    first = {"edit": "set_label", "id": "exit", "label": "Door"}
    response = edit(client, pid, first, *edits)
    assert response.status_code == 400
    body = response.json()
    assert_error(body, "E180")
    [issue] = body["issues"]
    assert issue["code"] == "E180" and issue["severity"] == "error"
    assert issue["path"] == f"/edits/{len(edits)}"
    assert issue["component"] is None
    assert issue["message"] and issue["hint"]
    assert body["error"]["message"] == issue["message"]
    assert "Traceback" not in response.text and "Error(" not in response.text
    assert on_disk(client, pid) == (shop(), 1)


def test_connect_in_an_optimization_model_is_e180(client: TestClient) -> None:
    pid = seeded(client, plan())
    response = edit(client, pid, {"edit": "connect", "from": "a.out", "to": "b.in"})
    assert response.status_code == 400
    body = response.json()
    assert_error(body, "E180")
    assert [issue["path"] for issue in body["issues"]] == ["/edits/0"]
    assert on_disk(client, pid) == (plan(), 1)


def test_remove_experiment_in_an_optimization_model_is_e180_not_500(client: TestClient) -> None:
    """Review of PR #35: an optimization model has no experiments."""
    pid = seeded(client, plan())
    response = edit(client, pid, {"edit": "remove_experiment", "id": "base"})
    assert response.status_code == 400
    assert_error(response.json(), "E180")
    assert on_disk(client, pid) == (plan(), 1)


def test_a_null_scenario_set_in_a_batch_does_not_fail_the_request(client: TestClient) -> None:
    """Review of PR #35: a batch may pass through a state the schema pass would refuse."""
    pid = seeded(client)
    response = edit(
        client,
        pid,
        {"edit": "set_experiment", "id": "base", "scenarios": [{"id": "s", "set": None}]},
        {"edit": "remove_parameter", "id": "spare"},
        {"edit": "set_experiment", "id": "base", "scenarios": []},
    )
    assert response.status_code == 200
    assert "spare" not in response.json()["model"]["parameters"]


def test_a_stale_base_revision_is_409_with_e181_and_nothing_is_applied(client: TestClient) -> None:
    pid = seeded(client)
    response = edit(client, pid, {"edit": "set_label", "id": "till", "label": "X"}, base_revision=0)
    assert response.status_code == 409
    body = response.json()
    assert set(body) == {"error", "issues", "model", "revision"}
    assert body["error"]["code"] == "E181"
    assert "0" in body["error"]["message"] and "1" in body["error"]["message"]
    assert body["issues"] == []
    assert (body["model"], body["revision"]) == (shop(), 1)
    assert on_disk(client, pid) == (shop(), 1)


@pytest.mark.parametrize(
    ("body", "path"),
    [
        ({}, "/edits"),
        ({"edits": []}, "/edits"),
        ({"edits": "set_label"}, "/edits"),
        ({"edits": [{"edit": "fly"}]}, "/edits/0/edit"),
        ({"edits": [{"edit": "set_label", "id": 1, "label": None}]}, "/edits/0/id"),
        (
            {"edits": [{"edit": "set_label", "id": "a", "label": None}], "base_revision": "1"},
            "/base_revision",
        ),
        (
            {"edits": [{"edit": "set_label", "id": "a", "label": None}], "base_revision": True},
            "/base_revision",
        ),
        ({"edits": [{"edit": "set_label", "id": "a", "label": None}], "force": True}, "/force"),
    ],
)
def test_a_malformed_edit_request_is_400_with_e184(
    client: TestClient, body: Json, path: str
) -> None:
    pid = seeded(client)
    response = client.post(f"/v1/projects/{pid}/model/edits", json=body)
    assert response.status_code == 400
    answer = response.json()
    assert_error(answer, "E184")
    assert [issue["path"] for issue in answer["issues"]] == [path]
    assert on_disk(client, pid) == (shop(), 1)


def test_edits_on_a_model_json_that_fails_the_schema_are_e186(client: TestClient) -> None:
    pid = seeded(client)
    broken = shop()
    broken["surprise"] = 1
    (folder(client, pid) / MODEL_FILE).write_text(json.dumps(broken), encoding="utf-8")
    response = edit(client, pid, {"edit": "set_label", "id": "till", "label": "X"})
    assert response.status_code == 400
    body = response.json()
    assert_error(body, "E186")
    assert [issue["code"] for issue in body["issues"]] == ["E100"]
    # A whole-model PUT replaces it.
    assert put(client, pid, shop()).status_code == 200


def test_a_rejected_write_is_not_a_write(client: TestClient) -> None:
    pid = seeded(client)
    edit(client, pid, {"edit": "remove_component", "id": "pump"})
    edit(client, pid, {"edit": "set_label", "id": "till", "label": "X"}, base_revision=0)
    put(client, pid, "{")
    response = edit(client, pid, {"edit": "set_label", "id": "till", "label": "X"})
    assert response.json()["revision"] == 2


# --- POST .../validate -----------------------------------------------------------------


class FlaggingAdapter(ProcessAdapter):
    """The process adapter with one engine-specific issue from ``validate``."""

    name = "flagging"
    calls: list[str]

    def __init__(self) -> None:
        self.calls = []

    def validate(self, model: Model) -> list[Issue]:
        self.calls.append(model.meta.name)
        return [
            Issue(
                code="E300",
                component="till",
                path="/components/2",
                message="The engine cannot run 'till' this way.",
                hint="Change it.",
            )
        ]


@pytest.fixture
def flagging(config: ServiceConfig) -> tuple[FastAPI, FlaggingAdapter]:
    adapter = FlaggingAdapter()
    return create_app(dataclasses.replace(config, adapters={"flagging": adapter})), adapter


def test_validate_runs_the_schema_and_meaning_passes_then_the_adapter(
    flagging: tuple[FastAPI, FlaggingAdapter],
) -> None:
    app, adapter = flagging
    with TestClient(app, base_url=BASE_URL, headers=AUTH) as client:
        model = shop()
        component(model, "arrivals")["params"]["interarrival"] = {
            "dist": "normal",
            "mean": "1 min",
            "sd": "1 min",
        }
        pid = seeded(client, model)
        response = client.post(f"/v1/projects/{pid}/validate")
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"revision", "issues"}
        assert body["revision"] == 1
        # The meaning pass's warnings, then the adapter's issue. Arrivals about every
        # 1.08 min (the clipped normal) need 1.38 tills of the one there is, under its
        # failure, and of the pool under its rota: W201 at both since #73.
        assert [issue["code"] for issue in body["issues"]] == ["W201", "W201", "W202", "E300"]
        assert adapter.calls == ["Shop"]
        # A write's response carries loading's issues only, not the adapter's.
        response = edit(client, pid, {"edit": "set_label", "id": "till", "label": "X"})
        assert [issue["code"] for issue in response.json()["issues"]] == ["W201", "W201", "W202"]
        assert adapter.calls == ["Shop"]


def test_validate_does_not_call_the_adapter_after_a_meaning_error(
    flagging: tuple[FastAPI, FlaggingAdapter],
) -> None:
    app, adapter = flagging
    with TestClient(app, base_url=BASE_URL, headers=AUTH) as client:
        model = shop()
        component(model, "till")["params"]["capacity"] = "two"
        pid = seeded(client, model)
        body = client.post(f"/v1/projects/{pid}/validate").json()
        assert [issue["code"] for issue in body["issues"]] == ["E123"]
        assert adapter.calls == []


def test_validate_reports_a_schema_failure_of_the_saved_file(client: TestClient) -> None:
    pid = seeded(client)
    (folder(client, pid) / MODEL_FILE).write_text('{"format_version": "0.1"}', encoding="utf-8")
    body = client.post(f"/v1/projects/{pid}/validate").json()
    assert body["issues"] and {issue["code"] for issue in body["issues"]} == {"E100"}


def test_validate_of_the_default_models(client: TestClient) -> None:
    """A new process model has no issues; a new optimization model starts empty, so its
    one issue is E179 at /variables (#80, D2)."""
    pid = new_project(client, "process")
    assert client.post(f"/v1/projects/{pid}/validate").json() == {"revision": 0, "issues": []}
    pid = new_project(client, "optimization")
    body = client.post(f"/v1/projects/{pid}/validate").json()
    assert [(issue["code"], issue["path"]) for issue in body["issues"]] == [("E179", "/variables")]


def test_validate_checks_data_references_against_the_project(client: TestClient) -> None:
    model = shop()
    component(model, "arrivals")["params"]["interarrival"] = {
        "dist": "empirical",
        "data": {"file": "a.csv", "column": "gap"},
    }
    pid = seeded(client, model)
    body = client.post(f"/v1/projects/{pid}/validate").json()
    assert [issue["code"] for issue in body["issues"]] == ["E162"]


# --- numbers JSON cannot hold, on every way in (review of PR #35) ---------------------

INFINITE_UI = '"ui": {"x": 1e400'


def infinite_shop_text() -> str:
    text = json.dumps(shop()).replace('"ui": {"x": 10', INFINITE_UI)
    assert INFINITE_UI in text
    return text


@pytest.mark.parametrize("number", ["1e400", "NaN", "-Infinity"])
def test_a_model_json_on_disk_with_a_number_json_cannot_hold_is_e186(
    client: TestClient, number: str
) -> None:
    pid = seeded(client)
    text = json.dumps(shop()).replace('"ui": {"x": 10', '"ui": {"x": ' + number)
    (folder(client, pid) / MODEL_FILE).write_text(text, encoding="utf-8")
    for response in (
        client.get(f"/v1/projects/{pid}/model"),
        edit(client, pid, {"edit": "set_label", "id": "till", "label": "X"}),
        edit(client, pid, {"edit": "set_label", "id": "till", "label": "X"}, base_revision=0),
    ):
        assert response.status_code == 400
        body = response.json()
        assert_error(body, "E186")
        assert [(issue["code"], issue["path"]) for issue in body["issues"]] == [
            ("E100", "/components/2/ui/x")
        ]
    # Nothing moved: the revision is where it was.
    assert json.loads((folder(client, pid) / PROJECT_FILE).read_text())["model_revision"] == 1
    # Validate reports the admission gate's E100, at its place, and nothing else.
    body = client.post(f"/v1/projects/{pid}/validate").json()
    assert [(issue["code"], issue["path"]) for issue in body["issues"]] == [
        ("E100", "/components/2/ui/x")
    ]
    # A whole-model PUT replaces it.
    assert put(client, pid, shop()).status_code == 200


def test_an_opened_folder_whose_model_json_holds_one_is_e186_when_read(
    client: TestClient, tmp_path: Path
) -> None:
    pid = seeded(client)
    source = folder(client, pid)
    (source / MODEL_FILE).write_text(infinite_shop_text(), encoding="utf-8")
    moved = tmp_path / "moved"
    source.rename(moved)
    assert client.post("/v1/projects/open", json={"path": str(moved)}).status_code == 200
    response = client.get(f"/v1/projects/{pid}/model")
    assert response.status_code == 400
    assert_error(response.json(), "E186")


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-1e400"])
def test_a_put_body_with_a_number_json_cannot_hold_is_e100(client: TestClient, number: str) -> None:
    pid = new_project(client)
    text = json.dumps(shop()).replace('"ui": {"x": 10', '"ui": {"x": ' + number)
    response = put(client, pid, text)
    assert response.status_code == 400
    assert_error(response.json(), "E100")
    assert on_disk(client, pid)[1] == 0


@pytest.mark.parametrize("number", ["NaN", "Infinity", "1e400"])
def test_an_edit_value_with_a_number_json_cannot_hold_is_e184(
    client: TestClient, number: str
) -> None:
    pid = seeded(client)
    body = '{"edits": [{"edit": "set_path", "path": "/meta/x", "value": [' + number + "]}]}"
    response = client.post(
        f"/v1/projects/{pid}/model/edits",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    answer = response.json()
    assert_error(answer, "E184")
    assert [issue["path"] for issue in answer["issues"]] == ["/edits/0/value"]
    assert on_disk(client, pid) == (shop(), 1)


@pytest.mark.parametrize("number", ["NaN", "1e400"])
def test_other_bodies_with_a_number_json_cannot_hold_are_e184(
    client: TestClient, number: str
) -> None:
    for path, body in (
        ("/v1/projects", '{"name": ' + number + "}"),
        ("/v1/projects/open", '{"path": ' + number + "}"),
        (
            f"/v1/projects/{seeded(client)}/model/edits",
            '{"edits": [{"edit": "set_label", "id": "a", "label": null}], "base_revision": '
            + number
            + "}",
        ),
    ):
        response = client.post(path, content=body, headers={"Content-Type": "application/json"})
        assert response.status_code == 400, path
        assert_error(response.json(), "E184")
