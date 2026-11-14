"""``GET /v1/templates``, ``GET /v1/templates/{tid}`` and ``POST /v1/projects`` with
``template`` (spec 3 "Endpoints" notes; spec 4 "Template package"; AKS-122)."""

import dataclasses
import json
import logging
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from ithax.model.loading import load_text
from ithax.service.app import create_app
from ithax.service.config import ServiceConfig, default_templates_dir
from service.service_support import AUTH, BASE_URL, assert_error

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "templates"


def template_client(config: ServiceConfig, folder: Path) -> TestClient:
    app = create_app(dataclasses.replace(config, templates_dir=folder))
    return TestClient(app, base_url=BASE_URL, headers=AUTH)


@pytest.fixture
def templated(config: ServiceConfig) -> Iterator[TestClient]:
    """A service serving the repository's ``templates/``."""
    with template_client(config, TEMPLATES) as test_client:
        yield test_client


def read(name: str, tid: str = "coffee_shop") -> Any:
    return json.loads((TEMPLATES / tid / name).read_text(encoding="utf-8"))


def test_the_default_templates_folder_is_templates_of_the_checkout() -> None:
    assert default_templates_dir() == ROOT / "templates"


def test_without_a_templates_folder_there_are_no_templates(client: TestClient) -> None:
    response = client.get("/v1/templates")
    assert response.status_code == 200
    assert response.json() == []
    missing = client.get("/v1/templates/coffee_shop")
    assert missing.status_code == 404
    assert_error(missing.json(), "E185")
    assert "'coffee_shop'" in missing.json()["error"]["message"]


def test_the_templates_are_listed_in_id_order(templated: TestClient) -> None:
    response = templated.get("/v1/templates")
    assert response.status_code == 200
    listed = response.json()
    ids = [item["id"] for item in listed]
    assert ids == sorted(ids)
    assert {
        "clinic_patient_flow",
        "coffee_shop",
        "how_many_machines",
        "inventory_reorder_point",
        "machine_breakdowns",
        "product_mix",
        "staff_rota",
        "three_machine_line",
        "transport_plan",
        "warehouse_pick_pack",
    } == set(ids)
    assert listed[ids.index("coffee_shop")] == read("template.json")


def test_one_template_is_its_template_lesson_and_expected_values(templated: TestClient) -> None:
    response = templated.get("/v1/templates/three_machine_line")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"template", "lesson", "expected"}
    assert body["template"] == read("template.json", "three_machine_line")
    lesson = (TEMPLATES / "three_machine_line" / "lesson.md").read_text(encoding="utf-8")
    assert body["lesson"] == lesson
    assert body["expected"] == read("expected.json", "three_machine_line")


@pytest.mark.parametrize("tid", ["nothing", "..", "Coffee_Shop", "coffee shop"])
def test_an_unknown_template_is_404_with_e185(templated: TestClient, tid: str) -> None:
    response = templated.get(f"/v1/templates/{tid}")
    assert response.status_code == 404
    assert_error(response.json(), "E185")
    assert response.json()["issues"] == []


def broken_folder(tmp_path: Path) -> Path:
    """A templates folder with the coffee shop and a copy of it whose lesson is broken."""
    root = tmp_path / "templates"
    shutil.copytree(TEMPLATES / "coffee_shop", root / "coffee_shop")
    shutil.copytree(TEMPLATES / "coffee_shop", root / "broken")
    template = read("template.json")
    (root / "broken" / "template.json").write_text(
        json.dumps({**template, "id": "broken"}), encoding="utf-8"
    )
    (root / "broken" / "lesson.md").write_text("no title", encoding="utf-8")
    (root / ".hidden").mkdir()
    return root


