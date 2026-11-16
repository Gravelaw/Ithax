# Spec 5 research: Combining engines (chaining and co-simulation)

## Question

Spec 5 "Combining engines" says "chaining first" and defers "stepping together" because it
"is harder to make stable". The research item asks for "published guidance on stability and
step-size control when engines run in step". This note answers:

1. What the literature and the FMI and SSP standards say about the stability of
   co-simulation master algorithms: Jacobi against Gauss-Seidel, zero-order hold, algebraic
   loops, step-size control, error estimation, energy-based methods, rollback.
2. How chaining (one run's output becomes another's input, offline, one way) differs from
   stepping together, and when chaining is sound.
3. What a chaining contract needs: what is passed, units, interpolation, cycle detection,
   provenance.
4. Which open tools already run FMUs in step, and their licences.
5. A small trial with scipy showing how the coupling error grows with the communication
   step.

## Finding

### Terms

- **Communication step (macro step) H.** The interval between two exchanges of values
  between engines. Each engine integrates on its own inside the step (FMI 2.0.4, ch. 4;
  FMI 3.0.1, §2.2.6).
- **Master (orchestrator, "co-simulation algorithm").** The code that advances time,
  exchanges values and decides H. FMI 2.0.4: "Note that the master algorithm itself is not
  part of the FMI standard." FMI 3.0.1: "The co-simulation algorithm itself is not part of
  the FMI standard. The co-simulation algorithm is responsible for: advancing the overall
  simulation time, exchange input and output data, triggering of input clocks, and handling
  events."
- **Jacobi.** All engines read the others' values at t = nH and step in parallel.
  **Gauss-Seidel** ("sequential or zig-zag"): engines step in an order, and a later engine
  uses the earlier one's value at t = (n+1)H; "more accurate, but hinders the
  parallelization potential" (Gomes et al., §4.3.2 preprint text).
- **Zero-order hold (constant extrapolation).** An input is held at its last exchanged
  value for the whole step.

### Stability and accuracy: what the sources say

- **Stability is a property of the coupled system and the scheme together.** The survey
  defines numerical stability of a co-simulation as the trace going to rest when the true
  system does, and checks it by the spectral radius of the one-step map (ρ < 1). Its own
  example (two-mass oscillator, Jacobi, constant extrapolation, H = 0.001) gives ρ = 0.9992
  (stable); with a coupling damping of 6.0E6 it gives ρ ≈ 76.43 (unstable) (Gomes et al.,
  §4.3.5).
- **Rules of thumb from the survey**, citing Arnold, Busch, Busch and Schweizer, Kübler and
  Schiehlen, Schweizer et al.: "Co-simulators that employ fixed point iteration techniques
  typically have better stability properties"; "Gauss-Seidel coupling approach has slightly
  better stability properties when the order in which the simulation units compute is
  appropriate. For example, the simulation unit with the highest mass should be computed
  first". Iterative techniques "require rollback functionalities which can be difficult to
  support" (Gomes et al., §4.3.5).
- **Algebraic loops decide whether the simple master is safe.** Kübler and Schiehlen (2000)
  report that zero-stability of non-iterative coupling is guaranteed only when there are no
  algebraic loops, and propose iterative coupling for the general case (abstract and zbMATH
  review read; full text paywalled, not read). Arnold, Clauß and Schierz (2013): "the
  global error is bounded in terms of local errors if there are no algebraic loops in the
  coupled system"; with loops the error bound "does in general not guarantee
  zero-stability" and there is "a risk of exponential instability unless an additional
  contractivity condition is satisfied". They give a sufficient structural test: the
  feed-through graph's adjacency matrix is nilpotent (their Example 1). The survey adds
  that "neglecting an algebraic loop can lead to a prohibitively high error" and that the
  better way is fixed-point iteration, repeating the step until convergence, which needs
  rollback when states are involved (§4.3.2).
- **FMI gives the master the information to find loops.** FMI 3.0.1 §2.2.11: output-to-input
  dependency data in `<ModelStructure>`; "If this data is not provided, the worst case must
  be assumed: all output variables depend algebraically on all input variables."
