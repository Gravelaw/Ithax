"""Starting, finding, cancelling and reading runs for the API (spec 3 "Service rules",
"Endpoints", "Progress events"; spec 1 "Run folder and results"; AKS-112).

``RunService`` is what the run routes call:

- **Starting.** ``submit`` reads the project's ``model.json`` bytes and its column index and
  creates the run with the ``local`` target (``ithax.runs.targets``), which copies the
  columns of its ``data`` references, all while it holds the model store's per-project
  write lock, so it never meets a half-made model write or data import (AKS-113); the
  manifest carries the project's id and the request's client. Submissions are taken one
  at a time, so the order in which runs are created is the order in which they enter the
  run queue (``ithax.runs.queue``) and the project's index (``ithax.runs.index``). A
  refused run creates nothing: 422 with the issues (E172 for a target), or 400 with E184
  for the experiment.
- **Driving.** The queue executes each run in a thread of the service; the run's worker is
  a child process of the service. Each state change is published to the project's events
  (``run`` events) and to the run's feed (``ithax.service.run_feed``), each progress report
  to the feed. A run holds the service's lifetime from its acceptance to its final state.
- **Finishing** (CI on PR #36). On disk a run finishes in one order: tables and
  ``summary.json``, the manifest with the final state, then ``worker.lock`` removed (E191
  reads the manifest first). A final state becomes visible (the run endpoints, the run's
  events, the project's events) only after that and, for a run the queue executed, after
  its queue place is free (``RunQueue.on_finished``); then its lifetime hold is released.
  Until then the run endpoints show the run as the service last published it, from the
  feed, even though its manifest already says final.
- **Finding.** A ``run_id`` is looked up in the index of each registered project, in
  ``projects.json`` order; the run's manifest is the source of truth for its state.
- **Recovering.** The first time the service uses a project's runs (on start for every
  registered project, otherwise when an opened project is first used), it fails with E191
  every run whose process is gone and makes the index match the run folders.
- **Stopping.** ``stop`` starts no more runs and interrupts every unfinished one (E191),
  then waits for them to end.
- **Findings** (AKS-135). ``summary`` reads a done run's ``summary.json`` and the run
  folder's ``model.json`` (the model that ran, never the project's current one), and adds
  the findings of ``ithax.findings.find`` at the thresholds of ``settings.json``, read at
  each call (``ithax.service.finding_settings``), with the W220 issues of reading them.
  Nothing is stored: the same files and thresholds give the same findings.

Errors are spec 3 bodies: 404 with E185 (no such project, run or table, or a run file that
cannot be read: a ``summary.json`` or ``model.json`` changed outside the product), 400 with E186 (a
project that cannot be read) or E184, 409 with E188 (not allowed in the run's state).
"""

from __future__ import annotations

import contextlib
import csv
import io
import logging
import math
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from ithax.engines.adapter import EngineAdapter
from ithax.engines.registry import installed_engines
from ithax.findings import find
from ithax.model.data import read_data_index
from ithax.model.issues import Issue
from ithax.model.loading import build_document
from ithax.model.model import Model
from ithax.model.validation import meaning_pass
from ithax.runs.ids import RUN_ID_PATTERN
from ithax.runs.index import RUNS_FOLDER, RunIndex
from ithax.runs.manager import ExperimentChoiceError
from ithax.runs.manifest import read_run_manifest
from ithax.runs.queue import RunQueue
from ithax.runs.snapshots import DATA_FOLDER
from ithax.runs.states import FINAL_STATES, JobState
from ithax.runs.tables import SUMMARY_FILE, TABLE_NAMES, TABLES_FOLDER
from ithax.runs.targets import MODEL_FILE, LocalRun, LocalTarget, RunRefused, recover_interrupted
from ithax.service.errors import (
    MALFORMED,
    NOT_ALLOWED,
    NOT_FOUND,
    PROJECT_FOLDER,
    ServiceError,
    malformed,
)
from ithax.service.events import ProjectEvents
from ithax.service.finding_settings import read_finding_settings
from ithax.service.lifetime import Lifetime
from ithax.service.model_store import ModelStore
from ithax.service.projects_store import PROJECT_FILE, ProjectRegistry, read_project
from ithax.service.run_feed import RunFeed
from ithax.service.run_settings import RunSettings
from ithax.strict_json import read_json_file

