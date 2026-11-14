"""``/v1/engines`` and ``/v1/schema``: the installed adapters and the model file's schema
(spec 3 "Endpoints"; spec 1 "Engine adapter interface").

- ``GET /v1/engines``: each adapter's ``Capabilities``, by adapter name, with its
  component types as a list of names.
- ``GET /v1/schema/components/{type}``: one component type's description: its domain and
  adapter, a one-sentence ``description``, its ports, its settings (each with the keys of
  the catalogue that apply to it) and its metrics. A type no installed adapter has is 404
  with E185. Where two adapters declare the same type, the first by name is described.
- ``GET /v1/schema``: spec 1's static schema with one added top-level annotation,
  ``x-component-types``, mapping each component type to that description. An annotation
  does not change what the schema accepts (AKS-110, owner to confirm).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import fields
from enum import Enum
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi import Path as PathParameter

from ithax.engines.adapter import EngineAdapter
from ithax.model.catalogue import BlockType, SettingSpec
from ithax.model.schema import model_schema
from ithax.model.units import Quantity
from ithax.service.errors import NOT_FOUND, ServiceError
from ithax.service.state import ServiceState, service_state

__all__ = [
    "COMPONENT_TYPES_KEY",
    "composed_schema",
    "describe_component",
    "describe_engine",
    "describe_setting",
    "router",
]

router = APIRouter(prefix="/v1")

State = Annotated[ServiceState, Depends(service_state)]

#: The annotation the composed schema adds (spec 3 "Endpoints" notes).
COMPONENT_TYPES_KEY = "x-component-types"

_SETTING_DEFAULTS = {
    spec.name: spec.default for spec in fields(SettingSpec) if spec.name not in ("name", "kind")
}


def _quantity_text(quantity: Quantity) -> str:
    """A quantity as the model file writes one, in SI units: ``"86400 s"``."""
    magnitude = quantity.magnitude
    number = str(int(magnitude)) if magnitude.is_integer() else repr(magnitude)
    return f"{number} {quantity.unit}"


def _json_value(value: object) -> object:
    if isinstance(value, Quantity):
        return _quantity_text(value)
    if isinstance(value, SettingSpec):
        return describe_setting(value)
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


def describe_setting(spec: SettingSpec) -> dict[str, Any]:
    """A setting as JSON: ``name``, ``kind`` and ``required``, then each other key of
    the catalogue whose value differs from its default."""
    described: dict[str, Any] = {
        "name": spec.name,
        "kind": spec.kind.value,
        "required": spec.required,
    }
    for key, default in _SETTING_DEFAULTS.items():
        value = getattr(spec, key)
        if key != "required" and value != default:
            described[key] = _json_value(value)
    return described


def describe_component(
    type_name: str, block: BlockType, engine: str, domain: str
) -> dict[str, Any]:
    """One component type as ``GET /v1/schema/components/{type}`` returns it."""
    return {
        "type": type_name,
        "domain": domain,
        "engine": engine,
        "description": block.description,
        "inputs": list(block.inputs),
        "outputs": list(block.outputs),
        "outputs_from": block.outputs_from,
        "settings": [describe_setting(spec) for spec in block.settings],
        "metrics": list(block.metrics),
    }


def _component_types(
    adapters: Mapping[str, EngineAdapter],
) -> Iterator[tuple[str, BlockType, str, str]]:
    """Each component type once: (type, block, adapter name, domain), adapters by name."""
    seen: set[str] = set()
    for name in sorted(adapters):
        capabilities = adapters[name].capabilities()
        domain = capabilities.domains[0] if capabilities.domains else ""
        for type_name, block in capabilities.component_types.items():
            if type_name not in seen:
                seen.add(type_name)
                yield type_name, block, name, domain


def composed_schema(adapters: Mapping[str, EngineAdapter]) -> dict[str, Any]:
    """Spec 1's schema with the installed component types under ``x-component-types``."""
    schema = model_schema()
    schema[COMPONENT_TYPES_KEY] = {
        type_name: describe_component(type_name, block, engine, domain)
        for type_name, block, engine, domain in _component_types(adapters)
    }
    return schema


def describe_engine(adapter: EngineAdapter) -> dict[str, Any]:
    """An adapter as ``GET /v1/engines`` lists it."""
    capabilities = adapter.capabilities()
    return {
        "name": adapter.name,
        "version": adapter.version,
        "domains": list(capabilities.domains),
        "component_types": list(capabilities.component_types),
        "hardware": list(capabilities.hardware),
        "parallel_modes": list(capabilities.parallel_modes),
        "licence": capabilities.licence,
        "invocation": capabilities.invocation,
    }


@router.get("/engines")
def list_engines(state: State) -> list[dict[str, Any]]:
    """The installed adapters with their capabilities, by name."""
    return [describe_engine(state.adapters[name]) for name in sorted(state.adapters)]


@router.get("/schema")
def get_schema(state: State) -> dict[str, Any]:
    """The composed JSON Schema."""
    return composed_schema(state.adapters)


@router.get("/schema/components/{type}")
def get_component_type(
    type_name: Annotated[str, PathParameter(alias="type")], state: State
) -> dict[str, Any]:
    """One component type's settings, ports and description."""
    for found, block, engine, domain in _component_types(state.adapters):
        if found == type_name:
            return describe_component(found, block, engine, domain)
    raise ServiceError(404, NOT_FOUND, f"No installed engine has the component type '{type_name}'.")
