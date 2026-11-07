"""The simulation-based search (spec 2 "Simulation-based optimization"; spec 1 "Experiments";
AKS-109), and the machine-count test of spec 2's acceptance table.

Most tests run the search in this process through ``run_experiment`` with
``SearchAdapter`` (``dummy_adapters.py``), whose metrics are exact functions of the
candidate and the replication number, so every candidate, stage and verdict can be stated.
The machine-count tests (marker ``benchmark``) run the coffee shop through the SimPy adapter.
"""

import copy
import json
import math
import threading
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest
from dummy_adapters import SEARCH_INPUT, SEARCH_OUTPUT, SearchAdapter, search_metrics

from lcsim.engines.adapter import Progress
from lcsim.engines.process.adapter import ProcessAdapter
from lcsim.model.loading import load_document
from lcsim.model.model import Model
from lcsim.model.streams import optimizer_generator
from lcsim.model.units import Dimension, Quantity
from lcsim.runs import search as search_module
from lcsim.runs.manager import RunOutcome, run_experiment
from lcsim.runs.search import (
    ASK_LIMIT_FACTOR,
    candidate_model,
    combination_count,
    combinations,
    optimizer_record,
    run_search,
    search_method,
    search_of,
    tpe_seed,
)

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"

# The research note's recipe raises no warning (no deprecated `constraints_func`, no NaN
# told as a value); any warning here is a failure.
pytestmark = pytest.mark.filterwarnings("error")


def coffee_shop() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (EXAMPLES / "coffee_shop.json").read_text(encoding="utf-8")
    )
    return document


def searching(
    recipe: str,
    *,
    value: int = 1,
    high: int = 5,
    budget: int = 10,
    op: str = ">=",
    limit: float = 0.2,
    sense: str = "minimize",
    seed: int = 12345,
    **search: Any,
) -> dict[str, Any]:
    """The coffee shop named ``recipe`` (``search_metrics``) with `tills` from 1 to ``high``
    at ``value``, objective ``sense`` `till.wait.mean`, constraint `till.utilization`
    ``op`` ``limit``, and a search of ``budget``."""
    document = coffee_shop()
    document["meta"]["name"] = recipe
    document["parameters"]["tills"].update({"value": value, "max": high})
    document["objectives"] = [{"id": "wait", "metric": "till.wait.mean", "sense": sense}]
    document["constraints"] = [
        {"id": "busy", "metric": "till.utilization", "op": op, "value": limit}
    ]
    document["experiments"][0]["seed"] = seed
    document["experiments"][0]["search"] = {"objective": "wait", "budget": budget, **search}
    return document


def load(document: dict[str, Any]) -> Model:
    result = load_document(document)
    assert result.errors == (), [issue.as_dict() for issue in result.errors]
    assert result.model is not None
    return result.model


def run(document: dict[str, Any], workdir: Path, **options: Any) -> RunOutcome:
    return run_experiment(SearchAdapter(), load(document), "base", workdir, **options)


def search_of_summary(outcome: RunOutcome) -> dict[str, Any]:
    assert outcome.state == "done" and outcome.summary is not None
    found: dict[str, Any] = outcome.summary["search"]
    return found


def tills_of(found: dict[str, Any]) -> list[int]:
    return [candidate["set"]["tills"] for candidate in found["candidates"]]


def confirmed(found: dict[str, Any]) -> list[int]:
    return [c["set"]["tills"] for c in found["candidates"] if c["confirmed"]]


def mean(candidate: dict[str, Any], metric: str = "till.wait.mean") -> Any:
    return candidate["metrics"][metric]["mean"]


# --- which path --------------------------------------------------------------------------


def test_combinations_are_every_integer_value_the_first_variable_slowest() -> None:
    document = searching("bowl", high=2)
    document["parameters"]["staff"] = {"value": 2, "type": "integer", "min": 1, "max": 3}
    model = load(document)
    _, _, search = search_of(model, "base")
    assert search.variables == ("tills", "staff")
    assert combinations(model, search) == [(1, 1), (1, 2), (1, 3), (2, 1), (2, 2), (2, 3)]
    assert search_method(model, search) == "exhaustive"
    small = load(searching("bowl", budget=5))
    _, _, five = search_of(small, "base")
    assert search_method(small, five) == "exhaustive"
    fewer = load(searching("bowl", budget=4))
    _, _, four = search_of(fewer, "base")
    assert search_method(fewer, four) == "optuna"


