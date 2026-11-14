"""Run limits (spec 4 "Limits"; spec 1 E192; AKS-103): defaults, reading memory, and the
decision."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from ithax.runs import limits
from ithax.runs.limits import (
    DEFAULT_TIME_LIMIT_S,
    Limits,
    default_memory_limit,
    descendant_ids,
    limit_exceeded,
    process_tree_memory,
    system_memory,
)


def test_the_defaults_are_ten_minutes_and_half_of_system_memory() -> None:
    assert DEFAULT_TIME_LIMIT_S == 600.0
    total = system_memory()
    assert total is not None and total > 0  # Linux, where the checks run
    assert default_memory_limit() == total // 2
    assert Limits() == Limits(time_s=600.0, memory_bytes=total // 2)


def test_system_memory_is_unknown_without_sysconf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(os, "sysconf")  # as on Windows
    assert system_memory() is None
    assert default_memory_limit() is None
    assert Limits().memory_bytes is None


def test_system_memory_is_unknown_when_sysconf_cannot_say(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(name: str) -> int:
        raise ValueError(name)

    monkeypatch.setattr(os, "sysconf", refuse)
    assert system_memory() is None


def test_a_limit_must_be_positive() -> None:
    with pytest.raises(ValueError, match="time limit"):
        Limits(time_s=0)
    with pytest.raises(ValueError, match="memory limit"):
        Limits(memory_bytes=0)


def test_the_decision() -> None:
    small = Limits(time_s=10.0, memory_bytes=1000)
    assert limit_exceeded(small, elapsed_s=10.0, memory_bytes=1000) is None  # at the limit
    assert limit_exceeded(small, elapsed_s=10.01, memory_bytes=0) == "time"
    assert limit_exceeded(small, elapsed_s=0.0, memory_bytes=1001) == "memory"
    assert limit_exceeded(small, elapsed_s=11.0, memory_bytes=2000) == "time"  # time first
    assert limit_exceeded(small, elapsed_s=1.0, memory_bytes=None) is None  # not read
    unknown = Limits(time_s=10.0, memory_bytes=None)
    assert limit_exceeded(unknown, elapsed_s=1.0, memory_bytes=10**12) is None


def test_this_process_uses_memory() -> None:
    used = process_tree_memory(os.getpid())
    assert used is not None and used > 1_000_000


def test_a_child_process_counts_with_its_parent() -> None:
    alone = process_tree_memory(os.getpid())
    # The child holds 50 MB of touched memory, then says so.
    code = "import sys; b = b'x' * 50_000_000; print('ready', flush=True); sys.stdin.read()"
    # As a context manager, so both pipes are closed and the child waited for (P20).
    with subprocess.Popen(
        [sys.executable, "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    ) as child:
        try:
            assert child.stdout is not None and child.stdout.readline().strip() == "ready"
            own = process_tree_memory(child.pid)
            with_child = process_tree_memory(os.getpid())
            assert alone is not None and with_child is not None and own is not None
            assert own > 50_000_000
            assert with_child > alone + 45_000_000  # the parent's own use moves a little
        finally:
            assert child.stdin is not None
            child.stdin.close()
            child.wait()


def test_memory_is_unknown_without_proc(tmp_path: Path) -> None:
    assert process_tree_memory(os.getpid(), proc=tmp_path / "missing") is None


def test_memory_is_unknown_for_a_process_that_is_gone(tmp_path: Path) -> None:
    (tmp_path / "self").mkdir()
    assert process_tree_memory(424242, proc=tmp_path) is None


def test_unreadable_entries_are_skipped(tmp_path: Path) -> None:
    # A fake /proc: process 10 has child 11 (comm with a space and a parenthesis) and a
    # grandchild 12; 13 is unrelated; 14 vanished between listing and reading; "net" is
    # not a process.
    def process(pid: int, ppid: int, pages: int, comm: str = "python") -> None:
        folder = tmp_path / str(pid)
        folder.mkdir()
        (folder / "stat").write_text(f"{pid} ({comm}) S {ppid} 1 1 0\n", encoding="ascii")
        (folder / "statm").write_text(f"1000 {pages} 10 1 0 50 0\n", encoding="ascii")

    process(10, 1, 100)
    process(11, 10, 20, comm="a) b")
    process(12, 11, 3)
    process(13, 1, 999)
    (tmp_path / "14").mkdir()
    (tmp_path / "net").mkdir()
    process(15, 10, 0)
    (tmp_path / "15" / "statm").unlink()  # ended between the two reads: counts 0
    page = limits.PAGE_SIZE
    assert process_tree_memory(10, proc=tmp_path) == (100 + 20 + 3) * page
    assert process_tree_memory(11, proc=tmp_path) == (20 + 3) * page
    assert sorted(descendant_ids(10, proc=tmp_path)) == [11, 12, 15]
    assert descendant_ids(13, proc=tmp_path) == []
    assert descendant_ids(99, proc=tmp_path) == []  # not there
    assert descendant_ids(10, proc=tmp_path / "missing") == []  # no /proc
