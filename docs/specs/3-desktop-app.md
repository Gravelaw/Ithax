# Spec 3: Desktop Application

> Version 0.3 · working copy in the repository (source of truth, owner to confirm) · changes are listed under "Changes in this version".

The app is two programs: an engine service that does all the work, and an interface that talks to it only through an API. That split is what lets a Windows interface drive Linux engines.

> **Warning: untested.** Nothing in this spec has been built. The interface frameworks were re-checked on 2026-11-06 (`docs/research/spec-3-framework-check.md`); the service framework is re-checked at M6. The performance targets are proposals. This spec defines behaviour; the user flows, wireframes, canvas rules, design system and accessibility check are in `docs/design/` (2026-11-06), but the owner's walkthrough is outstanding, and interface code must not start until the "Design before building" checklist is complete. See "Known gaps" in the Build guide.

## Scope

- **In:** the engine service, its API, the interface, project storage, data import, packaging, hardware tiers.
- **Out:** the model format (spec 1), engines (specs 2, 5, 6), templates and assistant tools (spec 4).

## Architecture

| Part | Role | Proposed technology |
| --- | --- | --- |
| Engine service | Validates models, schedules runs, hosts engine adapters, serves results | Python with FastAPI, on Linux |
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
2. **Canvas:** drag blocks from a palette, connect them, edit properties in a side panel. Validation errors appear on the offending block. For an `optimization` model, which has no components, the screen shows a form of variables, objective and constraints in place of the graph.
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

## Packaging

- **Linux:** one installable package containing interface, service and Phase 1 engines.
- **Windows:** one installer containing interface, service and Phase 1 engines (proposed default); alternative, an installer plus a prepared WSL image.
- **Engines:** Phase 1 engines are bundled; an environment manager is introduced with the first Phase 3 engine, so later physics engines can be added without reinstalling the app.

## Detailed specification

The sections below are binding. Where they differ from the summary above, these win. None of this has been built.

### Service rules

- **Local only.** The service listens on `127.0.0.1` and refuses other addresses unless the user turns on remote access.
- **Token.** `Authorization: Bearer <token>`; the token is 32 random bytes, base64url. WebSocket connections authenticate with a first text message `{"token": "..."}` within 5 seconds, else the server closes with code 1008, because webviews cannot set headers.
- **Discovery.** The service binds 127.0.0.1 on a port chosen by the operating system and writes `service.json` `{port, token, pid, started}` with mode 0600 in its configuration folder; the interface, the MCP server and scripts read it.
- **One service per user.** A second start reads the file, probes `GET /v1/system`, and exits if it answers; otherwise it overwrites the file.
- **Hardening.** Requests whose `Host` is not `127.0.0.1:<port>` or `localhost:<port>` are rejected; no CORS headers are sent; WebSocket upgrades carrying an `Origin` other than the interface's own (fixed at M9) are rejected.
- **Lifetime** (proposed default, owner to confirm): the service stays up while runs are active or clients are connected and exits after 30 idle minutes; the interface and the MCP server start it on demand.
- **Runs outlive the interface.** Runs are child processes of the service, not of the interface.
- **Run queue.** At most `max_concurrent_runs` (default 1, Settings) run at once; others wait in `queued` in arrival order; a run receives `workers` = cores of the active tier.
- **Revision.** Every model write increments an integer `revision`, returned with the model and stored in `project.json`; `PUT .../model` and `POST .../model/edits` accept optional `base_revision`, and a mismatch returns 409 with `{"error": {"code": "E181", ...}, "model": <current>, "revision": N}` and applies nothing.
- **Client header.** Requests may carry `X-Client: ui|mcp|script`, recorded in the run manifest.
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
| `POST /v1/projects` | `{name, template?, path?}` | The new project |
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

- `POST /v1/projects`: without `template` the project holds `{format_version, meta: {name}, domain: "process", parameters: {}, components: [], connections: [], experiments: [{id: "base", length: "8 h", warmup: "0 s", replications: 30}], run: {target: "local", fidelity: "standard"}}`, which validates with no errors. Projects live under `<user data folder>/projects/<id>/` unless `path` is given (proposed); the service keeps `projects.json` in its configuration folder mapping id to path.
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

Every error body is `{"error": {"code", "message"}, "issues": [...]}`, where issues use the spec 1 issue object.

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

`project.json` holds `{id, name, created, layout_version, model_revision}`; `id` is a UUID4 string and is `pid`. The model's own `format_version` is inside `model.json`.

The folder is plain files so it can be copied, zipped or put under version control. The project folder, not the model file alone, is the unit to share when a model uses imported data; the Results screen's export produces a zip of the project folder.

### Canvas behaviour

These are functional rules. Visual design is covered by the checklist below.

- **Single source.** The canvas shows the model file and nothing else. Every canvas action is one or more model edits.
- **Add.** Dragging a block from the palette adds a component with a generated id, such as `server_2`, and default settings.
- **Connect.** Dragging from an output port to an input port sends `connect`. Dragging from an output port that is already connected replaces its connection.
- **Delete.** Removes the selection and its connections.
- **Undo and redo.** At least 100 steps, covering every model edit. Each step stores the model as it was; undo and redo write the stored model with `PUT .../model` and `base_revision`, because some edits (such as `set_setting` creating a new key) have no inverse edit.
- **Save.** Automatic after every edit. There is no save button.
- **Validate.** Runs half a second after the last edit. Issues appear as a marker on the block and in a list; selecting a list entry selects the block.
- **Run.** Disabled while errors exist, with the reason shown.
- **Rename.** Changing a component's id updates its connections and any references to its metrics.
- **External edits.** The canvas sends `base_revision` on every write and, on a `model` event whose revision it did not produce, reloads the model and shows a one-line notice naming the client. The reload clears the undo and redo history, so an undo cannot silently revert another client's change.
- **References.** Blocks without ports (`resource_pool`, `schedule`, `failure`) are placed like any block. Their `pool` and `target` settings are drawn as dashed reference lines, which are not connections; they are set in the side panel with `set_setting`.

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
