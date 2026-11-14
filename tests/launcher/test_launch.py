"""``python -m ithax.launcher`` (spec 3 "Service rules", Launcher; AKS-119).

The launcher finds a running service through ``service.json``, starts one detached when none
answers (also when the file is left from a service that has gone), waits for it, and opens
or prints the interface's address with the token in its fragment.
"""

import contextlib
import io
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx2
import pytest

import ithax.launcher.launch as launcher
from ithax.launcher.launch import (
    LOG_FILE,
    detach_options,
    interface_url,
    main,
    service_command,
    wait_until_ready,
)
from ithax.service.discovery import SERVICE_FILE, ServiceInfo, read_service_file, write_service_file


def stop(info: ServiceInfo, config_dir: Path) -> None:
    """Stop a service the launcher started, wait until its file is gone, and reap it."""
    with contextlib.suppress(ProcessLookupError):
        os.kill(info.pid, signal.SIGTERM)
    deadline = time.monotonic() + 30
    while (config_dir / SERVICE_FILE).exists():
        assert time.monotonic() < deadline, "the service did not stop"
        time.sleep(0.05)
    for process in [process for process in launcher.DETACHED if process.pid == info.pid]:
        process.wait(timeout=30)
        launcher.DETACHED.remove(process)


class Run:
    """``main`` with its output captured."""

    def __init__(self, argv: list[str], opener: object = None) -> None:
        self.out = io.StringIO()
        self.err = io.StringIO()
        kwargs = {} if opener is None else {"opener": opener}
        self.status = main(argv, out=self.out, err=self.err, **kwargs)  # type: ignore[arg-type]


@pytest.fixture
def folders(tmp_path: Path) -> list[str]:
    return [
        "--config-dir",
        str(tmp_path / "config"),
        "--data-dir",
        str(tmp_path / "data"),
        "--idle-minutes",
        "1",
    ]


@pytest.fixture
def started(folders: list[str], tmp_path: Path) -> Iterator[tuple[Run, ServiceInfo]]:
    """A service the launcher started, stopped after the test."""
    run = Run([*folders, "--print-url"])
    config_dir = tmp_path / "config"
    info = read_service_file(config_dir)
    assert run.status == 0, run.err.getvalue()
    assert info is not None
    yield run, info
    stop(info, config_dir)


def test_the_launcher_starts_the_service_and_prints_the_interface_address(
    started: tuple[Run, ServiceInfo],
) -> None:
    run, info = started
    assert run.out.getvalue().strip() == interface_url(info)
    assert interface_url(info) == f"http://127.0.0.1:{info.port}/v1/ui/#token={info.token}"
    assert info.pid != os.getpid()
    with httpx2.Client(trust_env=False, timeout=5) as client:
        system = client.get(
            f"http://127.0.0.1:{info.port}/v1/system",
            headers={"Authorization": f"Bearer {info.token}"},
        )
    assert system.status_code == 200


@pytest.mark.skipif(os.name == "nt", reason="sessions are a POSIX notion")
def test_the_service_is_detached_from_the_launcher(started: tuple[Run, ServiceInfo]) -> None:
    _, info = started
    assert os.getsid(info.pid) == info.pid
    assert os.getsid(info.pid) != os.getsid(0)


def test_the_service_s_output_goes_to_its_log(
    started: tuple[Run, ServiceInfo], tmp_path: Path
) -> None:
    _, info = started
    log = (tmp_path / "config" / LOG_FILE).read_text(encoding="utf-8")
    assert f"lcsim service on 127.0.0.1:{info.port}" in log


