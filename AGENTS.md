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
- a save of several files that restores old files after its commit point, or a recovery that
  admits a folder whose recorded change it could not finish: either can pair one revision with
  another's model (helper: `ithax.service.commit`, redo only; `tests/service/test_commit.py`
  stops the writer and its replay at every step; one lock per folder covers a whole commit or
  replay, so a replay never removes a later commit's record; PR #182, two rounds); also a
  filesystem error that escapes a commit or replay as anything but `CommitFailed` (a NUL's
  `ValueError`, an unreadable folder's `PermissionError`, a symlink loop's `RuntimeError` on
  Python 3.11): one guard over each whole call maps `commit.FILE_ERRORS`, and
  `tests/service/test_commit.py` raises each of them from each filesystem call (PR #182,
  fourth round); also a read of a project folder's model, `project.json` or column index made
  in a hold of the project's lock that did not settle the folder, which can see a save left
  half done in between (helper: `ModelStore.settled`; `tests/test_conventions.py` finds a
  reader outside one; PR #182, fifth round);
- interface state written from a stale draft or after a screen has closed.
