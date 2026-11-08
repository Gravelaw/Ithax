"""Spec 3 acceptance, M6: "Route table test" (AKS-114).

Spec 3 "Endpoints": "`tests/service/test_routes.py` lists the application's routes and
asserts the set equals this table, both ways; each row also has at least one request test."

The table is read from ``docs/specs/3-desktop-app.md`` when the test runs, so the spec stays
the source of truth (as ``tests/test_docs.py`` reads the guide). The application's routes
are ``lcsim.service.app.route_table``: a WebSocket route is listed as ``GET``, as the table
writes ``GET /v1/runs/{rid}/events``.

"Each row also has at least one request test" is shown by the routes the session's request
tests reached (``route_recorder.py``): every ``TestClient`` in ``tests/service/`` records the
``(method, path template)`` the router matched, and the last test of the session asserts
that every row was reached. When the session did not run every service test (a single
file, ``-k``, a deselection), that test runs ``tests/service`` in a separate pytest process
and reads its record instead, so the check never depends on which tests happened to run.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI

from lcsim.service.app import route_table
from service import route_recorder
from service.conftest import COVERAGE_TEST

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


def test_the_endpoint_table_is_read_from_spec_3() -> None:
    rows = spec_routes(SPEC_3.read_text(encoding="utf-8"))
    # The table of spec 3 0.4 has 25 rows; the count guards the parser, not the spec: a
    # row added to the spec changes it, and with it this number.
    assert len(rows) == 25
    assert rows[0] == ("GET", "/v1/system")
    assert rows[-1] == ("GET", "/v1/runs/{rid}/tables/{name}")
    assert ("GET", "/v1/projects/{pid}/events") in rows


def test_the_parser_reads_only_the_endpoint_table() -> None:
    text = "\n".join(
        [
            "| `GET /v1/elsewhere` | | |",
            "### Endpoints",
            "| Method and path | Request | Response |",
            "| --- | --- | --- |",
            "| `GET /v1/system` |  | Cores |",
            "| `POST /v1/projects/{pid}/data/{file}/fit` | `{column}` | Candidates |",
            "Notes: `PUT /v1/not-a-row` is prose.",
            "### Model edits",
            "| `DELETE /v1/after` | | |",
        ]
    )
    assert spec_routes(text) == [
        ("GET", "/v1/system"),
        ("POST", "/v1/projects/{pid}/data/{file}/fit"),
    ]


def test_every_route_of_the_app_is_a_row_of_the_table(app: FastAPI) -> None:
    extra = route_table(app) - spec_table()
    assert not extra, f"routes the spec 3 endpoint table does not list: {sorted(extra)}"


def test_every_row_of_the_table_is_a_route_of_the_app(app: FastAPI) -> None:
    missing = spec_table() - route_table(app)
    assert not missing, f"spec 3 endpoint rows the app does not serve: {sorted(missing)}"


def test_the_app_s_route_set_equals_the_table(app: FastAPI) -> None:
    assert route_table(app) == spec_table()


def fallback_record(tmp_path: Path, own_test: str) -> set[tuple[str, str]]:
    """The routes reached by every other service test, run in a separate pytest process."""
    record = tmp_path / "routes.json"
    environment = {**os.environ, route_recorder.RECORD_FILE_VARIABLE: str(record)}
    finished = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/service",
            "-q",
            "-p",
            "no:cacheprovider",
            "--deselect",
            own_test,
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )
    assert finished.returncode == 0, finished.stdout[-4000:] + finished.stderr[-4000:]
    return route_recorder.read_record(record)


def test_every_row_of_the_endpoint_table_has_a_request_test(
    app: FastAPI, tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    assert request.node.name == COVERAGE_TEST
    if route_recorder.INCOMPLETE:
        recorded = fallback_record(tmp_path, request.node.nodeid)
    else:
        recorded = set(route_recorder.RECORDED)
    table = spec_table()
    assert recorded, "no request reached any route: the recorder is not installed"
    unreached = table - recorded
    assert not unreached, f"endpoint rows with no request test: {sorted(unreached)}"
    # Whatever else was reached is a test's own route, never a product route off the table.
    assert recorded & route_table(app) == table
