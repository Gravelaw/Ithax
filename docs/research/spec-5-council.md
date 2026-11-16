# Spec 5 council: review of the version 0.3 draft

## Question

Is the version 0.3 draft of spec 5 (`docs/specs/5-systems-and-design.md`) correct, lawful, buildable and in scope? This is the council of owner decision F3 (2026-11-13: "an agent council … deliberates and expands each spec … each council report is saved under `docs/research/`") and of M17's row in the Phase 2 table. It was held on 2026-11-16 in the spec 5 research session (#104).

## Finding

**How it was held.** Four reviewer agents worked independently and in parallel, each with one lens. Each read the draft at commit `243b039` (branch `docs/spec-5-v0.3`), the research notes and the repository; none saw another's report or the author's conclusions. Their reports are kept verbatim:

| Lens | Report | Findings |
| --- | --- | --- |
| Correctness of the numbers | `spec-5-council/numbers.md` | 3 errors, 8 inconsistencies, 4 suggestions; about 115 numbers recomputed, every closed form right |
| Licences | `spec-5-council/licences.md` | 2 blocking, 8 should-fix, 10 notes; 15 wheels downloaded and their licence files read |
| Implementability against spec 1 and `src/ithax/` | `spec-5-council/implement.md` | 7 blocking, 16 should-fix, 9 suggestions |
| Scope against spec 0 and the Phase 2 table | `spec-5-council/scope.md` | 6 blocking, 11 should-fix, 3 suggestions |

F3's own lenses (simulation, optimization, computational mechanics, software engineering) are covered across these four. The outside reviewer's draft expansion of specs 5 to 7 that F3 names is held by the owner outside the repository and was not available, so it was not used.

**The council's main conclusions:**

1. Every benchmark value is right. Some pass rules were not backed by a trial, some gates would fail on a new seed, and one benchmark used a time unit the spec does not allow.
2. Several sections marked Specified could not be built as written. Search and studies need a seed. The fidelity label could not name the method. Metric names were undefined. Studies and chaining had no lifecycle. The expression grammar was ambiguous.
3. The libraries proposed for in-process import had no licence record in `docs/DECISIONS.md`. JuPedSim's wheel compiles in GPL code.
4. The draft silently moved scope (workforce, pedestrians), left items without a phase, and had about 20 blocking questions, against the limit of ten.
5. M23 should be split.

