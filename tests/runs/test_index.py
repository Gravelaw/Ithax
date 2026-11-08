"""``index.sqlite``, the run index of a project (spec 3 "Project folder"; spec 1 "Run folder
and results"; AKS-112): a cache of the run ids of ``runs/`` in the order the runs were
accepted, rebuilt from the run folders when it is missing or cannot be read."""

import sqlite3
import threading
from pathlib import Path

import pytest

from lcsim.runs.index import INDEX_FILE, RunIndex, readable_runs
from lcsim.runs.manifest import MANIFEST_FILE, read_run_manifest, write_manifest


def make_run(project: Path, rid: str, created: str, state: str = "done") -> Path:
    folder = project / "runs" / rid
    folder.mkdir(parents=True)
    write_manifest(
        folder,
        {
            "run_id": rid,
            "state": state,
            "created": created,
            "experiment_id": "base",
            "fraction": 0.0,
        },
    )
    return folder


A = "20261107T100000-AAAAAA"
B = "20261107T100000-BBBBBB"
C = "20261107T090000-CCCCCC"


def test_added_runs_are_listed_in_the_order_added(tmp_path: Path) -> None:
    index = RunIndex(tmp_path)
    index.sync()
    assert (tmp_path / INDEX_FILE).is_file()
    for rid in (B, A, C):
        make_run(tmp_path, rid, "2026-11-07T10:00:00.000Z")
        index.add(rid, "2026-11-07T10:00:00.000Z", "base")
    assert index.run_ids() == [B, A, C]
    assert index.contains(A)
    assert not index.contains("20261107T100000-ZZZZZZ")
    index.add(A, "2026-11-07T10:00:00.000Z", "base")  # a repeat changes nothing
    assert index.run_ids() == [B, A, C]


def test_a_missing_index_is_rebuilt_in_created_then_run_id_order(tmp_path: Path) -> None:
    make_run(tmp_path, B, "2026-11-07T10:00:00.000Z")
    make_run(tmp_path, A, "2026-11-07T10:00:00.000Z")
    make_run(tmp_path, C, "2026-11-07T09:00:00.000Z")
    index = RunIndex(tmp_path)
    assert index.run_ids() == [C, A, B]


@pytest.mark.parametrize("content", [b"garbage" * 200, b"", b"SQLite format 3\x00" + b"\x01" * 500])
def test_an_index_that_cannot_be_read_is_rebuilt(tmp_path: Path, content: bytes) -> None:
    make_run(tmp_path, A, "2026-11-07T10:00:00.000Z")
    (tmp_path / INDEX_FILE).write_bytes(content)
    index = RunIndex(tmp_path)
    assert index.run_ids() == [A]
    assert index.contains(A)
    index.add(B, "2026-11-07T11:00:00.000Z", None)
    assert index.run_ids() == [A, B]


def test_an_index_of_another_layout_is_rebuilt(tmp_path: Path) -> None:
    make_run(tmp_path, A, "2026-11-07T10:00:00.000Z")
    with sqlite3.connect(tmp_path / INDEX_FILE) as connection:
        connection.execute("CREATE TABLE other (x)")
    connection.close()
    assert RunIndex(tmp_path).run_ids() == [A]


def test_sync_adds_missing_runs_and_drops_runs_that_are_gone(tmp_path: Path) -> None:
    make_run(tmp_path, A, "2026-11-07T10:00:00.000Z")
    index = RunIndex(tmp_path)
    index.sync()
    make_run(tmp_path, C, "2026-11-07T09:00:00.000Z")
    index.add(B, "2026-11-07T11:00:00.000Z", None)  # its folder is gone
    index.sync()
    assert index.run_ids() == [A, C]


def test_folders_that_are_not_runs_are_left_out(tmp_path: Path) -> None:
    make_run(tmp_path, A, "2026-11-07T10:00:00.000Z")
    broken = tmp_path / "runs" / B
    broken.mkdir()
    (broken / MANIFEST_FILE).write_text("{")
    (tmp_path / "runs" / "notes.txt").write_text("x")
    (tmp_path / "runs" / "not-a-run").mkdir()
    make_run(tmp_path, "20261107T100000-DDDDDD", "2026-11-07T10:00:00.000Z", state="lost")
    assert [rid for rid, _ in readable_runs(tmp_path / "runs")] == [A]
    assert RunIndex(tmp_path).run_ids() == [A]


def test_readable_runs_of_a_project_without_runs_is_empty(tmp_path: Path) -> None:
    assert readable_runs(tmp_path / "runs") == []
    assert RunIndex(tmp_path).run_ids() == []


@pytest.mark.parametrize(
    "manifest",
    [
        [],
        {"run_id": A, "state": "done"},
        {"run_id": A, "state": 3, "created": "x"},
        {"run_id": B, "state": "done", "created": "x"},
        {"run_id": A, "state": "done", "created": 5},
    ],
)
def test_a_manifest_of_another_shape_is_not_a_run(tmp_path: Path, manifest: object) -> None:
    folder = tmp_path / A
    folder.mkdir()
    (folder / MANIFEST_FILE).write_text(__import__("json").dumps(manifest))
    assert read_run_manifest(folder) is None


def test_a_manifest_that_is_not_utf8_or_missing_is_not_a_run(tmp_path: Path) -> None:
    folder = tmp_path / A
    folder.mkdir()
    assert read_run_manifest(folder) is None
    (folder / MANIFEST_FILE).write_bytes(b"\xff\xfe")
    assert read_run_manifest(folder) is None


def test_concurrent_adds_are_all_kept(tmp_path: Path) -> None:
    index = RunIndex(tmp_path)
    index.sync()
    rids = [f"20261107T1000{n:02d}-AAAAAA" for n in range(20)]
    for rid in rids:
        make_run(tmp_path, rid, "2026-11-07T10:00:00.000Z")
    threads = [
        threading.Thread(target=index.add, args=(rid, "2026-11-07T10:00:00.000Z", None))
        for rid in rids
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(index.run_ids()) == rids


def test_a_row_that_is_not_a_run_id_is_left_out(tmp_path: Path) -> None:
    make_run(tmp_path, A, "2026-11-07T10:00:00.000Z")
    index = RunIndex(tmp_path)
    index.sync()
    with sqlite3.connect(tmp_path / INDEX_FILE) as connection:
        connection.execute(
            "INSERT INTO runs (run_id, created) VALUES ('../elsewhere', 'x'), (7, 'y')"
        )
    connection.close()
    assert index.run_ids() == [A]


def test_a_manifest_holding_nan_is_not_a_run(tmp_path: Path) -> None:
    folder = tmp_path / A
    folder.mkdir()
    (folder / MANIFEST_FILE).write_text(
        '{"run_id": "' + A + '", "state": "done", "created": "x", "fraction": NaN}'
    )
    assert read_run_manifest(folder) is None
