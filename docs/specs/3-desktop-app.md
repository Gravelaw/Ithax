# Spec 3: Desktop Application

The app is two programs: an engine service that does all the work, and an interface that talks to it only through an API. That split is what lets a Windows interface drive Linux engines.

> **Warning: untested, and design is missing.** Nothing in this spec has been built. The frameworks named were not re-checked, and the performance targets are proposals. This spec defines behaviour only: user flows, wireframes and the design system do not exist yet, and interface code must not start until the "Design before building" checklist is complete. See "Known gaps" in the Build guide.

## Scope

- **In:** the engine service, its API, the interface, project storage, data import, packaging, hardware tiers.
- **Out:** the model format (spec 1), engines (specs 2, 5, 6), templates and assistant tools (spec 4).

## Architecture

| Part | Role | Proposed technology |
| --- | --- | --- |
| Engine service | Validates models, schedules runs, hosts engine adapters, serves results | Python with FastAPI, on Linux |
| API | The only way in: HTTP for requests, WebSocket for live progress | Local address only by default |
| Interface | Canvas, forms, charts | React with React Flow, packaged as a desktop app with Tauri |
| Storage | One folder per project: model file, imported data, runs | Files, plus SQLite as a run index |

On Linux both parts run natively. On Windows the interface runs natively and the service runs under WSL.

## API

| Endpoint | Purpose |
| --- | --- |
| `/projects` | Create, open, list |
| `/models` | Read and write the model file |
| `/validate` | Run both validation passes |
| `/runs` | Start, cancel, list; `/runs/{id}/events` streams progress |
| `/results` | Summary, tables, fields |
| `/engines` | Installed adapters and their capabilities |
| `/system` | Detected hardware and the active tier |

The interface uses no private channel. Anything it can do, a script or an assistant can do through the same API.

## Screens

1. **Home:** recent projects, template gallery, Learn or Build entry.
2. **Canvas:** drag blocks from a palette, connect them, edit properties in a side panel. Validation errors appear on the offending block.
3. **Data:** import CSV or Excel, map columns, fit a distribution to a column.
4. **Experiment:** run length, replications, scenarios, optimization setup.
5. **Run monitor:** progress, live key numbers, cancel.
6. **Results:** plain-language findings first, then charts and tables; export to CSV and PDF.
7. **Settings:** run targets, hardware tier, engine management.

## Hardware tiers

- On first start the service detects cores, memory and graphics, and sets the tier.
- The tier sets defaults: parallel replications now, mesh size limits later.
- Graphics hardware is never required. Both Nvidia and Intel graphics are used when present.
- Low and mid tiers are tested on the development machine by limiting the cores and memory given to WSL.

## Packaging

- **Linux:** one installable package containing interface, service and Phase 1 engines.
- **Windows:** an installer for the interface, plus a prepared WSL image holding the service and engines.
- **Engines:** installed and updated through an environment manager, so later physics engines can be added without reinstalling the app.

## Detailed specification

The sections below are binding. Where they differ from the summary above, these win. None of this has been built.

### Service rules

- **Local only.** The service listens on `127.0.0.1` and refuses other addresses unless the user turns on remote access.
- **Token.** On first start the service writes a random token to a file in the user's configuration folder. Every request carries it in an `Authorization` header. This stops other programs and web pages on the machine from driving the service.
- **One service per user.** A second start finds the first and exits.
- **Runs outlive the interface.** Runs are child processes of the service, not of the interface.
- **Versioned paths.** Every path starts with `/v1`.

### Endpoints

| Method and path | Request | Response |
| --- | --- | --- |
| `GET /v1/system` |  | Cores, memory, graphics, active tier |
| `GET /v1/engines` |  | Installed adapters with their capabilities |
| `GET /v1/projects` |  | List of projects |
| `POST /v1/projects` | `{name, template?}` | The new project |
| `GET /v1/projects/{pid}/model` |  | The model file |
| `PUT /v1/projects/{pid}/model` | A whole model file | Validation issues |
| `POST /v1/projects/{pid}/model/edits` | `{edits: [...]}` | The updated model and validation issues |
| `POST /v1/projects/{pid}/validate` |  | Validation issues |
| `POST /v1/projects/{pid}/data` | An uploaded CSV or Excel file | Column names, types and a preview |
| `POST /v1/projects/{pid}/runs` | `{experiment_id, target?}` | `202` with `{run_id}` |
| `GET /v1/projects/{pid}/runs` |  | List of runs with state |
| `GET /v1/runs/{rid}` |  | State, progress, timings |
| `POST /v1/runs/{rid}/cancel` |  | New state |
| `GET /v1/runs/{rid}/events` | WebSocket | Stream of progress events |
| `GET /v1/runs/{rid}/summary` |  | `summary.json` plus findings |
| `GET /v1/runs/{rid}/tables/{name}` | `?format=json` or `csv` | Table rows |

