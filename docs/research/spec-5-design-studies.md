# Spec 5 research: Design study layer (OpenMDAO, Dakota, Optuna, pymoo, SALib, scipy.stats.qmc)

## Question

Spec 5 "Design studies" lists five study types (parameter sweep, designed experiment, sensitivity analysis, optimization, uncertainty study) and proposes "OpenMDAO for coupling and gradient-based optimization, with Optuna and pymoo for gradient-free and multi-objective problems". Its research item asks for "OpenMDAO against Dakota for wrapping external engines", and its acceptance row asks that "A design study optimizes a process model and a physical system model with the same interface".

Questions for this note:

- Licence, upkeep and Linux and WSL 2 install of OpenMDAO, Dakota, Optuna, pymoo, SALib and `scipy.stats.qmc`.
- How each wraps an external black-box engine; whether it needs gradients; whether it handles several objectives, constraints, parallel evaluations, and repeats exactly from a seed.
- Which library should do which study type, and whether OpenMDAO is needed at all when most Ithax engines are black boxes without gradients.

Context from the repository: Optuna is already a dependency (`pyproject.toml` `optuna>=5.0.0`, locked at 5.0.0) and drives the spec 2 simulation-based search in `src/ithax/runs/search.py` (TPE, seeded from the spec 1 stream `<seed>:0:optimizer`, ask and tell one trial at a time, `Trial.set_constraint`). scipy is already a dependency (`scipy>=1.17.1`). No sensitivity library has been chosen.

## Finding

Read on 2026-11-16.

### Licences (read from the files at pinned versions)

| Package | Version | File read | SPDX | AGPL-3.0, in-process? |
| --- | --- | --- | --- | --- |
| OpenMDAO | 3.45.2 | `openmdao-3.45.2.dist-info/licenses/LICENSE.txt` in `openmdao-3.45.2-py3-none-any.whl` (SHA-256 `2c24a08d…a1`) | Apache-2.0 | Compatible; import is fine |
| Optuna | 5.1.0 | `optuna-5.1.0.dist-info/licenses/LICENSE` and `LICENSE_THIRD_PARTY` in `optuna-5.1.0-py3-none-any.whl` (`aba6a73d…b1`) | MIT (third-party parts: SciPy BSD-3-Clause, fdlibm notice, Apache-2.0 text) | Compatible; import is fine (already imported) |
| pymoo | 0.6.2 | `pymoo-0.6.2.dist-info/licenses/LICENSE` in the cp312 manylinux x86_64 wheel (`9fd4569f…0a`) | Apache-2.0 | Compatible; import is fine |
| moocore (pymoo dependency) | 0.3.2 | `moocore-0.3.2.dist-info/licenses/COPYRIGHTS` in the abi3 manylinux x86_64 wheel (`8557a411…fb`): "the combined work is licensed under the LGPL v2.1 or later" (MPL-2.0 files plus an LGPL AVL-tree library) | LGPL-2.1-or-later | Compatible (LGPL-2.1-or-later can be taken as LGPL-3.0); import is fine |
| SALib | 1.6.0 | `salib-1.6.0.dist-info/licenses/LICENSE.md` in `salib-1.6.0-py3-none-any.whl` (`4bb4f036…df`) | MIT | Compatible; import is fine |
| SciPy (`scipy.stats.qmc`) | 1.18.1 | `scipy-1.18.1.dist-info/LICENSE.txt` in the cp312 manylinux x86_64 wheel (`f55fa87b…18`) | BSD-3-Clause; the binary also bundles OpenBLAS (BSD-3-Clause), LAPACK (BSD-3-Clause-Open-MPI) and the GCC runtime (GPL-3.0-or-later WITH GCC-exception-3.1) | Compatible; import is fine (already imported) |
| Dakota (Sandia) | 6.24.0 | `LICENSE`, `COPYRIGHT` and `README` at tag `v6.24.0`, fetched from `raw.githubusercontent.com/snl-dakota/dakota/v6.24.0/` | LGPL-2.1-or-later ("either version 2.1 of the License, or (at your option) any later version", README) | Compatible. Not importable anyway (a C++ program); it would run as a separate process. README lists optional third-party parts under GPL (fftw, CDDLIB; "disabled by default") and commercial add-ons (DOT, NLPQL, NPSOL) |

