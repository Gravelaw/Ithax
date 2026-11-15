# Phase 1 review: the changes to fold into specs 0 to 4

The checklist of #101, surveyed on 2026-11-15 at `main` c864cb9. This is the draft the owner approves (2026-11-09 B2; C10); the spec edits follow it, one PR per spec, each with a dated line and a version bump. Line numbers are those of c864cb9. Issue #101 ("Phase 1 review: fold accepted changes into specs 0 to 4", AKS-130); guide M16 row (build-guide.md line 125): "the Phase 1 review's changes are in specs 0 to 4".

Sources:
- **Explicit deferrals** found with `grep -n "Phase 1 review"` and `grep -n "AKS-130"` over specs 0 to 4 and overview.md: spec 0 lines 60 and 188; spec 3 lines 7, 23, 73, 148 (AKS-130), 318 and 332; overview line 40. Specs 1, 2 and 4 have none. DECISIONS.md 2026-11-09 adds four more deferrals that are not in the spec text: B2 (draft-and-approve step), B3 (block defaults wording in spec 2; walkthrough timing), B4 (Windows phase), and "B7 items 2, 4 and 5; B8; Parts C, D and E stay open for the Phase 1 review" (line 1978).
- **Decisions** in DECISIONS.md "2026-11-13 · Owner decisions on the Phase 1 decision list (Parts B to F)" (line 2316), B1 to F8, plus the 2026-11-15 owner decisions (line 3257), item 3 on Windows (#106).
- **The full sweep** (review of pull request 208, which found two decisions whose later-phase part was missing): every DECISIONS entry through 2026-11-15, every session summary's "Awaiting owner" list, and every line of specs 0 to 4 and the overview that says "owner question", "deferred", "Phase 1 review", "later phase", "stays open" or names Phase 2, 3 or 4. Each one found is in "Coverage" at the end, which `tests/test_phase_1_review.py` checks.
- The 2026-11-13 entry says: "Spec sections are not edited here: the Phase 1 review (AKS-130) drafts them, as decided on 2026-11-09 (B2)." So every "change needed" row is drafted for owner approval, not written straight to the specs (2026-11-09 B2; C10).

Status words: **already in spec** (built in M12 to M15 and the spec text updated; do not redo); **change needed** (the decision is settled, the text is not); **needs owner** (cannot be written without a number or choice; listed again at the end).

Out of scope here but worth noting: "owner to confirm" appears 1 / 70 / 66 / 72 / 32 times in specs 0 / 1 / 2 / 3 / 4 (`grep -c`). E1 accepts the build's readings "as built ... as the current behaviour of format 0.x (not frozen)", so the review may choose to sweep the E1-covered ones. This survey does not list them one by one.

## Spec 0 (product brief, version 0.4)

| Source | Current spec text | Needed change | Status |
| --- | --- | --- | --- |
| Deferred to review, line 60 (B4 2026-11-09) | 60: "A Windows version follows, deferred until the Phase 1 review sets its phase; the code stays platform-neutral meanwhile." | Say the Windows version is Phase 2 (F5), unsigned installer with SmartScreen note and checksum at first (2026-11-15 item 3). | change needed |
| Deferred to review, line 188 (change log) | 188: "...the Windows version and its WSL point deferred until the Phase 1 review..." | History line; leave it and add a new dated line for the review. | no change (history) |
| 2026-11-09 B2 | 5: "working copy in the repository (source of truth, owner to confirm)" | Drop "owner to confirm": the repository is the source of truth (B2 2026-11-09). Same in specs 1 to 4 line 3 and overview line 7. | change needed |
| C8 | 13: "The working title is not yet chosen." | The product is Ithax; the trademark and name-clash search comes before any public release. | change needed |
| F1, C4, B1, B5, F5, C3, D-items, F7 | 34-39: phases table has rows 1, 2, 3, 4 only; row 2 (37) "Agent-based and system dynamics models, ...; the remote (SSH) run target" | Add Phase 1a (F1: everything not assigned to 2, 3 or 4; order correctness, data safety, usability; v0.1.0 after the first two) and Phase 3a (C4, performance; F6 low/mid optimization) between 3 and 4. Phase 2 adds: objective types and multi-objective (B1), Windows installer (B5, F5), and the D-items moved there (D1, D4, D6 tables, D10, D11 part, D13, D14, D15; E1 M5-1/M5-10, M5-15, M3-2). Phase 3 adds: template expansion (2026-11-09 B7 item 3), 3D/field import (D6), D11 rest, three-tester timing (C3). Phase 4 adds: graphics detection on Windows and macOS (D7), further multi-objective methods (B1); "no outside contributors until Phase 4 is complete" (C9). | change needed |
| F1, F7 | 43: "What Phase 1 does not do. ... Phase 1 runs on the user's own machine only..." | Add that Phase 1 closes as Phase 1a with release v0.1.0 (F7); the owner tags it (2026-11-15 item 2). | change needed |
| F7 (absent) | No release or versioning text in spec 0 | Add: semantic versions with a changelog; v0.1.0 after Phase 1a correctness and data safety; model format and `/v1` API change only additively within 0.x. | change needed |
| F5 | 65: "Desktop interface \| Linux; a Windows version is deferred (B4)" | "Linux; Windows in Phase 2 (F5)". | change needed |
| F6 | 67: "Nvidia or Intel graphics speed up viewing and some solvers when present" | Add: GPU speed comes from engines that support it or upstream work, never solver code written here (F6). | change needed |
| B3, F6 | 73-74: Low and Mid tiers "Proposed; tested by limiting WSL"; 168: "[ ] Confirm the proposed low and mid tier numbers." | The hardware table is settled after the Phase 3 engine work (B3); low- and mid-tier optimization is Phase 3a (F6). Reword the open item; numbers stay proposals. | change needed |
| Deferred with Windows (B4), line 82 | 82: "WSL on user machines. Resolved as a proposed default in spec 3: the Windows version runs natively ... Owner to confirm." | Phase is Phase 2 (F5). Native versus WSL is not decided by F5 or #106. | needs owner choice |
| B4 and C7 | 98: "released under AGPL version 3" | "AGPL-3.0-only" (B4/C7), and add the Help "Open source licences" page generated from the package's licence list. | change needed |
| F4 | 117: "Engines keep their own licences. Phase 1 engines are MIT or BSD ... a licence that forbids wrapping is a reason not to adopt" | Add F4: engines run as separate processes exchanging files, so GPL-2.0-only engines such as CalculiX are usable; engine code is never copied or linked; the licences page cites each engine and its authors; further legal review deferred. | change needed |
| C8 | 121: "[ ] Choose a product name and check it is free to register as a trademark." | Name chosen (Ithax); keep the box for the trademark search before public release. | change needed |
| C9, C10 | 122: "[ ] Decide between a per-contribution sign-off and a contributor agreement." 123: "[ ] Write a short governance note: who can merge..." | No outside pull requests or contributors until Phase 4 is complete (C9), so 122 moves to "before Phase 4 ends"; 123 can state C10 (the orchestrating session merges, never with red or not-running CI). | change needed |
| B4 and C7 | 124: "[ ] Decide AGPL-3.0-only or AGPL-3.0-or-later" | Decided: AGPL-3.0-only; "or later" revisited before outside contributions open (C9). | change needed |
| B2 | 128: "These Phase 1 measures are proposals for you to adjust; none has been agreed." 130-136: five-row table | Replace with B2's six criteria (functionality and flow; correctness against open datasets; cognitive load in agent walkthroughs; MCP parity; app speed; run speed and parallelism), each with a numeric target set at this review. | needs owner number |
| C3, C1 | 132: "Three outside testers timed from installer to Results ... \| M10" | Three testers' time to a first template run moves to Phase 3 (C3); walkthroughs are by agents in roles as a gate every phase, plus one or two people at v0.1.0 (C1, C2). | change needed |
| C6 | 91: "The same API serves scripts." (AI access, 85-94) | Add C6: each feature ships with a thin API and MCP tool and a parity test; the last or second-to-last milestone of every phase is MCP hardening plus a trial with a different assistant. | change needed |
| 2026-11-09 B7 item 4 (deferred) | 151: "Ten risks ... The last six were added by the review of 2026-11-05 and are proposals." | Not answered on 2026-11-13; the default was "accept as proposals". | needs owner choice |
| B5, 2026-11-15 item 3 | 163: "Budget for code signing before the first Windows release; until then, and for the Phase 1 Linux package, document the warning and the checksum (proposed)" | Windows ships unsigned with a SmartScreen note and a checksum for now; signing is decided before the public launch (B5, #106). Drop "(proposed)". | change needed |
| B2 | 172: "[ ] Agree the success measures." | Tick once the six targets are set. | needs owner number |

Count: 23 rows: 19 change needed, 4 needs owner (82, 128, 151, 172), 1 history line. Nothing in spec 0 is already updated for the 2026-11-13 decisions.

## Spec 1 (model format, version 1.6)

| Source | Current spec text | Needed change | Status |
| --- | --- | --- | --- |
| 2026-11-09 B2 | 3: "(source of truth, owner to confirm)" | Drop "owner to confirm". | change needed |
| F4, B4/C7 | 94: "The product is AGPL-3.0. An adapter drives its engine as a separate process ... Proposed default, owner to confirm." | "AGPL-3.0-only"; state F4: separate processes make GPL-2.0-only engines usable, engine code is never copied or linked; drop "Proposed default, owner to confirm"; keep the lawyer sentence, since F4 defers further legal review. | change needed |
| F7, E1 | 130: "A minor increase is additive ... A major increase ships a migration" | Add: within 0.x the format changes only additively (F7), and 0.x behaviour is accepted as current, not frozen (E1). | change needed |
| F7, C8, M11-51 | 92: "The product's version follows owner decision F7: semantic versions, written to PEP 440 in the package (`0.1.0.dev0` until v0.1.0 is tagged)"; group `ithax.engines` | Done in M12 (#78, #70). | already in spec |
| B1 | 256: "`search.objective` (required) names an id in top-level `objectives` (exactly one in Phase 1)" | Note that several objectives (weighted sum, ε-constraint, Pareto) come in Phase 2 (B1), additively. | change needed |
| E1 M1-7 | 196: "Phase 1 rate units (format 0.3, #77) ... `1/s`, `1/min`, `1/h`, `1/d`"; 130: "This reader is version 0.3" | Done M13 (#77). | already in spec |
| E1 M2-1, M1-9 | 226: "W202 warns when more than 1% of samples are below zero (`mean` < 2.326 × `sd`)"; 231: "a `constant` `value` and a `uniform` or `triangular` `min` are not below zero (#69)" | Done M13 (#69). | already in spec |
| E1 M2-5, M4-14 | 339: "E196 \| run \| A run stopped because more than 1,000,000 events happened at one instant" | Done M13 (#74). | already in spec |
| E1 M4-39, M4-40 | 341: W201 "...its mean available capacity (its capacity, or under a schedule or failure its time average)...; or the servers that use a pool together need..." | Done M13 (#73). | already in spec |
| D13, E1 M4-34 | 343: "W203 ... (#84; D13, M4-34; one failure per unit is planned for Phase 2)" | Done M13 (#84). | already in spec |
| D2 | 322: "E179 \| meaning \| An `optimization` model with nothing to decide ... A new optimization project starts this way and shows the issue until a variable is added" | Done M13 (#80). Note: D2 says "shows as a tooltip warning"; it was built as an error code shown with a warning mark (spec 3 line 264). | already in spec (reading to confirm, see end) |
| E1 M5-1, M5-10 | 333: "E190 \| run \| Engine exited with an error" | Note that a solve stopped with a good solution becomes a `feasible` status with the gap in Phase 2, not E190 (main text in spec 2). | change needed |
| A1 (2026-11-09) | 113: "The `remote` target is built in Phase 2 and the `cluster` target in Phase 4" | Done at M11. | already in spec |
| 2026-11-09 B7 item 2 | (absent) weighted-sum objectives naming parameters | Answered on 2026-11-13 by B1 (weighted sum is Phase 2); covered by the line 256 row. | change needed (with 256) |

Count: 14 rows: 6 change needed (one of them folded into another), 8 already in spec (one with a reading to confirm). No explicit "Phase 1 review" deferral in spec 1.

## Spec 2 (core engine, version 1.1)

| Source | Current spec text | Needed change | Status |
| --- | --- | --- | --- |
| 2026-11-09 B2 | 3: "(source of truth, owner to confirm)" | Drop "owner to confirm". | change needed |
| Deferred to review: 2026-11-09 B3 ("Spec 2's 'proposed' wording for the block defaults changes at the Phase 1 review") | 122: "The council's proposed defaults above are built as written ...; all remain owner to confirm (AKS-76)." Also 101, 107 "Proposed default (AKS-99), owner to confirm" | Block defaults are confirmed for Phase 1 (B3), to be tested again in the agent walkthroughs that are a gate every phase (C1) and reworked if needed. | change needed |
| B1 | 44-51: Optimization table "Mathematical ... HiGHS through Pyomo"; "Simulation-based ... Optuna"; 276: "Phase 1 supports linear objectives and constraints only." | Add the Phase 2 objective types: nonlinear and MINLP after an engine trial (Ipopt or SCIP through Pyomo), black-box via metaheuristics or surrogates; weighted sum, ε-constraint, Pareto (NSGA-II preferred on simulations) with a trade-off-front view; more methods in Phase 4. | change needed |
| D1; 2026-11-07 item 7 | 347: "no ranking-and-selection procedure replaces it in Phase 1 (KN with common random numbers and Batur and Kim's feasibility check are the Phase 2 candidate, owner to confirm)" | Phase 2, early, with fresh-random-number confirmation; the method is chosen by a transparent rule from the problem's features (D1), which settles item 7's "score or vote" as a rule. | change needed |
| E1 M3-2 | 155: "Warm-up check (kept over MSER-5 ...; the 99% level and the 5% threshold are proposed defaults, owner to confirm)" | Kept for 0.x; a Phase 2 research item compares it with MSER-5 on the templates. | change needed |
| E1 M5-1, M5-10 | 329: "Any other ending ... has no `status` of the three, so the run fails with E190" | Phase 2: a `feasible` status with the gap, and `time_limit` and `mip_gap` settings, instead of E190 for a solve stopped with a good solution. | change needed |
| E1 M5-15 | 334: "**Duals.** `summary.json` holds no duals." | Duals are served as the first Phase 2 optimization item. | change needed |
| D10, D11 | 95: "Item attributes, the `attribute` rule and priority disciplines are deferred to Phase 2 (see spec 1)." | Add: time-varying arrivals (D10), leaving the queue, assembly, periodic stock policies and partial availability (D11) in Phase 2; probabilistic calendars and multitasking in Phase 3; each after research. | change needed |
| D13 | 110: "**Failure.** One `failure` block is one alternating process on its target ... So at most one unit of the target is failed at a time" | Cross-reference W203 (spec 1 line 343) and say one failure process per unit is Phase 2. | change needed |
| B3 / C1 / research | 367-376: research list holds M2 to M5 items only | Add the Phase 2 research items: D10, D11, MSER-5 (M3-2), the B1 engine trial, the D1 method rule, the noise-aware search method (M5-23). | change needed |
| B6 | 41: "Scenarios: named sets of parameter values"; 42: "Parallel runs: replications use all available processor cores." | "No cap" can be said here (B6); parallel to the core count is already line 42. The run-count, time-estimate and search-suggestion parts belong to spec 3. | change needed (one clause) |
| D12, E1 M4-17 | 89: "When the inventory position (stock on hand plus on order minus the items waiting for stock) falls to `reorder_point`" | Done M13. | already in spec |
| E1 M2-5, M4-14 | 103: "stops the run with E196 (spec 1) when more than 1,000,000 happen at one instant" | Done M13. | already in spec |
| E1 M2-7 | 249: "both files are gated on that theory: ... 300 replications ... within 2 standard errors ... holds them to ... 3 standard errors"; 385 acceptance row (M13) | Done M13 (#75). | already in spec |
| E1 M5-12 | 330: "an `integer` or `binary` variable is reported rounded to its whole number, and any other number within 64 units in the last place..." | Done M13 (#76). | already in spec |
| E1 M5-23, first part | 358: "An Optuna search's best is the best of those tried, not a proven optimum, and the findings and the Results screen say so (#85, M5-23)" | The label: done M13 (#85). | already in spec |
| E1 M5-23, second part | 358 (as above); nothing in spec 2 names a noise-aware method | Add that a noise-aware method for a `number` or `quantity` search, which handles the simulation's noise, is Phase 2 (E1 M5-23); until then the label stands. Listed with the research items too. | change needed |
| 2026-11-09 B7 item 1 | 365: "Phase 1 accepts `standard` only; `summary.json` carries `fidelity_label`. A `sketch` preview level is an owner question." | Answered: a `sketch` preview fidelity for process runs is Phase 2 (B7 item 1); Phase 1 accepts `standard` only. | change needed |
| D10; E1 (M4-1) | 18: "\| Source \| Arrivals, by distribution or from a schedule \|" | The block reference gives a source no schedule, so the summary is wrong for Phase 1 (M4 item 1): "Arrivals by distribution; time-varying arrivals (a source schedule) in Phase 2 (D10)". | change needed |

Count: 19 rows: 14 change needed, 5 already in spec. One explicit deferral, from DECISIONS (B3). The spec text holds one open owner question (365, `sketch`, answered by B7 item 1) and one "Phase 2 candidate" (347, D1).

## Spec 3 (desktop app, version 1.0)

| Source | Current spec text | Needed change | Status |
| --- | --- | --- | --- |
| 2026-11-09 B2 | 3: "(source of truth, owner to confirm)" | Drop "owner to confirm". | change needed |
| Deferred to review, line 7 | 7: "the Windows installer is deferred (owner decision B4, 2026-11-09), its phase set at the Phase 1 review" | "the Windows installer is Phase 2 (F5)". | change needed |
| Deferred to review, line 23 | 23: "the Windows version is deferred, and the Phase 1 review sets its phase. When it comes, both parts run natively on Windows (proposed default from the review, owner to confirm)... A WSL path is added in Phase 3" | Phase 2 (F5). Native versus WSL is still an owner choice. | change needed + needs owner choice |
| Deferred to review, line 73; B5; 2026-11-15 item 3 | 73: "**Windows:** deferred ...; the Phase 1 review sets its phase. When built: one installer ... (proposed default); alternative, an installer plus a prepared WSL image." | Phase 2; one installer, unsigned at first with a SmartScreen note and a checksum; signing decided before the public launch (B5: "a code-signing decision before the Windows release"). | change needed (installer form follows the native/WSL choice) |
| Deferred to review, line 318 | 318: "Deferred with Windows ..., only if the owner keeps WSL · WSL distribution ... Its phase is set with the Windows version's at the Phase 1 review." | Phase 2 with Windows if WSL is kept; dropped otherwise. | needs owner choice |
| Deferred to review, line 332 | 332: "Fresh install to first result under ten minutes on Windows \| Deferred (owner decision B4, 2026-11-09); the Phase 1 review sets its phase" | Milestone "Phase 2 (F5)". | change needed |
| AKS-130, line 148; D2 | 148: "which also validates with no errors under spec 1 as it stands (the owner's M5 decision to make a model with no variables an error is Phase 1a, AKS-130, and will need this default revisited)" | Stale: E179 was built at M13 (#80, spec 1 line 322). Say the new optimization project starts empty and shows E179 (as line 264 and the change line 411 already say). | change needed |
| B5 | 68: "a self-contained archive `ithax-<version>-linux-x86_64.tar.gz`" (no AppImage anywhere in the spec) | Add the AppImage as the Phase 1a Linux package (with #88, M16), keeping or retiring the archive. | change needed (with #88) |
| D4 | 48: "5. **Run monitor:** progress, live key numbers, cancel."; 274: "Live key numbers are not shown: no Phase 1 adapter sends `metrics` events" | Line 48 should say live key numbers are Phase 2 (D4). | change needed |
| D6 | 46: "3. **Data:** import CSV or Excel, map columns, fit a distribution to a column." | Add: wider formats with a progress bar, efficient table formats (for example Parquet) in Phase 2, 3D and field formats (STEP, VTK, HDF5) in Phase 3. | change needed |
| D5 | 156: "The request may be at most 64 MiB plus 64 KiB ... at most 512 MiB unpacked" | Keep (D5). | already in spec |
| D7 | 64: "`graphics` ... read from `/sys/class/drm` on Linux, and is `null` where it cannot be read (Windows and macOS until the interface needs it)" | "Windows and macOS until Phase 4 (D7)". | change needed |
| D14 | 264: "a notice says the plan is indexed and that its sets, tables and terms are changed in the model file or by an assistant, not i[n the views]" | Add: editing indexed models in the Table and Diagram views is Phase 2 (D14). | change needed |
| B6 | 47: "4. **Experiment:** run length, replications, scenarios, optimization setup." (no run count or estimate) | Add: before a run, show the run count (scenarios × replications) and an estimated time; run in parallel up to the core count; past a threshold suggest a `search`; a research note compares AnyLogic, Simio, FlexSim and open frameworks. | change needed; threshold needs owner number |
| C4, F6 | 280: "All proposed, to be measured on the low tier" (281-285 four targets) | Add: every phase keeps cheap performance budgets and regression checks; the dedicated performance work is Phase 3a; low/mid-tier optimization Phase 3a (F6). Targets stay proposals until B2 measure 5 is numbered. | change needed (numbers: see B2) |
| B3, F6 | 58-63: "Hardware tiers ... Low and mid tiers are tested on a machine, container or virtual machine capped to the tier" | Note that the tier table is settled after the Phase 3 engine work (B3). | change needed |
| C5 | 301: "[x] A check against accessibility guidelines: keyboard use, contrast, text size"; 325: "A pointer-only end-to-end test" | Add: mouse-first for now; the keyboard support built is kept, new keyboard work is deferred (C5). | change needed |
| C1, C2 | 303-311: "[ ] A walkthrough of the wireframes with at least one student and one business user, both outside the project..." | Walkthroughs are done by agents in assigned roles as a gate in every phase, plus one or two people at v0.1.0; the box can name that instead. | change needed |
| F7 (absent) | API section (98-170) has no compatibility rule | Add: the `/v1` API changes only additively within 0.x (F7); `tests/compat/` enforces it (CLAUDE.md). | change needed |
| D8 | 90: "`idle_timeout_minutes` ... a whole number from 1 to 10,080 ..., default 30, or 0, which means 'never exit'"; 276: "entered in minutes, hours or days with a 'Never' box that writes 0" | Done M15 (#87). | already in spec |
| D3, E1 M6-34 | 94: "the service writes a commit record, `.ithax-commit.json`, beside them; that write is the commit" | Done M14 (#71). | already in spec |
| B4, C7, F4 | 50: Help "holds 'Open source licences' ... generated from the package's licence list ... (#89; owner decisions B4, C7 and F4, 2026-11-13)"; 108 and 143: `GET /v1/licences`, "(Ithax, AGPL-3.0-only, its repository)" | Done M15 (#89). | already in spec |
| C8 | 69: "`ithax-<version>-linux-x86_64/`"; 71: "`ithax` starts the app ... `ithax-mcp` is the MCP server"; 84: `lcsim` folders read while no `ithax` one exists | Done M12 (#70). | already in spec |
| D17 | 164: "`GET .../summary`: `{summary, findings, issues}`" | Keep (D17). | already in spec |
| Deferred with Windows (B4), line 87 | 87: "built and tested on Linux (the Windows build is deferred with the Windows version, owner decision B4)" | The shell's Windows build (WebView2) is Phase 2 with the Windows version (F5). | change needed |
| Incidental (no decision) | 325: "a new project is written at the reader's version, 0.2 since AKS-123" | Format is 0.3 since #77 (spec 1 line 130). Fix while editing. | change needed (stale fact) |

Count: 26 rows: 18 change needed (two of them also need an owner choice or number), 1 needs owner choice only (318), 6 already in spec, 1 stale fact. Six explicit Phase 1 review deferrals, one AKS-130, and the shell's Windows build deferred with Windows (87).

## Spec 4 (content and AI, version 0.9)

| Source | Current spec text | Needed change | Status |
| --- | --- | --- | --- |
| 2026-11-09 B2 | 3: "(source of truth, owner to confirm)" | Drop "owner to confirm". | change needed |
| 2026-11-09 B7 item 3 | 16-29: ten-row template table; 31: "Phase 1 covers machines and people as resources..." | Add: Phase 1 keeps its ten templates; an eleventh (forklift/AGV transport) and template expansion in general are Phase 3. | change needed |
| C6 | 63-89: MCP tool table and "Rules for assistant access" (four rules); 7: "other assistants may still find names, inputs or descriptions to change" | Add the rule: each feature ships with a thin API and MCP tool and a parity test; the last or second-to-last milestone of every phase is MCP hardening plus a trial with a different assistant. | change needed |
| D15 | 261: "No data import tool (AKS-134). An assistant has no file to send, so the MCP server has no tool for the data endpoints" | Add: data import through the assistant is Phase 2 (D15). | change needed |
| C1, C2 | 289: "A first-time user completes one Learn walkthrough without outside help (one outside tester; fallback as in spec 3) \| M10 \| owner" | Agents in student and business-analyst roles as a gate every phase, plus one or two people at v0.1.0. | change needed |
| C6 | 293: "A real-assistant transcript meets the acceptance case \| M7 \| owner, or agent..." | Add a per-phase row for the different-assistant trial. | change needed |
| D16 | 58: "Not enough runs \| A confidence interval ... too wide to separate two scenarios" | Keep (D16). | already in spec |
| D9 | 122: "`length` 210 h including 10 h of warm-up, so 200 h measured (#86)"; 267 and 271 | Done M13 (#86). | already in spec |
| B4, C7 | 118: "each problem written for this project (`AGPL-3.0-only`...)" | Already AGPL-3.0-only. | already in spec |
| E1 M5-23 | 213 `optimization_result`; 338 change line: "the Results screen says 'Best of N tried, not proven'" | Done M13 (#85). | already in spec |
| C8 | 109: "the loader is `ithax.templates`"; 245, 247: `python -m ithax.service` | Done M12 (#70). | already in spec |

Count: 11 rows: 6 change needed, 5 already in spec. No explicit Phase 1 review deferral in spec 4.

## overview.md

| Source | Current spec text | Needed change | Status |
| --- | --- | --- | --- |
| 2026-11-09 B2 | 7: "The repository copy is the source of truth (owner to confirm)"; also "specs 1 to 4 are at 1.6, 1.1, 1.0 and 0.9 after M13" | Drop "owner to confirm"; update the version numbers after the review bumps them. | change needed |
| Deferred to review, line 40 | 40: "The owner chose Linux first on 2026-11-09 (B4): the Windows version is deferred, its phase set at the Phase 1 review" | "Windows in Phase 2 (F5)"; the "natively ... (proposed default after review)" part follows the native/WSL choice. | change needed + needs owner choice |
| F1, C4, F3 | 9-17: "Phase" column 1, 1, 1, 1, 2, 3, 3 | Specs 1 to 4 are Phase 1, closed as Phase 1a; F3 puts new items from specs 5 to 7 in Phase 3, 3a or 4. Phases 1a and 3a can be named. | change needed |
| 2026-11-09 B9, F3 | 50: "Specs 5 to 7 set structure only ... Each gets its detailed pass after its research items are done." | Add F3: one research session per spec, a small engine case first, an agent council expands each spec, reports under `docs/research/`. | change needed |
| C4 | 52: "Performance targets are proposals." | Add Phase 3a and the per-phase budgets (C4). | change needed |
| Incidental (no decision) | 49: "Only a prototype has been run ... The API, the MCP tools, the optimization layout and the other seven blocks are specified but have never run." | Stale since M2 to M11; rewrite as built. | change needed (stale fact) |

Count: 6 rows: 6 change needed (one also needs an owner choice).

## Decisions with no spec 0 to 4 target

B3 and F6 are only noted (rows above). C10, D18, F2 and F8 are governance and working mode for the build guide, CLAUDE.md and AGENTS.md, not specs 0 to 4. F3 is for specs 5 to 7 and the overview row. D5, D16 and D17 are "keep", already in spec. E1's dropped items (M4-23, M4-38, M9-5, M9-37, M9-38, M11-26, M11-40) need no spec text; check that none of them was written into a spec as planned work. F9 to F19 are not decided and are skipped.

## Later-phase parts of accepted readings (E1)

E1 accepts the build's readings "with their suggested phases". The later-phase part of a reading, where it has one, goes to the Phase 2 milestone table that the orchestrating session drafts (2026-11-15 item 1), not into spec text. The specs name a later phase only where an owner decision does (reading 6 below). Each one, by its session item and the DECISIONS reading it came from:

| Session item | DECISIONS reading | Later-phase part | Goes to |
| --- | --- | --- | --- |
| M4-1 | AKS-131 (Awaiting owner 1) | Time-varying arrivals (a source schedule) | Spec 2 rows "D10; E1 (M4-1)" and "D10, D11" |
| M4-2 | AKS-131 (Awaiting owner 2) | Reneging, assembly, order-up-to, partial availability; probabilistic calendars and multitasking | Spec 2 row "D10, D11" (D11) |
| M4-15 | AKS-106 | Ordering in multiples (s, nQ) | Phase 2 table |
| M4-17 | AKS-106 | Subtracting waiting items from the position | Done M13 (D12; spec 2 row "D12, E1 M4-17") |
| M4-20 | AKS-106 | A `<store>.queue_length` metric | Phase 2 table |
| M4-29 | AKS-107 | Overlapping shifts as an error | Phase 2 table |
| M4-34 | AKS-107 | One failure process per unit | Spec 2 row "D13" |
| M5-7 | AKS-132; 2026-11-07 item 7 | Ranking and selection | Spec 2 row "D1; 2026-11-07 item 7" |
| M5-15 | AKS-108 reading 8 | Duals in `summary.json` | Spec 2 row "E1 M5-15" |
| M5-21 | AKS-109 reading 2 | Searching within each scenario (E171 now) | Phase 2 table |
| (M5 "Left") | AKS-108 "Left" | A whole number too large for a float: a validation code | Phase 2 table |
| M6-7 | AKS-110 reading 7 | Graphics detection on Windows and macOS | Spec 3 row "D7" (Phase 4, D7 replaces the suggested Phase 2) |
| M6-28 | AKS-111 reading 11 | An edit that removes a field | Phase 2 table |
| M6-48 | AKS-112 | Live `metrics` events | Spec 3 row "D4" |
| M6-53 | AKS-113 | A units edit without importing again | Phase 2 table (with M9-61) |
| M6-54 | AKS-113 | Non-ASCII file names | Phase 2 table |
| M6-55 | AKS-113 | Other encodings, delimiters and a sheet choice | Phase 2 table (with D6, spec 3 row "D6") |
| M7-1 | AKS-115 | Streamable HTTP for the MCP server | Phase 2 table |
| M7-13 | AKS-134 | A `target` input to `run_model` | Phase 2 table, with the remote target (A1) |
| M7-19 | AKS-134 | A data import tool for assistants | Spec 4 row "D15" |
| M8-5 | AKS-117 | Pools judged as idle capacity | Phase 2 table (with M10-67) |
| M9-14 | AKS-119 reading 9 | A last-edited time on Home | Phase 2 table; #97 (M15) added the last-opened time, not this |
| M9-24 | AKS-136 reading 4 | A `remove_setting` edit | Phase 2 table |
| M9-35 | AKS-136 reading 15 | Find block, the context menu, Ctrl+Space, "Move to…" | Spec 3 row "C5" (new keyboard work deferred) |
| M9-44 | AKS-137 reading 4 | A rename shown as one change | Phase 2 table |
| M9-56 | AKS-137 reading 16 | Editing in the Diagram view | Phase 2 table; for indexed models, spec 3 row "D14" |
| M9-61 | AKS-120 reading 3 | A route that changes a column's unit | Phase 2 table |
| M9-65 | AKS-120 reading 7 | A data event on the project's events | Phase 2 table |
| M9-66 | AKS-120 reading 8 | One session per project, shared by its screens | Phase 2 table |
| M9-71 | AKS-120 reading 13 | The "{n} combinations" line | Phase 2 table, with B6's run count (spec 3 row "B6") |
| M9-74 | AKS-120 reading 16 | Code splitting (charts) | Phase 2 table |
| M9-79 | AKS-138 reading 3 | Live key numbers | Spec 3 row "D4" |
| M9-80 | AKS-138 reading 4 | A search's candidate event | Phase 2 table (with D4) |
| M9-81 | AKS-138 reading 5 | Sorting, filtering and "Use" in the trials table | Phase 2 table |
| M9-84 | AKS-138 reading 8 | Dot strip, interval-shrinkage chart, canvas overlay | Phase 2 table |
| M9-88 | AKS-138 reading 12 | Embedded fonts and charts in the PDF | Phase 2 table |
| M9-95 | AKS-138 reading 19 | Code splitting (bundle size) | Phase 2 table |
| M9-105 | AKS-121 reading 10 | Code splitting (Phase 1a if the low tier is slow) | Phase 2 table |
| M10-30 | AKS-123 reading 2 | Set aliases | Already in spec 2 (313: "waits for aliases (Phase 2)") |
| M10-31 | AKS-123 reading 3 | Per-member bounds and tables of more than numbers | Phase 2 table (spec 2 313 states the limit) |
| M10-38 | AKS-123 reading 10 | Editing sets, tables and terms in the views | Spec 3 row "D14" |
| M10-50 | AKS-124 reading 2 | A lesson's progress across reloads | Done M15 (#97, `lesson_step`; spec 4 "Where the lesson lives") |
| M10-53 | AKS-124 reading 5 | Plain words for an edit's paths | Phase 2 table |
| M10-67 | AKS-125 reading 6 | A finding rule for a resource pool | Phase 2 table |
| M11-32 | AKS-142 reading 6 | Capabilities, plugins and a folder picker for the shell | Phase 2 table |

Other later-phase items from the DECISIONS sweep, with no session item:

- 2026-11-06 M9 owner design review, choice 12: palette filters and sorting "in later phases". Goes to the Phase 2 table.
- 2026-11-08 M9 "Engine gap: Tauri": the Windows shell with WebView2. Goes to spec 3 row "Deferred with Windows (B4), line 87".
- 2026-11-14 M13 zero-time loops: carrying the issue across SSH. Goes to the Phase 2 table, with the remote target (A1).
- 2026-11-14 M12 retrospective: P12, P15, P16, P17, P18, P22, P23 and P25 from Phase 2. These go to the build guide, not specs 0 to 4.
- 2026-11-05 spec review council, question 6 (people, machine elements, reliability): settled in the detailing of specs 5 to 7 (2026-11-09 B9). Goes to the overview row "2026-11-09 B9, F3".

## Needs the owner

Filed as owner-decision issues (rule 5), each with its default and the date it applies:

1. **#206: the numeric targets of the six success measures (B2).** Default: the targets proposed there, each checkable by an existing test or measurement or at a named phase. Applies on 2026-11-17. It blocks spec 0's "Success measures" only.
2. **#207: Windows natively or through WSL (F5 set only the phase).** Default: native, with WSL only for later engines that have no Windows build. Applies on 2026-11-17. It blocks the Windows sentences of specs 0 and 3 and the overview.

## Readings

These are reversible readings (rule 5). Each is written as the default, and the owner can change it when approving this draft:

1. **B6's threshold for suggesting a `search`** is set when #111 builds the run-count estimate. The spec says "past a threshold" and names #111. The proposed threshold is an estimated time above the run time limit (default 10 minutes), or more than 20 scenarios.
2. **The six risk rows added on 2026-11-05** (spec 0 line 151; 2026-11-09 B7 item 4) are accepted as written, and "(proposed)" is dropped. They have already been acted on: checksums, the scripted MCP client, and the template licences.
3. **2026-11-09 B8** is taken as replaced by the 2026-11-13 list. Its content is not in the repository.
4. **D2:** the empty optimization model keeps error E179, shown with a warning mark, which is the tooltip D2 asks for. A model with nothing to decide gives no meaningful answer.
5. **The draft-and-approve step** (2026-11-09 B2) is this file, approved by the owner. After that comes one spec PR per spec, which the orchestrating session merges (C10).
6. **Where a later-phase part goes.** A later phase is written into spec text only where an owner decision names it (the 2026-11-07, 2026-11-09, 2026-11-13 and 2026-11-15 entries, E1's own table included). The later-phase part of a reading that E1 accepted "with its suggested phase" goes to the Phase 2 milestone table (section "Later-phase parts of accepted readings"), so the specs do not list a backlog.

## Coverage

`tests/test_phase_1_review.py` reads this section. Every owner-decision item, every DECISIONS reading whose bucket is a later phase, every session item that names a later phase, and every spec line that leaves something open must have a line here, or the test fails and names it. A spec's quotes are checked while the spec is at the version surveyed above.

Surveyed through: 2026-11-15.

### Owner decisions

- 2026-11-07 Item 5: engine licence rule; answered by F4 (spec 0 and spec 1 rows "F4").
- 2026-11-07 Item 6: fresh random numbers for confirmation; done (#79, spec 2 "Fresh random numbers for confirmation").
- 2026-11-07 Item 7: ranking and selection with a selection rule; spec 2 row "D1; 2026-11-07 item 7".
- 2026-11-07 Item 14: no variables is an error; done M13 (#80, E179; spec 1 row "D2", spec 3 row "AKS-130, line 148; D2").
- 2026-11-09 A1: remote Phase 2, cluster Phase 4; already in spec (spec 1 row "A1"; spec 0 line 43).
- 2026-11-09 B1: the example files; no spec text (closed a known gap).
- 2026-11-09 B2: the repository is the source of truth; the "2026-11-09 B2" rows of every spec; this file (reading 5).
- 2026-11-09 B3: block defaults kept; spec 2 row "Deferred to review: 2026-11-09 B3".
- 2026-11-09 B4: Linux first; the Windows rows of spec 0, spec 3 and the overview.
- 2026-11-09 B5: the idle timeout setting; done M11 and M15 (spec 3 row "D8").
- 2026-11-09 B6: the owner-only fallback; spec 3 row "C1, C2" and spec 4 row "C1, C2".
- 2026-11-09 B7: item 1 sketch: spec 2 row "2026-11-09 B7 item 1"; item 3: spec 4 row "2026-11-09 B7 item 3"; items 2, 4, 5: spec 1 row "2026-11-09 B7 item 2", spec 0 row "2026-11-09 B7 item 4", B3.
- 2026-11-09 B9: specs 5 to 7 after Phase 1; overview row "2026-11-09 B9, F3".
- 2026-11-13 B1: objective types; spec 1 row "B1", spec 2 row "B1", spec 0 phases row.
- 2026-11-13 B2: six success measures; spec 0 rows "B2"; #206.
- 2026-11-13 B3: hardware table after Phase 3; spec 0 row "B3, F6", spec 3 row "B3, F6".
- 2026-11-13 B4: AGPL-3.0-only and the licences page; spec 0 rows "B4 and C7", spec 1 row "F4, B4/C7", spec 3 row "B4, C7, F4".
- 2026-11-13 C7: as B4.
- 2026-11-13 B5: AppImage and Windows installer; spec 3 rows "B5" and line 73; spec 0 row "B5, 2026-11-15 item 3".
- 2026-11-13 B6: scenario count; spec 2 row "B6", spec 3 row "B6".
- 2026-11-13 C1: agent walkthroughs; spec 0 row "C3, C1", spec 3 row "C1, C2", spec 4 row "C1, C2".
- 2026-11-13 C2: as C1.
- 2026-11-13 C3: three testers in Phase 3; spec 0 row "C3, C1".
- 2026-11-13 C4: Phase 3a; spec 0 phases row, spec 3 row "C4, F6", overview row "C4".
- 2026-11-13 C5: mouse-first; spec 3 row "C5".
- 2026-11-13 C6: MCP parity; spec 0 row "C6", spec 4 rows "C6".
- 2026-11-13 C8: Ithax; spec 0 rows "C8"; spec 1, 3 and 4 rows "C8" (done M12).
- 2026-11-13 C9: no outside contributors until Phase 4; spec 0 row "C9, C10".
- 2026-11-13 C10: merging; spec 0 row "C9, C10"; the build guide.
- 2026-11-13 D1: spec 2 row "D1; 2026-11-07 item 7".
- 2026-11-13 D2: spec 1 row "D2" (reading 4).
- 2026-11-13 D3: spec 3 row "D3, E1 M6-34" (done M14).
- 2026-11-13 D4: spec 3 row "D4".
- 2026-11-13 D5: spec 3 row "D5" (keep).
- 2026-11-13 D6: spec 3 row "D6".
- 2026-11-13 D7: spec 3 row "D7".
- 2026-11-13 D8: spec 3 row "D8" (done M15).
- 2026-11-13 D9: spec 4 row "D9" (done M13).
- 2026-11-13 D10: spec 2 rows "D10, D11" and "D10; E1 (M4-1)".
- 2026-11-13 D11: spec 2 row "D10, D11".
- 2026-11-13 D12: spec 2 row "D12, E1 M4-17" (done M13).
- 2026-11-13 D13: spec 1 row "D13, E1 M4-34", spec 2 row "D13".
- 2026-11-13 D14: spec 3 row "D14".
- 2026-11-13 D15: spec 4 row "D15".
- 2026-11-13 D16: spec 4 row "D16" (keep).
- 2026-11-13 D17: spec 3 row "D17" (keep).
- 2026-11-13 D18: the build guide (section "Decisions with no spec 0 to 4 target").
- 2026-11-13 E1: the E1 rows of specs 1 and 2, and "Later-phase parts of accepted readings".
- 2026-11-13 M1-7: spec 1 row "E1 M1-7" (done M13).
- 2026-11-13 M1-9: spec 1 row "E1 M2-1, M1-9" (done M13).
- 2026-11-13 M2-1: as M1-9.
- 2026-11-13 M2-5: spec 1 and spec 2 rows "E1 M2-5, M4-14" (done M13).
- 2026-11-13 M4-14: as M2-5.
- 2026-11-13 M2-7: spec 2 row "E1 M2-7" (done M13).
- 2026-11-13 M3-2: spec 2 row "E1 M3-2" and the research row.
- 2026-11-13 M4-17: spec 2 row "D12, E1 M4-17" (done M13).
- 2026-11-13 M4-34: spec 1 row "D13, E1 M4-34", spec 2 row "D13".
- 2026-11-13 M4-39: spec 1 row "E1 M4-39, M4-40" (done M13).
- 2026-11-13 M4-40: as M4-39.
- 2026-11-13 M5-1: spec 1 row "E1 M5-1, M5-10", spec 2 row "E1 M5-1, M5-10".
- 2026-11-13 M5-10: as M5-1.
- 2026-11-13 M5-12: spec 2 row "E1 M5-12" (done M13).
- 2026-11-13 M5-15: spec 2 row "E1 M5-15".
- 2026-11-13 M5-23: spec 2 rows "E1 M5-23, first part" (done) and "E1 M5-23, second part" (the Phase 2 method), spec 4 row "E1 M5-23".
- 2026-11-13 M6-34: spec 3 row "D3, E1 M6-34" (done M14).
- 2026-11-13 M11-51: spec 1 row "F7, C8, M11-51" (done M12).
- 2026-11-13 F1: spec 0 phases row and row "F1, F7"; overview row "F1, C4, F3".
- 2026-11-13 F2: the build guide (retrospective adopted at M12).
- 2026-11-13 F3: overview rows "F1, C4, F3" and "2026-11-09 B9, F3".
- 2026-11-13 F4: spec 0 row "F4", spec 1 row "F4, B4/C7", spec 3 row "B4, C7, F4".
- 2026-11-13 F5: the Windows rows of spec 0, spec 3 and the overview.
- 2026-11-13 F6: spec 0 rows "F6" and "B3, F6", spec 3 row "C4, F6".
- 2026-11-13 F7: spec 0 rows "F1, F7" and "F7 (absent)", spec 1 row "F7, E1", spec 3 row "F7 (absent)".
- 2026-11-13 F8: the build guide (working mode).
- 2026-11-13 F9 to F19: not decided; for the council of specs 5 to 7 (F3).
- 2026-11-15 item 1: the Phase 2 milestone table, drafted by the orchestrating session; no spec text.
- 2026-11-15 item 2: spec 0 row "F1, F7" (the owner tags v0.1.0); #103.
- 2026-11-15 item 3: spec 0 rows "B5, 2026-11-15 item 3" and "Deferred with Windows (B4), line 82", spec 3 line 73 row.
- 2026-11-15 item 4: working mode; no spec text.

### Later-phase readings in DECISIONS

- DECISIONS AKS-108 reading 8: session item M5-15 in "Later-phase parts of accepted readings".
- DECISIONS AKS-108 Left: session item (M5 "Left") in "Later-phase parts of accepted readings".
- DECISIONS AKS-109 reading 2: session item M5-21 in "Later-phase parts of accepted readings".
- DECISIONS AKS-110 reading 7: session item M6-7 in "Later-phase parts of accepted readings".
- DECISIONS AKS-111 reading 11: session item M6-28 in "Later-phase parts of accepted readings".
- DECISIONS AKS-120 reading 3: session item M9-61 in "Later-phase parts of accepted readings".
- DECISIONS AKS-120 reading 7: session item M9-65 in "Later-phase parts of accepted readings".
- DECISIONS AKS-120 reading 8: session item M9-66 in "Later-phase parts of accepted readings".
- DECISIONS AKS-120 reading 13: session item M9-71 in "Later-phase parts of accepted readings".
- DECISIONS AKS-120 reading 16: session item M9-74 in "Later-phase parts of accepted readings".
- DECISIONS AKS-121 reading 10: session item M9-105 in "Later-phase parts of accepted readings".
- DECISIONS AKS-123 reading 2: session item M10-30 in "Later-phase parts of accepted readings".
- DECISIONS AKS-123 reading 3: session item M10-31 in "Later-phase parts of accepted readings".
- DECISIONS AKS-123 reading 10: session item M10-38 in "Later-phase parts of accepted readings".
- DECISIONS AKS-124 reading 2: session item M10-50 in "Later-phase parts of accepted readings".
- DECISIONS AKS-124 reading 5: session item M10-53 in "Later-phase parts of accepted readings".
- DECISIONS AKS-125 reading 6: session item M10-67 in "Later-phase parts of accepted readings".
- DECISIONS AKS-137 reading 4: session item M9-44 in "Later-phase parts of accepted readings".
- DECISIONS AKS-137 reading 16: session item M9-56 in "Later-phase parts of accepted readings".
- DECISIONS AKS-138 reading 3: session item M9-79 in "Later-phase parts of accepted readings".
- DECISIONS AKS-138 reading 5: session item M9-81 in "Later-phase parts of accepted readings".
- DECISIONS AKS-138 reading 8: session item M9-84 in "Later-phase parts of accepted readings".
- DECISIONS AKS-138 reading 12: session item M9-88 in "Later-phase parts of accepted readings".
- DECISIONS AKS-138 reading 19: session item M9-95 in "Later-phase parts of accepted readings".
- DECISIONS AKS-142 reading 6: session item M11-32 in "Later-phase parts of accepted readings".
- DECISIONS Item 7 entry: session item M5-7 in "Later-phase parts of accepted readings".

### Later-phase session items

- M4-1: "Later-phase parts of accepted readings".
- M4-2: "Later-phase parts of accepted readings".
- M4-15: "Later-phase parts of accepted readings".
- M4-17: "Later-phase parts of accepted readings".
- M4-20: "Later-phase parts of accepted readings".
- M4-29: "Later-phase parts of accepted readings".
- M4-34: "Later-phase parts of accepted readings".
- M5-7: "Later-phase parts of accepted readings".
- M5-15: "Later-phase parts of accepted readings".
- M5-21: "Later-phase parts of accepted readings".
- M6-7: "Later-phase parts of accepted readings".
- M6-28: "Later-phase parts of accepted readings".
- M6-48: "Later-phase parts of accepted readings".
- M6-53: "Later-phase parts of accepted readings".
- M6-54: "Later-phase parts of accepted readings".
- M6-55: "Later-phase parts of accepted readings".
- M7-1: "Later-phase parts of accepted readings".
- M7-13: "Later-phase parts of accepted readings".
- M7-19: "Later-phase parts of accepted readings".
- M8-5: "Later-phase parts of accepted readings".
- M9-14: "Later-phase parts of accepted readings".
- M9-24: "Later-phase parts of accepted readings".
- M9-35: "Later-phase parts of accepted readings".
- M9-44: "Later-phase parts of accepted readings".
- M9-56: "Later-phase parts of accepted readings".
- M9-61: "Later-phase parts of accepted readings".
- M9-65: "Later-phase parts of accepted readings".
- M9-66: "Later-phase parts of accepted readings".
- M9-71: "Later-phase parts of accepted readings".
- M9-74: "Later-phase parts of accepted readings".
- M9-79: "Later-phase parts of accepted readings".
- M9-80: "Later-phase parts of accepted readings".
- M9-81: "Later-phase parts of accepted readings".
- M9-84: "Later-phase parts of accepted readings".
- M9-88: "Later-phase parts of accepted readings".
- M9-95: "Later-phase parts of accepted readings".
- M9-105: "Later-phase parts of accepted readings".
- M10-30: "Later-phase parts of accepted readings".
- M10-31: "Later-phase parts of accepted readings".
- M10-38: "Later-phase parts of accepted readings".
- M10-50: "Later-phase parts of accepted readings".
- M10-53: "Later-phase parts of accepted readings".
- M10-67: "Later-phase parts of accepted readings".
- M11-32: "Later-phase parts of accepted readings".

### Open markers in the specs

- overview: "WSL deferred to Phase 3": overview row "Deferred to review, line 40".
- overview: "the Windows version is deferred, its phase set at the Phase 1 review": overview row "Deferred to review, line 40".
- spec 0: "The working title is not yet chosen.": spec 0 row "C8" (line 13).
- spec 0: "A Windows version follows, deferred until the Phase 1 review sets its phase": spec 0 row "Deferred to review, line 60".
- spec 0: "a Windows version is deferred (B4)": spec 0 row "F5" (line 65).
- spec 0: "Deferred with the Windows version (owner decision B4, 2026-11-09)": spec 0 row "Deferred with Windows (B4), line 82".
- spec 0: "Later phases add one engine at a time.": no change: a risk's mitigation, consistent with F1 and F3.
- spec 1: "deferred to Phase 2 until a block that sets attributes": already in spec (2026-11-05 council C5); D11 adds the rest in spec 2.
- spec 1: "carrying warnings there is deferred to #191 (Phase 3)": already in spec (owner decision #188, 2026-11-15).
- spec 2: "priority disciplines are deferred to Phase 2": already in spec; spec 2 row "D10, D11" extends the sentence.
- spec 2: "are the Phase 2 candidate, owner to confirm": spec 2 row "D1; 2026-11-07 item 7".
- spec 2: "A `sketch` preview level is an owner question.": spec 2 row "2026-11-09 B7 item 1".
- spec 3: "the Windows installer is deferred (owner decision B4, 2026-11-09), its phase set at the Phase 1 review": spec 3 row "Deferred to review, line 7".
- spec 3: "the Windows version is deferred, and the Phase 1 review sets its phase": spec 3 row "Deferred to review, line 23".
- spec 3: "**Windows:** deferred (owner decision B4, 2026-11-09); the Phase 1 review sets its phase": spec 3 row "Deferred to review, line 73; B5; 2026-11-15 item 3".
- spec 3: "the Windows build is deferred with the Windows version, owner decision B4": spec 3 row "Deferred with Windows (B4), line 87".
- spec 3: "is Phase 1a, AKS-130": spec 3 row "AKS-130, line 148; D2".
- spec 3: "carrying warnings there is deferred to #191 (Phase 3)": already in spec (owner decision #188, 2026-11-15).
- spec 3: "**Deferred with Windows (owner decision B4, 2026-11-09), only if the owner keeps WSL": spec 3 row "Deferred to review, line 318".
- spec 3: "Deferred (owner decision B4, 2026-11-09); the Phase 1 review sets its phase": spec 3 row "Deferred to review, line 332".
