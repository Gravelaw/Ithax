# Benchmark sources (spec 2, M2 part)

## Question

Spec 2 "Research before building", M2 and M5: find textbook problems with published
answers that may be reused freely. This note covers the M2 part: the queueing results
behind the five M2 benchmark cases (M/M/1, M/M/2, tandem, delay, branch). It also
recomputes the closed-form M4 queueing answers (M/M/1/K loss, batch, failure, pool) while
the formulas are at hand. The M5 part (linear and integer programs, machine count) is
added at M5.

## Finding

Two textbooks are free to read online and give every formula needed. Neither states a
licence (a text search of both found no copyright or licence notice), so copying their text
is not assumed to be allowed. The benchmarks reuse only the formulas, which are
mathematical facts, with the project's own parameters. No problem text is copied.

| Case | Formula | Source |
| --- | --- | --- |
| M/M/1 | E(W) = (ρ/μ)/(1 − ρ); E(Lq) = ρ²/(1 − ρ); E(S) = (1/μ)/(1 − ρ) | Adan and Resing, section 4.3 |
| M/M/2 | Π_W (Erlang C), equation (5.1); E(Lq) = Π_W · ρ/(1 − ρ), (5.2); E(W) = Π_W · 1/(1 − ρ) · 1/(cμ), (5.3) | Adan and Resing, sections 5.1 and 5.2 |
| Tandem | The departures of a stable M/M/1 queue are Poisson with the arrival rate, so the second station is again M/M/1 | Burke's theorem |
| Delay | E(L) = λE(S) (Little's law); a delay block is an M/G/∞ queue, so E(L) = λE(B) | Adan and Resing, sections 3.4 and 11.1 |
| Branch | Splitting with fixed probabilities: rate × weight / total weight | Arithmetic |
| M/M/1/K loss (M4) | P_K = (1 − ρ)ρ^K/(1 − ρ^(K+1)); admitted rate λ(1 − P_K) | Sztrik, section 5.4, table 4 |
| Batch (M4) | Items 1 to n of a batch wait n − 1, …, 0 interarrival times: mean (n − 1)/(2λ) | Arithmetic |
| Failure (M4) | Availability = MTTF/(MTTF + MTTR) | Wikipedia, "Availability" |

The formula code was first checked against a published table: Adan and Resing table 5.1
(M/M/c, mean service time 1, ρ = 0.9) gives Π_W and E(W) of 0.90 and 9.00 for c = 1, 0.85
and 4.26 for c = 2, 0.76 and 1.53 for c = 5, and 0.67 and 0.67 for c = 10. The script gives
the same to two decimals, except E(W) for c = 5, where it gives 1.52499 and the table
1.53. The exact value is 0.762493/(0.1 × 5) = 1.52499, so the table rounded at the half.

Every M2 answer in spec 2's "Benchmark definitions" matches the recomputation, and so do
the closed-form M4 answers. Times are in minutes, rates per hour.

| Case | Spec 2 answer | Recomputed | Match |
| --- | --- | --- | --- |
| M/M/1 wait | 4.500 | 4.5 | yes |
| M/M/1 `queue_length.mean` | 2.250 | 2.25 | yes |
| M/M/1 utilization | 0.750 | 0.75 | yes |
| M/M/1 `cycle_time.mean` | 6.000 | 6.0 | yes |
| M/M/1 throughput | 30.0 | 30.0 | yes |
| M/M/2 wait | 1.929 | 1.9286 | yes |
| M/M/2 queue length | 1.929 | 1.9286 | yes |
| M/M/2 utilization | 0.750 | 0.75 | yes |
| M/M/2 cycle time | 3.429 | 3.4286 | yes |
| M/M/2 throughput | 60.0 | 60.0 | yes |
| Tandem waits A and B | 4.500, 1.000 | 4.5, 1.0 | yes |
| Tandem utilizations | 0.750, 0.500 | 0.75, 0.5 | yes |
| Tandem cycle time | 8.000 | 8.0 | yes |
| Delay `cycle_time.mean` | 10.00 | 10.0 | yes |
| Delay `model.wip.mean` | 5.00 | 5.0 | yes |
| Branch `sink_a`, `sink_b` | 9.00, 21.00 | 9.0, 21.0 | yes |
| Queue, loss: P_3, throughput, discarded (M4) | 0.1543, 25.37, 4.63 | 0.1543, 25.37, 4.63 | yes |
| Batch wait (M4) | 2.000 | 2.0 | yes |
| Failure availability (M4) | 0.800 | 0.8 | yes |
| Resource pool (M4) | 4.500 and 1.929 | the M/M/1 and M/M/2 rows above | yes |

Two model details decide whether a formula applies, and the spec 2 cases meet both:

- **Loss case.** The standalone `queue` (capacity 2, `on_full` default `block`) feeds a
  server with `queue_capacity` 0 and capacity 1. At most 3 items can be in the system, and
  the source discards an arrival that finds the queue full ("Source when blocked"). This is
  the M/M/1/3 birth-death chain.
- **Delay case.** The `delay` block has no capacity limit, so it is the M/M/∞ (M/G/∞)
  queue that Little's law covers. Each item spends exactly its sampled delay in the system.

## Sources

- Ivo Adan and Jacques Resing, "Queueing Systems", lecture notes, Eindhoven University of
  Technology, 26 March 2015, https://iadan.win.tue.nl/queueing.pdf (opened 2026-11-06):
  section 3.4 (Little's law, equation 3.1), section 4.3 (M/M/1 means), sections 5.1 and
  5.2 (equations 5.1 to 5.3, table 5.1), section 11.1 (M/G/∞).
- János Sztrik, "Basic Queueing Theory", University of Debrecen, 2016,
  https://irh.inf.unideb.hu/~jsztrik/education/16/SOR_Main_Angol.pdf (opened 2026-11-06):
  section 2.4 and section 5.4, table 4 (M/M/1/K).
- Wikipedia, "M/M/1 queue", https://en.wikipedia.org/wiki/M/M/1_queue, and "M/M/c queue",
  https://en.wikipedia.org/wiki/M/M/c_queue (opened 2026-11-06): the same formulas as a
  cross-check, including Erlang's C formula.
- Wikipedia, "Burke's theorem", https://en.wikipedia.org/wiki/Burke%27s_theorem (opened
  2026-11-06), citing Burke (1956), "The Output of a Queuing System", Operations Research
  4(6).
- Wikipedia, "Little's law", https://en.wikipedia.org/wiki/Little%27s_law (opened
  2026-11-06).
