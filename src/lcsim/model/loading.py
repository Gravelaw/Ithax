"""Load a model file into the typed model of ``lcsim.model.model``.

Order of work:

1. ``load_text`` reads the file's bytes as UTF-8 JSON. Text that is not JSON, ``NaN`` or
   ``Infinity``, a number with more digits than Python reads, nesting deeper than the JSON
   reader allows, and a key written twice in one object are E100 issues: the file does not
   match the schema (spec 1 "Validation issues").
2. ``load_document`` runs the schema pass (``lcsim.model.schema.schema_pass``, E100 and
   E101). A file with a schema issue is not built.
3. It then builds the typed ``Model``: every quantity converted to SI (spec 1 "Units"),
   every ``{"$param": "id"}`` kept as a ``ParamRef``, every distribution checked against
   spec 1 "Distributions", every component's ``params`` against the ``process`` catalogue,
   and every experiment default of spec 1 "Experiments" filled in.
4. On a model that builds, it runs the meaning pass (``lcsim.model.validation``).
   ``build_document`` stops after step 3.

Building reports, with its spec 1 code, every problem that stops a value from being
converted: E102 (no single engine for the ``domain``, checked first with
``lcsim.model.validation.engine_issues``), E120 (unknown type), E121 (unknown setting),
E122 (required setting missing), E123 (a value of the wrong kind), E130 (a connection end
that is not ``<id>.<port>``), E140 and E141 (quantities), E150 (a scenario setting an
unknown parameter, whose value cannot be typed without it) and E160 (a distribution that is
not one of spec 1's). Checks across the model are the meaning pass's: identifiers,
settings that name components, and the connection graph (AKS-89); ranges, consistency of
distribution fields, metric names and warnings follow (AKS-90, AKS-91).

A file with any error issue gives no model. Building lists its issues in document order;
the meaning pass's follow, grouped by rule.
"""

from __future__ import annotations

import json
import secrets
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, TypeVar

from lcsim.model.catalogue import (
    DATA_FIELDS,
    DISTRIBUTIONS,
    PROCESS_TYPES,
    BlockType,
    FieldKind,
    FieldSpec,
    SettingKind,
    SettingSpec,
)
from lcsim.model.issues import Issue, pointer
from lcsim.model.model import (
    Component,
    Connection,
    DataRef,
    Distribution,
    Endpoint,
    Experiment,
    LinearConstraint,
    LinearObjective,
    LinearProgram,
    Meta,
    MetricConstraint,
    MetricObjective,
    Model,
    Parameter,
    ParameterValue,
    ParamRef,
    RunSettings,
    Scalar,
    Scenario,
    Search,
    SettingValue,
    Variable,
)
from lcsim.model.schema import schema_pass
from lcsim.model.units import Dimension, Quantity, QuantityError, read_number, read_quantity
from lcsim.model.validation import engine_issues, meaning_pass

__all__ = [
    "SEED_LIMIT",
    "LoadResult",
    "ModelLoadError",
    "build_document",
    "load_document",
    "load_model",
    "load_text",
]

# A seed the file leaves out is drawn from 0 to SEED_LIMIT - 1 (spec 1 "Experiments": chosen
# at random and recorded in the manifest), so that it fits a signed 64-bit integer.
SEED_LIMIT = 2**63

# Spec 1 "Experiments" defaults.
_REPLICATIONS = 30
_CONFIDENCE = 0.95
_RECORD_INTERVALS = 200  # record_interval defaults to length / 200
_SEARCH_BUDGET = 50
_SEARCH_REPLICATIONS = 10
_DEFAULT_SCENARIO = "default"

# Spec 1 "Top-level keys": `run` defaults.
_DEFAULT_TARGET = "local"
_DEFAULT_FIDELITY = "standard"

# The words of the enumerated keys (spec 1 "Parameters", "Metric names"; spec 2
# "Mathematical optimization in the model file").
_PARAMETER_TYPES = ("integer", "number", "quantity")
_SENSES = ("minimize", "maximize")
_METRIC_OPS = ("<=", ">=")
_LINEAR_OPS = ("<=", ">=", "==")
_VARIABLE_TYPES = ("continuous", "integer", "binary")

SeedSource = Callable[[], int]
_T = TypeVar("_T")
Segment = str | int


