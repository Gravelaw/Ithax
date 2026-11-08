# Performance at M9: the canvas with 200 components, and the interface served

Measured 2026-11-08 for AKS-121 under the Build guide's "Performance measurement protocol".
**Status: measured, owner to confirm on the low tier.** This container is not the owner's
low-tier machine. The owner confirms each target by running the same command on a machine
capped to 4 cores and 8 GB and recording the result in `docs/DECISIONS.md` (AKS-82).

## Question

Spec 3 "Performance targets" (proposed, measured on the low tier): "Canvas stays responsive
with 200 components: an end-to-end test adds 200 components by API and selecting a block
paints within 100 ms". And, for the M9 close: how large is the interface, and does the
service still meet its ready and idle targets with the interface served (AKS-138 reading 19,
AKS-120 reading 16)?

## Finding

The canvas target is met on 4 cores with a wide margin: the slowest of 12 selections took
30 to 36 ms in four runs, the median 20 to 22 ms. The first selection of a run is usually the
slowest. The M3 and M6 targets are met again in the same session, unchanged from perf-M6.

| Target (spec 3, proposed) | Measured, Python 3.13.18, Chromium 153.0.8010.12 | Met |
| --- | --- | --- |
| Selecting a block on a 200-component canvas paints within 100 ms (largest of 12) | 34.7 ms (median 20.8, first 34.7) in the full `pytest -m perf` run; 30.3, 30.0 and 36.4 ms (medians 19.6, 21.8, 20.0) in three runs of the check alone | yes, by about 65 ms |
| Service ready within 5 s, the interface served | 1.476 s (this check); 1.403, 1.444, 1.393 s (`test_service.py`, three starts) | yes |
| Under 300 MB idle, 5 s after the page loaded the 200-component canvas | 182.8 MiB (192 MB) | yes |
| Validation of a 200-component model within 200 ms (M6 check, rerun) | median 0.076 s, max 0.168 s | yes |
| Under 300 MB idle after the coffee shop's run (M6 check, rerun) | 251.0 MiB (263 MB) | yes |

- **Selecting a block** (`tests/perf/test_interface.py`, `ui/perf/canvas.perf.ts`). The
  service is a real `python -m lcsim.service` serving `ui/dist` (its default). The model is a
  source, 198 servers in a line and a sink, placed in a grid of 20 columns, written by API with
  one `PUT .../model`. The Canvas opens on it at 1,280 × 800, fitted to the view, and draws
  160 of the 200 blocks (React Flow draws only the blocks in view; the model holds all 200).
  Twelve drawn blocks, spread over those drawn (`s2`, `s15`, … `s184`), are clicked in turn.
  One selection is timed in the page from the click's `pointerdown` time stamp to the first
  frame painted after the block is drawn selected and the side panel's heading names it: the
  frame's `requestAnimationFrame` callback, then a message posted from it, which the browser
  delivers after that frame is painted. The largest of the 12 is the measurement (rule 5,
  owner to confirm). The Canvas took 1.85 to 2.01 s from opening the address to all blocks
  drawn with "No problems".
- **The interface's size** (`ui/dist`, 16 files, 1,628,919 bytes): JavaScript 1,283,279 bytes,
  395,924 gzipped (level 9); CSS 53,649 bytes, 9,034 gzipped (Vite's own report, at its gzip level: 1,283.27 kB and 401.02 kB, 53.64 kB and
  9.11 kB); the rest are 11 `.woff2` files of the three fonts, `index.html`, `LICENSE.txt` and
  `THIRD-PARTY-NOTICES.txt`. The service sends the files
  uncompressed over loopback. One bundle, not split; splitting the charts and the PDF writer
  into their own chunks is left (Phase 2).
- **Idle memory with the interface served** is the resident memory of the service and every
  process it started (`/proc`), read 5 s after the page had loaded the interface and the
  model and made its 12 selections; it is the same as after a plain start (178.6 MiB) plus
  about 4 MiB.
- **Peak RSS by `resource.getrusage`** in the full run: `RUSAGE_SELF` 244.6 MiB and
  `RUSAGE_CHILDREN` 242.2 MiB when the interface check ended (it ran first; the largest child
  that had ended, Node and its Chromium or a service); 397.6 MiB for both at the end of the
  session, which are the pytest process and its children over the whole session.

### Machine

- 4 cores (`os.cpu_count()` 4, affinity 4 under `taskset -c 0-3`), 15.71 GiB of memory,
  Linux 6.18.44 (glibc 2.39), Python 3.13.18. Node 22, Playwright 1.63.0, Chromium
  153.0.8010.12 headless.
- Wall time: the full `taskset -c 0-3 pytest -m perf` took 162.02 s (11 passed); the interface
  check alone takes 11.6 to 12.9 s, most of it starting the service and Chromium.

## Sources

- Build guide, "Performance measurement protocol" and "Known gaps" ("Performance targets are
  proposals ... Measured at M3, M6, M9").
- Spec 3 "Performance targets"; `docs/research/perf-M6.md` (the service targets and the
  method this note reuses); DECISIONS AKS-120 reading 16 and AKS-138 reading 19 (bundle
  size).
- `tests/perf/test_interface.py` and `ui/perf/canvas.perf.ts` (new), `ui/playwright.perf.config.ts`
  (`npm run perf`), and the measurements printed under "performance measurements"
  (`tests/perf/conftest.py`).
- HTML Living Standard, "Update the rendering" (animation frame callbacks run before the
  paint of their frame; a posted message is a task, run after it). Python documentation for
  `resource.getrusage`.

## Decision

- The canvas target is **measured** at M9, which closes the milestone's perf gate for a
  session. It is not **confirmed** until the owner runs the same command on a machine capped
  to 4 cores and 8 GB (AKS-82). No target changes.
- Readings (rule 5, owner to confirm; spec 3 "Performance targets" says so): "paints" is the
  first frame painted after the selection is drawn and the side panel names the block, timed
  from `pointerdown`; the measurement is the largest of 12 selections of drawn blocks; the
  200 components are the validation target's line, placed in a grid, at 1,280 × 800.
- For the owner: on the low tier, with integrated graphics, the margin should hold, but the
  first load of a 1.3 MB bundle and the Canvas's opening (about 2 s here) are the costs to
  watch; code splitting is the remedy if they are slow.

## Tested

The command, run from the repository root:

```bash
source .venv/bin/activate && export PATH=/opt/node22/bin:$PATH \
  PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers && taskset -c 0-3 pytest -m perf
```

On 2026-11-08, on branch `akshayjain00/aks-121-m9-pointer-only-end-to-end-test-api` at
f28bfe9 (the code of the M9 close; later commits change documents only), after `npm run
build` in `ui/`: 11 passed on Python 3.13.18 in 162.02 s, exit 0. The interface check was
also run alone three times (`taskset -c 0-3 pytest -m perf tests/perf/test_interface.py`),
each passing. Python 3.11 was not measured at M9 (the interface's timings are the browser's;
the service's were within 5% on 3.11 at M6).

For the owner (AKS-82): on a machine or virtual machine capped to 4 cores and 8 GB, after
`pip install -e ".[dev]"`, `npm ci` and `npm run build` in `ui/`, and with Chromium installed
for Playwright (`npx playwright install chromium`), run `taskset -c 0-3 pytest -m perf` (on
Windows, where there is no `taskset`, the cap comes from the virtual machine; run
`pytest -m perf`) and record the "performance measurements" lines in `docs/DECISIONS.md`.
