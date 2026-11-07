# Spec 3: Desktop Application

> Version 0.3 · working copy in the repository (source of truth, owner to confirm) · changes are listed under "Changes in this version".

The app is two programs: an engine service that does all the work, and an interface that talks to it only through an API. That split is what lets a Windows interface drive Linux engines.

> **Warning: untested.** Only the service skeleton has been built (M6, from AKS-110: the service rules, `system`, `engines`, `schema`, `templates` and `projects` endpoints); the rest of this spec has not. The interface frameworks were re-checked on 2026-11-06 (`docs/research/spec-3-framework-check.md`) and the service framework on 2026-11-07 (`docs/research/spec-3-service-framework-check.md`). The performance targets are proposals. This spec defines behaviour; the user flows, wireframes, canvas rules, design system and accessibility check are in `docs/design/` (2026-11-06), and the owner reviewed them on 2026-11-06 (design system version 2; `docs/DECISIONS.md` "Owner design review"). The walkthrough with outside users has not happened; the owner took the fallback below, so it is a condition of M10. See "Known gaps" in the Build guide.

## Scope

- **In:** the engine service, its API, the interface, project storage, data import, packaging, hardware tiers.
- **Out:** the model format (spec 1), engines (specs 2, 5, 6), templates and assistant tools (spec 4).

## Architecture

| Part | Role | Proposed technology |
| --- | --- | --- |
| Engine service | Validates models, schedules runs, hosts engine adapters, serves results | Python with FastAPI 0.162.1 or later, served by uvicorn 0.54.0 or later with websockets (never `uvicorn[standard]`, whose uvloop has no Windows build); confirmed 2026-11-07 (`docs/research/spec-3-service-framework-check.md`; licences in `docs/DECISIONS.md`) |
| API | The only way in: HTTP for requests, WebSocket for live progress | Local address only by default |
| Interface | Canvas, forms, charts | React with React Flow (`@xyflow/react`), packaged as a desktop app with Tauri 2, version 2.11.1 or later (confirmed 2026-11-06; licences in `docs/DECISIONS.md`) |
| Storage | One folder per project: model file, imported data, runs | Files, plus SQLite as a run index |

On Linux both parts run natively. On Windows, Phase 1 runs both parts natively (proposed default from the review, owner to confirm): every Phase 1 dependency ships Windows wheels or is pure Python (highspy, numpy, scipy, pyarrow, pyomo, simpy, optuna, pint, fastapi; PyPI file lists read on 2026-11-05), while WSL costs an administrator install, a restart and by default half the memory of a low-tier machine. A WSL path is added in Phase 3 for engines without Windows builds. Until the owner decides, service code must stay platform-neutral (no fork-only process code, no Linux-only paths).

## API

| Endpoint | Purpose |
| --- | --- |
| `/projects` | Create, open, list |
| `/models` | Read and write the model file |
| `/validate` | Run both validation passes |
| `/runs` | Start, cancel, list; `/runs/{id}/events` streams progress |
| `/results` | Summary and tables (fields arrive with spec 6) |
| `/engines` | Installed adapters and their capabilities |
| `/system` | Detected hardware and the active tier |

The interface uses no private channel. Anything it can do, a script or an assistant can do through the same API.

## Screens

1. **Home:** recent projects, template gallery, Learn or Build entry (Build mode form as in spec 4).
2. **Canvas:** drag blocks from a palette, connect them, edit properties in a side panel. Validation errors appear on the offending block. For an `optimization` model, which has no components, the screen shows its variables, objective and constraints in place of the graph, in a table view and a diagram view of the same model.
3. **Data:** import CSV or Excel, map columns, fit a distribution to a column.
4. **Experiment:** run length, replications, scenarios, optimization setup.
5. **Run monitor:** progress, live key numbers, cancel.
6. **Results:** plain-language findings first, then charts and tables; export to CSV and PDF. Every results page and exported PDF carries a footer: model name, run id, fidelity label, replications and confidence, engine name and version, and "Simulation results are estimates and carry no warranty."
7. **Settings:** run targets, hardware tier, engine management.

