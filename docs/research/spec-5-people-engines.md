# Spec 5 research: People engines (crowds, pedestrians, biomechanics)

## Question

Spec 5 "People in models", items (b) crowds and pedestrians and (c) human movement and
biomechanics, and the research item "People: open engines and data for pedestrian flow,
biomechanics and ergonomics". Which open engines can Ithax wrap, under what licence, how
well kept, and do they run a small case with a known answer? Candidates: JuPedSim and
Vadere for pedestrians, Mesa for crowds as agents, OpenSim for biomechanics. Also: open
pedestrian trajectory data and open musculoskeletal models. The ergonomics and human
reliability methods, and workforce settings, are in `spec-5-people-methods.md`.

## Finding

### Summary

| | JuPedSim 1.4.2 | Vadere v4.0 | OpenSim 4.6 (build 2) | Mesa 3.5.2 |
| --- | --- | --- | --- | --- |
| What it is | Pedestrian dynamics library: C++ core, Python API; several operational models (collision-free speed, generalized centrifugal force, social force, anticipation velocity, warp driver) | Java crowd simulation framework (GUI and console jar) | Musculoskeletal modelling and simulation (Simbody multibody core; Moco optimal control) | General agent-based modelling library |
| Licence (file read) | LGPL-3.0-or-later: `jupedsim-1.4.2.dist-info/licenses/LICENSE` (14-line notice "either version 3 of the License, or any later version") | LGPL-3.0: `LICENSE` at `gitlab.lrz.de/vadere/vadere`, master, the LGPL version 3 text (165 lines, sha256 `da7eabb7…4768`); README: "licensed under the GNU Lesser General Public License (LGPL)"; "or later" not stated | Apache-2.0 per wheel metadata (`License: Apache 2.0`); the wheel holds no licence file (see below) | Apache-2.0: `mesa-3.5.2.dist-info/licenses/LICENSE` and `NOTICE` |
| AGPL-3.0 combined work | Compatible; in-process import allowed | Compatible; Java, so a separate process anyway | Not settled: bundled Ipopt is EPL (see below); separate process | Compatible; in-process |
| Latest release | 1.4.2, 2026-05-21 | v4.0 tag 2026-04-07, release 2026-04-09; last master commit 2026-11-12 | 4.6 (builds -1 2026-04-26, -2 2026-06-23); the only PyPI release of 4.x | 3.5.2, 2026-10-28 |
| Releases since 2024-11-16 | 6 (1.3.0 2025-03-20 to 1.4.2) | 1 tagged release (v4.0) | 1 (4.6, two builds) | 16 (3.1.0 to 3.5.2, with 4.0.0a0) |
| Python | `>=3.10,<3.15`; wheels cp310 to cp314 | none (Java 17.0.11 or above, README) | wheels cp311 to cp313; none for 3.14 | `>=3.12` |
| Linux wheels | manylinux_2_27/2_28 x86_64 (0.9 MB); no aarch64 | n/a (jar) | manylinux_2_27/2_28 x86_64 (72 MB) | pure Python |
| WSL 2 | Yes (manylinux) | Needs a Java runtime; not tried | Yes (manylinux); imports and runs headless here | Yes |
| Trial run here | Yes (room exit, below) | Not run | Yes (pendulum, below) | Import only; see `spec-5-mesa.md` |

All PyPI facts from `https://pypi.org/pypi/<pkg>/json`, read 2026-11-16. Licence files read
2026-11-16 from the wheels installed with `uv pip install` into a scratch virtual environment.

### JuPedSim

- Declared dependencies: `numpy~=2.2`, `shapely~=2.0`, `pyside6~=6.8`, `vtk~=9.4`,
  `deprecated~=1.2.18` (wheel `METADATA`). PySide6 (673 MB installed; `LGPL-3.0-only OR
  GPL-2.0-only OR GPL-3.0-only`) and VTK (564 MB; BSD) serve its viewer: `import jupedsim`
  loads neither (checked: `'PySide6' in sys.modules` is `False`). Installed with `--no-deps`
  plus numpy, shapely, deprecated and wrapt, the environment is 64 MB and a one-agent run
  works (one agent crossing 8 m at the default 1.2 m/s leaves at t = 6.69 s). An adapter can
  install it that way; the environment manager must then pin the four dependencies itself.
