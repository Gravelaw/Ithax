# Spec 1: Model Format and Engine Contract

> Version 0.8 · working copy in the repository (source of truth, owner to confirm) · changes are listed under "Changes in this version".

A model is one JSON file that passes a published schema. Every engine is a plugin that implements the same five functions. The interface, the engines and any AI assistant all work through these two contracts.

> **Warning: partly tested.** A prototype ran this format on three models. The `weibull` and `empirical` with `values` distributions passed the sampling test at M2; `empirical` with `data` (M6) and the remote and cluster run targets have never run. Scenarios run from M3 in the experiment manager, and objectives and constraints from M5 in the simulation-based search (AKS-109). Verify each when its milestone arrives, and update this spec. See "Known gaps" in the Build guide.

## Scope

- **In:** the model file, units, validation, the engine plugin interface, run targets, the results format, versioning.
- **Out:** any specific engine (specs 2, 5, 6), the interface (spec 3).

## Model file

| Key | Holds |
| --- | --- |
| `format_version` | Version of this format, for migrations |
| `meta` | Name, description, author, template of origin |
| `domain` | Which engine family the model targets, for example `process` |
| `components` | The blocks: each has an id, a type and parameters |
| `connections` | Directed links between component ports |
| `parameters` | Named values that experiments and optimizers may change |
| `experiments` | Run length, replications, warm-up, scenarios |
| `objectives`, `constraints` | What to optimize and within what limits |
| `run` | Run target and fidelity level |

A minimal example:

```json
{
  "format_version": "0.1",
  "meta": {"name": "Coffee shop"},
  "domain": "process",
  "parameters": {
    "tills": {"value": 1, "type": "integer", "min": 1, "max": 5}
  },
  "components": [
    {"id": "arrivals", "type": "source",
     "params": {"interarrival": {"dist": "exponential", "mean": "2 min"}}},
    {"id": "till", "type": "server",
     "params": {"capacity": {"$param": "tills"},
                "service": {"dist": "exponential", "mean": "1.5 min"}}},
    {"id": "exit", "type": "sink", "params": {}}
  ],
  "connections": [
    {"from": "arrivals.out", "to": "till.in"},
    {"from": "till.out", "to": "exit.in"}
  ],
  "experiments": [
    {"id": "base", "length": "200 h", "warmup": "10 h",
     "replications": 30, "seed": 12345}
  ],
  "run": {"target": "local", "fidelity": "standard"}
}
```

## Units

- Every physical quantity is written with its unit, as in `"2 min"`.
- Values are converted to SI on load. A dimension mismatch is a validation error.
- Library: pint, confirmed by the M1 research note `docs/research/spec-1-schema-and-units.md`. It is declared as `pint>=0.25.3`: pint 0.26 needs Python 3.12, so Python 3.11 installs the 0.25 series. pint accepts much more than the grammar under "Quantities" (for example `2min`, `2 minutes`, `2 * min`, `nan s`), so the loader checks the grammar first and uses pint only to convert.

## Validation

Two passes, both run before any engine starts:

1. **Schema:** structure, types and required keys, checked against the JSON Schema (draft 2020-12, validated with the `jsonschema` package; the schema uses no `format` keyword).
2. **Meaning:** no dangling connections, no unknown component types, units of the right dimension, parameters within allowed ranges.

