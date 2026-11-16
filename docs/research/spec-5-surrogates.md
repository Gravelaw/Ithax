# Spec 5 research: Surrogate methods for few training runs, and honest error reporting

## Question

Spec 5 "Surrogate models" says a surrogate is built from a designed experiment, runs on the
processor by default (Gaussian process and gradient-boosted trees), always shows its
validation error and is marked as approximate, and is portable: "a surrogate trained on a
workstation is saved in the project and runs on a low-tier laptop". Its benchmark is
"Surrogate of a known function: error below a set threshold on held-out points", with no
threshold. The research item asks which methods work with few training runs and how to
report their error honestly. This note answers:

1. Literature: which methods work with few runs; rules of thumb for the number of runs;
   stochastic simulation outputs (noise, stochastic kriging); how to validate (k-fold and
   leave-one-out cross-validation, held-out sets, Q², standardised LOO residuals, coverage
   of predictive intervals); extrapolation outside the training box.
2. Libraries: scikit-learn, SMT, GPyTorch/BoTorch, XGBoost/LightGBM; licences read at
   pinned versions, upkeep, Linux and WSL 2 install, CPU only; how to save a trained model
   so it runs on another machine (pickle, skops, ONNX, or the runs plus hyperparameters).
3. Trial: Branin (d = 2) and Borehole (d = 8) with n = 5d, 10d and 20d Latin hypercube
   runs; a Gaussian process and gradient-boosted trees; error on 1,000 held-out points
   against the cross-validation estimate; coverage of the GP's 95 % intervals; a noisy
   case; refit determinism; saved size.
4. What spec 5 should say: default method, minimum runs, the error shown to the user, the
   label, portable and safe storage, and a benchmark threshold set from the trial.

## Finding

### 1. Literature

**Number of runs.** Loeppky, Sacks and Welch (2009) give "reasons and evidence supporting
the informal rule that the number of runs for an effective initial computer experiment
should be about 10 times the input dimension". They measure accuracy by leave-one-out
cross-validation, normalised by the range of the outputs (`e_avg`, the LOO RMSE divided by
the range, and `e_max`, the largest LOO error divided by the range), and "typically take
e_avg < 0.1 as the target for a 'useful' approximation". Their findings, read in the paper:

- n = 10d "will provide reasonable prediction accuracy for 'tractable' functions and are
  sufficient to diagnose more difficult problems"; "unless a huge sample size is
  available, more than n = 10d runs would be wasteful".
- Difficulty is the total sensitivity τ = Σθⱼ of the GP correlation parameters (inputs on
  [0, 1]): τ below about 10 is tractable with 10d runs for d up to 20; if sensitivity is
  spread equally over all inputs, even τ = 10 gives poor accuracy for d > 5.
- With d₀ active inputs out of d, "choosing n = 10d₀ is a useful complement".
- They "did not consider d < 4". The rule is not tested for Branin's d = 2.
- In their G-protein example, LOO and 120 new test points gave the same picture; "the use
  of new test data is a luxury", so in practice one relies on cross-validation.

