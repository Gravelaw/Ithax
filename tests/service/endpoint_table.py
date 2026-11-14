"""Spec 3's "Endpoints" table, read from ``docs/specs/3-desktop-app.md`` (AKS-114).

Shared by ``test_routes.py`` and by the controller's route check in ``tests/xdist_routes.py``,
which runs after every pytest-xdist worker has finished (#99, P1).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC_3 = ROOT / "docs" / "specs" / "3-desktop-app.md"

#: A row of the "Endpoints" table: its first cell is a method and a path in backquotes.
ROW = re.compile(r"^\| `(GET|POST|PUT|PATCH|DELETE) (/[^`\s]*)` \|", re.MULTILINE)


def endpoint_section(text: str) -> str:
    """The text of spec 3's "### Endpoints" section, up to the next heading."""
    start = text.index("\n### Endpoints\n")
    end = text.index("\n### ", start + 1)
    return text[start:end]


def spec_routes(text: str) -> list[tuple[str, str]]:
    """The ``(method, path)`` of each row of the endpoint table, in table order."""
    return ROW.findall(endpoint_section(text))


def spec_table() -> set[tuple[str, str]]:
    rows = spec_routes(SPEC_3.read_text(encoding="utf-8"))
    assert len(rows) == len(set(rows)), "a row of spec 3's endpoint table is written twice"
    return set(rows)


def route_problems(
    recorded: set[tuple[str, str]],
    table: set[tuple[str, str]],
    app_routes: set[tuple[str, str]],
) -> list[str]:
    """Why ``recorded`` does not show a request test for every row of ``table``; empty when
    it does."""
    if not recorded:
        return ["no request reached any route: the recorder is not installed"]
    problems: list[str] = []
    unreached = table - recorded
    if unreached:
        problems.append(f"endpoint rows with no request test: {sorted(unreached)}")
    # Whatever else was reached is a test's own route, never a product route off the table.
    off_table = (recorded & app_routes) - table
    if off_table:
        problems.append(f"product routes reached that the table does not list: {sorted(off_table)}")
    return problems