def test_a_large_integer_range_is_counted_not_enumerated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex review of PR #32: the path is chosen from the number of combinations, the
    product of the ranges, without listing them, so a range of 10⁹ values neither fills
    memory when the run is created nor when the search starts."""
    document = searching("bowl", value=1, high=10**9, budget=3)
    document["parameters"]["staff"] = {"value": 2, "type": "integer", "min": 1, "max": 10**9}
    model = load(document)
    _, _, search = search_of(model, "base")
    assert combination_count(model, search) == 10**18

    def refuse(*arguments: Any) -> Any:
        raise AssertionError("the combinations were listed")

    monkeypatch.setattr("itertools.product", refuse)
    assert search_method(model, search) == "optuna"
    result = run_search(model, "base", tmp_path, evaluator(model))
    assert result is not None and result.method == "optuna"
    assert len(result.candidates) == 3


def test_a_number_or_quantity_variable_has_no_combinations_and_uses_optuna() -> None:
    document = searching("mixed", budget=50)
    document["parameters"]["rate"] = {"value": 1.5, "type": "number", "min": 0.5, "max": 1.5}
    model = load(document)
    _, _, search = search_of(model, "base")
    assert combinations(model, search) is None
    assert combination_count(model, search) is None
    assert search_method(model, search) == "optuna"


def test_the_optimizer_record_names_the_method_and_the_optuna_version() -> None:
    import optuna

    assert optimizer_record("optuna") == {"name": "optuna", "version": optuna.__version__}
    assert optimizer_record("exhaustive") == {"name": "exhaustive", "version": None}


def test_the_tpe_seed_is_the_first_draw_below_2_to_the_32_of_the_optimizer_stream() -> None:
    """Research note recipe step 2: for seed 12345 it is 3441887045."""
    assert tpe_seed(12345) == int(optimizer_generator(12345).integers(0, 2**32))
    assert tpe_seed(12345) == 3441887045
    assert all(0 <= tpe_seed(seed) < 2**32 for seed in (0, 1, 2**63 - 1))


def test_search_of_refuses_an_unknown_experiment_or_one_without_a_search() -> None:
    model = load(coffee_shop())
    with pytest.raises(ValueError, match="no search"):
        search_of(model, "base")
    with pytest.raises(ValueError, match="no experiment 'nope'"):
        search_of(model, "nope")


def test_a_candidate_model_runs_one_default_scenario_with_the_candidate_values() -> None:
    document = searching("mixed")
    document["parameters"]["delay"] = {
        "value": "2 min",
        "type": "quantity",
        "min": "1 min",
        "max": "3 min",
    }
    document["experiments"].append({"id": "other", "length": "1 h"})
    model = load(document)
    values = (3, Quantity(150.0, Dimension.TIME))
    changed = candidate_model(model, "base", values, 7)
    experiment = changed.experiments[0]
    assert experiment.replications == 7 and experiment.search is None
    assert [scenario.id for scenario in experiment.scenarios] == ["default"]
    assert experiment.scenarios[0].set == {"tills": 3, "delay": Quantity(150.0, Dimension.TIME)}
    assert experiment.seed == model.experiments[0].seed
    assert changed.experiments[1] is model.experiments[1]
    assert model.experiments[0].search is not None  # the model itself is unchanged


# --- the exhaustive path -----------------------------------------------------------------


def test_the_exhaustive_path_runs_every_combination_baseline_first(tmp_path: Path) -> None:
    outcome = run(searching("bowl", value=3), tmp_path)
    found = search_of_summary(outcome)
    assert tills_of(found) == [3, 1, 2, 4, 5]
    # Feasible at search: utilization 1/tills >= 0.2, all five. Wait (tills - 4)² plus
    # 0.01 at odd replications: the best three other than the baseline are 4 (0.005), 5
    # (1.005) and 2 (4.005); 1 (9.005) is left out.
    assert confirmed(found) == [3, 2, 4, 5]
    assert found["status"] == "feasible"
    assert found["best"] == {"set": {"tills": 4}}
    assert found["objective"] == {
        "metric": "till.wait.mean",
        "before": pytest.approx(1.005),
        "after": pytest.approx(0.005),
    }
    assert found["separated"] is True
    # Each evaluation is translate, run and collect in its own subfolder of engine/.
    folders = sorted(path.name for path in tmp_path.iterdir())
    assert folders == [
        "confirm-000",
        "confirm-002",
        "confirm-003",
        "confirm-004",
        "search-000",
        "search-001",
        "search-002",
        "search-003",
        "search-004",
    ]
    for folder in folders:
        assert sorted(path.name for path in (tmp_path / folder).iterdir()) == [
            SEARCH_INPUT,
            SEARCH_OUTPUT,
        ]
    search_input = json.loads((tmp_path / "search-001" / SEARCH_INPUT).read_text("utf-8"))
    assert search_input["replications"] == 10 and search_input["values"]["tills"] == 1.0
    confirm_input = json.loads((tmp_path / "confirm-003" / SEARCH_INPUT).read_text("utf-8"))
    assert confirm_input["replications"] == 30 and confirm_input["values"]["tills"] == 4.0


def test_a_candidate_entry_has_its_set_metrics_feasibility_and_whether_confirmed(
    tmp_path: Path,
) -> None:
    found = search_of_summary(run(searching("bowl", value=3), tmp_path))
    assert [list(candidate) for candidate in found["candidates"]] == [
        ["set", "metrics", "feasible", "confirmed"]
    ] * 5
    baseline, one, *_ = found["candidates"]
    # Confirmed candidates carry their confirmed metrics (30 values), others the search
    # stage's (10 values).
    assert baseline["metrics"]["till.wait.mean"]["n"] == 30
    assert one["metrics"]["till.wait.mean"]["n"] == 10
    assert one["metrics"]["till.wait.mean"]["mean"] == pytest.approx(9.005)
    assert one["metrics"]["till.utilization"] == {
        "mean": 1.0,
        "half_width": 0.0,
        "unit": "1",
        "n": 10,
    }
    assert [c["feasible"] for c in found["candidates"]] == [True] * 5


def test_the_summary_is_the_best_confirmation_with_the_search_object(tmp_path: Path) -> None:
    outcome = run(searching("bowl", value=3), tmp_path)
    summary = outcome.summary
    assert summary is not None
    assert list(summary) == [
        "model",
        "experiment",
        "fidelity",
        "fidelity_label",
        "replications",
        "confidence",
        "scenarios",
        "differences",
        "warnings",
        "search",
    ]
    assert summary["replications"] == 30
    assert summary["fidelity_label"] == "Standard: 30 replications of 200 h, 95% confidence"
    assert list(summary["scenarios"]) == ["default"]
    assert summary["scenarios"]["default"]["set"] == {"tills": 4}
    assert summary["scenarios"]["default"]["metrics"]["till.wait.mean"]["n"] == 30
    assert summary["differences"] == []
    assert list(summary["search"]) == ["status", "best", "objective", "separated", "candidates"]
    assert outcome.results is not None
    assert outcome.results.tables["replications"].num_rows == 60


def test_a_constraint_that_fails_at_search_keeps_a_candidate_from_confirmation(
    tmp_path: Path,
) -> None:
    # Utilization 1/tills <= 0.3 holds for tills 4 and 5 only; maximize wait (tills - 4)².
    document = searching("bowl", value=1, op="<=", limit=0.3, sense="maximize")
    found = search_of_summary(run(document, tmp_path))
    assert [c["feasible"] for c in found["candidates"]] == [False, False, False, True, True]
    assert confirmed(found) == [1, 4, 5]
    assert found["best"] == {"set": {"tills": 5}}
    assert found["status"] == "feasible"
    assert found["objective"]["before"] == pytest.approx(9.005)
    assert found["objective"]["after"] == pytest.approx(1.005)


# --- the confirmation stage --------------------------------------------------------------


def test_the_baseline_alone_feasible_on_confirmation_is_the_best(tmp_path: Path) -> None:
    """The owner's case (AKS-109 comment, PR #1 review): the baseline fails the constraint
    at the search stage and passes at confirmation, while every other candidate fails
    confirmation. The baseline is the best and `after` equals `before`."""
    document = searching("late", value=1, high=5, limit=0.5)
    found = search_of_summary(run(document, tmp_path))
    baseline, *others = found["candidates"]
    # At the search stage (10 replications) the baseline's utilization mean is 0 and every
    # other candidate's is 1.
    assert tills_of(found) == [1, 2, 3, 4, 5]
    # Confirmed: the baseline always; then 2, 3 and 4 (best wait first), none feasible, so
    # the next group, 5, which is not feasible either; none remain.
    assert confirmed(found) == [1, 2, 3, 4, 5]
    assert mean(baseline, "till.utilization") == pytest.approx(2 / 3)
    assert baseline["feasible"] is True
    assert all(mean(c, "till.utilization") == pytest.approx(1 / 3) for c in others)
    assert all(c["feasible"] is False for c in others)
    assert found["status"] == "feasible"
    assert found["best"] == {"set": {"tills": 1}}
    assert found["objective"]["after"] == found["objective"]["before"] == 1.0
    assert found["separated"] is False


def test_confirmation_continues_in_threes_until_one_is_feasible(tmp_path: Path) -> None:
    # At the search stage 2 to 6 are feasible and the baseline (1) is not. Confirmed: the
    # baseline (feasible), then 2, 3 and 4 by wait, none feasible, so the next group, 5 and
    # 6, of which 6 is feasible. The best confirmed feasible is the baseline, wait 1.
    document = searching("late rescue", value=1, high=6, limit=0.5)
    found = search_of_summary(run(document, tmp_path))
    assert confirmed(found) == [1, 2, 3, 4, 5, 6]
    assert [c["feasible"] for c in found["candidates"]] == [True, False, False, False, False, True]
    assert found["best"] == {"set": {"tills": 1}}
    # The runner-up is tills 6: wait 1 against 6 at every replication, separated.
    assert found["separated"] is True


def test_the_next_group_is_not_confirmed_once_one_of_a_group_is_feasible(
    tmp_path: Path,
) -> None:
    # tills 1 to 9: at the search stage all but the baseline are feasible; confirmed, only
    # the baseline and tills 6 are. Groups by wait: (2, 3, 4), none feasible, then
    # (5, 6, 7), where 6 is, so the group (8, 9) is never confirmed.
    document = searching("late rescue", value=1, high=9, limit=0.5)
    found = search_of_summary(run(document, tmp_path))
    assert confirmed(found) == [1, 2, 3, 4, 5, 6, 7]
    assert found["best"] == {"set": {"tills": 1}}


def test_no_confirmed_feasible_candidate_is_infeasible_with_the_baseline(
    tmp_path: Path,
) -> None:
    # Utilization 1/tills >= 2 never holds: nothing is feasible at search, so only the
    # baseline is confirmed, and it fails too.
    found = search_of_summary(run(searching("bowl", value=3, limit=2.0), tmp_path))
    assert confirmed(found) == [3]
    assert found["status"] == "infeasible"
    assert found["best"] == {"set": {"tills": 3}}
    assert found["objective"]["after"] == found["objective"]["before"]
    assert found["candidates"][0]["metrics"]["till.wait.mean"]["n"] == 30
    assert found["separated"] is False


def test_equal_means_are_not_separated_and_the_earlier_candidate_wins(tmp_path: Path) -> None:
    # Every candidate's mean wait over 30 replications is 10; tills 1 and 2 differ by
    # -(r mod 3 - 1) per replication, around 0.
    found = search_of_summary(run(searching("flat", value=1, high=2), tmp_path))
    assert confirmed(found) == [1, 2]
    assert found["best"] == {"set": {"tills": 1}}
    assert found["separated"] is False


def test_an_undefined_objective_mean_is_never_feasible(tmp_path: Path) -> None:
    found = search_of_summary(run(searching("nan", value=1, high=3), tmp_path))
    two = found["candidates"][1]
    assert two["set"] == {"tills": 2} and mean(two) is None
    assert two["metrics"]["till.wait.mean"]["n"] == 0
    assert two["feasible"] is False and two["confirmed"] is False
    assert found["best"] == {"set": {"tills": 1}}


def test_confirmation_repeats_the_search_stage_replications_as_spec_2_is_written(
    tmp_path: Path,
) -> None:
    """Spec 2 as written (research note, decision "Overlap of the two stages"; owner to
    decide): confirmation replications are numbered from 0 with the experiment seed, so a
    candidate's first `search.replications` confirmed values are its search-stage values,
    and only the rest are new. The confirmed mean dilutes the search's selection bias but
    does not remove it."""
    document = searching("bowl", value=1, high=2)
    document["meta"]["name"] = "Coffee shop"
    document["experiments"][0].update(
        {"length": "4 h", "warmup": "0 s", "replications": 5, "seed": 99}
    )
    document["experiments"][0]["search"]["replications"] = 3
    model = load(document)
    outcome = run_experiment(ProcessAdapter(), model, "base", tmp_path)
    assert outcome.state == "done"

    def waits(folder: str) -> list[float]:
        table = pq.read_table(tmp_path / folder / "output" / "replications.parquet")
        rows = table.to_pylist()
        return [row["value"] for row in rows if row["metric"] == "till.wait.mean"]

    search_stage, confirmation = waits("search-000"), waits("confirm-000")
    assert len(search_stage) == 3 and len(confirmation) == 5
    assert confirmation[:3] == search_stage


# --- the Optuna path ---------------------------------------------------------------------


def staffed(budget: int, seed: int = 12345) -> dict[str, Any]:
    """`tills` and `staff`, both 1 to 9 (81 combinations), the baseline (1, 1)."""
    document = searching("bowl", value=1, high=9, budget=budget, seed=seed, limit=0.0)
    document["parameters"]["staff"] = {"value": 1, "type": "integer", "min": 1, "max": 9}
    return document


def test_the_optuna_path_proposes_budget_distinct_candidates_baseline_first(
    tmp_path: Path,
) -> None:
    found = search_of_summary(run(staffed(15), tmp_path))
    sets = [(c["set"]["tills"], c["set"]["staff"]) for c in found["candidates"]]
    assert len(sets) == 15 == len(set(sets))
    assert sets[0] == (1, 1)
    assert all(1 <= tills <= 9 and 1 <= staff <= 9 for tills, staff in sets)
    best = found["best"]["set"]
    assert (best["tills"], best["staff"]) in sets
    assert found["status"] == "feasible"


def test_a_seeded_optuna_search_repeats_exactly(tmp_path: Path) -> None:
    first = run(staffed(12), tmp_path / "a")
    again = run(staffed(12), tmp_path / "b")
    assert first.summary == again.summary
    other = run(staffed(12, seed=7), tmp_path / "c")
    assert search_of_summary(other)["candidates"] != search_of_summary(first)["candidates"]


def test_the_machine_count_suggestions_of_the_research_note(tmp_path: Path) -> None:
    """Research note "Integer parameters and repeats": `tills` 1 to 5, budget 3, seed 12345
    asks 4 times (1, 1, 2, 4); the repeated 1 reuses the baseline's results and does not
    count against the budget."""
    calls: list[str] = []
    real = search_module._Searcher.add

    def counted(self: Any, values: Any) -> Any:
        calls.append(str(values))
        return real(self, values)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(search_module._Searcher, "add", counted)
        model = load(searching("bowl", value=1, budget=3))
        result = run_search(model, "base", tmp_path, evaluator(model))
    assert result is not None
    assert [candidate.values for candidate in result.candidates] == [(1,), (2,), (4,)]
    assert result.asks == 4 and result.method == "optuna"
    assert calls == ["(1,)", "(2,)", "(4,)"]


def evaluator(model: Model) -> search_module.Evaluate:
    """An in-process evaluation through ``SearchAdapter``."""
    adapter = SearchAdapter()

    def evaluate(candidate: Model, experiment: str, folder: Path, report: Any) -> Any:
        folder.mkdir()
        adapter.translate(candidate, experiment, folder)
        adapter.run(folder, report, threading.Event(), 1)
        return adapter.collect(folder)

    return evaluate


def test_only_the_baseline_and_best_confirmations_keep_their_tables(tmp_path: Path) -> None:
    """Codex review of PR #32: the search keeps each search-stage evaluation's metrics, not
    its tables, and of the confirmations only the baseline's and the best so far, so the
    driving process's memory does not grow with the budget."""
    model = load(searching("late rescue", value=1, high=9, limit=0.5))
    result = run_search(model, "base", tmp_path, evaluator(model))
    assert result is not None
    assert all(candidate.search.results is None for candidate in result.candidates)
    kept = [
        candidate.index
        for candidate in result.candidates
        if candidate.confirmation is not None and candidate.confirmation.results is not None
    ]
    # Seven confirmed (the baseline and tills 2 to 7); the baseline is also the best.
    assert sum(c.confirmation is not None for c in result.candidates) == 7
    assert kept == [0]
    assert result.best_results.tables["replications"].num_rows == 60
    # A best other than the baseline: bowl from tills 3, best 4; kept: the baseline and 4.
    model = load(searching("bowl", value=3))
    (tmp_path / "bowl").mkdir()
    result = run_search(model, "base", tmp_path / "bowl", evaluator(model))
    assert result is not None
    kept_values = [
        candidate.values
        for candidate in result.candidates
        if candidate.confirmation is not None and candidate.confirmation.results is not None
    ]
    assert kept_values == [(3,), (4,)]
    assert result.separated is True


