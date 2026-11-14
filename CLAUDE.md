# Ithax (lcsim): guide for coding sessions

This file is a map (retrospective P8). The build guide, `docs/specs/build-guide.md`, holds the
rules, milestones, known gaps and procedures, and decides wherever this file is shorter.
Milestone status is in `docs/STATUS.md`, decisions in `docs/DECISIONS.md` (one record per
decision from Phase 2, guide "Session procedure"), specs in `docs/specs/`. Read the guide sections and the
spec your issue names.

## Commands

- Install: `uv sync --locked --extra dev` (a dependency change also needs `uv lock`).
- While working: `bash scripts/fast.sh` (lint, types, fast tests in parallel).
- Before every commit, and what CI runs: `bash scripts/check.sh`; judge it by its exit code.
- Subsets: `pytest tests/model`, `pytest -m benchmark`, `pytest -m template`;
  performance: `taskset -c 0-3 pytest -m perf`; package: `pytest -m package` after
  `python scripts/package_linux.py`.
- Interface: `cd ui && npm run check && npm run build && npm run e2e`.
- Both scripts use `.venv/bin/python` when it exists: the first `ruff`, `mypy` or `pytest`
  on PATH may be another install. Run single tools as `.venv/bin/<tool>`.

## Rules (the guide's session rules, short form)

1. Read the guide sections and the spec for your milestone first.
2. Two or three milestones per session, in order; the next starts only when the current
   one's acceptance checks pass. Research notes before code (`docs/research/`).
3. Tests before implementation. Acceptance rows tagged with the milestone are the gates;
   benchmarks are gates; rows marked "owner" are listed, not gated.
4. Never guess silently (guide rule 5): a blocking question is filed as an "Owner decision"
   GitHub issue before the work; a reversible reading is logged in `docs/DECISIONS.md` and
   listed in one line under "Readings".
5. A decision that departs from a spec changes the spec in the same PR, with a dated line
   under its "Changes in this version". Never write to the owner's Claude Docs.
6. Wrap engines; never write a numerical solver. Calculators cite a formula and a published
   worked example.
7. Work starts from a GitHub issue. PRs: one purpose, under about 400 changed lines of
   product code, body from `.github/pull_request_template.md`. The orchestrating session
   merges (owner decision C10); a coding session never merges its own PR.
8. A second review finding of the same class in one PR: fix the whole class through one
   helper and add a check that catches the next one (guide "Review findings").
9. A count or CI result in the record is copied from a named command's output; a CI result
   with its run ID and head SHA.
10. End with a summary (`docs/sessions/<yyyy-mm-dd>-M<n>.md`: Built, Checks passing,
    Decisions logged, Awaiting owner, Readings, Left) and update `docs/STATUS.md`.

## Rules the tools enforce (do not work around them)

| Rule | Enforced by |
|---|---|
| Randomness only through the spec 1 stream scheme (`ithax.model.streams`) | ruff TID251 |
| JSON read and written only through `ithax.strict_json` | ruff TID251 |
| Files replaced only through `ithax.files.atomic_write` | ruff TID251, `tests/test_conventions.py` |
| Numbers checked with `strict_json.is_whole`, `is_number`, `whole_in`, `real_in` | `tests/test_conventions.py` |
| No input makes a loader raise; problems are issue objects with a code | `tests/properties/` (routes: review) |
| A model file that loads keeps loading; `/v1` responses keep their fields | `tests/compat/` |
| Layers: model < engines < runs, templates, findings < service < mcp, launcher | review |
| Warnings are errors; functions stay short | pytest `filterwarnings`, `tests/test_function_length.py` |
| Format, lint, types | hooks in `.claude/settings.json`, then `scripts/check.sh` |

## Conventions the tools do not check

- Python 3.11 or later; full type hints; mypy --strict over `src` and `tests`.
- Units are converted at load; no unit strings past the model layer.
- Engines write only inside their run folder.
- Each new dependency is recorded in `docs/DECISIONS.md` with its licence.
- Commits: small, one purpose, `M<n>: <imperative summary>`, `specs: ...` or `docs: ...`.

## Skills (`.claude/skills/`)

- `pre-push`: the fast checks and the review classes, before the first push.
- `review-reply`: answer and resolve a review finding.
- `owner-question`: file a blocking question as an "Owner decision" issue.
- `close-milestone`: the checks, the session summary and `docs/STATUS.md`.

## Where things are

- `src/ithax/`: `model/` (schema, loading, validation, edits), `engines/` (adapter, plugins
  `process/` SimPy and `optimize/` HiGHS), `runs/`, `service/`, `mcp/`, `findings/`,
  `templates/`, `launcher/`; `tests/` mirrors `src/`.
- `ui/`: the interface (React, React Flow; its own `npm run check`). `desktop/`: the Tauri
  shell. `packaging/linux/`: the Linux package.
- `benchmarks/<case>/`, `examples/`, `templates/`: data with known answers.
- `AGENTS.md`: the rules automated review follows.
- `docs/research/`, `docs/design/`, `docs/sessions/`, `docs/specs/`, `docs/retrospective/`.

## Things the code does not show

- uvicorn re-raises SIGTERM and SIGINT after shutdown; cleanup must not rely on `finally`
  after `server.run()` (M6 bug, fixed at M9).
- Seeded simulation outputs are asserted exactly in a few tests; a numpy or simpy upgrade can
  change them. Upgrade dependencies in their own PR.
- Linux first (owner decision B4, 2026-11-09): keep the code platform-neutral as built;
  Windows packaging is deferred.
- The Python package is `ithax`; the distribution, commands and folders still read `lcsim`
  until the second #70 change.
