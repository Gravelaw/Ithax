"""A network guard for the offline test (AKS-114; spec 3 acceptance "The app works with
outbound network blocked", spec 0 principle 6 "Works offline").

``install(folder)`` adds an audit hook (PEP 578) to the current process that refuses every
network operation whose address is not loopback: ``socket.connect`` (which ``connect_ex``,
``create_connection`` and asyncio's connections all raise), ``socket.sendto`` and
``socket.sendmsg`` with an address, and name lookups (``getaddrinfo``, ``gethostbyname``,
``gethostbyname_ex``, ``gethostbyaddr``) of a name other than ``localhost`` or a loopback
address. A refused operation raises ``OSError`` (``ENETUNREACH``) where it was made and is
written to ``<folder>/violations-<pid>.txt``, so an attempt is seen even if the caller
swallows the error. ``install`` also writes ``<folder>/armed-<pid>``, so a test can show the
guard was on in each process it expects. Local sockets (``AF_UNIX`` paths, socket pairs)
and loopback addresses are allowed: the service listens on ``127.0.0.1``.

An audit hook cannot be removed, so the guard is installed only in processes made for the
test: ``offline_service.py`` installs it at import, before the service starts, and the run
workers the service spawns import that file again as their main module, so they install it
too. It is test code; nothing in ``src/lcsim`` imports it.
"""

from __future__ import annotations

import errno
import ipaddress
import os
import sys
from pathlib import Path
from typing import Any

__all__ = ["FOLDER_VARIABLE", "BlockedNetwork", "install", "install_from_environment"]

#: The environment variable naming the guard's folder; a process started with it set
#: (and its spawned children, which inherit it) installs the guard at import.
FOLDER_VARIABLE = "LCSIM_TEST_OFFLINE_DIR"

_ADDRESS_EVENTS = frozenset({"socket.connect", "socket.sendto", "socket.sendmsg"})
_NAME_EVENTS = frozenset(
    {
        "socket.getaddrinfo",
        "socket.gethostbyname",
        "socket.gethostbyname_ex",
        "socket.gethostbyaddr",
    }
)
_LOCAL_NAMES = frozenset({"localhost", "localhost.", ""})


class BlockedNetwork(OSError):
    """A network operation the guard refused."""


def loopback_host(host: object) -> bool:
    """Whether ``host`` (text, bytes or ``None``) names this machine's loopback."""
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if not isinstance(host, str):
        return False
    name = host.strip("[]").split("%", 1)[0].lower()
    if name in _LOCAL_NAMES:
        return True
    try:
        return ipaddress.ip_address(name).is_loopback
    except ValueError:
        return False


def local_address(address: object) -> bool:
    """Whether a socket address is local: an ``AF_UNIX`` path (text or bytes), no address,
    or an ``(host, port, ...)`` tuple whose host is loopback."""
    if address is None or isinstance(address, str | bytes | bytearray):
        return True
    if isinstance(address, tuple) and address:
        return loopback_host(address[0])
    return False


def install(folder: Path) -> None:
    """Installs the guard in this process; see the module docstring."""
    folder.mkdir(parents=True, exist_ok=True)
    pid = os.getpid()
    violations = folder / f"violations-{pid}.txt"

    def refuse(event: str, target: object) -> None:
        with violations.open("a", encoding="utf-8") as handle:
            handle.write(f"{event} {target!r}\n")
        raise BlockedNetwork(errno.ENETUNREACH, f"network blocked by the test: {target!r}")

    def hook(event: str, args: tuple[Any, ...]) -> None:
        if event in _ADDRESS_EVENTS:
            address = args[1] if len(args) > 1 else None
            if not local_address(address):
                refuse(event, address)
        elif event in _NAME_EVENTS:
            name = args[0] if args else None
            if not loopback_host(name):
                refuse(event, name)

    sys.addaudithook(hook)
    (folder / f"armed-{pid}").write_text(str(pid), encoding="utf-8")


def install_from_environment() -> None:
    """Installs the guard when ``LCSIM_TEST_OFFLINE_DIR`` is set."""
    folder = os.environ.get(FOLDER_VARIABLE)
    if folder:
        install(Path(folder))
