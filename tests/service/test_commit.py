"""Saving several files as one change (``ithax.service.commit``; AKS-111, AKS-113, #71).

The change is redo only: once the commit record is written it only goes forward, and
``replay`` finishes it (``docs/research/m14-atomic-save.md``).
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from ithax.service import commit
from ithax.service.commit import RECORD, CommitFailed, Planned, replace_in_order, replay

OLD = (b"old a", b"old b")
NEW = (b"new a", b"new b")


def two(folder: Path) -> list[Planned]:
    return [Planned(folder / "a", NEW[0]), Planned(folder / "b", NEW[1])]


def old_files(folder: Path) -> None:
    (folder / "a").write_bytes(OLD[0])
    (folder / "b").write_bytes(OLD[1])


def contents(folder: Path) -> tuple[bytes, bytes]:
    return (folder / "a").read_bytes(), (folder / "b").read_bytes()


def names(folder: Path) -> list[str]:
    return sorted(path.name for path in folder.iterdir())


def test_files_are_saved_in_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []
    real = os.replace

    def replace(source: Any, target: Any) -> None:
        order.append(Path(target).name)
        real(source, target)

    monkeypatch.setattr(os, "replace", replace)
    replace_in_order(two(tmp_path))
    # The commit record first (#71), then the files in order; the record is removed after.
    assert order == [RECORD, "a", "b"]
    assert names(tmp_path) == ["a", "b"]
    assert contents(tmp_path) == NEW


def test_a_temporary_file_that_cannot_be_written_saves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_files(tmp_path)
    real = Path.write_bytes

    def write_bytes(self: Path, data: Any) -> int:
        if self.name.startswith(".b."):
            raise PermissionError("denied")
        return real(self, data)

    monkeypatch.setattr(Path, "write_bytes", write_bytes)
    with pytest.raises(CommitFailed) as failed:
        replace_in_order(two(tmp_path))
    monkeypatch.undo()
    assert failed.value.pending is False
    assert names(tmp_path) == ["a", "b"]
    assert contents(tmp_path) == OLD


def test_a_record_that_cannot_be_written_saves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_files(tmp_path)
    real = os.replace

    def replace(source: Any, target: Any) -> None:
        if Path(target).name == RECORD:
            raise PermissionError("denied")
        real(source, target)

    monkeypatch.setattr(os, "replace", replace)
    with pytest.raises(CommitFailed) as failed:
        replace_in_order(two(tmp_path))
    monkeypatch.undo()
    assert failed.value.pending is False
    assert names(tmp_path) == ["a", "b"]
    assert contents(tmp_path) == OLD


@pytest.mark.parametrize("failing", ["a", "b"])
def test_a_rename_that_fails_leaves_the_change_recorded_for_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failing: str
) -> None:
    """Redo only (review of PR #182): nothing is put back, so no stop part-way through a
    roll-back can pair an old file with a new one; the next replay finishes the change."""
    old_files(tmp_path)
    real = os.replace

    def replace(source: Any, target: Any) -> None:
        if Path(target).name == failing:
            raise PermissionError("denied")
        real(source, target)

    monkeypatch.setattr(os, "replace", replace)
    with pytest.raises(CommitFailed) as failed:
        replace_in_order(two(tmp_path))
    assert failed.value.pending is True
    assert (tmp_path / RECORD).exists()
    with pytest.raises(CommitFailed):  # still cannot be written: the folder stays refused
        replay(tmp_path)
    monkeypatch.undo()
    assert replay(tmp_path)
    assert names(tmp_path) == ["a", "b"]
    assert contents(tmp_path) == NEW


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        '{"renames": 3}',
        '{"renames": []}',
        '{"renames": [["a"]]}',
        '{"renames": [["../x", "a"]]}',
        '{"renames": [["x", "sub/a"]]}',
        '{"renames": [["x", "a\\\\b"]]}',
        '{"renames": [["x", "bad\\u0000name"]]}',
        '{"renames": [["x", ".."]]}',
        '{"renames": [["x", ""]]}',
    ],
    ids=[
        "text",
        "number",
        "empty",
        "single",
        "parent",
        "slash",
        "backslash",
        "nul",
        "dotdot",
        "blank",
    ],
)
def test_a_record_that_cannot_be_read_refuses_the_folder_and_changes_nothing(
    tmp_path: Path, text: str
) -> None:
    """Review of PR #182: a NUL in a name raised ValueError past ``except OSError``; every
    such record now refuses, as a coded refusal can say, and nothing is renamed."""
    (tmp_path / "a").write_bytes(OLD[0])
    (tmp_path / "x").write_bytes(b"x")
    (tmp_path / RECORD).write_text(text, encoding="utf-8")
    with pytest.raises(CommitFailed) as failed:
        replay(tmp_path)
    assert failed.value.pending is True
    assert (tmp_path / RECORD).exists()
    assert (tmp_path / "a").read_bytes() == OLD[0]
    assert (tmp_path / "x").read_bytes() == b"x"


def test_files_of_one_commit_share_a_folder(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    with pytest.raises(ValueError, match="one folder"):
        replace_in_order([Planned(tmp_path / "a", b"1"), Planned(tmp_path / "sub" / "b", b"2")])


# --- a process that ends at any step (#71; review of PR #182) --------------------------------

#: A child that saves ``a`` then ``b`` (``mode`` "save") or replays (``mode`` "replay") and
#: ends at once, running no clean-up, at its stop-th step: a step is a call of
#: ``os.replace`` or ``os.fsync``. It exits 0 when it finishes before that step.
CHILD = """
import os, sys
from pathlib import Path
from ithax.service.commit import Planned, replace_in_order, replay
folder, mode, stop = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
steps = [0]
def stepping(real):
    def step(*args):
        steps[0] += 1
        if steps[0] == stop:
            os._exit(9)
        return real(*args)
    return step
os.replace, os.fsync = stepping(os.replace), stepping(os.fsync)
if mode == "save":
    replace_in_order([Planned(folder / "a", b"new a"), Planned(folder / "b", b"new b")])
else:
    replay(folder)
"""


def child(folder: Path, mode: str, stop: int) -> int:
    ended = subprocess.run(
        [sys.executable, "-c", CHILD, str(folder), mode, str(stop)], check=False, timeout=60
    )
    return ended.returncode


def settled(folder: Path) -> tuple[bytes, bytes]:
    """The folder as the next use reads it: replayed, then read."""
    replay(folder)
    assert not (folder / RECORD).exists()
    return contents(folder)


def test_a_save_stopped_at_any_step_then_its_replay_stopped_at_any_step_is_old_or_new(
    tmp_path: Path,
) -> None:
    """Every stop of the writer, and every stop of a replay after it, ends as the old two
    files or the new two, never one of each (the class of the review of PR #182)."""
    seen: set[tuple[bytes, bytes]] = set()
    stop = 1
    while True:
        folder = tmp_path / f"save-{stop}"
        folder.mkdir()
        old_files(folder)
        if child(folder, "save", stop) == 0:
            assert settled(folder) == NEW
            break
        recorded = (folder / RECORD).exists()
        again = 1
        while recorded:
            copy = tmp_path / f"save-{stop}-replay-{again}"
            shutil.copytree(folder, copy)
            if child(copy, "replay", again) == 0:
                assert settled(copy) == NEW
                break
            state = settled(copy)
            assert state == NEW, (stop, again, state)
            again += 1
        state = settled(folder)
        assert state in (OLD, NEW), (stop, state)
        assert state == NEW if recorded else state == OLD
        seen.add(state)
        stop += 1
    assert seen == {OLD, NEW}
    assert stop > 5


def test_the_record_names_each_temporary_and_its_target(tmp_path: Path) -> None:
    """The first stop that leaves a record shows what it holds."""
    for stop in range(1, 10):
        folder = tmp_path / f"at-{stop}"
        folder.mkdir()
        old_files(folder)
        child(folder, "save", stop)
        if (folder / RECORD).exists():
            record = json.loads((folder / RECORD).read_text(encoding="utf-8"))
            assert [target for _, target in record["renames"]] == ["a", "b"]
            assert all(source.startswith(f".{target}.") for source, target in record["renames"])
            return
    pytest.fail("no stop left a record")


def test_a_target_that_is_a_folder_saves_nothing(tmp_path: Path) -> None:
    """No rename onto a folder can be finished, so it is refused before the record."""
    (tmp_path / "a").write_bytes(OLD[0])
    (tmp_path / "b").mkdir()
    with pytest.raises(CommitFailed) as failed:
        replace_in_order(two(tmp_path))
    assert failed.value.pending is False
    assert names(tmp_path) == ["a", "b"]
    assert (tmp_path / "a").read_bytes() == OLD[0]


# --- a replay and a commit in one folder at once (review of PR #182, second round) ----------


def test_a_replay_and_a_later_save_in_one_folder_never_meet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex's interleaving: replay A reads the record of save 1 and pauses; save 2 runs,
    and its last rename fails, so its record must stay; A must not then remove it. One
    lock per folder over the whole of every replay and commit keeps them apart."""
    import threading

    old_files(tmp_path)
    real_replace = os.replace

    def failing_b(source: Any, target: Any) -> None:
        if Path(target).name == "b" and threading.current_thread().name in ("first", "second"):
            raise PermissionError("denied")
        real_replace(source, target)

    # Save 1 is left recorded: its rename of b fails.
    monkeypatch.setattr(os, "replace", failing_b)
    first = threading.Thread(target=lambda: _expect_pending(two(tmp_path)), name="first")
    first.start()
    first.join(30)
    assert (tmp_path / RECORD).exists()

    read, go = threading.Event(), threading.Event()
    real_renames = commit._renames

    def pausing(record: Path) -> list[tuple[str, str]] | None:
        found = real_renames(record)
        if threading.current_thread().name == "replay":
            read.set()
            go.wait(10)
        return found

    monkeypatch.setattr(commit, "_renames", pausing)
    replaying = threading.Thread(target=lambda: replay(tmp_path), name="replay")
    replaying.start()
    assert read.wait(10)
    later = [Planned(tmp_path / "a", b"2 a"), Planned(tmp_path / "b", b"2 b")]
    second = threading.Thread(target=lambda: _expect_pending(later), name="second")
    second.start()
    second.join(0.5)
    assert second.is_alive(), "the save went ahead while the replay held the folder"
    go.set()
    replaying.join(30)
    second.join(30)
    # Save 2 is recorded; the next replay finishes it, whole.
    assert (tmp_path / RECORD).exists()
    monkeypatch.undo()
    assert replay(tmp_path)
    assert contents(tmp_path) == (b"2 a", b"2 b")


def _expect_pending(files: list[Planned]) -> None:
    with pytest.raises(CommitFailed) as failed:
        replace_in_order(files)
    assert failed.value.pending is True


def test_a_record_that_cannot_be_looked_at_refuses_the_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Third review of PR #182: ``exists`` on the record can raise (a folder that cannot be
    read); that refuses as a recorded change does, never as an exception."""
    real = Path.exists

    def exists(self: Path, *args: Any, **options: Any) -> bool:
        if self.name == RECORD:
            raise PermissionError("denied")
        return real(self, *args, **options)

    monkeypatch.setattr(Path, "exists", exists)
    with pytest.raises(CommitFailed) as failed:
        replay(tmp_path)
    assert failed.value.pending is True