def test_asking_stops_after_ten_asks_per_candidate_of_the_budget(tmp_path: Path) -> None:
    # A `number` variable with min = max sends the search to Optuna, which can only ever
    # propose two distinct candidates (tills 1 or 2), so it stops at 10 x 3 asks.
    document = searching("mixed", value=1, high=2, budget=3)
    document["parameters"]["rate"] = {"value": 1, "type": "number", "min": 1, "max": 1}
    document["parameters"]["delay"] = {
        "value": "2 min",
        "type": "quantity",
        "min": "2 min",
        "max": "2 min",
    }
    model = load(document)
    result = run_search(model, "base", tmp_path, evaluator(model))
    assert result is not None
    assert result.asks == ASK_LIMIT_FACTOR * 3
    assert [candidate.values[0] for candidate in result.candidates] == [1, 2]
    assert result.candidates[0].values == (1, 1.0, Quantity(120.0, Dimension.TIME))


def test_number_and_quantity_variables_are_suggested_as_floats_in_si(tmp_path: Path) -> None:
    document = searching("mixed", value=2, high=3, budget=8)
    document["parameters"]["rate"] = {"value": 1.5, "type": "number", "min": 0.5, "max": 1.5}
    document["parameters"]["delay"] = {
        "value": "3 min",
        "type": "quantity",
        "min": "1 min",
        "max": "3 min",
    }
    found = search_of_summary(run(document, tmp_path))
    sets = [candidate["set"] for candidate in found["candidates"]]
    assert sets[0] == {"tills": 2, "rate": 1.5, "delay": 180.0}
    assert len(sets) == 8
    for item in sets:
        assert isinstance(item["tills"], int) and 1 <= item["tills"] <= 3
        assert isinstance(item["rate"], float) and 0.5 <= item["rate"] <= 1.5
        assert isinstance(item["delay"], float) and 60.0 <= item["delay"] <= 180.0
    candidate = json.loads((tmp_path / "search-001" / SEARCH_INPUT).read_text("utf-8"))
    assert candidate["values"]["delay"] == sets[1]["delay"]


