# Session 2026-11-06 · M9 design: owner design review (AKS-118)

The owner reviewed the M9 design step by step in conversation. Documents only; no `ui/` code. A second session on the same day and milestone as `2026-11-06-M9.md`.

## Built

- A walkthrough page with the real wireframes and a "Proposed new look" preview (example data), kept as `docs/design/preview/owner-review.html` with its icon data `docs/design/preview/icons.js`. The preview loads Google Fonts and ECharts from public hosts; it is a review record, not product code.
- Research notes: `docs/research/spec-3-wada-palette.md`, `spec-3-engaging-design.md`, `spec-3-icons-and-type.md`, `spec-3-results-visualization.md`; two AI persona walkthroughs, `spec-3-persona-walkthrough-student.md` and `spec-3-persona-walkthrough-business.md`.
- Design system version 2: `docs/design/tokens.json` (Sanzo Wada palette, softened dark theme, chart and colour-blind safe chart tokens, nine new pairs) and `docs/design/design-system.md` (type, icons, block shapes, line styles, review marks, after-run overlay, motion, charts, controls).
- `docs/design/canvas-interactions.md`, `flows.md` and `accessibility.md` updated for the owner's choices and the persona fixes.
- Wireframes recoloured to the Wada light palette, with Phosphor icons in the navigation rail, palette, blocks and canvas buttons; `wireframes/README.md` lists the approved changes not yet drawn.
- Spec 3 aligned (Screens item 2; Delete, External edits and References rules; Design before building; warning line; Changes in this version). `CLAUDE.md` "Current state" updated.

## Checks passing

- `bash scripts/check.sh`: exit 0 (format, lint, mypy strict, 1,163 tests, coverage 100%). In this container the check must run with `/usr/local/bin` first on `PATH`; an older `mypy` 2.3.1 under `/root/.local/bin` otherwise shadows the project's 2.4.1 and reports false errors.
- Contrast: 74 of 74 pairs pass (37 per theme). Lowest text pairs 4.60:1 (light) and 4.86:1 (dark); lowest non-text pairs 3.44:1 (light) and 4.02:1 (dark).

## Decisions logged

`docs/DECISIONS.md`, "2026-11-06 · M9 design: owner design review (AKS-118)": every walkthrough step and all twelve design choices with the owner's words and outcome; `set_label` and `set_path` confirmed; the M6 `domain` fix agreed; the walkthrough fallback taken; persona fixes; items logged for later spec changes.

## Awaiting owner

- The walkthrough with at least one student and one business user outside the project, now a condition of M10 (AKS-79, AKS-82).
- The spec changes the owner deferred: costs in results; the "Compare options" Build answer and template audiences (spec 4); a never-reused id counter; `domain` on project creation (M6); the chart data additions.
- A lawyer's check of the font, icon and chart licences before the first release (spec 0), as for every dependency.

## Left

- The M9 session draws the approved changes listed in `docs/design/wireframes/README.md` before building each screen, including a new wireframe for the optimization Table and Diagram views.
- Check the `Rows` icon for `queue` by eye; draw a custom icon if it does not read as a queue.
- Measure ECharts on the low tier at M9 (`docs/research/perf-M9.md`); uPlot is the fallback for live series.
