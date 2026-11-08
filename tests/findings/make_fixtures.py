"""Writes the finding-rule fixtures in ``tests/findings/fixtures/`` (spec 4 "Finding rules";
AKS-117).

A fixture is a finished run, not a model: findings read results, so each file holds the
run folder's ``model.json`` (the exact model that ran) under ``model`` and its
``summary.json`` under ``summary``, with ``about`` saying how it was made. The tests read
the files and run nothing.

Every fixture is a real run on the ``local`` run target (spec 1 "How the ``local`` target
runs a run"), so its ``summary.json`` is exactly what the experiment manager writes,
load-time warnings (W201) included. Each starts from an example or a benchmark file and
keeps its seed (12345 for the examples and the machine-count benchmark); a change from the
file is named in ``about``.

Regenerate with ``python tests/findings/make_fixtures.py`` from the repository root, after
``pip install -e ".[dev]"``. Runs use the ``spawn`` start method, so the work is under the
``__main__`` guard. Results do not depend on the number of workers (spec 1 "Identical
runs"), so a regeneration on the same Python and library versions writes the same files.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lcsim.runs.targets import LocalTarget
from lcsim.strict_json import read_json_file

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
WORKERS = min(4, os.cpu_count() or 1)

Document = dict[str, Any]


def _read(relative: str) -> Document:
    document = read_json_file(ROOT / relative)
    assert isinstance(document, dict)
    return document


def _unchanged(document: Document) -> Document:
    return document


def _overloaded(document: Document) -> Document:
    """The coffee shop with customers every 1.4 min: 1.5 / 1.4 = 1.07 of the till's
    capacity, so W201."""
    changed = copy.deepcopy(document)
    changed["components"][0]["params"]["interarrival"]["mean"] = "1.4 min"
    return changed


def _three_tills(document: Document) -> Document:
    """The coffee shop with ``tills`` 3: utilization 0.75 / 3 = 0.25."""
    changed = copy.deepcopy(document)
    changed["parameters"]["tills"]["value"] = 3
    return changed


def _close_scenarios(document: Document) -> Document:
    """The coffee shop with the service mean as a parameter and two scenarios, 1.5 min and
    1.51 min, run for 21 h with 1 h of warm-up and 10 replications: each scenario's wait
    interval is wide (about 26% of the mean), while the waits differ by about 3% in theory
    (270 s and 279 s). Common random numbers scale every service time of the same
    replication alike, so the paired difference is separated all the same."""
    changed = copy.deepcopy(document)
    changed["parameters"]["service_mean"] = {"value": "1.5 min", "type": "quantity"}
    changed["components"][1]["params"]["service"]["mean"] = {"$param": "service_mean"}
    changed["experiments"][0].update(
        {
            "length": "21 h",
            "warmup": "1 h",
            "replications": 10,
            "scenarios": [
                {"id": "now", "set": {}},
                {"id": "slower", "set": {"service_mean": "1.51 min"}},
            ],
        }
    )
    return changed


@dataclass(frozen=True)
class Case:
    """One run: the file it starts from, the change made, and the fixtures it writes."""

    source: str
    change: Callable[[Document], Document]
    about: str
    names: tuple[str, ...]

    def experiment(self, document: Document) -> str | None:
        if document["domain"] == "optimization":
            return None
        experiment_id = document["experiments"][0]["id"]
        assert isinstance(experiment_id, str)
        return experiment_id


COFFEE = "examples/coffee_shop.json"
LINE = "examples/three_machine_line.json"

CASES = (
    Case(
        LINE,
        _unchanged,
        "examples/three_machine_line.json unchanged (experiment base: 30 replications of "
        "100 h with 20 h of warm-up, seed 12345). The M1 three-machine line is the firing "
        "model for bottleneck and not_enough_runs (spec 4).",
        ("bottleneck_fires", "not_enough_runs_fires"),
    ),
    Case(
        COFFEE,
        _unchanged,
        "examples/coffee_shop.json unchanged (experiment base: 30 replications of 200 h "
        "with 10 h of warm-up, seed 12345). The coffee shop is the silent model for "
        "bottleneck and not_enough_runs (spec 4); it has no W201, no idle till and no "
        "optimization.",
        (
            "bottleneck_silent",
            "not_enough_runs_silent",
            "unstable_silent",
            "idle_capacity_silent",
            "optimization_result_silent",
        ),
    ),
    Case(
        COFFEE,
        _overloaded,
        "examples/coffee_shop.json with the interarrival mean 1.4 min in place of 2 min, "
        "so the till's load is 1.5 / 1.4 = 1.07 of its capacity and loading raises W201; "
        "otherwise unchanged (seed 12345).",
        ("unstable_fires",),
    ),
    Case(
        COFFEE,
        _three_tills,
        "examples/coffee_shop.json with parameter tills at 3 in place of 1, so the till's "
        "utilization is 0.75 / 3 = 0.25, below 0.30; otherwise unchanged (seed 12345).",
        ("idle_capacity_fires",),
    ),
    Case(
        "benchmarks/machine_count/model.json",
        _unchanged,
        "benchmarks/machine_count/model.json unchanged: the coffee shop searched over tills "
        "1 to 5 (exhaustive path, budget 10, seed 12345); a search run's summary.json with "
        "its search block (spec 2 'Simulation-based optimization').",
        ("optimization_result_fires",),
    ),
    Case(
        "benchmarks/product_mix/model.json",
        _unchanged,
        "benchmarks/product_mix/model.json unchanged: a mathematical optimization run, "
        "solved once by the HiGHS adapter (no seed); its summary.json is the solution.",
        ("optimization_result_program",),
    ),
    Case(
        COFFEE,
        _close_scenarios,
        "examples/coffee_shop.json with the service mean as a quantity parameter "
        "service_mean and two scenarios, now (1.5 min) and slower (1.51 min), run for 21 h "
        "with 1 h of warm-up and 10 replications (seed 12345). Each scenario's wait is "
        "uncertain, but common random numbers separate the paired difference.",
        ("not_enough_runs_scenarios",),
    ),
)


def run_case(case: Case, runs_root: Path) -> tuple[Document, Document]:
    """Runs the case on the local target and returns the run folder's model and summary."""
    document = case.change(_read(case.source))
    target = LocalTarget(runs_root, workers=WORKERS)
    run = target.create(json.dumps(document, indent=2).encode("utf-8"), case.experiment(document))
    state = run.execute()
    if state != "done":
        raise SystemExit(f"{case.source}: the run ended {state}; see {run.folder / 'log.txt'}")
    model = read_json_file(run.folder / "model.json")
    summary = read_json_file(run.folder / "summary.json")
    assert isinstance(model, dict) and isinstance(summary, dict)
    return model, summary


def main(names: list[str]) -> None:
    """Writes every fixture, or only those named."""
    FIXTURES.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        for case in CASES:
            wanted = [name for name in case.names if not names or name in names]
            if not wanted:
                continue
            model, summary = run_case(case, Path(folder) / "runs")
            for name in wanted:
                fixture = {"about": case.about, "model": model, "summary": summary}
                text = json.dumps(fixture, indent=1, ensure_ascii=False) + "\n"
                (FIXTURES / f"{name}.json").write_text(text, encoding="utf-8")
                print(f"wrote {name}.json")


if __name__ == "__main__":
    main(sys.argv[1:])
