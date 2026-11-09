# Spec 4: Content, Learning and AI Access

> Version 0.6 · working copy in the repository (source of truth, owner to confirm) · changes are listed under "Changes in this version".

This spec covers what makes the tool usable by non-experts: ready-made templates, lessons, findings in plain language, and an MCP server so any assistant can build and run models.

> **Warning: untested.** The MCP tools have run against one real assistant, Claude Code with Claude Opus 5.5 (M7, `docs/research/spec-4-mcp-trial-2026-11-08.md`), which changed two descriptions; other assistants may still find names, inputs or descriptions to change. The finding thresholds (0.85, 0.30, 10%) are proposals, checked at M8 on the coffee shop and the three-machine line only, on their fixtures (AKS-117) and end to end through the service (AKS-135); the user can change them in `settings.json` (spec 3). Six of the ten templates are written (coffee shop, three-machine line and machine breakdowns, AKS-122; clinic patient flow, warehouse pick and pack and inventory reorder point, AKS-139) and the other four are named but not written. Verify each at its milestone and update this spec. See "Known gaps" in the Build guide.

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
| Idle capacity | A server below a set utilization, unless a schedule sets its capacity |
| Not enough runs | A confidence interval on a key metric too wide to act on, or too wide to separate two scenarios |
| Optimization result | Best values found, the gain over the starting point, and which constraints are tight |

Findings are produced by fixed rules, so they are the same every time and work offline.

## MCP server

The MCP server, a separate program that an assistant starts, exposes these tools to any connected assistant. Each one maps to an API endpoint of the engine service from spec 3.

| Tool | Does |
| --- | --- |
| `list_templates` | Names and descriptions of available templates |
| `get_schema` | The model format and the documentation of each block type |
| `list_projects` | The projects the service knows |
| `create_model` | Starts a model from a template or from nothing |
| `get_model` | The current model file and its revision |
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

The sections below are binding. Where they differ from the summary above, these win. The MCP server, its tools, limits and acceptance case are built (M7: AKS-115, AKS-134, AKS-116); the finding rules are built and reach the run summary and `get_results` (M8: AKS-117, AKS-135); the template package format, its loader, the template endpoints and the first three templates are built (M10: AKS-122), and three more templates (AKS-139); the other templates and Learn and Build modes are not.

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

How a package is written and checked (AKS-122, from `docs/research/spec-4-teaching-practice.md` and `docs/research/spec-4-template-sources.md`; owner to confirm). The templates live in `templates/<template_id>/` at the repository root; the loader is `lcsim.templates` and the service serves the folder (spec 3 "Endpoints" notes). A package is accepted only when every rule below holds; each problem is an issue (spec 1), E195 for the package, and the model's own issues with their own codes, their `path` a JSON Pointer into the package whose first segment is the file's name (`/template.json/minutes`, `/model.json/experiments/0/warmup`, `/lesson.md/steps/2`, `/expected.json/3/source`). A package with any issue, error or warning, is not offered.

