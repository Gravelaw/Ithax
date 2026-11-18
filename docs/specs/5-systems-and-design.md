# Spec 5: Systems and Design Optimization

> Version 0.3 · detailed from the spec 5 research session and its council (#104); the ten owner decisions' defaults applied on 2026-11-18 · working copy in the repository (source of truth) · changes are listed under "Changes in this version".

Phase 2 adds four more ways of modelling and one layer above all engines: design optimization. That layer is what later lets a user optimize a machine across several kinds of physics.

> **Warning: partly specified.** Version 0.3 is detailed from the research notes `docs/research/spec-5-*.md`, their trial runs (`docs/research/spec-5-trials/`) and the council's review (`docs/research/spec-5-council.md`). Each section says its state:
> - **Specified:** ready to build once its milestone starts.
> - **Proposed:** detailed, with the defaults the research supports, but waiting on a decision that comes back when its milestone starts (#234, item 6: where studies, surrogates and calculators live, and their routes). Do not build it until that decision is recorded.
> - **Open:** not yet detailed, because an engine has not run or a source has not been read.
>
> The ten owner decisions (Q1 to Q10, #231 to #240) were not answered by 2026-11-18, so each recommended default applies ("Owner decisions" below; `docs/DECISIONS.md`, 2026-11-18). Milestones follow the split of M23 in #240; the build guide's table is renumbered in its own change.
>
> Every engine here is wrapped, never written (guide rule 7).

## Scope

- **In:** agent-based models, system dynamics, physical system models, multibody dynamics, chaining models, design studies, surrogate models, people and workforce models, reliability and maintenance models.
- **Out:** anything needing 3D geometry and meshes (spec 6). Phase 3 (F3; #231, #237): stepping engines together (co-simulation), pedestrian dynamics, biomechanics, fatigue and skill matching, the multibody 3D preview, and contacts, conveyors and vehicles (Project Chrono considered then).

## New engine adapters

| Domain (`domain`) | Models | Engine | Invocation | Canvas style | State |
| --- | --- | --- | --- | --- | --- |
| `agent` | Populations of individuals following rules: customers, an epidemic | Mesa 3.5 (Apache-2.0); Python 3.12 or later, Ithax's floor from #232 | in-process | Populations and rules | Specified, well-mixed only |
| `system_dynamics` | Stocks, flows and feedback loops: cash, workforce, market adoption | PySD 3.14 (MIT) | in-process | Stock-and-flow diagram | Specified |
| `physical` | Connected components that obey physical laws: masses, springs, circuits, heat flow | OpenModelica 1.27 builds an FMI 2.0 Co-Simulation FMU (a separate process); FMPy 0.3 (BSD-2-Clause) runs it in the run worker | process and in-process | Component diagram with physical connectors | Specified (#228, #236, #277) |
| `multibody` | Rigid bodies and joints: linkages, pendulums | MuJoCo 4.0 (Apache-2.0), in place of Project Chrono (#231) | in-process | Bodies and joints; plots in Phase 2, the 3D preview with spec 6's viewer in Phase 3 | Specified (#231) |

Each adapter follows the spec 1 contract (`capabilities`, `validate`, `translate`, `run`, `collect`) with its five methods unchanged. A model holds data only: no adapter takes Python, Modelica or XML text from a model file, and each writes its engine's input inside `engine/`. In-process engines may be imported because their licences are recorded in `docs/DECISIONS.md` (spec 1 "Engine licence rule", F4).

**Names in an engine's input.** An adapter never writes a component id as an engine name. It writes `c_<id>` in the generated Modelica, XMILE or MJCF, and maps each name back to its id when it collects. A user's id therefore cannot collide with a name the engine gives a meaning: Modelica keywords (`der`, `end`, `model`, `connect`), XMILE built-ins, which XMILE matches without regard to case (`dt`, `starttime`, `stoptime`, function names), or MuJoCo's own body `world`. Each adapter's tests build a model whose ids are those words and check that it runs. Sources: `spec-5-mesa.md`, `spec-5-pysd.md`, `spec-5-fmpy.md`, `spec-5-openmodelica-fmu.md`, `spec-5-chrono.md`, `spec-5-mujoco.md`.

Additions the adapters need outside the five methods (Specified, #234 items 1 to 5; each additive, each landing with its milestone with a compat test):

- **The method in the label.** `Results` gains an optional `method` text (for example "Euler, step 1/64 d"), which the manager puts after the fidelity in the label: "Standard: Euler, step 1/64 d, 200 d". The length follows spec 1's rule ("200 d"); a step is written in the experiment's unit, as a fraction when the step is one.
- **Two engines in one domain.** `physical` reports FMPy in `Capabilities` (`BSD-2-Clause`, `in-process`), and lists OpenModelica, run as a separate process, in a new `build_tools` list (name, version, SPDX identifier or `LicenseRef-OSMC-PL-1.2`, `process`).
- **Catalogues per domain.** The model layer's catalogue keyed by domain, not only `process`; `BlockType` gains `metrics_from` (metrics that depend on a setting, such as a population's `states`), served additively by `GET /v1/schema/components/{type}`.
- **Projects.** `POST /v1/projects` accepts the new domains.

## Model file for the new domains

The next free minor format version after M19's and M20's (#234), additive: a file of an older version loads unchanged. Every rule of spec 1 holds unless this section says otherwise: identifiers, parameters and `$param`, quantities, unknown keys, `ui`, `run`.

| Key | `agent` | `system_dynamics` | `physical` | `multibody` |
| --- | --- | --- | --- | --- |
| `components` | required | required | required | required |
| `connections` | not allowed | not allowed (links follow from equations) | required, undirected | not allowed (joints name their bodies) |
| `experiments` | required | required | required | required |
| `time_unit` | not allowed | required: `s`, `min`, `h` or `d` | not allowed | not allowed |
| `objectives`, `constraints` | as `process` | as `process` | as `process` | as `process` |

**Experiments.**

- `length` as spec 1. Every check below is exact, on the written decimals and the units' sizes, never on floats.
- **Stepped domains** (`agent`, `system_dynamics`, `multibody`). `time_step`, a time quantity, is required. `length` must be a whole multiple of `time_step` (E407). `record_interval` must be a whole multiple of `time_step` and divide `length` (E401), so the last recorded sample is at `length`. When `record_interval` is absent it is k × `time_step`, where k is the smallest divisor of `length` / `time_step` with k × `time_step` ≥ `length` / 200.
- **`physical`.** `time_step` is not allowed (E100): CVODE inside the FMU chooses its own steps. `record_interval` is the FMU's communication step, the interval at which FMPy steps the FMU and records its outputs (`output_interval`). It must divide `length` (E401). When absent it is `length` / 200.
- Every time that bounds a run or its statistics lies on the recording grid, so no statistic needs a value between samples: `length` (E407), `record_interval` (E401) and, for agents, `warmup`, which must be a whole multiple of `record_interval` (E401).
- `agent`: `replications`, `seed`, `confidence` and `warmup` as spec 1. The warm-up check W210 is not applied to agent runs, whose populations are meant to change; `warmup` only starts the statistics.
- `system_dynamics`, `physical`, `multibody` are deterministic. `replications` and `warmup` are not allowed (E100); a run has one replication, numbered 0. `seed` stays allowed, and drawn when absent, because a study's sampler is seeded from it.
- `scenarios` work as in spec 1 in every domain. Spec 2's `search` stays process-only until a search without replications (so without a confirmation stage) is designed (#234).

**Parameters.** A `quantity` parameter may name a `unit` from this format version, so a rate (`1/d`) or a physical setting (`N/m`) can be a parameter that scenarios, studies and searches vary; a parameter without `unit` stays a time (spec 1). E152 covers a parameter whose unit's dimension does not fit the place that refers to it (#234).

**Physical units** (#234), converted to SI at load, spelled as the units library reads them: `kg`, `g`; `m`, `mm`; `N`, `N/m`, `N*s/m`, `N*m`, `N*m/rad`; `rad`, `deg`; `kg*m^2`; `m/s`, `m/s^2`; `V`, `A`, `ohm`, `F`, `H`; `K`, `W`, `J/K`, `W/K`. Temperatures are in `K` only: `degC` is an offset unit, which spec 1's exact scaling cannot express. A unit of the wrong dimension is E140.

**Issue codes.** E400 to E449 are the spec 5 model-layer codes; E300 to E399 stay engine-specific (spec 1).

| Code | Pass | Meaning |
| --- | --- | --- |
| E401 | meaning | `record_interval` does not divide `length`, or, in a stepped domain, is not a whole multiple of `time_step`; or an agent `warmup` is not a whole multiple of `record_interval` |
| E402 | meaning | A population's `initial` counts do not sum to its `count`, or name a state it lacks; a transition names a state its population lacks |
| E403 | meaning | An expression names something that is not a stock, flow, auxiliary or `$parameter` |
| E404 | meaning | An expression does not parse |
| E405 | meaning | A loop in what must be evaluated before it is known: flows and auxiliaries with no stock between, or stocks' `initial` expressions |
| E406 | meaning | A physical connection joins connectors of different kinds |
| E407 | meaning | In a stepped domain, `length` is not a whole multiple of `time_step` |
| E408 | meaning | Multibody joints do not form a tree from `world`: a body that is the `child` of no joint or of more than one, or a loop of joints |
| E410 | calculator | A block diagram does not reduce by series, parallel and k-out-of-n steps |
| E421 | meaning | Chained models form a cycle |
| E422 | meaning | A chain's member model is itself a chain, or a link names a model, metric, statistic or parameter its chain lacks |
| E430 | study | A surrogate's run budget is below the larger of 5 per input and 10 |
| E431 | load | A surrogate's refit does not reproduce its stored validation numbers to a relative 1e-9 |

### Statistic definitions (Specified for `agent` and `system_dynamics`)

Metric names follow spec 1: `<component id>.<measure>.<statistic>`.

| Domain | Measures | Unit | Kind |
| --- | --- | --- | --- |
| `agent` | `<population>.<state>`: agents in that state | `1` | number |
| `system_dynamics` | `<stock>.value`, `<flow>.value`, `<auxiliary>.value` | `1` (per `time_unit` for a flow) | number |

Statistics, each from `warmup` (0 when absent) to the end, over the values at every recorded sample, the end included:

| Statistic | Definition | Unit |
| --- | --- | --- |
| `final` | the value at `length` | the measure's |
| `max`, `min` | the largest and smallest recorded value | the measure's |
| `time_of_max` | the first recorded time at which `max` is reached, from the run's start | `s` |
| `mean` | the time average by the trapezoid rule over the recorded samples | the measure's |

The `timeseries` table holds each measure at every `record_interval` from 0 to `length` inclusive. Rows follow spec 1's order: scenario, replication, component order, then each component's measures in the order above. For an agent population the measures follow its `states`; `metrics_from` names `states`.

### Agent-based models (Specified, well-mixed)

| Type | Settings | Behaviour |
| --- | --- | --- |
| `population` | `count` (integer ≥ 1), `states` (array of identifiers, at least one), `initial` (object: state to integer, summing to `count`) | `count` agents, each in one state, mixing uniformly |
| `transition` | `population` (id), `from`, `to` (states of it), `rate` (rate quantity or `$param`), optional `contact` (a state of the same population) | Moves agents from `from` to `to` at hazard r = `rate`, or `rate` × (agents in `contact`) / `count` when `contact` is given |

- **One step.** The hazards are computed from the counts at the start of the step. Each agent in a state with transitions leaves it with probability 1 − exp(−H Δt), where H is the sum of the hazards out of that state (competing risks). If it leaves, it takes transition i with probability rᵢ / H. All moves apply together at the end of the step.
- **Randomness.** One Mesa model per replication, its generator from the stream key `<seed>:<replication>:@agents` (spec 1's scheme; `@agents` cannot be a component id, so it never collides with one). Draws are taken in component order of the populations, then in agent creation order, two per agent that can move: one for whether it leaves and one for which transition.
- **Python.** Mesa 3.5 needs Python 3.12 or later, so Ithax's minimum becomes 3.12 and 3.11 leaves the CI matrix (#232; applied to `pyproject.toml`, CI and `CLAUDE.md` in their own change).
- **Phase 3:** spaces (grid, continuous, network) and movement rules.

### System dynamics (Specified)

| Type | Settings | Behaviour |
| --- | --- | --- |
| `stock` | `initial` (expression) | A level, integrated from its flows; `initial` is evaluated once, before the first step |
| `flow` | `from`, `to` (stock ids, either may be `null` for outside the model), `rate` (expression, per `time_unit`) | Drains `from` and fills `to` |
| `auxiliary` | `equation` (expression) | A named value computed each step |

- **Expressions** (a string that Ithax parses itself, never with `eval`):
  - Operands: numbers in spec 1's JSON number grammar; the ids of stocks, flows and auxiliaries; parameters written `$id`; and `time`, in `time_unit` from 0. `time` and the function names are reserved identifiers (E112) in this domain.
  - Operators, loosest first: `+` and `-`; `*` and `/`; unary `-`; `^`, which binds to the right. Parentheses group.
  - Functions: `min(a, b)`, `max(a, b)`, `exp(a)`, `ln(a)`, `abs(a)` and `if_then_else(c, a, b)`. The condition `c` is one comparison, `<`, `<=`, `>`, `>=`, `==` or `!=`, between two expressions; comparisons appear nowhere else.
  - Errors: an unknown name is E403, a syntax error E404, and a loop in what must be evaluated before it is known is E405. Two graphs are checked. (1) In each step, a flow's `rate` and an auxiliary's `equation` may not need themselves, directly or through other flows and auxiliaries; a stock's value is known at the start of the step, so a stock breaks such a loop. (2) Before the first step, stocks' `initial` expressions, and the flows and auxiliaries they name, are evaluated in dependency order; there no stock is yet known, so any loop through `initial` expressions is E405, stocks included.
  - Not in Phase 2: lookup tables and delays (Open).
- **Engine.** The adapter writes the model as XMILE 1.0 in `engine/`: on both benchmarks PySD's results from XMILE equal its results from Vensim `.mdl` exactly (#278, `spec-5-pysd.md`). PySD translates and runs it with `run(time_step=…, saveper=…)`. Never pass the step through `params`: PySD 3.14.3 ignored it there in the trial. PySD integrates by Euler only, so the answer depends on `time_step`, which the label states.
- **Warnings.** PySD 3.14.3 raises a chardet `DeprecationWarning` on import and a pandas `set_index(inplace=...)` deprecation on each run. Ithax's tests turn warnings into errors, so the adapter filters exactly these two, by message and module, and a test shows that nothing else is raised (#278).

### Physical systems (Specified)

From the research, the CI trial (#228, run 43938942488 at head `e94ef9b`), the FMU's contents (#277) and #236 (`spec-5-openmodelica-fmu.md`):

- Component types name Modelica Standard Library 4.1.0 classes from a fixed catalogue: translational, rotational, electrical and lumped thermal elements. Each setting is the class's parameter with its unit; initial values are settings.
- Connections are undirected, between connectors of the same kind (E406).
- The adapter writes `model.mo` and a `.mos` script that sets `--fmiFlags=s:cvode` and calls `buildModelFMU(..., version = "2.0", fmuType = "cs", platforms = {"static"})` with every argument stated, since the API's defaults (`fmuType = "me"`, `platforms = {"static"}`) differ from the user's guide. Without the flag, the trial's FMU stepped with forward Euler at the communication step (largest error 3.87e-2 m at 0.01 s); with it, CVODE (relative tolerance 1e-6) gave 2.08e-7 m. The label names CVODE and its tolerance. FMUs are cached in the project, keyed by the generated file's SHA-256 and the OpenModelica version. FMPy runs the FMU only in the run worker.
- The mass–spring–damper benchmark of the export passes when x stays within 1e-5 m of the closed form over 10 s at a communication step of 0.01 s, with CVODE.
- **What an FMU contains** (#277). The CVODE FMU carries SUNDIALS 5.4.0 (`libsundials_cvode.so.5`, `libsundials_nvecserial.so.5`) beside the model library, found through `RUNPATH $ORIGIN`, so it runs where OpenModelica is not installed (CI runs 43938942488 and 44013052146). It carries no licence or notice file. A template or package that ships an FMU adds SUNDIALS's BSD-3-Clause `LICENSE` and `NOTICE` and the OpenModelica runtime's notice to its notices.
- **Installation** (#236). OpenModelica is installed on request, with documented apt steps for Linux and WSL 2, and needs a C toolchain. Without it, physical models run only from FMUs Ithax built and cached. A project accepts only FMUs Ithax built: an FMU from elsewhere is native code from a third party.

### Multibody (Specified, #231)

On MuJoCo, after a trial matched the pendulum benchmark to about 1e-11 (`spec-5-mujoco.md`). Project Chrono is left for Phase 3, for vehicles and contact-rich models (#231, option C kept open; its CI pendulum passed one setting of twelve, `spec-5-chrono.md`):

| Type | Settings |
| --- | --- |
| `body` | `mass` (kg), `inertia` (three kg·m² values about the centre of mass; a point mass uses small values, the benchmark 1e-12), `centre` (three m values in the body frame) |
| `joint` | `kind` (`hinge` or `slide`), `parent` (body id, or `world` for the fixed frame), `child` (body id), `anchor` (three m), `axis` (three numbers), optional `initial`, `stiffness`, `damping` |
| `world` | `gravity` (three m/s² values, default 0, 0, −9.80665) |

`world` is reserved in this domain: no component may use it as its id (E112, as spec 1 reserves `model`), so `parent: "world"` always means the fixed frame and never a body. Joints form a tree from `world`: every body is the `child` of exactly one joint, and no joint chain returns to a body above it (E408; closed loops are Phase 3). The adapter writes MJCF in `engine/`; the integrator is `RK4` at `time_step`. Metrics `<joint>.position`, `<joint>.velocity`, `<body>.x`, `.y`, `.z`, with the statistics above. Contacts, closed loops, conveyors and vehicles: Phase 3.

## People in models

From `spec-5-people-engines.md`, `spec-5-people-methods.md` and `spec-5-transitive-licences.md`; the phases are #237's.

- **(a) Workforce in process models (Specified, #237; M24).** Spec 0 and the Phase 2 table hold "people and workforce models", so two settings come in Phase 2 as spec 2 extensions, a model format change that only adds, each with a benchmark:
  - a learning curve on `server`, Crawford's unit form: the n-th unit's service time is the first unit's × n^b, b = log2(learning rate);
  - absenteeism on `resource_pool`: each unit is absent for a shift with probability p, drawn from the pool's stream; mean available capacity = capacity × (1 − p).

  Fatigue and skill matching: Phase 3 (no published model chosen).
- **(b) Crowds and pedestrians (Phase 3, #237).** JuPedSim 1.4 is the candidate, after a legal check, next to spec 6's geometry. In the trial, door flows were 0.979 to 1.185 persons/(m·s) with default settings and 1.616 to 1.839 with a time gap of 0.5 s, against 1.2 to 1.8 published (Seyfried et al. 2008), for doors from 1.0 to 2.0 m; a 0.8 m door jammed. Its wheel compiles in CGAL packages under GPL-3.0-or-later (Boolean_set_operations_2, Triangulation_2, Surface_mesh; read from its source, #279), not only the LGPL its metadata states, and carries no notice for pybind11 (BSD-3-Clause). It needs 2D geometry (spec 6). Mesa stays for agents that are not walking.
- **(c) Biomechanics (Phase 3, #237).** OpenSim 4.6 ran the pendulum benchmark to a relative 2e-11. Its wheel holds no licence file. It bundles Ipopt 3.14.16, which is EPL-2.0 with no Secondary License named, so OpenSim runs as a separate worker process; MUMPS (CeCILL-C) and METIS (Apache-2.0) are read again at OpenSim's own versions before Phase 3 (#279).
- **(d) Ergonomics and human reliability (#238; M24).** Calculators under the guide's rule 7, each citing its formula and a published worked example. Their home in a project is Proposed (#234, item 6):
  - NIOSH revised lifting equation: public domain (NIOSH Applications Manual, 1994). Ithax computes by the formulas, as the manual says (#238): example 1 gives 16.03, 14.31, 34.93 and 24.68 lb, and the test checks each within 2% of the printed limits (16.3, 14.5, 35.1, 24.6 lb), which come from rounded tables.
  - SPAR-H: NUREG/CR-6883. Ithax applies the adjustment by the worksheets' rule, only with three or more negative factors (#238), so example 2 gives 6.40E-5. The two printed discrepancies are recorded beside the test: example 2 prints 6.41E-5 (the adjustment applied with no negative factors), and example 1 prints 0.81 where the formula gives 0.8016.
  - HEART, RULA and REBA: held until a lawyer confirms that Ithax may ship their scoring tables (#238). NIOSH and SPAR-H, US government works, go first.
  - Excluded: MTM and MOST (proprietary); users enter their own standard times.

## Reliability and maintenance

From `spec-5-reliability.md`; M24. **Proposed** for the calculators' home and entry point (#234, item 6: where a calculator's inputs live in a project, decided when M24 starts), otherwise as follows:

- **Life-data fitting.** `scipy.stats` `fit` with `CensoredData` (right-censored), in-process, for the spec 1 families `exponential`, `weibull`, `lognormal` and `normal`, as `src/ithax/model/fit.py` fits them today: `floc = 0` for `exponential`, `weibull` and `lognormal`, whose location is a threshold that life data starts from, and a free location for `normal`, whose location is its mean. It extends spec 3's distribution fit, and its result can fill a `failure` block's `time_to_failure`.
- **Block diagrams.** Calculators for nested series, parallel and k-out-of-n blocks, from each block's reliability, or from its MTTF and MTTR for steady-state availability A = MTTF / (MTTF + MTTR). A diagram that does not reduce by those steps is E410 (NIST 8.1.8.6).
- **Fault trees.** `faultree` 0.4 (BSD-3-Clause, in-process), for AND, OR and k-of-n gates: the exact top-event probability and the minimal cut sets, with the rare-event approximation and the cut-set upper bound shown beside them.
- **Maintenance-policy comparison (#239; M19).** The `failure` and `schedule` blocks cannot renew a unit before it fails, so `failure` gains optional settings: a preventive replacement interval or age, with its own duration. It is a spec 2 and model format change that only adds, built with D13's failure process per unit in M19, and tested against the age-replacement cost-rate formula with a published worked example, still to be found.

## Combining engines

**Chaining (Specified, #235; M23).** One model's output becomes another's input: a system model sets the cycle time used by a process model. From `spec-5-cosimulation.md`:

- **One file** (#235). A chain is a model file with `domain: "chain"` that holds its member models and the links between them, so it runs from one file. A member is not itself a chain (E422). The keys are written at M23 with a compat test. A word that the links give a fixed meaning is reserved under E112, as `world` is in multibody, so it can never also be a member's or a component's id.
- A chain is a directed acyclic graph of models. The manager runs them in order, each as an ordinary run with its own adapter, run folder and manifest, so no adapter changes. `/v1` shows one chain run that lists its member runs.
- In Phase 2 a link passes a scalar: a metric from the upstream `summary.json` (statistic `mean` for a replicated run) into a downstream parameter, whose unit must fit (E152). Time series pass once a downstream domain has a time-varying input (M19's source schedules, or system dynamics lookups).
- A cycle is E421, naming the models: Ithax never iterates whole runs to a fixed point (rule 7).
- The downstream `manifest.json` gains `chain_inputs`: each upstream run id, model SHA-256, metric, statistic and value. An upstream run is reused when its model and experiment are unchanged.

**Stepping together (Phase 3).** Two engines in step need a co-simulation master, which with step control, rollback or loop iteration is a numerical solver (rule 7). When it starts, it wraps a tool, libcosim through libcosimpy (MPL-2.0) first, after chaining has passed its acceptance row and the tool reproduces the note's two-mass benchmark. In the trial a Jacobi master with zero-order hold gained energy at every step tried, and a Gauss–Seidel one kept it.

## Design studies (#233; M26, NSGA-II in M20)

A design study wraps any model from any engine.

- **One evaluation** is one ordinary run through the adapter contract, in its own subfolder of `engine/` as spec 2's search does (`study-<n>`), with the study's inputs (parameters with bounds or distributions) set and its outputs (metrics) read. So a process model and a physical model are studied through the same interface (trial `trial_same_interface.py`: six study types, identical results in-process and as a separate process).
- **Libraries** (in-process; `spec-5-design-studies.md`; licences in `docs/DECISIONS.md`):

  | Study | Answers | Library |
  | --- | --- | --- |
  | Parameter sweep | How does the result change as one or two inputs vary? | A grid; no library |
  | Designed experiment | Which inputs matter? Space-filling samples | `scipy.stats.qmc` (Latin hypercube, scrambled Sobol); SALib Morris for screening |
  | Sensitivity analysis | How much of the output variation does each input explain? | SALib (Sobol indices with confidence half-widths) |
  | Optimization, one objective | Best inputs within constraints | Optuna TPE as spec 2; `scipy.optimize` (Nelder–Mead, COBYLA) for deterministic models |
  | Optimization, several objectives | The trade-off front | pymoo NSGA-II, as M20 builds it for B1 (#233): pymoo reached IGD 0.0056 on ZDT1 at 20,000 evaluations against Optuna's 0.057 |
  | Uncertainty study | The spread of the result given uncertain inputs | `scipy.stats` distributions sampled with `scipy.stats.qmc` |

- **Seeds.** Each library's seed is the first draw of the stream key `<seed>:0:@study` (outside the identifier pattern, so it cannot collide with a component id). Evaluations run one at a time in the library's order, or in a pool whose result does not depend on the pool.
- **Stochastic models.** A study works on means over a set number of replications per evaluation and reports their half-widths, as spec 2's search does.
- **Run time.** A study's evaluation count bounds its time: a 1,024-sample Sobol study is about 5,000 runs. The study runs under the run time limit like a search; studies that need more state their budget and the time limit they need.
- **OpenMDAO and Dakota are not used** (#233): Ithax engines give no derivatives, so OpenMDAO would only wrap SciPy's optimizers, and Dakota has no wheel and no Ubuntu binary.
- **Packaging** (#236, #279). pymoo and SALib are bundled without matplotlib, which they declare but which the study trials do not need: all three ran with it uninstalled and gave their recorded outputs.
- **Proposed, decided when M26 starts (#234, item 6):** where a study lives in the model file (proposed: an experiment's `study` object with a `kind` beside spec 2's `search`), its `summary.json` layout, and its `/v1` route and MCP tool.

## Surrogate models (#238; M26)

A surrogate is a fast approximation fitted to results from a slower model (`spec-5-surrogates.md`).

- **Built from a designed experiment.** The user picks inputs (with ranges), outputs and a run budget; the runs come from a `design` study.
- **Method.** Gaussian process regression (scikit-learn `GaussianProcessRegressor`, in-process, processor only): constant × Matern 5/2 with one length scale per input, inputs scaled to [0, 1], `normalize_y`. A stochastic model adds a white-noise term, or per-point noise from the replication variance when the design has replications. Gradient-boosted trees are not offered for small budgets: with 20 runs and default settings they predicted a constant (Branin Q² −0.029). Neural surrogates stay optional.
- **Budget** (#238). Default 10 runs per input (Loeppky, Sacks and Welch 2009); a warning below that, and E430 below the larger of 5 per input and 10.
- **Always labelled** (#238). Every surrogate result carries the fidelity label `surrogate` and "approximate: surrogate of <model>", with its validation error: the leave-one-out RMSE in the output's unit and as a share of its range, with the run count, and its 95% interval. The leave-one-out error is computed by refitting with scikit-learn once per left-out run, never by Ithax's own algebra (rule 7). With 20 or more runs, more than 5% of standardised residuals beyond ±3 gives a warning that the error estimate is unreliable. The trial found the true error up to 2.1 times the leave-one-out estimate.
- **Outside the trained range** (#238). Answered, with the mark "outside the trained range: not validated".
- **Portable and safe** (Proposed, decided when M26 starts: #234, item 6). Saved as `surrogates/<id>.json` in the project through the strict reader: the source model's SHA-256, inputs with units and ranges, outputs, runs, method, settings, seed, fitted hyperparameters, validation numbers and library versions. Rebuilt on load by refitting with the stored hyperparameters, never from a pickle, skops or ONNX file (ONNX could not convert the Matern model, and its RBF standard deviations were wrong in the trial). The refit was bit-identical in the trial; a refit that misses the stored validation numbers by more than a relative 1e-9 is E431.

## Service and MCP

Every Phase 2 feature gets its thin `/v1` route and MCP tool at the milestone that builds it, with a parity test (C6); M28 finishes them. The routes for studies, surrogates and calculators are designed with each when its milestone starts (#234, item 6); a chain is one run that lists its member runs (#235). Component types of the new domains need no new tools: `GET /v1/schema/components/{type}` and the existing edit tools serve them, with the additive changes listed under "New engine adapters".

## Benchmarks

Expected values are closed forms computed by `docs/research/spec-5-trials/benchmarks/expected_values.py` (scipy root finding and special functions, no simulation); the council recomputed each (`docs/research/spec-5-council.md`). A benchmark is a gate from its milestone.

| Case | Domain | Inputs | Known answer | Pass rule | Source | Milestone |
| --- | --- | --- | --- | --- | --- | --- |
| SIR final size and peak | `system_dynamics` | N 1000, I0 1, β 0.5/d, γ 0.25/d; `time_unit` d, `time_step` 1/64 d, 200 d | final size 797.154100; peak 153.926660 | within 0.5 and 0.25 persons (trial: +0.2171, +0.1434) | Brauer (2008) §2.4 | M23 |
| SIR final size, agents | `agent` | N 1000, I0 10, same rates, `time_step` 0.1 d, 200 d, 100 replications, seed 12345 | final size 800.203968 | mean within 3 standard errors (proposed; the trial ran 30 replications: 796.03 ± 9.18, 0.93 standard errors below) | as above | M23 |
| Predator and prey | `system_dynamics` | per day: α 1/365, β 0.1/365, γ 1.5/365, δ 0.075/365; x0 10, y0 5; `time_step` 0.0365 d, 5,475 d | V = δx − γ ln x + βy − α ln y, constant: −0.010447440 with these per-day rates (−3.813315552 with per-year rates; the time scale is the only change) | largest relative drift over the run below 1e-3 (trial in years at step 0.0001 year: 2.85e-4) | Hirsch, Smale and Devaney (2013) §11.2 | M23 |
| Mass, spring and damper | `physical` | m 1 kg, k 4 N/m, c 0.4 N·s/m, x0 1 m, v0 0; `length` 10 s, `record_interval` 0.01 s | x(10 s) = 0.079116024 m; damped period 3.157419417 s | within 1e-5 m over 10 s (FMPy on a hand-written FMU at relative tolerance 1e-8: 8.63e-7 m; OpenModelica's CVODE FMU at its tolerance 1e-6, step 0.01 s: 2.08e-7 m, CI run 43938942488) | Thomson and Dahleh (1998) §2.6 | M25 |
| Pendulum, 10° and 90° | `multibody` | L 1 m, g 9.80665 m/s², 1 kg with inertia 1e-12 kg·m², RK4, `time_step` 1 ms, 30 s | T = 2.010235893 s and 2.368246346 s | relative 1e-6 (MuJoCo: about 1e-11) | Thornton and Marion (2004) §4.4 | M25 |
| Branin | studies | Optuna TPE, 200 evaluations, seed 1 | 0.397887 | within 0.01 (trial: 0.399147 to 0.399725 over three seeds) | Surjanovic and Bingham | M26 |
| ZDT1, 30 variables | studies | pymoo NSGA-II, population 100, 20,000 evaluations | front f2 = 1 − √f1 | IGD below 0.01 (trial: 0.00555, 0.00564) | Zitzler, Deb and Thiele (2000) | M20 |
| Ishigami sensitivity | studies | a 7, b 0.1, SALib Sobol, N 1024, fixed seed | S1 0.3139, 0.4424, 0; ST 0.5576, 0.4424, 0.2437 | each within 0.05 (trial at N 1024: largest error 0.0079) | OpenTURNS use case (Ishigami and Homma 1990) | M26 |
| Surrogates of known functions | surrogates | Branin, GP, 40 runs; Borehole, GP, 80 runs; 1,000 held-out points | Q² ≥ 0.995 (Branin); Q² ≥ 0.999 and normalised RMSE ≤ 0.005 (Borehole); 95% coverage ≥ 0.90; held-out RMSE ≤ 2.5 × the stated error | as stated, each below the worst of ten designs in the trial | Surjanovic and Bingham; `spec-5-surrogates.md` | M26 |
| Weibull, right-censored | reliability | NIST 8.4.1.3 data, `floc = 0` | η 606.5280, β 1.7208 | four significant figures | NIST/SEMATECH e-Handbook 8.4.1.3 | M24 |
| 1-out-of-2 MTTF | reliability | λ 0.001 per hour, both units | 1500 h | exact to 1e-9 | Rausand, Example 4.9 | M24 |
| Series and parallel block diagram | reliability | 0.95, 0.90 in series with 0.80 ∥ 0.80; 2-out-of-3 at 0.9 | 0.8208; 0.9720 | exact to 1e-12 | formulas: NIST 8.1.8, Rausand ch. 4; inputs chosen here | M24 |
| Availability | reliability | one unit, MTTF 100, MTTR 25; two in parallel | 0.8; 0.96 | exact to 1e-12 | formula as above; `benchmarks/failure` | M24 |
| Fault tree | reliability | safety function of Lundteigen and Rausand, q 0.05, 0.01, 0.10 | exact 0.027005725; its five published cut sets | exact to 1e-12 | cut sets: Lundteigen and Rausand ch. 5; probabilities chosen here | M24 |
| Learning curve, 80% | workforce | first unit 1000; units 1, 2, 3, 4, 5, 10, 50, 100, 500, 1000 | 1000, 800, 702, 640, 596, 477, 284, 227, 135, 108 | equal after rounding to whole numbers | ICEAA learning-curve table | M24 |
| NIOSH lifting equation, example 1 | ergonomics | NIOSH Applications Manual (1994), example 1 | formulas: 16.03, 14.31, 34.93, 24.68 lb | each within 2% of the printed 16.3, 14.5, 35.1, 24.6 lb | NIOSH Applications Manual (1994) | M24 |
| SPAR-H, examples 1 and 2 | human reliability | NUREG/CR-6883, examples 1 and 2 | 0.8016; 6.40E-5 by the worksheets' rule | equal to three significant figures; the printed 0.81 and 6.41E-5 are recorded beside the test | NUREG/CR-6883 | M24 |

## Research before building

Done on 2026-11-16 and 2026-11-17 (#104); each item has a note under `docs/research/spec-5-*.md` with Question, Finding, Sources, Decision and Tested. The CI trials (#228), the CVODE FMU's contents (#277), XMILE through PySD (#278) and the bundled and transitive licences (#279) are done. Still to do, each before its milestone:

- **M19:** a published worked example of the age-replacement cost rate (#239).
- **M24:** the calculators' home in a project (#234, item 6).
- **M26:** where studies and surrogates live, and their routes (#234, item 6).
- **Phase 3:** MUMPS and METIS at OpenSim's own versions (#279); the legal checks of JuPedSim's GPL CGAL code and of HEART, RULA and REBA's tables, whose primary sources are not yet read (#237, #238); Project Chrono 10.0.0 with a body of physical inertia, if vehicles or contacts need it (#231).

## Owner decisions

Ten blocking questions (guide rule 5) were filed on 2026-11-16 as "Owner decision" issues, each with options and a recommended default. None was answered by 2026-11-18, so each default applies (`docs/DECISIONS.md`, 2026-11-18):

1. **Q1 (#231): A.** MuJoCo replaces Project Chrono. Phase 2 multibody shows plots; the 3D preview, contacts, conveyors and vehicles are Phase 3, where Chrono stays open (C).
2. **Q2 (#232): A.** Ithax's minimum Python becomes 3.12, and 3.11 leaves the CI matrix.
3. **Q3 (#233): A.** No OpenMDAO and no Dakota: `scipy.stats.qmc`, SALib, Optuna TPE, `scipy.optimize`, and pymoo for NSGA-II, here and in M20.
4. **Q4 (#234): B.** Items 1 to 5 are accepted: the format version, parameter units, physical units, deterministic experiments with `search` process-only, and the contract additions. Item 6, where studies, surrogates and calculators live and their routes, comes back for a decision when each milestone starts.
5. **Q5 (#235): A.** A chain is one file with `domain: "chain"`, and its members run as ordinary runs, each with its own folder and manifest; `/v1` shows one chain run listing them.
6. **Q6 (#236): A.** The package bundles the pure-Python engines (PySD, Mesa, MuJoCo, FMPy and the study libraries) with their notices. OpenModelica is installed on request; only FMUs Ithax built are accepted.
7. **Q7 (#237): A.** Phase 2: the learning curve and absenteeism. Phase 3: fatigue, skills, pedestrians and OpenSim.
8. **Q8 (#238): as recommended.** NIOSH by the formulas, tested within 2% of the printed values; SPAR-H by the worksheets' rule, with the printed discrepancies recorded; HEART, RULA and REBA held until a lawyer confirms; surrogates as listed under "Surrogate models".
9. **Q9 (#239): A.** Preventive replacement settings on `failure`, in M19 next to D13.
10. **Q10 (#240): A.** M23 is split. M23: system dynamics, agents and chaining. M24: reliability, calculators and workforce. M25: physical and multibody models. M26: design studies and surrogates. M27 to M29: Windows through WSL 2, MCP hardening, and the release. The build guide's table is renumbered in its own change.

## Acceptance tests

| Test | Milestone | Checked by |
| --- | --- | --- |
| Spec 5's research notes, small engine cases and council report exist, and this spec is detailed (B9, F3); the owner reviews it during development | M17 | agent; owner reviews |
| Each adapter passes its benchmarks and ships with a template | M23 (agent, system dynamics), M25 (physical, multibody) | agent |
| A chained model, system model feeding process model, runs from one file | M23 | agent |
| A design study optimizes a process model and a physical system model with the same interface | M26 (with M20's Pareto search), once #234's item 6 is decided | agent |
| A surrogate trained on the development machine loads on the low tier, gives the same predictions to 1e-9 of the output range on the same library versions, and its held-out RMSE on fresh runs is at most 2.5 × its stated error | M26 measured, once #234's item 6 is decided; owner confirms on the low tier | agent + owner |
| Each calculator reproduces its published worked example, NIOSH within 2% | M24 | agent |
| The learning curve and absenteeism settings pass their benchmarks | M24 | agent |
| Preventive replacement on `failure` matches the age-replacement cost rate of a published worked example | M19 | agent |
| Every new adapter runs on the `remote` target; FMUs are built where the run is created | each adapter's milestone (M23, M25), after M22 | agent |
| The bundled engines of spec 5 run under WSL 2, and OpenModelica installs there with the documented steps | M27 | agent or owner |
| Every new feature has its `/v1` route and MCP tool with a parity test; new component types need no new tools | M28 | agent |
| Agent walkthroughs in the student and business-analyst roles (C1) build and run one model of each new domain | M29 | agent |

## Changes in this version

2026-11-18, version 0.3, owner decisions' defaults applied (#231 to #240 unanswered by their date; `docs/DECISIONS.md`, 2026-11-18):

- Specified: physical systems (#228, #236, #277: CVODE, the FMU's SUNDIALS and its notices, OpenModelica on request, only Ithax-built FMUs), multibody on MuJoCo (#231), chaining as one `chain` file (#235, with E422), the workforce settings (#237), the calculators' answers (#238) and the surrogates' rules (#238), the format and contract additions (#234, items 1 to 5), and the design-study libraries (#233).
- Still Proposed, decided when each milestone starts: where studies, surrogates and calculators live, and their routes (#234, item 6).
- Experiments: the step rules apply to the stepped domains only. A `physical` experiment has no `time_step`; its `record_interval` is the FMU's communication step, which must divide `length`, by default `length` / 200 (Codex review of #241).
- Names: `world` is reserved as a component id in multibody (E112), so `parent: "world"` is never a body. Adapters write `c_<id>` as engine names, never the id, so engine keywords cannot collide with ids. A chain's fixed words are reserved the same way (Codex review of #241; the second finding of the reserved-name class, after the council's stream-key finding S6).
- Milestones follow #240's split: M23 system dynamics, agents and chaining; M24 reliability, calculators and workforce; M25 physical and multibody; M26 studies and surrogates; M27 to M29 Windows, MCP hardening and the release. Maintenance-policy settings are M19 (#239).
- Python 3.12 is the floor (#232). XMILE is the system dynamics input, with PySD's two warnings filtered (#278). Licences from #279: JuPedSim's GPL CGAL packages, OpenSim's EPL-2.0 Ipopt, pymoo and SALib without matplotlib. Benchmarks for NIOSH and SPAR-H and acceptance rows for workforce and maintenance policies added.

2026-11-16, version 0.3, spec 5 research session and council (#104; owner decision of 2026-11-16 to start it before M16 closed):

- Detailed from the research notes `docs/research/spec-5-*.md` and their trials, and revised from the council's review (`docs/research/spec-5-council.md`): the four domains, their component types, statistics and issue codes; chaining, design studies, surrogates, people and reliability; benchmarks with exact values, sources and milestones; acceptance rows tagged M17 to M26. The structure-only warning is replaced by a state per section (Specified, Proposed, Open).
- Specified: the agent-based and system dynamics domains and their statistics. Proposed, awaiting ten owner decisions (Q1 to Q10): MuJoCo in place of Project Chrono; OpenMDAO and Dakota dropped; the format and contract additions; chaining's layout; engine installation; people's phases; the calculators' answers; maintenance policies; splitting M23. Open: physical systems until OpenModelica's CI trial has run.

2026-11-05, version 0.2, spec review council:

- C28 (PHY-7, PHY-10, PHY-13, PHY-16): version line; people, workforce, reliability and maintenance in scope as structure only; multibody preview on the spec 6 viewer basis; SIR and pendulum benchmark answers corrected; reliability block diagram benchmark; research items for people and reliability.
