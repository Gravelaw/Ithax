"""``GET /v1/settings`` and ``PUT /v1/settings`` (spec 3 "Endpoints"; AKS-119).

The settings of ``settings.json`` as the service takes them, and the one way the interface
writes them: each value checked by the rules the service reads it with, every problem an
E184 issue at its JSON Pointer in the body, nothing written when any is found.
"""

import dataclasses
import json
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from ithax.findings import DEFAULT_THRESHOLDS
from ithax.service.app import create_app
from ithax.service.config import ServiceConfig
from ithax.service.finding_settings import read_finding_settings
from ithax.service.hardware import SETTINGS_FILE, Hardware
from ithax.service.run_settings import read_run_settings
from ithax.service.settings_store import INTERFACE_DEFAULTS, SETTINGS_KEYS, recommended_undo_steps
from service.service_support import AUTH, BASE_URL, assert_error

DEFAULT_FINDINGS = dataclasses.asdict(DEFAULT_THRESHOLDS)


def settings_file(config: ServiceConfig) -> dict[str, object]:
    loaded = json.loads((config.config_dir / SETTINGS_FILE).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def put(client: TestClient, body: object) -> dict[str, Any]:
    response = client.put("/v1/settings", json=body)
    assert response.status_code == 200, response.text
    answered = response.json()
    assert isinstance(answered, dict)
    return answered


def test_get_gives_every_setting_with_its_default(
    client: TestClient, config: ServiceConfig
) -> None:
    response = client.get("/v1/settings")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"settings", "issues"}
    assert body["issues"] == []
    settings = body["settings"]
    assert tuple(settings) == SETTINGS_KEYS
    assert settings["tier"] == "mid"  # 8 cores and 16 GiB, stored at the first start
    assert settings["max_concurrent_runs"] == 1
    assert settings["run_time_limit_s"] == 600
    memory = read_run_settings(config.config_dir).limits
    assert settings["run_memory_limit_bytes"] == memory.memory_bytes
    assert settings["idle_timeout_minutes"] == 30
    assert settings["finding_thresholds"] == DEFAULT_FINDINGS
    assert settings["interface"] == INTERFACE_DEFAULTS


def test_the_interface_defaults_are_the_specs() -> None:
    assert INTERFACE_DEFAULTS == {
        "first_start_seen": False,
        "ask_before_deleting": True,
        "undo_steps": None,
        "theme": "system",
        "text_size": 100,
        "motion": "system",
        "colour_blind_charts": False,
    }


@pytest.mark.parametrize(("tier", "steps"), [("low", 200), ("mid", 500), ("high", 1000)])
def test_the_undo_steps_recommended_by_tier(tier: str, steps: int) -> None:
    assert recommended_undo_steps(tier) == steps  # type: ignore[arg-type]


def test_put_writes_the_keys_given_and_keeps_the_others(
    client: TestClient, config: ServiceConfig
) -> None:
    stored = settings_file(config)
    stored["kept"] = {"by": "another version"}
    (config.config_dir / SETTINGS_FILE).write_text(json.dumps(stored), encoding="utf-8")
    body = put(client, {"interface": {"first_start_seen": True}, "max_concurrent_runs": 2})
    assert body["settings"]["interface"] == {**INTERFACE_DEFAULTS, "first_start_seen": True}
    assert body["settings"]["max_concurrent_runs"] == 2
    assert body["settings"]["tier"] == "mid"
    assert settings_file(config) == {
        "tier": "mid",
        "kept": {"by": "another version"},
        "interface": {"first_start_seen": True},
        "max_concurrent_runs": 2,
    }
    assert client.get("/v1/settings").json() == body


def test_a_nested_object_is_replaced_whole(client: TestClient, config: ServiceConfig) -> None:
    put(client, {"finding_thresholds": {"bottleneck_utilization": 0.9}})
    body = put(client, {"finding_thresholds": {"idle_utilization": 0.2}})
    assert settings_file(config)["finding_thresholds"] == {"idle_utilization": 0.2}
    assert body["settings"]["finding_thresholds"] == {**DEFAULT_FINDINGS, "idle_utilization": 0.2}


