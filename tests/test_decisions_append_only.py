"""``scripts/decisions_append_only.py``: a pull request only appends to
``docs/DECISIONS.md`` (the Phase 1 log, frozen from Phase 2 by P15). Lines were lost from it
in two merges, #189 and #213, so the check is in CI, not a manual step."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "decisions_append_only.py"
FIXTURES = Path(__file__).resolve().parent / "decisions_fixtures"

sys.path.insert(0, str(SCRIPT.parent))
import decisions_append_only  # noqa: E402


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_only_appending_passes() -> None:
    assert decisions_append_only.problems(fixture("base.md"), fixture("appends.md")) == []


def test_a_dropped_line_fails_and_is_named() -> None:
    found = decisions_append_only.problems(fixture("base.md"), fixture("drops.md"))
    assert found == [
        "line 11 of the base was changed or removed: '- **Dependencies added:** none.'"
    ]


def test_a_changed_line_and_an_inserted_entry_fail() -> None:
    base = fixture("base.md")
    assert decisions_append_only.problems(base, base.replace("one.", "uno.")) == [
        "line 5 of the base was changed or removed: '- **Decision:** one.'"
    ]
    inserted = base.replace("## 2026-11-15", "## 2026-11-14 · M14 · Inserted\n\n## 2026-11-15")
    assert len(decisions_append_only.problems(base, inserted)) == 1


def test_unchanged_and_trailing_newlines_pass() -> None:
    base = fixture("base.md")
    assert decisions_append_only.problems(base, base) == []
    assert decisions_append_only.problems(base, base + "\n\n") == []
    assert decisions_append_only.problems(base.rstrip("\n"), base) == []


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository whose ``main`` holds ``base.md`` as its DECISIONS, and a branch off it."""
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "config", "user.name", "test")
    record = tmp_path / "docs" / "DECISIONS.md"
    record.parent.mkdir()
    record.write_text(fixture("base.md"), encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    git(tmp_path, "checkout", "-q", "-b", "work")
    return tmp_path


def commit(repo: Path, name: str) -> None:
    (repo / "docs" / "DECISIONS.md").write_text(fixture(name), encoding="utf-8")
    git(repo, "commit", "-q", "-am", name)


def test_the_command_passes_a_branch_that_appends(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    commit(repo, "appends.md")
    assert decisions_append_only.main(["main", "--repo", str(repo)]) == 0
    assert "only appends" in capsys.readouterr().out


def test_the_command_fails_a_branch_that_drops_a_line(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    commit(repo, "drops.md")
    assert decisions_append_only.main(["main", "--repo", str(repo)]) == 1
    err = capsys.readouterr().err
    assert "::error file=docs/DECISIONS.md,line=11::" in err
    assert "Dependencies added" in err


def test_the_command_compares_with_the_merge_base_not_the_bases_tip(repo: Path) -> None:
    """main moving on after the branch point is not a deletion on the branch."""
    commit(repo, "appends.md")
    git(repo, "checkout", "-q", "main")
    (repo / "docs" / "DECISIONS.md").write_text(fixture("base.md") + "\nMore on main.\n", "utf-8")
    git(repo, "commit", "-q", "-am", "main moves on")
    git(repo, "checkout", "-q", "work")
    assert decisions_append_only.main(["main", "--repo", str(repo)]) == 0


def test_no_base_or_a_base_without_the_file_passes(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A push that creates a branch has no base (GitHub sends forty zeros)."""
    assert decisions_append_only.main(["0" * 40, "--repo", str(repo)]) == 0
    assert "no base" in capsys.readouterr().out
    git(repo, "rm", "-q", "docs/DECISIONS.md")
    git(repo, "commit", "-q", "-m", "without the record")
    without = git(repo, "rev-parse", "HEAD")
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs" / "DECISIONS.md").write_text(fixture("base.md"), encoding="utf-8")
    git(repo, "add", "docs/DECISIONS.md")
    git(repo, "commit", "-q", "-m", "the record again")
    assert decisions_append_only.main([without, "--repo", str(repo)]) == 0
    assert "no docs/DECISIONS.md at the base" in capsys.readouterr().out


def test_ci_runs_the_check_and_all_green_needs_it() -> None:
    workflow = (ROOT / ".github" / "workflows" / "checks.yml").read_text(encoding="utf-8")
    assert 'python scripts/decisions_append_only.py "$BASE"' in workflow
    assert "needs: [checks, interface, desktop, package, decisions]" in workflow
    # A pull request is compared with the branch it goes into, a push with its "before".
    assert "format('origin/{0}', github.base_ref) || github.event.before" in workflow
