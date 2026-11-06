"""The ``local`` run target (spec 1 "Run targets" and "Run folder and results"; AKS-103).

``LocalTarget(runs_root).create(model_file, experiment_id)`` checks a run and, when nothing
refuses it, creates ``runs_root/<run_id>/`` in state ``queued``; ``LocalRun.execute()``
then runs it to a final state, and ``LocalRun.cancel()`` (from any thread) cancels it.

Before a run exists: the file is loaded; a ``run.target`` other than ``local`` is E172;
the adapter is chosen (E102); the adapter's ``validate`` and the fidelity check (E173)
run. Any error raises ``RunRefused`` with the issues, and nothing is created.

The run folder: ``model.json`` (the file's bytes, unchanged), ``manifest.json``
(``lcsim.runs.manifest``), ``log.txt``, ``engine/`` (the adapter's ``workdir``), and when
done ``summary.json`` and ``tables/``. ``worker.lock`` is held while the run is unfinished
(``lcsim.runs.lock``), so that ``recover_interrupted`` can apply E191 after a restart.

Where each method runs: ``validate``, ``translate`` and ``collect`` in the process that
calls ``create`` and ``execute``; ``run`` in a worker process started with ``spawn``
(``lcsim.runs.worker.child_main``), whose token is a ``multiprocessing.Event``. While the
worker runs, this process reads its reports, writes progress to the manifest at most once
a second, and enforces the limits (``lcsim.runs.limits``): E192 sets the token, gives the
worker ``limit_grace_s`` to stop and then terminates it. A cancelled worker that has not
stopped after ``cancel_grace_s`` is terminated too. An exception from ``translate``,
``run`` or ``collect``, or a worker that ends without reporting, is E190, with the details
in ``log.txt``.
"""

from __future__ import annotations

import multiprocessing
import socket
import threading
import time
import traceback
from collections.abc import Mapping
from datetime import UTC, datetime
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import Any

from lcsim.engines.adapter import EngineAdapter
from lcsim.engines.registry import installed_engines, select_adapter
from lcsim.model.issues import Issue, pointer
from lcsim.model.loading import SeedSource, load_text
from lcsim.model.model import Model
from lcsim.runs.ids import new_run_id
from lcsim.runs.limits import Limits, limit_exceeded, process_tree_memory
from lcsim.runs.lock import LOCK_FILE, RunLock, is_held, take_lock
from lcsim.runs.manager import check_experiment, collect_summary
from lcsim.runs.manifest import (
    MANIFEST_FILE,
    ManifestWriter,
    new_manifest,
    read_manifest,
    utc_text,
    write_manifest,
)
from lcsim.runs.states import FINAL_STATES, JobState, check_move
from lcsim.runs.tables import write_summary, write_tables
from lcsim.runs.worker import child_main

__all__ = [
    "CANCEL_GRACE_S",
    "LIMIT_GRACE_S",
    "LOG_FILE",
    "MODEL_FILE",
    "LocalRun",
    "LocalTarget",
    "RunRefused",
    "describe_bytes",
    "describe_seconds",
    "now",
    "recover_interrupted",
]

MODEL_FILE = "model.json"
LOG_FILE = "log.txt"
ENGINE_FOLDER = "engine"

#: How long a cancelled worker may take to stop before it is terminated.
CANCEL_GRACE_S = 5.0
#: How long a worker over a limit may take to stop before it is terminated.
LIMIT_GRACE_S = 2.0
#: How often this process looks at the worker, its reports and the time limit.
POLL_S = 0.1
#: How often the worker's memory is read.
MEMORY_POLL_S = 1.0


def now() -> datetime:
    """The current time in UTC."""
    return datetime.now(UTC)


class RunRefused(Exception):
    """A run refused before it was created; ``issues`` say why (spec 1 issue objects)."""

    def __init__(self, issues: tuple[Issue, ...]) -> None:
        self.issues = issues
        codes = ", ".join(issue.code for issue in issues)
        super().__init__(f"the run was refused: {codes}")


def describe_seconds(seconds: float) -> str:
    """A time limit in words: whole minutes as "10 min", otherwise seconds."""
    if seconds >= 60 and seconds % 60 == 0:
        return f"{int(seconds // 60)} min"
    return f"{seconds:g} s"