def test_an_undefined_objective_is_told_to_optuna_as_a_failed_trial(tmp_path: Path) -> None:
    # tills 1 to 9 with budget 4 takes the Optuna path; tills 2 has no defined wait.
    document = searching("nan", value=2, high=9, budget=4)
    found = search_of_summary(run(document, tmp_path))
    assert found["candidates"][0]["set"] == {"tills": 2}
    assert found["candidates"][0]["feasible"] is False
    assert found["best"]["set"]["tills"] != 2


def test_a_constraint_on_an_undefined_mean_does_not_hold(tmp_path: Path) -> None:
    # tills 2 has no defined wait; a constraint on the wait is told to Optuna as violated
    # without limit, and the candidate is infeasible.
    document = searching("nan", value=2, high=9, budget=4)
    document["constraints"].append(
        {"id": "short", "metric": "till.wait.mean", "op": "<=", "value": "100 s"}
    )
    found = search_of_summary(run(document, tmp_path))
    assert found["candidates"][0]["set"] == {"tills": 2}
    assert found["candidates"][0]["feasible"] is False
    assert all(c["feasible"] for c in found["candidates"][1:])


# --- progress and cancel -----------------------------------------------------------------


def test_progress_rises_below_1_across_the_whole_search(tmp_path: Path) -> None:
    reports: list[Progress] = []
    run(searching("bowl", value=3), tmp_path, on_progress=reports.append)
    fractions = [report.fraction for report in reports]
    assert fractions == sorted(fractions)
    assert 0 < fractions[0] and fractions[-1] < 1
    assert reports[0].message == "Search, candidate 1: Replication 1"
    # Confirmed in rank order after the baseline: tills 4, 5, then 2 (candidate 3).
    assert reports[-1].message == "Confirmation, candidate 3: Replication 30"


