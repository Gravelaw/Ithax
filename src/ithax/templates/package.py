"""The template package loader (spec 4 "Template package"; AKS-122).

A package is a folder ``templates/<template_id>/`` holding ``template.json``,
``model.json``, ``lesson.md`` and ``expected.json``. ``load_package`` reads and checks
every rule of spec 4 and returns the package, or ``None`` with its issues: E195 (spec 1)
for the package, and the model's own issues with their codes, every ``path`` a JSON
Pointer into the package whose first segment is the file's name
(``/template.json/minutes``, ``/model.json/experiments/0/warmup``). A package with any
issue, error or warning, is not offered.

``package_folders`` lists the candidate folders of a templates folder: every
subfolder whose name does not start with ``.``, in name order.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ithax.engines.adapter import EngineAdapter
from ithax.engines.registry import installed_adapters
from ithax.model.catalogue import MODEL_METRICS, BlockType
from ithax.model.edits import apply_edits
from ithax.model.issues import Issue, pointer
from ithax.model.loading import load_document, load_text
from ithax.model.model import Model
from ithax.model.validation import IDENTIFIER_PATTERN
from ithax.strict_json import read_json, whole_in
from ithax.templates.expected import ExpectedRow, Run, read_rows
from ithax.templates.lesson import Lesson, parse_lesson

__all__ = [
    "AUDIENCES",
    "EXPECTED_FILE",
    "LESSON_FILE",
    "MAX_MINUTES",
    "MODEL_FILE",
    "TEMPLATE_FILE",
    "TEMPLATE_ISSUE",
    "TEMPLATE_KEYS",
    "PackageResult",
    "TemplatePackage",
    "installed_types",
    "load_package",
    "model_metrics",
    "package_folders",
]

TEMPLATE_FILE = "template.json"
MODEL_FILE = "model.json"
LESSON_FILE = "lesson.md"
EXPECTED_FILE = "expected.json"

#: Spec 1: a template package that cannot be used.
TEMPLATE_ISSUE = "E195"

TEMPLATE_KEYS = (
    "id",
    "title",
    "summary",
    "audience",
    "concepts",
    "minutes",
    "experiment",
    "origin",
    "licence",
    "exercise",
)
#: Spec 4 "Template library", the "For" column.
AUDIENCES = ("Students", "Business", "Both")
MAX_MINUTES = 120

#: What ``_Loader.json`` returns for a file it could not read, whose issue is recorded:
#: distinct from a file that holds JSON ``null``.
UNREAD = object()

_BENCHMARK = re.compile(r"benchmarks/([a-z][a-z0-9_]{0,63})(?![a-z0-9_])")


@dataclass(frozen=True)
class TemplatePackage:
    """A package that keeps every rule.

    ``template`` is ``template.json`` as written; ``model`` the model file's document and
    ``exercise_model`` the document after the exercise's edits; ``lesson_text`` the text
    of ``lesson.md`` and ``lesson`` its steps; ``expected`` the rows of ``expected.json``,
    whose document is ``expected_document``.
    """

    id: str
    folder: Path
    template: Mapping[str, Any]
    model: Mapping[str, Any]
    exercise_model: Mapping[str, Any]
    lesson_text: str
    lesson: Lesson
    expected: tuple[ExpectedRow, ...]
    expected_document: Sequence[Any]

    @property
    def experiment(self) -> str | None:
        """The experiment the lesson and the template test run; ``None`` for an
        optimization model."""
        experiment = self.template["experiment"]
        return experiment if isinstance(experiment, str) else None

    def document(self, run: Run) -> Mapping[str, Any]:
        """The model of ``run``: as written, or after the exercise's edits."""
        return self.model if run == "template" else self.exercise_model

    def rows(self, run: Run) -> tuple[ExpectedRow, ...]:
        """The rows of ``expected.json`` judged on ``run``."""
        return tuple(row for row in self.expected if row.run == run)


@dataclass(frozen=True)
class PackageResult:
    """The outcome of loading: the package, or ``None`` with every issue found."""

    package: TemplatePackage | None
    issues: tuple[Issue, ...]