The JSON Schema checks only the top-level keys, the JSON type of each top-level value, and that every component, connection, parameter and experiment entry is an object with its required keys of the right JSON type. Identifiers and names (`domain`, a component's `type`, `metric`, `run.engine`) are typed as plain strings and component settings (`params`) as a plain object, with no patterns and no per-type required lists; quantities, plain numbers and the enumerated words (a parameter's or variable's `type`, `sense`, `op`, `run.target` and `run.fidelity`) may be any JSON value in the schema. This is so that the meaning-pass codes in the table below (E102, E110 to E171, E174, E175, W200 to W202) and the run codes E172 and E173 are reported with their specific codes. The schema is `src/lcsim/model/schema.json`; `GET /v1/schema` serves it (spec 3). Component type descriptions (settings, ports) come from the adapter's `Capabilities`; until the process adapter exists (M2) the model layer carries the `process` type catalogue from spec 2's block reference, and at M2 the adapter's `capabilities()` must equal it (tested). Flow rates for W201 are propagated from sources: a probability branch multiplies by weight/total, a batch divides by `size`, an unbatch multiplies by it, merges add; where a rate cannot be propagated (shortest-queue branches, stores, timeouts, schedules, failures, and loss points: a `queue` with `on_full: discard`, or a source whose next block has a finite capacity, since either admits less than the offered rate) the check is skipped for every server downstream. In detail (AKS-91): a source's rate is 1 / the mean of its `interarrival`, also with `max_items`; a block with a finite capacity is a `queue` or a server with `queue_capacity`; a schedule or failure stops the rate at the server whose capacity it changes (its target, or a server whose `pool` is the target of a schedule), and that server is not checked either; an unbatch multiplies each batch it receives by the size of that batch, undoing one level of batching; a block on a loop of connections, or after one, is skipped, since a rate on a loop needs the traffic equations solved; so is everything after a value that cannot be read (a reference with E150 or E152, inconsistent fields, an `empirical` `data` column, an interarrival mean not above zero). A block no source reaches gets rate zero. Only the first connection from an output port, with both ends valid, carries items. The mean of a distribution is its theoretical mean from the sampling test under "Distributions", except that a `normal` is sampled clipped at zero, so its mean is mean·Φ(mean/sd) + sd·φ(mean/sd), which equals `mean` to within one part in 10⁷ when `mean` ≥ 5 `sd`. Rates are compared with the capacity exactly. The warnings W201 and W202 are checked with each parameter at its `value` and in each scenario, and name the first case that fails; not at `min` and `max`, since a search tries values the modeller may expect to be poor.

Errors name the component and the key, in plain language.

Before the schema pass the file is read as UTF-8 JSON (a leading byte order mark is accepted). Text that is not JSON, `NaN` or `Infinity`, a whole number with more digits than Python reads (4,300 by default), nesting deeper than the JSON reader allows, and a key written more than once in one object are E100, because the file cannot be read unambiguously. A file with a schema issue is not loaded further. Loading then converts every value (see "Units") and reports, with its own code, each value it cannot convert; the checks across the model (identifiers, references, the connection graph, ranges, metric names, warnings) follow on a model that loads.

## Engine contract

Each engine adapter is a Python class with five methods:

| Method | Does |
| --- | --- |
| `capabilities()` | Declares domains, component types, hardware needs and parallel modes |
| `validate(model)` | Engine-specific checks beyond the common ones |
| `translate(model, experiment_id, workdir)` | Writes the engine's own input files |
| `run(workdir, on_progress, cancel, workers)` | Executes, reports progress, honours cancel |
| `collect(workdir)` | Reads engine output into the common results format |

Adapters are discovered as plugins, so a new engine needs no change to the core.

Discovery mechanism, confirmed by the M2 research note (`docs/research/spec-1-plugin-mechanisms.md`): Python entry points in group `lcsim.engines`, each naming a class that implements `EngineAdapter`; the product's own adapters are registered the same way in its `pyproject.toml`. The entry-point name is the adapter name that `run.engine` refers to and equals the class's `name`. Entry points are listed without importing them; each is then loaded inside a guard, and one that fails to import is left out and logged, never fatal. Two installed entry points with the same name are both left out and logged, without importing either; if that leaves no single engine for the model's `domain`, the issue is E102. The guard covers the whole load: importing the entry point, creating the class with no arguments, and calling `capabilities()`. An entry point that fails any of these, whose object does not provide the `EngineAdapter` methods, whose `capabilities()` does not return `Capabilities`, or whose class `name` differs from the entry-point name is left out and logged in the same way, since `run.engine` could not name it reliably. The installed adapters are discovered once per process, when they are first needed; an engine installed later is found after a restart. The product's process adapter is named `simpy` (entry point `simpy = lcsim.engines.process.adapter:ProcessAdapter`) and its optimization adapter `highs` (entry point `highs = lcsim.engines.optimize.adapter:HighsAdapter`, AKS-108, owner to confirm); the `version` of each is the product version, since it ships with the product. The group name follows the package name: `lcsim` is a placeholder and is taken on PyPI by an unrelated project, so the group is renamed with the package before the first release.

**Engine licence rule.** The product is AGPL-3.0. An adapter drives its engine as a separate process through the engine's own input and output files; it does not import the engine into the service process unless the engine's licence is recorded in `docs/DECISIONS.md` as compatible with AGPL-3.0 for a combined work (Phase 1 engines SimPy, HiGHS via highspy, Pyomo and Optuna are MIT or BSD per PyPI metadata read on 2026-11-05 and may be imported). Engines are installed by the environment manager, not compiled into the product. `capabilities()` reports the engine's licence identifier and how it is invoked (`process` or `in-process`). This is not legal advice; a lawyer confirms the rule before the first release. Proposed default, owner to confirm.

## Run targets

| Target | How |
| --- | --- |
| `local` | A process on this machine |
| `remote` | Another machine reached over SSH |
| `cluster` | A job submitted to a Slurm queue |

Job states are `queued`, `running`, `done`, `failed` and `cancelled`. The same model file and the same results format apply to all three targets.

Where each method runs:

| Method | `local` | `remote` | `cluster` |
| --- | --- | --- | --- |
| `validate`, `translate`, `collect` | The service's worker process on this machine | The same | The same |
| `run` | In the worker process | `runs/<run_id>/` is synced to the host; `python -m lcsim.runs.worker <workdir>` is invoked over SSH (package and engine installed there; the service checks this first); the folder is synced back | The same through `sbatch`; cancel through `scancel` |

At M3 only `local` can run. A file naming `remote` or `cluster` still loads; starting it before M11 is refused with E172 and no run is created (spec 3: `POST .../runs` returns 422). The remote and cluster rows are proposed and built at M11 (the council recommends moving them to Phase 2; owner question).

The worker entry point (AKS-103, proposed default, owner to confirm): `python -m lcsim.runs.worker <workdir> [--workers N]` (`N` defaults to 1). `<workdir>` is `runs/<run_id>/engine/`, into which `translate` has already written the engine's input. The worker reads the adapter's name from `engine.name` in `<workdir>/../manifest.json`, creates that installed adapter with no arguments and calls `run(workdir, on_progress, cancel, N)`, with `cancel` reading as set once a file named `CANCEL` exists in `<workdir>`. It prints one line per progress report to standard output, `{"type": "progress", "fraction": ..., "message": ...}` as spec 3 "Progress events" shows it, and ends with exit status 0 when `run` returned, 3 when it was cancelled, 1 when the adapter raised (the traceback on standard error), and 2 when its arguments or the manifest cannot be used. It writes nothing itself; time and memory limits are enforced by the side that started it.

## Results

| File | Holds |
| --- | --- |
| `summary.json` | Key numbers, warnings, fidelity label |
| `manifest.json` | Engine name and version, random seeds, run target, timings |
| Tables | Time series and statistics, as Parquet |
| Fields | Spatial results for physics engines, as VTK-family files |

A run is reproducible from the run folder: the model, its manifest and any copied data.

## Versioning

`format_version` is `MAJOR.MINOR` as a string. A minor increase is additive: a reader accepts any file with its own major and a minor no higher than its own, filling defaults in memory. A major increase ships a migration that rewrites the file after asking the user. E101 is raised for an unknown major or a minor above the reader's, and for a string that is not two ASCII decimal integers without leading zeros joined by a dot (`"0.1.0"`, `"v0.1"`, `"0.01"`); a `format_version` that is not a string is E100. A file with E101 gets no other schema issue, because it may follow another version's schema. This reader is version 0.1, so it opens 0.0 and 0.1. Each new major version ships a migration that upgrades older files. The app never opens a file it cannot migrate without saying so. A migration is a function from one major version to another, registered for that pair of majors; a file is migrated through the fewest registered steps, and a file of the reader's major with a minor above the reader's is never migrated. The model layer never migrates on its own and never writes the file: a file of another major is E101 when loaded even when a migration exists, and the hint then says that the program can convert it. The caller (the service, the interface) asks the user, migrates, and saves the rewritten file only after the user agrees. Format 0 ships no migration; the M1 test registers a test-only one from the test itself.

## Detailed specification

The sections below are binding. Where they differ from the summary above, these win. The example above is one of three model files that a throwaway prototype ran successfully. The prototype script was not retained; the other two files are written fresh at M1 (proposed default, owner to confirm). This spec, not the prototype, defines the format.

### What the prototype changed

Running three example models against the first draft of the format forced four changes:

1. **Component settings are nested under `params`.** This keeps `id`, `type` and interface data apart from engine settings.
2. **Connections name ports.** A branch block has several outputs, so `["a", "b"]` pairs were not enough.
3. **Parameters are referenced with `{"$param": "name"}`.** Experiments and optimizers change the parameter, and every use follows.
4. **Experiments carry a `seed`.** Without it a run cannot be repeated.

### Identifiers

- Pattern: `^[a-z][a-z0-9_]{0,63}$` (E111), for the id of every component, parameter, experiment, scenario, objective, constraint and variable, and for each route of a branch (a route names an output port).
- Unique within their list (E110): components, parameters, experiments, the scenarios of one experiment, objectives, constraints, variables, the routes of one branch. Lists are separate: a component and an experiment may share an id. E110 is reported at each later use.
- Used unchanged in metric names, error messages and results.
- `model` is reserved as a metric prefix (`model.wip.mean`) and `optimizer` as the random-stream key of the simulation-based search (spec 2); neither may be a component id. `default` is reserved as the scenario id of the implicit scenario. Using a reserved identifier is E112.

### Top-level keys

| Key | Type | Required | Default |
| --- | --- | --- | --- |
| `format_version` | string | yes |  |
| `meta` | object with `name` (required), `description`, `author`, `template` | yes |  |
| `domain` | string; Phase 1 values `process` and `optimization` | yes |  |
| `parameters` | object keyed by parameter id | no | empty |
| `components` | array of component objects | yes for `process`; not allowed for `optimization` |  |
| `connections` | array of connection objects | yes for `process`; not allowed for `optimization` |  |
| `experiments` | array of experiment objects | yes for `process`; not allowed for `optimization` |  |
| `objectives` | array of `{id, metric, sense}` | `process` only; no | empty |
| `constraints` | `process`: array of `{id, metric, op, value}`; `optimization`: array of `{id, linear, op, rhs}` | no | empty |
| `variables` | array of `{id, type, lower?, upper?}` | yes for `optimization`; not allowed for `process` |  |
| `objective` | object `{sense, linear}` | yes for `optimization`; not allowed for `process` |  |
| `run` | object with `target` and `fidelity` (both required when `run` is present) and optional `engine` (adapter name) | no | `local`, `standard` |

Which keys are required, and the shape of `constraints`, depend on `domain`. A key that belongs to the other domain is an E100 error. When `domain` is not one of the Phase 1 values, the schema pass checks every key as above but requires and forbids no domain-specific key; the meaning pass reports E102. Phase 1 process and optimization engines accept only `fidelity: standard`; the fidelity ladder of spec 6 applies to physics domains. Another value is E173. The service selects the one installed adapter whose capabilities include the model's `domain`; if there are several and `run.engine` is absent, or none, the issue is E102. When `run.engine` is present, the adapter of that name is chosen, and E102 is raised if no installed adapter of that name handles the `domain`. The E102 `path` is `/domain` when no adapter handles the domain, and `/run/engine` otherwise. The loader checks this before building, since a model of a domain no engine runs cannot be built. Until an adapter existed for a Phase 1 domain (M2 for `process`, M5 for `optimization`), the model layer stood in for it, with no adapter name. From M5 both Phase 1 domains are checked against the discovered adapters and the stand-in is gone, so `run.engine` must name one of them (the product's are `simpy` for `process` and `highs` for `optimization`), and a domain no installed adapter handles is E102 at `/domain` (AKS-108).

Unknown keys are an error, except under any `ui` key, which engines ignore. In this version only a component has a `ui` key; a top-level `ui` is an unknown key.

### Quantities

- Grammar: a number, one space, a unit. Example: `"1.5 min"`.
  - The number follows the JSON number grammar, `-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?`; `nan`, `inf`, `+2` and `.5` are not numbers.
  - Exactly one space (U+0020) separates number and unit, with nothing before or after.
  - The unit is one of the Phase 1 units below, written exactly as listed; case matters.
  - A unit that the units library knows, but whose dimension differs from the one the setting expects (`"5 m"` for a time), is E140. Any other string that breaks these rules (`"2min"`, `"2 minutes"`, `"2 ms"`, `"nan s"`) is E141. A unit name with several readings is E140 only when no reading has the expected dimension: `"2 cd"` (candela, or centi-day) for a time is E141.
  - A number whose value in SI units is not a finite float (`"1e400 s"`, `"1e308 d"`) is E141.
- Phase 1 time units: `s`, `min`, `h`, `d`. Internal time is seconds, as a float; `"-0 s"` is stored as 0.0.
- Counts, probabilities and capacities are plain JSON numbers with no unit.
- A quantity where a plain number is expected, or the reverse, is an error (E123). Where a plain number is expected, any value other than a finite JSON number (a quantity, any other string, `true`, `false`, `null`, an array or an object) is E123. Where a quantity is expected, a value that is neither a string nor a number (`true`, `false`, `null`, an array, or an object other than a `{"$param": "id"}` reference) is E141.

### Parameters

Each entry has `value` and `type` (both required; `type` is `integer`, `number` or `quantity`), and optional `min`, `max`, `description`. `value`, `min`, `max` and a scenario's value for the parameter are written as its `type` says: an `integer` is a whole number (`2.0` reads as 2), a `number` a plain number, a `quantity` a time quantity, since time is the only dimension with Phase 1 units. A `{"$param": "id"}` object may appear anywhere a component setting takes a number or quantity, including a distribution's fields and the values inside an object setting; it is exactly that one key with a text id, and any other object is not a reference.

- A reference to an id that is not in `parameters` is E150.
- The parameter's `type` must fit the place that refers to it: `integer` where a whole number is taken, `integer` or `number` where a plain number is taken, and `quantity` where a time is taken. Otherwise E152.
- A `value`, or a scenario's value, below `min` or above `max` is E151, at that value; a `min` above `max` is E151 at `min`.
- A setting or distribution field that refers to a parameter is checked, by the error rules for that setting or field, against every value the model gives the parameter: its `value`, its `min` and `max` (the range a search explores), and each scenario's value. Where several parameters feed one check (two weights, a `min` and a `max`), every combination of their bounds is also checked, since a search varies them together. An issue names the first case that fails. Warnings W201 and W202 are checked only at the `value` and each scenario's value (see "Validation").

### Components and ports

Each component has `id`, `type`, `params`, and optional `label` and `ui`. The `ui` object holds canvas position and is never read by an engine.