__all__ = ["STOP_WAIT_S", "TABLE_FORMATS", "RunService", "Table"]

_log = logging.getLogger(__name__)

#: How long ``stop`` waits for interrupted runs to end: the cancel grace, the kill grace
#: and room to spare (spec 1 "Cancel").
STOP_WAIT_S = 30.0

#: Spec 3 ``GET .../tables/{name}``: ``?format=json`` (the default) or ``csv``.
TABLE_FORMATS = ("json", "csv")


@dataclass(frozen=True)
class Table:
    """A table as the API returns it: JSON rows, or CSV text."""

    format: str
    rows: list[dict[str, Any]] | None = None
    text: str | None = None


@dataclass
class _Active:
    """An unfinished run of this service: its project, the run and its lifetime hold."""

    pid: str
    run: LocalRun
    hold: contextlib.ExitStack
    started: bool = False


def _not_found(message: str) -> ServiceError:
    return ServiceError(404, NOT_FOUND, message)


def _not_allowed(message: str) -> ServiceError:
    return ServiceError(409, NOT_ALLOWED, message)


def _experiment_issue(error: ExperimentChoiceError, experiment_id: str | None) -> ServiceError:
    if error.reason == "missing":
        message = "The request has no 'experiment_id'; a process model runs one of its experiments."
        hint = 'Send the id of one of the model\'s experiments, such as {"experiment_id": "base"}.'
    elif error.reason == "unwanted":
        message = (
            f"The request names the experiment '{experiment_id}', but an optimization model "
            "has no experiments."
        )
        hint = "Leave 'experiment_id' out."
    else:
        message = f"The model has no experiment '{experiment_id}'."
        hint = "Send the id of one of the model's experiments."
    issue = Issue(code=MALFORMED, component=None, path="/experiment_id", message=message, hint=hint)
    return malformed([issue])


def _refused(issues: tuple[Issue, ...]) -> ServiceError:
    errors = [issue for issue in issues if issue.severity == "error"]
    if len(errors) == 1:
        message = errors[0].message
    else:
        message = (
            f"The model has {len(errors)} errors, so it cannot run; each is listed in 'issues'."
        )
    return ServiceError(422, errors[0].code, message, issues)


def _engine(value: object) -> dict[str, Any] | None:
    """The manifest's ``engine`` as the run endpoints show it: ``{name, version}`` with a
    text name and a text or ``null`` version, else ``None`` (a manifest changed outside the
    product; AKS-138)."""
    if isinstance(value, dict):
        name, version = value.get("name"), value.get("version")
        if isinstance(name, str) and (version is None or isinstance(version, str)):
            return {"name": name, "version": version}
    return None


