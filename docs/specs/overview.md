# Build Specs 1 to 7

Nov 6, 2026 · @Akshay

## What is here

Seven build specs, one per tab, plus a build guide for coding sessions. Each spec carries its own version and status line under its title; spec 0 is at 0.5, and specs 1 to 4 are at 1.7, 1.2, 1.2 and 1.1, after the review of Phase 1 that the owner approved on 2026-11-16 (#101); specs 5 to 7 are at 0.2 after the review of 2026-11-05. The repository copy is the source of truth (2026-11-09 B2); sessions never write to the Claude Docs. Specs 1 to 4 have a binding "Detailed specification" section each. Each ends with acceptance tests that an AI coding tool can be held to. Spec 0, the product brief, is a separate doc.

| Spec | Covers | Phase | Build after |
| --- | --- | --- | --- |
| 1 Model format and engine contract | The model file, units, validation, engine plugin interface, run targets, results | 1, closed as 1a | First |
| 2 Core engine | Process simulation, experiments, optimization, benchmarks | 1, closed as 1a | Spec 1 |
| 3 Desktop application | Engine service, API, interface, storage, packaging, hardware tiers | 1, closed as 1a | Spec 1, alongside spec 2 |
| 4 Content, learning and AI access | Templates, Learn and Build modes, plain-language findings, MCP server | 1, closed as 1a | Specs 2 and 3 |
| 5 Systems and design optimization | Agent-based, system dynamics, physical systems, multibody, design studies, surrogates | 2 | Phase 1 complete |
| 6 Physics platform | Geometry, meshing, materials, 3D viewer, coupling, annex structure | 3 | Phase 2 complete |
| 7 Physics and forces catalogue | Every physical effect, its standard model and its engine | 3 | Read with spec 6 |

Phase 1 closes as Phase 1a, with release v0.1.0 (owner decisions F1 and F7, 2026-11-13). Phase 3a, between Phases 3 and 4, is the performance phase (C4). New items from specs 5 to 7 go to Phase 3, 3a or 4 (F3). Spec 0 "Scope and build order" holds the full phase table.

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
| Linux first (owner decision B4, 2026-11-09). Windows runs the Linux package or the AppImage under WSL 2 until after Phase 3, and a native Windows build comes after Phase 3 (owner decision of 2026-11-16 on #207) | Specs 0 and 3 | A native Windows build from Phase 2 |
| Ten Phase 1 templates, listed by name | Spec 4 | Your own priority list |
| Findings written by fixed rules, not by a language model | Spec 4 | Assistant-written findings |
| OpenMDAO as the design study layer | Spec 5 | Dakota |
| CalculiX as the first physics engine | Spec 6 | Code\_Aster |
| Nine physics annexes, A to I, in a set order | Spec 6 | Your own order |

## Limits of these drafts

- **Phases 1 and 1a are built.** Specs 1 to 4 were built from M1 to M16: the model format, all twelve block types, the experiment manager, optimization, the service and its API, the MCP tools, the interface, the ten templates, and the Linux package and AppImage, each against its acceptance tests and benchmarks (`docs/STATUS.md`). The first throwaway prototype's numbers survive in spec 2 as reference values only; `coffee_shop.json` is its one verbatim fixture.
- **Detail falls with distance.** Specs 1 to 4 are detailed to field level. Specs 5 to 7 set structure only. Detailing them now would mean inventing input formats and behaviours for engines nobody has installed or tested yet, which would create false precision. Each gets its detailed pass after its research items are done: one research session per spec, a small engine case run before its section is written, and an agent council (simulation, optimization, computational mechanics and software engineering) that expands the spec, each council report saved under `docs/research/` (owner decisions 2026-11-09 B9 and F3, 2026-11-13).
- **Engine assignments in spec 7 are a first mapping.** They come from the research and general knowledge of each engine, and none has been tested.
- **Performance targets are proposals.** Every time and size target is marked as proposed. Every phase keeps cheap performance budgets and regression checks, and the dedicated performance work is Phase 3a (C4); the values measured are baselines, not gates, until targets are set after Phase 3 (#206).
- **Technology choices were not re-researched.** The interface and service frameworks named in spec 3 are well-established options, but I did not check their current state.
- **Still not researched:** injection moulding, acoustics, lubrication, precipitation in alloys.

## Changes in this version

- 2026-11-16, the review of Phase 1 (#101; the owner approved the checklist `docs/research/phase-1-review.md` on 2026-11-16): the spec versions after the review; "owner to confirm" dropped from the source-of-truth sentence (2026-11-09 B2); specs 1 to 4 closed as Phase 1a, Phase 3a named, and new items from specs 5 to 7 placed by F3; the Windows row as the owner decided on 2026-11-16 (#207); the stale prototype limit rewritten as built; F3's method for specs 5 to 7; C4 and #206 for the performance targets. This section is new; earlier changes to this page are in `docs/DECISIONS.md`.
