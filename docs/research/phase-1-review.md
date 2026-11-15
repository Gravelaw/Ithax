# Phase 1 review: the changes to fold into specs 0 to 4

The checklist of #101, surveyed on 2026-11-15 at `main` c864cb9. This is the draft the owner approves (2026-11-09 B2; C10); the spec edits follow it, one PR per spec, each with a dated line and a version bump. Line numbers are those of c864cb9. Issue #101 ("Phase 1 review: fold accepted changes into specs 0 to 4", AKS-130); guide M16 row (build-guide.md line 125): "the Phase 1 review's changes are in specs 0 to 4".

Sources:
- **Explicit deferrals** found with `grep -n "Phase 1 review"` and `grep -n "AKS-130"` over specs 0 to 4 and overview.md: spec 0 lines 60 and 188; spec 3 lines 7, 23, 73, 148 (AKS-130), 318 and 332; overview line 40. Specs 1, 2 and 4 have none. DECISIONS.md 2026-11-09 adds four more deferrals that are not in the spec text: B2 (draft-and-approve step), B3 (block defaults wording in spec 2; walkthrough timing), B4 (Windows phase), and "B7 items 2, 4 and 5; B8; Parts C, D and E stay open for the Phase 1 review" (line 1978).
- **Decisions** in DECISIONS.md "2026-11-13 · Owner decisions on the Phase 1 decision list (Parts B to F)" (line 2316), B1 to F8, plus the 2026-11-15 owner decisions (line 3257), item 3 on Windows (#106).
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
| B1 | 44-51: Optimization table "Mathematical ... HiGHS through Pyomo"; "Simulation-based ... Optuna" | Add the Phase 2 objective types: nonlinear and MINLP after an engine trial (Ipopt or SCIP through Pyomo), black-box via metaheuristics or surrogates; weighted sum, ε-constraint, Pareto (NSGA-II preferred on simulations) with a trade-off-front view; more methods in Phase 4. | change needed |
| D1 | 347: "no ranking-and-selection procedure replaces it in Phase 1 (KN with common random numbers and Batur and Kim's feasibility check are the Phase 2 candidate, owner to confirm)" | Phase 2, early, with fresh-random-number confirmation; the method is chosen by a transparent rule from the problem's features (D1). | change needed |
| E1 M3-2 | 155: "Warm-up check (kept over MSER-5 ...; the 99% level and the 5% threshold are proposed defaults, owner to confirm)" | Kept for 0.x; a Phase 2 research item compares it with MSER-5 on the templates. | change needed |
| E1 M5-1, M5-10 | 329: "Any other ending ... has no `status` of the three, so the run fails with E190" | Phase 2: a `feasible` status with the gap, and `time_limit` and `mip_gap` settings, instead of E190 for a solve stopped with a good solution. | change needed |
| E1 M5-15 | 334: "**Duals.** `summary.json` holds no duals." | Duals are served as the first Phase 2 optimization item. | change needed |
| D10, D11 | 95: "Item attributes, the `attribute` rule and priority disciplines are deferred to Phase 2 (see spec 1)." | Add: time-varying arrivals (D10), leaving the queue, assembly, periodic stock policies and partial availability (D11) in Phase 2; probabilistic calendars and multitasking in Phase 3; each after research. | change needed |
| D13 | 110: "**Failure.** One `failure` block is one alternating process on its target ... So at most one unit of the target is failed at a time" | Cross-reference W203 (spec 1 line 343) and say one failure process per unit is Phase 2. | change needed |
| B3 / C1 / research | 367-376: research list holds M2 to M5 items only | Add the Phase 2 research items: D10, D11, MSER-5 (M3-2), the B1 engine trial, the D1 method rule. | change needed |
| B6 | 41: "Scenarios: named sets of parameter values"; 42: "Parallel runs: replications use all available processor cores." | "No cap" can be said here (B6); parallel to the core count is already line 42. The run-count, time-estimate and search-suggestion parts belong to spec 3. | change needed (one clause) |
| D12, E1 M4-17 | 89: "When the inventory position (stock on hand plus on order minus the items waiting for stock) falls to `reorder_point`" | Done M13. | already in spec |
| E1 M2-5, M4-14 | 103: "stops the run with E196 (spec 1) when more than 1,000,000 happen at one instant" | Done M13. | already in spec |
| E1 M2-7 | 249: "both files are gated on that theory: ... 300 replications ... within 2 standard errors ... holds them to ... 3 standard errors"; 385 acceptance row (M13) | Done M13 (#75). | already in spec |
| E1 M5-12 | 330: "an `integer` or `binary` variable is reported rounded to its whole number, and any other number within 64 units in the last place..." | Done M13 (#76). | already in spec |
| E1 M5-23 | 358: "An Optuna search's best is the best of those tried, not a proven optimum, and the findings and the Results screen say so (#85, M5-23)" | Done M13. | already in spec |

Count: 16 rows: 11 change needed, 5 already in spec. One explicit deferral, from DECISIONS (B3), none in the spec text.

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
| Incidental (no decision) | 325: "a new project is written at the reader's version, 0.2 since AKS-123" | Format is 0.3 since #77 (spec 1 line 130). Fix while editing. | change needed (stale fact) |

Count: 25 rows: 17 change needed (two of them also need an owner choice or number), 1 needs owner choice only (318), 6 already in spec, 1 stale fact. Six explicit Phase 1 review deferrals plus one AKS-130.

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
