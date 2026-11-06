"""The three example models run end to end through the process adapter (spec 2 acceptance
row "The three example models run end to end", M2; AKS-99).

A smoke test: each example's own experiment, shortened to 5 h with 30 min of warm-up and 2
replications so that the suite stays fast, through ``translate``, ``run`` and ``collect``.
Measuring the examples against their targets is AKS-101.
"""

import json
import math
import threading
from pathlib import Path
from typing import Any

import pytest

from lcsim.engines.process.adapter import ProcessAdapter
from lcsim.model.catalogue import PROCESS_TYPES
from lcsim.model.loading import load_document

EXAMPLES = Path(__file__).resolve().parents[3] / "examples"


def shortened(name: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    document["experiments"][0].update({"length": "5 h", "warmup": "30 min", "replications": 2})
    return document


@pytest.mark.parametrize("name", ["coffee_shop.json", "three_machine_line.json", "warehouse.json"])
def test_each_example_runs_end_to_end(name: str, tmp_path: Path) -> None:
    document = shortened(name)
    model = load_document(document).model
    assert model is not None
    adapter = ProcessAdapter()
    adapter.translate(model, document["experiments"][0]["id"], tmp_path)
    adapter.run(tmp_path, lambda progress: None, threading.Event(), 1)
    results = adapter.collect(tmp_path)
    assert list(results.tables) == ["replications", "timeseries"]

    replications = results.tables["replications"].to_pylist()
    expected = [
        f"{component.id}.{measure}"
        for component in model.components
        for measure in PROCESS_TYPES[component.type].metrics
    ] + ["model.wip.mean"]
    assert [row["metric"] for row in replications] == expected * 2
    assert all(math.isfinite(row["value"]) for row in replications)
    sinks = [row for row in replications if row["metric"].endswith(".count")]
    assert all(row["value"] > 0 for row in sinks)

    servers = [component.id for component in model.components if component.type == "server"]
    series = results.tables["timeseries"].to_pylist()
    metrics = [
        f"{server}.{measure}" for server in servers for measure in ("queue_length", "utilization")
    ]
    expected_series = [metric for metric in [*metrics, "model.wip"] for _ in range(200)]
    assert [row["metric"] for row in series] == expected_series * 2
