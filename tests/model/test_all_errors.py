"""Every error at once (#92, Reviewer B finding 3): a block that cannot be built no longer
hides the value checks of the blocks that can (spec 1 "Validation").

Before #92 a build error (E122 here) stopped the load before the meaning pass, so a
parameter out of its range (E151), a setting out of its range (E123) and inconsistent
distribution fields (E160) on the other blocks were shown only once it was fixed.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from ithax.model.loading import load_document

ROOT = Path(__file__).resolve().parents[2]
COFFEE = json.loads((ROOT / "examples" / "coffee_shop.json").read_text(encoding="utf-8"))


def coffee() -> dict[str, Any]:
    return copy.deepcopy(COFFEE)


def codes_and_paths(document: dict[str, Any]) -> list[tuple[str, str]]:
    return [(issue.code, issue.path) for issue in load_document(document).issues]


def test_a_build_error_no_longer_hides_value_errors_elsewhere() -> None:
    document = coffee()
    # Block 1 cannot be built: its required 'service' is missing (E122).
    del document["components"][1]["params"]["service"]
    # Block 0, before it: an exponential whose mean is not above zero (E160).
    document["components"][0]["params"]["interarrival"]["mean"] = "-1 min"
    # Block 3, after it: a server whose capacity is 0 (E123), at its own index.
    document["components"].append(
        {
            "id": "back",
            "type": "server",
            "params": {"capacity": 0, "service": {"dist": "constant", "value": "1 min"}},
        }
    )
    # A parameter value above its max (E151).
    document["parameters"]["tills"]["value"] = 9
    result = load_document(document)
    assert result.model is None
    found = codes_and_paths(document)
    assert any(code == "E122" and path.startswith("/components/1/") for code, path in found)
    assert ("E151", "/parameters/tills/value") in found
    assert ("E160", "/components/0/params/interarrival/mean") in found
    assert ("E123", "/components/3/params/capacity") in found
    # The build's errors come first, then the value checks'.
    assert found[0][0] == "E122"


def test_checks_across_the_model_wait_for_a_model_that_builds() -> None:
    """A connection to a block that could not be built is not reported as a connection to
    nothing: the checks across the model (identifiers, connections, reachability, loads)
    still run only on a model that builds."""
    document = coffee()
    del document["components"][1]["params"]["service"]
    assert [code for code, _ in codes_and_paths(document)] == ["E122"]


def test_a_model_that_builds_is_checked_as_before() -> None:
    document = coffee()
    document["parameters"]["tills"]["value"] = 9
    assert codes_and_paths(document) == [("E151", "/parameters/tills/value")]


def test_an_experiment_after_one_that_cannot_be_built_keeps_its_index() -> None:
    """Review of PR #198: experiment 0 cannot be built (its 'length' is not a time), and a
    scenario of experiment 1 sets 'tills' above its max; the E151 names experiment 1."""
    document = coffee()
    second = copy.deepcopy(document["experiments"][0])
    second["id"] = "more"
    second["scenarios"] = [{"id": "many", "set": {"tills": 9}}]
    document["experiments"][0]["length"] = "lots"
    document["experiments"].append(second)
    found = codes_and_paths(document)
    assert ("E151", "/experiments/1/scenarios/0/set/tills") in found, found
    assert not any(path.startswith("/experiments/0/scenarios") for _, path in found), found
