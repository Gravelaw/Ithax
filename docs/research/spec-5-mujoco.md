# Spec 5 research: MuJoCo as a multibody engine

## Question

Project Chrono, spec 5's multibody engine, ships only as a 536 MB conda package with CUDA and MKL and could not be run in the research container (`spec-5-chrono.md`). Is there a lighter engine that installs from PyPI, has a compatible licence and reproduces the pendulum benchmark?

## Finding

Read on 2026-11-16.

- **Version.** MuJoCo 4.0.1, uploaded to PyPI on 2026-11-11, five days after 4.0.0. A major version is new, so its API should be watched.
- **Licence.** Apache-2.0. Read from `mujoco-4.0.1.dist-info/licenses/LICENSE` as installed from PyPI; `License-Expression: Apache-2.0` in `METADATA`. The two native parts, `mujoco-core` 4.0.1 and `mujoco-studio` 4.0.1, are also `Apache-2.0` with their own `LICENSE` and `LICENSES_THIRD_PARTY.md`. The third-party list names Abseil, cereal, Eigen (MPL-2.0), {fmt}, GLAD, GLFW, libccd, the LLVM runtime libraries, LodePNG, MarchingCubeCpp, GLM, pybind11, Qhull, TinyOBJLoader, TinyXML2, miniz, Dear ImGui, ImPlot, two fonts, Filament and SDL2. None is a GPL licence for a combined work; MPL-2.0 is file-level copyleft and compatible with AGPL-3.0. MuJoCo may be imported in-process under the spec 1 rule.
- **Upkeep.** 27 releases between 2024-11-16 and 2026-11-16 (PyPI JSON). Developed by Google DeepMind.
- **Python.** `requires_python >=3.11`, matching Ithax.
- **Linux and WSL 2.** manylinux_2_27/2_28 x86_64 wheels for CPython 3.12 (tag in `WHEEL`). The scratch environment with MuJoCo, numpy and scipy took 244 MB. Under WSL 2 it installs with pip as on Linux. Simulation needs no display; the bundled viewer needs OpenGL, which WSL 2 has through WSLg, but Ithax would not use it (spec 5: the preview uses spec 6's viewer basis).
- **Model format.** MJCF, an XML format, read with `MjModel.from_xml_string`. Bodies, joints (hinge, slide, ball, free), inertials, springs and dampers on joints, tendons, actuators and contacts are elements of MJCF, so an adapter can write MJCF from the model file's components into its run folder, as the process adapter writes `engine/input.json`.
- **Integrators.** `Euler` (semi-implicit), `RK4`, `implicit` and `implicitfast`, chosen per model with a fixed time step (`<option timestep>`).
- **Scope against Chrono.** Chrono has vehicle, granular and finite-element modules MuJoCo lacks. MuJoCo targets rigid bodies with joints and contacts, which covers spec 5's examples of linkages and simple mechanisms; whether it covers conveyors and vehicles was not checked.

## Sources

- PyPI JSON, <https://pypi.org/pypi/mujoco/json>, read 2026-11-16.
- MuJoCo 4.0.1 as installed: `mujoco-4.0.1.dist-info/licenses/LICENSE`, `LICENSES_THIRD_PARTY.md`, `METADATA`; `mujoco_core-4.0.1.dist-info`, `mujoco_studio-4.0.1.dist-info`.
- Pendulum period: as in `spec-5-chrono.md` (Thornton and Marion, section 4.4).

## Decision

Proposed (owner to confirm, see the blocking question in `spec-5-chrono.md`):

- **MuJoCo is the Phase 2 multibody engine**, in place of Project Chrono, imported in-process (Apache-2.0); `Capabilities.licence` `Apache-2.0`, `invocation` `in-process`, `distribution` `mujoco`; pinned to the 4.0 series.
- **The adapter writes MJCF** from bodies, joints and force elements in the model file, never from user XML, so a project holds data only.
- **Integrator.** `RK4` with a stated time step by default; the label names both.
- **Benchmark tolerance.** From the trial: the pendulum period within a relative 1e-6 of the exact value at 10° and 90°, with RK4 and a step of 1 ms. The trial reached about 1e-11, so the tolerance leaves room for a different measurement of the period.

Open questions:

- **Reversible:** whether conveyors and vehicles (spec 5's examples) need Chrono's modules. Checked at M23 against the templates it writes.

## Tested

`docs/research/spec-5-trials/mujoco/trial_pendulum.py`, output in `output.txt`. MuJoCo 4.0.1, numpy 2.5.5, scipy, Python 3.12, in a scratch virtual environment.

- **Case.** A 1 kg point mass on a massless rod of 1 m, a hinge without damping, g = 9.80665 m/s², released at rest; the period from ten periods of upward zero crossings, linearly interpolated.

  | Amplitude | Integrator, step | Period (s) | Exact (s) | Relative error |
  | --- | --- | --- | --- | --- |
  | 10° | RK4, 1 ms | 2.010235893 | 2.010235893 | +1.04e-11 |
  | 10° | RK4, 0.1 ms | 2.010235893 | 2.010235893 | −1.32e-12 |
  | 10° | Euler, 0.1 ms | 2.010235885 | 2.010235893 | −4.03e-09 |
  | 90° | RK4, 1 ms | 2.368246346 | 2.368246346 | −1.00e-11 |
  | 90° | RK4, 0.1 ms | 2.368246346 | 2.368246346 | −1.42e-12 |
  | 90° | Euler, 0.1 ms | 2.368246346 | 2.368246346 | −1.43e-12 |

- **Time.** 5.2 s for the six runs.
- **Not tried:** contacts, closed kinematic loops, and a model with several bodies.
