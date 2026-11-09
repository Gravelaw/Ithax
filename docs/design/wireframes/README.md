# Wireframes

Low-fidelity wireframes of the seven screens of spec 3 "Screens", the canvas first, plus the first-start notice (spec 3 "Service rules", First start). They serve spec 3 "Design before building" (second item).

Each file is a plain SVG at 1280 × 800, drawn in the light theme's tokens (`../design-system.md`), with a `<title>` and `<desc>` that say what it shows. They open in any browser. `tests/test_design.py` checks that every SVG here parses as XML and is listed below.

## After the owner design review (2026-11-06)

The wireframes show **layout and content**; the look is set by `../design-system.md` version 2. After the owner review they were recoloured to the Sanzo Wada light palette, and the placeholder squares were replaced by the Phosphor icons of `../design-system.md` "Icons": the navigation rail (filled icon on the current screen), the palette and block icons, and the Undo, Redo, Run and zoom buttons. Fonts in the drawings stay generic.

The approved look itself (block shapes per category, after-run overlay, results headline card, charts, the delete dialog) is shown in `../preview/owner-review.html`, section "Proposed new look", with example data. These approved changes are specified in the text files; the M9 session draws each before building its screen, and the table says which are drawn:

| Change (owner review) | Specified in | Affects |
| --- | --- | --- |
| Block shapes per category; distinct resource boxes; reference lines by pattern, icon and word | `../design-system.md` "Block styles", "Line styles" | **drawn at M9 (AKS-136):** `01-canvas.svg`, `01b-canvas-learn.svg`, `01c-canvas-states.svg` (capsule, rounded box and tag with an icon disc; a pool's count badge, a schedule's on and off strip, a failure's striped edge; long dashes and "staffs", dots and "sets hours", dash-dot and "breaks down") |
| Review marks for an outside change, "N changes to review" | `../canvas-interactions.md` "Reviewing an outside change" | **drawn at M9 (AKS-137):** `01-canvas.svg` (the top bar's "2 changes to review", the notice naming the client, a Changed block with Accept and Reject, a Removed ghost) and `01c-canvas-states.svg` (Added, Changed and Removed marks; the side panel's "Changes to review" list with Accept all and Reject all) |
| Delete confirmation dialog | `../canvas-interactions.md` "Deleting" | **drawn at M9 (AKS-136):** `01-canvas.svg`, as an inset |
| "Try a change" beside settings | `../canvas-interactions.md` "Trying a change" | **drawn at M9 (AKS-136):** `01-canvas.svg`, beside the service mean and the queue capacity (built with the Experiment screen, AKS-120) |
| Lesson rings the one field to change; prediction step | `../canvas-interactions.md` "Learn mode on the canvas" | **drawn at M9 (AKS-136):** `01b-canvas-learn.svg`, the exercise step (built with Learn mode, M10) |
| "Does this column include time spent waiting?" | `../flows.md` step B7b | **drawn at M9 (AKS-120):** `03-data.svg` (asked under "Use for" because the setting chosen is a service time: Yes, No and Not sure; Not sure shows the warning and the field is set only with "Use it anyway") |
| Data histogram with the fitted curve | `../design-system.md` "Charts" | **drawn at M9 (AKS-120):** `03-data.svg` (bars of the column, the chosen candidate's curve, the caption and "Show as table"; the fit table's score is "How well it fits") |
| Live trends; search best-so-far chart | `../design-system.md` "Charts" | **drawn at M9 (AKS-138):** `05-run-monitor.svg`, as the logged fallback: no Phase 1 engine reports numbers while it runs, so the monitor says live numbers are not available and has no Pause updates; a search run's inset shows its message and that the best-so-far chart and the table of all trials are on Results, drawn in `06-results.svg` from `summary.json` |
| Headline card that says why; charts per run kind; table of all trials | `../canvas-interactions.md` "Learn mode on the canvas", `../design-system.md` "Charts" | **drawn at M9 (AKS-138):** `06-results.svg` (the headline card, the run's first finding; bars with their likely ranges and the value over time for a process run; insets for a search run, the best-so-far dots with the best found and the table of all trials, and for an optimization model, the decisions, the goal and the fully used limits; each chart with "Show as table") |
| Undo steps, Ask before deleting, Motion, Colour-blind safe charts, Restore all defaults | `../canvas-interactions.md`, `../design-system.md`, `../accessibility.md` | **drawn at M9 (AKS-138):** `07-settings.svg` (Appearance with Motion and Colour-blind safe charts, Canvas with Ask before deleting and Undo steps, Restore all defaults after a question, the five thresholds with the service's W220 issue, and when each section takes effect) |
| Optimization models: Table view and Diagram view | `../canvas-interactions.md` "The model and the canvas" | **drawn at M9 (AKS-137):** `09-optimization.svg` (the product mix in the Table view, with the Diagram view beside it) |
| Plain words ("repeat runs", "likely range") | `../design-system.md` "Type" | all screens; `02-home.svg`, `02c-new-project.svg` and `08-first-start-notice.svg` checked at M9 (AKS-119): they use no technical term; `05-run-monitor.svg`, `06-results.svg` ("likely range of the average", "repeat runs") and `07-settings.svg` (each unit in words) drawn at M9 (AKS-138); **drawn at M9 (AKS-120):** `04-experiment.svg` ("Settling-in time", "Repeat runs", "Sure of the likely range", "Repeat runs each", each with its technical term under it) and `03-data.svg` ("How well it fits") |
| "New empty project" asks Process or Plan; Home before the templates (empty gallery, Build unavailable with its reason) | `../../DECISIONS.md` "Owner design review", "API additions and the open gap"; spec 3 `POST /v1/projects` | **drawn at M9 (AKS-119):** `02c-new-project.svg` |

Values in the drawings are examples. Numbers taken from the specs are marked as such in the drawing; `{braced}` text is a placeholder for a value that does not exist yet (template minutes, engine versions, fit scores).

| File | Screen (spec 3) | Shows | Behaviour described in |
| --- | --- | --- | --- |
| [`01-canvas.svg`](01-canvas.svg) | 2 Canvas | The coffee shop model with a newly added `server_2` in error; palette, side panel with the selected block's settings and "Try a change", problems list, Run disabled with its reason, zoom controls and minimap; an inset of the delete confirmation dialog; after an outside change, the top bar's "2 changes to review", the notice naming the client, a Changed block and a Removed ghost | `../canvas-interactions.md` |
| [`01b-canvas-learn.svg`](01b-canvas-learn.svg) | 2 Canvas, Learn mode | The exercise step card with its prediction step, the highlighted block and the ringed field to change | `../canvas-interactions.md` "Learn mode on the canvas", `../flows.md` "Learn mode" |
| [`01c-canvas-states.svg`](01c-canvas-states.svg) | 2 Canvas | Block and port states: the three block shapes, default, selected, focus, error, warning, Learn highlight, branch routes, the three port-less resource blocks with their reference lines, connecting; the review marks (Added, Changed, Removed) and the "Changes to review" list | `../design-system.md` "Block styles" |
| [`02-home.svg`](02-home.svg) | 1 Home | Learn and Build entries, template gallery, recent projects | `../flows.md` "Shared start" |
| [`02c-new-project.svg`](02c-new-project.svg) | 1 Home, New empty project | Home before the templates (Learn, Build unavailable with its reason, the gallery's empty state, recent projects) and the New empty project dialog: a name, Process or Plan, and a refusal shown as the service wrote it | `../flows.md` "Shared start"; spec 3 `POST /v1/projects` |
| [`02b-build-form.svg`](02b-build-form.svg) | 1 Home, Build mode form | The two-step fixed form of spec 4 "Build mode" | `../flows.md` "Build mode" |
| [`03-data.svg`](03-data.svg) | 3 Data | Imported files, columns and preview, distribution fit with the histogram and its fitted curve, "Use for" and the waiting question | `../flows.md` steps B5b to B7b |
| [`04-experiment.svg`](04-experiment.svg) | 4 Experiment | Run length, settling-in time, repeat runs, seed, how sure the likely range is, record interval; scenarios; objectives, constraints and search | `../flows.md` step B9 |
| [`05-run-monitor.svg`](05-run-monitor.svg) | 5 Run monitor | Progress with the service's message and Cancel run; live key numbers not available (logged fallback), so no Pause updates; a search run's inset; the project's runs | `../flows.md` steps L8 and B11 |
| [`06-results.svg`](06-results.svg) | 6 Results | The headline card that says why, findings first, key numbers with their likely range, charts per run kind each with a data table (insets for a search run and an optimization model), the replications table, exports, the "Tell us what you built" link, and the footer with model name, run id, fidelity label, replications and confidence, engine name and version, and "Simulation results are estimates and carry no warranty." | `../flows.md` steps L9 and B12 |
| [`07-settings.svg`](07-settings.svg) | 7 Settings | Run targets, runs and limits (units in words), hardware tier, engines, the five finding thresholds with W220 issues, appearance (theme, text size, motion, colour-blind safe charts), canvas (ask before deleting, undo steps), Restore all defaults, remote access, about; when each takes effect | `../flows.md` "Shared start" |
| [`09-optimization.svg`](09-optimization.svg) | 2 Canvas, optimization model | A plan (the product mix of spec 2): the Table view's Decisions, Goal and Limits with Add and Remove, and the Diagram view of the same model (decision cards linked to the goal and limit cards by their coefficients); no experiment picker | `../canvas-interactions.md` "The model and the canvas"; spec 3 "Screens" 2 |
| [`08-first-start-notice.svg`](08-first-start-notice.svg) | First-start notice | What the tool does, that results are estimates to support judgement, where the licence is; one Continue button | `../flows.md` "Shared start" |

## What each screen must do (spec 3), and where the wireframe shows it

| Spec 3 screen requirement | Wireframe |
| --- | --- |
| Home: recent projects, template gallery, Learn or Build entry (Build mode form as in spec 4) | `02-home.svg`, `02b-build-form.svg`, `02c-new-project.svg` |
| Canvas: drag blocks from a palette, connect them, edit properties in a side panel; validation errors appear on the offending block; for an `optimization` model, a table view and a diagram view | `01-canvas.svg`, `01c-canvas-states.svg`, `09-optimization.svg` |
| Data: import CSV or Excel, map columns, fit a distribution to a column | `03-data.svg` ("map columns" is the column picker plus "Use for", which maps a column to a block setting) |
| Experiment: run length, replications, scenarios, optimization setup | `04-experiment.svg` |
| Run monitor: progress, live key numbers, cancel | `05-run-monitor.svg` |
| Results: plain-language findings first, then charts and tables; export to CSV and PDF; the footer | `06-results.svg` |
| Settings: run targets, hardware tier, engine management | `07-settings.svg` |
| First start: what the tool does, that results are estimates to support judgement, where the licence is | `08-first-start-notice.svg` |

The Results PDF export carries the same footer on every page (spec 3 Screen 6); its layout follows the screen's order and is designed with the M9 code.
