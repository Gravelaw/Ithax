"""The finding thresholds in ``settings.json`` (spec 3 "Service rules", Finding thresholds;
spec 4 "Finding rules"; spec 1 W220; AKS-135).

``finding_thresholds`` is an object of up to five keys, each taking spec 4's default when
absent; a value that cannot be used, an unknown key, an object of another kind or a file
that cannot be read is refused as a W220 issue at its place in ``settings.json``, and the
default is used for it. These tests are W220's fixture cases: each yields W220 as its only
issue, with ``path`` filled, a message naming the key and a hint.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from lcsim.findings import DEFAULT_THRESHOLDS, Thresholds
from lcsim.service.finding_settings import (
    FINDING_THRESHOLDS,
    SETTINGS_PROBLEM,
    FindingSettings,
    read_finding_settings,
)
from lcsim.service.hardware import SETTINGS_FILE

EXCEPTION_TEXT = re.compile(r"Traceback|Exception|Error\b|ValueError")


def write(folder: Path, document: object) -> None:
    (folder / SETTINGS_FILE).write_text(json.dumps(document), encoding="utf-8")


def only_w220(settings: FindingSettings, path: str) -> dict[str, Any]:
    """The one issue of ``settings``: W220, a warning, at ``path``, in plain language."""
    [item] = settings.issues
    issue: dict[str, Any] = item.as_dict()
    assert issue["code"] == SETTINGS_PROBLEM == "W220"
    assert issue["severity"] == "warning"
    assert issue["component"] is None
    assert issue["path"] == path
    assert SETTINGS_FILE in item.message
    assert item.hint
    assert not EXCEPTION_TEXT.search(item.message + item.hint)
    return issue


def test_the_defaults_are_spec_4_s() -> None:
    assert DEFAULT_THRESHOLDS == Thresholds(
        bottleneck_utilization=0.85,
        idle_utilization=0.30,
        relative_half_width=0.10,
        min_time_s=60.0,
        min_rate_per_s=1 / 3600,
    )


def test_no_settings_file_gives_the_defaults_and_no_issue(tmp_path: Path) -> None:
    assert read_finding_settings(tmp_path) == FindingSettings(DEFAULT_THRESHOLDS, ())


def test_a_file_without_the_key_gives_the_defaults_and_no_issue(tmp_path: Path) -> None:
    write(tmp_path, {"tier": "low", "max_concurrent_runs": 2})
    assert read_finding_settings(tmp_path) == FindingSettings(DEFAULT_THRESHOLDS, ())


def test_every_key_given_is_used(tmp_path: Path) -> None:
    values = {
        "bottleneck_utilization": 0.9,
        "idle_utilization": 0.2,
        "relative_half_width": 0.05,
        "min_time_s": 30,
        "min_rate_per_s": 0.001,
    }
    write(tmp_path, {"tier": "low", FINDING_THRESHOLDS: values})
    settings = read_finding_settings(tmp_path)
    assert settings.issues == ()
    assert settings.thresholds == Thresholds(
        bottleneck_utilization=0.9,
        idle_utilization=0.2,
        relative_half_width=0.05,
        min_time_s=30.0,
        min_rate_per_s=0.001,
    )
    assert isinstance(settings.thresholds.min_time_s, float)


def test_a_key_left_out_keeps_its_default(tmp_path: Path) -> None:
    write(tmp_path, {FINDING_THRESHOLDS: {"bottleneck_utilization": 0.95}})
    settings = read_finding_settings(tmp_path)
    assert settings.issues == ()
    assert settings.thresholds.bottleneck_utilization == 0.95
    assert settings.thresholds.idle_utilization == DEFAULT_THRESHOLDS.idle_utilization


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("bottleneck_utilization", 0),
        ("bottleneck_utilization", 1),
        ("idle_utilization", 0.0),
        ("idle_utilization", 1),
        ("relative_half_width", 1),
        ("relative_half_width", 1e-9),
        ("min_time_s", 0),
        ("min_rate_per_s", 0),
        ("min_time_s", 1e300),
    ],
)
def test_the_ends_of_each_range_are_taken(tmp_path: Path, key: str, value: float) -> None:
    write(tmp_path, {FINDING_THRESHOLDS: {key: value}})
    settings = read_finding_settings(tmp_path)
    assert settings.issues == ()
    assert getattr(settings.thresholds, key) == value


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("bottleneck_utilization", 1.01),
        ("bottleneck_utilization", -0.1),
        ("bottleneck_utilization", True),
        ("bottleneck_utilization", "0.9"),
        ("bottleneck_utilization", None),
        ("idle_utilization", 2),
        ("idle_utilization", [0.3]),
        ("relative_half_width", 0),
        ("relative_half_width", 1.5),
        ("relative_half_width", False),
        ("min_time_s", -1),
        ("min_time_s", {"s": 60}),
        ("min_rate_per_s", -0.001),
        ("min_rate_per_s", 10**400),
    ],
)
def test_a_value_that_cannot_be_used_is_w220_and_its_default_is_used(
    tmp_path: Path, key: str, value: object, caplog: pytest.LogCaptureFixture
) -> None:
    write(tmp_path, {FINDING_THRESHOLDS: {key: value}})
    settings = read_finding_settings(tmp_path)
    issue = only_w220(settings, f"/{FINDING_THRESHOLDS}/{key}")
    assert f"'{key}'" in issue["message"]
    assert getattr(settings.thresholds, key) == getattr(DEFAULT_THRESHOLDS, key)
    assert settings.thresholds == DEFAULT_THRESHOLDS
    assert "W220" in caplog.text and key in caplog.text


def test_one_value_refused_leaves_the_others_used(tmp_path: Path) -> None:
    write(
        tmp_path,
        {FINDING_THRESHOLDS: {"bottleneck_utilization": 1.5, "relative_half_width": 0.2}},
    )
    settings = read_finding_settings(tmp_path)
    only_w220(settings, f"/{FINDING_THRESHOLDS}/bottleneck_utilization")
    assert settings.thresholds.bottleneck_utilization == 0.85
    assert settings.thresholds.relative_half_width == 0.2


def test_an_unknown_key_is_w220_and_changes_nothing(tmp_path: Path) -> None:
    write(tmp_path, {FINDING_THRESHOLDS: {"bottleneck": 0.5}})
    settings = read_finding_settings(tmp_path)
    issue = only_w220(settings, f"/{FINDING_THRESHOLDS}/bottleneck")
    assert "'bottleneck'" in issue["message"]
    assert "bottleneck_utilization" in issue["hint"]
    assert settings.thresholds == DEFAULT_THRESHOLDS


def test_an_unknown_key_s_path_is_escaped_as_a_json_pointer(tmp_path: Path) -> None:
    write(tmp_path, {FINDING_THRESHOLDS: {"a/b~c": 1}})
    only_w220(read_finding_settings(tmp_path), f"/{FINDING_THRESHOLDS}/a~1b~0c")


@pytest.mark.parametrize("value", [0.9, [], "default", None, True])
def test_thresholds_that_are_not_an_object_are_w220(tmp_path: Path, value: object) -> None:
    write(tmp_path, {FINDING_THRESHOLDS: value})
    settings = read_finding_settings(tmp_path)
    issue = only_w220(settings, f"/{FINDING_THRESHOLDS}")
    assert f"'{FINDING_THRESHOLDS}'" in issue["message"]
    assert settings.thresholds == DEFAULT_THRESHOLDS


@pytest.mark.parametrize(
    "raw",
    [b"{nope", b'{"finding_thresholds": {"min_time_s": NaN}}', b"[1, 2]", b"\xff\xfe"],
    ids=["not-json", "nan", "not-an-object", "not-utf8"],
)
def test_a_settings_file_that_cannot_be_read_is_w220_at_the_whole_file(
    tmp_path: Path, raw: bytes
) -> None:
    (tmp_path / SETTINGS_FILE).write_bytes(raw)
    settings = read_finding_settings(tmp_path)
    only_w220(settings, "")
    assert settings.thresholds == DEFAULT_THRESHOLDS


def test_a_settings_path_that_cannot_be_read_as_a_file_is_w220(tmp_path: Path) -> None:
    (tmp_path / SETTINGS_FILE).mkdir()
    settings = read_finding_settings(tmp_path)
    only_w220(settings, "")
    assert settings.thresholds == DEFAULT_THRESHOLDS


def test_the_reading_is_the_same_every_time(tmp_path: Path) -> None:
    write(tmp_path, {FINDING_THRESHOLDS: {"bottleneck_utilization": 2, "min_time_s": 5}})
    assert read_finding_settings(tmp_path) == read_finding_settings(tmp_path)
