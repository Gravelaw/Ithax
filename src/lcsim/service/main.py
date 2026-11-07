"""``python -m lcsim.service``: start the engine service (spec 3 "Service rules").

``main`` reads ``service.json`` and probes the service it names; if that answers, it
prints the port and exits with status 0 (one service per user). Otherwise it binds
``127.0.0.1`` on a port the operating system chooses, draws a token, writes
``service.json`` (mode 0600) and serves with uvicorn until stopped or idle for
``--idle-minutes`` (default 30, spec 3 "Lifetime", proposed); on exit it removes the file
if the file still names this service.

Options: ``--config-dir`` and ``--data-dir`` replace the per-user folders.
"""

from __future__ import annotations

import argparse
import os
import socket
from collections.abc import Sequence
from pathlib import Path

import uvicorn

from lcsim.service.app import create_app
from lcsim.service.config import (
    DEFAULT_IDLE_TIMEOUT_S,
    ServiceConfig,
    default_config_dir,
    default_data_dir,
    new_token,
)
from lcsim.service.discovery import (
    ServiceInfo,
    probe,
    read_service_file,
    remove_service_file,
    write_service_file,
)
from lcsim.service.projects_store import utc_now

__all__ = ["LOCAL_ADDRESS", "bind_local", "main"]

#: Spec 3 "Local only".
LOCAL_ADDRESS = "127.0.0.1"


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
    arguments = parser.parse_args(argv)
    if not arguments.idle_minutes > 0:
        parser.error("--idle-minutes must be above 0")
    return arguments


def main(argv: Sequence[str] | None = None) -> int:
    """Start the service, or exit if one already answers; return the exit status."""
    arguments = _arguments(argv)
    config_dir: Path = arguments.config_dir or default_config_dir()
    data_dir: Path = arguments.data_dir or default_data_dir()
    running = read_service_file(config_dir)
    if running is not None and probe(running):
        print(f"An lcsim service is already running on {LOCAL_ADDRESS}:{running.port}.")
        return 0
    servers: list[uvicorn.Server] = []

    def stop() -> None:
        for server in servers:
            server.should_exit = True

    idle_timeout_s = arguments.idle_minutes * 60
    with bind_local() as sock:
        port = sock.getsockname()[1]
        config = ServiceConfig(
            config_dir=config_dir,
            data_dir=data_dir,
            port=port,
            token=new_token(),
            idle_timeout_s=idle_timeout_s,
            idle_check_s=min(10.0, idle_timeout_s / 4),
            on_idle=stop,
        )
        server = uvicorn.Server(
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
        print(f"lcsim service on {LOCAL_ADDRESS}:{port}", flush=True)
        try:
            server.run(sockets=[sock])
        finally:
            remove_service_file(config_dir, info)
    return 0
