"""Admitting and saving a model (spec 3 "Revision", "Endpoints"; AKS-111, review of
PR #35).

Every way a model enters the service (a ``model.json`` read from disk, an opened folder,
a ``PUT`` body, an edit batch and its result, ``validate``) passes one admission gate: the
document must become the exact bytes that would be written (JSON without NaN or
infinities, encoded as strict UTF-8). Hostile values are refused with a coded issue,
whether or not the model also warns, and leave the revision, ``model.json``, the folder
and the events untouched. A save writes both files to temporary files first and commits
with the last rename, of ``project.json``.
"""

import dataclasses
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import ithax.model.edits as edits_module
from ithax.engines.process.adapter import ProcessAdapter
from ithax.model.issues import Issue
from ithax.model.model import Model
from ithax.service.app import create_app
from ithax.service.config import ServiceConfig
from ithax.service.errors import AsciiJSONResponse
from ithax.service.projects_store import MODEL_FILE, PROJECT_FILE, encode_json, write_json
from ithax.service.state import ServiceState
from service.service_support import AUTH, BASE_URL, assert_error

FIXTURES = Path(__file__).resolve().parents[1] / "model" / "fixtures" / "edits"

Json = dict[str, Any]

#: JSON tokens that Python reads but the service cannot write back.
HOSTILE = ["1e400", "NaN", "Infinity", "-Infinity", '"\\ud800"']

MARK = "__HOSTILE__"


def shop(*, warns: bool = False) -> Json:
    model: Json = json.loads((FIXTURES / "shop.json").read_text(encoding="utf-8"))
    if warns:
        # A normal that clips: W202, a warning only.
        model["components"][0]["params"]["interarrival"] = {
            "dist": "normal",
            "mean": "1 min",
            "sd": "1 min",
        }
    return model


def marked(place: str, *, warns: bool) -> Json:
    """The shop model with the marker at ``place``."""
    model = shop(warns=warns)
    till = model["components"][2]
    if place == "label":
        till["label"] = MARK
    elif place == "ui":
        till["ui"]["x"] = MARK
    elif place == "setting":
        till["params"]["capacity"] = MARK
    else:
        model["meta"]["description"] = MARK
    return model


def hostile_text(place: str, token: str, *, warns: bool) -> str:
    text = json.dumps(marked(place, warns=warns))
    assert f'"{MARK}"' in text
    return text.replace(f'"{MARK}"', token)


PLACES = ["label", "ui", "setting", "meta"]
CASES = [
    pytest.param(place, token, warns, id=f"{place}-{token}-{'warns' if warns else 'clean'}")
    for place in PLACES
    for token in HOSTILE
    for warns in (False, True)
]


class Recorder(ProcessAdapter):
    """The process adapter, noting each call of ``validate``."""

    name = "recorder"

    def __init__(self) -> None:
        self.calls = 0

    def validate(self, model: Model) -> list[Issue]:
        self.calls += 1
        return []


@pytest.fixture
def adapter() -> Recorder:
    return Recorder()


@pytest.fixture
def client(config: ServiceConfig, adapter: Recorder) -> Iterator[TestClient]:
    app = create_app(dataclasses.replace(config, adapters={"recorder": adapter}))
    with TestClient(app, base_url=BASE_URL, headers=AUTH) as test_client:
        yield test_client


def state_of(client: TestClient) -> ServiceState:
    app = client.app
    assert isinstance(app, FastAPI)
    state = app.state.service
    assert isinstance(state, ServiceState)
    return state


@pytest.fixture
def events(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int, str]]:
    published: list[tuple[str, int, str]] = []
    monkeypatch.setattr(
        state_of(client).events,
        "model_written",
        lambda pid, revision, who: published.append((pid, revision, who)),
    )
    return published


def project(client: TestClient, model: Json | None = None) -> tuple[str, Path]:
    pid = client.post("/v1/projects", json={"name": "Shop"}).json()["id"]
    response = client.put(f"/v1/projects/{pid}/model", content=json.dumps(model or shop()))
    assert response.status_code == 200
    [entry] = [item for item in client.get("/v1/projects").json() if item["id"] == pid]
    return pid, Path(entry["path"])


