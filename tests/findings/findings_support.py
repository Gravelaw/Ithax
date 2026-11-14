"""Reading the finding-rule fixtures (``tests/findings/fixtures/``, written by
``tests/findings/make_fixtures.py``; AKS-117).

Each fixture is a finished run: the run folder's ``model.json`` under ``model`` and its
``summary.json`` under ``summary``. Reading one loads the model (no run), so the tests run
nothing.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ithax.model.loading import load_document
from ithax.model.model import Model
from ithax.strict_json import read_json_file

FIXTURES = Path(__file__).resolve().parent / "fixtures"

Run = tuple[dict[str, Any], Model]


def fixture_document(name: str) -> dict[str, Any]:
    """The fixture ``<name>.json``: ``{about, model, summary}``."""
    document = read_json_file(FIXTURES / f"{name}.json")
    assert isinstance(document, dict)
    return document


def model_of(document: dict[str, Any]) -> Model:
    """The loaded model of a model file document, which must load without errors."""
    loaded = load_document(document)
    assert loaded.model is not None, loaded.issues
    return loaded.model


def read_run(name: str, change_model: Callable[[dict[str, Any]], None] | None = None) -> Run:
    """The fixture's summary (a fresh copy, free to edit) and loaded model; ``change_model``
    edits the model document before it is loaded."""
    document = fixture_document(name)
    model_document = copy.deepcopy(document["model"])
    if change_model is not None:
        change_model(model_document)
    return copy.deepcopy(document["summary"]), model_of(model_document)