The `dakota` name on PyPI is not Sandia's Dakota: `dakota-0.0.1.tar.gz` (uploaded 2013-11-22, the only release) holds a 63-byte `__init__.py` ("This is my python package namespace.") and declares CC BY-SA 3.0. `dakota-python`, `pydakota`, `pydakota2`, `dakotathon` and `dakota-interface` answer 404 on PyPI. There is no pip-installable Sandia Dakota.

Other runtime dependencies, from wheel metadata (not the licence files): OpenMDAO needs networkx, numpy, packaging, requests, scipy. pymoo needs numpy, scipy, moocore, autograd, cma, matplotlib, alive_progress, Deprecated. SALib needs matplotlib, multiprocess, numpy, pandas, scipy. All declare MIT, BSD, Apache-2.0, PSF, MPL-2.0 or LGPL-2.1-or-later in their metadata.

### Upkeep and install

PyPI JSON read 2026-11-16; "releases" counts versions first uploaded from 2024-11-16 to 2026-11-16.

| Package | Latest (date) | Releases in two years | Python | Linux wheels; WSL 2 |
| --- | --- | --- | --- | --- |
| OpenMDAO | 3.45.2 (2026-10-27) | 12 (3.36.0 to 3.45.2), about every two months | `>=3.10` | Pure-Python wheel; installs with pip under WSL 2 as on Linux. Parallel cases and parallel groups need MPI (mpi4py) |
| Optuna | 5.1.0 (2026-11-16) | 15, including 5.0.0rc1 and three 3.x backports | `>=3.10`; classifiers 3.10 to 3.15 | Pure-Python wheel; WSL 2 as Linux |
| pymoo | 0.6.2 (2026-06-28) | 4, including one `.dev0` | `>=3.10`; classifiers 3.10 to 3.14 | manylinux and musllinux wheels for x86_64 and aarch64; WSL 2 as Linux. Pulls in matplotlib |
| SALib | 1.6.0 (2026-09-19) | 2 (1.5.2, 1.6.0) | `>=3.10`; classifiers 3.10 to 3.12 and 3.14 | Pure-Python wheel; WSL 2 as Linux. Pulls in matplotlib and pandas |
| SciPy | 1.18.1 (2026-08-21) | 12 final releases (20 with release candidates) | `>=3.12` (1.18); 1.17.1 is locked for Python 3.11 | manylinux wheels; WSL 2 as Linux |
| Dakota | 6.24 (announced 2026-05-15) | Twice a year: 6.22 (2025-05-15), 6.23 (announced 2025-12-10; release notes dated 2025-11-17), 6.24 | C++ program, not a Python package | No wheel. Sandia ships binaries built on RHEL 7 and 8, Windows and macOS, and its download page says "Linux binaries usually will not work on other Linux distributions". Ubuntu under WSL 2 would need a build from source. A conda-forge package is listed (anaconda.org `cf-staging/dakota`, LGPL-2.1-or-later); conda is not allowed in this container |

### How each wraps an external engine

