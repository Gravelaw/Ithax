"""``GET /v1/licences``: the Help screen's "Open source licences" (#89; owner decisions B4,
C7 and F4)."""

import platform
from dataclasses import replace
from email.message import Message
from importlib import metadata
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from ithax import __version__
from ithax.files import atomic_write
from ithax.service.app import create_app
from ithax.service.config import ServiceConfig, default_licences_file
from ithax.service.licences import (
    NOT_GIVEN,
    _requirements,
    authors,
    copyright_holder,
    normalise,
    runtime_distributions,
)
from ithax.strict_json import encode_json, read_json_object_file
from service.service_support import AUTH, BASE_URL

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "packaging" / "linux" / "licences.json"


def _get(config: ServiceConfig) -> dict[str, Any]:
    with TestClient(create_app(config), base_url=BASE_URL, headers=AUTH) as client:
        response = client.get("/v1/licences")
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def test_the_product_and_its_engines_are_listed(client: TestClient) -> None:
    body = client.get("/v1/licences").json()
    assert body["product"] == {
        "name": "Ithax",
        "licence": "AGPL-3.0-only",
        "source": "https://github.com/Gravelaw/Ithax",
        "version": __version__,
    }
    assert body["engines"] == [
        {
            "name": "highs",
            "version": metadata.version("highspy"),
            "licence": "MIT",
            "distribution": "highspy",
            "authors": "HiGHS developers",
        },
        {
            "name": "simpy",
            "version": metadata.version("simpy"),
            "licence": "MIT",
            "distribution": "simpy",
            "authors": authors(metadata.distribution("simpy")),
        },
    ]
    assert "Ontje" in body["engines"][1]["authors"]


def test_every_run_time_package_is_listed_with_the_recorded_licence(client: TestClient) -> None:
    body = client.get("/v1/licences").json()
    record = read_json_object_file(RECORD)["distributions"]
    recorded = {normalise(name): entry for name, entry in record.items()}
    rows = {normalise(row["name"]): row for row in body["packages"]}
    # Every run-time requirement is in the package's licence list, so none can be shipped
    # without its licence recorded (the Linux build checks the same of what it installs).
    needed = runtime_distributions([])
    assert set(needed) <= set(recorded)
    assert set(needed) <= set(rows)
    for key, row in rows.items():
        assert row["version"] == metadata.version(row["name"])
        assert row["licence"] == recorded[key]["licence"]
        assert row["authors"] and "@" not in row["authors"]
    assert rows["numpy"]["authors"] == "Travis E. Oliphant et al."
    assert rows["alembic"]["authors"] == "Mike Bayer"
    assert [row["name"].lower() for row in body["packages"]] == sorted(
        row["name"].lower() for row in body["packages"]
    )
    assert "ithax" not in rows


def test_the_python_is_listed_with_what_the_package_python_bundles(
    client: TestClient, config: ServiceConfig, tmp_path: Path
) -> None:
    python = client.get("/v1/licences").json()["python"]
    assert python["name"] == platform.python_implementation()
    assert python["version"] == platform.python_version()
    assert python["licence"] == "PSF-2.0"
    record = read_json_object_file(RECORD)
    record["python"]["version"] = platform.python_version()
    record["crates"] = [{"name": "tauri", "version": "2.11.1", "licence": "Apache-2.0 OR MIT"}]
    path = tmp_path / "licences.json"
    atomic_write(path, encode_json(record))
    body = _get(replace(config, licences_file=path))
    assert body["python"]["bundled"][0] == {
        "name": "OpenSSL",
        "version": "3.5.9",
        "licence": "Apache-2.0",
    }
    assert body["crates"] == record["crates"]


def test_a_list_that_cannot_be_read_leaves_the_licences_to_the_metadata(
    config: ServiceConfig, tmp_path: Path
) -> None:
    path = tmp_path / "licences.json"
    atomic_write(path, b"[1, ")
    body = _get(replace(config, licences_file=path))
    rows = {normalise(row["name"]): row for row in body["packages"]}
    assert (
        rows["numpy"]["licence"]
        == metadata.metadata("numpy").get_all("License-Expression", [None])[0]
    )
    # scipy's metadata has no License-Expression.
    assert rows["scipy"]["licence"] == NOT_GIVEN
    assert body["python"]["bundled"] == [] and body["crates"] == []
    assert body["python"]["licence"] == "PSF-2.0"


