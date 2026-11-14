# Fresh random numbers for search confirmation (#79)

Written 2026-11-14 for M13, before the change. Issue #79 (AKS-133): confirmation runs
reuse the search's streams, which biases the best result. Use fresh streams, recorded in
the run audit trail.

## What is decided already

- **The owner's decision.** `docs/DECISIONS.md`, 2026-11-07, "Owner decisions on M5
  'Awaiting owner' items", item 6:
  - Confirmation replications are numbered from `search.replications` onward. They draw
    random numbers the search stage never used, and keep common random numbers across the
    confirmed candidates.
  - Each evaluation records its stage, candidate, seed and replication range, so every
    confirmed mean can be traced back to its random streams.
- **Why the bias.** The M5 note `docs/research/spec-2-simulation-based-optimization.md`
  ("Overlap of the two stages") explains it. Candidates are ranked, and the top three
  chosen, on their search-stage replications. When a confirmation re-runs those same
  replications, its mean keeps part of the luck that got the candidate chosen: the
  optimizer's curse, or selection bias (Law, *Simulation Modeling and Analysis*, 5th ed.,
  ch. 12, on selecting the best of k systems).
- **Why this fixes it.** Replications drawn from streams the search stage never used are
  independent of the ranking. Using the same numbers for every confirmed candidate
  (common random numbers) keeps the comparison between them paired.

## How it is built

Spec 1's stream key is `<seed>:<replication>:<component id>`, so the replication number is
the only thing that has to change.

- **Experiment and engine.**
  - `Experiment.first_replication` holds the offset. It is never in the file, and the
    loader sets it to 0.
  - The process adapter's engine input carries it (input version 2).
  - The runner numbers its pairs from it, and the `replications` and `timeseries` tables
    carry the stream numbers. Progress still counts 1 to n.
- **The search.**
  - The search stage runs replications 0 to `search.replications` − 1.
  - A confirmation runs `replications` of them from `search.replications`.
  - `separated` pairs the best and the runner-up by replication number, which the two
    confirmations share.
- **The audit trail.** Each candidate in the summary's `search.candidates` lists its
  `evaluations`, the search stage first, as `{stage, folder, seed, first_replication,
  replications}`. Each folder's `engine/input.json` holds the same seed and first
  replication.

The machine-count benchmark's theory rows are judged at 3 standard errors on the
confirmed means, so they do not depend on which replications are drawn. The test that
compares the confirmations with an enumeration now enumerates the same replication numbers.
