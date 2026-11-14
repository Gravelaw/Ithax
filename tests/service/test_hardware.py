"""Hardware detection, tiers and ``GET /v1/system`` (spec 3 "Hardware tiers"; AKS-110)."""

import ctypes
import json
import os
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from ithax.service import hardware
from ithax.service.hardware import (
    SETTINGS_FILE,
    TIERS,
    Hardware,
    active_tier,
    detect_hardware,
    graphics_vendors,
    physical_memory,
    tier_for,
    tier_workers,
    usable_cores,
)

GIB = 1024**3


# --- cores ----------------------------------------------------------------------------


def test_usable_cores_uses_process_cpu_count_when_there(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "process_cpu_count", lambda: 6, raising=False)
    assert usable_cores() == 6


def test_usable_cores_uses_the_affinity_mask_before_python_3_13(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(os, "process_cpu_count", raising=False)
    monkeypatch.setattr(os, "sched_getaffinity", lambda _pid: {0, 1, 2}, raising=False)
    assert usable_cores() == 3


def test_usable_cores_falls_back_to_cpu_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(os, "process_cpu_count", raising=False)
    monkeypatch.delattr(os, "sched_getaffinity", raising=False)
    monkeypatch.setattr(os, "cpu_count", lambda: None)
    assert usable_cores() == 1
    monkeypatch.setattr(os, "cpu_count", lambda: 12)
    assert usable_cores() == 12


def test_usable_cores_on_this_machine() -> None:
    assert usable_cores() >= 1


# --- memory ---------------------------------------------------------------------------


class FakeKernel32:
    def __init__(self, total: int, succeeds: bool = True) -> None:
        self.total = total
        self.succeeds = succeeds

    def GlobalMemoryStatusEx(self, reference: Any) -> int:
        status = reference._obj
        assert status.dwLength == ctypes.sizeof(status)
        status.ullTotalPhys = self.total
        return 1 if self.succeeds else 0


class FakeWindll:
    def __init__(self, kernel32: FakeKernel32) -> None:
        self.kernel32 = kernel32


def test_windows_memory_comes_from_global_memory_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ctypes, "windll", FakeWindll(FakeKernel32(16 * GIB)), raising=False)
    assert physical_memory("win32") == 16 * GIB


def test_windows_memory_is_unknown_when_the_call_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ctypes, "windll", FakeWindll(FakeKernel32(0, False)), raising=False)
    assert physical_memory("win32") is None


def test_windows_memory_is_unknown_without_windll(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(ctypes, "windll", raising=False)
    assert physical_memory("win32") is None


def test_memory_elsewhere_comes_from_sysconf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware, "system_memory", lambda: 8 * GIB)
    assert physical_memory("linux") == 8 * GIB
    assert physical_memory("darwin") == 8 * GIB


def test_memory_on_this_machine() -> None:
    memory = physical_memory()
    assert memory is None or memory > 0


# --- graphics -------------------------------------------------------------------------


def card(drm: Path, name: str, vendor: str | bytes) -> None:
    device = drm / name / "device"
    device.mkdir(parents=True)
    if isinstance(vendor, bytes):
        (device / "vendor").write_bytes(vendor)
    else:
        (device / "vendor").write_text(vendor, encoding="ascii")


def test_graphics_vendors_are_read_from_drm(tmp_path: Path) -> None:
    card(tmp_path, "card0", "0x8086\n")
    card(tmp_path, "card1", "0x10DE\n")
    card(tmp_path, "card2", "0x10de\n")
    card(tmp_path, "card3", "0x1002\n")
    card(tmp_path, "card4", "0x1af4\n")
    card(tmp_path, "card5", "\n")
    card(tmp_path, "card6", b"\xff\xfe")
    (tmp_path / "card7").mkdir()  # no device folder
    (tmp_path / "renderD128").mkdir()
    assert graphics_vendors(tmp_path) == ("0x1af4", "amd", "intel", "nvidia")


def test_no_display_device_is_an_empty_list(tmp_path: Path) -> None:
    assert graphics_vendors(tmp_path) == ()


def test_graphics_are_unknown_without_drm(tmp_path: Path) -> None:
    assert graphics_vendors(tmp_path / "missing") is None


def test_detect_hardware_reads_this_machine() -> None:
    found = detect_hardware()
    assert found.cores == usable_cores()
    assert found.memory == physical_memory()
    assert found.graphics == graphics_vendors()