| | OpenMDAO | Dakota | Optuna | pymoo | SALib | `scipy.stats.qmc` |
| --- | --- | --- | --- | --- | --- | --- |
| Wrapping | `ExplicitComponent.compute` (Python call) or `ExternalCodeComp` (writes inputs, runs a command, checks named input and output files, timeout, return codes, `fail_hard` or soft `AnalysisError`) | `fork` or `system` interface: Dakota writes a parameters file, runs an analysis driver, reads a results file; `dprepro` fills input templates. A Python `direct` interface "requires a special Dakota build" | Any Python callable; ask and tell | `ElementwiseProblem._evaluate` (Python call) | Samples are arrays; the caller evaluates them and passes the outputs back | Samples only; the caller evaluates |
| Gradients | Uses them; for a black box, finite differences (`method="fd"`) | Optional; many derivative-free methods | Not used | Not used | Not used | n/a |
| Several objectives | Through drivers such as pyOptSparse (not tried) | Yes (MOGA in JEGA) | Yes (`NSGAIISampler`, TPE) | Yes, its main purpose (NSGA-II, NSGA-III, MOEA/D …) | n/a | n/a |
| Constraints | Yes (`add_constraint`) | Yes | Yes (`Trial.set_constraint`, feasible at 0 or less) | Yes (`out["G"]`, feasible at 0 or less) | n/a | n/a |
| Parallel evaluations | `DOEDriver(run_parallel=True)` and parallel groups need MPI | Asynchronous local evaluations, MPI | Parallel trials exist, but the spec 2 note found they reseed the sampler from the operating system | `StarmapParallelization` with any pool; tried: same result as serial | Caller decides | Caller decides |
| Seed | Driver and generator seeds; `LatinHypercubeGenerator(seed=…)` needs the optional `pydoe` package | `seed` keyword | `TPESampler(seed=…)`; tried: repeats | `minimize(..., seed=…)`; tried: repeats | `seed=` on sample and analyse; tried: repeats | `rng=` on `LatinHypercube`, `Sobol`; tried: repeats |

### Trials

All in a scratch Python 3.12 virtual environment with openmdao 3.45.2, optuna 5.1.0, pymoo 0.6.2, salib 1.6.0, scipy 1.18.1, numpy 2.5.5. Scripts and their outputs are in `docs/research/spec-5-trials/design-studies/`; "Tested" below lists them.

- **OpenMDAO, paraboloid, SLSQP.** In-process and through `ExternalCodeComp` both gave x = 6.666666, y = −7.333334, f = −27.333333, |f − f*| = 3.30e-13, with 17 external process calls. With OpenMDAO's default polling the external run took 5.44 s; with `poll_delay` 0.005 s, 0.73 s; the same script run 17 times with `subprocess.run` took 0.46 s. With `poll_delay` 0, OpenMDAO polls every max(0.1, timeout/100) s (`openmdao/utils/shell_proc.py`), here 0.3 s per call.
- **OpenMDAO, Rosenbrock 2-D, SLSQP with finite differences** from (−1.2, 1): x = (0.999699, 0.999398), f = 9.051e-08, distance to (1, 1) 6.73e-04. Finite-difference gradients limit the accuracy.
- **OpenMDAO LHS DOE** not run: `LatinHypercubeGenerator requires the 'pydoe' package`.
- **Optuna TPE, Branin.** Best value over seeds 1, 2, 3: budget 50: 0.417087, 0.419572, 0.435196; budget 100: 0.417087, 0.419572, 0.405632; budget 200: 0.399147, 0.399705, 0.399725 (published 0.397887). Seed 1, budget 100 repeated exactly. With the constraint x1 ≥ 5 (as `set_constraint`), 200 trials: 0.398902 at (9.4146, 2.4891), feasible.
- **pymoo GA, constrained Branin** (x1 ≥ 5 as `G`), 20 × 10 evaluations: 0.406066 at (9.4623, 2.4690), feasible.
- **ZDT1 (30 variables), IGD against 1,001 points of f2 = 1 − √f1.** pymoo NSGA-II, population 100: 2,000 evaluations: 0.50462 (seed 1), 0.56906 (seed 2); 20,000 evaluations: 0.00555, 0.00564, about 1 s each. Optuna `NSGAIISampler`, population 100: 2,000 trials: 0.52389, 0.64142; 20,000 trials (seed 1): 0.05699 in 61.0 s. pymoo seed 1 repeated exactly.
- **SALib Sobol, Ishigami (a = 7, b = 0.1).** Analytic from the OpenTURNS formulas: S1 = 0.3139, S2 = 0.4424, S3 = 0, ST1 = 0.5576, ST2 = 0.4424, ST3 = 0.2437, mean 3.5, variance 13.8446. These match the values given in the task. With N = 8192 (40,960 evaluations): S1 = 0.3146, 0.4415, 0.0009; ST = 0.5576, 0.4424, 0.2438; confidence half-widths 0.0108 to 0.0284. With N = 1024 (5,120 evaluations) every estimate was within its confidence half-width of the analytic value. The same seed repeated exactly.
- **SALib Morris**, r = 100 (400 evaluations): μ* = 7.079, 7.875, 6.499; σ = 6.249, 7.9, 8.97. Morris ranks x3 last on μ* but gives it the largest σ, which flags its interaction with x1.
- **`scipy.stats.qmc`, uncertainty study of Ishigami, 4,096 points, seed 5.** Latin hypercube: mean 3.4918, variance 13.7968; scrambled Sobol: mean 3.5001, variance 13.8825; plain Monte Carlo with `numpy.random.default_rng(5)`: mean 3.4259, variance 13.3933 (known 3.5 and 13.8446). Centred discrepancy 2.55e-05, 2.05e-07 and 1.04e-04. Both qmc samples repeated exactly from the seed.
- **One interface, two engines.** `trial_same_interface.py` defines `evaluate(values: dict) -> dict`, once in-process and once as a separate process exchanging JSON files (0.047 s per evaluation, mostly Python start-up). Optuna, pymoo, SciPy Nelder–Mead, a sweep, a Latin hypercube and SALib Sobol ran unchanged on both and gave identical results (`same results from both engines: True`). Nelder–Mead reached 0.397887357729946 in 111 evaluations. pymoo GA with four worker processes gave the same best (0.444150) as serial.

