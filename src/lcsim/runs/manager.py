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
(E190). A plain experiment only: a search experiment (spec 2 "Simulation-based
optimization") is M5's.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from lcsim.engines.adapter import CancelToken, EngineAdapter, Progress, Results
from lcsim.model.issues import Issue, pointer
from lcsim.model.model import Model
from lcsim.runs.summary import build_summary

__all__ = ["OFFERED_FIDELITIES", "RunOutcome", "RunState", "fidelity_issues", "run_experiment"]

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


def fidelity_issues(model: Model) -> list[Issue]:
    """E173 when ``run.fidelity`` is not one the Phase 1 engines offer."""
    fidelity = model.run.fidelity
    if fidelity in OFFERED_FIDELITIES:
        return []
    offered = " or ".join(json.dumps(item) for item in OFFERED_FIDELITIES)
    return [
        Issue(
            code="E173",
            component=None,
            path=pointer("run", "fidelity"),
            message=f"The fidelity {json.dumps(fidelity)} is not offered by this engine; "
            f"Phase 1 engines offer {offered} only.",
            hint=f"Set 'fidelity' in 'run' to {offered}.",
        )
    ]


def _ignore(progress: Progress) -> None:
    """The default progress callback."""


def run_experiment(
    adapter: EngineAdapter,
    model: Model,
    experiment_id: str,
    workdir: Path,
    *,
    on_progress: Callable[[Progress], None] = _ignore,
    cancel: CancelToken | None = None,
    workers: int = 1,
) -> RunOutcome:
    """Runs experiment ``experiment_id`` of ``model`` through ``adapter`` in ``workdir``
    and returns the outcome with its ``summary.json`` dict.

    ``cancel`` defaults to a token that is never set. An experiment the model does not
    have raises ``ValueError``; a search experiment raises ``NotImplementedError`` (M5).
    """
    experiment = next((item for item in model.experiments if item.id == experiment_id), None)
    if experiment is None:
        raise ValueError(f"the model has no experiment {experiment_id!r}")
    if experiment.search is not None:
        raise NotImplementedError(
            f"experiment {experiment_id!r} has a search, which the experiment manager runs "
            "from M5 (spec 2 'Simulation-based optimization')"
        )
    issues = (*adapter.validate(model), *fidelity_issues(model))
    if any(issue.severity == "error" for issue in issues):
        return RunOutcome("refused", issues, None, None)
    token: CancelToken = threading.Event() if cancel is None else cancel
    workdir.mkdir(parents=True, exist_ok=True)
    adapter.translate(model, experiment_id, workdir)
    adapter.run(workdir, on_progress, token, workers)
    if token.is_set():
        return RunOutcome("cancelled", issues, None, None)
    results = adapter.collect(workdir)
    summary = build_summary(model, experiment_id, results, issues)
    return RunOutcome("done", issues, results, summary)
