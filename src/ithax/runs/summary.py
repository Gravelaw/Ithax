"""Building ``summary.json`` from an adapter's ``Results`` (spec 1 "Run folder and results"
and "Division of labour"; AKS-102).

A process run's summary is, in this order: ``model`` (the model's name), ``experiment``,
``fidelity``, ``fidelity_label``, ``replications``, ``confidence``, ``scenarios`` keyed by
scenario id in the experiment's order, each ``{set, metrics}`` with every metric of the
``replications`` table as ``{mean, half_width, unit, n}``; ``differences``, the paired
scenario differences; and ``warnings``: the warnings given (the local run target gives the
load-time warnings W200 to W202, then the adapter's ``validate`` warnings; AKS-103), then
the adapter's ``collect`` warnings, then W210 from the warm-up check
(``ithax.runs.warmup``), which runs on the ``timeseries`` table of a plain experiment.

An optimization run's summary is ``model``, then the adapter's ``solution``, then
``fidelity_label`` and ``warnings``; the manager computes no statistics for it.

A table the adapter did not return is treated as empty: no metrics, or no warm-up check.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ithax.engines.adapter import Results
from ithax.model.issues import Issue
from ithax.model.model import Experiment, Model, ParameterValue
from ithax.model.units import Quantity
from ithax.runs.statistics import across_replications, paired_differences
from ithax.runs.warmup import warmup_check, warmup_warning

__all__ = ["build_summary", "fidelity_label", "format_length"]

# Phase 1 time units, largest first, in seconds (spec 1 "Quantities").
_TIME_UNITS = (("d", 86400.0), ("h", 3600.0), ("min", 60.0))


def _number(value: float) -> str:
    """A whole number without ``.0``, otherwise the shortest repr of the float."""
    return str(int(value)) if value == int(value) else repr(value)


def format_length(seconds: float) -> str:
    """A run length as a whole number in the largest Phase 1 time unit that gives one
    (``d``, ``h``, ``min``), and otherwise in seconds: 720000 s is "200 h"."""
    for symbol, size in _TIME_UNITS:
        count = seconds / size
        if count >= 1 and count == int(count):
            return f"{int(count)} {symbol}"
    return f"{_number(seconds)} s"


def fidelity_label(fidelity: str, replications: int, length: float, confidence: float) -> str:
    """The text the interface shows (spec 1 "Run folder and results"), such as "Standard:
    30 replications of 200 h, 95% confidence"; ``length`` is in seconds."""
    percent = f"{confidence * 100:g}"
    return (
        f"{fidelity.capitalize()}: {replications} replications of {format_length(length)}, "
        f"{percent}% confidence"
    )


def _fidelity(model: Model) -> str:
    fidelity = model.run.fidelity
    if not isinstance(fidelity, str):
        raise ValueError(f"fidelity {fidelity!r} is not text; the run should have been refused")
    return fidelity


def _si(value: ParameterValue) -> int | float:
    """A parameter value in SI units: a quantity as its SI magnitude."""
    return value.magnitude if isinstance(value, Quantity) else value


def _experiment(model: Model, experiment_id: str | None) -> tuple[int, Experiment]:
    for index, experiment in enumerate(model.experiments):
        if experiment.id == experiment_id:
            return index, experiment
    raise ValueError(f"the model has no experiment {experiment_id!r}")


def build_summary(
    model: Model,
    experiment_id: str | None,
    results: Results,
    warnings: Sequence[Issue] = (),
) -> dict[str, Any]:
    """The ``summary.json`` dict of a run of ``model``'s experiment ``experiment_id``.

    ``warnings`` are issues to list before the adapter's (its ``validate`` warnings). When
    ``results.solution`` is set (an optimization run), ``experiment_id`` is not used.
    An experiment the model does not have raises ``ValueError``.
    """
    fidelity = _fidelity(model)
    if results.solution is not None:
        return {
            "model": model.meta.name,
            **results.solution,
            "fidelity_label": fidelity.capitalize(),
            "warnings": [issue.as_dict() for issue in (*warnings, *results.warnings)],
        }
    index, experiment = _experiment(model, experiment_id)
    scenario_ids = [scenario.id for scenario in experiment.scenarios]
    confidence = experiment.confidence
    replications = results.tables.get("replications")
    metrics = (
        across_replications(replications, scenario_ids, confidence)
        if replications is not None
        else {scenario: {} for scenario in scenario_ids}
    )
    differences = (
        paired_differences(replications, scenario_ids, confidence)
        if replications is not None
        else []
    )
    issues = [*warnings, *results.warnings]
    timeseries = results.tables.get("timeseries")
    if timeseries is not None and experiment.search is None:
        drifts = warmup_check(timeseries, experiment.warmup.magnitude, scenario_ids)
        warning = warmup_warning(drifts, index)
        if warning is not None:
            issues.append(warning)
    return {
        "model": model.meta.name,
        "experiment": experiment.id,
        "fidelity": fidelity,
        "fidelity_label": fidelity_label(
            fidelity, experiment.replications, experiment.length.magnitude, confidence
        ),
        "replications": experiment.replications,
        "confidence": confidence,
        "scenarios": {
            scenario.id: {
                "set": {name: _si(value) for name, value in scenario.set.items()},
                "metrics": {
                    metric: item.as_dict() for metric, item in metrics[scenario.id].items()
                },
            }
            for scenario in experiment.scenarios
        },
        "differences": [pair.as_dict() for pair in differences],
        "warnings": [issue.as_dict() for issue in issues],
    }