@dataclass(frozen=True)
class LoadResult:
    """The outcome of loading: the model, or ``None`` when any issue is an error."""

    model: Model | None
    issues: tuple[Issue, ...]

    @property
    def errors(self) -> tuple[Issue, ...]:
        """The issues of severity ``error``."""
        return tuple(issue for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[Issue, ...]:
        """The issues of severity ``warning``."""
        return tuple(issue for issue in self.issues if issue.severity == "warning")


class ModelLoadError(Exception):
    """Raised by ``load_model`` when the file has error issues; ``issues`` lists them all."""

    def __init__(self, issues: Sequence[Issue]) -> None:
        self.issues = tuple(issues)
        summary = "; ".join(f"{issue.code} at '{issue.path}': {issue.message}" for issue in issues)
        super().__init__(f"the model file has {len(self.issues)} issue(s): {summary}")


def load_model(path: str | Path, *, seed_source: SeedSource | None = None) -> Model:
    """Load the model file at ``path``.

    Raises ``ModelLoadError`` carrying every issue when any issue is an error. A file that
    cannot be opened raises ``OSError``, as from ``open``: the caller chose the path.
    ``seed_source`` gives the seed of an experiment that has none (default: a random
    integer from 0 to ``SEED_LIMIT`` - 1 from the operating system's generator).
    """
    result = load_text(Path(path).read_bytes(), seed_source=seed_source)
    if result.model is None:
        raise ModelLoadError(result.issues)
    return result.model


def load_text(text: str | bytes, *, seed_source: SeedSource | None = None) -> LoadResult:
    """Load a model from JSON text; bytes are read as UTF-8, with or without a BOM."""
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8-sig")
        except UnicodeDecodeError:
            return _unreadable(
                "The file is not UTF-8 text, so it cannot be read as a model file.",
                "Save the file as UTF-8.",
            )
    # id of an object -> (the object, its keys written more than once). The object is held
    # so that its id cannot be reused by another object while the file is parsed (a value
    # replaced by a later duplicate key would otherwise be freed).
    duplicates: dict[int, tuple[dict[str, Any], list[str]]] = {}

    def make_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        made = dict(pairs)
        if len(made) != len(pairs):
            seen: set[str] = set()
            repeated: list[str] = []
            for key, _ in pairs:
                if key in seen and key not in repeated:
                    repeated.append(key)
                seen.add(key)
            duplicates[id(made)] = (made, repeated)
        return made

    try:
        document = json.loads(
            text,
            object_pairs_hook=make_object,
            parse_constant=_reject_constant,
            parse_int=_parse_int,
        )
    except _Unreadable as problem:
        return _unreadable(problem.message, problem.hint)
    except json.JSONDecodeError as error:
        return _unreadable(
            f"The file is not valid JSON: reading stops at line {error.lineno}, "
            f"column {error.colno}.",
            "Correct the JSON at that place; a JSON validator shows what is wrong.",
        )
    except RecursionError:
        return _unreadable(
            "The file is nested too deeply to be read.",
            "Model files nest objects and arrays only a few levels deep; check the file.",
        )
    # An object replaced by a later duplicate key has gone, but the object holding that
    # duplicate key is in the document, so a duplicate always yields an issue here.
    if duplicates and (issues := _duplicate_key_issues(document, duplicates)):
        return LoadResult(None, tuple(issues))
    return load_document(document, seed_source=seed_source)


def load_document(document: object, *, seed_source: SeedSource | None = None) -> LoadResult:
    """Load a model from a parsed JSON document: the schema pass, building, then the
    meaning pass (``lcsim.model.validation``) on a model that builds.

    ``document`` is not changed. The model may share the JSON values of a component's
    ``ui`` and of ``run.target`` and ``run.fidelity`` with it.
    """
    built = build_document(document, seed_source=seed_source)
    if built.model is None:
        return built
    issues = (*built.issues, *meaning_pass(built.model))
    if any(issue.severity == "error" for issue in issues):
        return LoadResult(None, issues)
    return LoadResult(built.model, issues)


def build_document(document: object, *, seed_source: SeedSource | None = None) -> LoadResult:
    """The schema pass and building only, without the meaning pass.

    The model it returns has every value converted but is not checked across the model
    (identifiers, references, connections): use ``load_document`` for a model to run.
    This step exists on its own so that building can be tested on fragments of a model.
    """
    schema_issues = schema_pass(document)
    if schema_issues:
        return LoadResult(None, tuple(schema_issues))
    assert isinstance(document, dict)  # the schema requires an object
    builder = _Builder(document, seed_source or _random_seed)
    model = builder.build()
    issues = tuple(builder.issues)
    if model is None or any(issue.severity == "error" for issue in issues):
        return LoadResult(None, issues)
    return LoadResult(model, issues)


def _random_seed() -> int:
    # The operating system's generator, not Python's global random generator: a seed the
    # file leaves out is the root of the spec 1 stream scheme, not a draw from it.
    return secrets.randbelow(SEED_LIMIT)


# --- reading JSON ------------------------------------------------------------------------


class _Unreadable(Exception):
    def __init__(self, message: str, hint: str) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


def _reject_constant(name: str) -> object:
    raise _Unreadable(
        f"The file holds '{name}', which is not a JSON number.",
        "Write a finite number; JSON has no NaN or Infinity.",
    )


def _parse_int(text: str) -> int:
    digits = len(text) - text.startswith("-")
    limit = sys.get_int_max_str_digits()
    if limit and digits > limit:
        raise _Unreadable(
            f"The file holds a whole number with too many digits to read ({digits} digits).",
            "Write a shorter number.",
        )
    return int(text)


def _unreadable(message: str, hint: str) -> LoadResult:
    return LoadResult(None, (Issue("E100", None, "", message, hint),))


def _duplicate_key_issues(
    document: object, duplicates: Mapping[int, tuple[dict[str, Any], list[str]]]
) -> list[Issue]:
    """E100 for each key written twice in one object that is in the document, in document
    order (an object that a later duplicate key replaced is not in the document).

    An explicit stack, so that a deeply nested file cannot exhaust the recursion limit.
    """
    issues: list[Issue] = []
    stack: list[tuple[object, tuple[Segment, ...]]] = [(document, ())]
    while stack:
        value, at = stack.pop()
        if isinstance(value, dict):
            held, repeated = duplicates.get(id(value), (None, []))
            for key in repeated if held is value else []:
                issues.append(
                    Issue(
                        "E100",
                        None,
                        pointer(*at, key),
                        f"The key '{key}' is written more than once in the same object, so "
                        "it is not clear which value is meant.",
                        f"Keep one '{key}' and remove the others.",
                    )
                )
            stack.extend((item, (*at, key)) for key, item in reversed(list(value.items())))
        elif isinstance(value, list):
            stack.extend((item, (*at, index)) for index, item in reversed(list(enumerate(value))))
    return issues


# --- building the model --------------------------------------------------------------------


def _show(value: object) -> str:
    """A JSON value as a message quotes it; never a long or unprintable one."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f"'{value}'"
    if isinstance(value, int) and value.bit_length() > 64:
        return "a very large whole number"
    if isinstance(value, int | float):
        return repr(value)
    if isinstance(value, list):
        return "an array"
    return "an object"


def _words(words: Sequence[str]) -> str:
    quoted = [f"'{word}'" for word in words]
    if len(quoted) == 1:
        return quoted[0]
    return ", ".join(quoted[:-1]) + " or " + quoted[-1]


def _param_ref(value: object) -> ParamRef | None:
    """A ``{"$param": "id"}`` reference: exactly that one key, with text as the id."""
    if isinstance(value, dict) and len(value) == 1 and isinstance(value.get("$param"), str):
        return ParamRef(value["$param"])
    return None


class _Builder:
    """Builds a ``Model`` from a document that passed the schema; collects issues."""

    def __init__(self, document: Mapping[str, Any], seed_source: SeedSource) -> None:
        self.document = document
        self.seed_source = seed_source
        self.issues: list[Issue] = []
        self.parameters: dict[str, Parameter] = {}

    # --- issues ---

    def issue(
        self,
        code: str,
        at: Sequence[Segment],
        message: str,
        hint: str,
        component: str | None = None,
    ) -> None:
        self.issues.append(Issue(code, component, pointer(*at), message, hint))

    def problem(
        self, error: QuantityError, where: str, at: Sequence[Segment], component: str | None
    ) -> None:
        self.issues.append(
            Issue.from_problem(error, where=where, path=pointer(*at), component=component)
        )

    # --- values ---

    def number(
        self,
        value: object,
        where: str,
        at: Sequence[Segment],
        component: str | None = None,
        *,
        integer: bool = False,
    ) -> int | float | None:
        """A plain number; with ``integer``, a whole number (``2.0`` reads as ``2``)."""
        try:
            number = read_number(value)
        except QuantityError as error:
            self.problem(error, where, at, component)
            return None
        if integer and isinstance(number, float):
            if not number.is_integer():
                self.issue(
                    "E123",
                    at,
                    f"In {where}, {_show(number)} is not a whole number; a whole number is "
                    "expected.",
                    "Write a whole number, as in 3.",
                    component,
                )
                return None
            return int(number)
        return number

    def quantity(
        self,
        value: object,
        dimension: Dimension,
        where: str,
        at: Sequence[Segment],
        component: str | None = None,
    ) -> Quantity | None:
        try:
            return read_quantity(value, dimension)
        except QuantityError as error:
            self.problem(error, where, at, component)
            return None

    def word(
        self,
        value: object,
        words: Sequence[str],
        where: str,
        at: Sequence[Segment],
        component: str | None = None,
    ) -> str | None:
        """One of ``words``; anything else is E123."""
        if isinstance(value, str) and value in words:
            return value
        self.issue(
            "E123",
            at,
            f"In {where}, {_show(value)} is not allowed; it must be {_words(words)}.",
            f"Write {_words(words)}.",
            component,
        )
        return None

    # --- the model ---

    def build(self) -> Model | None:
        document = self.document
        domain: str = document["domain"]
        engine: str | None = document.get("run", {}).get("engine")
        engine_problems = engine_issues(domain, engine)
        if engine_problems:
            # A model of a domain no engine runs cannot be built: its keys are not known.
            self.issues += engine_problems
            return None
        meta = document["meta"]
        self.load_parameters()
        components: tuple[Component, ...] = ()
        connections: tuple[Connection, ...] = ()
        experiments: tuple[Experiment, ...] = ()
        objectives: tuple[MetricObjective, ...] = ()
        constraints: tuple[MetricConstraint, ...] = ()
        program: LinearProgram | None = None
        if domain == "process":
            components = _present(
                self.component(index, raw) for index, raw in enumerate(document["components"])
            )
            connections = _present(
                self.connection(index, raw) for index, raw in enumerate(document["connections"])
            )
            experiments = _present(
                self.experiment(index, raw) for index, raw in enumerate(document["experiments"])
            )
            objectives = _present(
                self.metric_objective(index, raw)
                for index, raw in enumerate(document.get("objectives", []))
            )
            constraints = _present(
                self.metric_constraint(index, raw)
                for index, raw in enumerate(document.get("constraints", []))
            )
        else:
            program = self.program()
        if self.issues:
            return None
        return Model(
            format_version=document["format_version"],
            meta=Meta(
                name=meta["name"],
                description=meta.get("description"),
                author=meta.get("author"),
                template=meta.get("template"),
            ),
            domain=domain,
            parameters=MappingProxyType(dict(self.parameters)),
            components=components,
            connections=connections,
            experiments=experiments,
            objectives=objectives,
            constraints=constraints,
            program=program,
            run=self.run(),
        )

    # --- parameters ---

    def load_parameters(self) -> None:
        for parameter_id, raw in self.document.get("parameters", {}).items():
            at = ("parameters", parameter_id)
            kind = self.word(
                raw["type"],
                _PARAMETER_TYPES,
                f"the 'type' of parameter '{parameter_id}'",
                (*at, "type"),
            )
            if kind is None:
                continue
            values: dict[str, ParameterValue | None] = {}
            for key in ("value", "min", "max"):
                if key in raw:
                    values[key] = self.parameter_value(
                        kind, raw[key], f"the '{key}' of parameter '{parameter_id}'", (*at, key)
                    )
            value = values["value"]
            if value is None or any(item is None for item in values.values()):
                continue
            self.parameters[parameter_id] = Parameter(
                id=parameter_id,
                type=kind,  # type: ignore[arg-type]  # one of _PARAMETER_TYPES
                value=value,
                min=values.get("min"),
                max=values.get("max"),
                description=raw.get("description"),
            )

    def parameter_value(
        self, kind: str, value: object, where: str, at: Sequence[Segment]
    ) -> ParameterValue | None:
        """A value of a parameter of type ``kind``. A ``quantity`` parameter is a time: time
        is the only dimension with Phase 1 units (spec 1 "Quantities")."""
        if kind == "quantity":
            return self.quantity(value, Dimension.TIME, where, at)
        return self.number(value, where, at, integer=kind == "integer")

    # --- components ---

    def component(self, index: int, raw: Mapping[str, Any]) -> Component | None:
        component_id: str = raw["id"]
        type_name: str = raw["type"]
        params: Mapping[str, Any] = raw["params"]
        at = ("components", index)
        block = PROCESS_TYPES.get(type_name)
        if block is None:
            self.issue(
                "E120",
                (*at, "type"),
                f"The 'type' of component '{component_id}' is '{type_name}', which is not a "
                "known component type.",
                f"Use one of: {', '.join(PROCESS_TYPES)}.",
                component_id,
            )
            return None
        complete = True
        for key in params:
            if block.setting(key) is None:
                complete = False
                self.issue(
                    "E121",
                    (*at, "params", key),
                    f"Component '{component_id}' has an unknown setting '{key}'.",
                    f"Remove '{key}' or correct its spelling. {_settings_text(block)}",
                    component_id,
                )
        settings: dict[str, SettingValue] = {}
        for spec in block.settings:
            setting_at = (*at, "params", spec.name)
            if spec.name not in params:
                if spec.required or (
                    spec.required_when is not None
                    and params.get(spec.required_when[0]) == spec.required_when[1]
                ):
                    complete = False
                    self.issue(
                        "E122",
                        setting_at,
                        f"Component '{component_id}' is missing the required setting "
                        f"'{spec.name}'{_condition_text(spec)}.",
                        f"Add '{spec.name}' to the 'params' of '{component_id}'.",
                        component_id,
                    )
                continue
            value = self.setting(
                spec,
                params[spec.name],
                f"the '{spec.name}' setting of '{component_id}'",
                setting_at,
                component_id,
            )
            if value is None:
                complete = False
            else:
                settings[spec.name] = value
        if not complete:
            return None
        ui = raw.get("ui")
        return Component(
            id=component_id,
            type=type_name,
            settings=MappingProxyType(settings),
            label=raw.get("label"),
            ui=MappingProxyType(ui) if ui is not None else None,
        )

    def setting(
        self,
        spec: SettingSpec,
        value: object,
        where: str,
        at: Sequence[Segment],
        component: str,
        *,
        one: bool = False,
    ) -> SettingValue | None:
        """A setting (or a field of an object setting) converted per its spec.

        ``one`` reads a single entry of a ``many`` setting.
        """
        if spec.many and not one:
            if not isinstance(value, list):
                self.wrong_kind(value, "an array", where, at, component)
                return None
            items = [
                self.setting(
                    spec, item, f"item {index + 1} of {where}", (*at, index), component, one=True
                )
                for index, item in enumerate(value)
            ]
            if any(item is None for item in items):
                return None
            return tuple(item for item in items if item is not None)
        kind = spec.kind
        if kind is SettingKind.NUMBER or kind is SettingKind.QUANTITY:
            reference = _param_ref(value)
            if reference is not None:
                return reference
            if kind is SettingKind.NUMBER:
                return self.number(value, where, at, component, integer=spec.integer)
            assert spec.dimension is not None
            return self.quantity(value, spec.dimension, where, at, component)
        if kind is SettingKind.DISTRIBUTION:
            assert spec.dimension is not None
            return self.distribution(value, spec.dimension, where, at, component)
        if kind is SettingKind.IDENTIFIER:
            if spec.choices:
                return self.word(value, spec.choices, where, at, component)
            if not isinstance(value, str):
                self.wrong_kind(value, "a name written as text", where, at, component)
                return None
            return value
        return self.object_setting(spec, value, where, at, component)

    def object_setting(
        self, spec: SettingSpec, value: object, where: str, at: Sequence[Segment], component: str
    ) -> SettingValue | None:
        if not isinstance(value, dict):
            self.wrong_kind(value, "an object", where, at, component)
            return None
        result: dict[str, SettingValue] = {}
        complete = True
        if spec.values is not None:
            # Keyed by the entries of another setting (`weights` by `routes`): whether the
            # keys match those entries is a meaning-pass check.
            for key, item in value.items():
                converted = self.setting(
                    spec.values,
                    item,
                    f"the {spec.values.name} of '{key}' in {where}",
                    (*at, key),
                    component,
                )
                if converted is None:
                    complete = False
                else:
                    result[key] = converted
            return MappingProxyType(result) if complete else None
        known = {field.name for field in spec.fields}
        for key in value:
            if key not in known:
                complete = False
                self.issue(
                    "E121",
                    (*at, key),
                    f"In {where}, the key '{key}' is unknown.",
                    f"Remove '{key}'. The keys allowed here are: {', '.join(known)}.",
                    component,
                )
        for field in spec.fields:
            if field.name not in value:
                if field.required:
                    complete = False
                    self.issue(
                        "E122",
                        (*at, field.name),
                        f"In {where}, the required key '{field.name}' is missing.",
                        f"Add '{field.name}'.",
                        component,
                    )
                continue
            converted = self.setting(
                field,
                value[field.name],
                f"the '{field.name}' of {where}",
                (*at, field.name),
                component,
            )
            if converted is None:
                complete = False
            else:
                result[field.name] = converted
        return MappingProxyType(result) if complete else None

    def wrong_kind(
        self, value: object, expected: str, where: str, at: Sequence[Segment], component: str
    ) -> None:
        self.issue(
            "E123",
            at,
            f"In {where}, {_show(value)} is given, but {expected} is expected.",
            f"Change it to {expected}; spec 2 'Block reference' lists what each setting takes.",
            component,
        )

    # --- distributions ---

    def distribution(
        self,
        value: object,
        dimension: Dimension,
        where: str,
        at: Sequence[Segment],
        component: str,
    ) -> Distribution | None:
        names = _words(list(DISTRIBUTIONS))
        if not isinstance(value, dict):
            self.issue(
                "E160",
                at,
                f"In {where}, {_show(value)} is not a distribution; an object such as "
                '{"dist": "exponential", "mean": "2 min"} is expected.',
                f"Write an object with 'dist' and its fields; 'dist' is {names}.",
                component,
            )
            return None
        if "dist" not in value:
            self.issue(
                "E160",
                (*at, "dist"),
                f"In {where}, the distribution has no 'dist' to say which distribution it is.",
                f"Add 'dist': {names}.",
                component,
            )
            return None
        name = value["dist"]
        spec = DISTRIBUTIONS.get(name) if isinstance(name, str) else None
        if spec is None:
            self.issue(
                "E160",
                (*at, "dist"),
                f"In {where}, 'dist' is {_show(name)}, which is not a known distribution.",
                f"Use {names}.",
                component,
            )
            return None
        allowed = spec.field_names()
        complete = True
        for key in value:
            if key != "dist" and key not in allowed:
                complete = False
                self.issue(
                    "E160",
                    (*at, key),
                    f"In {where}, the '{spec.name}' distribution has an unknown field '{key}'.",
                    f"Remove '{key}'. The fields of '{spec.name}' are {_words(allowed)}.",
                    component,
                )
        present = [form for form in spec.forms if any(field.name in value for field in form)]
        if len(present) > 1:
            first, second = present[0][0].name, present[1][0].name
            self.issue(
                "E160",
                (*at, second),
                f"In {where}, the '{spec.name}' distribution has both '{first}' and "
                f"'{second}'; only one may be given.",
                f"Remove '{first}' or '{second}'.",
                component,
            )
            return None
        form = present[0] if present else spec.forms[0]
        for field in form:
            if field.name not in value:
                complete = False
                needed = (
                    _words([alternative[0].name for alternative in spec.forms])
                    if len(spec.forms) > 1
                    else f"'{field.name}'"
                )
                self.issue(
                    "E160",
                    (*at, field.name),
                    f"In {where}, the '{spec.name}' distribution is missing {needed}.",
                    f"Add {needed}.",
                    component,
                )
        if not complete:
            return None
        return self.distribution_fields(spec.name, form, value, dimension, where, at, component)

    def distribution_fields(
        self,
        name: str,
        form: tuple[FieldSpec, ...],
        value: Mapping[str, Any],
        dimension: Dimension,
        where: str,
        at: Sequence[Segment],
        component: str,
    ) -> Distribution | None:
        fields: dict[str, Scalar] = {}
        values: tuple[Scalar, ...] | None = None
        data: DataRef | None = None
        complete = True
        for field in form:
            raw = value[field.name]
            field_where = f"the '{field.name}' field of {where}"
            field_at = (*at, field.name)
            if field.kind is FieldKind.DATA:
                data = self.data_reference(raw, field_where, field_at, component)
                complete = complete and data is not None
            elif field.many:
                if not isinstance(raw, list):
                    complete = False
                    self.issue(
                        "E160",
                        field_at,
                        f"In {where}, '{field.name}' is {_show(raw)}, but an array is expected.",
                        f'Write \'{field.name}\' as an array, as in ["1 min", "2 min"].',
                        component,
                    )
                    continue
                items = [
                    self.scalar(
                        field.kind,
                        dimension,
                        item,
                        f"value {index + 1} of {field_where}",
                        (*field_at, index),
                        component,
                    )
                    for index, item in enumerate(raw)
                ]
                if any(item is None for item in items):
                    complete = False
                else:
                    values = tuple(item for item in items if item is not None)
            else:
                converted = self.scalar(
                    field.kind, dimension, raw, field_where, field_at, component
                )
                if converted is None:
                    complete = False
                else:
                    fields[field.name] = converted
        if not complete:
            return None
        return Distribution(name, MappingProxyType(fields), values=values, data=data)

    def scalar(
        self,
        kind: FieldKind,
        dimension: Dimension,
        value: object,
        where: str,
        at: Sequence[Segment],
        component: str,
    ) -> Scalar | None:
        """A distribution field: a quantity of the setting's dimension, or a plain number."""
        reference = _param_ref(value)
        if reference is not None:
            return reference
        if kind is FieldKind.NUMBER or dimension is Dimension.DIMENSIONLESS:
            return self.number(value, where, at, component)
        return self.quantity(value, dimension, where, at, component)

    def data_reference(
        self, value: object, where: str, at: Sequence[Segment], component: str
    ) -> DataRef | None:
        if (
            isinstance(value, dict)
            and set(value) == set(DATA_FIELDS)
            and all(isinstance(value[key], str) for key in DATA_FIELDS)
        ):
            return DataRef(file=value["file"], column=value["column"])
        self.issue(
            "E160",
            at,
            f"In {where}, {_show(value)} is not a data reference; an object with 'file' and "
            "'column', both text, is expected.",
            'Write it as {"file": "<file in data/>", "column": "<column>"}.',
            component,
        )
        return None

    # --- connections ---

    def connection(self, index: int, raw: Mapping[str, Any]) -> Connection | None:
        ends: list[Endpoint] = []
        for key in ("from", "to"):
            text: str = raw[key]
            component, dot, port = text.partition(".")
            if not (dot and component and port):
                self.issue(
                    "E130",
                    ("connections", index, key),
                    f"The '{key}' end of connection {index + 1} is {_show(text)}, which does "
                    "not name a component and a port.",
                    "Write the component id, a dot and the port, as in 'till.out'.",
                )
            else:
                ends.append(Endpoint(component, port))
        if len(ends) != 2:
            return None
        return Connection(origin=ends[0], destination=ends[1])

    # --- experiments ---

    def experiment(self, index: int, raw: Mapping[str, Any]) -> Experiment | None:
        experiment_id: str = raw["id"]
        at = ("experiments", index)
        before = len(self.issues)

        def where(key: str) -> str:
            return f"the '{key}' of experiment '{experiment_id}'"

        length = self.quantity(raw["length"], Dimension.TIME, where("length"), (*at, "length"))
        warmup: Quantity | None = Quantity(0.0, Dimension.TIME)
        if "warmup" in raw:
            warmup = self.quantity(raw["warmup"], Dimension.TIME, where("warmup"), (*at, "warmup"))
        replications: int | float | None = _REPLICATIONS
        if "replications" in raw:
            replications = self.number(
                raw["replications"], where("replications"), (*at, "replications"), integer=True
            )
        seed_chosen = "seed" not in raw
        seed: int | float | None
        if seed_chosen:
            seed = self.seed_source()
        else:
            seed = self.number(raw["seed"], where("seed"), (*at, "seed"), integer=True)
        confidence: int | float | None = _CONFIDENCE
        if "confidence" in raw:
            confidence = self.number(raw["confidence"], where("confidence"), (*at, "confidence"))
        record_interval: Quantity | None = None
        if "record_interval" in raw:
            record_interval = self.quantity(
                raw["record_interval"],
                Dimension.TIME,
                where("record_interval"),
                (*at, "record_interval"),
            )
        elif length is not None:
            record_interval = Quantity(length.magnitude / _RECORD_INTERVALS, Dimension.TIME)
        scenarios = self.scenarios(experiment_id, raw.get("scenarios") or [], at)
        search = self.search(experiment_id, raw["search"], at) if "search" in raw else None
        if len(self.issues) != before:
            return None
        assert length is not None and warmup is not None and record_interval is not None
        assert isinstance(replications, int) and isinstance(seed, int)
        assert confidence is not None
        return Experiment(
            id=experiment_id,
            length=length,
            warmup=warmup,
            replications=replications,
            seed=seed,
            seed_chosen=seed_chosen,
            scenarios=scenarios,
            default_scenario_added=not raw.get("scenarios"),
            confidence=confidence,
            record_interval=record_interval,
            search=search,
        )

    def scenarios(
        self, experiment_id: str, raw: list[Mapping[str, Any]], at: tuple[Segment, ...]
    ) -> tuple[Scenario, ...]:
        """The experiment's scenarios; none given (or an empty list) is the one ``default``
        scenario with an empty ``set``."""
        if not raw:
            return (Scenario(id=_DEFAULT_SCENARIO, set=MappingProxyType({})),)
        scenarios: list[Scenario] = []
        for index, entry in enumerate(raw):
            scenario_id: str = entry["id"]
            values: dict[str, ParameterValue] = {}
            for parameter_id, value in entry["set"].items():
                value_at = (*at, "scenarios", index, "set", parameter_id)
                parameter = self.parameters.get(parameter_id)
                if parameter is None:
                    if parameter_id not in self.document.get("parameters", {}):
                        self.issue(
                            "E150",
                            value_at,
                            f"Scenario '{scenario_id}' of experiment '{experiment_id}' sets "
                            f"'{parameter_id}', which is not a parameter.",
                            f"Add a parameter '{parameter_id}' to 'parameters', or correct "
                            "the name.",
                        )
                    # A parameter that failed to load has its own issue already.
                    continue
                converted = self.parameter_value(
                    parameter.type,
                    value,
                    f"the value of '{parameter_id}' in scenario '{scenario_id}' of experiment "
                    f"'{experiment_id}'",
                    value_at,
                )
                if converted is not None:
                    values[parameter_id] = converted
            scenarios.append(Scenario(id=scenario_id, set=MappingProxyType(values)))
        return tuple(scenarios)

    def search(
        self, experiment_id: str, raw: Mapping[str, Any], at: tuple[Segment, ...]
    ) -> Search | None:
        """The search with spec 1 defaults: ``budget`` 50, ``replications`` 10, and
        ``variables`` every parameter with both ``min`` and ``max``, in file order."""
        search_at = (*at, "search")

        def where(key: str) -> str:
            return f"the '{key}' of the search of experiment '{experiment_id}'"

        budget: int | float | None = _SEARCH_BUDGET
        if "budget" in raw:
            budget = self.number(
                raw["budget"], where("budget"), (*search_at, "budget"), integer=True
            )
        replications: int | float | None = _SEARCH_REPLICATIONS
        if "replications" in raw:
            replications = self.number(
                raw["replications"],
                where("replications"),
                (*search_at, "replications"),
                integer=True,
            )
        if "variables" in raw:
            variables = tuple(raw["variables"])
        else:
            variables = tuple(
                parameter.id
                for parameter in self.parameters.values()
                if parameter.min is not None and parameter.max is not None
            )
        if not isinstance(budget, int) or not isinstance(replications, int):
            return None
        return Search(
            objective=raw["objective"],
            budget=budget,
            variables=variables,
            replications=replications,
        )

    # --- objectives and constraints of a process model ---

    def metric_objective(self, index: int, raw: Mapping[str, Any]) -> MetricObjective | None:
        sense = self.word(
            raw["sense"],
            _SENSES,
            f"the 'sense' of objective '{raw['id']}'",
            ("objectives", index, "sense"),
        )
        if sense is None:
            return None
        return MetricObjective(id=raw["id"], metric=raw["metric"], sense=sense)  # type: ignore[arg-type]

    def metric_constraint(self, index: int, raw: Mapping[str, Any]) -> MetricConstraint | None:
        constraint_id: str = raw["id"]
        at = ("constraints", index)
        op = self.word(
            raw["op"], _METRIC_OPS, f"the 'op' of constraint '{constraint_id}'", (*at, "op")
        )
        # A plain number, or a time quantity for a metric measured in time. Whether the kind
        # fits the metric is a meaning-pass check.
        raw_value = raw["value"]
        where = f"the 'value' of constraint '{constraint_id}'"
        value: int | float | Quantity | None
        if isinstance(raw_value, int | float) and not isinstance(raw_value, bool):
            value = self.number(raw_value, where, (*at, "value"))
        else:
            value = self.quantity(raw_value, Dimension.TIME, where, (*at, "value"))
        if op is None or value is None:
            return None
        return MetricConstraint(
            id=constraint_id,
            metric=raw["metric"],
            op=op,  # type: ignore[arg-type]  # one of _METRIC_OPS
            value=value,
        )

    # --- the optimization domain ---

    def program(self) -> LinearProgram | None:
        document = self.document
        before = len(self.issues)
        variables: list[Variable] = []
        for index, raw in enumerate(document["variables"]):
            at = ("variables", index)
            variable_id: str = raw["id"]
            kind = self.word(
                raw["type"],
                _VARIABLE_TYPES,
                f"the 'type' of variable '{variable_id}'",
                (*at, "type"),
            )
            bounds: dict[str, int | float | None] = {}
            for key in ("lower", "upper"):
                bounds[key] = (
                    self.number(raw[key], f"the '{key}' of variable '{variable_id}'", (*at, key))
                    if key in raw
                    else None
                )
            if kind is not None:
                variables.append(
                    Variable(
                        id=variable_id,
                        type=kind,  # type: ignore[arg-type]  # one of _VARIABLE_TYPES
                        lower=bounds["lower"],
                        upper=bounds["upper"],
                    )
                )
        objective_raw = document["objective"]
        sense = self.word(
            objective_raw["sense"], _SENSES, "the 'sense' of the objective", ("objective", "sense")
        )
        objective_linear = self.linear(objective_raw["linear"], "the objective", ("objective",))
        constraints: list[LinearConstraint] = []
        for index, raw in enumerate(document.get("constraints", [])):
            at = ("constraints", index)
            constraint_id: str = raw["id"]
            linear = self.linear(raw["linear"], f"constraint '{constraint_id}'", at)
            op = self.word(
                raw["op"], _LINEAR_OPS, f"the 'op' of constraint '{constraint_id}'", (*at, "op")
            )
            rhs = self.number(
                raw["rhs"], f"the 'rhs' of constraint '{constraint_id}'", (*at, "rhs")
            )
            if linear is not None and op is not None and rhs is not None:
                constraints.append(
                    LinearConstraint(
                        id=constraint_id,
                        linear=linear,
                        op=op,  # type: ignore[arg-type]  # one of _LINEAR_OPS
                        rhs=rhs,
                    )
                )
        if len(self.issues) != before or sense is None or objective_linear is None:
            return None
        return LinearProgram(
            variables=tuple(variables),
            objective=LinearObjective(sense=sense, linear=objective_linear),  # type: ignore[arg-type]
            constraints=tuple(constraints),
        )

    def linear(
        self, raw: Mapping[str, Any], owner: str, at: tuple[Segment, ...]
    ) -> Mapping[str, int | float] | None:
        """Coefficients by variable id. Whether each id is a variable is checked at M5."""
        coefficients: dict[str, int | float] = {}
        complete = True
        for variable_id, value in raw.items():
            number = self.number(
                value,
                f"the coefficient of '{variable_id}' in {owner}",
                (*at, "linear", variable_id),
            )
            if number is None:
                complete = False
            else:
                coefficients[variable_id] = number
        return MappingProxyType(coefficients) if complete else None

    # --- run ---

    def run(self) -> RunSettings:
        raw = self.document.get("run")
        if raw is None:
            return RunSettings(target=_DEFAULT_TARGET, fidelity=_DEFAULT_FIDELITY, engine=None)
        return RunSettings(target=raw["target"], fidelity=raw["fidelity"], engine=raw.get("engine"))


def _present(items: Iterable[_T | None]) -> tuple[_T, ...]:
    """The items that were built; each ``None`` stands for one with an issue."""
    return tuple(item for item in items if item is not None)


def _settings_text(block: BlockType) -> str:
    if not block.settings:
        return f"A {block.name} has no settings."
    return f"The settings of a {block.name} are: {', '.join(s.name for s in block.settings)}."


def _condition_text(spec: SettingSpec) -> str:
    if spec.required or spec.required_when is None:
        return ""
    setting, word = spec.required_when
    return f", which is needed when '{setting}' is '{word}'"
