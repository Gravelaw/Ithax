# Spec 7: Physics and Forces Catalogue

> Version 0.2 · structure only · working copy in the repository (source of truth, owner to confirm) · changes are listed under "Changes in this version".

This is the master list of physical effects the product will offer, the standard model for each, and the engine that provides it. Each entry becomes a selectable physics option in the model file.

The annex column refers to spec 6. Engine assignments are a first mapping from the research and from general knowledge of each engine; none has been tested yet. "To confirm" marks the entries I am least sure of.

> **Warning: an untested first mapping.** No engine assignment in this catalogue has been confirmed by running the engine. Injection moulding, acoustics, lubrication and precipitation in alloys were never researched. Confirm each entry by test when its annex is written, and update this catalogue. See "Known gaps" in the Build guide.

## Loads and forces

| Effect | Standard model | Engine | Annex |
| --- | --- | --- | --- |
| Gravity, inertia, centrifugal force | Body forces | CalculiX | A |
| Point force, moment, pressure, hydrostatic pressure, surface traction | Applied loads on named regions | CalculiX | A |
| Bolt pre-tension | Pre-tension section | CalculiX | A |
| Springs and dampers | Linear and nonlinear elements | Project Chrono, CalculiX | Phase 2, A |
| Joint and constraint forces in mechanisms | Multibody equations | Project Chrono | Phase 2 |
| Thermal expansion | Thermal strain | CalculiX, Code\_Aster | A |
| Drag, lift and pressure loads from flow | Computed from the flow solution | OpenFOAM, SU2 | B |
| Buoyancy and natural convection | Density variation with temperature | OpenFOAM | B |
| Surface tension and free surfaces | Volume-of-fluid method | OpenFOAM | B, I |
| Impact and shock | Explicit time integration | OpenRadioss (line to confirm) | C |
| Magnetic and electric forces | Maxwell's equations | Elmer | G |
| Trusses, beams and frames | 1D beam and truss elements | CalculiX, Code\_Aster (to confirm) | A |

## Vibration, stability and dynamics

| Effect | Standard model | Engine | Annex |
| --- | --- | --- | --- |
| Natural frequencies and mode shapes | Eigenvalue analysis | CalculiX, Code\_Aster (to confirm) | A |
| Buckling load | Linear eigenvalue buckling | CalculiX, Code\_Aster (to confirm) | A |
| Response at a set frequency | Harmonic analysis with damping | CalculiX, Code\_Aster (to confirm) | A |
| Response to a time-varying load | Implicit transient dynamics, modal or direct | CalculiX, Code\_Aster (to confirm) | A |

## Contact, friction and wear

| Effect | Standard model | Engine | Annex |
| --- | --- | --- | --- |
| Contact between bodies | Penalty or constraint methods | CalculiX, Code\_Aster, OpenRadioss (line to confirm) | A, C |
| Sliding friction | Coulomb law | CalculiX, Code\_Aster, OpenRadioss (line to confirm) | A, C |
| Friction in forming at high pressure | Shear-factor (Tresca) law | To confirm | D |
| Heat from friction | Frictional work added to the heat equation | To confirm | D |
| Wear of tools and surfaces | Archard law, computed from contact pressure and sliding distance | Product code (calculator) on solver output | A, D |
| Lubricated contact | Reynolds equation | Not yet researched | Later |

## Material behaviour

| Effect | Standard model | Engine | Annex |
| --- | --- | --- | --- |
| Elastic deformation | Linear elasticity, isotropic or directional | CalculiX | A |
| Permanent deformation | Von Mises plasticity with hardening | CalculiX, Code\_Aster | A |
| Flow stress dependent on strain rate and temperature | Johnson-Cook, Hensel-Spittel | OpenRadioss (line to confirm); forming engines to confirm | C, D |
| Slow deformation under load | Creep laws such as Norton | Code\_Aster, CalculiX | A |
| Rubber-like behaviour | Hyperelastic models | CalculiX | A |
| Time-dependent stiffness | Viscoelastic models | CalculiX (partial) | A |
| Damage and fracture | Failure criteria with element removal | OpenRadioss (line to confirm) | C |
| Fatigue life | Stress-life and strain-life curves | Product code (calculator) on solver output | A |
| Grain-scale deformation and texture | Crystal plasticity | DAMASK | E |
| Layered and directional materials | Orthotropic elasticity; layered shells | CalculiX, Code\_Aster (to confirm) | A |