def test_a_cancel_during_the_search_ends_it_without_results(tmp_path: Path) -> None:
    cancel = threading.Event()

    def on_progress(report: Progress) -> None:
        if report.message.startswith("Search, candidate 2"):
            cancel.set()

    outcome = run(searching("bowl", value=3), tmp_path, cancel=cancel, on_progress=on_progress)
    assert outcome == RunOutcome("cancelled", (), None, None)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["search-000", "search-001"]


def test_a_cancel_during_confirmation_ends_it_without_results(tmp_path: Path) -> None:
    cancel = threading.Event()

    def on_progress(report: Progress) -> None:
        if report.message.startswith("Confirmation"):
            cancel.set()

    outcome = run(searching("bowl", value=3), tmp_path, cancel=cancel, on_progress=on_progress)
    assert outcome.state == "cancelled"
    assert not (tmp_path / "confirm-002").exists()


def test_a_cancel_while_a_group_is_confirmed_ends_it_without_results(tmp_path: Path) -> None:
    cancel = threading.Event()

    def on_progress(report: Progress) -> None:
        # After the baseline, tills 4 (candidate 4) is confirmed first.
        if report.message.startswith("Confirmation, candidate 4"):
            cancel.set()

    outcome = run(searching("bowl", value=3), tmp_path, cancel=cancel, on_progress=on_progress)
    assert outcome.state == "cancelled"
    assert (tmp_path / "confirm-003").exists() and not (tmp_path / "confirm-004").exists()