def describe_bytes(size: int) -> str:
    """A memory limit in binary units: "8 GiB", "1.5 GiB", "5 MiB", "1 B"."""
    for unit, scale in (("GiB", 2**30), ("MiB", 2**20), ("KiB", 2**10)):
        if size >= scale:
            return f"{size / scale:.3g} {unit}"
    return f"{size} B"


def _target_issue(target: object) -> Issue | None:
    """E172 for a ``run.target`` this build cannot run (spec 1 "Run targets")."""
    if target == "local":
        return None
    shown = f"'{target}'" if isinstance(target, str) else str(target)
    return Issue(
        code="E172",
        component=None,
        path=pointer("run", "target"),
        message=f"The run target {shown} is not available on this build: only 'local' "
        "runs before M11.",
        hint="Set 'target' in 'run' to 'local'.",
    )


def _engine_error(engine: str) -> Issue:
    return Issue(
        code="E190",
        component=None,
        path="",
        message=f"The engine '{engine}' stopped with an error, so the run failed.",
        hint="The details are in log.txt in the run folder; check the model, then run again.",
    )


def _interrupted() -> Issue:
    return Issue(
        code="E191",
        component=None,
        path="",
        message="The run was interrupted by a service restart.",
        hint="Run it again.",
    )


def _limit_issue(which: str, limits: Limits) -> Issue:
    if which == "time":
        limit = describe_seconds(limits.time_s)
        message = f"The run exceeded its time limit of {limit}."
        hint = "Shorten the run (fewer replications or a shorter length) or raise the time "
    else:
        assert limits.memory_bytes is not None  # only an enforced limit is exceeded
        limit = describe_bytes(limits.memory_bytes)
        message = f"The run exceeded its memory limit of {limit}."
        hint = "Make the run smaller (fewer workers or a shorter length) or raise the memory "
    return Issue(
        code="E192", component=None, path="", message=message, hint=hint + "limit in Settings."
    )


class LocalTarget:
    """Creates runs in ``runs_root`` on this machine.

    ``workers`` is passed to the adapter's ``run`` (spec 3: the cores of the active tier).
    ``client`` (``ui``, ``mcp`` or ``script``) and ``project_id`` go into the manifest; the
    service sets them from M6. ``adapters`` defaults to the installed adapters.
    """

    def __init__(
        self,
        runs_root: Path,
        *,
        workers: int = 1,
        limits: Limits | None = None,
        client: str = "script",
        project_id: str | None = None,
        adapters: Mapping[str, EngineAdapter] | None = None,
        cancel_grace_s: float = CANCEL_GRACE_S,
        limit_grace_s: float = LIMIT_GRACE_S,
    ) -> None:
        self.runs_root = runs_root
        self.workers = workers
        self.limits = Limits() if limits is None else limits
        self.client = client
        self.project_id = project_id
        self.adapters = adapters
        self.cancel_grace_s = cancel_grace_s
        self.limit_grace_s = limit_grace_s

    def create(
        self, model_file: bytes, experiment_id: str, *, seed_source: SeedSource | None = None
    ) -> LocalRun:
        """Checks a run of experiment ``experiment_id`` of the model file ``model_file``
        and creates it, ``queued``.

        Raises ``RunRefused`` when any check finds an error (nothing is created),
        ``ValueError`` for an experiment the model does not have, and
        ``NotImplementedError`` for a search or an optimization model (M5).
        ``seed_source`` gives the seed of an experiment the file leaves without one.
        """
        engines = None if self.adapters is None else installed_engines(self.adapters)
        loaded = load_text(model_file, seed_source=seed_source, engines=engines)
        if loaded.model is None:
            raise RunRefused(loaded.issues)
        model = loaded.model
        target_issue = _target_issue(model.run.target)
        if target_issue is not None:
            raise RunRefused((target_issue,))
        selection = select_adapter(model.domain, model.run.engine, self.adapters)
        # Loading checked run.engine against the same engines (E102), so the choice holds.
        assert not selection.issues
        if selection.adapter is None:
            raise NotImplementedError(
                f"a {model.domain} model runs from M5 (spec 2 'Mathematical optimization')"
            )
        adapter = selection.adapter
        checked = check_experiment(adapter, model, experiment_id)
        if any(issue.severity == "error" for issue in checked):
            raise RunRefused(checked)
        warnings = (*loaded.warnings, *checked)
        return LocalRun(self, model_file, model, experiment_id, adapter, warnings)