# --- tiers ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cores", "memory_gib", "tier"),
    [
        (16, 31.4, "high"),  # a 32 GB machine reports a little less
        (32, 64, "high"),
        (16, 16, "mid"),
        (8, 15.5, "mid"),
        (12, 64, "mid"),
        (8, 14, "low"),  # below 90% of 16 GB
        (4, 8, "low"),
        (2, 4, "low"),  # below the low tier is still low
        (7, 64, "low"),
    ],
)
def test_the_tier_is_the_highest_reached(cores: int, memory_gib: float, tier: str) -> None:
    assert tier_for(Hardware(cores, int(memory_gib * GIB), None)) == tier


def test_unknown_memory_is_the_low_tier() -> None:
    assert tier_for(Hardware(64, None, ("nvidia",))) == "low"


def test_graphics_do_not_set_the_tier() -> None:
    assert tier_for(Hardware(8, 16 * GIB, ("nvidia",))) == tier_for(Hardware(8, 16 * GIB, None))


def test_the_tiers_are_spec_0s() -> None:
    assert [(tier.name, tier.cores, tier.memory_gb) for tier in TIERS] == [
        ("high", 16, 32),
        ("mid", 8, 16),
        ("low", 4, 8),
    ]


@pytest.mark.parametrize(
    ("tier", "cores", "workers"),
    [
        ("low", 16, 4),
        ("mid", 16, 8),
        ("high", 16, 16),
        ("high", 6, 6),
        ("low", 2, 2),
        ("low", 0, 1),
    ],
)
def test_workers_are_the_tiers_cores_at_most_the_machines(
    tier: hardware.TierName, cores: int, workers: int
) -> None:
    assert tier_workers(tier, cores) == workers


# --- the tier of the first start --------------------------------------------------------


def test_the_first_start_stores_the_detected_tier(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    assert active_tier(config_dir, Hardware(8, 16 * GIB, None)) == "mid"
    assert json.loads((config_dir / SETTINGS_FILE).read_text(encoding="utf-8")) == {"tier": "mid"}


def test_later_starts_keep_the_stored_tier(tmp_path: Path) -> None:
    active_tier(tmp_path, Hardware(4, 8 * GIB, None))
    assert active_tier(tmp_path, Hardware(32, 64 * GIB, None)) == "low"


def test_other_settings_are_kept(tmp_path: Path) -> None:
    (tmp_path / SETTINGS_FILE).write_text(json.dumps({"max_concurrent_runs": 2}), "utf-8")
    assert active_tier(tmp_path, Hardware(16, 32 * GIB, None)) == "high"
    stored = json.loads((tmp_path / SETTINGS_FILE).read_text(encoding="utf-8"))
    assert stored == {"max_concurrent_runs": 2, "tier": "high"}


@pytest.mark.parametrize("text", ["{not json", "[1, 2]", '{"tier": "huge"}', '{"tier": 3}'])
def test_an_unusable_settings_file_gets_the_detected_tier(tmp_path: Path, text: str) -> None:
    (tmp_path / SETTINGS_FILE).write_text(text, encoding="utf-8")
    assert active_tier(tmp_path, Hardware(8, 16 * GIB, None)) == "mid"
    assert json.loads((tmp_path / SETTINGS_FILE).read_text(encoding="utf-8"))["tier"] == "mid"


# --- GET /v1/system ---------------------------------------------------------------------


def test_get_system_reports_hardware_tier_and_workers(client: TestClient) -> None:
    response = client.get("/v1/system")
    assert response.status_code == 200
    assert response.json() == {
        "cores": 8,
        "memory": 16 * GIB,
        "graphics": ["intel"],
        "tier": "mid",
        "workers": 8,
    }


def test_get_system_with_unknown_graphics_and_memory(tmp_path: Path) -> None:
    from ithax.service.app import create_app
    from ithax.service.config import ServiceConfig
    from service.service_support import AUTH, BASE_URL, PORT, TOKEN

    config = ServiceConfig(
        config_dir=tmp_path,
        data_dir=tmp_path,
        port=PORT,
        token=TOKEN,
        hardware=Hardware(cores=2, memory=None, graphics=None),
    )
    with TestClient(create_app(config), base_url=BASE_URL, headers=AUTH) as client:
        assert client.get("/v1/system").json() == {
            "cores": 2,
            "memory": None,
            "graphics": None,
            "tier": "low",
            "workers": 2,
        }


@pytest.mark.parametrize("text", ['{"other": "\\ud800"}', '{"other": 1e999}', '{"other": NaN}'])
def test_a_settings_file_that_cannot_be_written_back_is_replaced(tmp_path: Path, text: str) -> None:
    """Review of PR #36: such a file made the first start raise while storing the tier."""
    (tmp_path / SETTINGS_FILE).write_text(text)
    hardware = Hardware(cores=8, memory=16 * 1024**3, graphics=())
    assert active_tier(tmp_path, hardware) == "mid"
    assert json.loads((tmp_path / SETTINGS_FILE).read_text()) == {"tier": "mid"}