def snapshot(where: Path) -> tuple[bytes, bytes, list[str]]:
    """``model.json``, ``project.json`` and the folder's file names."""
    return (
        (where / MODEL_FILE).read_bytes(),
        (where / PROJECT_FILE).read_bytes(),
        sorted(path.name for path in where.iterdir()),
    )


def coded_refusal(response: Any, *codes: str) -> None:
    assert 400 <= response.status_code < 500, response.text
    body = response.json()
    assert body["error"]["code"] in codes
    assert body["error"]["message"]


# --- every admission path ----------------------------------------------------------------


@pytest.mark.parametrize(("place", "token", "warns"), CASES)
def test_a_hostile_model_on_disk_is_refused_on_every_path(
    client: TestClient,
    events: list[tuple[str, int, str]],
    adapter: Recorder,
    place: str,
    token: str,
    warns: bool,
) -> None:
    pid, where = project(client, shop(warns=warns))
    events.clear()
    (where / MODEL_FILE).write_text(hostile_text(place, token, warns=warns), encoding="utf-8")
    before = snapshot(where)
    for response in (
        client.get(f"/v1/projects/{pid}/model"),
        client.post(
            f"/v1/projects/{pid}/model/edits",
            json={"edits": [{"edit": "set_label", "id": "exit", "label": "Door"}]},
        ),
        client.post(
            f"/v1/projects/{pid}/model/edits",
            json={
                "edits": [{"edit": "set_label", "id": "exit", "label": "Door"}],
                "base_revision": 0,
            },
        ),
    ):
        coded_refusal(response, "E186")
        assert response.json()["issues"][0]["code"] == "E100"
    calls = adapter.calls
    body = client.post(f"/v1/projects/{pid}/validate").json()
    assert body["revision"] == 1
    assert [issue["code"] for issue in body["issues"]] == ["E100"]
    assert adapter.calls == calls
    assert snapshot(where) == before
    assert events == []


@pytest.mark.parametrize(("place", "token", "warns"), CASES)
def test_a_hostile_put_body_is_refused(
    client: TestClient,
    events: list[tuple[str, int, str]],
    place: str,
    token: str,
    warns: bool,
) -> None:
    pid, where = project(client, shop(warns=warns))
    events.clear()
    before = snapshot(where)
    response = client.put(
        f"/v1/projects/{pid}/model", content=hostile_text(place, token, warns=warns)
    )
    coded_refusal(response, "E100")
    assert snapshot(where) == before
    assert events == []


EDITS = {
    "label": '{"edit": "set_label", "id": "till", "label": TOKEN}',
    "ui": '{"edit": "set_ui", "id": "till", "ui": {"x": TOKEN}}',
    "setting": '{"edit": "set_setting", "id": "till", "path": "/capacity", "value": TOKEN}',
    "meta": '{"edit": "set_path", "path": "/meta/description", "value": TOKEN}',
}


@pytest.mark.parametrize(("place", "token", "warns"), CASES)
def test_a_hostile_edit_is_refused(
    client: TestClient,
    events: list[tuple[str, int, str]],
    place: str,
    token: str,
    warns: bool,
) -> None:
    pid, where = project(client, shop(warns=warns))
    events.clear()
    before = snapshot(where)
    edit = EDITS[place].replace("TOKEN", token)
    response = client.post(
        f"/v1/projects/{pid}/model/edits",
        content='{"edits": [{"edit": "set_label", "id": "exit", "label": "Door"}, ' + edit + "]}",
        headers={"Content-Type": "application/json"},
    )
    coded_refusal(response, "E184")
    assert response.json()["issues"][0]["path"].startswith("/edits/1/")
    assert snapshot(where) == before
    assert events == []