def test_null_removes_a_key_so_its_default_applies(
    client: TestClient, config: ServiceConfig
) -> None:
    put(client, {"tier": "low", "run_time_limit_s": 30.5, "interface": {"theme": "dark"}})
    body = put(client, {"tier": None, "run_time_limit_s": None, "interface": None})
    assert settings_file(config) == {}
    assert body["settings"]["tier"] == "mid"  # the detected tier, stored again next start
    assert body["settings"]["run_time_limit_s"] == 600
    assert body["settings"]["interface"] == INTERFACE_DEFAULTS


def test_an_empty_object_changes_nothing(client: TestClient, config: ServiceConfig) -> None:
    before = settings_file(config)
    assert put(client, {}) == client.get("/v1/settings").json()
    assert settings_file(config) == before


def test_every_value_in_range_is_taken(client: TestClient) -> None:
    body = {
        "tier": "high",
        "max_concurrent_runs": 64,
        "run_time_limit_s": 604800,
        "run_memory_limit_bytes": 2**63 - 1,
        "idle_timeout_minutes": 10080,
        "finding_thresholds": {
            "bottleneck_utilization": 1,
            "idle_utilization": 0,
            "relative_half_width": 1,
            "min_time_s": 0,
            "min_rate_per_s": 0.5,
        },
        "interface": {
            "first_start_seen": True,
            "ask_before_deleting": False,
            "undo_steps": 10000,
            "theme": "light",
            "text_size": 200,
            "motion": "off",
            "colour_blind_charts": True,
        },
    }
    assert put(client, body)["settings"] == body


@pytest.mark.parametrize(
    ("body", "paths"),
    [
        ([], [""]),
        ("text", [""]),
        (None, [""]),
        ({"tier": "huge"}, ["/tier"]),
        ({"tier": 1}, ["/tier"]),
        ({"max_concurrent_runs": 0}, ["/max_concurrent_runs"]),
        ({"max_concurrent_runs": 65}, ["/max_concurrent_runs"]),
        ({"max_concurrent_runs": True}, ["/max_concurrent_runs"]),
        ({"max_concurrent_runs": 1.0}, ["/max_concurrent_runs"]),
        ({"run_time_limit_s": 0}, ["/run_time_limit_s"]),
        ({"run_time_limit_s": 604801}, ["/run_time_limit_s"]),
        ({"run_time_limit_s": "600"}, ["/run_time_limit_s"]),
        ({"run_memory_limit_bytes": 0}, ["/run_memory_limit_bytes"]),
        ({"run_memory_limit_bytes": 2**63}, ["/run_memory_limit_bytes"]),
        ({"idle_timeout_minutes": 0}, ["/idle_timeout_minutes"]),
        ({"idle_timeout_minutes": 10081}, ["/idle_timeout_minutes"]),
        ({"idle_timeout_minutes": 1.5}, ["/idle_timeout_minutes"]),
        ({"idle_timeout_minutes": 30.0}, ["/idle_timeout_minutes"]),
        ({"idle_timeout_minutes": True}, ["/idle_timeout_minutes"]),
        ({"idle_timeout_minutes": "30"}, ["/idle_timeout_minutes"]),
        ({"finding_thresholds": []}, ["/finding_thresholds"]),
        ({"finding_thresholds": {"bottleneck": 0.9}}, ["/finding_thresholds/bottleneck"]),
        (
            {"finding_thresholds": {"bottleneck_utilization": 1.5}},
            ["/finding_thresholds/bottleneck_utilization"],
        ),
        (
            {"finding_thresholds": {"relative_half_width": 0}},
            ["/finding_thresholds/relative_half_width"],
        ),
        ({"finding_thresholds": {"min_time_s": False}}, ["/finding_thresholds/min_time_s"]),
        ({"interface": 3}, ["/interface"]),
        ({"interface": {"theme": "blue"}}, ["/interface/theme"]),
        ({"interface": {"text_size": 110}}, ["/interface/text_size"]),
        ({"interface": {"text_size": True}}, ["/interface/text_size"]),
        ({"interface": {"text_size": 100.0}}, ["/interface/text_size"]),
        ({"interface": {"undo_steps": 99}}, ["/interface/undo_steps"]),
        ({"interface": {"undo_steps": 10001}}, ["/interface/undo_steps"]),
        ({"interface": {"first_start_seen": 1}}, ["/interface/first_start_seen"]),
        ({"interface": {"motion": "fast"}}, ["/interface/motion"]),
        ({"interface": {"colour_blind_charts": None}}, ["/interface/colour_blind_charts"]),
        ({"interface": {"zoom": 2}}, ["/interface/zoom"]),
        ({"other": 1}, ["/other"]),
        ({"a/b~c": 1}, ["/a~1b~0c"]),
        (
            {"tier": "x", "interface": {"theme": "x", "motion": "x"}},
            ["/tier", "/interface/theme", "/interface/motion"],
        ),
    ],
)
def test_a_value_that_cannot_be_used_is_e184_at_its_place_and_nothing_is_written(
    client: TestClient, config: ServiceConfig, body: object, paths: list[str]
) -> None:
    before = (config.config_dir / SETTINGS_FILE).read_bytes()
    response = client.put("/v1/settings", json=body)
    assert response.status_code == 400
    assert_error(response.json(), "E184")
    issues = response.json()["issues"]
    assert [issue["path"] for issue in issues] == paths
    for issue in issues:
        assert issue["code"] == "E184"
        assert issue["severity"] == "error"
        assert issue["message"] and issue["hint"]
    assert (config.config_dir / SETTINGS_FILE).read_bytes() == before