- API: geometry as shapely polygons; `Simulation(model, geometry, dt)`; stages (exit,
  waypoint, waiting set, queue) and journeys; `add_agent(params)`; `iterate()`; agent
  positions readable each step; trajectory writers to SQLite or HDF5.
- Room exit trial (see Tested): with default parameters the collision-free speed model (CSM)
  gives specific flows of 0.98 to 1.19 persons/(m·s) through doors 1.0 to 2.0 m wide, below
  the published range; with the agents' `time_gap` at 0.5 s it gives 1.62 to 1.84. Published
  reference: Seyfried et al. (PED 2008, arXiv:0810.1945) state that the maximum specific flow
  Js,max of planning guidelines (SFPE handbook, Predtechenskii and Milinskii, Weidmann) and
  measurements "ranges from 1.2 (ms)−1 to 1.8 (ms)−1", and their Fig. 2 draws the bottleneck
  flow against width with a line marked "1.9 w", with flow "almost linear" in width for
  w > 0.6 m. So the engine reproduces the published range only after calibration; the
  default does not.
- At 0.8 m the collision-free speed model jammed: with the default time gap 11 of 150
  agents passed in 600 s; with 0.5 s, 73 of 150. Every generalized centrifugal force model
  run stopped with the engine error "Point (…) is outside of accessible area" after agents
  entered the corridor. These are engine behaviours an adapter must report as issues, not
  hide.

### Vadere

- Source and licence at `https://gitlab.lrz.de/vadere/vadere` (project created 2016-08-05,
  last activity 2026-11-13, public). The address `gitlab.com/vadere/vadere` answers
  "404 Project Not Found" on its API.
- Pre-built `vadere-console.jar` runs `java -jar vadere-console.jar scenario-run -f <scenario>
  -o <output>` (README), so an adapter would be a separate process exchanging scenario
  JSON and output files, which fits spec 1's engine licence rule.
- Not run: this session may not run downloaded binaries other than pip-installed Python
  packages, and a jar is one. No Python package exists.

### OpenSim

- Wheel contents: `opensim/` (218 MB) and `opensim.libs/` (58 MB). Bundled native libraries
  include Simbody 3.9, CasADi 3.7, Ipopt 3.14.16, MUMPS (`libcoinmumps` 3.0.5), METIS,
  OpenBLAS, LAPACK, libgfortran, freeglut, libGLU and X11 libraries (from the file listing
  and `opensim-4.6.dist-info/sboms/auditwheel.cdx.json`; the SBOM lists only the system
  libraries and gives no licences).
- No `LICENSE`, `NOTICE` or third-party licence file is in the wheel (`RECORD` searched).
  OpenSim's documentation page "License for OpenSim 4.0 and Later" (read 2026-11-16): "The
  OpenSim Application Programming Interface (API) is fully open source and licensed under
  the Apache 2.0 license"; "Models, examples and plugins retain their own custom licenses".
  Its "Acknowledgements" page lists Simbody (Apache 2.0), IPOPT (EPL-1.0), docopt.cpp (MIT),
  OpenMM Lepton (MIT); it does not list CasADi, MUMPS or METIS. CasADi on PyPI (3.8.2
  metadata) is LGPL-3.0-or-later. Unverified: the licence of the bundled Ipopt 3.14.16 (the
  page says EPL-1.0; newer Ipopt releases may be EPL-2.0) and of MUMPS and METIS.
- Consequence: EPL-1.0 is listed by the FSF as incompatible with the GPL (not re-read
  today; unverified here), so importing
  OpenSim into the AGPL service process is not cleared. Run it as a separate worker
  process. A lawyer confirms before release, as spec 1 already says for every engine.
- No model files (`.osim`) are in the wheel, so "arm26" was not available; the trial built
  its own model through the API.
- Pendulum trial (see Tested): period matches the exact large-amplitude formula to a
  relative 5e-12 at 10° and 2e-11 at 90°.

### Mesa for crowds