def test_the_list_is_the_checkout_s_or_else_the_installed_one(tmp_path: Path) -> None:
    assert default_licences_file() == RECORD
    share = tmp_path / "prefix" / "share" / "ithax"
    share.mkdir(parents=True)
    assert default_licences_file(tmp_path / "none", str(tmp_path / "prefix")) == (
        tmp_path / "none" / "packaging" / "linux" / "licences.json"
    )
    atomic_write(share / "licences.json", b"{}")
    assert default_licences_file(tmp_path / "none", str(tmp_path / "prefix")) == (
        share / "licences.json"
    )


class _File:
    """A file of a distribution's RECORD, at ``path`` on disk."""

    def __init__(self, record: str, path: Path) -> None:
        self.record, self.path = record, path
        self.name, self.suffix = Path(record).name, Path(record).suffix

    def __str__(self) -> str:
        return self.record

    def locate(self) -> Path:
        return self.path


class _Metadata:
    """A distribution with these metadata fields, these files and these requirements."""

    def __init__(
        self,
        fields: dict[str, str],
        files: list[_File] | None = None,
        requires: list[str] | None = None,
    ) -> None:
        self.metadata = Message()
        for key, value in fields.items():
            self.metadata[key] = value
        self.files = files or []
        self.requires = requires


def test_authors_are_names_without_addresses() -> None:
    def named(**fields: str) -> str:
        data = {key.replace("_", "-"): value for key, value in fields.items()}
        return authors(_Metadata(data))  # type: ignore[arg-type]

    assert named(Author="Kirill Simonov", Author_email="xi@resolvent.net") == "Kirill Simonov"
    assert named(Author_email='"Hernan E. Grecco" <h@g.com>, Ann <a@b.c>') == (
        "Hernan E. Grecco, Ann"
    )
    assert named(Author_email="only@mail.org", Maintainer_email="Pallets <c@p.com>") == "Pallets"
    assert named(Author_email="only@mail.org") == NOT_GIVEN
    assert named() == NOT_GIVEN


def test_a_pointer_to_a_file_gives_way_to_the_licence_s_holder() -> None:
    # et-xmlfile's metadata says "See AUTHORS.txt"; its own licence (LICENCE.rst) names
    # openpyxl, and the Python licence it also ships names the PSF, which is not its author.
    assert metadata.metadata("et-xmlfile")["Author"].startswith("See ")
    assert authors(metadata.distribution("et-xmlfile")) == "openpyxl"


def test_the_copyright_holder_of_a_licence_text() -> None:
    assert copyright_holder("MIT\n\nCopyright (c) 2010 openpyxl\n") == "openpyxl"
    assert copyright_holder("Copyright (c) 2017, Baidu Inc.") == "Baidu Inc."
    assert copyright_holder("Copyright (c) Meta Platforms, Inc.") == "Meta Platforms, Inc."
    template = "   Copyright [yyyy] [name of copyright owner]\nCopyright 2017 The ASF"
    assert copyright_holder(template) == "The ASF"
    assert copyright_holder("      copyright license to reproduce") is None
    assert copyright_holder("Copyright notice of the work") is None


def test_a_licence_file_that_cannot_be_read_or_names_no_holder_is_passed_over(
    tmp_path: Path,
) -> None:
    (tmp_path / "NOTICE").write_text("Some notice without a holder.\n", "utf-8")
    (tmp_path / "LICENSE.md").write_text("Copyright (c) 2024 The Holders\n", "utf-8")
    files = [
        _File("x-1.dist-info/LICENSE", tmp_path / "missing"),
        _File("x-1.dist-info/NOTICE", tmp_path / "NOTICE"),
        _File("x-1.dist-info/LICENSE.md", tmp_path / "LICENSE.md"),
        _File("x/LICENSE", tmp_path / "LICENSE.md"),
    ]
    found = authors(_Metadata({"Author": "See AUTHORS"}, files))  # type: ignore[arg-type]
    assert found == "The Holders"
    assert authors(_Metadata({"Author": "See AUTHORS"}, files[:2])) == "See AUTHORS"  # type: ignore[arg-type]


def test_requirements_follow_markers_and_skip_lines_that_cannot_be_read() -> None:
    requires = ["numpy>=2", "pytest; extra == 'dev'", "not a requirement !!", "simpy"]
    assert list(_requirements(_Metadata({}, requires=requires))) == ["numpy", "simpy"]  # type: ignore[arg-type]
    assert list(_requirements(_Metadata({}))) == []  # type: ignore[arg-type]
