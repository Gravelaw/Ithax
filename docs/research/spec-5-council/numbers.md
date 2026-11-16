# Council review, spec 5 v0.3: correctness of the numbers

Reviewer lens: numbers. Branch `docs/spec-5-v0.3`, file `docs/specs/5-systems-and-design.md`.
Method: every closed form recomputed independently (my own script, `.venv/bin/python`, scipy:
Lambert W and a `solve_ivp` run at rtol 1e-12 for SIR, my own Euler loops for the PySD
rows, `ellipk(m = k²)` for the pendulum, analytic Ishigami variances, Branin at all three
minima, Crawford unit form, NIOSH multipliers by formula, `weibull_min.fit` on
`CensoredData`). Every pass rule then checked against the trial output it cites.

**Numbers checked: about 115.** All closed-form "Known answer" values in the Benchmarks
table are correct to every printed digit: SIR 797.154100 / 153.926660 and 800.203968; LV
V = −3.813315552; x(10 s) = 0.079116024 m (ζ = 0.1), damped period 3.157419417 s; pendulum
2.010235893 s and 2.368246346 s; Branin 0.397887; Ishigami S1 0.3139, 0.4424, 0 and ST
0.5576, 0.4424, 0.2437; RBD 0.8208 and 0.9720; fault tree 0.027005725; learning curve
(all ten); NIOSH formula values 16.03, 14.31, 34.93, 24.68; SPAR-H 0.8016 and 6.4060e-5;
Weibull (my scipy fit: η 606.52757, β 1.72080). Every "trial:" figure quoted in the table
is copied correctly from its output file. My Euler reruns reproduce PySD's +0.2171 /
+0.1434 (SIR, step 1/64) and 2.85e-4 (LV, step 1e-4) exactly. The findings below are
about pass rules, parameters, and traceability.

## Errors

### N1. Physical: the default solver tolerance has no trial behind it, and the trial cited ran a different FMU type at a tighter tolerance
- Location: "Physical systems", Engine: "`tolerance` (default 1e-6) for the FMU's CVODE";
  Benchmarks, mass–spring–damper: "within 1e-5 m over 10 s (FMPy trial: 8.63e-7)".
- What is wrong: the FMPy trial ran a hand-written **Model Exchange** FMU (`msd.c`
  `fmi2DoStep` returns `fmi2Error`) with FMPy's CVODE at **relative_tolerance 1e-8**. The
  spec specifies a **Co-Simulation** FMU from OpenModelica with a default tolerance of
  **1e-6**. No note or output gives 1e-6. So the 8.63e-7 result says nothing about whether
  the 1e-5 m rule passes at the spec's default. With rtol 1e-6 the error is plausibly about
  100 times larger, close to the gate.
- Evidence: `spec-5-trials/fmpy/trial_msd.py:57` `fmi_type="ModelExchange"`, `:62`
  `relative_tolerance=1e-8`; `spec-5-fmpy.md:40` "at a relative tolerance of 1e-8";
  grep for `1e-6` in `spec-5-fmpy.md` and `spec-5-openmodelica-fmu.md` finds nothing.
- Fix: write "(FMPy trial, Model Exchange FMU, rtol 1e-8: 8.63e-7)". Either set the
  benchmark's tolerance to 1e-8 in its Inputs, or add to "Open until" that the 1e-5 m gate
  must be shown at the default tolerance with the OpenModelica CS FMU. Cite a source for the
  1e-6 default, or mark it as a reading.

### N2. Predator and prey: the benchmark's time unit is one the spec does not allow
- Location: Benchmarks, "Predator and prey": "α 1, β 0.1, γ 1.5, δ 0.075 per year … step
  0.0001, 15 years"; System dynamics, Experiment: "`time_unit` (one of `s`, `min`, `h`,
  `d`; rates are per that unit)"; Units: "The time units are spec 1's (`s`, `min`, `h`,
  `d`)".
- What is wrong: a model file cannot state this benchmark as written, because years are
  not an allowed time unit. Restated in days, the step would be 0.0365 d and the length
  5478.75 d, with rates per day of 1/365.25 and so on. Whether the drift then stays below
  1e-3 depends on the per-day step; the trial step of 1e-4 year equals 0.0365 d.