- Wikipedia, "Availability", https://en.wikipedia.org/wiki/Availability (opened
  2026-11-06): A = MTTF/(MTTF + MTTR).

## Decision

The M2 benchmark answers in spec 2 stand unchanged, each sourced to the closed-form result
above (Adan and Resing for M/M/1, M/M/c and Little's law, Burke's theorem for the tandem,
arithmetic for the branch), with no text copied from any source.

## Tested

Closed-form formulas only, no simulation and no numerical solving (CLAUDE.md rule 7). The
script below ran on Python 3.11.18 in a scratch environment outside the repository on
2026-11-06.

```python
"""Recompute spec 2 queueing benchmark answers from closed-form formulas (minutes)."""

from math import factorial


def mm1(lam: float, mu: float) -> dict[str, float]:
    rho = lam / mu
    wq = (rho / mu) / (1 - rho)  # Adan and Resing 4.3
    return {"rho": rho, "Wq": wq, "Lq": lam * wq, "W": wq + 1 / mu, "X_per_h": 60 * lam}


def erlang_c(c: int, lam: float, mu: float) -> float:
    rho = lam / (c * mu)
    a = c * rho
    top = a**c / factorial(c)
    below = sum(a**n / factorial(n) for n in range(c))
    return top / ((1 - rho) * below + top)  # Adan and Resing (5.1)


def mmc(c: int, lam: float, mu: float) -> dict[str, float]:
    rho = lam / (c * mu)
    pw = erlang_c(c, lam, mu)
    wq = pw / (1 - rho) / (c * mu)  # Adan and Resing (5.3)
    lq = pw * rho / (1 - rho)  # Adan and Resing (5.2)
    return {"rho": rho, "PW": pw, "Wq": wq, "Lq": lq, "W": wq + 1 / mu, "X_per_h": 60 * lam}


def mm1k_loss(lam: float, mu: float, k: int) -> float:
    rho = lam / mu
    return (1 - rho) * rho**k / (1 - rho ** (k + 1))  # Sztrik 5.4, P_K


for c in (1, 2, 5, 10):  # Adan and Resing table 5.1: mean service 1, rho 0.9
    r = mmc(c, 0.9 * c, 1.0)
    print(f"table 5.1 c={c}: PW {r['PW']:.2f} E(W) {r['Wq']:.2f}")
print("M/M/1", mm1(1 / 2, 1 / 1.5))
print("M/M/2", mmc(2, 1 / 1, 1 / 1.5))
a, b = mm1(1 / 2, 1 / 1.5), mm1(1 / 2, 1 / 1.0)
print("Tandem waits", a["Wq"], b["Wq"], "cycle time", a["W"] + b["W"])
print("Delay WIP", 0.5 * 10.0, "Branch", 30 * 0.3, 30 * 0.7)
p3 = mm1k_loss(1 / 2, 1 / 1.5, 3)
print(f"M/M/1/3 P3 {p3:.4f} throughput {30 * (1 - p3):.2f} discarded {30 * p3:.2f}")
print("Batch wait", (5 - 1) / (2 * 1.0), "Availability", 100 / (100 + 25))
```

Output, verbatim:

```text
table 5.1 c=1: PW 0.90 E(W) 9.00
table 5.1 c=2: PW 0.85 E(W) 4.26
table 5.1 c=5: PW 0.76 E(W) 1.52
table 5.1 c=10: PW 0.67 E(W) 0.67
M/M/1 {'rho': 0.75, 'Wq': 4.5, 'Lq': 2.25, 'W': 6.0, 'X_per_h': 30.0}
M/M/2 {'rho': 0.75, 'PW': 0.6428571428571429, 'Wq': 1.9285714285714288, 'Lq': 1.9285714285714288, 'W': 3.428571428571429, 'X_per_h': 60.0}
Tandem waits 4.5 1.0 cycle time 8.0
Delay WIP 5.0 Branch 9.0 21.0
M/M/1/3 P3 0.1543 throughput 25.37 discarded 4.63
Batch wait 2.0 Availability 0.8
```

A separate one-line run of the same Erlang C formula for c = 5, ρ = 0.9 printed
Π_W = 0.7624932207329357 and E(W) = 1.5249864414658716.
