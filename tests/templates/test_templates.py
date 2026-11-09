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
import math
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from scipy.stats import poisson

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

#: The templates of AKS-122 and AKS-139; later tickets add folders.
AKS_122 = {"coffee_shop", "three_machine_line", "machine_breakdowns"}
AKS_139 = {"clinic_patient_flow", "warehouse_pick_pack", "inventory_reorder_point"}


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


def test_the_aks_122_and_aks_139_templates_exist() -> None:
    assert set(IDS) >= AKS_122 | AKS_139


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
    ("tid", "measured", "said"),
    [
        ("coffee_shop", "190 h", "remaining 190 hours"),
        ("three_machine_line", "80 h", "remaining 80 hours"),
        ("machine_breakdowns", "190 h", "remaining 190 hours"),
        ("clinic_patient_flow", "190 h", "remaining 190 hours"),
        ("warehouse_pick_pack", "192 h", "remaining 192 hours"),
        ("inventory_reorder_point", "950 d", "remaining 950 days"),
    ],
)
def test_the_template_states_the_time_measured_as_length_minus_warmup(
    tid: str, measured: str, said: str
) -> None:
    """``length`` includes the warm-up (spec 1 "Experiments"), and the model's description
    and the lesson's first step say how long is measured."""
    package = load(tid)
    loaded = load_document(package.model)
    assert loaded.model is not None
    experiment = next(item for item in loaded.model.experiments if item.id == package.experiment)
    number, unit = measured.split()
    seconds = float(number) * {"h": 3_600.0, "d": 86_400.0}[unit]
    assert experiment.length.magnitude - experiment.warmup.magnitude == pytest.approx(seconds)
    assert f"so {measured} are measured" in package.model["meta"]["description"]
    assert said in package.lesson.steps[0].text


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


def types_of(package: TemplatePackage) -> dict[str, str]:
    return {item["id"]: item["type"] for item in package.model["components"]}


def expected_value(package: TemplatePackage, metric: str, run: Run = "template") -> float:
    return next(row.value for row in package.rows(run) if row.metric == metric)


@pytest.mark.parametrize(
    ("tid", "blocks"),
    [
        ("clinic_patient_flow", {"source", "branch", "resource_pool", "server", "sink"}),
        (
            "warehouse_pick_pack",
            {"source", "batch", "unbatch", "delay", "schedule", "server", "sink"},
        ),
        ("inventory_reorder_point", {"source", "store", "sink"}),
    ],
)
def test_the_template_exercises_the_blocks_spec_4_lists(tid: str, blocks: set[str]) -> None:
    """Spec 4 "Template library", the "Blocks exercised" column (AKS-139)."""
    assert set(types_of(load(tid)).values()) == blocks


def erlang_c_wait(arrival_rate: float, mean_service: float, servers: int) -> float:
    """Mean wait in the M/M/c queue, E(W) = Pi_W / (c mu - lambda), with Erlang C
    Pi_W = (a^c / c!) / (1 - rho) over (sum_{k<c} a^k / k! + (a^c / c!) / (1 - rho)),
    a = lambda E(S), rho = a / c (Adan and Resing, Queueing Systems (2015), (5.1), (5.3))."""
    offered = arrival_rate * mean_service
    rho = offered / servers
    top = offered**servers / math.factorial(servers) / (1 - rho)
    below = sum(offered**k / math.factorial(k) for k in range(servers))
    return top / (below + top) / (servers / mean_service - arrival_rate)


def test_erlang_c_reproduces_the_m_m_2_benchmark() -> None:
    """The test's own formula against spec 2's M/M/2 answer, 810/7 s."""
    assert erlang_c_wait(1 / 60, 90.0, 2) == pytest.approx(810 / 7)


@pytest.mark.parametrize(("run", "nurses"), [("template", 2), ("exercise", 3)])
def test_the_clinic_is_an_m_m_c_queue_on_its_nurses(run: Run, nurses: int) -> None:
    """Every visit needs a room and a nurse; each kind of room has at least as many places
    as there are nurses and both visits take the same exponential time, so the nurses
    are never idle while a patient waits and the clinic as a whole is M/M/c with c the
    number of nurses (spec 2 "Pool"): the cycle time and the work in progress of the
    expected values are Erlang C's."""
    package = load("clinic_patient_flow")
    document = package.document(run)
    components = {item["id"]: item for item in document["components"]}
    assert components["nurses"]["params"]["capacity"] == nurses
    rooms = [item for item in components.values() if item["type"] == "server"]
    assert {room["params"]["pool"] for room in rooms} == {"nurses"}
    assert all(room["params"]["capacity"] >= nurses for room in rooms)
    assert {json.dumps(room["params"]["service"]) for room in rooms} == {
        json.dumps({"dist": "exponential", "mean": "8 min"})
    }
    arrival_rate, mean_service = 1 / 300, 480.0
    cycle = erlang_c_wait(arrival_rate, mean_service, nurses) + mean_service
    assert expected_value(package, "home.cycle_time.mean", run) == pytest.approx(cycle)
    assert expected_value(package, "model.wip.mean", run) == pytest.approx(arrival_rate * cycle)
    assert expected_value(package, "nurses.utilization", run) == pytest.approx(
        arrival_rate * mean_service / nurses
    )


