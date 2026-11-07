"""The simulation-based search (spec 2 "Simulation-based optimization"; spec 1 "Experiments";
AKS-109, following ``docs/research/spec-2-simulation-based-optimization.md``, AKS-132).

Optuna is a search driver inside the experiment manager, not an adapter (spec 2). The search
never runs a model itself: each candidate evaluation is one ``translate``, ``run`` and
``collect`` of the model's adapter in its own subfolder of ``engine/`` (spec 1 "Division of
labour"), done by the ``evaluate`` function the caller gives (in-process for
``run_experiment``, through a spawned worker for the local target).

- **Variables** are the parameters ``search.variables`` names, each between its ``min`` and
  ``max``.
- **Candidates.** A candidate is one value per variable. It is run as the experiment with
  one scenario, ``default``, whose ``set`` holds the candidate's values, the experiment's
  seed (common random numbers: the stream key holds no candidate), and
  ``search.replications`` replications at the search stage. The baseline, every variable at
  its parameter's ``value``, is always the first candidate.
- **Exhaustive or Optuna.** When every variable is an ``integer`` parameter and the number
  of combinations is at most ``budget``, every combination is run, the baseline first and
  the others in order (the first variable slowest). Otherwise Optuna's TPE sampler proposes
  candidates by the recipe of the research note: logging at ``WARNING``; the sampler seed is
  the first draw ``integers(0, 2**32)`` of the stream ``<seed>:0:optimizer``
  (``lcsim.model.streams.optimizer_generator``); ``TPESampler(seed=...)`` with every other
  argument at its default; an in-memory study in the objective's direction; the baseline
  enqueued as trial 0; ask and tell one trial at a time; ``suggest_int`` for an ``integer``
  variable, ``suggest_float`` for a ``number`` and for a ``quantity`` (in seconds), in
  ``variables`` order; one ``Trial.set_constraint`` per constraint, ``value - mean`` for
  ``>=`` and ``mean - value`` for ``<=`` (feasible at 0 or less), ``math.inf`` when the mean
  is undefined; the objective's mean told, or ``TrialState.FAIL`` when it is undefined. A
  suggestion already evaluated is not run again: the trial is told the stored results and
  does not count against ``budget``. Asking stops when ``budget`` distinct candidates, the
  baseline included, have been evaluated, or after ``ASK_LIMIT_FACTOR`` x ``budget`` asks.
- **Feasible** means the objective's mean is defined and every constraint of the model's
  ``constraints`` holds on the means (a constraint on an undefined mean does not).
- **Confirmation.** The baseline, then the best ``CONFIRM_GROUP`` candidates other than the
  baseline by search-stage mean objective among those feasible at the search stage (ties by
  candidate order), are run again with the experiment's ``replications``; feasibility is
  judged again on the confirmed means. When none of a group is feasible on confirmation, the
  next group is confirmed, until one is or none remain. The confirmation replications are
  numbered from 0 like the search stage's, so a candidate's first ``search.replications``
  confirmed values are its search-stage values (spec 2 as written; the owner decides whether
  to make them disjoint, research note decision "Overlap of the two stages").
- **Best.** The confirmed feasible candidate, baseline included, with the best confirmed mean
  objective (ties by candidate order); ``status`` ``feasible``. When no confirmed candidate is
  feasible, the baseline, with ``status`` ``infeasible``. ``separated`` says whether the paired
  difference of the objective between the best and the confirmed feasible runner-up (same
  replication numbers, at the experiment's ``confidence``) excludes zero; ``False`` with no
  runner-up.

Optuna's sequences repeat on the same Optuna and numpy versions only (research note), so
``optimizer_record`` names the method and the Optuna version for the manifest.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

import optuna
from optuna.trial import Trial, TrialState

from lcsim.engines.adapter import Progress, Results, Table
from lcsim.model.issues import Issue
from lcsim.model.model import (
    Experiment,
    Model,
    Parameter,
    ParameterValue,
    Scenario,
    Search,
)
from lcsim.model.streams import optimizer_generator
from lcsim.model.units import Dimension, Quantity
from lcsim.runs.statistics import MetricEstimate, across_replications, estimate
from lcsim.runs.summary import build_summary

__all__ = [
    "ASK_LIMIT_FACTOR",
    "CONFIRM_GROUP",
    "SCENARIO",
    "Candidate",
    "Evaluate",
    "Evaluation",
    "Method",
    "SearchResult",
    "candidate_model",
    "combination_count",
    "combinations",
    "optimizer_record",
    "run_search",
    "search_method",
    "search_of",
    "search_summary",
    "tpe_seed",
]

#: Asking stops after this many asks per candidate of the budget (research note decision 7).
ASK_LIMIT_FACTOR = 10
#: How many candidates besides the baseline each confirmation group holds (spec 2).
CONFIRM_GROUP = 3
#: The one scenario a candidate is run as (spec 1 "Experiments": the implicit scenario).
SCENARIO = "default"

#: How a search proposes its candidates.
Method = Literal["exhaustive", "optuna"]

#: Runs one candidate evaluation: ``evaluate(model, experiment_id, folder, on_progress)``
#: creates ``folder`` (a subfolder of ``engine/`` that does not exist yet), calls the
#: adapter's ``translate``, ``run`` and ``collect`` in it and returns the results, or
#: ``None`` when the run was cancelled. An error raises.
Evaluate = Callable[[Model, str, Path, Callable[[Progress], None]], Results | None]


@dataclass(frozen=True)
class Evaluation:
    """One candidate evaluation: the ``default`` scenario's metrics across its
    replications, whether it is feasible on them, the objective metric's value in each
    replication (for ``separated``), and what ``collect`` returned while it is kept.

    The search keeps ``results`` only where the summary may need the tables: the baseline's
    confirmation and the best confirmation so far. Every other evaluation keeps its metrics
    and drops its tables (``results`` ``None``), so the driving process's memory does not
    grow with the budget (review of PR #32); the tables stay in the evaluation's folder.
    """

    results: Results | None
    metrics: Mapping[str, MetricEstimate]
    feasible: bool
    objective_values: Mapping[int, float]


@dataclass
class Candidate:
    """A candidate: its number (0 is the baseline), one value per variable in
    ``search.variables`` order, its search-stage evaluation and, once confirmed, its
    confirmation."""

    index: int
    values: tuple[ParameterValue, ...]
    search: Evaluation
    confirmation: Evaluation | None = None

    @property
    def latest(self) -> Evaluation:
        """The confirmation when there is one, otherwise the search-stage evaluation."""
        return self.search if self.confirmation is None else self.confirmation


@dataclass(frozen=True)
class SearchResult:
    """What a search found."""

    method: Method
    variables: tuple[str, ...]
    candidates: tuple[Candidate, ...]
    best: Candidate
    status: Literal["feasible", "infeasible"]
    separated: bool
    asks: int

    @property
    def best_results(self) -> Results:
        """The best candidate's confirmation results (it is always confirmed, and its
        tables are kept)."""
        assert self.best.confirmation is not None
        assert self.best.confirmation.results is not None
        return self.best.confirmation.results


def search_of(model: Model, experiment_id: str) -> tuple[int, Experiment, Search]:
    """The experiment's index, the experiment and its search; ``ValueError`` when the model
    has no such experiment or it has no search."""
    for index, experiment in enumerate(model.experiments):
        if experiment.id == experiment_id:
            if experiment.search is None:
                raise ValueError(f"experiment {experiment_id!r} has no search")
            return index, experiment, experiment.search
    raise ValueError(f"the model has no experiment {experiment_id!r}")


def _number(value: ParameterValue) -> int | float:
    return value.magnitude if isinstance(value, Quantity) else value


def _bounds(parameter: Parameter) -> tuple[int | float, int | float]:
    # Validation (E171) refuses a search variable without both bounds.
    assert parameter.min is not None and parameter.max is not None
    return _number(parameter.min), _number(parameter.max)


def combinations(model: Model, search: Search) -> list[tuple[int, ...]] | None:
    """Every combination of the variables' values, the first variable slowest, when every
    variable is an ``integer`` parameter; ``None`` otherwise (a ``number`` or ``quantity``
    variable has no finite set of values). It lists them all, so it is called only once
    ``combination_count`` is known to fit the budget."""
    parameters = [model.parameters[name] for name in search.variables]
    if any(parameter.type != "integer" for parameter in parameters):
        return None
    ranges = []
    for parameter in parameters:
        low, high = _bounds(parameter)
        ranges.append(range(int(low), int(high) + 1))
    return list(itertools.product(*ranges))


def combination_count(model: Model, search: Search) -> int | None:
    """The number of combinations, the product of each variable's range length
    (``max`` - ``min`` + 1), counted without listing them, when every variable is an
    ``integer`` parameter; ``None`` otherwise."""
    count = 1
    for name in search.variables:
        parameter = model.parameters[name]
        if parameter.type != "integer":
            return None
        low, high = _bounds(parameter)
        count *= int(high) - int(low) + 1
    return count


def search_method(model: Model, search: Search) -> Method:
    """``exhaustive`` when the integer combinations fit the budget, else ``optuna``. The
    combinations are counted, never listed, here (a range may hold 10⁹ values)."""
    count = combination_count(model, search)
    return "exhaustive" if count is not None and count <= search.budget else "optuna"


def optimizer_record(method: Method) -> dict[str, str | None]:
    """The manifest's ``optimizer``: ``{name, version}``, the Optuna version for an Optuna
    search and ``None`` for an exhaustive one."""
    if method == "optuna":
        return {"name": "optuna", "version": optuna.__version__}
    return {"name": "exhaustive", "version": None}


def tpe_seed(seed: int) -> int:
    """The TPE sampler's seed: the first draw in [0, 2³²) of the stream
    ``<seed>:0:optimizer`` (``numpy.random.RandomState`` accepts no larger seed)."""
    return int(optimizer_generator(seed).integers(0, 2**32))


def _value(parameter: Parameter, raw: int | float) -> ParameterValue:
    """A suggested or enumerated value as the parameter's type holds it."""
    if parameter.type == "integer":
        return int(raw)
    if parameter.type == "number":
        return float(raw)
    return Quantity(float(raw), Dimension.TIME)


