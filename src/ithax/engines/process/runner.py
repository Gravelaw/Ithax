"""Every scenario and replication of a run, in this process or in worker processes, and the
``replications`` and ``timeseries`` tables they make (spec 1 "Division of labour" and
"Tables for the ``process`` domain").

``run_all`` runs each (scenario, replication) pair once, the replications numbered by
their streams from the experiment's ``first_replication`` (0, or ``search.replications``
for a search's confirmation; #79), and the tables carry those numbers. With ``workers``
1 it runs them one after another in this process; otherwise in up to ``workers`` separately started
(``spawn``) processes, through ``concurrent.futures.ProcessPoolExecutor``. Each pair
depends only on the engine input and its own streams, and the rows are put in scenario
and replication order, so the table does not depend on ``workers``.

``cancel`` is checked at least every ``POLL_SECONDS``: in this process between batches of
events, and while workers run by the waiting loop, which then sets a stop event the
workers check between batches of events, drops the pairs not started and waits for the
running ones to stop. A cancelled run returns ``None``.

Progress is reported after each pair, with the fraction done and a message naming the
pair just finished: "Scenario 1 of 2, replication 12 of 30".
"""

from __future__ import annotations

import multiprocessing
from collections.abc import Callable, Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from functools import partial
from multiprocessing.synchronize import Event as ProcessEvent
from pathlib import Path
from typing import Any, TypeAlias

import pyarrow as pa
import pyarrow.parquet as pq

from ithax.engines.adapter import CancelToken, Progress, Table
from ithax.engines.process.replication import Outcome, run_replication
from ithax.engines.process.translate import read_input
from ithax.files import atomic_write_with

__all__ = [
    "POLL_SECONDS",
    "REPLICATIONS_SCHEMA",
    "TIMESERIES_SCHEMA",
    "Task",
    "init_worker",
    "replications_table",
    "run_all",
    "run_task",
    "timeseries_table",
    "write_table",
]

#: The longest wait between two checks of ``cancel`` while workers run.
POLL_SECONDS = 0.1

#: One (scenario index, replication) pair.
Task: TypeAlias = tuple[int, int]

#: Spec 1 "Tables for the ``process`` domain".
REPLICATIONS_SCHEMA = pa.schema(
    [
        ("scenario", pa.string()),
        ("replication", pa.int64()),
        ("metric", pa.string()),
        ("value", pa.float64()),
        ("unit", pa.string()),
    ]
)

#: Spec 1 "Tables for the ``process`` domain".
TIMESERIES_SCHEMA = pa.schema(
    [
        ("scenario", pa.string()),
        ("replication", pa.int64()),
        ("metric", pa.string()),
        ("time_s", pa.float64()),
        ("value", pa.float64()),
        ("unit", pa.string()),
    ]
)

# A worker process's engine input and stop event, set by ``init_worker``.
_worker_input: dict[str, Any] = {}
_worker_stop: list[ProcessEvent] = []


def init_worker(workdir: str, stop: ProcessEvent) -> None:
    """Prepares a worker process: reads the engine input once and keeps the stop event."""
    _worker_input.clear()
    _worker_input.update(read_input(Path(workdir)))
    _worker_stop[:] = [stop]


def run_task(scenario: int, replication: int) -> Outcome | None:
    """Runs one pair in a worker process that ``init_worker`` prepared."""
    return run_replication(_worker_input, scenario, replication, _worker_stop[0].is_set)


def _message(task: Task, scenarios: int, replications: int, first: int) -> str:
    """Progress counts the run's own replications from 1, whatever their stream numbers."""
    scenario, replication = task
    return (
        f"Scenario {scenario + 1} of {scenarios}, "
        f"replication {replication - first + 1} of {replications}"
    )