class LocalRun:
    """One run on the local target: created ``queued``; ``execute`` runs it."""

    def __init__(
        self,
        target: LocalTarget,
        model_file: bytes,
        model: Model,
        experiment_id: str,
        adapter: EngineAdapter,
        warnings: tuple[Issue, ...],
    ) -> None:
        self._target = target
        self._model = model
        self._experiment_id = experiment_id
        self._adapter = adapter
        self._warnings = warnings
        self._mutex = threading.RLock()
        self._cancel = multiprocessing.get_context("spawn").Event()
        self._cancelled_at: float | None = None
        self._started_at = 0.0
        self._memory_noted = False
        experiment = next(item for item in model.experiments if item.id == experiment_id)
        target.runs_root.mkdir(parents=True, exist_ok=True)
        while True:
            created = now()
            run_id = new_run_id(created)
            folder = target.runs_root / run_id
            try:
                folder.mkdir()
            except FileExistsError:
                continue
            break
        self.run_id = run_id
        self.folder = folder
        self.engine_folder = folder / ENGINE_FOLDER
        self._lock: RunLock | None = take_lock(folder / LOCK_FILE)
        (folder / MODEL_FILE).write_bytes(model_file)
        self.engine_folder.mkdir()
        self._manifest = ManifestWriter(
            folder,
            new_manifest(
                run_id=run_id,
                project_id=target.project_id,
                experiment_id=experiment_id,
                scenario_ids=[scenario.id for scenario in experiment.scenarios],
                created=created,
                host=socket.gethostname(),
                client=target.client,
                engine_name=adapter.name,
                engine_version=adapter.version,
                format_version=model.format_version,
                seed=experiment.seed,
            ),
        )
        self.log("state queued")

    @property
    def state(self) -> JobState:
        """The run's job state."""
        state: JobState = self._manifest.data["state"]
        return state

    @property
    def manifest(self) -> dict[str, Any]:
        """A copy of the run's manifest."""
        return self._manifest.data

    def log(self, text: str) -> None:
        """Appends a line, stamped with the UTC time, to ``log.txt``."""
        with (self.folder / LOG_FILE).open("a", encoding="utf-8") as stream:
            stream.write(f"{utc_text(now())} {text}\n")

    def move(self, state: JobState, **fields: object) -> None:
        """Moves the run to ``state`` and writes the manifest; a move spec 1 does not allow
        raises ``StateError``. A final state also sets ``ended`` and releases the lock."""
        with self._mutex:
            check_move(self.state, state)
            if state == "running":
                fields["started"] = utc_text(now())
            if state in FINAL_STATES:
                fields["ended"] = utc_text(now())
            self._manifest.update(state=state, **fields)
            self.log(f"state {state}")
            if state in FINAL_STATES and self._lock is not None:
                self._lock.release(remove=True)
                self._lock = None

    def cancel(self) -> None:
        """Cancels the run: a queued run is ``cancelled`` at once; a running run's token is
        set and the run ends ``cancelled``. A finished run is left as it is."""
        with self._mutex:
            if self.state == "queued":
                self._cancel.set()
                self.move("cancelled")
            elif self.state == "running":
                self._cancelled_at = time.monotonic()
                self._cancel.set()
                self.log("cancel requested")

    def _fail(self, issue: Issue, details: str) -> JobState:
        self.log(details.rstrip("\n"))
        self.move("failed", error=issue.as_dict())
        return "failed"

    def execute(self) -> JobState:
        """Runs the run to a final state and returns it; a run that is not ``queued`` is
        left as it is."""
        with self._mutex:
            if self.state != "queued":
                return self.state
            self.move("running")
            self._started_at = time.monotonic()
        engine = self._adapter.name
        try:
            self._adapter.translate(self._model, self._experiment_id, self.engine_folder)
        except Exception:
            return self._fail(_engine_error(engine), "translate raised:\n" + traceback.format_exc())
        if self._cancel.is_set():
            return self._end_cancelled()
        failure = self._run_worker()
        if failure is not None:
            return self._fail(*failure)
        if self._cancel.is_set():
            return self._end_cancelled()
        try:
            results, summary = collect_summary(
                self._adapter, self._model, self._experiment_id, self.engine_folder, self._warnings
            )
            write_tables(results.tables, self.folder)
            write_summary(summary, self.folder)
        except Exception:
            return self._fail(_engine_error(engine), "collect raised:\n" + traceback.format_exc())
        self.move("done", fraction=1.0)
        return "done"

    def _end_cancelled(self) -> JobState:
        self.move("cancelled")
        return "cancelled"

    def _run_worker(self) -> tuple[Issue, str] | None:
        """Runs ``run`` in a spawned worker; the E190 or E192 issue and the details for
        ``log.txt`` when it failed, otherwise ``None`` (finished or cancelled)."""
        context = multiprocessing.get_context("spawn")
        receive, send = context.Pipe(duplex=False)
        worker = context.Process(
            target=child_main,
            args=(
                type(self._adapter),
                str(self.engine_folder),
                self._cancel,
                self._target.workers,
                send,
            ),
            name=f"lcsim-run-{self.run_id}",
        )
        worker.start()
        send.close()
        pid = worker.pid
        assert pid is not None  # set by start()
        self.log(f"worker started, process {pid}")
        report, exceeded = self._watch(worker, pid, receive)
        receive.close()
        exit_code = worker.exitcode
        self.log(f"worker ended, exit status {exit_code}")
        if exceeded is not None:
            return _limit_issue(exceeded, self._target.limits), f"{exceeded} limit exceeded"
        if report is not None and report[0] == "error":
            return _engine_error(self._adapter.name), "run raised:\n" + str(report[1])
        if report is None and not self._cancel.is_set():
            return (
                _engine_error(self._adapter.name),
                f"the worker ended without reporting, exit status {exit_code}",
            )
        return None

    def _watch(
        self, worker: BaseProcess, pid: int, receive: Connection
    ) -> tuple[tuple[Any, ...] | None, str | None]:
        """Reads the worker's reports until it ends; returns its last report
        (``finished`` or ``error``) and the limit it exceeded, if any."""
        limits = self._target.limits
        report: tuple[Any, ...] | None = None
        memory: int | None = None
        next_memory = 0.0
        while True:
            if receive.poll(POLL_S):
                try:
                    message = receive.recv()
                except EOFError:
                    break
                if message[0] == "progress":
                    with self._mutex:  # cancel() may write from another thread
                        self._manifest.progress(float(message[1]))
                else:
                    report = message
            clock = time.monotonic()
            if clock >= next_memory:
                next_memory = clock + MEMORY_POLL_S
                memory = self._read_memory(pid)
            exceeded = limit_exceeded(
                limits, elapsed_s=clock - self._started_at, memory_bytes=memory
            )
            if exceeded is not None:
                self.log(f"{exceeded} limit exceeded; stopping the worker")
                self._cancel.set()
                self._stop(worker, self._target.limit_grace_s)
                return report, exceeded
            if (
                self._cancelled_at is not None
                and clock - self._cancelled_at > self._target.cancel_grace_s
            ):
                self._stop(worker, 0.0)
        worker.join()
        return report, None

    def _read_memory(self, pid: int) -> int | None:
        if self._target.limits.memory_bytes is None:
            reading = None
        else:
            reading = process_tree_memory(pid)
        if reading is None and not self._memory_noted:
            self._memory_noted = True
            self.log("the memory limit is not enforced: memory cannot be read here")
        return reading

    def _stop(self, worker: BaseProcess, grace_s: float) -> None:
        worker.join(grace_s)
        if worker.is_alive():
            worker.terminate()
            worker.join()
            self.log("worker terminated")


def recover_interrupted(runs_root: Path) -> list[str]:
    """E191: marks ``failed`` every run in ``runs_root`` whose manifest says ``queued`` or
    ``running`` and whose process is gone (its ``worker.lock`` can be taken, or is
    missing); returns their ``run_id`` values in order. The service calls this on start.
    """
    if not runs_root.is_dir():
        return []
    marked: list[str] = []
    for folder in sorted(runs_root.iterdir()):
        if not (folder / MANIFEST_FILE).is_file():
            continue
        if read_manifest(folder)["state"] not in ("queued", "running"):
            continue
        # The service runs this on start, before it starts any run, and is the only one
        # (spec 3 "One service per user"), so no live run finishes between these reads.
        lock_path = folder / LOCK_FILE
        if is_held(lock_path):
            continue
        manifest = read_manifest(folder)
        check_move(manifest["state"], "failed")
        manifest.update(state="failed", ended=utc_text(now()), error=_interrupted().as_dict())
        write_manifest(folder, manifest)
        with (folder / LOG_FILE).open("a", encoding="utf-8") as stream:
            stream.write(f"{utc_text(now())} state failed: E191, the run's process is gone\n")
        lock_path.unlink(missing_ok=True)
        marked.append(folder.name)
    return marked
