# Benchmark sources (spec 2, M2 and M5)

## Question

Spec 2 "Research before building", M2 and M5: find textbook problems with published
answers that may be reused freely. This note covers the M2 part: the queueing results
behind the five M2 benchmark cases (M/M/1, M/M/2, tandem, delay, branch). It also
recomputes the closed-form M4 queueing answers (M/M/1/K loss, batch, failure, pool) while
the formulas are at hand.

The M5 part (AKS-132) covers the five M5 rows of spec 2 "Benchmark definitions": the four
small linear and integer programs (product mix, knapsack, assignment, diet), whose answers
spec 2 says are "verified by enumeration", and the machine-count search, whose theory values
come from Erlang C. Each answer is re-derived here by enumeration or closed form, with no
LP solver (guide rule 7 forbids writing one in the product; the enumeration is a script run
by hand).

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

### M5: the four optimization cases and the machine count

**Method.** A linear program with two variables and a bounded, non-empty feasible region
has an optimum at a vertex (fundamental theorem of linear programming: an optimal solution
of a bounded polyhedron "is either an extreme point (vertex) of P or lies on a face F ⊂ P
of optimal solutions"). Each vertex is the intersection of two constraint lines; the script
intersects every pair (Cramer's rule on a 2 × 2 system, exact fractions), keeps the points
that satisfy every constraint and evaluates the objective. In two dimensions an optimal face
other than a vertex is an edge with two optimal vertices, so a single best vertex is the
unique optimum. The binary cases have finitely many points, all listed. The knapsack and the
assignment problem are the standard formulations (Wikipedia, "Knapsack problem": maximize
Σ vᵢxᵢ subject to Σ wᵢxᵢ ≤ W, xᵢ ∈ {0, 1}; "Assignment problem": the balanced case, each
agent to exactly one task and each task to exactly one agent, whose LP relaxation "always
has an optimal solution where the variables take integer values" because the constraint
matrix is totally unimodular); the diet problem is Stigler's kind (Wikipedia, "Stigler
diet": the cheapest foods meeting nutrient allowances), reduced to two foods and two
nutrients. Every number below is the project's own, written for spec 2; no problem text or
data is copied from a source.

| Case | Enumeration | Spec 2 answer | Match |
| --- | --- | --- | --- |
| Product mix | Vertices (0, 0) → 0; (0, 20) → 1,600; (45, 0) → 2,025; (24, 14) → 2,200. The best is the single vertex (24, 14), so it is the unique optimum. At (24, 14) both constraints bind (5·24 + 20·14 = 400; 10·24 + 15·14 = 450); the dual values solve y_w(5, 20) + y_l(10, 15) = (45, 80): y_w = 1, y_l = 4, both positive, and 400·1 + 450·4 = 2,200 equals the primal objective | 24 chairs, 14 tables, profit 2,200; dual values 1 and 4 | yes |
| Knapsack | 10 of the 16 subsets fit in 10; their values are 21, 20, 18, 17, 15, 13, 10, 8, 7, 0; 21 only for {b, c} (weight 10) | 21 with b = c = 1 | yes |
| Assignment | The 6 permutations cost 9, 10, 14, 16, 20, 21; 9 only for row 0 → column 1, row 1 → column 0, row 2 → column 2 (2 + 6 + 1) | 9 | yes |
| Diet | The region is unbounded, so the cut 0.6x + y ≤ 2.4 (the cost of the feasible point (4, 0)) is added: every point at least as cheap lies in the bounded region left, whose vertices are (16/9, 10/9) → 98/45 = 2.1778, (19/11, 15/11) → 2.4 and (4, 0) → 2.4. The optimum is the single vertex (16/9, 10/9) | 2.178 at x = 1.778, y = 1.111 | yes |

Two details of spec 2's wording hold. The product mix answer is unique, as spec 2 says, and
its dual values are 1 and 4 (HiGHS reports the same, `docs/research/spec-2-solver-layer.md`).
The diet optimum 98/45 = 2.17777… is 2.178 to four significant figures, and the variables
16/9 = 1.7778 and 10/9 = 1.1111 round to spec 2's 1.778 and 1.111. Both diet constraints
bind there (2·16/9 + 4·10/9 = 8; 5·16/9 + 10/9 = 10). The optimization benchmarks are
judged on the objective to four significant figures (spec 2 "Benchmarks"): 2,200, 21, 9 and
2.178.

**Machine count.** The coffee shop (`examples/coffee_shop.json`) has exponential
interarrival times of mean 2 min (λ = 1/2 per minute), one server `till` with exponential
service of mean 1.5 min (μ = 2/3 per minute) and capacity `$param` `tills`, integer 1 to 5,
value 1. With c tills it is the M/M/c queue of the M2 part, so the wait in queue is
E(W) = Π_W/(1 − ρ) · 1/(cμ) with Erlang's C formula Π_W (Adan and Resing, equations 5.1 and
5.3), and the utilization of each till is ρ = λ/(cμ).

| `tills` | Π_W (probability of waiting) | `till.wait.mean` (min) | `till.utilization` | `utilization >= 0.35` |
| --- | --- | --- | --- | --- |
| 1 | 0.750000 | 4.500000 (9/2) | 0.750 (3/4) | yes |
| 2 | 0.204545 | 0.245455 (27/110) | 0.375 (3/8) | yes |
| 3 | 0.044118 | 0.029412 (1/34) | 0.250 (1/4) | no |
| 4 | 0.007662 | 0.003536 (81/22,906) | 0.1875 (3/16) | no |
| 5 | 0.001099 | 0.000388 (243/626,518) | 0.150 (3/20) | no |

The feasible candidates are 1 and 2 tills, and 2 has the lower wait, so the best is `tills`
= 2, as spec 2 says; the theory values match it: 1 till 4.500 min, 2 tills 0.245 min at
utilization 0.375, and 3 or more break the constraint. The 1-till row is the M/M/1
benchmark (4.500 min, utilization 0.750). The margins are wide for a simulated search: 2
tills meets the constraint by 0.025 (3/8 against 0.35), and the nearest infeasible
candidate, 3 tills, misses it by 0.100.

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

M5 part (opened 2026-11-07; Wikipedia text is CC BY-SA, and only the problem formulations,
which are mathematical facts, are used):

- Wikipedia, "Fundamental theorem of linear programming",
  https://en.wikipedia.org/wiki/Fundamental_theorem_of_linear_programming: the vertex
  statement for a bounded polyhedron.
- Wikipedia, "Linear programming", https://en.wikipedia.org/wiki/Linear_programming:
  complementary slackness ("if the i-th slack variable of the primal is not zero, then the
  i-th variable of the dual is equal to zero").
- Wikipedia, "Knapsack problem", https://en.wikipedia.org/wiki/Knapsack_problem: the 0-1
  formulation.
- Wikipedia, "Assignment problem", https://en.wikipedia.org/wiki/Assignment_problem: the
  balanced formulation and the integral LP optimum.
- Wikipedia, "Stigler diet", https://en.wikipedia.org/wiki/Stigler_diet: the diet problem.
- Adan and Resing (above), equations 5.1 and 5.3, for the machine count.

## Decision

The M2 benchmark answers in spec 2 stand unchanged, each sourced to the closed-form result
above (Adan and Resing for M/M/1, M/M/c and Little's law, Burke's theorem for the tandem,
arithmetic for the branch), with no text copied from any source.

M5 part: the five M5 answers in spec 2 "Benchmark definitions" stand unchanged. Product mix
2,200 at (24, 14), unique, dual values 1 and 4; knapsack 21 with b = c = 1; assignment 9;
diet 2.178 at (1.778, 1.111); machine count best `tills` = 2 with the theory values 4.500
and 0.245 min and utilization 0.375, 3 or more tills infeasible. AKS-108 writes each
optimization case's `expected.json` with the exact value (2200, 21, 9 and 98/45) and method
`sig_figs_4`, and cites this note as its `source`; AKS-109 cites the Erlang C table for the
machine count. No spec change.

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

M5 part: the script below ran on Python 3.11.18 in a scratch environment outside the
repository on 2026-11-07, with exact fractions and no solver.

```python
"""Re-derive the spec 2 M5 benchmark answers by enumeration, with exact fractions (no LP solver)."""

from fractions import Fraction as F
from itertools import combinations, permutations, product
from math import factorial


def vertices(rows):
    """Rows (a, b, rhs, op) meaning a*x + b*y op rhs. Intersect each pair as equalities
    (Cramer's rule, 2 x 2) and keep the points that satisfy every row."""

    def ok(x, y):
        return all(
            (a * x + b * y <= r) if op == "<=" else (a * x + b * y >= r) for a, b, r, op in rows
        )

    found = set()
    for (a1, b1, r1, _), (a2, b2, r2, _) in combinations(rows, 2):
        det = a1 * b2 - a2 * b1
        if det == 0:
            continue
        x, y = (r1 * b2 - r2 * b1) / det, (a1 * r2 - a2 * r1) / det
        if ok(x, y):
            found.add((x, y))
    return sorted(found)


# Product mix: maximize 45c + 80t; wood 5c + 20t <= 400; labour 10c + 15t <= 450; c, t >= 0.
mix = [
    (F(5), F(20), F(400), "<="),
    (F(10), F(15), F(450), "<="),
    (F(1), F(0), F(0), ">="),
    (F(0), F(1), F(0), ">="),
]
print("Product mix vertices (chairs, tables, profit):")
for c, t in vertices(mix):
    print(f"  ({c}, {t}) -> {45 * c + 80 * t}")
# Duals at (24, 14): solve y_w * (5, 20) + y_l * (10, 15) = (45, 80) by Cramer's rule.
det = F(5 * 15 - 10 * 20)
yw, yl = (F(45) * 15 - F(80) * 10) / det, (F(5) * 80 - F(20) * 45) / det
print(f"  dual values at (24, 14): wood {yw}, labour {yl}; dual objective {400 * yw + 450 * yl}")

# Knapsack: maximize 10a + 13b + 8c + 7d subject to 5a + 6b + 4c + 3d <= 10, binary.
v, w = (10, 13, 8, 7), (5, 6, 4, 3)
subsets = [
    (sum(vi * x for vi, x in zip(v, xs)), xs)
    for xs in product((0, 1), repeat=4)
    if sum(wi * x for wi, x in zip(w, xs)) <= 10
]
best = max(s for s, _ in subsets)
print(
    f"Knapsack: {len(subsets)} of 16 subsets feasible; best {best} at "
    f"{[xs for s, xs in subsets if s == best]} (a, b, c, d)"
)
print("  feasible values:", sorted((s for s, _ in subsets), reverse=True))

# Assignment: 3 x 3 costs, each row and column once.
C = [[9, 2, 7], [6, 4, 3], [5, 8, 1]]
costs = sorted((sum(C[i][p[i]] for i in range(3)), p) for p in permutations(range(3)))
print("Assignment (cost, column of rows 0, 1, 2):", costs)

# Diet: minimize 0.6x + y; 2x + 4y >= 8; 5x + y >= 10; x, y >= 0. The region is unbounded,
# so add the cut 0.6x + y <= 2.4, the cost of the feasible point (4, 0): every point at least
# as good lies in the bounded region, where the optimum is at a vertex.
diet = [
    (F(2), F(4), F(8), ">="),
    (F(5), F(1), F(10), ">="),
    (F(1), F(0), F(0), ">="),
    (F(0), F(1), F(0), ">="),
    (F(3, 5), F(1), F(12, 5), "<="),
]
print("Diet vertices (x, y, cost), with the cut:")
for x, y in vertices(diet):
    print(f"  ({x}, {y}) -> {F(3, 5) * x + y} = {float(F(3, 5) * x + y):.4f}")


# Machine count: the coffee shop, arrivals exponential mean 2 min, service exponential mean
# 1.5 min, c tills (M/M/c). Erlang C, Adan and Resing (5.1) and (5.3), as in the M2 part.
def erlang_c(c, lam, mu):
    rho = lam / (c * mu)
    a = lam / mu
    top = a**c / factorial(c)
    below = sum(a**n / factorial(n) for n in range(c))
    return top / ((1 - rho) * below + top)


lam, mu = F(1, 2), F(2, 3)
print("Machine count (c, P(wait), Wq min, utilization, meets utilization >= 0.35):")
for c in range(1, 6):
    rho = lam / (c * mu)
    pw = erlang_c(c, lam, mu)
    wq = pw / (1 - rho) / (c * mu)
    print(
        f"  {c}: {float(pw):.6f}  {float(wq):.6f} ({wq})  {float(rho):.6f} ({rho})  {rho >= F(35, 100)}"
    )
```

Output, verbatim:

```text
Product mix vertices (chairs, tables, profit):
  (0, 0) -> 0
  (0, 20) -> 1600
  (24, 14) -> 2200
  (45, 0) -> 2025
  dual values at (24, 14): wood 1, labour 4; dual objective 2200
Knapsack: 10 of 16 subsets feasible; best 21 at [(0, 1, 1, 0)] (a, b, c, d)
  feasible values: [21, 20, 18, 17, 15, 13, 10, 8, 7, 0]
Assignment (cost, column of rows 0, 1, 2): [(9, (1, 0, 2)), (10, (1, 2, 0)), (14, (0, 1, 2)), (16, (2, 1, 0)), (20, (0, 2, 1)), (21, (2, 0, 1))]
Diet vertices (x, y, cost), with the cut:
  (19/11, 15/11) -> 12/5 = 2.4000
  (16/9, 10/9) -> 98/45 = 2.1778
  (4, 0) -> 12/5 = 2.4000
Machine count (c, P(wait), Wq min, utilization, meets utilization >= 0.35):
  1: 0.750000  4.500000 (9/2)  0.750000 (3/4)  True
  2: 0.204545  0.245455 (27/110)  0.375000 (3/8)  True
  3: 0.044118  0.029412 (1/34)  0.250000 (1/4)  False
  4: 0.007662  0.003536 (81/22906)  0.187500 (3/16)  False
  5: 0.001099  0.000388 (243/626518)  0.150000 (3/20)  False
```

The same four problems solved by HiGHS 1.15.1 through Pyomo in the solver-layer note gave
2200.0, 21.0, 9.0 and 2.177777777777778, the same answers.
