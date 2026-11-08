# Build Guide

This tab tells a coding session how to turn the specs into software: where things go, what order to build in, and what to do when a spec is unclear. Put its content in the repository's `CLAUDE.md` so every session starts from it.

## Session rules

1. **Read first.** Before any work, read this guide and the spec for the current milestone.
2. **One milestone per session.** Do not start the next until the current one's acceptance checks pass.
3. **Research before code.** Complete the research items tagged with the current milestone and save one note per item in `docs/research/`.
4. **Tests before implementation.** Write the acceptance checks as failing tests, then make them pass.
5. **Never guess silently.** If a spec is unclear or seems wrong, stop and ask. If the owner is not available, take the simplest reading, record it in `docs/DECISIONS.md`, and flag it in the session summary.
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
| The optimization layout in the model file has never run | Written from design, not from a prototype | M5 | Run the product mix example first; extend the layout for indexed problems when the transport template needs it |
| The API, model edits and progress events have never run | No service exists yet | M6 | Treat spec 3 as the starting contract; change the spec, not just the code, where it proves awkward |
| The MCP tools have never run | No server exists yet | M7 | Test with a real assistant; revise tool names, inputs and descriptions from what it gets wrong |
| Finding thresholds are proposals: 0.85, 0.30 and 10% | Chosen by judgement, checked on one model | M8 (fixtures), M10 (all templates) | M8 checked them on the fixtures and end to end (2026-11-08, AKS-117, AKS-135): unchanged, the three-machine line fires `bottleneck` (weld 0.901) and `not_enough_runs` (wait half-width 13.3%) and the coffee shop neither (till 0.749, 3.7%); they are user-adjustable in `settings.json`. M10 tests them against all templates; adjust so findings are neither noisy nor silent |
| Performance targets are proposals | Nothing has been measured on low-tier hardware | Measured at M3, M6, M9; confirmed by the owner before M11 | Measure on the low tier, then confirm or change each target |
| Visual and interaction design does not exist | Spec 3 covers behaviour only | Before M9 | Complete the "Design before building" checklist in spec 3; M9 may not start until every item is complete or has its logged fallback |
| Interface and service frameworks were not re-checked | Named from general knowledge | M6, M9 | Do the framework check in spec 3's research list before committing |
| Remote and cluster run targets are untested | The prototype ran locally only | M11 | Build against a real SSH host and a real Slurm queue, or a local test queue |
| Two example files and the prototype were not retained | Never supplied | M1 | Write `three_machine_line.json` and `warehouse.json` fresh to the spec 2 targets (proposed default, owner to confirm) |
| Block behaviour defaults in spec 2 are council proposals | Unstated before | M4 | Build to them; correct with a DECISIONS entry where a benchmark shows otherwise |
| Item attributes, priority discipline and attribute routing | No block sets attributes | Phase 2 | Design with a block that sets them |
| Engine licences were never checked against AGPL-3.0 | Named from general knowledge | Spec 5 and each annex | Record each in `DECISIONS.md` with the source; apply the spec 1 engine licence rule |
| Specs 5, 6 and 7 are structure only | Detailing them now would mean inventing input formats and behaviours for engines nobody has installed or tested | Before any Phase 2 or 3 code | Do that spec's research items, install and run the engine, then write its detailed specification section |
| Engine assignments in spec 7 are untested | A first mapping from research and general knowledge | Per annex | Confirm each by running the engine on a small case |
| Open material data is scarce | Flow stress curves, transformation diagrams and alloy databases are mostly proprietary | Annexes D and E | Find redistributable sources first; the annex scope follows what data exists |
| Some domains were never researched | Injection moulding, acoustics, lubrication, precipitation in alloys | Before their annex | Research pass, then add to spec 7 |

A rule for all of the above: where a spec section is marked untested, proposed or structure only, the session must not treat it as settled. It verifies, then updates the spec.

## Repository layout

The package name `lcsim` is a placeholder until the product is named.

```text
CLAUDE.md               this guide
LICENSE                 AGPL version 3
docs/
  specs/                the spec tabs, exported as Markdown
  research/             one note per research item
  design/               flows, wireframes, canvas rules, design system, accessibility
  sessions/             one summary per session
  DECISIONS.md          dated log of choices and their reasons
src/lcsim/
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
ui/                     the interface
```

## Conventions

| Topic | Rule |
| --- | --- |
| Language | Python 3.11 or later for everything except the interface |
| Types | Full type hints; a type checker runs in the checks |
| Tests | pytest; line coverage of `src/lcsim` at or above 90% (`--cov-fail-under`), every public function exercised by at least one test; benchmarks are tests (marker `benchmark`); performance checks carry `perf` and are excluded from `check.sh` |
| Style | One formatter and linter, run before every commit |
| Errors | User-facing problems are spec 1 issue objects with a code; never a bare exception message |
| Units | Quantities are converted at load; no unit strings past the model layer |
| Randomness | Only through the spec 1 stream scheme; never the global random generator |
| Files | Engines write only inside their run folder |
| Dependencies | Each new dependency is recorded in `DECISIONS.md` with its licence |
| Commits | Small, one purpose each; message `M<n>: <imperative summary>`, or `specs: ...` for spec-only commits |

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
| M11 | Remote and cluster run targets; packaging | 1, 3 | A run completes over SSH and through a Slurm or local test queue; a fresh install reaches a first result on Linux (agent) and Windows (owner) |

M7 comes before the interface on purpose. Once the service and MCP server exist, the product is usable through an assistant, and that use will expose format problems cheaply.

## Starting material

- **One verbatim example model file**, `examples/coffee_shop.json`, copied from spec 1. The two others are written fresh at M1 to the targets in spec 2 (proposed default, owner to confirm).
- **Benchmark answers** in spec 2, recomputed by the review council.

The prototype script was not retained; its numbers in spec 2 are reference values only. Nothing is copied from it and nothing is deleted at M3. If it is ever supplied, it goes in `reference/prototype/` with a not-product-code note and is deleted at the end of M3.

If the real adapter and the prototype's reference values disagree on a result, the specs and the theory values decide which is right, not the prototype.

## Session procedure

- **Research notes.** One file per research item, `docs/research/spec-<n>-<slug>.md`, with the headings Question, Finding, Sources, Decision, Tested.
- **Session summary.** `docs/sessions/<yyyy-mm-dd>-M<n>.md` with the headings Built, Checks passing, Decisions logged, Awaiting owner, Left. The session's last act updates "Current state" in `CLAUDE.md`.
- **Engine gaps.** A DECISIONS entry "Engine gap: <engine> lacks <feature>" with the workaround and the spec section concerned.
- **DECISIONS entry template.** A date and milestone heading, then Decision, Reason, Alternatives considered, Spec sections updated, Dependencies added (name, version, licence, how checked).
- **Test subsets.** `pytest tests/model`, `pytest -m benchmark`, `pytest -m perf`. The full gate is `bash scripts/check.sh`.

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
- [ ] `tests/test_docs.py` passes (guide and fixtures in sync).
- [ ] The session summary is written.