def candidate_model(
    model: Model, experiment_id: str, values: Sequence[ParameterValue], replications: int
) -> Model:
    """The model with experiment ``experiment_id`` set to run one candidate: one ``default``
    scenario whose ``set`` gives each variable its value, ``replications`` replications and
    no search; everything else, the seed included, is unchanged."""
    _, experiment, search = search_of(model, experiment_id)
    scenario = Scenario(SCENARIO, dict(zip(search.variables, values, strict=True)))
    changed = replace(
        experiment,
        replications=replications,
        scenarios=(scenario,),
        default_scenario_added=True,
        search=None,
    )
    experiments = tuple(changed if item is experiment else item for item in model.experiments)
    return replace(model, experiments=experiments)


class _Judge:
    """The objective and constraints of a search, judged on a scenario's means."""

    def __init__(self, model: Model, search: Search, confidence: float) -> None:
        objectives = {objective.id: objective for objective in model.objectives}
        self.objective = objectives[search.objective]
        self.constraints = model.constraints
        self.confidence = confidence

    def mean(self, metrics: Mapping[str, MetricEstimate], metric: str) -> float | None:
        found = metrics.get(metric)
        return None if found is None else found.estimate.mean

    def objective_mean(self, metrics: Mapping[str, MetricEstimate]) -> float | None:
        return self.mean(metrics, self.objective.metric)

    def margins(self, metrics: Mapping[str, MetricEstimate]) -> list[float]:
        """Each constraint's violation, feasible at 0 or less: ``value - mean`` for ``>=``,
        ``mean - value`` for ``<=``, ``math.inf`` for an undefined mean."""
        margins = []
        for constraint in self.constraints:
            mean = self.mean(metrics, constraint.metric)
            value = _number(constraint.value)
            if mean is None:
                margins.append(math.inf)
            elif constraint.op == ">=":
                margins.append(value - mean)
            else:
                margins.append(mean - value)
        return margins

    def evaluation(self, results: Results) -> Evaluation:
        table = results.tables.get("replications")
        metrics = (
            {}
            if table is None
            else across_replications(table, [SCENARIO], self.confidence)[SCENARIO]
        )
        feasible = self.objective_mean(metrics) is not None and all(
            margin <= 0 for margin in self.margins(metrics)
        )
        values = {} if table is None else _values_by_replication(table, self.objective.metric)
        return Evaluation(results, metrics, feasible, values)

    def rank(self, candidate: Candidate) -> tuple[float, int]:
        """A sort key for a feasible candidate (its mean objective is defined): the better
        mean of its latest evaluation first, then the earlier candidate."""
        mean = self.objective_mean(candidate.latest.metrics)
        assert mean is not None  # only feasible candidates are ranked
        return (mean if self.objective.sense == "minimize" else -mean, candidate.index)


