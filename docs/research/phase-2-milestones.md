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
  - Windows (F5), unsigned at first with a SmartScreen note and a checksum (2026-11-15, item 3);
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
- **The later-phase parts of accepted readings:** `docs/research/phase-1-review.md`, "Later-phase parts of accepted readings", every row marked "Phase 2 table". Each is named in a milestone row below (check: `tests/test_phase_2_milestones.py`).
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
- the cluster target (A1, Phase 4).

## Proposed milestones

Numbering continues the guide's, so Phase 2 starts at M17. Each row's "Done when" is what must be true before the next milestone starts (guide rule 2). As in Phase 1, issues are filed per item once the owner approves the table.

| # | Milestone | Spec | Done when |
| --- | --- | --- | --- |
| M17 | Phase 2 setup and research | Guide, 5 | The retrospective's Phase 2 items are applied or listed for the owner: P15 (one file per decision from Phase 2), P16 (import layers checked) and the rest. Spec 5's research session, small engine case and council report are done (F3), and spec 5 is detailed for the owner's approval. Research notes exist for D10, D11, MSER-5 against the warm-up check (M3-2), the B1 engine trial (Ipopt or SCIP through Pyomo), the D1 method rule and a noise-aware search (M5-23). |
| M18 | Simulation statistics | 1, 2 | Ranking and selection with fresh-random-number confirmation, chosen by a transparent rule (D1), passes its benchmarks. The noise-aware search replaces "best of N tried" where it applies (M5-23). The warm-up check is kept or replaced as M17's note found (M3-2). A `sketch` preview fidelity runs (B7 item 1). A search runs within each scenario (M5-21). |
| M19 | Process constructs | 1, 2, 4 | Each of these has a benchmark with a known answer and a spec 1 format change that only adds:<br>• time-varying arrivals, a source schedule (D10);<br>• reneging, assembly, periodic and order-up-to stock with ordering in multiples, and partial availability (D11; M4-15);<br>• one failure process per unit (D13);<br>• item attributes, priority and attribute routing;<br>• a `<store>.queue_length` metric (M4-20);<br>• overlapping shifts as an error (M4-29).<br>A finding rule judges resource pools (M8-5, M10-67). |
| M20 | Optimization | 1, 2 | Duals are served first (M5-15). A solve stopped with a good solution is `feasible`, with its gap and the `time_limit` and `mip_gap` settings (M5-1, M5-10). Sets take aliases, and bounds and tables per member (M10-30, M10-31). A whole number too large for a float to hold exactly has its own validation code (M5 "Left", AKS-108). Nonlinear and mixed-integer nonlinear models run on the engine M17 chose. Weighted sum, ε-constraint and Pareto search (NSGA-II on simulations) have a trade-off-front view (B1). |
| M21 | Data and interface | 3 | Wider table formats with a progress bar, for example Parquet (D6). The import reads other encodings, delimiters, a sheet choice and non-ASCII names (M6-54, M6-55), and changes a column's unit without importing again (M6-53, M9-61). The Run monitor shows live key numbers and a search's candidates (D4; M6-48, M9-79, M9-80). Indexed models are edited in the Table and Diagram views (D14; M9-56, M10-38). The edits gain removing a field and a setting (M6-28, M9-24), a rename shown as one change (M9-44), and plain words for an edit's paths (M10-53). The interface follow-ups:<br>• a last-edited time on Home (M9-14);<br>• a data event on the project's events, and one session per project shared by its screens (M9-65, M9-66);<br>• the "{n} combinations" line with B6's run count (M9-71);<br>• code splitting for the charts and the bundle size (M9-74, M9-95, M9-105);<br>• sorting, filtering and "Use" in the trials table (M9-81);<br>• the dot strip, the interval-shrinkage chart and the canvas overlay (M9-84);<br>• embedded fonts and charts in the PDF (M9-88);<br>• the shell's capabilities, plugins and folder picker (M11-32);<br>• the palette's filters and sorting (M9 design review, choice 12). |
| M22 | Remote (SSH) run target | 1, 3, 4 | The `remote` target runs a model on another machine over SSH, tested against a local sshd (spec 1's Phase 2 acceptance row). `run_model` takes a `target` (M7-13). A run-time issue crosses SSH (the M13 command-line worker). E172 no longer refuses `remote`. |
| M23 | Spec 5 models | 5 | The models of spec 5 as detailed at M17, each engine wrapped, never written: agent-based, system dynamics, physical systems and multibody, people and workforce, optimization across engines. Every model type has benchmarks and a template. M17's council may split this row into several milestones. |
| M24 | Windows | 0, 3 | A Windows installer, native or through WSL as #207 decides, holds the interface, the service and the engines. It is unsigned, with a SmartScreen note and a checksum (2026-11-15, item 3), and reaches a first result in under ten minutes (spec 3's Windows row). The shell's Windows build uses WebView2. |
| M25 | MCP hardening | 4 | Every Phase 2 feature has its thin API and MCP tool with a parity test (C6). A data import tool exists for assistants that can send files (D15; M7-19). The MCP server runs over Streamable HTTP as well as stdio (M7-1). A trial with a different assistant is recorded under `docs/research/mcp/`. |
| M26 | Phase 2 release | 0 to 5 | Agent walkthroughs in student and business-analyst roles pass (C1). The performance budgets hold (C4). The Phase 2 review's changes are in the specs. The owner checks are done, and v0.2.0 is tagged by the owner. |

## Readings (reversible)

1. **Order.** The Phase 1 parts that Phase 2 deepens come first (M18 to M21): they build on code that exists and has benchmarks. The remote target (M22) comes before spec 5's engines (M23), so that new engines are built able to run remotely. Windows (M24) comes after the engines, so that its installer packages them once.
2. **Spec 5 is one row** (M23) until its council has detailed it. B9 settles scope and phases during that detailing, so splitting it now would be guessing.
3. **The interface follow-ups are one milestone** (M21), not spread across the others. Each is small, and together they touch the same screens.
4. **C6** is met by M25, the second-to-last milestone.
5. **The 0.1.x line** (`release/0.1`) takes cherry-picked fixes during Phase 2 (`docs/release/v0.1.0.md`). It is not a milestone.
