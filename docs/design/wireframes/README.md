# Wireframes

Low-fidelity wireframes of the seven screens of spec 3 "Screens", the canvas first, plus the first-start notice (spec 3 "Service rules", First start). They serve spec 3 "Design before building" (second item).

Each file is a plain SVG at 1280 × 800, drawn in the light theme's tokens (`../design-system.md`), with a `<title>` and `<desc>` that say what it shows. They open in any browser. `tests/test_design.py` checks that every SVG here parses as XML and is listed below.

Values in the drawings are examples. Numbers taken from the specs are marked as such in the drawing; `{braced}` text is a placeholder for a value that does not exist yet (template minutes, engine versions, fit scores).

| File | Screen (spec 3) | Shows | Behaviour described in |
| --- | --- | --- | --- |
| [`01-canvas.svg`](01-canvas.svg) | 2 Canvas | The coffee shop model with a newly added `server_2` in error; palette, side panel with the selected block's settings, problems list, Run disabled with its reason, zoom controls and minimap | `../canvas-interactions.md` |
| [`01b-canvas-learn.svg`](01b-canvas-learn.svg) | 2 Canvas, Learn mode | The step card and the highlighted block | `../canvas-interactions.md` "Learn mode on the canvas", `../flows.md` "Learn mode" |
| [`01c-canvas-states.svg`](01c-canvas-states.svg) | 2 Canvas | Block and port states: default, selected, focus, error, warning, Learn highlight, branch routes, port-less resource blocks with reference lines, connecting | `../design-system.md` "Block styles" |
| [`02-home.svg`](02-home.svg) | 1 Home | Learn and Build entries, template gallery, recent projects | `../flows.md` "Shared start" |
| [`02b-build-form.svg`](02b-build-form.svg) | 1 Home, Build mode form | The two-step fixed form of spec 4 "Build mode" | `../flows.md` "Build mode" |
| [`03-data.svg`](03-data.svg) | 3 Data | Imported files, columns and preview, distribution fit and "Use for" | `../flows.md` steps B5b to B7b |
| [`04-experiment.svg`](04-experiment.svg) | 4 Experiment | Run length, warm-up, replications, seed, confidence, record interval; scenarios; objectives, constraints and search | `../flows.md` step B9 |
| [`05-run-monitor.svg`](05-run-monitor.svg) | 5 Run monitor | Progress with the service's message, live key numbers, Pause updates, Cancel run, the project's runs | `../flows.md` steps L8 and B11 |
| [`06-results.svg`](06-results.svg) | 6 Results | Findings first, key numbers with intervals, chart with data table, tables, exports, and the footer with model name, run id, fidelity label, replications and confidence, engine name and version, and "Simulation results are estimates and carry no warranty." | `../flows.md` steps L9 and B12 |
| [`07-settings.svg`](07-settings.svg) | 7 Settings | Run targets, runs and limits, hardware tier, engines, finding thresholds, appearance, remote access, about | `../flows.md` "Shared start" |
| [`08-first-start-notice.svg`](08-first-start-notice.svg) | First-start notice | What the tool does, that results are estimates to support judgement, where the licence is; one Continue button | `../flows.md` "Shared start" |

## What each screen must do (spec 3), and where the wireframe shows it

| Spec 3 screen requirement | Wireframe |
| --- | --- |
| Home: recent projects, template gallery, Learn or Build entry (Build mode form as in spec 4) | `02-home.svg`, `02b-build-form.svg` |
| Canvas: drag blocks from a palette, connect them, edit properties in a side panel; validation errors appear on the offending block | `01-canvas.svg`, `01c-canvas-states.svg` |
| Data: import CSV or Excel, map columns, fit a distribution to a column | `03-data.svg` ("map columns" is the column picker plus "Use for", which maps a column to a block setting) |
| Experiment: run length, replications, scenarios, optimization setup | `04-experiment.svg` |
| Run monitor: progress, live key numbers, cancel | `05-run-monitor.svg` |
| Results: plain-language findings first, then charts and tables; export to CSV and PDF; the footer | `06-results.svg` |
| Settings: run targets, hardware tier, engine management | `07-settings.svg` |
| First start: what the tool does, that results are estimates to support judgement, where the licence is | `08-first-start-notice.svg` |

The Results PDF export carries the same footer on every page (spec 3 Screen 6); its layout follows the screen's order and is designed with the M9 code.