## Heat

| Effect | Standard model | Engine | Annex |
| --- | --- | --- | --- |
| Conduction | Fourier's law | CalculiX | A |
| Surface convection, radiation, applied heat flux | Boundary conditions on named regions | CalculiX | A |
| Radiation between surfaces | View-factor (cavity) radiation | CalculiX (to confirm) | A |
| Heat exchange between fluid and solid | Multi-region conjugate heat transfer in one solver; two solvers coupled when the solid also needs stress | OpenFOAM multi-region solver (to confirm); OpenFOAM with CalculiX through preCICE | B |
| Melting and solidification | Enthalpy method with latent heat | OpenFOAM-based solvers | I |
| Heat from plastic work | Fraction of plastic work added as heat | To confirm | D |
| Induction and resistance heating | Eddy currents coupled to heat | Elmer | G |

## Fluids

| Effect | Standard model | Engine | Annex |
| --- | --- | --- | --- |
| Laminar and turbulent flow | Navier-Stokes with turbulence models | OpenFOAM, Code\_Saturne | B |
| High-speed compressible flow, shape optimization | Compressible solvers with adjoint method | SU2 | B |
| Two fluids with an interface | Volume-of-fluid method | OpenFOAM | B |
| Non-Newtonian fluids, porous media, rotating machinery | Solver options | OpenFOAM | B |
| Fluid-structure interaction | Coupled solvers | preCICE | B |
| Particles carried by a fluid | Coupled particle and flow solvers | MFiX, to confirm; OpenFOAM Lagrangian solvers as fallback (unverified) | F |

## Materials and metallurgy

