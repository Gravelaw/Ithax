# Build Specs 1 to 7

Nov 6, 2026 · @Akshay

## What is here

Seven build specs, one per tab, plus a build guide for coding sessions. Each spec carries its own version and status line under its title; spec 1 is at 1.1, spec 3 at 0.5 and spec 4 at 0.5 after M8 closed on 2026-11-08; spec 2 is at 0.8 after M5 closed the same day; spec 0 and specs 5 to 7 are at 0.2 after the review of 2026-11-05. The repository copy is the source of truth (owner to confirm); sessions never write to the Claude Docs. Specs 1 to 4 have a binding "Detailed specification" section each. Each ends with acceptance tests that an AI coding tool can be held to. Spec 0, the product brief, is a separate doc.

| Spec | Covers | Phase | Build after |
| --- | --- | --- | --- |
| 1 Model format and engine contract | The model file, units, validation, engine plugin interface, run targets, results | 1 | First |
| 2 Core engine | Process simulation, experiments, optimization, benchmarks | 1 | Spec 1 |
| 3 Desktop application | Engine service, API, interface, storage, packaging, hardware tiers | 1 | Spec 1, alongside spec 2 |
| 4 Content, learning and AI access | Templates, Learn and Build modes, plain-language findings, MCP server | 1 | Specs 2 and 3 |
| 5 Systems and design optimization | Agent-based, system dynamics, physical systems, multibody, design studies, surrogates | 2 | Phase 1 complete |
| 6 Physics platform | Geometry, meshing, materials, 3D viewer, coupling, annex structure | 3 | Phase 2 complete |
| 7 Physics and forces catalogue | Every physical effect, its standard model and its engine | 3 | Read with spec 6 |

## Research rule

Every spec has a "Research before building" section. The coding assistant completes it before implementing that spec.

- **Output.** One short note per spec in the repository: question, finding, sources, decision.
- **Sources.** Engine documentation and source code first, then peer-reviewed papers, then forums.
- **Paywalled papers.** Publisher sites show abstracts freely; full text needs a subscription or an open-access copy. Research tools should use what the user is entitled to read and prefer open-access versions. If paywalled, then create a list of papers with doi or isbn code for references.
- **Spec wins or changes.** If research contradicts a spec, the spec is updated before code is written. Code never silently departs from the spec.
- **Test over reading.** Where a claim about an engine can be tested in an hour, test it.

## Choices made without asking

You asked for all specs at once, so I made these calls. Each is easy to change now and costly to change after building starts.

| Choice | Where | Alternative |
| --- | --- | --- |
| Model file is JSON | Spec 1 | YAML, easier to hand-edit |
| Quantities written with units as text, such as "2 min" | Spec 1 | Separate value and unit fields |
| Optimization through Pyomo and HiGHS; Optuna for simulation-based search | Spec 2 | OR-Tools; SciPy |
| Engine service in Python with FastAPI | Spec 3 | Any local service framework |
| Interface in React with React Flow, packaged with Tauri | Spec 3 | Electron; a Qt desktop interface in Python |
| Phase 1 runs natively on Windows (proposed default after review); WSL deferred to Phase 3 | Spec 3 | Service under WSL |
| Ten Phase 1 templates, listed by name | Spec 4 | Your own priority list |
| Findings written by fixed rules, not by a language model | Spec 4 | Assistant-written findings |
| OpenMDAO as the design study layer | Spec 5 | Dakota |
| CalculiX as the first physics engine | Spec 6 | Code\_Aster |
| Nine physics annexes, A to I, in a set order | Spec 6 | Your own order |

## Limits of these drafts

- **Only a prototype has been run.** A throwaway prototype ran three example models against the spec 1 format and passed two queueing benchmarks. It covered five of the twelve block types. The API, the MCP tools, the optimization layout and the other seven blocks are specified but have never run. The prototype script and two of the three model files were not retained; their numbers survive in spec 2 as reference values only. `coffee_shop.json` is the one verbatim fixture.
- **Detail falls with distance.** Specs 1 to 4 are detailed to field level. Specs 5 to 7 set structure only. Detailing them now would mean inventing input formats and behaviours for engines nobody has installed or tested yet, which would create false precision. Each gets its detailed pass after its research items are done.
- **Engine assignments in spec 7 are a first mapping.** They come from the research and general knowledge of each engine, and none has been tested.
- **Performance targets are proposals.** Every time and size target is marked as proposed.
- **Technology choices were not re-researched.** The interface and service frameworks named in spec 3 are well-established options, but I did not check their current state.
- **Still not researched:** injection moulding, acoustics, lubrication, precipitation in alloys.
