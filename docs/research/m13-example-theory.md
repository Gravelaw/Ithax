# The line and the warehouse against their theory at 300 replications (#75)

Written 2026-11-14 for M13, before the gate. Issue #75 (E1, M2-7): at M2 the
three-machine line's paint wait was 3.32 standard errors below theory at seed 12345, with
30 replications. The issue says to run 300 replications, gate the examples on theory if
every value lies within 2 standard errors, and otherwise find the bug.

## Theory

The values are each file's `meta.description`, in SI units.

- **Poisson arrivals at every station.**
  - The source's interarrival times are exponential.
  - By Burke's theorem, a stable M/M/c station passes on a Poisson stream.
  - A constant delay shifts every item by the same time, so the stream stays Poisson. This
    covers the line's 2 min transfer and the warehouse's 5 min inspection.
  - The warehouse's probability branch splits a Poisson stream into two independent Poisson
    streams. Delaying one by a constant keeps the two independent, so pack sees Poisson
    arrivals at 60 per hour.
- **Utilization** is λE(S)/c:
  - Line: cut 0.6, weld 0.9, paint 0.5.
  - Warehouse: pick 2/3, pack 0.8.
- **Mean wait at a single server** is ρ/(1 − ρ) × E(S):
  - cut 108 s
  - weld 972 s
  - paint 60 s
  - pack 192 s
- **Mean wait at pick** (Erlang C, c = 3, a = 2): the probability of waiting is 4/9, and
  the wait is 4/9 × E(S)/(c − a) = 8/9 min = 53.33 s.
- **Cycle time:**
  - Line: 3.0 + 18.0 + 2 + 2.0 = 25.0 min.
  - Warehouse: 2.889 + 0.2 × 5 + 4.0 = 7.889 min.
- **Throughput** equals the arrival rate, because no block loses items: 30 and 60 per hour.

## Measured

Each file's own experiment, with only `replications` changed from 30 to 300: seed 12345,
4 workers. The line runs 100 h with 20 h of warm-up and takes 10.5 s. The warehouse runs
200 h with 10 h and takes 27.6 s. Each value is the deviation (mean − theory) / (sd/√300).

| Metric | Line | Warehouse |
| --- | --- | --- |
| Utilizations | cut +1.21, weld +0.19, paint −0.21 | pick −1.11, pack −0.18 |
| Mean waits | cut +1.70, weld +0.66, paint −1.19 | pick −0.11, pack +0.78 |
| Cycle time | +0.70 | +0.66 |
| Throughput | +0.49 | −1.19 |

All 14 lie within 2 standard errors, and the largest is the line's cut wait at +1.70.
The paint wait moves from −3.32 at 30 replications to −1.19 at 300: 59.57 s against 60 s.
This confirms the M2 reading that the earlier value was a reroll, not a bias (the M2
entry also has seeds 1, 2 and 7). There is no bug to find.

## The gate

`tests/engines/process/test_example_models.py`:

- The gate is `test_each_example_agrees_with_its_theory_at_300_replications`, which runs the
  14 checks at seed 12345 and 300 replications.
- It is marked `benchmark`, so `pytest -m benchmark` runs it, and so does
  `bash scripts/check.sh`, which does not exclude the marker.
- It uses spec 2's benchmark pass rule: |mean − theory| ≤ 3 standard errors.
- `test_the_theory_is_the_one_each_file_states` checks that the gate's values are the ones
  written in each `meta.description`.

**Why 3 standard errors, not 2.** The issue uses 2 standard errors as the test for whether
the engine is right, which it passes. A gate exists to catch a future change that breaks the
engine. A correct change that only rerolls the random streams (a numpy or simpy upgrade, a
new draw order) would fail at least one of 14 checks at 2 standard errors in about half of
runs (1 − 0.954^14 ≈ 0.48). At 3 standard errors that falls to about 3.7% (1 − 0.9973^14).
3 standard errors is also the rule every benchmark in spec 2 already uses.
