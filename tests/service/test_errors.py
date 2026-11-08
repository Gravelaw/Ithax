"""Error bodies (spec 3 "Status codes and errors"; AKS-110 acceptance: error bodies are
``{"error": {"code", "message"}, "issues": [...]}``, 404 for an unknown project)."""

import logging
import re

import pytest
from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.testclient import TestClient

from lcsim.model.issues import Issue
from lcsim.service.app import create_app
from lcsim.service.config import ServiceConfig
from lcsim.service.errors import (
    INTERNAL,
    MALFORMED,
    NOT_FOUND,
    PROJECT_FOLDER,
    REFUSED,
    TOKEN,
    ServiceError,
    error_body,
    malformed,
    request_issues,
)
from service.service_support import AUTH, BASE_URL, assert_error

EXCEPTION_TEXT = re.compile(r"Traceback|Exception|Error\b|validation error|Input should")


def test_the_service_codes_are_spec_1s() -> None:
    assert (TOKEN, REFUSED, MALFORMED, NOT_FOUND, PROJECT_FOLDER, INTERNAL) == (
        "E182",
        "E183",
        "E184",
        "E185",
        "E186",
        "E187",
    )


def test_error_body_layout() -> None:
    issue = Issue(code="E184", component=None, path="/name", message="m", hint="h")
    assert error_body("E184", "Bad.", [issue]) == {
        "error": {"code": "E184", "message": "Bad."},
        "issues": [issue.as_dict()],
    }
    assert error_body("E185", "Gone.") == {
        "error": {"code": "E185", "message": "Gone."},
        "issues": [],
    }


def test_malformed_names_one_problem_or_counts_several() -> None:
    one = Issue(code="E184", component=None, path="/a", message="A is bad.", hint="h")
    two = Issue(code="E184", component=None, path="/b", message="B is bad.", hint="h")
    assert malformed([one]).message == "A is bad."
    assert malformed([one, two]).message.startswith("The request has 2 problems")
    assert malformed([one]).status == 400


@pytest.mark.parametrize(
    ("error", "path", "words"),
    [
        ({"type": "json_invalid", "loc": ("body", 3)}, "", "not valid JSON"),
        ({"type": "missing", "loc": ("body",)}, "", "no body"),
        ({"type": "model_attributes_type", "loc": ("body",)}, "", "not a JSON object"),
        ({"type": "missing", "loc": ("body", "name")}, "/name", "'name' is missing"),
        ({"type": "extra_forbidden", "loc": ("body", "x")}, "/x", "'x' is not one"),
        ({"type": "string_too_short", "loc": ("body", "name")}, "/name", "'name' is empty"),
        ({"type": "string_type", "loc": ("body", "path")}, "/path", "'path' must be text"),
        (
            {"type": "literal_error", "loc": ("body", "domain"), "ctx": {"expected": "'a'"}},
            "/domain",
            "one of 'a'",
        ),
        ({"type": "int_type", "loc": ("body", "edits", 0)}, "/edits/0", "'edits' has a value"),
        ({"type": "missing", "loc": ("query", "format")}, "/query/format", "'format' is missing"),
    ],
)
def test_request_errors_become_e184_issues_in_lcsims_words(
    error: dict[str, object], path: str, words: str
) -> None:
    [issue] = request_issues([error])
    assert issue.code == "E184"
    assert issue.path == path
    assert words in issue.message
    assert issue.hint
    assert not EXCEPTION_TEXT.search(issue.message + issue.hint)


def test_repeated_request_errors_are_reported_once() -> None:
    error = {"type": "missing", "loc": ("body", "name")}
    assert len(request_issues([error, error])) == 1


# --- through the app ----------------------------------------------------------------------


def app_with_test_routes(config: ServiceConfig) -> FastAPI:
    """The product app plus test-only routes: a project lookup, a failure and an
    unusual HTTP error."""
    app = create_app(config)

    @app.get("/v1/test/projects/{pid}")
    def lookup(pid: str) -> dict[str, str]:
        state = app.state.service
        return {"path": str(state.projects.folder(pid))}

    @app.get("/v1/test/fail")
    def fail() -> None:
        raise RuntimeError("secret internal detail")

    @app.get("/v1/test/teapot")
    def teapot() -> None:
        raise HTTPException(418)

    @app.get("/v1/test/unavailable")
    def unavailable() -> None:
        raise HTTPException(503)

    @app.get("/v1/test/state")
    def state_route() -> dict[str, str]:
        raise ServiceError(409, "E181", "The model changed.")

    return app


def test_an_unknown_project_is_404_with_e185(config: ServiceConfig) -> None:
    with TestClient(app_with_test_routes(config), base_url=BASE_URL, headers=AUTH) as client:
        response = client.get("/v1/test/projects/6c7f3b1e-0000-4000-8000-000000000000")
    assert response.status_code == 404
    assert_error(response.json(), "E185")
    assert "6c7f3b1e-0000-4000-8000-000000000000" in response.json()["error"]["message"]


def test_a_known_project_is_found(config: ServiceConfig) -> None:
    with TestClient(app_with_test_routes(config), base_url=BASE_URL, headers=AUTH) as client:
        created = client.post("/v1/projects", json={"name": "Shop"}).json()
        response = client.get(f"/v1/test/projects/{created['id']}")
    assert response.json() == {"path": created["path"]}


def test_an_unknown_path_is_404_with_e185(client: TestClient) -> None:
    response = client.get("/v1/nothing/here")
    assert response.status_code == 404
    assert_error(response.json(), "E185")
    assert "'/v1/nothing/here'" in response.json()["error"]["message"]


def test_a_method_a_path_does_not_take_is_405_with_e185(client: TestClient) -> None:
    response = client.delete("/v1/system")
    assert response.status_code == 405
    assert_error(response.json(), "E185")
    assert "DELETE" in response.json()["error"]["message"]


def test_an_unexpected_failure_is_500_with_e187_and_no_exception_text(
    config: ServiceConfig, caplog: pytest.LogCaptureFixture
) -> None:
    app = app_with_test_routes(config)
    with (
        caplog.at_level(logging.ERROR, logger="lcsim.service.errors"),
        TestClient(app, base_url=BASE_URL, headers=AUTH, raise_server_exceptions=False) as client,
    ):
        response = client.get("/v1/test/fail")
    assert response.status_code == 500
    assert_error(response.json(), "E187")
    assert "secret" not in response.text
    assert not EXCEPTION_TEXT.search(response.text)
    assert "secret internal detail" in caplog.text  # the details are in the log


def test_other_http_errors_get_the_error_body(config: ServiceConfig) -> None:
    with TestClient(app_with_test_routes(config), base_url=BASE_URL, headers=AUTH) as client:
        teapot = client.get("/v1/test/teapot")
        unavailable = client.get("/v1/test/unavailable")
    assert teapot.status_code == 418
    assert_error(teapot.json(), "E184")
    assert unavailable.status_code == 503
    assert_error(unavailable.json(), "E187")


def test_a_service_error_keeps_its_status_and_code(config: ServiceConfig) -> None:
    with TestClient(app_with_test_routes(config), base_url=BASE_URL, headers=AUTH) as client:
        response = client.get("/v1/test/state")
    assert response.status_code == 409
    assert response.json() == {
        "error": {"code": "E181", "message": "The model changed."},
        "issues": [],
    }


def test_invalid_json_is_400_with_e184(client: TestClient) -> None:
    response = client.post(
        "/v1/projects", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
    assert_error(response.json(), "E184")
    assert response.json()["issues"][0]["message"] == "The request body is not valid JSON."
