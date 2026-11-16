# Spec 5 v0.3 council: implementability review

Reviewer lens: could a coding session build each "Specified" part as written, against spec 1 to 4,
the adapter Protocol as it stands (`src/ithax/engines/adapter.py`), the model layer, the run
manager, search and local target, and the build guide's rules? Draft: `docs/specs/5-systems-and-design.md`
(branch `docs/spec-5-v0.3`). No repository file was changed.

Short answer: the adapter **methods** (`capabilities`, `validate`, `translate`, `run`, `collect`)
can stay as they are. But the parts that sit next to them do not fit as written: the fidelity
label, the metric catalogue, the seed and replication rules, the domain catalogues and the
service. Several sections marked Specified (design studies, chaining, reliability calculators)
have no result layout and no entry point, so a session would have to guess. Seven blocking
findings, sixteen should-fix and nine suggestions follow.

---

## Blocking

### B1. Deterministic domains forbid `seed` and `replications`, but search (and studies) need both

- **Location:** "Experiments": "`replications` and `seed` apply to `agent` only; the other three domains are deterministic, so `replications` and `seed` are not allowed (E100) … `scenarios` and `search` work as in spec 1 for every domain." "Design studies": "Each library's seed is the first draw of the reserved stream `<seed>:0:study`."
- **Problem:** spec 1's search needs a seed and at least two replications per stage. `search.replications` must be an integer ≥ 2 (E170), and the confirmation stage re-runs with the experiment's `replications`, numbered from `search.replications`. The TPE sampler's seed is drawn from `<seed>:0:optimizer`. A `system_dynamics`, `physical` or `multibody` experiment has no `seed`, so none of this can run "as in spec 1". A study's `<seed>:0:study` has no seed either. `Experiment.seed` and `Experiment.replications` are required `int`s in the model.
- **Evidence:** spec 1 `docs/specs/1-model-format.md:249` (`replications` "integer, at least 2"), `:258` (E170 for `search.replications` below 2), `:262` (the optimizer stream); `src/ithax/runs/search.py:242-245` (`tpe_seed(self.experiment.seed)`), `:379-396` (confirmation re-runs `experiment.replications` from `search.replications`); `src/ithax/model/model.py:195-206` (`replications: int`, `seed: int`); `src/ithax/model/loading.py:1119-1148` (default 30, `assert isinstance(seed, int)`).
- **Fix:** state the deterministic search explicitly:
  1. `search.replications` is not allowed (E100).
  2. There is no confirmation stage: the search-stage value is final, and `separated` is `true` when the values differ.
  3. The sampler and study seed comes from an optional experiment `seed` that is allowed in every domain and used only by the search or study, recorded in the manifest. Without one, the loader draws it as spec 1 does today.
  4. The loader stores `replications = 1` and `first_replication = 0`.

  List these as spec 1 edits ("Experiments", E170, "Random streams") and spec 2 edits ("Simulation-based optimization").

### B2. The fidelity label cannot be produced by the existing manager or Protocol, and the examples break spec 1's length rule

