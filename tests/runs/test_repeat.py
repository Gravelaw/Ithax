"""Spec 1 acceptance (M3): "A repeated run is identical as defined above" (AKS-104).

Spec 1 "Identical runs": "`summary.json` metrics equal to full floating-point precision,
every table under `tables/` equal row for row, and `model.json` byte-equal.
`manifest.json` may differ only in `run_id`, `created`, `started`, `ended`, `host`."

Two runs of the same model file and seed on the local target (each ``execute`` starts its
own spawned worker process) are compared by ``run_comparison``: the summaries as parsed
JSON with exact equality, the tables as Arrow tables row for row (float cells exact and
NaN-aware), ``model.json`` as bytes, and the manifests key by key. A run with another seed
must differ, so the comparison is not vacuous; a run with ``workers=2`` must not, since the
results do not depend on ``workers`` (spec 1 "Division of labour").
"""

import json
import math
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest
from run_comparison import (
    MAY_DIFFER,
    has_nan,
    identical_differences,
    manifest_differences,
    read_json,
    read_tables,
    summary_metrics,
    tables_equal,
)

from ithax.runs.targets import LocalTarget

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def coffee_shop(seed: int = 12345) -> bytes:
    """The coffee shop over 20 h with 2 h of warm-up and 3 replications, with a second
    scenario (two tills), so that `differences` is filled. The file's own layout (an odd
    indent) is kept in `model.json`."""
    document: dict[str, Any] = json.loads(
        (EXAMPLES / "coffee_shop.json").read_text(encoding="utf-8")
    )
    document["experiments"][0].update(
        {
            "length": "20 h",
            "warmup": "2 h",
            "replications": 3,
            "seed": seed,
            "scenarios": [{"id": "one_till", "set": {}}, {"id": "two_tills", "set": {"tills": 2}}],
        }
    )
    return json.dumps(document, indent=3).encode("utf-8")


def sparse_shop() -> bytes:
    """A shop whose customers arrive every 20 h on average, run for 2 h after 1 h of
    warm-up: in most replications no service starts after warm-up, so `till.wait.mean` is
    NaN in the `replications` table (spec 1) and `null` in `summary.json`."""
    document: dict[str, Any] = json.loads(
        (EXAMPLES / "coffee_shop.json").read_text(encoding="utf-8")
    )
    document["components"][0]["params"]["interarrival"]["mean"] = "20 h"
    document["experiments"][0].update({"length": "3 h", "warmup": "1 h", "replications": 4})
    return json.dumps(document).encode("utf-8")


def run_once(runs: Path, model_file: bytes, *, workers: int = 1) -> Path:
    run = LocalTarget(runs, workers=workers).create(model_file, "base")
    assert run.execute() == "done"
    return run.folder


