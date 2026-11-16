# Spec 0: Product Brief

Nov 5, 2026 · @Akshay

> Version 0.5 · working copy in the repository (the source of truth) · changes are listed under "Changes in this version".

## Purpose

A free, open-source desktop tool that lets people model, simulate and optimize processes, machines and materials without writing code. It wraps proven open-source engines behind one visual interface.

Commercial tools in this field are priced by quote and built for specialists. Their free editions cap model size or forbid real use. Open-source engines match them on capability but need programming and Linux skills. This product closes that gap.

The product is Ithax. A trademark and name-clash search comes before any public release (owner decision C8, 2026-11-13).

## Users

Students and small or medium businesses are both first-class users from Phase 1. Academic groups with stronger hardware are served by the same product.

| User | What they need | What that requires |
| --- | --- | --- |
| Student or self-learner | Understand a method by building and running a model | Guided templates, explanations of results, runs on a basic laptop |
| Small or medium business | Answer a real question about a process, machine or supply chain | Import of their own data, trustworthy results, plain-language findings |
| Academic or research group | Run heavy physics and publish reproducible work | Workstation and cluster execution, open model files, scripting access |

Serving students and businesses together means one interface with two entry points:

- **Learn mode.** Starts from a worked example and explains each step.
- **Build mode.** Starts from the user's own data and question.

## Scope and build order

Every domain is in scope: process, systems, people, and the full range of physics including friction, heat, forming and materials behaviour. "All" still needs an order, because later domains reuse what earlier ones build.

