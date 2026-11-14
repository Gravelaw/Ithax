"""Saving several files as one change (``ithax.service.commit``; AKS-111, AKS-113)."""

import os
from pathlib import Path
from typing import Any

import pytest

from ithax.service.commit import CommitFailed, Planned, replace_in_order


def test_files_are_saved_in_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []
    real = os.replace

    def replace(source: Any, target: Any) -> None:
        order.append(Path(target).name)
        real(source, target)

    monkeypatch.setattr(os, "replace", replace)
    replace_in_order([Planned(tmp_path / "a", b"1", None), Planned(tmp_path / "b", b"2", None)])
    assert order == ["a", "b"]
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