- Each component type declares its ports. Most have `in` and `out`; a source has only `out`; a sink has only `in`; a branch has one output port per entry of its `routes` setting, named by that entry.
- A connection is `{"from": "<id>.<port>", "to": "<id>.<port>"}`. Each end is split at its first dot; an end without a dot, or with nothing before or after it, is E130.
- Every output port connects to exactly one input port. An input port accepts any number of connections.
- A `from` end must name an output port of its component and a `to` end an input port; an unknown component or port is E130, except that a `from` end on a branch naming a port that is not in its `routes` is E161. An output port that no connection names is E131, at the component (`/components/<i>`), or for a branch at the route's entry in `routes`. A second connection from the same output port is E132, at that connection's `from`. A connection whose `from` end is valid connects that port even when its `to` end is wrong, so a wrong `to` end gives one issue.

### Distributions

| `dist` | Fields | Notes |
| --- | --- | --- |
| `constant` | `value` |  |
| `exponential` | `mean` | `mean` is 1/rate; sampled as the scale |
| `uniform` | `min`, `max` |  |
| `triangular` | `min`, `mode`, `max` |  |
| `normal` | `mean`, `sd` | Negative samples are set to zero, which raises the sample mean; W202 warns when `mean` < 2 × `sd` |
| `lognormal` | `mean`, `sd` | Mean and standard deviation of the variable itself, not of its logarithm. Sampled with σ² = ln(1 + sd²/mean²), μ = ln(mean) − σ²/2 |
| `weibull` | `shape`, `scale` | Mean is scale × Γ(1 + 1/shape); not exercised by the prototype |
| `empirical` | `values` (array of plain numbers or quantities of one dimension, inline) or `data` = `{"file": "<name in data/>", "column": "<column>"}` | Sampled with equal probability and replacement. `values` must hold at least one value (E160). With `data`, values are read as numbers or as quantities per the column index's declared unit; the run copies the column to `runs/<run_id>/data/<component id>.<setting>.parquet`, where `<setting>` is the name of the setting that holds the distribution (for example `time_to_repair`), so two `data` references on one component never share a file (never under `tables/`, which holds only the tables listed in "Run folder and results") and the manifest records, per reference, the source file name, column and SHA-256; a missing or changed file is E162. Not exercised by the prototype; `data` arrives with the import endpoint at M6 |

Fields that must agree (E160): `sd`, `shape`, `scale`, and the `mean` of the positive distributions (`exponential` and `lognormal`) are greater than zero; a `min` is not above its `max`, and a triangular `mode` lies from `min` to `max`. A `min` equal to the `max` is allowed. A `normal` `mean` may be zero or negative; W202 warns when it clips.

Negative times are clipped (proposed default, owner to confirm): every distribution setting in Phase 1 is a time, and every sampled time below 0 s is set to 0 s, whatever the distribution, as the `normal` row already says. So a `constant` of `-1 min` always gives 0 s, a `uniform` from `-1 min` to `1 min` gives 0 s about half the time, and an `empirical` value below 0 s gives 0 s when drawn. No issue code reports a distribution that reaches below 0 s; only the `normal` has a warning (W202). W201 still uses the theoretical mean of the written distribution, with the clipped mean only for the `normal`, so it underestimates the load of a server whose service distribution reaches below 0 s.

Until the import endpoint (M6), an `empirical` with `data` cannot be sampled: asking for its sampler raises a condition with code E162 that names M6, which the adapter reports as an issue object. Validation already reports every `data` reference as E162 before then, so a run never reaches it.

A `data` reference is checked against the column index of the project's `data/` folder (spec 3 "Project folder"), which records each imported file's name, its columns with the declared unit of each, and the SHA-256 of the file at import. E162 is raised for a `file` not in the index, a file in the index that is now missing from the folder or whose SHA-256 differs, and a `column` the file does not have. Until the import endpoint writes the index (M6), the index is empty, so every `data` reference is E162. The model layer reads no values and checks no declared unit; M6 does both.


Sampling test (M2, every distribution): 20,000 samples from one stream; the sample mean lies within four standard errors of the theoretical mean, standard error = theoretical standard deviation / √20000. Theoretical mean and sd: constant: value, 0 (so the samples must equal the value exactly); exponential: mean, mean; uniform: (min+max)/2, (max−min)/√12; triangular: (min+mode+max)/3, √((a²+b²+c²−ab−ac−bc)/18); normal: tested with mean ≥ 5 sd so clipping is negligible, plus an assertion that no sample is negative; lognormal: the given mean and sd; weibull: scale·Γ(1+1/shape), variance scale²·[Γ(1+2/shape) − Γ(1+1/shape)²]; empirical: mean and population sd of `values`.

### Experiments

| Field | Type | Default |
| --- | --- | --- |
| `id` | identifier | required |
| `length` | time quantity | required |
| `warmup` | time quantity, less than `length` | `0 s` |
| `replications` | integer, at least 2 | 30 |
| `seed` | integer | chosen at random when the file is loaded (from 0 to 2⁶³ − 1, from the operating system's generator) and recorded in the manifest |
| `scenarios` | array of `{id, set: {parameter id: value}}`, both keys required | one scenario with the reserved id `default` and an empty `set`, also when the array is empty; a user scenario may not use that id (E112) |
| `confidence` | number in (0, 1) | 0.95 |
| `record_interval` | time quantity | `length` / 200 |
| `search` | object `{objective, budget, variables, replications}` | absent: a plain experiment |

`search.objective` (required) names an id in top-level `objectives` (exactly one in Phase 1); `search.budget` is an integer at least 1, default 50; `search.variables` is an array of parameter ids, default every parameter with both `min` and `max`; `search.replications` (integer at least 2, default 10) is the replications per candidate during the search, while the experiment's own `replications` is used for the confirmation stage of spec 2. E171 covers a `search` that names an unknown objective or a parameter without `min` and `max`, and a search with no variables (an empty `variables`, or none listed and no parameter with both `min` and `max`). It also covers a parameter named twice in `variables`, at the repeat, and a `search` in an experiment that lists scenarios, at `scenarios`, since a search runs its own candidates rather than scenarios (an empty `scenarios` is the `default` scenario and is allowed; AKS-109, owner to confirm). A variable that is not a parameter is E150.

E170 covers a value outside the ranges in the table: a `length` not above 0 s, a `warmup` below 0 s or not less than `length`, `replications` below 2, `confidence` outside (0, 1), a `record_interval` not above 0 s, a `search.budget` below 1 and `search.replications` below 2. Each is reported at its own key. Running an experiment that has `search` runs the simulation-based search of spec 2; the run id, states and events are those of any run. Verified at M5 (AKS-109): `tests/runs/test_search.py` runs searches through the experiment manager and `tests/runs/test_local_search.py` through the local target, where a search run is `queued`, `running`, then `done`, `failed` or `cancelled` like any other, with one `run_id`, one manifest and one time limit for the whole search (owner to confirm).

### Random streams

Each component gets its own random stream in each replication. The stream key is the UTF-8 string `<seed>:<replication>:<component id>` (replication numbered from 0). Its SHA-256 digest, read as a big-endian integer, seeds `numpy.random.SeedSequence`, which seeds a PCG64 `numpy.random.Generator`. Python's built-in `hash()` is salted per process and must never be used. Scenario and search candidate do not enter the key, so every scenario of an experiment and every candidate of a search faces the same random events (common random numbers). The search itself takes exactly one draw from the reserved key `<seed>:0:optimizer`, the seed of Optuna's sampler (spec 2 "Simulation-based optimization"; AKS-109). The generator name and the numpy version are written to `manifest.json`; a repeat is promised only on the same versions. Adding or removing one component therefore leaves every other component's random numbers unchanged. The prototype used this scheme and gave identical results on repeat runs. A component that samples several values draws them all from its one stream, in the order of the events that need them: a source draws each interarrival time after creating an item, a server draws each service time when that service starts, a `store` draws each `lead_time` when it places the order (AKS-106), and a component with two distributions (a `failure` block's `time_to_failure` and `time_to_repair`) interleaves them in event order: a `failure` block draws its first `time_to_failure` at time 0, a `time_to_repair` at each failure and the next `time_to_failure` at each repair (AKS-107). A `schedule` and a `resource_pool` draw nothing. Proposed default (AKS-98), owner to confirm.

### Metric names

`<component id>.<measure>` with an optional `.<statistic>`, for example `till.wait.mean` or `exit.throughput`. Objectives and constraints refer to metrics by these names:

```json
{"objectives": [{"id": "cost", "metric": "till.wait.mean", "sense": "minimize"}],
 "constraints": [{"id": "util", "metric": "till.utilization", "op": "<=", "value": 0.85}]}
```

An objective's `sense` is `minimize` or `maximize`. A constraint's `op` is `<=` or `>=` (an equality on a simulated mean is never met exactly), and its `value` is a plain number, or a time quantity for a metric measured in time (`wait.mean`, `cycle_time.mean`). A rate (`throughput`, `orders`, `discarded`: spec 2 defines each as a count divided by the period) is a plain number of items per second, the SI unit in which results store it, because Phase 1 has no rate unit: 30 items per hour is written `0.008333`. Proposed default, owner to confirm; a rate unit such as `1/h` would be an additive minor version. A `value` of the wrong kind for its metric is E123. A metric name is `<component id>.<measure>[.<statistic>]` exactly as spec 2 lists it for the component's type, or `model.wip.mean`; `till.wait` without `.mean` is not one. Metrics whose names are defined in spec 2 "Statistic definitions" are the only ones objectives and constraints may name; naming any other is E174. Item attributes, the `attribute` branch rule and priority queue disciplines are deferred to Phase 2 until a block that sets attributes exists (proposed default, owner to confirm; recorded in the Build guide known gaps).

