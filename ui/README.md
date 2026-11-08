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
- **Screens** are routes in the fragment (`src/app/router.ts`: `#/canvas/<project id>`); `src/app/App.tsx` maps each to a screen. The Canvas, Data, Experiment, Run monitor, Results and Settings screens are placeholders in `src/screens/Placeholders.tsx`; replace each with the real screen.
- **Dialogs** use `src/components/Dialog.tsx` (focus in and back, Escape, the rest inert). **Regions** are elements with `data-region` (F6 order); give a region's entry element `data-region-entry`.
- **Colours** are only the token variables `--color-<token>` from `docs/design/tokens.json` (`src/theme/tokens.ts`); a test fails on a raw colour in `src/`.
