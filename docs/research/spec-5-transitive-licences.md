# Spec 5 research: licences of bundled and transitive dependencies

## Question

Spec 5's "Research before building" lists licences not yet read. These are the libraries compiled into JuPedSim's wheel (CGAL, Boost, {fmt}), the solver libraries bundled in OpenSim's wheel (Ipopt, MUMPS, METIS), and the transitive dependencies the council found (`docs/research/spec-5-council/licences.md`, F6). The council left two checks open: whether pymoo and SALib need matplotlib, and which chardet version PySD resolves. What do these licences say, and what follows for Ithax?

## Finding

Read on 2026-11-17. All files were downloaded into scratch folders and read without being installed, with Python run with `-I`.

### JuPedSim 1.4.2

Source distribution `jupedsim-1.4.2.tar.gz` from PyPI, SHA-256 `a61ebf4f…`, equal to PyPI's digest. It vendors eight trees under `third-party/`. JuPedSim's own sources include headers from four of them; googletest and benchmark are test-only.

| Library | Version | Licence, as its file says | Used by JuPedSim's own sources |
| --- | --- | --- | --- |
| JuPedSim | 1.4.2 | LGPL-3.0-or-later (`LICENSE`) | — |
| CGAL | 6.0.1 | Per file: GPL-3.0-or-later or LGPL-3.0-or-later, each `OR LicenseRef-Commercial` (`LICENSE`, SPDX lines in each header) | yes, see below |
| Boost | 1.82.0 | BSL-1.0 (2,627 of 3,000 headers sampled carry the Boost Software License text; the tree holds headers and CMake files, no compiled library) | `boost/iterator`, `boost/variant.hpp` |
| {fmt} | 10.2.1 | MIT, with an optional exception: no notice is needed for portions embedded in object code | `fmt/core.h`, `format.h`, `ostream.h`, `ranges.h` |
| pybind11 | 2.12.0 | BSD-3-Clause | `pybind11/pybind11.h`, `functional.h`, `stl.h` |
| GLM | 1.0.1 | "The Happy Bunny License or MIT License" (`copying.txt`) | `glm/vec2.hpp`, `vec3.hpp`, `geometric.hpp` |

The CGAL headers JuPedSim includes, with each header's SPDX line:

- **GPL-3.0-or-later OR LicenseRef-Commercial:** `Boolean_set_operations_2.h` (package Boolean_set_operations_2); `Constrained_Delaunay_triangulation_2.h`, `Triangulation_vertex_base_with_info_2.h`, `mark_domain_in_triangulation.h` and `draw_triangulation_2.h` (package Triangulation_2); `Surface_mesh.h` (package Surface_mesh).
- **LGPL-3.0-or-later OR LicenseRef-Commercial:** the kernel headers `Exact_predicates_exact_constructions_kernel.h`, `Point_2.h` and `intersections.h`, plus `Polygon_2_algorithms.h`, `Polygon_with_holes_2.h` and `Distance_2/Point_2_Segment_2.h`.

The build sets `CGAL_DISABLE_GMP ON` (`third-party/CMakeLists.txt`), so GMP and MPFR (LGPL) are not linked. The installed module `py_jupedsim.cpython-312-x86_64-linux-gnu.so` needs only the C and C++ runtime libraries (`readelf -d`: libstdc++, libgcc_s, libm, libc, libpthread). The vendored libraries are therefore compiled in. The wheel's `RECORD` lists one licence file, JuPedSim's own LGPL text, and no notice for CGAL, pybind11, Boost, {fmt} or GLM.

This confirms the council's finding F2 from the source: the module contains GPL-3.0-or-later code, so the combined work is GPL-3.0-or-later, which is compatible with AGPL-3.0. Redistribution must also carry the BSD-3-Clause notice of pybind11. BSL-1.0 and {fmt}'s exception need no notice in object code. GLM's MIT terms ask for the notice in "copies or substantial portions", which a lawyer should read for header-only use.

### OpenSim 4.6: Ipopt, MUMPS, METIS

OpenSim's wheel ships these libraries without their licence files (`spec-5-people-engines.md`). Their licences were read from the conda-forge packages of the same upstream projects. Each package's SHA-256 was checked against conda-forge's `repodata.json`.

| Library | Package read | Licence file | Package metadata |
| --- | --- | --- | --- |
| Ipopt | `ipopt-3.14.16-h59d4785_11.conda`, the same version as OpenSim's | `share/doc/ipopt/LICENSE`: "Eclipse Public License - v 2.0"; 162 headers say "This code is published under the Eclipse Public License." | `EPL-1.0`: out of date |
| MUMPS | `mumps-seq-5.8.2-gfortran_h031f0af_3.conda` | `info/licenses/LICENSE`: CeCILL-C, "except for variants of AMD ordering and [sdcz]MUMPS_TRUNCATED_RRQR derived from the LAPACK package distributed under BSD 3-clause" | `CECILL-C` |
| METIS | `metis-5.1.0-h86e3903_1008.conda` | `info/licenses/LICENSE.txt`: Apache-2.0, "Copyright 1995-2013, Regents of the University of Minnesota" | `Apache-2.0` |

