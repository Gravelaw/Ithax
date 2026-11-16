# Spec 5 research: FMPy for running FMUs

## Question

Spec 5 runs physical system models as Functional Mock-up Units (FMUs) exported by OpenModelica and run with FMPy. What are FMPy's state, licence and upkeep, which FMI versions and interface types does it run, how does it install on Linux and under WSL 2, and does it reproduce the mass–spring–damper benchmark?

## Finding

Read on 2026-11-16.

- **Version.** FMPy 0.3.32, uploaded to PyPI on 2026-09-09.
- **Licence.** BSD-2-Clause, "Copyright (c) 2017-2025 Dassault Systemes". Read from `fmpy-0.3.32.dist-info/licenses/LICENSE.txt` in the wheel `fmpy-0.3.32-py3-none-any.whl` (SHA-256 `b379deb9…cf0`, equal to PyPI's digest). The same file lists what FMPy bundles:
  - the FMI headers and schema files, BSD-style (Modelica Association);
  - a compiled CVODE from SUNDIALS, BSD-3-Clause (Lawrence Livermore National Security);
  - icons under CC BY 4.0.
  
  A separate `fmpy/remoting/license.txt` covers the remoting binaries. All are compatible with AGPL-3.0, so FMPy may be imported in-process under the spec 1 rule.
- **Upkeep.** 11 releases between 2024-11-16 and 2026-11-16 (PyPI JSON).
- **Python.** `requires_python >=3.10`.
- **Dependencies** (wheel metadata): attrs, cmake, jinja2, lark, lxml, msgpack, nbformat, numpy. The `gui` extra pulls in PySide6 (LGPL-3.0) and is not needed.
- **Linux and WSL 2.** One `py3-none-any` wheel that carries the CVODE libraries for `x86_64-linux`, `x86_64-windows` and `aarch64-darwin`. It installs with pip under WSL 2 as on Linux.
- **FMI versions.** The wheel carries the headers and schemas of FMI 1.0, 2.0 and 3.0, and the SSP schemas (System Structure and Parameterization). FMPy runs Model Exchange FMUs with its own integrators (CVODE, or fixed-step Euler) and Co-Simulation FMUs through their own `doStep`.
- **Validation.** `read_model_description` validates an FMU's `modelDescription.xml` and refuses an invalid one: in the trial, an undeclared unit `kg` was refused with "The unit "kg" of variable "m" (line 9) is not defined." An adapter can report such a problem as an issue before a run starts.
- **What an FMU is.** A zip with `modelDescription.xml` and a compiled shared library per platform (`binaries/linux64/<id>.so`). Loading an FMU runs its native code in the loading process.

## Sources

- PyPI JSON, <https://pypi.org/pypi/fmpy/json>, read 2026-11-16.
- The wheel `fmpy-0.3.32-py3-none-any.whl`: `licenses/LICENSE.txt`, `fmpy/remoting/license.txt`, `METADATA`, `fmpy/c-code/`, `fmpy/schema/`, `fmpy/ssp/schema/`, `fmpy/sundials/`.
- Modelica Association, *Functional Mock-up Interface for Model Exchange and Co-Simulation*, version 2.0.5, and *FMI 3.0.2*, <https://fmi-standard.org/>, read 2026-11-16.
- Damped oscillator response: Thomson and Dahleh, *Theory of Vibration with Applications*, 5th ed. (1998), section 2.6.

## Decision

Proposed (owner to confirm):

- **FMPy runs physical system models**, confirmed, as FMI 2.0 FMUs (Co-Simulation and Model Exchange). FMI 3.0 runs in FMPy but OpenModelica's export of it is experimental (`spec-5-openmodelica-fmu.md`).
- **The FMU runs in a separate process.** FMPy is BSD-2-Clause and could be imported, but an FMU is native code from the project, and a fault in it would end the process that loaded it. The run target's worker (spec 1 "Where the methods run") is already a separate, spawned process, so the adapter loads the FMU there, never in the service. `Capabilities.licence` `BSD-2-Clause`, `invocation` `in-process` (FMPy itself), `distribution` `fmpy`.
- **An FMU is validated when the model loads**, with FMPy's validator, and each problem is an issue with a code.
- **Benchmark tolerance.** From the trial: the mass–spring–damper displacement within 1e-5 m of the analytic response over 10 s, at a relative tolerance of 1e-8.

Open questions:

- **Blocking (the model format):** whether a project may hold FMUs from any tool, or only those Ithax builds from its own components. An outside FMU is native code from a third party. Recommended: Phase 2 holds only FMUs that Ithax builds with OpenModelica from its own component library; importing outside FMUs is a later decision.

## Tested

`docs/research/spec-5-trials/fmpy/trial_msd.py`, with `msd.c` and `modelDescription.xml`; output in `output.txt`. FMPy 0.3.32, numpy 2.5.5, Python 3.12, gcc 13.3.0, in a scratch virtual environment.

OpenModelica could not be installed in the research container, so the FMU is not an OpenModelica export. It is a Model Exchange FMU written by hand in C that only states the equations as derivatives; FMPy's CVODE integrates them. This tests FMPy, not OpenModelica.

- **Case.** m x″ + c x′ + k x = 0, x(0) = 1 m, x′(0) = 0, m = 1 kg, k = 4 N/m: ωn = 2 rad/s.
- **Underdamped**, c = 0.4 N·s/m, ζ = 0.1: x(10 s) = 0.079115907 against the exact 0.079116024; largest error over 1,001 samples 8.63e-07.
- **Critically damped**, c = 4 N·s/m, ζ = 1: largest error 1.35e-07.
- **Validation.** `validate_fmu` returned no problems for the corrected FMU, and refused the first version (the undeclared unit above).
