"""Fixtures for the service tests (spec 3; AKS-110).

Every test gets a ``ServiceConfig`` with temporary configuration and data folders, a fixed
port and token and fixed hardware, and an in-process ``TestClient`` whose requests carry
the right ``Host`` and token. Tests that need a route the product does not have (the
WebSocket token helper, a project lookup, an unexpected failure) add it to their own
app instance with ``app.get`` or ``app.websocket``, never to a product router, which every
app shares.

Every ``TestClient`` of the session records the routes its requests reach
(``route_recorder.py``; AKS-114), so ``test_routes.py`` can show that every row of spec 3's
endpoint table has a request test. The hooks below move that test to the end of the session
and note when the session does not run every service test, in which case the test makes its
own record in a separate run.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from ithax.service.app import create_app
from ithax.service.config import ServiceConfig
from ithax.service.hardware import Hardware
from service import route_recorder
from service.service_support import AUTH, BASE_URL, PORT, TOKEN

SERVICE_TESTS = Path(__file__).resolve().parent
#: The test that reads the session's record; it must run after every other service test.
COVERAGE_TEST = "test_every_row_of_the_endpoint_table_has_a_request_test"


def _is_service_test(item: pytest.Item) -> bool:
    return Path(str(item.path)).resolve().parent == SERVICE_TESTS


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Moves the coverage test to the end of the session."""
    last = [item for item in items if item.name == COVERAGE_TEST and _is_service_test(item)]
    items[:] = [item for item in items if item not in last] + last


def pytest_deselected(items: list[pytest.Item]) -> None:
    deselected = [item.nodeid for item in items if _is_service_test(item)]
    if deselected:
        route_recorder.INCOMPLETE.append(f"{len(deselected)} service tests deselected")


def pytest_collection_finish(session: pytest.Session) -> None:
    collected = {Path(str(item.path)).resolve() for item in session.items if _is_service_test(item)}
    missing = sorted(
        path.name for path in SERVICE_TESTS.glob("test_*.py") if path.resolve() not in collected
    )
    if missing:
        route_recorder.INCOMPLETE.append(f"service test modules not run: {', '.join(missing)}")


def pytest_sessionfinish(session: pytest.Session) -> None:
    record = os.environ.get(route_recorder.RECORD_FILE_VARIABLE)
    if record:
        route_recorder.write_record(Path(record), route_recorder.RECORDED)
    # A pytest-xdist worker: its record goes to the controller's folder (tests/xdist_routes.py).
    workerinput = getattr(session.config, "workerinput", None)
    if workerinput is not None and route_recorder.RECORD_DIR_KEY in workerinput:
        route_recorder.write_worker_record(
            Path(workerinput[route_recorder.RECORD_DIR_KEY]),
            workerinput["workerid"],
            route_recorder.RECORDED,
            route_recorder.DEFERRED,
        )


@pytest.fixture(scope="session", autouse=True)
def record_routes() -> Iterator[None]:
    """Every ``TestClient`` of the session records the routes it reaches."""
    with pytest.MonkeyPatch.context() as patch:
        route_recorder.install(patch)
        yield


@pytest.fixture
def config(tmp_path: Path) -> ServiceConfig:
    return ServiceConfig(
        config_dir=tmp_path / "config",
        data_dir=tmp_path / "data",
        port=PORT,
        token=TOKEN,
        hardware=Hardware(cores=8, memory=16 * 1024**3, graphics=("intel",)),
    )


@pytest.fixture
def app(config: ServiceConfig) -> FastAPI:
    return create_app(config)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, base_url=BASE_URL, headers=AUTH) as test_client:
        yield test_client