@pytest.mark.parametrize("token", HOSTILE)
def test_an_opened_folder_with_a_hostile_model_is_refused_when_read(
    client: TestClient, tmp_path: Path, token: str
) -> None:
    pid, where = project(client)
    (where / MODEL_FILE).write_text(hostile_text("ui", token, warns=False), encoding="utf-8")
    moved = tmp_path / "moved"
    where.rename(moved)
    assert client.post("/v1/projects/open", json={"path": str(moved)}).status_code == 200
    coded_refusal(client.get(f"/v1/projects/{pid}/model"), "E186")


def test_an_edit_result_that_cannot_be_written_is_refused(
    client: TestClient, events: list[tuple[str, int, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gate also checks a batch's result, whatever the edits let through."""
    pid, where = project(client)
    events.clear()
    before = snapshot(where)
    real = edits_module.apply_edits

    def poisoned(*args: Any) -> Any:
        outcome = real(*args)
        assert outcome.model is not None
        outcome.model["meta"]["description"] = "\ud800"
        return outcome

    monkeypatch.setattr("ithax.service.model_store.apply_edits", poisoned)
    response = client.post(
        f"/v1/projects/{pid}/model/edits",
        json={"edits": [{"edit": "set_label", "id": "exit", "label": "Door"}]},
    )
    coded_refusal(response, "E180")
    assert response.json()["issues"][0]["path"] == "/edits"
    assert snapshot(where) == before
    assert events == []


def test_a_project_name_that_cannot_be_written_is_e184(client: TestClient) -> None:
    for path, body in (
        ("/v1/projects", '{"name": "\\ud800"}'),
        ("/v1/projects/open", '{"path": "/tmp/\\ud800"}'),
    ):
        response = client.post(path, content=body, headers={"Content-Type": "application/json"})
        assert response.status_code == 400, path
        assert_error(response.json(), "E184")


# --- the save --------------------------------------------------------------------------


@pytest.mark.parametrize("failing", [1, 2])
def test_a_save_that_fails_at_either_rename_changes_nothing(
    client: TestClient,
    events: list[tuple[str, int, str]],
    monkeypatch: pytest.MonkeyPatch,
    failing: int,
) -> None:
    """The first rename puts the new model in place, the second (``project.json``) is the
    commit; a failure at the second puts the old model back."""
    pid, where = project(client)
    events.clear()
    before = snapshot(where)
    real = os.replace
    calls: list[str] = []

    def replace(source: Any, target: Any) -> None:
        calls.append(Path(target).name)
        if len(calls) == failing:
            raise PermissionError("denied")
        real(source, target)

    monkeypatch.setattr(os, "replace", replace)
    response = client.post(
        f"/v1/projects/{pid}/model/edits",
        json={"edits": [{"edit": "set_label", "id": "exit", "label": "Door"}]},
    )
    monkeypatch.undo()
    coded_refusal(response, "E186")
    assert "denied" not in response.text
    # At the second rename the old model is renamed back into place.
    assert calls == ([MODEL_FILE] if failing == 1 else [MODEL_FILE, PROJECT_FILE, MODEL_FILE])
    assert snapshot(where) == before
    assert events == []


def test_a_save_commits_with_project_json_last_then_publishes(
    client: TestClient, events: list[tuple[str, int, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    pid, where = project(client)
    events.clear()
    real = os.replace
    order: list[str] = []

    def replace(source: Any, target: Any) -> None:
        order.append(Path(target).name)
        assert events == []
        real(source, target)

    monkeypatch.setattr(os, "replace", replace)
    response = client.post(
        f"/v1/projects/{pid}/model/edits",
        json={"edits": [{"edit": "set_label", "id": "exit", "label": "Door"}]},
    )
    monkeypatch.undo()
    assert response.status_code == 200
    assert order == [MODEL_FILE, PROJECT_FILE]
    assert events == [(pid, 2, "script")]
    assert sorted(path.name for path in where.iterdir()) == [
        "data",
        "model.json",
        "project.json",
        "runs",
    ]


# --- the pieces ------------------------------------------------------------------------


def test_encode_json_gives_the_bytes_written_or_refuses() -> None:
    assert encode_json({"a": "café"}) == '{\n  "a": "café"\n}\n'.encode()
    for value in (float("nan"), {"x": "\ud800"}, {"\ud800": 1}):
        with pytest.raises(ValueError):
            encode_json(value)


def test_responses_are_ascii_json_so_no_text_can_break_them() -> None:
    rendered = bytes(AsciiJSONResponse({"message": "café \ud800"}).body)
    assert rendered.decode("ascii")
    assert json.loads(rendered) == {"message": "café \ud800"}


def test_a_project_json_whose_text_cannot_be_written_back_is_e186(
    client: TestClient, events: list[tuple[str, int, str]]
) -> None:
    pid, where = project(client)
    events.clear()
    record = json.loads((where / PROJECT_FILE).read_text(encoding="utf-8"))
    text = json.dumps({**record, "name": "__NAME__"}).replace('"__NAME__"', '"\\ud800"')
    (where / PROJECT_FILE).write_text(text, encoding="utf-8")
    before = snapshot(where)
    response = client.post(
        f"/v1/projects/{pid}/model/edits",
        json={"edits": [{"edit": "set_label", "id": "exit", "label": "Door"}]},
    )
    coded_refusal(response, "E186")
    assert snapshot(where) == before
    assert events == []


def test_put_writes_a_model_json_that_was_missing(client: TestClient) -> None:
    pid, where = project(client)
    (where / MODEL_FILE).unlink()
    response = client.put(f"/v1/projects/{pid}/model", content=json.dumps(shop()))
    assert response.status_code == 200
    assert json.loads((where / MODEL_FILE).read_text(encoding="utf-8")) == shop()


def test_a_failed_commit_with_no_previous_model_leaves_none(
    client: TestClient, events: list[tuple[str, int, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    pid, where = project(client)
    (where / MODEL_FILE).unlink()
    events.clear()
    before = sorted(path.name for path in where.iterdir())
    record = (where / PROJECT_FILE).read_bytes()
    real = os.replace

    def replace(source: Any, target: Any) -> None:
        if Path(target).name == PROJECT_FILE:
            raise PermissionError("denied")
        real(source, target)

    monkeypatch.setattr(os, "replace", replace)
    response = client.put(f"/v1/projects/{pid}/model", content=json.dumps(shop()))
    monkeypatch.undo()
    coded_refusal(response, "E186")
    assert sorted(path.name for path in where.iterdir()) == before
    assert (where / PROJECT_FILE).read_bytes() == record
    assert events == []


def test_a_put_back_that_fails_is_logged_and_still_refused(
    client: TestClient,
    events: list[tuple[str, int, str]],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    pid, where = project(client)
    events.clear()
    real = os.replace
    calls: list[str] = []

    def replace(source: Any, target: Any) -> None:
        calls.append(Path(target).name)
        if len(calls) >= 2:
            raise PermissionError("denied")
        real(source, target)

    monkeypatch.setattr(os, "replace", replace)
    response = client.post(
        f"/v1/projects/{pid}/model/edits",
        json={"edits": [{"edit": "set_label", "id": "exit", "label": "Door"}]},
    )
    monkeypatch.undo()
    coded_refusal(response, "E186")
    assert "could not be put back" in caplog.text
    # The revision did not move and nothing was published; no temporary file is left.
    assert json.loads((where / PROJECT_FILE).read_text())["model_revision"] == 1
    assert sorted(path.name for path in where.iterdir()) == [
        "data",
        "model.json",
        "project.json",
        "runs",
    ]
    assert events == []


def test_encode_json_refuses_what_json_cannot_write() -> None:
    with pytest.raises(ValueError):
        encode_json(object())


def test_write_json_leaves_nothing_when_the_write_fails(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        write_json(tmp_path / "missing" / "x.json", {"a": 1})
    assert list(tmp_path.iterdir()) == []
