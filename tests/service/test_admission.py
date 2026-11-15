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
import subprocess
import sys
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
from ithax.service.commit import RECORD
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
def events(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> list[tuple[str, int, str | None]]:
    published: list[tuple[str, int, str | None]] = []
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
    events: list[tuple[str, int, str | None]],
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
    events: list[tuple[str, int, str | None]],
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
    events: list[tuple[str, int, str | None]],
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
    client: TestClient, events: list[tuple[str, int, str | None]], monkeypatch: pytest.MonkeyPatch
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


@pytest.mark.parametrize(("failing", "saved"), [(1, False), (2, True), (3, True)])
def test_a_save_that_fails_at_a_rename_is_refused_then_old_or_finished(
    client: TestClient,
    events: list[tuple[str, int, str | None]],
    monkeypatch: pytest.MonkeyPatch,
    failing: int,
    saved: bool,
) -> None:
    """The first rename puts the commit record in place (#71), the second the new model,
    the third ``project.json``. A failure at the record saves nothing. A failure after it
    leaves the change recorded (redo only, review of PR #182): the write is refused, and the
    next use of the project finishes it, so the model and the revision always agree."""
    pid, where = project(client)
    events.clear()
    before = snapshot(where)
    old = client.get(f"/v1/projects/{pid}/model").json()
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
    monkeypatch.setattr(os, "replace", real)  # the events fixture stays patched
    coded_refusal(response, "E186")
    body = response.json()
    assert "denied" not in response.text
    assert calls == [RECORD, MODEL_FILE, PROJECT_FILE][:failing]
    assert events == []
    if not saved:
        assert "not saved" in body["error"]["message"]
        assert snapshot(where) == before
        return
    assert "recorded" in body["error"]["message"]
    now = client.get(f"/v1/projects/{pid}/model").json()
    assert now["revision"] == old["revision"] + 1
    assert now["model"]["components"][-1]["label"] == "Door"
    assert not (where / RECORD).exists()
    # Published once the replay finishes it (third review of PR #182).
    assert events == [(pid, now["revision"], None)]


def test_a_save_commits_with_project_json_last_then_publishes(
    client: TestClient, events: list[tuple[str, int, str | None]], monkeypatch: pytest.MonkeyPatch
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
    assert order == [RECORD, MODEL_FILE, PROJECT_FILE]  # the commit record first (#71)
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
    client: TestClient, events: list[tuple[str, int, str | None]]
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


def test_a_save_over_no_model_that_fails_after_its_record_is_finished_on_next_use(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid, where = project(client)
    (where / MODEL_FILE).unlink()
    revision = json.loads((where / PROJECT_FILE).read_text())["model_revision"]
    real = os.replace

    def replace(source: Any, target: Any) -> None:
        if Path(target).name == PROJECT_FILE:
            raise PermissionError("denied")
        real(source, target)

    monkeypatch.setattr(os, "replace", replace)
    response = client.put(f"/v1/projects/{pid}/model", content=json.dumps(shop()))
    monkeypatch.undo()
    coded_refusal(response, "E186")
    now = client.get(f"/v1/projects/{pid}/model").json()
    assert now["revision"] == revision + 1 and now["model"] == shop()


def test_a_recorded_save_that_still_cannot_be_finished_refuses_the_project_until_it_can(
    client: TestClient,
    events: list[tuple[str, int, str | None]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review of PR #182: a replay that fails does not admit the folder; each use refuses
    with E186 and tries again, and once the folder can be written the save is finished."""
    pid, where = project(client)
    events.clear()
    real = os.replace
    calls: list[str] = []

    def replace(source: Any, target: Any) -> None:
        calls.append(Path(target).name)
        if Path(target).name == PROJECT_FILE:
            raise PermissionError("denied")
        real(source, target)

    monkeypatch.setattr(os, "replace", replace)
    response = client.post(
        f"/v1/projects/{pid}/model/edits",
        json={"edits": [{"edit": "set_label", "id": "exit", "label": "Door"}]},
    )
    coded_refusal(response, "E186")
    for _ in range(2):
        refused = client.get(f"/v1/projects/{pid}/model")
        assert refused.status_code == 400
        assert refused.json()["error"]["code"] == "E186"
        assert RECORD in refused.json()["error"]["message"]
    [listed] = [item for item in client.get("/v1/projects").json() if item["id"] == pid]
    assert listed["available"] is False
    monkeypatch.setattr(os, "replace", real)  # the events fixture stays patched
    now = client.get(f"/v1/projects/{pid}/model").json()
    assert now["revision"] == 2 and now["model"]["components"][-1]["label"] == "Door"
    assert sorted(path.name for path in where.iterdir()) == [
        "data",
        "model.json",
        "project.json",
        "runs",
    ]
    assert events == [(pid, 2, None)]  # published by the replay that finished it


def test_encode_json_refuses_what_json_cannot_write() -> None:
    with pytest.raises(ValueError):
        encode_json(object())


def test_write_json_leaves_nothing_when_the_write_fails(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        write_json(tmp_path / "missing" / "x.json", {"a": 1})
    assert list(tmp_path.iterdir()) == []


# --- a save a stopped service left half done (#71; docs/research/m14-atomic-save.md) --------

#: A child that saves the model bytes and project.json bytes it is given, as the model store
#: does, and ends at once (no clean-up runs) at its stop-th call of ``os.replace``.
HALF_SAVE = """
import os, sys
from pathlib import Path
from ithax.service.commit import Planned, replace_in_order
folder, model, record, stop = Path(sys.argv[1]), sys.argv[2], sys.argv[3], int(sys.argv[4])
real, calls = os.replace, []
def replace(source, target):
    calls.append(target)
    if len(calls) == stop:
        os._exit(9)
    real(source, target)
os.replace = replace
replace_in_order([
    Planned(folder / "model.json", Path(model).read_bytes()),
    Planned(folder / "project.json", Path(record).read_bytes()),
])
"""


def half_save(where: Path, tmp_path: Path, model: Json, stop: int) -> None:
    record = json.loads((where / PROJECT_FILE).read_text(encoding="utf-8"))
    record["model_revision"] += 1
    (tmp_path / "new-model.json").write_text(json.dumps(model), encoding="utf-8")
    (tmp_path / "new-record.json").write_text(json.dumps(record), encoding="utf-8")
    ended = subprocess.run(
        [
            sys.executable,
            "-c",
            HALF_SAVE,
            str(where),
            str(tmp_path / "new-model.json"),
            str(tmp_path / "new-record.json"),
            str(stop),
        ],
        check=False,
        timeout=60,
    )
    assert ended.returncode == 9


@pytest.mark.parametrize(("stop", "finished"), [(1, False), (2, True), (3, True)])
def test_a_save_a_stopped_service_left_half_done_is_old_or_new_on_the_next_start(
    config: ServiceConfig, tmp_path: Path, stop: int, finished: bool
) -> None:
    """Issue #71: the service stops before the commit record (1), after it (2), or between
    model.json and project.json (3, the gap of M6-34). The next service shows the old model
    and revision, or the new ones, never the new model at the old revision."""
    with TestClient(create_app(config), base_url=BASE_URL, headers=AUTH) as first:
        pid, where = project(first)
        old = first.get(f"/v1/projects/{pid}/model").json()
    new = {**old["model"], "meta": {**old["model"]["meta"], "name": "Shop after the save"}}
    half_save(where, tmp_path, new, stop)
    if stop == 3:
        assert json.loads((where / MODEL_FILE).read_text())["meta"]["name"] == "Shop after the save"
        assert json.loads((where / PROJECT_FILE).read_text())["model_revision"] == old["revision"]
    with TestClient(create_app(config), base_url=BASE_URL, headers=AUTH) as second:
        now = second.get(f"/v1/projects/{pid}/model").json()
        listed = [item for item in second.get("/v1/projects").json() if item["id"] == pid]
    expected = (new, old["revision"] + 1) if finished else (old["model"], old["revision"])
    assert (now["model"], now["revision"]) == expected
    assert listed[0]["model_revision"] == expected[1]
    assert not (where / RECORD).exists()


def test_an_opened_folder_finishes_a_half_done_save_first(
    config: ServiceConfig, tmp_path: Path
) -> None:
    """A project folder copied from elsewhere, mid-save, is finished when it is opened."""
    with TestClient(create_app(config), base_url=BASE_URL, headers=AUTH) as first:
        pid, where = project(first)
        old = first.get(f"/v1/projects/{pid}/model").json()
    new = {**old["model"], "meta": {**old["model"]["meta"], "name": "Copied mid-save"}}
    half_save(where, tmp_path, new, 3)
    other = dataclasses.replace(config, config_dir=tmp_path / "other-config")
    with TestClient(create_app(other), base_url=BASE_URL, headers=AUTH) as second:
        opened = second.post("/v1/projects/open", json={"path": str(where)})
        assert opened.status_code == 200, opened.text
        assert opened.json()["model_revision"] == old["revision"] + 1
        assert second.get(f"/v1/projects/{pid}/model").json()["model"] == new


def test_a_save_finished_by_a_replay_is_published_to_the_project_s_listeners(
    client: TestClient, events: list[tuple[str, int, str | None]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Third review of PR #182: a canvas open on the project hears of the save a replay
    finished, at the new revision; its writer is not known, so ``client`` is null."""
    pid, _where = project(client)
    real = os.replace

    def replace(source: Any, target: Any) -> None:
        if Path(target).name == PROJECT_FILE:
            raise PermissionError("denied")
        real(source, target)

    monkeypatch.setattr(os, "replace", replace)
    refused = client.post(
        f"/v1/projects/{pid}/model/edits",
        json={"edits": [{"edit": "set_label", "id": "exit", "label": "Door"}]},
    )
    monkeypatch.setattr(os, "replace", real)  # the events fixture stays patched
    coded_refusal(refused, "E186")
    events.clear()
    assert client.get(f"/v1/projects/{pid}/model").json()["revision"] == 2
    assert events == [(pid, 2, None)]


def test_a_project_whose_record_cannot_be_looked_at_is_refused_and_listed_unavailable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid, _where = project(client)
    real = Path.exists

    def exists(self: Path, *args: Any, **options: Any) -> bool:
        if self.name == RECORD:
            raise PermissionError("denied")
        return real(self, *args, **options)

    monkeypatch.setattr(Path, "exists", exists)
    refused = client.get(f"/v1/projects/{pid}/model")
    [listed] = [item for item in client.get("/v1/projects").json() if item["id"] == pid]
    monkeypatch.undo()
    coded_refusal(refused, "E186")
    assert listed["available"] is False


@pytest.mark.parametrize(
    "error",
    [PermissionError("denied"), ValueError("embedded null byte"), RuntimeError("loop")],
    ids=lambda e: type(e).__name__,
)
def test_a_project_whose_folder_cannot_be_looked_into_is_refused_and_listed_unavailable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    """Fourth review of PR #182: ``Path.resolve`` raised ``RuntimeError`` for a ``data``
    symlink loop (Python 3.11) and escaped the listing. Every filesystem error of a replay is
    now E186, and the listing still answers."""
    pid, where = project(client)
    real = Path.resolve

    def resolve(self: Path, *args: Any, **options: Any) -> Path:
        if self == where / "data":
            raise error
        return real(self, *args, **options)

    monkeypatch.setattr(Path, "resolve", resolve)
    refused = client.get(f"/v1/projects/{pid}/model")
    listing = client.get("/v1/projects")
    monkeypatch.setattr(Path, "resolve", real)
    coded_refusal(refused, "E186")
    assert listing.status_code == 200
    [listed] = [item for item in listing.json() if item["id"] == pid]
    assert listed["available"] is False


def test_a_data_folder_that_links_to_itself_never_escapes_as_an_exception(
    client: TestClient,
) -> None:
    """The real case: E186 where ``resolve`` refuses the loop (Python 3.11), the model where
    it does not (3.13); never an unexpected error."""
    import shutil

    pid, where = project(client)
    shutil.rmtree(where / "data")
    (where / "data").symlink_to("data")
    try:
        (where / "data").resolve()
        loops = False
    except RuntimeError:
        loops = True
    answer = client.get(f"/v1/projects/{pid}/model")
    listing = client.get("/v1/projects")
    assert listing.status_code == 200
    [listed] = [item for item in listing.json() if item["id"] == pid]
    if loops:
        coded_refusal(answer, "E186")
        assert listed["available"] is False
    else:
        assert answer.status_code == 200
        assert listed["available"] is True
