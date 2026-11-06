# Decisions

Dated log of choices and their reasons. Newest last. Each new dependency is recorded here
with its licence.

## 2026-11-05 · M0

### Specs exported into `docs/specs/`

The two Claude Docs ("Spec 0: Product Brief" and "Build Specs 1 to 7") were exported tab by
tab with the Docs service's Markdown exporter. Byte counts were checked against the sizes
the service reported. Files:

| File | Source tab | Doc revision at export |
| --- | --- | --- |
| `0-product-brief.md` | Spec 0: Product Brief | 13 |
| `overview.md` | Build Specs: Overview | 57 |
| `build-guide.md` | Build Specs: Build guide | 4 |
| `1-model-format.md` | 1 Model format | 5 |
| `2-core-engine.md` | 2 Core engine | 5 |
| `3-desktop-app.md` | 3 Desktop app | 4 |
| `4-content-and-ai.md` | 4 Content and AI | 4 |
| `5-systems-and-design.md` | 5 Systems and design | 3 |
| `6-physics-platform.md` | 6 Physics platform | 3 |
| `7-physics-catalogue.md` | 7 Physics catalogue | 5 |

From here on the files in `docs/specs/` are the working copy. A change that departs from a
spec updates the file in the same commit (guide rule 6).

### `CLAUDE.md` is the build guide

The guide says to put its content in `CLAUDE.md`. `CLAUDE.md` holds it verbatim, with a
short header and a "Current state" section appended at the end for session hand-over.

### Tooling for "checks"

The guide asks for one formatter and linter, a type checker and pytest, without naming
the first two. Simplest choice taken:

| Tool | Role | Version pinned as minimum | Licence |
| --- | --- | --- | --- |
| hatchling | build backend | 1.33 | MIT |
| pytest | tests | 9.2 | MIT |
| ruff | formatter and linter (one tool for both) | 0.17.4 | MIT |
| mypy | type checker, `--strict` | 2.4.1 | MIT |

`scripts/check.sh` runs all four checks. CI (`.github/workflows/checks.yml`) runs the same
script on Python 3.11 (the minimum) and 3.13.

Ruff also formats Python inside Markdown code blocks, so `docs/specs/` and `CLAUDE.md`
are excluded from it: the specs are never reformatted by tooling; edits are deliberate and
logged under each spec's "Changes in this version".

### Licence file

`LICENSE` is the AGPL version 3 text from gnu.org (`agpl-3.0.txt`, SHA-256
`0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0`). Package metadata
declares `AGPL-3.0-only`. Spec 0 says to have a lawyer confirm before the first public
release; that still stands. "Only" rather than "or later" is the narrower reading and is
easy to widen later; **owner to confirm**.

### Open: starting material is not in the repository

The guide lists three example model files (`coffee_shop.json`, `three_machine_line.json`,
`warehouse.json`) and the prototype `proto.py` as starting material. Only the coffee shop
model appears in the specs (spec 1, "A minimal example"). The other two files and the
prototype were not supplied. They are needed as fixtures from M1 on. They were **not**
reconstructed from the prototype results in spec 2, because that would be guessing.
Resolved as a proposed default by the spec review council below ("Spec council review",
2026-11-05): the two files are written fresh at M1 to the spec 2 targets unless the owner
supplies the originals first.

### Noted, not changed

Spec 0 (dated 5 November 2026) records the high-tier machine as "Recorded 6 November
2026". Left as written; owner to confirm the date (owner question 10 below).

## 2026-11-05 · Spec review council (before M1)

### Spec council review

**Decision.** Five independent expert reviews (product, architecture, simulation,
testing, physics) were merged by a chair; a skeptic re-derived every number and checked
every accepted change for consistency; every finding was ruled on. The accepted changes
C1 to C37 were applied to the repository copies by one editor. Specs 1 to 4 are bumped to
version 0.3, spec 0 and specs 5 to 7 to 0.2. Each spec now carries a version line under
its title and a "Changes in this version" section that lists the changes with their
finding ids. No change was dropped by the skeptic.

