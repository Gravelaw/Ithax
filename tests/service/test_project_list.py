"""Recent projects (#97, Reviewer B finding 10): rename, remove from the list, last opened,
the lesson step and the template a project came from (spec 3 "Endpoints").

- ``PATCH /v1/projects/{pid}`` takes any of ``name`` (the project's name in
  ``project.json``), ``opened`` (``true``: opened now) and ``lesson_step`` (a whole number
  from 0, or ``null`` for none).
- ``POST /v1/projects/{pid}/remove`` takes the project off the list; its folder is kept, and
  ``POST /v1/projects/open`` registers it again.
- ``GET /v1/projects`` adds ``opened``, ``template`` and ``lesson_step`` to each project, each
  ``null`` until known. They are kept in the configuration folder, not in the project
  folder, whose ``project.json`` keeps its five fields.
"""

import dataclasses
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from ithax.service.app import create_app
from ithax.service.config import ServiceConfig
from ithax.service.projects_store import PROJECT_FILE, ProjectRegistry
from service.service_support import AUTH, BASE_URL, assert_error

ROOT = Path(__file__).resolve().parents[2]


def listed(client: TestClient) -> list[dict[str, object]]:
    response = client.get("/v1/projects")
    assert response.status_code == 200
    return response.json()  # type: ignore[no-any-return]


def make(client: TestClient, name: str = "Shop", **extra: object) -> dict[str, object]:
    response = client.post("/v1/projects", json={"name": name, **extra})
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def test_a_new_project_lists_the_added_fields_as_null(client: TestClient) -> None:
    made = make(client)
    assert made["opened"] is None
    assert made["template"] is None
    assert made["lesson_step"] is None
    [entry] = listed(client)
    assert (entry["opened"], entry["template"], entry["lesson_step"]) == (None, None, None)


def test_rename_changes_the_name_only(client: TestClient) -> None:
    made = make(client)
    folder = Path(str(made["path"]))
    response = client.patch(f"/v1/projects/{made['id']}", json={"name": "Corner café"})
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Corner café"
    record = json.loads((folder / PROJECT_FILE).read_text(encoding="utf-8"))
    assert record["name"] == "Corner café"
    assert record["model_revision"] == made["model_revision"]
    assert sorted(record) == ["created", "id", "layout_version", "model_revision", "name"]
    [entry] = listed(client)
    assert entry["name"] == "Corner café"
    assert entry["id"] == made["id"]
    assert entry["path"] == made["path"]


def test_opened_stamps_now_and_lesson_step_is_kept(client: TestClient) -> None:
    made = make(client)
    response = client.patch(f"/v1/projects/{made['id']}", json={"opened": True, "lesson_step": 2})
    assert response.status_code == 200, response.text
    [entry] = listed(client)
    assert isinstance(entry["opened"], str) and entry["opened"].endswith("Z")
    assert entry["lesson_step"] == 2
    client.patch(f"/v1/projects/{made['id']}", json={"lesson_step": None})
    assert listed(client)[0]["lesson_step"] is None


def test_a_project_from_a_template_lists_it(config: ServiceConfig) -> None:
    app = create_app(dataclasses.replace(config, templates_dir=ROOT / "templates"))
    with TestClient(app, base_url=BASE_URL, headers=AUTH) as templated:
        made = make(templated, "Coffee", template="coffee_shop")
        assert made["template"] == "coffee_shop"
        assert listed(templated)[0]["template"] == "coffee_shop"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": ""},
        {"name": 3},
        {"opened": False},
        {"opened": "yes"},
        {"lesson_step": -1},
        {"lesson_step": 1.5},
        {"lesson_step": True},
        {"colour": "red"},
    ],
)
def test_a_patch_that_cannot_be_used_is_400_with_e184(
    client: TestClient, body: dict[str, object]
) -> None:
    made = make(client)
    refused = client.patch(f"/v1/projects/{made['id']}", json=body)
    assert refused.status_code == 400
    assert_error(refused.json(), "E184")
    [entry] = listed(client)
    assert entry["name"] == "Shop" and entry["opened"] is None


def test_an_unknown_project_is_404_with_e185(client: TestClient) -> None:
    for refused in (
        client.patch("/v1/projects/nobody", json={"name": "x"}),
        client.post("/v1/projects/nobody/remove"),
    ):
        assert refused.status_code == 404
        assert_error(refused.json(), "E185")


def test_remove_takes_it_off_the_list_and_keeps_its_folder(client: TestClient) -> None:
    kept = make(client, "Kept")
    gone = make(client, "Gone")
    client.patch(f"/v1/projects/{gone['id']}", json={"opened": True, "lesson_step": 1})
    response = client.post(f"/v1/projects/{gone['id']}/remove")
    assert response.status_code == 200, response.text
    assert response.json() == {"id": gone["id"], "path": gone["path"]}
    assert [entry["id"] for entry in listed(client)] == [kept["id"]]
    folder = Path(str(gone["path"]))
    assert (folder / PROJECT_FILE).is_file()
    # Opened again from its folder, it is listed once more, with nothing left over.
    again = client.post("/v1/projects/open", json={"path": str(folder)}).json()
    assert again["id"] == gone["id"]
    assert (again["opened"], again["lesson_step"]) == (None, None)


def test_the_notes_survive_a_new_registry(client: TestClient, tmp_path: Path) -> None:
    made = make(client)
    client.patch(f"/v1/projects/{made['id']}", json={"opened": True})
    config = client.app.state.service.config  # type: ignore[attr-defined]
    fresh = ProjectRegistry(Path(config.config_dir), Path(config.data_dir))
    [entry] = fresh.entries()
    assert entry["opened"] is not None


def test_an_unreadable_notes_file_lists_nulls(client: TestClient) -> None:
    made = make(client)
    client.patch(f"/v1/projects/{made['id']}", json={"opened": True})
    config = client.app.state.service.config  # type: ignore[attr-defined]
    notes = [p for p in Path(config.config_dir).iterdir() if p.name.startswith("project-notes")]
    [path] = notes
    path.write_text("not json", encoding="utf-8")
    [entry] = listed(client)
    assert (entry["opened"], entry["lesson_step"]) == (None, None)


def test_a_data_delete_with_dot_segments_never_removes_the_project(client: TestClient) -> None:
    """``DELETE .../data/..`` folds to ``DELETE /v1/projects/{pid}``, which is no route, so the
    project stays listed (why removing is ``POST .../remove``)."""
    made = make(client)
    response = client.delete(f"/v1/projects/{made['id']}/data/..")
    assert response.status_code in (404, 405)
    assert [entry["id"] for entry in listed(client)] == [made["id"]]
