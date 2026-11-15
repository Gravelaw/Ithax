# Changelog

All notable changes to Ithax are listed here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html), written to PEP 440 in the
Python package (owner decision F7, 2026-11-13).

**Compatibility within 0.x (F7):**

- The model format and the `/v1` API change only additively. A model file that loads keeps
  loading, and a `/v1` response keeps its fields (`tests/compat/`).
- Behaviour within 0.x is the current behaviour, not frozen (E1).
- A change that cannot meet this needs a new format or API version and an owner decision.

## [Unreleased]

## [0.1.0] - not yet released

The first release: Phase 1 (milestones M1 to M11) and Phase 1a (M12 to M16). It runs on Linux
on x86_64 and needs no network once downloaded. The owner tags and publishes it (owner
decisions, 2026-11-15).

### Added

- **Model format 0.3.** One JSON file holds a process or optimization model. It has units
  on every time and rate, parameters, scenarios and experiments. Validation reports every
  problem as an issue with a code, a place and a hint; no input makes the loader fail
  (specs 1 and 2).
- **Process simulation on SimPy.** The blocks are source, server, queue, delay, branch,
  batch, unbatch, store, resource pool, schedule, failure and sink. Runs have replications,
  warm-up, seeds and confidence intervals, and every block is checked against a benchmark
  with a known answer.
- **Optimization.**
  - Linear and mixed-integer models on HiGHS through Pyomo, with indexed sets and tables.
  - A simulation-based search on Optuna, whose candidates are confirmed with fresh random
    numbers, and whose best is labelled "best of N tried, not proven".
- **The engine service** (`/v1` HTTP and WebSocket API) for projects, models, data import
  (CSV and Excel), runs, results, findings, settings and licences. It listens on 127.0.0.1
  only and checks a token.
- **The MCP server** (`ithax-mcp`), so an AI assistant can build, check, run and explain a
  model through the same API.
- **Findings** in plain words: the bottleneck, instability, idle capacity, too few runs, and
  optimization results.
- **The interface**, in the desktop shell (Tauri) or the browser: Home, the Canvas, Data,
  Experiment, Run monitor, Results with charts and exports (CSV, PDF, project zip),
  Settings and Help. Help lists the open source licences of every package and engine.
- **Ten templates with lessons.** Learn mode walks through each one, ending in a
  predict-and-run exercise; the Build form picks a template from two questions.
- **The Linux package.** A self-contained archive, which installs commands and a menu entry,
  and an AppImage. Each comes with a SHA-256 checksum and is unsigned.

### Fixed in Phase 1a

- **Correctness (M13).**
  - Negative samples are caught.
  - The store's inventory position follows the textbook.
  - Warnings cover schedules, failures and pools.
  - Zero-time loops are guarded.
  - Solver values are cleaned.
  - Crossed variable bounds and plans with nothing to decide are errors.
  - Rate units are allowed in constraints.
  - Alternate optima are warned about.
- **Data safety (M14).**
  - Model saves are atomic.
  - The service stops in bounded time.
  - Large optimization results stay small.
  - MCP edits are typed.
- **Usability (M15).**
  - Numbers, units, metric names and messages are in plain words.
  - The Canvas works at 200% text and in narrow windows, and shows every error at once.
  - Results lead with the comparison.
  - Recent projects can be renamed and removed, and lessons resume where they were left.
  - The idle timeout is set in minutes, hours or days, or never.

### Known limitations

- Linux only. A Windows installer is planned for Phase 2 (F5).
- Unsigned packages: check the SHA-256 checksum (spec 0 "Risks").
- The remote (SSH) run target is Phase 2 and the cluster (Slurm) run target Phase 4. Both
  are refused with E172 until then.
- Several defaults are proposals that the owner has still to confirm, marked "owner to
  confirm" in the specs.

[Unreleased]: https://github.com/Gravelaw/Ithax/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Gravelaw/Ithax/releases/tag/v0.1.0
