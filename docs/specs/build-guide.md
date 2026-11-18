# Build Guide

This tab tells a coding session how to turn the specs into software: where things go, what order to build in, and what to do when a spec is unclear. The repository's `CLAUDE.md` is a short map that points here, so every session starts from it; milestone status is in `docs/STATUS.md` (retrospective P8, 2026-11-14).

## Session rules

1. **Read first.** Before any work, read this guide and the spec for the current milestone.
2. **Two or three milestones per session, in order.** Do not start the next until the current one's acceptance checks pass (owner decision F8, 2026-11-13).
3. **Research before code.** Complete the research items tagged with the current milestone and save one note per item in `docs/research/`.
4. **Tests before implementation.** Write the acceptance checks as failing tests, then make them pass.
5. **Never guess silently; sort before you ask.** If a spec is unclear or seems wrong, sort the question (owner decisions F2, F8 and D18, 2026-11-13, and of 2026-11-14; retrospective P14).
   - **Blocking:** it changes a user-visible answer, the model format, the `/v1` API, a target platform, a guide rule, a milestone or a convention. It should have been asked before the milestone ("Questions before a milestone" below); if it arises during the work, file it as an owner-decision issue with a recommended default and a date, list it under "Awaiting owner", and build only what does not depend on it.
   - **Reversible:** anything else. Take the simplest reading, record it in `docs/DECISIONS.md` (and in the spec with a dated line, rule 6), and list it under "Readings" in the session summary, one line each. Readings are not "Awaiting owner" items; the owner may sample them.
6. **The spec changes before the code does.** A decision that departs from a spec updates the spec file in the same change and adds a dated line under that spec's "Changes in this version" heading; the version number is bumped when a review or a milestone closes with changes to that spec. Sessions never write to the owner's Claude Docs; the repository is the source of truth.
7. **Wrap engines.** Never write a numerical solver: no code that integrates differential equations, solves linear systems or iterates to convergence over a field. If an engine lacks a feature, record it; do not fill the gap with new numerical code. Calculators are allowed: closed-form formulas, published empirical laws and code-based design checks applied to inputs or engine output (Archard wear, stress-life fatigue, JMAK kinetics). Each calculator cites its formula and is tested against a published worked example.
8. **Benchmarks are gates.** A milestone is not done while any benchmark fails.
9. **End with a summary.** State what was built, which checks pass, which decisions were logged, and what is left.
10. **Acceptance rows are the gates.** A milestone's acceptance checks are the rows of the spec acceptance tables tagged with that milestone. Rows marked "owner" are not gates for a coding session: the session lists them under "Awaiting owner" in its summary, and the owner closes each with a dated DECISIONS entry.

## Known gaps to resolve during the build

The specs were written before any product code existed. Each gap below is assigned to the milestone that must close it. A session reaching that milestone resolves the gap first, updates the spec, and logs the outcome in `docs/DECISIONS.md`.

