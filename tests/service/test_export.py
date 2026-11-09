"""``GET /v1/projects/{pid}/export`` (spec 3 "Endpoints", the export note; AKS-138), and the
run's ``engine`` as the run endpoints show it.

Runs use ``GatedAdapter`` (``run_adapters.py``), so a test decides which run has ended when
the export is made.
"""

import io
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from lcsim.runs.index import INDEX_FILE
from lcsim.runs.manifest import MANIFEST_FILE
from lcsim.service import export
from lcsim.service.run_service import _engine
from service.service_support import assert_error
from service.test_runs import (
    FINAL,
    client,
    folder_of,
    project,
    release,
    run_config,
    run_folder,
    shop,
    start,
    state_of,
    wait_state,
    waiting,
)

__all__ = ["client", "run_config"]  # fixtures used by name


def exported(client: TestClient, pid: str) -> zipfile.ZipFile:
    response = client.get(f"/v1/projects/{pid}/export")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["content-disposition"] == f'attachment; filename="{pid}.zip"'
    return zipfile.ZipFile(io.BytesIO(response.content))


def files_under(folder: Path) -> dict[str, bytes]:
    return {
        "/".join(path.relative_to(folder).parts): path.read_bytes()
        for path in folder.rglob("*")
        if path.is_file()
    }


def test_a_new_project_exports_its_files_byte_for_byte(client: TestClient) -> None:
    pid = project(client, shop())
    folder = folder_of(client, pid)
    with exported(client, pid) as zipped:
        names = zipped.namelist()
        assert sorted(names) == ["model.json", "project.json"]
        for name in names:
            assert zipped.read(name) == (folder / name).read_bytes()


def test_the_export_holds_data_and_ended_runs_but_no_index_and_no_unfinished_run(
    client: TestClient,
) -> None:
    pid = project(client, shop())
    folder = folder_of(client, pid)
    upload = client.post(
        f"/v1/projects/{pid}/data",
        files={"file": ("waits.csv", b"wait\n1\n2\n", "text/csv")},
    )
    assert upload.status_code == 200, upload.text
    ended = start(client, pid)
    waiting(client, ended)
    release(client, pid, ended)
    assert wait_state(client, ended, *FINAL)["state"] == "done"
    going = start(client, pid)
    waiting(client, going)
    # Files the index keeps beside it, a stray folder and a stray file under runs/.
    (folder / f"{INDEX_FILE}-journal").write_bytes(b"journal")
    (folder / f".{INDEX_FILE}.1.partial").write_bytes(b"partial")
    (folder / "runs" / "not-a-run").mkdir()
    (folder / "runs" / "not-a-run" / "x.txt").write_text("x")
    (folder / "runs" / "loose.txt").write_text("x")
    (folder / "notes.txt").write_text("kept")
    assert (folder / INDEX_FILE).is_file()
    try:
        with exported(client, pid) as zipped:
            names = set(zipped.namelist())
            expected = {
                name
                for name in files_under(folder)
                if name.split("/")[0] != "runs" or name.split("/")[1] == ended
            } - {INDEX_FILE, f"{INDEX_FILE}-journal", f".{INDEX_FILE}.1.partial"}
            assert names == expected
            assert "data/waits.csv" in names
            assert "data/index.json" in names
            assert f"runs/{ended}/{MANIFEST_FILE}" in names
            assert f"runs/{ended}/summary.json" in names
            assert "notes.txt" in names
            assert not any(name.startswith(f"runs/{going}") for name in names)
            for name in names:
                assert zipped.read(name) == (folder / name).read_bytes()
    finally:
        release(client, pid, going)
        wait_state(client, going, *FINAL)


def test_a_cancelled_run_is_exported(client: TestClient) -> None:
    pid = project(client, shop())
    rid = start(client, pid)
    waiting(client, rid)
    assert client.post(f"/v1/runs/{rid}/cancel").status_code == 200
    assert wait_state(client, rid, *FINAL)["state"] == "cancelled"
    with exported(client, pid) as zipped:
        assert f"runs/{rid}/{MANIFEST_FILE}" in zipped.namelist()


