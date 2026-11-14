# AGENTS.md

Coding sessions in this repository follow `CLAUDE.md`. This file steers automated review
(docs/retrospective/proposed-agent-setup.md, P7; #99).

## Code Review Rules

### Scope

- Review against the specs in `docs/specs/` and the build guide, `docs/specs/build-guide.md`.
  Do not comment on formatting or style: ruff and mypy --strict gate those.
- Do not ask for a guard against input that the spec says cannot reach that code.

### Treat as P1

- A process, worker or lock left behind after a stop, cancel or failure.
- Any file, request body or setting whose content makes a code path raise instead of returning
  an issue object (spec 1 "Issues").
- A write outside the project folder or the run folder.

### Classes that recurred in Phase 1

These are in `docs/retrospective/phase-1-engineering-review.md`. Look for them on every change
that reads input, and say whether the shared helper was bypassed:

- integers beyond float range, values near 1e308 and their sums, NaN and infinity
  (helpers: `ithax.strict_json.real_in`, `ithax.strict_json.whole_in`);
- a quantity scaled by a unit's size by hand (`value * 3600`, `seconds / 60`), which
  overflows near 1e308 or turns a finite rate into "inf per hour" (helpers:
  `ithax.model.units.in_unit` and `UNIT_SIZES`; `inUnit` in `ui/src/results/display.ts`;
  `tests/test_conventions.py` flags a literal 60, 3600 or 86400 outside `units.py`; PR #165);
- lone surrogate strings, JSON `null` where an object is expected, duplicate keys, and keys
  such as `constructor` in the interface (helper: `ithax.strict_json.read_json`);
- Windows paths without a drive, symlink or junction aliases, `..` after a link
  (helper: `ithax.service.paths.canonical`);
- loops that never check for cancellation; waits with no time limit;
- interface state written from a stale draft or after a screen has closed.
