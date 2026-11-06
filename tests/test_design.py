"""Checks on docs/design: wireframes are well-formed and indexed; colour contrast holds."""

import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "docs" / "design"
WIREFRAMES = DESIGN / "wireframes"
CONTRAST_SCRIPT = ROOT / "scripts" / "contrast.py"
SVG_NS = "{http://www.w3.org/2000/svg}"
REQUIRED_FILES = [
    "flows.md",
    "canvas-interactions.md",
    "design-system.md",
    "accessibility.md",
    "tokens.json",
    "wireframes/README.md",
]


def svgs() -> list[Path]:
    return sorted(WIREFRAMES.glob("*.svg"))


@pytest.mark.parametrize("name", REQUIRED_FILES)
def test_design_file_exists(name: str) -> None:
    assert (DESIGN / name).is_file(), f"docs/design/{name} is missing"


def test_there_are_wireframes() -> None:
    # Seven screens of spec 3 plus the first-start notice.
    assert len(svgs()) >= 8


@pytest.mark.parametrize("path", svgs(), ids=lambda p: p.name)
def test_wireframe_is_well_formed_svg_with_title(path: Path) -> None:
    root = ET.parse(path).getroot()
    assert root.tag == f"{SVG_NS}svg"
    title = root.find(f"{SVG_NS}title")
    desc = root.find(f"{SVG_NS}desc")
    assert title is not None and (title.text or "").strip()
    assert desc is not None and (desc.text or "").strip()


def test_every_wireframe_is_indexed_and_every_index_entry_exists() -> None:
    index = (WIREFRAMES / "README.md").read_text(encoding="utf-8")
    linked = set(re.findall(r"\]\(([^)]+\.svg)\)", index))
    on_disk = {p.name for p in svgs()}
    assert linked == on_disk


def contrast_output(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CONTRAST_SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_every_colour_pair_meets_its_wcag_threshold() -> None:
    result = contrast_output("--check")
    assert result.returncode == 0, result.stderr


def test_contrast_table_in_design_system_is_current() -> None:
    doc = (DESIGN / "design-system.md").read_text(encoding="utf-8")
    embedded = doc.split("<!-- contrast:start -->")[1].split("<!-- contrast:end -->")[0]
    assert embedded.strip() == contrast_output().stdout.strip()


def test_every_pair_names_defined_tokens_in_both_themes() -> None:
    data = json.loads((DESIGN / "tokens.json").read_text(encoding="utf-8"))
    themes = data["themes"]
    assert set(themes["light"]) == set(themes["dark"])
    for pair in data["pairs"]:
        assert pair["fg"] in themes["light"] and pair["bg"] in themes["light"]
        assert pair["kind"] in {"text", "large-text", "non-text"}
