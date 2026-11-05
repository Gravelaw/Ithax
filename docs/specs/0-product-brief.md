# Spec 0: Product Brief

Nov 5, 2026 · @Akshay

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

Every domain is in scope: process, systems, and the full range of physics including friction, heat, forming and materials behaviour. "All" still needs an order, because later domains reuse what earlier ones build.

| Phase | Delivers | Specs |
| --- | --- | --- |
| 1 | Process simulation and optimization in a working desktop app, with templates and AI access | 0 to 4 |
| 2 | Agent-based and system dynamics models, physical system models, multibody dynamics, optimization across engines | 5 |
| 3 | Physics platform: geometry, meshing, 3D results, material data, then one solver family at a time | 6, 7 and the annexes |

Proposed order of the Phase 3 annexes:

1. **Structural and thermal**, including contact and friction. Everything after it depends on geometry, meshing and the 3D viewer built here.
2. **Fluid flow**, then coupled heat transfer between fluid and solid.
3. **Explicit dynamics and sheet forming.**
4. **Bulk forming**: forging, extrusion and rolling, with automatic remeshing.
5. **Materials and metallurgy**: microstructure, phase change and heat treatment. Open-source engines for this were not covered in the research and need their own pass.
6. **Particles, electromagnetics and chemical process.**

One correction to the plan as stated. The governing equations are indeed published, but the equations are the small part. Turning them into solvers that are stable, accurate and fast is where the decades of effort in existing engines went. The product wraps those engines and does not re-derive them.

## Product principles

Six rules bind every later spec. A spec that breaks one needs a stated reason.

1. **Wrap engines; do not write solvers.** The product's own code is interface, translation and orchestration.
2. **The model file is the product's core.** The interface, the engines and any AI assistant all read and write the same documented format.
3. **One model, three run targets.** The same file runs on a laptop, a workstation or a cluster.
4. **Say what level of answer the user is getting.** A coarse laptop result is labelled as coarse, never presented as final.
5. **No engine ships without benchmarks.** Each adapter passes a set of problems with known answers before users see it.
6. **Works offline.** Core modelling and solving need no internet connection.

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

- **WSL on user machines.** WSL takes memory and needs installing. Whether low-tier Windows users run the engine service through WSL or receive natively built engines is an open design question.
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

To set before the first outside contribution:

- [ ] Choose a product name and check it is free to register as a trademark.
- [ ] Decide between a per-contribution sign-off and a contributor agreement.
- [ ] Write a short governance note: who can merge, and how decisions are made.

## Success measures

These Phase 1 measures are proposals for you to adjust; none has been agreed.

| Measure | Proposed target |
| --- | --- |
| Time for a new user to run a first template model | Under 30 minutes, with no code written |
| Benchmark accuracy | Every Phase 1 engine adapter passes its full benchmark set |
| Low-tier performance | All Phase 1 templates run to completion on the low-tier laptop |
| Assistant access | An assistant connected through MCP builds and runs each Phase 1 template from a text description |
| Real use | Five people outside the project build a model of their own problem |

## Risks and open items

Four risks could sink the project; each has a response built into the plan.

| Risk | Response |
| --- | --- |
| Scope is far larger than one builder can deliver at once | Phase 1 is a complete, useful product. Later phases add one engine at a time. |
| Simulations that run but give wrong answers | Benchmarks for every adapter; results labelled by fidelity level |
| AI-written code that the owner cannot review in depth | Small specs with acceptance tests; engines do the numerical work |
| Fifteen engines with different formats and failure modes | One engine contract in spec 1; each adapter built and tested alone |

Open items:

- [ ] Confirm the proposed low and mid tier numbers.
- [ ] Confirm the Phase 3 annex order.
- [ ] Research open-source engines for materials and metallurgy, casting, injection moulding, welding, additive manufacturing and acoustics.
- [ ] Confirm which OpenRadioss line to build on.
- [ ] Agree the success measures.

The background for this brief is in the research brief, "Low-Code Simulation, Modelling & Optimization Tool: Research Brief".