def test_a_second_launch_finds_the_running_service(
    started: tuple[Run, ServiceInfo], folders: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, info = started

    def no_start(*_args: object, **_kwargs: object) -> None:  # pragma: no cover - a failure
        raise AssertionError("a service was started although one answers")

    monkeypatch.setattr(launcher, "start_service", no_start)
    again = Run([*folders, "--print-url"])
    assert again.status == 0
    assert again.out.getvalue().strip() == interface_url(info)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


def test_a_stale_service_json_starts_a_new_service(folders: list[str], tmp_path: Path) -> None:
    """Spec 3 "Launcher": a file left by a service that has gone does not answer the probe,
    so it is never taken as a running service."""
    config_dir = tmp_path / "config"
    stale = ServiceInfo(
        port=free_port(), token="gone", pid=2**22 + 1, started="2026-01-01T00:00:00Z"
    )
    write_service_file(config_dir, stale)
    run = Run([*folders, "--print-url"])
    info = read_service_file(config_dir)
    try:
        assert run.status == 0, run.err.getvalue()
        assert info is not None and info != stale
        assert run.out.getvalue().strip() == interface_url(info)
    finally:
        if info is not None and info != stale:
            stop(info, config_dir)


def test_the_launcher_opens_the_browser_without_printing_the_token(
    started: tuple[Run, ServiceInfo], folders: list[str]
) -> None:
    _, info = started
    opened: list[str] = []

    def opener(url: str) -> bool:
        opened.append(url)
        return True

    run = Run(folders, opener)
    assert run.status == 0
    assert opened == [interface_url(info)]
    assert info.token not in run.out.getvalue()
    assert f"http://127.0.0.1:{info.port}/v1/ui/" in run.out.getvalue()


def test_without_a_browser_the_launcher_prints_the_whole_address(
    started: tuple[Run, ServiceInfo], folders: list[str]
) -> None:
    _, info = started
    run = Run(folders, lambda _url: False)
    assert run.status == 0
    assert interface_url(info) in run.out.getvalue()


def fake_command(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def test_a_service_that_fails_to_start_is_reported_with_its_log(
    folders: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        launcher, "service_command", lambda *_a: fake_command("print('broken'); exit(3)")
    )
    run = Run([*folders, "--print-url"])
    assert run.status == 1
    log = tmp_path / "config" / LOG_FILE
    assert str(log) in run.err.getvalue()
    assert "broken" in log.read_text(encoding="utf-8")
    assert run.out.getvalue() == ""


@pytest.mark.parametrize("code", ["exit(0)", "import time; time.sleep(60)"], ids=["exits", "hangs"])
def test_a_service_that_never_answers_is_given_up_after_the_wait(
    folders: list[str], monkeypatch: pytest.MonkeyPatch, code: str
) -> None:
    """A start that exits 0 may have found another service starting: the launcher keeps
    waiting for one to answer, up to the wait."""
    children: list[subprocess.Popen[bytes]] = []
    real_start = launcher.start_service

    def recording_start(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        child = real_start(*args, **kwargs)  # type: ignore[arg-type]
        children.append(child)
        return child

    monkeypatch.setattr(launcher, "service_command", lambda *_a: fake_command(code))
    monkeypatch.setattr(launcher, "start_service", recording_start)
    monkeypatch.setattr(launcher, "READY_WAIT_S", 0.5)
    try:
        run = Run([*folders, "--print-url"])
    finally:
        for child in children:
            child.kill()
            child.wait()
    assert run.status == 1
    assert "did not answer within 0.5 s" in run.err.getvalue()


def test_the_service_command_passes_the_options_on(tmp_path: Path) -> None:
    command = service_command(tmp_path / "c", tmp_path / "d", tmp_path / "u", 5.0)
    assert command[:3] == [sys.executable, "-m", "ithax.service"]
    assert command[3:] == [
        "--config-dir",
        str(tmp_path / "c"),
        "--data-dir",
        str(tmp_path / "d"),
        "--ui-dir",
        str(tmp_path / "u"),
        "--idle-minutes",
        "5.0",
    ]
    assert service_command(tmp_path / "c", None, None, None)[3:] == [
        "--config-dir",
        str(tmp_path / "c"),
    ]


def test_detaching_differs_by_platform() -> None:
    assert detach_options("linux") == {"start_new_session": True}
    assert detach_options("darwin") == {"start_new_session": True}
    # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP: no console, and no Ctrl+C from ours.
    assert detach_options("win32") == {"creationflags": 0x00000008 | 0x00000200}


def test_waiting_ends_as_soon_as_the_service_answers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = ServiceInfo(port=1, token="t", pid=1, started="2026-01-01T00:00:00Z")
    answers = iter([None, None, info])
    monkeypatch.setattr(launcher, "running_service", lambda _dir: next(answers))
    child = subprocess.Popen(fake_command("import time; time.sleep(60)"))
    try:
        assert wait_until_ready(tmp_path, child, 30.0) == info
    finally:
        child.kill()
        child.wait()


def test_idle_minutes_must_be_above_zero() -> None:
    with pytest.raises(SystemExit) as refused:
        main(["--idle-minutes", "0"])
    assert refused.value.code == 2


def test_the_module_entry_point_is_main() -> None:
    import ithax.launcher.__main__ as entry

    assert entry.main is main
