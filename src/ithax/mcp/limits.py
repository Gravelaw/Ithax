"""The MCP server's own run limit (spec 4 "Limits"; AKS-134).

"The MCP server itself allows at most two unfinished runs per project that it started,
tracked in memory; a third request returns an error object." ``StartedRuns`` keeps, for
each ``project_id`` given to ``run_model``, the ``run_id`` of every run this MCP server
started for it (an answer of 202), from the server's own start; runs the interface, a
script or another MCP server started are not in it.

``StartedRuns.start`` asks the service for each of them (``GET /v1/runs/{rid}``) before it
starts another: a run is unfinished while the service says ``queued`` or ``running``, so
nothing is guessed. A run the service says has ended, or no longer finds (404), is
forgotten, since it can never be unfinished again; any other refusal is returned as the
result and nothing is started, so a run whose state is not known still counts. With
``MAX_UNFINISHED_RUNS`` unfinished, ``RunLimitReached`` (spec 1 E194) is raised and no
request is sent to start a run. One lock covers the check and the start, so two calls at
once cannot both pass the check.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from ithax.model.issues import Issue, pointer

if TYPE_CHECKING:  # pragma: no cover - imports for the type checker only
    from ithax.mcp.client import Answer, ServiceClient

__all__ = [
    "MAX_UNFINISHED_RUNS",
    "RUN_LIMIT",
    "UNFINISHED_STATES",
    "RunLimitReached",
    "StartedRuns",
    "segment",
]

#: Spec 1 code for a run refused by the MCP server's limit (AKS-134, owner to confirm).
RUN_LIMIT = "E194"

#: The most unfinished runs of one project this MCP server keeps (spec 4 "Limits").
MAX_UNFINISHED_RUNS = 2

#: The job states of a run that is not finished (spec 1 "Run targets").
UNFINISHED_STATES = frozenset({"queued", "running"})

_ACCEPTED = 202
_NOT_FOUND = 404
_OK = 200


def segment(value: str) -> str:
    """``value`` as one percent-encoded path segment, so no input can name another route."""
    return quote(value, safe="")


class RunLimitReached(Exception):
    """A project already has ``MAX_UNFINISHED_RUNS`` unfinished runs this MCP server
    started: spec 1 E194, with their ids."""

    code = RUN_LIMIT

    def __init__(self, project_id: str, run_ids: tuple[str, ...]) -> None:
        self.project_id = project_id
        self.run_ids = run_ids
        self.message = (
            f"This MCP server has already started {len(run_ids)} runs of project "
            f"'{project_id}' that are not finished: {', '.join(run_ids)}."
        )
        super().__init__(self.message)

    def issue(self) -> Issue:
        return Issue(
            code=self.code,
            component=None,
            path=pointer("project_id"),
            message=self.message,
            hint=(
                "Wait until one of them is done, failed or cancelled (get_run_status shows "
                "its state), then call run_model again."
            ),
        )

    def body(self) -> dict[str, Any]:
        """An error body of the service's shape (spec 3), with the unfinished run ids."""
        return {
            "error": {"code": self.code, "message": self.message},
            "issues": [self.issue().as_dict()],
            "run_ids": list(self.run_ids),
        }


class StartedRuns:
    """The runs one MCP server started, by project, in memory. Safe to use from several
    threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, tuple[str, ...]] = {}

    def tracked(self, project_id: str) -> tuple[str, ...]:
        """The runs of ``project_id`` still counted, in the order they were started."""
        with self._lock:
            return self._runs.get(project_id, ())

    def start(self, client: ServiceClient, project_id: str, body: dict[str, Any]) -> Answer:
        """Send ``POST /v1/projects/{project_id}/runs`` with ``body`` unless the project
        already has ``MAX_UNFINISHED_RUNS`` unfinished runs (``RunLimitReached``); the
        service's answer, or the refusal of a status check."""
        with self._lock:
            unfinished: list[str] = []
            for rid in self._runs.get(project_id, ()):
                answer = client.request("GET", f"/v1/runs/{segment(rid)}")
                if answer.status == _NOT_FOUND:
                    continue
                if answer.status != _OK:
                    self._runs[project_id] = (*unfinished, *self._after(project_id, rid))
                    return answer
                state = answer.body.get("state") if isinstance(answer.body, dict) else None
                if state in UNFINISHED_STATES:
                    unfinished.append(rid)
            self._runs[project_id] = tuple(unfinished)
            if len(unfinished) >= MAX_UNFINISHED_RUNS:
                raise RunLimitReached(project_id, tuple(unfinished))
            answer = client.request("POST", f"/v1/projects/{segment(project_id)}/runs", body)
            started = answer.body.get("run_id") if isinstance(answer.body, dict) else None
            if answer.status == _ACCEPTED and isinstance(started, str):
                self._runs[project_id] = (*unfinished, started)
            return answer

    def _after(self, project_id: str, rid: str) -> tuple[str, ...]:
        """``rid`` and the runs of ``project_id`` after it, not yet asked about."""
        runs = self._runs[project_id]
        return runs[runs.index(rid) :]
