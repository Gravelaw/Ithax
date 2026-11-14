"""``ithax.files``: the one way the product replaces a file (#99, P5)."""

import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest

from ithax import files
from ithax.files import atomic_write, atomic_write_with, temporary_path, write_synced


@pytest.fixture
def umask_077() -> Iterator[None]:
    previous = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(previous)


def test_a_new_file_is_written_and_nothing_else_is_left(tmp_path: Path) -> None:
    target = tmp_path / "a.json"
    atomic_write(target, b"{}\n")
    assert target.read_bytes() == b"{}\n"
    assert [path.name for path in tmp_path.iterdir()] == ["a.json"]


def test_an_existing_file_is_replaced(tmp_path: Path) -> None:
    target = tmp_path / "a.json"
    target.write_bytes(b"old")
    atomic_write(target, b"new")
    assert target.read_bytes() == b"new"


def test_the_temporary_is_beside_the_target_and_named_for_process_and_thread(
    tmp_path: Path,
) -> None:
    temporary = temporary_path(tmp_path / "a.json")
    assert temporary.parent == tmp_path
    assert temporary.name.startswith(f".a.json.{os.getpid()}.")
    assert temporary.name.endswith(".tmp")


def test_a_leftover_temporary_is_replaced(tmp_path: Path) -> None:
    target = tmp_path / "a.json"
    temporary_path(target).write_bytes(b"left over")
    atomic_write(target, b"new")
    assert target.read_bytes() == b"new"
    assert [path.name for path in tmp_path.iterdir()] == ["a.json"]


def test_a_mode_is_given_exactly_whatever_the_umask(tmp_path: Path, umask_077: None) -> None:
    target = tmp_path / "a.json"
    atomic_write(target, b"x", mode=0o640)
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


def test_without_a_mode_the_umask_applies(tmp_path: Path, umask_077: None) -> None:
    target = tmp_path / "a.json"
    atomic_write(target, b"x")
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_a_failing_writer_leaves_the_old_file_and_no_temporary(tmp_path: Path) -> None:
    target = tmp_path / "a.json"
    target.write_bytes(b"old")

    def writer(temporary: Path) -> None:
        temporary.write_bytes(b"half")
        raise RuntimeError("stopped")

    with pytest.raises(RuntimeError, match="stopped"):
        atomic_write_with(target, writer)
    assert target.read_bytes() == b"old"
    assert [path.name for path in tmp_path.iterdir()] == ["a.json"]


def test_a_failing_rename_removes_the_temporary(tmp_path: Path) -> None:
    target = tmp_path / "a.json"
    target.mkdir()
    with pytest.raises(OSError):
        atomic_write(target, b"x")
    assert [path.name for path in tmp_path.iterdir()] == ["a.json"]
    assert target.is_dir()


def test_the_file_and_its_folder_are_flushed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    synced: list[Path] = []
    monkeypatch.setattr(files, "_sync", synced.append)
    target = tmp_path / "a.json"
    atomic_write(target, b"x")
    assert synced == [temporary_path(target), tmp_path]


def test_a_folder_that_cannot_be_opened_is_not_flushed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = files._sync

    def sync(path: Path) -> None:
        if path == tmp_path:
            raise PermissionError("a folder cannot be opened here (Windows)")
        real(path)

    monkeypatch.setattr(files, "_sync", sync)
    atomic_write(tmp_path / "a.json", b"x")
    assert (tmp_path / "a.json").read_bytes() == b"x"


def test_write_synced_writes_and_flushes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    synced: list[Path] = []
    monkeypatch.setattr(files, "_sync", synced.append)
    target = tmp_path / "a.tmp"
    write_synced(target, b"x")
    assert target.read_bytes() == b"x"
    assert synced == [target]
