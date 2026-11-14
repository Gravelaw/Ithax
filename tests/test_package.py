"""M0 smoke test: the package and its planned subpackages import."""

import importlib
import re
import tomllib
from importlib import metadata
from pathlib import Path

import pytest

import ithax
from ithax.strict_json import read_json_object_file

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


#: PEP 440 for the versions the product uses: a release, or a development release of one.
PEP_440 = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:\.dev(\d+))?")
DESKTOP = Path(__file__).resolve().parents[1] / "desktop"


def semver(version: str) -> str:
    """The semver spelling of a PEP 440 version: ``0.1.0.dev0`` is ``0.1.0-dev.0``."""
    match = PEP_440.fullmatch(version)
    assert match, version
    major, minor, patch, dev = match.groups()
    return f"{major}.{minor}.{patch}" + ("" if dev is None else f"-dev.{dev}")


def test_the_version_is_real() -> None:
    """#78: not the placeholder 0.0.0; the installed distribution reports the same."""
    assert ithax.__version__ != "0.0.0"
    assert PEP_440.fullmatch(ithax.__version__)
    assert metadata.version("ithax") == ithax.__version__


def test_the_semver_spelling() -> None:
    assert semver("0.1.0.dev0") == "0.1.0-dev.0"
    assert semver("1.2.3") == "1.2.3"


def test_the_desktop_shell_has_the_products_version() -> None:
    expected = semver(ithax.__version__)
    cargo = tomllib.loads((DESKTOP / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8"))
    assert cargo["package"]["version"] == expected
    for path in (DESKTOP / "package.json", DESKTOP / "src-tauri" / "tauri.conf.json"):
        assert read_json_object_file(path)["version"] == expected, path


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_imports(name: str) -> None:
    assert importlib.import_module(name).__name__ == name
