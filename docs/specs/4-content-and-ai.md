# Spec 4: Content, Learning and AI Access

> Version 0.3 · working copy in the repository (source of truth, owner to confirm) · changes are listed under "Changes in this version".

This spec covers what makes the tool usable by non-experts: ready-made templates, lessons, findings in plain language, and an MCP server so any assistant can build and run models.

> **Warning: untested.** The MCP tools have never run against a real assistant; expect their names, inputs and descriptions to change once one uses them. The finding thresholds (0.85, 0.30, 10%) are proposals checked on a single model. The ten templates are named but not written. Verify each at its milestone and update this spec. See "Known gaps" in the Build guide.

## Scope

- **In:** the Phase 1 template library, Learn and Build modes, the findings generator, the MCP server.
- **Out:** embedding a language model in the product. Users connect their own.

## Template library

Each template is a model file, a short lesson, the expected results and one exercise.

| Template | Teaches | For | Blocks exercised | Scope touched |
| --- | --- | --- | --- | --- |
| Coffee shop queue | Arrivals, service, waiting | Students | source, server, sink | people |
| Three-machine production line | Bottlenecks, buffers | Both | source, server, queue, delay, sink | machines |
| Machine breakdowns | Failure and repair, availability | Both | source, server, failure, sink | machines |
| Clinic patient flow | Routing, shared staff | Both | source, branch, resource_pool, server, sink | people |
| Warehouse pick and pack | Batching, shifts | Business | source, batch, unbatch, delay, schedule, server, sink | goods movement, people |
| Inventory reorder point | Stock rules, stock-outs | Business | source, store, sink | materials as stock |
| Product mix | Linear programming | Students | optimization domain | materials as inputs |
| Transport plan | Network optimization | Business | optimization domain | movement |
| Staff rota | Integer programming | Business | optimization domain | people |
| How many machines? | Simulation-based optimization | Both | simulation-based search | machines |

Phase 1 covers machines and people as resources, materials as stock, and movement as transport time. Physical movement, material behaviour and physics arrive in Phases 2 and 3. A template's model may extend the example file of the same name.

## Learn and Build modes

- **Learn:** opens a template with a guided walkthrough. Each step highlights one block and explains it. The exercise asks the user to change something and predict the result.
- **Build:** asks what the user wants to find out, suggests the closest template, and offers data import, which is optional (see "Build mode").

Both modes use the same canvas and the same model file.

## Findings in plain language

A rule set reads the results and writes short findings ahead of any chart.

| Finding | Rule |
| --- | --- |
| Bottleneck | The server with the highest utilization, when that is at least the bottleneck threshold |
| Unstable system | Arrivals exceed capacity, so queues grow without limit |
| Idle capacity | A server or pool below a set utilization |
| Not enough runs | A confidence interval on a key metric too wide to act on, or too wide to separate two scenarios |
| Optimization result | Best values found, the gain over the starting point, and which constraints are tight |

Findings are produced by fixed rules, so they are the same every time and work offline.

## MCP server

The service exposes these tools to any connected assistant. Each one maps to an API endpoint from spec 3.

| Tool | Does |
| --- | --- |
| `list_templates` | Names and descriptions of available templates |
| `get_schema` | The model format and the documentation of each block type |
| `create_model` | Starts a model from a template or from nothing |
| `edit_model` | Applies a change to components, connections or parameters |
| `validate_model` | Returns errors in plain language |
| `run_model` | Starts a run and returns its id |
| `get_run_status` | Progress and state |
| `get_results` | Summary, findings and requested tables |
| `list_engines` | What is installed and what it can do |

Rules for assistant access:

- **Model files only.** No tool accepts arbitrary code or shell commands.
- **Same validation.** Assistant-built models pass the same checks as hand-built ones.
- **Visible to the user.** Models an assistant creates open on the canvas, where the user can inspect and change them.
- **Bounded runs.** Run time and memory limits apply to every run.

## Detailed specification

The sections below are binding. Where they differ from the summary above, these win. None of this has been built.

### Template package

```text
templates/<template_id>/
  template.json   id, title, summary, audience, concepts, estimated minutes
  model.json      a valid model file
  lesson.md       the walkthrough, one section per step
  expected.json   metric name, expected value, tolerance, source
```

- Each lesson step names one component to highlight and gives up to 80 words of explanation.
- The last step is an exercise: a change to make, a prediction to choose, and the explanation shown after the run.
- A template is accepted only if a run reproduces every value in `expected.json` within its tolerance.
- `source` is `theory` (the formula), `benchmark` (a `benchmarks/<case>` id) or `recorded` (seed, engine version, date). Every simulation template has at least one `theory` or `benchmark` entry; `recorded` entries are regression checks only. Optimization templates cite the published optimum. Every simulation template sets a non-zero `warmup`.

