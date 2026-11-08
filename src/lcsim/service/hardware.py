"""Hardware detection and tiers (spec 3 "Hardware tiers"; spec 0 "Platform and hardware").

On first start the service detects cores, memory and graphics and sets the tier
(AKS-110, proposed default, owner to confirm):

- ``cores``: the logical processors this process may use;
- ``memory``: physical memory in bytes, from ``os.sysconf`` on Linux and macOS and from
  ``GlobalMemoryStatusEx`` on Windows; ``None`` where neither works;
- ``graphics``: the vendors of the display devices under ``/sys/class/drm`` on Linux;
  ``None`` where that cannot be read (Windows, macOS).

The tier is the highest of ``high``, ``mid`` and ``low`` whose cores and memory the
machine both reaches, memory counting as reached at 90% of the nominal size; ``low``
otherwise, and when memory is unknown. Graphics does not set the tier in Phase 1. The tier
of the first start is stored in ``settings.json`` in the configuration folder.

Everything here is platform-neutral: no code assumes ``/proc``, ``fork`` or a Windows API
without a guard.
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, cast

from lcsim.runs.limits import system_memory

__all__ = [
    "SETTINGS_FILE",
    "TIERS",
    "Hardware",
    "Tier",
    "TierName",
    "active_tier",
    "detect_hardware",
    "graphics_vendors",
    "physical_memory",
    "tier_for",
    "tier_workers",
    "usable_cores",
]

_log = logging.getLogger(__name__)

TierName = Literal["low", "mid", "high"]

#: The settings file in the configuration folder (spec 3 "Hardware tiers").
SETTINGS_FILE = "settings.json"

_GIB = 1024**3

# Memory counts as reached at this share of the nominal size: the operating system keeps
# some memory for itself, so a 16 GB machine reports less than 16 GiB.
_MEMORY_SHARE = 0.9

# PCI vendor ids of the graphics makers spec 0 names, and AMD.
_VENDORS: Mapping[str, str] = MappingProxyType(
    {"0x10de": "nvidia", "0x8086": "intel", "0x1002": "amd"}
)


@dataclass(frozen=True)
class Tier:
    """A hardware tier of spec 0: its cores and its memory in GB."""

    name: TierName
    cores: int
    memory_gb: int


#: Spec 0 "Hardware tiers", highest first: low 4 cores and 8 GB, mid 8 and 16, high (the
#: development machine) 16 and 32.
TIERS: tuple[Tier, ...] = (Tier("high", 16, 32), Tier("mid", 8, 16), Tier("low", 4, 8))


@dataclass(frozen=True)
class Hardware:
    """What the service found: usable cores, physical memory in bytes (``None`` when
    unknown) and graphics vendors (``None`` when they cannot be read)."""

    cores: int
    memory: int | None
    graphics: tuple[str, ...] | None


def usable_cores() -> int:
    """The logical processors this process may use: ``os.process_cpu_count`` (Python
    3.13), else the affinity mask where the platform has one (Linux), else
    ``os.cpu_count``; at least 1."""
    counter = cast("Callable[[], int | None] | None", getattr(os, "process_cpu_count", None))
    if counter is not None:
        count = counter()
    elif hasattr(os, "sched_getaffinity"):
        count = len(os.sched_getaffinity(0))
    else:
        count = os.cpu_count()
    return max(1, count or 1)


class _MemoryStatus(ctypes.Structure):
    """Windows ``MEMORYSTATUSEX``."""

    _fields_ = (
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    )


def _windows_memory() -> int | None:
    """Physical memory from ``GlobalMemoryStatusEx``, or ``None`` when the call fails."""
    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(_MemoryStatus)
    # ctypes.windll exists only on Windows; read it by name so the module imports anywhere.
    kernel32: Any = getattr(ctypes, "windll").kernel32  # noqa: B009
    if not kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.ullTotalPhys) or None


def physical_memory(platform: str | None = None) -> int | None:
    """The machine's physical memory in bytes, or ``None`` where it cannot be read."""
    if (sys.platform if platform is None else platform) == "win32":
        try:
            return _windows_memory()
        except (AttributeError, OSError):
            return None
    return system_memory()


def graphics_vendors(drm: Path = Path("/sys/class/drm")) -> tuple[str, ...] | None:
    """The vendors of the display devices under ``drm`` (Linux), sorted and without
    repeats: ``nvidia``, ``intel``, ``amd``, or another PCI vendor id as written;
    ``None`` when ``drm`` is not there (Windows, macOS)."""
    if not drm.is_dir():
        return None
    found: set[str] = set()
    for card in drm.glob("card*"):
        try:
            vendor = (card / "device" / "vendor").read_text(encoding="ascii").strip().lower()
        except (OSError, UnicodeDecodeError):
            continue
        if vendor:
            found.add(_VENDORS.get(vendor, vendor))
    return tuple(sorted(found))


def detect_hardware() -> Hardware:
    """Cores, memory and graphics of this machine."""
    return Hardware(usable_cores(), physical_memory(), graphics_vendors())


def tier_for(hardware: Hardware) -> TierName:
    """The highest tier whose cores and memory ``hardware`` both reaches; ``low`` below
    ``mid`` and when memory is unknown."""
    if hardware.memory is not None:
        for tier in TIERS[:-1]:
            enough_memory = hardware.memory >= _MEMORY_SHARE * tier.memory_gb * _GIB
            if hardware.cores >= tier.cores and enough_memory:
                return tier.name
    return "low"


def tier_workers(tier: TierName, cores: int) -> int:
    """``workers`` for a run (spec 3 "Run queue"): the tier's cores, at most ``cores``."""
    nominal = next(entry.cores for entry in TIERS if entry.name == tier)
    return max(1, min(nominal, cores))


def active_tier(config_dir: Path, hardware: Hardware) -> TierName:
    """The active tier: ``tier`` in ``settings.json`` when it holds one, else the tier of
    ``hardware``, which is then stored there (spec 3: set on first start). Other keys of
    the file are kept; a file that cannot be read is replaced, and that is logged."""
    path = config_dir / SETTINGS_FILE
    settings: dict[str, Any] = {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        loaded = {}
    except (OSError, ValueError):
        _log.warning("%s cannot be read; the tier is detected again.", path)
        loaded = {}
    if isinstance(loaded, dict):
        settings = loaded
    stored = settings.get("tier")
    if stored in [tier.name for tier in TIERS]:
        return cast("TierName", stored)
    settings["tier"] = tier_for(hardware)
    config_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return cast("TierName", settings["tier"])
