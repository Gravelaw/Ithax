"""The template package loader (spec 4 "Template package", spec 1 E195; AKS-122).

Each test copies the coffee shop package (or writes a small optimization package) to a
temporary folder, breaks one rule, and checks the issue and its place in the package.
"""

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ithax.model.loading import load_document
from ithax.templates import load_package, package_folders
from ithax.templates.package import model_metrics

ROOT = Path(__file__).resolve().parents[2]
COFFEE_SHOP = ROOT / "templates" / "coffee_shop"
CASES = frozenset({"mm1", "machine_count", "failure", "product_mix"})

Document = dict[str, Any]


def copy(tmp_path: Path, name: str = "coffee_shop") -> Path:
    folder = tmp_path / name
    shutil.copytree(COFFEE_SHOP, folder)
    return folder


def read(folder: Path, name: str) -> Any:
    return json.loads((folder / name).read_text(encoding="utf-8"))


def write(folder: Path, name: str, value: object) -> None:
    (folder / name).write_text(json.dumps(value), encoding="utf-8")


def change(folder: Path, name: str, edit: Callable[[Any], object]) -> None:
    document = read(folder, name)
    edit(document)
    write(folder, name, document)


def issues(folder: Path) -> list[tuple[str, str]]:
    result = load_package(folder, benchmark_cases=CASES)
    assert result.package is None
    for issue in result.issues:
        assert issue.message and issue.hint
    return [(issue.code, issue.path) for issue in result.issues]


def test_the_coffee_shop_package_loads(tmp_path: Path) -> None:
    result = load_package(copy(tmp_path), benchmark_cases=CASES)
    assert result.issues == ()
    package = result.package
    assert package is not None
    assert package.id == "coffee_shop"
    assert package.experiment == "base"
    assert package.template["minutes"] == 15
    assert package.lesson_text.startswith("# Coffee shop queue\n")
    assert package.document("template") is package.model
    assert package.exercise_model["parameters"]["tills"]["value"] == 2
    assert package.model["parameters"]["tills"]["value"] == 1
    assert len(package.rows("template")) + len(package.rows("exercise")) == len(
        package.expected_document
    )


def test_without_the_benchmark_cases_only_the_reference_s_form_is_checked(
    tmp_path: Path,
) -> None:
    folder = copy(tmp_path)
    assert load_package(folder, benchmark_cases=frozenset()).package is None
    assert load_package(folder).package is not None


def test_the_folder_name_is_the_template_id(tmp_path: Path) -> None:
    folder = copy(tmp_path, "Coffee-Shop")
    assert issues(folder) == [("E195", "")]


@pytest.mark.parametrize(
    ("edit", "path"),
    [
        (lambda t: t.update(colour="red"), "/template.json/colour"),
        (lambda t: t.pop("summary"), "/template.json/summary"),
        (lambda t: t.update(id="other"), "/template.json/id"),
        (lambda t: t.update(title=" "), "/template.json/title"),
        (lambda t: t.update(summary=3), "/template.json/summary"),
        (lambda t: t.update(audience="Kids"), "/template.json/audience"),
        (lambda t: t.update(concepts=[]), "/template.json/concepts"),
        (lambda t: t.update(concepts=["a", ""]), "/template.json/concepts"),
        (lambda t: t.update(minutes=0), "/template.json/minutes"),
        (lambda t: t.update(minutes=121), "/template.json/minutes"),
        (lambda t: t.update(minutes=True), "/template.json/minutes"),
        (lambda t: t.update(experiment=5), "/template.json/experiment"),
        (lambda t: t.update(origin=""), "/template.json/origin"),
        (lambda t: t.update(licence=None), "/template.json/licence"),
        (lambda t: t.update(exercise={"edits": []}), "/template.json/exercise"),
        (lambda t: t["exercise"].update(note="x"), "/template.json/exercise"),
        (lambda t: t.update(exercise=[]), "/template.json/exercise"),
        (lambda t: t.update(experiment="other"), "/template.json/experiment"),
    ],
)
def test_each_template_json_rule(
    tmp_path: Path, edit: Callable[[Document], object], path: str
) -> None:
    folder = copy(tmp_path)
    change(folder, "template.json", edit)
    found = issues(folder)
    assert ("E195", path) in found
    if path != "/template.json/title":
        assert found == [("E195", path)]


@pytest.mark.parametrize("document", [[], None])
def test_template_json_must_be_an_object(tmp_path: Path, document: object) -> None:
    folder = copy(tmp_path)
    write(folder, "template.json", document)
    assert issues(folder) == [("E195", "/template.json")]


