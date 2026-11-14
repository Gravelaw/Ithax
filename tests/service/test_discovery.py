"""The discovery file and the probe (spec 3 "Discovery" and "One service per user";
AKS-110 acceptance: ``service.json`` written with mode 0600)."""

import json
import os
import stat
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn

from ithax.files import temporary_path
from ithax.service.app import create_app
from ithax.service.config import ServiceConfig
from ithax.service.discovery import (
    SERVICE_FILE,
    ServiceInfo,
    probe,
    read_service_file,
    remove_service_file,
    write_service_file,
)
from ithax.service.hardware import Hardware
from ithax.service.main import bind_local

INFO = ServiceInfo(port=41234, token="abc", pid=1234, started="2026-11-07T10:00:00.000Z")


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no 0600 mode bits")
def test_the_file_is_written_with_mode_0600(tmp_path: Path) -> None:
    old = os.umask(0o022)
    try:
        path = write_service_file(tmp_path / "config", INFO)
    finally:
        os.umask(old)
    assert path == tmp_path / "config" / SERVICE_FILE
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no 0600 mode bits")
def test_an_old_file_with_a_wider_mode_is_replaced_by_one_with_0600(tmp_path: Path) -> None:
    old_file = tmp_path / SERVICE_FILE
    old_file.write_text("{}", encoding="utf-8")
    old_file.chmod(0o644)
    write_service_file(tmp_path, INFO)
    assert stat.S_IMODE(old_file.stat().st_mode) == 0o600


def test_the_file_holds_the_four_fields(tmp_path: Path) -> None:
    write_service_file(tmp_path, INFO)
    assert json.loads((tmp_path / SERVICE_FILE).read_text(encoding="utf-8")) == {
        "port": 41234,
        "token": "abc",
        "pid": 1234,
        "started": "2026-11-07T10:00:00.000Z",
    }
    assert read_service_file(tmp_path) == INFO
    assert [path.name for path in tmp_path.iterdir()] == [SERVICE_FILE]


def test_a_leftover_temporary_file_is_replaced(tmp_path: Path) -> None:
    temporary_path(tmp_path / SERVICE_FILE).write_text("x", encoding="utf-8")
    write_service_file(tmp_path, INFO)
    assert read_service_file(tmp_path) == INFO
    assert [path.name for path in tmp_path.iterdir()] == [SERVICE_FILE]


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[]",
        '{"port": 1, "token": "t", "pid": 2}',
        '{"port": "1", "token": "t", "pid": 2, "started": "s"}',
        '{"port": true, "token": "t", "pid": 2, "started": "s"}',
        '{"port": 1, "token": 5, "pid": 2, "started": "s"}',
        '{"port": 1, "token": "t", "pid": 2, "started": "s", "extra": 1}',
    ],
)
def test_a_file_that_does_not_hold_the_fields_is_none(tmp_path: Path, text: str) -> None:
    (tmp_path / SERVICE_FILE).write_text(text, encoding="utf-8")
    assert read_service_file(tmp_path) is None


def test_a_missing_file_is_none(tmp_path: Path) -> None:
    assert read_service_file(tmp_path) is None


def test_the_file_is_removed_only_while_it_names_this_service(tmp_path: Path) -> None:
    write_service_file(tmp_path, INFO)
    other = ServiceInfo(port=1, token="other", pid=99, started=INFO.started)
    assert not remove_service_file(tmp_path, other)
    assert read_service_file(tmp_path) == INFO
    assert remove_service_file(tmp_path, INFO)
    assert not (tmp_path / SERVICE_FILE).exists()
    assert not remove_service_file(tmp_path, INFO)


# --- the probe, against a real server ---------------------------------------------------


@pytest.fixture
def running(tmp_path: Path) -> Iterator[ServiceInfo]:
    """A real service on 127.0.0.1 in a thread, its info as service.json would hold it."""
    with bind_local() as sock:
        port = sock.getsockname()[1]
        config = ServiceConfig(
            config_dir=tmp_path / "config",
            data_dir=tmp_path / "data",
            port=port,
            token="real-token",
            hardware=Hardware(4, None, None),
        )
        server = uvicorn.Server(
            uvicorn.Config(create_app(config), log_level="warning", ws="websockets-sansio")
        )
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]})
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.01)
            yield ServiceInfo(port=port, token="real-token", pid=os.getpid(), started="now")
        finally:
            server.should_exit = True
            thread.join(10)


def test_the_probe_finds_a_service_that_answers(running: ServiceInfo) -> None:
    assert probe(running)


def test_the_probe_ignores_proxy_settings(
    running: ServiceInfo, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:9")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    assert probe(running)


def test_the_probe_does_not_count_a_service_with_another_token(running: ServiceInfo) -> None:
    other = ServiceInfo(running.port, "stale-token", running.pid, running.started)
    assert not probe(other)


def test_the_probe_finds_nothing_on_a_closed_port() -> None:
    with bind_local() as sock:
        port = sock.getsockname()[1]
    assert not probe(ServiceInfo(port, "t", 1, "s"), timeout_s=0.5)


@pytest.mark.parametrize("port", [0, 70000])
def test_the_probe_refuses_an_impossible_port(port: int) -> None:
    assert not probe(ServiceInfo(port, "t", 1, "s"))
