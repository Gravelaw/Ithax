# Spec 5 research: Reliability libraries for life data, fault trees and block diagrams

## Question

Spec 5 "Reliability and maintenance" names life-distribution fitting with censored data,
reliability block diagrams (RBDs), fault trees, availability and maintenance-policy
comparison, with "libraries to research, unverified". Its research item asks for open
Python libraries for life-data fitting and fault-tree analysis, with licences. This note
answers:

1. Which open Python libraries fit life distributions to right-censored data, and do they
   reproduce a published worked example?
2. Which maintained open libraries evaluate fault trees and RBDs? If none, can the
   analytic parts be calculators under guide rule 7?
3. What licence does each have (read from the wheel at a pinned version), and may it be
   imported into the service (owner decision F4, spec 1 "Engine licence rule") or must it
   run as a separate process?
4. Upkeep: latest release, cadence over the last two years, Python versions, Linux wheels,
   install under WSL 2.
5. What does the existing `failure` block (spec 2) give for availability and maintenance
   policies, and which benchmarks have exact known answers?

## Finding

### Licences and upkeep (read 2026-11-16)

Each licence was read from the file inside the wheel downloaded with
`pip download --no-deps` at the version shown. Release data is from the PyPI JSON API.
All packages below are pure Python wheels (`py3-none-any`) except scipy and dd, which ship
manylinux wheels; all installed with `uv pip` into a Python 3.12 venv on Linux, so they
install the same way under WSL 2 (WSL 2 is Linux). None needs a GUI; the fitting libraries
import matplotlib, which runs headless with `MPLBACKEND=Agg`.

