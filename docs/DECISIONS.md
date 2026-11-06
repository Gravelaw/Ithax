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

## 2026-11-06 · M0

### CI workflow (AKS-73)

- **Decision:** `.github/workflows/checks.yml` now has three jobs.
  - `checks` runs `bash scripts/check.sh` unchanged on Python 3.11 and 3.13. It stays the single gate.
  - `benchmarks` runs `pytest -m benchmark` on Python 3.11. A first step looks for `benchmarks/*/model.json` and `tests/benchmarks/test_benchmarks.py`. While either is missing (until M2) the job passes with a notice and runs nothing else. `pytest -m perf` is never run in CI.
  - `pr-title` runs on pull requests only. It fails unless the title matches `^AKS-[0-9]+(, AKS-[0-9]+)*: [^ ]`.
- **Hardening:** workflow `permissions: contents: read`; `pr-title.yml` has only `pull-requests: read`. Triggers are `pull_request` and pushes to `main`, not every push. A `concurrency` group per workflow and ref cancels the older run. `actions/setup-python` caches pip, keyed on `pyproject.toml`. The matrix no longer stops the other version when one fails (`fail-fast: false`).
- **Title edits:** the title check is its own workflow, `.github/workflows/pr-title.yml`, which also listens for `edited`, so a corrected title re-runs only `pr-title`. `checks.yml` uses the default `pull_request` types and never runs on an edit. (Revised 2026-11-06 after the PR #2 review: the first version skipped `checks` and `benchmarks` on a title edit, and GitHub counts a skipped job as passing a required check, so a later title edit could hide a failing benchmark on the same commit.)
- **Reason:** The ticket asks for CI to be the gate the guide describes (rule 8, "Test subsets"), with least privilege and a title that lets Linear link the PR.
- **Departure from the ticket:** AKS-73 names the pattern `^AKS-[0-9]+: `. That pattern rejects a PR that closes several issues, such as PR #1 ("AKS-71, AKS-72: ..."). The pattern used here also accepts a list of identifiers separated by ", ". It also requires a non-space character after ": ", so an empty summary fails.
- **Security:** The title reaches the script through an environment variable, never through `${{ }}` inside the script, so a crafted title cannot inject shell commands.
- **Alternatives considered:**
  - A third-party title-check action: not needed for one regular expression, and it would add a dependency.
  - A job-level `if: hashFiles(...)` guard for benchmarks: `hashFiles` is not available in a job-level `if`, so a step does the check.
  - Running benchmarks on both versions: `check.sh` already runs them on both once they exist; the separate job makes the gate visible.
- **Actions pinned:** to a major version, as before. `actions/checkout@v4` and `actions/setup-python@v5` (both MIT, github.com/actions; already used since the M0 skeleton, so no new action). The tags were checked with `git ls-remote` on 2026-11-06. Newer majors exist (v5 to v7 for both). They were not adopted here, to keep the known-good versions; moving up is a separate change.
- **Verified:** actionlint 1.7.12 with shellcheck 0.11.0 reports no errors. The workflow parses with PyYAML. The title script was run on 14 titles: the 3 valid ones pass, the 11 invalid ones fail. The detection step was run on the current tree (skips) and on a mock M2 tree (runs).
- **Spec sections updated:** none.
- **Dependencies added:** none. actionlint and shellcheck were used once for checking, in a scratch environment, not added to the project.

## 2026-11-06 · M1

### M1 research notes: JSON Schema draft, validator and units library (AKS-85)

- **Decision:**
  - The schema pass uses JSON Schema draft 2020-12 and the `jsonschema` package, with no extras. The schema uses no `format` keyword.
  - pint is confirmed as the units library (spec 1 had it as "Proposed"). It will be declared as `pint>=0.25.3`.
  - The loader checks the spec 1 quantity grammar before pint converts. The grammar is now exact: a JSON-grammar number, exactly one space, and a Phase 1 unit symbol written exactly (`s`, `min`, `h`, `d`). A unit pint knows with the wrong dimension is E140; any other string that breaks the grammar is E141.
  - Notes: `docs/research/spec-1-existing-model-formats.md`, `docs/research/spec-1-how-tools-save-models.md`, `docs/research/spec-1-schema-and-units.md`. The first two change nothing in the specs.
- **Reason:**
  - 2020-12 is the current published JSON Schema version (json-schema.org, read 2026-11-06). The next release will make `format` validate by default, so a schema without `format` keeps its meaning.
  - jsonschema supports 2020-12, reports every error with its path, and is pure Python apart from `rpds-py`, which ships Windows wheels for CPython 3.11 to 3.15.
  - pint parses the four Phase 1 symbols correctly, and its `DimensionalityError` separates E140 from E141. A plain table of four units could not do that, and the physics phases need a full unit system.
  - Testing showed that pint alone accepts far more than spec 1's grammar allows: `2min`, `2 minutes`, `2 * min`, `nan s`, and `2 Min`, which it reads as 2 megainch. Hence the grammar check first. The exact grammar is the simplest reading of "a number, one space, a unit" with the Phase 1 unit list. It was taken without the owner (guide rule 5) and is flagged for the owner in the PR.
  - pint 0.26 dropped Python 3.11, and the project supports 3.11. With `>=0.25.3`, Python 3.11 gets 0.25.3 and newer Pythons get 0.26.x. 8,036 test conversions gave the same floats on both versions.
- **Alternatives considered:**
  - jsonschema-rs (MIT; supports 2020-12): faster, but a compiled dependency that small model files do not need.
  - fastjsonschema (BSD-3-Clause): reads no draft newer than 07.
  - unyt (BSD-3-Clause): needs numpy and sympy in the model layer.
  - astropy units (BSD-3-Clause): a large astronomy package.
  - A hand-written table of the four time units: cannot separate E140 from E141.
  - Raising the minimum Python to 3.12 to get one pint version everywhere: departs from the guide's "Python 3.11 or later" for no gain the tests showed.
- **Spec sections updated:** spec 1 "Units", "Validation" and "Quantities". A dated line is under spec 1 "Changes in this version". The version number is unchanged until M1 closes (guide rule 6).
- **Dependencies added:** none to `pyproject.toml` in this change. The first M1 code change adds them. Pre-recorded here with licences:

  | Package | Version seen | Licence | How checked |
  | --- | --- | --- | --- |
  | jsonschema | 4.26.0 | MIT | PyPI metadata `License-Expression` 2026-11-06; `COPYING` in the installed wheel and on GitHub read |
  | attrs | 26.1.0 | MIT | PyPI metadata; `LICENSE` in the installed wheel read |
  | jsonschema-specifications | 2025.9.1 | MIT | PyPI metadata; `COPYING` in the installed wheel read |
  | referencing | 0.37.0 | MIT | PyPI metadata; `COPYING` in the installed wheel read |
  | rpds-py | 2026.9.1 | MIT | PyPI metadata; `LICENSE` in the installed wheel read; Windows wheels in the PyPI file list |
  | pint | 0.26.2 (Python 3.12 or later), 0.25.3 (Python 3.11) | BSD-3-Clause | PyPI metadata; `LICENSE` in both installed wheels read (identical files) and on GitHub |
  | flexcache | 0.3 | BSD 3-clause text | PyPI classifier "BSD License"; `LICENSE` in the installed wheel read |
  | flexparser | 0.4 | BSD-3-Clause | PyPI metadata; `LICENSE` in the installed wheel read |
  | platformdirs | 4.14.5 | MIT | PyPI metadata; `LICENSE` in the installed wheel read |
  | typing-extensions | 4.16.0 | PSF-2.0 | PyPI metadata; `LICENSE` in the installed wheel read |

  - **AGPL-3.0 compatibility:** all of these are MIT, BSD 3-clause or PSF licences. The FSF licence list (read 2026-11-06) calls the Expat (MIT) licence, the modified BSD licence and the licence of Python 2.0.1 and later "compatible with the GNU GPL". Each may therefore be combined into the AGPL-3.0 product and imported in-process. Not legal advice; the spec 1 engine licence rule still applies.
  - **Avoided:** jsonschema's `format` extra pulls in `rfc3987` 1.3.8 (GPL-3.0-or-later per PyPI). That licence could still be combined with AGPL-3.0, but the extra is not needed.

### Units and quantities (AKS-86)

- **Decision:**
  - `src/lcsim/model/units.py` is the quantity layer. Public API: `Dimension` (`TIME`, `DIMENSIONLESS`), `Quantity` (frozen; `magnitude` as an SI float, `dimension`, and `unit`, the SI symbol), `PHASE_1_UNITS`, `units_of(dimension)`, `si_symbol(dimension)` (`s` or `1`, for the results `unit` column), `parse_quantity(text, expected)`, `read_quantity(value, expected)`, `read_number(value)`, and the errors `QuantityError`, `QuantityParseError` (E141), `QuantityDimensionError` (E140) and `QuantityKindError` (E123).
  - It is the only module that imports pint (tested). The grammar is matched first, as the AKS-85 entry decided; pint then tells E140 from E141 and converts to SI base units.
  - E140 versus E141: E140 only when pint knows the unit name and none of its readings has the expected dimension. pint gives some names several readings with different dimensions (`cd` is candela or centi-day; `ha` is hectare or hecto-year; 91 such names were found). If any reading has the expected dimension, the unit is the right kind but not a Phase 1 unit, so E141.
  - A number whose SI value is not finite (`"1e400 s"`, `"1e308 d"`) is E141. `"-0 s"` is stored as 0.0.
  - Values that are neither quantities nor numbers: where a plain number is expected, anything other than a finite JSON number is E123 (`true` is not a number, although Python's `bool` is an `int`). An integer is always finite and is returned unchanged, however large (`10**309` would overflow `math.isfinite`, found in review of PR #4); an E123 message names an integer of more than 64 bits as "a very large integer", because Python cannot print one of more than 4,300 digits. Where a quantity is expected, a JSON number is E123 and `true`, `false`, `null`, an array or an object is E141. `{"$param": ...}` references are resolved before these functions are called.
  - The errors carry `code`, `value`, a plain-language `message` that quotes the value, and a `hint`. They are not yet spec 1 issue objects: AKS-87 builds the issue type, and the meaning pass (AKS-89, AKS-90) turns each error into an issue with `component` and `path`, and names the setting in the message. No shared issue type was built here, to leave that to AKS-87.
- **Reason:**
  - The spec 1 grammar left these cases open; each is the simplest reading that keeps unknown or unusable values from loading (guide rule 5). They are flagged for the owner in the PR.
  - Building one `UnitRegistry` takes about 0.14 s, so it is built once per process, on first use.
  - pint 0.25.3 (Python 3.11) raises `KeyError` for the dimensionality of `dimensionless`, so the module states each dimension's pint dimensionality itself instead of asking pint for it. pint 0.25 declares `UnitRegistry` generic and 0.26 does not, so the one annotation that names it carries `# type: ignore[type-arg,unused-ignore]`.
- **Alternatives considered:**
  - E140 for any known unit whose first pint reading has another dimension: `2 cd` for a time would then be E140, although centi-day is a time.
  - E123 for every non-number where a quantity is expected: `true` or `null` is not "a plain number", which is what E123 names in that direction.
  - Returning the pint quantity: pint would then leave the model layer.
- **Tested:** `tests/model/test_units.py` has 118 tests (130 pass and 29 skip in the full run); line coverage of `units.py` is 100%. `bash scripts/check.sh` exits 0 on Python 3.13.18 with pint 0.26.2 and on Python 3.11.18 with pint 0.25.3. 510 numbers times the four Phase 1 units (2,040 conversions) give exactly `float(number) × factor`. A fuzz of about 100,000 `parse_quantity` calls per pint version (every pint unit name, prefixed names and random tokens, each against both dimensions) raised only `QuantityError`, never another exception.
- **Spec sections updated:** spec 1 "Quantities", with a dated line under "Changes in this version".
- **Dependencies added:** `pint>=0.25.3` in `pyproject.toml`. Licences of pint and its dependencies (flexcache, flexparser, platformdirs, typing-extensions) are recorded in the AKS-85 entry above; the installed versions match it (pint 0.26.2 and 0.25.3, flexcache 0.3, flexparser 0.4, platformdirs 4.14.5, typing-extensions 4.16.0).