def _cell(value: object) -> object:
    """A table cell for JSON: a float that is not finite (a NaN mean) is ``None``; a value
    of a kind JSON has no word for (only in a table changed outside the product) is its
    text."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, str | int | float):
        return value
    return str(value)


def _csv_cell(value: object) -> str:
    """A table cell for CSV: an empty field for no value or a float that is not finite; a
    float as the shortest text that reads back to it."""
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return ""
    if isinstance(value, float):
        return repr(value)
    return str(value)


class RunService:
    """The runs of the registered projects."""

    def __init__(
        self,
        *,
        projects: ProjectRegistry,
        models: ModelStore,
        events: ProjectEvents,
        adapters: Mapping[str, EngineAdapter],
        lifetime: Lifetime,
        settings: RunSettings,
        workers: int,
        config_dir: Path,
    ) -> None:
        self.projects = projects
        self.models = models
        self.events = events
        self.adapters = adapters
        self.lifetime = lifetime
        self.settings = settings
        self.workers = workers
        self.config_dir = config_dir
        self.feed = RunFeed()
        self.queue = RunQueue(settings.max_concurrent_runs, on_finished=self._finished)
        self._lock = threading.Lock()
        self._submitting = threading.Lock()
        self._preparing = threading.Lock()
        self._active: dict[str, _Active] = {}
        self._indexes: dict[str, RunIndex] = {}
        self._prepared: set[str] = set()

    # --- projects ----------------------------------------------------------------------

    def _index(self, folder: Path) -> RunIndex:
        with self._lock:
            return self._indexes.setdefault(str(folder), RunIndex(folder))

    def _prepare(self, pid: str, folder: Path) -> None:
        """E191 for the project's orphaned runs and an index that matches its run
        folders, the first time the service uses the project's runs."""
        with self._preparing:
            if str(folder) in self._prepared:
                return
            for rid in recover_interrupted(folder / RUNS_FOLDER):
                _log.warning("The run %s was interrupted by a service restart (E191).", rid)
                self.events.run_changed(pid, rid, "failed")
            self._index(folder).sync()
            self._prepared.add(str(folder))

    def _project(self, pid: str) -> Path:
        """The folder of project ``pid``, prepared; 404 with E185 for an unknown project,
        400 with E186 for one that cannot be read."""
        folder = self.projects.folder(pid)
        record = read_project(folder)
        if record is None or record.id != pid:
            raise ServiceError(
                400,
                PROJECT_FOLDER,
                f"The project '{pid}' cannot be used: the {PROJECT_FILE} in '{folder}' is "
                "missing or cannot be read.",
            )
        self._prepare(pid, folder)
        return folder

    def start(self) -> None:
        """Prepares every registered project that can be read (on service start)."""
        for entry in self.projects.entries():
            if entry["available"]:
                self._prepare(entry["id"], Path(entry["path"]))

    def stop(self, timeout_s: float = STOP_WAIT_S) -> None:
        """Starts no more runs, interrupts every unfinished run (E191) and waits up to
        ``timeout_s`` for them to end."""
        self.queue.close()
        with self._lock:
            active = list(self._active.values())
        for item in active:
            item.run.interrupt()
        if not self.queue.join(timeout_s):
            _log.warning("Runs were still ending when the service stopped.")

    # --- the run target's hooks ----------------------------------------------------------

    def _on_state(self, run: LocalRun, state: JobState) -> None:
        """Publishes a state change; a final state of a run the queue started waits for
        the queue to report it (``_finished``), so that its place is free first."""
        with self._lock:
            active = self._active.get(run.run_id)
            if active is None:
                return
            if state == "running":
                active.started = True
            deferred = state in FINAL_STATES and active.started
        if state in FINAL_STATES:
            if not deferred:  # a queued run that ended without starting holds no place
                self._publish_final(run.run_id, state)
            return
        self.feed.state(run.run_id, state)
        self.events.run_changed(active.pid, run.run_id, state)

    def _finished(self, job: object) -> None:
        """The queue's report that a run it executed has returned and freed its place."""
        assert isinstance(job, LocalRun)
        state = job.state
        if state in FINAL_STATES:
            self._publish_final(job.run_id, state)
        else:
            _log.error("The run %s returned without reaching a final state.", job.run_id)

    def _publish_final(self, rid: str, state: JobState) -> None:
        """Makes a final state visible: the feed, the project's events, then the lifetime
        hold is released."""
        with self._lock:
            active = self._active.pop(rid, None)
        if active is None:
            return
        self.feed.state(rid, state)
        self.events.run_changed(active.pid, rid, state)
        active.hold.close()

    def _on_progress(self, run: LocalRun, fraction: float, message: str) -> None:
        self.feed.progress(run.run_id, fraction, message)

    # --- starting ----------------------------------------------------------------------

    def submit(self, pid: str, experiment_id: str | None, target: str | None, client: str) -> str:
        """Creates a run of the project's model and puts it in the run queue; its
        ``run_id``."""
        folder = self._project(pid)
        with self.models.locked(pid):
            return self._submit(pid, folder, experiment_id, target, client)

    def _submit(
        self, pid: str, folder: Path, experiment_id: str | None, target: str | None, client: str
    ) -> str:
        model_file = self.models.model_file(pid)
        local = LocalTarget(
            folder / RUNS_FOLDER,
            workers=self.workers,
            limits=self.settings.limits,
            client=client,
            project_id=pid,
            adapters=self.adapters,
            on_state=self._on_state,
            on_progress=self._on_progress,
            data=read_data_index(folder / DATA_FOLDER),
        )
        with self._submitting:
            try:
                run = local.create(model_file, experiment_id, target=target)
            except RunRefused as refused:
                raise _refused(refused.issues) from None
            except ExperimentChoiceError as error:
                raise _experiment_issue(error, experiment_id) from None
            hold = contextlib.ExitStack()
            hold.enter_context(self.lifetime.hold())
            with self._lock:
                self._active[run.run_id] = _Active(pid, run, hold)
            self.feed.begin(run.run_id)
            self._index(folder).add(run.run_id, run.manifest["created"], experiment_id)
            self.events.run_changed(pid, run.run_id, "queued")
            self.queue.submit(run)
        return run.run_id

    # --- reading -----------------------------------------------------------------------

    def _view(self, manifest: Mapping[str, Any]) -> dict[str, Any]:
        """The run as the API shows it. A run still live in the feed is shown as the
        service last published it, even when its manifest is already final (it is
        finishing): its state and fraction from the feed, no end time and no error."""
        snapshot = self.feed.snapshot(manifest["run_id"])
        view = {
            "run_id": manifest["run_id"],
            "project_id": manifest.get("project_id"),
            "experiment_id": manifest.get("experiment_id"),
            "engine": _engine(manifest.get("engine")),
            "state": manifest["state"],
            "fraction": manifest.get("fraction"),
            "message": "",
            "created": manifest["created"],
            "started": manifest.get("started"),
            "ended": manifest.get("ended"),
            "error": manifest.get("error"),
        }
        if snapshot is not None:
            view.update(
                state=snapshot.state,
                fraction=snapshot.fraction,
                message=snapshot.message,
                ended=None,
                error=None,
            )
            if snapshot.state == "queued":
                view["started"] = None
        return view

    def runs(self, pid: str) -> list[dict[str, Any]]:
        """The runs of project ``pid`` in the order they were accepted."""
        folder = self._project(pid)
        views = []
        for rid in self._index(folder).run_ids():
            manifest = read_run_manifest(folder / RUNS_FOLDER / rid)
            if manifest is not None:
                views.append(self._view(manifest))
        return views

    def find(self, rid: str) -> tuple[Path, dict[str, Any]]:
        """The folder and manifest of run ``rid``; 404 with E185 when no registered
        project has it, or its manifest cannot be read."""
        if RUN_ID_PATTERN.fullmatch(rid) is not None:
            folders = []
            for entry in self.projects.entries():
                if entry["available"]:
                    folder = Path(entry["path"])
                    self._prepare(entry["id"], folder)
                    folders.append(folder)
            for folder in folders:
                index = self._index(folder)
                if not index.contains(rid) and (folder / RUNS_FOLDER / rid).is_dir():
                    index.sync()  # a run folder the index lacks: the index is a cache
                if index.contains(rid):
                    manifest = read_run_manifest(folder / RUNS_FOLDER / rid)
                    if manifest is None:
                        raise _not_found(f"The manifest of the run '{rid}' cannot be read.")
                    return folder / RUNS_FOLDER / rid, manifest
        raise _not_found(f"There is no run '{rid}'.")

    def run(self, rid: str) -> dict[str, Any]:
        """Run ``rid`` as the API shows it."""
        return self._view(self.find(rid)[1])

    def cancel(self, rid: str) -> dict[str, Any]:
        """Cancels run ``rid``; 409 with E188 when it has ended."""
        self.find(rid)
        with self._lock:
            active = self._active.get(rid)
        if active is None or not active.run.cancel():
            raise _not_allowed(f"The run '{rid}' has ended, so it cannot be cancelled.")
        return self.run(rid)

    def _done(self, rid: str) -> tuple[Path, dict[str, Any]]:
        """The folder and manifest of run ``rid``, which must be ``done``."""
        folder, manifest = self.find(rid)
        state = self._view(manifest)["state"]
        if state != "done":
            raise _not_allowed(
                f"The run '{rid}' is {state}, so it has no results; they are written when it "
                "is done."
            )
        return folder, manifest

    def _run_model(self, rid: str, folder: Path, manifest: Mapping[str, Any]) -> Model:
        """The model that ran: the run folder's ``model.json``, loaded as the run loaded it
        except that its ``data`` references are not checked against the project's data
        again (the project's files may have changed or gone since; the run holds its own
        copies, and the finding rules read no data). The manifest's seed stands in for a
        seed the file leaves out. 404 with E185 when it cannot be read or loaded (a file
        changed outside the product)."""
        unreadable = _not_found(
            f"The {MODEL_FILE} of the run '{rid}' cannot be read as the model that ran, so its "
            "findings cannot be made."
        )
        try:
            document = read_json_file(folder / MODEL_FILE)
        except (OSError, ValueError):  # the strict reader's refusal is a ValueError
            raise unreadable from None
        seed = manifest.get("seed")
        built = build_document(
            document,
            seed_source=lambda: seed if isinstance(seed, int) else 0,
            engines=installed_engines(self.adapters),
        )
        if built.model is None:
            raise unreadable
        problems = [
            issue
            for issue in meaning_pass(built.model)
            if issue.severity == "error" and issue.code != "E162"
        ]
        if problems:
            raise unreadable
        return built.model

    def summary(self, rid: str) -> dict[str, Any]:
        """``{summary, findings, issues}`` of run ``rid``: ``summary.json``, the findings of
        ``ithax.findings`` for it and the model that ran, at the thresholds of
        ``settings.json`` read now, and the W220 issues of reading them (AKS-135)."""
        folder, manifest = self._done(rid)
        try:
            summary = read_json_file(folder / SUMMARY_FILE)
        except (OSError, ValueError):  # the strict reader's refusal is a ValueError
            raise _not_found(f"The {SUMMARY_FILE} of the run '{rid}' cannot be read.") from None
        model = self._run_model(rid, folder, manifest)
        settings = read_finding_settings(self.config_dir)
        not_results = _not_found(
            f"The {SUMMARY_FILE} of the run '{rid}' does not hold a run's results, so its "
            "findings cannot be made."
        )
        if not isinstance(summary, dict):
            raise not_results
        try:
            findings = find(summary, model, settings.thresholds)
        except Exception:
            # The rules read a summary.json the product wrote; one changed outside it into
            # JSON of another layout cannot be read, which is E185, never a 500. The
            # traceback goes to the log.
            _log.warning("The findings of the run %s cannot be made.", rid, exc_info=True)
            raise not_results from None
        return {
            "summary": summary,
            "findings": [finding.as_dict() for finding in findings],
            "issues": [issue.as_dict() for issue in settings.issues],
        }

    def table(self, rid: str, name: str, form: str | None) -> Table:
        """Table ``name`` of run ``rid`` in ``form`` (``json`` when ``None``)."""
        chosen = "json" if form is None else form
        if chosen not in TABLE_FORMATS:
            raise malformed(
                [
                    Issue(
                        code=MALFORMED,
                        component=None,
                        path="",
                        message=f"The query parameter 'format' is '{form}', which is not json "
                        "or csv.",
                        hint="Send ?format=json or ?format=csv, or leave it out for json.",
                    )
                ]
            )
        if name not in TABLE_NAMES:
            self.find(rid)
            raise _not_found(
                f"There is no table '{name}'; a run's tables are {' and '.join(TABLE_NAMES)}."
            )
        folder, _ = self._done(rid)
        try:
            table = pq.read_table(folder / TABLES_FOLDER / f"{name}.parquet")
        except (OSError, pa.ArrowException):
            raise _not_found(f"The run '{rid}' has no readable table '{name}'.") from None
        rows = table.to_pylist()
        if chosen == "json":
            return Table(
                "json", rows=[{key: _cell(value) for key, value in row.items()} for row in rows]
            )
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(table.column_names)
        for row in rows:
            writer.writerow([_csv_cell(row[column]) for column in table.column_names])
        return Table("csv", text=out.getvalue())