@pytest.mark.parametrize("document", [None, {}, []])
def test_expected_json_must_be_an_array_of_rows(tmp_path: Path, document: object) -> None:
    """A file holding JSON null is a shape problem, not a missing file (review of PR #50)."""
    folder = copy(tmp_path)
    write(folder, "expected.json", document)
    assert issues(folder) == [("E195", "/expected.json")]


@pytest.mark.parametrize("name", ["template.json", "model.json", "lesson.md", "expected.json"])
def test_each_file_must_exist(tmp_path: Path, name: str) -> None:
    folder = copy(tmp_path)
    (folder / name).unlink()
    assert issues(folder) == [("E195", f"/{name}")]


@pytest.mark.parametrize("name", ["template.json", "expected.json"])
def test_a_json_file_must_be_readable(tmp_path: Path, name: str) -> None:
    folder = copy(tmp_path)
    (folder / name).write_text('{"a": NaN}', encoding="utf-8")
    assert issues(folder) == [("E195", f"/{name}")]


def test_a_model_the_strict_reader_refuses_is_a_package_issue(tmp_path: Path) -> None:
    """A lone surrogate loads as a model but cannot be written back as UTF-8, so the
    strict reader refuses it; that is an E195 issue, not an exception (review of PR #50)."""
    folder = copy(tmp_path)
    change(folder, "model.json", lambda model: model["meta"].update(description="\ud800"))
    assert '"\\ud800"' in (folder / "model.json").read_text(encoding="utf-8")
    assert issues(folder) == [("E195", "/model.json")]


def _rename_the_till_in_the_exercise(folder: Path, exercise_prefix: str) -> None:
    change(
        folder,
        "template.json",
        lambda template: template["exercise"]["edits"].append(
            {"edit": "rename_component", "id": "till", "new_id": "counter"}
        ),
    )

    def rename(rows: list[Document]) -> None:
        for row in rows:
            if row.get("run") == "exercise":
                row["metric"] = row["metric"].replace("till.", exercise_prefix, 1)

    change(folder, "expected.json", rename)


def test_exercise_rows_are_checked_against_the_exercise_s_model(tmp_path: Path) -> None:
    """An exercise that renames a component reports its metrics under the new name; its
    rows are judged against the edited model, the template's against the original
    (review of PR #50)."""
    folder = copy(tmp_path)
    _rename_the_till_in_the_exercise(folder, "counter.")
    result = load_package(folder, benchmark_cases=CASES)
    assert result.issues == ()
    assert result.package is not None


def test_an_exercise_row_naming_a_component_the_edits_removed_is_refused(
    tmp_path: Path,
) -> None:
    folder = copy(tmp_path)
    _rename_the_till_in_the_exercise(folder, "till.")
    codes = issues(folder)
    assert codes and all(code == "E195" for code, _ in codes)
    assert all(path.startswith("/expected.json/") and path.endswith("/metric") for _, path in codes)


def test_the_model_s_own_issues_keep_their_codes_under_model_json(tmp_path: Path) -> None:
    folder = copy(tmp_path)
    change(folder, "model.json", lambda m: m["connections"].pop())
    assert issues(folder) == [
        ("E131", "/model.json/components/1"),
        ("W200", "/model.json/components/2"),
    ]


def test_a_model_warning_also_stops_the_package(tmp_path: Path) -> None:
    folder = copy(tmp_path)
    change(
        folder,
        "model.json",
        lambda m: m["components"][1]["params"]["service"].update(mean="3 min"),
    )
    assert issues(folder) == [("W201", "/model.json/components/1")]


def test_the_experiment_sets_a_seed(tmp_path: Path) -> None:
    folder = copy(tmp_path)
    change(folder, "model.json", lambda m: m["experiments"][0].pop("seed"))
    assert issues(folder) == [("E195", "/model.json/experiments/0/seed")]


def test_a_simulation_template_sets_a_non_zero_warmup(tmp_path: Path) -> None:
    folder = copy(tmp_path)
    change(folder, "model.json", lambda m: m["experiments"][0].update(warmup="0 s"))
    assert issues(folder) == [("E195", "/model.json/experiments/0/warmup")]


def test_the_template_s_experiment_runs_only_the_default_scenario(tmp_path: Path) -> None:
    """Expected values are read from the scenario ``default``, so an experiment that lists
    its own scenarios cannot be judged (review of PR #50)."""
    folder = copy(tmp_path)
    change(
        folder,
        "model.json",
        lambda m: m["experiments"][0].update(scenarios=[{"id": "baseline", "set": {}}]),
    )
    assert issues(folder) == [("E195", "/model.json/experiments/0/scenarios")]


def _add_to_the_exercise(folder: Path, *edits: Document) -> None:
    change(folder, "template.json", lambda t: t["exercise"]["edits"].extend(edits))


