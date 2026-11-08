"""The ``local`` run target (spec 1 "Run targets" and "Run folder and results"; AKS-103).

``LocalTarget(runs_root).create(model_file, experiment_id)`` checks a run and, when nothing
refuses it, creates ``runs_root/<run_id>/`` in state ``queued`` (an ``optimization`` model
has no experiments and is created with ``experiment_id`` ``None``; AKS-108); ``LocalRun.execute()``
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

A search experiment (spec 2 "Simulation-based optimization"; AKS-109) runs the same way once
per candidate evaluation, each in its own subfolder of ``engine/`` (``search-<n>``,
``confirm-<n>``; ``lcsim.runs.search``), with one worker per evaluation and one time limit for
the whole run. The run folder's ``summary.json`` and ``tables/`` are the best candidate's
confirmation with the ``search`` object, and the manifest names the search method and the
Optuna version in ``optimizer``.

For the service (AKS-112): ``on_state`` is told of every state change after the manifest is
written, and ``on_progress`` of every progress report with its message; ``create`` takes a
``target`` that overrides the file's ``run.target`` and is recorded in the manifest;
``cancel`` says whether it was accepted; ``interrupt`` stops a run as a cancel does but ends
it ``failed`` with E191, for a service that stops while the run is unfinished.
"""

from __future__ import annotations

import contextlib
import multiprocessing
import os
import signal
import socket
import threading
import time
import traceback
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import Any

from lcsim.engines.adapter import EngineAdapter, Progress, Results
from lcsim.engines.registry import installed_engines, select_adapter
from lcsim.model.issues import Issue, pointer
from lcsim.model.loading import SeedSource, load_text
from lcsim.model.model import Model
from lcsim.runs.ids import new_run_id
from lcsim.runs.limits import Limits, descendant_ids, limit_exceeded, process_tree_memory
from lcsim.runs.lock import LOCK_FILE, RunLock, is_held, take_lock
from lcsim.runs.manager import check_experiment, collect_summary
from lcsim.runs.manifest import (
    ManifestWriter,
    new_manifest,
    read_run_manifest,
    utc_text,
    write_manifest,
)
from lcsim.runs.search import (
    optimizer_record,
    run_search,
    search_method,
    search_summary,
)
from lcsim.runs.states import FINAL_STATES, JobState, check_move
from lcsim.runs.tables import write_summary, write_tables
from lcsim.runs.worker import child_main

