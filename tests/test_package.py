"""M0 smoke test: the package and its planned subpackages import."""

import importlib

import pytest

import lcsim

SUBPACKAGES = [
    "lcsim.model",
    "lcsim.engines",
    "lcsim.engines.process",
    "lcsim.engines.optimize",
    "lcsim.runs",
    "lcsim.service",
    "lcsim.mcp",
    "lcsim.findings",
]


def test_version_is_set() -> None:
    assert lcsim.__version__ == "0.0.0"


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_imports(name: str) -> None:
    assert importlib.import_module(name).__name__ == name