The owner's Claude Docs originals have **not** been updated and now lag the repository
copies. The repository is the source of truth (owner question 8); sessions never write to
the Claude Docs.

**Reason.** The specs were written before any code existed. The reviews found places where
an M1 schema could not be written (keys per domain, issue codes without an owning pass),
where results could not be reproduced (unnamed hash and generator), where benchmarks had
no defined answers for seven blocks, where the service could not work as written (token
over WebSocket, no port discovery, two writers with no revision check), and where
acceptance rows had no milestone or depended on people outside the project. Fixing these
in the specs before M1 is cheaper than discovering them in code.

**What changed, by spec.**

- Spec 1: random stream key and generator (numpy PCG64 via SeedSequence), "identical run"
  defined; top-level keys split by domain; experiments gain `default` scenario,
  `confidence`, `record_interval`, `search`; distribution parameterisations and the M2
  sampling test; reserved identifiers; issue codes allocated to schema, meaning, run and
  service passes (E100 to E192, W200 to W210); adapter signatures with `CancelToken` and
  `workers`; engine licence rule; where each method runs per target; `run_id`, manifest
  fields, `replications` and `timeseries` tables; acceptance table with milestones.
- Spec 2: benchmark pass rule 3 × standard error with fixed seeds and 100 replications;
  one known-answer benchmark per block and four optimization cases, all recomputed;
  block behaviour defaults labelled as council proposals; time-weighted statistics; t
  quantile from scipy; paired scenario differences; warm-up check; search procedure with
  baseline, exhaustive path, confirmation stage and result layout; optimization
  `summary.json`; prototype rows marked reference only.
- Spec 3: Phase 1 native on Windows as proposed default; service rules rewritten; new
  endpoints (templates, schema, project events, data, open); edit semantics; status codes;
  reconnect semantics; project folder; design checklist split with an owner fallback;
  acceptance table.
- Spec 4: template table with blocks and scope; Build mode as a fixed form;
  `expected.json` sources; finding rules rewritten with fixture layout; MCP tools mapped
  to endpoints; assistant acceptance case at two levels; acceptance table.
- Spec 0: people in scope; annex order kept in spec 6 only; AGPL consequences for users;
  success measures with method and milestone; six added risks; OpenRadioss open item.
- Specs 5 to 7 (structure only): people, workforce, reliability and maintenance sections;
  licence column and research items; vibration, machine-element and calculator rows;
  corrected benchmark answers (SIR, pendulum); FEMM dropped; citations corrected.
- Build guide and `CLAUDE.md`: rules 3, 6, 7 and new rule 10; known gaps; layout;
  conventions (coverage gate, commit messages); milestone done-when rows; starting
  material; session procedure; performance protocol.
- Tooling: `pytest-cov` and the 90% coverage gate in `scripts/check.sh` only; markers
  registered; `tests/test_docs.py` enforces guide equality, one fixture per validation
  code (from M1) and marker registration; `examples/coffee_shop.json` written from spec 1.

**What was dropped and why.** Nothing was dropped by the skeptic. Within the merged
changes: ARCH-20's `spawn_key` stream variant (more complex than the string key for no
gain); SIM-6's weighted-sum objectives for the machine-count test (the constraint form
needs no new syntax); the NAFEMS FV52 pairing for the beam frequency benchmark (FV52 is a
plate test); a `tables/empirical_<id>.parquet` copy location (conflicted with the table
name rule; moved to `data/`); byte-identical Parquet as the repeat criterion (a property
of the writer, not the product).

**How conflicts were resolved.** RNG family: numpy over stdlib `random`, because scipy and
pyarrow already bring numpy and one RNG family is simpler. Machine-count test: constraint
form over weighted objectives. `not_enough_runs`: the three proposals merged into one rule
with a floor on the mean. Statistic names: merged into one table in spec 2. Benchmark pass
rule: 3 × standard error with fixed seeds, replacing the 95% interval that fails one in
twenty on correct code. Issue codes: one allocation with an owning pass per code. Fidelity:
`standard` only for Phase 1 process and optimization engines.

