"""House rules that ruff cannot express (docs/retrospective/proposed-agent-setup.md, P5; #99).

"A JSON number, not a bool" is written once, in ``lcsim.strict_json`` (``is_whole``,
``is_number``, ``is_finite_real``, ``whole_in``, ``real_in``). This test finds the two
hand-written shapes of it elsewhere in ``src``:

- ``isinstance(x, int) and not isinstance(x, bool)`` (or ``int | float``, ``(int, float)``);
- ``isinstance(x, bool) or not isinstance(x, int)`` (the same, negated).

Only the numeric type sets are matched, so a check of a real boolean, or of "an int or a
string" (``lcsim.model.migration``), is not flagged. Other shapes, such as an early
``if isinstance(value, bool): return``, are left to review: the test is a backstop.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "lcsim"
HELPERS = {SRC / "strict_json.py"}
NUMERIC = frozenset({"int", "float"})


def _type_names(node: ast.expr) -> set[str] | None:
    """The names in an ``isinstance`` type argument: ``int``, ``(int, float)`` or
    ``int | float``; ``None`` for anything else."""
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.Tuple):
        names: set[str] = set()
        for element in node.elts:
            found = _type_names(element)
            if found is None:
                return None
            names |= found
        return names
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left, right = _type_names(node.left), _type_names(node.right)
        return None if left is None or right is None else left | right
    return None


def _isinstance_types(node: ast.expr) -> set[str] | None:
    """The type names of ``isinstance(x, <types>)``; ``None`` when ``node`` is not one."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "isinstance"
        and len(node.args) == 2
    ):
        return _type_names(node.args[1])
    return None


def _negated(node: ast.expr) -> ast.expr | None:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return node.operand
    return None


def _is_numeric(types: set[str] | None) -> bool:
    return types is not None and "int" in types and types <= NUMERIC


def number_checks(tree: ast.AST) -> list[int]:
    """Lines of a hand-written "JSON number, not a bool" check."""
    lines = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.BoolOp):
            continue
        values = node.values
        if isinstance(node.op, ast.And):
            numeric = any(_is_numeric(_isinstance_types(value)) for value in values)
            not_bool = any(
                (inner := _negated(value)) is not None and _isinstance_types(inner) == {"bool"}
                for value in values
            )
        else:
            numeric = any(
                (inner := _negated(value)) is not None and _is_numeric(_isinstance_types(inner))
                for value in values
            )
            not_bool = any(_isinstance_types(value) == {"bool"} for value in values)
        if numeric and not_bool:
            lines.append(node.lineno)
    return lines


def test_number_checks_go_through_strict_json() -> None:
    offenders = [
        f"{path.relative_to(SRC)}:{line}"
        for path in sorted(SRC.rglob("*.py"))
        if path not in HELPERS
        for line in number_checks(ast.parse(path.read_text(encoding="utf-8")))
    ]
    assert not offenders, (
        "Use lcsim.strict_json.is_whole, is_number or is_finite_real instead of a "
        "hand-written int-but-not-bool check: " + ", ".join(offenders)
    )


def test_the_check_finds_each_shape_and_only_numeric_ones() -> None:
    source = "\n".join(
        [
            "a = isinstance(x, int) and not isinstance(x, bool)",  # 1
            "b = isinstance(x, int | float) and not isinstance(x, bool)",  # 2
            "c = isinstance(x, (int, float)) and not isinstance(x, bool)",  # 3
            "d = isinstance(x, bool) or not isinstance(x, int)",  # 4
            "e = isinstance(x, bool) or not isinstance(x, int | float)",  # 5
            "f = isinstance(x, bool) or not isinstance(x, int | str)",  # 6: int or text
            "g = isinstance(x, bool)",  # 7: a real boolean
            "h = isinstance(x, str) and not isinstance(x, bool)",  # 8: not numeric
            "i = isinstance(x, float) and not isinstance(x, bool)",  # 9: no int
        ]
    )
    assert number_checks(ast.parse(source)) == [1, 2, 3, 4, 5]
