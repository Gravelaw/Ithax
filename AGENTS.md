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
- a value typed in a unit sent as something it does not mean: a result past a finite number
  sent as `null` (the default), a non-zero entry rounded to 0 (the idle timeout's "never"),
  a sentinel reached by typing (helpers: `typedInBase` and `inSize` in
  `ui/src/results/display.ts`; `ui/src/results/units.test.ts` checks every unit with 0, tiny,
  huge, negative and NaN entries, and fails when other interface code scales by a unit's
  size; PR #196, two findings);
- interface state written from a stale draft or after a screen has closed;
- the focus moved into the side panel while it is a closed overlay, where the target is hidden
  and inert, so the action does nothing (helper: `useSheet`'s `reveal` in
  `ui/src/canvas/SideSheet.tsx`, which opens it first; `SideSheet.test.ts` fails when
  `CanvasScreen.tsx` looks up an element by id itself; PR #192, two findings).
- a project read or changed outside App's one queue of actions (Home, a dialog, the Build
  form or App itself calling a project request directly), so a removed project reopens, an
  older name, list or lesson step is shown, or the open project is kept after removal
  (helper: `run` and `ProjectApi` in `ui/src/app/projectActions.ts`, with App's actions
  taking the `api`; `projectActions.test.ts` fails when code in `app/` or `screens/` other
  than `projectApi` calls a project request; while an action is pending Home disables the
  actions that conflict and says so; PR #201, seven findings).
- an answer that arrives after other requests or actions, acted on against the state known
  when its request was sent: a read sent before or during a write that puts back the old
  value, overlapping writes answered out of order, a completion that ends what a newer
  action started. Serialize the reads and writes of shared state in one queue; do not
  reconcile answers by their order (helper: `oneAtATime` in `ui/src/components/oneAtATime.ts`:
  the settings provider sends every settings read and write through one, and App's project
  actions run in one; `useCurrent` in `ui/src/components/useCurrent.ts` for an action that
  reads state when it runs, not when it was queued; a test per site lets a slower request
  finish after a newer action; PR #200 and its stack, four findings).
- a review checklist or spec edit that leaves out part of an accepted decision: a decision
  with a now-part and a later-phase part kept only for its first part, or an open owner
  question in a spec that a decision has already answered. Map every owner-decision item,
  every later-phase reading and every open spec marker to a row (check:
  `tests/test_phase_1_review.py` fails on any item of `docs/DECISIONS.md` or the session
  summaries, or any spec line saying "owner question", "deferred" or "Phase 1 review", that
  `docs/research/phase-1-review.md` "Coverage" does not name; PR #208, two findings).
- a wrapper or entry point that runs a command as its child (not by `exec`), or stays after
  it, and does not stop what it started when it is stopped itself: a signal that leaves the
  child, or a service it outlives, running, or lets go of files they still use (helper: the
  one `stop` handler in `packaging/linux/appimage/AppRun`, set in every phase, which
  remembers a stop; check: the table
  `test_a_signal_in_any_phase_stops_everything_from_the_appimage_before_apprun_ends` in
  `tests/linux_package/test_appimage_build.py`, every phase against TERM, INT and HUP, with
  and without a service started; PR #211, three findings). Such a wrapper also closes no
  descriptor it inherits: the AppImage runtime's keepalive pipe is one
  (`test_apprun_keeps_every_descriptor_it_inherits`).