- **`template.json`** is one JSON object with exactly these keys: `id` (the folder's name, an identifier as spec 1 defines it), `title` (non-empty text), `summary` (non-empty text, one or two sentences), `audience` (`"Students"`, `"Business"` or `"Both"`, the "For" column of "Template library"), `concepts` (an array of one or more non-empty texts), `minutes` (the estimated minutes, a whole number from 1 to 120), `experiment` (for a `process` model the id of the experiment the lesson and the template test run, which must set a `seed`, so its results repeat; `null` for an `optimization` model), `origin` (non-empty text: where the problem comes from), `licence` (an SPDX identifier: `AGPL-3.0-only` for a problem written for this project, else the source's, which must permit reuse; spec 0 "Risks") and `exercise`, an object `{edits}` whose `edits` is a non-empty array of spec 3 model edits ("Model edits") that make the exercise's change; the changed model must load with no error.
- **`model.json`** is a model file (spec 1) that loads with no issue at all, warnings included, and has no `empirical` `data` reference (a template carries no data folder). For a `process` model the named experiment's `warmup` is above 0 s. Its `length` includes the warm-up (spec 1 "Experiments"), and the lesson states the time measured as `length` minus `warmup`.
- **`lesson.md`** is Markdown: a first line `# <title>` equal to `title`, then one `## <heading>` section per step, at least two. A step's first non-empty line is ``Component: `<id>` ``, naming what the step highlights: a component of a `process` model, or a variable, a constraint or `objective` of an `optimization` model. Its text, every line after that one, holds at most 80 words (a word is a run of characters between spaces or line ends holding a letter or a digit). The last step's heading starts with `Exercise` and its text is three `### ` parts in this order: `### Change` (what to change, at most 80 words), `### Prediction` (two to four choices, one per line, each `- [ ] <text>` or `- [x] <text>` with exactly one `[x]`, the right one, each at most 30 words) and `### Explanation` (shown after the run, at most 80 words). No other step has a `###` part.
- **`expected.json`** is an array of one or more rows, each an object with exactly the keys `metric`, `value`, `method`, `source`, `reference` and optionally `run`. `metric` is a name as `summary.json` reports it: for a `process` model a metric of the scenario `default` (spec 1 "Metric names", every measure spec 2 lists for the component's type and `model.wip.mean`), or `search.best.<variable>` for an experiment with a `search`; for an `optimization` model `objective` or `variables.<id>`. `value` is a finite number in SI units, as `summary.json` reports it. `method` is one of spec 2's pass rules: `three_se` (|mean − value| ≤ 3 standard errors, the standard error being the summary's `half_width` divided by the t quantile it used, t(1 − (1 − `confidence`)/2, `n` − 1)), `exact` (the summary's mean and `value` equal to four significant figures) or `sig_figs_4` (a single value, an optimization result or `search.best.<variable>`, equal to four significant figures); a `process` metric of the scenario takes `three_se` or `exact`. `source` is `theory`, `benchmark` or `recorded`; `reference` is non-empty text: for `theory` the formula with its citation, for `benchmark` text starting `benchmarks/<case>` naming a case that exists, for `recorded` the seed, the engine and its version, and the date. `run` is `template` (the default) for the model as written or `exercise` for the model after the exercise's edits. A simulation template has at least one `theory` or `benchmark` row for `template`, and every template has at least one row for `exercise`, backing the right prediction. Whether a `benchmark` case exists is checked by the template test, which gives the loader the cases of `benchmarks/`; the service, which has no benchmarks folder, checks only the reference's form.
- **The template test** (`tests/templates/test_templates.py`, marker `template`, in `bash scripts/check.sh`) loads every folder under `templates/` with the loader (no issue), runs the model and then the exercise's model through the experiment manager, `experiment` with the file's `seed`, `replications`, `length` and `warmup` as written (`null` for an optimization model), and judges every row of its `run`; a template is accepted only when every row passes.
- **Projects from a template.** `POST /v1/projects` with `template` copies the package's `model.json` into the new project, with `meta.name` set to the project's name and `meta.template` to the template's `id`; the lesson and the expected values stay in the package, read with `GET /v1/templates/{tid}` (spec 3).

The Phase 1 templates built so far (AKS-122, AKS-139), each problem written for this project (`AGPL-3.0-only`; sources and answers in `docs/research/spec-4-template-sources.md`):

| `id` | Model | Run | Theory or benchmark rows | Exercise |
| --- | --- | --- | --- | --- |
| `coffee_shop` | `examples/coffee_shop.json` with a description | `base`: 30 replications, `length` 200 h including 10 h of warm-up, so 190 h measured, seed 12345 | M/M/1 wait 270 s, queue 2.25, utilization 0.75, cycle time 360 s, throughput 1/120 per s (`benchmarks/mm1`); Little's law WIP 3.0; 5,700 arrivals in 190 h | `tills` 1 to 2: Erlang C wait 162/11 s, utilization 0.375 |
| `three_machine_line` | `examples/three_machine_line.json` with a `queue` `buffer` of capacity 10 between cut and weld, and weld's `queue_capacity` 0, so parts wait in the buffer | `base`: 30 replications, `length` 100 h including 20 h of warm-up, so 80 h measured, seed 12345 | Throughput 1/120 per s; weld utilization 0.9, paint 0.5 (λE(S)/c in a stable line with no loss); 2,400 arrivals in 80 h | `buffer` capacity 10 to 3: the flow rows hold, and cut's utilization and the cycle time rise (`recorded`) |
| `machine_breakdowns` | One machine (arrivals every 4 min, 2 min jobs) with a `failure`: time to failure mean 90 min, repair mean 10 min | `base`: 30 replications, `length` 200 h including 10 h of warm-up, so 190 h measured, seed 12345 | Availability 0.9 (MTTF/(MTTF + MTTR), `benchmarks/failure`); utilization 5/9 of available time; throughput 1/240 per s; 2,850 arrivals | Repair mean 10 to 5 min: availability 18/19, utilization 0.5278; the wait falls (`recorded`) |
| `clinic_patient_flow` | Patients every 5 min; a `branch` sends 3 in 5 to `exam_rooms` and 2 in 5 to `treatment_rooms`, servers of capacity 3 each, both 8 min and both naming the `resource_pool` `nurses` of capacity 2 | `base`: 30 replications, `length` 200 h including 10 h of warm-up, so 190 h measured, seed 12345 | Nurse utilization 0.8 (`benchmarks/resource_pool`); M/M/2 on the nurses: cycle time 4,000/3 s, WIP 40/9 (Erlang C, Little); room utilizations 0.32 and 0.2133 (branch split); throughput 1/300 per s; 2,280 arrivals | `nurses` 2 to 3: M/M/3, utilization 8/15, cycle time 573.87 s, WIP 1.9129; the rooms' waits fall from 978 and 652 s to 101 and 83 s (`recorded`) |
| `warehouse_pick_pack` | Orders every minute into a `batch` `carts` of 5; `pickers` (capacity 3, 9 min a cart) on a `schedule` of 1 picker from 22:00 to 06:00 and 3 from 06:00 to 22:00; a 3 min `delay`, an `unbatch` and a `packer` of 30 s; written fresh, not extending `examples/warehouse.json` (see below) | `base`: 30 replications, `length` 216 h including 24 h of warm-up, so 192 h measured (8 whole days), `record_interval` 1 h, seed 12345 | Cart wait 120 s (`benchmarks/batch_unbatch`); scheduled fraction 7/9 (`exact`); throughput 1/60 per s; packer utilization 0.5; 11,520 arrivals; the pickers' utilization 0.7694 is `recorded` (see below) | Overnight capacity 1 to 2: scheduled fraction 8/9, throughput 1/60 per s; the pickers' wait falls from 3,704 s to 311 s (`recorded`) |
| `inventory_reorder_point` | Customers every 6 h (4 a day) into a `store` with `initial` 70, `reorder_point` 20, `order_quantity` 50 and a constant `lead_time` of 5 d | `base`: 30 replications, `length` 1000 d including 50 d of warm-up, so 950 d measured, seed 12345 | The (R, Q) policy with Poisson demand (see below): stock mean 25.588, stock-outs 135.03, waiting customers 0.088181 and cycle time 1,904.7 s; orders 1/50 of the demand rate; throughput 4 per day; 3,800 arrivals | `reorder_point` 20 to 30: stock mean 35.501 and the same orders (theory); stock-outs 1.2 (`recorded`; theory 2.4414) |

How the AKS-139 templates read the blocks (each a proposed default, owner to confirm):

- **Clinic: M/M/c through a pool.** When every server naming a pool has at least as many units as the pool and every such server's service is the same exponential distribution, the pool is never idle while an item waits anywhere (an item waiting for a server unit means all that server's units are held, each in service or asking the pool), so the number of items in the system is the M/M/c birth–death process with c the pool's capacity, whatever the order: the model's work in progress and a common sink's cycle time are Erlang C's. The waits at each server are not: a server whose units are all held makes its next item wait while the other server's items go ahead (spec 2 "Pool"), so the check-ups wait 978 s and the dressings 652 s around the clinic's 853 s, `recorded`.
- **Warehouse: whole periods.** A template with a `schedule` measures whole periods and samples on whole hours (`record_interval` dividing the `period`), with an even number of periods measured, so the two halves of the warm-up check (spec 2 "Statistic definitions", W210) cover alike parts of the day; with 7 days measured and the default `record_interval` the warehouse raised W210 on a steady periodic run. The pickers' utilization is `recorded`, not theory: spec 2 counts no busy time beyond the available capacity, so the part of a cart a picker finishes after the evening shift ends adds nothing, and 0.7694 lies below the offered 43.2 picker-hours over the 56 available, 0.7714 (−0.53 standard errors at seed 12345, but not an exact answer). The model is written fresh rather than extending `examples/warehouse.json`: picking by cart makes a batch, not an order, the picker's unit; the example's branch is not among the blocks above; and a schedule on its pickers would make the orders reaching a batch after them non-Poisson, so the batch wait would have no closed form.
- **Inventory: the (R, Q) policy.** With unit demand and at most one order outstanding (an order of 50 against a lead-time demand of Poisson mean 20: a second only if 50 customers come within one lead time, probability 1.2 × 10⁻⁸), the store of spec 2 "Store" is the textbook (R, Q) policy with backorders (spec 2 says why), so the stock position is uniform on R + 1 to R + Q and the net stock a lead time later is the position less the lead-time demand: stock-outs λT·(1/Q)Σ P(D ≥ y), mean stock (1/Q)Σ E[(y − D)⁺], waiting customers their difference from the mean net stock R + (Q + 1)/2 − λL (Zipkin 2000, section 6.2). At a reorder point of 30 stock-outs are rare and bunched, so 30 replications measure them poorly: 1.2 at seed 12345, 3.65 standard errors below the theory's 2.4414, while 400 replications at seed 777 give 2.505 plus or minus 0.296 (+0.42); the exercise's stock-out row is therefore `recorded`, its stock mean theory.

