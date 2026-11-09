"""``GET /v1/ui/{path}``: the interface's own files (spec 3 "Endpoints"; AKS-119).

The service serves the built interface from its ``ui_dir``, without the token, so the
interface's origin is the service's own; a path that leaves the folder is refused as not
found, and the response's ``Content-Security-Policy`` lets the page reach only the service.
"""

import dataclasses
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from lcsim.service.app import create_app, table_path
from lcsim.service.config import ServiceConfig
from lcsim.service.interface_files import content_security_policy, interface_path, media_type
from service.service_support import AUTH, BASE_URL, PORT, assert_error

INDEX = "<!doctype html><title>lcsim</title>"


@pytest.fixture
def ui_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "dist"
    (folder / "assets").mkdir(parents=True)
    (folder / "sub").mkdir()
    (folder / "index.html").write_text(INDEX, encoding="utf-8")
    (folder / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (folder / "assets" / "app.css").write_text("body{}", encoding="utf-8")
    (folder / "assets" / "font.woff2").write_bytes(b"wOF2")
    (folder / "sub" / "index.html").write_text("sub", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    return folder


@pytest.fixture
def served(config: ServiceConfig, ui_dir: Path) -> Iterator[TestClient]:
    """A client without the token, as a browser loading the page is."""
    app = create_app(dataclasses.replace(config, ui_dir=ui_dir))
    with TestClient(app, base_url=BASE_URL) as client:
        yield client


@pytest.mark.parametrize("path", ["/v1/ui/", "/v1/ui/index.html"])
def test_the_folder_s_index_is_served_without_the_token(served: TestClient, path: str) -> None:
    response = served.get(path)
    assert response.status_code == 200
    assert response.text == INDEX
    assert response.headers["content-type"] == "text/html; charset=utf-8"


def test_a_folder_path_ending_in_a_slash_gives_its_index(served: TestClient) -> None:
    assert served.get("/v1/ui/sub/").text == "sub"


@pytest.mark.parametrize(
    ("path", "kind"),
    [
        ("assets/app.js", "text/javascript; charset=utf-8"),
        ("assets/app.css", "text/css; charset=utf-8"),
        ("assets/font.woff2", "font/woff2"),
    ],
)
def test_files_carry_their_media_type(served: TestClient, path: str, kind: str) -> None:
    response = served.get(f"/v1/ui/{path}")
    assert response.status_code == 200
    assert response.headers["content-type"] == kind


def test_every_file_carries_the_page_s_security_headers(served: TestClient) -> None:
    headers = served.get("/v1/ui/").headers
    assert headers["content-security-policy"] == content_security_policy(PORT)
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["cache-control"] == "no-cache"


def test_the_policy_lets_the_page_reach_only_the_service() -> None:
    policy = dict(part.strip().split(" ", 1) for part in content_security_policy(PORT).split(";"))
    assert policy["default-src"] == "'self'"
    assert policy["script-src"] == "'self'"
    assert policy["font-src"] == "'self'"
    assert policy["connect-src"] == f"'self' ws://127.0.0.1:{PORT} ws://localhost:{PORT}"
    assert policy["frame-ancestors"] == "'none'"
    assert "http" not in content_security_policy(PORT).replace("ws://", "")


def test_head_is_answered_as_get_without_a_body(served: TestClient) -> None:
    response = served.head("/v1/ui/index.html")
    assert response.status_code == 200
    assert response.content == b""
    assert response.headers["content-length"] == str(len(INDEX))


@pytest.mark.parametrize(
    "path",
    [
        "missing.js",
        "sub",
        "assets",
        "%2e%2e/secret.txt",
        "assets/%2e%2e/index.html",
        "assets//app.js",
        "%2Fetc%2Fpasswd",
        "assets%5Capp.js",
        "C:%5Cwindows",
        "c:index.html",
        "index.html%00",
    ],
)
def test_a_missing_file_or_a_path_that_leaves_the_folder_is_404(
    served: TestClient, path: str
) -> None:
    response = served.get(f"/v1/ui/{path}")
    assert response.status_code == 404
    assert_error(response.json(), "E185")


@pytest.mark.skipif(os.name == "nt", reason="symbolic links need privileges on Windows")
def test_a_link_that_leads_out_of_the_folder_is_404(served: TestClient, ui_dir: Path) -> None:
    (ui_dir / "out.txt").symlink_to(ui_dir.parent / "secret.txt")
    (ui_dir / "in.html").symlink_to(ui_dir / "index.html")
    assert served.get("/v1/ui/out.txt").status_code == 404
    assert served.get("/v1/ui/in.html").text == INDEX


def test_a_missing_folder_is_404(config: ServiceConfig, tmp_path: Path) -> None:
    app = create_app(dataclasses.replace(config, ui_dir=tmp_path / "nowhere"))
    with TestClient(app, base_url=BASE_URL) as client:
        response = client.get("/v1/ui/")
    assert response.status_code == 404
    assert_error(response.json(), "E185")


def test_a_service_without_an_interface_is_404(client: TestClient) -> None:
    response = client.get("/v1/ui/")
    assert response.status_code == 404
    assert_error(response.json(), "E185")
    assert "interface" in response.json()["error"]["message"]


def test_another_method_needs_the_token_and_is_405(app: FastAPI) -> None:
    with TestClient(app, base_url=BASE_URL) as client:
        assert client.post("/v1/ui/index.html").status_code == 401
        response = client.post("/v1/ui/index.html", headers=AUTH)
    assert response.status_code == 405
    assert_error(response.json(), "E185")


def test_interface_path_refuses_names_that_leave_the_folder(ui_dir: Path) -> None:
    assert interface_path(ui_dir, "") == (ui_dir / "index.html").resolve()
    assert interface_path(ui_dir, "assets/app.js") == (ui_dir / "assets" / "app.js").resolve()
    for refused in ["..", "../secret.txt", "a/./b", "/abs", "a\\b", "d:x", "a\tb", "x\x7f"]:
        assert interface_path(ui_dir, refused) is None, refused


def test_media_type_falls_back_to_bytes() -> None:
    assert media_type(Path("a.HTML")) == "text/html; charset=utf-8"
    assert media_type(Path("a.svg")) == "image/svg+xml"
    assert media_type(Path("a.unknown")) == "application/octet-stream"


def test_the_route_is_written_as_the_table_writes_it() -> None:
    assert table_path("/v1/ui/{path:path}") == "/v1/ui/{path}"
    assert table_path("/v1/projects/{pid}/model") == "/v1/projects/{pid}/model"
