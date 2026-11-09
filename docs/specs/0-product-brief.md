# Spec 0: Product Brief

Nov 5, 2026 · @Akshay

> Version 0.3 · working copy in the repository (source of truth, owner to confirm) · changes are listed under "Changes in this version".

## Purpose

A free, open-source desktop tool that lets people model, simulate and optimize processes, machines and materials without writing code. It wraps proven open-source engines behind one visual interface.

Commercial tools in this field are priced by quote and built for specialists. Their free editions cap model size or forbid real use. Open-source engines match them on capability but need programming and Linux skills. This product closes that gap.

The working title is not yet chosen.

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
| 2 | Agent-based and system dynamics models, physical system models, multibody dynamics, people and workforce models, optimization across engines | 5 |
| 3 | Physics platform: geometry, meshing, 3D results, material data, then one solver family at a time | 6, 7 and the annexes |

The annex order is spec 6's letter order, A to I; spec 6 is the single place it is kept.

**What Phase 1 does not do.** Phase 1 covers machines and people as resources, materials as stock, and movement as transport time. Physical movement, material behaviour and physics arrive in Phases 2 and 3.

One correction to the plan as stated. The governing equations are indeed published, but the equations are the small part. Turning them into solvers that are stable, accurate and fast is where the decades of effort in existing engines went. The product wraps those engines and does not re-derive them.

## Product principles

Six rules bind every later spec. A spec that breaks one needs a stated reason.

1. **Wrap engines; do not write solvers.** The product's own code is interface, translation and orchestration.
2. **The model file is the product's core.** The interface, the engines and any AI assistant all read and write the same documented format.
3. **One model, three run targets.** The same file runs on a laptop, a workstation or a cluster.
4. **Say what level of answer the user is getting.** A coarse laptop result is labelled as coarse, never presented as final. Every exported result carries the same label, so it survives leaving the app.
5. **No engine ships without benchmarks.** Each adapter passes a set of problems with known answers before users see it.
6. **Works offline.** Core modelling and solving need no internet connection after installation; the installer itself may be downloaded.

## Platform and hardware

The product is built on Linux first, developed under WSL on Windows. A Windows version follows as a native interface that talks to the engine service through an API.

| Layer | Phase 1 choice |
| --- | --- |
| Engine service | Linux, run under WSL during development |
| Desktop interface | Linux first; Windows interface connects to the engine service by API |
| Browser or hosted version | Not planned |
| Graphics hardware | Optional. Everything runs on the processor alone; Nvidia or Intel graphics speed up viewing and some solvers when present |

Hardware tiers:

| Tier | Target | Status |
| --- | --- | --- |
| Low | 4 processor cores, 8 GB memory, integrated graphics | Proposed; tested by limiting WSL on the development machine |
| Mid | 8 processor cores, 16 GB memory, integrated or entry-level graphics | Proposed; tested the same way |
| High | The development machine: Intel Core Ultra 9 285H, 16 cores, 32 GB memory, Nvidia RTX 5080 laptop graphics plus Intel Arc 140T, two NVMe drives | Recorded 6 November 2026 |
| Cluster | Workstation or university cluster | Reached through remote run targets |

The development machine is a high-tier system, not a low or mid one. It can stand in for the lower tiers because WSL lets the cores and memory given to Linux be capped. It also covers both graphics cases, since it has Nvidia and Intel graphics. Real low-end hardware should still be tried before any release.

Two points to settle in spec 3:

- **WSL on user machines.** Resolved as a proposed default in spec 3: Phase 1 runs natively on Windows; WSL only for Phase 3 engines without Windows builds. Owner to confirm.
- **Compatibility testing.** The test matrix should cover machines with Nvidia graphics, Intel graphics and no dedicated graphics.

## AI access

The product does not embed a language model. It exposes an MCP server and a documented API, so any model the user chooses can build, run and inspect simulations.

- **Any model, cloud or local.** Users connect the assistant they already have. Offline users lose nothing from the core product.
- **The assistant works on the model file.** It creates and edits models in the documented format, which the product validates before running. It does not write solver input directly.
- **The same API serves scripts.** Researchers can automate studies without an assistant.
- **Results come back in a readable form.** Summaries, key numbers and warnings are returned as structured data, so an assistant can explain them.

Research systems that automate simulation setup report high success on standard cases and lower success on complex ones. Validation and benchmark checks apply to assistant-built models exactly as they do to hand-built ones.

## Licence and community

The product will be released under AGPL version 3 and developed as a community project. This is not legal advice; have a lawyer confirm before the first public release.

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
- **Engines keep their own licences.** Phase 1 engines are MIT or BSD per PyPI metadata (read 2026-11-05). Later engines are recorded in `DECISIONS.md` before adoption, and a licence that forbids wrapping is a reason not to adopt (see the engine licence rule in spec 1).

To set before the first outside contribution:

- [ ] Choose a product name and check it is free to register as a trademark.
- [ ] Decide between a per-contribution sign-off and a contributor agreement.
- [ ] Write a short governance note: who can merge, and how decisions are made.
- [ ] Decide AGPL-3.0-only or AGPL-3.0-or-later (DECISIONS.md 2026-11-05).

## Success measures

These Phase 1 measures are proposals for you to adjust; none has been agreed.