### Build mode

Build mode is a fixed form, not a conversation. Step 1 asks "What do you want to find out?" with answers and the template each opens: how long will people or items wait (Coffee shop); where is the bottleneck (Three-machine line); how much does downtime cost (Machine breakdowns); how many staff or machines do I need (How many machines); how much stock should I hold (Inventory reorder point); what mix, plan or rota is best (Product mix, Transport plan or Staff rota by a second question). Step 2 asks "Do you have data?": "Yes, import a file" (Data screen) or "No, I will estimate" (Canvas with the template's parameters open). Build mode never requires a data file.

### Finding rules

Thresholds are proposed defaults and are user-adjustable: `finding_thresholds` in `settings.json` (spec 3 "Service rules", Finding thresholds), read each time the summary makes findings; a value that cannot be used is W220 (spec 1) and its default is used (AKS-135, owner to confirm).

| Finding | Fires when | Wording pattern |
| --- | --- | --- |
| `bottleneck` | A server has the highest utilization in the model (ties: the longest mean wait) and it is at least 0.85; utilization is relative to available capacity (spec 2), so a failing or part-time server is judged on the time it could work | "{server} is the bottleneck: busy {utilization} of the time, with an average wait of {wait}." |
| `unstable` | Validation raised W201; the finding restates it in plain language for the affected server (one computation, not two) | "{server} cannot keep up. Work arrives faster than it can be done, so the queue will keep growing." |
| `idle_capacity` | A server's utilization (relative to available capacity) is below 0.30 and the server has no `schedule` | "{server} is idle {idle} of the time." |
| `not_enough_runs` | For each key metric (every metric named in an objective or constraint, every `<sink>.throughput` and `<sink>.cycle_time.mean`, and `<server>.wait.mean` for the server with the highest utilization): the half-width exceeds 10% of the mean and the mean is at least 60 s (time metrics) or 1 per hour (throughput). One finding per run and scenario, listing the metrics. When two scenarios are compared, it also fires for a key metric whose paired-difference interval includes zero and has a half-width above 10% of the smaller mean | "The estimates for {metrics} are still uncertain: {metric} is {mean} plus or minus {half_width}. About {n_required} replications would be needed for a 10% interval." or "{scenario_a} and {scenario_b} cannot be told apart on {metric} yet." |
| `optimization_result` | An optimization finishes | "Best found: {settings}. {metric} improved from {before} to {after}." where {before} is the baseline candidate's confirmed objective |

n_required = n × (half_width / (0.1 × mean))², rounded up to the next 10. Findings carry a `scenario` field. Evidence values are in SI units as in `summary.json`; the text uses display units. Test runs live in `tests/findings/fixtures/<rule>_fires.json` and `<rule>_silent.json`, each a finished run (the run folder's `model.json` and `summary.json`, made by `tests/findings/make_fixtures.py`); the coffee shop (till utilization 0.749, wait half-width 3.7% of the mean) is the silent model for `not_enough_runs` and `bottleneck`; the M1 three-machine line (weld utilization 0.901, wait half-width 13.3%) is the firing model for both. M8 repeated the check on these two models, on their fixtures (AKS-117) and end to end through the service with the same values (AKS-135), and M10 re-checks all thresholds on the ten templates. Thresholds stay proposals until then.

Checked at M8 (AKS-117), each example's own experiment at seed 12345: on the three-machine line (30 replications of 100 h after 20 h of warm-up) `bottleneck` fires for the weld station at 0.901, and `not_enough_runs` fires for its wait, 15.7 min plus or minus 2.09 min, a half-width of 13.3% of the mean (n_required 60). On the coffee shop (30 replications of 200 h with 10 h of warm-up) neither fires: the till is at 0.749 and its wait is 4.46 min plus or minus 0.163 min, 3.7% of the mean (3.4% in M7's 210 h run). The prototype's check, not retained, gave 0.90 and 26%.

Each finding is one object; the three-machine line's, evidence rounded here:

```json
{"rule": "bottleneck", "severity": "info", "component": "weld", "scenario": "default",
 "text": "weld is the bottleneck: busy 90% of the time, with an average wait of 15.7 min.",
 "evidence": {"weld.utilization": 0.901, "weld.wait.mean": 941.5}}
```

How the rules read this table (AKS-117, research note `docs/research/spec-4-findings-wording.md`; each a proposed default, owner to confirm):

- **Input and output.** `lcsim.findings.find(summary, model, thresholds)` reads a finished run's `summary.json` and the model that ran, and computes nothing from the replications: every number is the summary's. It is a pure function (no run, file, network, solver, model or random number). Findings come in a fixed order: `optimization_result`, `unstable`, then for each scenario in the summary's order `bottleneck`, `idle_capacity` (servers in model order) and `not_enough_runs`, then the scenario pairs. `severity` is `info` for `bottleneck`, `idle_capacity` and a found optimum, `warning` for `unstable`, `not_enough_runs` and an optimization without one. `component` and `scenario` are `null` when a finding is not about one.
- **Thresholds** are an input with the defaults above: the two utilizations from 0 to 1, the share above 0 and at most 1, the floors (60 s, 1 per hour) at least 0. The service takes them from `settings.json` and refuses a value outside these ranges there, as W220, before the rules see it (AKS-135).
- **`bottleneck`** is judged in each scenario, among servers; ties by the longest mean wait, an undefined wait counting as the shortest, then the first in the model. For a server whose capacity a `schedule` (on it or on its pool) or a `failure` changes, the text says "busy {utilization} of the time it was available"; with no measured wait it ends after "of the time". It fires alongside `unstable` for an unstable server.
- **`unstable`** is one finding per server named by a W201 issue in `summary.json` `warnings`, with `scenario` `null` (W201 names a case, spec 1) and the issue's `path` and `message` as evidence.
- **`idle_capacity`** is judged among servers; "no `schedule`" means none on the server or on the pool it names. A server with a `failure` is judged and is "idle {idle} of the time it was available".
- **`not_enough_runs`.** Key metrics are taken in the order the table names them, each once, the busiest server as `bottleneck` picks it. The floor is 60 s for a time and 1 per hour for a rate, at or above; a key metric in another unit (a utilization in a constraint) is judged when its mean is not zero. `{metric}`, `{mean}` and `{half_width}` are those of the listed metric whose half-width is the largest share of its mean, `{n_required}` the largest of the listed metrics', and the interval named is the threshold's ("10%"). n_required is computed exactly from the decimals `summary.json` writes. For two scenarios (each entry of `differences`), the key metrics of both; the smaller of the two means must pass the floor; the finding's `scenario` is the later scenario. Common random numbers separate even close scenarios on the examples (two service means 0.7% apart, each wait plus or minus 26%, are separated), so the pair form fires only when the scenarios' random numbers decouple.
- **`optimization_result`.** For a search: "improved" when the best beats the baseline in the sense of the objective the experiment's `search` names (review of PR #42: two objectives may share a metric), otherwise "went from"; "Best found: the starting values, {settings}. No setting tried improved {metric}, which is {before}." when the baseline is the best; "Best found: {settings}. The starting values break a constraint; {metric} went from {before} to {after}." when the baseline is infeasible; "No setting tried meets every constraint. With the starting values, {settings}, {metric} is {before}." when the search is infeasible. When another confirmed feasible candidate exists, the text adds "It is clearly better than the next best setting tried." or "The next best setting tried cannot be told apart from it yet." (spec 2: the result states whether the best is separated). For a mathematical optimization, which has no starting point: "Best found: {variables}. The objective is {objective}, with {tight constraints} tight.", "No values meet every constraint: the problem is infeasible." or "The objective can be improved without limit: a bound or a constraint is missing."
- **Display units.** Times in the largest Phase 1 unit they reach and rates per hour, to three significant figures, a half-width in its mean's unit; utilizations as percentages (whole in `bottleneck` and `idle_capacity`); an optimization's values to four figures.

### MCP tools

Each tool calls the spec 3 API and returns its response. Inputs and outputs are JSON.

| Tool | Input | Output | Calls |
| --- | --- | --- | --- |
| `list_templates` | none | Array of `template.json`, each with at least `{id, title, summary}` | `GET /v1/templates` |
| `get_schema` | optional `component_type` | The JSON Schema, or one component type's settings, ports and description | `GET /v1/schema` or `GET /v1/schema/components/{type}` |
| `list_projects` | none | Array of `{id, name, created, layout_version, model_revision, path, available}`, as spec 3 lists projects; `id` is the `project_id` the other tools take | `GET /v1/projects` |
| `create_model` | `name`, optional `template_id`, optional `domain` | The new project, as `list_projects` lists it; its `id` is the `project_id` the other tools take | `POST /v1/projects` |
| `get_model` | `project_id` | `{model, revision}`: the model file and its revision | `GET /v1/projects/{pid}/model` |
| `edit_model` | `project_id`, `edits` as in spec 3, optional `base_revision` | `{model, revision, issues}`; E181 is returned as data | `POST /v1/projects/{pid}/model/edits` |
| `validate_model` | `project_id` | `{revision, issues}` | `POST /v1/projects/{pid}/validate` |
| `run_model` | `project_id`, optional `experiment_id` (required for a process model, absent for an optimization model, as spec 3 defines) | `{run_id}` | `POST /v1/projects/{pid}/runs` |
| `get_run_status` | `run_id` | The run as spec 3 shows it: `{run_id, project_id, experiment_id, engine, state, fraction, message, created, started, ended, error}` | `GET /v1/runs/{rid}` |
| `get_results` | `run_id`, optional `tables` | `{summary, findings, issues, tables}`: `summary`, `findings` and `issues` as `GET .../summary` gives them, and `tables` an object mapping each requested table name to its rows | `GET /v1/runs/{rid}/summary` plus one `GET /v1/runs/{rid}/tables/{name}?format=json` per requested table |
| `list_engines` | none | Installed adapters and capabilities | `GET /v1/engines` |

Behaviour an assistant can rely on:

- **Errors are data.** A failed edit returns the issues with codes and hints; it does not raise a protocol error. The assistant reads them and corrects the model.
- **Edits are rejected only when they cannot be applied.** An edit is rejected only when it cannot be applied: unknown or duplicate component id, unknown type, unknown parameter or experiment, a `path` whose parent does not exist. Rejections are issue objects with code E180 and `path` `/edits/<n>`; the batch is then not applied. A batch that applies is saved even if validation then reports errors; the response carries the model, its revision and the issues (spec 3).
- **Runs are asynchronous.** `run_model` returns at once; the assistant polls `get_run_status`.
- **Tool descriptions teach the format.** Each tool's description includes one worked example, since the assistant sees nothing else.

How the server runs and answers (AKS-115, owner to confirm; research notes `docs/research/spec-4-mcp.md` and `docs/research/spec-4-assistant-tool-design.md`):

- **Program and transport.** `python -m lcsim.mcp` serves MCP over stdio, the transport desktop assistants use to start a local server, built on the official Python SDK (`mcp` 2.3.0 or later); it answers clients of both protocol eras that SDK speaks, the `initialize` handshake (2024-11-05 to 2025-11-25) and 2026-07-28. `--config-dir` and `--data-dir` name the service's folders as for `python -m lcsim.service` (spec 3 "Discovery"), default the same per-user folders, and are passed to the service when the MCP server starts it.
- **One way in.** Every tool call is one or more requests to the `/v1` API, never a private channel: to `127.0.0.1` without any proxy, with `Authorization: Bearer` and the token of `service.json`, and `X-Client: mcp`. Every response body is read with the service's strict JSON reader.
- **Starting the service.** The port and token come from `service.json` in the configuration folder. When the file is missing or its service does not answer the spec 3 probe, the MCP server starts `python -m lcsim.service` with the same folders, detached from itself so that the service and its runs outlive it (spec 3 "Lifetime"), with its input and output discarded, and waits up to 30 seconds for `service.json` to name a service that answers the probe; the service's own lock settles two starts at once (spec 3 "One service per user"). A request refused at connection, or answered 401 (a service restarted since, with a new token), is sent once more after finding or starting the service again; a request that may have reached a route is never sent twice.
- **Results.** A tool's result is the response body as JSON text, and the same object as `structuredContent` when it is a JSON object (the list endpoints return arrays). A response with a status of 400 or above is a result marked `isError` holding the service's body unchanged (`{error: {code, message}, issues, ...}`, spec 3 "Status codes and errors").
- **Inputs.** Each tool declares its inputs as this table names them, with no others allowed. An input that is missing, unknown or of the wrong kind (text must be valid Unicode, as spec 3 requires of a request's text) gives a result marked `isError` holding `{error: {code: "E184", message}, issues}`, one E184 issue per problem with `path` `/<input>`, and no request is sent. Path inputs are percent-encoded as one path segment. Only a tool name the server does not have is a protocol error, as the MCP specification lists unknown tools. The kinds (AKS-134, owner to confirm): `name`, `template_id`, `domain`, `project_id`, `experiment_id`, `run_id` and `component_type` are text; `base_revision` is a whole number (a JSON integer, not `true` or `3.5`); `tables` is an array of text; `edits` is an array whose numbers are all finite and which nests at most 100 levels deep, since a request body cannot hold `NaN` or an infinity and no model needs deeper nesting. Whatever else an input must be (a known `domain`, edits of the right shape, a revision that is current) is the service's to check, and its refusal is the result.
- **Requests made** (AKS-134, owner to confirm). `create_model` sends `{name, template?, domain?}` (`template_id` as `template`) and no `path`, so a new project's folder is under the user data folder (spec 3); `edit_model` sends `{edits, base_revision?}`; `run_model` sends `{experiment_id}` or `{}`, never a `target`, so a run uses the file's `run.target`. `get_results` asks for the summary first, then each requested table once, in the order first named, and returns the first answer with a status of 400 or above unchanged, as any tool returns a refusal (409 with E188 for a run that is not `done`, 404 with E185 for an unknown table); otherwise it returns the summary's answer with `tables` added. No tool repeats a request that may have reached a route, so a write is never applied twice.
- **No service.** When the service cannot be started, does not answer, or sends an answer the strict reader refuses, the result is marked `isError` and holds `{error: {code: "E193", message}, issues}` with one E193 issue (spec 1).
- **What the first real-assistant trial changed** (AKS-116, owner to confirm; transcript and findings in `docs/research/spec-4-mcp-trial-2026-11-08.md`). An experiment's `length` is the whole run, its warm-up included, so results are measured over `length` minus `warmup` (spec 1 "Experiments": `warmup` is less than `length`; spec 2 "Statistic definitions": the observed period starts at the end of warm-up). The assistant read "200 hours after a 10-hour warm-up" as `length` 200 h, which measures 190 h, and found the slip only from the arrival count, after a first run. `create_model`'s and `edit_model`'s descriptions now say that `length` includes the warm-up, with the arithmetic (200 h measured after a 10 h warm-up is `length` 210 h and `warmup` 10 h). `edit_model`'s description also says its `issues` are the model checks made when the model is loaded, and that `validate_model` adds the engine's own check, which the assistant skipped (spec 3: a write's issues are loading's). Every description stays within 4,096 characters, the limit on a tool description the trial's Claude Code CLI ran with (`CLAUDE_CODE_MAX_MCP_DESCRIPTION_LENGTH` 4096), since the worked example comes last and a cut would lose it; `edit_model`'s is the longest, 3,915. No tool name or input changed.
- **Templates** (AKS-122, owner to confirm). With templates installed, `list_templates`'s description no longer says an empty array is normal: it says the array lists every installed template's `template.json` (none is a normal answer only where no template is installed) and its example is the coffee shop's entry. `create_model`'s says a `template_id` copies that template's model, named after the project, and that `domain` may be left out with a template, since the template's model sets it; a `domain` that differs from it is refused (E184). No tool name or input changed.

### Limits

- The MCP server itself allows at most two unfinished runs per project that it started, tracked in memory; a third request returns an error object. How it is checked (AKS-134, owner to confirm): the MCP server keeps, for each `project_id` given to `run_model`, the `run_id` of every run it started for it (a `202` answer), from its own start; runs started by the interface, a script or another MCP server do not count. At each `run_model` it asks the service for each of them (`GET /v1/runs/{rid}`): a run is unfinished while the service says `queued` or `running`; a run the service no longer finds (404) is forgotten, and any other refusal, or no service (E193), is the result and no run is started. With two unfinished, the result is marked `isError` and holds `{error: {code: "E194", message}, issues, run_ids}`: one E194 issue at `/project_id` (spec 1) and the ids of the unfinished runs, which `get_run_status` follows; nothing is sent to the service. The check and the start are made one at a time, so two calls at once cannot both pass it.
- Default run limits: 10 minutes and half of system memory, adjustable in settings. These are the service's `run_time_limit_s` and `run_memory_limit_bytes` (spec 3 "Service rules", Run queue), which bound every run whichever client starts it; a run beyond them fails with E192 (spec 1). The MCP server sets no limit of its own (AKS-134).
- The MCP server reads and writes only inside project folders. How it is met (AKS-134, owner to confirm): no tool reads or writes a file at all; every tool is requests to the service, which reads and writes the project's folder (spec 3 "Project folder") and its own files. The MCP server's one file read is `service.json` in the configuration folder, to find the service (spec 3 "Discovery"); that is discovery, not a tool's read, and it writes no file. `create_model` takes no `path`, and `POST /v1/projects/open`, which registers a folder named by its path, is not a tool (spec 3). `tests/mcp/test_mcp_confinement.py` runs `python -m lcsim.mcp` as its own process with an audit hook (`sys.addaudithook`) recording every file the process opens, lists, creates, renames or removes while each of the eleven tools is called, and finds only the interpreter reading its own modules, the null device opened read-only (the SDK's stdio transport points standard input at it while it serves the protocol on a private copy), and `service.json`.
- No data import tool (AKS-134). An assistant has no file to send, so the MCP server has no tool for the data endpoints; data files are imported through the interface or `POST /v1/projects/{pid}/data`, within spec 3's limits (a request of at most 64 MiB plus 64 KiB, a file of at most 64 MiB, an `.xlsx` of at most 512 MiB unpacked, at most 1,048,576 records and 10,000,000 cells; E189 beyond them). A model written through `edit_model` may name an imported file in an `empirical` `data` reference.

### Assistant acceptance case

The fixed description lives in `tests/mcp/coffee_shop_description.txt`:

> Customers arrive at a coffee shop about every 2 minutes at random. One till serves them; serving takes about 1.5 minutes on average, also at random. Simulate 200 hours after a 10-hour warm-up, 30 times, and tell me the average wait and how busy the till is.

Pass criteria, independent of ids: the project validates with zero errors; the run reaches `done`; the server's `wait.mean` is within 3 standard errors of 270 s and its `utilization` within 3 standard errors of 0.75 (the spec 2 pass rule; the standard error is the half-width divided by the t quantile the summary used).

- **Level 1.** `tests/mcp/test_coffee_shop_scripted.py` drives the MCP server with a scripted client that sets `seed` 12345, in CI. The client sets `length` 210 h and `warmup` 10 h: `length` includes the warm-up (spec 1), so 200 h are measured after it, as the description asks (AKS-116, owner to confirm).
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
| Every template reproduces its expected values, with at least one `theory` or `benchmark` source | M10 | agent | `tests/templates/test_templates.py` (marker `template`): the three AKS-122 and the three AKS-139 templates and their exercises; the other four arrive with AKS-123 and AKS-140 |
| A first-time user completes one Learn walkthrough without outside help (one outside tester; fallback as in spec 3) | M10 | owner |  |
| Each finding rule fires on its `_fires` fixture and is silent on its `_silent` fixture | M8 | agent | `tests/findings`; end to end through the service, `tests/service/test_summary_findings.py` (AKS-135) |
| A Build-mode user without data reaches a completed run changing only parameters | M9/M10 | agent via the end-to-end test | Asserted at M10 close, when the Build-mode form exists. At M9, `ui/e2e/pointer-only.spec.ts` reaches a completed run of the coffee shop by pointer, without data, from a new project (spec 3 acceptance, AKS-121) |
| The scripted MCP case passes | M7 | agent | `tests/mcp/test_coffee_shop_scripted.py` |
| A real-assistant transcript meets the acceptance case | M7 | owner, or agent if an MCP-capable assistant is available | `docs/research/spec-4-mcp-trial-<date>.md`; met by the agent in `docs/research/spec-4-mcp-trial-2026-11-08.md` |
| No MCP tool reads or writes outside the project folder | M7 | agent | `tests/mcp/test_mcp_confinement.py` |

## Changes in this version

2026-11-05, version 0.3, spec review council:

- C24 (PRD-6, PRD-7, SIM-18, ARCH-19, SIM-8, PRD-14, TEST-18, SIM-17): template table with blocks and scope; Phase 1 scope sentence; summary findings aligned; Build mode form; `expected.json` sources.
- C25 (SIM-9, PRD-14, SIM-10, SIM-12, ARCH-10, SIM-18, ARCH-12, TEST-17, SIM-19, PRD-8): finding rules rewritten; `n_required`; fixture layout; threshold status.
- C26 (ARCH-7, ARCH-8, ARCH-13, TEST-10, TEST-1, TEST-12): MCP tools mapped to endpoints; `run_model` by domain; edit semantics; limits; assistant acceptance case; research items tagged; acceptance table.
- Verifier follow-up: the summary Build bullet says data import is optional, matching "Build mode".

2026-11-08, version 0.4, M7 closed (AKS-116); the lines below were added after version 0.3, during the M7 build:

- 2026-11-08, MCP server and the six read tools (AKS-115), from the research notes `docs/research/spec-4-mcp.md` and `docs/research/spec-4-assistant-tool-design.md` and while building `src/lcsim/mcp/`: "MCP server" says the MCP server, a separate program, exposes the tools, and its table adds `list_projects` and `get_model`, which "MCP tools" already had; "MCP tools" gives the outputs of `list_templates`, `list_projects`, `get_model` and `validate_model` as the spec 3 endpoints return them (each tool returns its endpoint's response, so `list_projects` gives `id` rather than `project_id`, `get_model` the revision with the model, and `validate_model` the revision with the issues), and adds "How the server runs and answers": stdio through the official SDK, `--config-dir` and `--data-dir`, requests only to `/v1` with the token and `X-Client: mcp`, starting the service on demand and waiting up to 30 s, one repeat only for a refused connection or a 401, results as JSON text and `structuredContent`, refusals marked `isError` with the service's body, input problems as E184 at `/<input>`, and E193 when there is no service (new spec 1 code). All owner to confirm.
- 2026-11-08, MCP write and run tools, run limits and confinement (AKS-134), while building them in `src/lcsim/mcp/`: "MCP tools" gives `create_model` the optional `domain` of `POST /v1/projects` (no edit changes a model's domain, so without it an assistant could not start an optimization model) and its output as that endpoint returns it, the new project with its `id` (as `list_projects` gives `id`), rather than `{project_id, model}`, which no endpoint returns; `get_run_status`'s output is the whole run as `GET /v1/runs/{rid}` returns it, `state`, `fraction` and `message` among its fields; `get_results`'s `tables` is an object keyed by table name; `run_model`'s input cell loses the code marks on the domain names. "How the server runs and answers" adds the kinds of the new inputs (a whole number, an array of text, edits with finite numbers nested at most 100 deep) and the requests the write and run tools make, with how `get_results` composes its answer. "Limits" says how the two-run limit is checked (runs this server started, unfinished while the service says `queued` or `running`, E194, a new spec 1 code, with the unfinished `run_ids`), that the run limits are the service's, how the server keeps to project folders (no tool touches a file; `service.json` is discovery; no `path`, no open), and that there is no data import tool, with spec 3's upload limits. The acceptance table names the confinement test. All owner to confirm.
- 2026-11-08, scripted coffee-shop case and first real-assistant trial (AKS-116), from `tests/mcp/test_coffee_shop_scripted.py` and `docs/research/spec-4-mcp-trial-2026-11-08.md`: "Assistant acceptance case" says the scripted client sets `length` 210 h and `warmup` 10 h, since `length` includes the warm-up (spec 1) and the description asks for 200 h after it. "How the server runs and answers" adds what the trial changed: `create_model`'s and `edit_model`'s descriptions say that `length` includes the warm-up, with the arithmetic, and `edit_model`'s that its issues are loading's and `validate_model` adds the engine's check; every description stays within 4,096 characters; no tool name or input changed. All owner to confirm.
- 2026-11-08, M7 closed (AKS-116): the warning line says the MCP tools have run against one real assistant, which changed two descriptions; the "Detailed specification" opening line names what M7 built; the acceptance table's real-assistant row names the trial note. Version 0.4.

2026-11-08, version 0.5, M8 closed (AKS-135); the lines below were added after version 0.4, during the M8 build:

- 2026-11-08, finding rules and their fixtures (AKS-117), from the research note `docs/research/spec-4-findings-wording.md` and while building `src/lcsim/findings/` and `tests/findings/`: "Finding rules" replaces the coffee shop's half-width of 4.8% with the measured 3.7% (seed 12345, its own 200 h experiment; M7's 210 h run gave 3.4%) and the prototype's three-machine-line check (0.90, half-width 26%) with the M8 measurement (weld 0.901, wait half-width 13.3%, so `bottleneck` and `not_enough_runs` fire, and neither fires for the coffee shop); says the fixtures are finished runs made by `tests/findings/make_fixtures.py`; updates the example finding to the three-machine line's; and adds "How the rules read this table" (input and order, severity, thresholds, ties, "of the time it was available", `unstable` per W201 server with `scenario` null, `idle_capacity` among servers without a schedule on them or their pool, the key metrics, floors, widest metric and largest n_required, the pair form, the optimization wordings, display units; after the review of PR #42, a search's sense is that of the objective its `search` names). "Findings in plain language" says idle capacity is a server's, as the detailed table does. The warning line says the thresholds were checked on two models; the "Detailed specification" opening line says the finding rules are built. All owner to confirm.
- 2026-11-08, findings in the run summary and `get_results`, user-adjustable thresholds (AKS-135), while wiring `lcsim.findings` into the service and the MCP server: "Finding rules" says where the thresholds come from (`finding_thresholds` in `settings.json`, spec 3, read at each summary, W220 for a value that cannot be used) and that M8 repeated the two-model check end to end through the service with the same values; the Thresholds reading says the service refuses an out-of-range value as W220 before the rules see it; "MCP tools" gives `get_results` the output `{summary, findings, issues, tables}`, and its description's worked example is now the three-machine line with its two findings; the acceptance table's M8 row names the end-to-end test; the warning line and the "Detailed specification" opening line say the findings reach the summary and `get_results`. All owner to confirm.

2026-11-08, version 0.6, M9 closed (AKS-121); the lines below were added after version 0.5, during the M9 build:

- 2026-11-08, the run's engine (AKS-138): `get_run_status`'s output names `engine`, the manifest's `{name, version}`, which spec 3 added to a run as the run endpoints show it for the Results footer; the tool's description and example say so. Owner to confirm.
- 2026-11-08, M9 closed (AKS-121): the acceptance table's M9/M10 row says it is asserted at M10 close, since the Build-mode form arrives at M10, and names the M9 pointer-only end-to-end test, which reaches a completed run without data. Version 0.6.

Since version 0.6, during the M10 build:

- 2026-11-09, template package, loader, endpoints and the first three templates (AKS-122), from the research notes `docs/research/spec-4-teaching-practice.md` and `docs/research/spec-4-template-sources.md` and while building `lcsim.templates` and `templates/`: "Template package" adds how a package is written and checked: the keys and kinds of `template.json` (`minutes`, `experiment` with a seed, `origin`, `licence`, `exercise` as spec 3 edits), the model loading with no issue and a non-zero `warmup` on the named experiment, `lesson.md`'s steps (`## ` sections, a `Component:` line, 80 words, the exercise's `### Change`, `### Prediction` with one `[x]` among two to four choices, and `### Explanation`), `expected.json`'s rows (`metric` as `summary.json` names it, `value` in SI units, `method` one of spec 2's `three_se`, `exact` and `sig_figs_4`, `source`, `reference`, `run` `template` or `exercise`), problems as issues with E195 (new spec 1 code) at pointers into the package, the template test and what `POST /v1/projects` with `template` copies; and a table of the three templates built, the coffee shop's `length` of 200 h stated as including its 10 h warm-up, so 190 h measured (M7 item 25). The warning line and the "Detailed specification" opening line say three templates are written; "How the server runs and answers" says how `list_templates`'s and `create_model`'s descriptions changed; the acceptance table's M10 template row names the test. All owner to confirm.
- 2026-11-09, three more simulation templates (AKS-139), while writing `templates/clinic_patient_flow`, `templates/warehouse_pick_pack` and `templates/inventory_reorder_point`: "Template package" adds the three to its table and says how they read the blocks (the clinic as M/M/c through a pool, the warehouse measuring whole days with hourly samples and its pickers' utilization `recorded`, the warehouse written fresh rather than extending the example, the inventory as the (R, Q) policy and its exercise's stock-outs `recorded`); the warning line and the "Detailed specification" opening line say six templates are written; the acceptance table's M10 template row names them. All owner to confirm.