| Package | Version | File read | SPDX | AGPL-3.0 combined work | Latest release; releases since 2024-11-16 | Python |
| --- | --- | --- | --- | --- | --- | --- |
| scipy | 1.18.1 | `scipy-1.18.1.dist-info/LICENSE.txt` | BSD-3-Clause (bundled parts listed in the same file) | yes, in-process; already a dependency (`scipy>=1.17.1`) | 2026-08-21; 20 | >=3.12 for 1.18 |
| lifelines | 0.30.3 | `lifelines-0.30.3.dist-info/licenses/LICENSE` | MIT | yes, in-process | 2026-03-05; 3 (0.30.1 to 0.30.3, none between 2024-10-29 and 2026-02-04) | >=3.11 |
| reliability (Matthew Reid) | 0.9.0 | `reliability-0.9.0.dist-info/LICENSE` | LGPL-3.0 (GNU LGPL version 3 text; metadata "LGPLv3"; "only" or "or later" not stated in the file) | yes, in-process import as a library | 2025-03-07; 1 (previous 0.8.16 on 2023-12-27) | >=3.10 |
| surpyval | 0.28 | `surpyval-0.28.dist-info/licenses/LICENSE` | MIT | yes, in-process | 2026-11-15; 21, all from 2026-06-10 (gap 2022-12-21 to 2026-06-10) | >=3.11 |
| predictr | 0.1.37 | `predictr-0.1.37.dist-info/LICENSE.txt` | MIT | yes, in-process | 2026-09-09; 10 | classifiers 3.6 to 3.13 |
| RePyability | 0.19.1 | `repyability-0.19.1.dist-info/licenses/LICENSE` | MIT | yes, in-process | 2026-11-16 (today); 18, all from 2026-07-18 (gap 2022-12-22 to 2026-07-18); "Development Status :: 4 - Beta" | >=3.11 |
| faultree | 0.4.0 | `faultree-0.4.0.dist-info/licenses/LICENSE` | BSD-3-Clause | yes, in-process | 2026-10-08; 4 (first 2025-03-21) | >=3.10 |
| dd (faultree's BDD dependency) | 0.6.0 | `dd-0.6.0.dist-info/LICENSE`; `dd/CUDD_LICENSE`; the manylinux wheel also carries `dd/GLIBC_COPYING.LIB` (LGPL-2.1 text) and `dd/GLIBC_LICENSES` | BSD-3-Clause (Caltech); CUDD BSD-3-Clause | yes, in-process; faultree imports only the pure-Python `dd.autoref` | wheel dated 2024-12-01 (PyPI release data not read) | not read |
| pfta | 0.4.0 | `pfta-0.4.0.dist-info/licenses/LICENSE` | GPL-3.0-only (README: "GPL-3.0-only"; file is the GPL v3 text) | GPL v3 section 13 allows combining with AGPL v3, but run it as a separate process through its CLI text files (F4) | 2025-05-19; 15, all 2025-04-17 to 2025-05-19 | >=3.11 (classifiers 3.11, 3.12) |
| sfta | 0.9.1 | no licence file in the wheel; METADATA classifier "GPLv3" | GPL-3.0 (classifier only) | as pfta; superseded by pfta (same author) | 2024-11-18; 1 | >=3.11 |
| pyrbd | 0.4.5 | `pyrbd-0.4.5.dist-info/licenses/LICENSE` | MIT | draws RBDs with LaTeX/TikZ; computes nothing, not useful | 2026-05-23; 10 | >=3.10 |
| weibull | 0.1.3 | not read | MIT (metadata) | unmaintained: last release 2019-11-04, classifiers 3.5 and 3.6 | 2019-11-04; 0 | not stated |
| cutsets | 1.4 | sdist has no licence file; metadata "MIT" | MIT (metadata) | unmaintained: 5 releases, all 2021-02-14/15 | 2021-02-15; 0 | >=3.6 |

Not found or not usable from PyPI:

- `scram` on PyPI is an unrelated RNA mapper (MIT, 2017). SCRAM the probabilistic risk
  analysis tool (C++, Open-PSA input, GPL-3 per web search) is not on PyPI; not installed,
  not run. Its licence file was not read (github.com answers 403 here).
- `fta` on PyPI is a finance package (Apache-2.0), not fault-tree analysis.
- `pyfta`, `fault-tree`, `faulttree`, `emfta`, `ftaim`, `openfta`, `rbd`,
  `reliability-block-diagram` and `pyreliability`: no such project on PyPI (HTTP 404).
- `pyfault` on PyPI is a Memfault exception handler, unrelated.
- XFTA and OpenFTA: not checked beyond the PyPI search; not read.

### What each library covers

| Need | scipy | lifelines | reliability | surpyval | RePyability | faultree | pfta |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Weibull MLE with right censoring | yes (`stats.CensoredData`, listed in the SciPy 1.11.0 release notes) | yes (`WeibullFitter`) | yes (`Fit_Weibull_2P`) | yes (`Weibull.fit`) | via surpyval | no | no |
| RBD: series, parallel, k-out-of-n, general graph | no | no | no | no | yes (`NonRepairableRBD`, exact) | no | no |
| Fault tree: AND, OR, vote, minimal cut sets, top-event probability | no | no | no | no | yes (`FaultTree`, exact; also NOT and dynamic gates) | yes (BDD, exact; cut sets with a completeness flag) | yes (truncated inclusion-exclusion over cut sets; text in, TSV and SVG out) |
| Repairable availability (steady state and over time) | no | no | no | no | yes (`RepairableRBD`) | no | per event (constant failure and repair rates) |
| Maintenance policy | no | no | `optimal_replacement_time` | no | yes (policies, crews, spares; not tried) | no | no |

### Trial results (all numbers copied from the `output-*.txt` files)

1. **Weibull, right-censored, NIST/SEMATECH e-Handbook 8.4.1.3.** Ten failures (54 to
   386 h) and ten units removed at 500 h; published η = 606.5280, β = 1.7208,
   log-likelihood −75.135. All five libraries agree with the published values to four
   significant figures:

   | Library | η | β | log-likelihood |
   | --- | --- | --- | --- |
   | reliability 0.9.0 | 606.5275 | 1.7208 | −75.135 |
   | lifelines 0.30.3 | 606.5275 | 1.7208 | −75.135 |
   | scipy 1.18.1 | 606.5276 | 1.7208 | −75.135 |
   | surpyval 0.28 | 606.5276 | 1.7208 | −75.135 |
   | predictr 0.1.37 | 606.5276 | 1.7208 | −75.135 |

   The η differences (−0.0004 to −0.0005) are optimiser tolerance; the closed-form
   log-likelihood at the published values is −75.135.

2. **RBDs.** RePyability 0.19.1 equals the closed form to at most 1.8e-12 in every case;
   a seeded numpy Monte Carlo (10⁶ draws, `default_rng(20261116)`) lies within 0.85
   standard errors in every case:

   | Case | Closed form | RePyability |
   | --- | --- | --- |
   | R1·R2·(1−(1−R3)(1−R4)), R = 0.95, 0.90, 0.80, 0.80 | 0.8208000000 | 0.8208000000 |
   | 2oo3, p = 0.9: 3p² − 2p³ | 0.9720000000 | 0.9720000000 |
   | Lundteigen and Rausand SIF: PT 2oo3 (q = 0.05), LS (0.01), SDV 1oo2 (0.10) | 0.9729942750 | 0.9729942750 |
   | MTTF 1oo2, λ = 0.001 (published 1500) | 1500 | 1500.0000000000 |
   | MTTF 2oo3, λ = 0.001: 5/(6λ) | 833.3333333333 | 833.3333333333 |
   | R(500) 2oo3, exponential: 3e^(−2λt) − 2e^(−3λt) | 0.6573780032 | 0.6573780032 |

   RePyability's minimal cut sets of the SIF equal the published ones.

3. **Fault tree** (the same SIF as a tree: OR of a 2-out-of-3 vote, LS, and an AND of the
   valves). Exact top-event probability 0.027005725000 from the closed form and from a
   64-state truth table; rare-event approximation 0.027500000000; minimal cut set upper
   bound 0.027232388439. RePyability 0.19.1, faultree 0.4.0 and pfta 0.4.0 (run as a
   subprocess) all give 0.027005725000 (differences ≤ 2.4e-17), and all three return the
   five published minimal cut sets.

4. **Availability.** A = MTTF/(MTTF + MTTR) = 100/125 = 0.8: RePyability
   `mean_availability` gives 0.8000000000; point availability at t = 10, 50, 200 matches
   μ/(λ+μ) + λ/(λ+μ)·e^(−(λ+μ)t) to within 1.1e-8; two such units in parallel give 0.96
   and in series 0.64, both exact; a 200-run simulation over 100,000 time units gives a
   mean fraction up of 0.7998.

### The existing `failure` block (spec 2)

- `failure` has `target`, `time_to_failure`, `time_to_repair`. One block is one
  alternating up/down process on calendar time, so at most one unit of the target is
  failed at a time ("Failure", spec 2).
- `<server>.availability` is the time at least one unit is not failed; a server of
  capacity 2 or more always has availability 1.
- `benchmarks/failure` already checks A = 100/(100 + 25) = 0.8 with exponential up and
  down times (M4, AKS-107, `three_se`). So a known availability is a benchmark already.
- What it cannot express: preventive or age-based replacement (a repair or replacement
  before failure that renews the unit), several units failing independently on one
  server, repair crews and spares. The
  `schedule` block changes capacity but does not renew a unit. So a maintenance-policy
  comparison (run to failure against age or block replacement) cannot be modelled on the
  Phase 1 engine as specified; it needs new settings on `failure` (a spec 2 and model
  format change).

### Rule 7 reading

- Series, parallel and k-out-of-n reliability, MTTF of k-out-of-n with constant rates,
  steady-state availability, the rare-event approximation and the minimal cut set upper
  bound are closed-form formulas with published sources: they fit the calculator rule.
- A general RBD (bridges, a component drawn twice) and the exact top-event probability of
  a tree with repeated events need structure-function evaluation (pivotal decomposition,
  BDD or inclusion-exclusion). That is not "integrating differential equations, solving
  linear systems or iterating to convergence", but it is an algorithm with its own failure
  modes and limits. Wrap a library for it rather than write it.
- Censored MLE is numerical optimisation: wrap scipy, never write it.

## Sources

- NIST/SEMATECH e-Handbook of Statistical Methods, 8.4.1.3 "A Weibull maximum likelihood
  estimation example", https://www.itl.nist.gov/div898/handbook/apr/section4/apr413.htm
  (read 2026-11-16): the data and η = 606.5280, β = 1.7208, log-likelihood −75.135,
  AIC 154.27.
- NIST/SEMATECH e-Handbook 8.1.8.2 "Series model", 8.1.8.3 "Parallel or redundant model",
  8.1.8.4 "R out of N model", 8.1.8.6 "Complex systems",
  https://www.itl.nist.gov/div898/handbook/apr/section1/apr182.htm (and apr183, apr184,
  apr186; read 2026-11-16). Formulas only, no numbers.
