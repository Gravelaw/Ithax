"""``GET /v1/projects``, ``POST /v1/projects`` and ``POST /v1/projects/open`` (spec 3
"Endpoints" and "Project folder"; AKS-110 acceptance: the default models validate with no
errors, ``domain`` on creation)."""

import json
import os
import re
import uuid
from pathlib import Path, PureWindowsPath

import pytest
from starlette.testclient import TestClient

from ithax.engines.registry import select_adapter
from ithax.model.loading import load_text
from ithax.model.migration import FORMAT_VERSION
from ithax.service.projects_store import (
    LAYOUT_VERSION,
    MODEL_FILE,
    PROJECT_FILE,
    PROJECTS_FILE,
    ProjectRecord,
    ProjectRegistry,
    default_model,
    read_project,
    utc_now,
)
from service.service_support import assert_error

ISO_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z")


def registry_file(client: TestClient) -> Path:
    return Path(client.app.state.service.config.config_dir) / PROJECTS_FILE  # type: ignore[attr-defined]


def validate(model_text: str) -> list[dict[str, str | None]]:
    """Every issue of a model: loading (schema and meaning passes), then the adapter's
    ``validate``, as ``POST .../validate`` will run them (spec 3)."""
    result = load_text(model_text)
    issues = [issue.as_dict() for issue in result.issues]
    if result.model is not None:
        selection = select_adapter(result.model.domain, result.model.run.engine)
        assert selection.adapter is not None
        issues += [issue.as_dict() for issue in selection.adapter.validate(result.model)]
    return issues


# --- creating ---------------------------------------------------------------------------


def test_a_new_project_holds_the_spec_3_folder(client: TestClient) -> None:
    response = client.post("/v1/projects", json={"name": "Coffee shop"})
    assert response.status_code == 200
    project = response.json()
    assert set(project) == {
        "id",
        "name",
        "created",
        "layout_version",
        "model_revision",
        "path",
        "available",
    }
    assert uuid.UUID(project["id"]).version == 4
    assert project["name"] == "Coffee shop"
    assert ISO_UTC.fullmatch(project["created"])
    assert project["layout_version"] == LAYOUT_VERSION == 1
    assert project["model_revision"] == 0
    assert project["available"] is True
    folder = Path(project["path"])
    data_dir = Path(client.app.state.service.config.data_dir)  # type: ignore[attr-defined]
    assert folder == data_dir / "projects" / project["id"]
    assert sorted(path.name for path in folder.iterdir()) == [
        "data",
        "model.json",
        "project.json",
        "runs",
    ]
    assert json.loads((folder / PROJECT_FILE).read_text(encoding="utf-8")) == {
        key: project[key] for key in ("id", "name", "created", "layout_version", "model_revision")
    }
    assert json.loads(registry_file(client).read_text(encoding="utf-8")) == {
        project["id"]: str(folder)
    }


def test_the_default_process_model_is_spec_3s_and_validates(client: TestClient) -> None:
    project = client.post("/v1/projects", json={"name": "Shop"}).json()
    text = (Path(project["path"]) / MODEL_FILE).read_text(encoding="utf-8")
    assert json.loads(text) == {
        "format_version": FORMAT_VERSION,
        "meta": {"name": "Shop"},
        "domain": "process",
        "parameters": {},
        "components": [],
        "connections": [],
        "experiments": [{"id": "base", "length": "8 h", "warmup": "0 s", "replications": 30}],
        "run": {"target": "local", "fidelity": "standard"},
    }
    assert validate(text) == []


