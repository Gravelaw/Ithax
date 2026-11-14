"""The controller's half of the route check under pytest-xdist (#99; P1 of
docs/retrospective/proposed-agent-setup.md), loaded as a plugin (``-p xdist_routes`` in
``pyproject.toml``, with ``tests`` on ``pythonpath``).

Spec 3 asks that every row of the endpoint table has a request test, which
``tests/service/test_routes.py`` shows from the routes the session's ``TestClient``s reached.
Under pytest-xdist each worker reaches only its own share, and the controller loads no
conftest below ``tests/``. So this plugin:

- gives every worker a folder to write its record to (``pytest_configure_node``);
- once every worker has finished, and only if a worker's coverage test handed the check over,
  reads the records, checks their union, and fails the session if a row was not reached
  (``pytest_sessionfinish``).

Without pytest-xdist, or with ``-n 0``, nothing here acts and the coverage test checks its own
session, as before. It is a plugin rather than ``tests/conftest.py`` because the process
adapter's tests import ``tests/engines/process/conftest.py`` as ``conftest``, which a second
top-level ``conftest`` module would shadow (and mypy refuses two). Nothing from ``ithax`` is
imported until the session ends, so loading the plugin before coverage starts costs no
coverage.
"""

import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

#: The ``workerinput`` key naming the folder the workers write their route records to.
RECORD_DIR_KEY = "ithax_route_record_dir"

#: The controller's record folder and the number of workers it was given to.
_FOLDER = pytest.StashKey[Path]()
_WORKERS = pytest.StashKey[int]()


def _record_folder(config: pytest.Config) -> Path:
    if _FOLDER not in config.stash:
        config.stash[_FOLDER] = Path(tempfile.mkdtemp(prefix="ithax-routes-"))
        config.stash[_WORKERS] = 0
    return config.stash[_FOLDER]


@pytest.hookimpl(optionalhook=True)
def pytest_configure_node(node: Any) -> None:
    """pytest-xdist calls this in the controller once for each worker it starts."""
    folder = _record_folder(node.config)
    node.workerinput[RECORD_DIR_KEY] = str(folder)
    node.config.stash[_WORKERS] += 1


def report(session: pytest.Session, problems: list[str]) -> None:
    """Fails the session with ``problems``, written to the terminal."""
    session.exitstatus = pytest.ExitCode.TESTS_FAILED
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_sep("=", "route check failed (tests/xdist_routes.py)", red=True)
        for problem in problems:
            reporter.write_line(problem, red=True)


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session: pytest.Session) -> None:
    config = session.config
    if getattr(config, "workerinput", None) is not None or _FOLDER not in config.stash:
        return
    folder = config.stash[_FOLDER]
    try:
        from service.route_check import controller_route_problems

        problems = controller_route_problems(folder, config.stash[_WORKERS])
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    if problems:
        report(session, problems)
