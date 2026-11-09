# The interface

The lcsim interface: React 19 with TypeScript (strict), built with Vite, tested with Vitest and Testing Library (components) and Playwright (end to end, against a real engine service). It is a client of the engine service's HTTP and WebSocket API and nothing else (spec 3 "API": no private channel). Its design is `docs/design/`; its behaviour is spec 3 "Screens".

Node 22.12 or later. Every dependency is pinned exactly in `package.json` and `package-lock.json`, and recorded with its licence in `docs/DECISIONS.md`.

## Scripts

| Command | What it does |
| --- | --- |
| `npm ci` | Install the pinned dependencies |
| `npm run build` | Build into `dist/`, which the service serves at `/v1/ui/`; also writes `dist/LICENSE.txt` (the product's licence) and `dist/THIRD-PARTY-NOTICES.txt` (every bundled package's licence, `plugins/notices.ts`) |
| `npm run check` | The interface gate: type check (`tsc`), format and lint (Biome), component tests (Vitest); each must exit 0 |
| `npm run typecheck`, `npm run lint`, `npm test` | The three parts of `check` alone |
| `npm run format` | Let Biome fix formatting and import order |
| `npm run e2e` | End-to-end tests (`e2e/`) in Chromium against a real service; run `npm run build` first |
| `npm run dev` | Vite's development server (it cannot reach a service: the service serves the interface itself; use `build` and the launcher) |

`bash scripts/check.sh` at the repository root stays the Python gate; CI runs both (`.github/workflows/checks.yml`, job `interface`).

## Running it

```bash
npm ci && npm run build
python -m lcsim.launcher          # from the repository root, with the package installed
```

The launcher (spec 3 "Service rules", Launcher) finds the running service through `service.json`, or starts one, and opens `http://127.0.0.1:<port>/v1/ui/#token=<token>`. The service serves `ui/dist` by default (`python -m lcsim.service --ui-dir` names another folder). The page takes the token from the fragment, removes it from the address bar and keeps it in the tab's session storage.

## End-to-end tests

`e2e/service.ts` starts a real service for each test through the launcher, with temporary `--config-dir` and `--data-dir` folders and `--ui-dir dist`, and stops it with SIGTERM after the test, checking that `service.json` is removed. The Python is `LCSIM_PYTHON`, else the repository's `.venv`, else `python3`; the package must be installed (`pip install -e ".[dev]"`).

`@playwright/test` is pinned to 1.63.0. Where Chromium is already installed (the agent container has it at `/opt/pw-browsers`), set `PLAYWRIGHT_BROWSERS_PATH` to that folder, or `LCSIM_CHROMIUM` to the browser itself; never run `playwright install` there. CI installs its own with `npx playwright install --with-deps chromium`.

The fixtures in `e2e/fixtures.ts` give each test:

- `service`: the running service, its `origin`, `token`, folders, and `api(method, path, body)` for requests a test makes itself, as a script would;
- `sent`: every `/v1` request the page made, with its headers (outside `/v1/ui/`);
- `outside`: every request that tried to leave the machine; the fixture aborts each one and fails the test if there was any (spec 0 principle 6).

## For the next M9 tickets