| Phase | Delivers | Specs |
| --- | --- | --- |
| 1 | Process simulation and optimization in a working desktop app, with templates and AI access | 0 to 4 |
| 1a | Phase 1 made ready for release: correctness, then data safety, then usability, and everything not assigned to a later phase (F1). Release v0.1.0 after correctness and data safety (F7) | 0 to 4 |
| 2 | Agent-based and system dynamics models, physical system models, multibody dynamics, people and workforce models, optimization across engines; the remote (SSH) run target; objective types and several objectives (B1); Windows through WSL 2 (F5; 2026-11-16, #207); early ranking and selection (D1), live key numbers (D4), wider table imports (D6), time-varying arrivals (D10), further process constructs (D11), one failure process per unit (D13), indexed models in the views (D14), data import through the assistant (D15); a `feasible` status with its gap, duals, and the MSER-5 comparison (E1) | 5; 1 to 4 for the rest |
| 3 | Physics platform: geometry, meshing, 3D results, material data, then one solver family at a time; template expansion (2026-11-09 B7 item 3); 3D and field imports (D6); the rest of D11; three outside testers timed to a first template run (C3) | 6, 7 and the annexes |
| 3a | Performance: low- and mid-tier optimization (F6), with improvements made upstream in the engines first (C4) | All |
| 4 | The cluster (Slurm) run target; graphics detection on Windows and macOS (D7); further multi-objective methods (B1) | 1 and 3 |

The annex order is spec 6's letter order, A to I; spec 6 is the single place it is kept. A native Windows build comes after Phase 3 (2026-11-16, #207). No outside pull requests or contributors are taken until Phase 4 is complete (C9). Every phase keeps cheap performance budgets and regression checks (C4), and agent walkthroughs in assigned roles are a gate in every phase (C1). The phase letters are owner decisions of 2026-11-13 (F1, C4).

**What Phase 1 does not do.** Phase 1 covers machines and people as resources, materials as stock, and movement as transport time. Physical movement, material behaviour and physics arrive in Phases 2 and 3. Phase 1 runs on the user's own machine only: the remote target arrives in Phase 2 and the cluster target in Phase 4 (owner decision A1, 2026-11-09). Phase 1 closes as Phase 1a, with release v0.1.0 (F7), which the owner tags (2026-11-15 item 2).

**Releases.** Versions are semantic, with a changelog (`CHANGELOG.md`). v0.1.0 follows Phase 1a's correctness and data safety. Within 0.x, the model format and the `/v1` API change only additively (owner decision F7, 2026-11-13).

One correction to the plan as stated. The governing equations are indeed published, but the equations are the small part. Turning them into solvers that are stable, accurate and fast is where the decades of effort in existing engines went. The product wraps those engines and does not re-derive them.

## Product principles

Six rules bind every later spec. A spec that breaks one needs a stated reason.

1. **Wrap engines; do not write solvers.** The product's own code is interface, translation and orchestration.
2. **The model file is the product's core.** The interface, the engines and any AI assistant all read and write the same documented format.
3. **One model, three run targets.** The same file runs on a laptop, a workstation or a cluster (the remote target from Phase 2, the cluster target from Phase 4).
4. **Say what level of answer the user is getting.** A coarse laptop result is labelled as coarse, never presented as final. Every exported result carries the same label, so it survives leaving the app.
5. **No engine ships without benchmarks.** Each adapter passes a set of problems with known answers before users see it.
6. **Works offline.** Core modelling and solving need no internet connection after installation; the installer itself may be downloaded.

## Platform and hardware

The product is built on Linux first, developed under WSL on Windows. Phase 1 is packaged and tested on Linux only (owner decision B4, 2026-11-09). Windows is supported through WSL 2, running the Linux package or the AppImage, until after Phase 3; a native Windows build follows after Phase 3, as refactoring and API work for the libraries that have no Windows build (owner decision of 2026-11-16 on #207). The code stays platform-neutral meanwhile.

| Layer | Phase 1 choice |
| --- | --- |
| Engine service | Linux, run under WSL during development |
| Desktop interface | Linux; on Windows through WSL 2 until after Phase 3 (#207) |
| Browser or hosted version | Not planned |
| Graphics hardware | Optional. Everything runs on the processor alone; Nvidia or Intel graphics speed up viewing and some solvers when present. GPU speed comes from engines that support it or from upstream work, never from solver code written here (F6) |

Hardware tiers:

| Tier | Target | Status |
| --- | --- | --- |
| Low | 4 processor cores, 8 GB memory, integrated graphics | Proposed; tested by limiting WSL on the development machine. Settled after the Phase 3 engine work (B3); optimized for in Phase 3a (F6) |
| Mid | 8 processor cores, 16 GB memory, integrated or entry-level graphics | Proposed; tested the same way, and settled and optimized for as the low tier is |
| High | The development machine: Intel Core Ultra 9 285H, 16 cores, 32 GB memory, Nvidia RTX 5080 laptop graphics plus Intel Arc 140T, two NVMe drives | Recorded 6 November 2026 |
| Cluster | Workstation or university cluster | Reached through the remote (Phase 2) and cluster (Phase 4) run targets |

The development machine is a high-tier system, not a low or mid one. It can stand in for the lower tiers because WSL lets the cores and memory given to Linux be capped. It also covers both graphics cases, since it has Nvidia and Intel graphics. Real low-end hardware should still be tried before any release.

Two points for spec 3:

- **WSL on user machines.** Decided: Windows users run the Linux package or the AppImage under WSL 2 until after Phase 3, and a native build comes after Phase 3 (owner decision of 2026-11-16 on #207, which replaces the native installer of 2026-11-15 item 3).
- **Compatibility testing.** The test matrix should cover machines with Nvidia graphics, Intel graphics and no dedicated graphics.

## AI access

The product does not embed a language model. It exposes an MCP server and a documented API, so any model the user chooses can build, run and inspect simulations.

- **Any model, cloud or local.** Users connect the assistant they already have. Offline users lose nothing from the core product.
- **The assistant works on the model file.** It creates and edits models in the documented format, which the product validates before running. It does not write solver input directly.
- **The same API serves scripts.** Researchers can automate studies without an assistant.
- **Every feature reaches the assistant.** Each feature ships with a thin API and MCP tool and a parity test, and the last or second-to-last milestone of every phase is MCP hardening plus a trial with a different assistant (owner decision C6, 2026-11-13).
- **Results come back in a readable form.** Summaries, key numbers and warnings are returned as structured data, so an assistant can explain them.

Research systems that automate simulation setup report high success on standard cases and lower success on complex ones. Validation and benchmark checks apply to assistant-built models exactly as they do to hand-built ones.

## Licence and community

The product is released under AGPL-3.0-only (owner decisions B4 and C7, 2026-11-13) and developed as a community project. A Help page, "Open source licences", lists every package and engine used, with its licence and authors, generated from the package's licence list so it cannot drift. This is not legal advice; have a lawyer confirm before the first public release.

What AGPL does:

- **Anyone who distributes a modified version must offer its source** to the people who receive it, under the same licence.
- **Anyone who offers a modified version as an online service must offer its source** to the users of that service.
- **White-labelling and selling are allowed.** A company may rebrand and sell the product. It cannot make its version closed.

What AGPL does not do:

- **It does not force changes back into the main repository.** A company must publish its source to its own users. It need not submit anything to this project. The community can then take those changes, since they carry the same licence.
- **It does not protect the name.** Stopping others from trading under the product's name needs a registered trademark and a usage policy.
- **It does not cover user work.** Models and results that people create remain their own.

What this means for people who use the product (not legal advice; a lawyer confirms before the first public release):

- **Scripts, assistants and other programs** that talk to the service through its API or MCP server are separate programs and are not covered by AGPL.
- **A company may build a private interface** against the API.
- **Section 13 applies only to someone who modifies the product** and lets others use the modified version over a network. Running the unmodified product on a shared workstation, or turning on remote access for your own team, creates no obligation.
- **Engines keep their own licences.** Phase 1 engines are MIT or BSD per PyPI metadata (read 2026-11-05). Later engines are recorded in `DECISIONS.md` before adoption, and a licence that forbids wrapping is a reason not to adopt (see the engine licence rule in spec 1). Engines run as separate processes that exchange files, so GPL-2.0-only engines such as CalculiX can be used; engine code is never copied or linked into Ithax, and the licences page cites each engine and its authors. Further legal review is deferred (owner decision F4, 2026-11-13).

No outside pull requests or contributors are taken until Phase 4 is complete (C9). To set before then:

- [x] Choose a product name: Ithax (C8).
- [ ] Check that the name is free to register as a trademark, before any public release (C8).
- [ ] Decide between a per-contribution sign-off and a contributor agreement, before Phase 4 ends (C9).
- [x] Governance: the orchestrating session merges and monitors CI, and never merges with red or not-running CI; the owner takes the decisions (C10).
- [x] AGPL-3.0-only (B4, C7). "Or later" is revisited before outside contributions open (C9).

## Success measures

Six measures (owner decision B2, 2026-11-13). They have no numeric targets: the targets are set after Phase 3. Until then the values measured are baselines, not targets, and they gate neither Phase 2 nor Phase 3 (owner decision of 2026-11-16 on #206).

| Measure | How measured | Baseline so far |
| --- | --- | --- |
| Functionality and flow of the application | Agent walkthroughs in assigned roles, such as a student and a business analyst, as a gate in every phase (C1); one or two people at v0.1.0 (C2); three outside testers timed to a first template run, following `docs/research/usability.md`, in Phase 3 (C3) | The tester script; a fresh install of the Linux package reaching the coffee shop template's first result in 13.3 s in a clean container (M11, `pytest -m package`) |
| Correctness of simulation and optimization results against open datasets and published benchmarks | `pytest -m benchmark` in CI, with cases from sources such as OR-Library, MIPLIB, Netlib, textbook queueing cases and Kaggle data under reusable licences | Every Phase 1 benchmark passes (34 at M13) |
| Cognitive load on the user | Agent walkthroughs in assigned roles (C1) | None recorded yet |
| MCP parity: what a user does in the interface can be done through MCP | A parity test for each feature, and a trial with a different assistant in every phase (C6) | An assistant built and ran each of the ten templates' problems through MCP (M10, `docs/research/mcp/`) |
| Speed and responsiveness of the application | `pytest -m perf` and `docs/research/perf-M*.md` | Service ready in 1.4 s (M6); selecting a block on a 200-component canvas at most 36 ms (M9) |
| Speed and parallelism of simulation and optimization runs | Timed runs of the templates on capped cores and memory, recorded in `docs/research/performance.md` | The ten templates on 4 cores within 8 GiB: 20 runs in 37.2 s (M10) |

The baselines are agent-container measurements; the owner confirms them on the low tier (#102). The records below are history: they are the measures of 2026-11-05, kept as M10 and M11 wrote them.

Recorded at M10 (2026-11-09, AKS-125; the owner confirms each, AKS-82):

- **Time to a first template run:** the tester script is in `docs/research/usability.md`. No outside tester has timed it; that is the owner's (the owner-only fallback applies). Until the M11 installer exists, the timing starts at the app's first start on a machine the owner has prepared (installing from source took about 9 minutes in the agent container).
- **Benchmark accuracy:** `pytest -m benchmark` passes every Phase 1 benchmark (19: the 17 cases of `benchmarks/` and the two machine-count tests), and `bash scripts/check.sh` and the benchmarks run in CI on every pull request.
- **Low-tier performance:** the ten templates and their exercises run to completion on 4 cores within an 8 GiB memory cap, 20 runs in 37.2 s, the slowest 8.1 s (`docs/research/performance.md`); measured in the agent container, not yet on the owner's low-tier machine.
- **Assistant access:** Claude Code with Claude Opus 5.5, connected through MCP to a service serving no templates, built and ran each of the ten templates' problems from a text description, and every answer agreed with the template's theory or benchmark value (`docs/research/mcp/`). "How many machines?" passed on a second attempt, after two tool descriptions named the parameter reference, and as five scenarios rather than a search.

Recorded at M11 (2026-11-09, AKS-127; the owner confirms, AKS-82):

- **Time to a first template run:** the Linux package exists (spec 3 "Packaging"), so the tester's clock starts at the installer (`docs/research/usability.md`). In a clean `ubuntu:24.04` container, as an ordinary user, checking the checksum, unpacking, `install.sh` and the coffee shop template's first result through the API took about 12 s, also offline (`pytest -m package`). The install is three typed commands; no outside tester has timed it.

## Risks and open items

Ten risks could sink the project; each has a response built into the plan. The last six were added by the review of 2026-11-05 and accepted at the Phase 1 review (2026-11-16).

| Risk | Response |
| --- | --- |
| Scope is far larger than one builder can deliver at once | Phase 1 is a complete, useful product. Later phases add one engine at a time. |
| Simulations that run but give wrong answers | Benchmarks for every adapter; results labelled by fidelity level |
| AI-written code that the owner cannot review in depth | Small specs with acceptance tests; engines do the numerical work |
| Around thirty engines and tools across three phases, each with its own input format and failure modes | One engine contract in spec 1; each adapter built, benchmarked and released alone; an engine that cannot pass its benchmarks is dropped from the catalogue, not worked around |
| A single maintainer: the project stalls if the owner is unavailable | Small milestones that each leave a working product; the repository, not a person, holds the specs, decisions and session summaries |
| An engine upgrade changes results | Benchmarks and recorded seeds are rerun on every upgrade; engine versions are written to every manifest; a changed answer is a DECISIONS entry |
| Template problems are not free to redistribute | Templates use textbook-style problems written for this project or sources whose licence permits reuse, recorded per template |
| Users act on a coarse or wrong result | Fidelity label and the estimate caveat on every results page and export; findings state their evidence |
| An unsigned package is blocked or distrusted | The Linux package and the AppImage, also under WSL 2 on Windows (#207), document the warning and the checksum; code signing is decided before the native Windows build after Phase 3 (B5, #207) |
| The MCP acceptance test needs an assistant the project does not control | A scripted MCP client in CI; the real-assistant transcript is an owner check, not a build gate |

Open items:

- [ ] Settle the low and mid tier numbers after the Phase 3 engine work (B3); low- and mid-tier optimization is Phase 3a (F6).
- [ ] Confirm the Phase 3 annex order.
- [ ] Research open-source engines for injection moulding, acoustics, lubrication and precipitation in alloys (the materials, casting, welding and additive manufacturing pass is summarised in spec 7).
- [ ] Confirm which OpenRadioss successor to build on: press reports (itsfoss.com, 5 Oct 2026, read by the council) say Siemens removed the upstream repository in October 2026 and a fork, OpenCourant, carries the code under AGPL-3.0; not confirmed from a Siemens or Altair statement or from the repositories themselves. Check for any closed-source component (a `hm_reader` binary was reported) before bundling.
- [x] Agree the success measures: the six of B2. Their numeric targets are set after Phase 3 (#206).

The background for this brief is in the research brief, "Low-Code Simulation, Modelling & Optimization Tool: Research Brief".

## Changes in this version

2026-11-05, version 0.2, spec review council:

- C27 (PHY-7, PHY-11, PRD-4, PRD-5, PRD-9, PRD-16, PRD-2, PRD-6, PRD-13, PRD-15, PHY-1): version line; people in scope; annex order kept in spec 6 only; what Phase 1 does not do; principles 4 and 6 extended; WSL point resolved as a proposed default; AGPL consequences for users; AGPL only/or-later checkbox; success measures with method and milestone; engine count and six added risks; open items on unresearched domains and the OpenRadioss successor.

2026-11-09, version 0.3, M10 closed (AKS-125):

- 2026-11-09, M10 closed (AKS-125): "Success measures" records what M10 measured for the first four measures (the tester script with the timing left to the owner; the benchmarks; the ten templates on 4 cores within 8 GiB; the assistant trials of the ten templates). The targets stay proposals. Version 0.3.

2026-11-09, version 0.4, M11 closed (AKS-127); the lines below were added after version 0.3, during the M11 build:

- 2026-11-09, owner decisions A1 and B4 (AKS-81, AKS-77; part of AKS-127): "Scope and build order" puts the remote (SSH) run target in Phase 2 and adds a Phase 4 for the cluster (Slurm) run target, and "What Phase 1 does not do", principle 3 and the Cluster tier say so; "Platform and hardware" says Phase 1 is packaged and tested on Linux only, the Windows version and its WSL point deferred until the Phase 1 review, the code staying platform-neutral; the unsigned-package risk covers the Phase 1 Linux package too.
- 2026-11-09, M11 closed (AKS-127): "Success measures" records, for the time to a first template run, that the Linux installer exists from M11 and how long it took in a clean container (`docs/research/usability.md`); the outside testers' timing stays the owner's. Version 0.4.

2026-11-16, version 0.5, the Phase 1 review (#101; the owner approved the checklist `docs/research/phase-1-review.md` on 2026-11-16):

- The version line drops "owner to confirm": the repository is the source of truth (2026-11-09 B2). The product is named Ithax, with the trademark search before any public release (C8).
- "Scope and build order" adds Phase 1a (F1, F7) and Phase 3a (C4, F6), the Phase 2, 3 and 4 items the owner decisions of 2026-11-13 assign (B1, C3, D1, D4, D6, D7, D10, D11, D13, D14, D15, E1; 2026-11-09 B7 item 3), the native Windows build after Phase 3 (#207) and no outside contributors before Phase 4 ends (C9); "What Phase 1 does not do" says Phase 1 closes as Phase 1a with v0.1.0, and a "Releases" paragraph states F7.
- "Platform and hardware": Windows through WSL 2 until after Phase 3, then a native build (owner decision of 2026-11-16 on #207, replacing the native installer of 2026-11-15 item 3); GPU speed only from engines or upstream (F6); the low and mid tiers settled after Phase 3 (B3) and optimized for in Phase 3a (F6).
- "AI access" adds C6. "Licence and community": AGPL-3.0-only and the Help licences page (B4, C7), separate engine processes and GPL-2.0-only engines (F4), and the checklist settled by C8, C9 and C10.
- "Success measures": the six measures of B2, with no numeric targets until after Phase 3 and the values so far as baselines (owner decision of 2026-11-16 on #206). The M10 and M11 records stay as history.
- "Risks and open items": the six risks of 2026-11-05 accepted (reading 2 of the checklist), the unsigned-package response rewritten for WSL 2 (B5, #207), the tier item reworded (B3, F6), and the success-measures item ticked. Version 0.5.