def test_the_exercise_keeps_the_template_s_experiment(tmp_path: Path) -> None:
    """The exercise runs the same experiment, so its edits may not remove it
    (review of PR #50)."""
    folder = copy(tmp_path)
    _add_to_the_exercise(
        folder,
        {
            "edit": "set_experiment",
            "id": "other",
            "length": "200 h",
            "warmup": "10 h",
            "replications": 30,
            "seed": 1,
        },
        {"edit": "remove_experiment", "id": "base"},
    )
    assert issues(folder) == [("E195", "/template.json/exercise/edits")]


_BASE_WITHOUT_SEED = {
    "edit": "set_experiment",
    "id": "base",
    "length": "200 h",
    "warmup": "10 h",
    "replications": 30,
}


@pytest.mark.parametrize(
    ("edits", "what"),
    [
        ([{"edit": "set_scenario", "experiment_id": "base", "id": "b", "set": {}}], "scenarios"),
        ([{"edit": "set_experiment", "id": "base", "warmup": "0 s"}], "warm-up"),
        ([{"edit": "remove_experiment", "id": "base"}, _BASE_WITHOUT_SEED], "seed"),
    ],
)
def test_the_exercise_s_experiment_is_checked_as_the_template_s_is(
    tmp_path: Path, edits: list[Document], what: str
) -> None:
    """The model after the exercise's edits passes the same experiment checks as the
    template's (review of PR #50)."""
    folder = copy(tmp_path)
    _add_to_the_exercise(folder, *edits)
    result = load_package(folder, benchmark_cases=CASES)
    assert result.package is None
    assert [(i.code, i.path) for i in result.issues][:1] == [
        ("E195", "/template.json/exercise/edits")
    ], result.issues
    assert what in result.issues[0].message


def test_the_exercise_s_edits_must_apply(tmp_path: Path) -> None:
    folder = copy(tmp_path)
    change(
        folder,
        "template.json",
        lambda t: t["exercise"].update(edits=[{"edit": "remove_parameter", "id": "nothing"}]),
    )
    assert issues(folder) == [("E195", "/template.json/exercise/edits/0")]


def test_the_exercise_s_model_must_load(tmp_path: Path) -> None:
    folder = copy(tmp_path)
    edit = {"edit": "set_setting", "id": "till", "path": "/capacity", "value": 0}
    change(folder, "template.json", lambda t: t["exercise"].update(edits=[edit]))
    assert issues(folder) == [("E195", "/template.json/exercise/edits")]


def test_the_lesson_s_problems_are_under_lesson_md(tmp_path: Path) -> None:
    folder = copy(tmp_path)
    text = (folder / "lesson.md").read_text(encoding="utf-8")
    (folder / "lesson.md").write_text(text.replace("- [x]", "- [ ]"), encoding="utf-8")
    assert issues(folder) == [("E195", "/lesson.md/steps/3/prediction")]


def test_the_lesson_is_utf_8(tmp_path: Path) -> None:
    folder = copy(tmp_path)
    (folder / "lesson.md").write_bytes(b"# Caf\xe9\n")
    assert issues(folder) == [("E195", "/lesson.md")]


def test_the_lesson_s_title_is_the_template_s(tmp_path: Path) -> None:
    folder = copy(tmp_path)
    change(folder, "template.json", lambda t: t.update(title="Coffee"))
    assert issues(folder) == [("E195", "/lesson.md")]


def test_each_step_names_a_component_of_the_model(tmp_path: Path) -> None:
    folder = copy(tmp_path)
    text = (folder / "lesson.md").read_text(encoding="utf-8")
    (folder / "lesson.md").write_text(text.replace("`exit`", "`door`"), encoding="utf-8")
    assert issues(folder) == [("E195", "/lesson.md/steps/2")]


@pytest.mark.parametrize(
    ("edit", "path"),
    [
        (lambda rows: rows[0].update(value="270 s"), "/expected.json/0/value"),
        (lambda rows: rows[0].update(metric="till.wait"), "/expected.json/0/metric"),
        (lambda rows: rows[0].update(method="sig_figs_4"), "/expected.json/0/method"),
        (lambda rows: rows[4].update(reference="mm1"), "/expected.json/4/reference"),
        (lambda rows: rows[4].update(reference="benchmarks/mm9"), "/expected.json/4/reference"),
        (
            lambda rows: [row.update(source="recorded") for row in rows[:7]],
            "/expected.json",
        ),
        (lambda rows: rows.__delitem__(slice(7, None)), "/expected.json"),
    ],
)
def test_each_expected_json_rule(
    tmp_path: Path, edit: Callable[[list[Document]], object], path: str
) -> None:
    folder = copy(tmp_path)
    rows = read(folder, "expected.json")
    edit(rows)
    write(folder, "expected.json", rows)
    assert issues(folder) == [("E195", path)]


