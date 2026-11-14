"""M0 smoke test: the package and its planned subpackages import."""

import importlib

import pytest

import ithax

SUBPACKAGES = [
    "ithax.model",
    "ithax.engines",
    "ithax.engines.process",
    "ithax.engines.optimize",
    "ithax.runs",
    "ithax.service",
    "ithax.mcp",
    "ithax.findings",
]


def test_version_is_set() -> None:
    assert ithax.__version__ == "0.0.0"


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_imports(name: str) -> None:
    assert importlib.import_module(name).__name__ == name