- **The API client** (`src/api/client.ts`) is the only code that calls `fetch` or `WebSocket`. Add each new route as a method that calls `request` (or `socket` for a WebSocket) with a documented `/v1` path, and type its body in `src/api/types.ts`. Results are data: `ok` with the body, `refused` with the service's error and issue objects, `failed` when there was no usable answer. Show a refusal with `ServiceProblem` or `IssueList` (`src/components/ServiceProblem.tsx`), which print the service's own code, message, hint and path; never write interface text for a model problem. `onRequest` sees every request, for AKS-121's request log.
- **Settings** (`src/settings/SettingsContext.tsx`): `useSettings()` gives `settings` (the six keys of `GET /v1/settings`) and `save(change)`, which sends `PUT /v1/settings`. A key given replaces the stored one whole (send the whole `interface` or `finding_thresholds` object, as the first-start notice does), `null` restores its default. Interface preferences apply at once (`src/settings/preferences.ts`); the tier and run settings at the next start of the service.
- **Screens** are routes in the fragment (`src/app/router.ts`: `#/canvas/<project id>`; the Run monitor and Results may name a run, `#/monitor/<project id>/<run id>`, AKS-138); `src/app/App.tsx` maps each to a screen. A screen can put tools in the top bar through the `toolbar` element App gives it (a portal), as the Canvas does.
- **Dialogs** use `src/components/Dialog.tsx` (focus in and back, Escape, the rest inert). **Regions** are elements with `data-region` (F6 order); give a region's entry element `data-region-entry`.
- **Colours** are only the token variables `--color-<token>` from `docs/design/tokens.json` (`src/theme/tokens.ts`); a test fails on a raw colour in `src/`.
- **The Canvas** (`src/canvas/`, AKS-136): `CanvasSession` (`session.ts`) holds the open model and is the only way the Canvas writes it: `write(plan)` sends one batch of edits (or a whole model) with `base_revision`, one at a time, records an undo step, and validates half a second later; `undo()` and `redo()` write whole models with `PUT .../model?base_revision=N`; a write with no answer makes it read-only and is retried every 2 seconds; a `model` event with a newer revision reloads the model and clears undo (`reloads` counts these, for AKS-137's notice and review marks). While a write or a reload awaits its answer the session is `busy` and refuses every other change (`canWrite()`), so every action is built from the model shown; the screen marks its controls `aria-disabled` through `BusyContext` (`busy.ts`) and a text field's commit tried meanwhile is refused: the box shows the saved value and the screen's notice asks for the change again. `CommitInput` shows the saved value again whenever the value or the model's revision changes (`RevisionContext`), so no draft outlives a change to the model shown. `move(positions, burst)` sends a move at once; burst moves of the same blocks within 500 ms join one undo step. `interleave.test.ts` checks the rule with seeded scripts against a slow fake service. `useSession` gives its state to React. The screen (`CanvasScreen.tsx`) puts its save state, Undo, Redo, experiment picker and Run in the top bar's slot; Run starts the run (`CanvasSession.startRun`, AKS-138) and opens the Run monitor at it. Model helpers (`model.ts`) read components, ports, reference lines and issues; `SettingFields.tsx` builds a form from `GET /v1/schema/components/{type}`. Component tests use `src/test/fakeModel.ts`, a fake project model that applies the edit kinds the Canvas sends, with the service's component types in `src/test/component-types.json` (kept equal to the service's by `tests/test_ui_fixtures.py`).
- **Outside changes and plans** (AKS-137): the session keeps one `baseline` (the model before the first outside change not yet reviewed, with the canvas's own writes taken in); `marks()` and `marksOf(state)` are `review.ts`'s comparison of it with the model shown, item by item by stable id (a rename is a removal and an addition). `accept(key)` puts an item into the baseline, `acceptAll()` drops it, `reject(key)` writes the model with the item as in the baseline and `rejectAll()` writes the baseline (whole models, undo steps; all four refused while busy). `outside` and `clientsOf` give the notice. `ReviewParts.tsx` draws the notice, the top bar's count, the chips and the "Changes to review" list. An `optimization` model opens `PlanScreen.tsx` instead of the graph: the Table view's Decisions, Goal and Limits, edited with the `set_path` and `remove_path` batches of `plan.ts`, and the read-only Diagram view. `Toolbar.tsx` holds the save state and Run's reason, shared by both screens. Look up anything by a name the model holds with `own.ts` (`own`, `hasOwn`, `setOwn`), never `record[name]` or `name in record`.
- **Other screens that change the model** (AKS-120): `ModelScreen` (`src/canvas/ModelFrame.tsx`) opens the project's model in a `CanvasSession` of the screen's own and gives the screen `writes` (`edit` and `replace` send one plan built from the model shown, refused with the wait notice while busy; `say` shows a notice), with the save state, "N changes to review", Undo and Redo in the top bar, the outside-change notice and the "Changes to review" list. Keep every draft in `useDraft` (`src/canvas/busy.ts`) or `CommitInput`, so it goes when the model shown changes. The Data screen (`src/data/DataScreen.tsx`) and the Experiment screen (`src/experiment/`) are built this way; "Try a change" (`src/canvas/tryChange.ts`) is a field action of the Canvas's side panel (`FieldActions.tryChange`).
- **Data routes** (AKS-120): `listData`, `importData` (a `FormData` body: `request` sends a form as it is), `deleteData` and `fitData` in `src/api/client.ts`; the fit's answer carries the column's `histogram` (spec 3).
- **Charts** (AKS-120): `Chart` (`src/charts/Chart.tsx`) draws an ECharts option as SVG; import each new chart type or component in its `use([...])` call, so the rest of ECharts stays out of the bundle. `useChartColours()` gives the series colours of the tokens, colour-blind safe when that preference is on. Every chart needs a data table beside it (`accessibility.md`). Component tests replace `Chart` with a stand-in (`vi.mock`), since jsdom draws nothing; `Chart.test.tsx` checks the real one renders an SVG.
- **Runs and results** (AKS-138): `startRun`, `listRuns`, `getRun`, `cancelRun`, `runEvents`, `getSummary`, `getTable`, and the files `tableCsv` and `exportProject` through `download` (a `Blob`; a refusal is still the service's JSON) in `src/api/client.ts`. Run on the Canvas and on the plan screen goes through `CanvasSession.startRun`: one request under the Save rule, its refusal the session's `refusal`. The Run monitor (`src/monitor/RunMonitor.tsx`) shows the run its address names, else the project's latest unfinished run, else its latest; it follows the run's events and the project's `run` events. Results (`src/results/`) derive everything from the answers for one run id (`summary.ts` reads `summary.json`, `display.ts` holds spec 4's display units, `charts.ts` the chart data and options, `report.ts` and `pdf.ts` the PDF, `save.ts` hands a file to the browser). Component tests read a PDF with `src/test/readPdf.ts` (pdf.js, a development dependency) and use the runs and summaries of `src/test/runs.ts`.
- **Settings** (AKS-138): `src/settings/SettingsScreen.tsx`; `useSettings()` also gives the W220 `issues` and `refresh()`. One write at a time; every field shows the saved value again after each answer (fields are keyed by the answers' count).
- **The project zip** is `GET /v1/projects/{pid}/export` (spec 3). End-to-end, `e2e/results.spec.ts` lists a downloaded zip with the repository's Python (`python()` of `e2e/service.ts`) and reads a downloaded PDF with pdf.js.