- M. Rausand, "System Reliability Theory" chapter 4 slides (version 0.1, for Rausand and
  Høyland, Wiley 2004), https://ntnu.edu/documents/624876/1277590549/chapt04-1.pdf (read
  2026-11-16): 2oo3 = 3p² − 2p³ (slide 14), 1oo2 MTTF 3/(2λ) = 1500 for λ = 0.001
  (Example 4.9, slide 27), 2oo3 MTTF 5/(6λ) (slide 29), koon MTTF table (slide 33), minimal
  cut set upper bound (slide 38). Slide 35 gives Q0 = q1·q2 for
  two inputs to an AND gate but prints "Q0 = 1 − ∏ qj" for m inputs; slide 37 gives the
  product, which is correct, so the "1 −" is a typo.
- M. A. Lundteigen and M. Rausand, SIS book chapter 5 "Fault Tree Analysis" slides,
  https://ntnu.edu/documents/624876/1277046207/SIS%20book%20-%20chapter%2005%20-%20Introduction%20to%20fault%20trees
  (read 2026-11-16): the SIF structure and its five minimal cut sets (slides 8 to 10),
  upper bound approximation (slide 14), q = MTTR/(MTTF + MTTR) (slide 16).
- SciPy 1.11.0 release notes, https://docs.scipy.org/doc/scipy/release/1.11.0-notes.html
  (read 2026-11-16): `scipy.stats.CensoredData` "can be used as input to the `fit` method
  of univariate distributions". The first 100,000 characters of the 1.10.0 notes do not
  mention it; the rest was not read.