- Evidence: spec lines 76 and 183; `pysd/predator_prey.mdl` uses dimensionless time.
- Fix: restate the row in `d` (rates ÷ 365 or 365.25, step 0.0365 d, length 5475 d, so
  that the step in units of model time is unchanged and the trial still applies). Or add
  `year` to the time units, which changes spec 1, so it is an owner decision.

### N3. SPAR-H is marked Specified, but its benchmark value depends on an open owner question
- Location: People (d), "**SPAR-H (Specified):** … test: section 2.5.1's example 2
  (6.41E-5)"; Benchmarks "SPAR-H, example 2 | 6.41E-5 | three significant figures".
- What is wrong: example 2 has no negative PSFs (0.8, 0.8, 0.1). 6.41E-5 comes only from
  applying the adjustment formula anyway (6.4060e-5). The worksheets' rule applies the
  adjustment only with three or more negative PSFs, and under that rule the answer is
  6.400e-5, which **fails** "three significant figures" against 6.41E-5. The research note
  lists exactly this as an open owner question that changes a user-visible answer.
- Evidence: `people-hra/output.txt` line 3 (unadjusted 6.400e-05, adjusted 6.4060e-05);
  `spec-5-people-methods.md:197-198` (open question); NUREG rule at
  `spec-5-people-methods.md:96`.
