"""The MCP server's one way into the engine service (spec 4 "How the server runs and
answers"; spec 3 "Service rules"; AKS-115).

``ServiceClient.request`` sends one request to the service's ``/v1`` API, never through a
private channel: to ``127.0.0.1`` without any proxy, with ``Authorization: Bearer`` and the
token of ``service.json``, and ``X-Client: mcp`` (spec 3 "Client header"). Redirects are not
followed. The answer's body is read with the strict JSON reader (``lcsim.strict_json``), so
the MCP server never passes on a value the service could not have written.

Finding the service uses the service's own rules (``lcsim.service.discovery``): the port and
token of ``service.json`` in the configuration folder, accepted once the spec 3 probe
answers. When the file is missing or its service does not answer, the client starts
``python -m lcsim.service`` with the same folders (spec 3 "Lifetime": "the interface and the
MCP server start it on demand"), detached so that it and its runs outlive the MCP server,
with its standard streams discarded so nothing reaches the MCP stdio stream, and waits up to
``START_TIMEOUT_S`` for ``service.json`` to name a service that answers. Two starts at once
are settled by the service's ``service.lock``: the second waits for the first, then exits
with status 0, and the client finds the first through the file.

A request is sent once more, after finding the service again, only when its connection was
refused (nothing reached the service) or it was answered 401 (refused by the token check
before any route ran, as after a restart with a new token). A request that may have reached
a route (a dropped connection, a timeout) is never repeated, since it may have been applied.

When no answer can be had the client raises ``ServiceUnavailable``, which becomes spec 1
issue E193 (AKS-115, owner to confirm).
"""

from __future__ import annotations

import http.client
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

from lcsim.model.issues import Issue
from lcsim.service.discovery import ServiceInfo, probe, read_service_file
from lcsim.service.main import LOCAL_ADDRESS, STARTUP_WAIT_S
from lcsim.service.paths import canonical
from lcsim.strict_json import UnreadableJSON, read_json

__all__ = [
    "CLIENT",
    "REQUEST_TIMEOUT_S",
    "SERVICE_UNAVAILABLE",
    "START_TIMEOUT_S",
    "Answer",
    "ServiceClient",
    "ServiceUnavailable",
    "detached_options",
]

#: Spec 3 "Client header": the MCP server's requests are recorded as ``mcp``.
CLIENT = "mcp"

#: Spec 1 code for a service the MCP server cannot reach (AKS-115, owner to confirm).
SERVICE_UNAVAILABLE = "E193"

#: How long the client waits for a service it started to answer: three times the
#: ``STARTUP_WAIT_S`` a second start of the service waits for the first, so a start that
#: defers to another still starting is covered, and six times spec 3's proposed "ready
#: within 5 seconds" (spec 4, AKS-115, owner to confirm).
START_TIMEOUT_S = 3 * STARTUP_WAIT_S

#: How long one request may take before it counts as not answered (AKS-115).
REQUEST_TIMEOUT_S = 60.0

#: Windows process creation flags: no console, and a process group of its own, so the
#: service neither shares the assistant's console nor receives its Ctrl+C.
_DETACHED_PROCESS = 0x00000008
_CREATE_NEW_PROCESS_GROUP = 0x00000200

_POLL_S = 0.1

_HINT = (
    "Check that lcsim is installed for the Python that runs the MCP server, then start the "
    "service with 'python -m lcsim.service' and try again."
)


@dataclass(frozen=True)
class Answer:
    """The service's answer: its HTTP status and its body as a JSON document."""

    status: int
    body: object


class ServiceUnavailable(Exception):
    """No answer could be had from the service: spec 1 E193 with a message and a hint."""

    code = SERVICE_UNAVAILABLE

    def __init__(self, message: str, hint: str = _HINT) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def issue(self) -> Issue:
        """The one E193 issue, about no place in a model."""
        return Issue(code=self.code, component=None, path="", message=self.message, hint=self.hint)

    def body(self) -> dict[str, Any]:
        """An error body of the service's shape (spec 3), holding the issue."""
        return {
            "error": {"code": self.code, "message": self.message},
            "issues": [self.issue().as_dict()],
        }


def detached_options(os_name: str | None = None) -> dict[str, Any]:
    """The ``subprocess.Popen`` options that start the service apart from the MCP server:
    a new session on POSIX, no console and a new process group on Windows."""
    if (os.name if os_name is None else os_name) == "nt":
        return {"creationflags": _DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Answers a redirect as it is: the service sends none, and a client of ``/v1`` must
    not be sent elsewhere."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: http.client.HTTPMessage,
        newurl: str,
    ) -> None:
        return None