class _Progress:
    """Maps each evaluation's progress onto the whole search: every evaluation weighs its
    replication count against the planned total, and the reported fraction never falls and
    stays below 1 (the run target sets 1 when the run is done)."""

    def __init__(self, report: Callable[[Progress], None], total: float) -> None:
        self._report = report
        self._total = total
        self._done = 0.0
        self._last = 0.0

    def stage(self, weight: float, label: str) -> Callable[[Progress], None]:
        done = self._done
        self._done += weight
        if self._done > self._total:
            self._total = self._done

        def on_progress(progress: Progress) -> None:
            fraction = min(0.99, (done + progress.fraction * weight) / self._total)
            self._last = max(self._last, fraction)
            self._report(Progress(self._last, f"{label}: {progress.message}"))

        return on_progress


class _Searcher:
    def __init__(
        self,
        model: Model,
        experiment_id: str,
        workdir: Path,
        evaluate: Evaluate,
        on_progress: Callable[[Progress], None],
    ) -> None:
        _, self.experiment, self.search = search_of(model, experiment_id)
        self.model = model
        self.experiment_id = experiment_id
        self.workdir = workdir
        self.evaluate = evaluate
        self.parameters = [model.parameters[name] for name in self.search.variables]
        self.judge = _Judge(model, self.search, self.experiment.confidence)
        self.method = search_method(model, self.search)
        count = combination_count(model, self.search)
        planned = count if count is not None and self.method == "exhaustive" else 0
        planned = planned or self.search.budget
        total = planned * self.search.replications + (1 + CONFIRM_GROUP) * (
            self.experiment.replications
        )
        self.progress = _Progress(on_progress, float(total))
        self.candidates: list[Candidate] = []

    def _run(
        self, values: Sequence[ParameterValue], replications: int, folder: str, label: str
    ) -> Evaluation | None:
        model = candidate_model(self.model, self.experiment_id, values, replications)
        on_progress = self.progress.stage(float(replications), label)
        results = self.evaluate(model, self.experiment_id, self.workdir / folder, on_progress)
        return None if results is None else self.judge.evaluation(results)

    def _drop_tables(self, evaluation: Evaluation) -> Evaluation:
        return replace(evaluation, results=None)

    def add(self, values: tuple[ParameterValue, ...]) -> Candidate | None:
        index = len(self.candidates)
        label = f"Search, candidate {index + 1}"
        found = self._run(values, self.search.replications, f"search-{index:03d}", label)
        if found is None:
            return None
        # The search stage needs only the metrics: its tables are dropped at once.
        candidate = Candidate(index, values, self._drop_tables(found))
        self.candidates.append(candidate)
        return candidate

    def baseline(self) -> tuple[ParameterValue, ...]:
        return tuple(parameter.value for parameter in self.parameters)

    def exhaustive(self) -> bool:
        baseline = self.baseline()
        found = combinations(self.model, self.search)
        assert found is not None
        if self.add(baseline) is None:
            return False
        for raw in found:
            values = tuple(_value(p, v) for p, v in zip(self.parameters, raw, strict=True))
            if values != baseline and self.add(values) is None:
                return False
        return True

    def optuna(self) -> tuple[bool, int]:
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        sampler = optuna.samplers.TPESampler(seed=tpe_seed(self.experiment.seed))
        study = optuna.create_study(direction=self.judge.objective.sense, sampler=sampler)
        names = self.search.variables
        baseline = zip(names, self.baseline(), strict=True)
        study.enqueue_trial({name: _number(value) for name, value in baseline})
        seen: dict[tuple[ParameterValue, ...], Candidate] = {}
        asks = 0
        while len(self.candidates) < self.search.budget:
            if asks >= ASK_LIMIT_FACTOR * self.search.budget:
                break
            trial = study.ask()
            asks += 1
            values = tuple(
                self._suggest(trial, name, parameter)
                for name, parameter in zip(names, self.parameters, strict=True)
            )
            candidate = seen.get(values)
            if candidate is None:
                candidate = self.add(values)
                if candidate is None:
                    return False, asks
                seen[values] = candidate
            metrics = candidate.search.metrics
            for constraint, margin in zip(
                self.judge.constraints, self.judge.margins(metrics), strict=True
            ):
                trial.set_constraint(constraint.id, margin)
            mean = self.judge.objective_mean(metrics)
            if mean is None:
                study.tell(trial, state=TrialState.FAIL)
            else:
                study.tell(trial, mean)
        return True, asks

    def _suggest(self, trial: Trial, name: str, parameter: Parameter) -> ParameterValue:
        low, high = _bounds(parameter)
        if parameter.type == "integer":
            return _value(parameter, trial.suggest_int(name, int(low), int(high)))
        return _value(parameter, trial.suggest_float(name, float(low), float(high)))

    def confirm(self, candidate: Candidate) -> bool:
        label = f"Confirmation, candidate {candidate.index + 1}"
        found = self._run(
            candidate.values,
            self.experiment.replications,
            f"confirm-{candidate.index:03d}",
            label,
        )
        if found is None:
            return False
        candidate.confirmation = found
        self._keep_needed_tables()
        return True

    def _confirmed_feasible(self) -> list[Candidate]:
        """The confirmed feasible candidates, best first."""
        return sorted(
            (
                item
                for item in self.candidates
                if item.confirmation is not None and item.confirmation.feasible
            ),
            key=self.judge.rank,
        )

    def _keep_needed_tables(self) -> None:
        """Drops the tables of every confirmation but the baseline's and the best so far."""
        feasible = self._confirmed_feasible()
        keep = {0} if not feasible else {0, feasible[0].index}
        for item in self.candidates:
            if item.index not in keep and item.confirmation is not None:
                item.confirmation = self._drop_tables(item.confirmation)

    def confirmation(self) -> bool:
        if not self.confirm(self.candidates[0]):
            return False
        judge = self.judge
        waiting = sorted(
            (item for item in self.candidates[1:] if item.search.feasible),
            key=judge.rank,
        )
        while waiting:
            group, waiting = waiting[:CONFIRM_GROUP], waiting[CONFIRM_GROUP:]
            for candidate in group:
                if not self.confirm(candidate):
                    return False
            if any(item.latest.feasible for item in group):
                break
        return True

    def result(self, asks: int) -> SearchResult:
        feasible = self._confirmed_feasible()
        if not feasible:
            return SearchResult(
                self.method,
                self.search.variables,
                tuple(self.candidates),
                self.candidates[0],
                "infeasible",
                False,
                asks,
            )
        best = feasible[0]
        separated = len(feasible) > 1 and _separated(best, feasible[1], self.experiment.confidence)
        return SearchResult(
            self.method,
            self.search.variables,
            tuple(self.candidates),
            best,
            "feasible",
            separated,
            asks,
        )