Jones, Schonlau and Welch (1998, the EGO paper) introduced the rule ("about n = 10k points
are needed in the initial design"; k is the number of inputs) and fitted Branin and
Goldstein–Price from a 21-point Latin hypercube design.

**Validation.**

- *Q², the predictivity coefficient.* Marrel, Iooss, Van Dorpe and Volkova (2008):
  Q² = 1 − Σ(yᵢ − ŷᵢ)² / Σ(ȳ − yᵢ)² over a test sample or K-fold cross-validation; "the
  classical coefficient of determination R² for a test sample, i.e. for prediction
  residuals". Training-set residuals cannot be used because a GP without a nugget
  interpolates its runs.
- *Standardised cross-validated residuals.* Jones et al. (1998): (y(xᵢ) − ŷ₋ᵢ(xᵢ)) /
  s₋ᵢ(xᵢ); "if the model is valid, the value should be roughly in the interval [−3, +3]".
  In practice they keep the hyperparameters estimated from all runs and only drop the run
  from the predictor, since dropping one run "usually has a negligible effect on the
  maximum likelihood estimates". They also plot the residuals against normal quantiles,
  and try a log or −1/y transform when they are poor.
- *Correlated validation data.* Bastos and O'Hagan (2009) note that "emulator predictions
  are not independent" and give diagnostics over a validation set that take the
  correlation into account: the Mahalanobis distance and pivoted Cholesky errors (read
  in the paper, sections 3.3 and following; not tried here).

**Stochastic simulation outputs.** Ankenman, Nelson and Staum (WSC 2008, journal version
Operations Research 58(2), 2010; the conference paper was read) separate *intrinsic*
uncertainty, the simulation noise εⱼ(x) whose variance V(x) may change with x, from
*extrinsic* uncertainty about the unknown surface M(x). A design is a set of pairs
(xᵢ, nᵢ), with nᵢ replications at xᵢ. The model is fitted to the replication means,
with V(xᵢ)/nᵢ estimated from the sample variance of the replications. "Intrinsic
uncertainty inflates MSE" everywhere, not only at the runs. A plain nugget (one noise
level for all x) is the special case of constant V. scikit-learn supports both forms:
`WhiteKernel` estimates one noise level, and `alpha` accepts "an array ... used as
datapoint-dependent noise level" (GaussianProcessRegressor 1.9.1 documentation). In
scikit-learn 1.9.1 `alpha` is added after `normalize_y` has scaled y (source read,
`_gpr.py` lines 275 to 350), so a per-point variance must be divided by the variance of y.

**Extrapolation.** Gramacy (2020, *Surrogates*, section 5.1.1): far from the data a GP
"is mean-reverting", and its "variance won't continue to increase" past a point. Trees
predict a constant outside the range of their training splits. A surrogate should
therefore never answer outside its training box without saying so.

**Methods for few runs.** The sources read treat the GP (kriging) as the standard
emulator for tens to hundreds of deterministic runs. SMT 2.15.1 also offers least squares,
second-order polynomials, radial basis functions, inverse-distance weighting, tensor-
product splines, polynomial chaos expansion (PCE and sparse PCE) and a small neural net
(GENN) (SMT surrogate-model list, read 2026-11-16). Polynomial chaos and RBF were not
compared in the trial; the PCE literature was not read for this note. The trial shows how
trees behave with few runs (below).

### 2. Libraries (licences read 2026-11-16)

Each licence was read from the file inside the wheel downloaded with `pip download
--no-deps` at the version shown (manylinux x86-64 wheel, or `py3-none-any`). Release data
from the PyPI JSON API on 2026-11-16.

| Package | Version | File read | SPDX | Import into the service? |
| --- | --- | --- | --- | --- |
| scikit-learn | 1.9.1 | `scikit_learn-1.9.1.dist-info/licenses/COPYING` (BSD 3-Clause; the file also lists the bundled GCC runtime `libgomp`, GPL-3.0 with the GCC Runtime Library Exception 3.1) | BSD-3-Clause | yes, compatible |
| smt | 2.15.1 | `smt-2.15.1.dist-info/licenses/LICENSE.txt` | BSD-3-Clause | yes; its dependencies pydoe 1.6.0 (BSD-3-Clause, PyPI metadata) and jenn 2.1.1 (MIT classifier, PyPI metadata), not read from files |
| xgboost | 3.4.1 | `xgboost-3.4.1.dist-info/licenses/LICENSE` | Apache-2.0 | yes |
| lightgbm | 4.7.0 | `lightgbm-4.7.0.dist-info/licenses/LICENSE` | MIT | yes |
| skops | 0.16.0 | `skops-0.16.0.dist-info/licenses/LICENSE` | MIT | yes |
| skl2onnx | 1.20.0 | `skl2onnx-1.20.0.dist-info/licenses/LICENSE` (+ `NOTICE`) | Apache-2.0 | yes |
| onnx | 1.23.2 | `onnx-1.23.2.dist-info/licenses/LICENSE` (+ `NOTICE`) | Apache-2.0 | yes |
| onnxruntime | 1.32.0 | `onnxruntime/LICENSE` (+ `ThirdPartyNotices.txt`, not read) | MIT | yes |
| gpytorch | 1.15.2 | `gpytorch-1.15.2.dist-info/licenses/LICENSE` | MIT | yes |
| botorch | 0.18.1 | `botorch-0.18.1.dist-info/licenses/LICENSE` | MIT | yes |
| torch | 2.15.0 | not read (wheel not downloaded; PyPI `License-Expression`: Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND ISC AND MIT AND Zlib) | not confirmed | not confirmed |