### Validation issues

Every issue is one object:

```json
{"code": "E131", "severity": "error", "component": "till",
 "path": "/components/1",
 "message": "The 'out' port of 'till' is not connected to anything.",
 "hint": "Connect it to another block or to a sink."}
```

`severity` is `error` or `warning`: `error` for an E code, `warning` for a W code. `path` is a JSON Pointer (RFC 6901) to the key or value concerned; for a missing key it is where the key belongs, and `""` is the whole file. `component` is the id of the component the path lies in, or `null`.

| Code | Pass | Meaning |
| --- | --- | --- |
| E100 | schema | File does not match the schema: wrong JSON type, missing required key, or an unknown key at top level or in a component, connection, parameter or experiment, including a key that belongs to the other `domain` |
| E101 | schema | Unsupported `format_version` |
| E102 | meaning | No single engine for this `domain` |
| E110 | meaning | Duplicate identifier |
| E111 | meaning | Identifier does not match the pattern |
| E112 | meaning | Reserved identifier used (`model` or `optimizer` as a component id, `default` as a scenario id) |
| E120 | meaning | Unknown component type |
| E121 | meaning | Unknown setting for this component type (an unknown key inside `params`, or inside an object setting such as a shift); also a key of a branch's `weights` that is not one of its `routes` |
| E122 | meaning | Required setting missing (also a required key of an object setting); also a route of a branch with `weights` that has no weight |
| E123 | meaning | Setting has a quantity where a number is expected, or the reverse; also any value that is not of the kind its place takes: a non-whole number where a whole number is expected, a word outside its list (a parameter's or variable's `type`, `sense`, `op`, `discipline`, `on_full`, `rule`), a setting that should be text, an array or an object and is not, a number or time below the smallest value its setting takes (spec 2 "Ranges"), a branch with no `routes`, `weights` that are all zero, a shift that does not end after it starts or ends after `period`, or a constraint `value` of the wrong kind for its metric |
| E124 | meaning | Setting names an unknown component or one of the wrong type (`pool`, `target`) |
| E125 | meaning | A server or pool is the target of more than one `schedule`, or a server of more than one `failure` |
| E130 | meaning | Connection names an unknown component or port |
| E131 | meaning | Output port not connected |
| E132 | meaning | Output port connected more than once |
| E140 | meaning | Quantity has the wrong kind of unit |
| E141 | meaning | Quantity cannot be parsed |
| E150 | meaning | Reference to an unknown parameter (a `$param`, a scenario's `set` or a search variable) |
| E151 | meaning | Parameter value outside its `min` and `max` (its `value` or a scenario's value), or a `min` above the `max` |
| E152 | meaning | Parameter type does not fit the setting that references it |
| E160 | meaning | Distribution fields inconsistent: `min` above `max` (or a triangular `mode` outside `min` to `max`); `sd`, `shape`, `scale` or the `mean` of a positive distribution not greater than zero; empty `values`. Also a distribution that cannot be read: not an object, no `dist` or an unknown one, a missing or unknown field, both or neither of `values` and `data`, `values` not an array, or `data` not `{file, column}` with text values |
| E161 | meaning | Connection names a branch route that is not in `routes` |
| E162 | meaning | Data reference names a file or column not in the project's `data/` folder, or the file is missing or its hash has changed |
| E170 | meaning | Experiment invalid, such as `warmup` not less than `length` or `confidence` outside (0, 1); every case is listed under "Experiments" |
| E171 | meaning | `search` names an unknown objective or a parameter without `min` and `max`, has no variables, names a parameter twice, or is in an experiment that lists scenarios |
| E172 | run | Run target not available on this build, not configured, or not reachable |
| E173 | run | Fidelity not offered by this engine |
| E174 | meaning | Objective or constraint names a metric that does not exist: an unknown component, or a measure or statistic that spec 2 does not define for that component's type |
| E175 | meaning | A coefficient in an `optimization` model's `objective` or in a constraint's `linear` names no variable in `variables`; reported at the coefficient's key, such as `/constraints/0/linear/desks` (AKS-108, owner to confirm) |
| E180 | service | Edit cannot be applied (spec 3 "Model edits" lists the cases: 400, at `/edits/<n>`) |
| E181 | service | Model changed since the stated revision |
| E182 | service | Token missing or wrong (spec 3: 401, or a WebSocket closed with 1008) |
| E183 | service | Request refused by the hardening rules: a `Host` other than the service's own address, or a WebSocket `Origin` other than the interface's (spec 3: 403) |
| E184 | service | Request malformed: a body that is not JSON, a field missing, unknown or of the wrong kind, or an unknown `X-Client` (spec 3: 400) |
| E185 | service | Not found: no such project, template, component type or path (spec 3: 404), or a method a path does not take (405) |
| E186 | service | Project folder cannot be used: not a project folder, not empty when a project is created there, already registered under another folder, or not writable; also a `model.json` that is not JSON, cannot be stored as it is (a number JSON cannot hold, or text that is not valid Unicode), or fails the schema pass when edits are sent (spec 3: 400) |
| E187 | service | The service failed while answering; the details are in its log (spec 3: 500) |
| E188 | service | Action not allowed in the run's current state: cancelling a run that has ended, or reading the summary or a table of a run that is not `done` (spec 3: 409) |
| E190 | run | Engine exited with an error (details in `log.txt`) |
| E191 | run | Run interrupted by a service restart |
| E192 | run | Run exceeded its time or memory limit |
| W200 | meaning | Component with an `in` port cannot be reached from any source (over connections whose two ends are valid, the first from each output port) |
| W201 | meaning | Mean arrival rate at a server times its mean service time is at least its capacity, and its queue is unlimited, so the queue will grow without limit |
| W202 | meaning | Normal distribution will clip about 2% or more of its samples at zero (`mean` < 2 × `sd`) |
| W210 | run | Results were still changing after warm-up; lengthen `warmup` |

Codes E300 to E399 are reserved for engine-specific issues from `validate(model)`; each adapter documents its own. Errors block a run. Warnings do not. Run and service codes are raised by the experiment manager or the service and are tested at their milestones, not by validation fixtures.

### Engine adapter interface

```python
class CancelToken(Protocol):
    def is_set(self) -> bool: ...


class EngineAdapter(Protocol):
    name: str
    version: str

    def capabilities(self) -> Capabilities: ...
    def validate(self, model: Model) -> list[Issue]: ...
    def translate(self, model: Model, experiment_id: str | None, workdir: Path) -> None: ...
    def run(self, workdir: Path,
            on_progress: Callable[[Progress], None],
            cancel: CancelToken,
            workers: int) -> None: ...
    def collect(self, workdir: Path) -> Results: ...
```

- `Capabilities` lists domains, component types with their settings and ports, hardware needs, parallel modes, the engine's licence identifier and how it is invoked. Fields: `domains` (the `domain` values it runs), `component_types` (type name to its description: settings, ports, metrics and a one-sentence `description` summarising its Behaviour in spec 2's "Block reference", as the model layer's `process` catalogue describes a type; `GET /v1/schema/components/{type}` serves it, spec 3), `hardware` (what the engine needs beyond a CPU and memory, such as `gpu`; empty for none), `parallel_modes` (drawn from `replications`, `threads`, `processes`, `gpu`; see "Division of labour"), `licence` (an SPDX identifier, such as `MIT`) and `invocation` (`process` or `in-process`; see "Engine licence rule"). The process adapter reports `domains` `process`, the twelve types of the `process` catalogue, no hardware, `replications`, `MIT` and `in-process`. The optimization adapter `highs` reports `domains` `optimization`, no component types, no hardware, no parallel modes (one solve per run), `MIT` (HiGHS's licence; Pyomo's BSD-3-Clause is recorded in `docs/DECISIONS.md`) and `in-process` (AKS-108, owner to confirm).
- `translate` is given the id of the experiment to run for a `process` model, and `None` for an `optimization` model, which has no experiments (spec 3 `POST .../runs`); a process adapter given `None`, or an optimization adapter given an id, raises `ValueError` (AKS-108, owner to confirm).
- `Progress` has `fraction` (0 to 1), `message`, and optional live `metrics`.
- `run` checks `cancel` at least once a second and stops cleanly when it is set.
- `CancelToken` is supplied by the run target, never by the adapter. `local`: a `multiprocessing.Event`. `remote` and `cluster`: a file named `CANCEL` in `workdir`, created over SSH or alongside `scancel`.
- An adapter never writes outside `workdir`.

#### Division of labour

`workdir` is `runs/<run_id>/engine/`; the manager owns everything else in the run folder. `translate`, `run` and `collect` are called once per run; a search run (spec 2) calls them once per candidate evaluation, each in its own subfolder of `engine/`: `search-<n>` for candidate n's search stage and `confirm-<n>` for its confirmation, n from `000`, the baseline (AKS-109, owner to confirm). Each evaluation is given the experiment with one `default` scenario holding the candidate's values and the stage's replications, so an adapter needs nothing new for a search. The adapter runs every scenario and replication inside `run`, using at most `workers` processes; it must honour `warmup`. `Table` is a pyarrow Arrow table (pyarrow, Apache-2.0, confirmed from the wheel's `LICENSE.txt` by the M2 research note `docs/research/spec-1-plugin-mechanisms.md`). A process adapter reports per-replication values and sampled time series only, in the `replications` and `timeseries` table layouts of "Run folder and results"; the manager computes means, half-widths and paired scenario differences. An optimization adapter has no replications: it returns `Results.solution`, a dict in the `summary.json` layout of spec 2 "Optimization model layout" (`status`, `objective`, `variables`, `constraints`), and the manager computes no statistics for it. `Results(tables: dict[str, Table], warnings: list[Issue], solution: dict | None = None)`; `solution` is set by optimization adapters only. The manager writes `tables/*.parquet`, `summary.json` (adding the fidelity label and warnings to `solution` for an optimization run) and `manifest.json`. `Capabilities.parallel_modes` is drawn from `replications`, `threads`, `processes`, `gpu`; an adapter listing `replications` runs them in parallel up to `workers`.

The process adapter (AKS-98): `translate` writes `engine/input.json`, holding the experiment's `id`, `length`, `warmup`, `replications`, `seed` and `record_interval` (times as SI floats), the connections, and for each scenario every component's `id`, `type` and settings, with parameters resolved for that scenario, quantities as SI floats and the catalogue's defaults filled in. It leaves out `ui`, `label` and `meta`, so changing them leaves the file byte-equal. `run` runs each scenario and replication from its own streams, in the calling process (the run target's worker process) when `workers` is 1 and otherwise in up to `workers` separately started (spawned) processes; the results do not depend on `workers`. It writes `engine/output/replications.parquet` and `engine/output/timeseries.parquet` once every replication has finished, and nothing when it is cancelled; `collect` returns both tables. Proposed default, owner to confirm.

