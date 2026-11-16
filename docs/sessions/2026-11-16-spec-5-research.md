# Session summary: spec 5 research and council (#104)

One session, as the owner decided on 2026-11-16 ("start spec 5 research now … This has to be done in a single session"). Documentation only: no product code under `src/` or `ui/`, and no engine became a project dependency.

## Built

- **Research notes**, one per item, with the headings Question, Finding, Sources, Decision and Tested:
  - engines (#227, merged): `docs/research/spec-5-{mesa,pysd,fmpy,openmodelica-fmu,chrono,mujoco}.md`;
  - methods (#230): `spec-5-{cosimulation,design-studies,surrogates,people-engines,people-methods,reliability}.md`.
- **Trials** under `docs/research/spec-5-trials/`, with their scripts and outputs: Mesa, PySD, FMPy, MuJoCo, co-simulation, design studies, surrogates, reliability, people (JuPedSim, OpenSim, NIOSH, HRA, workforce), and the benchmarks' closed forms (`benchmarks/expected_values.py`).
- **A CI job for the engines the container could not install** (#228): `.github/workflows/spec5-trials.yml`, run on `workflow_dispatch` and on pull requests that touch its paths, kept out of all-green. It installs OpenModelica 1.27.2, FMPy 0.3.32, micromamba 2.0.5 and PyChrono 9.0.1, each checked against a pinned SHA-256 and failing closed.
- **Spec 5 version 0.3** (#241): component types and schema fields, the model-file layout, issue codes, statistics, the chaining contract, design studies and surrogates, people and reliability, benchmarks with exact values and sources, acceptance rows tagged by milestone, and Specified, Proposed or Open on each section.
- **The council** (#242, merged): four independent reviewers (numbers, licences, implementability, scope); their reports and the disposition of every finding are in `docs/research/spec-5-council.md`.
- **Ten owner decisions**, #231 to #240, each with options, a recommended default and the date the default applies (2026-11-18).

## Checks passing

- `bash scripts/check.sh` passes in a plain clone at 296b1fa (#228's branch): 4653 passed, coverage 99.75%.
- The documentation tests on #241: `tests/test_docs.py`, `test_phase_2_milestones.py`, `test_phase_1_review.py` and `test_decisions_append_only.py`, 64 passed.
- **CI trials** (`spec5-trials.yml`):
  - Run 43935773704 at head `d98f5d7`. OpenModelica's default Co-Simulation FMU gave x(10) = 0.091237783 m against 0.079116024 m, with and without OpenModelica installed.
  - Run 43938942488 at head `e94ef9b`. The FMU built with `--fmiFlags=s:cvode` passed: largest error 2.08e-7 m at a communication step of 0.01 s, and 8.67e-8 m at 0.001 s. The run gave the same result in a clean container without OpenModelica. The default FMUs stepped with forward Euler (3.87e-2 m and 3.71e-3 m). PyChrono passed one setting of twelve: 90°, the default stepper at 0.1 ms, relative error +4.53e-8.

## Decisions logged

In `docs/DECISIONS.md`:

1. Owner decision: start spec 5 research now, in one session (#227).
2. Engine confirmation: Mesa, PySD, FMPy, OpenModelica, Project Chrono and MuJoCo (#227).
3. A CI job for the trials of OpenModelica and Project Chrono (#228).
4. Spec 5 version 0.3, detailed and reviewed by a council (#241), with the licences of SALib, pymoo, moocore, scikit-learn, faultree and dd.

## Awaiting owner

Each default applies on 2026-11-18 unless the owner answers first:

- #231 Q1: the multibody engine. Default: MuJoCo in place of Project Chrono, with the 3D preview in Phase 3.
- #232 Q2: Python 3.12 for Mesa 3.
- #233 Q3: the design-study engines. Default: OpenMDAO and Dakota are dropped, and pymoo is used.
- #234 Q4: the format version and the adapter contract.
- #235 Q5: chaining.
- #236 Q6: engine packaging, and OpenModelica.
- #237 Q7: the phases for people.
- #238 Q8: the answers of the calculators and of the surrogates.
- #239 Q9: maintenance on `failure`.
- #240 Q10: splitting M23.

Also for the owner:

- The stale branch `docs/spec-5-v0.3` can be deleted. The orchestrating session passed this on.
- After #241 merges and #233 is answered, `docs/specs/overview.md` needs spec 5's version and its design-study engine line. This is a small follow-up PR.

## Readings

Listed in the DECISIONS entry of #241 and in spec 5:

- Deterministic domains keep `seed` and drop `replications` and `warmup`.
- One stream per replication for agents, `@agents`.
- Stream keys sit outside the identifier pattern.
- The statistic definitions.
- Unit spellings.
- A top-level `time_unit`, with parameters written `$id`.
- The surrogate's leave-one-out error comes from refits.
- Chaining passes scalars only in Phase 2.
- One template per adapter.
- Predator–prey is stated in days.
- The FMU integrator is CVODE, set by flag (#228's notes and #241).

## Left

- **Why the CVODE FMU loads without OpenModelica.** `ldd` lists `libsundials_cvode.so.5` as not found, yet the FMU ran in the clean container. Explain this before a template ships an FMU.
- **XMILE.** Run it through PySD on the system dynamics benchmarks. The trial used Vensim `.mdl`.
- **Licences not yet read:**
  - JuPedSim's bundled CGAL, Boost and {fmt};
  - OpenSim's Ipopt, CasADi, MUMPS and METIS;
  - the dependencies of dependencies listed in the council record.
- **Sources not yet read:** HEART's primary tables, and RULA and REBA's original papers.
- **PyChrono at 10.0.0, and with a physical inertia.** The trial used 9.0.1 and a near-point mass. These matter only if #231 keeps Chrono.