All the licences read are permissive (BSD, MIT, Apache-2.0) and compatible with AGPL-3.0
for a combined work, so each may be imported in-process under spec 1's "Engine licence
rule" once recorded in `docs/DECISIONS.md`. Not legal advice.

| Package | Latest (date) | Releases 2024-11-16 to 2026-11-16 | Requires-Python | Linux wheel |
| --- | --- | --- | --- | --- |
| scikit-learn | 1.9.1 (2026-09-10) | 11, including release candidates (1.6.0 to 1.9.1) | >=3.11; classifiers 3.11 to 3.14 | manylinux x86-64, `libgomp` bundled |
| smt | 2.15.1 (2026-11-04) | 17 | >=3.10 | manylinux x86-64 with C extensions |
| xgboost | 3.4.1 (2026-08-15) | 18 | >=3.12 | manylinux_2_28 x86-64, 57.6 MB, `libgomp` bundled |
| lightgbm | 4.7.0 (2026-07-18) | 2 (4.6.0, 4.7.0) | >=3.10 | manylinux x86-64; links the system `libgomp.so.1` (ldd), not bundled |
| skl2onnx | 1.20.0 (2026-01-30) | 4 | >=3.8 | pure Python |
| onnxruntime | 1.32.0 (2026-11-13) | 22 | >=3.11 | manylinux x86-64, 27.8 MB |
| skops | 0.16.0 (2026-09-24) | 6 | >=3.9 | pure Python |
| gpytorch / botorch | 1.15.2 (2026-02-28) / 0.18.1 (2026-06-08) | 7 / 11 | >=3.10 / >=3.11 | pure Python, but need torch |

- **Python 3.11.** xgboost 3.4.1 requires Python 3.12 or later; the product supports 3.11
  (CLAUDE.md). scikit-learn, smt and lightgbm accept 3.11.
- **WSL 2** is Linux, so the manylinux wheels apply; none needs a GUI. LightGBM needs the
  system OpenMP runtime (`libgomp1` on Ubuntu); it was present here. scikit-learn and
  xgboost bundle theirs. Installed with `uv pip` on Python 3.12.3 on Linux; WSL itself not
  tried.
- **CPU only.** Everything in the trial ran on 4 CPU cores. GPyTorch and BoTorch need
  PyTorch (not installed, not run); they matter only for large n or GPU use.
- **scikit-learn already covers both defaults.** `GaussianProcessRegressor` and
  `HistGradientBoostingRegressor` are in scikit-learn, which needs only numpy and scipy
  (already product dependencies) plus joblib, narwhals and threadpoolctl (`Requires-Dist` in the 1.9.1 wheel; their licences not read here).

**Saving a model so it runs on another machine.**

- *pickle / joblib.* The scikit-learn 1.9.1 "Model persistence" page: pickle "should only
  be used if the artifact ... is coming from a trusted and verified source"; and "there
  are no supported ways to load a model trained with a different version of
  scikit-learn". A project file is not a trusted source (projects are shared), and the
  laptop may have another scikit-learn version. SMT's `save()` is zlib-compressed pickle
  (`smt/utils/persistence.py`, read). So pickle is out.
- *skops.* Loads only trusted types, but the trial shows the GP's kernels
  (`ConstantKernel`, `Matern`, `Product`) and HGB's `TreePredictor` are *not* trusted by
  default; a loader would have to trust them by name. Same version lock as pickle. Larger
  than pickle in the trial (below).
- *ONNX* (skl2onnx 1.20.0, onnxruntime 1.32.0): inference only; "Original Python object
  is lost" (scikit-learn page), and ONNX files can encode arbitrary computation, so the
  page recommends a sandbox. The supported-models page (skl2onnx 1.20.0) says it targets
  scikit-learn 1.8.0. With scikit-learn 1.9.1 the trial could not convert the Matern GP,
  the HGB model, or a GP's standard deviation with `normalize_y` (details under
  "Tested"); a GP with an RBF kernel converted its mean only. Not usable today.
