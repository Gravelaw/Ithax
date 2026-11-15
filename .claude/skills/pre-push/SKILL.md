---
name: pre-push
description: Check a branch before its first push or before reporting a PR ready. Runs the fast checks, then walks the review classes in AGENTS.md against the diff from main. Use it before every first push of a branch and before reporting a PR ready.
---

# Before the first push

Retrospective P8 and its evidence item 5: a review round costs 7 to 25 minutes, and catching a known class before review saves one.

1. Merge the latest `main` into the branch. Merge, do not rebase: `git fetch origin main && git merge origin/main`. Keep the trailers on the merge commit.
   - When `docs/DECISIONS.md` conflicts, do not resolve it hunk by hunk: git can count a line
     both sides share (a closing `- **Dependencies added:** none.`) as context and drop it.
     Take main's file whole and append the branch's own entries after it:
     `git show origin/main:docs/DECISIONS.md > docs/DECISIONS.md`, then add each `## ` entry
     of the branch (from `git show HEAD:docs/DECISIONS.md` during the merge, never from the
     conflicted file) whose heading main lacks.
   - Then confirm nothing was lost. The headings and the `Dependencies added` lines on the
     branch must number main's plus the PR's own:
     `grep -c "^## " docs/DECISIONS.md` and `grep -c "Dependencies added" docs/DECISIONS.md`,
     against the same counts of `git show origin/main:docs/DECISIONS.md`. A line diff
     (`grep -c "^-[^-]"`) cannot show a dropped line whose text appears elsewhere in the file.
   - That diff misses a line equal to one in another entry, such as `- **Dependencies added:** none.`: git pairs the lost one with its twin and shows no deletion (PR #189). So also compare counts: on the branch, the number of `## ` headings and of `- **Dependencies added:**` lines must each equal main's plus this PR's own new entries. Count each with `grep -c "^## " docs/DECISIONS.md` and `grep -c "^- \*\*Dependencies added:\*\*" docs/DECISIONS.md`, on the branch and on `git show origin/main:docs/DECISIONS.md`. `tests/test_docs.py` checks each milestone entry from 2026-11-13 on.
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