def test_a_cancel_before_the_search_starts_runs_nothing(tmp_path: Path) -> None:
    cancel = threading.Event()
    cancel.set()
    outcome = run(searching("bowl"), tmp_path, cancel=cancel)
    assert outcome.state == "cancelled"
    assert list(tmp_path.iterdir()) == []


def test_a_cancel_in_a_later_optuna_candidate_ends_the_search(tmp_path: Path) -> None:
    cancel = threading.Event()

    def on_progress(report: Progress) -> None:
        if report.message.startswith("Search, candidate 3"):
            cancel.set()

    outcome = run(staffed(6), tmp_path, cancel=cancel, on_progress=on_progress)
    assert outcome.state == "cancelled"


def test_the_warm_up_check_runs_on_the_best_candidates_confirmation(tmp_path: Path) -> None:
    """W210 for a search (spec 2 "Statistic definitions", scope decided at M5; AKS-109):
    the best candidate's confirmation, whose results the summary reports, is checked."""
    found = run(searching("bowl drift", value=3), tmp_path)
    assert found.summary is not None
    [warning] = found.summary["warnings"]
    assert warning["code"] == "W210" and warning["path"] == "/experiments/0/warmup"
    # Each replication's samples are 1, 1, 2, 2 (plus 1 in odd replications): the halves
    # differ by 1 and the mean is 2, a change of 50%.
    assert "till.queue_length in scenario default changed by 50%" in warning["message"]


