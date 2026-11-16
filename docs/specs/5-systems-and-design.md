# Spec 5: Systems and Design Optimization

> Version 0.3 · detailed draft from the spec 5 research session (#104), for the owner's approval · working copy in the repository (source of truth, owner to confirm) · changes are listed under "Changes in this version".

Phase 2 adds four more ways of modelling and one layer above all engines: design optimization. That layer is what later lets a user optimize a machine across several kinds of physics.

> **Warning: partly specified.** Version 0.3 is detailed from the research notes `docs/research/spec-5-*.md` and their trial runs (`docs/research/spec-5-trials/`). A section is ready to build only when its heading says **Specified**. A section marked **Open** still depends on an owner decision or an untried engine: do not implement it until the decision is recorded and the section is marked specified. Every engine here is wrapped, never written (guide rule 7).

## Scope

- **In:** agent-based models, system dynamics, physical system models, multibody dynamics, chaining models, design studies, surrogate models, people and workforce models, reliability and maintenance models.
- **Out:** anything needing 3D geometry and meshes (spec 6); the multibody preview is the exception and uses spec 6's viewer basis. Stepping engines together (co-simulation) is out of Phase 2 ("Combining engines").

## New engine adapters

| Domain (`domain`) | Models | Engine | Invocation | Canvas style | State |
| --- | --- | --- | --- | --- | --- |
| `agent` | Populations of individuals following rules: customers, an epidemic | Mesa 3.5 (Apache-2.0) | in-process | Populations and rules | Specified, well-mixed only |
| `system_dynamics` | Stocks, flows and feedback loops: cash, workforce, market adoption | PySD 3.14 (MIT) | in-process | Stock-and-flow diagram | Specified |
| `physical` | Connected components that obey physical laws: masses, springs, motors, circuits, heat flow | OpenModelica 1.27 builds an FMI 2.0 Co-Simulation FMU (GPL-3.0 or OSMC-PL, a separate process); FMPy 0.3 (BSD-2-Clause) runs it in the run worker | process (build), in-process (FMPy) | Component diagram with physical connectors | Open: OpenModelica not yet run |
| `multibody` | Rigid bodies and joints: linkages, pendulums | MuJoCo 4.0 (Apache-2.0) proposed in place of Project Chrono | in-process | Bodies and joints, with a 3D preview on spec 6's viewer basis | Open: engine choice awaits the owner |

Each adapter follows the spec 1 contract (`capabilities`, `validate`, `translate`, `run`, `collect`) unchanged, reports the licence, invocation and distribution above in `Capabilities`, and adds its component types to the schema. No adapter takes Python, Modelica or XML text from a model file: a model holds data only, and the adapter writes the engine's input in its run folder. Sources: `spec-5-mesa.md`, `spec-5-pysd.md`, `spec-5-fmpy.md`, `spec-5-openmodelica-fmu.md`, `spec-5-chrono.md`, `spec-5-mujoco.md`.

## Model file for the new domains

Format 0.4 (additive). Every Phase 1 rule of spec 1 holds unless this section says otherwise: identifiers, parameters and `$param`, quantities, unknown keys, `ui`, `run`.

| Key | `agent` | `system_dynamics` | `physical` | `multibody` |
| --- | --- | --- | --- | --- |
| `components` | required | required | required | required |
| `connections` | not allowed | not allowed (links follow from equations) | required, undirected | not allowed (joints name their bodies) |
| `experiments` | required | required | required | required |
| `objectives`, `constraints` | as `process` | as `process` | as `process` | as `process` |

**Experiments.** `length` and `record_interval` as spec 1. `time_step` (time quantity, required for `agent`, `system_dynamics` and `multibody`; `record_interval` must be a whole multiple of it, else E401). `replications` and `seed` apply to `agent` only; the other three domains are deterministic, so `replications` and `seed` are not allowed (E100) and a run has one replication, numbered 0. `warmup` is allowed in `agent` only. `scenarios` and `search` work as in spec 1 for every domain.

**Results.** Every new adapter returns spec 1's `replications` and `timeseries` tables, so the manager, findings and Results screen need no new layout. Metrics are `<component>.<variable>`, with `.final`, `.max`, `.min` and `.mean` (time-average) per recorded variable in `replications`. A deterministic run's `summary.json` metrics have `n` 1 and `half_width` `null`. The fidelity label names the method and step: "Standard: Euler, step 0.0625 d, 200 d" (system dynamics), "Standard: RK4, step 1 ms, 10 s" (multibody), "Standard: 30 replications of 200 d, step 0.1 d, 95% confidence" (agent).

**Units.** A `physical` or `multibody` setting is a quantity in one dimension; format 0.4 adds the units in "Physical units" below. Stocks, flows and agent counts are plain numbers. The time units are spec 1's (`s`, `min`, `h`, `d`).

**Issue codes.** E400 to E449 are the spec 5 model-layer codes (below); E300 to E399 stay engine-specific (spec 1).

| Code | Meaning |
| --- | --- |
| E401 | `record_interval` is not a whole multiple of `time_step` |
| E402 | A population's `initial` counts do not sum to its `count`, or name a state it lacks |
| E403 | An expression names something that is not a stock, flow, auxiliary or parameter |
| E404 | An expression does not parse |
| E405 | Auxiliaries depend on each other in a loop with no stock between |
| E406 | A physical connection joins connectors of different kinds |
| E410 | A block diagram does not reduce by series, parallel and k-out-of-n steps |
| E420 | A chained time series does not cover the downstream run's length |
| E421 | Chained models form a cycle |
| E430 | A surrogate's run budget is below the larger of 5 per input and 10 |
| E431 | A surrogate's refit does not reproduce its stored validation numbers |

### Agent-based models (Specified, well-mixed)

| Type | Settings | Behaviour |
| --- | --- | --- |
| `population` | `count` (integer ≥ 1), `states` (array of identifiers, at least one), `initial` (object: state to integer, summing to `count`, else E402) | `count` agents, each in one state, mixing uniformly |
| `transition` | `population` (id), `from`, `to` (states of it), `rate` (rate quantity, `1/d` etc.), optional `contact` (a state of the same population) | Each step, each agent in `from` moves to `to` with probability 1 − exp(−r Δt), where r is `rate`, or `rate` × (agents in `contact`) / `count` when `contact` is given. Decisions use the counts at the start of the step and apply together |

Randomness: one stream per population per replication, key `<seed>:<replication>:<population id>` (spec 1), given to `mesa.Model(rng=...)`. Metrics: `<population>.<state>` (count) in `timeseries`, and its `.final`, `.max` and `.time_of_max` in `replications`. Spaces (grid, continuous, network) and movement rules are **Open**: Phase 3 unless M23's templates need them.

### System dynamics (Specified)

| Type | Settings | Behaviour |
| --- | --- | --- |
| `stock` | `initial` (expression) | A level, integrated from its flows |
| `flow` | `from`, `to` (stock ids, either may be `null` for outside the model), `rate` (expression, per experiment `time_unit`) | Drains `from` and fills `to` |
| `auxiliary` | `equation` (expression) | A named value computed each step |

- **Expressions.** A string in a small grammar Ithax parses itself, never `eval`: numbers, the ids of stocks, flows, auxiliaries and parameters, `+ − * / ^`, parentheses, and the functions `min`, `max`, `exp`, `ln`, `abs`, `if_then_else(c, a, b)`, comparisons inside it, and `time`. An unknown name is E403, a syntax error E404, an auxiliary that depends on itself without a stock between E405. Phase 2 has no table (lookup) functions and no delays; both are **Open**.
- **Experiment.** `time_unit` (one of `s`, `min`, `h`, `d`; rates are per that unit) and `time_step` in that unit.
- **Engine.** The adapter writes an XMILE file (OASIS XMILE 1.0) in `engine/`, translates it with PySD and runs it with `run(time_step=…, saveper=…)`. PySD integrates by Euler only, so the answer depends on `time_step`; the label says so. Never pass the step through `params`: PySD 3.14.3 ignores it there (trial).
- **Metrics.** `<stock>` and `<flow>` values in `timeseries`; `.final`, `.max`, `.time_of_max` in `replications`.

### Physical systems (Open: OpenModelica not yet run)

- **Component types** name Modelica Standard Library 4.1.0 classes from a fixed catalogue: translational (`mass`, `spring`, `damper`, `fixed`, `force`), rotational (`inertia`, `torsion_spring`, `torque`), electrical (`resistor`, `capacitor`, `inductor`, `voltage_source`, `ground`) and lumped thermal (`heat_capacitor`, `thermal_conductor`, `fixed_temperature`). Each setting is the class's parameter, with its unit; initial values (`s_start`, `v_start`, `T_start`) are settings.
- **Connections** are undirected `{"from": "<id>.<connector>", "to": "<id>.<connector>"}` between connectors of the same kind (`flange` translational or rotational, `pin`, `heat_port`); a mismatch is E406.
- **Engine.** The adapter writes `model.mo` and a `.mos` script that calls `buildModelFMU(..., version = "2.0", fmuType = "cs")`; `omc` runs as a separate process. FMUs are cached in the project under `fmu/<sha256 of model.mo>-<OpenModelica version>.fmu`. FMPy runs the FMU in the run worker, never in the service, with `record_interval` as the communication step and `tolerance` (default 1e-6) for the FMU's CVODE.
- **Metrics.** `<component>.<variable>` as Modelica names them (`mass.s`, `mass.v`, `resistor.i`).
- **Open until:** an OpenModelica export of the mass–spring–damper runs in FMPy against the benchmark, and it is known whether an FMU built for `x86_64-linux-gnu` runs on a machine without OpenModelica (`spec-5-openmodelica-fmu.md`).

### Multibody (Open: engine choice)

Proposed on MuJoCo; Project Chrono could not be run here (`spec-5-chrono.md`, `spec-5-mujoco.md`).

| Type | Settings |
| --- | --- |
| `body` | `mass` (kg), `inertia` (three kg·m² values about the centre of mass), `centre` (three m values in the body frame) |
| `joint` | `kind` (`hinge` or `slide`), `parent` (body id or `world`), `child` (body id), `anchor` (three m), `axis` (three numbers), optional `initial` (angle or position), `stiffness`, `damping` |
| `world` | `gravity` (three m/s² values, default 0, 0, −9.80665) |

The adapter writes MJCF in `engine/`; the integrator is `RK4` with the experiment's `time_step`. Metrics: `<joint>.position`, `<joint>.velocity`, `<body>.x`, `.y`, `.z`. Contacts and closed loops are **Open**.

### Physical units (format 0.4)

Added for `physical` and `multibody` settings, converted to SI at load (spec 1 "Units"): `kg`, `g`; `m`, `mm`; `N`, `N/m`, `N.s/m`, `N.m`, `N.m/rad`; `rad`, `deg`; `kg.m2`; `m/s`, `m/s2`; `V`, `A`, `Ohm`, `F`, `H`; `K`, `degC` (an offset, converted as T + 273.15), `W`, `J/K`, `W/K`. A unit of the wrong dimension is E140; other grammar as spec 1.

## People in models

From `spec-5-people-engines.md` and `spec-5-people-methods.md`.

- **(a) Workforce in process models (Open: model format).** Two settings are ready to specify once the owner admits them to Phase 2, each with a benchmark:
  - a learning curve on `server`, Crawford's unit form: the n-th unit's time is the first unit's × n^b, b = log2(learning rate); test: the ICEAA 80% table, all ten values reproduced (trial);
  - absenteeism on `resource_pool`: each unit is absent for a shift with probability p, drawn from the pool's stream; test: mean available capacity = capacity × (1 − p).

  Fatigue and skill matching have no published model chosen; they stay open.
- **(b) Crowds and pedestrians (Open: engine and geometry).** Proposed: JuPedSim 1.4 (LGPL-3.0-or-later, in-process, installed without its viewer dependencies) as a `pedestrian` domain, in place of "Mesa first", so that Ithax writes no movement model of its own. It needs 2D room and corridor polygons in the model file. The trial's door flows were 0.979 to 1.185 persons/(m·s) with default settings and 1.616 to 1.839 with a time gap of 0.5 s, against 1.2 to 1.8 published (Seyfried et al. 2008), so templates carry calibrated settings and say so. Vadere (Java, LGPL-3.0) is deferred. Mesa stays for agents that are not walking.
- **(c) Human movement and biomechanics (Phase 3).** OpenSim 4.6 ran the pendulum benchmark to a relative 2e-11, but its wheel bundles Ipopt (EPL-1.0) and holds no licence file, so it would run as a separate process, Linux x86_64 only.
- **(d) Ergonomics and human reliability.** Calculators under the guide's rule 7:
  - **NIOSH revised lifting equation (Specified):** public domain (NIOSH Applications Manual, 1994); multipliers from the formulas, metric inputs converted at load; test: example 1's four recommended weight limits (16.3, 14.5, 35.1, 24.6 lb), within 2% since the manual's printed values come from rounded tables (the formulas give 16.03, 14.31, 34.93, 24.68 lb).
  - **SPAR-H (Specified):** public NRC report NUREG/CR-6883; test: section 2.5.1's example 2 (6.41E-5) and example 1, which prints 0.81 where the formula gives 0.8016.
  - **HEART (Open):** a primary source for its tables and a worked example is still to read.
  - **RULA and REBA (Open):** whether Ithax may ship their scoring tables needs a legal check.
  - **Excluded:** MTM and MOST (proprietary); users enter their own standard times.

## Reliability and maintenance

From `spec-5-reliability.md`:

- **Life-data fitting (Specified).** `scipy.stats` `fit` with `CensoredData` (right-censored), in-process, for the spec 1 families `exponential`, `weibull`, `lognormal`, `normal`; it extends spec 3's distribution fit. The result can fill a `failure` block's `time_to_failure`.
- **Block diagrams (Specified).** Calculators for series, parallel and k-out-of-n blocks, nested, with each block's reliability, or its MTTF and MTTR for steady-state availability A = MTTF / (MTTF + MTTR). A diagram that does not reduce by those steps is refused with E410 (NIST 8.1.8.6).
- **Fault trees (Specified).** `faultree` 0.4 (BSD-3-Clause, in-process) for AND, OR and k-of-n gates: the exact top-event probability and the minimal cut sets, with the rare-event approximation and the cut-set upper bound shown beside it.
- **Maintenance-policy comparison (Open).** The `failure` and `schedule` blocks cannot renew a unit before it fails, so preventive maintenance needs a `failure` extension, a model format change for the owner.

## Combining engines

**Chaining (Open: file layout awaits the owner; otherwise specified).** One model's output becomes another's input: a system model sets the cycle time used by a process model. From `spec-5-cosimulation.md`:

- A chain is a directed acyclic graph of models; the manager runs them in order, each as an ordinary run through its own adapter, so no adapter changes.
- A link passes either a scalar from the upstream `summary.json` (statistic `mean` by default for a replicated run) into a parameter, or a time series from `timeseries` into a time-varying input, with interpolation `linear` or `hold`; a series that does not cover the downstream run's length is E420. Units are checked at load.
- A cycle is E421, naming the models: Ithax does not iterate whole runs to a fixed point (rule 7).
- The downstream `manifest.json` gains `chain_inputs`: each upstream run id, model SHA-256, metric, statistic, and the value or the series' SHA-256. An upstream run is reused when its model and experiment are unchanged.
- **Open:** whether a chain is one file that embeds its models or links to other projects' models; and whether `/v1` shows it as one run or a group.

**Stepping together (out of Phase 2).** Two engines in step need a co-simulation master, which with step control, rollback or loop iteration is a numerical solver (rule 7). When it starts, it wraps a tool (libcosim through libcosimpy, MPL-2.0, first; OMSimulator second), after chaining has passed its acceptance row and the tool reproduces the two-mass benchmark of the note. The trial showed a Jacobi master with zero-order hold gaining energy at every step tried, and a Gauss–Seidel one keeping it.

## Design studies

A design study wraps any model from any engine. **Specified** except the file layout.

- **One evaluation.** A study sees named inputs (parameters with bounds or distributions) and named outputs (metrics). Each evaluation is one ordinary run through the adapter contract, in its own subfolder of `engine/` as spec 2's search does, so a process model and a physical model are studied through the same interface (trial `trial_same_interface.py`: six study types, identical results in-process and as a separate process).
- **Libraries** (all in-process; `spec-5-design-studies.md`):

  | Study | Answers | Library |
  | --- | --- | --- |
  | Parameter sweep | How does the result change as one or two inputs vary? | A grid; no library |
  | Designed experiment | Which inputs matter? Space-filling samples | `scipy.stats.qmc` (Latin hypercube, scrambled Sobol); SALib Morris for screening |
  | Sensitivity analysis | How much of the output variation does each input explain? | SALib (Sobol indices with confidence half-widths) |
  | Optimization, one objective | Best inputs within constraints | Optuna TPE as spec 2; `scipy.optimize` (Nelder–Mead, COBYLA) for deterministic models |
  | Optimization, several objectives | The trade-off front | pymoo NSGA-II (shared with M20's Pareto search, B1) |
  | Uncertainty study | The spread of the result given uncertain inputs | `scipy.stats` distributions sampled with `scipy.stats.qmc` |

- **Seeds.** Each library's seed is the first draw of the reserved stream `<seed>:0:study`, as spec 2's `<seed>:0:optimizer`; evaluations run one at a time in the library's order, or in a pool whose result does not depend on the pool.
- **Stochastic models.** A study works on means over a set number of replications per evaluation and reports their half-widths, as spec 2's search does.
- **OpenMDAO and Dakota are not used** (proposed, owner to confirm): Ithax engines give no derivatives, so OpenMDAO would only wrap SciPy's optimizers; Dakota has no wheel and no Ubuntu binary.
- **Open (model format):** where a study and a surrogate live in the model file. Proposed: an experiment's `study` object with a `kind` (`sweep`, `design`, `sensitivity`, `optimization`, `uncertainty`) beside spec 2's `search`, which stays as it is (format 0.4, additive), and surrogates as `surrogates/<id>.json` in the project folder.

## Surrogate models

A surrogate is a fast approximation fitted to results from a slower model. **Specified** except the file layout (`spec-5-surrogates.md`).

- **Built from a designed experiment.** The user picks inputs (with ranges), outputs and a run budget; the runs come from a `design` study.
- **Method.** Gaussian process regression (scikit-learn `GaussianProcessRegressor`, BSD-3-Clause, in-process, processor only): constant × Matern 5/2 with one length scale per input, inputs scaled to [0, 1], `normalize_y`. A stochastic model adds a white-noise term, or per-point noise from the replication variance when the design has replications. Gradient-boosted trees are not offered for small budgets: with 20 runs and default settings they predicted a constant (Branin Q² −0.029 in the trial). Neural surrogates stay optional.
- **Budget.** Default 10 runs per input (Loeppky, Sacks and Welch 2009); a warning below that, and a refusal (E430) below the larger of 5 per input and 10.
- **Always labelled.** Every surrogate result carries the fidelity label `surrogate` and "approximate: surrogate of <model>", with its validation error: the leave-one-out RMSE in the output's unit and as a share of its range, over the training runs, with the run count. A result also shows its 95% interval. More than 5% of standardised leave-one-out residuals beyond ±3 gives a warning that the error estimate is unreliable. The trial found the true error up to 2.1 times the leave-one-out estimate, so the benchmark gate below allows 2.5 times.
- **Outside the trained range.** A query with any input outside its trained range is answered only with the mark "outside the trained range: not validated".
- **Portable and safe.** A surrogate is saved in the project as JSON through the strict reader: the source model's SHA-256, the inputs with units and ranges, the outputs, the runs, the method and settings, the seed, the fitted hyperparameters, the validation numbers and the library versions. It is rebuilt on load by refitting with the stored hyperparameters, never from a pickle, skops or ONNX file (ONNX could not convert the Matern GP, and its RBF standard deviations were wrong in the trial). The refit was bit-identical in the trial; a file whose refit does not reproduce its stored validation numbers is refused with E431.

## Benchmarks

Expected values are closed forms computed by `docs/research/spec-5-trials/benchmarks/expected_values.py` (scipy root finding and special functions, no simulation), each with its source.

| Case | Domain | Inputs | Known answer | Pass rule | Source |
| --- | --- | --- | --- | --- | --- |
| SIR final size and peak | `system_dynamics` | N 1000, I0 1, β 0.5/d, γ 0.25/d; `time_step` 1/64 d, 200 d | final size 797.154100; peak 153.926660 | within 0.5 and 0.25 persons (trial: +0.2171, +0.1434) | Brauer (2008) §2.4 |
| SIR final size, agents | `agent` | N 1000, I0 10, same rates, `time_step` 0.1 d, 30 replications | final size 800.203968 | inside the 95% interval of the mean (trial: 796.03 ± 9.18) | as above |
| Predator and prey | `system_dynamics` | α 1, β 0.1, γ 1.5, δ 0.075 per year, x0 10, y0 5; step 0.0001, 15 years | V = δx − γ ln x + βy − α ln y = −3.813315552 | relative drift below 1e-3 (trial: 2.85e-4) | Hirsch, Smale and Devaney (2013) §11.2 |
| Mass, spring and damper | `physical` | m 1 kg, k 4 N/m, c 0.4 N·s/m, x0 1 m, v0 0 | x(10 s) = 0.079116024 m; damped period 3.157419417 s | within 1e-5 m over 10 s (FMPy trial: 8.63e-7) | Thomson and Dahleh (1998) §2.6 |
| Pendulum, 10° and 90° | `multibody` | L 1 m, g 9.80665 m/s², point mass | T = 2.010235893 s and 2.368246346 s | relative 1e-6 (MuJoCo trial: about 1e-11) | Thornton and Marion (2004) §4.4 |
| Test functions | studies | Branin; Rosenbrock 2-D; ZDT1 (30 variables) | 0.397887; 0 at (1, 1); front f2 = 1 − √f1 | Branin within 0.01 at 200 evaluations; ZDT1 IGD below 0.01 at 20,000 | Surjanovic and Bingham; Zitzler, Deb and Thiele (2000) |
| Ishigami sensitivity | studies | a 7, b 0.1, N 1024 | S1 0.3139, 0.4424, 0; ST 0.5576, 0.4424, 0.2437 | each within its confidence half-width | OpenTURNS use case (Ishigami and Homma 1990) |
| Surrogates of known functions | surrogates | Branin, GP, 40 runs; Borehole, GP, 80 runs; 1,000 held-out points | Q² ≥ 0.995 (Branin) and ≥ 0.999 with normalised RMSE ≤ 0.005 (Borehole); 95% coverage ≥ 0.90; held-out RMSE ≤ 2.5 × the stated error | as stated, each below the worst of ten designs in the trial | Surjanovic and Bingham; `spec-5-surrogates.md` |
| Weibull, right-censored | reliability | NIST 8.4.1.3 data | η 606.5280, β 1.7208 | four significant figures | NIST/SEMATECH e-Handbook 8.4.1.3 |
| Series and parallel block diagram | reliability | R 0.95, 0.90 in series with 0.80 ∥ 0.80; 2-out-of-3 at 0.9 | 0.8208; 0.9720 | exact to 1e-12 | NIST 8.1.8; Rausand ch. 4 |
| Learning curve, 80% | workforce | first unit 1000, units 1, 2, 3, 4, 5, 10, 50, 100, 500, 1000 | 1000, 800, 702, 640, 596, 477, 284, 227, 135, 108 | equal after rounding to whole numbers | ICEAA learning-curve table (`spec-5-people-methods.md`) |
| NIOSH lifting, example 1 | calculator | the manual's four tasks | RWL 16.3, 14.5, 35.1, 24.6 lb | within 2% | NIOSH Applications Manual (1994) |
| SPAR-H, example 2 | calculator | NUREG/CR-6883 §2.5.1 | 6.41E-5 | three significant figures | NUREG/CR-6883 (2005) |
| Fault tree | reliability | safety function, q 0.05, 0.01, 0.10 | exact 0.027005725; cut sets C1 to C5 | exact to 1e-12 | Lundteigen and Rausand ch. 5 |

## Research before building

Done on 2026-11-16; each item has a note under `docs/research/spec-5-*.md` with Question, Finding, Sources, Decision and Tested. Still to run before the sections marked Open become specified:

- **OpenModelica export.** Build the mass–spring–damper FMU with OpenModelica 1.27.2 and run it in FMPy; check that an FMU built for `x86_64-linux-gnu` runs without OpenModelica installed.
- **Multibody engine.** The owner's choice between MuJoCo and Project Chrono; if Chrono, its pendulum trial.

## Acceptance tests

| Test | Milestone | Checked by |
| --- | --- | --- |
| Spec 5's research notes, small engine cases and council report exist, and this spec is detailed for the owner (B9, F3) | M17 | agent; owner approves the spec |
| Each specified adapter passes its benchmarks and ships with two templates | M23 | agent |
| A chained model, system model feeding process model, runs from one file | M23 | agent |
| A design study optimizes a process model and a physical system model with the same interface | M23 (with M20's Pareto search) | agent |
| A surrogate trained on the development machine loads on the low tier, gives the same predictions to 1e-9 of the output range, and its held-out RMSE on fresh runs is at most 2.5 × its stated error | M23 measured; owner confirms on the low tier | agent + owner |
| Every new adapter runs on the `remote` target | M23, after M22 | agent |
| The engines of spec 5 install under WSL 2 with the documented steps | M24 | agent or owner |
| All new component types are reachable through the MCP tools without changes to them, with a parity test | M25 | agent |
| An agent walkthrough builds and runs one model of each new domain | M26 | agent |

## Changes in this version

2026-11-16, version 0.3, spec 5 research session (#104; owner decision of 2026-11-16 to start it before M16 closed):

- Detailed from the research notes `docs/research/spec-5-*.md` and their trials: the four domains with their component types, format 0.4, the chaining contract, design studies, reliability, and benchmarks with exact values and sources. Sections not settled are marked Open; the structure-only warning is replaced by per-section states.
- PySD confirmed; OpenModelica builds FMI 2.0 Co-Simulation FMUs; MuJoCo proposed in place of Project Chrono; OpenMDAO and Dakota dropped from design studies. Each awaits the owner where `docs/DECISIONS.md` says so.

2026-11-05, version 0.2, spec review council:

- C28 (PHY-7, PHY-10, PHY-13, PHY-16): version line; people, workforce, reliability and maintenance in scope as structure only; multibody preview on the spec 6 viewer basis; SIR and pendulum benchmark answers corrected; reliability block diagram benchmark; research items for people and reliability.
