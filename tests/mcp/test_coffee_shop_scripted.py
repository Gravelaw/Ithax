"""The scripted coffee-shop case: spec 4 "Assistant acceptance case", Level 1 (AKS-116).

A scripted client stands in for the assistant: the MCP SDK's own client side, over stdio,
against ``python -m ithax.mcp`` run as its own process, as a desktop assistant starts it.
The server is given temporary configuration and data folders (and a temporary home, so no
per-user folder can be reached even by mistake), so it starts its own engine service on
demand. The client makes the model the fixed description asks for with the tools alone
(``create_model``, ``edit_model``, ``validate_model``, ``run_model``, ``get_run_status``,
``get_model`` and ``get_results``), setting ``seed`` 12345, and the pass criteria are checked
without assuming any id (``mcp_support.coffee_shop_verdict``): the project validates with
zero errors, the run reaches ``done``, and the server's ``wait.mean`` is within 3 standard
errors of 270 s and its ``utilization`` within 3 standard errors of 0.75 (the spec 2 pass
rule; the standard error is the half-width divided by the t quantile the summary used).

The run is the description's: 30 replications of 200 h after a 10 h warm-up, which is
``length`` 210 h with ``warmup`` 10 h, since a length includes its warm-up. At the end the
service the MCP server started is stopped, with every process it started, and nothing is
left outside the test's folders.
"""

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import anyio
from mcp import Client, StdioServerParameters
from mcp_support import (
    COFFEE_SHOP_UTILIZATION,
    COFFEE_SHOP_WAIT_S,
    SPEC_4,
    coffee_shop_verdict,
    payload,
    stop_started,
)

from ithax.runs.statistics import t_quantile
from ithax.service.config import default_config_dir
from ithax.service.discovery import read_service_file

DESCRIPTION = Path(__file__).with_name("coffee_shop_description.txt")

#: How long the run may take before the case fails; it takes a few seconds on 4 cores.
RUN_TIMEOUT_S = 300.0

#: The edits a scripted client makes from the description: arrivals about every 2 minutes
#: at random (exponential), one till serving in about 1.5 minutes at random (exponential),
#: and the experiment of 200 h after a 10 h warm-up, 30 times, with seed 12345. An
#: experiment's length includes its warm-up (spec 1), so 200 h after 10 h is length 210 h.
EDITS: list[dict[str, Any]] = [
    {
        "edit": "add_component",
        "id": "arrivals",
        "type": "source",
        "params": {"interarrival": {"dist": "exponential", "mean": "2 min"}},
    },
    {
        "edit": "add_component",
        "id": "till",
        "type": "server",
        "params": {"capacity": 1, "service": {"dist": "exponential", "mean": "1.5 min"}},
    },
    {"edit": "add_component", "id": "exit", "type": "sink", "params": {}},
    {"edit": "connect", "from": "arrivals.out", "to": "till.in"},
    {"edit": "connect", "from": "till.out", "to": "exit.in"},
    {
        "edit": "set_experiment",
        "id": "base",
        "length": "210 h",
        "warmup": "10 h",
        "replications": 30,
        "seed": 12345,
    },
]


def test_the_description_file_is_spec_4_s_text() -> None:
    """The fixed description is the one spec 4 quotes, word for word."""
    text = SPEC_4.read_text(encoding="utf-8")
    section = text[text.index("### Assistant acceptance case") :]
    quoted = re.search(r"^> (.+)$", section, re.MULTILINE)
    assert quoted is not None
    assert DESCRIPTION.read_text(encoding="utf-8") == quoted.group(1) + "\n"


def server_parameters(tmp_path: Path) -> StdioServerParameters:
    """``python -m ithax.mcp`` with the test's folders, its own home and working folder."""
    home = tmp_path / "home"
    home.mkdir()
    return StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "ithax.mcp",
            "--config-dir",
            str(tmp_path / "config"),
            "--data-dir",
            str(tmp_path / "data"),
        ],
        env={
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
        },
        cwd=tmp_path,
    )


async def call(client: Client, name: str, arguments: dict[str, Any]) -> Any:
    """The JSON of a tool's result, which must not be marked ``isError``."""
    result = await client.call_tool(name, arguments)
    value = payload(result)
    assert not result.is_error, (name, value)
    return value


async def coffee_shop(client: Client) -> dict[str, Any]:
    """The case as a scripted client plays it; the answers the verdict reads."""
    project = await call(client, "create_model", {"name": "Coffee shop"})
    project_id = project["id"]
    edited = await call(
        client, "edit_model", {"project_id": project_id, "edits": EDITS, "base_revision": 0}
    )
    assert edited["issues"] == [], edited["issues"]
    validation = await call(client, "validate_model", {"project_id": project_id})
    model = (await call(client, "get_model", {"project_id": project_id}))["model"]
    started = await call(client, "run_model", {"project_id": project_id, "experiment_id": "base"})
    run_id = started["run_id"]
    deadline = time.monotonic() + RUN_TIMEOUT_S
    status = await call(client, "get_run_status", {"run_id": run_id})
    while status["state"] in ("queued", "running"):
        assert time.monotonic() < deadline, status
        await anyio.sleep(0.2)
        status = await call(client, "get_run_status", {"run_id": run_id})
    results = await call(client, "get_results", {"run_id": run_id})
    return {"model": model, "validation": validation, "run": status, "results": results}


