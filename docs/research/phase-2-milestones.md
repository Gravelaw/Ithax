# Phase 2: a proposed milestone table

A draft for the owner to approve. The owner decisions of 2026-11-15, item 1, say: "The orchestrating session proposes the grouping and sends it to the owner. It proceeds unless the owner objects within a day." Changing the guide's milestone table is the owner's (D18), so the approved table goes into `docs/specs/build-guide.md` "Milestones" in a PR of its own.

Drafted on 2026-11-15 at `main` d28f91e.

## What Phase 2 holds

- **Spec 0's Phase 2 row:**
  - agent-based and system dynamics models;
  - physical system models and multibody dynamics;
  - people and workforce models;
  - optimization across engines;
  - the remote (SSH) run target (A1).
- **Decided by the owner:**
  - Windows (F5) through WSL 2, with the Linux package or the AppImage, until after Phase 3 (owner decision of 2026-11-16 on #207, which replaces the native installer of 2026-11-15 item 3);
  - objective types and several objectives (B1);
  - early ranking and selection (D1);
  - live key numbers (D4);
  - wider table imports (D6);
  - time-varying arrivals (D10);
  - the constructs of D11;
  - one failure per unit (D13);
  - editing indexed models in the views (D14);
  - data import through the assistant (D15);
  - the `sketch` preview (B7 item 1);
  - E1's Phase 2 items: the `feasible` status and the gap (M5-1, M5-10), duals first (M5-15), the MSER-5 comparison (M3-2) and a noise-aware search (M5-23).
- **The later-phase parts of accepted readings:** `docs/research/phase-1-review.md`, "Later-phase parts of accepted readings", every row marked "Phase 2 table". Each is named in a milestone row below (check: `tests/test_phase_2_milestones.py`, which also checks every code in this section).
- **The retrospective's Phase 2 items:** P12, P15, P16, P17, P18, P22, P23 and P25 (`docs/DECISIONS.md`, 2026-11-14, "Retrospective PR 6").
- **Rules that hold in every phase:**
  - specs 5 to 7 start with research, a small engine case and a council (B9, F3);
  - cheap performance budgets and regression checks (C4);
  - agent walkthroughs in roles as a gate (C1);
  - the last or second-to-last milestone is MCP hardening plus a trial with a different assistant (C6).

Not in Phase 2:

- the run response carrying warnings (#191, Phase 3);
- probabilistic calendars and multitasking (D11, Phase 3);
- 3D and field imports (D6, Phase 3);
- graphics detection on Windows and macOS (D7, Phase 4);
- a native Windows build, with its installer and code signing: after Phase 3, as refactoring and API work for the libraries that have no Windows build (#207);
- numeric targets for spec 0's six success measures: set after Phase 3; until then the measured values are baselines, not gates (#206);
- the cluster target (A1, Phase 4).

## Proposed milestones

Numbering continues the guide's, so Phase 2 starts at M17. Each row's "Done when" is what must be true before the next milestone starts (guide rule 2). As in Phase 1, issues are filed per item once the owner approves the table.

| # | Milestone | Spec | Done when |
| --- | --- | --- | --- |
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

## Readings (reversible)

1. **Order.** The Phase 1 parts that Phase 2 deepens come first (M18 to M21): they build on code that exists and has benchmarks. The remote target (M22) comes before spec 5's engines (M23), so that new engines are built able to run remotely. Windows through WSL 2 (M27) comes after the engines, so that its install steps cover them once.
2. **Spec 5 is one row** (M23) until its council has detailed it. B9 settles scope and phases during that detailing, so splitting it now would be guessing. The council proposed the split (#240), whose default applied on 2026-11-18: spec 5 is now M23 to M26, and the last three rows moved to M27 to M29.
3. **The interface follow-ups are one milestone** (M21), not spread across the others. Each is small, and together they touch the same screens.
4. **C6** is met by M28, the second-to-last milestone.
5. **The 0.1.x line** (`release/0.1`) takes cherry-picked fixes during Phase 2 (`docs/release/v0.1.0.md`). It is not a milestone.