- **Location:** "Results": "The fidelity label names the method and step: 'Standard: Euler, step 0.0625 d, 200 d' … 'Standard: RK4, step 1 ms, 10 s' …"
- **Problem:** the manager, not the adapter, builds `fidelity_label` from the fidelity, the replications, the length and the confidence. `Results` and `Capabilities` have no field that carries a method name ("Euler", "RK4"), and the manager knows nothing of `time_step`, so "using the existing adapter Protocol unchanged" cannot produce these labels. The examples also contradict spec 1's length-formatting rule (the largest Phase 1 unit giving a whole number). `format_length(5400.0)` returns "90 min", not "0.0625 d", and `format_length(0.001)` returns "0.001 s"; `ms` is not a unit at all.
- **Evidence:** `src/ithax/runs/summary.py:52-58` and `:126-128`; `src/ithax/engines/adapter.py:90-112` and `:146-157`; spec 1 `:432`; output of `format_length` checked in the venv.
- **Fix:** add a `method: str | None = None` field to `Capabilities` (additive to the dataclass; the Protocol's methods do not change), or a per-domain label rule in `runs/summary.py` keyed on `model.domain`. Then define the step's formatting: say "step 1/64 d", or use the same whole-number rule, and rewrite the three examples to match. List the edit to spec 1's "Fidelity label".

### B3. Metric names and statistics are inconsistent and undefined, so E174, objectives and `summary.json` cannot be built

- **Location:** "Results": "Metrics are `<component>.<variable>`, with `.final`, `.max`, `.min` and `.mean` (time-average)". Agent: "`<population>.<state>` (count) in `timeseries`, and its `.final`, `.max` and `.time_of_max`". System dynamics: "`<stock>` and `<flow>` values in `timeseries`; `.final`, `.max`, `.time_of_max`".
- **Problem:**
  1. The three lists disagree. `.min` and `.mean` appear only in "Results", and `.time_of_max` only in the domain sections.
  2. A bare `<stock>` metric has no measure. Spec 1's grammar is `<component id>.<measure>[.<statistic>]`, and spec 1 says `till.wait` without `.mean` is not a metric.
  3. Nothing defines `.mean`: whether it is a time average over the recorded samples or over every step, which rule (trapezoid or step) it uses, and from `warmup` or from 0.
  4. `.final` is not in `timeseries`, which samples "from 0 s to before the end".
  5. `.time_of_max` has no tie rule and no unit.
  6. E174 needs each type's metric list and each measure's kind (time, rate or number). `BlockType.metrics` is a static tuple, but agent metrics depend on the `states` setting, and physical metrics are "as Modelica names them".
  7. `MEASURE_KINDS` has no entry for any new measure, so a constraint's `value` kind (E123) is undefined. Physical metrics are lengths or speeds, which a constraint `value` cannot express (time or rate only).
- **Evidence:** spec 1 `:264-273` ("Metric names", E174); `src/ithax/model/catalogue.py:111-125` (`metrics: tuple[str, ...]`), `:382-410` (`MEASURE_KINDS`); spec 1 `:455` (timeseries "from 0 s to before the end").
- **Fix:** add a "Statistic definitions" table for spec 5 with, for each domain, the exact measure names (for example `<stock>.value`, `<population>.<state>`), each statistic's formula (sample at the end time; max over every recorded sample from `warmup`; first time of the max; time average by the trapezoid rule over recorded samples), each one's unit and `MeasureKind`, and the row order in the `replications` and `timeseries` tables. Add `metrics_from` (like `outputs_from`) to `BlockType` for state-derived metrics, as an additive field in `GET /v1/schema/components/{type}`.

### B4. Design studies are marked Specified but have no result layout, no entry point and no run lifecycle

- **Location:** "Design studies": "**Specified** except the file layout." and "Each evaluation is one ordinary run through the adapter contract, in its own subfolder of `engine/` as spec 2's search does."
- **Problem:** a session could not build this as written. Missing:
  1. What a study run writes: a `summary.json` `study` object, tables for sweep grids, Sobol indices, the Pareto front and uncertainty samples, and the manifest's `optimizer`-like record of library versions.
  2. The subfolder names (search uses `search-<n>` and `confirm-<n>`).
  3. How progress is weighted, and what a cancel or a failed evaluation does.
  4. How a study is started: there is no `/v1` route, no MCP tool and no model-file location, since the location is Open.
  5. Whether a study and `search` may sit in one experiment, and whether a study may sit with `scenarios`.

  The manager change is larger than the draft implies. `run_experiment` and `LocalRun` know only `search` (`_has_search`, `run_search`), so a study driver is a new module in `runs/` with its own summary builder.
- **Evidence:** `src/ithax/runs/manager.py:193-200`; `src/ithax/runs/targets.py:348-349` and `:534-537` (the search-only branch); spec 1 `:383` (subfolder naming); `:415-417` (the `search` object in `summary.json`).
- **Fix:** mark the section Open until the model-file location is decided, or specify:
  - the `summary.json` `study` object and its tables per study kind;
  - the subfolder names (`study-<n>`);
  - progress, cancel and failure, as for search;
  - the time limit (see S11);
  - the API and MCP parity rows.

### B5. Chaining is "otherwise specified", but a time series has no consumer in any specified domain, and a chain does not fit the one-engine run

- **Location:** "Chaining (Open: file layout …; otherwise specified)": "a time series from `timeseries` into a time-varying input, with interpolation `linear` or `hold`"; "the manager runs them in order, each as an ordinary run through its own adapter, so no adapter changes"; "E420 … E421" as "spec 5 model-layer codes".
- **Problem:**
  1. No specified domain has a time-varying input. System dynamics lookups are Open, and process source schedules are M19 (D10, not yet in spec 1).
  2. One run has exactly one `engine {name, version}`, one `experiment_id` and one `run_id`, and `LocalRun` drives one adapter, so a chained run either breaks the manifest or is a group, and that question is Open.
  3. "Units are checked at load" is impossible for upstream metrics: their units exist only in the upstream run's tables, or in a metric catalogue that does not exist yet (B3).
  4. E420 needs upstream results, so it is a run code, not a meaning-pass code.
  5. "Reused when its model and experiment are unchanged" is ambiguous when the upstream file omits `seed`: the loader then draws a new seed at every load.
- **Evidence:** spec 1 `:129` (manifest fields: `engine`, `experiment_id`); `src/ithax/runs/targets.py:326-349`; `docs/research/phase-2-milestones.md:54` (M19 time-varying arrivals); the draft's own "System dynamics": "no table (lookup) functions … **Open**".
- **Fix:** mark chaining wholly Open, or restrict the specified part to scalar links into parameters. Define the reuse key as model SHA-256, experiment id and the resolved seed. Move E420 to a run code. Add a manifest field for a chained run (and say whether a chain is one run or a group) as a spec 1 edit.

### B6. The system dynamics expression grammar and time units are under-defined, and names can be ambiguous

- **Location:** "Expressions": "numbers, the ids of stocks, flows, auxiliaries and parameters, `+ − * / ^`, … `min`, `max`, `exp`, `ln`, `abs`, `if_then_else(c, a, b)`, comparisons inside it, and `time`". "Experiment": "`time_unit` … and `time_step` in that unit." Versus "Experiments": "`time_step` (time quantity …)".
- **Problem:**
  1. Spec 1 lets a component and a parameter share an id ("Lists are separate"), so `beta` in an expression can name either one.
  2. `time`, `min`, `max`, `exp`, `ln`, `abs` and `if_then_else` all match the identifier pattern, so a stock named `time` or `max` is legal and collides with them.
  3. The grammar does not fix operator precedence, the associativity of `^`, unary minus, the number grammar (JSON or otherwise), the comparison operators (`<`, `<=`, `==`, `!=`?), boolean operators, function arity or whitespace. The draft prints U+2212 `−` where code needs ASCII `-`.
  4. `time_unit` sits in the **experiment**, so one model's flow `rate` means different things in two experiments. Rates are a property of the model.
  5. `time_step` is a time quantity in one place and a number "in that unit" in another.
  6. A parameter of `type` `quantity` (seconds, spec 1) used in an expression has no defined unit.
  7. Whether a flow may go negative (uniflow) is not said, and XMILE has both kinds.
- **Evidence:** spec 1 `:148` ("a component and an experiment may share an id"; parameters are a separate list), `:202` (a `quantity` parameter is a time); `src/ithax/model/validation.py:138` (the reserved-id table).
- **Fix:**
  - Give the grammar as EBNF, with ASCII operators and precedence.
  - Make an id that is both a parameter and a component an error in `system_dynamics` (new E40x).
  - Reserve the function names and `time` as component and parameter ids in `system_dynamics` only (E112), so process files keep loading (`tests/compat`).
  - Move `time_unit` to a model-level key, or make all expression values per second.
  - Make `time_step` a time quantity everywhere.
  - Allow only `integer` and `number` parameters in expressions (E152 otherwise).
  - State that flows are biflows, or add a `non_negative` setting.

  Ithax only parses and checks expressions; it never evaluates them. PySD does, which keeps rule 7.

### B7. Agent randomness: one Mesa model generator against "one stream per population", with draw order and competing transitions undefined

- **Location:** "Randomness: one stream per population per replication, key `<seed>:<replication>:<population id>` (spec 1), given to `mesa.Model(rng=...)`." Transition: "Decisions use the counts at the start of the step and apply together."
- **Problem:**
  1. `mesa.Model` takes one `rng` (`docs/research/spec-5-mesa.md:17`). With two populations, the draft does not say which stream goes in, or whether each population gets its own `Model`. They are independent, since `contact` is within one population, so that would work, but it is not stated.
  2. The draw order within a step decides "Identical runs" (spec 1 `:460-462`) and is not given: transitions in component order? agents in creation order? `AgentSet.shuffle_do` (which draws from `model.random`)?
  3. Two transitions out of the same `from` state (competing risks) are undefined: one agent could be selected by both.
  4. A transition's `from` or `to` that is not a state of its population, or a `contact` that is not one, has no issue code. E402 covers only `initial`.
- **Evidence:** `docs/research/spec-5-mesa.md:17` and `:33`; spec 1 `:262` (each component's draws "in the order of the events that need them").
- **Fix:**
  - Specify one `mesa.Model` per population, with its stream.
  - Per step: transitions in component order; within one, the agents in `from` in creation order, one `rng.random()` each.
  - For competing transitions out of one state, use the total-rate probability 1 − exp(−Σr Δt), then choose by rate share, drawn from the same stream. Or forbid two transitions out of one state (new code).
  - Add E40x for a `from`, `to` or `contact` that is not a state, and for a `transition` whose `population` is not a population (E130-like).

---

## Should-fix

### S1. "Format 0.4" collides with M19, and the versioning rule for 0.4 keys is missing

- **Location:** "Format 0.4 (additive)."
- **Problem:** M19, which comes before M23, also makes "a spec 1 format change that only adds" (source schedule, reneging, attributes), so 0.4 will probably be taken first. Spec 1 also needs, for each minor, what an older-minor file holding a new key gets: E100 with a hint, as for 0.2 and 0.3. The draft does not say what a 0.3 file with `domain: "agent"`, `time_step` or a physical unit gets. The experiment schema has `additionalProperties: false` and needs `time_step`, `time_unit` (and `study`), with per-domain forbids for `replications`, `seed`, `warmup` and `connections`. `schema.py`'s `_domain_keys` assigns each forbidden key one "owner" domain for the "belongs to the X domain" message, which becomes misleading with six domains.
- **Evidence:** `docs/research/phase-2-milestones.md:54` (M19); spec 1 `:130` (Versioning, E100 hints for 0.2 and 0.3); `src/ithax/model/schema.json` `$defs.experiment.additionalProperties = false`; `src/ithax/model/schema.py:104-129`.
- **Fix:** write "format 0.N, the minor after M19's". Add the older-minor E100 rule for each new key, domain value and unit. Add the per-domain experiment schema branches. Reword the E100 "other domain" message.

### S2. Units and parameters: rates and physical quantities cannot be parameters; E401 and the defaults are under-defined

- **Location:** "Experiments" (E401); `transition.rate` "(rate quantity, `1/d` etc.)"; "Physical units".
- **Problem:**
  1. A parameter's `type: quantity` is a time only (spec 1). So `$param` cannot feed a transition `rate` or any physical setting, and a search or study over β, or over a spring constant, is impossible. Every benchmark that sweeps or optimizes these is affected.
  2. E401's "whole multiple" check on SI floats is not exact. It should be checked exactly on the written decimals, with the `UNIT_SIZES` fractions.
  3. Spec 1's default `record_interval = length/200` can itself fail E401, so a file that omits `record_interval` would be refused.
  4. `length` that is not a whole multiple of `time_step` is undefined: how many steps does Mesa or PySD run?
- **Evidence:** spec 1 `:202`; `src/ithax/model/loading.py:129` and `:1133-1142` (default `record_interval`); `src/ithax/model/units.py:64-90` (dimensions are time, rate and dimensionless only).
- **Fix:**
  - Add a parameter `unit` (or `dimension`) for quantity parameters from 0.4, with E152 extended.
  - Specify an exact E401 check.
  - Default `record_interval` = the smallest multiple of `time_step` that is at least `length/200`.
  - Make `length` that is not a whole multiple of `time_step` an E40x error.

### S3. W210 fires on agent runs that are meant to change; `warmup` has no defined effect on the new statistics

- **Location:** "`warmup` is allowed in `agent` only."
- **Problem:** the manager runs the warm-up check on every `timeseries` (n ≥ 2), outside a search. An epidemic's counts trend by design, so W210 ("lengthen `warmup`") would appear on every SIR agent run, including the benchmark and its templates. What `warmup` does to `.final`, `.max` and `.time_of_max` is not said.
- **Evidence:** `src/ithax/runs/summary.py:117-122`; `src/ithax/runs/warmup.py:95-121`.
- **Fix:** state that W210 is checked only for `process` (or only when `warmup` is above 0), and that statistics count from `warmup`, as in B3.

### S4. The model layer is wired to the process catalogue; where the new catalogues live, and how settings are described, is unstated

- **Location:** "Each adapter … adds its component types to the schema."
- **Problem:**
  - Loading and validation read `PROCESS_TYPES` directly, about ten call sites. `InstalledEngine` carries only a name and domains. The E40x codes are called "model-layer codes", so the model layer must hold the agent and system dynamics catalogues. Yet the model layer may not import engines (layer rule), and spec 1 says the catalogue comes from `Capabilities`.
  - `SettingKind` has no expression kind, no fixed-length vector (multibody's three-value settings) and no nullable reference (`flow.from` may be `null`).
  - `BlockType` has directed `inputs` and `outputs` only, with no connector kind (physical, E406).
  - `GET /v1/schema/components/{type}` returns `kind` values from the catalogue, and is keyed by type alone, so type names must be unique across adapters.
- **Evidence:** `src/ithax/model/loading.py:723`; `src/ithax/model/model.py:119`; `src/ithax/model/validation.py:376, 468, 605, 658, 986`; `src/ithax/model/catalogue.py:59` (`DOMAINS`), `:62-69` (`SettingKind`), `:111-125` (`BlockType`); `src/ithax/model/validation.py:162-165` (`InstalledEngine`); `src/ithax/runs/snapshots.py:96`; spec 3 `:146`.
- **Fix:** say that the model layer carries one catalogue per domain (as for `process`), and that each adapter's `capabilities()` must equal it (tested, as at M2). List the new `SettingKind` values (`expression`, `vector` with `length`, and a nullable `identifier`) as additive `/v1` schema changes. Require component type names to be unique across installed adapters.

### S5. Service, MCP and project-creation changes are needed but not mentioned, which contradicts the M25 row

- **Location:** acceptance: "All new component types are reachable through the MCP tools without changes to them".
- **Problem:** `POST /v1/projects` accepts only `process` or `optimization`, and `default_model` builds those two. A new-domain project therefore cannot be created through the API or `create_model` without a change: its default model (experiment with `time_step`), and possibly an empty-model warning like W204, have to be defined. Tool descriptions and examples are process-specific. `edit_model` is described as changing "components, connections or parameters", not experiments' new keys.
- **Evidence:** `src/ithax/service/projects_store.py:60` (`Domain = Literal["process", "optimization"]`), `:83-108`; `src/ithax/service/projects.py:149`; spec 4 `docs/specs/4-content-and-ai.md:72-81`; `src/ithax/mcp/tools.py:364, 457, 496`.
- **Fix:** add a "Changes to specs 1 to 4" section listing:
  - the `domain` values of `POST /v1/projects` and their default models;
  - the new `kind` values in `/v1/schema`;
  - the MCP tool texts.

  Reword the M25 row to "with a parity test", without "without changes".

### S6. A reserved stream key `study` collides with process component ids, and reserving it breaks compatibility

- **Location:** "Each library's seed is the first draw of the reserved stream `<seed>:0:study`".
- **Problem:** `study` is a valid identifier. A process component named `study` already draws `<seed>:0:study` in replication 0, the same collision that made `optimizer` reserved (E112). Reserving `study` now would make an existing 0.3 file with a component `study` stop loading, against `tests/compat` ("a model file that loads keeps loading"). The same applies to a surrogate's seed if it gets a key, and to `world` (multibody `parent`).
- **Evidence:** spec 1 `:150`; `src/ithax/model/streams.py:45-47`; `src/ithax/model/validation.py:138`; `tests/compat/test_models_load.py`.
- **Fix:** use a key that cannot be an identifier, for example `<seed>:0:@study` (the identifier pattern `^[a-z][a-z0-9_]{0,63}$` excludes `@`), or reuse `optimizer`. Reserve `world` only inside `multibody`.

### S7. Cancel, progress and adapter identity are not specified per adapter

- **Problem:**
  1. Spec 1 requires `run` to check `cancel` at least once a second. PySD's `run()` is one call, while Mesa and MuJoCo are loops the adapter writes, so the draft should say each adapter runs in chunks (PySD 3 can step a model in parts, or the run is split by `return_timestamps`) and reports `Progress`.
  2. The entry-point names (the `run.engine` values: `mesa`, `pysd`?), `version` (the engine distribution's version, as spec 1 does for `simpy` and `highspy`), and `parallel_modes` (`replications` for agent; none for the deterministic domains) are not given.
- **Evidence:** spec 1 `:369-377` and `:339` (named adapters and versions); `src/ithax/engines/registry.py:99-111`.
- **Fix:** add, per specified adapter, a line in the style of spec 1's process adapter: entry point, version source, `Capabilities` fields, the `engine/` files written, and how cancel and progress are honoured.

### S8. The XMILE path is not the one the trial ran

- **Location:** "The adapter writes an XMILE file (OASIS XMILE 1.0) in `engine/`, translates it with PySD".
- **Problem:** the PySD trial translated Vensim `.mdl` files (`sir.mdl`, `predator_prey.mdl`), not XMILE. PySD's XMILE translator is separate code, and its coverage of `if_then_else`, `min`, `max`, `ln`, `abs` and `TIME` is untested here. The SD section claims Specified on an untried path.
- **Evidence:** `docs/research/spec-5-pysd.md`, "Tested" (`trial_pysd.py with sir.mdl and predator_prey.mdl`).
- **Fix:** run the two benchmarks through generated XMILE, with every grammar function, before marking the section Specified. Otherwise specify `.mdl` output.

### S9. Which fidelities the new adapters accept; `surrogate` as a label or as a fidelity

- **Problem:** spec 1 says the spec 6 fidelity ladder "applies to physics domains". `physical` and `multibody` may count as physics domains, but the draft does not say which `run.fidelity` values they accept (E173). `OFFERED_FIDELITIES` is a single global in the manager, and `Capabilities` has no fidelities field. "Every surrogate result carries the fidelity label `surrogate`" leaves unclear whether `surrogate` is a `run.fidelity` value (E173 today) or only a label.
- **Evidence:** spec 1 `:171`; `src/ithax/runs/manager.py:63`.
- **Fix:** state "every spec 5 adapter accepts only `standard`", and that `surrogate` is a result label, not a `run.fidelity` value. If a ladder is wanted later, it needs an additive `Capabilities.fidelities` field.

### S10. Surrogates: the leave-one-out computation risks rule 7; E431 has no tolerance; NaN outputs; no way to query

- **Problem:**
  1. Computing the GP leave-one-out residuals in closed form needs K⁻¹, which is Ithax solving a linear system (guide rule 7).
  2. E431's "does not reproduce its stored validation numbers" has no tolerance, while the acceptance row allows 1e-9 of the range across machines.
  3. An evaluation whose metric mean is undefined (`null` in `summary.json`) cannot be stored in strict JSON, and the draft does not say whether it is dropped or refused.
  4. The GP's `random_state` stream key is not given (see S6).
  5. Nothing says where a surrogate prediction is served (route, MCP tool, results layout), so "every surrogate result carries…" has nothing to attach to.
- **Evidence:** `docs/specs/build-guide.md:15` (rule 7: "solves linear systems"); `src/ithax/strict_json.py` (CLAUDE.md: no NaN).
- **Fix:**
  - Compute leave-one-out by refitting scikit-learn with fixed hyperparameters (`optimizer=None`) n times, which wraps the library.
  - Set E431's tolerance (for example 1e-9 relative to the range).
  - Drop undefined outputs, with a count, and refuse below the budget.
  - Name the seed key.
  - Specify the query API.

### S11. Studies through spawned workers will not finish inside the run time limit; benchmark functions do not run through adapters

- **Problem:**
  1. The local target spawns one worker per evaluation. The Ishigami Sobol benchmark (N 1024, 3 inputs) needs 1024 × (2·3 + 2) = 8,192 evaluations, and the ZDT1 row needs 20,000. Through spawned workers that import PySD or pandas this is hours, while the default run time limit is 10 minutes (E192), counted over the whole search.
  2. The benchmark rows use analytic test functions (Branin, Rosenbrock, ZDT1, Ishigami), which no adapter runs. The draft does not say they are run against the library layer.
  3. The method and settings behind "Branin within 0.01 at 200 evaluations" (TPE? Nelder–Mead?) and ZDT1 (NSGA-II population and generations) are unspecified.
- **Evidence:** spec 1 `:442` (E192 time limit) and `:446` (search: a spawned worker per evaluation).
- **Fix:**
  - Say that benchmark functions run in-process through the study layer's evaluation interface.
  - Fix the method and settings per row.
  - Define the study's time limit (per evaluation, or scaled), or let one worker run a batch of evaluations.

### S12. pymoo against the owner's B1 and M20 ("NSGA-II, already in Optuna")

- **Location:** "Optimization, several objectives | … pymoo NSGA-II (shared with M20's Pareto search, B1)".
- **Problem:** owner decision B1 prefers NSGA-II "already in Optuna", and M20's row says "Pareto search (NSGA-II on simulations)". pymoo is a new dependency that pulls in matplotlib, autograd, cma and moocore (LGPL-2.1-or-later). Citing B1 for pymoo misstates the decision.
- **Evidence:** `docs/DECISIONS.md:2322` (B1); `docs/research/phase-2-milestones.md:55`; `docs/research/spec-5-design-studies.md:25-33`.
- **Fix:** use `optuna.samplers.NSGAIISampler`, or file an owner question if pymoo's extra algorithms are wanted. Record the dependency and its licence if kept.

### S13. Reliability and calculators are marked Specified with no input format, home or entry point

- **Problem:**
  1. Block diagrams, fault trees, NIOSH and SPAR-H have no input format, no package (`findings`? a new `calculators/` under which layer?), no `/v1` route and no MCP tool. E410 has no file path to point at, and "metric inputs converted at load" names no load.
  2. Life-data fitting "extends spec 3's distribution fit", but the fit endpoint's body is `{column}`, with no censoring column, and its Kolmogorov–Smirnov score is undefined for censored data.
  3. The NIST answer needs `floc=0` (in the research note, missing from the draft).
  4. The fault-tree engine is still "proposed" against RePyability and pfta in the research note's open questions, yet marked Specified.
- **Evidence:** `docs/specs/3-desktop-app.md:128` and `:160` (fit request and response); `src/ithax/model/fit.py:1-30`; `docs/research/spec-5-reliability.md:184-185` (`floc=0`) and `:241` (open question 2).
- **Fix:** give each calculator a module path, an input dataclass with units, and an API and MCP entry or "library only in Phase 2". Define the censored fit's request (`censored` column) and its score (for example none, or a censored goodness-of-fit). Add `floc=0`. Mark fault trees Open until the owner picks the engine.

### S14. The issue-code table needs a Pass column, and some codes are not model-file codes

- **Location:** "E400 to E449 are the spec 5 model-layer codes".
- **Problem:** spec 1's table gives each code its Pass. The issue-code fixture test expects one `fixtures/issues/E4xx_*.json` **model file** per schema or meaning code. But E420 needs run results, E421 concerns a chain file, and E430 and E431 concern surrogate files. The draft also does not say that spec 1's table gains these rows in the same PR (rule 5).
- **Evidence:** `tests/model/test_issues.py:1-8` and `:45-60`; spec 1 `:288-334`.
- **Fix:** add the Pass column (meaning, run or service), and state the spec 1 table edit. Also reserve W400–W449 (the surrogate budget warning and the leave-one-out residual warning need codes).

### S15. Open physical section: problems to settle before it is marked Specified

- **Problem:**
  1. "FMUs are cached in the project under `fmu/…`" breaks "An adapter never writes outside `workdir`" and spec 3's folder layout (`layout_version` 1). The `remote` target syncs only `runs/<run_id>/`.
  2. `omc` would build in `translate`, which runs in the service's process: no cancel, no progress, outside the time limit, and the FMU's architecture must match the remote host.
  3. The FMU's OpenModelica runtime is loaded into the worker by FMPy (a combined work). Its licence is not checked; only `omc` is a separate process.
  4. Undirected connections clash with E130, E131 and E132 (`from` an output port, `to` an input port).
  5. The manifest records one engine version, but the result depends on both OpenModelica and FMPy.
  6. `tolerance` has no home key.
- **Evidence:** spec 1 `:376`, `:213-216`, `:129`; spec 3 `:231-245`.
- **Fix:** list these as the "Open until" items.

### S16. Acceptance rows: gaps and dependencies on Open sections

- **Problem:**
  1. No row gates the calculators, reliability or life-data fitting, although they have benchmarks. "Each specified adapter passes its benchmarks" covers adapters only.
  2. "Two templates" per adapter are not named. Spec 4's template table needs each template's expected results.
  3. "A chained model … runs from one file" depends on the Open file layout.
  4. "optimizes … a physical system model" depends on the Open physical section.
  5. The surrogate benchmark's "each below the worst of ten designs in the trial" is not a pass rule a test can apply.
  6. M23 holds four engines, studies, surrogates, reliability and calculators. Guide rule 2 (two or three milestones a session) suggests splitting it, and the M17 council may.
- **Fix:**
  - Add a calculators and reliability row.
  - Name the templates or defer them.
  - Use a system dynamics model in place of the physical one in the study row until physical is Specified.
  - Rewrite the surrogate pass rule as fixed thresholds.
  - Split M23 into, for example, M23a (agent, system dynamics), M23b (studies, surrogates), M23c (reliability, calculators) and M23d (physical, multibody, when specified).

---

## Suggestions

1. **Spelling of physical units.** Six of the listed spellings do not parse in the installed pint 0.25: `N.s/m`, `N.m`, `N.m/rad` and `kg.m2` (DefinitionSyntaxError: unknown operator '.'), `m/s2` and `Ohm` (UndefinedUnitError). `units.py` uses pint to tell E140 from E141, and `tests/model/test_units.py:446-449` checks that pint agrees with each size, so each spelling needs a pint mapping. `degC` is an offset unit, which `UNIT_SIZES` (exact multiplicative fractions) and `in_unit` cannot express, and pint raises `OffsetUnitCalculusError` on multiplication. The "Physical units" subsection also has no Specified or Open state. (Checked with `.venv/bin/python` in this repository.)
2. **`confidence` and the manifest.** Forbid `confidence` in deterministic experiments, or say it is ignored. Say the manifest's `seed` is `null` for them, as for optimization runs.
3. **Deterministic differences.** For n = 1, `separated` is always `false` (`src/ithax/runs/statistics.py:61-65`). Say whether a deterministic difference is shown as exact.
4. **Predator–prey units.** The benchmark is stated "per year … 15 years", but there is no year unit (spec 1 time units are `s`, `min`, `h`, `d`). Restate it with `time_unit` d (α 1 per d, 15 d), which is the same mathematics.
5. **Agent behaviour is Ithax's code.** Mesa only schedules; the transition rule is code Ithax writes. That is not a solver (rule 7 holds), but repeatability rests on Ithax's adapter code as much as on Mesa's version. Say so, and record the 13.6 s trial time against the time limit.
6. **Changes to specs 1 to 4.** Add a list of the edits rule 5 needs in the same PR: spec 1 "Top-level keys" (domain values), "Experiments", "Random streams", "Validation issues", "Fidelity label", "Tables"; spec 2 "Simulation-based optimization"; spec 3 `POST /v1/projects`, `/v1/schema`, fit; spec 4 tools.
7. **Findings and display units.** The finding rules are typed on `server` and silent elsewhere, which is fine. `findings/display.py` knows only fraction metrics and seconds, so physical results (m, N, K) need display units (spec 3 "chooses display units").
8. **`world`.** `world` is both a reserved `parent` word and a component type. Say a body may not be named `world` (in `multibody` only).
9. **Benchmarks.** State the seed of each stochastic benchmark (the agent SIR row): "inside the 95% interval" fails for about 5% of seeds.

---

## What holds

- **The adapter contract.** No new adapter needs a change to `capabilities`, `validate`, `translate(model, experiment_id, workdir)`, `run` or `collect`. The new domains are experiment-based, so `check_experiment`'s rule (an id for every domain except `optimization`) already fits (`src/ithax/runs/manager.py:152-176`).
- **Deterministic summaries.** "n 1 and `half_width` `null`" is what `estimate` already returns (`src/ithax/runs/statistics.py:68-78`). The warm-up check skips fewer than 2 replications (`src/ithax/runs/warmup.py:13`).
- **Rule 7.** Wrapping PySD, Mesa, FMPy, MuJoCo, SALib, scikit-learn and scipy is within rule 7, and so is refusing chain cycles and leaving co-simulation out. The one risk found is the surrogate leave-one-out computation (S10).