def test_the_scripted_coffee_shop_case_passes(tmp_path: Path) -> None:
    answers: dict[str, Any] = {}
    # A service of the user's own, if one runs, is not this test's and must be left as it is.
    users_service = read_service_file(default_config_dir())

    async def session() -> None:
        async with Client(server_parameters(tmp_path)) as client:
            answers.update(await coffee_shop(client))

    started = time.monotonic()
    try:
        anyio.run(session)
    finally:
        stopped = stop_started(tmp_path / "config")
    elapsed = time.monotonic() - started

    verdict = coffee_shop_verdict(
        answers["model"], answers["validation"], answers["run"], answers["results"]["summary"]
    )
    # Printed for the session summary (pytest -s or -rP shows it).
    print(json.dumps({"elapsed_s": round(elapsed, 2), "verdict": verdict}, indent=2))
    assert verdict["servers"] == ["till"]
    assert verdict["validation_errors"] == []
    assert verdict["state"] == "done"
    wait, utilization = verdict["metrics"]["wait.mean"], verdict["metrics"]["utilization"]
    assert (wait["target"], utilization["target"]) == (COFFEE_SHOP_WAIT_S, COFFEE_SHOP_UTILIZATION)
    assert wait["unit"] == "s" and wait["n"] == 30 and utilization["n"] == 30
    summary = answers["results"]["summary"]
    assert summary["fidelity_label"] == "Standard: 30 replications of 210 h, 95% confidence"
    assert abs(wait["deviation"]) <= 3 and abs(utilization["deviation"]) <= 3
    assert verdict["passed"]
    # The coffee shop fires no finding (spec 4 "Finding rules"; AKS-135): the till is busy
    # about 75% of the time and its wait interval is about 3.4% of the mean.
    assert answers["results"]["findings"] == []
    assert answers["results"]["issues"] == []

    # The service was this test's: started in its configuration folder, and stopped.
    assert stopped, "the MCP server started no service"
    assert read_service_file(default_config_dir()) == users_service
    # Nothing was written to the temporary home: no per-user folder was used.
    assert list((tmp_path / "home").iterdir()) == []
    # The project, and the run's folder inside it, are in the test's data folder.
    [project] = (tmp_path / "data" / "projects").iterdir()
    [run_folder] = (project / "runs").iterdir()
    assert run_folder.name == answers["run"]["run_id"]
    assert (run_folder / "summary.json").is_file()


def test_the_verdict_fails_what_the_case_does_not_meet() -> None:
    """The verdict is not a formality: each criterion can fail it."""
    model = {"components": [{"id": "s1", "type": "server"}]}
    clean: dict[str, Any] = {"issues": []}
    done = {"state": "done"}

    def summary(wait: float, utilization: float) -> dict[str, Any]:
        # Half-widths whose standard error is 1.0 s and 0.01 (t at 0.95 for n 30, 2.0452).
        t = t_quantile(0.95, 30)
        return {
            "confidence": 0.95,
            "scenarios": {
                "default": {
                    "metrics": {
                        "s1.wait.mean": {"mean": wait, "half_width": t, "unit": "s", "n": 30},
                        "s1.utilization": {
                            "mean": utilization,
                            "half_width": t * 0.01,
                            "unit": "1",
                            "n": 30,
                        },
                    }
                }
            },
        }

    assert coffee_shop_verdict(model, clean, done, summary(272.9, 0.779))["passed"]
    assert not coffee_shop_verdict(model, clean, done, summary(273.1, 0.75))["passed"]
    assert not coffee_shop_verdict(model, clean, done, summary(270.0, 0.7199))["passed"]
    error = {"issues": [{"code": "E130", "severity": "error"}]}
    assert not coffee_shop_verdict(model, error, done, summary(270, 0.75))["passed"]
    warning = {"issues": [{"code": "W210", "severity": "warning"}]}
    assert coffee_shop_verdict(model, warning, done, summary(270, 0.75))["passed"]
    assert not coffee_shop_verdict(model, clean, {"state": "failed"}, summary(270, 0.75))["passed"]
    two = {"components": [*model["components"], {"id": "s2", "type": "server"}]}
    assert not coffee_shop_verdict(two, clean, done, summary(270, 0.75))["passed"]
    missing = summary(270, 0.75)
    del missing["scenarios"]["default"]["metrics"]["s1.utilization"]
    assert not coffee_shop_verdict(model, clean, done, missing)["passed"]
    assert not coffee_shop_verdict(model, clean, done, None)["passed"]
