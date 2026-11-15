"""Fail when a branch changes or removes a line ``docs/DECISIONS.md`` held at its merge base.

``docs/DECISIONS.md`` is the Phase 1 log, frozen from Phase 2 (retrospective P15): a pull
request may only append to it. Lines were lost from it in two merges, #189 and #213, both
times from a conflict resolved by hand, so CI checks it.

Usage: ``python scripts/decisions_append_only.py <base> [--repo <path>]``. ``<base>`` is the
branch or commit the change goes into (``origin/main`` for a pull request into main); the
check compares the working tree's file with the file at the merge base of ``HEAD`` and
``<base>``. Forty zeros, GitHub's "before" of a push that creates a branch, means no base.
"""

import argparse
import subprocess
import sys
from pathlib import Path

RECORD = "docs/DECISIONS.md"
NO_BASE = "0" * 40


def problems(base: str, head: str) -> list[str]:
    """Where ``head`` does not start with ``base``, line by line; trailing newlines aside."""
    old = base.rstrip("\n").splitlines()
    new = head.rstrip("\n").splitlines()
    for number, line in enumerate(old, start=1):
        if number > len(new) or new[number - 1] != line:
            return [f"line {number} of the base was changed or removed: {line!r}"]
    return []


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def base_text(repo: Path, base: str) -> str | None:
    """The record at the merge base of ``HEAD`` and ``base``, or None if it has none."""
    merge_base = git(repo, "merge-base", "HEAD", base)
    if merge_base.returncode != 0:
        raise SystemExit(f"no merge base of HEAD and {base}: {merge_base.stderr.strip()}")
    shown = git(repo, "show", f"{merge_base.stdout.strip()}:{RECORD}")
    return shown.stdout if shown.returncode == 0 else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("base")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    if args.base == NO_BASE:
        print(f"{RECORD}: no base to compare with (a new branch)")
        return 0
    base = base_text(args.repo, args.base)
    if base is None:
        print(f"{RECORD}: no {RECORD} at the base; nothing to compare")
        return 0
    head = (args.repo / RECORD).read_text(encoding="utf-8")
    found = problems(base, head)
    for problem in found:
        line = problem.split()[1]
        print(
            f"::error file={RECORD},line={line}::{problem}. {RECORD} is append-only: "
            "restore the base's lines and add the new entry after them.",
            file=sys.stderr,
        )
    if not found:
        print(f"{RECORD} only appends to the base ({len(base.splitlines())} lines kept)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
