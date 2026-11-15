"""Saving several files as one change (``ithax.service.commit``; AKS-111, AKS-113)."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from ithax.service.commit import RECORD, CommitFailed, Planned, replace_in_order, replay


def test_files_are_saved_in_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []
    real = os.replace

    def replace(source: Any, target: Any) -> None:
        order.append(Path(target).name)
        real(source, target)

    monkeypatch.setattr(os, "replace", replace)
    replace_in_order([Planned(tmp_path / "a", b"1", None), Planned(tmp_path / "b", b"2", None)])
    # The commit record first (#71), then the files in order; the record is removed after.
    assert order == [RECORD, "a", "b"]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["a", "b"]


def test_a_temporary_file_that_cannot_be_written_saves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "a").write_bytes(b"old")
    real = Path.write_bytes

    def write_bytes(self: Path, data: Any) -> int:
        if self.name.startswith(".b."):
            raise PermissionError("denied")
        return real(self, data)

    monkeypatch.setattr(Path, "write_bytes", write_bytes)
    with pytest.raises(CommitFailed):
        replace_in_order(
            [Planned(tmp_path / "a", b"new", b"old"), Planned(tmp_path / "b", b"2", None)]
        )
    monkeypatch.undo()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["a"]
    assert (tmp_path / "a").read_bytes() == b"old"


def test_a_failed_commit_puts_every_earlier_file_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "a").write_bytes(b"old")
    real = os.replace

    def replace(source: Any, target: Any) -> None:
        if Path(target).name == "c":
            raise PermissionError("denied")
        real(source, target)

    monkeypatch.setattr(os, "replace", replace)
    with pytest.raises(CommitFailed):
        replace_in_order(
            [
                Planned(tmp_path / "a", b"new", b"old"),
                Planned(tmp_path / "b", b"2", None),
                Planned(tmp_path / "c", b"3", None),
            ]
        )
    monkeypatch.undo()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["a"]
    assert (tmp_path / "a").read_bytes() == b"old"


def test_a_failed_commit_leaves_no_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A rename that fails undoes the change, so nothing is left to finish (#71)."""
    real = os.replace

    def replace(source: Any, target: Any) -> None:
        if Path(target).name == "b":
            raise PermissionError("denied")
        real(source, target)

    monkeypatch.setattr(os, "replace", replace)
    with pytest.raises(CommitFailed):
        replace_in_order([Planned(tmp_path / "a", b"1", None), Planned(tmp_path / "b", b"2", None)])
    monkeypatch.undo()
    assert not (tmp_path / RECORD).exists()
    assert not replay(tmp_path)


# --- a process that ends during the commit (#71; docs/research/m14-atomic-save.md) -----------

#: A child that saves ``a`` then ``b`` and ends at once (no clean-up runs) at its step-th call
#: of ``os.replace``: 1 is the record's rename, 2 is ``a``'s, 3 is ``b``'s.
CHILD = """
import os, sys
from pathlib import Path
from ithax.service.commit import Planned, replace_in_order
folder, stop = Path(sys.argv[1]), int(sys.argv[2])
real, calls = os.replace, []
def replace(source, target):
    calls.append(target)
    if len(calls) == stop:
        os._exit(9)
    real(source, target)
os.replace = replace
replace_in_order(
    [Planned(folder / "a", b"new a", b"old a"), Planned(folder / "b", b"new b", b"old b")]
)
"""


def crash(folder: Path, stop: int) -> None:
    (folder / "a").write_bytes(b"old a")
    (folder / "b").write_bytes(b"old b")
    ended = subprocess.run(
        [sys.executable, "-c", CHILD, str(folder), str(stop)], check=False, timeout=60
    )
    assert ended.returncode == 9


def contents(folder: Path) -> tuple[bytes, bytes]:
    return (folder / "a").read_bytes(), (folder / "b").read_bytes()


def test_a_process_that_ends_between_the_renames_is_finished_on_replay(tmp_path: Path) -> None:
    """The gap of #71: the new ``a`` beside the old ``b``, until the record is replayed."""
    crash(tmp_path, 3)
    assert contents(tmp_path) == (b"new a", b"old b")
    assert (tmp_path / RECORD).exists()
    assert replay(tmp_path)
    assert contents(tmp_path) == (b"new a", b"new b")
    assert not (tmp_path / RECORD).exists()
    assert not replay(tmp_path)


def test_a_process_that_ends_before_the_first_rename_is_finished_on_replay(
    tmp_path: Path,
) -> None:
    crash(tmp_path, 2)
    assert contents(tmp_path) == (b"old a", b"old b")
    assert replay(tmp_path)
    assert contents(tmp_path) == (b"new a", b"new b")


def test_a_process_that_ends_before_the_record_keeps_the_old_files(tmp_path: Path) -> None:
    crash(tmp_path, 1)
    assert not (tmp_path / RECORD).exists()
    assert not replay(tmp_path)
    assert contents(tmp_path) == (b"old a", b"old b")


def test_a_record_that_cannot_be_read_is_left_and_changes_nothing(tmp_path: Path) -> None:
    (tmp_path / "a").write_bytes(b"old a")
    for text in ("not json", '{"renames": [["../x", "a"]]}', '{"renames": 3}'):
        (tmp_path / RECORD).write_text(text, encoding="utf-8")
        assert not replay(tmp_path)
        assert (tmp_path / RECORD).exists()
        assert (tmp_path / "a").read_bytes() == b"old a"


def test_files_of_one_commit_share_a_folder(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    with pytest.raises(ValueError, match="one folder"):
        replace_in_order(
            [Planned(tmp_path / "a", b"1", None), Planned(tmp_path / "sub" / "b", b"2", None)]
        )
