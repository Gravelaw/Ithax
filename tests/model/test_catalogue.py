"""The process type catalogue and the distribution table (AKS-88).

Spec 1 "Validation": until the process adapter exists (M2) the model layer carries the
``process`` type catalogue from spec 2 "Block reference"; at M2 the adapter's
``capabilities()`` must equal it. Spec 1 "Components and ports" and "Distributions";
spec 2 "Block reference" and "Statistic definitions". Each test names the rule it checks.
"""

import pytest

from lcsim.model.catalogue import (
    DATA_FIELDS,
    DISTRIBUTIONS,
    DOMAINS,
    MODEL_METRICS,
    PROCESS_TYPES,
    BlockType,
    FieldKind,
    SettingKind,
    SettingSpec,
    output_ports,
)
from lcsim.model.units import Dimension, Quantity

TIME = Dimension.TIME

# Spec 2 "Block reference": the twelve types, in table order.
TWELVE = [
    "source",
    "server",
    "delay",
    "branch",
    "queue",
    "batch",
    "unbatch",
    "store",
    "resource_pool",
    "schedule",
    "failure",
    "sink",
]


def spec(type_name: str, setting: str) -> SettingSpec:
    found = PROCESS_TYPES[type_name].setting(setting)
    assert found is not None, (type_name, setting)
    return found


def test_domains_are_the_phase_1_values() -> None:
    # Spec 1 "Top-level keys": `domain`, Phase 1 values `process` and `optimization`.
    assert DOMAINS == ("process", "optimization")


def test_the_catalogue_holds_the_twelve_block_types_in_spec_order() -> None:
    assert list(PROCESS_TYPES) == TWELVE
    for name, block in PROCESS_TYPES.items():
        assert isinstance(block, BlockType)
        assert block.name == name


@pytest.mark.parametrize(
    ("type_name", "inputs", "outputs", "outputs_from"),
    [
        # Spec 1 "Components and ports": most have `in` and `out`; a source only `out`;
        # a sink only `in`; a branch one output port per entry of `routes`.
        ("source", (), ("out",), None),
        ("server", ("in",), ("out",), None),
        ("delay", ("in",), ("out",), None),
        ("branch", ("in",), (), "routes"),
        ("queue", ("in",), ("out",), None),
        ("batch", ("in",), ("out",), None),
        ("unbatch", ("in",), ("out",), None),
        ("store", ("in",), ("out",), None),
        # Spec 2 "Block reference": `resource_pool`, `schedule` and `failure` have none.
        ("resource_pool", (), (), None),
        ("schedule", (), (), None),
        ("failure", (), (), None),
        ("sink", ("in",), (), None),
    ],
)
def test_ports(
    type_name: str, inputs: tuple[str, ...], outputs: tuple[str, ...], outputs_from: str | None
) -> None:
    block = PROCESS_TYPES[type_name]
    assert block.inputs == inputs
    assert block.outputs == outputs
    assert block.outputs_from == outputs_from


def test_output_ports_of_a_branch_are_its_routes() -> None:
    branch = PROCESS_TYPES["branch"]
    assert output_ports(branch, ("a", "b")) == ("a", "b")
    assert output_ports(branch, ()) == ()


def test_output_ports_of_other_types_ignore_routes() -> None:
    assert output_ports(PROCESS_TYPES["server"], ("a",)) == ("out",)
    assert output_ports(PROCESS_TYPES["sink"], ()) == ()


