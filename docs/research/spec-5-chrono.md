# Spec 5 research: Project Chrono (PyChrono) for multibody dynamics

## Question

Spec 5 names Project Chrono for multibody dynamics: rigid bodies, joints, springs and contacts. What are its licence, upkeep and install on Linux and under WSL 2, and does it reproduce the pendulum benchmark?

## Finding

Read on 2026-11-16.

- **Distribution.** PyChrono is published only as conda packages on the `projectchrono` channel ("`conda install projectchrono::pychrono -c conda-forge`", PyChrono install page). **The PyPI name `pychrono` belongs to an unrelated project** ("A package for managing delays, scheduling tasks, timing functions…", version 1.1.0, 2024-10-24). An install by `pip install pychrono` gets the wrong package; the install documentation must say so.
- **Version.** 10.0.0, builds for Python 3.12 and 3.13, the newest built 2026-10-13 (`pychrono-10.0.0-py312h98ab86c_1198.conda`, SHA-256 `988e6abf…09c5f4e`, equal to the channel's `repodata.json`).
- **Upkeep.** From the channel's `repodata.json`: 7.0.0 (2022-12), 8.0.0 (2023-01 to 2024-04), 9.0.1 (2025-08 to 2026-03), 10.0.0 (2026-04 to 2026-10), with 18 builds of 10.0.0. Linux, Windows and macOS packages are provided (install page).
- **Licence.** BSD-3-Clause, "Copyright (c) 2016, Project Chrono Development Team" (<https://projectchrono.org/license-chrono.txt>); the package's `info/index.json` and `info/about.json` say `"license": "BSD 3-Clause"`. The package itself holds no top-level licence file; its data files carry their own (for example Apache-2.0 fonts and an LGPL-3.0 OpenFOAM example).
- **Dependencies of the conda package** (`info/index.json`), which matter for licences and size:
  - the CUDA runtime, cuBLAS, cuRAND, cuSPARSE, NPP and NVRTC 12.8 (conda-forge's licence field: `LicenseRef-NVIDIA-End-User-License-Agreement`);
  - Intel MKL 2025.2 (`LicenseRef-IntelSimplifiedSoftwareOct2022`);
  - Open MPI 5 (BSD-3-Clause), Irrlicht 1.8 (Zlib), VulkanSceneGraph 1.1 (MIT), Eigen 3.4 (MPL-2.0), freeglut, GLFW, GLEW, urdfdom, tinyxml2, yaml.
  
  The package alone is 536,464,058 bytes. CUDA and MKL are proprietary but redistributable. Ithax would not ship them: the environment manager installs engines (spec 1 rule).
- **Linux and WSL 2.** conda on Linux; under WSL 2 the same conda steps apply. The CUDA libraries load without a GPU only if Chrono's GPU modules are not used; this was not tested. The run-time viewers (Irrlicht, VSG) need a display, which WSL 2 has through WSLg; Ithax would not use them (spec 5: the preview is built on spec 6's viewer basis).

## Sources

- `https://conda.anaconda.org/projectchrono/linux-64/repodata.json`, read 2026-11-16; the package `pychrono-10.0.0-py312h98ab86c_1198.conda`, its `info/index.json` and `info/about.json`, read with Python's `zipfile` and `zstandard` without installing it.
- <https://projectchrono.org/license-chrono.txt> and <https://api.projectchrono.org/pychrono_installation.html>, read 2026-11-16.
- PyPI JSON, <https://pypi.org/pypi/pychrono/json>, read 2026-11-16 (the unrelated package).
- conda-forge `linux-64/repodata.json`, licence fields of `mkl`, `cuda-runtime`, `openmpi`, `irrlicht`, `vulkanscenegraph` and `eigen`, read 2026-11-16.
- Pendulum period: T = 4 √(L/g) K(sin(θ0/2)), with K the complete elliptic integral of the first kind; Thornton and Marion, *Classical Dynamics of Particles and Systems*, 5th ed. (2004), section 4.4.

## Decision

Proposed (owner to confirm):

- **Project Chrono is not started in M23 without a trial.** Its licence (BSD-3-Clause) is compatible, and it is maintained, but its CI trial passed in one setting of twelve (Tested), and MuJoCo passed in all six of its settings (see the open question). Run as a separate process in its own conda environment: its dependencies (CUDA, MKL, Open MPI) are large and proprietary in part, and should not enter Ithax's own environment. `Capabilities.licence` `BSD-3-Clause`, `invocation` `process`, `distribution` empty (not a PyPI distribution).
- **Spec 5 version 0.3 details the multibody section on MuJoCo**, as a proposal awaiting the owner's answer to the question below; the benchmark values are closed forms either way.
- **Benchmark values** (L = 1 m, g = 9.80665 m/s², computed by `docs/research/spec-5-trials/benchmarks/expected_values.py`): period 2.010235893 s at 10° and 2.368246346 s at 90° (ratios to the small-angle period 1.001907188 and 1.180340599).

Open questions:

- **Blocking (an engine choice the spec names):** a 536 MB engine with CUDA and MKL for a pendulum is a heavy install. MuJoCo 4.0.1 (Apache-2.0, on PyPI with manylinux wheels) ran the pendulum benchmark in this session to a relative error of about 1e-11 (`spec-5-mujoco.md`). Options: (a) MuJoCo replaces Chrono as spec 5's multibody engine; (b) Chrono stays, as an optional engine installed through conda, after a trial in CI; (c) both, MuJoCo first and Chrono later for contact-rich or vehicle models MuJoCo does not cover. Recommended: (a), with (c) left open for Phase 3.
- **Answered by the CI trial:** the package runs without a GPU for the modules the pendulum uses (Tested).

## Tested

Not in the research container: the session's permission rules refused running a conda tool there (micromamba, although its SHA-256 matched conda-forge's index), the container has no Docker daemon, and PyChrono is not on PyPI. The pendulum was run in CI instead, by the `pychrono` job of `spec5-trials.yml` (#228):

- micromamba 2.0.5 and `pychrono-9.0.1-py312h98ab86c_406.conda` from the `projectchrono` channel, each checked against a pinned SHA-256, failing closed. The job pins 9.0.1, as approved for it, not the newest 10.0.0; 10.0.0 was not run.
- The licence as the installed package declares it was printed in the log: BSD-3-Clause, as under Finding.
- `docs/research/spec-5-trials/chrono/pendulum.py`: a 1 kg body with an inertia of 1e-9 kg m² about its centre, on a revolute joint 1 m above it, released at rest; the period over ten periods of upward zero crossings. Three time steppers, two steps each.

Run 43938942488, head `e94ef9b` (copied from the job log; run 43935773704 at head `d98f5d7`, with the same script, gave the same pattern of passes and failures):

| Amplitude | Time stepper, step | Period (s) | Relative error | Within 1e-6 |
| --- | --- | --- | --- | --- |
| 10° | Euler implicit linearized (default), 1 ms | failed: no crossing in 40 s | | no |
| 10° | Euler implicit linearized, 0.1 ms | failed: no crossing in 40 s | | no |
| 10° | Euler implicit projected, 1 ms | failed: 1 crossing in 40 s | | no |
| 10° | Euler implicit projected, 0.1 ms | 3.029092654 | +5.07e-01 | no |
| 10° | HHT, 1 ms | 2.010238304 | +1.20e-06 | no |
| 10° | HHT, 0.1 ms | failed: minimum step size reached | | no |
| 90° | Euler implicit linearized, 1 ms | 2.368256571 | +4.32e-06 | no |
| 90° | Euler implicit linearized, 0.1 ms | 2.368246453 | +4.53e-08 | yes |
| 90° | Euler implicit projected, 1 ms | 2.327115794 | −1.74e-02 | no |
| 90° | Euler implicit projected, 0.1 ms | 2.363512098 | −2.00e-03 | no |
| 90° | HHT, 1 ms | failed: minimum step size reached | | no |
| 90° | HHT, 0.1 ms | failed: minimum step size reached | | no |

What the run shows:

- **PyChrono installs and runs on a runner without a GPU**, which answers the reversible question above for the CPU-only modules used here.
- **One setting of twelve passed.** The default stepper at 0.1 ms reproduces the 90° period to 4.5e-8, so the engine can meet the gate. The failures at 10° and with HHT are most likely the trial's model and not Chrono: an inertia of 1e-9 kg m² makes the system badly conditioned. A body with a physical inertia, with the exact period computed for a compound pendulum, was not tried.
- **Compared with MuJoCo**, which passed all six of its settings to about 1e-11 on a point mass (`spec-5-mujoco.md`), Chrono needs more care in setting up the same benchmark. This supports the recommendation of option (a), with Chrono left for Phase 3.

The Decision section is revised to cite this trial.
