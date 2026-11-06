# Spec 6: Physics Platform

> Version 0.2 · structure only · working copy in the repository (source of truth, owner to confirm) · changes are listed under "Changes in this version".

Phase 3 builds the shared services every physics solver needs once, then adds solver families one annex at a time. The shared services are the larger half of the work.

> **Warning: structure only. Do not implement from this spec as it stands.** It has no detailed specification section, because no physics engine has been installed or tested, and writing field-level detail now would be guesswork. Before any Phase 3 code: complete the research items below, then write a detailed section for the shared services and a separate spec for each annex. Open material data is scarce and will limit annexes D and E. See "Known gaps" in the Build guide.

## Scope

- **In:** geometry, meshing, boundary tagging, material data, the 3D results viewer, resource estimation, solver coupling, and the annex structure.
- **Out:** the list of physical effects and which engine provides each (spec 7).

## Shared services

| Service | Does | Proposed basis |
| --- | --- | --- |
| Geometry | Imports STEP files; builds simple shapes from parameters; 2D sketches for flat and axisymmetric models | OpenCASCADE through a Python layer |
| Named regions | Lets the user click faces and volumes and name them: "inlet", "clamped end", "die surface" | Product code; names carry through to every solver |
| Meshing | Generates the mesh from geometry and a size preset | Gmsh |
| Material data | A library of materials with the properties each physics option needs, plus import of user data | Product code; open data where it exists |
| Results viewer | Started in Phase 2 for the multibody preview; shows fields on the 3D model, with slices, probes and animation | VTK through PyVista |
| Resource estimator | Predicts memory and run time from the mesh before the run starts | Product code, calibrated per engine |
| Coupling | Runs two solvers together across a shared surface | preCICE |

## How a physics model reads in the model file

Spec 1's format gains four keys for physics domains: `geometry`, `regions`, `materials` and `physics`. The `physics` key lists options from the spec 7 catalogue, each bound to named regions. Loads and constraints are also bound to named regions, never to mesh numbers, so they survive remeshing.

## Fidelity ladder

| Level | Meaning | Typical tier |
| --- | --- | --- |
| Sketch | 1D beam or truss, 2D or axisymmetric, coarse mesh, seconds to minutes | Low |
| Standard | 3D, moderate mesh | Mid |
| Detailed | 3D, fine mesh, full physics | High or cluster |

Before each run the estimator compares the need with the machine. If the run will not fit, the app offers a lower level or a remote target. It never starts a run it expects to fail.

## Field-solver adapter contract

Physics adapters implement the spec 1 contract and declare four more things:

- Which catalogue entries they support.
- Mesh requirements: element types, quality limits.
- Parallel modes: threads, multiple processes, graphics acceleration.
- A memory and time model for the estimator.

## Annexes

Each annex is its own short spec, written when its turn comes.

| Annex | Covers | First engine | Then | Licence (checked / unverified) |
| --- | --- | --- | --- | --- |
| A | Structural and thermal, with contact and friction | CalculiX | Code\_Aster | CalculiX GPL-2 (only vs or-later unverified); Code\_Aster unverified |
| B | Fluid flow and coupled heat transfer | OpenFOAM (line to choose: Foundation or ESI) | SU2 | OpenFOAM, SU2 unverified |
| C | Explicit dynamics and sheet forming | OpenRadioss successor to be chosen: upstream repository reported removed in October 2026 (press report); OpenCourant fork (AGPL-3.0, reported) is the candidate | None identified; find a second explicit solver during annex C research | OpenCourant AGPL-3.0 reported, not read |
| D | Bulk forming with automatic remeshing | Built on annex A or C engines |  | As annexes A and C |
| E | Materials and metallurgy | pycalphad, Code\_Aster metallurgy | DAMASK | pycalphad MIT (PyPI); DAMASK AGPL-3.0 (LICENSE read 2026-11-05); Code\_Aster unverified |
| F | Particles and bulk solids | Yade (to confirm); LIGGGHTS-PUBLIC only if Yade lacks a feature (public repository reported dormant since 2023; not verifiable from this session) | MFiX (licence unverified; registration-gated download, so not installable by the environment manager until confirmed); OpenFOAM Lagrangian solvers as fallback (unverified) | Yade unverified; LIGGGHTS GPL-2.0-or-later (reported by the review, not re-read by the chair); MFiX unverified |
| G | Electromagnetics | Elmer | openEMS | Elmer, openEMS unverified. FEMM dropped: Aladdin Free Public License, read at femm.info on 2026-11-05, forbids paid distribution and is Windows-only |
| H | Chemical process flowsheets | DWSIM |  | DWSIM GPL-3.0 (reported by the review, not re-read by the chair) |
| I | Casting, welding and additive manufacturing | OpenFOAM-based solvers, AdditiveFOAM (requires OpenFOAM-14, Foundation line; README read 2026-11-05) |  | AdditiveFOAM GPL-3.0-or-later (README read 2026-11-05) |

