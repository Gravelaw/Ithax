"""Sync checks between the Build guide, CLAUDE.md, spec 1 and the test tree."""

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


def guide_part_of_claude_md() -> str:
    """The text of CLAUDE.md between the header comment and '## Current state'."""
    text = CLAUDE_MD.read_text(encoding="utf-8")
    start = text.index("-->") + len("-->")
    end = text.index("\n## Current state")
    return text[start:end].strip()


def test_claude_md_holds_the_build_guide() -> None:
    assert guide_part_of_claude_md() == BUILD_GUIDE.read_text(encoding="utf-8").strip()


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


def test_spec_1_lists_the_30_schema_and_meaning_codes() -> None:
    """AKS-91 acceptance: the fixture check covers all 29 schema and meaning codes of M1;
    AKS-108 adds E175 (a coefficient that names no variable), so there are 30."""
    assert len(spec_1_issue_codes()) == 30
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
