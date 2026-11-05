# Spec 1: Model Format and Engine Contract

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

Errors name the component and the key, in plain language.

## Engine contract

Each engine adapter is a Python class with five methods:

| Method | Does |
| --- | --- |
| `capabilities()` | Declares domains, component types, hardware needs and parallel modes |
| `validate(model)` | Engine-specific checks beyond the common ones |
| `translate(model, workdir)` | Writes the engine's own input files |
| `run(workdir, on_progress)` | Executes, reports progress, honours cancel |
| `collect(workdir)` | Reads engine output into the common results format |

Adapters are discovered as plugins, so a new engine needs no change to the core.

## Run targets

| Target | How |
| --- | --- |
| `local` | A process on this machine |
| `remote` | Another machine reached over SSH |
| `cluster` | A job submitted to a Slurm queue |

Job states are `queued`, `running`, `done`, `failed` and `cancelled`. The same model file and the same results format apply to all three targets.

## Results

| File | Holds |
| --- | --- |
| `summary.json` | Key numbers, warnings, fidelity label |
| `manifest.json` | Engine name and version, random seeds, run target, timings |
| Tables | Time series and statistics, as Parquet |
| Fields | Spatial results for physics engines, as VTK-family files |

A run is reproducible from the model file plus its manifest.

## Versioning

The format follows semantic versioning. Each new version ships a migration that upgrades older files. The app never opens a file it cannot migrate without saying so.

## Detailed specification

The sections below are binding. Where they differ from the summary above, these win. The example above is one of three model files that a throwaway prototype ran successfully. That prototype is a reference only and is deleted at the end of milestone M3; this spec, not the prototype, defines the format.

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

### Top-level keys

| Key | Type | Required | Default |
| --- | --- | --- | --- |
| `format_version` | string | yes |  |
| `meta` | object with `name` (required), `description`, `author`, `template` | yes |  |
| `domain` | string; Phase 1 values `process` and `optimization` | yes |  |
| `parameters` | object keyed by parameter id | no | empty |
| `components` | array of component objects | yes for `process` |  |
| `connections` | array of connection objects | yes for `process` |  |
| `experiments` | array of experiment objects | yes for `process` |  |
| `objectives`, `constraints` | arrays | no | empty |
| `run` | object with `target` and `fidelity` | no | `local`, `standard` |

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

- Each component type declares its ports. Most have `in` and `out`; a source has only `out`; a sink has only `in`; a branch has one output port per named route.
- A connection is `{"from": "<id>.<port>", "to": "<id>.<port>"}`.
- Every output port connects to exactly one input port. An input port accepts any number of connections.

### Distributions

| `dist` | Fields | Notes |
| --- | --- | --- |
| `constant` | `value` |  |
| `exponential` | `mean` |  |
| `uniform` | `min`, `max` |  |
| `triangular` | `min`, `mode`, `max` |  |
| `normal` | `mean`, `sd` | Negative samples are set to zero |
| `lognormal` | `mean`, `sd` | Mean and standard deviation of the variable itself, not of its logarithm |
| `weibull` | `shape`, `scale` | Not exercised by the prototype |
| `empirical` | `values`, or `data` naming an imported column | Not exercised by the prototype |

### Experiments

| Field | Type | Default |
| --- | --- | --- |
| `id` | identifier | required |
| `length` | time quantity | required |
| `warmup` | time quantity, less than `length` | `0 s` |
| `replications` | integer, at least 2 | 30 |
| `seed` | integer | chosen at random and recorded in the manifest |
| `scenarios` | array of `{id, set: {parameter id: value}}` | one unnamed scenario using the model's parameter values |

### Random streams

Each component gets its own random stream in each replication, derived from a hash of seed, replication number and component id. Adding or removing one component therefore leaves every other component's random numbers unchanged. The prototype used this scheme and gave identical results on repeat runs.

### Metric names

`<component id>.<measure>` with an optional `.<statistic>`, for example `till.wait.mean` or `exit.throughput`. Objectives and constraints refer to metrics by these names:

