"""A first template result through the installed package, as the interface would reach it
(spec 3 acceptance, "Fresh install to first result under ten minutes on Linux in a clean
container"; AKS-127).

Run inside the clean container by ``clean_install.sh`` with the package's own Python and
``-I``, so it uses the standard library only and nothing of the repository::

    python3 -I first_result.py --launcher ~/.local/bin/ithax-launcher [--offline]

It starts the service with the installed ``ithax-launcher --print-url``, reads the token
from the printed address, checks that the service serves the interface and ten templates,
creates a project from the coffee shop template with ``POST /v1/projects``, runs its
experiment with ``POST /v1/projects/{pid}/runs``, waits for ``done`` and reads
``GET /v1/runs/{rid}/summary``: only documented ``/v1`` routes. With ``--offline`` it first
shows that an outbound connection fails. It prints one JSON object on standard output.
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from typing import Any

TEMPLATE = "coffee_shop"
RUN_WAIT_S = 300.0
_ADDRESS = re.compile(r"http://127\.0\.0\.1:(?P<port>[0-9]+)/v1/ui/#token=(?P<token>[\w-]+)")


class Service:
    """The documented API of one service, with its token and ``X-Client: script``."""

    def __init__(self, port: int, token: str) -> None:
        self.base = f"http://127.0.0.1:{port}"
        self.token = token
        # The service is on loopback; no proxy, whatever the environment says.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def call(self, method: str, path: str, body: object = None, token: bool = True) -> Any:
        data = None if body is None else json.dumps(body).encode()
        headers = {"Content-Type": "application/json", "X-Client": "script"}
        if token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(self.base + path, data, headers, method=method)
        with self.opener.open(request, timeout=60) as response:
            payload = response.read()
            kind = response.headers.get("Content-Type", "")
        return json.loads(payload) if kind.startswith("application/json") else payload.decode()


def outbound_blocked() -> dict[str, str]:
    """What an outbound name lookup and an outbound connection did; each must fail."""
    seen: dict[str, str] = {}
    try:
        socket.getaddrinfo("pypi.org", 443)
        seen["lookup"] = "succeeded"
    except OSError as error:
        seen["lookup"] = f"failed: {error}"
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=5).close()
        seen["connect"] = "succeeded"
    except OSError as error:
        seen["connect"] = f"failed: {error}"
    return seen


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--launcher", required=True)
    parser.add_argument("--offline", action="store_true")
    arguments = parser.parse_args(argv)
    result: dict[str, Any] = {}
    if arguments.offline:
        result["outbound"] = outbound_blocked()

    started = time.monotonic()
    printed = subprocess.run(
        [arguments.launcher, "--print-url"], capture_output=True, text=True, timeout=120
    )
    match = _ADDRESS.fullmatch(printed.stdout.strip())
    if printed.returncode != 0 or match is None:
        print(f"the launcher failed: {printed.returncode} {printed.stderr}", file=sys.stderr)
        return 1
    service = Service(int(match["port"]), match["token"])
    result["service_ready_s"] = round(time.monotonic() - started, 2)

    page = service.call("GET", "/v1/ui/", token=False)
    title = re.search(r"<title>([^<]*)</title>", page)
    result["interface_title"] = title.group(1) if title else None
    templates = service.call("GET", "/v1/templates")
    result["templates"] = sorted(template["id"] for template in templates)
    result["engines"] = sorted(engine["name"] for engine in service.call("GET", "/v1/engines"))

    template = service.call("GET", f"/v1/templates/{TEMPLATE}")["template"]
    project = service.call("POST", "/v1/projects", {"name": "First result", "template": TEMPLATE})
    run = service.call(
        "POST", f"/v1/projects/{project['id']}/runs", {"experiment_id": template["experiment"]}
    )
    deadline = time.monotonic() + RUN_WAIT_S
    while (state := service.call("GET", f"/v1/runs/{run['run_id']}"))["state"] not in (
        "done",
        "failed",
        "cancelled",
    ):
        if time.monotonic() > deadline:
            print(f"the run did not finish: {state}", file=sys.stderr)
            return 1
        time.sleep(0.5)
    result["run_state"] = state["state"]
    if state["state"] != "done":
        print(f"the run did not succeed: {state}", file=sys.stderr)
        return 1
    answer = service.call("GET", f"/v1/runs/{run['run_id']}/summary")
    metrics = answer["summary"]["scenarios"]["default"]["metrics"]
    result["till_wait_mean_s"] = metrics["till.wait.mean"]["mean"]
    result["till_wait_half_width_s"] = metrics["till.wait.mean"]["half_width"]
    result["till_wait_n"] = metrics["till.wait.mean"]["n"]
    result["confidence"] = answer["summary"]["confidence"]
    result["findings"] = [finding["rule"] for finding in answer["findings"]]
    result["first_result_s"] = round(time.monotonic() - started, 2)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