| Gap | Why it exists | Resolve at | How |
| --- | --- | --- | --- |
| Seven process blocks have never run: `queue`, `batch`, `unbatch`, `store`, `resource_pool`, `schedule`, `failure` | The prototype covered only five block types | M4 | Build each with a unit test and a benchmark; correct spec 2 where behaviour proves unclear |
| `weibull` and `empirical` with `values` have never run | Not needed by the three example models | M2 | Add a sampling test for each against its known mean |
| `empirical` with `data` has never run | Needs the import endpoint | M6, with the import endpoint | Add the sampling test against the copied column |
| The optimization layout in the model file has never run | Written from design, not from a prototype | M5 | Run the product mix example first; extend the layout for indexed problems when the transport template needs it. Done: the flat layout ran at M5 (AKS-108, the four optimization benchmarks); the indexed layout (sets and tables, format 0.2) was designed and built for the transport template at M10 (2026-11-09, AKS-123, `benchmarks/transport`) |
| The API, model edits and progress events have never run | No service exists yet | M6 | Treat spec 3 as the starting contract; change the spec, not just the code, where it proves awkward |
| The MCP tools have never run | No server exists yet | M7 | Test with a real assistant; revise tool names, inputs and descriptions from what it gets wrong. Done at M7 (`docs/research/spec-4-mcp-trial-2026-11-08.md`); at M10 the same assistant built and ran each of the ten templates' problems from a text description (`docs/research/mcp/`, 2026-11-09, AKS-125), and two descriptions were revised from what it got wrong |
| Finding thresholds are proposals: 0.85, 0.30 and 10% | Chosen by judgement, checked on one model | M8 (fixtures), M10 (all templates) | M8 checked them on the fixtures and end to end (2026-11-08, AKS-117, AKS-135): unchanged, the three-machine line fires `bottleneck` (weld 0.901) and `not_enough_runs` (wait half-width 13.3%) and the coffee shop neither (till 0.749, 3.7%); they are user-adjustable in `settings.json`. M10 tested them against all ten templates and their exercises (2026-11-09, AKS-125): unchanged, `bottleneck` fires only for the line's weld station, `idle_capacity` for the clinic's treatment rooms (0.215) and the till of the "How many machines?" exercise (0.2495), `not_enough_runs` for the inventory's cycle time (12.6%) and the line exercise's (16.6%); two wordings changed (spec 4 "Finding rules"); owner to confirm |
| Performance targets are proposals | Nothing has been measured on low-tier hardware | Measured at M3, M6, M9; confirmed by the owner before M11 | Measure on the low tier, then confirm or change each target. Measured at M3 (`docs/research/perf-M3.md`), M6 (`perf-M6.md`), M9 (`perf-M9.md`, 2026-11-08, AKS-121: selecting a block on a 200-component canvas paints within the 100 ms proposed) and M10 (`docs/research/performance.md`, 2026-11-09, AKS-125: the ten templates and their exercises run to completion on 4 cores within an 8 GiB memory control group, 20 runs in 37.2 s); all on 4 cores of the agent container, not yet confirmed by the owner on the low tier (AKS-82) |
| Visual and interaction design does not exist | Spec 3 covers behaviour only | Before M9 | Complete the "Design before building" checklist in spec 3; M9 may not start until every item is complete or has its logged fallback. Done: the five session items on 2026-11-06 (AKS-118), the owner review and the walkthrough fallback logged in `docs/DECISIONS.md` the same day (the outside walkthrough was a condition of M10; not done there, it moves to M11 under the owner's fallback of 2026-11-09, B6), and every approved change drawn at M9 (`docs/design/wireframes/README.md`) |
| Interface and service frameworks were not re-checked | Named from general knowledge | M6, M9 | Do the framework check in spec 3's research list before committing. Done: the service half at M6 (FastAPI with uvicorn, `docs/research/spec-3-service-framework-check.md`, AKS-110) and the interface half for M9 (React, React Flow, Tauri 2, `docs/research/spec-3-framework-check.md`, 2026-11-06, re-checked 2026-11-08); the Tauri shell itself was built on Linux at M11, after a re-check on 2026-11-09 (AKS-142, `desktop/`; DECISIONS "Engine gap: Tauri lacks a build in the agent container", closed) |
| Remote and cluster run targets are untested | The prototype ran locally only | Phase 2 (SSH), Phase 4 (Slurm) | Build against a real SSH host and a real Slurm queue, or a local test queue. Moved by the owner on 2026-11-09 (A1): M11 is packaging only, and E172 refuses both targets until each is built |
| Two example files and the prototype were not retained | Never supplied | M1 | Write `three_machine_line.json` and `warehouse.json` fresh to the spec 2 targets. Done: written fresh at M1 (AKS-93); the owner accepted them on 2026-11-09 (B1): the fresh files are the examples, and the originals and the prototype are not needed |
| Block behaviour defaults in spec 2 are council proposals | Unstated before | M4 | Build to them; correct with a DECISIONS entry where a benchmark shows otherwise |
| Item attributes, priority discipline and attribute routing | No block sets attributes | Phase 2 | Design with a block that sets them |
| Engine licences were never checked against AGPL-3.0 | Named from general knowledge | Spec 5 and each annex | Record each in `DECISIONS.md` with the source; apply the spec 1 engine licence rule |
| Specs 5, 6 and 7 are structure only | Detailing them now would mean inventing input formats and behaviours for engines nobody has installed or tested | Before any Phase 2 or 3 code | Do that spec's research items, install and run the engine, then write its detailed specification section |
| Engine assignments in spec 7 are untested | A first mapping from research and general knowledge | Per annex | Confirm each by running the engine on a small case |
| Open material data is scarce | Flow stress curves, transformation diagrams and alloy databases are mostly proprietary | Annexes D and E | Find redistributable sources first; the annex scope follows what data exists |
| Some domains were never researched | Injection moulding, acoustics, lubrication, precipitation in alloys | Before their annex | Research pass, then add to spec 7 |

A rule for all of the above: where a spec section is marked untested, proposed or structure only, the session must not treat it as settled. It verifies, then updates the spec.

## Repository layout

The product is Ithax (owner decision C8); its package, commands and folders are `ithax`, renamed from the working name `lcsim` in M12 (#70).

```text
CLAUDE.md               a map of this guide, under 120 lines (tests/test_docs.py)
AGENTS.md               rules for automated review
.claude/                hooks (settings.json) and skills (skills/<name>/SKILL.md)
LICENSE                 AGPL version 3
docs/
  specs/                the spec tabs, exported as Markdown
  research/             one note per research item
  design/               flows, wireframes, canvas rules, design system, accessibility
  sessions/             one summary per session
  DECISIONS.md          dated log of choices and their reasons
  STATUS.md             milestone status
src/ithax/
  model/                schema, loading, units, validation, edits
  engines/              adapter interface and plugin loading
  engines/process/      SimPy adapter
  engines/optimize/     HiGHS adapter
  runs/                 run targets, job states, results writing, simulation-based search (Optuna)
  service/              the API
  mcp/                  the MCP server
  findings/             finding rules
templates/              template packages
examples/               coffee_shop.json, three_machine_line.json, warehouse.json
benchmarks/             <case>/model.json and expected.json; run by tests/benchmarks/test_benchmarks.py
tests/                  mirrors src/
tests/perf/             performance checks (marker perf)
tests/linux_package/    the Linux package's install checks (marker package)
ui/                     the interface
desktop/                the desktop shell (Tauri 2): src-tauri/ and its own page
packaging/linux/        the Linux package: pinned wheels, licence list, commands, install scripts
scripts/                check.sh and the package build, package_linux.py
```

## Conventions

| Topic | Rule |
| --- | --- |
| Language | Python 3.11 or later for everything except the interface |
| Types | Full type hints; a type checker runs in the checks |
| Tests | pytest, run in parallel by `check.sh` (pytest-xdist, `-n auto`); line and branch coverage of `src/ithax` at or above 99% (`--cov-fail-under`), every public function exercised by at least one test; benchmarks are tests (marker `benchmark`); performance checks carry `perf` and are excluded from `check.sh` |
| Style | One formatter and linter, run before every commit |
| Errors | User-facing problems are spec 1 issue objects with a code; never a bare exception message |
| Units | Quantities are converted at load; no unit strings past the model layer |
| Randomness | Only through the spec 1 stream scheme; never the global random generator |
| Files | Engines write only inside their run folder |
| Dependencies | Each new dependency is recorded in `DECISIONS.md` with its licence |
| Compatibility | A model file that loads in a released version loads in every later version, through migration if its format version is older. A `/v1` request that works keeps working, and a `/v1` response keeps every field it had, with the same JSON type; new fields may be added. A change that cannot meet this needs a new format version with a migration, or a new API version, and an owner decision record. `tests/compat/` checks it: a model corpus that only grows (owner decision F2, 2026-11-13; retrospective P24) |
| Commits | Small, one purpose each; message `M<n>: <imperative summary>`, or `specs: ...` for spec-only commits and `docs: ...` for other documentation-only commits |
| Tracking | GitHub issues are the project tracker, labelled `phase:*` and `type:bug`, `type:feature`, `type:research`, `type:chore` or `type:epic`; each phase is an epic issue and its sub-issues are the work. Linear is retired and kept as read-only history (2026-11-13) |
| Pull requests | Title as a commit message (checked by `.github/workflows/pr-title.yml`); the body follows `.github/pull_request_template.md`, at most about 12 lines: `Closes #<n>` for every issue it closes, Why, What (at most five bullets), Checks and Needs owner. Details go in the issue, `DECISIONS.md` and the session summary. The orchestrating session merges once CI is green and review has nothing open (owner decision C10) |

## Milestones

Build in this order. Each milestone lists what must be true before moving on.

| # | Milestone | Spec | Done when |
| --- | --- | --- | --- |
| M0 | Repository skeleton, checks, licence, specs exported into `docs/specs/` | Guide | Checks run and pass on an empty test |
| M1 | Model schema, loading, units, validation | 1 | `examples/*.json` load with zero issues; one fixture per validation issue code passes `tests/model/test_issues.py`; the migration test passes; `bash scripts/check.sh` passes |
| M2 | Process adapter with `source`, `server`, `delay`, `branch`, `sink` | 2 | The three examples run; every distribution passes the sampling test; the M2 benchmarks (M/M/1, M/M/2, tandem, delay, branch) pass under the spec 2 pass rule |
| M3 | Experiment manager, local run target, results folder | 1, 2 | A run writes the full run folder; a repeat with the same seed is identical as spec 1 defines, also across processes; `docs/research/perf-M3.md` exists |
| M4 | Remaining process blocks and their benchmarks | 2 | Every block has a unit test and appears in a benchmark; the M4 benchmarks pass |
| M5 | Mathematical and simulation-based optimization | 2 | Product mix returns 24, 14 and 2,200; knapsack, assignment and diet pass; the machine-count test finds `tills` = 2 |
| M6 | Engine service and API | 3 | `tests/service/test_routes.py` passes; every endpoint has a request test; a run survives a client disconnect; `docs/research/perf-M6.md` exists |
| M7 | MCP server | 4 | The scripted MCP case passes in CI; a real-assistant transcript meeting spec 4 is in `docs/research/` or listed under Awaiting owner |
| M8 | Finding rules | 4 | Each rule fires on its `_fires` fixture and is silent on its `_silent` fixture |
| M9 | Interface | 3 | `docs/design/` files exist; the owner's walkthrough or logged fallback is in `DECISIONS.md`; the pointer-only end-to-end test passes; `docs/research/perf-M9.md` exists |
| M10 | Templates and Learn mode | 4 | All ten templates reproduce their expected results, each with at least one theory- or benchmark-sourced value; the first four success measures of spec 0 are measured and recorded |
| M11 | Packaging (Linux); idle timeout setting | 3 (and 0) | The service's idle timeout is a setting with a default of 30 minutes; a Linux package installs the interface, the service and the Phase 1 engines, and a fresh install reaches a first template result in under ten minutes in a clean container (agent); the installed app works offline; the unsigned-package note and the checksum are documented. Remote and cluster targets moved to Phases 2 and 4 (A1), the Windows installer deferred (B4) |
| M12 | Phase 1a setup | Guide | Issues #100, #99, #135, #70 and #78 are closed: PR and issue templates and the PR-title check are in place; the package test's shell check no longer fails at random; the retrospective's agent setup is applied, or its conflicting items listed for the owner; the package is `ithax` and the command `ithax-mcp`; Ithax, SimPy and HiGHS report their real versions |
| M13 | Phase 1a correctness | 1, 2, 3, 4 | Issues #69, #72, #73, #74, #75, #76, #77, #79, #80, #81, #84, #85, #86 and #132 are closed, and the two wrong error hints of #83 are fixed; each correctness fix has a fixture or benchmark that fails before it and passes after |
| M14 | Phase 1a data safety, MCP and limits | 1, 3, 4 | Issues #71, #82 and #98 are closed, and #83 with its stale `service.json` |
| M15 | Phase 1a usability | 3, 4 | Issues #87, #89, #90, #91, #92, #93, #94, #95, #96 and #97 are closed |
| M16 | Phase 1a release | 0 to 4 | Issues #88, #101, #102 and #103 are closed: the AppImage builds, the Phase 1 review's changes are in specs 0 to 4, the owner checks are done, and v0.1.0 is tagged |
| M17 | Phase 2 setup and research | Guide, 5 | The retrospective's Phase 2 items are applied, each with the check its proposal names:<br>• one file per decision under `docs/decisions/`, with `docs/DECISIONS.md` frozen (P15);<br>• `model/validation.py` and `model/loading.py` split, a service-protocol module, and the import layers checked by import-linter (P16);<br>• one fault-injection test per supervisor (service, run worker, search) for SIGTERM, SIGINT, a killed child, a failed start, an ignored SIGTERM and a cancel while writing results (P12);<br>• every `while True` names its bound (a conventions test), every wait has a timeout, JSON nesting has a depth limit, and no test synchronises by sleeping (P22);<br>• a scheduled fuzzing workflow running the property tests at length (P23);<br>• a weekly mutation-testing report on `model/` and `strict_json.py`, not gated (P18);<br>• the fix-only stabilisation step in the guide's "Milestones", the maintainer's spec check, and a "Not verified" heading in every PR and summary (P25; the guide text needs the owner, D18);<br>• typed responses: the first routes declare `response_model`, and `ui/src/api/types.ts` is generated and checked in CI (P17; the remaining routes as each Phase 2 milestone touches them, finished in M28).<br>Spec 5's research session, small engine case and council report are done (B9, F3), and spec 5 is detailed for the owner's approval. Research notes exist for D10, D11, MSER-5 against the warm-up check (M3-2), the B1 engine trial (Ipopt or SCIP through Pyomo), the D1 method rule and a noise-aware search (M5-23). |
| M18 | Simulation statistics | 1, 2 | Ranking and selection with fresh-random-number confirmation, chosen by a transparent rule (D1), passes its benchmarks. The noise-aware search replaces "best of N tried" where it applies (M5-23). The warm-up check stays for 0.x (E1, M3-2): the comparison with MSER-5 on the templates is recorded with M17's note, and a replacement would need an owner decision. A `sketch` preview fidelity runs (B7 item 1). A search runs within each scenario (M5-21). |
| M19 | Process constructs | 1, 2, 4 | Each of these has a benchmark with a known answer and a spec 1 format change that only adds:<br>• time-varying arrivals, a source schedule (D10);<br>• reneging, assembly, periodic and order-up-to stock with ordering in multiples, and partial availability (D11; M4-15);<br>• one failure process per unit (D13);<br>• item attributes, priority and attribute routing;<br>• a `<store>.queue_length` metric (M4-20);<br>• overlapping shifts as an error (M4-29).<br>A finding rule judges resource pools (M8-5, M10-67). |
| M20 | Optimization | 1, 2 | Duals are served first (E1: M5-15). A solve stopped with a good solution is `feasible`, with its gap and the `time_limit` and `mip_gap` settings (M5-1, M5-10). Sets take aliases, and bounds and tables per member (M10-30, M10-31). A whole number too large for a float to hold exactly has its own validation code (M5 "Left", AKS-108). Nonlinear and mixed-integer nonlinear models run on the engine M17 chose. Weighted sum, ε-constraint and Pareto search (NSGA-II on simulations) have a trade-off-front view (B1). |
| M21 | Data and interface | 3 | Wider table formats with a progress bar, for example Parquet (D6). The import reads other encodings, delimiters, a sheet choice and non-ASCII names (M6-54, M6-55), and changes a column's unit without importing again (M6-53, M9-61). The Run monitor shows live key numbers and a search's candidates (D4; M6-48, M9-79, M9-80). Indexed models are edited in the Table and Diagram views (D14; M9-56, M10-38). The edits gain removing a field and a setting (M6-28, M9-24), a rename shown as one change (M9-44), and plain words for an edit's paths (M10-53). The interface follow-ups:<br>• a last-edited time on Home (M9-14);<br>• a data event on the project's events, and one session per project shared by its screens (M9-65, M9-66);<br>• the "{n} combinations" line with B6's run count (M9-71);<br>• code splitting for the charts and the bundle size (M9-74, M9-95, M9-105);<br>• sorting, filtering and "Use" in the trials table (M9-81);<br>• the dot strip, the interval-shrinkage chart and the canvas overlay (M9-84);<br>• embedded fonts and charts in the PDF (M9-88);<br>• the shell's capabilities, plugins and folder picker (M11-32);<br>• the palette's filters and sorting (M9 design review, choice 12). |
| M22 | Remote (SSH) run target | 1, 3, 4 | The `remote` target (A1) runs a model on another machine over SSH, tested against a local sshd (spec 1's Phase 2 acceptance row). `run_model` takes a `target` (M7-13). A run-time issue crosses SSH (the M13 command-line worker). E172 no longer refuses `remote`. |
| M23 | Spec 5: system dynamics, agents and chaining | 5 | The `system_dynamics` adapter (PySD, written as XMILE) and the `agent` adapter (Mesa, well mixed), each wrapped, never written, as spec 5 v0.3 specifies them, pass their benchmarks and ship with a template each. A chain of models, a system model feeding a process model, runs from one `chain` file, its members as ordinary runs (#235). |
| M24 | Spec 5: reliability, calculators and workforce | 2, 5 | Life-data fitting, block diagrams and fault trees, and the NIOSH and SPAR-H calculators, each reproduce their published worked examples (#238). The learning curve on `server` and absenteeism on `resource_pool` are spec 2 extensions with benchmarks (#237). Where a calculator's inputs live in a project is decided first (#234, item 6). |
| M25 | Spec 5: physical and multibody models | 5 | The `physical` adapter (OpenModelica, installed on request, builds FMUs that FMPy runs; #236) and the `multibody` adapter (MuJoCo; #231) pass their benchmarks and ship with a template each. A shipped FMU carries the notices of what it contains (#277). |
| M26 | Spec 5: design studies and surrogates | 5 | One study interface runs sweeps, designed experiments, sensitivity, optimization and uncertainty studies over a process model and a physical model alike (#233). Gaussian-process surrogates carry their leave-one-out error and refuse a budget below the larger of 5 runs per input and 10 (#238). Each has its benchmarks. Where studies and surrogates live, and their routes, are decided first (#234, item 6). |
| M27 | Windows through WSL 2 | 0, 3 | A documented install of the Linux package or the AppImage under WSL 2 on Windows (F5; #207) reaches a first template result. It is tested in CI on a WSL runner where one is available; otherwise the same steps are an owner check on a Windows machine. |
| M28 | MCP hardening | 4 | Every Phase 2 feature has its thin API and MCP tool with a parity test (C6). A data import tool exists for assistants that can send files (D15; M7-19). The MCP server runs over Streamable HTTP as well as stdio (M7-1). Every route declares its `response_model` (P17). A trial with a different assistant is recorded under `docs/research/mcp/`. |
| M29 | Phase 2 release | 0 to 5 | Agent walkthroughs in student and business-analyst roles pass (C1). The performance budgets hold (C4). Spec 0's success measures are recorded as baselines; they have no numeric targets before Phase 3 and do not gate this release (#206). The Phase 2 review's changes are in the specs. The owner checks are done, and v0.2.0 is tagged by the owner. |

M17 to M29 are Phase 2. The owner approved M17 to M26 on 2026-11-16 (D18) as `docs/research/phase-2-milestones.md` proposed them, and the split of spec 5's row into M23 to M26, which moved the last three rows to M27 to M29, by the default of #240 on 2026-11-18; that file keeps the readings behind their order and grouping, and `tests/test_phase_2_milestones.py` keeps the two tables equal. As in Phase 1, issues are filed per item, as sub-issues of the Phase 2 epic.

M7 comes before the interface on purpose. Once the service and MCP server exist, the product is usable through an assistant, and that use will expose format problems cheaply.

## Starting material

- **One verbatim example model file**, `examples/coffee_shop.json`, copied from spec 1. The two others were written fresh at M1 to the targets in spec 2, and the owner accepted them on 2026-11-09 (B1).
- **Benchmark answers** in spec 2, recomputed by the review council.

The prototype script was not retained; its numbers in spec 2 are reference values only. Nothing is copied from it and nothing is deleted at M3. If it is ever supplied, it goes in `reference/prototype/` with a not-product-code note and is deleted at the end of M3.

If the real adapter and the prototype's reference values disagree on a result, the specs and the theory values decide which is right, not the prototype.

## Session procedure

- **Research notes.** One file per research item, `docs/research/spec-<n>-<slug>.md`, with the headings Question, Finding, Sources, Decision, Tested.
- **Issues.** Work starts from a GitHub issue; a new issue uses a template in `.github/ISSUE_TEMPLATE/` (bug, feature, research or chore), each with the sections "Why and what", "Done when" and "Source". A session checks each issue it closed on GitHub before it ends.
- **Questions before a milestone.** Before a milestone starts, its session lists every blocking question (rule 5) and files each as a GitHub issue titled "Owner decision: <question>", with the options, a recommended default, what it blocks, and the date on which the default applies if unanswered. Work that depends on an open blocking question is not started; the rest of the milestone proceeds (retrospective P13).
- **Session summary.** `docs/sessions/<yyyy-mm-dd>-M<n>.md` with the headings Built, Checks passing, Decisions logged, Awaiting owner, Readings, Left. "Awaiting owner" holds only blocking questions and owner checks, at most ten, each with its recommended default and the date it applies; "Readings" lists reversible readings, one line each (retrospective P14). The session's last act updates its milestone's row in `docs/STATUS.md`.
- **Owner digest.** At the owner's decision cadence (every two days, owner decision F8) or at a milestone's close, whichever comes first, the orchestrating session sends the owner the open blocking questions, at most ten, each with a one-line recommendation and its default date, and the number of readings since the last digest with a link to them. A default that passes its date unanswered is recorded in `DECISIONS.md` as "default applied". The owner can turn any reading into a question (retrospective P14).
- **Pull requests.** Each PR does one thing and stays under about 400 changed lines of product code (tests, fixtures and docs not counted). A PR whose work depends on another waits for it to merge, or stacks on it one level only. A milestone closes when its last PR merges (retrospective P10).
- **Merge readiness.** Before reporting a PR ready or merging it, the orchestrating session checks on GitHub, for the PR's current head SHA: every check run succeeded (`all-green`); Codex's last review refers to that SHA and no review thread is unresolved; the base is `main` and the PR is not a draft; and no commit was pushed after these were read, or it starts again (retrospective P19).
- **Numbers in the record.** A count or a CI result in a summary, a status line or a decision is copied from the output of a named command or API call (a CI result with its run ID and head SHA), never retyped (retrospective P15, P19).
- **Editing this guide.** Sessions update factual and status rows freely (`docs/STATUS.md`, the "How" column of the known gaps); changes to rules, milestones or conventions are proposed to the owner and made once approved (owner decision D18, 2026-11-13).
- **Review findings.** Reply to each finding with *Fixed in `<sha>`*, *Fixed for the whole class in `<sha>`*, or *Not a defect: `<the spec section or invariant that makes it unreachable>`*. When a review finds a second defect of the same class in one PR, stop patching: find every site of that class in the repository, fix them through one shared helper, add a check that would have caught the next one (a lint rule, a conventions test or a property test), and say so in the reply to the second finding. A class found twice also gets a bullet in `AGENTS.md`'s "Code Review Rules" (owner decision F2, 2026-11-13; retrospective P7).
- **Engine gaps.** A DECISIONS entry "Engine gap: <engine> lacks <feature>" with the workaround and the spec section concerned.
- **DECISIONS entry template.** A date and milestone heading, then Decision, Reason, Alternatives considered, Spec sections updated, Dependencies added (name, version, licence, how checked). This holds through Phase 1a. From Phase 2, each decision is its own record, `docs/decisions/NNNN-<slug>.md` (adapted from MADR's minimal template: Status, Context, Decision, Consequences, Dependencies added with name, version, licence and how checked), with one line in `docs/decisions/README.md`, and `docs/DECISIONS.md` is the frozen Phase 1 log (retrospective P15).
- **Test subsets.** `pytest tests/model`, `pytest -m benchmark`, `pytest -m perf`; `pytest -m package` after `python scripts/package_linux.py` (M11). The full gate is `bash scripts/check.sh`.

## Performance measurement protocol

- Performance checks live in `tests/perf/`, carry the marker `perf`, and are excluded from `check.sh`.
- Run them with `taskset -c 0-3 pytest -m perf`.
- Write wall time, peak RSS (`resource.getrusage`), core count, memory and Python version to `docs/research/perf-M<n>.md`.
- A target is "measured" when that note exists, and "confirmed" when the owner runs the same command on a machine capped to 4 cores and 8 GB and records it in `DECISIONS.md`. Measured closes the milestone for a session.

## Definition of done for any change

- [ ] Acceptance checks for the milestone pass.
- [ ] All benchmarks pass.
- [ ] New behaviour has tests.
- [ ] Specs and `DECISIONS.md` match the code.
- [ ] `tests/test_docs.py` passes (`CLAUDE.md`'s links and the fixtures in sync).
- [ ] The session summary is written.
