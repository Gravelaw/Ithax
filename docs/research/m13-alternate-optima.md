# Alternate optima (#176, #132)

Written 2026-11-14 for M13, before the change. Owner decision on #176 (option B): the
optimization adapter detects alternate optima, and the finding says that several plans reach
the same objective. The staff rota template is the case. Its integer programme has 7 optimal
rotas of 9 people (all listed by exhaustive enumeration while filing #176). highspy 1.15.1
returns one of them and highspy 1.16 returns another, so the "Best found" text depends on the
solver version.

## What "alternate optima" means here

Take an optimal plan x\* with objective z\*. The optimal set is every feasible plan whose
objective equals z\*. For a linear programme this set is a face of the feasible polyhedron.
For an integer programme it is the integer points of the feasible region that reach z\*.
There are alternate optima when the set holds a second plan.

## Ways to detect them, within rule 7 (wrap engines, write no solver)

1. **Duals and reduced costs (linear programmes only).** A nonbasic variable with a zero
   reduced cost signals another optimal vertex, unless the solution is degenerate
   (Bertsimas and Tsitsiklis, *Introduction to Linear Optimization*, section 3.3; Hillier and
   Lieberman, chapter 4).
   - Under degeneracy, which is common in transport and assignment problems, the signal is
     not reliable.
   - It says nothing for integer programmes.
   - Pyomo's preview interface gives duals but no basis status.
   - Not taken.
2. **No-good cut.** Re-solve with the objective fixed at z\* and a cut that excludes x\*.
   - For binary variables the cut is linear: Σ over x\*=1 of (1 − x) + Σ over x\*=0 of x ≥ 1.
   - For general integers and continuous variables, excluding one point needs a
     disjunction: extra binaries and big-M bounds, which our models need not have.
   - Not taken.
3. **One variable at a time.** Over the optimal set, minimize and then maximize each variable.
   - This is exact, and the method of optimal-face ("solution range") analysis.
   - It costs 2n solves for n variables, with no bound worth stating for large models (#82).
   - Not taken.
4. **A probe direction (taken).** Over the optimal set, minimize and then maximize one linear
   function d·x whose weights are generic.
   - If the optimal set holds a second point y, d·x cannot take the same value at x\* and
     at y, unless d is orthogonal to y − x\*. So the minimizer or the maximizer differs from
     x\*.
   - It costs one or two more HiGHS solves of the same size, and stops after the first if
     that one already differs.

## The probe

- **The optimal set.** The model's own constraints plus "objective no worse than z\*":
  c·x ≤ z\* for minimize, c·x ≥ z\* for maximize.
  - A band of 1e-6 × |z\*| around z\* was tried first. It admits plans slightly worse than z\*,
    and on a linear programme the probe then moves the values by about the band's width:
    product mix chairs −8.8e-5, transport ship[north,market] 1.3e-3, diet x 2.2e-5. Those are
    false alarms.
  - With the bound at z\* itself, the only slack is HiGHS's feasibility tolerance, about 1e-7.
- **The weights.** d_i = √s_i, where s_i is the i-th square-free integer (2, 3, 5, 6, 7, 10, …),
  taken in the model's variable order.
  - Square roots of distinct square-free integers are linearly independent over the
    rationals (Besicovitch, 1940).
  - A difference y − x\* between two plans of a model with rational data is a rational
    vector (every float is rational). So d·(y − x\*) is never exactly 0, and no plan can tie
    with x\* by the model's structure, as equal weights would allow.
  - It is deterministic, so it needs no random stream, and the same model gives the same
    answer on every run.
- **What counts as different.**
  - An integer or binary variable differs when its value, rounded, differs (values are
    rounded as reported, #76).
  - A continuous variable differs when the gap is more than `TIGHT_TOLERANCE` (1e-6) × max(1,
    |value|): far above the 1e-7 slack, far below the gaps real alternatives show.
- **When the probe beats z\*.** The probe's plan must also reach z\* within that tolerance.
  HiGHS stops an integer programme within a relative gap of 1e-4 (`mip_rel_gap`), so a probe
  could find a strictly better plan. That is not an alternate optimum, so nothing is claimed.
- **Other probe outcomes.**
  - Unbounded: the optimal set is unbounded, so there are infinitely many optimal plans.
    Reported.
  - Any other outcome other than optimal (stopped, infeasible through tolerance): nothing is
    claimed. The answer is the solve's, as before.

## Measured on every shipped optimization model (HiGHS 1.15.1)

| Model | Variables | Objective | First probe | Second probe | Reported |
| --- | --- | --- | --- | --- | --- |
| `templates/staff_rota` | 7 integer | 9 | differs: staff[mon_fri] +1, staff[sun_thu] −1 | not needed | several plans |
| `templates/product_mix`, `benchmarks/product_mix` | 2 | 2,200 | same | same | one plan |
| `templates/transport_plan`, `benchmarks/transport` | 12 | 2,690 | same | same | one plan |
| `benchmarks/assignment` | 9 binary | 9 | same | same | one plan |
| `benchmarks/knapsack` | 4 binary | 21 | same | same | one plan |
| `benchmarks/diet` | 2 | 2.1778 | same | same | one plan |

The staff rota's seven optima were counted independently by enumeration (#176).

## Limits

- The probe is a test, not a proof. Two plans whose difference is nearly orthogonal to d
  (|d·(y − x\*)| below HiGHS's tolerances) could be missed. With the weights above that needs
  a large near-relation among square roots, which the small models of Phase 1 do not have.
- It costs at most two more solves per optimization run. For a large integer programme this
  can double or triple the solve time. The run time limit covers the whole run, as before.

## Where it is reported

- **No new field.** An optimization `summary.json` already ends with `warnings`, the issue
  objects of spec 1 (spec 1 "Run folder and results"). The adapter's `Results.warnings`
  carries them, and W210 is a warning of the run stage.
- **W211, stage `run`.** It reads: "Other plans reach the same objective; the plan shown is
  one of them." So no `/v1` field and no model-format change are needed.
- **The finding.** `optimization_result` adds: "Other plans reach the same objective; this is
  one of them."
- **The upgrade.** HiGHS is upgraded in its own PR (#132). The template test then no longer
  depends on which optimal rota a version returns: it checks the rota shown is a valid one
  of 9 and the finding's sentence.
