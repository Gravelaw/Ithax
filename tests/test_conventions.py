"""House rules that ruff cannot express (docs/retrospective/proposed-agent-setup.md, P5; #99).

"A JSON number, not a bool" is written once, in ``ithax.strict_json`` (``is_whole``,
``is_number``, ``is_finite_real``, ``whole_in``, ``real_in``). This test finds the two
hand-written shapes of it elsewhere in ``src``:

- ``isinstance(x, int) and not isinstance(x, bool)`` (or ``int | float``, ``(int, float)``);
- ``isinstance(x, bool) or not isinstance(x, int)`` (the same, negated).

Only the numeric type sets are matched, so a check of a real boolean, or of "an int or a
string" (``ithax.model.migration``), is not flagged. Other shapes, such as an early
``if isinstance(value, bool): return``, are left to review: the test is a backstop.

A file is replaced in one way, ``ithax.files.atomic_write`` (or ``atomic_write_with``).
Ruff bans ``os.replace`` and ``os.rename``; this test finds the method form ruff cannot
see, ``path.replace(target)`` or ``path.rename(target)``: a call of an attribute named
``replace`` or ``rename`` with one argument and no keywords (``str.replace`` takes two,
``dataclasses.replace`` keywords). A line marked ``# noqa: TID251`` carries its reason
beside it and is allowed.

A quantity is converted to or from a unit in one place, ``ithax.model.units`` (``UNIT_SIZES``,
``in_unit``; review of PR #165): a hand-written ``value * 3600`` overflows near 1e308, an
exact conversion does not. This test finds a product, quotient or remainder with 60, 3600 or
86400, and a unit symbol paired with such a size, anywhere else in ``src``. A line marked
``# unit factor:`` with its reason (a whole number of minutes from a setting, a constant) is
allowed.
"""

import ast
from pathlib import Path

import ithax

# The package as imported, so a moved or renamed package cannot leave the scans empty (#70).
SRC = Path(ithax.__file__).resolve().parent
HELPERS = {SRC / "strict_json.py"}
FILE_HELPERS = {SRC / "files.py"}
UNIT_HELPERS = {SRC / "model" / "units.py"}
UNIT_FACTORS = frozenset({60, 3600, 86400})
UNIT_SYMBOLS = frozenset({"s", "min", "h", "d", "1/s", "1/min", "1/h", "1/d"})
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
        "Use ithax.strict_json.is_whole, is_number or is_finite_real instead of a "
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


def renames(source: str) -> list[int]:
    """Lines of a ``path.replace(target)`` or ``path.rename(target)`` call not marked
    ``# noqa: TID251``."""
    lines = source.splitlines()
    found = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"replace", "rename"}
            and len(node.args) == 1
            and not node.keywords
            and "# noqa: TID251" not in lines[node.lineno - 1]
        ):
            found.append(node.lineno)
    return sorted(found)


def test_files_are_replaced_through_ithax_files() -> None:
    offenders = [
        f"{path.relative_to(SRC)}:{line}"
        for path in sorted(SRC.rglob("*.py"))
        if path not in FILE_HELPERS
        for line in renames(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        "Replace a file with ithax.files.atomic_write or atomic_write_with, not a "
        "hand-written rename: " + ", ".join(offenders)
    )


def test_the_rename_check_finds_the_method_forms_only() -> None:
    source = "\n".join(
        [
            "partial.replace(path)",  # 1
            "temporary.rename(path)",  # 2
            "text.replace('a', 'b')",  # 3: str.replace
            "dataclasses.replace(value, values=values)",  # 4: keywords
            "os.replace(a, b)  # noqa: TID251",  # 5: two arguments, and marked
            "aside.replace(path)  # noqa: TID251",  # 6: marked
            "value.replace(tzinfo=None)",  # 7: a keyword only
        ]
    )
    assert renames(source) == [1, 2]


def _is_factor(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Constant)
        and type(node.value) in (int, float)
        and node.value in UNIT_FACTORS
    )


def unit_factors(source: str) -> list[int]:
    """Lines that scale by a unit's size by hand: ``x * 3600``, ``x / 60``, ``x % 60``, or
    a pair such as ``("h", 3600)``; a line marked ``# unit factor:`` is allowed."""
    lines = source.splitlines()
    found: set[int] = set()
    for node in ast.walk(ast.parse(source)):
        hit = (
            isinstance(node, ast.BinOp)
            and isinstance(node.op, (ast.Mult, ast.Div, ast.FloorDiv, ast.Mod))
            and (_is_factor(node.left) or _is_factor(node.right))
        ) or (
            isinstance(node, ast.Tuple)
            and len(node.elts) == 2
            and isinstance(node.elts[0], ast.Constant)
            and node.elts[0].value in UNIT_SYMBOLS
            and _is_factor(node.elts[1])
        )
        if hit and "# unit factor:" not in lines[node.lineno - 1]:  # type: ignore[attr-defined]
            found.add(node.lineno)  # type: ignore[attr-defined]
    return sorted(found)


def test_quantities_are_converted_through_ithax_model_units() -> None:
    offenders = [
        f"{path.relative_to(SRC)}:{line}"
        for path in sorted(SRC.rglob("*.py"))
        if path not in UNIT_HELPERS
        for line in unit_factors(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        "Convert a quantity with ithax.model.units.in_unit and UNIT_SIZES, not by hand: "
        + ", ".join(offenders)
    )


def test_the_unit_factor_check_finds_hand_scaling_only() -> None:
    source = "\n".join(
        [
            "per_hour = rate * 3600",  # 1
            "minutes = seconds / 60",  # 2
            'units = (("d", 86_400.0), ("h", 3_600.0))',  # 3: two pairs, one line
            "left = seconds % 60",  # 4
            "limit = 7 * 24 * 3600.0  # unit factor: a constant",  # 5: marked
            "count = items * 61",  # 6: not a unit's size
            'shown = in_unit(rate, "1/h")',  # 7: the helper
            "flag = 60 == value",  # 8: a comparison
        ]
    )
    assert unit_factors(source) == [1, 2, 3, 4]
