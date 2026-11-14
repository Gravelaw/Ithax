"""``manifest.json`` (spec 1 "Run folder and results"; AKS-103): fields, atomic writes and
at most one progress write a second."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

import lcsim
from lcsim.model.streams import generator_info
from lcsim.runs.manifest import (
    MANIFEST_FILE,
    MANIFEST_KEYS,
    ManifestWriter,
    new_manifest,
    read_manifest,
    utc_text,
    write_manifest,
)


def manifest() -> dict[str, object]:
    return new_manifest(
        run_id="20261106T180509-ABCDEF",
        project_id=None,
        experiment_id="base",
        scenario_ids=("default",),
        created=datetime(2026, 11, 6, 18, 5, 9, 123456, tzinfo=UTC),
        host="here",
        client="script",
        engine_name="simpy",
        engine_version="0.0.0",
        format_version="0.1",
        seed=12345,
    )


def test_utc_text_is_iso_8601_to_the_millisecond_with_z() -> None:
    assert utc_text(datetime(2026, 11, 6, 18, 5, 9, 123456, tzinfo=UTC)) == (
        "2026-11-06T18:05:09.123Z"
    )


def test_a_new_manifest_has_every_spec_1_field_in_order() -> None:
    data = manifest()
    assert list(data) == list(MANIFEST_KEYS)
    assert MANIFEST_KEYS == (
        "run_id",
        "project_id",
        "experiment_id",
        "scenario_ids",
        "state",
        "created",
        "started",
        "ended",
        "target",
        "host",
        "client",
        "engine",
        "generator",
        "product_version",
        "format_version",
        "seed",
        "fraction",
        "data_files",
    )
    info = generator_info()
    assert data == {
        "run_id": "20261106T180509-ABCDEF",
        "project_id": None,
        "experiment_id": "base",
        "scenario_ids": ["default"],
        "state": "queued",
        "created": "2026-11-06T18:05:09.123Z",
        "started": None,
        "ended": None,
        "target": "local",
        "host": "here",
        "client": "script",
        "engine": {"name": "simpy", "version": "0.0.0"},
        "generator": {"name": info.name, "numpy_version": info.numpy_version},
        "product_version": lcsim.__version__,
        "format_version": "0.1",
        "seed": 12345,
        "fraction": 0.0,
        "data_files": [],
    }


def test_writing_is_atomic_and_leaves_no_temporary_file(tmp_path: Path) -> None:
    write_manifest(tmp_path, manifest())
    assert sorted(path.name for path in tmp_path.iterdir()) == [MANIFEST_FILE]
    assert read_manifest(tmp_path) == manifest()
    text = (tmp_path / MANIFEST_FILE).read_text(encoding="utf-8")
    assert text.endswith("\n") and json.loads(text) == manifest()


def test_a_failed_write_keeps_the_old_manifest(tmp_path: Path) -> None:
    write_manifest(tmp_path, manifest())
    broken = manifest() | {"fraction": float("nan")}
    with pytest.raises(ValueError):
        write_manifest(tmp_path, broken)
    assert read_manifest(tmp_path) == manifest()
    assert sorted(path.name for path in tmp_path.iterdir()) == [MANIFEST_FILE]


def test_a_failed_rename_removes_the_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_manifest(tmp_path, manifest())

    def refuse(source: object, target: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("lcsim.files.os.replace", refuse)
    with pytest.raises(OSError, match="disk full"):
        write_manifest(tmp_path, manifest() | {"fraction": 0.5})
    assert sorted(path.name for path in tmp_path.iterdir()) == [MANIFEST_FILE]
    assert read_manifest(tmp_path)["fraction"] == 0.0


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_the_writer_writes_every_update_at_once(tmp_path: Path) -> None:
    clock = Clock()
    writer = ManifestWriter(tmp_path, manifest(), clock=clock)
    assert read_manifest(tmp_path)["state"] == "queued"
    writer.update(state="running", started="x")
    assert read_manifest(tmp_path)["state"] == "running"
    assert writer.data["started"] == "x"
    writer.data["state"] = "changed outside"  # a copy: the writer's own data is unchanged
    assert writer.data["state"] == "running"


def test_progress_is_written_at_most_once_a_second(tmp_path: Path) -> None:
    clock = Clock()
    writer = ManifestWriter(tmp_path, manifest(), clock=clock)
    assert writer.progress(0.1) is True  # the first progress report is written
    clock.now += 0.5
    assert writer.progress(0.2) is False
    assert writer.data["fraction"] == 0.2
    assert read_manifest(tmp_path)["fraction"] == 0.1
    clock.now += 0.5
    assert writer.progress(0.3) is True
    assert read_manifest(tmp_path)["fraction"] == 0.3
    clock.now += 0.2
    assert writer.progress(0.35) is False
    writer.update(state="running")  # a state change writes the latest fraction too
    assert read_manifest(tmp_path)["fraction"] == 0.35
    clock.now += 0.7
    assert writer.progress(0.4) is False  # 0.9 s since the last progress write
    clock.now += 0.1
    assert writer.progress(0.5) is True


def test_an_unknown_key_is_refused(tmp_path: Path) -> None:
    writer = ManifestWriter(tmp_path, manifest())
    with pytest.raises(KeyError, match="message"):
        writer.update(message="no such field")
    writer.update(error={"code": "E190"})
    assert read_manifest(tmp_path)["error"] == {"code": "E190"}
