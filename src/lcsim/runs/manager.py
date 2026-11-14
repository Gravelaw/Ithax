"""The experiment manager's run of one adapter (spec 1 "Engine contract" and "Division of
labour"; spec 2 "Experiment manager"; AKS-102).

``run_experiment`` takes an adapter through its methods in a given ``workdir`` (the run
folder's ``engine/``, which the run target chooses; AKS-103):

1. ``validate(model)``, together with the fidelity check (E173): any error refuses the run
   and nothing is translated;
2. ``translate(model, experiment_id, workdir)``;
3. ``run(workdir, on_progress, cancel, workers)``; when ``cancel`` is set afterwards, the
   run is cancelled and nothing is collected;
4. ``collect(workdir)``, then ``build_summary`` (``lcsim.runs.summary``) with the
   ``validate`` warnings first.

It writes nothing itself and knows nothing of the run folder, the manifest or job states:
the run target writes ``summary.json`` and the tables with ``lcsim.runs.tables`` and
records the state. An exception from the adapter propagates; the run target reports it
(E190).

An experiment with a ``search`` (spec 2 "Simulation-based optimization"; AKS-109) runs the
search of ``lcsim.runs.search`` instead of steps 2 to 4: each candidate evaluation calls
``translate``, ``run`` and ``collect`` in its own subfolder of ``workdir``, and the summary is
``search_summary``'s (the best candidate's confirmation with the ``search`` object); the
outcome's ``results`` are the best candidate's confirmation results.

An ``optimization`` model has no experiments (spec 3: ``POST .../runs`` takes no
``experiment_id`` for it), so it is run with ``experiment_id`` ``None``, which ``translate``
receives as it is; a ``process`` model needs the id of one of its experiments (AKS-108).

The steps are also available one by one, for the ``local`` run target
(``lcsim.runs.targets``; AKS-103), which runs ``validate``, ``translate`` and ``collect``
in its own process and ``run`` in a worker process: ``check_experiment`` (step 1) and
``collect_summary`` (step 4, with the warnings to put first in the summary).
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from lcsim.engines.adapter import CancelToken, EngineAdapter, Progress, Results
from lcsim.model.issues import Issue, pointer
from lcsim.model.model import Model
from lcsim.runs.search import run_search, search_summary
from lcsim.runs.summary import build_summary
from lcsim.strict_json import json_text

__all__ = [
    "OFFERED_FIDELITIES",
    "ExperimentChoiceError",
    "RunOutcome",
    "RunState",
    "check_experiment",
    "collect_summary",
    "fidelity_issues",
    "run_experiment",
]

#: Spec 1 "Top-level keys": Phase 1 process and optimization engines accept only these.
OFFERED_FIDELITIES = ("standard",)

#: How ``run_experiment`` ended.
RunState = Literal["done", "refused", "cancelled"]


@dataclass(frozen=True)
class RunOutcome:
    """How a run ended, with what it produced.

    - ``done``: ``issues`` are the ``validate`` warnings; ``results`` and ``summary`` are
      set.
    - ``refused``: ``issues`` are everything ``validate`` and the fidelity check found,
      errors included; nothing was translated or run.
    - ``cancelled``: ``cancel`` was set; nothing was collected.
    """

    state: RunState
    issues: tuple[Issue, ...]
    results: Results | None
    summary: dict[str, Any] | None


class ExperimentChoiceError(ValueError):
    """The experiment chosen does not fit the model: ``reason`` is ``missing`` (none for a
    process model), ``unwanted`` (one for an optimization model, which has no experiments)
    or ``unknown`` (one the model does not have). The service answers 400 (AKS-112)."""

    def __init__(self, reason: Literal["missing", "unwanted", "unknown"], message: str) -> None:
        super().__init__(message)
        self.reason = reason


def fidelity_issues(model: Model) -> list[Issue]:
    """E173 when ``run.fidelity`` is not one the Phase 1 engines offer."""
    fidelity = model.run.fidelity
    if fidelity in OFFERED_FIDELITIES:
        return []
    offered = " or ".join(json_text(item, ascii_only=True) for item in OFFERED_FIDELITIES)
    return [
        Issue(
            code="E173",
            component=None,
            path=pointer("run", "fidelity"),
            message=f"The fidelity {json_text(fidelity, ascii_only=True)} is not offered by "
            f"this engine; Phase 1 engines offer {offered} only.",
            hint=f"Set 'fidelity' in 'run' to {offered}.",
        )
    ]


def _ignore(progress: Progress) -> None:
    """The default progress callback."""


def run_experiment(
    adapter: EngineAdapter,
    model: Model,
    experiment_id: str | None,
    workdir: Path,
    *,
    on_progress: Callable[[Progress], None] = _ignore,
    cancel: CancelToken | None = None,
    workers: int = 1,
) -> RunOutcome:
    """Runs experiment ``experiment_id`` of ``model`` through ``adapter`` in ``workdir``
    and returns the outcome with its ``summary.json`` dict.

    ``cancel`` defaults to a token that is never set. ``experiment_id`` is ``None`` for an
    optimization model. An experiment the model does not have, an experiment id for an
    optimization model or none for a process model raises ``ValueError``.
    """
    issues = check_experiment(adapter, model, experiment_id)
    if any(issue.severity == "error" for issue in issues):
        return RunOutcome("refused", issues, None, None)
    token: CancelToken = threading.Event() if cancel is None else cancel
    workdir.mkdir(parents=True, exist_ok=True)
    if experiment_id is not None and _has_search(model, experiment_id):
        return _run_search(
            adapter, model, experiment_id, workdir, on_progress, token, workers, issues
        )
    adapter.translate(model, experiment_id, workdir)
    adapter.run(workdir, on_progress, token, workers)
    if token.is_set():
        return RunOutcome("cancelled", issues, None, None)
    results, summary = collect_summary(adapter, model, experiment_id, workdir, issues)
    return RunOutcome("done", issues, results, summary)


def check_experiment(
    adapter: EngineAdapter, model: Model, experiment_id: str | None
) -> tuple[Issue, ...]:
    """Step 1: the adapter's ``validate`` issues, then E173 from the fidelity check; any
    error among them refuses the run.

    ``experiment_id`` is ``None`` for an optimization model, which has no experiments. An
    experiment the model does not have, an experiment id for an optimization model or none
    for a process model raises ``ExperimentChoiceError`` (a ``ValueError``).
    """
    if model.program is not None:
        if experiment_id is not None:
            raise ExperimentChoiceError(
                "unwanted",
                f"an optimization model has no experiments, but {experiment_id!r} was given",
            )
        return (*adapter.validate(model), *fidelity_issues(model))
    if experiment_id is None:
        raise ExperimentChoiceError(
            "missing", "a process model runs one of its experiments; none was given"
        )
    experiment = next((item for item in model.experiments if item.id == experiment_id), None)
    if experiment is None:
        raise ExperimentChoiceError("unknown", f"the model has no experiment {experiment_id!r}")
    return (*adapter.validate(model), *fidelity_issues(model))


def collect_summary(
    adapter: EngineAdapter,
    model: Model,
    experiment_id: str | None,
    workdir: Path,
    warnings: Sequence[Issue],
) -> tuple[Results, dict[str, Any]]:
    """Step 4: ``collect(workdir)`` and the ``summary.json`` dict, with ``warnings``
    first in its ``warnings``."""
    results = adapter.collect(workdir)
    return results, build_summary(model, experiment_id, results, warnings)


def _has_search(model: Model, experiment_id: str) -> bool:
    return any(item.id == experiment_id and item.search is not None for item in model.experiments)


def _run_search(
    adapter: EngineAdapter,
    model: Model,
    experiment_id: str,
    workdir: Path,
    on_progress: Callable[[Progress], None],
    token: CancelToken,
    workers: int,
    issues: tuple[Issue, ...],
) -> RunOutcome:
    """The search, every evaluation in this process."""

    def evaluate(
        candidate: Model, experiment: str, folder: Path, report: Callable[[Progress], None]
    ) -> Results | None:
        if token.is_set():
            return None
        folder.mkdir()
        adapter.translate(candidate, experiment, folder)
        adapter.run(folder, report, token, workers)
        if token.is_set():
            return None
        return adapter.collect(folder)

    result = run_search(model, experiment_id, workdir, evaluate, on_progress)
    if result is None:
        return RunOutcome("cancelled", issues, None, None)
    summary = search_summary(model, experiment_id, result, issues)
    return RunOutcome("done", issues, result.best_results, summary)