## Hardware tiers

- On first start the service detects cores, memory and graphics, and sets the tier.
- The tier sets defaults: parallel replications now, mesh size limits later.
- Graphics hardware is never required. Both Nvidia and Intel graphics are used when present.
- Low and mid tiers are tested on a machine, container or virtual machine capped to the tier (WSL capping on the development machine is one way).
- How it is detected (AKS-110, proposed default, owner to confirm): `cores` are the logical processors the service process may use; `memory` is the physical memory in bytes (`null` where it cannot be read); `graphics` lists the vendors found (`nvidia`, `intel`, `amd`, or another PCI vendor id as `0x....`), read from `/sys/class/drm` on Linux, and is `null` where it cannot be read (Windows and macOS until the interface needs it). The tier is the highest of `high` (16 cores, 32 GB), `mid` (8 cores, 16 GB) and `low` whose cores and memory the machine both reaches, memory counting as reached at 90% of the nominal size (a 16 GB machine reports less than 16 GiB); below `mid`, or with memory unknown, it is `low`. Graphics does not set the tier in Phase 1, since no Phase 1 engine uses it. The tier found on the first start is stored as `tier` in `settings.json` in the configuration folder, which Settings will change (M9); later starts keep it. `workers` for a run is the lesser of the active tier's cores (4, 8, 16) and the cores the process may use.

## Packaging

- **Linux:** one installable package containing interface, service and Phase 1 engines.
- **Windows:** one installer containing interface, service and Phase 1 engines (proposed default); alternative, an installer plus a prepared WSL image.
- **Engines:** Phase 1 engines are bundled; an environment manager is introduced with the first Phase 3 engine, so later physics engines can be added without reinstalling the app.

## Detailed specification

The sections below are binding. Where they differ from the summary above, these win. Only the service rules and the `system`, `engines`, `schema`, `templates` and `projects` rows of "Endpoints" have been built (AKS-110).

### Service rules

