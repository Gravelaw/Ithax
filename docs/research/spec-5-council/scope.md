# Council review of spec 5 v0.3: scope against spec 0 and the Phase 2 plan

Reviewer lens: scope. Branch `docs/spec-5-v0.3`, read on 2026-11-16. Sources: `docs/specs/0-product-brief.md` (v0.5), `docs/specs/overview.md`, `docs/research/phase-2-milestones.md`, `docs/research/phase-1-review.md`, `docs/DECISIONS.md` (A1, B1, B7, B9, C3, C6, D1, F3 to F9, #206, #207, the two spec 5 entries of 2026-11-16), `docs/specs/build-guide.md` rule 5 and "Questions before a milestone", the draft `docs/specs/5-systems-and-design.md` and the twelve `docs/research/spec-5-*.md` notes. No repository file was changed.

Severity: **blocking** means the spec cannot be approved or M23 cannot start as written. **Should-fix** means fix it in this PR. **Suggestion** means optional.

---

## 1. Scope against spec 0 and F3

### S1. Workforce models are framed as optional, but spec 0 and the M23 row already promise them (blocking)

- **Location:** "People in models" (a): "Two settings are ready to specify once the owner admits them to Phase 2".
- **Problem:** The owner has already put "people and workforce models" in Phase 2. Spec 0 v0.5 "Scope and build order" lists them in the Phase 2 row, and so does the Phase 2 table ("What Holds", and M23: "people and workforce"). B9's "whether people ... stay in scope, and in which phase" was settled when the owner approved spec 0 v0.5 on 2026-11-16. The draft turns a promised item into one the owner has to opt into. If the owner never answers, Phase 2 quietly delivers no workforce model, which drops a spec 0 promise.
- **Evidence:** spec 0 line 38; phase-2-milestones lines 12 and 58; `spec-5-people-methods.md` "Open questions, blocking", first bullet.
- **Fix:** Reword the open question. It is not whether workforce enters Phase 2; it is **which settings** do, which is a model-format question for the owner. Make the default "learning curve and absenteeism in Phase 2", the two settings that already have benchmarks. Fatigue and skill matching go to Phase 3 under F3, since no published model has been chosen. Mark (a) "Specified once the format question is answered". Also see S17: these settings could go into M19.

### S2. Crowds and pedestrians may silently drop out of Phase 2 (blocking)

- **Location:** (b): "Proposed: JuPedSim 1.4 ... as a `pedestrian` domain, in place of 'Mesa first' ... It needs 2D room and corridor polygons in the model file." Also "Agent-based models (Specified, well-mixed)": "Spaces ... are Open: Phase 3 unless M23's templates need them".
- **Problem:** In v0.2, Phase 2 covered crowds through Mesa ("Agent-based, Mesa first"). v0.3 makes Mesa well-mixed only, with no space, so Mesa can no longer model walking. The replacement is a new domain with new 2D geometry in the model file, and it is marked Open with no phase. Either outcome changes scope without saying so. If the owner admits JuPedSim, Phase 2 gains a domain, a geometry format and a calibration problem that are not in the Phase 2 table. If the owner does not, crowds leave Phase 2 without a recorded decision. The draft's Scope "In" list also has no `pedestrian` row, and the adapter table and benchmarks omit it.
- **Evidence:** v0.2 (`git show main:docs/specs/5-systems-and-design.md`) line 30. `spec-5-people-engines.md` "Open questions, blocking": "changes spec 5's engine choice and the Phase 2 milestone content" and "Is 2D polygon geometry in scope for Phase 2 (model format)?". F3: "New items go to Phase 3, Phase 3a or Phase 4."
- **Fix:** Make this an explicit owner question with a phase in every option: (a) a JuPedSim `pedestrian` domain in Phase 2, with its own milestone row, 2D geometry in format 0.x and the Seyfried benchmark; (b) pedestrians in Phase 3 beside spec 6's geometry (recommended under F3, because the 2D geometry overlaps spec 6 and the default settings miss the published flow range). Under (b), add a line under Scope "Out", "Crowds and pedestrians: Phase 3", so the drop is recorded rather than implied. Phase 2 still meets spec 0's "people" through workforce settings and the ergonomics and HRA calculators.

### S3. Some Phase 2 content is narrowed without a recorded decision (should-fix)

- **Location:** the adapter table and the domain sections, compared with v0.2.
  - Agent: v0.2 had "customers, vehicles, an epidemic" on the canvas "Agent types, rules, a space". v0.3 is "well-mixed only", and spaces stay "Phase 3 unless M23's templates need them".
  - Physical: v0.2 listed "motors, pumps, tanks, heat exchangers, circuits". The v0.3 catalogue has no fluid classes (no pumps, tanks or heat exchangers) and no motors as such.
  - Multibody: v0.2 listed "springs, contacts: linkages, conveyors, vehicles". In v0.3, "Contacts and closed loops are Open", and conveyors and vehicles are gone. `spec-5-mujoco.md` says that is checked at M23.
  - Maintenance-policy comparison: Open, with no phase.
  - HEART, RULA and REBA: Open, with no phase. The people-methods note suggests "Phase 2 or 3".
- **Problem:** Each item is a reasonable narrowing, but none says which phase it moves to, and some are conditional ("unless M23's templates need them"). A condition like that lets M23 grow its own scope. F3 requires new or deferred items to land in Phase 3, 3a or 4. Also, a well-mixed population with rate transitions is in effect a stochastic compartment model. Whether that meets spec 0's "agent-based models" is a user-visible scope call, not a detail.
- **Fix:** Add a "Deferred from Phase 2" list under Scope, with a phase for each item:
  - agent spaces and movement: Phase 3, with no M23 escape clause, or a firm Phase 2 choice;
  - fluid components: Phase 3;
  - multibody contacts, closed loops, conveyors and vehicles: Phase 3;
  - HEART: Phase 2 once its source is read, else Phase 3;
  - RULA and REBA: Phase 3 after the legal check;
  - maintenance policies: Phase 2 if the owner accepts the `failure` extension, else Phase 3.

  List "is well-mixed enough to count as agent-based for Phase 2?" with the owner questions (user-visible).

### S4. Stepping together is "out of Phase 2" but has no phase (should-fix)

- **Location:** Scope: "Stepping engines together (co-simulation) is out of Phase 2". "Combining engines": "When it starts, it wraps a tool ...".
- **Problem:** F3 places items in Phase 3, 3a or 4. "When it starts" leaves no phase, so the item is not in spec 0's phase table at all.
- **Fix:** Name the phase. Phase 3 fits, alongside spec 6 coupling, which spec 0's overview already gives "coupling". Add it to spec 0's Phase 3 row in the same PR, or in the Phase 2 review PR if the owner prefers.

### S5. The multibody 3D preview depends on Phase 3 work and has no milestone (should-fix)

- **Location:** adapter table: "Bodies and joints, with a 3D preview on spec 6's viewer basis". Scope: "the multibody preview is the exception and uses spec 6's viewer basis".
- **Problem:** Spec 6 is Phase 3 (overview: "Build after: Phase 2 complete"). v0.2 said the preview is "minimal in Phase 2 and extended in Phase 3"; v0.3 drops that qualifier. No acceptance row or milestone covers the preview. As written, M23 would have to build the base of spec 6's viewer (VTK/PyVista or vtk.js in the Tauri webview, plus graphics under WSLg), which pulls Phase 3 work into Phase 2.
- **Fix:** Pick one and write it in. (a) The Phase 2 preview is a 2D or schematic joint view in the existing React interface; the 3D viewer comes in Phase 3. (b) A minimal 3D preview in M23 (or the split milestone, see S11), with an acceptance row and the viewer dependency recorded. Recommend (a): it keeps spec 6's viewer in Phase 3 and avoids a graphics dependency under WSL 2.

### S6. Interface and `/v1` for the new features are not specified anywhere (blocking)

- **Location:** acceptance row "All new component types are reachable through the MCP tools without changes to them, with a parity test | M25"; canvas styles in the adapter table.
- **Problem:** Design studies, surrogates, chains and the calculators (life-data fit, block diagrams, fault trees, NIOSH, SPAR-H) are not component types. They need new routes and new MCP tools. C6 says "each feature ships with a thin API and MCP tool and a parity test", meaning at the milestone that builds it, with M25 only hardening. The draft has no `/v1` section, and a `/v1` change is blocking under guide rule 5. Its one `/v1` question, "whether `/v1` shows [a chain] as one run or a group", is the only one raised. The four canvas styles (populations, stock-and-flow, physical component diagram, bodies and joints) have no screen spec, no milestone and no acceptance row. Spec 0's purpose is "without writing code", so a domain reachable only through MCP does not meet it.
- **Evidence:** spec 0 "AI access" (C6); phase-2-milestones M25 ("Every Phase 2 feature has its thin API and MCP tool"); guide rule 5.
- **Fix:**
  - Add a short "API and interface" section listing the routes and MCP tools each feature needs (`study`, `surrogate`, `chain`, calculators) and the canvas style per domain. Mark it Open where spec 3 must detail it, and list the `/v1` additions as owner questions.
  - Add acceptance rows: "each new feature has its `/v1` route and MCP tool with a parity test" tagged to the building milestone, and "each new domain is built and run from its canvas" (interface).
  - Reword the M25 row to match the table ("every Phase 2 feature").

### S7. Optimization across engines: B1's surrogate-based black-box objective is missing (should-fix)

- **Location:** "Design studies" table, rows for one objective and several objectives; "Surrogate models".
- **Problem:** B1 (Phase 2) includes "black-box simulation objectives through metaheuristics or surrogate models". The draft builds surrogates but never says a study can optimize on one, or how a result found on a surrogate is confirmed on the real model. Spec 0 promises "optimization across engines"; the draft's answer is the design-study layer, which is fine, but the surrogate half of B1 is not specified. Note too that C3 places "optimization on surrogates" for physics in Phase 3.
- **Fix:** Pick one. (a) Add an "optimization on a surrogate" mode to the `optimization` study, with a confirmation run of the chosen point on the source model and the surrogate label on anything unconfirmed. (b) State that surrogate-based optimization is Phase 3 (C3) and that B1's Phase 2 black-box objective is met by metaheuristics alone. Either way, say it.

### S8. Spec 5 chooses M20's NSGA-II library, overriding B1's text (should-fix)

- **Location:** "Optimization, several objectives | The trade-off front | pymoo NSGA-II (shared with M20's Pareto search, B1)".
- **Problem:** B1 says "Pareto search (NSGA-II, already in Optuna) is preferred". M20, a spec 2 milestone that comes before M23, would now depend on pymoo, which brings moocore (LGPL-2.1-or-later) and matplotlib, and the decision is made in spec 5. Spec 2 does not mention pymoo. This is a cross-spec choice, and under rule 5 the departing spec must change in the same PR. The ZDT1 benchmark also has no milestone, so it is unclear whether M20 or M23 gates it.
- **Evidence:** DECISIONS B1; `spec-5-design-studies.md` "Reversible": "Optuna's `NSGAIISampler` would avoid pymoo at the cost of a worse front".
- **Fix:** Either (a) M20 uses Optuna's NSGA-II as B1 says, and pymoo enters at the design-study milestone, if at all; or (b) record "pymoo for M20" as a reading, change spec 2's multi-objective section in this PR, and tag ZDT1 to M20. Recommend (b) only if the trial's front-quality gap matters for the templates; otherwise (a).

### S9. The format version 0.4 will likely collide with M19 and M20 (should-fix)

- **Location:** "Model file for the new domains": "Format 0.4 (additive)". "Physical units (format 0.4)". Design studies: "(format 0.4, additive)".
- **Problem:** The reader is at 0.3 (spec 1 "Versioning"). M19 adds format changes (D10 schedules, D11 constructs, D13, attributes) and M20 adds format changes (aliases, per-member bounds), and both come before M23. Under spec 1's rule each additive change bumps the minor, so 0.4 will already be taken when M23 starts.
- **Fix:** Write "the next minor after M19 and M20's (0.4 if none intervenes)". Or reserve the minors per milestone in the Phase 2 table and list that as a reading.

### S10. Templates: one or two per type, and B7 item 3 (should-fix)

- **Location:** acceptance row "Each specified adapter passes its benchmarks and ships with two templates | M23".
- **Problem:** The Phase 2 table's M23 row says "Every model type has benchmarks and a template" (one). B7 item 3 puts "template expansion in general" in Phase 3. With four adapters, two templates each is 8 templates (10 or more with pedestrians or calculators). That doubles the template set inside one milestone and leans on a Phase 3 decision.
- **Fix:** Align with the table: one template per new domain in Phase 2, with the second in Phase 3 under B7 item 3. Or record a reading that new-domain templates are not "template expansion" and update the Phase 2 table row to "two".

---

## 2. Acceptance rows and milestones

### S11. M23 is not one milestone; split it into four (blocking, a milestone question for the owner, D18)

- **Location:** acceptance rows tagged "M23" (five of the nine rows); the Phase 2 table's M23 row: "M17's council may split this row into several milestones".
- **Problem:**
  - **Size.** M23 holds the following, against rule 7's "under about 400 changed lines of product code" per PR, which puts it at roughly 25 to 40 PRs. Phase 1 milestones were one spec area each.
    - four adapters (five with pedestrians);
    - format 0.4 with 13 new codes;
    - an expression parser and loop check;
    - about 25 physical units;
    - an FMU build cache;
    - five study kinds over six libraries;
    - surrogates with a new project file and refit check;
    - chaining with a new manifest field;
    - three reliability calculators, two ergonomics and HRA calculators, and two process-engine settings;
    - 14 benchmarks;
    - 8 or more templates;
    - remote runs for each adapter;
    - the `/v1` and MCP tools for each feature (C6);
    - four canvas styles.
  - **Gating.** Rule 2: the next milestone starts only when this one's acceptance passes. Physical and multibody are Open: MuJoCo awaits the owner, and OpenModelica has never been run. In one M23, the Specified majority could not close until those were settled, and M24 to M26 would wait on them.
  - **Dependencies.** The chaining row needs only system dynamics and process. The cross-engine study row needs physical. Reliability and the calculators need no new adapter.
- **Proposed split** (renumber the rest; MCP stays second to last for C6):

  | # | Milestone | Holds | Acceptance rows |
  | --- | --- | --- | --- |
  | M23 | System dynamics, agents and chaining | Format base: `time_step`, deterministic runs, E401 to E405, E420 and E421; the expression grammar; PySD and Mesa adapters; chaining (system dynamics to process); stock-and-flow and population canvases | SIR (both forms) and predator–prey benchmarks; a template each; the chain row; remote for both adapters; API and MCP for chains |
  | M24 | Reliability and people | Life-data fit (extends spec 3's fit); block diagrams (E410); fault trees; NIOSH and SPAR-H; learning curve and absenteeism if admitted (S1; or move these to M19, see S17) | Weibull, block-diagram, fault-tree, learning-curve, NIOSH and SPAR-H benchmarks; API and MCP for the calculators |
  | M25 | Physical systems and multibody | OpenModelica and FMPy, MuJoCo or Chrono, physical units, E406, component and joint canvases. Starts only after the owner answers MuJoCo vs Chrono, the OpenModelica install question (S13) and the OpenModelica trial | mass–spring–damper and pendulum benchmarks; a template each; remote |
  | M26 | Design studies and surrogates (optimization across engines) | Study kinds, `scipy.stats.qmc`, SALib, pymoo or Optuna (S8), surrogates (E430, E431), B1's surrogate objective (S7) | test-function, Ishigami and surrogate benchmarks; the process-and-physical study row; the surrogate portability row |
  | M27 | Windows through WSL 2 | (was M24) | |
  | M28 | MCP hardening | (was M25) | |
  | M29 | Phase 2 release | (was M26) | |

- **Ordering:** Specified work comes first, which gives the owner time on the Open questions. M25 may swap ahead of M24 if the owner answers early. M26 comes last because its acceptance row needs a physical model.
- **Fix:** Put the split in the council report as a proposal to the owner. Changing the milestone table is the owner's (D18), so it is blocking until answered. Retag the acceptance rows. Add a milestone column to the Benchmarks table (S12).

### S12. Benchmarks have no milestone, and several features have no acceptance row (should-fix)

- **Location:** "Benchmarks" (14 rows, no milestone column); acceptance table.
- **Problem:**
  - Spec 2 "Benchmark definitions" requires a `milestone` in each `expected.json` (`tests/benchmarks/conftest.py`, `CURRENT_MILESTONE`). Rule 3 says benchmarks are gates, so each needs a milestone.
  - The acceptance table gates only "each specified adapter". Nothing gates the calculators (NIOSH, SPAR-H, block diagrams, fault trees, life-data fit), the workforce settings, the study kinds other than optimization (sweep, design, sensitivity, uncertainty), or the error codes E401 to E431.
  - C4 says every phase keeps cheap performance budgets, yet there is no performance row: for example, surrogate prediction time on the low tier, or a PySD run of the SIR template on 4 cores.
- **Fix:** Add a Milestone column to Benchmarks. Add rows for:
  - "each calculator reproduces its benchmark";
  - "each study kind runs on a process model and on a deterministic model";
  - "each new issue code has a fixture" (as `tests/model/fixtures/issues`);
  - "a performance budget per new adapter (`pytest -m perf`)".

  Tag each to the milestone that builds it.

### S13. Rows tagged to other milestones: mostly right, with two gaps (should-fix)

- **M17** ("research notes, small engine cases and council report exist, and this spec is detailed for the owner (B9, F3) | M17 | ... owner approves the spec"): this matches the M17 row. But F3 says "No owner approval before work starts; the owner reviews the specs and council reports during development." Reword to "owner reviews the spec (F3); Open sections need the owner's answers before they are built", so the row does not read as an approval gate F3 removed.
- **M22 remote** ("Every new adapter runs on the `remote` target | M23, after M22"): this is correct (Phase 2 table reading 1). But the physical adapter's FMU build (`omc`, a C toolchain) and the project's FMU cache are not specified for remote. Say where the FMU is built (locally, then copied with the project) and that the remote host needs FMPy only. Otherwise the remote row fails for `physical`, or demands OpenModelica on every remote host.
- **M24 WSL 2** ("The engines of spec 5 install under WSL 2 with the documented steps | M24 | agent or owner"): this matches the M24 row. See S14: the steps include an apt repository and a toolchain for OpenModelica, which the M24 row ("the Linux package or the AppImage") does not cover.
- **M25 MCP:** this matches C6 and the M25 row, but is too narrow (S6).
- **M26 walkthroughs** ("An agent walkthrough builds and runs one model of each new domain | M26 | agent"): M26 requires walkthroughs "in student and business-analyst roles" (C1). Name the roles and the route (interface or MCP); otherwise an MCP-only run satisfies the row without testing the interface (S6).
- Nothing is tagged to M18 to M21 except, implicitly, M20's Pareto search (S8). That is consistent with the table, apart from S8 and S17.

---

## 3. Engine changes against v0.2: are they owner decisions?

### S14. Engine changes are only partly flagged (should-fix)

- **MuJoCo in place of Chrono:** flagged in the adapter table ("Open: engine choice awaits the owner"), in "Multibody (Open: engine choice)", in "Research before building" and in DECISIONS 2026-11-16 ("that choice is an owner question"). Good. Still needed: the "Owner decision" issue (guide "Questions before a milestone"). No such issue exists; the REST search for "Owner decision" issues returns #176, #181, #188, #206 and #207 only.
- **JuPedSim in place of "Mesa first":** flagged as "Proposed", "(Open: engine and geometry)". It is absent from the DECISIONS engine entry and from the adapter table. Add it to both, or defer it per S2.
- **OpenMDAO and Dakota dropped:** the line itself says "(proposed, owner to confirm)", but the section heading says "**Specified** except the file layout". The draft's own warning says Specified sections are ready to build, so this is a contradiction. The note sorts it as "Blocking (a milestone and the spec's engine choice)". `overview.md`, on this branch, still lists "OpenMDAO as the design study layer | Spec 5 | Dakota" under "Choices made without asking", and still says "specs 5 to 7 are at 0.2". Rule 5 says the overview changes in the same PR.
- **Fix:**
  - Make the heading "Specified except the file layout and the engine choice (OpenMDAO dropped: owner)".
  - Update the overview's spec 5 row and version line.
  - File one owner-decision issue per engine change.

---

## 4. Platform: Linux first, Windows via WSL 2

### S15. Mesa needs Python 3.12; Ithax supports 3.11 (blocking, a convention; missing from the draft)

- **Location:** adapter table "Mesa 3.5 (Apache-2.0) | in-process | ... Specified". The draft does not mention the Python version.
- **Problem:** Mesa 3.5.2 is `requires_python >=3.12`. `pyproject.toml` says `>=3.11`, CI tests 3.11 and 3.13 (`.github/workflows/checks.yml` line 31), and CLAUDE.md says "Python 3.11 or later". `spec-5-mesa.md` sorts this as "**Blocking (a convention)**", but the spec marks the agent domain Specified without it. SciPy 1.18, used in the design-study trials, is also 3.12-only (1.17.1 is the 3.11 lock), so a 3.11 floor also constrains the study libraries' versions.
- **Fix:** Add it to the owner questions. Options: (a) the agent adapter only on 3.12+, reporting E102 on 3.11, with its tests skipped on the 3.11 CI leg; (b) raise the minimum to 3.12 (the package already ships 3.13.16). Recommend (b): it is simpler, the package is unaffected, and it avoids a domain that exists on one CI leg and not the other. Either way it changes CLAUDE.md, `pyproject.toml` and the CI matrix, so it is a convention change for the owner.

### S16. Physical models need OpenModelica and a C toolchain, which the package does not carry (blocking, a target platform; missing from the draft)

- **Location:** "Physical systems": "`omc` runs as a separate process. FMUs are cached in the project ...". Nothing says how `omc` is installed.
- **Problem:**
  - `spec-5-openmodelica-fmu.md` sorts it as "**Blocking (a target platform)**: a machine without a C toolchain and OpenModelica cannot build an FMU". The options are (a) a documented apt install, or (b) bundling.
  - Under (a), a Linux or WSL 2 user must add OpenModelica's apt repository and install `build-essential` with sudo before any physical model runs. Spec 0's Purpose names exactly that ("need programming and Linux skills") as the gap Ithax closes. M24's row covers "the Linux package or the AppImage" only.
  - OpenModelica has not been installed or run in this research, so whether a portable FMU runs without its libraries is unknown.
  - More broadly, the draft never says which spec 5 engines ship inside the Linux package and AppImage, and which the "environment manager" (spec 1) installs later. That matters for package size, for principle 6 (offline after install) and for the M24 WSL 2 steps.
- **Fix:** Add a "Distribution" line per engine (bundled in the package, or installed on demand). Add the OpenModelica install question to the owner list, with the platform consequence spelled out. Recommended:
  - Mesa, PySD, FMPy, MuJoCo, scikit-learn, SALib, pymoo and faultree are bundled (all pure Python or manylinux wheels).
  - OpenModelica is an optional documented install for building physical models.
  - Shipped templates carry prebuilt FMUs, so a first template result needs no toolchain. This is conditional on the portability test.

### S17. Other platform notes (suggestion)

- None of the proposed Phase 2 engines needs conda, CUDA or a GPU: MuJoCo, JuPedSim, Mesa, PySD, FMPy, scikit-learn and faultree are manylinux or pure-Python wheels. Dropping Chrono removes the only CUDA, MKL and conda dependency (`spec-5-chrono.md`), which is a real gain for WSL 2. State that in the multibody section as a reason, so the owner sees the platform side of the choice.
- JuPedSim has no aarch64 wheel, and OpenSim is Linux x86_64 only. That is fine for WSL 2 on x86_64 Windows, but Windows-on-ARM WSL 2 is then excluded. Note it under the pedestrian and biomechanics items so the post-Phase 3 native build (#207) inherits the information.
- MuJoCo's bundled viewer needs OpenGL (WSLg). The draft does not use it; say so explicitly (ties to S5).
- Workforce settings change the `process` engine and spec 2's format. M19 (process constructs, format additions, same benchmark harness) may be a better home than M23 or M24, because it saves a second process-format bump. This is optional within S11.

---

## 5. Open questions: blocking against reversible (guide rule 5)

### S18. User-visible answers are marked Specified, though their notes sort them as blocking (blocking)

- **Surrogates** ("**Specified** except the file layout"): `spec-5-surrogates.md` sorts three items as blocking, user-visible: B-S2 (inputs outside the trained box: refuse or answer marked), B-S3 (which error is shown: leave-one-out RMSE) and B-S4 (refuse below max(5d, 10)). The draft states the proposed answer to each as settled.
- **NIOSH** ("**Specified**"): the formula against the manual's rounded tables, which differ by up to 1.7%. `spec-5-people-methods.md` sorts it as blocking (user-visible). The draft picks formulas with a 2% tolerance.
- **SPAR-H** ("**Specified**"): when the adjustment applies (three or more negative PSFs, or as in example 2). Sorted blocking (user-visible) in the note; the draft is silent.
- **FMU sources** (`spec-5-fmpy.md`): whether a project may hold outside FMUs. Sorted blocking (model format). The draft implies "only those Ithax builds" but never states it.
- **Problem:** Guide rule 5 says a question that changes a user-visible answer is blocking. It must be filed as an owner-decision issue, and work that depends on it is not started. Marking these sections Specified lets M23 build them without that step.
- **Fix:** Keep the recommended answers, but mark each as "Specified, default pending owner: <issue>", and file the issues.

### S19. The draft has no list of owner questions; there are more than ten (should-fix)

- **Location:** the whole draft. Open items are spread across 11 sections, and "Research before building" lists only OpenModelica and the multibody engine.
- **Problem:** "Questions before a milestone" requires every blocking question to be listed and filed before the milestone, and "Awaiting owner" holds at most ten. The sorting work is in the notes, but the spec has no single list. By my count there are about 20 blocking questions:
  - multibody engine;
  - JuPedSim and 2D geometry;
  - workforce settings;
  - Python 3.12;
  - the OpenModelica install and distribution;
  - outside FMUs;
  - OpenMDAO and Dakota dropped;
  - the study file layout;
  - the surrogate file layout and B-S2 to B-S4;
  - the chain file;
  - chain `/v1`;
  - maintenance-policy `failure` extension;
  - NIOSH;
  - SPAR-H;
  - RULA and REBA legal check;
  - the M23 split;
  - pymoo for M20 (S8);
  - the format minor (S9).

  The reversible ones are sorted correctly in the notes: default statistic and interpolation, fault-tree library, kernel choice, warning thresholds, jam reporting, the default PySD step, and XMILE import later. Two are mis-sorted. "Whether conveyors and vehicles need Chrono's modules", which `spec-5-mujoco.md` calls reversible, is a scope question if MuJoCo is chosen (S3). "Agent rule types checked against the templates M23 writes", also called reversible, decides what "agent-based" means in Phase 2 (S3).
- **Fix:** Add an "Owner questions" section to the spec, or to the council report, that lists each blocking question with its category (rule 5), options, recommended default, the milestone it blocks and a default date. Group them by the split milestone of S11, so the at-most-ten limit holds per milestone digest. The M23 questions go first (Python 3.12, chain file and `/v1`, workforce settings, the split); the M25 and M26 questions can wait. Move the two mis-sorted reversible items to blocking.

### S20. F9, F11 and F12 are not dispositioned (suggestion)

- **Location:** none in the draft.
- **Problem:** DECISIONS says "F9 to F19. Proposed by the agent council (F3), then reviewed by the owner", and phase-1-review line 319 leaves them "for the council of specs 5 to 7". `spec-2-simulation-optimization-literature.md` ties F9 and F11 to spec 5's "Combining engines", "Design studies" and "Surrogate models", and F12 to the remote target. The candidates there include SAA to join process simulation with HiGHS and SimOpt problems as benchmarks.
- **Fix:** The council report should say which F items concern spec 5, and either fold them into Phase 2 (if already covered: chaining and surrogates) or assign them to Phase 3 or 4 under F3.

### S21. Licences of in-process non-engine libraries are deferred (suggestion, outside the scope lens)

- Spec 1's engine licence rule and F4 ("engines run as separate processes") allow in-process use only once a licence is recorded in DECISIONS. The 2026-11-16 entry records seven engines. JuPedSim (LGPL-3.0-or-later), faultree, pymoo with moocore (LGPL-2.1-or-later), SALib and scikit-learn are in-process in the draft but not yet recorded. That is acceptable at adoption under CLAUDE.md, but the adapter table's "invocation" column should cite the F4 exception for each in-process engine, so the departure from F4's wording is visible.

---

## Summary

- **Blocking (6):**
  - S1: workforce framed as optional despite spec 0.
  - S2: pedestrians may silently leave Phase 2, or enter it as a new domain with geometry.
  - S6: no `/v1`, MCP or interface plan for studies, surrogates, chains and calculators.
  - S11: M23 is too large and mixes Specified with Open work; proposed split into M23 to M26, then WSL 2, MCP and release at M27 to M29.
  - S15 and S16: Mesa's Python 3.12 floor and OpenModelica's install and toolchain are platform and convention questions missing from the draft.
  - S18: surrogate, NIOSH, SPAR-H and FMU-source answers are marked Specified though the notes sort them as blocking.
- **Should-fix (10):** S3 (narrowings without phases), S4 (co-simulation without a phase), S5 (3D preview pulls spec 6 into Phase 2), S7 (B1's surrogate objective), S8 (pymoo decided for M20), S9 (format 0.4 collision), S10 (one or two templates), S12 (benchmarks without milestones, missing acceptance rows), S13 (M17 wording against F3, remote FMU builds, M26 roles), S14 (OpenMDAO under a Specified heading, stale overview, no owner issues), S19 (no consolidated owner-question list).
- **Suggestions (3):** S17 (platform notes; workforce settings into M19), S20 (F9, F11, F12), S21 (F4 exception per in-process engine).
- **Consistent with the plan:** the engine choices avoid conda, CUDA and GPUs, so WSL 2 is not threatened except by OpenModelica. The M22, M24 and M25 tags match the Phase 2 table. Co-simulation and OpenSim are correctly kept out of Phase 2. The MuJoCo change is flagged as an owner decision.
