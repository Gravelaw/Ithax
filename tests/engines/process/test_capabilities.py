"""The process adapter's ``capabilities()`` (AKS-97).

Spec 1 "Validation": until the process adapter exists (M2) the model layer carries the
``process`` type catalogue from spec 2's block reference, "and at M2 the adapter's
``capabilities()`` must equal it (tested)". Spec 1 "Engine licence rule": ``capabilities()``
reports the engine's licence identifier and how it is invoked; SimPy is MIT and imported
into the process. Spec 1 "Division of labour" and the AKS-98 plan: replications run in
parallel up to ``workers``.
"""

from ithax.engines.process.adapter import ProcessAdapter
from ithax.model.catalogue import PROCESS_TYPES, output_ports

# Spec 2 "Process block library" and "Block reference": the twelve types, written out here
# rather than read from the catalogue, so that a type lost from both would still fail.
SPEC_2_TYPES = {
    "source",
    "queue",
    "server",
    "delay",
    "branch",
    "batch",
    "unbatch",
    "store",
    "resource_pool",
    "schedule",
    "failure",
    "sink",
}


def test_the_component_types_equal_the_model_layer_catalogue() -> None:
    capabilities = ProcessAdapter().capabilities()
    assert capabilities.component_types == PROCESS_TYPES
    assert dict(capabilities.component_types) == dict(PROCESS_TYPES)
    assert list(capabilities.component_types) == list(PROCESS_TYPES)


def test_every_spec_2_type_is_described_with_its_settings_and_ports() -> None:
    types = ProcessAdapter().capabilities().component_types
    assert set(types) == SPEC_2_TYPES
    for name, block in types.items():
        assert block.name == name
        assert block == PROCESS_TYPES[name]
        assert block.settings == PROCESS_TYPES[name].settings
    # Spec 1 "Components and ports": a source has only `out`, a sink only `in`, a branch one
    # output port per route.
    assert (types["source"].inputs, types["source"].outputs) == ((), ("out",))
    assert (types["sink"].inputs, types["sink"].outputs) == (("in",), ())
    assert output_ports(types["branch"], ["a", "b"]) == ("a", "b")


def test_the_adapter_runs_the_process_domain() -> None:
    assert ProcessAdapter().capabilities().domains == ("process",)


def test_simpy_is_mit_and_runs_in_process() -> None:
    capabilities = ProcessAdapter().capabilities()
    assert capabilities.licence == "MIT"
    assert capabilities.invocation == "in-process"


def test_replications_run_in_parallel_and_no_hardware_is_needed() -> None:
    capabilities = ProcessAdapter().capabilities()
    assert capabilities.parallel_modes == ("replications",)
    assert capabilities.hardware == ()


def test_capabilities_are_the_same_each_call() -> None:
    adapter = ProcessAdapter()
    assert adapter.capabilities() == adapter.capabilities() == ProcessAdapter().capabilities()