def run_all(
    workdir: Path,
    engine_input: Mapping[str, Any],
    on_progress: Callable[[Progress], None],
    cancel: CancelToken,
    workers: int,
) -> dict[Task, Outcome] | None:
    """The outcome of every pair, or ``None`` when ``cancel`` was set."""
    if workers < 1:
        raise ValueError(f"workers {workers!r} is below 1")
    scenarios = len(engine_input["scenarios"])
    replications = int(engine_input["experiment"]["replications"])
    # Replications are numbered by their streams, from first_replication (#79).
    first = int(engine_input["experiment"]["first_replication"])
    numbers = range(first, first + replications)
    tasks = [(scenario, rep) for scenario in range(scenarios) for rep in numbers]
    done: dict[Task, Outcome] = {}

    def record(task: Task, outcome: Outcome) -> None:
        done[task] = outcome
        fraction = len(done) / len(tasks)
        on_progress(Progress(fraction, _message(task, scenarios, replications, first)))

    if workers == 1:
        for task in tasks:
            outcome = run_replication(engine_input, *task, cancel.is_set)
            if outcome is None or cancel.is_set():
                return None
            record(task, outcome)
        return done

    if cancel.is_set():  # no worker is started for a run cancelled already
        return None
    return _run_in_workers(workdir, tasks, record, cancel, workers, done)


def _run_in_workers(
    workdir: Path,
    tasks: list[Task],
    record: Callable[[Task, Outcome], None],
    cancel: CancelToken,
    workers: int,
    done: dict[Task, Outcome],
) -> dict[Task, Outcome] | None:
    """Every pair in up to ``workers`` spawned processes, each recorded as it finishes;
    ``done``, or ``None`` when ``cancel`` was set."""
    context = multiprocessing.get_context("spawn")
    stop = context.Event()
    with ProcessPoolExecutor(
        max_workers=min(workers, len(tasks)),
        mp_context=context,
        initializer=init_worker,
        initargs=(str(workdir), stop),
    ) as pool:
        futures: dict[Future[Outcome | None], Task] = {
            pool.submit(run_task, *task): task for task in tasks
        }
        pending = set(futures)
        try:
            while pending:
                if cancel.is_set():
                    _stop_all(stop, pending)
                    return None  # leaving the block waits for the running pairs to stop
                finished, pending = wait(pending, timeout=POLL_SECONDS, return_when=FIRST_COMPLETED)
                for future in sorted(finished, key=futures.__getitem__):
                    outcome = future.result()
                    assert outcome is not None  # only a set stop event gives None
                    record(futures[future], outcome)
        except BaseException:
            # A pair raised (a RunIssue such as E196, or a fault): the other workers stop
            # and the pairs not started are cancelled, so leaving the block does not wait
            # for the rest of the run (review of PR #160).
            _stop_all(stop, pending)
            raise
    return done


def _stop_all(stop: ProcessEvent, pending: set[Future[Outcome | None]]) -> None:
    """Tells every worker to stop its pair and cancels the pairs not started."""
    stop.set()
    for future in pending:
        future.cancel()


def _table(
    engine_input: Mapping[str, Any],
    done: Mapping[Task, Outcome],
    schema: pa.Schema,
    rows_of: Callable[[Outcome], list[Any]],
) -> Table:
    """A table of rows from every pair, each row prefixed with its scenario id and
    replication, in scenario and replication order."""
    columns: dict[str, list[Any]] = {name: [] for name in schema.names}
    for task in sorted(done):
        scenario_id = engine_input["scenarios"][task[0]]["id"]
        for row in rows_of(done[task]):
            for name, value in zip(schema.names, (scenario_id, task[1], *row), strict=True):
                columns[name].append(value)
    return pa.table(columns, schema=schema)


def replications_table(engine_input: Mapping[str, Any], done: Mapping[Task, Outcome]) -> Table:
    """The ``replications`` table, in scenario and replication order."""
    return _table(engine_input, done, REPLICATIONS_SCHEMA, lambda outcome: outcome.rows)


def timeseries_table(engine_input: Mapping[str, Any], done: Mapping[Task, Outcome]) -> Table:
    """The ``timeseries`` table, in scenario and replication order, then by metric and
    time."""
    return _table(engine_input, done, TIMESERIES_SCHEMA, lambda outcome: outcome.series)


def write_table(table: Table, path: Path) -> None:
    """Writes ``table`` as Parquet, through a temporary file and a rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_with(path, partial(pq.write_table, table))
