# Build Guide

This tab tells a coding session how to turn the specs into software: where things go, what order to build in, and what to do when a spec is unclear. Put its content in the repository's `CLAUDE.md` so every session starts from it.

## Session rules

1. **Read first.** Before any work, read this guide and the spec for the current milestone.
2. **One milestone per session.** Do not start the next until the current one's acceptance checks pass.
3. **Research before code.** Complete the spec's "Research before building" items for that milestone and save the note in `docs/research/`.
4. **Tests before implementation.** Write the acceptance checks as failing tests, then make them pass.
5. **Never guess silently.** If a spec is unclear or seems wrong, stop and ask. If the owner is not available, take the simplest reading, record it in `docs/DECISIONS.md`, and flag it in the session summary.
6. **The spec changes before the code does.** A decision that departs from a spec updates the spec file in the same change.
7. **Wrap engines.** Never write a numerical solver. If an engine lacks a feature, record it; do not fill the gap with new numerical code.
8. **Benchmarks are gates.** A milestone is not done while any benchmark fails.
9. **End with a summary.** State what was built, which checks pass, which decisions were logged, and what is left.

## Known gaps to resolve during the build

The specs were written before any product code existed. Each gap below is assigned to the milestone that must close it. A session reaching that milestone resolves the gap first, updates the spec, and logs the outcome in `docs/DECISIONS.md`.

| Gap | Why it exists | Resolve at | How |
| --- | --- | --- | --- |
| Seven process blocks have never run: `queue`, `batch`, `unbatch`, `store`, `resource_pool`, `schedule`, `failure` | The prototype covered only five block types | M4 | Build each with a unit test and a benchmark; correct spec 2 where behaviour proves unclear |
| `weibull` and `empirical` distributions have never run | Not needed by the three example models | M2 | Add a sampling test for each against its known mean |
| The optimization layout in the model file has never run | Written from design, not from a prototype | M5 | Run the product mix example first; extend the layout for indexed problems when the transport template needs it |
| The API, model edits and progress events have never run | No service exists yet | M6 | Treat spec 3 as the starting contract; change the spec, not just the code, where it proves awkward |
| The MCP tools have never run | No server exists yet | M7 | Test with a real assistant; revise tool names, inputs and descriptions from what it gets wrong |
| Finding thresholds are proposals: 0.85, 0.30 and 10% | Chosen by judgement, checked on one model | M8 | Test against all templates; adjust so findings are neither noisy nor silent |
| Performance targets are proposals | Nothing has been measured on low-tier hardware | M3, M6, M9 | Measure on the low tier, then confirm or change each target |
| Visual and interaction design does not exist | Spec 3 covers behaviour only | Before M9 | Complete the "Design before building" checklist in spec 3; M9 may not start without it |
| Interface and service frameworks were not re-checked | Named from general knowledge | M6, M9 | Do the framework check in spec 3's research list before committing |
| Remote and cluster run targets are untested | The prototype ran locally only | M11 | Build against a real SSH host and a real Slurm queue, or a local test queue |
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
  research/             one note per spec
  DECISIONS.md          dated log of choices and their reasons
src/lcsim/
  model/                schema, loading, units, validation, edits
  engines/              adapter interface and plugin loading
  engines/process/      SimPy adapter
  engines/optimize/     HiGHS and Optuna adapters
  runs/                 run targets, job states, results writing
  service/              the API
  mcp/                  the MCP server
  findings/             finding rules
templates/              template packages
examples/               coffee_shop.json, three_machine_line.json, warehouse.json
benchmarks/             benchmark models with their known answers
tests/                  mirrors src/
ui/                     the interface
```

## Conventions

| Topic | Rule |
| --- | --- |
| Language | Python 3.11 or later for everything except the interface |
| Types | Full type hints; a type checker runs in the checks |
| Tests | pytest; every public function has a test; benchmarks are tests |
| Style | One formatter and linter, run before every commit |
| Errors | User-facing problems are spec 1 issue objects with a code; never a bare exception message |
| Units | Quantities are converted at load; no unit strings past the model layer |
| Randomness | Only through the spec 1 stream scheme; never the global random generator |
| Files | Engines write only inside their run folder |
| Dependencies | Each new dependency is recorded in `DECISIONS.md` with its licence |
| Commits | Small, one purpose each, message names the milestone |

## Milestones

Build in this order. Each milestone lists what must be true before moving on.

| # | Milestone | Spec | Done when |
| --- | --- | --- | --- |
| M0 | Repository skeleton, checks, licence, specs exported into `docs/specs/` | Guide | Checks run and pass on an empty test |
| M1 | Model schema, loading, units, validation | 1 | The three example files load; each issue code has a test file that triggers it |
| M2 | Process adapter with `source`, `server`, `delay`, `branch`, `sink` | 2 | The three examples run; M/M/1 and M/M/2 benchmarks pass |
| M3 | Experiment manager, local run target, results folder | 1, 2 | A run writes the full run folder; a repeat with the same seed is identical; the prototype folder is deleted |
| M4 | Remaining process blocks and their benchmarks | 2 | Every block has a unit test and appears in a benchmark |
| M5 | Mathematical and simulation-based optimization | 2 | Product mix returns 24, 14 and 2,200; the machine-count test finds the known best |
| M6 | Engine service and API | 3 | Every endpoint has a test; a run survives a client disconnect |
| M7 | MCP server | 4 | An assistant builds and runs the coffee shop model from a description |
| M8 | Finding rules | 4 | Each rule fires and stays silent on its test models |
| M9 | Interface | 3 | The design checklist is complete; the coffee shop model is built by mouse alone |
| M10 | Templates and Learn mode | 4 | All ten templates reproduce their expected results |
| M11 | Remote and cluster run targets; packaging | 1, 3 | A run completes over SSH; a fresh install reaches a first result |

M7 comes before the interface on purpose. Once the service and MCP server exist, the product is usable through an assistant, and that use will expose format problems cheaply.

## Starting material

- **Three example model files** that already ran in a prototype. They are the first test fixtures for M1 and M2.
- **A prototype translator** of about 100 lines. Reference only; see the rules below.
- **Benchmark answers** in spec 2.

### The prototype is a reference only

The script `proto.py` exists to show that the model format works. It is not the start of the product.

- **Do not copy it into `src/`,** extend it, or import from it. Product code is written fresh against specs 1 and 2, with tests.
- **What it is good for:** reading how a model file maps to a simulation, and reproducing the benchmark numbers in spec 2.
- **What it lacks:** schema validation, issue codes, real units handling, seven of the twelve blocks, two distributions, scenarios, the results folder, and any error handling. It also hard-codes the statistics table value for 30 replications.
- **Where it lives:** outside the package, in `reference/prototype/`, with a note at the top of the file saying it is not product code.
- **When it is cleared:** delete `reference/prototype/` at the end of M3, once the real adapter runs the three examples, passes both queue benchmarks and repeats exactly with the same seed. Record the deletion in `docs/DECISIONS.md`.
- **What stays:** the three example model files. They move to `examples/` and remain as test fixtures.

If the real adapter and the prototype disagree on a result, the specs and the theory values decide which is right, not the prototype.

## Definition of done for any change

- [ ] Acceptance checks for the milestone pass.
- [ ] All benchmarks pass.
- [ ] New behaviour has tests.
- [ ] Specs and `DECISIONS.md` match the code.
- [ ] The session summary is written.
