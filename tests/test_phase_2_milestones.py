"""The proposed Phase 2 milestone table (``docs/research/phase-2-milestones.md``) names
every row of the Phase 1 review's "Later-phase parts of accepted readings" that goes to the
"Phase 2 table" in a milestone row (review of pull request 214: two rows had no milestone,
and a catch-all hid the rest)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEW = ROOT / "docs" / "research" / "phase-1-review.md"
MILESTONES = ROOT / "docs" / "research" / "phase-2-milestones.md"
MILESTONE_ROW = re.compile(r"^\| M\d+ \|", re.MULTILINE)


def section(text: str, heading: str) -> str:
    start = text.index(f"\n## {heading}\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end >= 0 else len(text)]


def phase_2_items() -> list[str]:
    """The session items of the rows whose "Goes to" starts with "Phase 2 table"."""
    rows = section(REVIEW.read_text("utf-8"), "Later-phase parts of accepted readings (E1)")
    items = []
    for line in rows.splitlines():
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) == 4 and cells[3].startswith("Phase 2 table"):
            items.append(cells[0].strip("()"))
    return items


def milestone_rows() -> str:
    text = MILESTONES.read_text("utf-8")
    return "\n".join(line for line in text.splitlines() if MILESTONE_ROW.match(line))


def test_every_phase_2_table_row_has_a_milestone() -> None:
    items = phase_2_items()
    assert len(items) > 20
    rows = milestone_rows()
    missing = [item for item in items if not re.search(rf"{re.escape(item)}(?!\d)", rows)]
    assert not missing, f"name these items in a Phase 2 milestone row: {missing}"


def test_the_parser_finds_the_two_rows_of_the_finding() -> None:
    assert {'M5 "Left"', "M6-28", "M9-105"} <= set(phase_2_items())


CODE = re.compile(r"\b(?:[A-F]\d+|P\d+|M\d+-\d+)\b")


def holds_codes() -> list[str]:
    """The decision, retrospective and session codes of "What Phase 2 holds"."""
    text = MILESTONES.read_text("utf-8")
    holds = section(text, "What Phase 2 holds").split("\nNot in Phase 2:", 1)[0]
    return sorted(set(CODE.findall(holds)))


def test_every_item_phase_2_holds_has_a_milestone() -> None:
    """Review of pull request 214, second finding: the retrospective's items were covered
    by "and the rest", and could be closed by listing them."""
    codes = holds_codes()
    assert {"P12", "P25", "D10", "M5-23"} <= set(codes)
    rows = milestone_rows()
    missing = [code for code in codes if not re.search(rf"\b{re.escape(code)}(?![\d-])", rows)]
    assert not missing, f"name these codes in a Phase 2 milestone row: {missing}"


def test_no_milestone_closes_by_listing_or_a_catch_all() -> None:
    rows = milestone_rows()
    for phrase in ("and the rest", "listed for the owner", "rows of"):
        assert phrase not in rows, f'a milestone row says "{phrase}"; name each item instead'


GUIDE = ROOT / "docs" / "specs" / "build-guide.md"


def test_the_guide_holds_the_approved_phase_2_rows_unchanged() -> None:
    """The owner approved the table on 2026-11-16 (D18); the guide's M17 to M26 rows are
    that table, so a change to one must be made to both."""
    guide = [line for line in GUIDE.read_text("utf-8").splitlines() if MILESTONE_ROW.match(line)]
    phase_2 = [line for line in guide if int(line.split("|")[1].strip()[1:]) >= 17]
    assert phase_2 == milestone_rows().splitlines()
    assert [line.split("|")[1].strip() for line in phase_2] == [f"M{n}" for n in range(17, 27)]
