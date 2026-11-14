"""``python -m ithax.service``: start the engine service (spec 3 "Service rules").

A service holds an exclusive lock on ``service.lock`` in the configuration folder for its
whole life, so two starts can never both serve (review of PR #34). A start that cannot
take the lock is a second start: it reads ``service.json`` and probes the service it
names; once that answers it prints the port and exits with status 0 (one service per
user). It waits up to ``STARTUP_WAIT_S`` for a service that is still starting, and exits
with status 1 if none answers by then. A start that takes the lock binds
``127.0.0.1`` on a port the operating system chooses, draws a token, writes
``service.json`` (mode 0600) and serves with uvicorn until stopped or idle; on exit it
removes the file if the file still names this service. The idle time is ``--idle-minutes``
when given, and otherwise ``idle_timeout_minutes`` in ``settings.json``, read once at the
start (default 30; a value that cannot be used is logged as W220 and the default used;
spec 3 "Lifetime", owner decision B5, AKS-141).

A signal that stops the service (``SIGTERM``, ``SIGINT``) is caught by uvicorn, which shuts
down gracefully and then raises the signal again; raised there, it ended the process before
``service.json`` was removed (M7 "Left"). ``SignalServer`` keeps the caught signals instead,
and ``main`` raises them again once the file is removed and the lock released, so the exit
status still says how the service was stopped (AKS-119).

Options: ``--config-dir`` and ``--data-dir`` replace the per-user folders; ``--ui-dir``
names the built interface the service serves at ``/v1/ui/`` (default
``ithax.service.config.default_ui_dir``); ``--templates-dir`` the template packages it
serves at ``/v1/templates`` (default ``ithax.service.config.default_templates_dir``;
AKS-122).
"""

from __future__ import annotations

import argparse
import contextlib
import os
import signal
import socket
import sys
import time
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import TextIO

import uvicorn

from ithax.runs.lock import RunLock, take_lock
from ithax.service.app import create_app
from ithax.service.config import (
    ServiceConfig,
    default_config_dir,
    default_data_dir,
    default_templates_dir,
    default_ui_dir,
    new_token,
)
from ithax.service.discovery import (
    ServiceInfo,
    probe,
    read_service_file,
    remove_service_file,
    write_service_file,
)
from ithax.service.idle_settings import read_idle_settings
from ithax.service.paths import canonical
from ithax.service.projects_store import utc_now

__all__ = [
    "LOCAL_ADDRESS",
    "SERVICE_LOCK",
    "STARTUP_WAIT_S",
    "SignalServer",
    "bind_local",
    "main",
    "raise_again",
]

#: Spec 3 "Local only".
LOCAL_ADDRESS = "127.0.0.1"

#: The lock a running service holds in its configuration folder (AKS-110).
SERVICE_LOCK = "service.lock"

#: How long a second start waits for a service that is still starting: twice spec 3's
#: proposed "ready within 5 seconds" (AKS-110).
STARTUP_WAIT_S = 10.0

_POLL_S = 0.1


class SignalServer(uvicorn.Server):
    """uvicorn's server, except that a signal it caught while serving is kept in
    ``caught_signals`` rather than raised again as the server finishes, so that ``main``
    can remove ``service.json`` first (AKS-119)."""

    def __init__(self, config: uvicorn.Config) -> None:
        super().__init__(config)
        self.caught_signals: list[int] = []

    @contextlib.contextmanager
    def capture_signals(self) -> Iterator[None]:
        with super().capture_signals():
            try:
                yield
            finally:
                # uvicorn raises what it captured once this block ends; take it over.
                self.caught_signals.extend(self._captured_signals)
                self._captured_signals.clear()


def raise_again(signals: Sequence[int]) -> None:
    """Raise ``signals`` again, the last caught first, as uvicorn does."""
    for caught in reversed(signals):
        signal.raise_signal(caught)