def _link(target: Path, link: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except OSError:  # pragma: no cover - Windows without the right to make links
        pytest.skip("symbolic links cannot be made here")


def test_links_are_never_followed_or_included(client: TestClient, tmp_path: Path) -> None:
    pid = project(client, shop())
    folder = folder_of(client, pid)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    _link(outside / "secret.txt", folder / "data" / "linked.txt")
    _link(outside, folder / "linked_folder")
    _link(folder / "model.json", folder / "inside_link.json")
    with exported(client, pid) as zipped:
        names = zipped.namelist()
    assert sorted(names) == ["model.json", "project.json"]


def test_a_path_whose_real_path_is_outside_is_left_out(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A Windows junction is not a symbolic link before Python 3.12; the real-path check
    # stands for it here by letting a symbolic link past the link check.
    pid = project(client, shop())
    folder = folder_of(client, pid)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    _link(outside, folder / "junction")
    monkeypatch.setattr(export, "_is_link", lambda path: False)
    with exported(client, pid) as zipped:
        assert sorted(zipped.namelist()) == ["model.json", "project.json"]


def test_a_junction_is_recognised_where_the_platform_has_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.setattr(os.path, "isjunction", lambda path: True, raising=False)
    assert export._is_link(plain)
    monkeypatch.delattr(os.path, "isjunction")
    assert not export._is_link(plain)


@pytest.mark.skipif(os.name == "nt", reason="file names are Unicode on Windows")
def test_a_name_that_is_not_valid_unicode_is_left_out(client: TestClient) -> None:
    pid = project(client, shop())
    folder = folder_of(client, pid)
    try:
        descriptor = os.open(os.fsencode(folder) + b"/bad\xff.txt", os.O_CREAT | os.O_WRONLY)
    except OSError:  # pragma: no cover - a file system that refuses such names (macOS)
        pytest.skip("the file system refuses names that are not UTF-8")
    os.close(descriptor)
    with exported(client, pid) as zipped:
        assert sorted(zipped.namelist()) == ["model.json", "project.json"]


def test_a_file_older_than_1980_is_exported(client: TestClient) -> None:
    pid = project(client, shop())
    folder = folder_of(client, pid)
    old = folder / "data" / "old.txt"
    old.write_text("old")
    os.utime(old, (0, 0))
    with exported(client, pid) as zipped:
        assert zipped.read("data/old.txt") == b"old"


def test_an_unknown_project_is_404_and_an_unreadable_one_400(client: TestClient) -> None:
    unknown = client.get("/v1/projects/00000000-0000-4000-8000-000000000000/export")
    assert unknown.status_code == 404
    assert_error(unknown.json(), "E185")
    pid = project(client, shop())
    (folder_of(client, pid) / "project.json").write_text("{")
    unreadable = client.get(f"/v1/projects/{pid}/export")
    assert unreadable.status_code == 400
    assert_error(unreadable.json(), "E186")


def test_the_zip_is_sent_in_parts_and_its_file_closed(tmp_path: Path) -> None:
    data = os.urandom(export.CHUNK * 2 + 5)
    archive = (tmp_path / "a.zip").open("w+b")
    archive.write(data)
    archive.seek(0)
    sent = list(export.parts(archive))
    assert [len(part) for part in sent] == [export.CHUNK, export.CHUNK, 5]
    assert b"".join(sent) == data
    assert archive.closed


def test_a_failure_while_writing_closes_the_temporary_file(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = project(client, shop())
    opened: list[Any] = []
    real = tempfile.TemporaryFile

    def recorded() -> Any:
        archive = real()
        opened.append(archive)
        return archive

    def failing(*_: object) -> Any:
        raise OSError("disk full")

    monkeypatch.setattr(tempfile, "TemporaryFile", recorded)
    monkeypatch.setattr(export, "_files", failing)
    with pytest.raises(OSError, match="disk full"):
        export.archive_project(state_of(client), pid)
    assert len(opened) == 1 and opened[0].closed


def test_the_export_holds_the_project_write_lock(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid = project(client, shop())
    state = state_of(client)
    held: list[bool] = []
    real_files = export._files

    def files(folder: Path, root: Path, ended: set[str]) -> Any:
        lock = state.models._lock_for(pid)
        held.append(lock._is_owned())  # type: ignore[attr-defined]
        return real_files(folder, root, ended)

    monkeypatch.setattr(export, "_files", files)
    with exported(client, pid):
        pass
    assert held and all(held)


def test_a_run_shows_the_engine_that_ran(client: TestClient) -> None:
    pid = project(client, shop())
    rid = start(client, pid)
    run = waiting(client, rid)
    assert run["engine"] == {"name": "gated", "version": "1.0.0"}
    manifest_path = run_folder(client, pid, rid) / MANIFEST_FILE
    release(client, pid, rid)
    wait_state(client, rid, *FINAL)
    manifest = json.loads(manifest_path.read_text())
    manifest["engine"] = "gated"
    manifest_path.write_text(json.dumps(manifest))
    assert client.get(f"/v1/runs/{rid}").json()["engine"] is None


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        ({"name": "simpy", "version": "0.0.0"}, {"name": "simpy", "version": "0.0.0"}),
        ({"name": "simpy", "version": None, "other": 1}, {"name": "simpy", "version": None}),
        ({"name": "simpy"}, {"name": "simpy", "version": None}),
        ({"name": 1, "version": "0"}, None),
        ({"name": "simpy", "version": 2}, None),
        (["simpy"], None),
        (None, None),
    ],
)
def test_the_engine_is_shown_only_in_its_declared_shape(value: object, shown: object) -> None:
    assert _engine(value) == shown