def test_the_warehouse_measures_whole_days() -> None:
    """A schedule repeats every day, so the warm-up and the measured period are whole days
    and the samples fall on whole hours: the two halves of the warm-up check (spec 2
    "Statistic definitions", W210) then cover alike parts of the day."""
    package = load("warehouse_pick_pack")
    experiment = package.model["experiments"][0]
    assert (experiment["length"], experiment["warmup"]) == ("216 h", "24 h")
    assert experiment["record_interval"] == "1 h"
    # 192 h measured: 8 days, so each half of the warm-up check is 4 whole days.
    assert (216 - 24) % (2 * 24) == 0
    schedule = next(item for item in package.model["components"] if item["id"] == "shifts")
    assert "period" not in schedule["params"]  # the default, 24 h
    hours = {
        (shift["start"], shift["end"]): shift["capacity"] for shift in schedule["params"]["shifts"]
    }
    assert hours == {("0 h", "6 h"): 1, ("6 h", "22 h"): 3, ("22 h", "24 h"): 1}
    assert expected_value(package, "pickers.scheduled_fraction") == pytest.approx(
        (8 * 1 + 16 * 3) / (24 * 3)
    )
    assert expected_value(package, "pickers.scheduled_fraction", "exercise") == pytest.approx(
        (8 * 2 + 16 * 3) / (24 * 3)
    )


def reorder_point_answers(
    demand: float, lead_time: float, reorder_point: int, quantity: int, period: float
) -> dict[str, float]:
    """The (R, Q) policy with Poisson unit demand and a constant lead time L: the stock
    position is uniform on R + 1, ..., R + Q and the net stock L later is the position
    minus the demand D ~ Poisson(lambda L) meanwhile (Zipkin, Foundations of Inventory
    Management (2000), section 6.2; Axsater, Inventory Control (2015), section 5.3)."""
    mean = demand * lead_time
    positions = range(reorder_point + 1, reorder_point + quantity + 1)
    out = sum(float(poisson.sf(y - 1, mean)) for y in positions) / quantity
    on_hand = (
        sum(sum((y - d) * float(poisson.pmf(d, mean)) for d in range(y)) for y in positions)
        / quantity
    )
    waiting = on_hand - (reorder_point + (quantity + 1) / 2 - mean)
    return {
        "stock.stock.mean": on_hand,
        "stock.stockouts": demand * period * out,
        "stock.orders": demand / quantity,
        "model.wip.mean": waiting,
        "sold.cycle_time.mean": waiting / demand,
    }


@pytest.mark.parametrize(("run", "reorder_point"), [("template", 20), ("exercise", 30)])
def test_the_inventory_values_are_the_reorder_point_formulas(run: Run, reorder_point: int) -> None:
    """The store reviews after each withdrawal and does not count waiting items in its
    position (spec 2 "Store"); with an order of 50 against a lead-time demand of mean 20,
    one order at most is outstanding, and the store is then the textbook (R, Q) policy."""
    package = load("inventory_reorder_point")
    assert types_of(package)["stock"] == "store"
    params = next(item for item in package.document(run)["components"] if item["id"] == "stock")[
        "params"
    ]
    assert params["reorder_point"] == reorder_point
    assert params["order_quantity"] == 50
    # A second order is outstanding only if 50 customers come within one 5-day lead time.
    assert float(poisson.sf(49, 20.0)) < 2e-8  # 1.25e-8
    day = 86_400.0
    answers = reorder_point_answers(4 / day, 5 * day, reorder_point, 50, 950 * day)
    theory = [row for row in package.rows(run) if row.source == "theory"]
    assert theory
    for row in theory:
        if row.metric in answers:
            assert row.value == pytest.approx(answers[row.metric], rel=1e-9), row.metric