@pytest.mark.parametrize(
    "raw",
    [b"", b"{", b'{"run_time_limit_s": NaN}', b'{"run_time_limit_s": 1e999}', b'{"a": "\\ud800"}'],
    ids=["empty", "not-json", "nan", "infinity", "surrogate"],
)
def test_a_body_the_strict_reader_refuses_is_e184(client: TestClient, raw: bytes) -> None:
    response = client.put("/v1/settings", content=raw)
    assert response.status_code == 400
    assert_error(response.json(), "E184")
    assert [issue["path"] for issue in response.json()["issues"]] == [""]


def test_a_settings_file_that_cannot_be_read_is_replaced(
    client: TestClient, config: ServiceConfig
) -> None:
    (config.config_dir / SETTINGS_FILE).write_text("{not json", encoding="utf-8")
    got = client.get("/v1/settings").json()
    assert got["settings"]["tier"] == "mid"
    assert got["settings"]["interface"] == INTERFACE_DEFAULTS
    assert [issue["code"] for issue in got["issues"]] == ["W220"]
    body = put(client, {"interface": {"theme": "dark"}})
    assert settings_file(config) == {"interface": {"theme": "dark"}}
    assert body["issues"] == []


def test_a_settings_file_holding_another_kind_is_replaced(
    client: TestClient, config: ServiceConfig
) -> None:
    (config.config_dir / SETTINGS_FILE).write_text("[1, 2]", encoding="utf-8")
    put(client, {"max_concurrent_runs": 3})
    assert settings_file(config) == {"max_concurrent_runs": 3}


def test_stored_values_that_cannot_be_used_read_as_their_defaults(
    client: TestClient, config: ServiceConfig
) -> None:
    stored = {
        "tier": "giant",
        "max_concurrent_runs": "many",
        "finding_thresholds": {"bottleneck_utilization": 7},
        "interface": {"theme": "neon", "text_size": 150, "unknown": 1},
    }
    (config.config_dir / SETTINGS_FILE).write_text(json.dumps(stored), encoding="utf-8")
    got = client.get("/v1/settings").json()
    settings = got["settings"]
    assert settings["tier"] == "mid"
    assert settings["max_concurrent_runs"] == 1
    assert settings["finding_thresholds"] == DEFAULT_FINDINGS
    assert settings["interface"] == {**INTERFACE_DEFAULTS, "text_size": 150}
    assert [issue["path"] for issue in got["issues"]] == [
        "/finding_thresholds/bottleneck_utilization"
    ]


