"""Sync checks between the Build guide, CLAUDE.md, docs/STATUS.md, spec 1 and the test tree."""

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = ROOT / "CLAUDE.md"
BUILD_GUIDE = ROOT / "docs" / "specs" / "build-guide.md"
SPEC_1 = ROOT / "docs" / "specs" / "1-model-format.md"
PYPROJECT = ROOT / "pyproject.toml"
ISSUE_FIXTURES = ROOT / "tests" / "model" / "fixtures" / "issues"
TESTS = ROOT / "tests"

ISSUE_ROW = re.compile(r"^\| ([EW]\d{3}) \| (schema|meaning) \|", re.MULTILINE)
MARK_USE = re.compile(r"pytest\.mark\.([A-Za-z_][A-Za-z0-9_]*)")
# Markers pytest itself defines; they are never registered in pyproject.toml.
BUILTIN_MARKERS = frozenset(
    {"parametrize", "skip", "skipif", "xfail", "usefixtures", "filterwarnings"}
)


# CLAUDE.md is a map of the build guide, not a copy of it (retrospective P8, #99): it stays
# short, and every path it names exists. Status is in docs/STATUS.md.
MAX_CLAUDE_MD_LINES = 120
CODE_SPAN = re.compile(r"`([^`\s]+)`")
FILE_SUFFIXES = (".md", ".py", ".sh", ".json", ".toml", ".yml")
STATUS = ROOT / "docs" / "STATUS.md"
SKILLS = ROOT / ".claude" / "skills"
SKILL_LINE = re.compile(r"^- `([a-z-]+)`: ", re.MULTILINE)
MILESTONE_ROW = re.compile(r"^\| (M\d+) ", re.MULTILINE)


def named_paths(text: str) -> list[str]:
    """The repository paths in ``text``'s code spans: a span with a ``/`` before its end, or
    a file name with a known suffix. Placeholders (``<name>``), API routes (``/v1``), dotted
    Python names and the local ``.venv`` are not paths."""
    paths = []
    for span in CODE_SPAN.findall(text):
        if "<" in span or span.startswith(("/", ".venv")):
            continue
        if "/" in span.rstrip("/") or span.endswith(FILE_SUFFIXES):
            paths.append(span)
    return paths


def test_claude_md_is_a_short_map() -> None:
    lines = CLAUDE_MD.read_text(encoding="utf-8").splitlines()
    assert len(lines) < MAX_CLAUDE_MD_LINES, f"CLAUDE.md has {len(lines)} lines"


def test_every_path_claude_md_names_exists() -> None:
    paths = named_paths(CLAUDE_MD.read_text(encoding="utf-8"))
    assert "docs/specs/build-guide.md" in paths and "docs/STATUS.md" in paths
    missing = [path for path in paths if not (ROOT / path).exists()]
    assert not missing, f"CLAUDE.md names paths that do not exist: {missing}"


def test_the_path_finder_skips_what_is_not_a_path() -> None:
    text = (
        "`docs/x.md` `AGENTS.md` `model/` `ithax.files` `docs/<n>.md` `.venv/bin/python` "
        "`/v1` `a b`"
    )
    assert named_paths(text) == ["docs/x.md", "AGENTS.md"]


def test_every_skill_is_listed_and_named_as_its_folder() -> None:
    listed = set(SKILL_LINE.findall(CLAUDE_MD.read_text(encoding="utf-8")))
    folders = {path.name for path in SKILLS.iterdir() if path.is_dir()}
    assert listed == folders
    for name in folders:
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        front = text.split("---\n")[1]
        assert f"name: {name}\n" in front
        assert "\ndescription: " in f"\n{front}"


def test_status_rows_are_milestones_of_the_guide() -> None:
    guide = set(MILESTONE_ROW.findall(BUILD_GUIDE.read_text(encoding="utf-8")))
    status = MILESTONE_ROW.findall(STATUS.read_text(encoding="utf-8"))
    assert status, "docs/STATUS.md has no milestone rows"
    assert set(status) <= guide


def spec_1_issue_codes() -> list[tuple[str, str]]:
    return ISSUE_ROW.findall(SPEC_1.read_text(encoding="utf-8"))


def test_spec_1_lists_validation_issue_codes() -> None:
    assert spec_1_issue_codes(), "spec 1 issue table has no schema or meaning rows"


# Every schema and meaning code has its fixture from M1 on (spec 1 acceptance table; guide M1
# "Done when"). The map of codes whose fixture was still pending (AKS-87 to AKS-90) was
# emptied by AKS-91 and then removed, so a code added to spec 1 later must arrive with its
# fixture. Design: docs/DECISIONS.md, 2026-11-06 · M1, "Warnings W200, W201 and W202 and
# the complete fixture set (AKS-91)".
@pytest.mark.parametrize(("code", "issue_pass"), spec_1_issue_codes())
def test_every_validation_issue_code_has_a_fixture(code: str, issue_pass: str) -> None:
    assert ISSUE_FIXTURES.is_dir(), f"{ISSUE_FIXTURES} is missing; it exists from M1 on"
    matches = list(ISSUE_FIXTURES.glob(f"{code}_*.json"))
    assert matches, f"no fixture for {code} ({issue_pass} pass) under {ISSUE_FIXTURES}"


def test_spec_1_lists_the_34_schema_and_meaning_codes() -> None:
    """AKS-91 acceptance: the fixture check covers all 29 schema and meaning codes of M1;
    AKS-108 adds E175 (a coefficient that names no variable), so there are 30; AKS-123 adds
    E176 to E178 (sets and tables of an indexed optimization model), so there are 33; #80
    adds E179 (a plan with nothing to decide), so there are 34."""
    assert len(spec_1_issue_codes()) == 34
    assert ("E175", "meaning") in spec_1_issue_codes()


def registered_markers() -> set[str]:
    with PYPROJECT.open("rb") as handle:
        config = tomllib.load(handle)
    entries: list[str] = config["tool"]["pytest"]["ini_options"]["markers"]
    return {entry.split(":", 1)[0].strip() for entry in entries}


def used_markers() -> set[str]:
    names: set[str] = set()
    for path in TESTS.rglob("*.py"):
        names.update(MARK_USE.findall(path.read_text(encoding="utf-8")))
    return names - BUILTIN_MARKERS


def test_every_marker_used_in_tests_is_registered() -> None:
    unregistered = used_markers() - registered_markers()
    assert not unregistered, f"markers used but not registered in pyproject.toml: {unregistered}"