| Measure | Proposed target | How measured | Checked at |
| --- | --- | --- | --- |
| Time for a new user to run a first template model | Under 30 minutes, with no code written | Three outside testers timed from installer to Results, following the script in `docs/research/usability.md` | M10 |
| Benchmark accuracy | Every Phase 1 engine adapter passes its full benchmark set | `bash scripts/check.sh` in CI | Every milestone |
| Low-tier performance | All Phase 1 templates run to completion on the low-tier laptop | Timed run of the ten templates on a machine capped to the low tier, recorded in `docs/research/performance.md` | M10 |
| Assistant access | An assistant connected through MCP builds and runs each Phase 1 template from a text description | Transcripts under `docs/research/mcp/` | M10 |
| Real use | Five people outside the project build a model of their own problem | A GitHub issue template and a "Tell us what you built" link on the Results screen that only opens the browser | Within three months of first release |

Recorded at M10 (2026-11-09, AKS-125; the owner confirms each, AKS-82):

- **Time to a first template run:** the tester script is in `docs/research/usability.md`. No outside tester has timed it; that is the owner's (the owner-only fallback applies). Until the M11 installer exists, the timing starts at the app's first start on a machine the owner has prepared (installing from source took about 9 minutes in the agent container).
- **Benchmark accuracy:** `pytest -m benchmark` passes every Phase 1 benchmark (19: the 17 cases of `benchmarks/` and the two machine-count tests), and `bash scripts/check.sh` and the benchmarks run in CI on every pull request.
- **Low-tier performance:** the ten templates and their exercises run to completion on 4 cores within an 8 GiB memory cap, 20 runs in 37.2 s, the slowest 8.1 s (`docs/research/performance.md`); measured in the agent container, not yet on the owner's low-tier machine.
- **Assistant access:** Claude Code with Claude Opus 5.5, connected through MCP to a service serving no templates, built and ran each of the ten templates' problems from a text description, and every answer agreed with the template's theory or benchmark value (`docs/research/mcp/`). "How many machines?" passed on a second attempt, after two tool descriptions named the parameter reference, and as five scenarios rather than a search.

## Risks and open items

Ten risks could sink the project; each has a response built into the plan. The last six were added by the review of 2026-11-05 and are proposals.

| Risk | Response |
| --- | --- |
| Scope is far larger than one builder can deliver at once | Phase 1 is a complete, useful product. Later phases add one engine at a time. |
| Simulations that run but give wrong answers | Benchmarks for every adapter; results labelled by fidelity level |
| AI-written code that the owner cannot review in depth | Small specs with acceptance tests; engines do the numerical work |
| Around thirty engines and tools across three phases, each with its own input format and failure modes | One engine contract in spec 1; each adapter built, benchmarked and released alone; an engine that cannot pass its benchmarks is dropped from the catalogue, not worked around |
| A single maintainer: the project stalls if the owner is unavailable | Small milestones that each leave a working product; the repository, not a person, holds the specs, decisions and session summaries (proposed) |
| An engine upgrade changes results | Benchmarks and recorded seeds are rerun on every upgrade; engine versions are written to every manifest; a changed answer is a DECISIONS entry (proposed) |
| Template problems are not free to redistribute | Templates use textbook-style problems written for this project or sources whose licence permits reuse, recorded per template (proposed) |
| Users act on a coarse or wrong result | Fidelity label and the estimate caveat on every results page and export; findings state their evidence (proposed) |
| An unsigned Windows package is blocked or distrusted | Budget for code signing before the first Windows release; until then, document the warning and the checksum (proposed) |
| The MCP acceptance test needs an assistant the project does not control | A scripted MCP client in CI; the real-assistant transcript is an owner check, not a build gate (proposed) |

Open items:

- [ ] Confirm the proposed low and mid tier numbers.
- [ ] Confirm the Phase 3 annex order.
- [ ] Research open-source engines for injection moulding, acoustics, lubrication and precipitation in alloys (the materials, casting, welding and additive manufacturing pass is summarised in spec 7).
- [ ] Confirm which OpenRadioss successor to build on: press reports (itsfoss.com, 5 Oct 2026, read by the council) say Siemens removed the upstream repository in October 2026 and a fork, OpenCourant, carries the code under AGPL-3.0; not confirmed from a Siemens or Altair statement or from the repositories themselves. Check for any closed-source component (a `hm_reader` binary was reported) before bundling.
- [ ] Agree the success measures.

The background for this brief is in the research brief, "Low-Code Simulation, Modelling & Optimization Tool: Research Brief".

## Changes in this version

2026-11-05, version 0.2, spec review council:

- C27 (PHY-7, PHY-11, PRD-4, PRD-5, PRD-9, PRD-16, PRD-2, PRD-6, PRD-13, PRD-15, PHY-1): version line; people in scope; annex order kept in spec 6 only; what Phase 1 does not do; principles 4 and 6 extended; WSL point resolved as a proposed default; AGPL consequences for users; AGPL only/or-later checkbox; success measures with method and milestone; engine count and six added risks; open items on unresearched domains and the OpenRadioss successor.

2026-11-09, version 0.3, M10 closed (AKS-125):

- 2026-11-09, M10 closed (AKS-125): "Success measures" records what M10 measured for the first four measures (the tester script with the timing left to the owner; the benchmarks; the ten templates on 4 cores within 8 GiB; the assistant trials of the ten templates). The targets stay proposals. Version 0.3.