__all__ = [
    "CANCEL_GRACE_S",
    "KILL_GRACE_S",
    "LIMIT_GRACE_S",
    "LOG_FILE",
    "MODEL_FILE",
    "LocalRun",
    "LocalTarget",
    "ProgressHook",
    "RunRefused",
    "StateHook",
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
#: How long a terminated worker may take to end before it is killed (``terminate`` is
#: SIGTERM on POSIX, which a worker can ignore; ``kill`` is SIGKILL).
KILL_GRACE_S = 2.0
#: How often this process looks at the worker, its reports and the time limit.
POLL_S = 0.1
#: How often the worker's memory is read.
MEMORY_POLL_S = 1.0
#: The signal that ends a forcibly stopped worker's own processes (SIGKILL where it
#: exists; Windows has none, and has no /proc to find them either).
_KILL = getattr(signal, "SIGKILL", signal.SIGTERM)


#: Told of every state change of a run, after its manifest is written (AKS-112).
StateHook = Callable[["LocalRun", JobState], None]
#: Told of every progress report of a run: its fraction and message (AKS-112).
ProgressHook = Callable[["LocalRun", float, str], None]


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


def _target_issue(target: object, *, requested: bool = False) -> Issue | None:
    """E172 for a run target this build cannot run (spec 1 "Run targets"): the file's
    ``run.target``, or with ``requested`` the ``target`` of the request (AKS-112)."""
    if target == "local":
        return None
    shown = f"'{target}'" if isinstance(target, str) else str(target)
    if requested:
        return Issue(
            code="E172",
            component=None,
            path="/target",
            message=f"The run target {shown} named in the request is not available on this "
            "build: only 'local' runs before M11.",
            hint="Send 'target' as 'local', or leave it out.",
        )
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


class _EvaluationFailed(Exception):
    """A search's candidate evaluation failed: the issue and the details for ``log.txt``."""

    def __init__(self, issue: Issue, details: str) -> None:
        super().__init__(issue.code)
        self.issue = issue
        self.details = details


class LocalTarget:
    """Creates runs in ``runs_root`` on this machine.

    ``workers`` is passed to the adapter's ``run`` (spec 3: the cores of the active tier).
    ``client`` (``ui``, ``mcp`` or ``script``) and ``project_id`` go into the manifest; the
    service sets them from M6. ``adapters`` defaults to the installed adapters.
    ``on_state`` and ``on_progress`` are told of each run's state changes and progress
    reports (AKS-112); they are called while the run's lock is held, so they must be quick
    and must not call back into the run.
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
        kill_grace_s: float = KILL_GRACE_S,
        on_state: StateHook | None = None,
        on_progress: ProgressHook | None = None,
    ) -> None:
        self.runs_root = runs_root
        self.workers = workers
        self.limits = Limits() if limits is None else limits
        self.client = client
        self.project_id = project_id
        self.adapters = adapters
        self.cancel_grace_s = cancel_grace_s
        self.limit_grace_s = limit_grace_s
        self.kill_grace_s = kill_grace_s
        self.on_state = on_state
        self.on_progress = on_progress

    def create(
        self,
        model_file: bytes,
        experiment_id: str | None = None,
        *,
        target: str | None = None,
        seed_source: SeedSource | None = None,
    ) -> LocalRun:
        """Checks a run of experiment ``experiment_id`` of the model file ``model_file``
        (``None`` for an optimization model, which has no experiments) and creates it,
        ``queued``.

        Raises ``RunRefused`` when any check finds an error (nothing is created) and
        ``ExperimentChoiceError`` (a ``ValueError``) for an experiment the model does not
        have, an experiment id for an optimization model or none for a process model.
        ``target``, when given, replaces the file's ``run.target`` (spec 3 ``POST .../runs``;
        E172 at ``/target`` unless it is ``local``). ``seed_source`` gives the seed of an
        experiment the file leaves without one.
        """
        engines = None if self.adapters is None else installed_engines(self.adapters)
        loaded = load_text(model_file, seed_source=seed_source, engines=engines)
        if loaded.model is None:
            raise RunRefused(loaded.issues)
        model = loaded.model
        if target is None:
            target_issue = _target_issue(model.run.target)
        else:
            target_issue = _target_issue(target, requested=True)
        if target_issue is not None:
            raise RunRefused((target_issue,))
        selection = select_adapter(model.domain, model.run.engine, self.adapters)
        # Loading checked run.engine against the same engines (E102), so the choice holds.
        adapter = selection.adapter
        assert adapter is not None and not selection.issues
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
        experiment_id: str | None,
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
        self._interrupted = False
        self._started_at = 0.0
        self._memory_noted = False
        self._on_report: Callable[[float, str], None] = self._record_progress
        experiment = next((item for item in model.experiments if item.id == experiment_id), None)
        self._search = experiment is not None and experiment.search is not None
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
                scenario_ids=[]
                if experiment is None
                else [scenario.id for scenario in experiment.scenarios],
                created=created,
                host=socket.gethostname(),
                client=target.client,
                engine_name=adapter.name,
                engine_version=adapter.version,
                format_version=model.format_version,
                target="local",
                seed=None if experiment is None else experiment.seed,
                optimizer=None
                if experiment is None or experiment.search is None
                else optimizer_record(search_method(model, experiment.search)),
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
            if self._target.on_state is not None:
                self._target.on_state(self, state)

    def cancel(self) -> bool:
        """Cancels the run: a queued run is ``cancelled`` at once; a running run's token is
        set and the run ends ``cancelled``. Returns whether the cancel was accepted: a
        finished run is left as it is and gives ``False``; a running run gives ``True``,
        also for a repeat."""
        with self._mutex:
            if self.state == "queued":
                self._cancel.set()
                self._end_cancelled()
                return True
            if self.state != "running":
                return False
            if self._cancelled_at is None:
                # Only the first cancel starts the grace: a repeat must not postpone it.
                self._cancelled_at = time.monotonic()
                self._cancel.set()
                self.log("cancel requested")
            return True

    def interrupt(self) -> None:
        """Stops the run because the service is stopping: as ``cancel``, but the run ends
        ``failed`` with E191 instead of ``cancelled`` (spec 3 "Runs outlive the interface";
        AKS-112). A finished run is left as it is."""
        with self._mutex:
            if self.state in FINAL_STATES:
                return
            self._interrupted = True
            self.log("the service is stopping")
            self.cancel()

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
        try:
            return self._drive()
        except Exception:
            # Not the adapter's error (those are handled where they arise) but this process's,
            # such as a hook that raised: the run must still end, or it would stay
            # ``running`` and hold the service (AKS-112). The worker is told to stop.
            self._cancel.set()
            details = "driving the run raised:\n" + traceback.format_exc()
            with self._mutex:
                if self.state in FINAL_STATES:
                    raise
                return self._fail(_engine_error(self._adapter.name), details)

    def _drive(self) -> JobState:
        """``execute`` once the run is ``running``."""
        if self._search:
            return self._execute_search()
        engine = self._adapter.name
        try:
            self._adapter.translate(self._model, self._experiment_id, self.engine_folder)
        except Exception:
            return self._fail(_engine_error(engine), "translate raised:\n" + traceback.format_exc())
        if self._cancel.is_set():
            return self._end_cancelled()
        failure = self._run_worker(self.engine_folder)
        if failure is not None:
            return self._fail(*failure)
        if self._cancel.is_set():
            return self._end_cancelled()
        try:
            results, summary = collect_summary(
                self._adapter, self._model, self._experiment_id, self.engine_folder, self._warnings
            )
        except Exception:
            return self._fail(_engine_error(engine), "collect raised:\n" + traceback.format_exc())
        return self._finish(results, summary)

    def _finish(self, results: Results, summary: dict[str, Any]) -> JobState:
        """Writes the tables and ``summary.json`` and moves the run to ``done``, unless a
        cancel came first."""
        # Holding the mutex, a cancel() either came before this check or finds the run
        # final: a cancel accepted while collecting is never lost.
        with self._mutex:
            if self._cancel.is_set():
                return self._end_cancelled()
            try:
                write_tables(results.tables, self.folder)
                write_summary(summary, self.folder)
            except Exception:
                return self._fail(
                    _engine_error(self._adapter.name),
                    "writing the results raised:\n" + traceback.format_exc(),
                )
            self.move("done", fraction=1.0)
        return "done"

    def _execute_search(self) -> JobState:
        """The search: every candidate evaluation translated and collected here, and run
        in a worker of its own."""
        engine = self._adapter.name
        assert self._experiment_id is not None  # a search belongs to an experiment

        def evaluate(
            model: Model, experiment_id: str, folder: Path, report: Callable[[Progress], None]
        ) -> Results | None:
            if self._cancel.is_set():
                return None
            folder.mkdir()
            self.log(f"evaluation {folder.name}")
            try:
                self._adapter.translate(model, experiment_id, folder)
            except Exception:
                details = f"translate raised in {folder.name}:\n" + traceback.format_exc()
                raise _EvaluationFailed(_engine_error(engine), details) from None
            if self._cancel.is_set():
                return None
            self._on_report = lambda fraction, message: report(Progress(fraction, message))
            try:
                failure = self._run_worker(folder)
            finally:
                self._on_report = self._record_progress
            if failure is not None:
                raise _EvaluationFailed(*failure)
            if self._cancel.is_set():
                return None
            try:
                return self._adapter.collect(folder)
            except Exception:
                details = f"collect raised in {folder.name}:\n" + traceback.format_exc()
                raise _EvaluationFailed(_engine_error(engine), details) from None

        def progress(report: Progress) -> None:
            self._record_progress(report.fraction, report.message)

        try:
            result = run_search(
                self._model, self._experiment_id, self.engine_folder, evaluate, progress
            )
            if result is None:
                return self._end_cancelled()
            summary = search_summary(self._model, self._experiment_id, result, self._warnings)
        except _EvaluationFailed as failed:
            return self._fail(failed.issue, failed.details)
        except Exception:
            return self._fail(
                _engine_error(engine), "the search raised:\n" + traceback.format_exc()
            )
        return self._finish(result.best_results, summary)

    def _record_progress(self, fraction: float, message: str) -> None:
        """Writes a progress fraction to the manifest (at most once a second) and tells
        ``on_progress``."""
        with self._mutex:  # cancel() may write from another thread
            self._manifest.progress(fraction)
            if self._target.on_progress is not None:
                self._target.on_progress(self, fraction, message)

    def _end_cancelled(self) -> JobState:
        """Ends a run whose token was set: ``cancelled``, or ``failed`` with E191 when the
        service stopped it."""
        if self._interrupted:
            self.move("failed", error=_interrupted().as_dict())
            return "failed"
        self.move("cancelled")
        return "cancelled"

    def _run_worker(self, workdir: Path) -> tuple[Issue, str] | None:
        """Runs ``run`` in ``workdir`` in a spawned worker; the E190 or E192 issue and the
        details for ``log.txt`` when it failed, otherwise ``None`` (finished or
        cancelled)."""
        context = multiprocessing.get_context("spawn")
        receive, send = context.Pipe(duplex=False)
        worker = context.Process(
            target=child_main,
            args=(
                type(self._adapter),
                str(workdir),
                self._cancel,
                self._target.workers,
                send,
            ),
            name=f"lcsim-run-{self.run_id}",
        )
        try:
            worker.start()
        except Exception:  # no process, file or memory left to start one
            send.close()
            receive.close()
            return (
                _engine_error(self._adapter.name),
                "the worker could not be started:\n" + traceback.format_exc(),
            )
        send.close()
        pid = worker.pid
        assert pid is not None  # set by start()
        self.log(f"worker started, process {pid}")
        try:
            report, exceeded = self._watch(worker, pid, receive)
        except BaseException:
            # Watching failed (a hook raised): the worker must not outlive the run, so it is
            # told to stop, given the limit grace, then ended with what it started (review
            # of PR #36).
            self._cancel.set()
            self._stop(worker, pid, self._target.limit_grace_s)
            receive.close()
            raise
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
        reporting = True
        while True:
            # The pipe closing does not mean the worker has ended (its interpreter may still
            # wait for threads or children), so it is watched until it has.
            if not reporting:
                worker.join(POLL_S)
                if not worker.is_alive():
                    break
            elif receive.poll(POLL_S):
                try:
                    message = receive.recv()
                except EOFError:
                    reporting = False
                    continue
                if message[0] == "progress":
                    self._on_report(float(message[1]), str(message[2]))
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
                self._stop(worker, pid, self._target.limit_grace_s)
                return report, exceeded
            if (
                self._cancelled_at is not None
                and clock - self._cancelled_at > self._target.cancel_grace_s
            ):
                self._stop(worker, pid, 0.0)
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

    def _stop(self, worker: BaseProcess, pid: int, grace_s: float) -> None:
        """Waits ``grace_s`` for the worker to end, then ends it and every process it
        started (found through ``/proc``; on Windows and macOS only the worker itself)."""
        worker.join(grace_s)
        if worker.is_alive():
            started = descendant_ids(pid)  # read first: they lose their parent below
            worker.terminate()
            worker.join(self._target.kill_grace_s)
            if worker.is_alive():
                worker.kill()
                worker.join()
                self.log("worker killed: it did not end when terminated")
            for child in started:
                with contextlib.suppress(OSError):  # it may have ended already
                    os.kill(child, _KILL)
            self.log(f"worker terminated, with {len(started)} process(es) it started")


def recover_interrupted(runs_root: Path) -> list[str]:
    """E191: marks ``failed`` every run in ``runs_root`` whose manifest says ``queued`` or
    ``running`` and whose process is gone (its ``worker.lock`` can be taken, or is
    missing); returns their ``run_id`` values in order. The service calls this on start.
    A folder that is not a run (``read_run_manifest``) is left as it is (AKS-112).
    """
    if not runs_root.is_dir():
        return []
    marked: list[str] = []
    for folder in sorted(runs_root.iterdir()):
        found = read_run_manifest(folder)
        if found is None or found["state"] not in ("queued", "running"):
            continue
        # The service runs this on start, before it starts any run, and is the only one
        # (spec 3 "One service per user"), so no live run finishes between these reads.
        lock_path = folder / LOCK_FILE
        if is_held(lock_path):
            continue
        manifest = found
        check_move(manifest["state"], "failed")
        manifest.update(state="failed", ended=utc_text(now()), error=_interrupted().as_dict())
        write_manifest(folder, manifest)
        with (folder / LOG_FILE).open("a", encoding="utf-8") as stream:
            stream.write(f"{utc_text(now())} state failed: E191, the run's process is gone\n")
        lock_path.unlink(missing_ok=True)
        marked.append(folder.name)
    return marked