def test_stored_interface_preferences_of_another_kind_read_as_defaults(
    client: TestClient, config: ServiceConfig
) -> None:
    (config.config_dir / SETTINGS_FILE).write_text('{"interface": [true]}', encoding="utf-8")
    assert client.get("/v1/settings").json()["settings"]["interface"] == INTERFACE_DEFAULTS


def test_the_tier_and_run_settings_take_effect_at_the_next_start(
    client: TestClient, config: ServiceConfig, app: FastAPI
) -> None:
    put(client, {"tier": "low", "max_concurrent_runs": 3})
    assert client.get("/v1/system").json()["tier"] == "mid"
    assert app.state.service.runs.settings.max_concurrent_runs == 1
    restarted = create_app(config)
    assert restarted.state.service.tier == "low"
    assert restarted.state.service.runs.settings.max_concurrent_runs == 3
    with TestClient(restarted, base_url=BASE_URL, headers=AUTH) as again:
        assert again.get("/v1/system").json()["tier"] == "low"


def test_the_tier_detected_when_none_is_stored_follows_the_hardware(
    config: ServiceConfig,
) -> None:
    small = dataclasses.replace(config, hardware=Hardware(cores=2, memory=None, graphics=None))
    with TestClient(create_app(small), base_url=BASE_URL, headers=AUTH) as client:
        put(client, {"tier": None})
        assert client.get("/v1/settings").json()["settings"]["tier"] == "low"


def test_settings_need_the_token(app: FastAPI) -> None:
    with TestClient(app, base_url=BASE_URL) as client:
        assert client.get("/v1/settings").status_code == 401
        assert client.put("/v1/settings", json={}).status_code == 401


def test_new_thresholds_are_what_the_next_summary_reads(
    client: TestClient, config: ServiceConfig
) -> None:
    put(client, {"finding_thresholds": {"bottleneck_utilization": 0.95}})
    assert read_finding_settings(config.config_dir).thresholds.bottleneck_utilization == 0.95


# --- the idle timeout (spec 3 "Lifetime"; owner decision B5, AKS-141) ----------------------


def test_put_writes_the_idle_timeout_and_get_returns_it(
    client: TestClient, config: ServiceConfig
) -> None:
    body = put(client, {"idle_timeout_minutes": 1})
    assert body["settings"]["idle_timeout_minutes"] == 1
    assert body["issues"] == []
    assert settings_file(config)["idle_timeout_minutes"] == 1
    assert client.get("/v1/settings").json()["settings"]["idle_timeout_minutes"] == 1
    put(client, {"idle_timeout_minutes": None})
    assert "idle_timeout_minutes" not in settings_file(config)
    assert client.get("/v1/settings").json()["settings"]["idle_timeout_minutes"] == 30


def test_the_idle_timeout_refused_names_its_range(client: TestClient) -> None:
    response = client.put("/v1/settings", json={"idle_timeout_minutes": 0})
    [issue] = response.json()["issues"]
    assert issue["path"] == "/idle_timeout_minutes"
    assert "a whole number of minutes from 1 to 10,080 (7 days)" in issue["message"]


@pytest.mark.parametrize("value", [0, 10081, 2.5, "30", False, None])
def test_a_stored_idle_timeout_that_cannot_be_used_is_w220_and_30(
    client: TestClient, config: ServiceConfig, value: object
) -> None:
    stored = {"idle_timeout_minutes": value, "finding_thresholds": {"min_time_s": -1}}
    (config.config_dir / SETTINGS_FILE).write_text(json.dumps(stored), encoding="utf-8")
    got = client.get("/v1/settings").json()
    assert got["settings"]["idle_timeout_minutes"] == 30
    assert [(issue["code"], issue["path"]) for issue in got["issues"]] == [
        ("W220", "/finding_thresholds/min_time_s"),
        ("W220", "/idle_timeout_minutes"),
    ]
