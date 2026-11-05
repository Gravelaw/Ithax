# Spec 1: Model Format and Engine Contract

> Version 0.3 · working copy in the repository (source of truth, owner to confirm) · changes are listed under "Changes in this version".

A model is one JSON file that passes a published schema. Every engine is a plugin that implements the same five functions. The interface, the engines and any AI assistant all work through these two contracts.

> **Warning: partly tested.** A prototype ran this format on three models. The `weibull` and `empirical` distributions, scenarios, objectives and constraints, and the remote and cluster run targets have never run. Verify each when its milestone arrives, and update this spec. See "Known gaps" in the Build guide.

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
- Proposed library: pint.

## Validation

Two passes, both run before any engine starts:

1. **Schema:** structure, types and required keys, checked against the JSON Schema.
2. **Meaning:** no dangling connections, no unknown component types, units of the right dimension, parameters within allowed ranges.

The JSON Schema checks only the top-level keys, the JSON type of each top-level value, and that every component, connection, parameter and experiment entry is an object with its required keys of the right JSON type. Identifiers, quantities and component settings are typed as plain strings or objects in the schema, with no patterns and no per-type required lists, so that the meaning-pass codes in the table below (E102, E110 to E171, E174, W200 to W202) are reported with their specific codes. Component type descriptions (settings, ports) come from the adapter's `Capabilities`; until the process adapter exists (M2) the model layer carries the `process` type catalogue from spec 2's block reference, and at M2 the adapter's `capabilities()` must equal it (tested). Flow rates for W201 are propagated from sources: a probability branch multiplies by weight/total, a batch divides by `size`, an unbatch multiplies by it, merges add; where a rate cannot be propagated (shortest-queue branches, stores, timeouts, schedules, failures) the check is skipped for every server downstream.

Errors name the component and the key, in plain language.

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

Proposed discovery mechanism, confirmed by the M2 research note: Python entry points in group `lcsim.engines`, each naming a class that implements `EngineAdapter`.

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

## Results

| File | Holds |
| --- | --- |
| `summary.json` | Key numbers, warnings, fidelity label |
| `manifest.json` | Engine name and version, random seeds, run target, timings |
| Tables | Time series and statistics, as Parquet |
| Fields | Spatial results for physics engines, as VTK-family files |

A run is reproducible from the run folder: the model, its manifest and any copied data.

## Versioning

`format_version` is `MAJOR.MINOR` as a string. A minor increase is additive: a reader accepts any file with its own major and a minor no higher than its own, filling defaults in memory. A major increase ships a migration that rewrites the file after asking the user. E101 is raised for an unknown major or a minor above the reader's. Each new major version ships a migration that upgrades older files. The app never opens a file it cannot migrate without saying so.

## Detailed specification

The sections below are binding. Where they differ from the summary above, these win. The example above is one of three model files that a throwaway prototype ran successfully. The prototype script was not retained; the other two files are written fresh at M1 (proposed default, owner to confirm). This spec, not the prototype, defines the format.

### What the prototype changed

Running three example models against the first draft of the format forced four changes:

1. **Component settings are nested under `params`.** This keeps `id`, `type` and interface data apart from engine settings.
2. **Connections name ports.** A branch block has several outputs, so `["a", "b"]` pairs were not enough.
3. **Parameters are referenced with `{"$param": "name"}`.** Experiments and optimizers change the parameter, and every use follows.
4. **Experiments carry a `seed`.** Without it a run cannot be repeated.

### Identifiers

- Pattern: `^[a-z][a-z0-9_]{0,63}$`.
- Unique within their list: components, parameters, experiments, scenarios.
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
| `run` | object with `target`, `fidelity` and optional `engine` (adapter name) | no | `local`, `standard` |

Which keys are required, and the shape of `constraints`, depend on `domain`. A key that belongs to the other domain is an E100 error. Phase 1 process and optimization engines accept only `fidelity: standard`; the fidelity ladder of spec 6 applies to physics domains. Another value is E173. The service selects the one installed adapter whose capabilities include the model's `domain`; if there are several and `run.engine` is absent, or none, the issue is E102.

