# Council review of spec 5 v0.3: licences

Reviewer lens: licences. The product is AGPL-3.0. Branch `docs/spec-5-v0.3` at 243b039. This is not legal advice. Where a lawyer is needed, the finding says so.

Rules applied:
- Spec 1, "Engine licence rule" (`docs/specs/1-model-format.md:94`): an engine runs as a separate process through its own files, unless `docs/DECISIONS.md` records its licence as compatible with AGPL-3.0 for a combined work. `capabilities()` reports an SPDX `licence` and an `invocation`.
- Owner decision F4 (`docs/DECISIONS.md:2391`).
- Build guide "Known gaps" (`docs/specs/build-guide.md:40`): record each engine licence in DECISIONS with its source.
- Build guide conventions (`:97`): record each new dependency in DECISIONS with its licence.

How I checked: I downloaded the wheels from PyPI into `/tmp/claude-0/-home-user-Ithax/248edffc-5b1a-5941-acc3-1e2e2cbbc2ee/scratchpad/council-lic/`. I compared each SHA-256 with PyPI's digest (all matched) and read the licence files with `zipfile`. No downloaded code was run.

## What checks out (read from the licence file in the wheel, digest equal to the note's)

| Adopted | Spec says | Verified | Invocation allowed? |
|---|---|---|---|
| Mesa 3.5.2 | Apache-2.0, in-process | `licenses/LICENSE` + `NOTICE`; sha `ec6dcb7e…e610` | yes. The NOTICE must appear on the licences page; `service/licences.py:129` already picks up `NOTICE` |
| PySD 3.14.3 | MIT, in-process | `pysd-3.14.3.dist-info/LICENSE`; sha `e663c537…9d4a` | yes (but see F6 on `portion`) |
| FMPy 0.3.32 | BSD-2-Clause, in-process | `licenses/LICENSE.txt` (BSD-2, plus FMI headers, SUNDIALS CVODE BSD-3, icons CC BY 4.0) and `fmpy/remoting/license.txt` (BSD-2); sha `b379deb9…cf0` | yes |
| MuJoCo 4.0.1 | Apache-2.0, in-process | `licenses/LICENSE`, `LICENSES_THIRD_PARTY.md` | yes (see N1) |
| pymoo 0.6.2 | Apache-2.0 | `licenses/LICENSE`; sha `9fd4569f…0a` | yes |
| moocore 0.3.2 (pymoo dependency) | LGPL-2.1-or-later | `licenses/COPYRIGHTS`: "due to the license of the AVL-tree library, the combined work is licensed under the LGPL v2.1 or later" | yes. LGPL in-process is fine, and `LGPL-2.1-or-later` is already in `packaging/linux/licences.json` "compatible" |
| SALib 1.6.0 | MIT | `licenses/LICENSE.md` | yes |
| scikit-learn 1.9.1 | BSD-3-Clause | `licenses/COPYING` (libgomp under GPL-3.0 with GCC exception 3.1) | yes |
| faultree 0.4.0 | BSD-3-Clause | `licenses/LICENSE` "Copyright (c) 2026, Mateus Santana" | yes. dd 0.6.0 is BSD-3 + CUDD BSD-3 and carries `GLIBC_COPYING.LIB` (LGPL-2.1) and `GLIBC_LICENSES` notices |
| OpenModelica 1.27.2 | GPL-3.0 or OSMC-PL 1.2, separate process | read by the note from the `.deb` copyright files (not re-read here: apt repo) | yes, as a process under F4 (`omc` is the engine's own executable) |

## Findings

### F1. In-process libraries in "Specified" sections have no DECISIONS licence record. Severity: **blocking** (for marking those sections Specified)

- **Location:**
  - "Design studies … **Specified** except the file layout", with "Libraries (all in-process …)" naming SALib, pymoo NSGA-II and `scipy.stats.qmc`.
  - "Surrogate models … **Specified**", with "scikit-learn `GaussianProcessRegressor`, BSD-3-Clause, in-process".
  - "Fault trees (Specified). `faultree` 0.4 (BSD-3-Clause, in-process)".
- **Problem:**
  - Spec 1's rule allows an in-process import only when the licence "is recorded in `docs/DECISIONS.md` as compatible".
  - The only Spec 5 licence record is the 2026-11-16 "Engine confirmation" entry (`DECISIONS.md:3675`). It covers Mesa, PySD, FMPy, OpenModelica, MSL, Chrono and MuJoCo.
  - Nothing records pymoo, moocore, SALib, scikit-learn, faultree or dd (`grep -n -i "pymoo\|salib\|scikit\|faultree\|moocore" docs/DECISIONS.md` returns nothing).
  - None of these is in `pyproject.toml`. The design-studies note says so itself: "Reversible: add pymoo (with moocore …) and SALib … record each in `docs/DECISIONS.md` with its licence" (`spec-5-design-studies.md:115`).
  - As written, a build session would import libraries the rule does not yet allow.
- **Evidence:** the `docs/DECISIONS.md` lines 3675–3705 and the grep above. The licences are correct (table above), so this is a missing record, not a wrong licence.
- **Fix:** add one DECISIONS record, or extend the engine-confirmation record, with a table like its own:
  - libraries: pymoo 0.6.2, moocore 0.3.2, SALib 1.6.0, scikit-learn 1.9.1, faultree 0.4.0 and dd 0.6.0;
  - columns: licence, file read, wheel SHA-256 and invocation;
  - plus the transitive licences in F6.

  Until that record exists, the spec should say "Specified once the licence record exists".

### F2. JuPedSim's native library contains GPL-3.0-or-later CGAL code; "LGPL-3.0-or-later" is wrong for what ships. Severity: **blocking** (for the owner decision on (b) Crowds)

- **Location:** "(b) Crowds and pedestrians … Proposed: JuPedSim 1.4 (LGPL-3.0-or-later, in-process …)". Note: `spec-5-people-engines.md:20-21` "Compatible; in-process import allowed".
- **Problem:**
  - JuPedSim's own code is LGPL-3.0-or-later.
  - Its wheel's `py_jupedsim.cpython-312-x86_64-linux-gnu.so` compiles in CGAL templates from packages that CGAL licenses under the GPL:
    - 2D Arrangements (`CGAL::Arrangement_on_surface_2`, `Arr_*`);
    - 2D Regularized Boolean Set-Operations (`CGAL::General_polygon_set_2`, `Gps_*`);
    - 2D Triangulations (`CGAL::Constrained_Delaunay_triangulation_2`).
  - The binary therefore carries GPL-3.0-or-later obligations, not only LGPL ones.
  - The wheel also holds no licence notice for CGAL, Boost, {fmt} or pybind11. All four are in the binary. The wheel's only licence file is JuPedSim's 14-line notice, which has no full LGPL text either.
  - AGPL-3.0 §13 / GPL-3.0 §13 still allow combining GPL-3.0 with AGPL-3.0, so the in-process import is probably still allowed. Three things change:
    - the SPDX `licence` that `Capabilities` must report;
    - the obligations if Ithax ever redistributes the wheel: corresponding source for the GPL parts, plus notices the wheel lacks;
    - the note's claim that JuPedSim fits the rule as LGPL.
- **Evidence:**
  - Wheel `jupedsim-1.4.2-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl`, sha `48a0a283…7f08` (PyPI digest matched).
  - `strings py_jupedsim…so | c++filt` shows 209 `CGAL` symbol strings, including those classes. `readelf -d` shows only libc, libm, libstdc++, libgcc_s and pthread as NEEDED, so CGAL is compiled in.
  - CGAL Package Overview (doc.cgal.org/latest/Manual/packages.html, read 2026-11-16): 2D Arrangements, 2D Regularized Boolean Set-Operations and 2D Triangulations are "License: GPL". 2D Polygons and the Kernel are LGPL.
- **Fix:**
  - Record JuPedSim's licence as `LGPL-3.0-or-later AND GPL-3.0-or-later` (CGAL), plus `BSL-1.0` (Boost) and `MIT` ({fmt}) or the actual terms once read.
  - Read the JuPedSim source tree's third-party licence files for the 1.4.2 tag. They could not be read here: github.com and cgal.org/license are unreachable.
  - Keep (b) Open until that is done.
  - A lawyer confirms the GPL-3.0-in-AGPL-process reading before release.

### F3. `Capabilities` has one `licence` and one `invocation`, but the physical domain has two engines with different licences and invocations. Severity: **should-fix**

- **Location:**
  - The table row for `physical`: "OpenModelica 1.27 builds … (GPL-3.0 or OSMC-PL, a separate process); FMPy 0.3 (BSD-2-Clause) runs it in the run worker | process (build), in-process (FMPy)".
  - The text under the table: "reports the licence, invocation and distribution above in `Capabilities`".
- **Problem:**
  - Spec 1's `Capabilities` has a single `licence` (one SPDX id), a single `invocation` and a single `distribution` (`1-model-format.md:372`).
  - The OpenModelica note offers `GPL-3.0-only OR OSMC-PL-1.2` / `process` for the build step, and the FMPy note offers `BSD-2-Clause` / `in-process` / `fmpy`. Neither says which one the adapter reports.
- **Fix:** either:
  - extend spec 1's `Capabilities` to a list of `{licence, invocation, distribution}` per engine (an additive `/v1` change; record it);
  - or state that the `physical` adapter reports FMPy and that the licences page lists OpenModelica separately.

  Also say that chaining (one run per adapter) is unaffected.

### F4. OpenModelica's licence identifier is not SPDX, and "-only" is not supported by the text quoted. Severity: **should-fix**

- **Location:**
  - `spec-5-openmodelica-fmu.md:40`: "`Capabilities.licence` `GPL-3.0-only OR OSMC-PL-1.2`".
  - Spec table: "GPL-3.0 or OSMC-PL".
- **Problem:**
  - Spec 1 requires an SPDX identifier. `OSMC-PL-1.2` is not on the SPDX list; it must be `LicenseRef-OSMC-PL-1.2`.
  - The quoted copyright text says only "GPL VERSION 3". Whether that means `-only` or `-or-later` depends on the full text of the OSMC-PL, which the note did not quote.
  - The runtime licence "OSMC-PL 1.8" has the same SPDX problem.
- **Fix:**
  - Quote the clause that settles -only or -or-later.
  - Use `LicenseRef-OSMC-PL-1.2` and `LicenseRef-OSMC-PL-1.8`.
  - Make the spec table use the exact identifiers the adapter will report.

### F5. "A template may ship an FMU" (BSD-3-Clause) rests on reading the runtime headers only. Severity: **should-fix**

- **Location:**
  - DECISIONS 2026-11-16: "The runtime inside an FMU is BSD-new, AGPL-3.0 or OSMC-PL 1.8 at the user's choice, so a template may ship an FMU".
  - Note `:14` "An FMU built by OpenModelica can therefore be shipped under BSD-3-Clause".
  - Spec "Physical systems": FMUs cached and shipped.
- **Problem:**
  - The note read the 159 headers in `usr/include/omc/c/` and 21 in `omsi/`. It did not read the built FMU, because none was built.
  - `buildModelFMU` defaults to `platforms = {"static"}` (note `:21`), which statically links more than the C runtime. By the guide's own words, the FMU "links the SUNDIALS libraries installed there". `omc` also depends on `liblapack-dev`.
  - A static FMU therefore likely carries SUNDIALS (BSD-3), LAPACK/BLAS (BSD-3 variants), possibly libgfortran (GCC exception) and OpenModelica 3rdParty sources under `sources/`. Each has its own notice requirement.
  - The model code is generated from Modelica Standard Library classes (BSD-3), whose notice must also go with a binary.
  - None of this blocks shipping, but "BSD-3-Clause" alone is not the full licence of the artefact, and BSD-3 requires the notices to travel with the binary.
- **Fix:**
  - Add a step to the pending OpenModelica trial ("Research before building"): unzip the built mass–spring–damper FMU, list `binaries/` and `sources/`, run `readelf -d` / `nm` for linked libraries, and record every licence.
  - Each template that ships an FMU carries a `NOTICE` (OpenModelica runtime under the BSD option, MSL 4.1.0, SUNDIALS, LAPACK, …).
  - If templates go into the Linux package, their FMUs are listed in `licences.json` like any other bundled component.

### F6. Transitive dependencies adopted in-process were not read, and some fall outside the package's licence gate. Severity: **should-fix**

- **Location:**
  - Each note's "Dependencies (wheel metadata)" line.
  - `spec-5-design-studies.md:33` "All declare MIT, BSD, Apache-2.0, PSF, MPL-2.0 or LGPL-2.1-or-later in their metadata".
  - `spec-5-reliability.md:278` "Licences of transitive dependencies … not read".
- **Problem.** PyPI JSON for the pinned versions, read 2026-11-16, shows:
  - **PySD 3.14.3** requires `portion`, which is **LGPL-3.0-or-later** (`License-Expression`; the wheel's `licenses/LICENSE.txt` is the LGPL v3 text). The PySD note does not list it as LGPL, and `LGPL-3.0-or-later` is not in `packaging/linux/licences.json` "compatible". In-process import is fine for the AGPL. Packaging would fail the gate.
  - **Mesa 3.5.2** requires `pythran>=0.17.0` (BSD-3; pulls gast, beniget, ply). The Mesa note's list ("numpy, pandas, scipy, tqdm") omits it.
  - **pymoo** and **SALib** require **matplotlib**. Its wheel `LICENSE` (sha `df4f7784…`) lists:
    - the Matplotlib licence (PSF-style);
    - OFL-1.1 (STIX, AMS fonts);
    - the "BaKoMa Fonts Licence" (non-standard);
    - Bitstream-Charter;
    - `FTL OR GPL-2.0-or-later` (FreeType);
    - the Qhull licence;
    - MIT-Modern-Variant (HarfBuzz).

    matplotlib also pulls in pillow (`MIT-CMU`). Of these, `licences.json` "compatible" has none but the MIT and Apache terms.
  - **FMPy** requires `cmake` (a 30+ MB binary, Apache-2.0/BSD per metadata, bundles not read) and `nbformat` → `jupyter-core`, `traitlets`, `fastjsonschema`. Its icons are CC BY 4.0, which is not in "compatible".
  - **PySD** also pulls `regex` (`Apache-2.0 AND CNRI-Python`; CNRI-Python is not in "compatible") and `chardet`. chardet is 0BSD at 7.7.0, but chardet 5.x and earlier were LGPL-2.1, so the resolved version matters.
  - **MuJoCo** requires `mujoco-studio` (the viewer, a hard dependency), `glfw` (bundles libglfw, Zlib) and `pyopengl` (BSD). Its third-party file includes OFL-1.1 fonts and Eigen's LGPL-2.1 parts (N1).
- **Fix:**
  - Read each transitive licence from its file, as the direct ones were.
  - Record the set in DECISIONS with F1.
  - Decide whether pymoo and SALib are installed without their plotting dependencies. pymoo imports matplotlib only in `pymoo.visualization`, which needs checking. If not, extend `licences.json` "compatible" deliberately: each new term is a recorded decision, not an edit to make the build pass.

### F7. Spec 5 does not say whether Phase 2 engines are bundled in the Linux package, and the obligations depend on it. Severity: **should-fix**

- **Location:**
  - Spec 5 "New engine adapters" (silent).
  - Spec 1: "Engines are installed by the environment manager, not compiled into the product."
  - Spec 3 `:75`: "Phase 1 engines are bundled; an environment manager is introduced with the first Phase 3 engine".
- **Problem:**
  - Phase 2 engines fall between those two statements. If they are bundled, `requirements.lock` and `licences.json` gain them, and Ithax becomes a distributor:
    - LGPL: library text and the ability to replace the library (moocore, portion, JuPedSim);
    - GPL: corresponding source for CGAL in JuPedSim (F2);
    - Apache NOTICE files;
    - BSD notices for the FMU contents.
  - If they are not bundled, the user installs them, and Ithax's obligations shrink to its own code.
  - The OpenModelica note's option (b), "Ithax bundles OpenModelica", would also make Ithax a distributor of GPL-3.0 binaries, which needs a source offer.
- **Fix:**
  - Add one line to "New engine adapters" naming the delivery route of each engine: Linux package, environment manager, or user-installed (OpenModelica via apt, recommended (a)).
  - For bundled engines, state that `scripts/package_linux.py`'s licence check covers them.

### F8. "A separate process" does not cover an Ithax-written worker script that imports the engine. Severity: **should-fix** (lawyer needed)

- **Location:**
  - "(c) Human movement and biomechanics … its wheel bundles Ipopt (EPL-1.0) … so it would run as a separate process".
  - Chrono note `:35`: "Run as a separate process in its own conda environment" (CUDA under NVIDIA EULA, MKL under Intel licence).
- **Problem:**
  - Spec 1 and F4 clear an engine that runs "as a separate process through the engine's own input and output files".
  - For OpenSim and PyChrono there is no named engine executable. The natural adapter is a Python worker that Ithax writes and that does `import opensim` / `import pychrono`.
  - That worker is Ithax code (AGPL-3.0) in the same process as EPL code (OpenSim's Ipopt) or proprietary libraries (CUDA, MKL in Chrono's dependencies). This is the combination the separate-process rule is meant to avoid.
  - FMPy's run worker is not a problem: everything in it is BSD.
- **Fix:**
  - State in spec 1's rule (and cite it in spec 5) what may run in the separate process:
    - only the engine's own executable or CLI (for example `opensim-cmd` with XML setup files, if the wheel or the conda package provides one);
    - or a worker shim kept outside the AGPL work under a licence chosen for compatibility with the engine (for example Apache-2.0).
  - Have a lawyer confirm before OpenSim or Chrono enter a phase.
  - Phase 3 only, but the rule text is shared.

### F9. HEART needs the same legal check as RULA and REBA. Severity: **should-fix**

- **Location:** "HEART (Open): a primary source for its tables and a worked example is still to read." Compare "RULA and REBA (Open): whether Ithax may ship their scoring tables needs a legal check."
- **Problem:**
  - The note's table (`spec-5-people-methods.md:24`) gives HEART the same status as RULA/REBA: "Papers under copyright; method widely applied; no licence terms found".
  - HEART's generic task types and error-producing-condition multipliers are tables from Williams' copyrighted papers.
  - The spec makes reading a primary source the only gate, so a builder could ship the tables once a source is read.
- **Fix:** add "and the same legal check as RULA and REBA on shipping its tables" to the HEART line. The lawyer question can cover all three in one go.

### F10. Spec states OpenSim's Ipopt as EPL-1.0, which the note marks unverified. Severity: **should-fix** (wording)

- **Location:** "its wheel bundles Ipopt (EPL-1.0) and holds no licence file".
- **Problem:**
  - The note says "Unverified: the licence of the bundled Ipopt 3.14.16 (the page says EPL-1.0; newer Ipopt releases may be EPL-2.0) and of MUMPS and METIS", and the FSF list was "not re-read today".
  - The wheel also bundles CasADi (LGPL-3.0-or-later per PyPI metadata), MUMPS and METIS, whose licences were not read.
- **Fix:** write "Ipopt (EPL, version unverified), plus CasADi, MUMPS and METIS not read", and add "read them from source before Phase 3" to "Research before building".

## Notes

- **N1. MuJoCo third-party list.**
  - The note says "None is a GPL licence for a combined work". The file also contains:
    - Eigen's statement that some files are LGPL-2.1-only or LGPL-2.1-or-later;
    - the full GPL-3.0 text with the Bison exception inside Glslang's entry;
    - OFL-1.1 fonts (Open Sans) and Font Awesome.
  - These come from the viewer side (`mujoco-studio`), a hard dependency of `mujoco` 4.0.1.
  - Still compatible in my reading, but the sentence should be "no licence incompatible with AGPL-3.0". Record the OFL/LGPL terms for packaging (F6).
- **N2. FMPy licence discrepancy.** The wheel says BSD-2-Clause and the docs home page says BSD-3-clause (cosimulation note `:164`). The wheel file governs. Fine as recorded.
- **N3. libcosimpy (Phase 3 co-simulation).** MPL-2.0 is fine, but the 20 MB `libcosimc.so` bundles third-party code whose licences are not in the wheel. The note says "not checked". Read them before it moves from "first candidate" to adopted.
- **N4. OMSimulator.** AGPL-3.0 option, which is compatible. The note found its sdist downloads binaries with TLS verification off. That is a supply-chain reason not to install it that way, not a licence issue.
- **N5. Project Chrono.** CUDA (NVIDIA EULA) and MKL (Intel ISSL) are proprietary but redistributable. The note correctly says Ithax would not ship them. If Chrono returns, F8 applies.
- **N6. Data sets.**
  - Jülich archive: CC BY 4.0 by the wiki footer only; per-dataset licences not read.
  - The spec uses published flow numbers (Seyfried et al. 2008), which are facts.
  - If trajectories ever ship under `benchmarks/`, add attribution and record `CC-BY-4.0` (not in `licences.json` "compatible").
- **N7. Assessment methods.**
  - NIOSH Applications Manual: public domain, quoted from the front matter. Fine.
  - SPAR-H: NUREG/CR-6883 is a contractor report (INL) with no copyright notice found. Formula and multipliers are methods and numbers. Add that reasoning to the record, and include it in the lawyer question with RULA, REBA and HEART.
  - MTM and MOST excluded: correct. Avoid their trademarks in UI text beyond saying they are not supported.
  - ICEAA 80% table: values computed from Crawford's formula, used as test values. Fine.
- **N8. Benchmarks and test functions.**
  - The Surjanovic and Bingham R code is GPL-2.0; the surrogate note says it was not copied. Keep it that way: formulas only.
  - Ishigami values come from an OpenTURNS use case (LGPL). Numbers only. Fine.
  - NIST e-Handbook data is US Government work.
- **N9. OSMC-PL runtime choice.** Choosing the BSD option for an FMU's runtime is a recipient's election. Record in the template's NOTICE which option Ithax elects.
- **N10. scipy and numpy** are already bundled, with their bundled terms in `licences.json`. scikit-learn adds libgomp (GPL-3.0-or-later WITH GCC-exception-3.1, already "compatible").

## Where a lawyer is needed

- F2: GPL-3.0 CGAL in the AGPL process, and redistribution of the JuPedSim wheel.
- F8: what counts as a separate process for an engine driven through an Ithax-written script.
- F9 and N7: shipping RULA, REBA, HEART (and SPAR-H) tables.
- F5: the BSD election and notices for shipped FMUs.
- F6: matplotlib's BaKoMa font licence, if matplotlib is bundled.
- Spec 1 already defers the whole rule to a lawyer before the first release.
