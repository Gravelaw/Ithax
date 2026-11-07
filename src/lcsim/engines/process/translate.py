"""The process adapter's own input, ``engine/input.json`` (spec 1 "Division of labour").

``engine_input(model, experiment_id)`` builds it: the experiment's ``id``, ``length``,
``warmup``, ``replications``, ``seed`` and ``record_interval`` (times as SI floats), the
connections as the model file writes them, and for each scenario every component's ``id``,
``type`` and settings, with that scenario's parameter values resolved, quantities as SI
floats, distributions as objects of SI floats, and the catalogue's defaults filled in.

``ui``, ``label`` and ``meta`` are left out: an engine never reads ``ui`` (spec 1
"Components and ports"), so changing them leaves the file byte-equal. The JSON is written
with a fixed key order and Python's shortest round-trip float text.

The adapter runs every type of spec 2's block reference (``BLOCK_TYPES`` holds every
type of the model layer's catalogue since M4). An ``empirical`` with ``data`` is written with
the values the run target read from its column, in seconds (``lcsim.runs.snapshots``;
AKS-113); one whose column has not been read raises ``DataNotReadError`` (E162).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from lcsim.model.catalogue import PROCESS_TYPES
from lcsim.model.distributions import DataNotReadError
from lcsim.model.model import (
    Component,
    Distribution,
    Experiment,
    JsonValue,
    Model,
    ParameterValue,
    ParamRef,
    SettingValue,
)
from lcsim.model.units import Quantity

__all__ = [
    "INPUT_FILE",
    "INPUT_VERSION",
    "engine_input",
    "read_input",
    "resolve_setting",
    "write_input",
]

#: The engine input's file name inside ``workdir``.
INPUT_FILE = "input.json"
#: The layout version of the engine input.
INPUT_VERSION = 1


def engine_input(model: Model, experiment_id: str) -> dict[str, Any]:
    """The engine input for experiment ``experiment_id`` of ``model``.

    An unknown experiment id raises ``ValueError``: the caller chose it from the model.
    """
    experiment = next((item for item in model.experiments if item.id == experiment_id), None)
    if experiment is None:
        raise ValueError(f"the model has no experiment '{experiment_id}'")
    return {
        "input_version": INPUT_VERSION,
        "experiment": _experiment(experiment),
        "connections": [
            {
                "from": f"{connection.origin.component}.{connection.origin.port}",
                "to": f"{connection.destination.component}.{connection.destination.port}",
            }
            for connection in model.connections
        ],
        "scenarios": [
            {
                "id": scenario.id,
                "components": [
                    _component(model, component, scenario.set) for component in model.components
                ],
            }
            for scenario in experiment.scenarios
        ],
    }


def write_input(model: Model, experiment_id: str, workdir: Path) -> Path:
    """Writes the engine input to ``workdir/input.json`` and returns its path."""
    document = engine_input(model, experiment_id)
    text = json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    workdir.mkdir(parents=True, exist_ok=True)
    path = workdir / INPUT_FILE
    path.write_bytes(text.encode("utf-8"))
    return path


def read_input(workdir: Path) -> dict[str, Any]:
    """The engine input ``write_input`` wrote in ``workdir``."""
    document: dict[str, Any] = json.loads((workdir / INPUT_FILE).read_text(encoding="utf-8"))
    if document.get("input_version") != INPUT_VERSION:
        raise ValueError(f"'{workdir / INPUT_FILE}' is not a version {INPUT_VERSION} input")
    return document


def _experiment(experiment: Experiment) -> dict[str, Any]:
    return {
        "id": experiment.id,
        "length": experiment.length.magnitude,
        "warmup": experiment.warmup.magnitude,
        "replications": experiment.replications,
        "seed": experiment.seed,
        "record_interval": experiment.record_interval.magnitude,
    }


def _component(
    model: Model, component: Component, values: Mapping[str, ParameterValue]
) -> dict[str, Any]:
    settings: dict[str, Any] = {}
    for spec in PROCESS_TYPES[component.type].settings:
        if spec.name in component.settings:
            settings[spec.name] = resolve_setting(model, component.settings[spec.name], values)
        elif spec.default is not None:
            settings[spec.name] = resolve_setting(model, spec.default, values)
    return {"id": component.id, "type": component.type, "settings": settings}


def _number(value: ParameterValue) -> int | float:
    return value.magnitude if isinstance(value, Quantity) else value


def resolve_setting(
    model: Model, value: SettingValue, values: Mapping[str, ParameterValue]
) -> JsonValue:
    """A setting as plain JSON: references resolved, quantities as SI floats."""
    if isinstance(value, ParamRef):
        return _number(values.get(value.parameter, model.parameters[value.parameter].value))
    if isinstance(value, Quantity):
        return value.magnitude
    if isinstance(value, Distribution):
        return _distribution(model, value, values)
    if isinstance(value, tuple):
        return [resolve_setting(model, entry, values) for entry in value]
    if isinstance(value, Mapping):
        return {key: resolve_setting(model, entry, values) for key, entry in value.items()}
    return value  # a whole number, a number or a word


def _distribution(
    model: Model, distribution: Distribution, values: Mapping[str, ParameterValue]
) -> dict[str, JsonValue]:
    if distribution.data is not None and distribution.values is None:
        raise DataNotReadError(distribution.data)
    resolved: dict[str, JsonValue] = {"dist": distribution.dist}
    for name, scalar in distribution.fields.items():
        resolved[name] = _float(resolve_setting(model, scalar, values))
    if distribution.values is not None:
        resolved["values"] = [
            _float(resolve_setting(model, entry, values)) for entry in distribution.values
        ]
    return resolved


def _float(value: JsonValue) -> float:
    assert isinstance(value, int | float)  # a distribution field is a number
    return float(value)
