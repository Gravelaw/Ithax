# Phase 1 engineering review

AKS-143, 2026-11-09. A retrospective of how Phase 1 (M0 to M10, 2026-11-05 to 2026-11-09) was built, not of what was built. The proposals that follow from it are in [`proposed-agent-setup.md`](proposed-agent-setup.md). Nothing here changes a spec, the build guide, CI or the code. The owner decided on 2026-11-09 (B2) that such changes are drafted for approval first.

**How to read the claims.** Each claim about this project names its evidence: a PR, run, commit, file and line, Linear issue or e-mail. Each claim about outside practice carries a link. Text marked *(judgement)* is the reviewer's opinion, not a finding. Numbers were collected on 2026-11-09 from:

- the GitHub REST API: 58 PRs, 478 workflow runs, 971 jobs, 100 Codex review threads;
- a full clone of `main` at `f36a6f5` (440 commits; the session checkout is shallow and shows 396);
- `docs/DECISIONS.md` and the ten `docs/sessions/*.md` summaries;
- the 74 Linear issues in P-AKS-2;
- the owner's Outlook mailbox (GitHub billing mails, "Run failed" mails, Codex mails);
- static analysis of `src/` and `tests/` (radon, grimp, jscpd, vulture, mypy, ruff, coverage with branches);
- two timed local test runs.

**What could not be established.**

- When the repository was made public. The API has no visibility-change timestamp. The event feed puts it shortly before 06:51 UTC on 2026-11-09.
- Whether a given merge was done by the owner or by an agent. Every merge and every Linear comment is under the owner's own account (`Gravelaw` on GitHub, "Akshay" on Linear).
- How many clean Codex passes there were. Codex creates a review object only when it has findings, and edits one summary comment in place, so earlier clean passes cannot be counted.
- The full count of Codex mails. Only 50 were counted.

## Summary

Phase 1 delivered a working product in about 80 hours of elapsed time from M1 start to M10 close. That covers:

- 15,981 lines of Python product code (radon SLOC; 19,602 effective lines with docstrings) and 29,631 of Python tests (SLOC);
- 3,892 passing tests, with 100% line coverage and 99.6% branch coverage (2,899 of 2,910 branches; measured, not gated);
- mypy `--strict` clean over 237 files;
- every benchmark passing against theory.

The gates held. No lint or type failure ever reached CI, and all 351 non-merge commits follow the message convention.

The costs were in the process around the code, not in the code itself. Ranked by what they cost:

1. **Owner decisions arrived after the work that depended on them.**
   - Eight of the ten council questions waited 76 hours for an answer. Two answers changed defaults that M3 to M6 had already built: one (B5, the idle exit) means rework, and one (B4) deferred the Windows work already done.
   - The session summaries hold 402 "Awaiting owner" items, about 386 of them rule-5 readings. That is more than the "about 330" in the brief. The owner has ruled on 4.
2. **The same classes of bug kept coming back, and were fixed one call site at a time.**
   - Codex left 100 findings on PRs #1 to #56. 29 were in the input-robustness family: numeric edge cases, unvalidated input, and exceptions instead of issues. Most were hostile or extreme input (huge numbers, NaN or infinity, lone surrogates, `null`, inherited keys) crashing a code path instead of producing an issue. They span 16 PRs from M1 to M10.
   - Shared helpers existed but were bypassed.
   - There is not one property-based test.
3. **CI was slow and expensive, and once stopped altogether.**
   - The free Actions minutes ran out at 20:56 UTC on 2026-11-08, after a 90% warning mail at 16:35 that no agent could see.
   - No job ran for 9 h 43 min.
   - Each Python job took a median of 4.8 to 6.2 minutes (p90 about 10.5 minutes). Benchmarks ran twice on every push.
4. **The stacked-PR workflow added manual steps, hid failures and blurred who merged.**
   - 17 PR bases were changed by hand, and 33 extra merge commits synced fixes up the stacks.
   - Merging in bursts cancelled 61% of the CI runs on `main`.
   - PR #49 was merged 37 seconds after its last push, before CI finished. The `interface` job then failed on its head and on `main`, and the record says CI passed.
5. **The written record outgrew the agents that must read it.**
   - `docs/DECISIONS.md` is 610 KB, about 150,000 tokens, and was touched by 36% of all commits.
   - Specs 1 to 4 total 393 KB. `CLAUDE.md` is 24 KB.
   - Several figures in the record are wrong: the M9 "CI passed", "27 findings" (30 in fact), a false "in progress" status, and two real CI failures that were never logged.

The opportunities follow directly. Each is ranked in the proposals document.

- Decide early and in small batches.
- Turn recurring review findings into shared helpers, lint rules and property-based tests.
- Run tests in parallel, and split a fast inner gate from a full outer gate.
- Merge each PR to `main` as soon as it is green, with GitHub deleting branches and retargeting stacks automatically.
- Shrink `CLAUDE.md` to a map, and move standing rules into hooks.

## What worked

**The code-quality gates were real, and nothing bypassed them.**
- `scripts/check.sh` runs ruff format, ruff check, mypy `--strict` over `src` and `tests`, and pytest with coverage.
- CI ran the same script on Python 3.11 and 3.13.
- Of 28 failed CI jobs, none failed lint, format or types. Everything of that kind was caught before pushing (CI and git mining).
- The 100% line figure is honest: there is exactly one `pragma: no cover` in `src`, at `mcp/limits.py:27` (a `TYPE_CHECKING` block).
- Branch coverage, measured here but not gated, is 99.6%.