### What this means for Ithax

- Every Ithax engine is reached through the spec 1 adapter contract (`translate`, `run`, `collect`), and the spec 2 search already runs each candidate as its own evaluation in `engine/search-<n>`. A design study needs exactly that: one evaluation is "set these inputs, run, read these metrics". The same-interface trial shows that all the candidate libraries can drive such a callable, and that the study layer never needs to know the engine.
- OpenMDAO's strengths are coupled multidisciplinary models with analytic or complex-step derivatives, and MPI-scale parallelism. Ithax engines give no derivatives, and SimPy outputs are noisy, so finite differences on them are unreliable. Wrapping an Ithax run in OpenMDAO would add a layer (a Problem, a model, components, drivers, recorders) whose only use would be SciPy's optimizers, which can be called directly; it adds polling latency unless tuned, an optional `pydoe` for designed experiments and MPI for parallel runs. Coupling ("chaining first", spec 5) is already the experiment manager's job.
- Dakota covers every study type, but it is a C++ program with no wheel, Linux binaries only for RHEL, a text input deck of its own, and file-based exchange. Ithax would write Dakota decks and parse Dakota output, a second model format to keep in step. Its licence would allow a separate process.

## Sources

- Spec 5 `docs/specs/5-systems-and-design.md` ("Design studies", "Research before building", "Acceptance tests"); spec 1 "Engine licence rule"; spec 2 "Simulation-based optimization" and `docs/research/spec-2-simulation-based-optimization.md`; `src/ithax/runs/search.py`; build guide rule 7. Read 2026-11-16.
- PyPI JSON for openmdao, optuna, pymoo, SALib, scipy, dakota, moocore (`https://pypi.org/pypi/<pkg>/json`), read 2026-11-16; wheels and the `dakota` sdist downloaded from the URLs in that JSON.
- Dakota: `LICENSE`, `COPYRIGHT`, `README` at <https://raw.githubusercontent.com/snl-dakota/dakota/v6.24.0/>; licensing page <https://dakota.sandia.gov/?p=184>; releases <https://dakota.sandia.gov/category/release/>; downloads <https://dakota.sandia.gov/downloads/>; simulation interfaces and the `python` analysis driver, <https://snl-dakota.github.io/docs/6.23.0/users/_sources/usingdakota/inputfile/interfaces/simulationinterfaces.rst.txt> and <https://snl-dakota.github.io/docs/6.24.0/users/_sources/usingdakota/reference/interface-analysis_drivers-python.rst.txt>; conda listing <https://anaconda.org/cf-staging/dakota>. All read 2026-11-16.
- OpenMDAO documentation: "Paraboloid - A Single-Discipline Model" (f = (x−3)² + xy + (y+4)² − 3, minimum at x = 20/3, y = −22/3; f there = −246/9 = −27.333 computed from the formula), `ExternalCodeComp`, `DOEDriver` (generators needing pydoe; `run_parallel` "requires MPI"), <https://openmdao.org/newdocs/versions/latest/>, read 2026-11-16.
- Surjanovic, S. and Bingham, D., *Virtual Library of Simulation Experiments*, <https://www.sfu.ca/~ssurjano/rosen.html> (f(x*) = 0 at (1, …, 1)) and <https://www.sfu.ca/~ssurjano/branin.html> (a = 1, b = 5.1/(4π²), c = 5/π, r = 6, s = 10, t = 1/(8π); f(x*) = 0.397887 at (−π, 12.275), (π, 2.275), (9.42478, 2.475)), read from the pages' formula images 2026-11-16. Ishigami page <https://www.sfu.ca/~ssurjano/ishigami.html> (a = 7, b = 0.1 after Crestaux et al. 2007 and Marrel et al. 2009).
- Zitzler, E., Deb, K. and Thiele, L. (2000), "Comparison of multiobjective evolutionary algorithms: empirical results", *Evolutionary Computation* 8(2), 173–195, doi:10.1162/106365600568202; ZDT1 is T1, equation 7 on p. 177: "The Pareto-optimal front is formed with g(x) = 1". Read from <https://sop.tik.ee.ethz.ch/publicationListFiles/zdt2000a.pdf> on 2026-11-16.
- OpenTURNS, "The Ishigami function" use case, source `use_case_ishigami.rst` at <https://openturns.github.io/openturns/latest/_sources/usecases/use_case_ishigami.rst.txt> (E[Y], Var Y, V1, V2, V13 and the S and ST formulas), citing Ishigami and Homma (1990) and Sobol' and Levitan (1999); read 2026-11-16.

