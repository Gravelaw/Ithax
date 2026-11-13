"""Power of Ten rule 4 for Python: no function longer than 60 lines (P21).

Proposed in docs/retrospective/proposed-agent-setup.md, P21; adopted under owner decision F2
(#99). The allow-list holds the functions that were longer on 2026-11-09. It may only shrink:
splitting one of them means deleting its line here, and no new name may be added.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "lcsim"
MAX_LINES = 60
ALLOWED = {
    "model/loading.py::_Builder.build",
    "model/loading.py::_Builder.component",
    "model/loading.py::_Builder.distribution",
    "model/loading.py::_Builder.program",
    "model/migration.py::migrate",
    "model/schema.py::_issues_from_error",
    "model/validation.py::identifier_issues",
    "model/validation.py::setting_issues",
    "model/validation.py::connection_issues",
    "model/validation.py::_setting_values",
    "model/validation.py::_distribution_issues",
    "model/validation.py::data_issues",
    "model/validation.py::experiment_issues",
    "model/validation.py::_experiment_values",
    "runs/snapshots.py::read_columns",
    "runs/summary.py::build_summary",
    "runs/targets.py::LocalRun.__init__",
    "service/app.py::create_app",
    "templates/package.py::_Loader.template",
    "templates/package.py::_Loader.runnable",
}


def _long_functions(path: Path, root: Path = SRC) -> set[str]:
    found: set[str] = set()

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, f"{prefix}{child.name}.")
            elif isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                end = child.end_lineno if child.end_lineno is not None else child.lineno
                if end - child.lineno + 1 > MAX_LINES:
                    found.add(f"{path.relative_to(root).as_posix()}::{prefix}{child.name}")
                visit(child, f"{prefix}{child.name}.")

    visit(ast.parse(path.read_text(encoding="utf-8")), "")
    return found


def test_no_new_function_is_longer_than_60_lines() -> None:
    long: set[str] = set()
    for path in sorted(SRC.rglob("*.py")):
        long |= _long_functions(path)
    assert not long - ALLOWED, (
        f"Split these functions (at most {MAX_LINES} lines): {sorted(long - ALLOWED)}"
    )
    assert not ALLOWED - long, f"Now short enough; remove from ALLOWED: {sorted(ALLOWED - long)}"


def test_the_ratchet_finds_long_methods_and_nested_functions(tmp_path: Path) -> None:
    """The visitor reaches methods and nested functions, so the test above cannot pass vacuously."""
    long_body = "".join(f"        x{i} = {i}\n" for i in range(MAX_LINES))
    short_body = "".join(f"        y{i} = {i}\n" for i in range(MAX_LINES - 2))
    source = (
        "class C:\n    def long(self) -> None:\n"
        + long_body
        + "    def short(self) -> None:\n"
        + short_body
        + "def outer() -> None:\n    def inner() -> None:\n"
        + long_body
    )
    probe = tmp_path / "probe.py"
    probe.write_text(source, encoding="utf-8")
    assert _long_functions(probe, tmp_path) == {
        "probe.py::C.long",
        "probe.py::outer",
        "probe.py::outer.inner",
    }