def test_rows_are_checked_against_the_model_only_when_it_loads(tmp_path: Path) -> None:
    folder = copy(tmp_path)
    change(folder, "model.json", lambda m: m["connections"].pop())
    change(folder, "expected.json", lambda rows: rows[0].update(metric="nothing.here"))
    assert issues(folder) == [
        ("E131", "/model.json/components/1"),
        ("W200", "/model.json/components/2"),
    ]


PRODUCT_MIX: Document = {
    "format_version": "0.1",
    "meta": {"name": "Product mix"},
    "domain": "optimization",
    "variables": [
        {"id": "chairs", "type": "continuous", "lower": 0},
        {"id": "tables", "type": "continuous", "lower": 0},
    ],
    "objective": {"sense": "maximize", "linear": {"chairs": 45, "tables": 80}},
    "constraints": [
        {"id": "wood", "linear": {"chairs": 5, "tables": 20}, "op": "<=", "rhs": 400},
        {"id": "labour", "linear": {"chairs": 10, "tables": 15}, "op": "<=", "rhs": 450},
    ],
}

PRODUCT_MIX_LESSON = """# Product mix

## Profit

Component: `objective`

Chairs earn 45 and tables 80.

## Wood

Component: `wood`

Wood is limited to 400.

## Exercise: more labour

Component: `labour`

### Change

Raise the labour available.

### Prediction

- [x] Profit rises.
- [ ] Profit falls.

### Explanation

Labour is a tight constraint.
"""


def optimization_package(tmp_path: Path, experiment: object = None) -> Path:
    folder = tmp_path / "product_mix"
    folder.mkdir()
    write(folder, "model.json", PRODUCT_MIX)
    write(
        folder,
        "template.json",
        {
            "id": "product_mix",
            "title": "Product mix",
            "summary": "Choose the mix.",
            "audience": "Students",
            "concepts": ["linear programming"],
            "minutes": 10,
            "experiment": experiment,
            "origin": "Spec 2's product mix.",
            "licence": "AGPL-3.0-only",
            "exercise": {
                "edits": [{"edit": "set_path", "path": "/constraints/1/rhs", "value": 500}]
            },
        },
    )
    (folder / "lesson.md").write_text(PRODUCT_MIX_LESSON, encoding="utf-8")
    write(
        folder,
        "expected.json",
        [
            {
                "metric": "objective",
                "value": 2200,
                "method": "sig_figs_4",
                "source": "benchmark",
                "reference": "benchmarks/product_mix",
            },
            {
                "metric": "variables.chairs",
                "value": 24,
                "method": "three_se",
                "source": "theory",
                "reference": "Vertex enumeration",
            },
            {
                "metric": "objective",
                "value": 2400,
                "method": "sig_figs_4",
                "source": "theory",
                "reference": "Vertex enumeration",
                "run": "exercise",
            },
        ],
    )
    return folder


def test_an_optimization_package_names_variables_constraints_and_the_objective(
    tmp_path: Path,
) -> None:
    folder = optimization_package(tmp_path)
    # Its one problem: a variable is a single value, judged by sig_figs_4.
    assert issues(folder) == [("E195", "/expected.json/1/method")]
    change(folder, "expected.json", lambda rows: rows[1].update(method="sig_figs_4"))
    result = load_package(folder)
    assert result.issues == ()
    assert result.package is not None
    assert result.package.experiment is None
    assert result.package.lesson.components == ("objective", "wood", "labour")


def test_an_optimization_package_names_no_experiment(tmp_path: Path) -> None:
    folder = optimization_package(tmp_path, "base")
    change(folder, "expected.json", lambda rows: rows[1].update(method="sig_figs_4"))
    assert issues(folder) == [("E195", "/template.json/experiment")]


def test_the_metrics_a_model_reports() -> None:
    coffee = load_document(json.loads((COFFEE_SHOP / "model.json").read_text("utf-8"))).model
    assert coffee is not None
    metrics = model_metrics(coffee, "base")
    assert {"till.wait.mean", "exit.throughput", "model.wip.mean"} <= metrics
    assert not any(name.startswith("search.") for name in metrics)
    search = json.loads((ROOT / "benchmarks" / "machine_count" / "model.json").read_text("utf-8"))
    model = load_document(search).model
    assert model is not None
    assert "search.best.tills" in model_metrics(model, "base")
    mix = load_document(PRODUCT_MIX).model
    assert mix is not None
    assert model_metrics(mix, None) == {"objective", "variables.chairs", "variables.tables"}


def test_the_package_folders_are_the_subfolders_not_starting_with_a_dot(tmp_path: Path) -> None:
    assert package_folders(tmp_path / "missing") == []
    for name in ("b", "a", ".hidden"):
        (tmp_path / name).mkdir()
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    assert [folder.name for folder in package_folders(tmp_path)] == ["a", "b"]