- *The runs plus the fitted hyperparameters, as JSON.* For a GP, the model *is* its
  training runs plus the kernel hyperparameters: a refit with the optimiser off gave
  bit-identical means and standard deviations (trial). The file is plain data, read with
  the product's strict JSON reader, and works with any later scikit-learn that has the
  same kernel. It also keeps the evidence (the runs) beside the surrogate. For trees there
  is no small parameter set; the equivalent is the runs plus the settings and seed, and a
  refit on load (HGB refit was bit-identical with the same seed on the same machine).

### 3. Trial results

All numbers below are copied from `docs/research/spec-5-trials/surrogates/output.txt`
(the script `trial.py` beside it). Ten Latin hypercube designs (seeds 0 to 9) per row;
"median [min, max]" over the ten. Held-out error on 1,000 Latin hypercube points.
Q² is on the held-out points; nRMSE is RMSE divided by the range of the held-out outputs
(Loeppky's `e_avg` form). GP: Matern 5/2, one length scale per input, `normalize_y`,
5 optimiser restarts. HGB-default: `HistGradientBoostingRegressor` defaults;
HGB-small: `min_samples_leaf=2, max_iter=500, learning_rate=0.05`.

**Held-out accuracy.**

| Function, n | GP Q² | GP nRMSE | HGB-default Q² | HGB-small Q² |
| --- | --- | --- | --- | --- |
| Branin, 10 (5d) | 0.6763 [−0.1142, 0.7457] | 0.1053 | −0.0149 | 0.1463 |
| Branin, 20 (10d) | 0.9914 [0.8997, 0.9976] | 0.01716 [0.009016, 0.05863] | −0.02934 | 0.475 |
| Branin, 40 (20d) | 0.9996 [0.999, 0.9999] | 0.003678 [0.001724, 0.00589] | 0.1162 | 0.7555 |
| Borehole, 40 (5d) | 0.9994 [0.9987, 0.9996] | 0.005093 | 0.6657 | 0.8226 |
| Borehole, 80 (10d) | 0.9999 [0.9998, 1] | 0.001789 [0.001347, 0.002565] | 0.9107 | 0.868 |
| Borehole, 160 (20d) | 1 [0.9999, 1] | 0.0008966 | 0.9601 | 0.9157 |

- The GP is far better than boosted trees at these sizes. HGB with defaults has
  `min_samples_leaf=20`, so with 20 runs it fits one leaf: a constant (Branin Q² about 0).
  Even tuned, HGB reached Q² 0.7555 on Branin with 40 runs and 0.9157 on Borehole with
  160. Trees are not a default for small designed experiments.
- Branin at 10d: median Q² 0.9914 but worst 0.8997. A gate of "Q² ≥ 0.99 with 20 runs"
  would fail on some designs. At 20d (40 runs) the worst was 0.999.
- SMT KRG (squared exponential, defaults) at 10d agreed: Branin Q² 0.9952 [0.9637,
  0.9985], Borehole 0.9999 [0.9999, 1].
- The GP's largest held-out error is about ten times its RMSE (Branin 20: RMSE 4.892,
  max 34.77; Borehole 80: 0.4009 and 4.439).

**Is cross-validation honest?** Ratio = cross-validated RMSE from the training runs alone
÷ true held-out RMSE (1 = honest, above 1 = pessimistic, below 1 = optimistic).

| Function, n | GP LOO ratio | GP 5-fold ratio | HGB-small 5-fold ratio |
| --- | --- | --- | --- |
| Branin, 10 | 1.424 [0.5989, 1.828] | 1.905 [0.7127, 2.402] | 1.21 [0.7604, 2.31] |
| Branin, 20 | 1.549 [0.6267, 11.04] | 4.903 [1.084, 16.46] | 1.335 [0.6139, 1.962] |
| Branin, 40 | 1.324 [0.6051, 4.684] | 2.085 [0.7145, 11.41] | 1.253 [0.978, 1.732] |
| Borehole, 40 | 1.04 [0.6309, 1.862] | 1.826 [1.307, 2.549] | 1.103 [0.8741, 1.346] |
| Borehole, 80 | 1.314 [0.7739, 4.02] | 1.887 [0.9452, 4.348] | 1.271 [0.8563, 1.524] |
| Borehole, 160 | 0.9044 [0.468, 2.12] | 1.221 [0.5603, 3.397] | 1.065 [0.9605, 1.346] |