**Facts checked by the chair, with method.** PyPI JSON metadata and file lists read on
2026-11-05: pytest-cov 7.1.0 MIT; numpy 2.5.4 BSD-3-Clause; scipy 1.18.1 BSD; pyarrow
26.0.1 Apache-2.0; highspy 1.15.1 MIT; pyomo 6.10.1 BSD-3-Clause; simpy 4.1.2 MIT; optuna
5.0.0 MIT; pint 0.26.2 BSD-3-Clause; fastapi 0.162.0 MIT; pycalphad MIT; all of these
ship Windows wheels or are pure Python. Licence files read on 2026-11-05: Gmsh
(gmsh.info/LICENSE.txt, GPL-2.0-or-later with linking exception); FEMM (femm.info, Aladdin
Free Public License); AdditiveFOAM README (GPL-3.0-or-later, requires OpenFOAM-14
Foundation line); OpenSim LICENSE (Apache-2.0); DAMASK LICENSE (AGPL-3.0). Press: itsfoss
article of 5 October 2026 on the OpenRadioss repository removal and the OpenCourant fork.
Not verifiable from the session: GitHub repository states (LIGGGHTS-PUBLIC activity, the
OpenRadioss and OpenCourant repositories themselves); OpenModelica, DWSIM, LIGGGHTS
licences are as reported by the review, not re-read; CalculiX, Code_Aster, Elmer,
OpenFOAM, SU2, preCICE, Yade, Code_Saturne, openEMS, MFiX licences unverified.

**Dependencies pre-recorded for M1 to M3** (confirm from each distribution's LICENSE file
when added):

| Package | Version seen | Licence | How checked |
| --- | --- | --- | --- |
| numpy | 2.5.4 | BSD-3-Clause | PyPI metadata, 2026-11-05 |
| scipy | 1.18.1 | BSD-3-Clause | PyPI metadata, 2026-11-05 |
| pyarrow | 26.0.1 | Apache-2.0 | PyPI metadata, 2026-11-05 |
| pytest-cov | 7.1.0 | MIT | PyPI metadata, 2026-11-05; added to the dev extra now |

**Proposed default for the two example files.** `three_machine_line.json` and
`warehouse.json` are written fresh at M1, with M2 blocks only, to the spec 2 targets
(weld utilization 0.85 to 0.92 with the other stations below 0.70; warehouse throughput
within 1% of 60 per hour and pack utilization 0.75 to 0.85). If the owner does not answer
before M1 starts, guide rule 5 applies and M1 proceeds under this default with its own
DECISIONS entry.

**Engine licence rule** (spec 1, proposed). An adapter drives its engine as a separate
process unless the engine's licence is recorded here as compatible with AGPL-3.0 for a
combined work. Phase 1 engines (SimPy, HiGHS via highspy, Pyomo, Optuna) are MIT or BSD
per PyPI metadata and may be imported. Not legal advice; a lawyer confirms before release.

### Owner questions from this review

Recorded, not decided. Each has the council's recommended default and the milestone it
blocks.

1. **The three-machine line and warehouse model files and `proto.py` were never
   supplied.** Supply the originals, or approve writing both fresh at M1 to the spec 2
   targets? Options: (a) supply originals; (b) write fresh at M1 (written into the specs
   as the proposed default). Recommendation: (b); if no answer arrives, rule 5 lets M1
   proceed under (b) with a DECISIONS entry. Blocks: M1.
2. **Phase 1 on Windows:** run the service natively (every Phase 1 dependency has Windows
   wheels or is pure Python, verified on PyPI 2026-11-05) or keep the prepared WSL image?
   Options: native (proposed default in spec 3) / WSL image. Recommendation: native; WSL
   costs an admin install, a restart and half of a low-tier machine's memory, breaking the
   offline and ten-minute-install promises. Blocks: M6 process model choices; M11
   packaging.
