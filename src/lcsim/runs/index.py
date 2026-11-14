"""``index.sqlite``, the run index of a project (spec 3 "Project folder"; spec 1 "Run folder
and results"; AKS-112).

The index is a cache: the run ids of the project's ``runs/`` in the order the runs were
accepted, each with its ``created`` time and ``experiment_id``. The manifests are the source
of truth, so a run's state is never kept here. ``RunIndex`` rebuilds the file from the run
folders when it is missing or cannot be read (in the order of ``created``, then ``run_id``),
and ``sync`` also adds the run folders it lacks and drops those that are gone.

Each operation opens its own connection, so the index can be used from any thread; one lock
per ``RunIndex`` makes them one at a time. A rebuild writes a new file beside the old one
and renames it into place, so a reader never sees half an index.
"""

from __future__ import annotations

import contextlib
import logging
import sqlite3
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, TypeVar

from lcsim.files import atomic_write_with
from lcsim.runs.ids import RUN_ID_PATTERN
from lcsim.runs.manifest import read_run_manifest

__all__ = ["INDEX_FILE", "RUNS_FOLDER", "RunIndex", "readable_runs"]

INDEX_FILE = "index.sqlite"
RUNS_FOLDER = "runs"

_log = logging.getLogger(__name__)

_T = TypeVar("_T")

_SCHEMA = (
    "CREATE TABLE runs (seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL UNIQUE, "
    "created TEXT NOT NULL, experiment_id TEXT)"
)


def readable_runs(runs_root: Path) -> list[tuple[str, dict[str, Any]]]:
    """The runs in ``runs_root`` with their manifests, in the order of ``created``, then
    ``run_id``; a folder that is not a run (``read_run_manifest``) is left out."""
    if not runs_root.is_dir():
        return []
    found: list[tuple[str, dict[str, Any]]] = []
    for folder in runs_root.iterdir():
        if RUN_ID_PATTERN.fullmatch(folder.name) is None:
            continue
        manifest = read_run_manifest(folder)
        if manifest is not None:
            found.append((folder.name, manifest))
    found.sort(key=lambda item: (item[1]["created"], item[0]))
    return found


@contextlib.contextmanager
def _connected(path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path, timeout=30, isolation_level=None)
    try:
        yield connection
    finally:
        connection.close()


class RunIndex:
    """The run index of the project in ``project_folder``."""

    def __init__(self, project_folder: Path) -> None:
        self.path = project_folder / INDEX_FILE
        self.runs_root = project_folder / RUNS_FOLDER
        self._lock = threading.Lock()

    # --- building --------------------------------------------------------------------

    def _rebuild(self) -> None:
        """Writes a new index from the run folders and renames it into place."""
        rows = [
            (rid, manifest["created"], _text(manifest.get("experiment_id")))
            for rid, manifest in readable_runs(self.runs_root)
        ]

        def write(temporary: Path) -> None:
            with _connected(temporary) as connection:
                connection.execute(_SCHEMA)
                connection.executemany(
                    "INSERT INTO runs (run_id, created, experiment_id) VALUES (?, ?, ?)", rows
                )

        atomic_write_with(self.path, write)

    def _use(self, action: Callable[[sqlite3.Connection], _T]) -> _T:
        """``action`` on the index, rebuilding it once when it is missing or cannot be
        read."""
        with self._lock:
            if self.path.is_file():
                try:
                    with _connected(self.path) as connection:
                        return action(connection)
                except sqlite3.DatabaseError:
                    _log.warning(
                        "%s cannot be read; it is rebuilt from the run folders.", self.path
                    )
            self._rebuild()
            with _connected(self.path) as connection:
                return action(connection)

    # --- using -----------------------------------------------------------------------

    def sync(self) -> None:
        """Makes the index match the run folders: rebuilt when missing or unreadable,
        runs it lacks added in ``created`` order, runs whose folder is gone dropped."""

        def update(connection: sqlite3.Connection) -> None:
            listed = {row[0] for row in connection.execute("SELECT run_id FROM runs")}
            present = readable_runs(self.runs_root)
            names = {rid for rid, _ in present}
            connection.executemany(
                "DELETE FROM runs WHERE run_id = ?", [(rid,) for rid in listed - names]
            )
            connection.executemany(
                "INSERT INTO runs (run_id, created, experiment_id) VALUES (?, ?, ?)",
                [
                    (rid, manifest["created"], _text(manifest.get("experiment_id")))
                    for rid, manifest in present
                    if rid not in listed
                ],
            )

        self._use(update)

    def add(self, run_id: str, created: str, experiment_id: str | None) -> None:
        """Adds a run just accepted, after every run already listed; a run listed already
        is left where it is."""
        self._use(
            lambda connection: connection.execute(
                "INSERT OR IGNORE INTO runs (run_id, created, experiment_id) VALUES (?, ?, ?)",
                (run_id, created, experiment_id),
            )
        )

    def run_ids(self) -> list[str]:
        """Every run id in the index, in the order the runs were accepted; a row that is
        not a ``run_id`` (the file was changed outside the product) is left out."""
        return self._use(
            lambda connection: [
                row[0]
                for row in connection.execute("SELECT run_id FROM runs ORDER BY seq")
                if isinstance(row[0], str) and RUN_ID_PATTERN.fullmatch(row[0]) is not None
            ]
        )

    def contains(self, run_id: str) -> bool:
        """Whether the index lists ``run_id``."""
        return self._use(
            lambda connection: (
                connection.execute("SELECT 1 FROM runs WHERE run_id = ?", (run_id,)).fetchone()
                is not None
            )
        )


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None
