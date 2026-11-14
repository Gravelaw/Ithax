"""Spec 3 "Performance targets" (proposed, measured on the low tier; M9 measured, the owner
confirms; AKS-121): "Canvas stays responsive with 200 components: an end-to-end test adds
200 components by API and selecting a block paints within 100 ms", with what the interface
adds to the service's own targets.

Run with ``taskset -c 0-3 pytest -m perf`` (guide "Performance measurement protocol"), after
``npm ci`` and ``npm run build`` in ``ui/``, with Chromium installed for Playwright
(``PLAYWRIGHT_BROWSERS_PATH`` or ``ITHAX_CHROMIUM``, ``ui/README.md``).

- **Selecting a block paints within 100 ms.** A real ``python -m ithax.service`` serves the
  built interface (``ui/dist``, its default); ``ui/perf/canvas.perf.ts`` (Playwright with
  Chromium) writes a model of 200 components by API, opens the Canvas on it and clicks 12
  drawn blocks in turn, each timed from its ``pointerdown`` to the first frame painted with
  the block drawn selected and named in the side panel. The largest of the 12 must be under
  100 ms; the median and the first are recorded too, and the time the Canvas took to open.
- **The service with the interface served:** ready (the first ``200`` from ``GET /v1/system``
  after the start, as ``test_service.py`` times it) and its idle memory, 5 s after the page
  has loaded the interface and the 200-component model (the service and every process it
  started), against spec 3's 5 s and 300 MB.
- **The interface's size:** each file the build wrote (``ui/dist``), and the JavaScript and
  CSS bundles raw and gzipped (level 9, as a server would send them; the service sends them
  uncompressed, over loopback).
"""

import gzip
import json
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from ithax.service.discovery import read_service_file
from perf.test_service import IDLE_TARGET_BYTES, READY_TARGET_S, Service, machine
from perf.test_three_machine_line import max_rss_bytes, mib

pytestmark = pytest.mark.perf

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "ui"
DIST = UI / "dist"

PAINT_TARGET_MS = 100.0


def bundle() -> dict[str, Any]:
    """The built interface's files: the total, and each JavaScript and CSS file raw and
    gzipped."""
    files = [path for path in DIST.rglob("*") if path.is_file()]
    code = sorted(path for path in files if path.suffix in (".js", ".css"))
    return {
        "dist_files": len(files),
        "dist_bytes": sum(path.stat().st_size for path in files),
        "bundles": {
            path.relative_to(DIST).as_posix(): {
                "bytes": path.stat().st_size,
                "gzip_bytes": len(gzip.compress(path.read_bytes(), compresslevel=9)),
            }
            for path in code
        },
    }


def test_selecting_a_block_on_a_200_component_canvas_paints_within_100_ms(
    tmp_path: Path, perf_record: Callable[[dict[str, Any]], None]
) -> None:
    assert (DIST / "index.html").is_file(), "run `npm run build` in ui/ first"
    npx = shutil.which("npx")
    assert npx is not None, "the check needs Node 22 and npm (npx) on PATH"
    out = tmp_path / "canvas.json"
    running = Service(tmp_path)
    try:
        info = read_service_file(running.config_dir)
        assert info is not None
        environment = {
            **os.environ,
            "ITHAX_PERF_ORIGIN": f"http://127.0.0.1:{info.port}",
            "ITHAX_PERF_TOKEN": info.token,
            "ITHAX_PERF_OUT": str(out),
        }
        finished = subprocess.run(
            [npx, "playwright", "test", "-c", "playwright.perf.config.ts", "--trace", "off"],
            cwd=UI,
            env=environment,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        idle = running.idle_memory()
    finally:
        running.stop()
    assert out.is_file(), finished.stdout[-4000:] + finished.stderr[-4000:]
    canvas = json.loads(out.read_text(encoding="utf-8"))
    record = {
        "check": "Canvas of 200 components: pointerdown to the painted selection, 12 blocks",
        **canvas,
        "target_ms": PAINT_TARGET_MS,
        "service_ready_s": round(running.ready_s, 3),
        "service_ready_target_s": READY_TARGET_S,
        "service_idle_after_canvas_mib": None if idle is None else mib(idle),
        "service_idle_target_bytes": IDLE_TARGET_BYTES,
        **bundle(),
        "max_rss_self_mib": mib(max_rss_bytes("self")),
        "max_rss_children_mib": mib(max_rss_bytes("children")),
        **machine(),
    }
    perf_record(record)
    assert finished.returncode == 0, finished.stdout[-4000:] + finished.stderr[-4000:]
    assert canvas["max_ms"] < PAINT_TARGET_MS, record
    assert running.ready_s < READY_TARGET_S, record
    assert idle is not None and idle < IDLE_TARGET_BYTES, record
