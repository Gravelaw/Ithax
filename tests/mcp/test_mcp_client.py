"""The MCP server's service client (spec 4 "How the server runs and answers"; spec 3
"Discovery", "One service per user", "Lifetime" and "Client header"; AKS-115).

The client finds the service through ``service.json`` and the spec 3 probe, starts
``python -m lcsim.service`` when none answers, sends every request to ``/v1`` on
``127.0.0.1`` with the token and ``X-Client: mcp`` and no proxy, reads every answer with the
strict JSON reader, repeats a request only when its connection was refused or it was
answered 401, and reports a service it cannot reach as E193.
"""

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from mcp_support import DROP, StubService, in_process_service, stop_service

from lcsim.mcp.client import (
    CLIENT,
    SERVICE_UNAVAILABLE,
    START_TIMEOUT_S,
    Answer,
    ServiceClient,
    ServiceUnavailable,
    detached_options,
)
from lcsim.service.discovery import ServiceInfo, probe, read_service_file, write_service_file
from lcsim.service.main import STARTUP_WAIT_S


@pytest.fixture
def folders(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "config", tmp_path / "data"


@pytest.fixture
def stub(folders: tuple[Path, Path]) -> Iterator[StubService]:
    service = StubService(folders[0])
    service.start()
    yield service
    service.stop()


@pytest.fixture
def stub_client(folders: tuple[Path, Path], stub: StubService) -> ServiceClient:
    # A command that cannot start a service, so a test never starts one by accident.
    return ServiceClient(*folders, command=[sys.executable, "-c", "raise SystemExit(3)"])


def closed_port() -> int:
    """A port nothing listens on."""
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


# --- requests: the API, the headers, the strict reader ------------------------------------


def test_a_request_goes_to_v1_with_the_token_and_x_client_mcp(
    stub: StubService, stub_client: ServiceClient
) -> None:
    stub.answer(200, {"ok": True})
    answer = stub_client.request("GET", "/v1/projects")
    assert answer == Answer(status=200, body={"ok": True})
    [request] = stub.requests
    assert (request.method, request.path) == ("GET", "/v1/projects")
    assert request.headers["Authorization"] == f"Bearer {stub.token}"
    assert request.headers["X-Client"] == CLIENT == "mcp"
    info = read_service_file(stub.config_dir)
    assert info is not None and request.headers["Host"] == f"127.0.0.1:{info.port}"
    assert request.body == b""


def test_a_json_body_is_sent_as_json(stub: StubService, stub_client: ServiceClient) -> None:
    stub_client.request("POST", "/v1/projects", {"name": "Café"})
    [request] = stub.requests
    assert request.headers["Content-Type"] == "application/json"
    assert json.loads(request.body) == {"name": "Café"}


def test_a_path_outside_v1_is_refused_before_anything_is_sent(
    stub: StubService, stub_client: ServiceClient
) -> None:
    for path in ("/v2/projects", "v1/projects", "http://example.com/v1/x", "/v1"):
        with pytest.raises(ValueError, match="/v1/"):
            stub_client.request("GET", path)
    assert stub.requests == [] and stub.probes == 0


def test_an_error_status_is_an_answer_with_its_body(
    stub: StubService, stub_client: ServiceClient
) -> None:
    body = {"error": {"code": "E185", "message": "There is no project 'x'."}, "issues": []}
    stub.answer(404, body)
    assert stub_client.request("GET", "/v1/projects/x/model") == Answer(404, body)


def test_a_redirect_is_not_followed(stub: StubService, stub_client: ServiceClient) -> None:
    stub.answer(307, {"moved": True}, {"Location": "/v1/elsewhere"})
    assert stub_client.request("GET", "/v1/projects") == Answer(307, {"moved": True})
    assert [request.path for request in stub.requests] == ["/v1/projects"]


def test_no_proxy_is_used(
    stub: StubService, stub_client: ServiceClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.setenv(name, f"http://127.0.0.1:{closed_port()}")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    assert stub_client.request("GET", "/v1/projects").status == 200


@pytest.mark.parametrize(
    "raw", [b"", b"not json", b"[NaN]", b'{"a": 1e999}', b'"\\ud800"', b"\xff\xfe"]
)
def test_an_answer_the_strict_reader_refuses_is_e193(
    stub: StubService, stub_client: ServiceClient, raw: bytes
) -> None:
    stub.answer(200, raw)
    with pytest.raises(ServiceUnavailable) as caught:
        stub_client.request("GET", "/v1/projects")
    assert caught.value.code == SERVICE_UNAVAILABLE == "E193"
    assert "could not be read" in caught.value.message
    assert len(stub.requests) == 1


def test_a_dropped_connection_is_e193_and_the_request_is_not_repeated(
    stub: StubService, stub_client: ServiceClient
) -> None:
    stub.answers.append(DROP)
    with pytest.raises(ServiceUnavailable) as caught:
        stub_client.request("POST", "/v1/projects", {"name": "once"})
    assert "did not answer" in caught.value.message
    assert len(stub.requests) == 1


def test_a_request_that_times_out_is_e193_and_not_repeated(
    folders: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    import socket
    import threading

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    port = listener.getsockname()[1]
    accepted: list[socket.socket] = []
    seen: list[bytes] = []

    def serve() -> None:
        # Answers each probe and then holds the next connection open without answering.
        while True:
            try:
                connection, _ = listener.accept()
            except OSError:
                return
            accepted.append(connection)
            data = connection.recv(65536)
            seen.append(data)
            if data.startswith(b"GET /v1/system "):
                connection.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}")
                connection.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    write_service_file(folders[0], ServiceInfo(port, "t" * 43, 0, "2026-11-08T00:00:00Z"))
    client = ServiceClient(*folders, request_timeout_s=0.5, command=["unused"])
    try:
        with pytest.raises(ServiceUnavailable) as caught:
            client.request("GET", "/v1/projects")
    finally:
        listener.close()
        for connection in accepted:
            connection.close()
    assert "did not answer" in caught.value.message
    assert sum(data.startswith(b"GET /v1/projects ") for data in seen) == 1


def test_a_connection_that_fails_while_sending_is_e193_and_not_repeated(
    stub: StubService, stub_client: ServiceClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import urllib.error

    opened: list[object] = []

    def reset(request: object, timeout: float) -> None:
        opened.append(request)
        raise urllib.error.URLError(ConnectionResetError("reset while sending"))

    monkeypatch.setattr(stub_client._opener, "open", reset)
    with pytest.raises(ServiceUnavailable) as caught:
        stub_client.request("POST", "/v1/projects", {"name": "once"})
    assert "did not answer" in caught.value.message
    assert len(opened) == 1


# --- finding the service again: a refused connection, a stale token ----------------------


def test_a_refused_connection_finds_the_service_again_and_repeats_once(
    folders: tuple[Path, Path], stub: StubService, stub_client: ServiceClient
) -> None:
    stub_client.request("GET", "/v1/projects")
    stub.stop()
    replacement = StubService(folders[0], token="another-token-0123456789")
    replacement.start()
    try:
        replacement.answer(200, ["second"])
        assert stub_client.request("GET", "/v1/projects") == Answer(200, ["second"])
    finally:
        replacement.stop()
    assert len(replacement.requests) == 1


def test_a_request_refused_twice_is_e193(
    stub: StubService, stub_client: ServiceClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[ServiceInfo] = []

    def refused(info: ServiceInfo, method: str, path: str, body: object) -> None:
        calls.append(info)
        return None

    monkeypatch.setattr(stub_client, "_send", refused)
    with pytest.raises(ServiceUnavailable) as caught:
        stub_client.request("GET", "/v1/projects")
    assert "did not answer" in caught.value.message
    assert len(calls) == 2


def test_a_401_finds_the_service_again_and_repeats_once(
    stub: StubService, stub_client: ServiceClient
) -> None:
    stub.answer(401, {"error": {"code": "E182", "message": "stale"}, "issues": []})
    stub.answer(200, {"second": True})
    assert stub_client.request("GET", "/v1/projects") == Answer(200, {"second": True})
    assert len(stub.requests) == 2


def test_a_second_401_is_returned_as_the_answer(
    stub: StubService, stub_client: ServiceClient
) -> None:
    refusal = {"error": {"code": "E182", "message": "The token is missing or wrong."}}
    stub.answer(401, refusal)
    stub.answer(401, refusal)
    assert stub_client.request("GET", "/v1/projects") == Answer(401, refusal)
    assert len(stub.requests) == 2


def test_the_service_found_is_kept_for_later_requests(
    stub: StubService, stub_client: ServiceClient
) -> None:
    for _ in range(3):
        stub_client.request("GET", "/v1/projects")
    assert stub.probes == 1


# --- starting the service on demand --------------------------------------------------------


def test_the_service_command_passes_both_folders(folders: tuple[Path, Path]) -> None:
    client = ServiceClient(*folders)
    config_dir, data_dir = (folder.resolve() for folder in folders)
    assert client.config_dir == config_dir and client.data_dir == data_dir
    assert client.command == [
        sys.executable,
        "-m",
        "lcsim.service",
        "--config-dir",
        str(config_dir),
        "--data-dir",
        str(data_dir),
    ]


def test_the_start_timeout_outlasts_a_second_start_waiting_for_the_first() -> None:
    # spec 4: 30 s; a second start of the service waits up to STARTUP_WAIT_S for the first.
    assert START_TIMEOUT_S == 30.0 > STARTUP_WAIT_S


def test_a_missing_service_json_starts_the_service(folders: tuple[Path, Path]) -> None:
    client = ServiceClient(*folders)
    try:
        answer = client.request("GET", "/v1/system")
        assert answer.status == 200
        assert isinstance(answer.body, dict) and answer.body["cores"] >= 1
        info = read_service_file(folders[0])
        assert client.started is not None and info is not None
        assert info.pid == client.started.pid
        # The service is a separate session or process group, so it outlives this one.
        if os.name != "nt":
            assert os.getsid(info.pid) == info.pid != os.getsid(0)
        # Later requests use the service found.
        assert client.request("GET", "/v1/projects") == Answer(200, [])
    finally:
        stop_service(folders[0], client.started)


def test_a_service_json_whose_service_is_gone_starts_a_new_one(
    folders: tuple[Path, Path],
) -> None:
    write_service_file(folders[0], ServiceInfo(closed_port(), "x" * 43, 1, "2026-11-08T00:00:00Z"))
    client = ServiceClient(*folders)
    try:
        assert client.request("GET", "/v1/templates") == Answer(200, [])
        info = read_service_file(folders[0])
        assert client.started is not None and info is not None and info.pid == client.started.pid
    finally:
        stop_service(folders[0], client.started)


def test_a_running_service_is_used_and_none_is_started(folders: tuple[Path, Path]) -> None:
    with in_process_service(*folders):
        client = ServiceClient(*folders, command=[sys.executable, "-c", "raise SystemExit(3)"])
        assert client.request("GET", "/v1/projects") == Answer(200, [])
        assert client.started is None


def test_two_clients_starting_at_once_give_one_service(folders: tuple[Path, Path]) -> None:
    import threading

    clients = [ServiceClient(*folders) for _ in range(2)]
    answers: list[Answer] = []
    threads = [
        threading.Thread(target=lambda c=c: answers.append(c.request("GET", "/v1/system")))
        for c in clients
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(120)
    try:
        assert [answer.status for answer in answers] == [200, 200]
        info = read_service_file(folders[0])
        assert info is not None
        started = [c.started for c in clients if c.started is not None]
        assert info.pid in [process.pid for process in started]
        # The other start, if any, found the first and exited with status 0.
        for process in started:
            if process.pid != info.pid:
                assert process.wait(60) == 0
    finally:
        for c in clients:
            stop_service(folders[0], c.started)


def test_a_service_that_exits_with_an_error_is_e193(folders: tuple[Path, Path]) -> None:
    client = ServiceClient(*folders, command=[sys.executable, "-c", "raise SystemExit(1)"])
    with pytest.raises(ServiceUnavailable) as caught:
        client.request("GET", "/v1/projects")
    assert caught.value.code == "E193"
    assert "could not be started" in caught.value.message


def test_a_command_that_cannot_run_is_e193(folders: tuple[Path, Path], tmp_path: Path) -> None:
    client = ServiceClient(*folders, command=[str(tmp_path / "no-such-program")])
    with pytest.raises(ServiceUnavailable) as caught:
        client.request("GET", "/v1/projects")
    assert "could not be started" in caught.value.message


def test_a_service_that_never_answers_is_e193_after_the_start_timeout(
    folders: tuple[Path, Path],
) -> None:
    client = ServiceClient(
        *folders,
        command=[sys.executable, "-c", "import time; time.sleep(60)"],
        start_timeout_s=0.5,
    )
    try:
        with pytest.raises(ServiceUnavailable) as caught:
            client.request("GET", "/v1/projects")
        assert "did not answer within 0.5 s" in caught.value.message
    finally:
        assert client.started is not None
        client.started.kill()
        client.started.wait(60)


def test_a_start_that_exits_cleanly_finds_the_service_it_deferred_to(
    folders: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    # A second start exits with 0 once the first answers (spec 3); the client then finds
    # that first service through service.json.
    with in_process_service(*folders) as info:
        probes: list[ServiceInfo] = []
        real_probe = probe

        def first_probe_fails(found: ServiceInfo) -> bool:
            probes.append(found)
            return len(probes) > 1 and real_probe(found)

        monkeypatch.setattr("lcsim.mcp.client.probe", first_probe_fails)
        client = ServiceClient(*folders, command=[sys.executable, "-c", "pass"])
        assert client.request("GET", "/v1/projects") == Answer(200, [])
        assert client.started is not None and client.started.wait(60) == 0
        assert probes[-1] == info


# --- the issue -----------------------------------------------------------------------------


def test_service_unavailable_gives_one_e193_issue_and_an_error_body() -> None:
    problem = ServiceUnavailable("The engine service did not answer.", "Try again.")
    issue = problem.issue()
    assert issue.as_dict() == {
        "code": "E193",
        "severity": "error",
        "component": None,
        "path": "",
        "message": "The engine service did not answer.",
        "hint": "Try again.",
    }
    assert problem.body() == {
        "error": {"code": "E193", "message": "The engine service did not answer."},
        "issues": [issue.as_dict()],
    }


# --- platform-neutral start ----------------------------------------------------------------


def test_detached_options_on_posix_start_a_new_session() -> None:
    assert detached_options("posix") == {"start_new_session": True}


def test_detached_options_on_windows_detach_into_a_new_process_group() -> None:
    # DETACHED_PROCESS (0x8) and CREATE_NEW_PROCESS_GROUP (0x200), Windows process
    # creation flags.
    assert detached_options("nt") == {"creationflags": 0x00000008 | 0x00000200}


def test_detached_options_default_to_this_platform() -> None:
    assert detached_options() == detached_options(os.name)


def test_the_service_is_started_with_its_output_discarded(
    folders: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, object] = {}

    class Refused(OSError):
        pass

    def popen(command: list[str], **options: object) -> subprocess.Popen[bytes]:
        seen.update(options, command=command)
        raise Refused

    monkeypatch.setattr("lcsim.mcp.client.subprocess.Popen", popen)
    client = ServiceClient(*folders)
    with pytest.raises(ServiceUnavailable):
        client.request("GET", "/v1/projects")
    assert seen["command"] == client.command
    for stream in ("stdin", "stdout", "stderr"):
        assert seen[stream] == subprocess.DEVNULL
    assert {key: seen[key] for key in detached_options()} == detached_options()