def test_a_package_whose_json_is_null_is_left_out_not_a_500(
    config: ServiceConfig, tmp_path: Path
) -> None:
    """Review of PR #50: ``null`` in ``expected.json`` or ``template.json`` is an E195
    issue, so the gallery leaves the package out and the others are still served."""
    root = tmp_path / "templates"
    shutil.copytree(TEMPLATES / "coffee_shop", root / "coffee_shop")
    for tid, name in (("null_rows", "expected.json"), ("null_template", "template.json")):
        shutil.copytree(TEMPLATES / "coffee_shop", root / tid)
        template = {**read("template.json"), "id": tid}
        (root / tid / "template.json").write_text(json.dumps(template), encoding="utf-8")
        (root / tid / name).write_text("null", encoding="utf-8")
    with template_client(config, root) as test_client:
        listed = test_client.get("/v1/templates")
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == ["coffee_shop"]
        for tid, name in (("null_rows", "expected.json"), ("null_template", "template.json")):
            response = test_client.get(f"/v1/templates/{tid}")
            assert response.status_code == 404
            assert_error(response.json(), "E185")
            assert ("E195", f"/{name}") in [
                (issue["code"], issue["path"]) for issue in response.json()["issues"]
            ]
            created = test_client.post("/v1/projects", json={"name": "X", "template": tid})
            assert created.status_code == 404


def test_a_package_with_issues_is_not_served_and_its_issues_are_logged(
    config: ServiceConfig, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, logger="ithax.service.templates")
    with template_client(config, broken_folder(tmp_path)) as test_client:
        assert [item["id"] for item in test_client.get("/v1/templates").json()] == ["coffee_shop"]
        response = test_client.get("/v1/templates/broken")
    assert response.status_code == 404
    assert_error(response.json(), "E185")
    assert {issue["code"] for issue in response.json()["issues"]} == {"E195"}
    assert response.json()["issues"][0]["path"].startswith("/lesson.md")
    assert "The template 'broken' cannot be served" in caplog.text


# --- POST /v1/projects with template ----------------------------------------------------


def test_a_project_from_a_template_holds_its_model_named_after_the_project(
    templated: TestClient,
) -> None:
    response = templated.post("/v1/projects", json={"name": "My cafe", "template": "coffee_shop"})
    assert response.status_code == 200
    project = response.json()
    assert project["name"] == "My cafe"
    assert project["model_revision"] == 0
    model = templated.get(f"/v1/projects/{project['id']}/model").json()["model"]
    expected = read("model.json")
    expected["meta"] = {**expected["meta"], "name": "My cafe", "template": "coffee_shop"}
    assert model == expected
    folder = Path(project["path"])
    assert sorted(path.name for path in folder.iterdir()) == [
        "data",
        "model.json",
        "project.json",
        "runs",
    ]
    loaded = load_text((folder / "model.json").read_bytes())
    assert loaded.issues == ()
    assert loaded.model is not None
    assert loaded.model.meta.template == "coffee_shop"
    validated = templated.post(f"/v1/projects/{project['id']}/validate").json()
    assert validated["issues"] == []


def test_a_project_from_a_template_may_name_its_domain(templated: TestClient) -> None:
    body = {"name": "Line", "template": "three_machine_line", "domain": "process"}
    response = templated.post("/v1/projects", json=body)
    assert response.status_code == 200


def test_a_domain_that_differs_from_the_template_s_is_400_with_e184(
    templated: TestClient,
) -> None:
    body = {"name": "X", "template": "coffee_shop", "domain": "optimization"}
    response = templated.post("/v1/projects", json=body)
    assert response.status_code == 400
    assert_error(response.json(), "E184")
    assert response.json()["issues"][0]["path"] == "/domain"
    assert templated.get("/v1/projects").json() == []


@pytest.mark.parametrize("tid", ["nothing", "../../etc", ""])
def test_a_project_from_an_unknown_template_is_404_with_e185(
    templated: TestClient, tid: str
) -> None:
    response = templated.post("/v1/projects", json={"name": "X", "template": tid})
    assert response.status_code == 404
    assert_error(response.json(), "E185")
    assert templated.get("/v1/projects").json() == []


def test_a_project_from_a_template_with_issues_is_404_with_its_issues(
    config: ServiceConfig, tmp_path: Path
) -> None:
    with template_client(config, broken_folder(tmp_path)) as test_client:
        response = test_client.post("/v1/projects", json={"name": "X", "template": "broken"})
        assert response.status_code == 404
        assert_error(response.json(), "E185")
        assert response.json()["issues"]
        assert test_client.get("/v1/projects").json() == []
