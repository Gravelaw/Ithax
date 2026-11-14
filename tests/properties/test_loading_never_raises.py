"""Property: no document makes the model loader raise; it returns a model or an issue.

Covers the input-robustness findings of Phase 1 (docs/retrospective/
phase-1-engineering-review.md, W2; proposed-agent-setup.md, P6; #99).
"""

import copy
import json
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from lcsim.model.loading import load_document, load_text
from properties.strategies import JSON_VALUES

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = json.loads((ROOT / "examples" / "coffee_shop.json").read_text(encoding="utf-8"))


def _leaf_paths(value: object, path: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
    if isinstance(value, dict):
        return [p for k, v in value.items() for p in _leaf_paths(v, (*path, k))] or [path]
    if isinstance(value, list):
        return [p for i, v in enumerate(value) for p in _leaf_paths(v, (*path, i))] or [path]
    return [path]


LEAVES = _leaf_paths(EXAMPLE)


@given(JSON_VALUES)
def test_any_document_gives_a_model_or_an_issue(document: object) -> None:
    result = load_document(document)
    assert result.model is not None or result.issues


# No deadline: a valid model reaches the engine discovery and the meaning pass, and the first
# such call took 920 ms when this test was tried on 2026-11-09.
@settings(max_examples=300, deadline=None)
@given(st.sampled_from(LEAVES), JSON_VALUES)
def test_the_example_with_one_hostile_leaf_gives_a_model_or_an_issue(
    path: tuple[object, ...], value: object
) -> None:
    document = copy.deepcopy(EXAMPLE)
    target: object = document
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    if path:
        target[path[-1]] = value  # type: ignore[index]
    result = load_document(document)
    assert result.model is not None or result.issues


@given(st.binary(max_size=200) | st.text(max_size=200))
def test_any_bytes_or_text_gives_a_model_or_an_issue(text: bytes | str) -> None:
    result = load_text(text)
    assert result.model is not None or result.issues