# (type, setting, kind, required) for every setting of spec 2 "Block reference".
SETTINGS = [
    ("source", "interarrival", SettingKind.DISTRIBUTION, True),
    ("source", "first_arrival", SettingKind.QUANTITY, False),
    ("source", "max_items", SettingKind.NUMBER, False),
    ("server", "capacity", SettingKind.NUMBER, True),
    ("server", "service", SettingKind.DISTRIBUTION, True),
    ("server", "queue_capacity", SettingKind.NUMBER, False),
    ("server", "discipline", SettingKind.IDENTIFIER, False),
    ("server", "pool", SettingKind.IDENTIFIER, False),
    ("delay", "time", SettingKind.DISTRIBUTION, True),
    ("branch", "routes", SettingKind.IDENTIFIER, True),
    ("branch", "rule", SettingKind.IDENTIFIER, True),
    ("branch", "weights", SettingKind.OBJECT, False),
    ("queue", "capacity", SettingKind.NUMBER, True),
    ("queue", "discipline", SettingKind.IDENTIFIER, False),
    ("queue", "on_full", SettingKind.IDENTIFIER, False),
    ("batch", "size", SettingKind.NUMBER, True),
    ("batch", "timeout", SettingKind.QUANTITY, False),
    ("store", "initial", SettingKind.NUMBER, True),
    ("store", "reorder_point", SettingKind.NUMBER, True),
    ("store", "order_quantity", SettingKind.NUMBER, True),
    ("store", "lead_time", SettingKind.DISTRIBUTION, True),
    ("resource_pool", "capacity", SettingKind.NUMBER, True),
    ("schedule", "target", SettingKind.IDENTIFIER, True),
    ("schedule", "shifts", SettingKind.OBJECT, True),
    ("schedule", "period", SettingKind.QUANTITY, False),
    ("failure", "target", SettingKind.IDENTIFIER, True),
    ("failure", "time_to_failure", SettingKind.DISTRIBUTION, True),
    ("failure", "time_to_repair", SettingKind.DISTRIBUTION, True),
]


def test_settings_table_is_complete() -> None:
    declared = {
        (block.name, setting.name) for block in PROCESS_TYPES.values() for setting in block.settings
    }
    assert declared == {(t, s) for t, s, _, _ in SETTINGS}
    # `unbatch` and `sink`: settings "none".
    assert PROCESS_TYPES["unbatch"].settings == ()
    assert PROCESS_TYPES["sink"].settings == ()


@pytest.mark.parametrize(("type_name", "setting", "kind", "required"), SETTINGS)
def test_setting_kind_and_required(
    type_name: str, setting: str, kind: SettingKind, required: bool
) -> None:
    found = spec(type_name, setting)
    assert found.kind is kind
    assert found.required is required


def test_unknown_setting_is_none() -> None:
    assert PROCESS_TYPES["server"].setting("speed") is None


def test_quantities_and_distributions_are_times() -> None:
    for block in PROCESS_TYPES.values():
        for setting in block.settings:
            if setting.kind in (SettingKind.QUANTITY, SettingKind.DISTRIBUTION):
                assert setting.dimension is TIME, (block.name, setting.name)
            elif setting.kind is not SettingKind.OBJECT:
                assert setting.dimension is None, (block.name, setting.name)


@pytest.mark.parametrize(
    ("type_name", "setting"),
    [
        ("source", "max_items"),
        ("server", "capacity"),
        ("server", "queue_capacity"),
        ("queue", "capacity"),
        ("batch", "size"),
        ("store", "initial"),
        ("store", "reorder_point"),
        ("store", "order_quantity"),
        ("resource_pool", "capacity"),
    ],
)
def test_counts_and_capacities_are_whole_numbers(type_name: str, setting: str) -> None:
    assert spec(type_name, setting).integer is True


def test_word_settings_list_their_choices_and_defaults() -> None:
    # Spec 2 "Discipline": `fifo` (default) or `lifo`; `on_full` `block` (default) or
    # `discard`; branch `rule` `probability` or `shortest_queue`.
    for type_name in ("server", "queue"):
        discipline = spec(type_name, "discipline")
        assert discipline.choices == ("fifo", "lifo")
        assert discipline.default == "fifo"
    assert spec("queue", "on_full").choices == ("block", "discard")
    assert spec("queue", "on_full").default == "block"
    assert spec("branch", "rule").choices == ("probability", "shortest_queue")
    assert spec("branch", "rule").default is None


def test_schedule_period_defaults_to_24_h() -> None:
    assert spec("schedule", "period").default == Quantity(86_400.0, TIME)


def test_component_references_name_their_target_types() -> None:
    # Spec 2: `pool` names a resource pool; a schedule targets a server or pool; a failure
    # a server (spec 1 E124: "names an unknown component or one of the wrong type").
    assert spec("server", "pool").refers_to == ("resource_pool",)
    assert spec("schedule", "target").refers_to == ("server", "resource_pool")
    assert spec("failure", "target").refers_to == ("server",)
    assert spec("server", "discipline").refers_to == ()