- Mesa 3.5.2 offers `ContinuousSpace`, grids, `VoronoiGrid` and `Network` spaces, but no
  pedestrian movement model. A crowd in Mesa means writing the movement rule; a
  force-based rule (social force) integrates an equation of motion step by step, which is
  close to "never write a numerical solver" (build guide rule 7). Simple grid rules
  (cellular automaton floor fields) are rules, not solvers, but are a model of their own to
  verify against data. Engine status and licence of Mesa are in `spec-5-mesa.md`.

### Data

- Jülich pedestrian dynamics data archive, `https://ped.fz-juelich.de/da/` (DOI
  10.34735/ped.da): the wiki footer reads "Except where otherwise noted, content on this
  wiki is licensed under the following license: CC Attribution 4.0 International" (read
  2026-11-16). Holds bottleneck, corridor and other experiments with trajectories (e.g.
  "2005 Jülich bottleneck", per search results; individual dataset pages and their
  licences not read). Usable for benchmark data with attribution; check each dataset's
  page.
- OpenSim models: per the licence page, each model keeps its own licence; none read.
  Unverified which common models (gait2392, Rajagopal 2015, arm26) permit redistribution
  in templates.

## Sources

- PyPI JSON for `jupedsim`, `opensim`, `mesa`, `casadi`, read 2026-11-16.
- Wheel files: `jupedsim-1.4.2.dist-info/licenses/LICENSE`, `METADATA`;
  `opensim-4.6.dist-info/METADATA`, `RECORD`, `sboms/auditwheel.cdx.json`;
  `mesa-3.5.2.dist-info/licenses/LICENSE`, `NOTICE`; `pyside6-6.12.0.dist-info/METADATA`;
  `vtk-9.7.2.dist-info/METADATA`.
- Vadere: `https://gitlab.lrz.de/vadere/vadere/-/raw/master/LICENSE`, `README.md`; GitLab
  API `projects/vadere%2Fvadere` (project, tags, releases, commits), read 2026-11-16;
  `https://www.vadere.org/` (search result: LGPL).
- OpenSim: "License for OpenSim 4.0 and Later",
  `https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53086437`; "Acknowledgements",
  `https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53085061`; read 2026-11-16.
- A. Seyfried, M. Boltes, J. Kähler, W. Klingsch, A. Portz, T. Rupprecht, A. Schadschneider,
  B. Steffen, A. Winkens, "Enhanced empirical data for the fundamental diagram and the flow
  through bottlenecks", Pedestrian and Evacuation Dynamics 2008, Springer;
  arXiv:0810.1945, pages 3 to 5 read 2026-11-16.
- JuPedSim's model papers (collision-free speed model and others): not read.
- Jülich pedestrian dynamics data archive, `https://ped.fz-juelich.de/da/doku.php`, read
  2026-11-16.

## Decision

Proposed defaults (owner to confirm):

- **(b) Crowds: JuPedSim as the pedestrian engine**, in-process (LGPL-3.0-or-later),
  installed without its viewer dependencies (`--no-deps` plus numpy, shapely, deprecated,
  pinned by the environment manager). Mesa stays for crowds as general agents (customers,
  epidemics) on grids or networks, not for walking dynamics, so that Ithax writes no force
  model of its own. This departs from spec 5's "Mesa first" for pedestrians.
- **Pedestrian benchmark:** room exit through one door, flow within the published range
  1.2 to 1.8 persons/(m·s) (Seyfried et al. 2008) once the model is calibrated, plus a
  Jülich archive bottleneck experiment (CC BY 4.0) as a second case. The engine's default
  parameters do not reach the range, so templates carry calibrated settings and say so.
- **Vadere: deferred.** Java, separate process; a second pedestrian engine is not needed
  while JuPedSim covers the domain. Revisit if a user needs its locomotion or
  psychology layers.
- **(c) Biomechanics: OpenSim in Phase 3**, as a separate worker process (the bundled
  Ipopt is EPL, not cleared for an AGPL combined work), Linux x86_64 and Python 3.11 to
  3.13 only. Phase 2 has no biomechanics engine; ergonomics in Phase 2 is calculators only
  (methods note).
- **Phases:** Phase 2: JuPedSim adapter with 2D polygon geometry, exit, waypoint and
  waiting stages, flow and evacuation-time metrics; Mesa agent models. Phase 3: OpenSim.

Open questions, blocking:

