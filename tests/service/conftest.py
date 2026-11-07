"""Fixtures for the service tests (spec 3; AKS-110).

Every test gets a ``ServiceConfig`` with temporary configuration and data folders, a fixed
port and token and fixed hardware, and an in-process ``TestClient`` whose requests carry
the right ``Host`` and token. Tests that need a route the product does not have (the
WebSocket token helper, a project lookup, an unexpected failure) add it to their own
app instance with ``app.get`` or ``app.websocket``, never to a product router, which every
app shares.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from lcsim.service.app import create_app
from lcsim.service.config import ServiceConfig
from lcsim.service.hardware import Hardware
from service.service_support import AUTH, BASE_URL, PORT, TOKEN


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