## Decision

Proposed defaults (owner to confirm):

1. **No OpenMDAO in Phase 2.** Spec 5's "Proposed engine" line changes to the split below. OpenMDAO is reconsidered only if a later phase needs coupled models with derivatives (for example FMUs that provide directional derivatives). Candid reading: for black-box engines it is a wrapper around SciPy's optimizers with extra cost, not an engine.
2. **No Dakota.** No wheel, no Ubuntu or WSL 2 binary, and a second input format to maintain. Its methods overlap what the libraries below give in-process.
3. **One evaluation interface.** A design study sees named inputs (model parameters with bounds or distributions) and named outputs (metrics), and each evaluation is one ordinary Ithax run through the adapter contract, in its own subfolder as the spec 2 search does. This is what makes a process model and an FMU model optimizable "with the same interface" (spec 5 acceptance row).
4. **Library per study type.**

   | Study | Library | Notes |
   | --- | --- | --- |
   | Parameter sweep | None (a grid of values) | One or two inputs; each point is a run |
   | Designed experiment | `scipy.stats.qmc` (Latin hypercube, scrambled Sobol) | Already a dependency; SALib Morris for screening many inputs |
   | Sensitivity analysis | SALib (Sobol indices, Morris) | MIT; report confidence half-widths beside each index |
   | Optimization, one objective | Optuna TPE (as spec 2), and `scipy.optimize` (Nelder–Mead, COBYLA, SLSQP) for smooth deterministic models such as FMUs | Optuna already in use with the spec 1 seeding recipe |
   | Optimization, several objectives | pymoo NSGA-II | At 20,000 evaluations it reached IGD 0.0056 against Optuna's 0.057 |
   | Uncertainty study | `scipy.stats` distributions sampled with `scipy.stats.qmc` | Report the spread (percentiles) of each metric |