**What changed in the draft.** The draft was revised at `d9c70b6` (#241). Three of the changes are general:

- Each section now says Specified, Proposed or Open.
- The blocking questions were grouped into ten owner decisions, #231 to #240.
- Owner questions were kept out of Specified sections.

The disposition of every blocking and should-fix finding:

| Finding | Disposition |
| --- | --- |
| Numbers N1 (MSD tolerance untested) | Accepted: the pass rule now states relative tolerance 1e-8, as the trial ran; OpenModelica's own run is in CI (#228) |
| N2 (predator–prey in years) | Accepted: restated in days with per-day rates; the invariant given for both |
| N3, N4 (SPAR-H) | Accepted: SPAR-H moved to Proposed; the adjustment rule and both printed discrepancies are in #238 |
| N5 (Rosenbrock without a rule) | Accepted: removed from the benchmarks |
| N6 (library-specific rules) | Accepted: Branin and ZDT1 rows name the library, budget and settings |
| N7 (agent SIR gate) | Accepted: 100 replications, mean within 3 standard errors, marked proposed |
| N8 (Ishigami joint gate) | Accepted: each index within 0.05 (trial largest error 0.0079) |
| N9 (chosen inputs, no published example) | Accepted: Rausand Example 4.9 (MTTF 1500) and an availability row added; rows say which inputs were chosen here |
| N10, N11 (labels, pendulum inputs) | Accepted: label examples rewritten; the pendulum row gives the step, length and inertia |
| N12 (door range) | Accepted: the range is given with door widths 1.0 to 2.0 m and the 0.8 m jam |
| N13 (NIOSH margin, load constant) | Partly: the formula-or-table choice is in #238; the metric load constant is left to the calculator's milestone |
| N14 (surrogate warning, E431 tolerance) | Accepted: the warning applies from 20 runs; E431 at a relative 1e-9; the 1e-9 check is on the same library versions |
| N15 (housekeeping) | Accepted: `expected_values.py`'s docstring is corrected in #230 |
| Licences F1 (no licence records) | Accepted: the DECISIONS entry of #241 records SALib, pymoo, moocore, scikit-learn, faultree and dd |
| F2 (JuPedSim's CGAL is GPL) | Accepted: pedestrians proposed for Phase 3, after a legal check (#237); the people-engines note is corrected in #230 |
| F3 (two engines in one domain) | Accepted: `Capabilities.build_tools` proposed (#234) |
| F4 (SPDX identifiers) | Accepted: `LicenseRef-OSMC-PL-1.2`; OpenModelica's GPL text says "GPL version 3", recorded without "-only" |
| F5 (what a shipped FMU contains) | Accepted: listed as a condition before physical systems are specified |
| F6 (dependencies of dependencies) | Accepted as research to do before bundling: listed under "Research before building" and in the DECISIONS entry |
| F7 (what the package bundles) | Accepted: owner decision #236 |
| F8 ("separate process" for an Ithax worker importing EPL or proprietary code) | Recorded for a lawyer: OpenSim and Chrono are not proposed for Phase 2, so nothing depends on it yet |
| F9, F10 (HEART tables; OpenSim's bundled libraries) | Accepted: HEART is in the legal check of #238; OpenSim's bundled licences listed as not yet read |
| Implementability B1 (seed and replications) | Accepted: deterministic domains keep `seed`; `search` stays process-only until #234 |
| B2 (method in the label) | Accepted: `Results.method` proposed (#234); label examples follow spec 1's length rule |
| B3 (metric names) | Accepted: a statistic definitions table, specified for agents and system dynamics, with `metrics_from` |
| B4 (studies have no lifecycle) | Accepted: design studies moved to Proposed, with layout, routes and run time in #234 |
| B5 (chaining) | Accepted: Phase 2 chaining passes scalars only; moved to Proposed (#235); E420 dropped |
| B6 (expressions) | Accepted: grammar with precedence, `$id` parameters, reserved names; `time_unit` top-level |
| B7 (agent randomness) | Accepted: one stream per replication (`@agents`), fixed draw order, competing risks |
| S1 (format 0.4) | Accepted: "the next free minor version" (#234) |
| S2 (parameter units, E401, defaults) | Accepted: parameter `unit`; exact E401; E407; default `record_interval` |
| S3 (W210) | Accepted: not applied to agent runs |
| S4, S5 (catalogues, projects route) | Accepted: listed under "New engine adapters" (#234) |
| S6 (stream key collides with ids) | Accepted: `@study` and `@agents`, outside the identifier pattern |
| S7 (cancel and progress per adapter) | Left to M23: spec 1's rules apply unchanged (a check once a second; progress fractions) |
| S8 (XMILE untried) | Accepted: XMILE is confirmed on the benchmarks first, else `.mdl` |
| S9 (`surrogate` as a label or a fidelity) | Left open in #234 |
| S10 (surrogate leave-one-out and rule 7) | Accepted: computed by refits with scikit-learn |
| S11 (study run time) | Accepted: stated; budgets and time limits in #234 |
| S12 (pymoo against B1) | Accepted: owner decision #233 |
| S13 (calculators without a home) | Accepted: moved to Proposed (#234) |
| S14 (code table) | Accepted: a Pass column; E420 removed |
| S15 (physical systems) | Accepted: the section stays Open with its conditions |
| S16 (acceptance rows) | Accepted: rows say which decisions they wait on; a calculator row added |
| Scope S1 (workforce) | Accepted: Phase 2 by default, in #237 |
| S2 (pedestrians) | Accepted: Phase 3 proposed, in #237 |
| S3, S4 (items without a phase) | Accepted: Phase 3 named for spaces, contacts, conveyors, vehicles, fatigue, skills and co-simulation |
| S5 (3D preview) | Accepted: plots in Phase 2, the preview in Phase 3 (#231) |
| S6 (`/v1`, MCP, interface) | Accepted: a "Service and MCP" section and the M25 row; the interface's canvases are left to each milestone's design step |
| S7 (B1's surrogate-based objective) | Left to M20 and #234: no text yet |
| S8, S9 | As implementability S12 and S1 |
| S10 (templates) | Accepted: one template per adapter, as the Phase 2 table says |
| S11 (split M23) | Accepted as owner decision #240, with the reviewer's four-way split |
| S12 (benchmark milestones, missing rows) | Accepted: a milestone column; performance budgets (C4) are left to M26 |
| S13 (M17 approval wording, remote FMUs, C1 roles) | Accepted |
| S14 (engine changes, `overview.md`) | Accepted for spec 5. `docs/specs/overview.md` still names OpenMDAO and specs 5 to 7 at 0.2; it belongs to the session editing specs 0 to 4 and the overview, so it is reported to the orchestrating session, not edited here |
| S15, S16, S18, S19 | Accepted: owner decisions #232, #236, #238; ten questions in all |
| S20 (F9, F11, F12) | Recorded: F9 and F11 are answered by "Combining engines", "Design studies" and "Surrogate models"; F12 (remote target) by the M22 row |

## Sources

- The four reports under `docs/research/spec-5-council/`, written 2026-11-16.
- The draft at `243b039` and its revision at `d9c70b6`; the research notes `docs/research/spec-5-*.md`; owner decisions B1, B9, C6, D18, F3, F4 and F8 in `docs/DECISIONS.md`; `docs/research/phase-2-milestones.md`.

## Decision

- Fold every accepted finding into spec 5 version 0.3 (#241), as the table says.
- Send ten blocking questions to the owner (#231 to #240), each with a default that applies on 2026-11-18.
- Record the rest as stated: left to a milestone, left to a lawyer, or reported to the orchestrating session.

## Tested

The reviewers ran what each report names, in scratch environments outside the repository:

- the numbers reviewer recomputed the closed forms with scipy, and re-ran PySD's Euler steps;
- the licences reviewer downloaded 15 wheels, checked each SHA-256 against PyPI, and read their licence files without running them.

No engine was run by the council. After the revision, the documentation tests that check specs and DECISIONS passed on #241 (`tests/test_phase_1_review.py`, `test_phase_2_milestones.py`, `test_docs.py`, `test_decisions_append_only.py`: 64 passed).
