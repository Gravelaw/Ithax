"""``manifest.json`` (spec 1 "Run folder and results"; AKS-103).

The fields, in spec 1 order: ``run_id``, ``project_id``, ``experiment_id``,
``scenario_ids``, ``state``, ``created``, ``started``, ``ended``, ``target``, ``host``,
``client``, ``engine`` ``{name, version}``, ``generator`` ``{name, numpy_version}`` (from
``lcsim.model.streams.generator_info()``), ``product_version``, ``format_version``,
``seed``, ``fraction``, ``data_files``, and ``error`` on a failed run only.

Times are ISO 8601 UTC to the millisecond, ending in ``Z``. ``fraction`` is the run's
progress: 0 when queued, then each progress fraction, 1 at ``done``. ``data_files`` stays
empty until M6.

The file is written through a temporary file in the same folder and ``os.replace``, so a
reader sees the old manifest or the new one, never part of one. ``ManifestWriter`` writes
on every update (a state change) and at most once a second on progress.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import lcsim
from lcsim.model.streams import generator_info

__all__ = [
    "MANIFEST_FILE",
    "MANIFEST_KEYS",
    "PROGRESS_INTERVAL_S",
    "ManifestWriter",
    "new_manifest",
    "read_manifest",
    "utc_text",
    "write_manifest",
]

MANIFEST_FILE = "manifest.json"

#: The fields every manifest has, in spec 1 order; ``error`` follows on a failed run.
MANIFEST_KEYS = (
    "run_id",
    "project_id",
    "experiment_id",
    "scenario_ids",
    "state",
    "created",
    "started",
    "ended",
    "target",
    "host",
    "client",
    "engine",
    "generator",
    "product_version",
    "format_version",
    "seed",
    "fraction",
    "data_files",
)
_OPTIONAL_KEYS = ("error",)

#: The shortest time between two progress writes (spec 1: at most once a second).
PROGRESS_INTERVAL_S = 1.0


def utc_text(moment: datetime) -> str:
    """``moment`` as ISO 8601 UTC to the millisecond: ``2026-11-06T18:05:09.123Z``."""
    return moment.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_manifest(
    *,
    run_id: str,
    project_id: str | None,
    experiment_id: str | None,
    scenario_ids: Sequence[str],
    created: datetime,
    host: str,
    client: str,
    engine_name: str,
    engine_version: str,
    format_version: str,
    seed: int | None,
) -> dict[str, Any]:
    """The manifest of a run just created: ``queued``, on the ``local`` target, with no
    progress and no data files. An optimization run has no experiment and draws nothing,
    so its ``experiment_id`` and ``seed`` are ``None`` and its ``scenario_ids`` empty
    (AKS-108)."""
    info = generator_info()
    return {
        "run_id": run_id,
        "project_id": project_id,
        "experiment_id": experiment_id,
        "scenario_ids": list(scenario_ids),
        "state": "queued",
        "created": utc_text(created),
        "started": None,
        "ended": None,
        "target": "local",
        "host": host,
        "client": client,
        "engine": {"name": engine_name, "version": engine_version},
        "generator": {"name": info.name, "numpy_version": info.numpy_version},
        "product_version": lcsim.__version__,
        "format_version": format_version,
        "seed": seed,
        "fraction": 0.0,
        "data_files": [],
    }


def write_manifest(folder: Path, manifest: dict[str, Any]) -> None:
    """Writes ``folder/manifest.json`` atomically; a value JSON cannot hold (NaN) raises
    ``ValueError`` and leaves the old file as it was."""
    text = json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    handle, temporary = tempfile.mkstemp(dir=folder, prefix=".manifest-", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, folder / MANIFEST_FILE)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def read_manifest(folder: Path) -> dict[str, Any]:
    """The manifest in ``folder``."""
    data: dict[str, Any] = json.loads((folder / MANIFEST_FILE).read_text(encoding="utf-8"))
    return data


class ManifestWriter:
    """Keeps a run's manifest and writes it: on every ``update`` at once, and on
    ``progress`` at most once every ``interval`` seconds of ``clock``."""

    def __init__(
        self,
        folder: Path,
        manifest: dict[str, Any],
        *,
        clock: Callable[[], float] = time.monotonic,
        interval: float = PROGRESS_INTERVAL_S,
    ) -> None:
        self._folder = folder
        self._data = dict(manifest)
        self._clock = clock
        self._interval = interval
        self._last_progress: float | None = None
        write_manifest(folder, self._data)

    @property
    def data(self) -> dict[str, Any]:
        """A copy of the manifest as last set."""
        return dict(self._data)

    def update(self, **fields: object) -> None:
        """Sets ``fields`` and writes the manifest; a field spec 1 does not list raises
        ``KeyError``."""
        for key in fields:
            if key not in MANIFEST_KEYS and key not in _OPTIONAL_KEYS:
                raise KeyError(f"manifest.json has no field {key!r}")
        self._data.update(fields)
        write_manifest(self._folder, self._data)

    def progress(self, fraction: float) -> bool:
        """Sets ``fraction``; writes the manifest, and returns ``True``, when no progress
        was written in the last ``interval`` seconds."""
        self._data["fraction"] = fraction
        now = self._clock()
        if self._last_progress is not None and now - self._last_progress < self._interval:
            return False
        self._last_progress = now
        write_manifest(self._folder, self._data)
        return True
