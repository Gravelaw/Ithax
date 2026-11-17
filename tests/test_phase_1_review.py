"""The Phase 1 review's checklist (#101, ``docs/research/phase-1-review.md``) leaves out no
accepted decision: every owner decision, every later-phase reading of ``docs/DECISIONS.md``
and of the session summaries' "Awaiting owner" lists, and every open marker in specs 0 to
4 and the overview is named in its "Coverage" section (review of pull request 208: a
decision's later-phase half was missed twice).

The DECISIONS entries are read up to the checklist's "Surveyed through" date, and a spec
only while it is at the version the checklist surveyed: once a spec's review PR raises its
version, the rows for it have been applied."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEW = ROOT / "docs" / "research" / "phase-1-review.md"
DECISIONS = ROOT / "docs" / "DECISIONS.md"
SESSIONS = ROOT / "docs" / "sessions"
SPECS = ROOT / "docs" / "specs"
SPEC_FILES = {
    "spec 0": "0-product-brief.md",
    "spec 1": "1-model-format.md",
    "spec 2": "2-core-engine.md",
    "spec 3": "3-desktop-app.md",
    "spec 4": "4-content-and-ai.md",
    "overview": "overview.md",
}

# A spec line that leaves something open or puts it off. "Owner to confirm" is not one:
# E1 (2026-11-13) accepts those readings as the current behaviour of format 0.x.
OPEN_MARKER = re.compile(
    r"owner question|to be decided|\bdeferred\b|Phase 1 review|AKS-130|not yet chosen"
    r"|\bstays? open\b|Phase 2 candidate|later phases?\b",
    re.IGNORECASE,
)
LATER_PHASE = re.compile(r"\bPhase (?:2|3|3a|4)\b")
BUCKET = re.compile(r"[Bb]ucket[^.|]*?\bPhase (?:2|3|3a|4)\b")
OWNER_ENTRY = re.compile(r"^## (\d{4}-\d\d-\d\d) · Owner decisions")
ENTRY_DATE = re.compile(r"^## (\d{4}-\d\d-\d\d) ")
# The item codes of an owner-decision entry: "### A1 (...)", "### Item 6: ...",
# "- **B4 and C7.**", "| D1 Ranking ... |", "| M4-39, M4-40 |" and "  1. **Phase 2 ...".
OWNER_CODE = re.compile(
    r"^(?:### (?P<heading>[A-F]\d+|Item \d+)\b"
    r"|- \*\*(?P<bold>[A-F]\d+(?:(?:, | and )[A-F]\d+)*|F9 to F19)\."
    r"|\| (?P<row>[A-Z]\d+(?:-\d+)?(?:, [A-Z]\d+-\d+)*)(?= )"
    r"|  (?P<numbered>\d+)\. \*\*)",
    re.MULTILINE,
)
COVERED = re.compile(r"^- (?P<key>[^:\n]+?): ", re.MULTILINE)
QUOTED = re.compile(r'^- (?P<spec>spec [0-4]|overview): "(?P<quote>[^"\n]+)"', re.MULTILINE)
SURVEYED = re.compile(r"^Surveyed through: (\d{4}-\d\d-\d\d)\.?$", re.MULTILINE)
SURVEYED_VERSION = re.compile(r"^## (Spec [0-4]) \([^)]*, version (\d+\.\d+)\)$", re.MULTILINE)
SPEC_VERSION = re.compile(r"^> Version (\d+\.\d+) ", re.MULTILINE)


def review() -> str:
    return REVIEW.read_text("utf-8")


def coverage() -> str:
    text = review()
    start = text.index("\n## Coverage\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end >= 0 else len(text)]


def covered_keys() -> set[str]:
    return {match["key"].strip() for match in COVERED.finditer(coverage())}


def surveyed_entries() -> list[tuple[str, str]]:
    """The DECISIONS entries, as (date, text), dated up to "Surveyed through"."""
    found = SURVEYED.search(review())
    assert found, 'the checklist says "Surveyed through: <date>."'
    entries = re.split(r"(?m)^(?=## )", DECISIONS.read_text("utf-8"))
    dated = []
    for entry in entries:
        date = ENTRY_DATE.match(entry)
        if date and date[1] <= found[1]:
            dated.append((date[1], entry))
    return dated


def owner_keys() -> set[str]:
    keys = set()
    for date, entry in surveyed_entries():
        if not OWNER_ENTRY.match(entry):
            continue
        for match in OWNER_CODE.finditer(entry):
            code = next(value for value in match.groupdict().values() if value)
            if match["numbered"]:
                keys.add(f"{date} item {code}")
            elif code == "F9 to F19":
                keys.add(f"{date} {code}")
            else:
                keys.update(f"{date} {part}" for part in re.split(r", | and ", code))
    return keys


def entry_code(heading: str) -> str:
    """The issue an entry heading names (``AKS-108``, ``#85``), else its ``Item <n>``."""
    issue = re.search(r"\b(AKS-\d+|#\d+)\b", heading)
    if issue:
        return issue[1]
    item = re.match(r"#+ (Item \d+)\b", heading)
    return item[1] if item else heading.lstrip("# ").strip()


def reading_keys() -> set[str]:
    """``DECISIONS <issue> reading <n>`` for each numbered reading whose bucket is a later
    phase, or ``DECISIONS <issue> <label>`` for a bulleted one."""
    keys = set()
    for _date, entry in surveyed_entries():
        heading = ""
        for line in entry.splitlines():
            if line.startswith("#"):
                heading = line
                continue
            if not BUCKET.search(line):
                continue
            number = re.match(r"\s*(\d+)\. ", line)
            label = re.match(r"\s*- \*\*([^*:]+):?\*\*", line)
            if number:
                keys.add(f"DECISIONS {entry_code(heading)} reading {number[1]}")
            else:
                keys.add(f"DECISIONS {entry_code(heading)} {label[1] if label else 'entry'}")
    return keys


def session_keys() -> set[str]:
    """``M<n>-<item>`` for each "Awaiting owner" item of a session summary that names a later
    phase (E1 accepted them with their phases)."""
    keys = set()
    for path in sorted(SESSIONS.glob("*-M*.md")):
        milestone = re.search(r"-M(\d+)\.md$", path.name)
        awaiting = re.search(r"(?ms)^## Awaiting owner\n(.*?)(?=^## |\Z)", path.read_text("utf-8"))
        if not milestone or not awaiting:
            continue
        for line in awaiting[1].splitlines():
            item = re.match(r"(\d+)\. ", line)
            if item and LATER_PHASE.search(line):
                keys.add(f"M{milestone[1]}-{item[1]}")
    return keys


def specs_at_surveyed_version() -> dict[str, str]:
    """The specs still at the version the checklist surveyed, and the overview."""
    surveyed = dict(SURVEYED_VERSION.findall(review()))
    current = {"overview": (SPECS / SPEC_FILES["overview"]).read_text("utf-8")}
    for name, file in SPEC_FILES.items():
        if name == "overview":
            continue
        text = (SPECS / file).read_text("utf-8")
        version = SPEC_VERSION.search(text)
        assert version, f"{file} has a version line"
        if surveyed.get(name.capitalize()) == version[1]:
            current[name] = text
    return current


def open_lines(text: str) -> list[str]:
    body = text.split("\n## Changes in this version", 1)[0]
    return [line for line in body.splitlines() if OPEN_MARKER.search(line)]


def test_every_owner_decision_is_covered() -> None:
    missing = sorted(owner_keys() - covered_keys())
    assert len(owner_keys()) > 50
    assert not missing, f"add these owner decisions to the checklist's Coverage: {missing}"


def test_every_later_phase_reading_is_covered() -> None:
    missing = sorted(reading_keys() - covered_keys())
    assert len(reading_keys()) > 20
    assert not missing, f"add these DECISIONS readings to the checklist's Coverage: {missing}"


def test_every_later_phase_session_item_is_covered() -> None:
    missing = sorted(session_keys() - covered_keys())
    assert len(session_keys()) > 40
    assert not missing, f"add these session items to the checklist's Coverage: {missing}"


def test_every_open_marker_in_the_specs_is_covered() -> None:
    quotes: dict[str, list[str]] = {}
    for match in QUOTED.finditer(coverage()):
        quotes.setdefault(match["spec"], []).append(match["quote"])
    uncovered = []
    for name, text in specs_at_surveyed_version().items():
        for line in open_lines(text):
            if not any(quote in line for quote in quotes.get(name, [])):
                uncovered.append(f"{name}: {line[:120]}")
        if name != "overview":
            stale = [quote for quote in quotes.get(name, []) if quote not in text]
            assert not stale, f"{name} no longer holds these quoted markers: {stale}"
    assert not uncovered, f"quote these lines in the checklist's Coverage: {uncovered}"


def test_the_parsers_find_the_known_cases() -> None:
    """The two misses of pull request 208, and one of each shape, are found."""
    assert {"2026-11-09 B7", "2026-11-13 M5-23", "2026-11-13 C7", "2026-11-15 item 3"} <= (
        owner_keys()
    )
    assert {"2026-11-13 D18", "2026-11-13 F9 to F19", "2026-11-07 Item 7"} <= owner_keys()
    assert {"DECISIONS AKS-123 reading 2", "DECISIONS AKS-108 Left"} <= reading_keys()
    assert {"M9-44", "M10-30"} <= session_keys()
    # Spec 2's line as surveyed (version 1.1); its spec PR answered it, so the probe is
    # the line itself, not the live spec.
    surveyed = "Phase 1 accepts `standard` only. A `sketch` preview level is an owner question."
    assert open_lines(surveyed) == [surveyed]
    assert open_lines("A `sketch` preview fidelity is Phase 2 (2026-11-09 B7 item 1).") == []