def test_routes_are_a_list_of_identifiers() -> None:
    routes = spec("branch", "routes")
    assert routes.many is True
    assert routes.choices == ()


def test_weights_are_keyed_by_route_and_required_for_probability() -> None:
    weights = spec("branch", "weights")
    assert weights.keyed_by == "routes"
    assert weights.required_when == ("rule", "probability")
    assert weights.values is not None
    assert weights.values.kind is SettingKind.NUMBER
    assert weights.values.integer is False


def test_shifts_are_a_list_of_start_end_capacity_objects() -> None:
    shifts = spec("schedule", "shifts")
    assert shifts.many is True
    fields = {field.name: field for field in shifts.fields}
    assert list(fields) == ["start", "end", "capacity"]
    assert fields["start"].kind is SettingKind.QUANTITY
    assert fields["start"].dimension is TIME
    assert fields["end"].kind is SettingKind.QUANTITY
    assert fields["capacity"].kind is SettingKind.NUMBER
    assert fields["capacity"].integer is True
    assert all(field.required for field in shifts.fields)


# --- metrics (spec 2 "Statistic definitions") ---------------------------------------------


@pytest.mark.parametrize(
    ("type_name", "metrics"),
    [
        (
            "server",
            (
                "wait.mean",
                "utilization",
                "availability",
                "scheduled_fraction",
                "queue_length.mean",
                "queue_length.max",
            ),
        ),
        ("queue", ("queue_length.mean", "queue_length.max", "wait.mean", "discarded")),
        ("sink", ("throughput", "cycle_time.mean", "count")),
        ("batch", ("wait.mean",)),
        ("resource_pool", ("utilization",)),
        ("store", ("stock.mean", "stockouts", "orders")),
        ("source", ("created", "discarded")),
        ("delay", ()),
        ("branch", ()),
        ("unbatch", ()),
        ("schedule", ()),
        ("failure", ()),
    ],
)
def test_metrics_per_type(type_name: str, metrics: tuple[str, ...]) -> None:
    assert PROCESS_TYPES[type_name].metrics == metrics


def test_model_metrics() -> None:
    assert MODEL_METRICS == ("wip.mean",)


# --- distributions (spec 1 "Distributions") -----------------------------------------------


def fields_of(dist: str) -> list[list[tuple[str, FieldKind, bool]]]:
    return [
        [(field.name, field.kind, field.many) for field in form]
        for form in DISTRIBUTIONS[dist].forms
    ]


Q = FieldKind.QUANTITY
N = FieldKind.NUMBER


def test_the_eight_distributions_in_spec_order() -> None:
    assert list(DISTRIBUTIONS) == [
        "constant",
        "exponential",
        "uniform",
        "triangular",
        "normal",
        "lognormal",
        "weibull",
        "empirical",
    ]
    for name, distribution in DISTRIBUTIONS.items():
        assert distribution.name == name


@pytest.mark.parametrize(
    ("dist", "forms"),
    [
        ("constant", [[("value", Q, False)]]),
        ("exponential", [[("mean", Q, False)]]),
        ("uniform", [[("min", Q, False), ("max", Q, False)]]),
        ("triangular", [[("min", Q, False), ("mode", Q, False), ("max", Q, False)]]),
        ("normal", [[("mean", Q, False), ("sd", Q, False)]]),
        ("lognormal", [[("mean", Q, False), ("sd", Q, False)]]),
        # `shape` is a plain number; `scale` has the setting's dimension.
        ("weibull", [[("shape", N, False), ("scale", Q, False)]]),
        # `values` inline, or `data` = {file, column}: exactly one of the two.
        ("empirical", [[("values", Q, True)], [("data", FieldKind.DATA, False)]]),
    ],
)
def test_distribution_fields(dist: str, forms: list[list[tuple[str, FieldKind, bool]]]) -> None:
    assert fields_of(dist) == forms


def test_field_names_of_a_distribution() -> None:
    assert DISTRIBUTIONS["triangular"].field_names() == ("min", "mode", "max")
    assert DISTRIBUTIONS["empirical"].field_names() == ("values", "data")


def test_a_data_reference_has_file_and_column() -> None:
    assert DATA_FIELDS == ("file", "column")
