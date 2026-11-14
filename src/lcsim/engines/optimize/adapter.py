"""The HiGHS adapter: the ``optimization`` domain on HiGHS through Pyomo (spec 2
"Optimization"; AKS-108).

Registered in ``pyproject.toml`` as entry point ``highs`` in group ``lcsim.engines``
(spec 1 "Engine contract"). Its ``capabilities()`` reports the ``optimization`` domain, no
component types (an optimization model has none), no special hardware, no parallel mode
(one solve per run), HiGHS's licence (MIT; Pyomo's BSD-3-Clause is recorded in
``docs/DECISIONS.md``) and ``in-process`` invocation (HiGHS runs inside the worker through
``highspy``; spec 1 "Engine licence rule").

An optimization model has no experiments, so ``translate`` takes no experiment id
(``None``) and writes ``workdir/input.json`` (``lcsim.engines.optimize.translate``).
``run`` solves it (``lcsim.engines.optimize.solver``) and writes
``workdir/output/solution.json``: the ``summary.json`` layout of spec 2 (``status``,
``objective``, ``variables``, ``constraints``), with the duals of a continuous program and
the solver's name and version beside it. ``collect`` returns the layout as
``Results.solution``, with no tables.

Cancel: a HiGHS solve called through Pyomo cannot be interrupted (engine gap, recorded in
``docs/DECISIONS.md``), so ``run`` checks ``cancel`` before and after the solve and writes
nothing when it is set; a solve longer than the cancel grace is ended by the run target,
which terminates the worker.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import lcsim
from lcsim.engines.adapter import CancelToken, Capabilities, Progress, Results
from lcsim.engines.optimize.solver import is_tight, solve, solver_version
from lcsim.engines.optimize.translate import INPUT_FILE, read_input, write_input
from lcsim.model.issues import Issue
from lcsim.model.model import Model
from lcsim.strict_json import encode_json, read_json_object_file

__all__ = ["INPUT_FILE", "SOLUTION_FILE", "SOLUTION_KEYS", "HighsAdapter"]

#: Where ``run`` writes the solution, relative to ``workdir``.
SOLUTION_FILE = Path("output") / "solution.json"
#: Spec 2: the keys of an optimization ``summary.json`` that come from the adapter.
SOLUTION_KEYS = ("status", "objective", "variables", "constraints")


class HighsAdapter:
    """The HiGHS adapter for the ``optimization`` domain."""

    name: str = "highs"
    # The product's own adapters ship with the product, so they carry its version.
    version: str = lcsim.__version__

    def capabilities(self) -> Capabilities:
        """The ``optimization`` domain, no component types, no special hardware, no
        parallel mode, MIT, imported into the process."""
        return Capabilities(
            domains=("optimization",),
            component_types={},
            hardware=(),
            parallel_modes=(),
            licence="MIT",
            invocation="in-process",
        )

    def validate(self, model: Model) -> list[Issue]:
        """Checks beyond the common ones (codes E300 to E399): none so far."""
        return []

    def translate(self, model: Model, experiment_id: str | None, workdir: Path) -> None:
        """Writes ``model``'s program to ``workdir/input.json``. An optimization model has
        no experiments: an ``experiment_id`` other than ``None`` raises ``ValueError``."""
        if experiment_id is not None:
            raise ValueError(
                f"an optimization model has no experiments, but {experiment_id!r} was given"
            )
        write_input(model, workdir)

    def run(
        self,
        workdir: Path,
        on_progress: Callable[[Progress], None],
        cancel: CancelToken,
        workers: int,
    ) -> None:
        """Solves the program once (``workers`` is not used) and writes
        ``workdir/output/solution.json``; writes nothing when ``cancel`` is set before or
        after the solve. ``SolverStopped`` when HiGHS gives no answer of the three."""
        program = read_input(workdir)
        output = workdir / SOLUTION_FILE
        output.unlink(missing_ok=True)
        if cancel.is_set():
            return
        on_progress(Progress(0.0, "Solving with HiGHS"))
        outcome = solve(program)
        if cancel.is_set():
            return
        document: dict[str, Any] = {
            "solver": {"name": "HiGHS", "version": solver_version()},
            "status": outcome.status,
            "objective": outcome.objective,
            "variables": outcome.values,
            "constraints": {
                name: {"tight": is_tight(slack), "slack": slack}
                for name, slack in outcome.slacks.items()
            },
            "duals": outcome.duals,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        partial = output.with_name(output.name + ".partial")
        partial.write_bytes(encode_json(document))
        partial.replace(output)
        on_progress(Progress(1.0, f"Solved: {outcome.status}"))

    def collect(self, workdir: Path) -> Results:
        """The solution ``run`` wrote, in the spec 2 layout, as ``Results.solution``;
        ``FileNotFoundError`` when ``run`` did not finish."""
        document = read_json_object_file(workdir / SOLUTION_FILE)
        return Results(
            tables={}, warnings=[], solution={key: document[key] for key in SOLUTION_KEYS}
        )