- Cross-validation is pessimistic in the median, as expected (each fit sees fewer runs),
  but it is optimistic for some designs: the worst LOO ratio was 0.468 (Borehole 160), so
  the true error was up to 2.1 times the LOO estimate (1 / 0.468, computed here).
- 5-fold CV on a GP with 20 runs is very pessimistic (median 4.903): removing 4 of 20 runs
  leaves holes. LOO is closer (median 1.549). Loeppky et al. also use LOO.
- LOO used the hyperparameters fitted on all runs (Jones et al. 1998); 5-fold refitted
  them.

**Interval coverage (nominal 95 %).** GP held-out coverage: Branin 20: 1 [0.892, 1];
Branin 40: 1 [0.995, 1]; Borehole 80: 0.9775 [0.919, 0.994]; Borehole 160: 0.965
[0.931, 0.982]. LOO coverage at n = 10d: Branin 0.95 [0.95, 1], Borehole 0.9625 [0.925,
1]. Standardised LOO residuals beyond ±3: 0 to 1 per design at n = 10d, up to 3 of 160
at n = 160. Intervals are roughly calibrated to conservative at 10d and above, not below.

**Noisy outputs** (Branin plus Gaussian noise, GP with a `WhiteKernel`; error against the
noise-free function):

| Noise sd, n | Q² vs f | Fitted noise sd | 95 % coverage of f |
| --- | --- | --- | --- |
| 5, 20 | 0.9726 [0.6974, 0.9862] | 1.935 [0.004226, 6.076] | 0.875 [0.673, 0.996] |
| 5, 40 | 0.9896 [0.9724, 0.9954] | 4.312 [2.948, 5.145] | 0.9385 [0.848, 0.994] |
| 5, 80 | 0.9966 [0.9911, 0.9971] | 4.597 [4.052, 5.407] | 0.977 [0.925, 0.996] |
| 20, 20 | 0.8483 [0.5892, 0.8733] | 12.68 [0.005958, 19.71] | 0.899 [0.751, 0.99] |
| 20, 80 | 0.9615 [0.9329, 0.9711] | 19.23 [16.55, 22.14] | 0.954 [0.884, 0.981] |

- With 20 single runs the noise level is poorly identified (fitted sd from 0.004 to 6.1
  for a true 5), and coverage drops to 0.875. From 40 runs it is close.
- Replicated design (20 points × 5 replications, heteroscedastic noise sd = 2 + 0.1 f(x)):
  per-point `alpha` from the replication variances (stochastic-kriging style) gave Q²
  0.9716 [0.8164, 0.9888] and coverage 0.9645 [0.746, 1]; one `WhiteKernel` on the same
  means gave Q² 0.9695 [0.8415, 0.9888] and coverage 0.9125 [0.565, 1]. Similar accuracy;
  the per-point form gave better-calibrated intervals here.
- 5-fold CV RMSE on noisy runs includes the noise, so it is not the error against the
  true mean (noise 5, n = 80: CV 6.354 against 3.07 vs f).

**Extrapolation** (Branin GP trained on x₁ ∈ [−5, 2.5], 20 runs): inside the box Q²
0.9994 [0.9976, 0.9999], RMSE 1.171; outside (x₁ ∈ [2.5, 10]) Q² 0.7121 [−0.2967,
0.8361], RMSE 29.1. Coverage outside was 1 [1, 1]: the intervals widen enough to cover,
but are then too wide to be useful.

**Determinism, size and portability** (Borehole, 80 runs, seed 0):

- GP refit with the same seed: bit-identical. HGB refit with the same seed:
  bit-identical. GP refit with the runs in another order: max difference 2.323e-08 of
  the output range (not bit-identical).
- Saved size: GP pickle 64,117 bytes, skops 88,819; HGB-small pickle 1,765,222, skops
  3,630,625. GP as JSON (runs + hyperparameters) 14,924 bytes; refit from it with the
  optimiser off: mean and standard deviation bit-identical.
- GP single-point prediction: 0.08883 ms on this machine (4-core 2.1 GHz Xeon). Fit
  times at 10d: GP Branin 0.09768 s, Borehole 0.4991 s (medians).