def test_the_recipes_are_what_the_tests_say() -> None:
    assert search_metrics("late", {"tills": 1.0}, 9)["till.utilization"] == 0.0
    assert search_metrics("late", {"tills": 1.0}, 10)["till.utilization"] == 1.0
    assert search_metrics("late rescue", {"tills": 6.0}, 20)["till.utilization"] == 1.0
    assert math.isnan(search_metrics("nan", {"tills": 2.0}, 0)["till.wait.mean"])
    with pytest.raises(ValueError, match="no recipe"):
        search_metrics("other", {}, 0)


# --- the machine-count test (spec 2 acceptance table, M5) --------------------------------


def machine_count(budget: int) -> dict[str, Any]:
    """Spec 2 "Benchmark definitions", machine count: the coffee shop with `tills` integer 1
    to 5, objective minimize `till.wait.mean`, constraint `till.utilization >= 0.35`, the
    file's seed 12345, 30 replications of 200 h with 10 h of warm-up, and
    `search.replications` at its default of 10."""
    document = coffee_shop()
    document["objectives"] = [{"id": "wait", "metric": "till.wait.mean", "sense": "minimize"}]
    document["constraints"] = [
        {"id": "busy", "metric": "till.utilization", "op": ">=", "value": 0.35}
    ]
    document["experiments"][0]["search"] = {"objective": "wait", "budget": budget}
    return document


WORKERS = 4


