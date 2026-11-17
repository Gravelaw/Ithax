# Spec 5 research: PySD for system dynamics

## Question

Spec 5 names PySD for system dynamics, "to be confirmed". What are its state, licence and upkeep, how does it install on Linux and under WSL 2, which model formats does it read, how does it integrate, and does it reproduce the SIR and predator–prey benchmarks?

## Finding

Read on 2026-11-16.

- **Version.** PySD 3.14.3, uploaded to PyPI on 2025-03-23. No release since, so 20 months without one.
- **Licence.** MIT. Read from `pysd-3.14.3.dist-info/LICENSE` in the wheel `pysd-3.14.3-py3-none-any.whl` (SHA-256 `e663c537…9d4a`, equal to PyPI's digest): "The MIT License (MIT) Copyright (c) 2013-2022 PySD contributors". MIT may be imported in-process under the spec 1 rule.
- **Upkeep.** One release between 2024-11-16 and 2026-11-16 (3.14.3); the two before were 3.14.1 (2024-07-18) and 3.14.2 (2024-11-13). The project is maintained but slow.
- **Python.** `requires_python >=3.9`.
- **Dependencies** (wheel metadata): numpy, pandas with Excel support, parsimonious, xarray, lxml, regex, chardet, black, openpyxl, scipy, progressbar2, portion. All are installed from wheels.
- **Linux and WSL 2.** A pure-Python wheel; it installs with pip under WSL 2 as on Linux. No graphics or system library.
- **Formats.** PySD translates Vensim `.mdl` and XMILE (`translators/vensim`, `translators/xmile`) into a Python module and runs that. It writes the translated `.py` beside the model file, so an adapter must translate inside its run folder.
- **Integration.** Fixed-step Euler only: `py_backend/model.py` has `_euler_step` and no other method. The error is therefore first order in the time step (see Tested).
- **A trap for the adapter.** Setting the time step through `run(params={"TIME STEP": dt})` was silently ignored in the trial: three different steps gave identical results. `run(time_step=dt, saveper=dt)` works. The adapter must use the arguments, and a test must check the step used, as the trial does.

## Sources

- PyPI JSON, <https://pypi.org/pypi/pysd/json>, read 2026-11-16.
- The wheel `pysd-3.14.3-py3-none-any.whl`: `LICENSE`, `METADATA`; PySD 3.14.3 source as installed: `py_backend/model.py` (`run`, `_euler_step`), `translators/`.
- SIR final size and peak: Brauer (2008), as in `spec-5-mesa.md`; the peak from the first integral I + S − (N/R0) ln S = constant, at S = N/R0.
- Lotka–Volterra first integral V = δx − γ ln x + βy − α ln y: Hirsch, Smale and Devaney, *Differential Equations, Dynamical Systems, and an Introduction to Chaos*, 3rd ed. (2013), section 11.2.
- XMILE: OASIS, *XML Interchange Language for System Dynamics (XMILE) Version 1.0*, OASIS Standard, 14 December 2015.

## Decision

Proposed (owner to confirm):

- **PySD is the system dynamics engine**, confirmed. Imported in-process (MIT); `Capabilities.licence` `MIT`, `invocation` `in-process`, `distribution` `pysd`.
- **The model file holds stocks, flows and auxiliaries as components**, and the adapter writes an XMILE file in its run folder for PySD to translate. Confirmed on the benchmarks on 2026-11-17 (Tested): PySD's results from XMILE equal its results from Vensim `.mdl` exactly. XMILE is an open standard, so the translated file is a readable record of what ran, as `engine/input.json` is for the process adapter.
- **Time step.** An experiment states its `time_step`; the result's label names it and the integration method ("Euler, step 0.0625 d"), since the answer depends on it.
- **Benchmarks state their step and tolerance.** From the trial: SIR final size within 0.5 person at a step of 1/64 day, and the predator–prey invariant within 0.1% relative drift at a step of 0.0001 year.
- **Upkeep risk recorded.** If PySD stops being maintained, XMILE keeps the models portable to another engine.

Open questions:

- **Reversible:** the default time step when an experiment gives none. Proposed: none; `time_step` is required, since a silent default would change answers.
- **Reversible:** whether XMILE or Vensim files can be imported into Ithax. Proposed: later (D6's wider imports), not in M23.

## Tested

`docs/research/spec-5-trials/pysd/trial_pysd.py` with `sir.mdl` and `predator_prey.mdl`; output in `output.txt`. PySD 3.14.3, scipy 1.18.1, Python 3.12, in a scratch virtual environment.

- **SIR**, N = 1000, I0 = 1, β = 0.5 per day, γ = 0.25 per day. Known: final size 797.154100, peak infected 153.926660 (scipy root finding on the closed forms, `docs/research/spec-5-trials/benchmarks/`).

  | Step (day) | Final size | Error | Peak | Error |
  | --- | --- | --- | --- | --- |
  | 0.25 | 800.675577 | +3.5215 | 156.222521 | +2.2959 |
  | 0.0625 | 798.024919 | +0.8708 | 154.501338 | +0.5747 |
  | 0.015625 | 797.371216 | +0.2171 | 154.070058 | +0.1434 |

  The error falls by four when the step falls by four, as Euler's should.
- **Predator–prey**, α = 1, β = 0.1, γ = 1.5, δ = 0.075, x0 = 10, y0 = 5, 15 years. Known: V = −3.813315552, constant.

  | Step (year) | Largest relative drift of V |
  | --- | --- |
  | 0.01 | 3.20e-02 |
  | 0.001 | 2.88e-03 |
  | 0.0001 | 2.85e-04 |

- **Time.** The whole script ran in 4.6 s.

**XMILE** (2026-11-17). `docs/research/spec-5-trials/pysd/trial_xmile.py`, with `sir.xmile` and `predator_prey.xmile`; output in `output_xmile.txt`. Same environment as above.

- **Files.** The two models were written by hand in XMILE 1.0 (OASIS namespace, `sim_specs method="Euler"`), with the same stocks, flows, auxiliaries and values as `sir.mdl` and `predator_prey.mdl`. Names with spaces, such as `infection rate`, are written with underscores in equations and in `inflow` and `outflow`, as the standard requires. PySD read both with `pysd.read_xmile` without an edit to the files.
- **Result.** At each of the six steps above, every saved value from XMILE was equal to the value from `.mdl`: the largest difference was 0.0 in all six runs. The SIR final sizes and peaks, and the predator–prey drifts, are therefore the ones in the tables above (for example 798.024919 at 1/16 day, and 2.85e-04 at 0.0001 year).
- **What this settles.** The adapter can write XMILE for PySD, as the Decision proposes; the `.mdl` fallback in spec 5 is not needed for these two benchmarks.
- **Warnings.** The trial script ignores warnings, as `trial_pysd.py` does. Run again with every warning shown, PySD 3.14.3 raised two: a `DeprecationWarning` from `chardet.universaldetector` when `pysd` is imported, and a pandas deprecation of `set_index(inplace=...)` in each run. Ithax's tests turn warnings into errors (`pyproject.toml`, `filterwarnings`), so the adapter must filter exactly these two, named by message and module, and a test must show nothing else is raised. This applies to `.mdl` as much as to XMILE.
- **Not tried:** XMILE arrays, graphical functions (lookup tables), delays, and `<units>` checks; none is in spec 5's Phase 2 system dynamics.
- **Time.** 15.4 s for the twelve runs, translation included.

