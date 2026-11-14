"""Spec 3 acceptance, M6: "Route table test" (AKS-114).

Spec 3 "Endpoints": "`tests/service/test_routes.py` lists the application's routes and
asserts the set equals this table, both ways; each row also has at least one request test."

The table is read from ``docs/specs/3-desktop-app.md`` when the test runs, so the spec stays
the source of truth (as ``tests/test_docs.py`` reads the guide). The application's routes
are ``ithax.service.app.route_table``: a WebSocket route is listed as ``GET``, as the table
writes ``GET /v1/runs/{rid}/events``.

"Each row also has at least one request test" is shown by the routes the session's request
tests reached (``route_recorder.py``): every ``TestClient`` in ``tests/service/`` records the
``(method, path template)`` the router matched, and the last test of the session asserts
that every row was reached. When the session did not run every service test (a single
file, ``-k``, a deselection), that test runs ``tests/service`` in a separate pytest process
and reads its record instead, so the check never depends on which tests happened to run.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI

import xdist_routes
from ithax.service.app import route_table
from service import route_recorder
from service.conftest import COVERAGE_TEST
from service.endpoint_table import ROOT, SPEC_3, route_problems, spec_routes, spec_table
from service.route_check import controller_route_problems


def test_the_endpoint_table_is_read_from_spec_3() -> None:
    rows = spec_routes(SPEC_3.read_text(encoding="utf-8"))
    # The table of spec 3 has 29 rows since AKS-138 (28 since AKS-119, 25 at 0.4); the count
    # guards the parser, not the spec: a row added to the spec changes it, and with it this
    # number.
    assert len(rows) == 29
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
            # One process, so that its record holds every request test (#99, P1).
            "-p",
            "no:xdist",
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
    """Under pytest-xdist each worker sees only its own requests, so a complete run hands the
    check to the controller (``tests/xdist_routes.py``), which reads every worker's record after
    all of them have finished (#99, P1)."""
    assert request.node.name == COVERAGE_TEST
    workerinput = getattr(request.config, "workerinput", None)
    if route_recorder.INCOMPLETE:
        recorded = fallback_record(tmp_path, request.node.nodeid)
    elif workerinput is not None:
        assert route_recorder.RECORD_DIR_KEY in workerinput, (
            "under pytest-xdist without the controller's route check (tests/xdist_routes.py)"
        )
        route_recorder.DEFERRED.append(request.node.nodeid)
        return
    else:
        recorded = set(route_recorder.RECORDED)
    problems = route_problems(recorded, spec_table(), route_table(app))
    assert not problems, "; ".join(problems)


def test_route_problems_names_each_gap() -> None:
    table = {("GET", "/v1/system"), ("POST", "/v1/projects")}
    app_routes = table | {("GET", "/v1/hidden")}
    assert route_problems(set(), table, app_routes) == [
        "no request reached any route: the recorder is not installed"
    ]
    assert route_problems(table | {("GET", "/own")}, table, app_routes) == []
    assert route_problems({("GET", "/v1/system")}, table, app_routes) == [
        "endpoint rows with no request test: [('POST', '/v1/projects')]"
    ]
    assert route_problems(table | {("GET", "/v1/hidden")}, table, app_routes) == [
        "product routes reached that the table does not list: [('GET', '/v1/hidden')]"
    ]


def test_the_controller_checks_only_when_a_coverage_test_handed_over(tmp_path: Path) -> None:
    """The controller's half under pytest-xdist (tests/xdist_routes.py; #99, P1)."""
    table = spec_table()
    rows = sorted(table)
    half = len(rows) // 2
    # No worker's coverage test ran (a subset such as `pytest -n 4 tests/model`): no check.
    route_recorder.write_worker_record(tmp_path, "gw0", set(rows[:1]), [])
    assert controller_route_problems(tmp_path, 1) == []
    # Two workers between them reached every row: nothing to report.
    route_recorder.write_worker_record(tmp_path, "gw0", set(rows[:half]), [])
    route_recorder.write_worker_record(tmp_path, "gw1", set(rows[half:]), ["test_routes"])
    assert controller_route_problems(tmp_path, 2) == []
    # A worker that wrote no record is reported, not passed over.
    assert controller_route_problems(tmp_path, 3) == [
        "only 2 of 3 pytest-xdist workers wrote a route record"
    ]
    # A row no worker reached fails the check.
    route_recorder.write_worker_record(tmp_path, "gw1", set(rows[half:-1]), ["test_routes"])
    assert controller_route_problems(tmp_path, 2) == [
        f"endpoint rows with no request test: {[rows[-1]]}"
    ]


def test_the_controller_fails_the_session_and_says_why() -> None:
    lines: list[tuple[str, bool]] = []

    class Reporter:
        def write_sep(self, sep: str, title: str, red: bool) -> None:
            lines.append((title, red))

        def write_line(self, line: str, red: bool) -> None:
            lines.append((line, red))

    class Plugins:
        def get_plugin(self, name: str) -> Reporter | None:
            return Reporter() if name == "terminalreporter" else None

    class Config:
        pluginmanager = Plugins()

    class Session:
        config = Config()
        exitstatus: int | pytest.ExitCode = pytest.ExitCode.OK

    session = Session()
    xdist_routes.report(session, ["endpoint rows with no request test: [('GET', '/v1/x')]"])  # type: ignore[arg-type]
    assert session.exitstatus == pytest.ExitCode.TESTS_FAILED
    assert lines == [
        ("route check failed (tests/xdist_routes.py)", True),
        ("endpoint rows with no request test: [('GET', '/v1/x')]", True),
    ]
