# Spec 6: Physics Platform

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
| Results viewer | Shows fields on the 3D model, with slices, probes and animation | VTK through PyVista |
| Resource estimator | Predicts memory and run time from the mesh before the run starts | Product code, calibrated per engine |
| Coupling | Runs two solvers together across a shared surface | preCICE |

## How a physics model reads in the model file

Spec 1's format gains four keys for physics domains: `geometry`, `regions`, `materials` and `physics`. The `physics` key lists options from the spec 7 catalogue, each bound to named regions. Loads and constraints are also bound to named regions, never to mesh numbers, so they survive remeshing.

## Fidelity ladder

| Level | Meaning | Typical tier |
| --- | --- | --- |
| Sketch | 2D or axisymmetric, coarse mesh, seconds to minutes | Low |
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

| Annex | Covers | First engine | Then |
| --- | --- | --- | --- |
| A | Structural and thermal, with contact and friction | CalculiX | Code\_Aster |
| B | Fluid flow and coupled heat transfer | OpenFOAM | SU2 |
| C | Explicit dynamics and sheet forming | OpenRadioss |  |
| D | Bulk forming with automatic remeshing | Built on annex A or C engines |  |
| E | Materials and metallurgy | pycalphad, Code\_Aster metallurgy | DAMASK |
| F | Particles and bulk solids | LIGGGHTS or Yade | MFiX |
| G | Electromagnetics | Elmer | openEMS, FEMM |
| H | Chemical process flowsheets | DWSIM |  |
| I | Casting, welding and additive manufacturing | OpenFOAM-based solvers, AdditiveFOAM |  |

Annex D is a build item, not a wrapper. It needs a loop that detects mesh distortion, remeshes, and carries results across to the new mesh.

## Benchmarks

| Annex | Case | Known answer |
| --- | --- | --- |
| A | Cantilever beam under end load | Beam theory deflection |
| A | Plate with a circular hole in tension | Stress concentration factor near 3 |
| A | Heated bar with fixed ends | Thermal stress formula |
| B | Flow in a straight pipe | Parabolic velocity profile and pressure drop |
| B | Lid-driven cavity | Published reference velocities |
| C | Cylinder impact on a rigid wall | Published final length |
| D | Upsetting of a cylinder | Published force and barrelling |
| E | Iron-carbon phase diagram | Published phase boundaries |
| E | End-quench test | Published hardness profile |

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
- **Literature.** Recent papers on the hardest part of that annex. For annex D, automatic remeshing and transfer of results between meshes. For annex C, which OpenRadioss line is maintained.

## Acceptance tests

- [ ] A STEP part is imported, regions named, meshed and viewed without leaving the app.
- [ ] Region names survive a remesh at a different size.
- [ ] The estimator's memory prediction is within a factor of two on the annex A benchmarks.
- [ ] Every Sketch-level template runs on the low tier.
- [ ] Annex A passes its benchmarks before annex B work starts.