def bind_local() -> socket.socket:
    """A TCP socket bound to ``127.0.0.1`` on a port the operating system chose, already
    listening, so that connections made before serving starts wait in its backlog."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((LOCAL_ADDRESS, 0))
        sock.listen(128)
    except OSError:
        sock.close()
        raise
    return sock


def _arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m ithax.service", description="Start the Ithax engine service."
    )
    parser.add_argument("--config-dir", type=Path, help="the configuration folder")
    parser.add_argument("--data-dir", type=Path, help="the user data folder")
    parser.add_argument(
        "--idle-minutes",
        type=float,
        help="exit after this many idle minutes (default: idle_timeout_minutes in "
        "settings.json, 30 when unset)",
    )
    parser.add_argument(
        "--ui-dir",
        type=Path,
        help="the built interface to serve at /v1/ui/ (default: the checkout's ui/dist, else "
        "share/ithax/ui under the Python prefix)",
    )
    parser.add_argument(
        "--templates-dir",
        type=Path,
        help="the template packages to serve at /v1/templates (default: the checkout's "
        "templates, else share/ithax/templates under the Python prefix)",
    )
    arguments = parser.parse_args(argv)
    if arguments.idle_minutes is not None and not arguments.idle_minutes > 0:
        parser.error("--idle-minutes must be above 0")
    return arguments


def _own_or_find(config_dir: Path, out: TextIO, err: TextIO) -> RunLock | int:
    """The service lock, or the exit status of a second start: 0 when the service
    holding the lock answers, 1 when none answers within ``STARTUP_WAIT_S``."""
    deadline = time.monotonic() + STARTUP_WAIT_S
    while True:
        try:
            return take_lock(config_dir / SERVICE_LOCK)
        except BlockingIOError:
            pass
        running = read_service_file(config_dir)
        if running is not None and probe(running):
            print(
                f"An Ithax service is already running on {LOCAL_ADDRESS}:{running.port}.", file=out
            )
            return 0
        if time.monotonic() >= deadline:
            print(
                f"Another Ithax service holds {config_dir / SERVICE_LOCK} but did not answer "
                f"within {STARTUP_WAIT_S:g} s.",
                file=err,
            )
            return 1
        time.sleep(_POLL_S)


def main(
    argv: Sequence[str] | None = None,
    *,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    """Start the service, or exit if one already answers; return the exit status.
    ``out`` and ``err`` default to the standard streams."""
    arguments = _arguments(argv)
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    config_dir = canonical(arguments.config_dir or default_config_dir())
    data_dir = canonical(arguments.data_dir or default_data_dir())
    config_dir.mkdir(parents=True, exist_ok=True)
    ui_dir = canonical(arguments.ui_dir or default_ui_dir())
    templates_dir = canonical(arguments.templates_dir or default_templates_dir())
    owned = _own_or_find(config_dir, out, err)
    if isinstance(owned, int):
        return owned
    try:
        # Read once the lock is taken: a second start serves nothing and needs no idle time.
        if arguments.idle_minutes is not None:
            idle_timeout_s = arguments.idle_minutes * 60  # unit factor: whole minutes, a setting
        else:
            idle_timeout_s = read_idle_settings(config_dir).timeout_s
        caught = _serve(config_dir, data_dir, ui_dir, templates_dir, idle_timeout_s, out)
    finally:
        owned.release()
    raise_again(caught)
    return 0


def _serve(
    config_dir: Path,
    data_dir: Path,
    ui_dir: Path,
    templates_dir: Path,
    idle_timeout_s: float,
    out: TextIO,
) -> list[int]:
    """Bind, write ``service.json``, serve until stopped or idle, remove the file; return
    the signals that stopped the service, if any."""
    servers: list[uvicorn.Server] = []

    def stop() -> None:
        for server in servers:
            server.should_exit = True

    with bind_local() as sock:
        port = sock.getsockname()[1]
        config = ServiceConfig(
            config_dir=config_dir,
            data_dir=data_dir,
            port=port,
            token=new_token(),
            ui_dir=ui_dir,
            templates_dir=templates_dir,
            idle_timeout_s=idle_timeout_s,
            idle_check_s=min(10.0, idle_timeout_s / 4),
            on_idle=stop,
        )
        server = SignalServer(
            uvicorn.Config(
                create_app(config),
                ws="websockets-sansio",
                lifespan="on",
                log_level="warning",
                proxy_headers=False,
                server_header=False,
            )
        )
        servers.append(server)
        info = ServiceInfo(port=port, token=config.token, pid=os.getpid(), started=utc_now())
        write_service_file(config_dir, info)
        print(f"Ithax service on {LOCAL_ADDRESS}:{port}", file=out, flush=True)
        try:
            server.run(sockets=[sock])
        finally:
            remove_service_file(config_dir, info)
    return server.caught_signals