def package_folders(root: Path) -> list[Path]:
    """The candidate packages of the templates folder ``root``: each subfolder whose
    name does not start with ``.``, in name order; none when ``root`` is not a folder."""
    if not root.is_dir():
        return []
    return sorted(
        (path for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")),
        key=lambda path: path.name,
    )


def model_metrics(model: Model, experiment: str | None) -> frozenset[str]:
    """Every metric name a run of ``model`` reports, as ``expected.json`` names it: the
    process metrics of spec 1 "Metric names" (each component's measures and
    ``model.wip.mean``) and ``search.best.<variable>`` when ``experiment`` has a search;
    for an optimization model ``objective`` and ``variables.<id>``."""
    if model.program is not None:
        names = {f"variables.{variable.id}" for variable in model.program.variables}
        return frozenset({"objective", *names})
    types = installed_types(model.domain)
    metrics = {
        f"{component.id}.{measure}"
        for component in model.components
        if component.type in types
        for measure in types[component.type].metrics
    } | {f"model.{measure}" for measure in MODEL_METRICS}
    search = next((item.search for item in model.experiments if item.id == experiment), None)
    if search is not None:
        metrics |= {f"search.best.{name}" for name in search.variables}
    return frozenset(metrics)


def installed_types(
    domain: object, adapters: Mapping[str, EngineAdapter] | None = None
) -> dict[str, BlockType]:
    """The component types the installed adapters offer for ``domain``; where two
    declare one type, the first by name (as the service's model store reads them)."""
    adapters = installed_adapters() if adapters is None else adapters
    types: dict[str, BlockType] = {}
    for name in sorted(adapters):
        capabilities = adapters[name].capabilities()
        if domain in capabilities.domains:
            for type_name, block in capabilities.component_types.items():
                types.setdefault(type_name, block)
    return types


class _Loader:
    def __init__(
        self,
        folder: Path,
        adapters: Mapping[str, EngineAdapter] | None,
        benchmark_cases: Collection[str] | None,
    ) -> None:
        self.folder = folder
        self.adapters = adapters
        self.benchmark_cases = benchmark_cases
        self.issues: list[Issue] = []

    def issue(self, path: str, message: str, hint: str, component: str | None = None) -> None:
        self.issues.append(Issue(TEMPLATE_ISSUE, component, path, message, hint))

    def read(self, name: str) -> bytes | None:
        try:
            return (self.folder / name).read_bytes()
        except OSError:
            self.issue(
                pointer(name),
                f"The template '{self.folder.name}' has no readable {name}.",
                f"Add {name} to the template's folder.",
            )
            return None

    def json(self, name: str) -> object:
        """The file's JSON document, or ``UNREAD`` (its issue recorded) when it is missing
        or cannot be read; a file holding ``null`` is the document ``None``, a shape the
        caller refuses (review of PR #50)."""
        raw = self.read(name)
        if raw is None:
            return UNREAD
        try:
            return read_json(raw)
        except ValueError:
            self.issue(
                pointer(name),
                f"The template's {name} is not JSON that can be read.",
                f"Correct {name}: UTF-8 JSON with no NaN, infinity or repeated key.",
            )
            return UNREAD

    # --- template.json --------------------------------------------------------------

    def template(self, document: object) -> dict[str, Any] | None:
        if not isinstance(document, dict):
            if document is not UNREAD:
                self.issue(
                    pointer(TEMPLATE_FILE),
                    "template.json is not a JSON object.",
                    "Write template.json as one object.",
                )
            return None
        found = len(self.issues)
        for key in document:
            if key not in TEMPLATE_KEYS:
                self.issue(
                    pointer(TEMPLATE_FILE, key),
                    f"template.json has the unknown key '{key}'.",
                    f"Use only {', '.join(TEMPLATE_KEYS)}.",
                )
        for key in TEMPLATE_KEYS:
            if key not in document:
                self.issue(
                    pointer(TEMPLATE_FILE, key),
                    f"template.json has no '{key}'.",
                    f"Add '{key}' (spec 4 \"Template package\").",
                )
        concepts = document.get("concepts")
        exercise = document.get("exercise")
        checks: tuple[tuple[str, bool, str], ...] = (
            (
                "id",
                document.get("id") == self.folder.name,
                f"the folder's name, '{self.folder.name}'",
            ),
            ("title", _text(document.get("title")), "non-empty text"),
            ("summary", _text(document.get("summary")), "non-empty text"),
            ("audience", document.get("audience") in AUDIENCES, f"one of {', '.join(AUDIENCES)}"),
            (
                "concepts",
                isinstance(concepts, list) and bool(concepts) and all(map(_text, concepts)),
                "an array of one or more non-empty texts",
            ),
            (
                "minutes",
                whole_in(document.get("minutes"), 1, MAX_MINUTES) is not None,
                f"a whole number from 1 to {MAX_MINUTES}",
            ),
            (
                "experiment",
                document.get("experiment") is None or _text(document.get("experiment")),
                "an experiment id or null",
            ),
            ("origin", _text(document.get("origin")), "non-empty text"),
            ("licence", _text(document.get("licence")), "an SPDX licence identifier"),
            (
                "exercise",
                isinstance(exercise, dict)
                and set(exercise) == {"edits"}
                and isinstance(exercise["edits"], list)
                and bool(exercise["edits"]),
                "an object {edits} holding one or more model edits",
            ),
        )
        for key, good, kind in checks:
            if key in document and not good:
                self.issue(
                    pointer(TEMPLATE_FILE, key),
                    f"template.json's '{key}' is not {kind}.",
                    f"Set '{key}' to {kind}.",
                )
        return document if len(self.issues) == found else None

    # --- model.json -----------------------------------------------------------------

    def model(self) -> tuple[Model, dict[str, Any]] | None:
        raw = self.read(MODEL_FILE)
        if raw is None:
            return None
        loaded = load_text(raw)
        for issue in loaded.issues:
            self.issues.append(
                Issue(
                    issue.code,
                    issue.component,
                    pointer(MODEL_FILE) + issue.path,
                    issue.message,
                    issue.hint,
                )
            )
        if loaded.model is None or loaded.issues:
            return None
        try:
            document = read_json(raw)
        except ValueError:
            # Loading accepts a lone surrogate the strict reader cannot write back as
            # UTF-8; the package is refused, not the gallery (review of PR #50).
            self.issue(
                pointer(MODEL_FILE),
                f"The template's {MODEL_FILE} is not JSON that can be read.",
                f"Correct {MODEL_FILE}: UTF-8 JSON with no NaN, infinity or repeated key.",
            )
            return None
        assert isinstance(document, dict)  # the model loaded, so it is an object
        return loaded.model, document

    def runnable(self, model: Model, name: object, *, exercise: bool = False) -> None:
        """Whether ``model`` runs as the template says: the one check applied to the
        template's model and, with ``exercise``, to the model after the exercise's edits,
        since the template test and Learn mode run both with the same experiment (review
        of PR #50). An optimization model names no experiment. A simulation's experiment
        ``name`` exists, sets a seed so its results repeat, has a non-zero warm-up (spec 4)
        and lists no scenarios of its own, since the expected values are read from the
        scenario ``default`` (spec 1 "Experiments"). For the template a problem is placed
        at its key in ``model.json``; for the exercise at its edits."""

        def report(where: Sequence[str | int], message: str, hint: str) -> None:
            if exercise:
                self.issue(
                    pointer(TEMPLATE_FILE, "exercise", "edits"),
                    f"After the exercise's edits, {message[0].lower()}{message[1:]}",
                    hint,
                )
            else:
                self.issue(pointer(*where), message, hint)

        if model.program is not None:
            if name is not None and not exercise:
                self.issue(
                    pointer(TEMPLATE_FILE, "experiment"),
                    "An optimization model has no experiments, so 'experiment' is null.",
                    "Set 'experiment' to null.",
                )
            return
        index = next((at for at, item in enumerate(model.experiments) if item.id == name), None)
        if index is None:
            report(
                (TEMPLATE_FILE, "experiment"),
                f"The model has no experiment {name!r} for the template to run.",
                "Name one of the model's experiments in 'experiment', and keep it in the "
                "exercise's model.",
            )
            return
        chosen = model.experiments[index]
        at = (MODEL_FILE, "experiments", index)
        if chosen.seed_chosen:
            report(
                (*at, "seed"),
                f"The template's experiment '{name}' sets no seed, so its results would "
                "not repeat.",
                "Set 'seed' in the experiment.",
            )
        if chosen.warmup.magnitude <= 0:
            report(
                (*at, "warmup"),
                f"The template's experiment '{name}' has no warm-up; every simulation "
                "template sets a non-zero warmup (spec 4).",
                "Set 'warmup' above 0 s, less than 'length'.",
            )
        if not chosen.default_scenario_added:
            report(
                (*at, "scenarios"),
                f"The template's experiment '{name}' lists scenarios; its expected values "
                "are read from the scenario 'default', which only an experiment without "
                "scenarios runs.",
                "Remove 'scenarios' from the experiment.",
            )

    def exercise(self, document: Mapping[str, Any], edits: Sequence[Any]) -> dict[str, Any] | None:
        where = pointer(TEMPLATE_FILE, "exercise", "edits")
        outcome = apply_edits(document, edits, installed_types(document["domain"], self.adapters))
        if outcome.model is None:
            first = outcome.issues[0]
            self.issue(
                where + first.path.removeprefix("/edits"),
                f"The exercise's edits cannot be applied: {first.message}",
                first.hint,
            )
            return None
        errors = load_document(outcome.model).errors
        if errors:
            first = errors[0]
            self.issue(
                where,
                f"The exercise's edits leave a model with an error: {first.code} at "
                f"'{first.path}': {first.message}",
                "Change the edits so that the changed model loads.",
            )
            return None
        return outcome.model

    # --- lesson.md ------------------------------------------------------------------

    def lesson(self, title: object, names: frozenset[str] | None) -> tuple[str, Lesson] | None:
        raw = self.read(LESSON_FILE)
        if raw is None:
            return None
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            self.issue(pointer(LESSON_FILE), "lesson.md is not UTF-8 text.", "Save it as UTF-8.")
            return None
        lesson, problems = parse_lesson(text)
        for problem in problems:
            self.issue(pointer(LESSON_FILE) + problem.path, problem.message, problem.hint)
        if lesson is None:
            return None
        found = len(self.issues)
        if isinstance(title, str) and lesson.title != title:
            self.issue(
                pointer(LESSON_FILE),
                f"The lesson's title '{lesson.title}' is not template.json's '{title}'.",
                "Give the lesson the template's title.",
            )
        if names is not None:
            for index, component in enumerate(lesson.components):
                if component not in names:
                    self.issue(
                        pointer(LESSON_FILE, "steps", index),
                        f"Step {index + 1} highlights '{component}', which the model does "
                        "not have.",
                        "Name a component of the model (for an optimization model, a "
                        "variable, a constraint or 'objective').",
                    )
        return (text, lesson) if len(self.issues) == found else None

    # --- expected.json --------------------------------------------------------------

    def expected(
        self,
        document: object,
        model: Model | None,
        experiment: object,
        exercise: Model | None = None,
    ) -> tuple[ExpectedRow, ...] | None:
        """Read ``expected.json``. A row is judged against the model its run uses: the
        template's for ``template`` rows, the model after the exercise's edits for
        ``exercise`` rows, so a renamed or added component is named as it is there; with
        no exercise model (its edits failed, an issue already recorded) an exercise row's
        metric is not checked (review of PR #50)."""
        if document is UNREAD:
            return None
        rows, problems = read_rows(document)
        for problem in problems:
            self.issue(pointer(EXPECTED_FILE) + problem.path, problem.message, problem.hint)
        if problems:
            return None
        found = len(self.issues)
        name = experiment if isinstance(experiment, str) else None
        metrics = None if model is None else model_metrics(model, name)
        exercise_metrics = None if exercise is None else model_metrics(exercise, name)
        for index, row in enumerate(rows):
            if row.run == "exercise":
                self.row(index, row, model, exercise_metrics)
            else:
                self.row(index, row, model, metrics)
        if not any(row.source != "recorded" and row.run == "template" for row in rows):
            self.issue(
                pointer(EXPECTED_FILE),
                "expected.json has no 'theory' or 'benchmark' row for the template.",
                "Add a row whose value comes from a formula or a benchmarks/<case>.",
            )
        if not any(row.run == "exercise" for row in rows):
            self.issue(
                pointer(EXPECTED_FILE),
                "expected.json has no row for the exercise, to back its right prediction.",
                'Add a row with "run": "exercise".',
            )
        return rows if len(self.issues) == found else None

    def row(
        self, index: int, row: ExpectedRow, model: Model | None, metrics: frozenset[str] | None
    ) -> None:
        if metrics is not None and row.metric not in metrics:
            self.issue(
                pointer(EXPECTED_FILE, index, "metric"),
                f"Row {index} names the metric '{row.metric}', which the model does not report.",
                "Name a metric as summary.json reports it, such as 'till.wait.mean'.",
            )
        single = model is not None and (
            model.program is not None or row.metric.startswith("search.best.")
        )
        if model is not None and (row.method == "sig_figs_4") != single:
            kind = "sig_figs_4" if single else "three_se or exact"
            self.issue(
                pointer(EXPECTED_FILE, index, "method"),
                f"Row {index}'s method '{row.method}' does not fit '{row.metric}', which "
                f"takes {kind}.",
                f"Set 'method' to {kind}.",
            )
        if row.source == "benchmark":
            match = _BENCHMARK.match(row.reference)
            known = self.benchmark_cases
            if match is None or (known is not None and match.group(1) not in known):
                self.issue(
                    pointer(EXPECTED_FILE, index, "reference"),
                    f"Row {index} is a benchmark row, but its reference does not start "
                    "with a benchmarks/<case> that exists.",
                    "Start the reference with 'benchmarks/<case>', a case of benchmarks/.",
                )


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _names(model: Model) -> frozenset[str]:
    """What a lesson step may highlight: a component, or for an optimization model a
    variable, a constraint or ``objective``, by its declared id (``ship``) or, for an
    indexed one, an expanded name (``ship[north,city]``; spec 4, AKS-123)."""
    if model.program is None or model.declared is None:
        return frozenset(component.id for component in model.components)
    program = model.program
    declared = model.declared
    return frozenset(
        {
            "objective",
            *(v.id for v in program.variables),
            *(c.id for c in program.constraints),
            *(v.id for v in declared.variables),
            *(c.id for c in declared.constraints),
        }
    )


def load_package(
    folder: Path,
    *,
    adapters: Mapping[str, EngineAdapter] | None = None,
    benchmark_cases: Collection[str] | None = None,
) -> PackageResult:
    """The package in ``folder``, or ``None`` with its issues.

    ``adapters`` give the component types an exercise's edits may use (default: the
    installed adapters). ``benchmark_cases`` are the ids of ``benchmarks/`` a ``benchmark``
    row may name; ``None`` checks only that its reference starts ``benchmarks/<case>``
    (the service has no benchmarks folder; the template test passes it).
    """
    loader = _Loader(folder, adapters, benchmark_cases)
    if IDENTIFIER_PATTERN.fullmatch(folder.name) is None:
        loader.issue(
            "",
            f"The template folder '{folder.name}' is not an identifier, so it cannot be a "
            "template id.",
            "Name the folder with lower-case letters, digits and '_', starting with a letter.",
        )
        return PackageResult(None, tuple(loader.issues))
    template = loader.template(loader.json(TEMPLATE_FILE))
    loaded = loader.model()
    model, document = loaded if loaded is not None else (None, None)
    exercise_model = None
    exercise = None
    if template is not None and model is not None and document is not None:
        found = len(loader.issues)
        loader.runnable(model, template["experiment"])
        runs = len(loader.issues) == found
        exercise_model = loader.exercise(document, template["exercise"]["edits"])
        if exercise_model is not None and runs:
            # A problem the template's model already has is reported once, there.
            exercise = load_document(exercise_model).model
            assert exercise is not None  # exercise() refused a model with errors
            loader.runnable(exercise, template["experiment"], exercise=True)
    title = None if template is None else template["title"]
    lesson = loader.lesson(title, None if model is None else _names(model))
    experiment = None if template is None else template["experiment"]
    expected_document = loader.json(EXPECTED_FILE)
    rows = loader.expected(expected_document, model, experiment, exercise)
    if loader.issues:
        return PackageResult(None, tuple(loader.issues))
    assert template is not None and document is not None and exercise_model is not None
    assert lesson is not None and rows is not None and isinstance(expected_document, list)
    package = TemplatePackage(
        id=folder.name,
        folder=folder,
        template=template,
        model=document,
        exercise_model=exercise_model,
        lesson_text=lesson[0],
        lesson=lesson[1],
        expected=rows,
        expected_document=expected_document,
    )
    return PackageResult(package, ())