def test_an_optimization_project_starts_empty_with_e179(client: TestClient) -> None:
    """D2 (#80): a new plan starts empty, and validation says what is missing."""
    response = client.post("/v1/projects", json={"name": "Plan", "domain": "optimization"})
    assert response.status_code == 200
    text = (Path(response.json()["path"]) / MODEL_FILE).read_text(encoding="utf-8")
    assert json.loads(text) == {
        "format_version": FORMAT_VERSION,
        "meta": {"name": "Plan"},
        "domain": "optimization",
        "variables": [],
        "objective": {"sense": "maximize", "linear": {}},
        "constraints": [],
        "run": {"target": "local", "fidelity": "standard"},
    }
    assert [(issue["code"], issue["path"]) for issue in validate(text)] == [("E179", "/variables")]


def test_domain_process_is_the_default(client: TestClient) -> None:
    explicit = client.post("/v1/projects", json={"name": "A", "domain": "process"}).json()
    model = json.loads((Path(explicit["path"]) / MODEL_FILE).read_text(encoding="utf-8"))
    assert model == default_model("A", "process")


def test_a_project_is_created_at_a_given_empty_or_missing_folder(
    client: TestClient, tmp_path: Path
) -> None:
    missing = tmp_path / "work" / "line"
    first = client.post("/v1/projects", json={"name": "Line", "path": str(missing)}).json()
    assert first["path"] == str(missing)
    assert (missing / PROJECT_FILE).is_file()
    empty = tmp_path / "empty"
    empty.mkdir()
    second = client.post("/v1/projects", json={"name": "Two", "path": str(empty)}).json()
    assert second["path"] == str(empty)
    listed = client.get("/v1/projects").json()
    assert [project["id"] for project in listed] == [first["id"], second["id"]]


def test_a_given_path_is_normalised(client: TestClient, tmp_path: Path) -> None:
    given = f"{tmp_path}/a/../b/"
    project = client.post("/v1/projects", json={"name": "B", "path": given}).json()
    assert project["path"] == str(tmp_path / "b")