3. **Remote (SSH) and cluster (Slurm) run targets:** keep them in Phase 1 (M11), or keep
   them in the spec 1 contract but build them in Phase 2? Options: Phase 1 at M11
   (current text) / Phase 2 (contract unchanged, M11 becomes packaging only).
   Recommendation: Phase 2; they serve the third user group and no Phase 1 engine needs
   them; the contract stays so nothing is redesigned. Blocks: none before M11.
4. **Block behaviour defaults written into spec 2 as council proposals:** source discards
   when blocked; failure is preempt-resume; a busy unit finishes its item when a shift
   ends; partial batches release on timeout; server seizes own capacity then pool; queue
   `on_full` defaults to block; store demand takes one unit and waits at zero; item
   attributes, priority discipline and attribute routing deferred to Phase 2. Options:
   confirm all / change named items (for example preempt-restart for failures, lost items
   on shift end, priority in Phase 1 via `attributes` on `source`). Recommendation:
   confirm; each is the simplest reading and M4 may correct with a DECISIONS entry where a
   benchmark shows otherwise. Blocks: M4 (M1 can proceed).
5. **Engine licence rule (spec 1)** and the pending AGPL-3.0-only versus -or-later
   choice. Options: confirm rule / amend; only / or-later. Recommendation: confirm the
   rule (lawyer to review before release); keep -only until a lawyer advises. Blocks: none
   before Phase 2 engines; the only/or-later choice before the first outside
   contribution.
6. **Scope additions for people ("man"), machine elements and reliability:** accept the
   structure-only sections in specs 5 and 7 and the spec 0 scope line, and in which
   phase? Options: accept as proposed (Phase 2 for workforce/reliability, Phase 2 to 3 for
   the rest) / narrow / drop. Recommendation: accept as structure only; nothing is
   implemented before its research items. Blocks: none in Phase 1.
