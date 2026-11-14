---
name: close-milestone
description: Close a milestone. Runs the full checks, writes the session summary from the template, updates docs/STATUS.md and lists the owner items in the digest format.
disable-model-invocation: true
---

# Closing a milestone

These steps come from the build guide's rules 8 to 10 and its "Session procedure" (retrospective P8 and P14).

1. **Gates.**
   - Every acceptance row tagged with the milestone passes (rule 10). Rows marked "owner" are listed in the summary, not gated.
   - Every benchmark passes (rule 8).
   - Every issue the milestone closes is closed on GitHub: check each one.
2. **Checks, each copied from its command's output** (guide "Numbers in the record"):
   - `bash scripts/check.sh; echo EXIT=$?`: the exit code and the test count from its last line.
   - `pytest -m benchmark` and `pytest -m template`: the passed counts.
   - `cd ui && npm run check && npm run build && npm run e2e`, when the interface changed.
   - The CI result of the last merged PR: its run ID and head SHA.
3. **Summary.** Write `docs/sessions/<yyyy-mm-dd>-M<n>.md` with these headings, in order:
   - Built.
   - Checks passing.
   - Decisions logged.
   - Awaiting owner: only blocking questions and owner checks, at most ten, each with its recommended default and the date it applies.
   - Readings: the reversible readings, one line each.
   - Left.
4. **Status.** Update the milestone's row in `docs/STATUS.md`: the date, what passes (with counts), the spec versions, and a pointer to the summary.
5. **Digest.** Send the orchestrating session (or the owner) the digest:
   - the open blocking questions, at most ten, each with a one-line recommendation and its default date;
   - the number of readings since the last digest, with a link to the summary.
6. **Merge.** Open the closing PR (`M<n>: ...`) and follow the `pre-push` skill. The milestone closes when its last PR merges.
