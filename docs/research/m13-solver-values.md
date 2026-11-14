# Clean solver values (#76)

Written 2026-11-14 for M13, before the change. Issue #76 (E1, M5-12): results show
24.000000000000004, 0.9999999999999997 and -0.0, and a finding reports 0.00000000000005684.
It is done when results, findings and MCP show clean values, with tests.

## What HiGHS gives

`solve` was run on every shipped optimization program (HiGHS 1.15.1 through Pyomo; the
script is not kept). These are the numbers that are not clean:

| Program | Values | Slacks | Duals |
| --- | --- | --- | --- |
| `benchmarks/product_mix`, `templates/product_mix` | chairs 24.000000000000004, tables 13.999999999999998 | wood 5.684341886080802e-14 | wood 0.9999999999999996 |
| `benchmarks/assignment` | x_1_1 −0.0, x_2_0 −0.0 (binary) | | |
| `templates/staff_rota` | staff[mon_fri] −0.0, staff[tue_sat] −0.0 (integer) | | |
| `benchmarks/transport`, `templates/transport_plan` | | | supply[north] −0.0 |

`knapsack` and `diet` are clean. The finding's 0.00000000000005684 is how `figures`
prints a value of 5.684e-14 to four significant figures. That value is the product mix's
wood slack. A variable at that size would be counted as not 0 and listed in "Best found".

## Why there is noise

- **Integers and binaries.** HiGHS solves an integer program by branch and bound over LP
  relaxations. A value counts as integral when it is within the MIP feasibility tolerance
  (`mip_feasibility_tolerance`, 1e-6 by default) of a whole number. The value given back is
  the LP's float, which can be −0.0 or a few units in the last place away from the whole
  number.
- **Continuous values.** These come from floating-point arithmetic: the simplex basis
  solve and the slack computed as rhs minus the left-hand side. The error is a few units in
  the last place, about 1e-16 of the value per operation, so 24 becomes 24.000000000000004.
- **Feasibility tolerance.** HiGHS's primal feasibility tolerance
  (`primal_feasibility_tolerance`) is 1e-7. A difference below it means nothing to the
  solver.

## Rule

- **Integer and binary variables** are reported rounded to the nearest whole number.
  HiGHS's integrality tolerance makes that the value it means.
- **Every other number** is reported as the nearest whole number when it lies within
  `NOISE` × max(1, |value|) of it, with `NOISE` = 1e-9. This covers a continuous value, the
  objective, a slack and a dual. 1e-9 is about 10⁷ times the floating-point noise and 100
  times below the feasibility tolerance. So noise is removed, and a value the solver means,
  such as 16/9 or 1e-7, is kept.
- **No number is −0.0.** Python's `float(round(-0.0))` is 0.0.
- **Consistency.** The rounded values are set back into the Pyomo model before the slacks
  and the objective are read. Each slack and the objective therefore agree with the values
  reported, and are cleaned the same way.

The rule is applied once, in `ithax.engines.optimize.solver.solve`. Everything downstream
reads the adapter's `solution.json`, so `summary.json`, the findings and the MCP tools
inherit clean values: the product mix reports 24, 14, 2,200, slacks 0 and duals 1 and 4.
The interface's display rounding is unchanged.

## Sources

- HiGHS options reference, `mip_feasibility_tolerance` (default 1e-6) and
  `primal_feasibility_tolerance` (default 1e-7), as quoted in
  `src/ithax/engines/optimize/solver.py` ("tight").
- IEEE 754 double precision: machine epsilon 2.2e-16.