Shared services: Gmsh GPL-2.0-or-later with linking exception (gmsh.info/LICENSE.txt read 2026-11-05); preCICE, Code\_Saturne unverified. OpenModelica (spec 5) AGPL-3.0 or OSMC-PL, reported by the review, not re-read by the chair.

Annex D is a build item, not a wrapper. It needs a loop that detects mesh distortion, remeshes, and carries results across to the new mesh.

## Benchmarks

| Annex | Case | Known answer |
| --- | --- | --- |
| A | Cantilever beam under end load | Beam theory deflection |
| A | Plate with a circular hole in tension | Stress concentration factor near 3 |
| A | Heated bar with fixed ends | Thermal stress formula |
| A | Simply supported beam, first natural frequency | Euler–Bernoulli beam formula |
| A | Pinned column under axial load | Euler buckling load |
| B | Flow in a straight pipe | Parabolic velocity profile and pressure drop |
| B | Lid-driven cavity | Published reference velocities |
| C | Cylinder impact on a rigid wall | Published final length |
| D | Upsetting of a cylinder | Published force and barrelling |
| E | Iron-carbon phase diagram | Published phase boundaries, using an openly licensed Fe–C database identified in the annex E research note |
| E | End-quench test | Published hardness profile, for a steel whose composition and published curve may be reproduced |

Published engineering benchmark sets, such as those from NAFEMS, are added per annex.

## Research before building

Complete these and record the findings, with sources, in a short note in the repository before writing code. If a finding contradicts this spec, update the spec first.

For the shared services:

- **Geometry layer.** Compare the Python layers over OpenCASCADE, and FreeCAD used as a library.
- **Meshing.** Gmsh's Python interface, quality controls and limits; alternatives for hexahedral meshes.
- **Mesh and result formats.** Conversion tools between solver formats, and what each loses.
- **Viewer.** Options for embedding a 3D results view in the chosen interface framework.
- **Estimation.** Published memory and time scaling for each solver type.

For each annex, before its own spec is written:

- **Install and run.** Does the engine install cleanly under WSL, and how is it driven from Python?
- **Input format.** What the adapter must write, and how errors are reported.
- **Benchmarks.** Published cases with reference answers, including the engine's own test suite.
- **Interface study.** How existing front ends for that engine guide setup.
- **Licence.** Read the engine's own licence file; record SPDX id, "only" or "or later", and any bundled non-free component.
- **Literature.** Recent papers on the hardest part of that annex. For annex D, automatic remeshing and transfer of results between meshes. For annex C, which OpenRadioss successor is maintained, whether it builds without proprietary pieces, and whether any second open explicit solver exists.
- **Annex B, OpenFOAM line.** Foundation or ESI: which the annex I solvers need, which installs under WSL, whether both can coexist.
- **Annex F.** Compare Yade, LIGGGHTS-PUBLIC and the LAMMPS GRANULAR package on upkeep, Python driving and licence; licence and distribution of MFiX.

## Acceptance tests

- [ ] A STEP part is imported, regions named, meshed and viewed without leaving the app.
- [ ] Region names survive a remesh at a different size.
- [ ] The estimator's memory prediction is within a factor of two on the annex A benchmarks.
- [ ] Every Sketch-level template runs on the low tier.
- [ ] Annex A passes its benchmarks before annex B work starts.

## Changes in this version

2026-11-05, version 0.2, spec review council:

- C29 (PHY-1, PHY-2, PHY-3, PHY-4, PHY-5, PHY-6, PHY-8, PHY-12, PHY-13, PHY-17): version line; annex engines revised (OpenFOAM line, OpenRadioss successor, Yade first, MFiX status, FEMM dropped, AdditiveFOAM requirement); licence column with checked and unverified entries; viewer started in Phase 2; Sketch includes 1D; beam and column benchmarks; annex E data conditions; licence, OpenFOAM line, annex C and annex F research items.
