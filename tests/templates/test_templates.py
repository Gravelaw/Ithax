"""Every template reproduces its expected values (spec 4 "Template package" and acceptance
table, M10; AKS-122).

The test marked ``template`` loads each folder under ``templates/`` with the package loader
(no issue), runs its model and then the exercise's model through the experiment manager
(the experiment ``template.json`` names, with the file's seed, replications, length and
warm-up), and judges every ``expected.json`` row of that run by its pass rule. The other
tests check the rules spec 4 names directly, so a failure says which one broke: a
``theory`` or ``benchmark`` row, a non-zero warm-up, lesson steps naming real components
within 80 words, and the exercise's three parts with one right prediction.
"""

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from lcsim.engines.registry import select_adapter
from lcsim.model.loading import load_document
from lcsim.runs.manager import run_experiment
from lcsim.templates import TemplatePackage, judge, load_package, package_folders
from lcsim.templates.expected import RUNS, Run, summary_estimates
from lcsim.templates.lesson import MAX_STEP_WORDS, count_words

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "templates"
EXAMPLES = ROOT / "examples"
BENCHMARK_CASES = frozenset(path.parent.name for path in (ROOT / "benchmarks").glob("*/model.json"))
IDS = [folder.name for folder in package_folders(TEMPLATES)]
# Results do not depend on the number of workers (spec 1 "Random streams").
WORKERS = min(4, os.cpu_count() or 1)

#: The templates of AKS-122; later tickets add folders.
AKS_122 = {"coffee_shop", "three_machine_line", "machine_breakdowns"}


def load(tid: str) -> TemplatePackage:
    result = load_package(TEMPLATES / tid, benchmark_cases=BENCHMARK_CASES)
    assert result.issues == (), [issue.as_dict() for issue in result.issues]
    assert result.package is not None
    return result.package


def run_summary(document: Mapping[str, Any], experiment: str | None, workdir: Path) -> Any:
    loaded = load_document(document)
    assert loaded.errors == ()
    assert loaded.model is not None
    selection = select_adapter(loaded.model.domain, loaded.model.run.engine)
    assert selection.adapter is not None
    outcome = run_experiment(selection.adapter, loaded.model, experiment, workdir, workers=WORKERS)
    assert outcome.state == "done"
    return outcome.summary


def test_the_aks_122_templates_exist() -> None:
    assert set(IDS) >= AKS_122


@pytest.mark.template
@pytest.mark.parametrize("run", RUNS)
@pytest.mark.parametrize("tid", IDS)
def test_the_template_reproduces_its_expected_values(tid: str, run: Run, tmp_path: Path) -> None:
    package = load(tid)
    rows = package.rows(run)
    assert rows, f"{tid} has no expected.json row for its {run}"
    summary = run_summary(package.document(run), package.experiment, tmp_path)
    estimates = summary_estimates(summary)
    judged = [judge(row, estimates) for row in rows]
    assert all(item.passed for item in judged), "\n".join(item.message() for item in judged)


@pytest.mark.parametrize("tid", IDS)
def test_the_template_has_a_theory_or_benchmark_row(tid: str) -> None:
    package = load(tid)
    sources = {row.source for row in package.rows("template")}
    assert sources & {"theory", "benchmark"}


@pytest.mark.parametrize("tid", IDS)
def test_a_simulation_template_sets_a_non_zero_warmup(tid: str) -> None:
    package = load(tid)
    if package.model["domain"] != "process":
        assert package.experiment is None
        return
    loaded = load_document(package.model)
    assert loaded.model is not None
    experiment = next(item for item in loaded.model.experiments if item.id == package.experiment)
    assert experiment.warmup.magnitude > 0
    assert experiment.warmup.magnitude < experiment.length.magnitude


@pytest.mark.parametrize("tid", IDS)
def test_each_lesson_step_names_a_real_component_within_80_words(tid: str) -> None:
    package = load(tid)
    ids = {component["id"] for component in package.model.get("components", [])}
    if package.model["domain"] == "optimization":
        ids = {"objective"} | {item["id"] for item in package.model["variables"]}
        ids |= {item["id"] for item in package.model["constraints"]}
    assert set(package.lesson.components) <= ids
    texts = [step.text for step in package.lesson.steps]
    texts += [package.lesson.exercise.change, package.lesson.exercise.explanation]
    assert all(0 < count_words(text) <= MAX_STEP_WORDS for text in texts)


@pytest.mark.parametrize("tid", IDS)
def test_the_lesson_ends_with_the_exercise(tid: str) -> None:
    package = load(tid)
    exercise = package.lesson.exercise
    assert exercise.heading.startswith("Exercise")
    assert exercise.change and exercise.explanation
    assert 2 <= len(exercise.choices) <= 4
    assert sum(choice.right for choice in exercise.choices) == 1
    assert package.lesson.title == package.template["title"]
    assert package.template["exercise"]["edits"]


@pytest.mark.parametrize("tid", IDS)
def test_the_template_records_the_source_and_licence_of_its_problem(tid: str) -> None:
    """Spec 0 "Risks": the source and licence are recorded per template."""
    package = load(tid)
    assert package.template["origin"].strip()
    assert package.template["licence"] == "AGPL-3.0-only"


def without_description(document: Mapping[str, Any]) -> dict[str, Any]:
    copied = json.loads(json.dumps(document))
    copied["meta"].pop("description", None)
    return dict(copied)


def test_the_coffee_shop_template_is_the_example_with_a_description() -> None:
    """The template's model is spec 1's example, so its length reading is the example's:
    200 h including 10 h of warm-up (M7 item 25)."""
    package = load("coffee_shop")
    example = json.loads((EXAMPLES / "coffee_shop.json").read_text(encoding="utf-8"))
    assert without_description(package.model) == example
    assert package.model["experiments"][0]["length"] == "200 h"
    assert package.model["experiments"][0]["warmup"] == "10 h"


@pytest.mark.parametrize(
    ("tid", "measured"),
    [("coffee_shop", "190 h"), ("three_machine_line", "80 h"), ("machine_breakdowns", "190 h")],
)
def test_the_template_states_the_time_measured_as_length_minus_warmup(
    tid: str, measured: str
) -> None:
    """``length`` includes the warm-up (spec 1 "Experiments"), and the model's description
    and the lesson's first step say how long is measured."""
    package = load(tid)
    hours = measured.split()[0]
    assert f"so {measured} are measured" in package.model["meta"]["description"]
    assert f"remaining {hours} hours" in package.lesson.steps[0].text


def test_the_three_machine_line_extends_the_example_with_a_buffer() -> None:
    """Spec 4: the line exercises a `queue`; the template extends the M1 example."""
    package = load("three_machine_line")
    example = json.loads((EXAMPLES / "three_machine_line.json").read_text(encoding="utf-8"))
    types = {item["id"]: item["type"] for item in package.model["components"]}
    assert {item["id"]: item["type"] for item in example["components"]}.items() <= types.items()
    assert types["buffer"] == "queue"
    assert set(types.values()) == {"source", "server", "queue", "delay", "sink"}


def test_machine_breakdowns_exercises_a_failure() -> None:
    package = load("machine_breakdowns")
    types = {item["type"] for item in package.model["components"]}
    assert types == {"source", "server", "failure", "sink"}