- PyPI JSON API, `https://pypi.org/pypi/<package>/json`, for every package in the table
  (read 2026-11-16).
- pfta 0.4.0 README (in the wheel's METADATA) and `pfta/computation.py` docstrings: input
  format, GPL-3.0-only, truncated inclusion-exclusion.
- Spec 2 `docs/specs/2-core-engine.md` "Failure", "Statistic definitions" and
  `benchmarks/failure/expected.json`.
- Web search (2026-11-16) for open fault-tree tools; SCRAM's GPL-3 licence is from search
  results only, not from its licence file.

## Decision

Proposed defaults, owner to confirm:

- **Life-data fitting: scipy.stats, in-process.** `weibull_min.fit(stats.CensoredData(...),
  floc=0)` and the same for the other spec 1 families. No new dependency (scipy is already
  in, BSD-3-Clause), and it matches NIST 8.4.1.3. It extends the M6 distribution fit
  (`docs/research/spec-3-distribution-fit.md`). lifelines (MIT) is the fallback if
  confidence bounds or a Kaplan-Meier curve are needed; reliability (LGPL-3.0, one release
  in two years) is not proposed, though an in-process import would be allowed.
- **RBD calculators.** Series, parallel, k-out-of-n (identical and, by the structure
  function, non-identical parts), koon MTTF with constant rates, and steady-state
  availability A = MTTF/(MTTF + MTTR) per block, combined by series and parallel rules.
  Each cites NIST 8.1.8 and Rausand chapter 4. A diagram that does not reduce by series,
  parallel and koon steps is refused with an issue code in Phase 2 (NIST 8.1.8.6 says
  reduction "will work for many, but not all, systems").
- **Fault trees: faultree (BSD-3-Clause), in-process.** Exact (BDD), cut sets with a
  completeness flag, AND, OR and k-of-n gates, 4 releases since 2025-03. Alternatives:
  RePyability (MIT; widest coverage but beta and 18 releases in four months, so its API is
  still moving); pfta (GPL-3.0-only) as a separate process with its text input and TSV
  output, which fits the file-exchange adapter pattern but has had no release since
  2025-05-19 and uses inclusion-exclusion, which grows fast with the number of cut sets.
  The rare-event approximation and the minimal cut set upper bound are calculators shown
  next to the exact value.
- **Maintenance-policy comparison** stays on the process engine as spec 5 says, but needs
  a `failure` extension (see blocking question 1).
- **Monte Carlo cross-checks** in tests draw through `ithax.model.streams`, as the
  randomness rule requires; the trial used `numpy.random.default_rng` only because it is
  research code.
- **Benchmarks** (exact, deterministic, four significant figures per spec 2):

  | Case | Known answer | Source |
  | --- | --- | --- |
  | Weibull MLE, NIST 8.4.1.3 data, right-censored | η = 606.5, β = 1.721 (606.5280, 1.7208) | NIST 8.4.1.3 |
  | 2oo3, p = 0.9 | 0.9720 | Rausand ch. 4 slide 14 formula 3p² − 2p³ |
  | Series-parallel R1·R2·(1−(1−R3)(1−R4)), 0.95, 0.90, 0.80, 0.80 | 0.8208 | NIST 8.1.8.2 and 8.1.8.3 |
  | 1oo2 MTTF, λ = 0.001 | 1500 | Rausand Example 4.9 |
  | 2oo3 MTTF, λ = 0.001 | 833.3 | Rausand slides 29 and 33 |
  | SIF fault tree (published cut sets), q = 0.05, 0.01, 0.10 | cut sets C1 to C5; exact Q = 0.02701; rare-event 0.02750; upper bound 0.02723 | Lundteigen and Rausand ch. 5; formulas above |
  | Single repairable unit, MTTF 100, MTTR 25 | A = 0.8000 | existing `benchmarks/failure` (process engine, `three_se`) and the calculator |
  | Two such units in parallel, independent repair | A = 0.9600 | NIST 8.1.8.3 applied to availabilities |

  The SIF and series-parallel probabilities were chosen in this note, not published; the
  formulas are published. A benchmark whose numbers are printed in a source would be
  stronger: see reversible question 4.

Open questions.

Blocking:

1. **Maintenance policies on the process engine.** Spec 5 says policy comparison runs on
   the Phase 1 engine with `failure` and `schedule`, but neither can renew a unit before
   it fails, and `failure` fails one unit at a time. Options: (a) add optional settings to
   `failure` (for example a preventive replacement interval or age, with its own
   duration), a spec 2 and model format change; (b) run policy comparison in RePyability
   `RepairableRBD` instead of the process engine; (c) drop policy comparison from Phase 2.
   Recommended default: (a), with a benchmark from the age-replacement cost-rate formula
   (source to find). Changes the model format, so it needs an owner decision issue.

Reversible:

2. Fault-tree engine: faultree (proposed) against RePyability or pfta as a process.
3. Whether to add lifelines for confidence bounds on fitted parameters, or report none in
   Phase 2.
4. Find a fault-tree or RBD worked example with printed numbers (NUREG-0492 Fault Tree
   Handbook, 1981, was not reachable: nrc.gov answered 403) to replace the chosen
   probabilities in the benchmarks above.
5. Whether a general (non-reducible) RBD is in Phase 2; if so, wrap RePyability or faultree
   (an RBD is a fault tree of its minimal cut sets) rather than write pivotal
   decomposition.

## Tested

All on 2026-11-16, Linux, Python 3.12 venv in the session's scratch folder, installed with
`uv pip install reliability==0.9.0 lifelines==0.30.3 scipy==1.18.1 surpyval==0.28
predictr==0.1.37 repyability==0.19.1 faultree==0.4.0 pfta==0.4.0 sfta==0.9.1` (resolved
numpy 2.5.5, dd 0.6.0, matplotlib 3.11.2, pandas 2.3.3). Scripts and their real output are
in `docs/research/spec-5-trials/reliability/`:

- `weibull_censored.py` → `output-weibull_censored.txt` (run with `MPLBACKEND=Agg`):
  five libraries against NIST 8.4.1.3; all match to four significant figures.
- `rbd.py` → `output-rbd.txt`: RePyability and seeded Monte Carlo against six closed
  forms; all match (library to 1.8e-12, Monte Carlo within 0.85 standard errors).
- `fault_tree.py` → `output-fault_tree.txt`: RePyability, faultree and pfta (CLI in a
  subprocess, output in a temporary folder) against the closed form and a truth table;
  all give 0.027005725000 and the five published cut sets.
- `availability.py` → `output-availability.txt`: RePyability steady-state, point,
  parallel and series availability against closed forms; all match (point availability
  to 1.1e-8); simulated 0.7998 against 0.8.

Not run:

- The Ithax `benchmarks/failure` case was not rerun here; its expected value (0.8) was read
  from `benchmarks/failure/expected.json`.
- SCRAM, XFTA and OpenFTA: not on PyPI, so not installed (no apt, conda or binaries here).
- sfta: installed, not run (superseded by pfta, same author).
- RePyability maintenance policies, `reliability.optimal_replacement_time`, Python 3.11 and
  3.13 installs, Windows, and dd's PyPI release history: not tried or not read.
- Licences of transitive dependencies (autograd, formulaic, pint, networkx, ply, tqdm and
  others): not read.
