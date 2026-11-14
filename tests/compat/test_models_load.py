"""Compatibility: every model in the corpus loads with zero errors (build guide
"Conventions", Compatibility; docs/retrospective/proposed-agent-setup.md, P24; #99).

The corpus (``tests/compat/models/<format_version>/``) only grows; see its README.
"""

import json
from pathlib import Path

import pytest

from ithax.model.loading import load_text

CORPUS = Path(__file__).resolve().parent / "models"
FILES = sorted(CORPUS.glob("*/*.json"))
#: The corpus at its start (2026-11-14). The count may rise, never fall.
FLOOR = 30


def test_the_corpus_only_grows() -> None:
    assert len(FILES) >= FLOOR, f"the corpus lost files: {len(FILES)} < {FLOOR}"


@pytest.mark.parametrize("path", FILES, ids=lambda path: f"{path.parent.name}/{path.name}")
def test_a_saved_model_loads_with_zero_errors(path: Path) -> None:
    raw = path.read_bytes()
    assert json.loads(raw)["format_version"] == path.parent.name, "filed under its version"
    result = load_text(raw)
    assert not result.errors, [f"{issue.code} {issue.message}" for issue in result.errors]
    assert result.model is not None