Unknown keys are an error, except under any `ui` key, which engines ignore.

### Quantities

- Grammar: a number, one space, a unit. Example: `"1.5 min"`.
- Phase 1 time units: `s`, `min`, `h`, `d`. Internal time is seconds, as a float.
- Counts, probabilities and capacities are plain JSON numbers with no unit.
- A quantity where a plain number is expected, or the reverse, is an error.

### Parameters

Each entry has `value` (required), `type` (`integer`, `number` or `quantity`), and optional `min`, `max`, `description`. A `{"$param": "id"}` object may appear anywhere a component setting takes a number or quantity.

### Components and ports

Each component has `id`, `type`, `params`, and optional `label` and `ui`. The `ui` object holds canvas position and is never read by an engine.

- Each component type declares its ports. Most have `in` and `out`; a source has only `out`; a sink has only `in`; a branch has one output port per entry of its `routes` setting.
- A connection is `{"from": "<id>.<port>", "to": "<id>.<port>"}`.
- Every output port connects to exactly one input port. An input port accepts any number of connections.

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
| `empirical` | `values` (array of plain numbers or quantities of one dimension, inline) or `data` = `{"file": "<name in data/>", "column": "<column>"}` | Sampled with equal probability and replacement. With `data`, values are read as numbers or as quantities per the column index's declared unit; the run copies the column to `runs/<run_id>/data/<component id>.parquet` (never under `tables/`, which holds only the tables listed in "Run folder and results") and the manifest records the file name and SHA-256; a missing or changed file is E162. Not exercised by the prototype; `data` arrives with the import endpoint at M6 |

Sampling test (M2, every distribution): 20,000 samples from one stream; the sample mean lies within four standard errors of the theoretical mean, standard error = theoretical standard deviation / √20000. Theoretical mean and sd: constant: value, 0 (so the samples must equal the value exactly); exponential: mean, mean; uniform: (min+max)/2, (max−min)/√12; triangular: (min+mode+max)/3, √((a²+b²+c²−ab−ac−bc)/18); normal: tested with mean ≥ 5 sd so clipping is negligible, plus an assertion that no sample is negative; lognormal: the given mean and sd; weibull: scale·Γ(1+1/shape), variance scale²·[Γ(1+2/shape) − Γ(1+1/shape)²]; empirical: mean and population sd of `values`.

### Experiments

| Field | Type | Default |
| --- | --- | --- |
| `id` | identifier | required |
| `length` | time quantity | required |
| `warmup` | time quantity, less than `length` | `0 s` |
| `replications` | integer, at least 2 | 30 |
| `seed` | integer | chosen at random and recorded in the manifest |
| `scenarios` | array of `{id, set: {parameter id: value}}` | one scenario with the reserved id `default` and an empty `set`; a user scenario may not use that id (E112) |
| `confidence` | number in (0, 1) | 0.95 |
| `record_interval` | time quantity | `length` / 200 |
| `search` | object `{objective, budget, variables, replications}` | absent: a plain experiment |

`search.objective` names an id in top-level `objectives` (exactly one in Phase 1); `search.budget` is an integer at least 1, default 50; `search.variables` is an array of parameter ids, default every parameter with both `min` and `max`; `search.replications` (integer at least 2, default 10) is the replications per candidate during the search, while the experiment's own `replications` is used for the confirmation stage of spec 2. E171 covers a `search` that names an unknown objective or a parameter without `min` and `max`. Running an experiment that has `search` runs the simulation-based search of spec 2; the run id, states and events are those of any run. Proposed; verified at M5.

### Random streams

Each component gets its own random stream in each replication. The stream key is the UTF-8 string `<seed>:<replication>:<component id>` (replication numbered from 0). Its SHA-256 digest, read as a big-endian integer, seeds `numpy.random.SeedSequence`, which seeds a PCG64 `numpy.random.Generator`. Python's built-in `hash()` is salted per process and must never be used. Scenario and search candidate do not enter the key, so every scenario of an experiment and every candidate of a search faces the same random events (common random numbers). The generator name and the numpy version are written to `manifest.json`; a repeat is promised only on the same versions. Adding or removing one component therefore leaves every other component's random numbers unchanged. The prototype used this scheme and gave identical results on repeat runs.