The optimization adapter (AKS-108): `translate` writes `engine/input.json`, the model's `variables`, `objective` and `constraints` in the model file's layout with every number as a float (no `meta` or `run`, so changing them leaves the file byte-equal; a whole number too large for a float fails the run with E190). `run` solves it once with HiGHS through Pyomo in the calling process (`workers` is not used) and writes `engine/output/solution.json`: the spec 2 `summary.json` layout (`status`, `objective`, `variables`, `constraints`), with the duals of a program whose variables are all `continuous` and the solver's name and version beside it; it writes nothing when `cancel` is set before or after the solve. A solve called through Pyomo cannot be interrupted, so a cancel during a solve takes effect when the solve returns, or when the run target terminates the worker after the cancel grace (engine gap, `docs/DECISIONS.md`). `collect` returns the layout as `Results.solution` and no tables. Proposed default, owner to confirm.

### Run folder and results

`run_id` is `<UTC time YYYYMMDDTHHMMSS>-<6 random base32 characters>`, unique across projects; the service resolves a `run_id` through the `index.sqlite` of each project listed in `projects.json` (spec 3).

```text
runs/<run_id>/
  model.json      the exact model that ran
  manifest.json   engine name and version, seed, target, start and end times, host
  summary.json    key numbers and warnings
  tables/         one Parquet file per table
  data/           copied empirical columns, present only when the model uses `data`
  engine/         the engine's own input and output files
  log.txt
```