```json
{"objectives": [{"id": "cost", "metric": "till.wait.mean", "sense": "minimize"}],
 "constraints": [{"metric": "till.utilization", "op": "<=", "value": 0.85}]}
```

### Validation issues

Every issue is one object:

```json
{"code": "E131", "severity": "error", "component": "till",
 "path": "/components/1",
 "message": "The 'out' port of 'till' is not connected to anything.",
 "hint": "Connect it to another block or to a sink."}
```

| Code | Meaning |
| --- | --- |
| E100 | File does not match the schema |
| E101 | Unsupported `format_version` |
| E110 | Duplicate identifier |
| E111 | Identifier does not match the pattern |
| E120 | Unknown component type |
| E121 | Unknown setting for this component type |
| E122 | Required setting missing |
| E130 | Connection names an unknown component or port |
| E131 | Output port not connected |
| E132 | Output port connected more than once |
| E140 | Quantity has the wrong kind of unit |
| E141 | Quantity cannot be parsed |
| E150 | Reference to an unknown parameter |
| E151 | Parameter value outside its `min` and `max` |
| E160 | Distribution fields inconsistent, such as `min` above `max` |
| E170 | Experiment invalid, such as `warmup` not less than `length` |
| W200 | Component cannot be reached from any source |
| W201 | Arrivals meet or exceed capacity, so the queue will grow without limit |

Errors block a run. Warnings do not.

### Engine adapter interface

```python
class EngineAdapter(Protocol):
    name: str
    version: str

    def capabilities(self) -> Capabilities: ...
    def validate(self, model: Model) -> list[Issue]: ...
    def translate(self, model: Model, experiment_id: str, workdir: Path) -> None: ...
    def run(self, workdir: Path,
            on_progress: Callable[[Progress], None],
            cancel: threading.Event) -> None: ...
    def collect(self, workdir: Path) -> Results: ...
```

- `Capabilities` lists domains, component types with their settings and ports, and parallel modes.
- `Progress` has `fraction` (0 to 1), `message`, and optional live `metrics`.
- `run` checks `cancel` at least once a second and stops cleanly when it is set.
- An adapter never writes outside `workdir`.

### Run folder and results

```text
runs/<run_id>/
  model.json      the exact model that ran
  manifest.json   engine name and version, seed, target, start and end times, host
  summary.json    key numbers and warnings
  tables/         one Parquet file per table
  engine/         the engine's own input and output files
  log.txt
```

Results are stored in SI units with the unit named. The interface chooses display units. A `summary.json` from the prototype's coffee shop run:

```json
{"model": "Coffee shop", "experiment": "base", "fidelity": "standard",
 "replications": 30, "confidence": 0.95,
 "metrics": {
   "till.wait.mean":   {"mean": 273.3, "half_width": 13.0, "unit": "s"},
   "till.utilization": {"mean": 0.752, "half_width": 0.006, "unit": "1"}
 },
 "warnings": []}
```

Job states and allowed moves: `queued` to `running`; `running` to `done`, `failed` or `cancelled`; `queued` to `cancelled`. No other moves.

## Research before building

Complete these and record the findings, with sources, in a short note in the repository before writing code. If a finding contradicts this spec, update the spec first.

- **Existing model formats.** What can be borrowed from System Structure and Parameterization, the FMI model description, Modelica, SysML v2 and the DEVS formalism?
- **How existing tools save models.** JaamSim configuration files, CalculiX input files, OpenModelica.
- **Schema and units.** Current JSON Schema version and tooling; unit-handling libraries and their limits.
- **Plugin mechanisms.** How mature Python projects discover and load plugins.
- **Cluster submission.** Libraries for SSH and Slurm job handling from Python.

## Acceptance tests

- [ ] Three hand-built example models (coffee shop, three-machine line, small warehouse) are expressed in the format without workarounds.
- [ ] Twenty deliberately broken files each produce a clear, correct error.
- [ ] A dummy engine adapter passes through all five methods on all three run targets.
- [ ] A run repeated from model plus manifest gives identical results.
- [ ] A version 0.1 file opens after a format change through its migration.