- Fix: mark SPAR-H Open until the owner answers, or state the reading ("adjustment applied
  whenever …") in the calculator and in `docs/DECISIONS.md`. Make the benchmark value follow
  that reading: 6.41E-5 if the adjustment is always applied, 6.40E-5 if not.

## Inconsistencies

### N4. SPAR-H example 1 is called a test, but the benchmark table has no row or pass rule for it, and the shared rule would fail
- Location: People (d): "test: section 2.5.1's example 2 (6.41E-5) and example 1, which
  prints 0.81 where the formula gives 0.8016"; the Benchmarks row lists example 2 only.
- What is wrong: if example 1 is held to the table's "three significant figures" rule
  against the printed 0.81, it fails (0.802). The expected value and the rule are not given.
- Fix: add example 1 with expected 0.8016 (the formula) and the rule "three significant
  figures against the formula; the printed 0.81 is recorded as a rounding in the source".

### N5. Rosenbrock has a known answer but no pass rule, and no trial with a proposed library
- Location: Benchmarks, "Test functions": known "0 at (1, 1)"; the pass rule covers only
  Branin and ZDT1.
- What is wrong: no gate is defined for it. Its only trial was OpenMDAO SLSQP
  (|x − x*| = 6.73e-4, f = 9.05e-8), and the spec drops OpenMDAO.
- Evidence: `design-studies/output_openmdao.txt` line 6; `spec-5-design-studies.md:64`.
- Fix: run Rosenbrock with `scipy.optimize` Nelder–Mead from (−1.2, 1) and set a rule from
  that run (for example f < 1e-6 and |x − (1, 1)| < 1e-3), or remove Rosenbrock from the
  row.

### N6. The test-function pass rules do not name the library, and one library the spec offers would fail ZDT1
- Location: Benchmarks, "Branin within 0.01 at 200 evaluations; ZDT1 IGD below 0.01 at
  20,000".
- What is wrong: the ZDT1 rule holds for pymoo NSGA-II with population 100 (0.00555 and
  0.00564). Optuna `NSGAIISampler` at 20,000 trials gave 0.05699 and would fail. The Branin
  rule holds for Optuna TPE at 200 trials (gaps 1.26e-3 to 1.84e-3, three seeds) but fails
  at 50 or 100 for some seeds (up to 3.73e-2). "Within 0.01" does not say absolute or
  relative; it reads as absolute, which is what the trial shows.
- Evidence: `design-studies/output_optuna_pymoo.txt` lines 3–24.
- Fix: write "Branin, Optuna TPE, 200 trials, seed s: best − 0.397887 < 0.01 (absolute)"
  and "ZDT1, pymoo NSGA-II, population 100, 200 generations: IGD against 1,001 front points
  < 0.01".

### N7. The agent SIR gate has a sizeable built-in chance of failing on a new seed or library version
- Location: Benchmarks, "SIR final size, agents … inside the 95% interval of the mean
  (trial: 796.03 ± 9.18)".
- What is wrong: a finite-N, discrete-step stochastic model is not unbiased for the
  deterministic final size. The trial mean is 4.17 below it, about 0.93 standard errors
  (s = 24.59, SE = 4.49; the half-width 2.045 × 4.49 = 9.18 checks). If that bias is real,
  a fresh 30-replication run fails the gate with probability of roughly
  P(|Z − 0.93| > 1.96) ≈ 15%. A numpy or Mesa upgrade re-draws the streams, so the gate
  would fail about one upgrade in seven (CLAUDE.md "Things the code does not show").
- Evidence: `mesa/output.txt` line 3. `trial_mesa.py:15` itself says "A stochastic model of
  finite N is not expected to equal it exactly".
- Fix: either gate on 3 half-widths (three_se, as spec 2's failure benchmark does), or
  raise to 100 replications and gate on |mean − 800.20| < 2 % of N plus the half-width.
  Record the trial's bias in the row.

### N8. The Ishigami gate is six simultaneous 95% tests
- Location: Benchmarks, "Ishigami … each within its confidence half-width" (N 1024).
- What is wrong: six bootstrap 95% intervals, all required to cover. On a new seed the chance
  that at least one misses is about 1 − 0.95⁶ ≈ 26% if the six were independent; they are
  correlated, but the risk stays well above 5%. The trial passed, with x1's S1 at 0.0051
  against a half-width of 0.0578.
- Evidence: `design-studies/output_salib_qmc.txt` lines 3–6.
- Fix: gate each index within 2 × its half-width, or within max(half-width, 0.02)
  absolute. Also state `calc_second_order=False` (5,120 evaluations), as the trial ran it.

### N9. The SPAR-H, NIOSH and RBD rows rest on numbers chosen or derived in the trial, while the published worked example sits unused
- Location: Benchmarks, "Series and parallel block diagram … 0.8208; 0.9720 | NIST 8.1.8;
  Rausand ch. 4" and "Fault tree … q 0.05, 0.01, 0.10 … exact 0.027005725".
- What is wrong: rule 6 (CLAUDE.md) asks a calculator to cite a formula **and a published
  worked example**. The note records that NIST 8.1.8 gives "formulas only, no numbers".
  The RBD reliabilities and the fault-tree probabilities were chosen by the trial
  (`fault_tree.py` docstring: "Basic event probabilities are chosen here"). So both "Known
  answers" are our own closed forms, while the Source column reads as if the numbers came
  from the sources. A published number exists and was reproduced: Rausand Example 4.9,
  MTTF of a 1oo2 with λ = 0.001 is 1500 (`output-rbd.txt` line 6). The spec's block-diagram
  calculator also covers MTTF/MTTR availability, which has no benchmark row; the trial has
  A = 0.8, 1oo2 0.96, series 0.64.
- Fix: add "MTTF 1oo2, λ 0.001 → 1500 (Rausand Example 4.9)" and "MTTF 2oo3 → 833.333…" to
  the RBD row, and an availability case. In the Source column, say "formula: NIST 8.1.8;
  values chosen" for 0.8208 and 0.9720, and "structure and cut sets: Lundteigen and Rausand;
  probabilities chosen" for the fault tree.

### N10. Fidelity-label examples use steps or lengths that do not match the benchmarks
- Location: Model file, Results: "Standard: Euler, step 0.0625 d, 200 d" (system dynamics)
  and "Standard: RK4, step 1 ms, 10 s" (multibody).
- What is wrong: at step 0.0625 d the SIR benchmark misses its gate (final size error
  +0.8708 > 0.5, peak +0.5747 > 0.25; `pysd/output.txt` line 4). A reader will take the
  example as the recommended setting. The pendulum trial measures 10 periods from 11 upward
  zero crossings, which takes about 22 s (10°) to 26 s (90°), not 10 s
  (`mujoco/trial_pendulum.py:13,42`).
- Fix: use "step 0.015625 d" (the benchmark's 1/64 d) in the SD example. Use the length the
  pendulum benchmark needs (for example 30 s) in the multibody example, and state the
  pendulum benchmark's `time_step` (1 ms, RK4) and length in its Inputs, which now give
  neither.

### N11. Pendulum "point mass" conflicts with the `body` schema
- Location: Benchmarks pendulum "point mass"; Multibody `body`: "`inertia` (three kg·m²
  values about the centre of mass)".
- What is wrong: the trial used `diaginertia="1e-12 1e-12 1e-12"`, not zero
  (`mujoco/trial_pendulum.py:29`). The spec does not say whether zero inertia is allowed.
  If it is not, the benchmark input is 1e-12; if it is, the adapter must handle it.
- Fix: state the benchmark inertia as (1e-12, 1e-12, 1e-12) kg·m², or state that the
  inertia values must be ≥ 0 and what the adapter writes for 0.

## Suggestions

### N12. The JuPedSim flow ranges omit the door widths and the jams
- Location: People (b): "door flows were 0.979 to 1.185 … and 1.616 to 1.839 with a time
  gap of 0.5 s".
- What is wrong: these ranges cover doors of 1.0 to 2.0 m only. At 0.8 m the default model
  jammed (11 of 150 out) and the 0.5 s time gap gave 1.294 over the 73 who left
  (`people-jupedsim/output.txt` lines 3 and 8).
- Fix: add "doors 1.0 to 2.0 m; a 0.8 m door jammed".

### N13. The NIOSH 2% tolerance leaves a thin margin
- Location: People (d), NIOSH "within 2%".
- What is wrong: my formula values give −1.65%, −1.32%, −0.48% and +0.33% against the
  printed values, so the tightest case clears the gate by 0.35 points. The spec also does
  not say which load constant applies after metric inputs are converted. The note says
  23 kg ≠ 51 lb (0.6% apart), which on its own would push origin to about −2.2% if metric
  constants were used against the printed US values.
- Fix: say that the benchmark uses the US constants (LC 51 lb) after conversion, and that
  metric-unit tasks use LC 23 kg with their own expected values.

### N14. Smaller points on the surrogate numbers
- "The trial found the true error up to 2.1 times the leave-one-out estimate" is correct
  (1/0.468, Borehole 160), but at the two benchmark sizes the worst was 1.65× (Branin 40,
  1/0.6051) and 1.29× (Borehole 80, 1/0.7739). The 2.5× gate is therefore loose but
  consistent. All the other surrogate thresholds are looser than the trial's worst of ten,
  as claimed (Q² 0.999 and 0.9998; nRMSE 0.002565; coverage 0.995 and 0.919).
- The ">5% of standardised LOO residuals beyond ±3" warning fires on any single residual
  when n < 20. With the minimum budget for d = 2 (10 runs) the trial shows it would fire on
  about half of the designs (Branin n = 10, loo_out3 median 0.5). This may be intended;
  say so.
- The acceptance row's "same predictions to 1e-9 of the output range" on another machine
  was not measured. The trial is same-machine bit-identical only. E431's "does not
  reproduce its stored validation numbers" needs a tolerance, or BLAS differences on the low
  tier will refuse valid files.

### N15. Trial-script housekeeping
- `benchmarks/expected_values.py` docstring says "scipy 1.16 … used" but `output.txt`
  line 1 says `scipy 1.18.1`. It also cites `docs/research/spec-5-benchmarks.md`, which
  does not exist.
- The Predator-and-prey rule "relative drift below 1e-3" should say "maximum over the
  run", which is what the trial measured (`pysd/output.txt`: "max relative drift over 15
  years").
- Benchmark "SIR final size and peak" "within 0.5 and 0.25 persons": the trial is +0.2171
  and +0.1434. The gate passes; the Euler error at this step is positive, so a one-sided
  note would help readers who see the agent row's negative bias.
