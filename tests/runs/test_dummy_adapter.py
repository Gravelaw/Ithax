"""Spec 1 acceptance (M3): "A dummy adapter passes through all five methods on the local
target".

The dummy implements the spec 1 interface without an engine (``dummy_adapters``). Each
method must be called once, in its spec 1 place ("Run targets": ``validate``,
``translate`` and ``collect`` in the process that drives the run, ``run`` in the worker
process), in the order capabilities, validate, translate, run, collect.
"""

import json
import os
from pathlib import Path

from dummy_adapters import INPUT_FILE, OUTPUT_FILE, RUN_RECORD, DummyAdapter

from ithax.runs.manifest import read_manifest
from ithax.runs.targets import LocalTarget

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def test_a_dummy_adapter_passes_through_all_five_methods_on_the_local_target(
    tmp_path: Path,
) -> None:
    adapter = DummyAdapter()
    model_file = (EXAMPLES / "coffee_shop.json").read_bytes()
    run = LocalTarget(tmp_path / "runs", adapters={"dummy": adapter}).create(model_file, "base")
    # Choosing the adapter asks its capabilities; validate refuses or admits the run.
    names = [name for name, _ in adapter.calls]
    assert "capabilities" in names and names[-1] == "validate"
    calls_before_run = len(adapter.calls)

    assert run.execute() == "done"

    here = os.getpid()
    after = adapter.calls[calls_before_run:]
    assert after == [("translate", here), ("collect", here)]
    assert {pid for _, pid in adapter.calls} == {here}
    assert names.count("validate") == 1
    record = json.loads((run.engine_folder / RUN_RECORD).read_text(encoding="utf-8"))
    assert record["pid"] != here  # run ran in the worker process
    assert record["input"] == {"experiment": "base", "model": "Coffee shop"}  # after translate
    assert record["workers"] == 1
    # Everything the adapter wrote is in engine/.
    assert sorted(path.name for path in run.engine_folder.iterdir()) == [
        INPUT_FILE,
        OUTPUT_FILE,
        RUN_RECORD,
    ]
    manifest = read_manifest(run.folder)
    assert manifest["state"] == "done"
    assert manifest["engine"] == {"name": "dummy", "version": "9.9.9"}
    summary = json.loads((run.folder / "summary.json").read_text(encoding="utf-8"))
    assert summary["scenarios"]["default"]["metrics"]["till.utilization"]["n"] == 2
