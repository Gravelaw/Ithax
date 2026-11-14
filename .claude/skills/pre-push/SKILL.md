---
name: pre-push
description: Check a branch before its first push or before reporting a PR ready. Runs the fast checks, then walks the review classes in AGENTS.md against the diff from main. Use it before every first push of a branch and before reporting a PR ready.
---

# Before the first push

Retrospective P8 and its evidence item 5: a review round costs 7 to 25 minutes, and catching a known class before review saves one.

1. Merge the latest `main` into the branch. Merge, do not rebase: `git fetch origin main && git merge origin/main`. Keep the trailers on the merge commit.
   - When `docs/DECISIONS.md` conflicts, keep both entries in date order, with main's first.
   - Then confirm nothing was lost: `git diff origin/main -- docs/DECISIONS.md | grep -c "^-[^-]"` must print 0.
2. Run `bash scripts/fast.sh` and judge it by its exit code.
3. Read `git diff origin/main...HEAD` against each heading of `AGENTS.md` "Code Review Rules". For each class the change could reach, name the shared helper it uses, or fix it:
   - numbers: `ithax.strict_json.real_in` and `whole_in`;
   - JSON: `read_json`;
   - paths: `ithax.service.paths.canonical`;
   - file writes: `ithax.files.atomic_write`;
   - loops and waits: a cancellation check and a time limit.
4. Check the rest of the change:
   - New behaviour has a test.
   - A fix has a fixture or benchmark that fails before it and passes after.
   - A departure from a spec changes the spec in the same PR, with a dated line (guide rule 6).
   - A new dependency has its licence in `docs/DECISIONS.md`, and `uv lock` was run.
5. Run `bash scripts/check.sh; echo EXIT=$?`, plus `pytest -m benchmark`.
   - Also run `cd ui && npm run check` when `ui/` changed.
   - Never commit after a non-zero exit.
6. Count the product lines: `git diff --stat origin/main...HEAD -- src ui/src`. Keep it under about 400 (guide "Pull requests").