- **Ipopt names no Secondary License.** EPL-2.0 allows a program to name GPL-2.0-or-later as a Secondary License in its Exhibit A. Ipopt's `LICENSE` is the plain EPL-2.0 text and ends without such a notice. So the GPL route through Exhibit A does not apply. The research note's proposal stands: OpenSim runs as a separate worker process, never imported into the AGPL service.
- **Version caveat.** OpenSim bundles `libcoinmumps` 3.0.5, COIN-OR's build of MUMPS. MUMPS's licence was read here at 5.8.2, and OpenSim's METIS version is not stated in its wheel. Before Phase 3, read both at the versions OpenSim actually bundles.
- **CeCILL-C** is a file-level copyleft licence written for French law. Its compatibility with AGPL-3.0 for a combined work was not settled here. It is left to the lawyer's check that spec 1 already requires before release.

### Transitive dependencies (council F6)

- **chardet:** PySD 3.14.3 resolves chardet 7.7.0, `License-Expression: 0BSD` (installed metadata). The LGPL-2.1 releases (5.x and earlier) are not what PySD gets today. A pin of `chardet>=7` keeps it so.
- **portion 2.6.3** (PySD) and **regex 2026.11.15** (PySD): as the council read them, LGPL-3.0-or-later and `Apache-2.0 AND CNRI-Python`. Neither term is in `packaging/linux/licences.json` "compatible". Adding them is a decision, recorded when PySD is bundled (owner decision #236).
- **matplotlib** is required by pymoo 0.6.2 and SALib 1.6.0, but neither needs it for the work spec 5 proposes. See Tested.

## Sources

- PyPI JSON for `jupedsim` 1.4.2, read 2026-11-17, and its source distribution: `LICENSE`, `third-party/*/LICENSE*`, `third-party/glm-1.0.1/copying.txt`, `third-party/CMakeLists.txt`, and the CGAL headers named above.
- The installed `jupedsim` 1.4.2 wheel in the earlier research environment: `jupedsim-1.4.2.dist-info/RECORD` and `METADATA`; `readelf -d` of `py_jupedsim.cpython-312-x86_64-linux-gnu.so`.
- conda-forge `linux-64/repodata.json` (licence fields and SHA-256), and the three `.conda` packages above: `info/about.json`, `info/licenses/`, and `share/doc/ipopt/LICENSE`. Read 2026-11-17.
- Eclipse Public License 2.0, section 3.2 (Secondary Licenses) and Exhibit A, as printed in Ipopt's `LICENSE`.
- `docs/research/spec-5-council/licences.md` (F2, F6); `packaging/linux/licences.json`.

## Decision

Proposed (owner to confirm, with #236 and #237):

- **JuPedSim** stays proposed for Phase 3 after a legal check (#237). The check now has its inputs: the GPL CGAL packages (Boolean_set_operations_2, Triangulation_2, Surface_mesh), and the notices a bundle must add (pybind11 BSD-3-Clause, GLM MIT).
- **OpenSim** stays a separate worker process in Phase 3. Ipopt 3.14.16 is EPL-2.0 with no Secondary License named. Before Phase 3, read MUMPS and METIS at OpenSim's own versions.
- **pymoo and SALib are installed without matplotlib** when Ithax bundles them. The environment manager installs them with `--no-deps` and their other requirements pinned. This avoids matplotlib's font licences (council F6) and its size. In the trial environment, matplotlib takes 30 MB on disk, and the packages it pulls in (pillow, fontTools, kiwisolver, contourpy, cycler, pyparsing, mpl_toolkits) about 40 MB more.
- **chardet stays at 7.x or later**, so PySD's dependency tree has no LGPL-2.1 chardet.

## Tested

- **pymoo, SALib and Optuna without matplotlib.**
  - Setup: a scratch environment with pymoo 0.6.2, SALib 1.6.0, Optuna 5.1.0, scipy 1.18.1, numpy 2.5.5 and moocore 0.3.2, then matplotlib uninstalled. `uv pip check` then reports that both packages declare matplotlib.
  - Run: the three design-study trials (`trial_optuna_pymoo.py`, `trial_salib_qmc.py`, `trial_same_interface.py`), with deprecation warnings as errors.
  - Result: all three exited 0, and each output equalled its recorded `output_*.txt` apart from timing lines. So NSGA-II on ZDT1 in pymoo, Sobol and Morris analysis in SALib, and the shared study interface run without matplotlib.
- **Not run:** JuPedSim and OpenSim; only their licence files were read.