5. **Seeds from spec 1 streams.** Each library's seed is one draw from a reserved stream (as `<seed>:0:optimizer` for the spec 2 search), and evaluations run one at a time in the sampler's order, or in a pool whose result does not depend on the pool (as pymoo's `StarmapParallelization` did here). Optuna trials are never run in parallel.
6. **Benchmarks** for "Standard optimization test functions" use the published optima above: Branin 0.397887, Rosenbrock 0 at (1, 1), paraboloid −27.3333 at (20/3, −22/3), ZDT1 front f2 = 1 − √f1 with an IGD threshold, and the Ishigami Sobol indices. Tolerances from these trials: Ishigami S and ST within their confidence half-widths at N = 1024.

Open questions:

- **Blocking (a milestone and the spec's engine choice):** drop OpenMDAO and Dakota from spec 5 as proposed in 1 and 2? Recommended: yes.
- **Blocking (the model format):** where a study lives in the model file. Recommended: generalise spec 2's `search` block into a `study` block with a `kind` (`sweep`, `design`, `sensitivity`, `optimization`, `uncertainty`), so the existing search becomes one kind.
- **Reversible:** add pymoo (with moocore, LGPL-2.1-or-later, and matplotlib) and SALib (with pandas and matplotlib) as dependencies; record each in `docs/DECISIONS.md` with its licence. Optuna's `NSGAIISampler` would avoid pymoo at the cost of a worse front for the same number of runs.
- **Reversible:** for stochastic process models, every study works on the means over a set number of replications per evaluation, and reports their half-widths, as spec 2's search does.

## Tested

Scratch virtual environment: Python 3.12, openmdao 3.45.2, optuna 5.1.0, pymoo 0.6.2 (moocore 0.3.2), salib 1.6.0, scipy 1.18.1, numpy 2.5.5. Scripts in `docs/research/spec-5-trials/design-studies/`; each output file is the script's real output, redirected:

- `trial_openmdao.py` with `external_paraboloid.py` → `output_openmdao.txt`. Paraboloid by SLSQP in-process and through `ExternalCodeComp` matched the known minimum to 3.30e-13 in f; Rosenbrock by SLSQP with finite differences reached 6.73e-04 of (1, 1). The LHS DOE was not run (needs `pydoe`, not installed).
- `trial_optuna_pymoo.py` → `output_optuna_pymoo.txt`. Branin by Optuna TPE (3 seeds × 3 budgets, plus a repeat check), constrained Branin by Optuna and pymoo, ZDT1 by pymoo NSGA-II and Optuna `NSGAIISampler` with IGD against the published front.
- `trial_salib_qmc.py` → `output_salib_qmc.txt` (run with `-W error`). Ishigami Sobol and Morris; Latin hypercube, scrambled Sobol and plain Monte Carlo estimates of the mean and variance against the analytic values.
- `trial_same_interface.py` with `external_branin.py` → `output_same_interface.txt`. Six study types through one `evaluate` callable, in-process and as a separate process, with identical results; pymoo with four worker processes equal to serial.

Not run:

- **Dakota.** No Sandia Dakota on PyPI (the `dakota` package there is an unrelated 2013 placeholder); its binaries are installers built on RHEL, and conda, apt and running downloaded binaries are not allowed in this container. Nothing about Dakota here is from a run.
- OpenMDAO with MPI, OpenMDAO's pyOptSparse driver and its multi-objective use; Optuna parallel trials (the spec 2 note covers them); Ithax's own engines (SimPy, FMPy) inside a study, which needs the study layer to exist.
