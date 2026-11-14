---
name: owner-question
description: File a blocking question for the owner as a GitHub issue titled "Owner decision: <question>", with options, a recommended default, what it blocks and the date the default applies. Use it when a question changes a user-visible answer, the model format, the /v1 API, a target platform, a guide rule, a milestone or a convention.
---

# Filing an owner question

The build guide's rule 5 and its "Questions before a milestone" procedure (owner decisions F2, F8 and D18; retrospective P13 and P14).

1. Sort the question first. It is **blocking** only if it changes one of these:
   - a user-visible answer;
   - the model format;
   - the `/v1` API;
   - a target platform;
   - a guide rule, a milestone or a convention.

   Anything else is a **reversible reading**. Take the simplest reading and record it in `docs/DECISIONS.md` (and in the spec, with a dated line). List it in one line under "Readings" in the session summary. Do not file it.
2. Check that no open issue already asks it.
3. Open a GitHub issue from `.github/ISSUE_TEMPLATE/` (research or chore), titled `Owner decision: <the question>`. Give it the labels `phase:*` and `type:research`.
   - **Why and what:** the question in one sentence, and what prompted it.
   - **Options:** each option with its consequence.
   - **Recommended default:** one option and its reason.
   - **Blocks:** the milestones, issues or acceptance rows that wait on it.
   - **Default applies on:** a date, two days out (owner decision F8).
   - **Source:** the spec section or the issue.
4. List it under "Awaiting owner" in the session summary, with its default and date (at most ten items).
   - Build only what does not depend on it.
5. If the date passes unanswered, record it in `docs/DECISIONS.md` as "default applied" and go ahead.