**Tests came first, and the benchmarks anchor correctness to theory.**
- M/M/1, M/M/2, tandem, the M4 blocks, and the LP, knapsack, assignment and diet benchmarks all pass under the spec 2 statistical pass rule (`pytest -m benchmark`, 19 passed at M10).
- Templates reproduce theory- or benchmark-sourced values (`tests/templates/test_templates.py`).

**The architecture is clean at the level of functions and layers.**
- Mean cyclomatic complexity is 3.44 across 1,261 blocks, with 4 at grade D and none worse.
- jscpd finds 0 clones at 70 tokens.
- `model` never imports `service`, `runs` or `mcp`, and `runs` never imports `service`.
- Engines are plugins, reached only through `engines/adapter.py` and the entry-point registry.
- MCP talks to the service over HTTP rather than calling it in-process.

**User-facing errors have one model.**
- Every user-facing error is an `Issue` object with a validated code, JSON Pointer path, message and hint (`model/issues.py`).
- The service returns one error body through 4 handlers (`service/errors.py`).
- Of the 18 `except Exception` sites, all those inspected are at plugin or third-party boundaries and log the traceback. There is no bare `except:`.

**Review comments were handled with discipline.**
- All 100 Codex threads on PRs #1 to #56 got a reply, 99 of them naming the fix commit, and all were resolved.
- After repeated findings on one mechanism, sessions redesigned it rather than patching it again: queue transfers on #27 and path handling on #34 (the new `service/paths.py`), each after a third finding; admission on #35; run completion on #36, after a second CI timing failure; and canvas writes on #45, after five redesigns in a row.
- The redesigned path module is now a strength: `canonical()` has 21 call sites, and `os.path` appears in only two modules.

**Reviewing the specs before coding paid for itself.** Codex's 7 findings on PR #1 were spec bugs found before any code existed. Examples are utilization reaching 2.0 off shift, and work-in-progress never dropping discarded items (PR #1 threads).

**Commit and PR hygiene was consistent.**
- All 351 non-merge commits conform to `M<n>:` or `specs:`.
- Every PR title passed `pr-title.yml`.
- Only the root commit was pushed straight to `main`.
- Every milestone left a session summary with "Awaiting owner" and "Left" sections, and the counts each summary states match its own list.

**The service is designed to survive.** The service, MCP server and interface work with outbound network blocked (`tests/service/test_offline.py`). A run survives a client disconnect (`tests/service/test_run_disconnect.py`). The MCP tools are confined to the project folder (`tests/mcp/test_mcp_confinement.py`).

**Using an assistant before the interface existed worked as intended.** M7 came before M9 on purpose. A real-assistant trial revised two tool descriptions at M7 (`docs/research/spec-4-mcp-trial-2026-11-08.md`), and at M10 an assistant built all ten template problems from text descriptions (`docs/research/mcp/`).

## Weaknesses and mistakes

The weaknesses are ordered by estimated cost. Cost is given in what can be measured (hours, review rounds, CI minutes, rework). Where it cannot be measured, the cost is described and marked *(judgement)*.

### W1. Owner decisions came after the work that depended on them

**Evidence**

