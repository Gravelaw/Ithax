"""The run settings in ``settings.json`` (spec 3 "Run queue"; spec 4 "Limits"; AKS-112):
``max_concurrent_runs``, ``run_time_limit_s`` and ``run_memory_limit_bytes``, each taking its
default when absent or not of its kind."""

import json
from pathlib import Path

import pytest

from lcsim.runs.limits import DEFAULT_TIME_LIMIT_S, default_memory_limit
from lcsim.service.hardware import SETTINGS_FILE
from lcsim.service.run_settings import RunSettings, read_run_settings


def test_defaults_without_a_settings_file(tmp_path: Path) -> None:
    settings = read_run_settings(tmp_path)
    assert settings == RunSettings()
    assert settings.max_concurrent_runs == 1
    assert settings.limits.time_s == DEFAULT_TIME_LIMIT_S
    assert settings.limits.memory_bytes == default_memory_limit()


def test_values_in_the_file_are_used(tmp_path: Path) -> None:
    (tmp_path / SETTINGS_FILE).write_text(
        json.dumps(
            {
                "tier": "low",
                "max_concurrent_runs": 3,
                "run_time_limit_s": 1.5,
                "run_memory_limit_bytes": 2**30,
            }
        )
    )
    settings = read_run_settings(tmp_path)
    assert settings.max_concurrent_runs == 3
    assert settings.limits.time_s == 1.5
    assert settings.limits.memory_bytes == 2**30


@pytest.mark.parametrize(
    "values",
    [
        {"max_concurrent_runs": 0},
        {"max_concurrent_runs": 1.5},
        {"max_concurrent_runs": True},
        {"max_concurrent_runs": "2"},
        {"run_time_limit_s": 0},
        {"run_time_limit_s": -1},
        {"run_time_limit_s": True},
        {"run_time_limit_s": "10"},
        {"run_memory_limit_bytes": 0},
        {"run_memory_limit_bytes": 1.5},
        {"run_memory_limit_bytes": False},
    ],
)
def test_a_value_of_another_kind_takes_its_default_and_is_logged(
    tmp_path: Path, values: dict[str, object], caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / SETTINGS_FILE).write_text(json.dumps(values))
    assert read_run_settings(tmp_path) == RunSettings()
    assert next(iter(values)) in caplog.text


@pytest.mark.parametrize("text", ["{", "[]", "\udcff"])
def test_a_file_that_cannot_be_read_gives_the_defaults(tmp_path: Path, text: str) -> None:
    (tmp_path / SETTINGS_FILE).write_bytes(text.encode("utf-8", "surrogateescape"))
    assert read_run_settings(tmp_path) == RunSettings()


def test_a_huge_time_limit_takes_the_default(tmp_path: Path) -> None:
    """Above 7 days (review of PR #36; it was kept before)."""
    (tmp_path / SETTINGS_FILE).write_text(json.dumps({"run_time_limit_s": 1e300}))
    assert read_run_settings(tmp_path).limits.time_s == DEFAULT_TIME_LIMIT_S


@pytest.mark.parametrize("value", ["1e999", "NaN", "Infinity", '"\\ud800"'])
def test_a_settings_file_that_cannot_be_written_back_gives_the_defaults(
    tmp_path: Path, value: str
) -> None:
    """Review of PR #36: one strict reader for every JSON file read from disk."""
    (tmp_path / SETTINGS_FILE).write_text(
        f'{{"max_concurrent_runs": 2, "run_time_limit_s": {value}}}'
    )
    assert read_run_settings(tmp_path) == RunSettings()


BAD_WHOLE: list[object] = [10**400, -1, 0, 1.5, 2.0, True, "2", None, [2]]


@pytest.mark.parametrize("key", ["max_concurrent_runs", "run_memory_limit_bytes"])
@pytest.mark.parametrize("value", BAD_WHOLE)
def test_a_whole_setting_of_another_kind_or_out_of_range_takes_its_default(
    tmp_path: Path, key: str, value: object
) -> None:
    """Review of PR #36: every number read from disk is typed and bounded, and reading it
    never raises."""
    (tmp_path / SETTINGS_FILE).write_text(json.dumps({key: value}))
    assert read_run_settings(tmp_path) == RunSettings()


@pytest.mark.parametrize("value", [10**400, -(10**400), -1, 0, 604_801, True, "10", None])
def test_a_time_limit_of_another_kind_or_out_of_range_takes_its_default(
    tmp_path: Path, value: object
) -> None:
    (tmp_path / SETTINGS_FILE).write_text(json.dumps({"run_time_limit_s": value}))
    assert read_run_settings(tmp_path) == RunSettings()


def test_the_bounds_themselves_are_taken(tmp_path: Path) -> None:
    (tmp_path / SETTINGS_FILE).write_text(
        json.dumps(
            {
                "max_concurrent_runs": 64,
                "run_time_limit_s": 604_800,
                "run_memory_limit_bytes": 2**63 - 1,
            }
        )
    )
    settings = read_run_settings(tmp_path)
    assert settings.max_concurrent_runs == 64
    assert settings.limits.time_s == 604_800.0
    assert settings.limits.memory_bytes == 2**63 - 1
    (tmp_path / SETTINGS_FILE).write_text(json.dumps({"max_concurrent_runs": 65}))
    assert read_run_settings(tmp_path).max_concurrent_runs == 1


def test_the_service_starts_with_a_settings_file_holding_huge_numbers(tmp_path: Path) -> None:
    from starlette.testclient import TestClient

    from lcsim.service.app import create_app
    from lcsim.service.config import ServiceConfig
    from lcsim.service.hardware import Hardware
    from service.service_support import AUTH, BASE_URL, PORT, TOKEN

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    huge = "1" + "0" * 400
    text = '{"tier": "low", "max_concurrent_runs": ' + huge + ', "run_time_limit_s": ' + huge + "}"
    (config_dir / SETTINGS_FILE).write_text(text)
    config = ServiceConfig(
        config_dir=config_dir,
        data_dir=tmp_path / "data",
        port=PORT,
        token=TOKEN,
        hardware=Hardware(cores=4, memory=8 * 1024**3, graphics=()),
    )
    with TestClient(create_app(config), base_url=BASE_URL, headers=AUTH) as client:
        assert client.get("/v1/system").status_code == 200
