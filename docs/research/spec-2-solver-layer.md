# Solver layer (spec 2, M5)

## Question

Spec 2 "Research before building", M5: "Solver layer. Current versions and licences of
HiGHS, Pyomo, OR-Tools and Optuna." Spec 2 "Optimization" names "HiGHS through Pyomo" for
mathematical optimization and Optuna for simulation-based optimization. Before the HiGHS
adapter (AKS-108) and the search (AKS-109) are built, this note settles:

- the current version and licence of each package, read from PyPI and from the licence
  files inside the distributions, with every runtime dependency that `highspy`, `pyomo` and
  `optuna` pull in, checked against AGPL-3.0 under the spec 1 engine licence rule (owner
  decision AKS-83 still open);
- which Pyomo interface drives HiGHS, and whether it runs in-process through `highspy`;
- how that interface reports optimal, infeasible and unbounded models, and how duals and
  slacks are read;
- the lowest versions that install and work on Python 3.11 and 3.13, and the lower bounds
  to declare.

## Finding

### Versions and licences, read on 2026-11-07

Method: `https://pypi.org/pypi/<name>/json` fetched with `curl` for each package; the
wheel downloaded with `pip download --no-deps --only-binary=:all:` (Python 3.13.18, Linux
x86-64) into a fresh empty directory of a scratch folder outside the repository, never
run, and its licence files read with `unzip -p`.

| Package | Version (uploaded) | PyPI licence field | Licence file in the wheel | Licence |
| --- | --- | --- | --- | --- |
| highspy (HiGHS) | 1.15.1 (2026-07-02) | `License-Expression: MIT` | `highspy-1.15.1.dist-info/licenses/LICENSE.txt`: "MIT License, Copyright (c) 2026 HiGHS"; `THIRD_PARTY_NOTICES.md` | MIT, with bundled third-party code (below) |
| pyomo | 6.10.1 (2026-06-04) | `License-Expression: BSD-3-Clause` | `pyomo-6.10.1.dist-info/licenses/LICENSE.md`: 3-clause BSD, "Copyright (c) 2008-2026 National Technology and Engineering Solutions of Sandia, LLC", then "Additional Notices" for derived code (below) | BSD-3-Clause |
| optuna | 5.0.0 (2026-09-07) | classifier "License :: OSI Approved :: MIT License" | `optuna-5.0.0.dist-info/licenses/LICENSE`: "MIT License, Copyright (c) 2018 Preferred Networks, Inc."; `LICENSE_THIRD_PARTY` | MIT, with code from SciPy (BSD 3-clause) and fdlibm (permissive notice) |
| ortools | 9.15.6755 (2026-01-14) | `License: Apache 2.0`, classifier Apache Software License | `ortools-9.15.6755.dist-info/licenses/LICENSE`: Apache License, Version 2.0 | Apache-2.0 |