def enumerated(tmp_path: Path) -> dict[int, dict[str, Any]]:
    """Every `tills` from 1 to 5 run as a plain experiment of five scenarios with the
    experiment's 30 replications and seed: the metrics of each."""
    document = coffee_shop()
    document["experiments"][0]["scenarios"] = [
        {"id": f"tills_{tills}", "set": {"tills": tills}} for tills in range(1, 6)
    ]
    outcome = run_experiment(ProcessAdapter(), load(document), "base", tmp_path, workers=WORKERS)
    assert outcome.summary is not None
    return {
        tills: outcome.summary["scenarios"][f"tills_{tills}"]["metrics"] for tills in range(1, 6)
    }


def enumerated_best(metrics: dict[int, dict[str, Any]]) -> int:
    feasible = [t for t, m in metrics.items() if m["till.utilization"]["mean"] >= 0.35]
    return min(feasible, key=lambda t: (metrics[t]["till.wait.mean"]["mean"], t))


@pytest.mark.benchmark
def test_the_machine_count_search_finds_2_tills_equal_to_the_enumerated_best(
    tmp_path: Path,
) -> None:
    """Spec 2 acceptance: "The machine-count test finds `tills` = 2 and equals the
    enumerated best". Budget 10 holds the five combinations: the exhaustive path."""
    model = load(machine_count(10))
    _, _, search = search_of(model, "base")
    assert search_method(model, search) == "exhaustive"
    outcome = run_experiment(ProcessAdapter(), model, "base", tmp_path / "search", workers=WORKERS)
    found = search_of_summary(outcome)
    metrics = enumerated(tmp_path / "enumerated")
    assert enumerated_best(metrics) == 2
    assert found["best"] == {"set": {"tills": 2}}
    assert found["status"] == "feasible"
    assert tills_of(found) == [1, 2, 3, 4, 5]
    # Feasible at search: 1 and 2 (utilization 0.75 and 0.375); 3 to 5 are below 0.35.
    assert [c["feasible"] for c in found["candidates"]] == [True, True, False, False, False]
    assert confirmed(found) == [1, 2]
    # Common random numbers and the same seed: each confirmed candidate's metrics are the
    # enumeration's for its value of tills.
    for candidate in found["candidates"][:2]:
        assert candidate["metrics"] == metrics[candidate["set"]["tills"]]
    # Theory (Erlang C): 270 s and 14.73 s (0.245 min) at utilization 0.375.
    one, two = found["candidates"][:2]
    assert mean(one) == pytest.approx(270.0, rel=0.05)
    assert mean(two) == pytest.approx(27 / 110 * 60, rel=0.05)
    assert mean(two, "till.utilization") == pytest.approx(0.375, rel=0.02)
    assert found["objective"]["before"] == mean(one) and found["objective"]["after"] == mean(two)
    assert found["separated"] is True


@pytest.mark.benchmark
def test_the_machine_count_search_on_the_optuna_path_is_feasible_and_repeats(
    tmp_path: Path,
) -> None:
    """The same with budget 3, fewer than the five combinations: the Optuna path. The best
    is feasible, and a second run with the same seed gives the same candidates and result."""
    model = load(machine_count(3))
    _, _, search = search_of(model, "base")
    assert search_method(model, search) == "optuna"
    first = run_experiment(ProcessAdapter(), model, "base", tmp_path / "a", workers=WORKERS)
    again = run_experiment(ProcessAdapter(), model, "base", tmp_path / "b", workers=WORKERS)
    found = search_of_summary(first)
    best = [c for c in found["candidates"] if c["set"] == found["best"]["set"]]
    assert found["status"] == "feasible" and best and best[0]["feasible"] and best[0]["confirmed"]
    assert mean(best[0], "till.utilization") >= 0.35
    assert search_of_summary(again) == found
    assert again.summary == first.summary
    # Research note: the sampler proposes 1, 1, 2, 4 for seed 12345.
    assert tills_of(found) == [1, 2, 4]
    assert found["best"] == {"set": {"tills": 2}}


def test_the_machine_count_model_is_the_benchmark_file() -> None:
    root = Path(__file__).resolve().parents[2]
    document = json.loads((root / "benchmarks" / "machine_count" / "model.json").read_text("utf-8"))
    expected = copy.deepcopy(machine_count(10))
    assert document["objectives"] == expected["objectives"]
    assert document["constraints"] == expected["constraints"]
    assert document["experiments"] == expected["experiments"]
    assert document["parameters"] == expected["parameters"]
    assert document["components"] == expected["components"]
