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