### Build mode

Build mode is a fixed form, not a conversation. Step 1 asks "What do you want to find out?" with answers and the template each opens: how long will people or items wait (Coffee shop); where is the bottleneck (Three-machine line); how much does downtime cost (Machine breakdowns); how many staff or machines do I need (How many machines); how much stock should I hold (Inventory reorder point); what mix, plan or rota is best (Product mix, Transport plan or Staff rota by a second question). Step 2 asks "Do you have data?": "Yes, import a file" (Data screen) or "No, I will estimate" (Canvas with the template's parameters open). Build mode never requires a data file.

### Finding rules

Thresholds are proposed defaults and are user-adjustable.

| Finding | Fires when | Wording pattern |
| --- | --- | --- |
| `bottleneck` | A server has the highest utilization in the model (ties: the longest mean wait) and it is at least 0.85; utilization is relative to available capacity (spec 2), so a failing or part-time server is judged on the time it could work | "{server} is the bottleneck: busy {utilization} of the time, with an average wait of {wait}." |
| `unstable` | Validation raised W201; the finding restates it in plain language for the affected server (one computation, not two) | "{server} cannot keep up. Work arrives faster than it can be done, so the queue will keep growing." |
| `idle_capacity` | A server's utilization (relative to available capacity) is below 0.30 and the server has no `schedule` | "{server} is idle {idle} of the time." |
| `not_enough_runs` | For each key metric (every metric named in an objective or constraint, every `<sink>.throughput` and `<sink>.cycle_time.mean`, and `<server>.wait.mean` for the server with the highest utilization): the half-width exceeds 10% of the mean and the mean is at least 60 s (time metrics) or 1 per hour (throughput). One finding per run and scenario, listing the metrics. When two scenarios are compared, it also fires for a key metric whose paired-difference interval includes zero and has a half-width above 10% of the smaller mean | "The estimates for {metrics} are still uncertain: {metric} is {mean} plus or minus {half_width}. About {n_required} replications would be needed for a 10% interval." or "{scenario_a} and {scenario_b} cannot be told apart on {metric} yet." |
| `optimization_result` | An optimization finishes | "Best found: {settings}. {metric} improved from {before} to {after}." where {before} is the baseline candidate's confirmed objective |

n_required = n × (half_width / (0.1 × mean))², rounded up to the next 10. Findings carry a `scenario` field. Evidence values are in SI units as in `summary.json`; the text uses display units. Test models live in `tests/findings/fixtures/<rule>_fires.json` and `<rule>_silent.json`; the coffee shop (half-width 4.8% of the mean) is the silent model for `not_enough_runs` and `bottleneck`; the M1 three-machine line is the firing model for both. The original three-machine-line check (0.90, half-width 26%) is unverified until that model exists; M8 repeats it and M10 re-checks all thresholds on the ten templates. Thresholds stay proposals until then.

Checked against the prototype's three-machine line: `bottleneck` fires for the weld station at 0.90, and `not_enough_runs` fires for its wait, where the half-width is 26% of the mean. Neither fires for the coffee shop.

Each finding is one object:

```json
{"rule": "bottleneck", "severity": "info", "component": "weld", "scenario": "default",
 "text": "weld is the bottleneck: busy 90% of the time, with an average wait of 17.3 min.",
 "evidence": {"weld.utilization": 0.90, "weld.wait.mean": 1038.8}}
```

### MCP tools

Each tool calls the spec 3 API and returns its response. Inputs and outputs are JSON.

| Tool | Input | Output | Calls |
| --- | --- | --- | --- |
| `list_templates` | none | Array of `{id, title, summary}` | `GET /v1/templates` |
| `get_schema` | optional `component_type` | The JSON Schema, or one component type's settings, ports and description | `GET /v1/schema` or `GET /v1/schema/components/{type}` |
| `list_projects` | none | Array of `{project_id, name}` | `GET /v1/projects` |
| `create_model` | `name`, optional `template_id` | `{project_id, model}` | `POST /v1/projects` |
| `get_model` | `project_id` | The model file | `GET /v1/projects/{pid}/model` |
| `edit_model` | `project_id`, `edits` as in spec 3, optional `base_revision` | `{model, revision, issues}`; E181 is returned as data | `POST /v1/projects/{pid}/model/edits` |
| `validate_model` | `project_id` | `{issues}` | `POST /v1/projects/{pid}/validate` |
| `run_model` | `project_id`, optional `experiment_id` (required for a `process` model, absent for an `optimization` model, as spec 3 defines) | `{run_id}` | `POST /v1/projects/{pid}/runs` |
| `get_run_status` | `run_id` | `{state, fraction, message}` | `GET /v1/runs/{rid}` |
| `get_results` | `run_id`, optional `tables` | `{summary, findings, tables}` | `GET /v1/runs/{rid}/summary` plus one `GET /v1/runs/{rid}/tables/{name}?format=json` per requested table |
| `list_engines` | none | Installed adapters and capabilities | `GET /v1/engines` |

Behaviour an assistant can rely on:

- **Errors are data.** A failed edit returns the issues with codes and hints; it does not raise a protocol error. The assistant reads them and corrects the model.
- **Edits are rejected only when they cannot be applied.** An edit is rejected only when it cannot be applied: unknown or duplicate component id, unknown type, unknown parameter or experiment, a `path` whose parent does not exist. Rejections are issue objects with code E180 and `path` `/edits/<n>`; the batch is then not applied. A batch that applies is saved even if validation then reports errors; the response carries the model, its revision and the issues (spec 3).
- **Runs are asynchronous.** `run_model` returns at once; the assistant polls `get_run_status`.
- **Tool descriptions teach the format.** Each tool's description includes one worked example, since the assistant sees nothing else.

### Limits

- The MCP server itself allows at most two unfinished runs per project that it started, tracked in memory; a third request returns an error object.
- Default run limits: 10 minutes and half of system memory, adjustable in settings.
- The MCP server reads and writes only inside project folders.

### Assistant acceptance case

The fixed description lives in `tests/mcp/coffee_shop_description.txt`:

> Customers arrive at a coffee shop about every 2 minutes at random. One till serves them; serving takes about 1.5 minutes on average, also at random. Simulate 200 hours after a 10-hour warm-up, 30 times, and tell me the average wait and how busy the till is.

Pass criteria, independent of ids: the project validates with zero errors; the run reaches `done`; the server's `wait.mean` is within 3 standard errors of 270 s and its `utilization` within 3 standard errors of 0.75 (the spec 2 pass rule; the standard error is the half-width divided by the t quantile the summary used).

- **Level 1.** `tests/mcp/test_coffee_shop_scripted.py` drives the MCP server with a scripted client that sets `seed` 12345, in CI.
- **Level 2.** A real assistant, named with its model, completes the case within three attempts; its run may use any seed. The transcript is saved as `docs/research/spec-4-mcp-trial-<date>.md`; tool changes it caused are logged in `DECISIONS.md`.

## Research before building

Complete these and record the findings, with sources, in a short note in the repository before writing code. If a finding contradicts this spec, update the spec first.

- **M7 · MCP.** Current protocol version, the official Python server library, and how desktop assistants connect to local servers.
- **M7 · Assistant tool design.** What the published simulation-automation systems found about tool granularity, validation loops and error messages.
- **M10 · Teaching practice.** How simulation and operations research are taught, and which worked examples recur across textbooks.
- **M10 · Template sources.** Example problems that may be reused freely, with their expected answers.
- **M8 · Findings wording.** How commercial tools phrase bottleneck and stability findings for non-experts.

## Acceptance tests

| Test | Milestone | Checked by | Evidence |
| --- | --- | --- | --- |
| Every template reproduces its expected values, with at least one `theory` or `benchmark` source | M10 | agent |  |
| A first-time user completes one Learn walkthrough without outside help (one outside tester; fallback as in spec 3) | M10 | owner |  |
| Each finding rule fires on its `_fires` fixture and is silent on its `_silent` fixture | M8 | agent | `tests/findings` |
| A Build-mode user without data reaches a completed run changing only parameters | M9/M10 | agent via the end-to-end test |  |
| The scripted MCP case passes | M7 | agent | `tests/mcp/test_coffee_shop_scripted.py` |
| A real-assistant transcript meets the acceptance case | M7 | owner, or agent if an MCP-capable assistant is available | `docs/research/spec-4-mcp-trial-<date>.md` |
| No MCP tool reads or writes outside the project folder | M7 | agent |  |

## Changes in this version

2026-11-05, version 0.3, spec review council:

- C24 (PRD-6, PRD-7, SIM-18, ARCH-19, SIM-8, PRD-14, TEST-18, SIM-17): template table with blocks and scope; Phase 1 scope sentence; summary findings aligned; Build mode form; `expected.json` sources.
- C25 (SIM-9, PRD-14, SIM-10, SIM-12, ARCH-10, SIM-18, ARCH-12, TEST-17, SIM-19, PRD-8): finding rules rewritten; `n_required`; fixture layout; threshold status.
- C26 (ARCH-7, ARCH-8, ARCH-13, TEST-10, TEST-1, TEST-12): MCP tools mapped to endpoints; `run_model` by domain; edit semantics; limits; assistant acceptance case; research items tagged; acceptance table.
- Verifier follow-up: the summary Build bullet says data import is optional, matching "Build mode".