- **Input approximation.** Zero-order hold delays every input by up to H and makes inputs
  jump at each communication point; Busch (ZAMM 96(9), 2016) analyses stability of
  approximation methods and proposes "extrapolated interpolation" to remove the jumps
  (secondary description in the survey and search results; Busch's full text not read).
  FMI 2.0 offers `fmi2SetRealInputDerivatives` (`canInterpolateInputs`) and
  `fmi2GetRealOutputDerivatives` (`maxOutputDerivativeOrder`); FMI 3.0 keeps output
  derivatives (`fmi3GetOutputDerivatives`) and replaces input derivatives with Intermediate
  Update Mode (FMI 3.0.1 §1.1, §4.1.2).
- **Step-size control and error estimation.** Schierz, Arnold and Clauß (2012) and Arnold,
  Clauß and Schierz (2013) estimate the local error by Richardson extrapolation (two steps
  of H against one of 2H) and by a cheaper modified variant, and set
  H_opt = α·H·(1/ERR)^(1/P), with α in [0.8, 0.9] and P = k + 1 with direct feed-through,
  else k + 2 (k the extrapolation order). Richardson needs the FMU state to be saved and
  restored. The survey lists other estimators: multi-order input extrapolation, Milne's
  device, a parallel embedded method, and conservation laws (§4.3.4).
- **Rollback in the standard.** FMI 2.0 lists "the ability to repeat a rejected
  communication step ... with reduced communication step size" as a capability for
  sophisticated masters, through `fmi2GetFMUstate`/`fmi2SetFMUstate` when
  `canGetAndSetFMUstate` is true, and `canHandleVariableCommunicationStepSize`. FMI 3.0.1
  §2.2.7.4 gives the use: "For variable step-size control of co-simulation algorithms: get
  the FMU state for every accepted communication step; if the follow-up step is not
  accepted, restart co-simulation from this FMU state." Both are optional flags; an FMU
  that does not set them cannot be rolled back.
- **Energy-based, non-iterative control (ECCO).** Sadjina et al. (Engineering with
  Computers, 2016; arXiv 1602.06434) identify power bonds between subsystems, use the energy
  residual as the coupling-error estimate and adapt H with it; the abstract says the method
  is "non-iterative and only requires knowledge of the current coupling data" (no rollback),
  with error reductions of up to 93 % on a quarter-car benchmark. libcosim ships it
  (`EccoParams` in libcosimpy 0.0.6, citing Sadjina and Pedersen 2020).
- **Stabilised methods for algebraic constraints.** Schweizer and Lu (Multibody System
  Dynamics 2014; ZAMM 2015) propose semi-implicit predictor/corrector coupling with
  index-2 stabilisation or Baumgarte stabilisation (abstracts and a group slide deck only;
  full texts not read).
- **Events.** FMI 3.0.1: if a continuous input "deviates too much from the extrapolation
  polynomial", the master "must raise an event (if supported)". The survey notes that
  hybrid (event plus continuous) co-simulation can be unstable even when each mode is
  stable (§5.2.7), and that a standard for hybrid co-simulation is an open challenge.

### Chaining against stepping together

| | Chaining | Stepping together |
| --- | --- | --- |
| Time | Each run covers its whole horizon alone | All engines advance together, H at a time |
| Data | A finished run's results become inputs of the next | Values exchanged every H |
| Direction | One way: a directed acyclic graph of runs | Any, including feedback |
| Engine needs | None beyond the spec 1 adapter contract | doStep-like control, often state save/restore |
| Error source | Only the passed quantity (summary or sampled series and its interpolation) | Coupling error from H, extrapolation and loops; can be unstable |
| Numerical method in Ithax | None: the manager orders runs and copies values | A master algorithm with step control |

- **Chaining is sound without further analysis when the chain graph has no cycle.** Then
  the downstream run sees a fixed input, exactly as if the user typed it; its error is that
  of the upstream run plus the interpolation of a series. This follows from the
  definitions above (my reading; no source states it for Ithax's case).
- **Feedback across whole runs** (A feeds B, B feeds A) is waveform relaxation: repeat whole
  runs until the exchanged signals stop changing (Lelarasmee, Ruehli and
  Sangiovanni-Vincentelli 1982, cited in the survey; not read). It needs a convergence
  criterion, an iteration limit and a contraction condition that a general master cannot
  check in advance. Under guide rule 7 ("no code that ... iterates to convergence") this is
  a numerical method Ithax should not write. A cycle is therefore an error in Phase 2, not
  an invitation to iterate. A design-study driver (OpenMDAO's nonlinear solvers) could
  close such a loop later, as an engine feature, not Ithax code.
- **Scalar summaries remove time coupling altogether.** "A system model sets the cycle time
  used by a process model" (spec 5) passes one number: no interpolation, no step size, and
  the units are those of a setting.

### What a chaining contract needs

- **Link.** From `(model, run output)` to `(model, input setting)`. Output kinds: a scalar
  from `summary.json` (a metric mean, an optimum's objective or variable) or a time series
  from `tables/timeseries.parquet`.
- **Units.** Both ends carry a dimension; the loader checks they match and converts at load
  (CLAUDE.md: no unit strings past the model layer). A mismatch is an issue with a code.
- **Statistic for stochastic upstream runs.** Which value of a replicated output is passed:
  mean (default), a stated quantile, or one value per replication (paired, so replication i
  of the downstream run uses replication i of the upstream). Passing a mean hides spread;
  the result must say so.
- **Time series input.** Interpolation `linear` for continuous quantities, `hold` (previous
  value) for discrete ones; behaviour outside the recorded range (FMPy's `Input` holds the
  first and last values and treats repeated time stamps as an event, read in
  `fmpy/simulation.py` 0.3.32); a check that the series covers the downstream horizon, or an
  issue. Time bases must agree (start time, time unit).
- **Cycle detection.** The chain is a directed graph of models; a topological sort orders
  the runs and any cycle (including a self-loop) is a load issue naming the models in it.
- **Provenance.** The downstream run's `manifest.json` records, per chained input, the
  upstream run id, the upstream model file hash, the output name, the statistic, the value
  or the hash of the series file passed, and the interpolation. A re-run of the chain
  reruns upstream only when its model or settings changed (same rule as any cached run).
- **Fidelity label.** The chained result inherits the lowest fidelity label of its inputs
  (for example a surrogate upstream marks the downstream result as approximate).

### Open tools that run FMUs in step

| Tool | What it offers (as read) | Licence (where read, 2026-11-16) | AGPL-3.0 combined work |
| --- | --- | --- | --- |
| FMPy 0.3.32 (PyPI, 2026-09-09; pure-Python wheel `py3-none-any`, Python ≥ 3.10) | `fmpy.ssp.simulate_ssp`: fixed step, all FMUs step, then connections copied (Jacobi, zero-order hold); no step control, no rollback, no loop handling (read in `fmpy/ssp/simulation.py`) | BSD-2-Clause, `fmpy-0.3.32.dist-info/licenses/LICENSE.txt` in the wheel ("released under the 2-Clause BSD license"; the docs home page says BSD 3-clause) | Compatible; in-process import fine |
| libcosim via libcosimpy 0.0.6 (PyPI, 2026-06-30; manylinux_2_28 x86-64 and win-amd64 wheels; Python 3.11 to 3.14) | Fixed-step and ECCO (energy-based adaptive) algorithms; loads SSP and OSP config files (`CosimExecution.from_ssp_file`, `CosimAlgorithm.create_ecco_algorithm`) | MPL-2.0, `libcosimpy-0.0.6.dist-info/licenses/LICENSE` in the wheel; libcosim's own LICENSE (MPL-2.0) read from raw.githubusercontent.com. MPL-2.0 §1.12 names AGPL-3.0 as a "Secondary License" | Compatible (file-level copyleft); in-process import fine. The 20 MB `libcosimc.so` bundles third-party code whose licences are not in the wheel: not checked |
| OMSimulator 3.0.0.post198 (PyPI, 2026-10-07; sdist only) | Fixed and variable step settings, SSP (docs table of contents only; solver details not read) | OSMC-PL 1.8 with AGPL-3.0 as an option for any party, `OSMC-License.txt` in the sdist | AGPL-3.0 option is compatible. The sdist's `build_helpers.py` downloads nightly binaries from build.openmodelica.org with `requests.get(url, verify=False)` (TLS check off); not installed for that reason |
| Maestro (INTO-CPS) 4.0.0 (Maven Central, 2025-03-27; Java) | FMI 2.0 co-simulation orchestration engine (docs) | "INTO-CPS Association Public License" in `root-4.0.0.pom`; that licence (read from raw.githubusercontent.com) is GPL-3.0 for any party, EPL-based modes for members | GPL-3.0 is compatible with AGPL-3.0; Java runtime needed, so a separate process |
| DACCOSIM NG (EDF; Java, JavaFMI) | Distributed co-simulation (survey and search results) | Not read: EDF page answered 403, Bitbucket 404. Search snippets conflict (older papers AGPL, newer EDF text LGPL-3.0) | Unknown |

None of these was run: running an FMU master needs FMUs, and FMU export is the separate
research item "OpenModelica export".

### Is a co-simulation master a "numerical solver" under rule 7?

- A fixed-step Jacobi or Gauss-Seidel master with zero-order hold does no integration
  itself; it calls `doStep` and copies values. It still decides the numerical method of the
  coupled system: the trial below shows the Jacobi choice alone adds energy and diverges.
- A master with step-size control (error estimate, step rejection, H_opt formula) or with
  fixed-point iteration over algebraic loops is a time-integration method for the coupled
  system. Rule 7 forbids "code that integrates differential equations ... or iterates to
  convergence"; this is that. Ithax should wrap a master (libcosim first: MPL-2.0, Python
  wheel, ECCO and SSP built in), not write one.

### Trial result (summary; full output in `spec-5-trials/cosimulation/output.txt`)

Undamped two-mass oscillator, all constants 1, x1(0) = 1, run to t = 50. Monolithic
`solve_ivp` (DOP853) against the analytic normal-mode solution: max |x1 error| 2.025e-12,
energy at t = 50 = 1.000000000000.

| H | Jacobi max \|x1 err\| | Jacobi energy at 50 (exact 1) | Jacobi growth per step | Gauss-Seidel max \|x1 err\| | Gauss-Seidel energy at 50 |
| --- | --- | --- | --- | --- | --- |
| 0.001 | 1.178e-02 | 1.0128 | 1.000000250 | 3.946e-04 | 1.0000 |
| 0.01 | 1.181e-01 | 1.1580 | 1.000024999 | 4.023e-03 | 1.0000 |
| 0.05 | 6.232e-01 | 2.6927 | 1.000624545 | 2.217e-02 | 1.0000 |
| 0.1 | 1.466e+00 | 9.0996 | 1.002492729 | 4.985e-02 | 1.0000 |
| 0.2 | 5.348e+00 | 1.0207e+02 | 1.009884658 | 1.245e-01 | 1.0000 |
| 0.5 | 1.447e+02 | 6.2526e+04 | 1.058242742 | 5.077e-01 | 1.0000 |
| 1.0 | 2.674e+03 | 4.0132e+07 | 1.192488219 | 1.180e+00 | 1.0000 |

- Jacobi with zero-order hold has a growth factor above 1 at every H tried, so on this
  undamped system it gains energy at any step size; the error is about 1e-2 even at
  H = 0.001 and the run blows up from H ≈ 0.2.
- Gauss-Seidel kept the energy at 1.0000 (four digits printed) with growth factor
  1.000000000 at every H, and its error grew roughly in proportion to H (first order). It
  is bounded but still wrong in phase: 1.18 error at H = 1.
- The ordering of engines, a choice a user would never see, changed the answer by up to
  three orders of magnitude. This supports deferring stepping together until it can be
  delegated to a tool with error control.

## Sources

All read on 2026-11-16 unless marked "not read".

- C. Gomes, C. Thule, D. Broman, P. G. Larsen, H. Vangheluwe, "Co-simulation: State of the
  art", arXiv:1702.00686v1 (2017), PDF downloaded from https://arxiv.org/pdf/1702.00686 and
  read for §4.3.2, §4.3.4, §4.3.5, §5.2.7. Published as "Co-simulation: a survey", ACM
  Computing Surveys 51(3), article 49, 2018, doi:10.1145/3179993 (published version not
  read; section numbers above are the preprint's).
- Modelica Association, "Functional Mock-up Interface for Model Exchange and
  Co-Simulation", version 2.0.4, 2022-11-10, PDF from
  https://github.com/modelica/fmi-standard/releases/download/v2.0.4/FMI-Specification-2.0.4.pdf
  (the release download answered; text extracted with pypdf 5.1.0).
- Modelica Association, FMI 3.0.1, https://fmi-standard.org/docs/3.0.1/ (§1.1, §1.2,
  §2.2.6, §2.2.7.4, §2.2.8, §2.2.11, §4.1.2).
- T. Schierz, M. Arnold, C. Clauß, "Co-simulation with communication step size control in
  an FMI compatible master algorithm", 9th Modelica Conference, 2012,
  doi:10.3384/ecp12076205,
  https://2012.international.conference.modelica.org/proceedings/html/pdf/ecp12076205_SchierzArnoldClauss.pdf
- M. Arnold, C. Clauß, T. Schierz, "Error analysis and error estimates for co-simulation in
  FMI for Model Exchange and Co-Simulation V2.0", Archive of Mechanical Engineering 60(1),
  75-94, 2013, doi:10.2478/meceng-2013-0005, https://journals.pan.pl//Content/84687/PDF/05_paper.pdf
  (7 of 20 pages failed text extraction; the parts quoted were extracted).
- R. Kübler, W. Schiehlen, "Two methods of simulator coupling", Mathematical and Computer
  Modelling of Dynamical Systems 6(2), 93-113, 2000: abstract via search results and
  https://ideas.repec.org/a/taf/nmcmxx/v6y2000i2p93-113.html; full text not read
  (paywalled).
- M. Busch, "Continuous approximation techniques for co-simulation methods: Analysis of
  numerical stability and local error", ZAMM 96(9), 1061-1081, 2016,
  doi:10.1002/zamm.201500196: bibliographic data and secondary descriptions only; not read.
- B. Schweizer, D. Lu, stabilised index-2 and predictor/corrector co-simulation papers
  (Multibody System Dynamics 2014; ZAMM 2015): abstracts and
  https://www.ad.tu-darmstadt.de/media/ad/dokumenten/forschungsthemen_ad/F_cosim2.pdf via
  search results; full texts not read.
- S. Sadjina, L. T. Kyllingstad, E. Pedersen, S. Skjong, "Energy conservation and power
  bonds in co-simulations: non-iterative adaptive step size control and error estimation",
  Engineering with Computers, 2016, doi:10.1007/s00366-016-0492-8,
  https://arxiv.org/abs/1602.06434 (abstract read).
- SSP standard home page, https://ssp-standard.org/ (SSP 2.0.1, 2026-05-05, per the page;
  the standard text itself not read).
- FMPy docs, https://fmpy.readthedocs.io/en/latest/; wheel `fmpy-0.3.32-py3-none-any.whl`
  (licence file, `fmpy/ssp/simulation.py`, `fmpy/simulation.py`); PyPI JSON
  https://pypi.org/pypi/fmpy/json.
- libcosimpy wheel `libcosimpy-0.0.6-cp312-cp312-manylinux_2_28_x86_64.whl` (licence,
  `CosimAlgorithm.py`, `CosimExecution.py`); PyPI JSON; libcosim LICENSE at
  https://raw.githubusercontent.com/open-simulation-platform/libcosim/master/LICENSE
- OMSimulator sdist `omsimulator-3.0.0.post198.tar.gz` (`OSMC-License.txt`,
  `build_helpers.py`, `README.md`); PyPI JSON; user guide contents page
  https://openmodelica.org/doc/OMSimulator/master/OMSimulator/UsersGuide/html/
- Maestro: https://into-cps-maestro.readthedocs.io/ (via search results);
  https://repo1.maven.org/maven2/org/into-cps/maestro/root/4.0.0/root-4.0.0.pom;
  licence text
  https://raw.githubusercontent.com/INTO-CPS-Association/INTO-CPS-Association.github.io/master/LICENSE
- DACCOSIM NG: search results only (EDF and Bitbucket pages not reachable); licence not
  read.

## Decision

Proposed defaults for spec 5 "Combining engines" (owner to confirm):

1. **Phase 2 builds chaining only.** A chain is a directed acyclic graph of models in one
   file; the manager runs them in topological order, each as an ordinary run, and passes
   values. No engine needs new adapter methods.
2. **What may be passed:** a scalar from an upstream `summary.json` (with a stated statistic
   for replicated runs: `mean` by default, or a quantile, or `paired` per replication) or a
   time series from `timeseries.parquet` with interpolation `linear` or `hold` and an issue
   when the series does not cover the downstream horizon. Units are checked and converted
   at load.
3. **A cycle in the chain graph is a load issue** (with a code, naming the models). Ithax
   does not iterate whole runs to a fixed point: that is a convergence iteration under rule
   7.
4. **Provenance** of every chained input goes in the downstream `manifest.json` (upstream
   run id, model hash, output, statistic, value or series hash, interpolation); the fidelity
   label is the lowest of the inputs.
5. **Stepping together stays deferred.** Ithax does not write a co-simulation master: a
   master with step control, rollback or loop iteration is a numerical solver under rule
   7, and even a fixed-step one chooses a coupling method whose error the user cannot see.
   When it starts, it wraps a tool: libcosim through libcosimpy (MPL-2.0, Python wheels for
   Linux, fixed-step and ECCO, SSP input) as first candidate; OMSimulator (AGPL-3.0 option)
   as second, run as a separate process.
6. **Conditions to start stepping together:** (a) chaining has passed its acceptance row;
   (b) the FMU export research item shows FMUs with co-simulation and, ideally,
   `canGetAndSetFMUstate`; (c) the wrapped tool reproduces this note's two-mass benchmark
   (analytic answer above) within a stated tolerance at a stated step, and reports its
   error estimate; (d) the model's coupling has no algebraic loop by the FMU dependency
   data (FMI 3.0.1 §2.2.11), or the tool handles loops; (e) every co-simulated result
   carries the communication step and the coupling method in its manifest and a fidelity
   label.
7. **Benchmark to add** for stepping together: the undamped two-mass oscillator of the trial
   (normal-mode analytic answer; energy conserved = 1).

Open questions:

- Blocking:
  - Whether a chain is one model file holding several models or a separate chain file
    referring to model files (model format; spec 1).
  - Whether `/v1` exposes a chain run as one run or as a group of runs (API; spec 3).
  - Whether libcosimpy (a native 20 MB library bundling unlisted third-party code) may be
    imported into the service process, or must run as a separate process (engine licence
    rule; owner decision F4).
- Reversible:
  - Default statistic for a replicated upstream (proposed `mean`).
  - Default interpolation (proposed `linear` for continuous, `hold` for discrete).
  - Whether a stale upstream run is reused or rerun (proposed: reuse when model hash and
    settings match).

## Tested

- Run: `docs/research/spec-5-trials/cosimulation/trial_jacobi_zoh.py` with Python 3.12,
  scipy 1.14.1, numpy 2.1.3 in a scratch virtual environment; output stored in
  `docs/research/spec-5-trials/cosimulation/output.txt`. Each subsystem is integrated by
  `scipy.integrate.solve_ivp` (RK45, rtol 1e-10, atol 1e-12); the script only exchanges
  values every H. The growth factor is the spectral radius of the one-step map, built by
  running one master step from each unit vector.
- Compared with the known answer: monolithic `solve_ivp` against the analytic normal-mode
  solution agreed to 2.025e-12 (max |x1 error|) with energy 1.000000000000 at t = 50. The
  coupled results are compared with the analytic solution in the table above.
- Ruff and mypy were not run on the trial script: the repository has no `.venv` in this
  container and the brief forbids installing into it.
- Not run: any FMU master (FMPy `simulate_ssp`, libcosimpy, OMSimulator, Maestro,
  DACCOSIM), because no co-simulation FMUs exist yet (FMU export is a separate research
  item); OMSimulator also because its install downloads binaries with TLS verification
  off. Whole-run fixed-point iteration (waveform relaxation) was not tried, as the
  decision above rules it out. The full texts of Kübler and Schiehlen, Busch, and Schweizer
  and Lu were not read.
