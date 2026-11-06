# Spec 5: Systems and Design Optimization

> Version 0.2 · structure only · working copy in the repository (source of truth, owner to confirm) · changes are listed under "Changes in this version".

Phase 2 adds four more ways of modelling and one layer above all engines: design optimization. That layer is what later lets a user optimize a machine across several kinds of physics.

> **Warning: structure only. Do not implement from this spec as it stands.** It has no detailed specification section, because the engines it names have not been installed or tested, and writing field-level detail now would be guesswork. Before any Phase 2 code: complete the research items below, install and run each engine on a small case, then write the detailed section. See "Known gaps" in the Build guide.

## Scope

- **In:** agent-based models, system dynamics, physical system models, multibody dynamics, design studies, surrogate models, people and workforce models, reliability and maintenance models.
- **Out:** anything needing 3D geometry and meshes (spec 6); the multibody preview is the exception and uses spec 6's viewer basis.

## New engine adapters

| Domain | Models | Engine | Canvas style |
| --- | --- | --- | --- |
| Agent-based | Populations of individuals following rules: customers, vehicles, an epidemic | Mesa | Agent types, rules, a space |
| System dynamics | Stocks, flows and feedback loops: cash, workforce, market adoption | PySD (to be confirmed) | Stock-and-flow diagram |
| Physical systems | Connected components that obey physical laws: motors, pumps, tanks, heat exchangers, circuits | OpenModelica, exported as FMU and run with FMPy | Component diagram with physical connectors |
| Multibody dynamics | Rigid bodies, joints, springs, contacts: linkages, conveyors, vehicles | Project Chrono | Bodies and joints, with a 3D preview built on the spec 6 results viewer basis (VTK through PyVista), minimal in Phase 2 and extended in Phase 3; no separate viewer is written (proposed default, owner to confirm) |

Each adapter follows the spec 1 contract and adds its component types to the schema.

## People in models

Structure only; engines, formats and phases are decided after research.

- **(a) Workforce in process models.** Skill, learning curves, fatigue, absenteeism as settings on `resource_pool` and `schedule`; a spec 2 extension.
- **(b) Crowds and pedestrians.** Agent-based, Mesa first; dedicated engines to research (candidates, unverified: JuPedSim, Vadere).
- **(c) Human movement and biomechanics.** Candidate OpenSim (Apache-2.0, LICENSE file read 2026-11-05; Python bindings; not run).
- **(d) Ergonomics and human reliability.** Published assessment methods (NIOSH lifting equation, RULA/REBA, HEART/SPAR-H) as calculators under the spec 7 calculator rule.

**Reliability and maintenance.** Life-distribution fitting including censored data, reliability block diagrams and fault trees, availability and maintenance-policy comparison. Analytic parts are calculators; policy comparison runs on the Phase 1 engine with `failure` and `schedule`; libraries to research, unverified.

## Combining engines

- **Chaining first.** One model's output becomes another's input: a system model sets the cycle time used by a process model.
- **Stepping together later.** Running two engines in step is harder to make stable. It is deferred until chaining is proven.

## Design studies

A design study wraps any model from any engine.

| Study | Answers |
| --- | --- |
| Parameter sweep | How does the result change as one or two inputs vary? |
| Designed experiment | Which inputs matter most? Uses space-filling samples. |
| Sensitivity analysis | How much of the output variation does each input explain? |
| Optimization | Which input values give the best result within the constraints? |
| Uncertainty study | Given uncertain inputs, what is the spread of the result? |

Proposed engine: OpenMDAO for coupling and gradient-based optimization, with Optuna and pymoo for gradient-free and multi-objective problems.

## Surrogate models

A surrogate is a fast approximation fitted to results from a slower model.

- **Built from a designed experiment.** The user picks inputs, outputs and a run budget.
- **Runs on the processor by default.** Gaussian process and gradient-boosted tree models need no graphics hardware. Neural surrogates are optional where a graphics card is present.
- **Always labelled.** Every surrogate result shows its validation error and is marked as approximate.
- **Portable.** A surrogate trained on a workstation is saved in the project and runs on a low-tier laptop.

## Benchmarks

| Case | Known answer |
| --- | --- |
| Epidemic model (SIR), system dynamics form | Final size from the SIR final-size relation solved by root finding, and the peak-infection formula |
| Predator and prey | Conserved quantity along the solution |
| Mass, spring and damper | Analytic response |
| Simple pendulum, multibody | Period from the exact large-amplitude formula (complete elliptic integral), checked at 10 and 90 degrees |
| Standard optimization test functions | Published optima |
| Surrogate of a known function | Error below a set threshold on held-out points |
| Series and parallel reliability block diagram | Closed-form system reliability |

## Research before building

Complete these and record the findings, with sources, in a short note in the repository before writing code. If a finding contradicts this spec, update the spec first.

- **Engine confirmation.** Current state, licence and upkeep of Mesa, PySD, FMPy and Project Chrono, including how each installs under WSL.
- **OpenModelica export.** Which FMI version exports reliably today, and which standard libraries are usable.
- **Co-simulation.** Published guidance on stability and step-size control when engines run in step.
- **Design study layer.** OpenMDAO against Dakota for wrapping external engines.
- **Surrogate methods.** Which methods work with few training runs, and how to report their error honestly.
- **People.** Open engines and data for pedestrian flow, biomechanics and ergonomics; licences of assessment methods (some time-standard systems such as MTM are proprietary).
- **Reliability.** Open Python libraries for life-data fitting and fault-tree analysis, with licences.

## Acceptance tests

- [ ] Each adapter passes its benchmarks and ships with two templates.
- [ ] A chained model, system model feeding process model, runs from one file.
- [ ] A design study optimizes a process model and a physical system model with the same interface.
- [ ] A surrogate trained on the development machine reproduces held-out results within its stated error on the low tier.
- [ ] All new component types are reachable through the MCP tools without changes to them.

## Changes in this version

2026-11-05, version 0.2, spec review council:

- C28 (PHY-7, PHY-10, PHY-13, PHY-16): version line; people, workforce, reliability and maintenance in scope as structure only; multibody preview on the spec 6 viewer basis; SIR and pendulum benchmark answers corrected; reliability block diagram benchmark; research items for people and reliability.