- **Eight of the ten council questions (AKS-74 to AKS-79, AKS-81, AKS-84) waited 76.4 hours.** Q5, the licence (AKS-83), was deferred by the owner on 11-07. AKS-80 is only partly answered.
  - They were raised in `DECISIONS.md` on 2026-11-05 (lines 188 to 248) and filed as AKS-74 to AKS-84 (AKS-82 is the owner checks, not a council question) at 05:15 UTC on 11-06.
  - They were answered at 09:41 UTC on 11-09 (`DECISIONS.md` lines 1975 to 2061, PR #51).
  - Meanwhile M4 built the block defaults (AKS-76, "Blocks: M4"), M6 built Windows support and the lifetime rules (AKS-77 and AKS-78, "Blocks: M6"), and M9 took the walkthrough fallback (AKS-79).
- **Of 14 explicit owner verdicts** (the council questions plus the four M5 items), 5 confirmed the default, 6 overturned or modified it, and 3 deferred it. Counting B7's two confirmed items separately gives 6 confirmed.
  - B4 replaced native Windows with "Linux first", after M3 to M6 had built platform-neutral code with Windows paths (msvcrt locking, Windows path handling, memory limits; `docs/sessions/2026-11-06-M3.md:81,82,86`, `2026-11-07-M6.md:142`). The code is kept, and the Windows installer is deferred to a phase the Phase 1 review sets.
  - B5 turned the 30-minute idle exit into a setting, which is M11 rework (AKS-141).
  - A1 moved the remote and cluster targets out of M11 altogether.
- **Rule 5 ("take the simplest reading, log it, flag it") produced 402 numbered "Awaiting owner" items** across the ten milestone summaries: 386 readings and 16 owner checks.
  - Counting the sub-bullets that M1 to M3 used gives 455.
  - By milestone: M1 11, M2 7, M3 6, M4 40, M5 33, M6 68, M7 25, M8 26, M9 103, M10 67.
  - The "about 330" in the brief is an undercount, and no natural subset gives 330.
  - The orchestrator's own count on AKS-130 (2026-11-08 08:41) was "about 250 items. About 20 of them need a real owner choice". That agrees with the granular count for M1 to M7: 263 items, 259 of them readings.
- **The owner has ruled on 4 of the 386**, all from M5 (`DECISIONS.md:1382-1423`): two overturned, one modified, one deferred. The rest wait for AKS-130, the Phase 1 review, which is in Backlog.
- **AKS-82** (the owner checks and the low-tier performance confirmation) has been carried in every summary from M3 to M10 and is still Todo after 85 hours.

**Cost**

- Rework already scheduled: the idle-exit setting at M11 (AKS-141).
- Windows code paths whose use is now deferred, with their tests to maintain until then.
- 386 unreviewed readings. Each will either be accepted blind or cost owner time now that the build has moved on.
- The ratio is the important figure: the orchestrator judged about 20 of the first 250 as real choices. The process asked the owner to read every reading in order to find those 20 *(judgement)*.

### W2. Recurring classes of bug were fixed locally, not systematically

**Evidence**

- **Codex left 100 inline findings on PRs #1 to #56:** 2 P1 and 98 P2, on 29 of the 56 PRs, over 72 review rounds that had findings.
- **The largest family is input robustness: extreme or hostile input reaching a path that raises instead of returning an issue.** It holds 29 findings on 16 PRs: 15 numeric edge cases, 10 input-validation, and 4 error-handling cases (an exception or HTTP 500 instead of an issue). A few, such as a rounded contrast ratio (#6) and a chart axis clipping negatives (#48), are numeric slips rather than hostile input. The core of the family recurs across milestones:

  | Bug class | PRs (milestone) |
  |---|---|
  | Huge integer or float overflows, or becomes infinity (10\*\*309, 1e308, 1e400, sums reaching inf) | #4 (M1), #9, #10 (M1), #15 (M2), #18 (M2), #35, #36, #37 (M6), #53 (M10) |
  | Malformed input surfaces as an exception or HTTP 500 instead of an issue | #5 (M1), #35, #36 (M6), #39 (M7), #50 (M10) |
  | Lone surrogate or unencodable string | #35 (M6), #50 (M10) |
  | Inherited `constructor` key read as data | #46 (M9) |

- **Every fix was local.** Each PR added a gate at the site Codex named, such as `fits_in_seconds` and `CoefficientTooLarge` (PR #34 to #56 mining, section 5).
- **Shared helpers existed and were not used.**
  - `strict_json.encode_json` is re-typed verbatim in 5 other places (`engines/process/translate.py:88`, `engines/optimize/adapter.py:111`, `engines/optimize/translate.py:74`, `runs/tables.py:66`, `runs/manifest.py:140`).
  - There are 5 different policies for reading JSON back. Only the model loader detects duplicate keys.
  - "Integer but not a bool" is defined three times under three names, plus about 8 inline copies (16 `isinstance(..., bool)` sites in 11 files).
  - Atomic file writes are hand-rolled at 8 sites, with three naming schemes and no `fsync`.
  - `strict_json.whole_in` and `real_in` are used in 9 files, but not by the model loader or validation, `mcp`, `findings` or `discovery`.
- **No test generates inputs.** There is no `hypothesis` in `pyproject.toml` or `tests/`, and no property-based test in either language.
- **The second-largest family is process lifetime and cancellation:** 11 findings plus one late bug.
  - #18: sampling loops that ignore cancel.
  - #24: 6 findings in `runs/targets.py`, among them a P1 for descendant processes left running, a lost cancel, unbounded joins, and a run stuck in "running" when the worker failed to start.
  - #27: a self-fed queue never yields.
  - #34: concurrent service starts.
  - #36: a worker never reaped.
  - The stale `service.json` after SIGTERM: introduced in 7dc2fd0 (M6, #34), found at M7 (`DECISIONS.md:1644`), fixed in 269f5ec (M9, #44). The M6 tests "stop services without asserting the removal" (`docs/sessions/2026-11-08-M7.md:100`).

**Cost**

- Each recurrence cost at least one Codex round. The gap between rounds was typically 7 to 25 minutes, and sometimes over an hour (round timestamps on #34 and #45).
- The two worst milestones were the longest:
  - M6 had 13 rounds with findings, and AKS-110 took 14.1 h.
  - M9 had 17 rounds, and AKS-119 took 19.1 h.
- The Codex bot, not the test suite, was the effective gate for this whole class. CI never caught a logic bug in PRs #1 to #33; its only real catches in Phase 1 were 3 timing races (CI mining).

### W3. CI was slow and expensive, and its outage stopped merging

**Evidence**

- **Free minutes ran out on 2026-11-08.**
  - GitHub mailed "used 90% of the Actions minutes included for the Gravelaw account" at 16:35 UTC (1,809 of 2,000 minutes), then "100%" at 20:56.
  - The same account had hit 100% before, on 2026-07-13 and 2026-09-24.
  - From 21:08:58 to 22:01:29 UTC, 25 jobs on PRs #48 and #49 failed in 1 to 4 seconds. The annotation reads "The job was not started because recent account payments have failed or your spending limit needs to be increased" (job 128862565923).
  - Actions was blocked for 9 h 43 min, from 21:08 UTC until two runs were re-run at 06:51:36 UTC on 11-09. No new run was created after 22:01. M9 merged 13 minutes after the re-runs.
- **Where the minutes went.** Billed minutes before the first blocked job came to 2,027, with each job rounded up to a whole minute. Over the whole build, raw minutes were 2,645 and billed minutes 3,289:
  - `checks (3.11)` 1,000 raw minutes, `checks (3.13)` 969, `benchmarks` 368, `interface` 294;
  - `pr-title` took 14 raw minutes but about 245 billed, because each 3-second run is billed as a full minute;
  - cancelled jobs 125, failed jobs 38.
- **Benchmarks ran twice on every push.** The `benchmark` marker is not excluded in `pyproject.toml` `addopts`, so `check.sh` runs them, and the `benchmarks` job runs them again. That is about 368 raw minutes, 14% of the total.
- **The Python jobs are slow.** Median `checks (3.11)` time was 6.2 min (p90 10.3, max 12.3). Locally the suite takes 384.6 s serially on 4 cores. `pytest -n 4` takes 193.0 s, 1.99× faster, with one test that is not safe for parallel runs (`tests/service/test_routes.py::test_every_row_of_the_endpoint_table_has_a_request_test`). Four directories take 83% of test time: `tests/runs` 32%, `tests/service` 20%, `tests/benchmarks` 17%, `tests/mcp` 14%.
- **No job sets `timeout-minutes`**, so a hung job may run for GitHub's default of 360 minutes. There is no lockfile, and every job resolves the newest dependency versions.
- **Five flaky failures**, one in Python and four in Vitest. One of them turned `main` red (W4).

**Cost**

- About 10 hours with no CI, and one milestone's merge delayed overnight.
- Every push from M6 on waited 5 to 12 minutes per Python job.
- On a paid private plan the build would have cost about 3,289 × $0.006 ≈ $20 at the rate GitHub documents for Linux 2-core runners ([GitHub billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)). Money was not the problem. The hidden quota and the warning that no agent could see were *(judgement)*.

### W4. Stacked PRs and burst merging added manual steps and hid failures

**Evidence**

- **Bases changed by hand.** 17 PRs carry a `base_ref_changed` event by `Gravelaw`, each a few seconds after its parent merged (#35 to #38, #40, #41, #43, #45 to #49, #52 to #56).
  - No head branch was ever deleted, so GitHub had nothing to retarget on.
  - GitHub retargets automatically when a merged PR's head branch is deleted: "GitHub automatically updates any such pull requests, changing their base branch to the merged pull request's base branch" ([GitHub docs](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-and-deleting-branches-within-your-repository)).
  - Branch deletion through the agents' git proxy fails with 403 (`docs/sessions/2026-11-08-M7.md:99`).
  - The repository setting "Automatically delete head branches" would have done both jobs.
- **Every one of the ten summaries carries a merge-order recipe.**
- **Fixes were synced up the stacks by hand.** There are 33 sync merges, 13 of them with git's default message. On 2026-11-09 alone the M10 session made 15 "merge the review fixes … into aks-12x" commits (5 branches × 3 rounds).
- **Burst merges cancelled most CI on `main`.** Stacks were merged seconds apart (#44 to #49 within 26 s), so 41 of 67 push runs on `main` (61%) were cancelled by concurrency. Only the tip of each stack was tested on `main`.
- **#49 was merged with failing CI.**
  - Docs-only commit bc17810 ("M9: Record that CI passed on #48 and #49 once GitHub Actions ran again") was pushed at 07:04:31 UTC. The PR was merged at 07:05:08.
  - Codex's pass on that head finished at 07:06:13, after the merge.
  - On that head the `interface` job failed at 07:06:28, 80 s after the merge, and the run concluded at about 07:12: Vitest `CanvasScreen.test.tsx`, "edits a branch's routes and weights…", timed out at 5,000 ms.
  - The push run on `main` (run 42577047650, commit 8e2dbfe) failed in the same job: `npm run check` failed at 07:11:32, and the run completed at 07:19:56. Both Python jobs and the benchmarks passed. The next `main` run (05e1551, PR #51) passed.
  - `grep` finds neither bc17810 nor 8e2dbfe anywhere in `docs/`.
  - The test was later given an explicit timeout in 7919636 (M10).
- **The claim that "docs-only commits landed after review on #56" does not hold.** Its docs commit 4613047e came after the first review, but three code-carrying merges followed, and Codex's last clean pass on the final head (15:12:49) preceded the merge (16:01:50).
- **Who merged cannot be audited.** All 56 merges are by `Gravelaw`, the same account the agents use for PRs, commits and Linear comments. The brief reports that the M10 session merged its own PRs against instructions. The record is consistent with that, but cannot prove or disprove it.
- **Linear automation reported false states.** It moved AKS-130 and AKS-133 to In Progress at 13:51 UTC on 11-07, because the title of PR #33 named them. They stayed there for 21.6 h and 14.5 h, and the M6 summary repeated "AKS-133, in progress" (`docs/sessions/2026-11-07-M6.md:185`). PR #51 did the same to AKS-74 to AKS-81 and AKS-84.

**Cost**

- Repeated manual steps for the owner, and context spent by each session on merge choreography.
- One milestone (M10) built on a `main` whose last run was red. It was harmless only because the failure was a flaky test.
- An audit gap on the most important control: who merges *(judgement)*.

### W5. The written record outgrew its readers, and several numbers in it are wrong

**Evidence**

- **`docs/DECISIONS.md`** is 2,204 lines and 610 KB (about 150,000 tokens at four characters per token). That is more than an agent can read alongside its work.
  - It changed in 127 commits, 36% of all non-merge commits.
  - "Owner to confirm" appears 109 times in it, and "simplest reading" 31 times.
- **Specs 1 to 4 are 102, 96, 120 and 75 KB.** Spec 1 went from 0.3 to 1.3 in four days with 56 change bullets (10 version bumps), and spec 3 changed in 53 commits.
- **`CLAUDE.md`** is 172 lines but 24 KB.
  - The "Known gaps" table is 6.5 KB and the "Current state" table 7.8 KB of dense per-milestone prose.
  - The guide text is duplicated in `docs/specs/build-guide.md`, and `tests/test_docs.py` requires the two to match.
- **Figures in the record that are wrong:**
  - The M9 close says CI passed on #48 and #49, but the head of #49 and `main` after it failed (W4).
  - "M9 had 27 Codex findings" (`docs/sessions/2026-11-08-M9.md:42`): the threads show 30 (#44 3, #45 18, #46 3, #47 2, #48 4).
  - "AKS-133, in progress" (M6 summary): false, the status came from automation.
  - Real CI failures on #39 (6af0b23) and #45 (087e015) are not in `DECISIONS.md`.
  - The brief's own "about 330 readings" is low (W1).

**Cost**

- A milestone session cannot read the decision log it is told to keep consistent with (rule 6 of the guide), and cannot check what an earlier session decided except by searching.
- The owner gets a record that is long, and in places inaccurate *(judgement)*.
- Anthropic's guidance gives the reason this matters: "Longer files consume more context and reduce adherence" ([Claude Code memory docs](https://code.claude.com/docs/en/memory)), and "context rot" lowers recall as context grows ([Anthropic, context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)).

### W6. Pull requests were milestone-sized

**Evidence**

- 38 commits exceed 1,000 changed lines. The largest is 6,213 (bae7740, the M9 interface shell).
- By milestone: commits prefixed M9 changed 49,012 lines (PRs #44 to #49 alone +36,437/−878), and M6 19,830.
- PR #45 (the canvas) drew 18 findings in 10 rounds over 2.4 hours. 17 of them were races in queued writes and drafts, with five redesigns in a row ending in "one write at a time, no kept drafts".
- PR #1 to #33 open-to-merge median was 2.4 h; #34 to #56 was 6.7 h. Both are dominated by waiting for the owner's merge batch, not by review time.

**Cost:** The largest PRs drew the most review rounds, and each round re-reviewed thousands of lines. Google's code-review study found that "the number of useful comments decreases … and the review latency increases … as the size of the change increases", with a median change of 24 lines ([Sadowski et al., ICSE-SEIP 2018](https://doi.org/10.1145/3183519.3183525)).

### W7. Structural debts in the code

**Evidence**

- **Two modules are too large.**
  - `model/validation.py` is 2,105 effective lines and `model/loading.py` 1,458. Both have maintainability index 0, and they hold 3 of the 4 grade-D functions (`_outputs` CC 29, `_distribution_issues` 25, `_Builder.program` 24).
  - The interface mirrors this, with screen components of 800 to 1,250 lines (`ui/src/canvas/CanvasScreen.tsx` 1,247).
- **Hidden coupling.**
  - `mcp/client.py:50-52` imports two constants from `service/main.py`. That pulls in the FastAPI app and loads 72 of the 97 `lcsim` modules.
  - `model/loading.py` imports `engines.registry` lazily, which is a `model` → `engines` cycle.
  - No import-linter contract enforces the layers.
- **Weak typing at the boundaries.**
  - `src` has 302 `Any`, 130 `dict[str, Any]` and 0 `TypedDict`.
  - 24 routes return `dict[str, Any]`, and only 2 of 26 declare a `response_model`.
  - `ui/src/api/types.ts` is a hand-written mirror of the service's responses.
  - There are 6 identical `# type: ignore[arg-type]` in `model/loading.py` (str to `Literal`).
- **Dependency drift.**
  - The 16 runtime dependencies have lower bounds only, and there is no Python lockfile. numpy 2.5.3 is already installed against `>=2.4.6`.
  - Several tests pin seeded simulation output to 3 or 4 decimals, for example `tests/findings/test_rules.py:110` (`== 0.901`) and `tests/service/test_summary_findings.py:114-174` (0.901, 0.133, 0.749, 0.037). A numpy or simpy release that changes a sampling routine would fail them with no product change.
  - pydantic is imported directly but not declared.
- **Timing-dependent tests.** Several race tests rely on fixed sleeps of 0.2 to 1.0 s, for example `tests/service/test_runs.py:543,1210` and `tests/runs/test_local_search.py:138`.

**Cost:** Not yet paid. These are the places where Phase 2 changes will be slowest and riskiest *(judgement)*.

### W8. Rules in prose that nothing enforces

**Evidence**

- Each of the guide's hard rules is a sentence in `CLAUDE.md`: "Randomness: never the global random generator", "never a bare exception message", "Files: Engines write only inside their run folder", "Dependencies: each new dependency is recorded in `DECISIONS.md`".
- No lint rule, hook or test enforces any of them. They held through discipline and review, and the W2 helpers show where discipline slipped.
- The repository has no `.claude/` directory: no hooks, skills, project settings or path-scoped rules.
- There is no `pre-commit` configuration.
- `check.sh` gates at `--cov-fail-under=90` while the guide and the record speak of 100%. The 100% is achieved, but it is not gated, so a drop to 91% would pass.

**Cost:** Indirect. Anthropic's documentation describes instructions in `CLAUDE.md` as non-deterministic: "there's no guarantee that it'll follow your instructions", and "If you keep adding emphasis to a `CLAUDE.md` line and Claude still misses it, that's a sign the line belongs in a hook" ([Claude Code best practices](https://code.claude.com/docs/en/best-practices)).

## Patterns in the review findings

### Counts

| | PRs #1 to #33 (M0 to M5, specs, design) | PRs #34 to #56 (M6 to M10) | Total |
|---|---|---|---|
| Codex inline findings | 40 | 60 | **100** |
| Priority P1 / P2 | 2 / 38 | 0 / 60 | 2 / 98 |
| PRs with at least one finding | 15 of 33 | 14 of 23 | 29 of 56 |
| Rounds with findings | 31 | 41 | 72 |
| Findings rejected by the author | 0 | 0 | 0 |
| Threads resolved | 40 | 60 | 100 |
| Open-to-merge, median | 2.44 h | 6.66 h | — |

Two PRs drew a P1, both for resource safety: #24 (a forced stop left descendant processes running) and #32 (the whole search space was built in memory before the budget check).

### By category

| Category | #1 to #33 | #34 to #56 | Total | Where |
|---|---|---|---|---|
| Spec or contract mismatch | 9 | 13 | 22 | #1 (6, all in spec text), #23 (2), #5, #50 (3), #53 (3), #34, #42, #45 to #48, #55 |
| UI state and races | 0 | 22 | 22 | #45 (17), #44 (2), #47, #48, #55 |
| Numeric edge cases | 6 | 9 | 15 | #4, #6, #9, #10, #15, #18, #35, #36, #37, #48, #53 |
| Concurrency and process lifetime | 9 | 2 | 11 | #24 (6), #18 (2), #27, #34, #36 |
| Input validation of untrusted data | 4 | 6 | 10 | #5 (3), #9, #35 (2), #46 (2), #50 (2) |
| Paths and platform | 3 | 4 | 7 | #34 (4), #25 (2), #1 |
| Error handling (exception instead of issue) | 1 | 3 | 4 | #5, #35, #39, #44 |
| Resource and cleanup | 2 | 0 | 2 | #32 (2) |
| Determinism and randomness | 1 | 0 | 1 | #30 |
| Other (recursion depth 2, CI gating 1, performance 1, simulation logic 1, chart axis 1) | 5 | 1 | 6 | #2, #5, #18, #27 (2), #48 |

### By milestone

| Milestone | PRs | Findings | Rounds with findings | Median open-to-merge |
|---|---|---|---|---|
| M0 to M5 (with specs and design) | #1 to #33 | 40 | 31 | 2.44 h |
| M6 service | #34 to #38 | 16 | 13 | 10.42 h |
| M7 MCP | #39 to #41 | 1 | 1 | 2.02 h |
| M8 findings | #42, #43 | 1 | 1 | 1.81 h |
| M9 interface | #44 to #49 | 30 | 17 | 12.34 h |
| M10 templates | #50, #52 to #56 | 12 | 9 | 5.23 h |

### What the pattern shows

1. **The defects are concentrated, not spread.**
   - Two families account for half of all findings: hostile or extreme input not becoming an issue (29), and the interface's queued-write races (22).
   - Add process lifetime (11) and 62 of 100 findings come from three families.
   - All three are classic targets for generated tests:
     - property-based tests for parsers and validators;
     - model-based or stateful tests for UIs and process supervisors;
     - fault injection (signals, OSError) for process lifetime.

   The fact is the concentration; that these tests would have caught them is *(judgement)*.
2. **Codex found what the tests could not.** Coverage was 100% of lines throughout, yet Codex found 100 defects. That is what the research predicts:
   - Inozemtseva and Holmes found "a low to moderate correlation between coverage and effectiveness", and that coverage "should not be used as a quality target" ([ICSE 2014](https://dl.acm.org/doi/10.1145/2568225.2568271)).
   - Google's guidance warns that pushing toward 100% "leads to a false sense of security" ([Google Testing Blog, 2020](https://testing.googleblog.com/2020/08/code-coverage-best-practices.html)).
3. **The same class came back because each fix was local.** The numeric-overflow class appeared on 9 PRs from M1 (#4) to M10 (#53). Each fix added a guard at the named site. No fix added a shared guard, a lint rule or a generated test that would have found the next site.
4. **"Redesign after the third finding" worked, but came late.** On #34 the redesign followed the third path finding. On #45 the fifth redesign finally removed the race class. A rule to stop and redesign after the *second* finding of the same class in a PR would have saved about one round per case *(judgement)*.
5. **Every finding was accepted.** None of the 100 was rejected or disputed. That is consistent with high precision, but also with a reviewer that "will always find something" and an author that fixes everything ([Claude Code best practices](https://code.claude.com/docs/en/best-practices)). Some fixes were low-value hardening, for example the 4,301-digit object key on #5 *(judgement)*. An industrial study of an AI review bot found 73.8% of its comments resolved, while average PR closure rose from 5 h 52 min to 8 h 20 min ([Cihan et al., ICSE-SEIP 2025](https://arxiv.org/abs/2412.18531)).
6. **Review rounds track PR size.** The three PRs with the most rounds, #45 (10), #1 (5) and #34 (5), are among the largest of their milestones (W6).

## Industry comparison

The facts below come from the projects' own configuration files and documentation, read on 2026-11-09. The verdict column is judgement.

### Repository, packaging and tooling

| Practice | Ithax now | Peers and current tooling | Verdict |
|---|---|---|---|
| Build backend | hatchling | pydantic and attrs: hatchling; FastAPI: pdm-backend; pandas, NumPy, SciPy: meson-python (C extensions) | Fine |
| Lockfile | None for Python; `ui/package-lock.json` for the interface | pydantic installs strictly from `uv.lock` in CI (`UV_FROZEN: true`); attrs sets a one-week dependency cooldown (`exclude-newer = "1 week"`). uv: "`uv.lock` … should be checked into version control" ([uv docs](https://docs.astral.sh/uv/concepts/projects/layout/)) | **Gap.** No reproducible environment, with seeded exact-value tests on top |
| Linter rules | ruff `E, F, W, I, B, UP, ANN, RUF` | pandas: broad, including `PL`, `PT`, `TID`, `PERF`; SimPy adds `TRY`, `SIM`, `RET`; attrs: `select = ["ALL"]` with a commented ignore list | Narrow but clean. The gap is in project-specific rules (next row) |
| Enforcing house helpers | Prose in `CLAUDE.md` | pandas uses ruff `banned-api` to force its own helpers, for example `"numpy.random.RandomState".msg = "Use numpy.random.Generator …"` and `"pytest.warns".msg = "Use tm.assert_produces_warning …"` ([pandas `pyproject.toml`](https://raw.githubusercontent.com/pandas-dev/pandas/main/pyproject.toml)) | **Gap.** The direct fix for W2 and W8 |
| Layer contracts | Hold by discipline | import-linter supports layers, forbidden, independence and acyclic contracts ([docs](https://import-linter.readthedocs.io/en/stable/)). OpenAI's agent-built product enforces layers "mechanically via custom linters … and structural tests" ([OpenAI, harness engineering](https://openai.com/index/harness-engineering/)) | **Gap** |
| Type checking | mypy `strict` over `src` and `tests` | FastAPI and httpx: mypy strict; NumPy: mypy plus pyrefly; attrs: mypy, pyright, ty and pyrefly. Pyrefly reached 1.0 on 2026-05-12 ([pyrefly](https://pyrefly.org/blog/v1.0/)); ty is still 0.0.x (0.0.99, 2026-11-06) | **Ahead** on strictness. The gap is boundary types (`TypedDict` and response models), not the checker |
| Pre-commit or hooks | None | attrs: pre-commit (now prek); pre-commit "identifying simple issues before submission" ([pre-commit](https://pre-commit.com/)) | Gap, but agent hooks matter more here (see the agent practice table) |

### Testing

| Practice | Ithax now | Peers and evidence | Verdict |
|---|---|---|---|
| Parallel tests | Serial: 6.4 min locally, 6.2 min median in CI | FastAPI: `pytest -n auto --dist loadgroup`; attrs: `-n auto`; pandas: `--dist=worksteal`, with `single_cpu` tests in a separate serial step. Measured here: `-n 4` gives 1.99× with one test to fix | **Gap**, and a quick win |
| Coverage gate | Lines, gated at 90%, achieved 100%; branches not gated (99.6% measured) | attrs: 100% **branch** coverage gated. FastAPI: 100% line coverage on the combined report. pandas, SciPy, NumPy, Pyomo and pydantic set no percentage gate. Google: 60/75/90% as acceptable, commendable, exemplary; "per-commit coverage goals of 99% are reasonable" | Over-invested in the metric, under-invested in what it misses |
| Property-based tests | 0 | NumPy and SciPy use Hypothesis. CPython caches the Hypothesis database across CI runs. A study of 426 Python projects found "each property-based test finds about 50 times as many mutations as the average unit test", though with a small effect size of 0.05 ([Ravi and Coblenz, OOPSLA 2025](https://dl.acm.org/doi/full/10.1145/3764068)) | **Gap**, and the best-matched fix for 29 of 100 findings |
| Mutation testing | None | Google runs diff-based mutation testing for 6,000 engineers, and mutants "are indeed coupled with real faults" ([ICSE-SEIP 2018](https://research.google/pubs/state-of-mutation-testing-at-google/), [ICSE 2021](https://ieeexplore.ieee.org/document/9402038)). mutmut 3.8.1 is incremental | Opportunity, non-gating |
| Slow-test split | Benchmarks run twice; no `slow` marker | pandas: `slow` and `single_cpu` markers; SimPy: `-m "not benchmark"`; Pyomo: `default` and `expensive`; FastAPI: per-test `timeout = "20"` | **Gap** |
| Affected-test selection for the inner loop | None | pytest-testmon selects tests from coverage data, but cannot collect "if you run under … coverage" ([testmon](https://testmon.org/)), so it suits the inner loop only | Opportunity |

### CI

| Practice | Ithax now | Peers and documentation | Verdict |
|---|---|---|---|
| Concurrency cancel | Yes, keyed on `github.ref` | attrs, pandas, CPython and Pyomo do the same. pandas keys pushes to main on `run_number`, so a main run is never cancelled | Good. Main runs should not be cancelled (W4) |
| Job timeouts | None (default 360 min) | FastAPI 5 to 10 min, pandas 90, CPython 60, Pyomo 120 | Gap, and a quick win |
| Path filters and one required check | None; docs-only pushes run the full suite | FastAPI: a `dorny/paths-filter` job, job-level `if:`, and one `alls-green` required job. A workflow skipped by a path filter leaves its required check "Pending" and blocks merging, while a job skipped by `if:` reports success ([GitHub docs](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks)) | Opportunity |
| Required checks before merge | Not enforced (#49 merged red) | attrs: `alls-green` as the single required check, plus the `merge_group` trigger | **Gap** |
| Cost | Private repository on 2,000 free minutes, exhausted | Free plan: an allowance of about 2,000 Linux minutes, after which "usage is blocked" without a payment method; public repositories are free ([GitHub billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)) | Resolved by making the repository public; the risk returns if it goes private again |

### Agent practice

| Practice | Ithax now | Published guidance | Verdict |
|---|---|---|---|
| Size of `CLAUDE.md` or `AGENTS.md` | 172 lines, 24 KB, about half status tables | Anthropic: "target under 200 lines per CLAUDE.md file. Longer files consume more context and reduce adherence" ([memory docs](https://code.claude.com/docs/en/memory)). OpenAI: "one big AGENTS.md … failed in predictable ways … It rots instantly", so they use about 100 lines as "a map", with the rest in `docs/` ([harness engineering](https://openai.com/index/harness-engineering/)) | **Gap.** Within the line limit, but the content is the kind both vendors say to move out |
| Hard rules | Prose | Anthropic: rules that cannot have exceptions belong in hooks, deny rules or settings, which are "deterministic"; a Stop hook that exits 2 blocks Claude from finishing ([best practices](https://code.claude.com/docs/en/best-practices)). OpenAI: "When documentation falls short, we promote the rule into code", with lint messages written "to inject remediation instructions into agent context" | **Gap** (W8) |
| One feature per session, with a checkable done state | One milestone per session, one sub-agent per ticket, acceptance rows as gates | Anthropic's harness for long-running agents uses one feature per session, a JSON feature list with `"passes": false`, a progress file and commits; it names an agent that would "see that progress had been made, and declare the job done", and a "tendency to mark a feature as complete without proper testing", as failure modes ([Anthropic](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)) | **Ahead** in structure. Behind in one place: the M9 close declared CI green from a commit message, not from a check |
| Multi-agent cost | One Opus sub-agent per ticket, plus an orchestrator and a monitor | "multi-agent systems use about 15× more tokens than chats", and "most coding tasks involve fewer truly parallelizable tasks than research" ([Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)) | Reasonable for independent tickets. The stacks show the tickets were not independent |
| Spec-driven development | Eight specs, rule 6 ("the spec changes before the code"), 166 change bullets | Thoughtworks puts spec-driven development at "Assess", warning that "handcrafting detailed rules for AI ultimately doesn't scale" ([Radar](https://www.thoughtworks.com/radar/techniques/spec-driven-development)). Böckeler: "I'd rather review code than all these markdown files" ([martinfowler.com](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html)) | Mixed. The specs caught real bugs (PR #1); their size and churn are W5 |
| AI review bot | Codex on every push, 100 findings, all accepted | Codex reads a "Review guidelines" section in `AGENTS.md` to steer its reviews ([OpenAI](https://developers.openai.com/codex/integrations/github)). Anthropic: review against the spec and skip style | Opportunity: give Codex the project's bug classes and priorities |
| Batch size | Milestone-sized stacks merged in bursts | DORA: small batches act "as a safety net for AI adoption" ([DORA](https://dora.dev/capabilities/working-in-small-batches/)); in trunk-based development "branches … typically last no more than a few hours" ([DORA](https://dora.dev/capabilities/trunk-based-development/)). Google's median change is 24 lines | **Gap** (W4, W6) |
| Decision records | One 610 KB log | Nygard: "Large documents are never kept up to date. Small, modular documents have at least a chance", with one decision per record ([Nygard 2011](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions)); MADR offers minimal templates ([MADR](https://adr.github.io/madr/)) | **Gap** (W5) |
| Benchmarks for agents | — | SWE-bench Verified has been retired by OpenAI: "at least 59.4% of the audited problems have flawed test cases" ([OpenAI](https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/)). METR now marks its 2025 slowdown result as "out of date" ([METR 2025 study](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/)), and calls its 2026 follow-up "only very weak evidence" ([METR 2026 update](https://metr.org/blog/2026-02-24-uplift-update/)). Agent PRs in 100-star repositories were accepted 69.3% of the time, Claude Code 71.9% ([Pinna et al.](https://dl.acm.org/doi/10.1145/3793302.3793576)) | Context only: public benchmarks say little about a project like this one |

Overall *(judgement)*: Phase 1 is ahead of most peers on type strictness, test volume and the discipline of its written process. It is behind on the mechanisms that make discipline unnecessary: lockfiles, parallel tests, generated tests, lint-enforced helpers, layer contracts, agent hooks, required checks and small batches. Several of the peers it should be compared with (attrs, FastAPI, pandas) already use each of these.

## Opportunities

Each opportunity maps to proposals in [`proposed-agent-setup.md`](proposed-agent-setup.md), where it is ranked by benefit, cost and risk.

| Weakness | Opportunity | Proposals |
|---|---|---|
| W1 owner decisions | Ask the blocking questions before a milestone starts. Separate the few real choices from reversible defaults. Batch the rest into a short weekly digest with a default that applies on a date | P13, P14 |
| W2 recurring bugs | One shared helper per check, enforced by ruff `banned-api` and a small custom check. Hypothesis tests for "never raises, always an issue". Stop and redesign after the second finding of a class. Fault-injection tests for process lifetime. Periodic mutation testing | P5, P6, P7, P12, P18 |
| W3 CI | `pytest -n auto`, no duplicate benchmarks, job timeouts, uv with a lockfile, a budget alert if the repository goes private | P1, P3, P9 |
| W4 merging | Merge each PR to `main` when it is green and reviewed. Let GitHub delete head branches and retarget stacks. Require one `alls-green` check. A separate identity for agents. A merge-readiness check that reads facts, not messages | P4, P10, P11, P19 |
| W5 record | `CLAUDE.md` as a map under 100 lines. Status out of `CLAUDE.md`. One file per decision. Counts and CI states taken from the source, not retyped | P8, P15 |
| W6 PR size | A size budget per PR, and tickets cut to fit it | P10 |
| W7 structure | Split `validation.py` and `loading.py` by rule group. A service protocol module for MCP and the launcher. Layer contracts. `TypedDict` and response models at the boundary | P16, P17 |
| W8 enforcement | Agent hooks: format on edit, lint and types on stop. Lint-enforced helpers. A branch-coverage gate at the achieved level | P2, P5, P9 |
