"""``python -m lcsim.service``: start the engine service (spec 3 "Service rules").

A service holds an exclusive lock on ``service.lock`` in the configuration folder for its
whole life, so two starts can never both serve (review of PR #34). A start that cannot
take the lock is a second start: it reads ``service.json`` and probes the service it
names; once that answers it prints the port and exits with status 0 (one service per
user). It waits up to ``STARTUP_WAIT_S`` for a service that is still starting, and exits
with status 1 if none answers by then. A start that takes the lock binds
``127.0.0.1`` on a port the operating system chooses, draws a token, writes
``service.json`` (mode 0600) and serves with uvicorn until stopped or idle for
``--idle-minutes`` (default 30, spec 3 "Lifetime", proposed); on exit it removes the file
if the file still names this service.

A signal that stops the service (``SIGTERM``, ``SIGINT``) is caught by uvicorn, which shuts
down gracefully and then raises the signal again; raised there, it ended the process before
``service.json`` was removed (M7 "Left"). ``SignalServer`` keeps the caught signals instead,
and ``main`` raises them again once the file is removed and the lock released, so the exit
status still says how the service was stopped (AKS-119).

Options: ``--config-dir`` and ``--data-dir`` replace the per-user folders; ``--ui-dir``
names the built interface the service serves at ``/v1/ui/`` (default
``lcsim.service.config.default_ui_dir``).
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

from lcsim.runs.lock import RunLock, take_lock
from lcsim.service.app import create_app
from lcsim.service.config import (
    DEFAULT_IDLE_TIMEOUT_S,
    ServiceConfig,
    default_config_dir,
    default_data_dir,
    default_ui_dir,
    new_token,
)
from lcsim.service.discovery import (
    ServiceInfo,
    probe,
    read_service_file,
    remove_service_file,
    write_service_file,
)
from lcsim.service.paths import canonical
from lcsim.service.projects_store import utc_now

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
        prog="python -m lcsim.service", description="Start the lcsim engine service."
    )
    parser.add_argument("--config-dir", type=Path, help="the configuration folder")
    parser.add_argument("--data-dir", type=Path, help="the user data folder")
    parser.add_argument(
        "--idle-minutes",
        type=float,
        default=DEFAULT_IDLE_TIMEOUT_S / 60,
        help="exit after this many idle minutes (default 30)",
    )
    parser.add_argument(
        "--ui-dir", type=Path, help="the built interface to serve at /v1/ui/ (default: ui/dist)"
    )
    arguments = parser.parse_args(argv)
    if not arguments.idle_minutes > 0:
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
                f"An lcsim service is already running on {LOCAL_ADDRESS}:{running.port}.", file=out
            )
            return 0
        if time.monotonic() >= deadline:
            print(
                f"Another lcsim service holds {config_dir / SERVICE_LOCK} but did not answer "
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
    owned = _own_or_find(config_dir, out, err)
    if isinstance(owned, int):
        return owned
    try:
        caught = _serve(config_dir, data_dir, ui_dir, arguments.idle_minutes * 60, out)
    finally:
        owned.release()
    raise_again(caught)
    return 0


def _serve(
    config_dir: Path, data_dir: Path, ui_dir: Path, idle_timeout_s: float, out: TextIO
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
        print(f"lcsim service on {LOCAL_ADDRESS}:{port}", file=out, flush=True)
        try:
            server.run(sockets=[sock])
        finally:
            remove_service_file(config_dir, info)
    return server.caught_signals
