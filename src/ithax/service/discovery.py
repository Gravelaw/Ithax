"""The discovery file and the one-service-per-user probe (spec 3 "Service rules").

The service writes ``service.json`` ``{port, token, pid, started}`` with mode 0600 in its
configuration folder; the interface, the MCP server and scripts read it. A second start
reads the file and probes ``GET /v1/system`` with its token; if that answers 200 the
second start exits, otherwise it overwrites the file.

The file is written to a temporary file in the same folder, created with mode 0600, and
renamed over the old one, so a reader never sees half a file. On Windows the mode bits
cannot express 0600 (``os.chmod`` sets only the read-only flag); the per-user
configuration folder keeps the file private there.
"""

from __future__ import annotations

import contextlib
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from ithax.files import atomic_write
from ithax.strict_json import is_whole, json_text, read_json_file

__all__ = [
    "PROBE_TIMEOUT_S",
    "SERVICE_FILE",
    "ServiceInfo",
    "probe",
    "read_service_file",
    "remove_service_file",
    "write_service_file",
]

#: Spec 3 "Discovery".
SERVICE_FILE = "service.json"

#: How long the probe waits for ``GET /v1/system`` (AKS-110).
PROBE_TIMEOUT_S = 2.0

_MODE = 0o600


@dataclass(frozen=True)
class ServiceInfo:
    """The content of ``service.json``: ``started`` is ISO 8601 UTC ending in ``Z``."""

    port: int
    token: str
    pid: int
    started: str


def write_service_file(config_dir: Path, info: ServiceInfo) -> Path:
    """Write ``service.json`` in ``config_dir`` (created if missing) with mode 0600, by a
    temporary file and a rename; return its path."""
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / SERVICE_FILE
    text = json_text(asdict(info), ascii_only=True) + "\n"
    atomic_write(path, text.encode("utf-8"), mode=_MODE)
    return path


def read_service_file(config_dir: Path) -> ServiceInfo | None:
    """The ``service.json`` in ``config_dir``, or ``None`` when it is missing or does not
    hold the four fields with the right JSON types."""
    try:
        loaded = read_json_file(config_dir / SERVICE_FILE)
    except (OSError, ValueError):
        return None
    if not isinstance(loaded, dict) or set(loaded) != {"port", "token", "pid", "started"}:
        return None
    port, token, pid, started = (loaded[key] for key in ("port", "token", "pid", "started"))
    whole = all(is_whole(value) for value in (port, pid))
    if not (whole and isinstance(token, str) and isinstance(started, str)):
        return None
    return ServiceInfo(port=port, token=token, pid=pid, started=started)


def remove_service_file(config_dir: Path, info: ServiceInfo) -> bool:
    """Remove ``service.json`` if it still describes ``info``'s service; return whether
    it was removed. A file another service has written since is left alone."""
    if read_service_file(config_dir) != info:
        return False
    with contextlib.suppress(FileNotFoundError):
        (config_dir / SERVICE_FILE).unlink()
    return True


def probe(info: ServiceInfo, timeout_s: float = PROBE_TIMEOUT_S) -> bool:
    """Whether a service answers ``GET /v1/system`` with 200 at ``info``'s port and token
    within ``timeout_s`` seconds. The request goes to ``127.0.0.1`` without any proxy."""
    if not 0 < info.port < 65536:
        return False
    request = urllib.request.Request(
        f"http://127.0.0.1:{info.port}/v1/system",
        headers={"Authorization": f"Bearer {info.token}"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout_s) as response:
            return bool(response.status == 200)
    except (urllib.error.URLError, OSError, ValueError):
        return False