- **Local only.** The service listens on `127.0.0.1` and refuses other addresses unless the user turns on remote access.
- **Token.** `Authorization: Bearer <token>`; the token is 32 random bytes, base64url. WebSocket connections authenticate with a first text message `{"token": "..."}` within 5 seconds, else the server closes with code 1008, because webviews cannot set headers. The token is drawn from the operating system's generator (Python's `secrets`), base64url without padding (43 characters), anew at every start; it is a secret, not simulation randomness, so the spec 1 stream scheme does not apply. Every HTTP request needs it, `GET /v1/system` included; a request without it, or with another, gets 401 with E182 and `WWW-Authenticate: Bearer`. A first message that is not that JSON object with the right token, or none within 5 seconds, closes the WebSocket with 1008 and the reason `E182` (AKS-110).
- **Discovery.** The service binds 127.0.0.1 on a port chosen by the operating system and writes `service.json` `{port, token, pid, started}` with mode 0600 in its configuration folder; the interface, the MCP server and scripts read it. `port` and `pid` are integers, `token` the token text and `started` ISO 8601 UTC ending in `Z`. The file is written before the service answers (through a temporary file and a rename, so a reader never sees half a file) and removed when the service exits, if it still names this service. The configuration folder is `%APPDATA%\lcsim` on Windows, `~/Library/Application Support/lcsim` on macOS and `$XDG_CONFIG_HOME/lcsim` (default `~/.config/lcsim`) elsewhere; the user data folder is `%LOCALAPPDATA%\lcsim`, `~/Library/Application Support/lcsim` and `$XDG_DATA_HOME/lcsim` (default `~/.local/share/lcsim`); `python -m lcsim.service --config-dir ... --data-dir ...` overrides both (AKS-110, proposed default, owner to confirm; `lcsim` is renamed with the package).
- **One service per user.** A second start reads the file, probes `GET /v1/system`, and exits if it answers; otherwise it overwrites the file. The probe sends the file's token, goes to `127.0.0.1` without any proxy, and counts as answered only on a 200 within 2 seconds; the second start then exits with status 0 and prints the running service's port (AKS-110). So that two starts at the same moment cannot both serve, a service holds an exclusive lock on `service.lock` in its configuration folder from before it reads the file until it exits; a start that cannot take the lock is the second start, and it keeps probing for up to 10 seconds while the first is still starting, then exits with status 1 if nothing answers (review of PR #34, owner to confirm).
- **Hardening.** Requests whose `Host` is not `127.0.0.1:<port>` or `localhost:<port>` are rejected; no CORS headers are sent; WebSocket upgrades carrying an `Origin` other than the interface's own (fixed at M9) are rejected. Rejection is 403 with E183, checked before the token; for a WebSocket the upgrade is refused before it is accepted, which the server answers with 403. An upgrade without an `Origin` (scripts and the MCP server send none) passes this check. Until M9 fixes the interface's origin no `Origin` is allowed (AKS-110, owner to confirm).
- **Lifetime** (proposed default, owner to confirm): the service stays up while runs are active or clients are connected and exits after 30 idle minutes; the interface and the MCP server start it on demand. Idle means no run active, no WebSocket open and no HTTP request in progress; the 30 minutes count from the end of the last of these (AKS-110, AKS-78 open).
- **Runs outlive the interface.** Runs are child processes of the service, not of the interface.
- **Run queue.** At most `max_concurrent_runs` (default 1, Settings) run at once; others wait in `queued` in arrival order; a run receives `workers` = cores of the active tier.
- **Revision.** Every model write increments an integer `revision`, returned with the model and stored in `project.json`; `PUT .../model` and `POST .../model/edits` accept optional `base_revision`, and a mismatch returns 409 with `{"error": {"code": "E181", ...}, "model": <current>, "revision": N}` and applies nothing.
- **Client header.** Requests may carry `X-Client: ui|mcp|script`, recorded in the run manifest. A request without it counts as `script`; any other value is 400 with E184, checked after the token and before any route runs (AKS-110, owner to confirm).
- **First start.** The interface shows once what the tool does, that results are estimates to support judgement, and where the licence is.
- **Versioned paths.** Every path starts with `/v1`.

### Endpoints

| Method and path | Request | Response |
| --- | --- | --- |
| `GET /v1/system` |  | Cores, memory, graphics, active tier |
| `GET /v1/engines` |  | Installed adapters with their capabilities |
| `GET /v1/schema` |  | The composed JSON Schema (static schema plus installed adapters' component types) |
| `GET /v1/schema/components/{type}` |  | One component type's settings, ports and description |
| `GET /v1/templates` |  | Array of `template.json` |
| `GET /v1/templates/{tid}` |  | `template.json`, `lesson.md` text, `expected.json` |
| `GET /v1/projects` |  | List of projects |
| `POST /v1/projects` | `{name, template?, domain?, path?}` | The new project |
| `POST /v1/projects/open` | `{path}` | Registers an existing project folder (not exposed as an MCP tool) |
| `GET /v1/projects/{pid}/model` |  | The model file and its `revision` |
| `PUT /v1/projects/{pid}/model` | A whole model file, optional `base_revision` | The model, its `revision` and validation issues |
| `POST /v1/projects/{pid}/model/edits` | `{edits: [...], base_revision?}` | The updated model, its `revision` and validation issues |
| `POST /v1/projects/{pid}/validate` |  | Validation issues: runs the schema pass, the meaning pass, then `validate` of the adapter selected for the model's domain |
| `GET /v1/projects/{pid}/events` | WebSocket | `{"type": "model", "revision": N, "client": ...}` on every write and `{"type": "run", "run_id", "state"}` on every run state change |
| `POST /v1/projects/{pid}/data` | An uploaded CSV or Excel file | Column names, types and a preview |
| `GET /v1/projects/{pid}/data` |  | Files and columns |
| `DELETE /v1/projects/{pid}/data/{file}` |  | Removes the file and its column index |
| `POST /v1/projects/{pid}/data/{file}/fit` | `{column}` | Candidate distributions from the spec 1 list with fitted fields and a fit score (library chosen at M6 research) |
| `POST /v1/projects/{pid}/runs` | `{experiment_id?, target?}` | `202` with `{run_id}` |
| `GET /v1/projects/{pid}/runs` |  | List of runs with state |
| `GET /v1/runs/{rid}` |  | State, progress, timings |
| `POST /v1/runs/{rid}/cancel` |  | New state |
| `GET /v1/runs/{rid}/events` | WebSocket | Stream of progress events |
| `GET /v1/runs/{rid}/summary` |  | `summary.json` plus findings |
| `GET /v1/runs/{rid}/tables/{name}` | `?format=json` or `csv` | Table rows; `{name}` is `replications` or `timeseries` (spec 1); unknown names return 404 |

Notes on the rows:

- `GET /v1/system`: `{cores, memory, graphics, tier, workers}` as "Hardware tiers" defines them (`memory` in bytes).
- `GET /v1/engines`: an array, by adapter name, of `{name, version, domains, component_types, hardware, parallel_modes, licence, invocation}`, the adapter's `Capabilities` (spec 1) with `component_types` as the list of type names.
- `GET /v1/schema`: spec 1's static schema (`src/lcsim/model/schema.json`) with one added top-level annotation, `x-component-types`, mapping each installed adapter's component type to the description that `GET /v1/schema/components/{type}` returns. An annotation does not change what the schema accepts, so the composed schema validates exactly as the static one (AKS-110, owner to confirm).
- `GET /v1/schema/components/{type}`: `{type, domain, engine, description, inputs, outputs, outputs_from, settings, metrics}`. `description` is one sentence summarising the type's Behaviour in spec 2's "Block reference"; `outputs_from` names the setting whose entries are the output ports (`routes` for a branch) or is `null`; each setting is `{name, kind, required, ...}` with the keys of the model layer's catalogue that apply to it (`dimension`, `integer`, `many`, `choices`, `refers_to`, `fields`, `keyed_by`, `values`, `required_when`, `minimum`, `exclusive_minimum`, `min_items`, `default`), a time default written as a quantity in seconds (`"86400 s"`). A type no installed adapter has is 404 with E185 (AKS-110).
- `GET /v1/templates` is `[]` and `GET /v1/templates/{tid}` 404 with E185 until the templates arrive (M10).
- `GET /v1/projects`: an array of projects in the order they were registered, each `{id, name, created, layout_version, model_revision, path, available}`; a registered folder whose `project.json` cannot be read, or holds another `id`, is listed with `available` `false` and the other fields `null` except `id` and `path` (AKS-110, owner to confirm).
- `POST /v1/projects`: without `template` the project holds `{format_version, meta: {name}, domain: "process", parameters: {}, components: [], connections: [], experiments: [{id: "base", length: "8 h", warmup: "0 s", replications: 30}], run: {target: "local", fidelity: "standard"}}`, which validates with no errors. With `domain` `"optimization"` it holds `{format_version, meta: {name}, domain: "optimization", variables: [], objective: {sense: "maximize", linear: {}}, constraints: [], run: {target: "local", fidelity: "standard"}}`, which also validates with no errors under spec 1 as it stands (the owner's M5 decision to make a model with no variables an error is Phase 1a, AKS-130, and will need this default revisited). `domain` is `"process"` (the default) or `"optimization"` (AKS-110, owner design review 2026-11-06). Projects live under `<user data folder>/projects/<id>/` unless `path` is given (proposed); the service keeps `projects.json` in its configuration folder mapping id to absolute path (a relative `--data-dir` is made absolute when the service starts). `path` must be absolute and name a folder that does not exist or is empty, else 400 with E186. `name` is non-empty text. A `template` is 404 with E185 until M10. The response is the project as `GET /v1/projects` lists it; the new folder holds `project.json`, `model.json`, `data/` and `runs/`, with `model_revision` 0 and `layout_version` 1 (`index.sqlite` is made with the first run, AKS-112). Proposed defaults, owner to confirm.
- `POST /v1/projects/open`: `path` must be absolute; a folder that does not exist is 404 with E185, and one without a readable `project.json` holding the five fields is 400 with E186. Opening a project already registered at the same path returns it unchanged; one whose `id` is registered at another folder that still holds that project is 400 with E186 (a copied folder keeps its id), and otherwise the registration moves to the new path (AKS-110, owner to confirm).
- `POST .../runs`: `experiment_id` is required for a `process` model and must be absent for an `optimization` model, which has no experiments (400 otherwise). `target` overrides the file's `run.target` for this run and is recorded in the manifest; 422 when the model has errors; E172 with 422 when the target is unavailable.

`tests/service/test_routes.py` lists the application's routes and asserts the set equals this table, both ways; each row also has at least one request test.

### Model edits

An edit is rejected only when it cannot be applied: unknown or duplicate component id, unknown type, an unknown parameter or experiment named by `remove_parameter`, `remove_experiment`, `set_scenario` or `remove_scenario`, a new parameter without `value` and `type`, a `path` whose parent does not exist. Rejections are issue objects with code E180 and `path` `/edits/<n>`; the batch is then not applied and the response is 400. A batch that applies is saved even if validation then reports errors; the response is 200 with the model, its revision and the issues. `PUT .../model` follows the same principle: the file is saved when it passes the schema pass, and the response carries the meaning-pass issues; a schema failure (E100, E101) returns 400 with those issues and saves nothing. 422 is returned only by `POST .../runs`. The interface and the MCP server both use this one mechanism.

| Edit | Fields |
| --- | --- |
| `add_component` | `id`, `type`, `params`, optional `ui` |
| `remove_component` | `id`; its connections are removed with it |
| `rename_component` | `id`, `new_id`; rewrites connections, `schedule` and `failure` targets, `pool` references, objectives and constraints |
| `set_setting` | `id`, `path`, `value`; `path` is a JSON Pointer relative to the component's `params`, for example `/service/mean`; the last segment may be new, every earlier one must exist |
| `connect` | `from`, `to`; if `from` is already connected, the old connection is replaced |
| `disconnect` | `from` |
| `set_parameter` | `id` and any of `value`, `type`, `min`, `max`; a new `id` creates the parameter and then needs `value` and `type` |
| `remove_parameter` | `id`; E180 if referenced |
| `set_experiment` | `id` and any experiment fields; a new `id` creates the experiment, and fields not given take the values of the `base` experiment of a new project (`length` 8 h, `warmup` 0 s, `replications` 30) |
| `remove_experiment` | `id` |
| `set_scenario` | `experiment_id`, `id`, `set` |
| `remove_scenario` | `experiment_id`, `id` |
| `set_path` | `path`, `value`; JSON Pointer on the whole model, for `meta`, `run`, `objectives`, `constraints`, `search`, and in an `optimization` model `variables` and `objective` |
| `remove_path` | `path`; JSON Pointer on the whole model, as `set_path` |
| `set_ui` | `id`, `ui` |
| `set_label` | `id`, `label`; a `label` of `null` removes it |

### Status codes and errors

| Code | When |
| --- | --- |
| 200 | Success |
| 202 | Run accepted |
| 400 | Request malformed |
| 401 | Token missing or wrong |
| 404 | Project, run or table not found |
| 409 | Action not allowed in the run's current state, or the model revision has changed (E181) |
| 422 | `POST .../runs` only: the model has validation errors; the body lists the issues |
| 403 | Refused by the hardening rules: `Host` or WebSocket `Origin` not allowed (E183) |
| 405 | Method not allowed on a documented path (E185) |
| 500 | The service failed; the details are in its log, never in the body (E187) |

Every error body is `{"error": {"code", "message"}, "issues": [...]}`, where issues use the spec 1 issue object. `error.code` is a spec 1 code (AKS-110, owner to confirm): E182 for 401, E183 for 403, E184 for a malformed request (body not JSON, a field missing, unknown or of the wrong kind, a bad `X-Client`), E185 for an unknown project, template, component type or path (404) or method (405), E186 for a project folder that cannot be used (400), E187 for 500, and the codes the rows above name. For E184 `issues` holds one issue per problem, its `path` a JSON Pointer into the request body as E180's `/edits/<n>` is; otherwise `issues` is empty unless the row says it lists them.

### Progress events

```json
{"type": "progress", "fraction": 0.4, "message": "Scenario 1 of 2, replication 12 of 30"}
{"type": "metrics", "scenario": "default", "values": {"till.wait.mean": 268.1}}
{"type": "state", "state": "done"}
```

On connection the stream first sends `{"type": "state", ...}` and the latest `progress` event, then live events; after a terminal state the server sends it and closes. A client may connect at any time, including after `done`.

### Project folder

```text
<project>/
  project.json    id, name, created, layout_version, model_revision
  model.json      the current model
  data/           imported files, unchanged, plus a column index
  runs/           one folder per run, as in spec 1
  index.sqlite    run index, rebuilt from runs/ if missing
```

`project.json` holds `{id, name, created, layout_version, model_revision}`; `id` is a UUID4 string and is `pid`. The model's own `format_version` is inside `model.json`. `created` is ISO 8601 UTC ending in `Z`; `layout_version` is 1 for the layout above; `model_revision` is 0 for a new project (AKS-110).

The folder is plain files so it can be copied, zipped or put under version control. The project folder, not the model file alone, is the unit to share when a model uses imported data; the Results screen's export produces a zip of the project folder.

### Canvas behaviour

These are functional rules. Visual design is covered by the checklist below.

- **Single source.** The canvas shows the model file and nothing else. Every canvas action is one or more model edits.
- **Add.** Dragging a block from the palette adds a component with a generated id, such as `server_2`, and default settings.
- **Connect.** Dragging from an output port to an input port sends `connect`. Dragging from an output port that is already connected replaces its connection.
- **Delete.** Removes the selection and its connections, after a confirmation the user can turn off in Settings (on by default).
- **Undo and redo.** At least 100 steps, covering every model edit. Each step stores the model as it was; undo and redo write the stored model with `PUT .../model` and `base_revision`, because some edits (such as `set_setting` creating a new key) have no inverse edit.
- **Save.** Automatic after every edit. There is no save button.
- **Validate.** Runs half a second after the last edit. Issues appear as a marker on the block and in a list; selecting a list entry selects the block.
- **Run.** Disabled while errors exist, with the reason shown.
- **Rename.** Changing a component's id updates its connections and any references to its metrics.
- **External edits.** The canvas sends `base_revision` on every write and, on a `model` event whose revision it did not produce, reloads the model and shows a one-line notice naming the client. The reload clears the undo and redo history, so an undo cannot silently revert another client's change. The canvas marks what the other client added, changed or removed, and the user can accept or reject each change; a rejection is an ordinary write of the model with that item restored, sent with `PUT .../model` and `base_revision`.
- **References.** Blocks without ports (`resource_pool`, `schedule`, `failure`) are placed like any block. Their `pool` and `target` settings are drawn as reference lines, which are not connections and differ by kind in pattern, icon and word; they are set in the side panel with `set_setting`.

### Performance targets

All proposed, to be measured on the low tier (proposed; measured per the Build guide protocol, confirmed by the owner):

- Service ready within 5 seconds of start.
- Canvas stays responsive with 200 components: an end-to-end test adds 200 components by API and selecting a block paints within 100 ms (proposed).
- Validation of a 200-component model within 200 milliseconds.
- Service uses under 300 MB of memory when idle.

## Design before building

This spec lists the screens and what each must do. It does not contain their visual or interaction design. These are needed before interface code is written.

Produced by a session:

- [x] User flows for Learn mode and Build mode, from first launch to first result: `docs/design/flows.md`.
- [x] Wireframes for the seven screens, the canvas first: `docs/design/wireframes/`.
- [x] Interaction rules for the canvas: adding, connecting, selecting, undo, zoom, error display: `docs/design/canvas-interactions.md`.
- [x] A small design system: colours, type, spacing, block and port styles, light and dark themes: `docs/design/design-system.md`.
- [x] A check against accessibility guidelines: keyboard use, contrast, text size: `docs/design/accessibility.md`.

Done by the owner:

- [ ] A walkthrough of the wireframes with at least one student and one business user, both outside the project. If nobody is available within two weeks of the wireframes being ready, the owner does a scripted think-aloud walkthrough, logs the gap in `docs/DECISIONS.md`, and the outside walkthrough becomes a condition of M10 instead of M9 (proposed default, owner to confirm).

M9 may start when the five files exist and the owner has recorded the walkthrough or its fallback.

Owner decision, 2026-11-06: the fallback is taken. Nobody outside the project has walked through the wireframes. The owner's own step-by-step review of the design, with two AI persona walkthroughs (`docs/research/spec-3-persona-walkthrough-student.md` and `-business.md`), counts as the owner walkthrough; the gap is logged in `docs/DECISIONS.md`; the walkthrough with at least one student and one business user outside the project is a condition of M10 instead of M9. The box above stays unticked until that outside walkthrough happens.

## Research before building

Complete these and record the findings, with sources, in a short note in the repository before writing code. If a finding contradicts this spec, update the spec first.

- **M9 · Interface study.** How JaamSim, PrePoMax, AnyLogic and FlexSim lay out canvas, palette, properties and results. What do users praise and complain about?
- **M9 · Node-editor patterns.** How general workflow tools handle large graphs, grouping and errors.
- **M6 (service) and M9 (interface) · Framework check.** Current state, licences and Linux support of Tauri, Electron, Qt and React Flow.
- **M11, only if the owner keeps WSL · WSL distribution.** How to ship and update a prepared WSL image, and its memory cost on a low-tier machine.
- **Phase 3 · Engine packaging.** Environment managers that can install compiled solvers reproducibly.

## Acceptance tests

| Test | Milestone | Checked by | Evidence |
| --- | --- | --- | --- |
| A pointer-only end-to-end test (Playwright or tauri-driver; Tauri's documentation lists `tauri-driver` for Linux and Windows, read 2026-11-06, not yet run) builds, runs and views the coffee shop; the saved model equals `examples/coffee_shop.json` except `ui`; `till.wait.mean` is within 3 standard errors of 270 s at the seed fixed in the test (the spec 2 pass rule) | M9 | agent; the owner repeats it by hand once before release |  |
| Every interface action is reproducible by API: the end-to-end request log contains only documented `/v1` routes | M9 | agent |  |
| Route table test | M6 | agent | `tests/service/test_routes.py` |
| A run survives a client disconnect | M6 | agent |  |
| Reopening the interface mid-run shows its progress | M9 | agent |  |
| The app works with outbound network blocked | M6 | agent |  |
| Fresh install to first result under ten minutes on Linux in a clean container | M11 | agent |  |
| Fresh install to first result under ten minutes on Windows | M11 | owner |  |
| All Phase 1 templates run on a machine or virtual machine capped to the low tier | M10 | agent on a capped container, owner confirms |  |

## Changes in this version

2026-11-05, version 0.3, spec review council:

- C18 (PRD-2, ARCH-9, ARCH-19, TEST-8): Phase 1 native on Windows as proposed default; packaging; tier testing; performance targets measured per protocol.
- C19 (ARCH-9, ARCH-18, ARCH-8, PRD-11, PRD-13): service rules rewritten: token over WebSocket, discovery file, hardening, lifetime, run queue, revisions, client header, first start.
- C20 (ARCH-6, ARCH-7, ARCH-14, ARCH-10, TEST-17, ARCH-8, ARCH-5): endpoints for templates, schema, project events, data, open; run request by domain; table names; route table test.
- C21 (ARCH-13, ARCH-8): edit semantics, `PUT .../model` saving rule, new edit kinds, status codes.
- C22 (ARCH-5, ARCH-12, ARCH-6, ARCH-17, PRD-12, PRD-11, PRD-13, PRD-7): scenario in events, reconnect semantics, `project.json` fields, external edits, results footer.
- C23 (TEST-9, PRD-10, TEST-1, TEST-8, TEST-12, PRD-2): version line, design checklist split with owner fallback, research items tagged, acceptance table.
- Verifier follow-up: the M9 end-to-end test uses the spec 2 pass rule (3 × standard error at a fixed seed).
- 2026-11-06, review of PR #1: `set_parameter` and `set_experiment` create the parameter or experiment when `id` is new, so a project started without a template can gain parameters and experiments through edits (and so through the MCP `edit_model` tool).
- 2026-11-06, M9 design (AKS-118, ahead of the milestone order at the owner's request): the five session items of "Design before building" are done in `docs/design/`; the owner walkthrough stays open. Framework check: React, React Flow and Tauri 2 confirmed, Tauri at 2.11.1 or later for advisory GHSA-7gmj-67g7-phm9; warning line updated. Gaps the design found, each closed by the simplest reading: the Canvas screen of an `optimization` model is a form; `set_path` and `remove_path` reach `variables` and `objective`, which no edit could change before; new `set_label` edit, since no edit could set a component's `label`; undo and redo write stored models with `PUT .../model`; an external reload clears the undo history; new "References" rule for blocks without ports. The end-to-end test row notes that `tauri-driver` is documented for Linux.
- 2026-11-06, owner design review (AKS-118): design system version 2 in `docs/design/` (Sanzo Wada palette, bundled fonts, Phosphor icons, block shapes, charts). Spec text aligned with the owner's choices: the optimization Canvas screen has a table view and a diagram view; Delete asks for confirmation unless turned off; external edits are marked for the user to accept or reject; reference lines differ by kind. Walkthrough fallback taken by the owner: the outside walkthrough is a condition of M10; warning line updated. Logged for a later spec change, not made here: results costs, a "Compare options" Build answer (spec 4), a never-reused id counter, `domain` on project creation (M6), and the chart data additions of `docs/research/spec-3-results-visualization.md`.
- 2026-11-07, service skeleton (AKS-110), found while building `src/lcsim/service/` and its research note `docs/research/spec-3-service-framework-check.md`: the warning line says the service skeleton is built and the service framework re-checked; "Architecture" confirms FastAPI and names uvicorn with websockets, not `uvicorn[standard]`; "Hardware tiers" says how cores, memory and graphics are detected, the tier thresholds (90% of nominal memory; `low` when memory is unknown), where the first tier is stored and how `workers` follows it; "Service rules" says how the token is drawn and checked (401 with E182 on every HTTP route, the WebSocket close reason), the fields, configuration folder and removal of `service.json`, how a second start probes (and, after the review of PR #34, the `service.lock` that makes two simultaneous starts give one service), that Host and Origin rejection is 403 with E183 and an upgrade without `Origin` passes, that no `Origin` is allowed until M9, what idle means for the lifetime, and that a request without `X-Client` counts as `script` and another value is refused before any route runs (review of PR #34); "Endpoints" adds `domain` to `POST /v1/projects` with the default `optimization` model (the owner design review's "`domain` on project creation (M6)"), and notes on the layouts of `system`, `engines`, the composed schema (`x-component-types`), a component type, `templates` before M10, the projects list, creation (absolute empty `path`, revision 0, layout 1; after the review of PR #34, `projects.json` holds absolute paths) and open; "Status codes and errors" adds 403, 405 and 500 and names the `error.code` of each status (new service codes E182 to E187 in spec 1); "Project folder" fixes `created`, `layout_version` and the first `model_revision`. All owner to confirm.