def test_a_folder_that_is_not_empty_is_400_with_e186(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("mine", encoding="utf-8")
    response = client.post("/v1/projects", json={"name": "X", "path": str(tmp_path)})
    assert response.status_code == 400
    assert_error(response.json(), "E186")
    assert (tmp_path / "notes.txt").read_text(encoding="utf-8") == "mine"
    assert not (tmp_path / PROJECT_FILE).exists()


def test_a_file_in_the_way_is_400_with_e186(client: TestClient, tmp_path: Path) -> None:
    target = tmp_path / "file"
    target.write_text("", encoding="utf-8")
    response = client.post("/v1/projects", json={"name": "X", "path": str(target)})
    assert response.status_code == 400
    assert_error(response.json(), "E186")


def test_a_write_failure_is_400_with_e186(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "mkdir", refuse)
    response = client.post("/v1/projects", json={"name": "X", "path": str(tmp_path / "p")})
    assert response.status_code == 400
    assert_error(response.json(), "E186")
    assert "denied" not in response.text


def test_a_relative_path_is_400_with_e184(client: TestClient) -> None:
    response = client.post("/v1/projects", json={"name": "X", "path": "relative/folder"})
    assert response.status_code == 400
    assert_error(response.json(), "E184")
    assert response.json()["issues"][0]["path"] == "/path"


def test_a_template_is_404_with_e185_when_the_service_has_none(client: TestClient) -> None:
    """This client's service has no templates folder; projects from a template are
    tested in ``test_templates.py`` (AKS-122)."""
    response = client.post("/v1/projects", json={"name": "X", "template": "coffee_shop"})
    assert response.status_code == 404
    assert_error(response.json(), "E185")
    assert client.get("/v1/projects").json() == []


@pytest.mark.parametrize(
    ("body", "path"),
    [
        ({}, "/name"),
        ({"name": ""}, "/name"),
        ({"name": 5}, "/name"),
        ({"name": "X", "domain": "physics"}, "/domain"),
        ({"name": "X", "domain": None}, "/domain"),
        ({"name": "X", "colour": "red"}, "/colour"),
        ({"name": "X", "path": 3}, "/path"),
    ],
)
def test_a_malformed_body_is_400_with_e184(
    client: TestClient, body: dict[str, object], path: str
) -> None:
    response = client.post("/v1/projects", json=body)
    assert response.status_code == 400
    assert_error(response.json(), "E184")
    assert path in [issue["path"] for issue in response.json()["issues"]]
    assert client.get("/v1/projects").json() == []


# --- listing ----------------------------------------------------------------------------


def test_no_projects_at_first(client: TestClient) -> None:
    assert client.get("/v1/projects").json() == []


def test_a_project_whose_folder_is_gone_is_listed_unavailable(
    client: TestClient, tmp_path: Path
) -> None:
    folder = tmp_path / "gone"
    project = client.post("/v1/projects", json={"name": "Gone", "path": str(folder)}).json()
    (folder / PROJECT_FILE).unlink()
    assert client.get("/v1/projects").json() == [
        {
            "id": project["id"],
            "name": None,
            "created": None,
            "layout_version": None,
            "model_revision": None,
            "path": str(folder),
            "available": False,
        }
    ]


def test_a_folder_holding_another_project_is_listed_unavailable(
    client: TestClient, tmp_path: Path
) -> None:
    first = client.post("/v1/projects", json={"name": "A", "path": str(tmp_path / "a")}).json()
    second = client.post("/v1/projects", json={"name": "B", "path": str(tmp_path / "b")}).json()
    (tmp_path / "a" / PROJECT_FILE).write_text(
        (tmp_path / "b" / PROJECT_FILE).read_text(encoding="utf-8"), encoding="utf-8"
    )
    listed = {project["id"]: project for project in client.get("/v1/projects").json()}
    assert listed[first["id"]]["available"] is False
    assert listed[second["id"]]["available"] is True


@pytest.mark.parametrize("text", ["{broken", "[]", '{"id": 5}'])
def test_an_unreadable_registry_is_set_aside_not_lost(client: TestClient, text: str) -> None:
    path = registry_file(client)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    assert client.get("/v1/projects").json() == []
    aside = path.with_name(PROJECTS_FILE + ".unreadable")
    assert aside.read_text(encoding="utf-8") == text
    client.post("/v1/projects", json={"name": "New"})
    assert len(json.loads(path.read_text(encoding="utf-8"))) == 1


# --- opening ----------------------------------------------------------------------------


def test_opening_registers_an_existing_folder(client: TestClient, tmp_path: Path) -> None:
    folder = tmp_path / "shared"
    project = client.post("/v1/projects", json={"name": "Shared", "path": str(folder)}).json()
    registry_file(client).unlink()
    assert client.get("/v1/projects").json() == []
    response = client.post("/v1/projects/open", json={"path": str(folder)})
    assert response.status_code == 200
    assert response.json() == project
    assert client.get("/v1/projects").json() == [project]


def test_opening_a_registered_folder_again_changes_nothing(
    client: TestClient, tmp_path: Path
) -> None:
    folder = tmp_path / "p"
    project = client.post("/v1/projects", json={"name": "P", "path": str(folder)}).json()
    before = registry_file(client).read_text(encoding="utf-8")
    assert client.post("/v1/projects/open", json={"path": str(folder)}).json() == project
    assert registry_file(client).read_text(encoding="utf-8") == before


def test_a_moved_project_is_registered_at_its_new_folder(
    client: TestClient, tmp_path: Path
) -> None:
    old = tmp_path / "old"
    project = client.post("/v1/projects", json={"name": "P", "path": str(old)}).json()
    new = tmp_path / "new"
    old.rename(new)
    opened = client.post("/v1/projects/open", json={"path": str(new)}).json()
    assert opened == {**project, "path": str(new)}
    assert client.get("/v1/projects").json() == [opened]


def test_a_copied_project_is_400_with_e186(client: TestClient, tmp_path: Path) -> None:
    original = tmp_path / "original"
    client.post("/v1/projects", json={"name": "P", "path": str(original)})
    copy = tmp_path / "copy"
    copy.mkdir()
    (copy / PROJECT_FILE).write_text(
        (original / PROJECT_FILE).read_text(encoding="utf-8"), encoding="utf-8"
    )
    response = client.post("/v1/projects/open", json={"path": str(copy)})
    assert response.status_code == 400
    assert_error(response.json(), "E186")
    assert str(original) in response.json()["error"]["message"]


def test_opening_a_missing_folder_is_404_with_e185(client: TestClient, tmp_path: Path) -> None:
    response = client.post("/v1/projects/open", json={"path": str(tmp_path / "missing")})
    assert response.status_code == 404
    assert_error(response.json(), "E185")


@pytest.mark.parametrize(
    "content",
    [
        None,
        "not json",
        "[]",
        '{"id": "x", "name": "n", "created": "c", "layout_version": 1, "model_revision": 0}',
        '{"id": "6c7f3b1e-0000-4000-8000-000000000000", "name": "n", "created": "c"}',
        '{"id": "6c7f3b1e-0000-4000-8000-000000000000", "name": "n", "created": "c",'
        ' "layout_version": true, "model_revision": 0}',
        '{"id": "6c7f3b1e-0000-1000-8000-000000000000", "name": "n", "created": "c",'
        ' "layout_version": 1, "model_revision": 0}',
        '{"id": "6C7F3B1E-0000-4000-8000-000000000000", "name": "n", "created": "c",'
        ' "layout_version": 1, "model_revision": 0}',
    ],
    ids=["missing", "not-json", "array", "id-not-uuid", "fields-missing", "bool", "uuid1", "upper"],
)
def test_opening_a_folder_that_is_not_a_project_is_400_with_e186(
    client: TestClient, tmp_path: Path, content: str | None
) -> None:
    if content is not None:
        (tmp_path / PROJECT_FILE).write_text(content, encoding="utf-8")
    response = client.post("/v1/projects/open", json={"path": str(tmp_path)})
    assert response.status_code == 400
    assert_error(response.json(), "E186")


@pytest.mark.parametrize(("body", "code"), [({}, "E184"), ({"path": "rel"}, "E184")])
def test_opening_needs_an_absolute_path(
    client: TestClient, body: dict[str, object], code: str
) -> None:
    response = client.post("/v1/projects/open", json=body)
    assert response.status_code == 400
    assert_error(response.json(), code)


# --- the store on its own ---------------------------------------------------------------


def test_read_project_reads_the_five_fields(tmp_path: Path) -> None:
    record = ProjectRecord(str(uuid.uuid4()), "N", utc_now(), 1, 4)
    (tmp_path / PROJECT_FILE).write_text(json.dumps(record.__dict__), encoding="utf-8")
    assert read_project(tmp_path) == record


def test_the_registry_uses_the_id_it_is_given(tmp_path: Path) -> None:
    fixed = "0f1e2d3c-4b5a-4968-8776-655443322110"
    registry = ProjectRegistry(tmp_path / "config", tmp_path / "data", new_id=lambda: fixed)
    created = registry.create("N", "process", None)
    assert created["id"] == fixed
    assert registry.folder(fixed) == tmp_path / "data" / "projects" / fixed
    assert registry.entries() == [created]


def test_utc_now_is_iso_utc_to_the_millisecond() -> None:
    assert ISO_UTC.fullmatch(utc_now())


def test_a_relative_data_folder_still_registers_absolute_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review of PR #34: a project path stored relative to the working directory would
    be lost by a service started from another folder."""
    from ithax.service.app import create_app
    from ithax.service.config import ServiceConfig
    from ithax.service.hardware import Hardware
    from service.service_support import AUTH, BASE_URL, PORT, TOKEN

    monkeypatch.chdir(tmp_path)
    config = ServiceConfig(
        config_dir=Path("config"),
        data_dir=Path("data"),
        port=PORT,
        token=TOKEN,
        hardware=Hardware(4, None, None),
    )
    assert config.config_dir == tmp_path / "config"
    assert config.data_dir == tmp_path / "data"
    with TestClient(create_app(config), base_url=BASE_URL, headers=AUTH) as client:
        project = client.post("/v1/projects", json={"name": "Rel"}).json()
    assert project["path"] == str(tmp_path / "data" / "projects" / project["id"])
    stored = json.loads((tmp_path / "config" / PROJECTS_FILE).read_text(encoding="utf-8"))
    assert stored == {project["id"]: project["path"]}


def test_the_registry_makes_its_folders_absolute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    registry = ProjectRegistry(Path("c"), Path("d"))
    assert registry.config_dir == tmp_path / "c"
    assert registry.data_dir == tmp_path / "d"


# --- fully qualified paths (review of PR #34: Windows drive-relative paths) -------------


@pytest.mark.parametrize("path", [r"\projects\demo", r"C:projects\demo"])
def test_both_project_endpoints_refuse_a_windows_path_without_drive_or_share(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """``os.path.isabs`` on Windows takes ``\\projects\\demo`` as absolute although it has no
    drive, so it would be persisted and later name a folder on whichever drive is current."""
    monkeypatch.setattr("ithax.service.paths.PATH_FLAVOUR", PureWindowsPath)
    for route, body in (
        ("/v1/projects", {"name": "Demo", "path": path}),
        ("/v1/projects/open", {"path": path}),
    ):
        response = client.post(route, json=body)
        assert response.status_code == 400, route
        assert_error(response.json(), "E184")
        assert response.json()["issues"][0]["path"] == "/path"
    assert client.get("/v1/projects").json() == []


# --- canonical paths and aliases (review of PR #34, third path finding) ----------------


def _link(target: Path, alias: Path) -> Path:
    try:
        os.symlink(target, alias, target_is_directory=True)
    except (OSError, NotImplementedError):  # pragma: no cover - depends on the platform
        pytest.skip("this system cannot create symbolic links")
    return alias


def test_opening_a_registered_project_through_an_alias_is_the_same_project(
    client: TestClient, tmp_path: Path
) -> None:
    real = tmp_path / "real"
    project = client.post("/v1/projects", json={"name": "P", "path": str(real)}).json()
    before = registry_file(client).read_text(encoding="utf-8")
    alias = _link(real, tmp_path / "alias")
    response = client.post("/v1/projects/open", json={"path": str(alias)})
    assert response.status_code == 200, response.json()
    assert response.json() == project
    assert registry_file(client).read_text(encoding="utf-8") == before


def test_projects_json_stores_the_resolved_path(client: TestClient, tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    alias = _link(real, tmp_path / "alias")
    project = client.post("/v1/projects", json={"name": "P", "path": str(alias / "p")}).json()
    assert project["path"] == str(real / "p")
    stored = json.loads(registry_file(client).read_text(encoding="utf-8"))
    assert stored == {project["id"]: str(real / "p")}
    # Opening it unregistered through the alias also stores the resolved path.
    registry_file(client).unlink()
    opened = client.post("/v1/projects/open", json={"path": str(alias / "p")}).json()
    assert opened["path"] == str(real / "p")


def test_the_service_folders_are_resolved(tmp_path: Path) -> None:
    from ithax.service.config import ServiceConfig

    real = tmp_path / "real"
    real.mkdir()
    alias = _link(real, tmp_path / "alias")
    config = ServiceConfig(config_dir=alias / "c", data_dir=alias / "d", port=1, token="t")
    assert (config.config_dir, config.data_dir) == (real / "c", real / "d")
    registry = ProjectRegistry(alias / "c", alias / "d")
    assert (registry.config_dir, registry.data_dir) == (real / "c", real / "d")


def test_a_copy_reached_through_an_alias_is_still_400_with_e186(
    client: TestClient, tmp_path: Path
) -> None:
    original = tmp_path / "original"
    client.post("/v1/projects", json={"name": "P", "path": str(original)})
    copy = tmp_path / "copy"
    copy.mkdir()
    (copy / PROJECT_FILE).write_text(
        (original / PROJECT_FILE).read_text(encoding="utf-8"), encoding="utf-8"
    )
    alias = _link(copy, tmp_path / "alias")
    response = client.post("/v1/projects/open", json={"path": str(alias)})
    assert response.status_code == 400
    assert_error(response.json(), "E186")


POISONED_PROJECT_JSON = ['"name": 1e999', '"name": NaN', '"name": -Infinity', '"name": "\\ud800"']


@pytest.mark.parametrize("field", POISONED_PROJECT_JSON)
def test_a_project_json_that_cannot_be_written_back_is_unreadable(
    client: TestClient, field: str
) -> None:
    """Review of PR #36: one strict reader for every JSON file read from disk."""
    created = client.post("/v1/projects", json={"name": "Shop"}).json()
    folder = Path(created["path"])
    record = json.loads((folder / PROJECT_FILE).read_text())
    text = json.dumps(record).replace('"name": "Shop"', field)
    (folder / PROJECT_FILE).write_text(text)
    listed = client.get("/v1/projects")
    assert listed.status_code == 200
    assert listed.json()[0]["available"] is False
    response = client.get(f"/v1/projects/{created['id']}/model")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "E186"


@pytest.mark.parametrize("text", ['{"\\ud800": "/x"}', '{"a": "\\ud800"}'])
def test_a_registry_that_cannot_be_written_back_is_set_aside(client: TestClient, text: str) -> None:
    app = client.app
    path = app.state.service.projects.config_dir / PROJECTS_FILE  # type: ignore[attr-defined]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    assert client.get("/v1/projects").json() == []
    assert path.with_name(PROJECTS_FILE + ".unreadable").read_text() == text
    assert client.post("/v1/projects", json={"name": "Shop"}).status_code == 200


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("model_revision", 10**400),
        ("model_revision", -1),
        ("model_revision", 2**63),
        ("model_revision", 1.0),
        ("model_revision", True),
        ("model_revision", "1"),
        ("layout_version", 10**400),
        ("layout_version", 0),
        ("layout_version", -1),
        ("layout_version", 1.0),
        ("layout_version", False),
        ("layout_version", "1"),
    ],
)
def test_a_project_json_number_out_of_its_range_is_unreadable(
    client: TestClient, key: str, value: object
) -> None:
    """Review of PR #36: every number read from disk is typed and bounded."""
    created = client.post("/v1/projects", json={"name": "Shop"}).json()
    folder = Path(created["path"])
    record = json.loads((folder / PROJECT_FILE).read_text())
    record[key] = value
    (folder / PROJECT_FILE).write_text(json.dumps(record))
    assert read_project(folder) is None
    assert client.get("/v1/projects").json()[0]["available"] is False
    response = client.get(f"/v1/projects/{created['id']}/model")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "E186"


def test_a_write_that_would_pass_the_largest_revision_is_400_with_e186(
    client: TestClient,
) -> None:
    created = client.post("/v1/projects", json={"name": "Shop"}).json()
    folder = Path(created["path"])
    record = json.loads((folder / PROJECT_FILE).read_text())
    record["model_revision"] = 2**63 - 1
    (folder / PROJECT_FILE).write_text(json.dumps(record))
    before = (folder / PROJECT_FILE).read_bytes(), (folder / MODEL_FILE).read_bytes()
    model = client.get(f"/v1/projects/{created['id']}/model").json()["model"]
    response = client.put(f"/v1/projects/{created['id']}/model", content=json.dumps(model))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "E186"
    assert ((folder / PROJECT_FILE).read_bytes(), (folder / MODEL_FILE).read_bytes()) == before