7. **Owner-only acceptance rows:** accept the fallback for the wireframe walkthrough
   (owner's scripted think-aloud, logged, outside walkthrough moved to M10) and the
   "Awaiting owner" handling of the first-time-user, Windows-install and real-assistant
   rows? Options: accept / require outside testers before M9. Recommendation: accept;
   otherwise M9 can block on recruitment rather than work. Blocks: M9.
8. **Source of truth:** is the repository copy of the specs now authoritative (sessions
   edit it, the owner re-imports when they choose), or does the owner keep editing in
   Claude Docs with sessions re-exporting at session start? Options: repository (written
   as the proposed default) / Claude Docs. Recommendation: repository; rule 6 cannot work
   otherwise. Blocks: none, but every spec edit from now on.
9. **Service lifetime after the interface closes:** exit after 30 idle minutes with no
   runs or clients (interface and MCP server start it on demand), or stay up until stopped
   from Settings? Options: idle exit (proposed default) / stay up. Recommendation: idle
   exit. Blocks: M6.
10. **Smaller product choices:** a `sketch` preview fidelity for process runs (default no
    in Phase 1); weighted-sum objectives naming parameters (default no); an eleventh
    "forklift/AGV transport" template (default no); the success-measure methods and the
    six added risk rows in spec 0 (default accept as proposals); the 5 versus 6 November
    date in spec 0's hardware table ("Noted, not changed" above). Options: accept
    defaults / change individually. Recommendation: accept the defaults. Blocks: none
    (M10 for the success measures).

### Verifier follow-up (2026-11-05, before M1)

The verifier confirmed every council change and found six small inconsistencies that came from the agreed instructions rather than from the editor. Each was fixed by the simplest reading and logged under that spec's "Changes in this version":

- Spec 1: only a new major version needs a migration.
- Spec 1: E172 refuses a run before it is created, so it never appears in a manifest. This matches the 422 response in spec 3.
- Spec 1: a `run_id` is resolved through the `index.sqlite` of each project listed in `projects.json`.
- Spec 1: the list of codes in the meaning pass is now exact.
- Spec 3: the M9 end-to-end test uses the spec 2 pass rule.
- Spec 4: in the summary, data import in Build mode is optional.

## 2026-11-06 · Specs synced back to Claude Docs (owner request)

- **Decision:** The owner asked for the repository specs to be copied back to the Claude Docs, so all ten tabs were replaced with the repository files. The same request overrides guide rule 6, "Sessions never write to the owner's Claude Docs", for this sync only.
- **What was kept:** The title and byline blocks of "Spec 0: Product Brief" and the "Overview" tab were left as they were, because they hold a date chip and an @-mention.
- **Precondition:** Before the sync, no tab had changed since the 2026-11-05 export: a `sinceRev` read returned no changes. Nothing the owner wrote in the Docs was lost.
- **Verification:** Each tab was exported again as Markdown and compared byte for byte with its repository file.
  - Seven tabs match exactly.
  - Build guide, spec 1, spec 2 and spec 4 differ only where the exporter puts a backslash before `<`, `[`, `]`, `_` or `|` in plain text. The stored text is the same.
- **Defect found:** The sync found one real fault in the repository. Spec 2's "Statistic definitions" table had an unescaped `|` inside a code span, which splits the cell in GitHub Markdown. The repository file now writes it as `\|`, and the fix is logged in spec 2's change list.
- **Source of truth:** The repository is still the source of truth (owner question 8).

## 2026-11-06 · M2 (research notes, started early)

### M2 research notes written before M1 closes

- **Decision:** The three M2 research notes (`docs/research/spec-2-simulation-library.md`, `docs/research/spec-1-plugin-mechanisms.md`, `docs/research/spec-2-benchmark-sources.md`) are written now, while M1 is still open.
- **Reason:** The owner asked for parallel work ahead of the normal order (Linear AKS-95). The notes are documents only: no product code, no tests and no change to `pyproject.toml`, so M1's work and checks are untouched. Guide rule 2 (one milestone per session) is kept in spirit: this session builds nothing for M2.
- **Alternatives considered:** Wait for M1 to close (the normal order).
- **Spec sections updated:** see the next three entries.
- **Dependencies added:** none.

### SimPy confirmed as the process engine

- **Decision:** SimPy stays the engine for the `process` domain. Spec 2's "Simultaneous events" rule now states SimPy's tested ordering: at one instant, events run in scheduling order, except that a process start or an interrupt runs first, and an event due exactly at the end of the run does not run.
- **Reason:** On 100 replications of the spec 2 M/M/1 case, SimPy took about 5 s, Ciw 9 s and salabim 142 s; all three met the 3 × standard error rule. Ciw draws from Python's global `random` module, which the conventions forbid and spec 1's stream scheme cannot use. salabim's default mode needs the undeclared `greenlet` package. Details in `docs/research/spec-2-simulation-library.md`.
- **Alternatives considered:** salabim (has a capacity setter for schedules and animation, but is 25 to 30 times slower on this case); Ciw (network-of-queues only, global random generator).
- **Spec sections updated:** spec 2 "Block reference" (Simultaneous events) and "Changes in this version".
- **Dependencies added:** none in this change; recorded below for M2.

### Engine gap: SimPy lacks resource capacity that changes over time

- **Decision:** At M4 the adapter builds the `schedule` block itself, because SimPy's `Resource.capacity` is a read-only property (checked in `simpy/resources/base.py`, 4.1.2). One workaround is a process that seizes the off-shift units with priority on a `PriorityResource`. Another is a counter in the adapter that holds back units. M4 chooses one and tests it against the deterministic schedule benchmark. This is event logic, not numerical code (guide rule 7).
- **Reason:** Spec 2 `schedule` changes the capacity of a server or pool over time.
- **Alternatives considered:** salabim, whose `Resource.set_capacity()` exists, was rejected on speed (previous entry).
- **Spec sections updated:** none yet; spec 2 "Block reference" `schedule` is verified at M4.
- **Dependencies added:** none.

### Engine discovery by entry points confirmed

- **Decision:** Adapters are found through entry points in group `lcsim.engines`, read with the standard library's `importlib.metadata`. The entry-point name is the adapter name used by `run.engine`. A plugin that fails to import is left out and logged. Duplicate names are left out and logged, with E102 if no single engine remains. The group is renamed with the placeholder package, because `lcsim` is taken on PyPI by an unrelated liquid crystal simulator.
- **Reason:** Entry points are the packaging standard for plugins. xarray uses them for its I/O engines, and pluggy and stevedore build on them. They need no dependency. A test showed that a plugin with a broken import is listed but fails only on load, and that `EntryPoints[name]` silently picks one of two duplicates; the spec now says what the core does in each case. Details in `docs/research/spec-1-plugin-mechanisms.md`.
- **Alternatives considered:** a naming convention or namespace packages (both import every candidate to discover it); pluggy or stevedore (hook calling and driver managers that spec 1 does not need, and one more dependency).
- **Spec sections updated:** spec 1 "Engine contract", "Division of labour" (pyarrow) and "Changes in this version".
- **Dependencies added:** none.

### Libraries for M2, confirmed from their licence files

Not added to `pyproject.toml` in this change; M2's first code change adds them. Each licence was read from the installed wheel's own licence file with `importlib.metadata` on 2026-11-06, in scratch environments on Python 3.11.18 and 3.13.18. These replace the "PyPI metadata" rows of "Dependencies pre-recorded for M1 to M3" for these four packages.

| Package | Version on Python 3.11 / 3.12 and later | Licence | How checked | AGPL-3.0 |
| --- | --- | --- | --- | --- |
| simpy | 4.1.2 / 4.1.2 | MIT | `simpy-4.1.2.dist-info/licenses/LICENSE.rst`, "The MIT License (MIT)" | compatible (Expat, FSF list) |
| numpy | 2.4.6 / 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 (`License-Expression`) | `numpy-*.dist-info/licenses/LICENSE.txt`, BSD 3-clause; the Linux wheel bundles OpenBLAS (BSD-3-Clause), LAPACK (BSD-3-Clause-Open-MPI), libgfortran (GPL-3.0-or-later WITH GCC-exception-3.1) and libquadmath (LGPL-2.1-or-later) | compatible |
| scipy | 1.17.1 / 1.18.1 | BSD-3-Clause, with the same four bundled libraries as numpy in the Linux wheel | `scipy-*.dist-info/LICENSE.txt` | compatible |
| pyarrow | 26.0.1 / 26.0.1 | Apache-2.0 | `pyarrow-26.0.1.dist-info/licenses/LICENSE.txt`, Apache License 2.0 plus notices for bundled Apache-2.0, BSD, MIT and ZPL-2.1 code | compatible |

- **Python 3.11 gets older numpy and scipy.** numpy 2.5.4 and scipy 1.18.1 declare `Requires-Python >=3.12`. The PyPI JSON shows the newest releases for 3.11 are numpy 2.4.6 and scipy 1.17.1, and pip picked them on 3.11.18. CI runs on 3.11 and 3.13, so it tests both pairs. Spec 1 promises a repeat run only on the same versions, so nothing changes. The spec 1 stream for key `42:0:till` gave bit-identical exponential samples on numpy 2.4.6 and 2.5.4; that was observed, not promised.
- **AGPL-3.0 compatibility.** The FSF licence list says Apache-2.0 is "compatible with version 3 of the GNU GPL", that Expat (MIT) and Modified BSD are "compatible with the GNU GPL", and that LGPLv2.1 "is compatible with GPLv2 and GPLv3". It also says AGPLv3 allows combining "separate modules or source files released under both of those licenses [AGPLv3 and GPLv3] in a single project". The GCC runtime library exception permits use by non-GPL programs. All four packages may therefore be imported into the service process under spec 1's engine licence rule. This is not legal advice; a lawyer confirms before release (spec 1).
- **Windows.** The PyPI JSON lists `cp311` and `cp313` `win_amd64` wheels for numpy 2.4.6, scipy 1.17.1 and pyarrow 26.0.1, and `cp313` only for numpy 2.5.4 and scipy 1.18.1. simpy is pure Python. This is consistent with spec 3's native-Windows default.