### Metric names

`<component id>.<measure>` with an optional `.<statistic>`, for example `till.wait.mean` or `exit.throughput`. Objectives and constraints refer to metrics by these names:

```json
{"objectives": [{"id": "cost", "metric": "till.wait.mean", "sense": "minimize"}],
 "constraints": [{"id": "util", "metric": "till.utilization", "op": "<=", "value": 0.85}]}
```

Metrics whose names are defined in spec 2 "Statistic definitions" are the only ones objectives and constraints may name; naming any other is E174. Item attributes, the `attribute` branch rule and priority queue disciplines are deferred to Phase 2 until a block that sets attributes exists (proposed default, owner to confirm; recorded in the Build guide known gaps).

### Validation issues

Every issue is one object:

```json
{"code": "E131", "severity": "error", "component": "till",
 "path": "/components/1",
 "message": "The 'out' port of 'till' is not connected to anything.",
 "hint": "Connect it to another block or to a sink."}
```

`severity` is `error` or `warning`.

| Code | Pass | Meaning |
| --- | --- | --- |
| E100 | schema | File does not match the schema: wrong JSON type, missing required key, or an unknown key at top level or in a component, connection, parameter or experiment, including a key that belongs to the other `domain` |
| E101 | schema | Unsupported `format_version` |
| E102 | meaning | No single engine for this `domain` |
| E110 | meaning | Duplicate identifier |
| E111 | meaning | Identifier does not match the pattern |
| E112 | meaning | Reserved identifier used (`model` or `optimizer` as a component id, `default` as a scenario id) |
| E120 | meaning | Unknown component type |
| E121 | meaning | Unknown setting for this component type (an unknown key inside `params`) |
| E122 | meaning | Required setting missing |
| E123 | meaning | Setting has a quantity where a number is expected, or the reverse |
| E124 | meaning | Setting names an unknown component or one of the wrong type (`pool`, `target`) |
| E125 | meaning | A server or pool is the target of more than one `schedule`, or a server of more than one `failure` |
| E130 | meaning | Connection names an unknown component or port |
| E131 | meaning | Output port not connected |
| E132 | meaning | Output port connected more than once |
| E140 | meaning | Quantity has the wrong kind of unit |
| E141 | meaning | Quantity cannot be parsed |
| E150 | meaning | Reference to an unknown parameter |
| E151 | meaning | Parameter value outside its `min` and `max` |
| E152 | meaning | Parameter type does not fit the setting that references it |
| E160 | meaning | Distribution fields inconsistent: `min` above `max`; `sd`, `shape`, `scale` or the `mean` of a positive distribution not greater than zero; empty `values` |
| E161 | meaning | Connection names a branch route that is not in `routes` |
| E162 | meaning | Data reference names a file or column not in the project's `data/` folder, or the file's hash has changed |
| E170 | meaning | Experiment invalid, such as `warmup` not less than `length` or `confidence` outside (0, 1) |
| E171 | meaning | `search` names an unknown objective or a parameter without `min` and `max` |
| E172 | run | Run target not available on this build, not configured, or not reachable |
| E173 | run | Fidelity not offered by this engine |
| E174 | meaning | Objective or constraint names a metric that does not exist: an unknown component, or a measure or statistic that spec 2 does not define for that component's type |
| E180 | service | Edit cannot be applied |
| E181 | service | Model changed since the stated revision |
| E190 | run | Engine exited with an error (details in `log.txt`) |
| E191 | run | Run interrupted by a service restart |
| E192 | run | Run exceeded its time or memory limit |
| W200 | meaning | Component with an `in` port cannot be reached from any source |
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
    def translate(self, model: Model, experiment_id: str, workdir: Path) -> None: ...
    def run(self, workdir: Path,
            on_progress: Callable[[Progress], None],
            cancel: CancelToken,
            workers: int) -> None: ...
    def collect(self, workdir: Path) -> Results: ...
