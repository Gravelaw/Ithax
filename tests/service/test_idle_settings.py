"""The idle timeout in ``settings.json`` (spec 3 "Service rules", Lifetime; spec 1 W220;
owner decision B5, AKS-141).

``idle_timeout_minutes`` is a whole number from 1 to 10,080, default 30. A key that is absent
takes the default without an issue; a value that cannot be used is a W220 issue at
``/idle_timeout_minutes`` and the default is used. A file that cannot be read gives the
default; its W220 issue is the finding thresholds' (at ``""``), so it is not given twice.
"""

import json
import logging
import re
from pathlib import Path

import pytest

from lcsim.service.config import DEFAULT_IDLE_TIMEOUT_S
from lcsim.service.hardware import SETTINGS_FILE
from lcsim.service.idle_settings import (
    DEFAULT_IDLE_MINUTES,
    IDLE_TIMEOUT,
    MAX_IDLE_MINUTES,
    IdleSettings,
    read_idle_settings,
)

EXCEPTION_TEXT = re.compile(r"Traceback|Exception|Error\b|ValueError")


def write(folder: Path, document: object) -> None:
    (folder / SETTINGS_FILE).write_text(json.dumps(document), encoding="utf-8")


def test_the_default_is_30_minutes_and_the_bounds_1_to_10080() -> None:
    assert IDLE_TIMEOUT == "idle_timeout_minutes"
    assert DEFAULT_IDLE_MINUTES == 30
    assert DEFAULT_IDLE_TIMEOUT_S == 30 * 60
    assert MAX_IDLE_MINUTES == 10_080 == 7 * 24 * 60


def test_no_settings_file_gives_the_default_and_no_issue(tmp_path: Path) -> None:
    assert read_idle_settings(tmp_path) == IdleSettings(30, ())


def test_an_absent_key_gives_the_default_and_no_issue(tmp_path: Path) -> None:
    write(tmp_path, {"tier": "low"})
    assert read_idle_settings(tmp_path) == IdleSettings(30, ())


@pytest.mark.parametrize("minutes", [1, 5, 30, 10_080])
def test_a_whole_number_in_range_is_used(tmp_path: Path, minutes: int) -> None:
    write(tmp_path, {IDLE_TIMEOUT: minutes})
    settings = read_idle_settings(tmp_path)
    assert settings == IdleSettings(minutes, ())
    assert settings.timeout_s == minutes * 60


@pytest.mark.parametrize(
    "value", [0, -1, 10_081, 1.5, 30.0, True, False, "30", None, [30], {"minutes": 30}]
)
def test_a_value_that_cannot_be_used_is_w220_and_the_default(
    tmp_path: Path, value: object, caplog: pytest.LogCaptureFixture
) -> None:
    write(tmp_path, {IDLE_TIMEOUT: value})
    with caplog.at_level(logging.WARNING):
        settings = read_idle_settings(tmp_path)
    assert settings.minutes == 30
    [item] = settings.issues
    issue = item.as_dict()
    assert issue["code"] == "W220"
    assert issue["severity"] == "warning"
    assert issue["component"] is None
    assert issue["path"] == "/idle_timeout_minutes"
    assert IDLE_TIMEOUT in item.message and SETTINGS_FILE in item.message
    assert "30" in item.message
    assert "1 to 10,080" in item.hint
    assert not EXCEPTION_TEXT.search(item.message + item.hint)
    assert "W220" in caplog.text and "/idle_timeout_minutes" in caplog.text


@pytest.mark.parametrize("text", ["{not json", "[1, 2]", '{"idle_timeout_minutes": NaN}'])
def test_a_file_that_cannot_be_read_gives_the_default_without_its_own_issue(
    tmp_path: Path, text: str
) -> None:
    (tmp_path / SETTINGS_FILE).write_text(text, encoding="utf-8")
    assert read_idle_settings(tmp_path) == IdleSettings(30, ())
