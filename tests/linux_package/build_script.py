"""``scripts/package_linux.py`` loaded as the module ``package_linux`` (``scripts/`` is not
a package), for the tests of this folder."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "package_linux", ROOT / "scripts" / "package_linux.py"
)
assert _spec is not None and _spec.loader is not None
build = importlib.util.module_from_spec(_spec)
sys.modules["package_linux"] = build
_spec.loader.exec_module(build)
