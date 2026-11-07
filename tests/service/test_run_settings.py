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


def test_a_huge_time_limit_is_kept(tmp_path: Path) -> None:
    (tmp_path / SETTINGS_FILE).write_text(json.dumps({"run_time_limit_s": 1e300}))
    assert read_run_settings(tmp_path).limits.time_s == 1e300