@pytest.fixture(scope="module")
def runs(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Six runs, each in its own worker process: the coffee shop twice at seed 12345, once
    with two workers and once at seed 12346; the sparse shop twice."""
    root = tmp_path_factory.mktemp("repeat") / "runs"
    return {
        "first": run_once(root, coffee_shop()),
        "repeat": run_once(root, coffee_shop()),
        "two_workers": run_once(root, coffee_shop(), workers=2),
        "other_seed": run_once(root, coffee_shop(seed=12346)),
        "sparse": run_once(root, sparse_shop()),
        "sparse_repeat": run_once(root, sparse_shop()),
    }


# --- the acceptance row ------------------------------------------------------------------


def test_a_repeated_run_is_identical(runs: dict[str, Path]) -> None:
    assert identical_differences(runs["first"], runs["repeat"]) == []


def test_the_summary_metrics_are_equal_to_full_precision(runs: dict[str, Path]) -> None:
    first, repeat = summary_metrics(runs["first"]), summary_metrics(runs["repeat"])
    assert list(first) == ["one_till", "two_tills"]
    assert first == repeat  # parsed JSON floats, compared exactly
    # The rest of summary.json (differences, warnings, label) repeats too.
    assert read_json(runs["first"] / "summary.json") == read_json(runs["repeat"] / "summary.json")
    assert read_json(runs["first"] / "summary.json")["differences"]


def test_every_table_is_equal_row_for_row(runs: dict[str, Path]) -> None:
    first, repeat = read_tables(runs["first"]), read_tables(runs["repeat"])
    assert sorted(first) == ["replications.parquet", "timeseries.parquet"]
    for name, table in first.items():
        assert table.num_rows > 0
        assert tables_equal(table, repeat[name]), name
        assert table.equals(repeat[name]), name  # no NaN in these tables, so Arrow agrees


def test_model_json_is_byte_equal_and_is_the_file(runs: dict[str, Path]) -> None:
    written = (runs["first"] / "model.json").read_bytes()
    assert written == (runs["repeat"] / "model.json").read_bytes()
    assert written == coffee_shop()


def test_the_manifests_differ_only_where_spec_1_allows(runs: dict[str, Path]) -> None:
    differences = manifest_differences(runs["first"], runs["repeat"])
    assert differences <= MAY_DIFFER
    assert "run_id" in differences  # two runs, two ids
    manifest = read_json(runs["first"] / "manifest.json")
    assert manifest["state"] == "done" and manifest["seed"] == 12345


def test_a_repeat_with_more_workers_is_identical(runs: dict[str, Path]) -> None:
    assert identical_differences(runs["first"], runs["two_workers"]) == []


def test_nan_cells_repeat_and_are_compared(runs: dict[str, Path]) -> None:
    first, repeat = read_tables(runs["sparse"]), read_tables(runs["sparse_repeat"])
    replications = first["replications.parquet"]
    assert has_nan(replications)
    assert not replications.equals(repeat["replications.parquet"])  # Arrow: NaN != NaN
    assert identical_differences(runs["sparse"], runs["sparse_repeat"]) == []
    metrics = summary_metrics(runs["sparse"])["default"]
    assert metrics["till.wait.mean"]["n"] < 4


# --- the comparison is not vacuous -------------------------------------------------------


def test_another_seed_gives_other_tables(runs: dict[str, Path]) -> None:
    first, other = read_tables(runs["first"]), read_tables(runs["other_seed"])
    for name, table in first.items():
        assert table.schema.equals(other[name].schema)
        assert table.num_rows == other[name].num_rows  # same rows, other values
        assert not tables_equal(table, other[name]), name
    assert summary_metrics(runs["first"]) != summary_metrics(runs["other_seed"])
    problems = identical_differences(runs["first"], runs["other_seed"])
    assert "summary.json metrics differ" in problems
    assert "tables/replications.parquet differs" in problems
    assert "model.json differs" in problems
    assert any("'seed'" in problem for problem in problems)


def test_the_table_comparison_sees_one_bit_and_nan(tmp_path: Path) -> None:
    def table(values: list[float]) -> Any:
        return pa.table({"metric": ["a"] * len(values), "value": values})

    base = table([1.0, math.nan])
    assert tables_equal(base, table([1.0, math.nan]))
    assert not tables_equal(base, table([math.nextafter(1.0, 2.0), math.nan]))
    assert not tables_equal(base, table([1.0, 0.0]))
    assert not tables_equal(table([0.0]), table([-0.0]))
    assert not tables_equal(base, table([math.nan, 1.0]))  # row order matters
    assert not tables_equal(base, base.rename_columns(["metric", "values"]))
    assert not tables_equal(
        base,
        pa.table({"metric": ["a", "a"], "value": [1.0, math.nan]}).cast(
            pa.schema([("metric", pa.large_string()), ("value", pa.float64())])
        ),
    )


def test_the_manifest_comparison_sees_a_missing_key(tmp_path: Path) -> None:
    for name, manifest in (("a", {"run_id": "x", "seed": 1}), ("b", {"run_id": "y"})):
        (tmp_path / name).mkdir()
        (tmp_path / name / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert manifest_differences(tmp_path / "a", tmp_path / "b") == {"run_id", "seed"}
