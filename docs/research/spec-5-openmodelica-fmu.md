# Spec 5 research: OpenModelica FMU export and FMI version

## Question

Spec 5 builds physical system models in OpenModelica, exported as FMUs and run with FMPy. Its research list asks: "Which FMI version exports reliably today, and which standard libraries are usable." What are OpenModelica's licence, upkeep and install on Linux and under WSL 2, and can an exported FMU be shipped with a template?

## Finding

Read on 2026-11-16, from the OpenModelica apt repository for Ubuntu 24.04 (`https://build.openmodelica.org/apt`, suite `noble`, component `release`) and the user's guide. Packages were downloaded and unpacked with `dpkg-deb -x` to read their files; none was installed or run (see Tested).

- **Version.** 1.27.2, the newest in the `release` component (`omc_1.27.2-1_amd64.deb`, 2026-10-30, SHA-256 `94125561…fac77`, equal to the repository's `Packages` index).
- **Upkeep.** The `contrib-noble` pool holds 30 releases of `omc` from 1.22.4 (2024-04-30) to 1.27.2 (2026-10-30): a minor release about every three to six months and a patch release about monthly.
- **Licence of the compiler and tools.** `usr/share/doc/omc/copyright` (and the same file in `libomcsimulation`): "PROVIDED UNDER THE TERMS OF GPL VERSION 3 LICENSE OR THIS OSMC PUBLIC LICENSE (OSMC-PL) VERSION 1.2 … ACCORDING TO RECIPIENTS CHOICE". GPL-3.0 is compatible with AGPL-3.0, and under owner decision F4 the compiler is run as a separate process through its own files, which the spec 1 rule allows for any licence.
- **Licence of the runtime that goes into an FMU.** The C runtime headers and sources in `omc-common` (`usr/include/omc/c/`, 159 files) say "PROVIDED UNDER THE TERMS OF THE BSD NEW LICENSE OR THE AGPL VERSION 3 LICENSE OR THE OSMC PUBLIC LICENSE (OSMC-PL) VERSION 1.8 … ACCORDING TO RECIPIENTS CHOICE"; so do the 21 headers of `libomcsimulation` under `usr/include/omc/omsi/`, and OMPython 4.1.0's `LICENSE` (the "OpenModelica Run-time System Public License"). An FMU built by OpenModelica can therefore be shipped under BSD-3-Clause, which lets a template carry one.
- **Modelica Standard Library.** The `omlibrary` package (1.27.2, SHA-256 `8829b9b2…3701`) holds the Modelica Standard Library 3.2.3, 4.0.0 and 4.1.0 (`version="4.1.0"` in `Modelica/package.mo`), BSD-3-Clause, "Copyright (c) 1998-2024, Modelica Association and contributors" (its `LICENSE`).
- **FMI versions.** The user's guide (v1.28.0-dev-1948, read 2026-11-16, "Functional Mock-up Interface"):
  - FMI 1.0 is "Deprecated, will be removed after OpenModelica 1.28.0 is released";
  - FMI 2.0 is supported for Model Exchange and Co-Simulation;
  - FMI 3.0 is "experimental".

  The 1.27.2 runtime agrees: `usr/include/omc/c/fmi-export/` holds `fmu1_model_interface` and `fmu2_model_interface` and nothing for FMI 3.
- **Defaults disagree between two pages.** The scripting API's signature of `buildModelFMU` (read 2026-11-16) gives `version = "2.0"`, `fmuType = "me"`, `platforms = {"static"}` (everything statically linked; `"dynamic"` links the runtime dynamically) and `method = "<default>"`, "<default> = dassl", for the integrator in a Co-Simulation FMU. The FMI page of the user's guide says the default export makes both interface types and names CVODE as the default integrator. Ithax therefore states `version`, `fmuType` and `platforms` explicitly, and the CI trial records which integrator the FMU carries (Tested: neither, by default).
- **Solvers inside a Co-Simulation FMU** (the user's guide). CVODE, or forward Euler with `--fmiFlags=s:euler`; "Forward Euler does an Euler step of `communicationStepSize` in `fmi2DoStep`." The guide says that on the platform OpenModelica runs on, the FMU links the SUNDIALS libraries installed there.
- **Source-code FMUs.** OpenModelica exports source-code FMUs built with CMake; an empty `platforms` setting gives a source-code-only FMU. `platforms` also takes `native` or a host triple such as `x86_64-linux-gnu`.
- **What `omc` needs.** The `omc` package depends on `clang`, `cmake`, `build-essential`, `libexpat1-dev`, `liblapack-dev`, `zip`, `unzip` and the OpenModelica libraries: exporting an FMU compiles C code, so a C toolchain must be installed where FMUs are built.
- **Linux and WSL 2.** Ubuntu and Debian packages from the apt repository above (suites from `bionic` to `noble` and Debian `buster` to `bookworm` are listed). WSL 2 runs Ubuntu, so the same apt steps apply. Only the compiler's command line is needed; OMEdit, the graphical editor, is not.

## Sources

- `https://build.openmodelica.org/apt/dists/noble/release/binary-amd64/Packages` and the pool listing `https://build.openmodelica.org/apt/pool/contrib-noble/`, read 2026-11-16.
- Unpacked packages: `omc_1.27.2-1_amd64.deb`, `libomcsimulation_1.27.2-1_amd64.deb` (SHA-256 `be399546…49003d2`), `omc-common_1.27.2-1_all.deb` (SHA-256 `60fcc544…6abd666`), `omlibrary_1.27.2-1_all.deb`.
- OMPython 4.1.0 wheel, `ompython-4.1.0.dist-info/licenses/LICENSE` (SHA-256 of the wheel `151f5e07…a534`, equal to PyPI's).
- OpenModelica User's Guide, "Functional Mock-up Interface - FMI", <https://openmodelica.org/doc/OpenModelicaUsersGuide/latest/fmitlm.html>, and "Scripting API", `buildModelFMU`, <https://openmodelica.org/doc/OpenModelicaUsersGuide/latest/scripting_api.html>, read 2026-11-16.

## Decision

Proposed (owner to confirm):

- **FMI 2.0 Co-Simulation** is the export format for Phase 2, with `version`, `fmuType` and `platforms` always given, never left to their defaults. Model Exchange is not used: Co-Simulation keeps the integrator inside the FMU, so FMPy only steps it, and a Model Exchange FMU would make FMPy's integrator part of the answer as well. FMI 3.0 is revisited when OpenModelica's export is no longer experimental.
- **Ithax writes Modelica, OpenModelica compiles it.** The adapter writes a `.mo` file in its run folder from the model file's components, which name Modelica Standard Library 4.1.0 classes, and calls `omc` with a `.mos` script that sets `--fmiFlags=s:cvode` and runs `buildModelFMU(..., version = "2.0", fmuType = "cs", platforms = {"static"})`; CI run 43938942488 showed that without the flag the FMU steps with forward Euler at the communication step (Tested). `omc` runs as a separate process (GPL-3.0 under F4); for the build step `GPL-3.0` (the text says "GPL version 3", without "only" or "or later") `OR LicenseRef-OSMC-PL-1.2` (OSMC-PL has no SPDX identifier; council finding F4), `invocation` `process`.
- **Built FMUs are cached** in the project, keyed by the SHA-256 of the generated `.mo` file and the OpenModelica version, so a model that has not changed is not compiled again, and a template can ship its FMU (BSD-3-Clause runtime) for a machine without OpenModelica.
- **Standard library.** Modelica Standard Library 4.1.0 only, in Phase 2.

Open questions:

- **Blocking (a target platform):** a machine without a C toolchain and OpenModelica cannot build an FMU. Options: (a) building physical models needs OpenModelica installed (documented, apt under Linux and WSL 2), and running a shipped FMU needs only FMPy; (b) Ithax bundles OpenModelica in its package. Recommended: (a); (b) makes the Linux package much larger.
- **Reversible, partly tested:** FMUs built with `platforms = {"static"}` ran in a clean container without OpenModelica (Tested). The CVODE FMU still names SUNDIALS libraries that `ldd` cannot find there; this is explained before templates ship FMUs.

## Tested

In CI, workflow `spec5-trials.yml` (#228), because OpenModelica could not be installed in the research container (its apt repository was refused by the session's permission rules, and there is no Docker daemon). The job downloads the five pinned 1.27.2 packages, checks each SHA-256 and fails closed, installs them on `ubuntu-24.04`, builds `docs/research/spec-5-trials/openmodelica/MSD.mo` (`Modelica.Mechanics.Translational`, MSL 4.1.0) with `build.mos`, and runs the FMUs with FMPy 0.3.32 (pinned wheel, SHA-256 checked) through `run_fmu.py`. A second job runs the same FMUs in a clean `python:3.12-slim-bookworm` container without OpenModelica. The known answer is x(10) = 0.079116024 m (`benchmarks/expected_values.py`); the gate is a largest error of 1e-5 m over the run.

- **Run 43935773704, head `d98f5d7`.** Two FMUs, built with the defaults apart from `fmuType = "cs"`: x(10) = 0.091237783 m for both, with and without OpenModelica installed, failing the gate. The error pointed at the integrator.
- **Run 43938942488, head `e94ef9b`** (copied from the job logs of `openmodelica` and `fmu-without-openmodelica`):

  | FMU | Communication step | x(10) (m) | Largest error (m) | Within 1e-5 |
  | --- | --- | --- | --- | --- |
  | `MSD_dynamic` (`platforms = {"dynamic"}`) | 0.01 s | 0.091237783 | 3.87e-02 | no |
  | `MSD_dynamic` | 0.001 s | 0.080235811 | 3.71e-03 | no |
  | `MSD_static` (`{"static"}`) | 0.01 s | 0.091237783 | 3.87e-02 | no |
  | `MSD_static` | 0.001 s | 0.080235811 | 3.71e-03 | no |
  | `MSD_cvode` (`{"static"}`, `--fmiFlags=s:cvode`) | 0.01 s | 0.079116035 | 2.08e-07 | yes |
  | `MSD_cvode` | 0.001 s | 0.079116022 | 8.67e-08 | yes |

  The results without OpenModelica were the same to every printed digit.

What the runs show:

- **The default Co-Simulation integrator is not CVODE in 1.27.2.** Without the flag, the error falls tenfold when the communication step falls tenfold, as a first-order method's does, which matches the guide's description of forward Euler at the communication step. With `--fmiFlags=s:cvode` the FMU logs "CVODE linear multistep method CV_BDF" and "relative error tolerance 1.000000e-06" and passes. Both pages read under Finding were therefore wrong for this version in one respect: neither the API's "dassl" nor the guide's "CVODE" is what an FMU gets by default.
- **The FMUs ran on a machine without OpenModelica.** `ldd` lists only `libm` and `libc` for the default FMUs. For `MSD_cvode` it lists `libsundials_cvode.so.5` and `libsundials_nvecserial.so.5` as "not found", yet the FMU loaded and gave the CVODE result in the clean container. Why it loaded was not established.
- **Licences** were read from the installed files in the job log, and agree with Finding.

The Decision section is revised accordingly:

- The adapter always sets `--fmiFlags=s:cvode` before `buildModelFMU`, and the label names CVODE and its tolerance.
- A benchmark of the export passes only with CVODE: x(10) within 1e-5 m at a communication step of 0.01 s.
- Before a template ships a CVODE FMU, the missing SUNDIALS libraries are explained, and the FMU is run on a clean machine in CI, as the second job does.