The versions agree with those the chair read on 2026-11-05 (DECISIONS "Facts checked by
the chair": highspy 1.15.1 MIT, pyomo 6.10.1 BSD-3-Clause, optuna 5.0.0 MIT); no newer
release has appeared since.

Bundled code, from the licence files:

- **highspy.** `THIRD_PARTY_NOTICES.md` lists AMD (BSD-3), CLI11 (BSD-3 text; used only by
  the command-line executable), METIS and GKlib (Apache 2.0), pdqsort (zlib), RCM (MIT)
  and zstr (MIT). AMD, METIS and RCM belong to the HiPO interior-point solver, which the
  notice says is off by default when building from source; the wheel's binary lists HiPO
  options ("HiPO matrix reordering: "choose", "metis", "amd" or "rcm""), so the PyPI wheel
  is built with HiPO and that code is in it.
- **pyomo.** "Additional Notices" for code derived from FOQUS (BSD-style, with a clause
  granting LBNL a licence to enhancements a user chooses to publish), IDAES (copyright
  notice), PLY (BSD 3-clause), PyUtilib (Sandia, BSD-style), the Water Security Toolkit
  ("Revised BSD License") and WaterTAP (BSD-style with the same enhancements clause). None
  is copyleft.

### Runtime dependencies

Method: `highspy==1.15.1 pyomo==6.10.1 optuna==5.0.0` installed into a fresh venv on
`/usr/bin/python3.11` (3.11.18) and one on `/usr/bin/python3.13` (3.13.18); a script
walked `importlib.metadata` requirements from the three roots, evaluating markers with
no extras, and printed each distribution's licence metadata and licence files; the head of
every licence file was then read. Both Pythons give the same tree except numpy's version.

| Distribution | Version (3.11 / 3.13) | Needed by | Licence (licence file read) | AGPL-3.0 |
| --- | --- | --- | --- | --- |
| highspy | 1.15.1 | root | MIT, bundles above | compatible |
| pyomo | 6.10.1 | root | BSD-3-Clause; no runtime dependencies at all | compatible |
| optuna | 5.0.0 | root | MIT | compatible |
| numpy | 2.4.6 / 2.5.4 | highspy, optuna | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 (already a product dependency, AKS-96) | compatible |
| alembic | 1.20.1 | optuna | MIT ("Copyright 2009-2026 Michael Bayer") | compatible |
| SQLAlchemy | 2.1.8 | optuna, alembic | MIT | compatible |
| Mako | 1.4.3 | alembic | MIT | compatible |
| MarkupSafe | 3.0.4 | Mako | BSD-3-Clause ("Copyright 2010 Pallets") | compatible |
| typing_extensions | 4.16.0 | alembic, SQLAlchemy | PSF-2.0 (the Python licence text) | compatible |
| colorlog | 6.12.0 | optuna | MIT | compatible |
| packaging | 26.3 | optuna | Apache-2.0 OR BSD-2-Clause | compatible |
| tqdm | 4.70.1 | optuna | MPL-2.0 AND MIT: the `LICENCE` gives MPL-2.0 Exhibit A for most files and MIT for some; no Exhibit B ("Incompatible With Secondary Licenses") notice | compatible (below) |
| PyYAML | 6.0.3 | optuna | MIT | compatible |

SQLAlchemy 2.1.8 did not pull in `greenlet` on either Python. OR-Tools was not installed:
it is not chosen (see Decision), so its dependencies (absl-py, numpy, pandas, protobuf,
typing-extensions, immutabledict, from its PyPI `requires_dist`) were not checked.

**AGPL-3.0 check (spec 1 engine licence rule).** The rule lets an adapter import its
engine in-process when the licence is recorded here as compatible with AGPL-3.0 for a
combined work. Every licence above is permissive, or MPL-2.0:

- MIT (Expat), BSD-3-Clause and the Python licence: the FSF licence list calls each
  compatible with the GNU GPL (read 2026-11-06, DECISIONS AKS-85 and AKS-96; the FSF page
  answered 403 to a fetch today, so that reading stands). Apache-2.0: compatible with GPLv3
  (same entries). 0BSD and CC0-1.0 impose no conditions.
- zlib (pdqsort in highspy, and in numpy): the Wikipedia article "zlib License" quotes the
  FSF list: "a free software license, and compatible with the GPL".
- MPL-2.0 (tqdm): section 1.12 of the licence defines "Secondary License" to include the
  GNU Affero General Public License, Version 3.0 or later, and section 3.3 lets a Larger
  Work combining the covered software with such a work be distributed with the covered
  software also under that licence, unless the code is marked "Incompatible With Secondary
  Licenses" (Exhibit B). tqdm's `LICENCE` carries Exhibit A only.
- The FOQUS and WaterTAP enhancement clauses in Pyomo's notices grant a licence to
  enhancements a user *chooses* to publish without a separate agreement; they add no
  condition on distributing the product, and the product modifies no Pyomo code.

So HiGHS (via highspy), Pyomo and Optuna, with every dependency they pull in, may be
imported into the service process under the rule, as spec 1 already says. This is not
legal advice; spec 1 keeps the lawyer's review before the first release, and AKS-83 is
still open.

### Which Pyomo interface drives HiGHS

Pyomo 6.10.1 offers HiGHS through two interfaces, both registered as plugins (read from
`pyomo/contrib/solver/plugins.py` and `pyomo/contrib/appsi/plugins.py`):

| Interface | How to get it | What it is |
| --- | --- | --- |
| `pyomo.contrib.solver` (solver API "v2") | `from pyomo.contrib.solver.common.factory import SolverFactory; SolverFactory("highs")` returns `pyomo.contrib.solver.solvers.highs.Highs`; `pyomo.environ.SolverFactory("highs")` returns the same class behind a legacy wrapper | "Persistent interface to HiGHS"; imports `highspy` and builds the model in a `highspy.Highs` object |
| APPSI | `pyomo.environ.SolverFactory("appsi_highs")` returns `pyomo.contrib.appsi.base.LegacySolver` | The older "auto-persistent" interface, also on `highspy` |

The Pyomo documentation page "Future Solver Interface Changes" (under "Experimental
features") describes `pyomo.contrib.solver`: "The new solver interfaces are still under
active development. They are included in the releases as development previews." and
"APIs and functionality may change with no notice." It lists HiGHS as `highs` in both the
new and the legacy factory, and shows `from pyomo.__future__ import solver_factory_v3` as a
"preview" of the future default. It does not mention APPSI.

Both are in-process: neither runs an executable. The scratch venvs hold no `highs`
executable in `bin/`, and a probe that patched `subprocess.Popen.__init__` recorded no
call during six solves through `SolverFactory("highs")`. HiGHS runs inside the Python
process through the `highspy` extension module (`highspy/_core.cpython-313-x86_64-linux-gnu.so`
and `libhighs.so.1.15.1`).

### What the interface reports

All of the following ran on Python 3.11.18 and 3.13.18 with pyomo 6.10.1 and highspy 1.15.1
(HiGHS 1.15.1), with identical output on both (script and output in Tested).

`solve(model, ...)` returns a `Results` object with `termination_condition`
(`pyomo.contrib.solver.common.results.TerminationCondition`), `solution_status`
(`SolutionStatus`), `incumbent_objective`, `objective_bound` and a `solution_loader`.

| Model | Default call (`load_solutions=True`, `raise_exception_on_nonoptimal_result=True`) | With both `False` |
| --- | --- | --- |
| Product mix (spec 2) | `convergenceCriteriaSatisfied` / `optimal`; objective 2200.0; chairs 24.000000000000004, tables 13.999999999999998 loaded into the variables | same, values loaded only on `solution_loader.load_vars()` |
| Infeasible LP (x ≥ 2, x ≤ 1) | raises `NoOptimalSolutionError` | `provenInfeasible` / `noSolution`, objective `None` |
| Unbounded LP (max x + y, x − y ≤ 1) | raises `NoOptimalSolutionError` | `unbounded` / `feasible`, objective 1.0 (a point, not an optimum) |
| Infeasible integer program (2x = 3, x integer) | raises `NoOptimalSolutionError` | `provenInfeasible` / `noSolution` |
| Unbounded integer program (max x + y, x − y ≤ 1, integers) | raises `NoOptimalSolutionError` | `infeasibleOrUnbounded` / `noSolution` |
| The same, `solver_options={"presolve": "off"}` | | `unbounded` / `feasible` |
| An LP both primal and dual infeasible | | `provenInfeasible` / `noSolution`, with presolve on or off |

`raise_exception_on_nonoptimal_result=False` with `load_solutions=True` still raises
`NoFeasibleSolutionError` on an infeasible model ("A feasible solution was not found, so
no solution can be loaded. Please set opt.config.load_solutions=False ..."), so both must
be `False` for a call that never raises on a non-optimal model.

`infeasibleOrUnbounded` is HiGHS's `kUnboundedOrInfeasible` ("The model is unbounded or
infeasible", HiGHS documentation, "Enums"). For an LP, HiGHS resolves it itself: J. A. J.
Hall wrote on HiGHS issue 1956 (2 October 2024) that if presolve finds the LP dual
infeasible, "by default, HiGHS runs primal simplex to identify which holds". The integer
program above shows that a MIP can still end there; a second solve with presolve `"off"`
gave the definite `unbounded`.

**Duals.** `results.solution_loader.get_duals()` returns a map from each constraint to its
dual. For the product mix: wood 0.9999999999999996, labour 4.0. For the diet problem
(minimize): 0.24444444444444444 and 0.022222222222222213, that is 11/45 and 1/45. In both
cases the sign is ∂objective/∂rhs: raising the wood limit by one raises the maximum profit by
1, raising the first diet requirement by one raises the minimum cost by 11/45. For an
integer program `get_duals()` raises `NoDualsError` ("Solver does not currently have
valid duals"); `get_reduced_costs()` gives the reduced costs of an LP.

**Slacks.** The interface has no slack method; Pyomo's own constraint methods give them
after `load_vars()`: `con.uslack()` (upper bound minus body), `con.lslack()` (body minus
lower bound, `inf` when there is no lower bound) and `con.slack()` (the smaller). For the
product mix, wood has `uslack()` 5.684341886080802e-14 and labour 0.0: the binding wood
constraint is not exactly 0, so "tight" needs a tolerance.

**Options.** `opt.config` holds `tee`, `working_dir`, `load_solutions`,
`raise_exception_on_nonoptimal_result`, `symbolic_solver_labels`, `timer`, `threads`,
`time_limit`, `solver_options`, `rel_gap`, `abs_gap` and `auto_updates`; HiGHS's own options
pass through `solver_options`. With `tee` left `False`, no solve printed anything to
standard output, and no warning was raised.

**Import time** on 3.13.18 (one cold start each): `pyomo.environ` 0.35 s, `optuna` 0.24 s,
`highspy` 0.08 s.

### Lowest versions that install and work

Method: for each combination, a fresh venv on `/usr/bin/python3.11` or `/usr/bin/python3.13`,
`pip install --only-binary=:all: pyomo==<p> highspy==<h>` (newest numpy), then a check
script that imports `pyomo.contrib.solver.common.factory`, solves the product mix (2200, 24
chairs, duals 1 and 4, wood slack below 1e-6), an infeasible LP, an unbounded LP, the
unbounded integer program with and without presolve, and the assignment problem.

| pyomo | highspy | Python | Result |
| --- | --- | --- | --- |
| 6.8.0, 6.8.1, 6.9.0, 6.9.1 | 1.15.1 | 3.13 (6.9.1 also 3.11) | `ModuleNotFoundError: No module named 'pyomo.contrib.solver.common'` |
| 6.9.2, 6.9.3, 6.9.4, 6.9.5, 6.10.0, 6.10.1 | 1.15.1 | 3.13 | every check passes |
| 6.10.1 | 1.8.1, 1.9.0, 1.10.0, 1.11.0 | 3.13 | every check passes |
| 6.9.2 | 1.8.1 | 3.11 and 3.13 | every check passes |
| 6.9.2 | 1.7.2 | 3.11 | every check passes |
| 6.10.1 | 1.15.1 | 3.11 and 3.13 | every check passes |

highspy 1.8.1 (2024-11-13) is the first release with a CPython 3.13 Linux wheel (PyPI file
list), so the lowest pair that works on both Pythons is pyomo 6.9.2 and highspy 1.8.1.
Of the releases tested, pyomo 6.9.2 is the first with `pyomo.contrib.solver.common.factory`.

For Optuna the floor is set by the API the search needs, not by installation: Optuna
4.0.0, 4.5.0 and 4.9.0 install on 3.13 but have no `Trial.set_constraint` (an
`AttributeError`), which arrived in 5.0.0, where the sampler argument `constraints_func`
is deprecated (`docs/research/spec-2-simulation-based-optimization.md`). The lowest Optuna
the search can use without a deprecated argument is 5.0.0, the current release; it is pure
Python (`py3-none-any`) and ran on 3.11.18 and 3.13.18.

### OR-Tools

OR-Tools 9.15.6755 is Apache-2.0, its classifiers list CPython 3.10 to 3.14, and it would bring
absl-py, pandas and protobuf (`protobuf<6.34,>=6.33.1`) with it; its wheel is 29.8 MB
against 5.0 MB for highspy and 4.6 MB for pyomo, and Pyomo has no runtime dependencies at
all. Spec 2 asks only for its version and licence; it is not needed for any Phase 1 problem
(linear objectives and constraints, continuous, integer and binary variables), which HiGHS
covers.

## Sources

- PyPI JSON API, `https://pypi.org/pypi/highspy/json`, `.../pyomo/json`,
  `.../ortools/json`, `.../optuna/json` (fetched 2026-11-07): versions, upload times, licence
  fields, `requires_dist`, file lists.
- The wheels' own licence files (downloaded 2026-11-07, read with `unzip -p`):
  `highspy-1.15.1.dist-info/licenses/LICENSE.txt` and `THIRD_PARTY_NOTICES.md`,
  `pyomo-6.10.1.dist-info/licenses/LICENSE.md`, `optuna-5.0.0.dist-info/licenses/LICENSE` and
  `LICENSE_THIRD_PARTY`, `ortools-9.15.6755.dist-info/licenses/LICENSE`; and the installed
  dependencies' licence files listed in the table.
- Pyomo documentation, "Future Solver Interface Changes",
  https://pyomo.readthedocs.io/en/stable/explanation/experimental/solvers.html (opened
  2026-11-07).
- Pyomo 6.10.1 source, `pyomo/contrib/solver/plugins.py`, `pyomo/contrib/solver/solvers/highs.py`,
  `pyomo/contrib/solver/common/results.py`, `pyomo/contrib/appsi/plugins.py` (read in the
  installed wheel).
- HiGHS documentation, "Enums", https://ergo-code.github.io/HiGHS/dev/structures/enums/
  (opened 2026-11-07): `HighsModelStatus` values; "List of options",
  https://ergo-code.github.io/HiGHS/stable/options/definitions/ (`presolve`: "off", "choose"
  or "on").
- J. A. J. Hall, comment of 2 October 2024 on HiGHS issue 1956, "Option to force
  primal/dual ray", https://github.com/ERGO-Code/HiGHS/issues/1956 (opened 2026-11-07).
- Mozilla Public License 2.0, https://www.mozilla.org/en-US/MPL/2.0/ (opened 2026-11-07):
  sections 1.12 and 3.3, Exhibit B.
- Wikipedia, "zlib License", https://en.wikipedia.org/wiki/Zlib_License (opened
  2026-11-07), quoting the FSF's "Various Licenses and Comments about Them".
- `docs/DECISIONS.md`, AKS-85 and AKS-96 entries: the FSF licence list as read on
  2026-11-06 (Expat, modified BSD, Python 2.0.1 and later, Apache 2.0).

## Decision

- **"HiGHS through Pyomo" is confirmed** for mathematical optimization, and **Optuna is
  confirmed** for simulation-based optimization. All three are MIT or BSD-3-Clause, every
  runtime dependency they pull in is compatible with AGPL-3.0 as above, and all run
  in-process, so under the spec 1 engine licence rule they may be imported (not legal
  advice; AKS-83 open). OR-Tools is not adopted: nothing in Phase 1 needs it, and it brings
  more dependencies than Pyomo and HiGHS together.
- **The interface for AKS-108** is `pyomo.contrib.solver`:
  `from pyomo.contrib.solver.common.factory import SolverFactory` and
  `SolverFactory("highs")`, a fresh solver object per run, checked with `opt.available()`.
  Not APPSI (`appsi_highs`), which is the older interface of the two, and not the legacy
  `pyomo.environ.SolverFactory("highs")`, which wraps the same class but returns the older
  `pyomo.opt.results.results_.SolverResults` (`results.solver.termination_condition`
  `optimal`, `results.solver.status` `ok`). Because
  Pyomo calls this interface a development preview whose API may change, AKS-108 keeps every
  call to it in one module of `src/lcsim/engines/optimize/`, and the version bounds below
  are tested in CI.
- **The call:** `opt.solve(model, load_solutions=False,
  raise_exception_on_nonoptimal_result=False, tee=False)`, so that no outcome raises. Then,
  on `results.termination_condition`:

  | `TerminationCondition` | `summary.json` `status` | What the adapter reads |
  | --- | --- | --- |
  | `convergenceCriteriaSatisfied` (with `solution_status` `optimal`) | `optimal` | `results.solution_loader.load_vars()`, then each variable's value, `results.incumbent_objective`, each constraint's slack and, for a model with no `integer` or `binary` variable, `results.solution_loader.get_duals()` |
  | `provenInfeasible` or `locallyInfeasible` | `infeasible` | nothing |
  | `unbounded` | `unbounded` | nothing (the point HiGHS holds is not an optimum) |
  | `infeasibleOrUnbounded` | solve once more with `solver_options={"presolve": "off"}` and map that result by this table; if it is again `infeasibleOrUnbounded`, as any other row below | |
  | anything else (`maxTimeLimit`, `iterationLimit`, `objectiveLimit`, `minStepLength`, `error`, `interrupted`, `licensingProblems`, `emptyModel`, `unknown`) | none of the three | an E190 (engine error) carrying the condition's name, since spec 2 has no fourth status; `maxTimeLimit` is E192 if AKS-108 sets a time limit |

- **Slack and tight:** a `<=` constraint's slack is `uslack()`, a `>=` constraint's is
  `lslack()`, an `==` constraint's is `slack()` (both sides); tight means |slack| at or below
  a tolerance. HiGHS 1.15.1's defaults, read with `highspy.Highs().getOptionValue`, are
  `primal_feasibility_tolerance` 1e-07 and `mip_feasibility_tolerance` 1e-06, so 1e-6 is at
  least as loose as both; AKS-108 fixes the value and writes it into spec 2.
  The wood constraint's 5.7e-14 shows that spec 2's example `"slack": 0` is a rounded value;
  AKS-108 also decides whether reported slacks and values are rounded.
- **Duals** are read with `get_duals()` for continuous problems only; their sign is
  ∂objective/∂rhs for both senses, as observed. Spec 2's layout does not report duals; the
  product mix benchmark's uniqueness argument uses them (dual values 1 and 4).
- **Declared lower bounds** for `pyproject.toml` (AKS-108 and AKS-109 add them):
  `highspy>=1.15.1`, `pyomo>=6.10.1`, `optuna>=5.0.0`. These follow the house rule of
  AKS-96 to AKS-98: the newest release that installs on Python 3.11, since CI runs 3.11 and
  3.13 with the newest versions and so tests nothing older. The lowest versions that were
  seen to work (pyomo 6.9.2 with highspy 1.8.1 on both Pythons; Optuna 5.0.0 for the
  search's API) are recorded above in case the owner prefers wider bounds.
- **Licence identifiers** in `Capabilities.licence` (spec 1: "an SPDX identifier"): the
  optimization adapter reports `MIT`, the licence of HiGHS, its engine, with `invocation`
  `in-process`; Pyomo's BSD-3-Clause is recorded here and in DECISIONS, not in
  `capabilities()`, which names one identifier. Optuna is not an adapter (spec 2: "a search
  driver inside the experiment manager"), so it reports nothing; its MIT licence is
  recorded here. Owner to confirm.

## Tested

Everything ran in scratch venvs outside the repository on 2026-11-07, on Python 3.11.18 and
3.13.18; nothing was added to `src/`. The probe below (abridged to the product mix and the
three status cases) is what produced the tables in "What the interface reports".

```python
import pyomo.environ as pyo
from pyomo.contrib.solver.common.factory import SolverFactory

opt = SolverFactory("highs")
m = pyo.ConcreteModel()
m.chairs = pyo.Var(bounds=(0, None))
m.tables = pyo.Var(bounds=(0, None))
m.obj = pyo.Objective(expr=45 * m.chairs + 80 * m.tables, sense=pyo.maximize)
m.wood = pyo.Constraint(expr=5 * m.chairs + 20 * m.tables <= 400)
m.labour = pyo.Constraint(expr=10 * m.chairs + 15 * m.tables <= 450)
r = opt.solve(m)
print(
    r.termination_condition,
    r.solution_status,
    r.incumbent_objective,
    pyo.value(m.chairs),
    pyo.value(m.tables),
)
print({c.name: d for c, d in r.solution_loader.get_duals().items()})
print(m.wood.uslack(), m.labour.uslack())
# infeasible(), unbounded() and the integer programs are built the same way and solved with
# opt.solve(m, load_solutions=False, raise_exception_on_nonoptimal_result=False)
```

Output on both Pythons (pyomo 6.10.1, HiGHS 1.15.1): the snippet's three lines, then the
lines the full probes printed for the other models (the full probes' output was identical
on 3.11.18 and 3.13.18, compared by checksum):

```text
TerminationCondition.convergenceCriteriaSatisfied SolutionStatus.optimal 2200.0 24.000000000000004 13.999999999999998
{'wood': 0.9999999999999996, 'labour': 4.0}
5.684341886080802e-14 0.0
infeasible load_solutions=False, raise=False -> TerminationCondition.provenInfeasible SolutionStatus.noSolution obj None
unbounded load_solutions=False, raise=False -> TerminationCondition.unbounded SolutionStatus.feasible obj 1.0
integer infeasible load_solutions=False, raise=False -> TerminationCondition.provenInfeasible SolutionStatus.noSolution obj None
MIP unbounded: infeasibleOrUnbounded / noSolution obj=None
MIP unbounded, presolve off: unbounded / feasible obj=1.0
knapsack TerminationCondition.convergenceCriteriaSatisfied 21.0 {'a': 0.0, 'b': 1.0, 'c': 1.0, 'd': 0.0}
MIP duals: NoDualsError Solver does not currently have valid duals. Please check results.termination_condition and/or results.solution_status.
diet convergenceCriteriaSatisfied 2.177777777777778 1.777777777777778 1.1111111111111112 {'a': 0.24444444444444444, 'b': 0.022222222222222213}
```

The version check printed one line per venv, for example
`py3.11.18 pyomo 6.9.2 highspy 1.8.1 numpy 2.4.6 | mix=ok | inf=provenInfeasible |
unb=unbounded | mipunb=infeasibleOrUnbounded | mipunb_nopre=unbounded | assign=9.0 |
warnings=[]`, and `ERROR ModuleNotFoundError: No module named
'pyomo.contrib.solver.common'` for pyomo 6.9.1 and older.