| Effect | Standard model | Engine | Annex |
| --- | --- | --- | --- |
| Phase diagrams and phase fractions at equilibrium | CALPHAD method | [pycalphad](https://github.com/pycalphad/pycalphad) (project organisation; MIT per PyPI, read 2026-11-05) | E |
| Phase change during cooling and heating | Transformation kinetics: Johnson-Mehl-Avrami-Kolmogorov, Koistinen-Marburger | Code\_Aster (metallurgy operators; documentation reference added at annex E research) | E |
| Hardness after heat treatment | Mixture rule over phase fractions | Code\_Aster | E |
| Residual stress and distortion from quenching | Coupled thermal, metallurgical and mechanical analysis | Code\_Aster | E |
| Carbon diffusion in case hardening | Fick's laws | To confirm | E |
| Recrystallization and grain growth in hot forming | Semi-empirical kinetic models | Product code (calculator) on solver output; [DAMASK](https://www.mpie.de/4981753/damask-3?c=4197887) for research use | D, E |
| Grain structure from solidification | Cellular automata on thermal history | [AdditiveFOAM](https://github.com/ORNL/AdditiveFOAM) with ExaCA | I |
| Precipitation and ageing | Nucleation and growth models | Not yet researched | E |

## Electromagnetics and particles

| Effect | Standard model | Engine | Annex |
| --- | --- | --- | --- |
| Static electric and magnetic fields, eddy currents | Low-frequency Maxwell | Elmer (2D and 3D) | G |
| Radio-frequency waves and antennas | Time-domain Maxwell | openEMS | G |
| Contact between grains | Hertz-Mindlin model | Yade, LIGGGHTS (public line reported dormant), LAMMPS GRANULAR package to evaluate | F |

## Machine elements and standard calculations

Closed-form or code-based calculations, not field solvers: product code under the calculator rule, each tested against a published worked example.

| Effect | Standard model | Engine | Annex |
| --- | --- | --- | --- |
| Gear tooth bending and contact stress | Lewis/AGMA-style formulas | Product code (calculator) | A or Phase 2 |
| Rolling bearing life | L10 life | Product code (calculator) | A or Phase 2 |
| Shaft under combined load | Stress-life with stress concentration | Product code (calculator) | A or Phase 2 |
| Bolted joint | Preload, stiffness, separation, fatigue | Product code (calculator) | A or Phase 2 |
| Springs | Closed-form spring design | Product code (calculator) | A or Phase 2 |
| Belt and chain drives | Closed-form drive design | Product code (calculator) | A or Phase 2 |

## What the materials research found

- **Phase equilibria are well served.** pycalphad is MIT-licensed and reads the standard thermodynamic database format.
- **Heat treatment has a ready engine.** Code\_Aster includes a metallurgical transformation model and a hardness calculation, and has been used and extended for quenching studies.
- **Grain-scale mechanics has a mature research code.** DAMASK reached version 3 with a Python library, and is used in academia and industry, and is AGPL-3.0 (LICENSE read 2026-11-05).
- **Manufacturing processes build on OpenFOAM.** Published open solvers exist for additive manufacturing, [beam welding](https://peeref.com/works/25060913), [direct-chill casting](https://joss.theoj.org/papers/10.21105/joss.04871) and mould filling with solidification. Each is tied to one OpenFOAM line and release; see spec 6.
- **Data is the real gap.** Flow stress curves, transformation diagrams and thermodynamic databases for commercial alloys are mostly proprietary. The engines are free; much of the material data is not.

## Rules for catalogue entries

1. Every entry names the material properties it needs. The app asks for exactly those.
2. Every entry has at least one benchmark before it is offered to users.
3. Every entry carries a status: planned, adapter built, or verified.
4. Every engine assignment is confirmed when its annex spec is written, by testing the engine, not by reading about it.
5. New entries are added here first, then implemented.
6. An entry whose engine is "Product code (calculator)" applies a closed-form or published empirical model to inputs or engine output and never integrates a field; the Build guide's rule 7 defines the boundary.

## Research before building

Complete these and record the findings, with sources, in a short note in the repository before writing code. If a finding contradicts this spec, update the spec first.

- **Every "to confirm" entry.** Find the engine's documentation for that effect, then test it.
- **Standard models.** For each entry, the textbook or review paper that defines the model and its range of validity.
- **Friction in forming.** Which friction laws the forming literature recommends for cold, warm and hot processes.
- **Microstructure models.** Published recrystallization and grain growth models, and the alloys they were fitted to.
- **Open material data.** Sources of flow stress curves, transformation diagrams and thermodynamic databases that may be redistributed, with their licences. The annex E benchmarks depend on this; if no redistributable Fe–C database exists, the benchmark moves to a binary system that has one.
- **Unresearched domains.** Injection moulding (starting point, unverified: OpenFOAM-based mould-filling solvers), acoustics (starting point, unverified: Elmer's Helmholtz solver, openEMS-style time-domain methods), lubrication (starting point, unverified: Reynolds-equation solvers in open tribology codes), precipitation in alloys (starting point, unverified: open KWN-type nucleation and growth implementations). Every starting point is unverified; a research pass decides whether an engine exists and whether a calculator suffices.
- **2D electromagnetics.** FEMM dropped (licence, Windows-only); candidates to test, unverified: xfemm, GetDP/ONELAB.
- **Machine elements.** Which design standards may be referenced freely, and open implementations to reuse.

## Acceptance tests

- [ ] Each catalogue entry maps to a schema option, an engine adapter and a benchmark.
- [ ] Selecting an entry in the app prompts for its required material properties and nothing else.
- [ ] The app shows each entry's status to the user.
- [ ] A starter material library covers the materials used in all templates, with the source of every value recorded.

## Changes in this version

2026-11-05, version 0.2, spec review council:

- C30 (PHY-1, PHY-3, PHY-4, PHY-5, PHY-6, PHY-8, PHY-9, PHY-12, PHY-14, PHY-15, PHY-17, PHY-18): version line; OpenRadioss line, Elmer 2D and 3D, MFiX and grains rows, conjugate heat transfer row revised; vibration, stability and dynamics section; beams and trusses, surface radiation, layered materials rows; machine elements and standard calculations section; calculator rule 6; citations corrected (pycalphad organisation, Code\_Aster reference deferred, DAMASK licence, OpenFOAM line note); research items on material data, unresearched domains, 2D electromagnetics and machine elements.