def _values_by_replication(table: Table, metric: str) -> dict[int, float]:
    """The ``default`` scenario's value of ``metric`` in each replication of a
    ``replications`` table."""
    rows = zip(
        *(
            table.column(name).to_pylist()
            for name in ("scenario", "replication", "metric", "value")
        ),
        strict=True,
    )
    return {
        rep: value for scenario, rep, name, value in rows if (scenario, name) == (SCENARIO, metric)
    }


def _separated(best: Candidate, other: Candidate, confidence: float) -> bool:
    """Whether the paired difference of the objective between two confirmed candidates
    excludes zero (spec 2 "Between scenarios": same replication numbers, NaN pairs left
    out, n ≥ 2 and |mean| > half-width)."""
    assert best.confirmation is not None and other.confirmation is not None
    first = best.confirmation.objective_values
    second = other.confirmation.objective_values
    differences = [
        first[rep] - second[rep]
        for rep in sorted(first.keys() & second.keys())
        if not math.isnan(first[rep]) and not math.isnan(second[rep])
    ]
    return estimate(differences, confidence).separated


def run_search(
    model: Model,
    experiment_id: str,
    workdir: Path,
    evaluate: Evaluate,
    on_progress: Callable[[Progress], None] | None = None,
) -> SearchResult | None:
    """Runs the search of experiment ``experiment_id``; each evaluation goes to a subfolder
    of ``workdir``: ``search-<n>`` for candidate n's search stage and ``confirm-<n>`` for its
    confirmation (n from 000, the baseline). Returns ``None`` when an evaluation was
    cancelled."""
    searcher = _Searcher(
        model, experiment_id, workdir, evaluate, on_progress or (lambda progress: None)
    )
    asks = 0
    if searcher.method == "exhaustive":
        finished = searcher.exhaustive()
    else:
        finished, asks = searcher.optuna()
    if not finished or not searcher.confirmation():
        return None
    return searcher.result(asks)