`manifest.json` fields: `run_id`, `project_id`, `experiment_id`, `scenario_ids`, `state`, `created`, `started`, `ended` (ISO 8601 UTC), `target`, `host`, `client` (`ui`, `mcp` or `script`), `engine` `{name, version}`, `generator` `{name, numpy_version}`, `product_version`, `format_version`, `seed`, `fraction`, `data_files` (array of `{file, sha256}`), on a search run `optimizer` `{name, version}` (`optuna` with the Optuna version, or `exhaustive` with `null`, since a seeded Optuna search repeats only on the same Optuna version; AKS-109, owner to confirm), optional `error`. `manifest.json` is rewritten atomically (temp file and rename) on every state change and at most once a second on progress. It is the source of truth; `index.sqlite` is a cache. `error` is an issue object with E190, E191 or E192 (E172 never reaches a manifest: the run is refused before it is created). On start the service marks every run whose manifest says `queued` or `running` and whose worker is not alive as `failed` with E191. A service that stops while runs are unfinished stops their workers and marks each `failed` with E191 itself, as it does a queued run (spec 3 "Runs outlive the interface"; AKS-112, owner to confirm). On start, and when it first uses an opened project, the service checks every run folder of the project in this way; a folder whose `manifest.json` cannot be read (by the service's strict reader, which also refuses `NaN`, infinities such as `1e999` and text that is not valid Unicode; review of PR #36), or does not hold a `state` of the five, a `created` text, `project_id`, `experiment_id`, `started` and `ended` as text or `null`, a `fraction` from 0 to 1 and a `seed` that is `null` or a whole number from 0 to 2⁶³ − 1 (review of PR #36), is not a run: it is left as it is and listed nowhere (AKS-112, owner to confirm).

Results are stored in SI units with the unit named. The interface chooses display units. A `summary.json` for the coffee shop run:

```json
{"model": "Coffee shop", "experiment": "base", "fidelity": "standard",
 "fidelity_label": "Standard: 30 replications of 200 h, 95% confidence",
 "replications": 30, "confidence": 0.95,
 "scenarios": {
   "default": {
     "set": {},
     "metrics": {
       "till.wait.mean":   {"mean": 273.3, "half_width": 13.0, "unit": "s", "n": 30},
       "till.utilization": {"mean": 0.752, "half_width": 0.006, "unit": "1", "n": 30}
     }
   }
 },
 "differences": [],
 "warnings": []}
```

`fidelity_label` is the text the interface shows (principle 4). A search run adds a `search` object, defined in spec 2; the rest of its `summary.json`, and its `tables/`, are those of the best candidate's confirmation, with the one scenario `default` (spec 2 "Simulation-based optimization"; AKS-109, owner to confirm).

How the experiment manager fills `summary.json` for a process run (AKS-102, proposed default, owner to confirm):

- **Metrics.** Each scenario's `metrics` holds every metric of the `replications` table, in its row order, as `{mean, half_width, unit, n}`: the mean and half-width across replications of spec 2 "Statistic definitions", the table's `unit`, and `n`, the number of replication values they are over (a NaN value is left out, spec 2). An undefined `mean` or `half_width` is `null`, since JSON has no NaN.
- **Scenarios.** `scenarios` follows the experiment's scenario order. A scenario's `set` gives each parameter value in SI units: a `quantity` parameter as seconds.
- **Differences.** `differences` holds the paired scenario differences of spec 2 "Between scenarios": one entry for each pair of scenarios, in the experiment's order (the first with the second, the first with the third and so on, then the second with the third), written `{"scenario": <later id>, "against": <earlier id>, "metrics": {<metric>: {mean, half_width, unit, n, separated}}}`. Each difference is `scenario` minus `against`; `separated` is `true` when the interval excludes zero. With one scenario, `differences` is empty.
- **Warnings.** `warnings` holds issue objects: the warnings found when the model was loaded (W200 to W202; AKS-103, owner to confirm), then the adapter's `validate` warnings, then those `collect` returned, then the manager's W210.
- **Fidelity label.** "<fidelity, capitalised>: <replications> replications of <length>, <confidence × 100>% confidence". The length is written as a whole number in the largest Phase 1 time unit that gives one (`d`, `h`, `min`, `s`), and otherwise in seconds; `200 h` is "200 h" and `48 h` is "2 d". The percentage drops a trailing `.0` ("95%", "97.5%").
- **Optimization.** For an optimization run, `summary.json` is `model` (the model's name), then the adapter's `solution`, then `fidelity_label` (the fidelity capitalised, "Standard", since nothing is replicated) and `warnings`.

Job states and allowed moves: `queued` to `running`; `running` to `done`, `failed` or `cancelled`; `queued` to `cancelled`; and `queued` to `failed`, used only by E191 for a queued run whose process is gone (AKS-103, owner to confirm: the E191 rule above names queued runs, which no other move could fail). No other moves.

How the `local` target runs a run (AKS-103, proposed default, owner to confirm):

- **Before a run exists.** A run is started from the model file's bytes and, for a `process` model, an experiment id; an `optimization` model has no experiments and is started without one (spec 3 `POST .../runs`; AKS-108, owner to confirm). An experiment id the model does not have, an id given for an optimization model, or none for a process model is refused before anything is created (the service answers 400 from M6). The file is loaded; then a `run.target` other than `local` is E172 at `/run/target`; then the adapter is chosen (E102); then the adapter's `validate` and the fidelity check (E173) run. Any error refuses the run: no `run_id` is issued and no folder is created. Otherwise `runs/<run_id>/` is created in state `queued` with `model.json`, `manifest.json`, `log.txt` and an empty `engine/`. The `runs/` folder is given by the caller (the project folder's `runs/` from M6).
- **`run_id`.** The time is `created`, in UTC. The six characters are RFC 4648 base32 (`A` to `Z`, `2` to `7`) from the operating system's generator (Python's `secrets`); they are an identifier, not simulation randomness, so the stream scheme does not apply. A clash with an existing folder draws again.
- **`model.json`** is the file's bytes exactly as given, not a re-serialised model, so a repeat started from the same file is byte-equal. A seed the file leaves out is chosen at load and recorded in the manifest's `seed` only.
- **Where the methods run.** `validate`, `translate` and `collect` run in the process that drives the run (the service's worker from M6; the caller before then). `run` runs in a worker process started with the `spawn` method, never `fork`; the worker creates the adapter's class with no arguments, and is not a daemon, so an adapter may start its own processes. The worker stops by itself, its token reading as set, if the process driving it ends.
- **Manifest values.** `project_id` is `null` and `client` is `script` when a run is started outside the service; the service sets `project_id` to the project's id and `client` to the request's `X-Client` (`script` when absent) (AKS-112); `target` is `local`, the file's `run.target` or the `target` of `POST .../runs`, which overrides it (spec 3; a `target` other than `local` there is E172 at `/target`, the request field, AKS-112, owner to confirm); `host` is the machine's host name; `started` and `ended` are `null` until reached; times are ISO 8601 UTC to the millisecond, ending in `Z`. An optimization run has no experiment and draws no random numbers, so its `experiment_id` and `seed` are `null` and its `scenario_ids` is empty; it writes no tables, so its run folder has no `tables/` (AKS-108, owner to confirm). `fraction` is the run's progress from 0 to 1: 0 when queued, then each `Progress.fraction` the adapter reports, 1 at `done`; a cancelled or failed run keeps its last value. The progress `message` is not written to the manifest. `error` is present only on a failed run. The manifest is written through a temporary file in the run folder and `os.replace`.
- **Cancel** sets the `multiprocessing.Event`. A queued run moves to `cancelled` at once and never starts. A running worker that has not stopped 5 s after the first cancel is terminated; cancelling again does not move that deadline. A run whose token was set ends `cancelled`, and no `summary.json` or `tables/` is written, even when the cancel arrives while `collect` runs: the move to `done` and the cancel are taken in turn, so an accepted cancel is never lost.
- **E190.** An exception from `translate`, `run` or `collect`, a worker process that cannot be started, a worker that ends without reporting, or an exception in the process driving the run while it is `running` (such as the service's own progress or state handling; AKS-112, owner to confirm), fails the run with E190 (`component` `null`, `path` `""`). The traceback, or the worker's exit status, goes to `log.txt`; the issue's message names the engine and never holds exception text.
- **E191.** The process driving a run holds an exclusive lock on `worker.lock` in the run folder from creation until the run reaches a final state, then removes the file (`fcntl.flock` on Linux and macOS, `msvcrt.locking` on Windows; the operating system releases the lock when the process ends, whatever the platform). On start, the service tries that lock for each run whose manifest says `queued` or `running`; when the lock can be taken, or the file is gone, the worker is not alive and the run is failed with E191.
- **E192.** The time limit (default 10 min, spec 4 "Limits") counts from `started` and is checked every 0.1 s while the worker runs. The memory limit (default half of the machine's physical memory) is compared once a second with the resident memory of the worker and every process it started, read from `/proc`; where `/proc` or the machine's memory size cannot be read (Windows, macOS), the memory limit is not enforced and `log.txt` says so. On either, the token is set, the worker has 2 s to stop and is then terminated, and the run is failed with E192.
- **Watching and stopping the worker.** The worker is watched until its process has ended, not only until its report pipe closes, since its interpreter may still wait for threads or processes it started; the limits and the cancel deadline apply throughout. Terminating is `Process.terminate()` (SIGTERM on Linux and macOS, which a worker can ignore), then `Process.kill()` if the worker has not ended 2 s later. A worker that is terminated is ended together with every process it started, found through `/proc` before it is terminated; on Windows and macOS only the worker itself is ended, and its own processes must notice that it has gone.
- **Search.** A search run (AKS-109, owner to confirm) runs every candidate evaluation as above: `translate` and `collect` in the driving process, `run` in a spawned worker of its own, each in its subfolder of `engine/` ("Division of labour"). Progress is each evaluation's fraction weighted by its replications against the planned total, never falling, and below 1 until `done`. A cancel stops the evaluation that is running and starts no other; the time limit counts from `started` over the whole search. An exception or a failed worker in any evaluation fails the run with E190 (or E192), and `log.txt` names the evaluation's folder.
- **Finishing order** (CI on PR #36, owner to confirm). A run finishes on disk in one order: `tables/` and `summary.json` (for `done`), then the manifest with the final state, then `worker.lock` removed; E191 depends on the manifest turning final before the lock goes. The service makes a final state visible (spec 3: the run endpoints, the run's events, the project's events) only after that and after the run's place in the run queue is free; until then its run endpoints show the run as it last published it, though the manifest already says final.
- **Files.** The manager's own files are `model.json`, `manifest.json`, `summary.json`, `tables/`, `log.txt` and, while the run is unfinished, `worker.lock`; every file an adapter writes is inside `engine/`.

#### Tables for the `process` domain

- `replications`: columns `scenario` (string), `replication` (int from 0), `metric` (string), `value` (float64), `unit` (string: SI symbol or `1`). The unit is `s` for a time (`wait.mean`, `cycle_time.mean`), `1/s` for a rate (`throughput`, `orders`, `discarded`; see "Metric names") and `1` for counts, fractions and numbers of items. Rows follow the experiment's scenario order, then replication, then the model's component order with each component's metrics in spec 2 order, and `model.wip.mean` last. A mean over no items (a `wait.mean` when no service started after warm-up, a `cycle_time.mean` when no item reached the sink after warm-up) is undefined: its row is written with `value` NaN, so every replication has the same rows. Proposed default (AKS-98), owner to confirm.
- `timeseries`: columns `scenario`, `replication`, `metric`, `time_s` (float64 from run start), `value`, `unit`; time-persistent statistics sampled every `record_interval`. The metrics and sample times are those of spec 2 "Statistic definitions" (`<server>.queue_length`, `<server>.utilization`, `<queue>.queue_length`, `<store>.stock`, `<pool>.utilization`, `model.wip`, from 0 s to before the end); `value` is float64 and `unit` is `1`. Rows follow the experiment's scenario order, then replication, then metric (the model's component order with each server's `queue_length` before its `utilization`, and `model.wip` last), then time. Proposed default (AKS-99; the queue's series AKS-105, the store's AKS-106, the pool's AKS-107), owner to confirm.

Units are a column, not Parquet metadata; `summary.json` repeats them per metric. `GET .../tables/{name}` accepts only these names.

#### Identical runs

Identical means: `summary.json` metrics equal to full floating-point precision, every table under `tables/` equal row for row, and `model.json` byte-equal. `manifest.json` may differ only in `run_id`, `created`, `started`, `ended`, `host`. The comparison is made on the same machine, Python and library versions. Tables are compared as tables, not as file bytes: the same columns with the same types, and the same rows in the same order, each float equal to the last bit; a NaN cell (a mean over no items) equals a NaN cell in the same place. The results do not depend on `workers` or on which process runs a replication. Proposed default (AKS-104), owner to confirm.

## Research before building

Complete these and record the findings, with sources, in a short note in the repository before writing code. If a finding contradicts this spec, update the spec first.

- **M1 · Existing model formats.** What can be borrowed from System Structure and Parameterization, the FMI model description, Modelica, SysML v2 and the DEVS formalism?
- **M1 · How existing tools save models.** JaamSim configuration files, CalculiX input files, OpenModelica.
- **M1 · Schema and units.** Current JSON Schema version and tooling; unit-handling libraries and their limits.
- **M2 · Plugin mechanisms.** How mature Python projects discover and load plugins.
- **M11 · Cluster submission.** Libraries for SSH and Slurm job handling from Python.

## Acceptance tests

| Test | Milestone | Checked by | Evidence |
| --- | --- | --- | --- |
| The three example models in `examples/` load with zero issues | M1 | agent | `tests/model/test_examples.py` |
| One deliberately broken file per issue code with Pass `schema` or `meaning`, in `tests/model/fixtures/issues/<code>_<slug>.json`, yields that code as its only issue of that severity, with `path` filled and `component` filled where the code concerns a component; every `message` names the component id or key concerned and contains no exception text | M1 | agent | `tests/model/test_issues.py` |
| Every distribution passes the sampling test | M2 | agent | `tests/model/test_distributions.py` |
| A dummy adapter passes through all five methods on the local target | M3 | agent | `tests/runs/test_dummy_adapter.py` |
| The same on remote and cluster, markers `remote` and `cluster`, against a local sshd and a local Slurm test queue or stub scheduler | M11 | agent |  |
| A repeated run is identical as defined above | M3 | agent | `tests/runs/test_repeat.py` |
| Two separately started worker processes produce `replications` tables equal row for row for the same model and seed | M3 | agent | `tests/runs/test_cross_process.py` |
| A test-only migration rewrites a 0.1 file to a test version and back; the first real format change replaces it with the real migration and a 0.1 fixture that must still open | M1 | agent | `tests/model/test_migration.py` |

## Changes in this version

2026-11-05, version 0.3, spec review council:

- C1 (SIM-1, ARCH-20, TEST-4, SIM-8): random stream key and generator named; "identical run" defined.
- C2 (ARCH-1, ARCH-16, ARCH-17, ARCH-18): top-level keys split by domain; `variables`, `objective`, `run.engine`; fidelity `standard` only in Phase 1; `MAJOR.MINOR` versioning rule.
- C3 (ARCH-2, ARCH-12, SIM-11, SIM-16, SIM-7, TEST-7): `default` scenario, `confidence`, `record_interval`, `search` in experiments; `summary.json` keyed by scenario with `fidelity_label`.
- C4 (SIM-15, TEST-16, ARCH-14, PRD-12): distribution parameterisations, `empirical` `data` reference, `data/` in the run folder, the M2 sampling test.
- C5 (ARCH-10, SIM-13, ARCH-11): branch ports from `routes`; reserved identifiers; metrics limited to spec 2 definitions; attributes and priority deferred to Phase 2.
- C6 (TEST-3, ARCH-10, SIM-12, SIM-15, SIM-17, ARCH-2, ARCH-4, ARCH-5, ARCH-8, ARCH-13, ARCH-14, ARCH-16, ARCH-18, TEST-11, PRD-12): schema pass scope, W201 propagation, issue codes allocated to passes.
- C7 (ARCH-3, ARCH-4, ARCH-16, ARCH-19, PHY-2): adapter signatures, `CancelToken`, `workers`, discovery by entry points, engine licence rule, division of labour.
- C8 (ARCH-4, TEST-11, PRD-3): where each adapter method runs per target; remote and cluster before M11.
- C9 (ARCH-5, ARCH-6, ARCH-11, SIM-11, PRD-12, ARCH-7): `run_id`, manifest fields, `replications` and `timeseries` tables.
- C10 (TEST-1, TEST-3, TEST-11, TEST-12, PRD-1, TEST-2, PRD-15, TEST-13): version line, prototype status, research items tagged, acceptance table.
- Verifier follow-up: a new minor version needs no migration; E172 refuses a run before it is created; `run_id` lookup goes through `projects.json`; meaning-pass codes listed exactly.

2026-11-06, version 0.4, M1 closed (AKS-94); the lines below were added after version 0.3, during the review of PR #1 and the M1 build:

- 2026-11-06, review of PR #1: the adapter contract scopes "per-replication values only" to process adapters; optimization adapters return `Results.solution` (status, objective, variables, constraints), which the manager writes to `summary.json`.
- 2026-11-06, review of PR #1: an `empirical` `data` snapshot is named `data/<component id>.<setting>.parquet`, so a component with two data-driven distributions (such as a `failure` block) keeps both; the manifest records file, column and hash per reference. The duplicate `Results(...)` signature left by the previous change is removed.
- 2026-11-06, review of PR #1: W201 rate propagation stops at loss points (a discarding `queue`, or a source feeding a finite-capacity block), so a stable server downstream of a loss system is not flagged.
- 2026-11-06, M1 research notes (AKS-85): "Units" confirms pint (was "Proposed library"), declared as `pint>=0.25.3` because pint 0.26 needs Python 3.12, with the grammar checked before pint converts (`docs/research/spec-1-schema-and-units.md`); "Validation" names JSON Schema draft 2020-12, the `jsonschema` package and no `format` keyword; "Quantities" states the exact grammar for the number, the single space and the unit symbol, and which strings are E140 and which E141.
- 2026-11-06, units and quantities (AKS-86): "Quantities" adds what the grammar left open, found while building `src/lcsim/model/units.py`: a unit name with several readings is E140 only when no reading has the expected dimension; a number that is not finite in SI units is E141; `"-0 s"` is stored as 0.0; where a plain number is expected, any value other than a finite JSON number is E123; where a quantity is expected, `true`, `false`, `null`, an array or a non-`$param` object is E141.
- 2026-11-06, issue objects and the schema pass (AKS-87), found while building `src/lcsim/model/schema.json` and `schema.py`: "Validation" says quantities, plain numbers and enumerated words take any JSON value in the schema (it said "plain strings or objects", which would have made `"length": true` E100 instead of the E141 that "Quantities" requires, and `run.target` E100 instead of E172); "Top-level keys" says what the schema pass checks for an unknown `domain`, that `run` needs `target` and `fidelity` when present, and that only a component has `ui`; "Parameters" makes `type` required (spec 3 already rejects a new parameter without `value` and `type`); "Experiments" makes both keys of a scenario and `search.objective` required; "Versioning" says which strings are E101, that a non-string is E100, and that E101 stops the schema pass; "Validation issues" defines `severity`, `path` and `component`.
- 2026-11-06, model loading (AKS-88), found while building `src/lcsim/model/loading.py`, `model.py` and `catalogue.py`: "Validation" says how the file is read before the schema pass (UTF-8 with an optional BOM; non-JSON text, `NaN`, `Infinity`, over-long whole numbers, too-deep nesting and duplicate keys are E100) and that loading reports values it cannot convert; "Parameters" says how `value`, `min`, `max` and scenario values follow the parameter's `type` (a `quantity` parameter is a time in Phase 1; `2.0` is a whole number) and that `$param` also works inside distribution fields and object settings; "Components and ports" names a branch's output ports by their routes and says how a connection end is split; "Experiments" says the missing `seed` is chosen at load, from 0 to 2⁶³ − 1, and that an empty `scenarios` array also gets the `default` scenario; "Metric names" lists the `sense` and `op` words and the kinds of a constraint's `value`; the E123 and E160 rows of "Validation issues" name the further cases loading reports with them.
- 2026-11-06, meaning pass A (AKS-89), found while building `src/lcsim/model/validation.py`: "Identifiers" lists every id the pattern and uniqueness apply to (objectives, constraints, variables and a branch's routes added; scenarios unique within one experiment); "Top-level keys" says how `run.engine` chooses an adapter, where E102 points, and that until an adapter exists the model layer stands in for it without a name, so `run.engine` is not checked before then; "Components and ports" says which end is E130 and which E161, and where E131 and E132 point; the E121 and E122 rows of "Validation issues" cover a branch's `weights` keys against its `routes`.
- 2026-11-06, meaning pass B (AKS-90), found while building the value checks of `src/lcsim/model/validation.py` and the data index `src/lcsim/model/data.py`: "Parameters" says where E150, E151 and E152 apply, which parameter types fit which places, and that a setting fed by a parameter is checked for its `value`, `min`, `max`, scenario values and, with several parameters, every combination of their bounds (added after review of PR #9); "Distributions" lists the fields that must agree (adding a triangular `mode` outside `min` to `max`, and allowing `min` equal to `max`) and how a `data` reference is checked against the column index, which is empty until M6; "Experiments" lists every E170 case (adding `length`, a negative `warmup`, `record_interval` and the search's `budget` and `replications`), adds a search with no variables to E171 and a search variable that is not a parameter to E150; "Metric names" says which metrics are times and which rates, that a rate constraint is a plain number per second (owner to confirm), and that a wrong kind of `value` is E123; the E123, E150, E151, E160, E162, E170 and E171 rows of "Validation issues" follow.
- 2026-11-06, warnings W200 to W202 (AKS-91), found while building them in `src/lcsim/model/validation.py`: "Validation" details the W201 propagation (a source's rate with `max_items`, which blocks have a finite capacity, that a schedule or failure stops the rate at the server it changes and skips that server, how an unbatch undoes one level of batching, that loops and values that cannot be read stop the rate, that an unreached block has rate zero, which connections carry items, the clipped mean of a `normal`, exact comparison) and says that W201 and W202 are checked at each parameter's `value` and each scenario's value, not at `min` and `max`; "Parameters" says its bounds rule is for errors; the W200 row says which connections count.
- 2026-11-06, format versioning and the test-only migration (AKS-92), found while building `src/lcsim/model/migration.py`: "Versioning" says how a migration is registered and chained, that a newer minor of the reader's major is never migrated, that a file of a major with a migration is still E101 when loaded (with a hint that it can be converted) because the model layer never migrates on its own, that the caller asks the user before the rewritten file is saved, and that format 0 ships no migration.

2026-11-06, version 0.5, M2 closed (AKS-101); the lines below were added after version 0.4, during the M2 research notes and the M2 build:

- 2026-11-06, M2 research note `docs/research/spec-1-plugin-mechanisms.md`: entry points in `lcsim.engines` confirmed; the entry-point name is the adapter name, a plugin that fails to import is left out and logged, duplicate names are left out (E102 if no single engine remains), and the group is renamed with the placeholder package. pyarrow's Apache-2.0 licence confirmed from the wheel's `LICENSE.txt`.
- 2026-11-06, random streams and distribution sampling (AKS-96), a rule-5 reading of M1 owner item 9: "Distributions" says every sampled time below 0 s is set to 0 s for every distribution, not only the `normal`, with no new issue code (owner to confirm); that W201 keeps the written mean except for the `normal`; and that an `empirical` with `data` cannot be sampled until M6, which raises a condition with code E162.
- 2026-11-06, engine adapter interface and discovery (AKS-97), found while building `src/lcsim/engines/adapter.py`, `registry.py` and the process adapter's `capabilities()`: "Engine adapter interface" names the fields of `Capabilities` (`hardware` as a list of words, empty for none, was left open; owner to confirm); "Engine contract" says the guard also covers creating the class and calling `capabilities()`, that an entry point whose class `name` differs from its entry-point name is left out and logged (the spec required them equal but did not say what happens otherwise; owner to confirm), that duplicate names are left out without importing either, that adapters are discovered once per process, and that the product's process adapter is named `simpy` with the product version (owner to confirm); "Top-level keys" says `run.engine` is checked for `process` from M2 and the `optimization` stand-in applies only while no installed adapter handles that domain.
- 2026-11-06, SimPy adapter core (AKS-98), found while building `src/lcsim/engines/process/`: "Random streams" says a component draws all its samples from its one stream in event order, and when a source and a server draw (owner to confirm); "Tables for the `process` domain" names the `unit` of times (`s`), rates (`1/s`) and the rest (`1`), fixes the row order, and writes a mean over no items as NaN (owner to confirm); "Division of labour" describes the process adapter's `engine/input.json` (no `ui`, `label` or `meta`), its worker processes, and `engine/output/replications.parquet` (owner to confirm).
- 2026-11-06, SimPy adapter delay, branch, blocking and time series (AKS-99), found while building the `timeseries` table: "Tables for the `process` domain" names the time-series metrics, their unit (`1`) and the row order, pointing to spec 2 for the sample times (owner to confirm); "Division of labour" adds `engine/output/timeseries.parquet` and says `collect` returns both tables.
- 2026-11-06, M2 close (AKS-101): the warning line says that `weibull` and `empirical` with `values` passed the sampling test at M2 (`tests/model/test_distributions.py`), closing that known gap of the Build guide; `empirical` with `data` still waits for M6.

2026-11-06, version 0.6, M3 closed (AKS-104); the lines below were added after version 0.5, during the M3 build:

- 2026-11-06, experiment manager (AKS-102), found while building `src/lcsim/runs/`: "Run folder and results" says how the manager fills `summary.json` for a process run, which the example left open: each metric adds `n`, the number of replication values its mean is over, and an undefined mean or half-width is `null`; `differences` holds the paired scenario differences, one entry per pair in scenario order with `scenario`, `against` and per-metric `separated`; a scenario's `set` is in SI units; the order of `warnings`; the wording of `fidelity_label`; and the layout for an optimization run (owner to confirm).
- 2026-11-06, local run target (AKS-103), found while building `src/lcsim/runs/targets.py`, `worker.py`, `manifest.py`, `states.py`, `ids.py`, `limits.py` and `lock.py`: "Run folder and results" adds how the `local` target runs a run: the checks made before a run exists, the `run_id` characters, `model.json` as the file's bytes, which process runs which method, the manifest's values (`fraction` as the progress, null `project_id`, `client` `script`), cancel, E190, how E191 knows a worker is gone (a lock on `worker.lock`), how E192 measures time and memory, and the manager's own files; the job states add `queued` to `failed` for E191 only; `summary.json` `warnings` start with the load-time warnings W200 to W202; "Run targets" defines what `python -m lcsim.runs.worker` reads, prints and returns (all owner to confirm).
- 2026-11-06, review of PR #24 (AKS-103): "How the `local` target runs a run" says that a cancel arriving while `collect` runs still ends the run `cancelled` without results, that the worker is watched until its process ends rather than until its pipe closes, and that a terminated worker's own processes are ended with it where `/proc` finds them, and that a worker still running 2 s after it is terminated is killed; the 5 s cancel grace counts from the first cancel; and a worker that cannot be started is E190 (owner to confirm).
- 2026-11-06, identical runs (AKS-104), found while writing `tests/runs/test_repeat.py` and `tests/runs/test_cross_process.py`: "Identical runs" says how tables are compared (as tables, not file bytes; floats to the last bit; a NaN cell equal to a NaN cell in the same place, since pyarrow's `Table.equals` treats NaN as unequal to itself) and that results do not depend on `workers` or on the process that runs a replication (owner to confirm); the acceptance table names the evidence for the two M3 reproducibility rows.

2026-11-07, version 0.7, M4 closed (AKS-107); the lines below were added after version 0.6, during the M4 build:

- 2026-11-07, `queue`, `batch` and `unbatch` blocks (AKS-105), found while building them in `src/lcsim/engines/process/blocks.py`: "Tables for the `process` domain" adds `<queue>.queue_length` to the `timeseries` metrics, in component order (owner to confirm). The W201 propagation of "Validation" (a batch divides by `size`, an unbatch multiplies by the size of what it receives, a discarding `queue` and a source feeding a `queue` or a server with `queue_capacity` stop the rate) is unchanged: with the blocks running, deterministic models in `tests/engines/process/test_flow_rates.py` pass exactly the rates it computes, and a loss point lets less through than it is offered.
- 2026-11-07, `store` block (AKS-106), found while building it in `src/lcsim/engines/process/blocks.py`: "Random streams" says a store draws each `lead_time` from its own stream when it places the order, and "Tables for the `process` domain" adds `<store>.stock` to the `timeseries` metrics, in component order (owner to confirm). The W201 rule of "Validation" (a store stops the rate, so every server downstream is skipped) is unchanged: `tests/engines/process/test_flow_rates.py` now runs a model where the source's rate would load the server below a store at 1.5, while the store's orders let through one item per lead time and the server keeps up.
- 2026-11-07, `resource_pool`, `schedule` and `failure` blocks (AKS-107), found while building them in `src/lcsim/engines/process/blocks.py`: "Random streams" says when a `failure` block draws (its first `time_to_failure` at time 0, a `time_to_repair` at each failure, the next `time_to_failure` at each repair) and that a `schedule` and a `resource_pool` draw nothing; "Tables for the `process` domain" adds `<pool>.utilization` to the `timeseries` metrics, in component order (owner to confirm). E124, E125 and the W201 rule of "Validation" (a schedule or failure stops the rate at the server whose capacity it changes, and a schedule on a pool at every server of that pool, none of them checked) are unchanged: `tests/engines/process/test_flow_rates.py` now runs a scheduled server whose nominal load is 2/3 but which passes 17 of 20 items, and a pooled server on a scheduled pool feeding a server with a failure.

2026-11-07, version 0.8, M5 closed (AKS-109); the lines below were added after version 0.7, during the M5 build:

- 2026-11-07, HiGHS adapter (AKS-108), found while building `src/lcsim/engines/optimize/` and replacing the optimization stand-in: "Top-level keys" and "Engine contract" say that from M5 both Phase 1 domains are checked against the discovered adapters, that the stand-in is gone, and that the product's optimization adapter is `highs` with the product version; "Validation issues" adds E175 for a coefficient that names no variable (the M1 leftover; spec 1 had no code), and "Validation" lists it among the meaning-pass codes; "Engine adapter interface" makes `translate`'s `experiment_id` `None` for an optimization model, which has no experiments, and gives the optimization adapter's `Capabilities`; "Division of labour" describes the optimization adapter's `engine/input.json`, `engine/output/solution.json` and cancel; "How the `local` target runs a run" says that an optimization model is started without an experiment id, that a missing or unwanted id is refused before a run exists, and that its manifest has `null` `experiment_id` and `seed`, no `scenario_ids` and no `tables/` (all owner to confirm).
- 2026-11-07, search validation (AKS-109; M1 leftover), found while building the search: "Experiments" and the E171 row of "Validation issues" add two cases: a parameter named twice in `search.variables` (at the repeat; the search varies each parameter once), and a `search` in an experiment that lists scenarios (at `scenarios`; a search runs its own candidates, and spec 2's result has one set of metrics per candidate). Both owner to confirm.
- 2026-11-07, simulation-based search (AKS-109), found while building `src/lcsim/runs/search.py` and running it through the manager and the local target: the warning line says scenarios run from M3 and objectives and constraints from M5; "Experiments" replaces "Proposed; verified at M5" with what was verified (a search run has the states, `run_id`, manifest and time limit of any run); "Random streams" says the search takes one draw from `<seed>:0:optimizer`; "Run folder and results" adds the manifest's `optimizer` (`{name, version}`: the search method and the Optuna version, which a repeat needs, research note decision 8) and says that a search run's `summary.json` and `tables/` are the best candidate's confirmation with `search`; "Division of labour" names the evaluation subfolders `search-<n>` and `confirm-<n>`; "How the `local` target runs a run" adds how a search runs there (all owner to confirm).

### Since version 0.8

- 2026-11-07, service skeleton (AKS-110), found while building `src/lcsim/service/`: "Validation issues" adds the service codes E182 to E187 (token, hardening, malformed request, not found, project folder, internal failure), which spec 3 "Status codes and errors" puts in `error.code` and which had no spec 1 code; "Engine adapter interface" adds a one-sentence `description` to a component type's description, which `GET /v1/schema/components/{type}` serves and spec 3 names (owner to confirm).
- 2026-11-07, model endpoints (AKS-111), found while building the model edits of spec 3: the E186 row adds a project whose `model.json` is not JSON, or fails the schema pass when edits are sent (the file was changed outside the service), and the E180 row points to spec 3 "Model edits" for its cases (owner to confirm).
- 2026-11-07, review of PR #35 (AKS-111): the E186 row adds a `model.json` holding a number JSON cannot hold (`NaN`, `Infinity`, or `1e400`, which reads as an infinity) (owner to confirm).
- 2026-11-07, review of PR #35 (AKS-111), third round: the E186 row adds a `model.json` holding text that is not valid Unicode, which cannot be written back either (owner to confirm).
- 2026-11-07, run endpoints (AKS-112), found while building `src/lcsim/service/runs.py`, `src/lcsim/runs/queue.py` and `src/lcsim/runs/index.py`: "Validation issues" adds E188 for an action the run's state does not allow (spec 3's 409 for runs had no code); "Manifest values" says the service sets `project_id` and `client`, and that a request's `target` overrides `run.target` (E172 at `/target` when it is not `local`); "Run folder and results" says a service that stops with unfinished runs marks them E191 itself, that runs are recovered on start and when an opened project is first used, that a folder whose manifest cannot be read is not a run (`recover_interrupted` raised on one, so a service with such a folder in a project could not start), and that an exception in the process driving a running run fails it with E190 instead of leaving it `running` (owner to confirm).
- 2026-11-07, review of PR #36 (AKS-112): "Run folder and results" says a manifest is read by the service's strict reader, so one holding `NaN`, an infinity (`1e999`) or a lone surrogate is not a run (it made the run endpoints answer 500) (owner to confirm).
- 2026-11-07, review of PR #36 (AKS-112), third finding on numbers read from disk: "Run folder and results" gives the kinds and ranges a manifest's fields must have to be a run (`fraction` 0 to 1, `seed` `null` or 0 to 2⁶³ − 1, the timestamps and ids text or `null`) (owner to confirm).
- 2026-11-07, CI on PR #36 (AKS-112): "How the `local` target runs a run" adds the finishing order: tables and summary, the final manifest, `worker.lock` removed, and only then, with the run's queue place free, the final state made visible by the service (a test saw `done` with the lock still present) (owner to confirm).