```

- `Capabilities` lists domains, component types with their settings and ports, and parallel modes.
- `Progress` has `fraction` (0 to 1), `message`, and optional live `metrics`.
- `run` checks `cancel` at least once a second and stops cleanly when it is set.
- `CancelToken` is supplied by the run target, never by the adapter. `local`: a `multiprocessing.Event`. `remote` and `cluster`: a file named `CANCEL` in `workdir`, created over SSH or alongside `scancel`.
- An adapter never writes outside `workdir`.

#### Division of labour

`workdir` is `runs/<run_id>/engine/`; the manager owns everything else in the run folder. `translate`, `run` and `collect` are called once per run; a search run (spec 2) calls them once per candidate evaluation, each in its own subfolder of `engine/`. The adapter runs every scenario and replication inside `run`, using at most `workers` processes; it must honour `warmup`. `Results(tables: dict[str, Table], warnings: list[Issue])` where `Table` is a pyarrow Arrow table (pyarrow, Apache-2.0 per PyPI metadata read on 2026-11-05; confirmed by the M2 research note, since the first adapter needs it at M2). The adapter reports per-replication values and sampled time series only, in the `replications` and `timeseries` table layouts of "Run folder and results". The manager computes means, half-widths and paired scenario differences, writes `tables/*.parquet`, `summary.json` and `manifest.json`. `Capabilities.parallel_modes` is drawn from `replications`, `threads`, `processes`, `gpu`; an adapter listing `replications` runs them in parallel up to `workers`.

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

`manifest.json` fields: `run_id`, `project_id`, `experiment_id`, `scenario_ids`, `state`, `created`, `started`, `ended` (ISO 8601 UTC), `target`, `host`, `client` (`ui`, `mcp` or `script`), `engine` `{name, version}`, `generator` `{name, numpy_version}`, `product_version`, `format_version`, `seed`, `fraction`, `data_files` (array of `{file, sha256}`), optional `error`. `manifest.json` is rewritten atomically (temp file and rename) on every state change and at most once a second on progress. It is the source of truth; `index.sqlite` is a cache. `error` is an issue object with E190, E191 or E192 (E172 never reaches a manifest: the run is refused before it is created). On start the service marks every run whose manifest says `queued` or `running` and whose worker is not alive as `failed` with E191.

Results are stored in SI units with the unit named. The interface chooses display units. A `summary.json` for the coffee shop run:

```json
{"model": "Coffee shop", "experiment": "base", "fidelity": "standard",
 "fidelity_label": "Standard: 30 replications of 200 h, 95% confidence",
 "replications": 30, "confidence": 0.95,
 "scenarios": {
   "default": {
     "set": {},
     "metrics": {
       "till.wait.mean":   {"mean": 273.3, "half_width": 13.0, "unit": "s"},
       "till.utilization": {"mean": 0.752, "half_width": 0.006, "unit": "1"}
     }
   }
 },
 "warnings": []}
```

`fidelity_label` is the text the interface shows (principle 4). A search run adds a `search` object, defined in spec 2.

Job states and allowed moves: `queued` to `running`; `running` to `done`, `failed` or `cancelled`; `queued` to `cancelled`. No other moves.

#### Tables for the `process` domain

- `replications`: columns `scenario` (string), `replication` (int from 0), `metric` (string), `value` (float64), `unit` (string: SI symbol or `1`).
- `timeseries`: columns `scenario`, `replication`, `metric`, `time_s` (float64 from run start), `value`, `unit`; time-persistent statistics sampled every `record_interval`.

Units are a column, not Parquet metadata; `summary.json` repeats them per metric. `GET .../tables/{name}` accepts only these names.

#### Identical runs

Identical means: `summary.json` metrics equal to full floating-point precision, every table under `tables/` equal row for row, and `model.json` byte-equal. `manifest.json` may differ only in `run_id`, `created`, `started`, `ended`, `host`. The comparison is made on the same machine, Python and library versions.

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
| Two separately started worker processes produce `replications` tables equal row for row for the same model and seed | M3 | agent |  |
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
