"""Compatibility of the ``/v1`` API: each recorded response keeps every field it had, with
the same JSON type; new fields may be added (build guide "Conventions", Compatibility;
docs/retrospective/proposed-agent-setup.md, P24; #99).

One fixed, seeded scenario is run through the service in process: the coffee shop, short,
created, saved, validated and run to the end. Each JSON response is reduced to its shape: the
set of key paths with their JSON types, array items merged under ``[]``, and integers and
floats both ``number`` (a mean that happens to be whole is still a number). The shapes are
recorded in ``tests/compat/api/v1/``; this test fails when a recorded path disappears or its
type changes.

To record after an intended, compatible change (new fields only), or for a new route:
``ITHAX_RECORD_API_SHAPES=1 pytest tests/compat/test_api_shapes.py``, then review the diff:
a recorded line may be added, never removed or changed, without a new API version and an
owner decision record.

Not recorded: the WebSocket event streams, ``GET /v1/ui/{path}`` and the project export
(not JSON), and the data upload, fit and delete and the run cancel routes (they need their
own scenarios).
"""

import json
import os
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from ithax.service.app import create_app
from ithax.service.config import ServiceConfig
from ithax.service.hardware import Hardware

ROOT = Path(__file__).resolve().parents[2]
SHAPES = Path(__file__).resolve().parent / "api" / "v1"
# The old name, LCSIM_RECORD_API_SHAPES, is read for one release (#70).
RECORD = "1" in (
    os.environ.get("ITHAX_RECORD_API_SHAPES"),
    os.environ.get("LCSIM_RECORD_API_SHAPES"),
)
PORT = 8767
TOKEN = "compat-token"
BASE_URL = f"http://127.0.0.1:{PORT}"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
TIMEOUT_S = 120.0

Json = Any


def json_type(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def shape(value: object, path: str = "$") -> set[str]:
    """``value``'s key paths with their JSON types, as ``"<path> <type>"`` lines."""
    found = {f"{path} {json_type(value)}"}
    if isinstance(value, dict):
        for key, item in value.items():
            found |= shape(item, f"{path}.{key}")
    elif isinstance(value, list):
        for item in value:
            found |= shape(item, f"{path}[]")
    return found


def test_shape_merges_array_items_and_counts_whole_numbers_as_numbers() -> None:
    assert shape({"a": [1, 2.5, {"b": None}], "c": True}) == {
        "$ object",
        "$.a array",
        "$.a[] number",
        "$.a[] object",
        "$.a[].b null",
        "$.c boolean",
    }


@pytest.fixture(scope="module")
def responses(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Json]]:
    """Each recorded route's response body, keyed by its file name."""
    folder = tmp_path_factory.mktemp("compat")
    config = ServiceConfig(
        config_dir=folder / "config",
        data_dir=folder / "data",
        port=PORT,
        token=TOKEN,
        templates_dir=ROOT / "templates",
        hardware=Hardware(cores=4, memory=8 * 1024**3, graphics=()),
    )
    model = json.loads((ROOT / "examples" / "coffee_shop.json").read_text(encoding="utf-8"))
    model["experiments"][0].update(length="2 h", warmup="0 s", replications=2)
    bodies: dict[str, Json] = {}

    def ok(name: str, response: Any, status: int = 200) -> Json:
        assert response.status_code == status, (name, response.status_code, response.text)
        bodies[name] = response.json()
        return bodies[name]

    with TestClient(create_app(config), base_url=BASE_URL, headers=AUTH) as client:
        ok("get-system", client.get("/v1/system"))
        ok("get-settings", client.get("/v1/settings"))
        ok("get-engines", client.get("/v1/engines"))
        ok("get-schema-component-server", client.get("/v1/schema/components/server"))
        ok("get-templates", client.get("/v1/templates"))
        ok("get-template-coffee_shop", client.get("/v1/templates/coffee_shop"))
        project = ok(
            "post-projects", client.post("/v1/projects", json={"name": "Shop", "domain": "process"})
        )
        pid = project["id"]
        ok("get-projects", client.get("/v1/projects"))
        ok("put-model", client.put(f"/v1/projects/{pid}/model", content=json.dumps(model)))
        ok("get-model", client.get(f"/v1/projects/{pid}/model"))
        ok("post-validate", client.post(f"/v1/projects/{pid}/validate"))
        ok("get-data", client.get(f"/v1/projects/{pid}/data"))
        started = ok(
            "post-runs",
            client.post(f"/v1/projects/{pid}/runs", json={"experiment_id": "base"}),
            status=202,
        )
        rid = started["run_id"]
        deadline = time.monotonic() + TIMEOUT_S
        while client.get(f"/v1/runs/{rid}").json()["state"] not in ("done", "failed"):
            assert time.monotonic() < deadline, "the run did not finish"
            time.sleep(0.2)
        run = ok("get-run", client.get(f"/v1/runs/{rid}"))
        assert run["state"] == "done", run
        ok("get-runs", client.get(f"/v1/projects/{pid}/runs"))
        ok("get-summary", client.get(f"/v1/runs/{rid}/summary"))
        ok("get-table-replications", client.get(f"/v1/runs/{rid}/tables/replications"))
    yield bodies


NAMES = sorted(path.stem for path in SHAPES.glob("*.txt")) if SHAPES.is_dir() else []


def test_every_route_of_the_scenario_has_a_record(responses: dict[str, Json]) -> None:
    if RECORD:
        SHAPES.mkdir(parents=True, exist_ok=True)
        for name, body in responses.items():
            (SHAPES / f"{name}.txt").write_text("\n".join(sorted(shape(body))) + "\n", "utf-8")
    recorded = {path.stem for path in SHAPES.glob("*.txt")}
    assert recorded == set(responses), "record the shapes: see this module's docstring"


@pytest.mark.parametrize("name", NAMES)
def test_a_response_keeps_every_recorded_field_and_type(
    name: str, responses: dict[str, Json]
) -> None:
    recorded = set((SHAPES / f"{name}.txt").read_text("utf-8").splitlines())
    missing = recorded - shape(responses[name])
    assert not missing, f"{name}: fields gone or changed type: {sorted(missing)}"
