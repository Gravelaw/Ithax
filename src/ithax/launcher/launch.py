"""``python -m ithax.launcher``: find or start the engine service and open the interface
(spec 3 "Service rules", Launcher; AKS-119, owner to confirm).

Until the desktop shell exists (M11) this is how the interface reaches the service:

1. read ``service.json`` in the configuration folder and probe the service it names
   (``ithax.service.discovery.probe``), as a second start of the service does;
2. when nothing answers, also when the file is left from a service that has gone, start
   ``python -m ithax.service`` detached from the launcher (a new session on Linux and macOS,
   a new process group without a console on Windows), its output appended to
   ``service.log`` in the configuration folder;
3. wait up to ``READY_WAIT_S`` for ``service.json`` to name a service that answers;
4. open ``http://127.0.0.1:<port>/v1/ui/#token=<token>`` in the default browser, or with
   ``--print-url`` print it, for scripts and tests.

The exit status is 0 once the address is opened or printed, and 1 when no service answered
in time. ``--config-dir``, ``--data-dir``, ``--ui-dir`` and ``--idle-minutes`` are passed to
a service the launcher starts. The page takes the token from the fragment, which a browser
never sends to the service (``ui/src/api/token.ts``).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import webbrowser
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TextIO

from ithax.service.config import default_config_dir
from ithax.service.discovery import ServiceInfo, probe, read_service_file
from ithax.service.paths import canonical

__all__ = [
    "LOG_FILE",
    "READY_WAIT_S",
    "detach_options",
    "interface_url",
    "main",
    "running_service",
    "service_command",
    "start_service",
    "wait_until_ready",
]

#: The service's output, appended, in the configuration folder.
LOG_FILE = "service.log"

#: How long the launcher waits for a service it started to answer: six times spec 3's
#: proposed "ready within 5 seconds", for a slow first start on the low tier.
READY_WAIT_S = 30.0

_POLL_S = 0.1

# Windows process creation flags (``subprocess`` defines them only on Windows).
_DETACHED_PROCESS = 0x00000008
_CREATE_NEW_PROCESS_GROUP = 0x00000200


def interface_url(info: ServiceInfo) -> str:
    """The interface's address on the service ``info`` names, its token in the fragment."""
    return f"http://127.0.0.1:{info.port}/v1/ui/#token={info.token}"


def running_service(config_dir: Path) -> ServiceInfo | None:
    """The service ``service.json`` names, when it answers; ``None`` otherwise."""
    info = read_service_file(config_dir)
    return info if info is not None and probe(info) else None


def service_command(
    config_dir: Path, data_dir: Path | None, ui_dir: Path | None, idle_minutes: float | None
) -> list[str]:
    """The command that starts the service with the launcher's options."""
    command = [sys.executable, "-m", "ithax.service", "--config-dir", str(config_dir)]
    if data_dir is not None:
        command += ["--data-dir", str(data_dir)]
    if ui_dir is not None:
        command += ["--ui-dir", str(ui_dir)]
    if idle_minutes is not None:
        command += ["--idle-minutes", str(idle_minutes)]
    return command


def detach_options(platform: str) -> dict[str, Any]:
    """The ``subprocess.Popen`` options that detach the service from the launcher, so it
    outlives the launcher and its terminal."""
    if platform == "win32":
        return {"creationflags": _DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


#: The services this process started, which are meant to outlive it (``detach_options``).
#: Each handle is kept so that it is never collected while its service runs, which Python
#: reports as a ``ResourceWarning`` ("subprocess ... is still running"); the service is
#: reaped by whoever outlives this process (#99, retrospective P20).
DETACHED: list[subprocess.Popen[bytes]] = []


def start_service(command: Sequence[str], log: Path) -> subprocess.Popen[bytes]:
    """Start ``command`` detached, its output appended to ``log``; its handle is kept in
    ``DETACHED``."""
    with log.open("ab") as output:
        process = subprocess.Popen(
            list(command),
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            close_fds=True,
            **detach_options(sys.platform),
        )
    DETACHED.append(process)
    return process


def wait_until_ready(
    config_dir: Path, process: subprocess.Popen[bytes], timeout_s: float
) -> ServiceInfo | None:
    """The service that answers once ``service.json`` names it, or ``None`` when none does
    within ``timeout_s`` seconds or ``process`` fails first. A start that exits with status
    0 found another service starting, so waiting goes on until the time is up."""
    deadline = time.monotonic() + timeout_s
    while True:
        found = running_service(config_dir)
        if found is not None:
            return found
        failed = process.poll() not in (None, 0)
        if failed or time.monotonic() >= deadline:
            return None
        time.sleep(_POLL_S)


def _arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m ithax.launcher",
        description="Open the lcsim interface, starting the engine service if needed.",
    )
    parser.add_argument("--config-dir", type=Path, help="the configuration folder")
    parser.add_argument("--data-dir", type=Path, help="the user data folder, for a new service")
    parser.add_argument("--ui-dir", type=Path, help="the built interface, for a new service")
    parser.add_argument(
        "--idle-minutes", type=float, help="the idle limit of a new service (default: its setting)"
    )
    parser.add_argument(
        "--print-url",
        action="store_true",
        help="print the interface's address, with its token, instead of opening a browser",
    )
    arguments = parser.parse_args(argv)
    if arguments.idle_minutes is not None and not arguments.idle_minutes > 0:
        parser.error("--idle-minutes must be above 0")
    return arguments


def main(
    argv: Sequence[str] | None = None,
    *,
    out: TextIO | None = None,
    err: TextIO | None = None,
    opener: Callable[[str], bool] = webbrowser.open,
) -> int:
    """Open or print the interface's address; return the exit status. ``out`` and ``err``
    default to the standard streams; ``opener`` opens an address in a browser."""
    arguments = _arguments(argv)
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    config_dir = canonical(arguments.config_dir or default_config_dir())
    info = running_service(config_dir)
    if info is None:
        config_dir.mkdir(parents=True, exist_ok=True)
        log = config_dir / LOG_FILE
        command = service_command(
            config_dir,
            None if arguments.data_dir is None else canonical(arguments.data_dir),
            None if arguments.ui_dir is None else canonical(arguments.ui_dir),
            arguments.idle_minutes,
        )
        info = wait_until_ready(config_dir, start_service(command, log), READY_WAIT_S)
        if info is None:
            print(
                f"The engine service did not answer within {READY_WAIT_S:g} s; its log is {log}.",
                file=err,
            )
            return 1
    url = interface_url(info)
    if arguments.print_url:
        print(url, file=out)
    elif opener(url):
        print(f"Opened the interface at http://127.0.0.1:{info.port}/v1/ui/", file=out)
    else:
        print(f"No browser could be opened. Open this address: {url}", file=out)
    return 0
