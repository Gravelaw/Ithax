"""The worker process: where an adapter's ``run`` runs (spec 1 "Run targets"; AKS-103).

Two ways in, both platform-neutral (spec 3 "Architecture": no fork-only process code):

- ``child_main``: the function the ``local`` target starts with the ``spawn`` method. It
  creates the adapter's class with no arguments, calls ``run`` with the target's
  ``multiprocessing.Event`` as the token (``WatchedToken`` also reads as set once the
  process that started it has ended), and sends what happens through a pipe:
  ``("progress", fraction, message)`` for each report, then ``("finished",)`` or
  ``("error", traceback)``.
- ``python -m lcsim.runs.worker <workdir> [--workers N]``: the entry point the remote and
  cluster targets will invoke (M11). ``<workdir>`` is ``runs/<run_id>/engine/`` with the
  engine's input already translated. It reads the adapter's name from ``engine.name`` in
  ``<workdir>/../manifest.json``, creates that installed adapter, and calls
  ``run(workdir, on_progress, cancel, N)``, ``N`` defaulting to 1; ``cancel`` is set once
  a file named ``CANCEL`` exists in ``<workdir>`` (spec 1 "Engine adapter interface"),
  looked at no more than every 0.05 s. It prints one JSON line per progress report,
  ``{"type": "progress", "fraction": ..., "message": ...}`` (spec 3 "Progress events"),
  and exits with ``EXIT_DONE`` (0), ``EXIT_ERROR`` (1, the traceback on standard error),
  ``EXIT_USAGE`` (2: arguments, manifest or adapter unusable) or ``EXIT_CANCELLED`` (3).
  It writes nothing itself; limits are enforced by the side that started it.
"""

from __future__ import annotations

import argparse
import multiprocessing
import sys
import time
import traceback
from collections.abc import Callable, Mapping, Sequence
from multiprocessing.connection import Connection
from pathlib import Path
from typing import TextIO

from lcsim.engines.adapter import CancelToken, EngineAdapter, Progress
from lcsim.engines.registry import installed_adapters
from lcsim.strict_json import json_text, read_json_object_file

__all__ = [
    "CANCEL_FILE",
    "EXIT_CANCELLED",
    "EXIT_DONE",
    "EXIT_ERROR",
    "EXIT_USAGE",
    "FileCancelToken",
    "WatchedToken",
    "child_main",
    "main",
    "parent_alive",
]

#: The file whose presence in ``workdir`` cancels a remote or cluster run.
CANCEL_FILE = "CANCEL"

EXIT_DONE = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_CANCELLED = 3

#: The shortest time between two looks at the ``CANCEL`` file.
CANCEL_LOOK_INTERVAL_S = 0.05


class FileCancelToken:
    """Set once ``path`` exists; looks at the file at most every ``interval`` seconds of
    ``clock``, and stays set once it has seen it."""

    def __init__(
        self,
        path: Path,
        *,
        interval: float = CANCEL_LOOK_INTERVAL_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._path = path
        self._interval = interval
        self._clock = clock
        self._next_look = clock()
        self._set = False

    def is_set(self) -> bool:
        if not self._set and self._clock() >= self._next_look:
            self._set = self._path.exists()
            self._next_look = self._clock() + self._interval
        return self._set


def parent_alive() -> bool:
    """Whether the process that started this one is still running; ``True`` in a process
    that multiprocessing did not start."""
    parent = multiprocessing.parent_process()
    return parent is None or parent.is_alive()


class WatchedToken:
    """Set when ``token`` is set or ``alive()`` says the starting process has ended, so a
    worker whose run has lost its driver stops (docs/DECISIONS.md, AKS-103)."""

    def __init__(self, token: CancelToken, alive: Callable[[], bool]) -> None:
        self._token = token
        self._alive = alive

    def is_set(self) -> bool:
        return self._token.is_set() or not self._alive()


def child_main(
    adapter_class: Callable[[], EngineAdapter],
    workdir: str,
    cancel: CancelToken,
    workers: int,
    connection: Connection,
) -> None:
    """The spawned worker's body: runs the adapter in ``workdir`` and reports through
    ``connection``, which it closes."""
    try:

        def report(progress: Progress) -> None:
            connection.send(("progress", progress.fraction, progress.message))

        try:
            adapter_class().run(Path(workdir), report, WatchedToken(cancel, parent_alive), workers)
        except Exception:
            connection.send(("error", traceback.format_exc()))
        else:
            connection.send(("finished",))
    finally:
        connection.close()


def _engine_name(workdir: Path) -> str:
    manifest = read_json_object_file(workdir.parent / "manifest.json")
    name = manifest["engine"]["name"]
    if not isinstance(name, str):
        raise TypeError("engine.name is not text")
    return name


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    adapters: Mapping[str, EngineAdapter] | None = None,
) -> int:
    """``python -m lcsim.runs.worker``; returns the exit status. ``adapters`` defaults to
    the installed adapters."""
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    parser = argparse.ArgumentParser(
        prog="python -m lcsim.runs.worker",
        description="Run an engine adapter's run step in a run folder's engine/ folder.",
    )
    parser.add_argument("workdir", type=Path, help="the run folder's engine/ folder")
    parser.add_argument("--workers", type=int, default=1, help="processes to use (default 1)")
    arguments = parser.parse_args(argv)
    workdir: Path = arguments.workdir
    workers: int = arguments.workers
    if workers < 1:
        print(f"--workers must be 1 or more, not {workers}", file=err)
        return EXIT_USAGE
    try:
        name = _engine_name(workdir)
    except (OSError, ValueError, KeyError, TypeError) as problem:
        print(
            f"cannot read the engine name from {workdir.parent / 'manifest.json'}: {problem!r}",
            file=err,
        )
        return EXIT_USAGE
    adapter = (installed_adapters() if adapters is None else adapters).get(name)
    if adapter is None:
        print(f"the engine adapter {name!r} is not installed", file=err)
        return EXIT_USAGE

    def report(progress: Progress) -> None:
        line = {"type": "progress", "fraction": progress.fraction, "message": progress.message}
        print(json_text(line, ascii_only=True), file=out, flush=True)

    token = FileCancelToken(workdir / CANCEL_FILE)
    try:
        adapter.run(workdir, report, token, workers)
    except Exception:
        traceback.print_exc(file=err)
        return EXIT_ERROR
    return EXIT_CANCELLED if token.is_set() else EXIT_DONE


if __name__ == "__main__":
    raise SystemExit(main())