class ServiceClient:
    """Requests to the service whose ``service.json`` is in ``config_dir``, starting it
    with ``config_dir`` and ``data_dir`` when it does not answer.

    ``command`` replaces the start command (tests); ``started`` is the last service process
    this client started, or ``None``. Safe to use from several threads.
    """

    def __init__(
        self,
        config_dir: Path,
        data_dir: Path,
        *,
        command: Sequence[str] | None = None,
        start_timeout_s: float = START_TIMEOUT_S,
        request_timeout_s: float = REQUEST_TIMEOUT_S,
    ) -> None:
        self.config_dir = canonical(config_dir)
        self.data_dir = canonical(data_dir)
        self.command = list(command) if command is not None else self._service_command()
        self.start_timeout_s = start_timeout_s
        self.request_timeout_s = request_timeout_s
        self.started: subprocess.Popen[bytes] | None = None
        self._info: ServiceInfo | None = None
        self._lock = threading.Lock()
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def _service_command(self) -> list[str]:
        return [
            sys.executable,
            "-m",
            "lcsim.service",
            "--config-dir",
            str(self.config_dir),
            "--data-dir",
            str(self.data_dir),
        ]

    def request(self, method: str, path: str, body: object | None = None) -> Answer:
        """Send ``method`` ``path`` (a path under ``/v1/``) with ``body`` as JSON, or no
        body when ``None``; the service's answer, whatever its status.
        ``ServiceUnavailable`` when there is none."""
        if not path.startswith("/v1/"):
            raise ValueError(f"{path!r} is not a path under /v1/")
        info = self._service()
        answer = self._send(info, method, path, body)
        if answer is not None and answer.status != 401:
            return answer
        self._forget(info)
        answer = self._send(self._service(), method, path, body)
        if answer is None:
            raise ServiceUnavailable("The engine service did not answer.")
        return answer

    # --- one request -------------------------------------------------------------------

    def _send(self, info: ServiceInfo, method: str, path: str, body: object) -> Answer | None:
        """The answer, or ``None`` when the connection was refused, so nothing was sent."""
        headers = {"Authorization": f"Bearer {info.token}", "X-Client": CLIENT}
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=True, allow_nan=False).encode("ascii")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"http://{LOCAL_ADDRESS}:{info.port}{path}", data=data, headers=headers, method=method
        )
        try:
            with self._opener.open(request, timeout=self.request_timeout_s) as response:
                status, raw = int(response.status), response.read()
        except urllib.error.HTTPError as refusal:
            with refusal:
                status, raw = refusal.code, refusal.read()
        except urllib.error.URLError as failure:
            if isinstance(failure.reason, ConnectionRefusedError):
                return None
            raise ServiceUnavailable("The engine service did not answer.") from None
        except (OSError, http.client.HTTPException):
            raise ServiceUnavailable("The engine service did not answer.") from None
        try:
            return Answer(status=status, body=read_json(raw))
        except UnreadableJSON:
            raise ServiceUnavailable(
                "The engine service sent an answer that could not be read as JSON."
            ) from None

    # --- finding and starting the service ----------------------------------------------

    def _service(self) -> ServiceInfo:
        with self._lock:
            if self._info is None:
                self._info = self._find()
            return self._info

    def _forget(self, info: ServiceInfo) -> None:
        with self._lock:
            if self._info == info:
                self._info = None

    def _answering(self) -> ServiceInfo | None:
        info = read_service_file(self.config_dir)
        return info if info is not None and probe(info) else None

    def _find(self) -> ServiceInfo:
        """The service ``service.json`` names once it answers the probe, starting one
        when none answers."""
        found = self._answering()
        if found is not None:
            return found
        process = self._start()
        deadline = time.monotonic() + self.start_timeout_s
        while True:
            found = self._answering()
            if found is not None:
                return found
            status = process.poll()
            if status not in (None, 0):
                raise ServiceUnavailable("The engine service could not be started.")
            if time.monotonic() >= deadline:
                raise ServiceUnavailable(
                    f"The engine service did not answer within {self.start_timeout_s:g} s "
                    "of being started."
                )
            time.sleep(_POLL_S)

    def _start(self) -> subprocess.Popen[bytes]:
        try:
            process = subprocess.Popen(
                self.command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **detached_options(),
            )
        except OSError:
            raise ServiceUnavailable("The engine service could not be started.") from None
        self.started = process
        return process