- Pedestrians on JuPedSim rather than Mesa first (changes spec 5's engine choice and the
  Phase 2 milestone content).
- A pedestrian domain needs 2D geometry (room and corridor polygons) in the model file;
  spec 5 puts geometry needs in spec 6. Is 2D polygon geometry in scope for Phase 2
  (model format)?
- OpenSim in Phase 3 only, Linux x86_64 only (target platform).

Open questions, reversible:

- Whether the adapter reports a jam (agents left at the time limit) as a run issue or a
  result; proposed: an issue with a code and the count left.
- Which JuPedSim operational model is the default; proposed: collision-free speed model
  (the generalized centrifugal force model failed every case here).
- Licences of the bundled Ipopt, MUMPS and METIS in the OpenSim wheel, and of each OpenSim
  model a template would ship; to read from their sources before Phase 3.

## Tested

All on 2026-11-16, Python 3.12, in a scratch virtual environment, `jupedsim==1.4.2`,
`opensim==4.6` (wheel build 2, `opensim.GetVersion()` = `4.6-2026-06-22-85aaf64`),
`mesa==3.5.2`, `numpy==2.5.5`, `shapely==2.2.0`, `scipy==1.18.1`.

- `docs/research/spec-5-trials/people-jupedsim/room_exit.py`, output in `output.txt`
  beside it. 150 agents in a 10 m × 10 m room leave through one door into a 4 m corridor,
  dt 0.01 s, seed 1; the script counts crossings of the door line and takes the specific
  flow over crossings 10 to 140. Results (persons/(m·s)):

  | Door width (m) | CSM, time gap 1.0 s (default) | CSM, time gap 0.5 s | Generalized centrifugal force model |
  | --- | --- | --- | --- |
  | 0.8 | jam: 11 of 150 out in 600 s | jam: 73 of 150 out; 1.294 over those | engine error |
  | 1.0 | 0.979 (evacuation 155.39 s) | 1.616 (96.24 s) | engine error |
  | 1.2 | 1.060 (121.39 s) | 1.714 (78.14 s) | engine error |
  | 1.6 | 1.185 (84.22 s) | 1.839 (56.29 s) | engine error |
  | 2.0 | 1.139 (70.84 s) | 1.739 (47.80 s) | engine error |

  Compared with the published 1.2 to 1.8 (ms)−1: default below it in every case; time gap
  0.5 s inside it except 1.839 at 1.6 m, just above. Wall time 3.3 to 11.5 s per completed
  case, 42 to 82 s for the jams.
- Lean install: `jupedsim==1.4.2 --no-deps` with numpy, shapely, deprecated, wrapt: 64 MB,
  one agent run completed (t = 6.69 s).
- `docs/research/spec-5-trials/people-opensim/pendulum.py`, output in `output.txt`. A 1 kg
  point mass on a 1 m pin joint, g = 9.80665 m/s², integrator accuracy 1e-10, sampled every
  1 ms for 10 s; period from zero crossings. Known answer T = 4√(L/g) K(sin(θ0/2)) (spec 5
  pendulum benchmark), K from `scipy.special.ellipk`:

  | θ0 | OpenSim (s) | Exact (s) | Relative error |
  | --- | --- | --- | --- |
  | 10° | 2.010236 | 2.010236 | −4.87e-12 |
  | 90° | 2.368246 | 2.368246 | −2.17e-11 |

  Small-angle period 2π√(L/g) = 2.006409 s for reference. An energy check from the
  recorded angle gives 3.27e-06 relative, limited by the script's own finite-difference
  speed, not the engine. OpenSim prints an info block per `integrate()` call and by default
  writes `opensim.log` into the working folder (16 MB in a first run here); the script sets
  `osim.Logger.setLevelString("warn")` and calls `osim.Logger.removeFileSink()`. An adapter
  must do the same so that the engine writes only inside its run folder.
- Mesa: imported, spaces listed; no crowd run (see `spec-5-mesa.md` for the Mesa trial).
- Not run: Vadere (a downloaded jar may not be run here); OpenSim's arm26 or any shipped
  model (none in the wheel); JuPedSim's social force, anticipation velocity and warp driver
  models; any Jülich archive dataset (none downloaded).