- Warnings: the GP fits raise scikit-learn `ConvergenceWarning`s (Borehole 80: 176 over
  the ten designs and their CV refits). A scratch run of seeds 0 to 2 showed they are
  length scales at the upper bound for the near-inactive Borehole inputs (r, Tu, Tl) and,
  on Branin, `lbfgs` stopping abnormally and the variance at its bound. The product runs
  with warnings as errors, so the adapter must catch these and turn the meaningful ones
  into issues.

## Sources

- Loeppky, J. L., Sacks, J., Welch, W. J. (2009). Choosing the sample size of a computer
  experiment: a practical guide. *Technometrics* 51(4), 366–376. doi:10.1198/TECH.2009.08040.
  Read from https://www.asc.ohio-state.edu/statistics/comp_exp/jour.club/LoeppkySacksWelch_TNX2009.pdf
  (abstract, sections 2, 3, 5, 7), 2026-11-16.
- Jones, D. R., Schonlau, M., Welch, W. J. (1998). Efficient global optimization of
  expensive black-box functions. *Journal of Global Optimization* 13, 455–492. Read from
  https://openturns.github.io/openturns/papers/jones1998.pdf (cross-validation section,
  initial design), 2026-11-16.
- Ankenman, B., Nelson, B. L., Staum, J. (2008). Stochastic kriging for simulation
  metamodeling. *Proceedings of the 2008 Winter Simulation Conference*, 362–370. Read from
  https://www.informs-sim.org/wsc08papers/042.pdf, 2026-11-16. Journal version:
  *Operations Research* 58(2), 371–382 (2010), doi:10.1287/opre.1090.0754 (not read;
  paywalled).
- Marrel, A., Iooss, B., Van Dorpe, F., Volkova, E. (2008). An efficient methodology for
  modeling complex computer codes with Gaussian processes. arXiv:0802.1099v2. Read the
  abstract and section 3 (Q² definition), 2026-11-16.
- Bastos, L. S., O'Hagan, A. (2009). Diagnostics for Gaussian process emulators.
  *Technometrics* 51(4), 425–438. Read from
  https://www.asc.ohio-state.edu/statistics/comp_exp//jour.club/BastosOHagan-Tnx2009.pdf
  (section 3.3 and the pivoted Cholesky passage, found by text search; not read in full),
  2026-11-16.
- Gramacy, R. B. (2020). *Surrogates: Gaussian Process Modeling, Design and Optimization
  for the Applied Sciences*. Chapman Hall/CRC. https://bookdown.org/rbg/surrogates/chap5.html
  (sections 5.1.1, 5.2), read 2026-11-16.
