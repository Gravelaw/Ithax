"""The registered process adapter before AKS-98 (AKS-97).

Its name and version, its engine-specific checks (none yet: codes E300 to E399 are
reserved for them), and the three methods AKS-98 fills in, which raise until then.
"""

import json
import multiprocessing
from pathlib import Path

import pytest

import lcsim
from lcsim.engines.process.adapter import ProcessAdapter
from lcsim.model.loading import load_document

ROOT = Path(__file__).resolve().parents[3]


def coffee_shop() -> object:
    return json.loads((ROOT / "examples" / "coffee_shop.json").read_text(encoding="utf-8"))


def test_the_adapter_is_named_simpy_with_the_product_version() -> None:
    adapter = ProcessAdapter()
    assert adapter.name == "simpy"
    assert adapter.version == lcsim.__version__


def test_validate_adds_no_issue_to_a_valid_model() -> None:
    model = load_document(coffee_shop()).model
    assert model is not None
    assert ProcessAdapter().validate(model) == []


def test_translate_run_and_collect_wait_for_aks_98(tmp_path: Path) -> None:
    adapter = ProcessAdapter()
    model = load_document(coffee_shop()).model
    assert model is not None
    with pytest.raises(NotImplementedError, match="AKS-98"):
        adapter.translate(model, "base", tmp_path)
    with pytest.raises(NotImplementedError, match="AKS-98"):
        adapter.run(tmp_path, lambda progress: None, multiprocessing.Event(), 1)
    with pytest.raises(NotImplementedError, match="AKS-98"):
        adapter.collect(tmp_path)
    assert list(tmp_path.iterdir()) == []