### Model edits

Edits are applied in order, all or none. The interface and the MCP server both use this one mechanism.

| Edit | Fields |
| --- | --- |
| `add_component` | `id`, `type`, `params`, optional `ui` |
| `remove_component` | `id`; its connections are removed with it |
| `set_setting` | `id`, `path`, `value` |
| `connect` | `from`, `to` |
| `disconnect` | `from` |
| `set_parameter` | `id` and any of `value`, `type`, `min`, `max` |
| `set_experiment` | `id` and any experiment fields |
| `set_ui` | `id`, `ui` |

### Status codes and errors

| Code | When |
| --- | --- |
| 200 | Success |
| 202 | Run accepted |
| 400 | Request malformed |
| 401 | Token missing or wrong |
| 404 | Project, run or table not found |
| 409 | Action not allowed in the run's current state |
| 422 | Model has validation errors; the body lists the issues |

Every error body is `{"error": {"code", "message"}, "issues": [...]}`, where issues use the spec 1 issue object.

### Progress events

```json
{"type": "progress", "fraction": 0.4, "message": "Replication 12 of 30"}
{"type": "metrics", "values": {"till.wait.mean": 268.1}}
{"type": "state", "state": "done"}
```

### Project folder

```text
<project>/
  project.json    name, created date, format version
  model.json      the current model
  data/           imported files, unchanged, plus a column index
  runs/           one folder per run, as in spec 1
  index.sqlite    run index, rebuilt from runs/ if missing
```

The folder is plain files so it can be copied, zipped or put under version control.

### Canvas behaviour

These are functional rules. Visual design is covered by the checklist below.

- **Single source.** The canvas shows the model file and nothing else. Every canvas action is one or more model edits.
- **Add.** Dragging a block from the palette adds a component with a generated id, such as `server_2`, and default settings.
- **Connect.** Dragging from an output port to an input port sends `connect`. Dragging from an output port that is already connected replaces its connection.
- **Delete.** Removes the selection and its connections.
- **Undo and redo.** At least 100 steps, covering every model edit.
- **Save.** Automatic after every edit. There is no save button.
- **Validate.** Runs half a second after the last edit. Issues appear as a marker on the block and in a list; selecting a list entry selects the block.
- **Run.** Disabled while errors exist, with the reason shown.
- **Rename.** Changing a component's id updates its connections and any references to its metrics.

### Performance targets

All proposed, to be measured on the low tier:

- Service ready within 5 seconds of start.
- Canvas stays responsive with 200 components.
- Validation of a 200-component model within 200 milliseconds.
- Service uses under 300 MB of memory when idle.

## Design before building

This spec lists the screens and what each must do. It does not contain their visual or interaction design. These are needed before interface code is written:

- [ ] User flows for Learn mode and Build mode, from first launch to first result.
- [ ] Wireframes for the seven screens, the canvas first.
- [ ] Interaction rules for the canvas: adding, connecting, selecting, undo, zoom, error display.
- [ ] A small design system: colours, type, spacing, block and port styles, light and dark themes.
- [ ] A check against accessibility guidelines: keyboard use, contrast, text size.
- [ ] A walkthrough of the wireframes with two students and two business users.

## Research before building

Complete these and record the findings, with sources, in a short note in the repository before writing code. If a finding contradicts this spec, update the spec first.

- **Interface study.** How JaamSim, PrePoMax, AnyLogic and FlexSim lay out canvas, palette, properties and results. What do users praise and complain about?
- **Node-editor patterns.** How general workflow tools handle large graphs, grouping and errors.
- **Framework check.** Current state, licences and Linux support of Tauri, Electron, Qt and React Flow.
- **WSL distribution.** How to ship and update a prepared WSL image, and its memory cost on a low-tier machine.
- **Engine packaging.** Environment managers that can install compiled solvers reproducibly.

## Acceptance tests

- [ ] A user builds, runs and views the coffee shop model with the mouse alone.
- [ ] Every interface action is reproducible with API calls alone.
- [ ] Closing the interface mid-run does not stop the run; reopening shows its progress.
- [ ] The app works with the network disconnected.
- [ ] Fresh install to first result takes under ten minutes on Linux and on Windows (proposed target).
- [ ] The app starts and runs all Phase 1 templates when WSL is limited to the low tier.