- Surjanovic, S., Bingham, D. Virtual Library of Simulation Experiments: Branin
  (https://www.sfu.ca/~ssurjano/branin.html) and Borehole
  (https://www.sfu.ca/~ssurjano/borehole.html) pages and their R code pages (formulas,
  constants, input ranges), read 2026-11-16. The R code is GPL-2.0; it was not copied, the
  formulas were re-typed.
- scikit-learn 1.9.1 documentation: "Model persistence"
  (https://scikit-learn.org/stable/model_persistence.html) and `GaussianProcessRegressor`
  (https://scikit-learn.org/stable/modules/generated/sklearn.gaussian_process.GaussianProcessRegressor.html),
  read 2026-11-16; source `sklearn/gaussian_process/_gpr.py` in the 1.9.1 wheel.
- skl2onnx 1.20.0 supported-models page, https://onnx.ai/sklearn-onnx/supported.html
  (first 100,000 characters), read 2026-11-16.
- SMT surrogate-model list, https://smt.readthedocs.io/en/latest/_src_docs/surrogate_models.html,
  read 2026-11-16; `smt/utils/persistence.py` in the 2.15.1 wheel.
- PyPI JSON API (`https://pypi.org/pypi/<pkg>/json`) for every package in the tables,
  read 2026-11-16; licence files from the wheels as listed.

## Decision

Proposed defaults for spec 5 "Surrogate models" (owner to confirm):

- **Default method: Gaussian process regression**, scikit-learn
  `GaussianProcessRegressor`, in-process (BSD-3-Clause). Kernel: constant × Matern 5/2
  with one length scale per input, inputs scaled to [0, 1] at fit, `normalize_y`, a fixed
  number of optimiser restarts with the seed drawn from the spec 1 stream scheme. Noise:
  for a stochastic model, a `WhiteKernel` when each design point has one run, and
  per-point noise (`alpha` from the replication variance ÷ replications, scaled for
  `normalize_y`) when the design has replications (stochastic kriging, Ankenman et al.).
- **Gradient-boosted trees** (`HistGradientBoostingRegressor`) are offered only for large
  budgets (several hundred runs or more; not measured here) or discontinuous outputs, and
  never with scikit-learn's default `min_samples_leaf` on a small design. They give no
  predictive interval. XGBoost and LightGBM add nothing the trial needed; xgboost needs
  Python 3.12 or later.
- **Neural surrogates** stay optional, as the spec says; GPyTorch/BoTorch would bring
  PyTorch (licence not read from the wheel) and are not needed for CPU use.
- **Run budget.** Default 10 × the number of inputs (Loeppky et al.; Jones et al.).
  The interface warns below 10d and refuses below 5d or 10 runs, whichever is larger (the
  trial's Branin at 5d had median Q² 0.6763).
- **The error shown ("validation error").** The leave-one-out RMSE in the output's units,
  and as a share of the output range, with the leave-one-out Q² and the largest LOO
  error, computed from the training runs alone (GP: hyperparameters from all runs, as
  Jones et al.; trees: 5-fold). Shown with the run count, for example (illustrative wording) "validation error ± 0.45
  m³/yr RMSE (0.2 % of range), leave-one-out over 80 runs". A held-out error is shown
  instead when the user has spare runs. The standardised LOO residuals are checked; more
  than 5 % beyond ±3 gives a warning that the error estimate is unreliable. The note
  says plainly that the true error was up to 2.1 times the LOO estimate in the trial.
- **Label.** Every surrogate result carries the fidelity label `surrogate` (spec 1's
  existing `run.fidelity` and `summary.json` label) and the text "approximate: surrogate
  of <model>, validation error …". A GP result also shows its 95 % interval. A query
  outside the training box (any input outside its trained range) is refused or marked
  "outside the trained range: not validated", never silently answered.
- **Storage: no pickle, no skops, no ONNX.** The surrogate is saved in the project as a
  JSON file read and written through `ithax.strict_json`: the model id and version it was
  trained from, the input names, units and ranges, the output name and unit, the runs
  (inputs and outputs, with replications), the method and its settings, the seed, the
  fitted hyperparameters (GP), the validation numbers, and the library versions used. On
  load, the surrogate is rebuilt by refitting with the stored hyperparameters and the
  optimiser off (GP; bit-identical in the trial, 14,924 bytes for 80 runs of 8 inputs) or
  by refitting with the stored settings and seed (trees). Loading never executes stored
  code, and a newer scikit-learn only changes the fit, which is rechecked against the
  stored validation numbers.
- **Benchmarks, set from this trial's outputs** (fixed design seed 0, 1,000 held-out
  Latin hypercube points from a separate seed):

  | Case | Gate | Trial result over 10 designs |
  | --- | --- | --- |
  | Branin, GP, 40 runs (20d; d < 4 is outside Loeppky's study) | Q² ≥ 0.995, held-out 95 % coverage ≥ 0.90 | Q² 0.9996 [0.999, 0.9999]; coverage 1 [0.995, 1] |
  | Borehole, GP, 80 runs (10d) | Q² ≥ 0.999, nRMSE ≤ 0.005, coverage ≥ 0.90 | Q² 0.9999 [0.9998, 1]; nRMSE 0.001789 [0.001347, 0.002565]; coverage 0.9775 [0.919, 0.994] |
  | Noisy Branin (noise sd 5), GP + WhiteKernel, 40 runs | Q² against the noise-free function ≥ 0.95 | 0.9896 [0.9724, 0.9954] |
  | Honesty | held-out RMSE ≤ 2.5 × the stated LOO RMSE (Branin 40, Borehole 80) | worst LOO ratio over all GP rows 0.468, i.e. 2.1× |
  | Portability | predictions after save and load equal those before, bit for bit, on the same versions | bit-identical (Borehole 80) |

  Each gate sits below the worst of the ten designs, so a fixed seed passes with a
  margin, and a regression (a broken kernel, scaling or refit) fails it. Branin at 20 runs
  is listed but not gated (median Q² 0.9914, worst 0.8997).
- **Acceptance test wording.** "A surrogate trained on the development machine
  reproduces held-out results within its stated error on the low tier" becomes: the
  surrogate file loads on the low tier with the same library versions and gives the same
  predictions (to 1e-9 of the output range), and its held-out RMSE on fresh runs is at
  most 2.5 × its stated validation error.

Open questions:

- *Blocking* (changes the model format or a user-visible answer):
  - B-S1. The surrogate file format: JSON runs plus hyperparameters, refitted on load
    (proposed), versus a binary model file. Changes the project format.
  - B-S2. Inputs outside the training box: refuse, or answer with an "outside trained
    range" mark (proposed: answer, marked, with the GP interval). User-visible.
  - B-S3. The error shown: LOO RMSE (proposed) versus 5-fold or a held-out set. User-visible.
  - B-S4. Minimum budget: refuse below max(5d, 10) runs (proposed). User-visible.
- *Reversible*:
  - R-S1. Kernel (Matern 5/2 vs RBF) and number of restarts.
  - R-S2. The warning threshold for standardised LOO residuals (5 % beyond ±3).
  - R-S3. Whether to record SMT as a second engine (BSD-3-Clause; KRG agreed in the trial)
    for PCE, RBF or gradient-enhanced kriging later.
  - R-S4. Which scikit-learn `ConvergenceWarning`s become issues and which are expected
    (length scales at the bound mean an input has little effect).
  - R-S5. The benchmark margins above, revisited after the adapter exists.

## Tested

Environment: Python 3.12.3 on Linux x86-64, 4 cores, a fresh venv in the scratch folder:
numpy 2.5.4, scipy 1.18.1, scikit-learn 1.9.1, smt 2.15.1, skops 0.16.0, skl2onnx 1.20.0,
onnx 1.23.2, onnxruntime 1.32.0 (xgboost 3.4.1 and lightgbm 4.7.0 installed and imported,
not used in the trial).

- `docs/research/spec-5-trials/surrogates/trial.py`, output in `output.txt` beside it
  (run `python -I trial.py > output.txt`, exit code 0, 846 s). Known answers: Branin and
  Borehole evaluated exactly at 1,000 held-out points; all errors are against those. The
  Branin formula was checked against the Virtual Library constants (a = 1,
  b = 5.1/(4π²), c = 5/π, r = 6, s = 10, t = 1/(8π)); the trial does not separately print
  the Branin minimum 0.397887.
- `docs/research/spec-5-trials/surrogates/onnx_probe.py`, output in
  `onnx_probe_output.txt` (30 toy points, 2 inputs). Results with scikit-learn 1.9.1 and
  skl2onnx 1.20.0: GP with an RBF kernel, mean only: converted, max difference 7.61e-08
  (`normalize_y=True`) and 5.25e-08 (`False`); GP standard deviation with
  `normalize_y=True`: `TypeError`; with `normalize_y=False`: converted, but the ONNX
  standard deviation differed by up to 6.95 where scikit-learn's was 4.42e-06 to 1e-05
  (wrong); GP with a Matern kernel: every case failed (`AttributeError: 'int' object has
  no attribute 'encode'`); HistGradientBoostingRegressor: failed (`TypeError('Field
  onnx.AttributeProto.ints: Expected an int, got a boolean.')`). These may be version
  mismatches (the skl2onnx page targets scikit-learn 1.8.0); scikit-learn 1.8.0 was not
  tried.
- A scratch run (not kept) classified the GP `ConvergenceWarning`s for seeds 0 to 2 of
  Branin 40 and Borehole 80 (results under "Determinism, size and portability").
- Not run: XGBoost and LightGBM fits (scikit-learn's HGB stands for boosted trees);
  GPyTorch, BoTorch and PyTorch (not installed; torch licence not read from the wheel);
  polynomial chaos and RBF surrogates; Bastos and O'Hagan's Mahalanobis and pivoted
  Cholesky diagnostics; loading a saved model on a second machine or under WSL 2 (only
  the same machine, same versions); Python 3.11 (all runs on 3.12.3); a real Ithax
  simulation model as the source of runs.