def _si_set(variables: Sequence[str], values: Sequence[ParameterValue]) -> dict[str, int | float]:
    return {name: _number(value) for name, value in zip(variables, values, strict=True)}


def search_summary(
    model: Model, experiment_id: str, result: SearchResult, warnings: Sequence[Issue] = ()
) -> dict[str, Any]:
    """The ``summary.json`` dict of a search run: the process layout of the best candidate's
    confirmation (its one ``default`` scenario with the best candidate's ``set``, the warm-up
    check on its time series, and the experiment's ``replications``), followed by
    ``search``: ``{status, best: {set}, objective: {metric, before, after}, separated,
    candidates: [{set, metrics, feasible, confirmed}]}``. ``before`` is the baseline's
    confirmed mean objective and ``after`` the best's; a candidate's ``metrics`` and
    ``feasible`` are from its confirmation when it has one, otherwise from the search
    stage."""
    _, experiment, search = search_of(model, experiment_id)
    best = result.best
    assert best.confirmation is not None
    best_model = candidate_model(model, experiment_id, best.values, experiment.replications)
    summary = build_summary(best_model, experiment_id, result.best_results, warnings)
    objectives = {objective.id: objective for objective in model.objectives}
    metric = objectives[search.objective].metric
    baseline = result.candidates[0]
    assert baseline.confirmation is not None

    def mean(evaluation: Evaluation) -> float | None:
        found = evaluation.metrics.get(metric)
        return None if found is None else found.estimate.mean

    summary["search"] = {
        "status": result.status,
        "best": {"set": _si_set(result.variables, best.values)},
        "objective": {
            "metric": metric,
            "before": mean(baseline.confirmation),
            "after": mean(best.confirmation),
        },
        "separated": result.separated,
        "candidates": [
            {
                "set": _si_set(result.variables, candidate.values),
                "metrics": {
                    name: item.as_dict() for name, item in candidate.latest.metrics.items()
                },
                "feasible": candidate.latest.feasible,
                "confirmed": candidate.confirmation is not None,
            }
            for candidate in result.candidates
        ],
    }
    return summary
