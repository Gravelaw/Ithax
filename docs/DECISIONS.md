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

### Issue objects, JSON Schema and the schema pass (AKS-87)

- **Decision:**
  - `src/lcsim/model/issues.py` holds the spec 1 issue object. Public API: `Issue` (frozen dataclass with `code`, `component`, `path`, `message`, `hint`, and `severity`, which follows from the code: `error` for E, `warning` for W), `Issue.as_dict()` (the spec 1 JSON object, keys in spec order), `Issue.from_problem(problem, *, where, path, component)`, the `CodedProblem` protocol (`code`, `message`, `hint`), `Severity`, and `pointer(*segments)` (an RFC 6901 JSON Pointer). An `Issue` refuses a code that is not `[EW]` and three digits, a path that is not a JSON Pointer, and an empty message or hint.
  - Hand-off from the units layer (AKS-86): `QuantityError` satisfies `CodedProblem`, so the meaning pass (AKS-89, AKS-90) writes `Issue.from_problem(error, where="the 'mean' setting of 'till'", path=..., component="till")`; the message becomes "In the 'mean' setting of 'till', '5 m' has the wrong kind of unit: a time is expected." and the hint is the error's own. Tested with real E140, E141 and E123 errors. No meaning-pass wiring is done here.
  - `src/lcsim/model/schema.json` is the static schema, kept as data (draft 2020-12, no `format`, `pattern` or `enum`). `src/lcsim/model/schema.py` exposes `FORMAT_VERSION` (`"0.1"`), `model_schema()` (a fresh copy, for `GET /v1/schema` at M6) and `schema_pass(document) -> list[Issue]`. The domain rules are two `if`/`then` branches on `domain`: each requires its own keys, forbids the other domain's keys with `{"not": {}}` and sets the item shape of `constraints`. The keys that belong to each domain are read from those branches, not listed twice.
  - What the schema types: identifiers and names (`domain`, a component's `type`, `metric`, `run.engine`) as strings, `params`, `ui`, `set` and `linear` as objects, lists as arrays. Quantities, plain numbers and the enumerated words (a parameter's or variable's `type`, `sense`, `op`, `run.target`, `run.fidelity`) take any JSON value, so that the meaning pass and the run checks report E123, E141, E150 to E152, E170 to E173 with their own codes. Spec 1 said such values are "typed as plain strings or objects"; read literally, `"length": true` would be E100, not the E141 that spec 1 "Quantities" requires.
  - Required keys where spec 1 left it open (simplest reading, guide rule 5): a parameter's `type` (spec 3 already rejects a new parameter without `value` and `type`); `target` and `fidelity` when `run` is present (only `engine` is called optional); both `id` and `set` of a scenario; `search.objective` (spec 1 gives defaults for `budget`, `variables` and `replications`, none for `objective`). `ui` is accepted only on a component, as spec 1 "Components and ports" says; a top-level `ui` is an unknown key.
  - An unknown `domain` (`"physics"`, `""`): the schema pass checks every key as for any model, but requires and forbids no domain-specific key; E102 is the meaning pass's.
  - E101: `format_version` must be two ASCII decimal integers without leading zeros joined by a dot. The parts are compared as digit strings (length, then text), never with `int()`, which Python refuses for more than 4,300 digits; path segments are sorted the same way. Another major, a higher minor, or a string of another form is E101, and nothing else is reported for that file, because it may follow another version's schema. A non-string `format_version` is E100. "0.0" and "0.1" pass. Spec 1's "a lower minor loads with defaults filled in memory" is met in this version by the loader (AKS-88), which fills every default for any accepted file: 0.1 is the only version, so no default differs by minor. AKS-92 adds the migration registry and decides which other majors can be opened.
  - Messages are written by lcsim and never copy the validator's text (research note `spec-1-schema-and-units.md`). `path` points at the key concerned; for a missing key it is where the key belongs (`/experiments/0/length`); `""` is the whole file. `component` is the id of the component the path lies in, when it has a string id; otherwise `null`. Several unknown or missing keys give one issue each. Issues are sorted by path with array indexes in numeric order. An unknown key's hint lists the keys allowed there (at top level, those of the model's domain). A key of the other domain gives one issue; nothing inside it is reported.
  - `tests/test_docs.py`: creating `tests/model/fixtures/issues/` switches on the 29 fixture tests, but this ticket owns only E100 and E101. A map `FIXTURE_PENDING` names the later ticket of each of the other 27 codes (AKS-89: E102, E110 to E112, E120 to E125, E130 to E132, E161; AKS-90: E140, E141, E150 to E152, E160, E162, E170, E171, E174; AKS-91: W200 to W202). A pending code skips with "fixture arrives with AKS-n"; a pending code that has a fixture fails, so each ticket must remove its codes when it adds their fixtures. A second test checks that every pending code is a spec 1 schema or meaning code. AKS-91 empties the map; its acceptance already requires the check to pass for all 29 codes.
- **Reason:** spec 1 "Validation", "Top-level keys", "Versioning", "Validation issues" and the M1 acceptance row; guide "Conventions", Errors. Keeping the schema as data lets the M6 service serve it unchanged and lets M2 compose adapter component types into it. Not creating the fixtures folder would have kept the E100 and E101 fixtures out of the place spec 1 names; adding placeholder fixtures for other tickets' codes would have tested nothing.
- **Alternatives considered:**
  - `unevaluatedProperties: false` with the domain keys only in the branches: jsonschema then treats every property of a failing branch as unevaluated, so one missing key would also report the domain's present keys as unknown (checked against jsonschema 4.26.0).
  - `false` subschemas for the other domain's keys: jsonschema 4.26.0 gives such an error the parent's path, not the key's, so the key could not be named; `{"not": {}}` gives the key's path (checked).
  - The schema written as a Python dict: works, but a JSON file is what `GET /v1/schema` serves and what a reader checks against spec 1.
  - Severity as a constructor argument: it could then disagree with the code.
  - Skipping the whole fixture test until AKS-91: E100 and E101 would go unchecked by `test_docs.py` until then.
- **Tested:** `tests/model/test_issues.py` (fixture test over 12 fixtures, 10 E100 and 2 E101, plus the issue object and `pointer`) and `tests/model/test_schema.py`. `bash scripts/check.sh` exits 0 on Python 3.13.18 (jsonschema 4.26.0, pint 0.26.2) and Python 3.11.18 (jsonschema 4.26.0, pint 0.25.3): 330 passed and 27 skipped (the pending fixture codes); line coverage of `src/lcsim` 100%. After review of PR #5, a second fuzz of 20,000 documents that adds keys and versions of 5,000 digits and non-string enumerated words gave 22,858 issues, all E100 or E101, and no exception; a third of 20,000 documents with integers of 5,000 digits in any place gave 26,697 issues and no exception. Nesting as deep as `json.loads` accepts (9,000 levels on Python 3.13) was validated without error. 40,000 randomly mutated coffee-shop and product-mix documents (keys deleted or added, values replaced with nulls, booleans, very large integers, arrays, objects, keys such as `/`, `~`, `²` and `10`) gave 55,584 issues and no exception; every issue was E100 or E101, none used validator text, and only a non-object file had the empty path. A wheel built with `pip wheel` contains `lcsim/model/schema.json`.
- **Review of PR #5 (Codex):** three findings, all confirmed by running them and fixed: the schema typed the enumerated words as strings, contradicting the spec 1 text above (now any JSON value, tested with 5, null, true, an array and an object); an object key of more than 4,300 digits and a `format_version` with such a part made `int()` raise `ValueError` (now compared as digit strings, tested with 5,000 digits). A second review round found that jsonschema itself prints the offending value with `repr()` when it builds an error, so an integer of more than 4,300 digits in a wrong place raised `ValueError` (confirmed). The schema pass now validates a copy in which every integer of more than 14,000 bits (about 4,200 digits) is 0; the copy keeps every key and JSON type, messages never print a number's value, and the copy is made only when such an integer exists. Both walks over the document use an explicit stack, not recursion. A third round found that issues were deduplicated with a list, which made 1,000 entries each missing three keys take 1.6 s and grow quadratically (measured); they are now deduplicated with a dict in insertion order, and 10,000 such entries take 1.6 s. A fourth round found that a key of the other domain with a wrong type, or with missing keys of its own, also got those issues (`"objective": {}` in a process model asked for `linear` and `sense`); every other error at such a key, not only below it, is now dropped.
- **Spec sections updated:** spec 1 "Validation", "Top-level keys", "Parameters", "Experiments", "Versioning" and "Validation issues", with a dated line under "Changes in this version". Version number unchanged until M1 closes (guide rule 6).
- **Dependencies added:**
  - `jsonschema>=4.26.0` in `pyproject.toml` `dependencies`. It and its dependencies (attrs, jsonschema-specifications, referencing, rpds-py) are recorded with licences in the AKS-85 entry above; the installed versions match it (jsonschema 4.26.0, attrs 26.1.0, jsonschema-specifications 2025.9.1, referencing 0.37.0, rpds-py 2026.9.1). No extras, so no `rfc3987`.
  - `types-jsonschema>=4.26.0.20261006` in the `dev` extra: type stubs from typeshed, because jsonschema ships no `py.typed` and the checks run `mypy --strict`. Licence Apache-2.0 (PyPI metadata `License-Expression` read 2026-11-06; the `LICENSE` in the installed wheel read: typeshed's Apache 2.0 text). It depends only on `referencing`. It is a development tool and is not shipped; the FSF licence list calls Apache 2.0 compatible with GPLv3, so it would not conflict even if it were. Not legal advice.

### Model loading, the process type catalogue and distribution definitions (AKS-88)

- **Decision:**
  - Three modules. `src/lcsim/model/catalogue.py` is data only: `DOMAINS`, `PROCESS_TYPES` (the twelve types of spec 2 "Block reference" as `BlockType`: `inputs`, `outputs`, `outputs_from`, `settings`, `metrics`, and `setting(name)`), `SettingSpec` (`kind`, `required`, `dimension`, `integer`, `many`, `choices`, `refers_to`, `fields`, `keyed_by`, `values`, `required_when`, `default`), `SettingKind` (number, quantity, distribution, identifier, object), `DISTRIBUTIONS` (`DistributionSpec` with one or more `forms` of `FieldSpec`; `FieldKind` quantity, number or data), `DATA_FIELDS`, `MODEL_METRICS` and `output_ports(block, routes)`. `src/lcsim/model/model.py` holds the frozen typed model (`Model`, `Meta`, `Parameter`, `Component` with `input_ports` and `output_ports`, `Distribution`, `DataRef`, `ParamRef`, `Connection`, `Endpoint`, `Experiment`, `Scenario`, `Search`, `MetricObjective`, `MetricConstraint`, `LinearProgram`, `Variable`, `LinearObjective`, `LinearConstraint`, `RunSettings`, and `Model.component(id)`); every mapping is read-only. `src/lcsim/model/loading.py` exposes `load_model(path, *, seed_source=None) -> Model` (raises `ModelLoadError` with `.issues`), `load_text(text | bytes) -> LoadResult`, `load_document(document) -> LoadResult` (`model`, `issues`, `errors`, `warnings`) and `SEED_LIMIT`.
  - The catalogue's metrics per type are spec 2 "Statistic definitions", for E174 (AKS-90). It records the spec's defaults for optional settings (`discipline` `fifo`, `on_full` `block`, `period` 24 h) but the loader does not fill them in: a component's settings are what the file says, and the engine applies the defaults at M2. Experiment defaults are filled, as the ticket and spec 1 "Experiments" require.
  - Every quantity is a `Quantity` holding an SI float; a `{"$param": "id"}` reference stays a `ParamRef` so that scenarios and searches change the parameter and every use follows. A reference is exactly one key `$param` with a text id; any other object is a plain value error (E123 for a number, E141 for a quantity, as the units layer already decides).
  - What loading reports. Loading reports every problem that stops a value from being converted, with its spec 1 code: E102 for a `domain` that is not `process` or `optimization`, E120, E121, E122, E123, E130 (an end that is not `<id>.<port>`), E140, E141, E150 (a scenario that sets an unknown parameter, whose value cannot be typed without the parameter's `type`) and E160 (a distribution that cannot be read). It does not report checks across the model (E110 to E112, E124, E125, E131, E132, E150 for `$param`, E151, E152, E160 consistency of field values, E161, E162, E170, E171, E174, W200 to W202): they are AKS-89 to AKS-91's, on a model that loads. A file with any error gives no model; issues are in document order. `tests/model/test_issues.py` now collects issues through `load_document`, so later passes join there.
  - Before the schema pass, `load_text` reads UTF-8 (a BOM is accepted). Non-JSON text (line and column given, never the parser's message), `NaN` and `Infinity` (Python's reader accepts them), a whole number longer than `sys.get_int_max_str_digits()`, nesting too deep for the JSON reader, and a key written twice in one object (Python keeps the last silently) are E100 with the path of the duplicate key or `""`. A file that cannot be opened raises `OSError`: the caller chose the path, it is not a model problem.
  - Readings taken without the owner (guide rule 5), each written into the specs:
    - E123 also covers a non-whole number where a whole number is expected, a word outside its list (a parameter's or variable's `type`, `sense`, `op`, `discipline`, `on_full`, `rule`) and a setting that should be text, an array or an object. No other code fits these, and spec 1 "Quantities" already uses E123 for "any value other than a finite JSON number" where a number is expected.
    - E160 also covers a distribution that cannot be read (not an object, no or unknown `dist`, missing or unknown field, both or neither of `values` and `data`, `values` not an array, `data` not `{file, column}`). E121 and E122 are about component settings; a distribution's fields are not settings.
    - A whole number written as `2.0` is accepted as 2 (JSON Schema's definition of an integer). A `quantity` parameter is a time, since time is the only dimension with Phase 1 units.
    - A missing `seed` is drawn at load with `secrets.randbelow(2**63)` (the operating system's generator, not Python's global one) and `Experiment.seed_chosen` is true. The ticket lists the seed among the defaults to fill; the manifest (M3) records it. An empty `scenarios` array gets the `default` scenario, like an absent one.
    - Process constraints take `op` `<=` or `>=` only; optimization constraints also `==`, which the assignment benchmark (spec 2, M5) needs. A process constraint's `value` is a plain number or a time quantity; whether its kind fits the metric is left to the meaning pass.
    - Spec 2 left some setting kinds open: `first_arrival` and `timeout` are time quantities; `max_items`, `queue_capacity`, queue `capacity`, `size`, the store's three stock levels, pool `capacity` and a shift's `capacity` are whole numbers. A queue's `discipline` is optional with default `fifo` (the table lists it without "optional", but the rule "`fifo` (default)" gives it a default). A branch's output ports are named by its routes (E161 already implies this).
    - Optimization variable bounds are plain numbers and a missing bound means none, as in Pyomo.
    - `run.target` and `run.fidelity` are kept as written, of any JSON type: spec 1 says a file naming `remote` or `cluster` still loads, and E172 and E173 are raised when a run starts.
  - Spec 1's "a lower minor loads with defaults filled in memory" (left to this ticket by AKS-87): a `0.0` file loads with every default filled; `Model.format_version` keeps the version as written. Tested.
  - `FIXTURE_PENDING` in `tests/test_docs.py` is unchanged. Loading now emits E102, E120 to E123, E130, E140, E141, E150 and E160, but their fixtures are part of AKS-89's and AKS-90's acceptance, so this ticket adds none and removes no code from the map.
- **Reason:** spec 1 "Validation", "Model file", "Units", "Parameters", "Components and ports", "Distributions", "Experiments", "Versioning"; spec 2 "Block reference", "Statistic definitions", "Mathematical optimization in the model file"; guide "Conventions" (types, units converted at load, errors as issue objects). A typed model cannot be built from a value that cannot be converted, so loading must say why, with the code a user will later see from the meaning pass. Keeping the catalogue as data lets M2 compare it with `capabilities()`.
- **Alternatives considered:**
  - A loader that reports nothing and builds only from a file that already passed the meaning pass: until AKS-89 and AKS-90 exist it would raise plain exceptions on bad values, which the guide forbids.
  - One class per distribution: more code for no gain; the sampler at M2 dispatches on `dist`, and the field list is data the meaning pass also reads.
  - Filling component setting defaults at load: the ticket asks only for experiment defaults, and some optional settings have no spec default (`first_arrival`, `max_items`).
  - Choosing the missing seed when a run starts: the ticket lists it as a load default; either way the manifest records it.
  - New issue codes for wrong words and unreadable distributions: spec 1's codes already name these conditions closely enough, and new codes would change the fixture set of AKS-89 to AKS-91.
- **Left open, for later tickets:**
  - Range checks with no spec 1 code (a `capacity` or `size` below 1, a negative weight, a `budget` below 1): not reported by anything yet. AKS-89 and AKS-90 decide which code covers them, or the spec gains one.
  - `weights` keys that are not routes, or routes without a weight: AKS-89 (E161 is about connections only).
  - Optimization coefficients that name no variable, and duplicate variable ids: spec 1 has no code; M5 verifies the optimization layout.
  - Phase 1 has no rate unit, so a constraint on `<sink>.throughput` can only be written as a plain number, presumably per second. Spec 1 does not say; owner question.
- **Tested:** `tests/model/test_catalogue.py` (every type's ports, every setting's kind and required status, choices, defaults, references, metrics, every distribution's forms and field kinds) and `tests/model/test_loading.py` (every public function; the coffee shop in SI with defaults filled; a `0.0` file; every block type and distribution, `weibull`, `empirical` with `values` and with `data`; `$param` in settings, distribution fields, `values` and `weights`; the product mix; each issue code loading reports, with `path`, `component` and a message naming the id and key). `bash scripts/check.sh` exits 0 on Python 3.13.18 (pint 0.26.2) and 3.11.18 (pint 0.25.3), 569 passed and 27 skipped (the pending fixture codes), line coverage of `src/lcsim` 100%. A fuzz of 40,000 randomly mutated coffee-shop, product-mix and all-block documents (values replaced with nulls, booleans, 5,000-digit integers, words, `$param` objects, distributions; keys deleted and added) gave 54,219 issues, raised no other exception, and no message or hint held exception or validator text; 5,000 corrupted JSON texts gave only issues. A `ui` nested 20,000 levels deep loads.
- **Spec sections updated:** spec 1 "Validation", "Parameters", "Components and ports", "Experiments", "Metric names" and "Validation issues" (E123 and E160 rows); spec 2 "Block reference", its "Schedule" rule and "Mathematical optimization in the model file". Each has a dated line under its "Changes in this version". Version numbers unchanged until M1 closes (guide rule 6).
- **Dependencies added:** none (`secrets`, `json` and `sys` are the standard library).

### Meaning pass A: identifiers, engines, settings and connections (AKS-89)

- **Decision:**
  - `src/lcsim/model/validation.py` is part A of the meaning pass, one function per rule group, each returning `list[Issue]`. Public API: `engine_issues(domain, engine, installed=STAND_IN_ENGINES)` (E102), `identifier_issues(model)` (E110, E111, E112), `setting_issues(model)` (E124, E125, and a branch's `weights` against its `routes`), `connection_issues(model)` (E130, E131, E132, E161), `meaning_pass(model)` (the last three), `InstalledEngine` (`name`, `domains`), `STAND_IN_ENGINES`, `IDENTIFIER_PATTERN`, `RESERVED_COMPONENT_IDS` and `RESERVED_SCENARIO_ID`.
  - The meaning pass runs on a model that builds (spec 1 "Validation": the checks across the model follow on a model that loads). A built model holds every entry at its index in the file, so every path points into the file. `load_document` now runs the schema pass, building and then `meaning_pass`; any error gives no model. The new `build_document` stops after building: `tests/model/test_loading.py` uses it to test building on fragments (a component added and left unconnected). `load_text` and `load_model` go through `load_document`, so they include the meaning pass.
  - `Experiment.default_scenario_added` (new field) is true when the file listed no scenarios and the loader added `default`. Without it a scenario the file itself calls `default` (E112) could not be told from the added one.
  - E102 follows spec 1 "Top-level keys": the one installed adapter whose capabilities include the `domain`; several with no `run.engine`, or none, is E102. With `run.engine`, the adapter of that name is chosen, and none of that name for the domain is E102 (the spec did not say; simplest reading). The path is `/domain` when nothing handles the domain, else `/run/engine`. Until adapters exist the model layer stands in, one `InstalledEngine(None, (domain,))` per Phase 1 domain; a stand-in has no name, so `run.engine` is not checked before M2 (`process`) and M5 (`optimization`). The ticket names the process stand-in only; the optimization stand-in keeps the product mix loading, as it did before this ticket. The loader calls `engine_issues` before building, as before.
  - Identifiers. The pattern is matched with `fullmatch` (`$` would accept a final newline). Spec 1 named four lists; this pass also applies the pattern and uniqueness to objective, constraint and variable ids and to a branch's routes. Results, `search.objective` and the optimization `summary.json` name these by id, and a route names an output port, so a repeat would be ambiguous. Scenario ids are unique within one experiment. Parameter ids cannot repeat (a repeated key is E100 when the file is read), but they are checked against the pattern. E110 is reported at each later use; an id off the pattern that repeats gets both E111 and E110. `Model` in another case is E111 only, not E112.
  - Settings. E124 when `pool` (server), or `target` (schedule, failure), names no component or a component of a type the catalogue's `refers_to` does not list. E125 at each later `schedule` on one server or pool, and each later `failure` on one server, counted only over targets that pass E124. A `weights` key that is not a route is E121 and a route without a weight E122, at `/components/<i>/params/weights/<key>`: these are an unknown key and a missing required key inside an object setting, which the loader already reports with E121 and E122 (a shift's keys), so no new code was needed.
  - Connections. A `from` end must name an output port of its component, a `to` end an input port: otherwise E130, except that a `from` on a branch naming a port that is not a route is E161 (spec 1 row). E131 is at `/components/<i>`, as spec 1's own example shows, or at the route's entry in `routes` for a branch. E132 is at each later connection's `from`. A connection whose `from` end is valid connects the port even when its `to` end is wrong, so a typo in `to` gives one issue. A typo in `from` gives E130 and also E131 for the port it meant; both are true. With a repeated component id (E110) the first component's ports are used, so the second is not reported again.
  - `component` is the id of the component the path lies in (spec 1 "Validation issues"; AKS-87), so issues at `/connections/...` (E130, E132, E161) have `component` null, as the loader's E130 already did.
  - Fixtures: 14 files, one per code this ticket owns, each the coffee shop with one fault: `E102_unknown_domain`, `E110_duplicate_component_id`, `E111_uppercase_component_id`, `E112_reserved_component_id`, `E120_unknown_component_type`, `E121_unknown_server_setting`, `E122_server_without_service`, `E123_quantity_as_capacity`, `E124_pool_names_unknown_component`, `E125_two_schedules_on_one_server`, `E130_unknown_component_in_connection`, `E131_server_out_unconnected`, `E132_server_out_connected_twice`, `E161_route_not_in_routes`. E120 to E123 come from the loader (AKS-88). Their codes left `FIXTURE_PENDING`, which now holds AKS-90's ten codes and AKS-91's three.
  - The fixture test in `tests/model/test_issues.py` asked every message to quote the last key of `path`. For an issue about a whole component (`/components/1`, spec 1's own E131 example) the last key is `components`, which the spec's example message does not quote. The acceptance row says the message "names the component id or key concerned", so for such a path the test now checks the component id only (it already did).
- **Reason:** spec 1 "Identifiers", "Top-level keys", "Components and ports", "Validation", "Validation issues"; spec 2 "Block reference" and "Targets"; the AKS-89 acceptance list. A model that runs must have no dangling connections and no setting that names nothing.
- **Alternatives considered:**
  - Running the meaning pass on the raw document: paths would be as easy, but values would be read twice, and AKS-90 needs the converted model; one input type for every rule group is simpler.
  - A `meaning` flag on `load_document` instead of `build_document`: a flag on the main entry point is easier to leave off by mistake.
  - Making `test_loading.py` wire every added component: many building tests would test connections too.
  - A new code for `weights` keys: E121 and E122 already mean an unknown and a missing key in a setting.
  - `component` filled with the origin component for E132 and E161: departs from the spec 1 definition of `component`.
  - Rejecting any `run.engine` before M2: a file naming the adapter it will need would fail now and load at M2.
- **AKS-88 open items:** taken on: `weights` keys against `routes` (E121, E122); duplicate variable ids (E110), as part of identifiers. Left: range checks with no code (a `capacity` or `size` below 1, a negative weight, a `budget` below 1, an empty `routes`), which are the value half of the meaning pass (AKS-90) or need a code; optimization coefficients that name no variable (a reference, not an identifier, setting or connection; spec 1 has no code; M5 verifies the optimization layout); the rate unit for throughput constraints (owner question). Also left: `weights` given with the `shortest_queue` rule is accepted and unused; spec 2 does not say it is wrong.
- **Tested:** `tests/model/test_validation.py` (every function and branch: engine lookup with stand-ins and with fake installed adapters, each identifier list, reserved ids, the added `default` scenario, every `pool` and `target` case, E125 for schedules on servers and pools and for failures, `weights`, every connection end, routes, repeated ids, the loader entry points). `bash scripts/check.sh` exits 0 on Python 3.13.18 (pint 0.26.2) and 3.11.18 (pint 0.25.3): 693 passed and 13 skipped (the pending fixture codes); line coverage of `src/lcsim` 100%. A fuzz of 20,000 coffee-shop documents with branches, pools, schedules, failures and queues added and ids, connection ends, targets, pools, routes, weights, scenarios, experiments and objectives replaced from a list of valid, invalid and reserved words gave 91,018 issues and no exception; no message or hint held exception text, and every issue at a component path had that component's id as `component`.
- **Spec sections updated:** spec 1 "Identifiers", "Top-level keys", "Components and ports" and the E121 and E122 rows of "Validation issues", with a dated line under "Changes in this version". Version number unchanged until M1 closes (guide rule 6).
- **Dependencies added:** none (`re` and `dataclasses` are the standard library).

### Meaning pass B: parameters, values, distributions, data, experiments and metrics (AKS-90)

- **Decision:**
  - `src/lcsim/model/validation.py` gains part B of the meaning pass, one function per rule group, each returning `list[Issue]`: `parameter_issues(model)` (E151), `reference_issues(model)` (E150, E152 for `$param` in components), `range_issues(model)` (E123 for values out of range), `distribution_issues(model)` (E160), `data_issues(model, data=EMPTY_DATA_INDEX)` (E162), `experiment_issues(model)` (E170, E171, and E150 for a search variable) and `metric_issues(model)` (E174, and E123 for a constraint `value` of the wrong kind). `meaning_pass(model, data=EMPTY_DATA_INDEX)` runs part A and then these, in that order.
  - `src/lcsim/model/data.py` is new: `DataColumn` (`name`, `unit`: the declared unit, or `None` for plain numbers), `DataFile` (`name`, `columns`, `sha256` at import; `column(name)`), `DataIndex` (`folder`, `files`; `file(name)`, `current_sha256(name)`), `file_sha256(path)` and `EMPTY_DATA_INDEX`. A file name must be a name in the folder (no `/`, `\`, `.` or `..`), the hash 64 lower-case hex digits, and an index with files needs its folder. The column index file format is the import endpoint's (M6); this type holds only what E162 checks. `load_document`, `load_text` and `load_model` take `data=` (default: the empty index) and pass it to the meaning pass.
  - `src/lcsim/model/catalogue.py`: `SettingSpec` gains `minimum`, `exclusive_minimum` and `min_items`; `FieldSpec` gains `positive`; `DistributionSpec` gains `ordered`; `MeasureKind` and `MEASURE_KINDS` say whether each metric is a time, a rate or a plain number.
  - E140 and E141 were already reported by the loader (AKS-88) with the setting and component named; this ticket adds their fixtures only.
  - Values from parameters. A setting or distribution field that refers to a parameter is checked against every value the model gives that parameter: its `value`, each scenario that sets it, and its `min` and `max`. `min` and `max` are included because they are the range a search explores, and a search's default variables are every parameter with both. Where several parameters feed one check (two weights, a uniform's `min` and `max`, a shift's `start` and `end`), every combination of their bounds is checked too, since a search varies them together; above 12 parameters, only all at their lowest and all at their highest bound. Every such check is a linear inequality, or "not all zero" over values each at least zero, so it fails somewhere in the box of bounds only if it fails at a corner. An issue names the first case that fails ("with the parameter 'tills' at its 'min'", "in scenario 'none' of experiment 'base'", "with 'x' at its 'min' and 'y' at its 'min'") and is reported once, at the setting, with the component filled. A reference with E150 or E152 is not checked further.
  - E151 is at the parameter's `value`, or at the scenario's entry in `set`. A `min` above the `max` is one E151 at `min`, and that parameter's values are then not compared with them.
  - E152 fits: `integer` where a whole number is taken; `integer` or `number` where a plain number is taken (a weight, a weibull `shape`); `quantity` where a time is taken.
  - Ranges of settings (the AKS-88 and AKS-89 open items) are E123, not a new code. E123 already covers "any value that is not of the kind its place takes", including a non-whole number where a whole number is expected; a capacity of 0 is the same kind of fault. The smallest values: a server's, queue's or pool's `capacity`, a batch's `size`, a store's `order_quantity` and a source's `max_items` at least 1; a `queue_capacity`, `initial`, `reorder_point` and shift `capacity` at least 0; each weight at least 0 and not all zero; `first_arrival` and a shift's `start` at least 0 s; `timeout` and `period` above 0 s; at least one route; a shift's `end` after its `start` and no later than `period`. `queue_capacity` 0 is allowed because the spec 2 loss benchmark uses it; shift capacity 0 is allowed because capacity outside a shift is 0 anyway.
  - E160, as spec 1 lists it: `sd`, `shape` and `scale` above zero, the `mean` of `exponential` and `lognormal` above zero, `min` not above `max`, and `values` not empty. Two additions. A triangular `mode` outside `min` to `max` is E160 at `mode`, since the fields are then inconsistent. A `min` equal to `max` is allowed, since spec 1 names only "above".
  - E162 is checked against the data index. A `file` not in the index is E162 at `.../data/file`. So is a file in the index that is now missing from the folder, or whose SHA-256 differs from the one recorded at import. A `column` the file does not have is E162 at `.../data/column`. Each file is hashed once per pass. At M1 the index is empty, so every `data` reference is E162, which is the fixture. No values are read, no declared unit is checked against the setting, and nothing is sampled: that is M6.
  - E170, each at its own key: `length` not above 0 s; `warmup` below 0 s, or not less than `length`; `replications` below 2; `confidence` outside (0, 1); `record_interval` not above 0 s (checked only when `length` is valid, so a default of `length` / 200 is not reported twice); `search.budget` below 1; `search.replications` below 2. A search's budget and replications are values of the experiment, not names, so they are E170, not E171.
  - E171: a `search.objective` that is not an objective id; a variable without both `min` and `max`; and a search with no variables. The last covers an empty list, or none listed when no parameter has both bounds. A search variable that is not a parameter is E150, since it is a reference to an unknown parameter.
  - E174: a metric is `<component id>.<measure>` with the measure exactly as spec 2 lists it for the component's type (`till.wait` is not `till.wait.mean`), or `model.wip.mean`. The message lists the metrics the type reports, or says it reports none. With a repeated component id, the first component is used. Issues at `/objectives/...` and `/constraints/...` have `component` null, since the path is not in a component (spec 1 "Validation issues").
  - Throughput constraints (owner question from AKS-88, raised again in the AKS-90 comments). Phase 1 has no rate unit. The simplest reading taken here: a constraint on a rate (`throughput`, `orders`, `discarded`) takes a plain number of items per second, the SI unit in which results store rates. So 30 per hour is written `0.008333`. A constraint on a time metric (`wait.mean`, `cycle_time.mean`) takes a time quantity, and any other metric takes a plain number. A `value` of the wrong kind is E123, which spec 1 "Quantities" already uses for a quantity where a number is expected, and the reverse. Flagged for the owner.
  - Fixtures, one per code, each the coffee shop with one fault: `E140_service_mean_in_metres`, `E141_service_mean_without_space`, `E150_capacity_names_unknown_parameter`, `E151_parameter_value_above_max`, `E152_number_parameter_as_capacity`, `E160_uniform_min_above_max`, `E162_data_file_not_imported`, `E170_warmup_not_less_than_length`, `E171_search_names_unknown_objective`, `E174_objective_names_undefined_metric`. These ten codes left `FIXTURE_PENDING`, which now holds only AKS-91's W200 to W202.
- **Reason:** spec 1 "Parameters", "Quantities", "Distributions", "Experiments", "Metric names" and "Validation issues"; spec 2 "Block reference", "Schedule" and "Statistic definitions"; the AKS-90 acceptance list and comments. Where the specs were silent, each reading is the simplest one that keeps a model the engines cannot run from loading (guide rule 5). Each is written into the specs.
- **Alternatives considered:**
  - A new code for out-of-range settings (for example E126): clearer to a reader of the code list. But the fault is close to E123's, a new code changes the count of 29 fixture codes that AKS-91's acceptance names, and the user sees the message, not the code.
  - A rate unit such as `1/h` or `/h` in the quantity grammar: friendlier to write. But it is a grammar change in the units layer, and it needs a third dimension in `units.py` and in the results `unit` column. It can be added later as an additive minor version if the owner wants it.
  - Checking parameter-fed settings only at the parameter's `value`: a scenario or a search could then run with a capacity of 0.
  - Reporting at the parameter rather than at the setting: the parameter may feed several settings with different ranges, and the setting is where the rule lives.
  - E171 for a search variable that is not a parameter: spec 1's E171 names "a parameter without `min` and `max`", which assumes the parameter exists, while E150 is exactly "reference to an unknown parameter".
  - Checking negative times in distributions (a `constant` of `-1 min`, a `uniform` with a negative `min`): spec 1 does not list them under E160, and spec 2 clips only the normal. Left as an open item below.
- **Left open:**
  - A time distribution that can give negative times (`constant`, `uniform`, `triangular` or `empirical` below 0 s) is not reported. Spec 1 lists no such check. Owner question; M2's sampling would otherwise meet it.
  - A data column's declared unit against the setting's dimension, and reading the column: M6, with the import endpoint.
  - A repeated entry in `search.variables` is accepted.
  - `weights` given with the `shortest_queue` rule are still checked (each at least 0, not all zero) although unused (AKS-89 left this open).
  - AKS-89's other open item, optimization coefficients that name no variable, stays with M5.
- **Tested:**
  - `tests/model/test_validation_b.py` (161 tests) covers every rule group and branch: each minimum and its boundary, cases from `value`, `min`, `max` and scenarios, the weights and shift rules, every positive and ordered field, every E162 case against a real folder (missing, changed, unknown file and column, hashed once), every E170 and E171 case, every metric form and constraint kind, and the loader entry points with `data=`.
  - `tests/model/test_data.py` covers the data index; `tests/model/test_catalogue.py` covers the new catalogue data.
  - `bash scripts/check.sh` exits 0 on Python 3.13.18 (pint 0.26.2) and Python 3.11.18 (pint 0.25.3): 925 passed and 3 skipped (AKS-91's pending codes); line coverage of `src/lcsim` 100%.
  - A fuzz of 30,000 coffee-shop documents (20,000 on Python 3.13 and 10,000 on 3.11) gave 94,265 issues and no exception. It drew parameters of each type with random bounds, references to known and unknown parameters, every distribution with random fields, schedules, branches with weights, experiment values, scenarios, searches, metrics and constraint values, all against a data index with a real file. No message or hint held exception text, and every issue at a component path had that component's id.
- **Review of PR #9 (Codex):** two findings, both confirmed by running them and fixed.
  - Parameters were varied one at a time, so two weights fed by parameters with `min` 0 passed, although a search can set both to 0 at once (confirmed: no issue). Joint combinations of bounds are now checked, as above.
  - The all-zero weights check summed the weights, and a weight of `10**309` beside `1.0` raised `OverflowError` from `load_document` (confirmed). It now tests whether any weight is above zero, without arithmetic.
  - A second fuzz of 30,000 documents, adding integers of 401 digits to every number, gave 93,518 issues and no exception.
- **Spec sections updated:** spec 1 "Parameters", "Distributions", "Experiments", "Metric names", and the E123, E150, E151, E160, E162, E170 and E171 rows of "Validation issues"; spec 2 "Rules that apply across blocks" ("Ranges"). Each has a dated line under its "Changes in this version". Version numbers are unchanged until M1 closes (guide rule 6).
- **Dependencies added:** none (`hashlib` is the standard library).

### Warnings W200, W201 and W202 and the complete fixture set (AKS-91)

- **Decision:**
  - `src/lcsim/model/validation.py` gains the three meaning-pass warnings, one function each, returning `list[Issue]`: `unreachable_issues(model)` (W200), `load_issues(model)` (W201) and `clipping_issues(model)` (W202). `meaning_pass` runs them last, after part B. Two helpers are public because spec 4's `unstable` finding must reuse the same computation ("one computation, not two"): `flow_rates(model, values=None)`, the mean arrival rate in units per second at each component with an input port (`None` where it cannot be propagated), and `distribution_mean(model, distribution, values=None, *, dimension=TIME)`, the theoretical mean in SI units (`None` where it cannot be known). Warnings do not block: a file with only warnings still gives a model (tested on each W fixture).
  - The graph. A connection carries items only when both its ends are valid and it is the first from its output port (a later one is E132). With a repeated component id (E110), the first component is used and the later one is not checked. W200 walks this graph from every `source` and names, at `/components/<i>`, each component with an input port that no walk reaches; blocks without an input port (`source`, `resource_pool`, `schedule`, `failure`) are never named.
  - W201 propagation, exactly as spec 1 "Validation" lists it, with closed-form arithmetic only (guide rule 7). Blocks are visited in topological order (Kahn's algorithm); merges add. A source gives 1 / the mean of its `interarrival`. A probability branch gives each route weight/total of its flow, a batch divides by `size`, an unbatch multiplies by the size of each batch it receives, and a server, a delay and a blocking `queue` pass their flow on. A shortest-queue branch, a store, a batch with `timeout`, a discarding `queue` and a source whose next block has a finite capacity stop the rate: every server after them is skipped. A server is checked when its rate is known and its queue is unlimited (no `queue_capacity`): W201 when rate × mean service time ≥ `capacity`, at `/components/<i>`. Rates are exact fractions (`fractions.Fraction`), so a load of exactly 1 is reported. The message gives the rate per hour, the mean service time, the load and the capacity.
  - Readings taken where spec 1 was silent (guide rule 5), each written into spec 1 "Validation":
    - A block with a finite capacity, for the loss point "a source whose next block has a finite capacity", is a `queue` or a server with `queue_capacity`. Only the block the source's `out` connects to counts; a source feeding a branch or delay that feeds such a block is not a loss point.
    - A schedule or failure stops the rate at the server whose capacity it changes: its target, or a server whose `pool` is the target of a schedule. That server is not checked either: a schedule's shift capacity may differ from `capacity`, so "its capacity" has no single value.
    - An unbatch undoes one level of batching: a batch of 3 batches of 2 becomes 3 batches of 2. A single item passes an unbatch unchanged (spec 2: "an `unbatch` splits whatever it receives").
    - A block on a loop of connections (a rework loop), or after one, is skipped. Its rate would need the traffic equations solved, which is a linear system: a numerical solver, which rule 7 forbids. Kahn's order never reaches such a block, so no loop is iterated.
    - A value that cannot be read stops the rate: a reference with E150 or E152, distribution fields that are inconsistent (E160), weights that are negative, missing or all zero, a batch `size` below 1, an `empirical` `data` column (the model layer reads no values), and an interarrival mean not above zero (a `constant` 0 s gives no finite rate). A server with an unknown capacity or service mean is not checked.
    - A source with `max_items` is still checked: spec 1 propagates from every source, and the queue grows over the run even if it stops later.
    - A block no source reaches gets rate 0, so an unreached server gets no W201 (it has W200).
    - A server downstream of an unstable server is checked against the offered rate, not the upstream server's output rate (`capacity` / mean service time), because spec 1 lists no cap. Such a server would be overloaded once the upstream one is fixed. Flagged for the owner below.
  - The mean of a distribution is its theoretical mean from the spec 1 sampling test: `constant` value; `exponential` mean; `uniform` (min + max)/2; `triangular` (min + mode + max)/3; `lognormal` mean; `weibull` scale·Γ(1 + 1/shape); `empirical` the mean of `values`. A `normal` is sampled clipped at zero (spec 1 "Distributions"), so its mean is that of the clipped variable, mean·Φ(mean/sd) + sd·φ(mean/sd) (`math.erfc` and `math.exp`). It equals `mean` to within one part in 10⁷ when `mean` ≥ 5 `sd`, the sampling test's condition (tested: 600.0000064 s for mean 10 min, sd 2 min). A weibull whose mean overflows a float gives no mean.
  - W202 at the distribution (for example `/components/1/params/service`) for every `normal` whose `mean` is below 2 × `sd`, in any setting. The message gives the share of samples below zero, Φ(−mean/sd), and the clipped mean. A normal with `sd` not above zero (E160) or a reference with E150 or E152 is not checked. `mean` = 2 × `sd` exactly (2.3% clipped) is not reported, since spec 1 says "<".
  - Parameter cases for warnings. W201 and W202 are checked with each parameter at its `value`, then in each scenario that sets a parameter; the first case that fails is named ("in scenario 'one' of experiment 'base'"). They are not checked at `min`, `max` or their combinations, unlike the errors of AKS-90: a search tries values the modeller may expect to be poor, as in spec 2's machine-count benchmark, and a warning there would be noise. Spec 1 "Parameters" now says its bounds rule is for errors.
  - Fixtures, each the coffee shop with one fault: `W200_sink_no_source_reaches` (an extra sink, `spare_exit`, with nothing connected to it), `W201_till_cannot_keep_up` (service mean 2.5 min, load 1.25 on one till) and `W202_normal_service_clips_at_zero` (service `normal` mean 1.5 min, sd 1 min: 6.7% clipped, load 0.765, so no W201). Each yields its code as its only issue.
  - `FIXTURE_PENDING` removed, not left empty. Its own comment said "AKS-91 empties this map", and its second test allowed only AKS-90 and AKS-91 as owners, so no later ticket could use it. An empty map would keep a skip branch that never runs and invite a code to be added without its fixture. `tests/test_docs.py` now asserts that the fixtures folder exists (it skipped "from M1" before; M1 is here) and that spec 1 lists exactly 29 schema and meaning codes, so the 29 per-code checks run with no skip. A code added to spec 1 later must arrive with its fixture.
  - Two earlier tests now also expect a W200: removing the till-to-exit connection, and a branch with no routes, both cut the exit off from the source.
- **Reason:** spec 1 "Validation", "Distributions" and "Validation issues" (W rows); spec 2 "Block reference" and "Statistic definitions"; the AKS-91 acceptance list; guide rules 5 and 7.
- **Alternatives considered:**
  - Capping a server's output at `capacity` / mean service time when it is overloaded: closer to the long-run rate downstream, and quieter. Not in spec 1's propagation rule; left to the owner.
  - Solving the rate on a loop as λ / (1 − p) for a single loop: closed form for one loop, but loops in general need a linear system. Skipping every loop is one rule.
  - Floating-point rates: a load of exactly 1 (interarrival and service both 6 s) could round either way.
  - Checking warnings at `min` and `max` as the errors are: warns on correct models whose search range includes poor values.
  - The plain `mean` for a normal: wrong by more than 0.4% exactly where W202 fires, and negative or zero for a normal with `mean` ≤ 0.
  - W201 at the server's `service` or `capacity`: the warning is about the server as a whole, as spec 4's `unstable` finding is.
- **Awaiting owner:**
  - Whether a server downstream of an overloaded server should be checked against the offered rate (now) or the upstream server's capacity / service time.
  - Whether a source feeding a branch or delay that feeds a finite-capacity block is also a loss point (now: only the block the source connects to counts).
  - Whether warnings should also be checked across a search's `min` and `max` (now: `value` and scenarios only).
- **Tested:**
  - `tests/model/test_validation_w.py` (107 tests): W200 on reached, unreached, looped, wrongly connected, doubly connected and repeated blocks; every distribution's mean against its formula, exact where the formula is exact, and every case with no mean; W201 for each propagation rule (branch weights, merges, batch, unbatch, nested batches, mixed batched and single items, blocking queue), each skip case (shortest queue, store, timeout, discarding queue, source into a queue or a limited server, schedule, failure, pool with a schedule, loop, merge with an unknown input, unreadable values), scenarios, parameters, the exact boundary, huge and tiny values; W202 in each setting, at the boundary, in a scenario, and not for unusable normals.
  - A cross-check of 5,000 random lines (source, then servers, delays, batches, unbatches and probability branches) against an independent floating-point computation: every rate agreed to 1e-12 and every server's W201 matched (469 warned).
  - A fuzz of 40,000 random process graphs (every block type, every distribution, bad and huge values, integers of 401 digits, references to unknown parameters, loops, wrong and doubled connections, repeated ids, scenarios) gave 216,199 issues and no exception; no warning message held exception text, and every warning at a component path had that component's id.
  - `bash scripts/check.sh` exits 0 on Python 3.13.18 (pint 0.26.2) and 3.11.18 (pint 0.25.3): 1,038 passed, 0 skipped (after the review fix); line coverage of `src/lcsim` 100%. All 29 per-code fixture checks in `tests/test_docs.py` pass.
- **Review of PR #10 (Codex):** one finding, confirmed by running it and fixed. A `normal` with `mean` and `sd` both `1.7e308 s` (valid, finite fields) has a clipped mean beyond the range of a float, and turning it into a `Fraction` for the W202 message raised `OverflowError` from `load_document`. The message now shows such a mean as "a very long time" (test added). A further fuzz of 40,000 graphs with times near the largest float (`1.7e308 s`, `1.79e308 s`, `-1.7e308 s`) gave 219,131 issues and no exception.
- **Spec sections updated:** spec 1 "Validation" (the W201 details and the cases for warnings), "Parameters" (its bounds rule is for errors) and the W200 row of "Validation issues", with a dated line under "Changes in this version". Version number unchanged until M1 closes (guide rule 6).
- **Dependencies added:** none (`fractions`, `math` and `collections` are the standard library).

### Format versioning and the test-only migration (AKS-92)

- **Decision:**
  - `src/lcsim/model/migration.py` owns the format version rules. Public API: `FORMAT_VERSION` (`"0.1"`, moved here from `schema.py`, which still exports it), `parse_version(version) -> tuple[str, str] | None` (the major and minor as digit strings, or `None` for any other form), `Migration` (a function from a model dict of one major to a model dict of another), `MigrationRegistry` with `register(from_major, to_major, migration)`, `unregister(from_major, to_major)`, `pairs()` and `route(from_major, to_major)`, the program's registry `MIGRATIONS`, `can_open(version, *, registry=MIGRATIONS) -> bool`, `version_issue(version, *, registry=MIGRATIONS) -> Issue | None` and `migrate(document, to_version=FORMAT_VERSION, *, registry=MIGRATIONS) -> MigrationResult` (`document`, `issues`, `migrated`).
  - Which other majors can be opened (left to this ticket by AKS-87): exactly those from which a chain of registered migrations leads to the reader's major. Format 0 ships no migration, so `MIGRATIONS` is empty and no other major opens. A file of the reader's major with a minor above the reader's (`"0.2"`) is never passed to a migration, whatever the target.
  - The model layer never migrates on its own and never writes a file. Loading a file of another major is E101 even when a migration exists; the schema pass now takes its E101 from `version_issue`, whose hint for such a file says "This program can convert the file to format version 0.1. Convert it when the program offers to; the file is rewritten only after you agree." The caller (service at M6, interface at M9) asks the user, calls `migrate`, loads the result, and saves it only after the user agrees. `migrated` tells it whether there is anything to ask about.
  - `migrate` returns a copy and never changes the dict it is given (the copy is made with an explicit stack, so a `ui` nested 20,000 levels deep is copied without recursion). A file of the target's major and a minor no higher is returned unchanged with `migrated` false (minor versions need no migration; the loader fills defaults). Otherwise the shortest chain of registered steps is applied, breadth first, with steps tried in numeric order of majors. A missing or non-text `format_version` is E100; a version that cannot be brought to the target is E101, the same issue the schema pass reports when the target is the reader's version.
  - A migration that writes a `format_version` other than a version of its target major, or whose last step writes a minor above the target's, raises `ValueError`: that is a fault of the program, not of the user's file, so it is not an issue object. A target that is not `MAJOR.MINOR` also raises `ValueError`.
  - Majors are kept as digit strings and compared by length, then text, never with `int()` (AKS-87's rule for versions of more than 4,300 digits). `register` takes a whole number or a digit string; it refuses a pair registered twice, two equal majors (a minor increase needs no migration), negative numbers, leading zeros, booleans and other types.
  - The acceptance test (`tests/model/test_migration.py`) defines the test-only migration in the test file and registers it in `MIGRATIONS` from a fixture that unregisters it afterwards: 0 to 99.0 renames `components` to `blocks` and `connections` to `links`, keeping key order; 99 to 0 renames them back and writes `"0.1"`. Major 99 is far from the first real major (1), so the two cannot collide. The test migrates `examples/coffee_shop.json` to 99.0 and back, checks that the 99.0 document is E101 with the "can convert" hint, that the round trip serializes to the same bytes as the original, and that the result loads with zero issues. A second test starts a fresh interpreter and checks that `MIGRATIONS` is empty there, so the test migration is not shipped.
  - "Byte-equal after the round trip" (AKS-92 acceptance) is read as: the round-tripped dict, written with one fixed serializer (`json.dumps(..., ensure_ascii=False, indent=2)`), gives the same bytes as the original dict written the same way. That compares every key, key order, value and JSON number type (`1` against `1.0`). The file's own whitespace is not compared, because migrations rewrite a model dict, not text, and the model layer never writes the file; the test checks instead that the file's bytes are unchanged on disk.
- **Reason:** spec 1 "Versioning" and its M1 acceptance row; the AKS-92 acceptance list and agent notes (the "ask the user" step stays out of the model layer); guide "Conventions", Errors. Spec 1 said E101 is for "an unknown major" and that a migration rewrites the file "after asking the user"; the model layer cannot ask, so the simplest reading is that a file with a migration is still not opened as it is (guide rule 5).
- **Alternatives considered:**
  - Migrating in memory inside the loader when a migration exists: opens the file without asking the user, which spec 1 forbids for a major change.
  - A new issue code for "convertible": spec 1 lists none, and E101 with a different hint tells the caller and the user the same thing.
  - A registry passed to every function with no global: the schema pass and the loader would need a registry argument too; one module-level registry, with an optional `registry` argument on the functions for tests, keeps the loading API unchanged.
  - Keeping `FORMAT_VERSION` in `schema.py`: `migration.py` needs it and `schema.py` needs the registry, which would make an import cycle.
  - Comparing the round trip against the file's bytes: would need a writer that reproduces hand formatting, which no spec defines.
- **Tested:** `tests/model/test_migration.py` (73 tests): the acceptance round trip; value types, key order and non-ASCII text through the round trip; an empty registry in a fresh interpreter; `parse_version` on valid, invalid and 5,000-digit versions; `register`, `unregister`, `pairs` and `route` including refusals, numeric order, shortest chains and 5,000-digit majors; `can_open` and `version_issue` for the reader's versions, newer minors, other majors with and without a route; the schema pass hint; that loading never migrates; `migrate` within one major, by default to the reader, without changing its input, over two steps, E100 and E101 (to the reader's version, equal to the schema pass's issue, and to another version), and each `ValueError`; a 20,000-level copy. A fuzz of 20,000 random versions against random registries checked that `can_open` agrees with `version_issue`, that `migrate` gives a document exactly when `can_open` is true, and that every migrated document reached the target major and loaded without E101. `bash scripts/check.sh` exits 0 on Python 3.13.18 (pint 0.26.2, jsonschema 4.26.0) and 3.11.18 (pint 0.25.3, jsonschema 4.26.0): 1,111 passed, 0 skipped; line coverage of `src/lcsim` 100%.
- **Spec sections updated:** spec 1 "Versioning", with a dated line under "Changes in this version". Version number unchanged until M1 closes (guide rule 6).
- **Dependencies added:** none (`collections.deque`, `re` and `dataclasses` are the standard library).

### Example models: `three_machine_line.json` and `warehouse.json` (AKS-93)

- **Decision:**
  - **Owner decision 1 (AKS-74) has no answer, so option (b) applies** (guide rule 5): both files are written fresh at M1, with M2 blocks only, to the spec 2 targets, as the council's proposed default above ("Spec council review", 2026-11-05) and the guide's known-gaps table say. Owner to confirm. If the owner later supplies the originals, they replace these files and this entry is superseded.
  - `examples/three_machine_line.json`: `arrivals` (source, exponential interarrival mean 2 min, 30 per hour) → `cut` (server, capacity 1, exponential mean 1.2 min) → `weld` (server, capacity 1, exponential mean 1.8 min) → `transfer` (delay, constant 2 min) → `paint` (server, capacity 1, exponential mean 1 min) → `exit` (sink). Experiment `base`: 100 h, warm-up 20 h, 30 replications, seed 12345.
  - `examples/warehouse.json`: `orders` (source, exponential interarrival mean 1 min, 60 per hour) → `pick` (server, capacity 3, exponential mean 2 min) → `check` (branch, `probability`, routes `direct` weight 4 and `inspect` weight 1) → `direct` to `pack`, `inspect` through `inspection` (delay, constant 5 min) to `pack` → `pack` (server, capacity 1, exponential mean 0.8 min) → `dispatch` (sink). Experiment `base`: 200 h, warm-up 10 h, 30 replications, seed 12345.
  - Where each value comes from:
    - Arrival rates: the warehouse's 60 per hour is the spec 2 target; the line's 30 per hour (mean 2 min) is the coffee shop's and the spec 2 M/M/1 benchmark's arrival rate.
    - Service means: chosen so that utilization = arrival rate × mean service time / capacity meets the spec 2 targets with exact, short decimals: weld 0.90 (target 0.85 to 0.92; the prototype's 0.90), cut 0.60 and paint 0.50 (target below 0.70), pack 0.80 (target 0.75 to 0.85; the prototype's 0.83 rounded to a value with an exact mean), pick 2/3. Every station stays at or above 0.30, so spec 4's `idle_capacity` does not fire, and the weld station is the single highest, so `bottleneck` can fire only there.
    - The `delay` and `branch` blocks are there so that the three examples together use all five M2 blocks, which M2 runs ("The three example models run end to end"). Constant times keep the arithmetic exact; integer weights 4 and 1 give exactly one order in five.
    - Seed 12345, `replications` 30 and the warehouse's 200 h with 10 h warm-up are the coffee shop's (spec 1's example); the seed has no other meaning.
    - The line's 100 h with 20 h warm-up: spec 4 needs the line to fire `not_enough_runs` at M8 (the weld wait's half-width above 10% of its mean; the prototype had 26%). An estimate, not a check: Whitt (1989, "Planning queueing simulations", Management Science 35(11)) gives the asymptotic variance of the time-average number in an M/M/1 system as 2ρ(1 + ρ)/(1 − ρ)⁴ mean service times. For the weld station (ρ 0.90, 1.8 min, mean number 9) over 80 h observed and 30 replications that gives a 95% half-width of about 15% of the mean, against about 10% with the coffee shop's 190 h observed. The same formula gives 3.7% for the coffee shop's number in system, beside the 4.8% spec 4 reports for its wait, so the order of magnitude is plausible. 20 h of warm-up is about 1.75 relaxation times of the weld station (1/(μ(1 − √ρ)²) = 684 min). M8 measures both; neither is claimed here.
  - Consistency arithmetic, closed form only (guide rule 7), written in each file's `meta.description` and asserted exactly with fractions in `tests/model/test_examples.py`. Both are open lines with Poisson arrivals and exponential service, so by Burke's theorem every station sees Poisson arrivals (a constant delay and a probability split of a Poisson stream keep it Poisson).
    - Line: ρ cut = 0.5/min × 1.2 min = 0.60, weld = 0.5 × 1.8 = 0.90, paint = 0.5 × 1 = 0.50. M/M/1 mean wait ρ/(1 − ρ) × s: cut 1.8 min, weld 16.2 min, paint 1.0 min. Cycle time 3.0 + 18.0 + 2 + 2.0 = 25.0 min; throughput 30 per hour. The weld wait of 16.2 min differs from the prototype's 17.3 min, as spec 2 foresaw (17.3 would need a service mean near 1.92 min); reproducing it is not required.
    - Warehouse: no block loses items and every server is stable, so throughput = arrival rate = 60 per hour exactly in the long run; the 1% band is the tolerance for M2's estimate (a sink count over 190 h at 60 per hour has a Poisson standard deviation of about 0.94% per replication, about 0.17% for the mean of 30). ρ pick = 1/min × 2 min / 3 = 2/3; Erlang C with c = 3 and offered load 2: (2³/3! × 3/(3 − 2)) / (1 + 2 + 2²/2! + 4) = 4/9, mean wait (4/9)/(3/2 − 1) = 8/9 min = 0.889 min. ρ pack = 1/min × 0.8 min = 0.80, mean wait 4 × 0.8 = 3.2 min. Inspection flow 12 per hour. Cycle time 2.889 + 0.2 × 5 + 4.0 = 71/9 = 7.889 min.
  - Spec 4 "Finding rules" needs the line to fire `bottleneck` and `not_enough_runs` at M8: the weld utilization 0.90 sits within 0.85 to 0.92, so the 0.85 `bottleneck` threshold fires on the expected value. Verified at M8, not here.
  - The test `tests/model/test_examples.py` holds the spec 1 acceptance row ("The three example models in `examples/` load with zero issues", through the whole validator, warnings included) and checks each file's structure, settings, experiment and arithmetic. `flow_rates` and `distribution_mean` (AKS-91) supply the rates and means, so the W201 computation and the arithmetic in the files agree.
- **Reason:** guide rule 5 and the known-gaps row "Two example files and the prototype were not retained"; spec 2 "Reference values from the prototype"; spec 1 acceptance (M1 row 1); spec 4 "Finding rules"; the AKS-93 acceptance list.
- **Alternatives considered:**
  - Waiting for the owner's answer to AKS-74: blocks M1; rule 5 says to proceed under the simplest reading.
  - Reconstructing the prototype's numbers (weld wait 17.3 min, pack 0.83): would mean guessing parameters nobody kept, and 0.83 has no short exact service mean at 60 per hour; spec 2 says reproducing them is not required.
  - Lower-variance service (normal or triangular) to bring the weld wait nearer 17.3 min: loses the closed-form wait (M/G/1 needs the second moment and, in a line, the arrival process is no longer Poisson) for no requirement.
  - Spec 4's template block lists for these names (queue, batch, schedule): those are templates for M10, and spec 2 says these files use M2 blocks only.
  - Branching the warehouse to two sinks: splits the throughput metric; one sink keeps "throughput 60 per hour" one number.
- **Awaiting owner:** confirm the two example files, or supply the originals (AKS-74, option (a) or (b)).
- **Tested:** `tests/model/test_examples.py` (25 tests). The arithmetic was also recomputed independently in floating point outside the test suite and agrees.
- **Spec sections updated:** spec 2 "Reference values from the prototype", with a dated line under "Changes in this version". Version number unchanged until M1 closes (guide rule 6).
- **Dependencies added:** none.

### M1 closed (AKS-94)

- **Decision:**
  - M1 is closed. Every gate in the guide's M1 "Done when" row and every spec 1 acceptance row tagged M1 passes on the top of the M1 stack (PR #13 plus this change). Evidence is in `docs/sessions/2026-11-06-M1.md`:
    - the three `examples/*.json` load with zero issues;
    - each of the 29 schema and meaning codes has a fixture, and `tests/model/test_issues.py` passes with 0 skips;
    - the migration test passes;
    - `bash scripts/check.sh` exits 0 on Python 3.13.18 and 3.11.18: 1,140 passed, 0 skipped, line coverage of `src/lcsim` 100%;
    - `tests/test_docs.py` passes.
  - The known-gaps row assigned to M1, "Two example files and the prototype were not retained", is closed under the proposed default (AKS-93). The owner still has to confirm it (AKS-74). No other known-gaps row names M1.
  - Spec versions (guide rule 6). M1 closes with changes to spec 1 and spec 2, so both go from 0.3 to 0.4.
    - In each, the lines dated 2026-11-06 under "Changes in this version" now sit under a new heading, "2026-11-06, version 0.4, M1 closed (AKS-94)". The version 0.3 block above them is kept as it was.
    - The trailing "Version number unchanged until M1 closes." is removed from each line, because it is no longer true.
    - The 2026-11-06 lines from the review of PR #1 and the sync to Claude Docs were also made after 0.3, so they go under 0.4 too.
    - The overview's version sentence is updated to match.
  - Specs 0, 3 to 7 and the build guide are unchanged by M1 and keep their versions.
    - Spec 3 has one 2026-11-06 line, from the review of PR #1, and no M1 line. It is left at 0.3: this ticket bumps only the specs that M1 changed. Its bump is left to the owner or to the close of that review.
  - `CLAUDE.md` "Current state": M1 is Done, and a row says M2 is ready to start. Only the table below the verbatim guide changes, so `tests/test_docs.py` still finds the guide unchanged.
- **Reason:** guide rules 6, 8, 9 and 10; the guide's "Session procedure", "Definition of done for any change" and M1 row; the AKS-94 acceptance list.
- **Alternatives considered:**
  - Replacing the 0.3 change list with only the 0.4 changes, since the heading says "this version": this would drop the council's record from the file. Git keeps it, but readers of the spec would lose it.
  - Bumping spec 3 as well: its only new line comes from the review of PR #1, not from M1.
  - Leaving "Version number unchanged until M1 closes." in each line: it would contradict the new version line.
- **Spec sections updated:** spec 1 and spec 2 version lines and "Changes in this version" (bumped to 0.4); the overview's "What is here" version sentence. No spec content changed.
- **Dependencies added:** none.
  - Every dependency added during M1 is recorded above with name, version, licence and how it was checked: `jsonschema` and `pint` with their dependencies (AKS-85, AKS-86, AKS-87), and `types-jsonschema` (AKS-87). The versions installed on 2026-11-06 still match those entries: jsonschema 4.26.0; pint 0.26.2 on Python 3.13 and 0.25.3 on Python 3.11; types-jsonschema 4.26.0.20261006.

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

## 2026-11-06 · M9 design before building (AKS-118, ahead of order)

### Design checklist done in parallel with M1

- **Decision:** The session items of spec 3 "Design before building" and the three M9 research notes were done now, alongside M1, instead of after M8.
- **Reason:** The owner asked for it. The work is documents only: nothing was written under `ui/`, so the rule that interface code waits for the checklist still holds. This departs from the guide's build order ("Build in this order") and rule 2, which would have M1 to M8 pass first; the owner's request authorizes the departure. This session did no M1 work and closes no milestone.
- **Alternatives considered:** Waiting for M8 (the normal order). Rejected by the owner's request.
- **Spec sections updated:** Spec 3 "Design before building" (five session boxes ticked; the owner walkthrough box stays open), warning line, "Changes in this version".
- **Dependencies added:** None.

### Interface framework confirmed: React, React Flow, Tauri 2

- **Decision:** Keep spec 3's interface stack: React with React Flow (`@xyflow/react`), packaged with Tauri 2 at version 2.11.1 or later. Electron is the fallback if WebKitGTK proves unworkable on the low tier.
- **Reason:** Both Tauri and Electron support Linux and Windows under permissive licences. Tauri uses the system webview, so the product does not ship and update a browser engine on Electron's eight-week major cadence (three majors supported at a time). React Flow provides the node editor with keyboard support. Qt would need its own node editor. Tauri 2.0 to 2.11.0 have advisory GHSA-7gmj-67g7-phm9 (CVE-2026-42184), so 2.11.1 is the minimum. Details: `docs/research/spec-3-framework-check.md`.
- **Alternatives considered:** Electron 45.2.3 (MIT); Qt 6 through PySide6 6.12.0 (LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only, with some modules GPL-3.0 only) or PyQt6 6.12.0 (GPL-3.0-only).
- **Spec sections updated:** Spec 3 "Architecture" (Interface row), warning line, acceptance table (`tauri-driver` row), "Changes in this version".
- **Dependencies added:** None now; no interface code exists. Recorded for M9, to be pinned and re-checked from each package's LICENSE file when added:

| Package | Version seen | Licence | How checked |
| --- | --- | --- | --- |
| `tauri` (crate) | 2.12.5 | Apache-2.0 OR MIT | crates.io API, 2026-11-06 |
| `wry` (crate) | 0.57.1 | Apache-2.0 OR MIT | crates.io API, 2026-11-06 |
| `tao` (crate) | 0.37.2 | Apache-2.0 | crates.io API, 2026-11-06 |
| `@tauri-apps/cli`, `@tauri-apps/api` | 2.12.4 | Apache-2.0 OR MIT | npm registry, 2026-11-06 |
| `@xyflow/react` | 12.12.1 | MIT | npm registry and repository `LICENSE` (webkid GmbH), 2026-11-06 |
| `react` | 19.3.1 | MIT | npm registry, 2026-11-06 |

AGPL-3.0 compatibility: MIT is permissive; for Apache-2.0 the Apache Software Foundation records that the FSF considers it compatible with GPLv3 (read 2026-11-06), and AGPL-3.0 is in the same version 3 family. WebKitGTK (Linux, LGPL and BSD per webkit.org) and WebView2 (Windows, proprietary) are system components the product loads but does not ship. Not legal advice; the lawyer review before release (spec 0) should confirm the system-library reading for WebView2.

### Design choices where the specs were silent (owner to confirm)

- **Decision:** The design takes these simplest readings. Each is marked "(design choice)" in `docs/design/`.
  1. Undo and redo store whole models and write them back with `PUT .../model` and `base_revision`; 200 steps are kept (spec 3 asks for at least 100).
  2. A `model` event from another client reloads the canvas and clears the undo and redo history.
  3. Blocks without ports (`resource_pool`, `schedule`, `failure`) show their `pool` and `target` settings as dashed reference lines, set only in the side panel.
  4. An `optimization` model's Canvas screen is a form of variables, objective and constraints.
  5. Generated ids are `<type>_<n>` with the smallest free `n` from 1; `ui` holds `{x, y}` in canvas pixels.
  6. No grouping, sub-models, copy and paste or canvas comments in Phase 1.
  7. Zoom range 20% to 200%; a drag or a burst of arrow-key moves is one undo step.
  8. While a write is failing, the canvas is read-only and retries every 2 seconds; nothing is queued.
  9. Run is also disabled while a write or a validation is pending.
  10. Settings lets the user choose the hardware tier, defaulting to the detected one; theme (System, Light, Dark) and text size (100% to 200%) are settings.
  11. System fonts only, so nothing is downloaded (spec 0 principle 6).
  12. Block categories for the palette and stripes: flow (`source`, `sink`, `delay`, `branch`), work (`server`, `queue`, `batch`, `unbatch`, `store`), resource (`resource_pool`, `schedule`, `failure`).
- **Reason:** Spec 3 defines behaviour but not these details. Each choice is the simplest that meets the spec and the accessibility target (WCAG 2.2 AA).
- **Alternatives considered:** Inverse edits for undo (rejected: some edits have no inverse); keeping undo history across external edits (rejected: an undo could silently revert another client's change); connecting resource blocks by dragging (rejected: they have no ports in spec 2).
- **Spec sections updated:** Spec 3 "Screens" item 2 (choice 4), "Canvas behaviour" (choices 1 to 3).
- **Dependencies added:** None.

### Spec gaps found by the design, closed in spec 3

- **Decision:** (a) `set_path` and `remove_path` also reach `variables` and `objective` in an `optimization` model. (b) A new edit, `set_label` (`id`, `label`; `null` removes it), sets a component's optional `label`.
- **Reason:** (a) Spec 3 limited `set_path` to `meta`, `run`, `objectives`, `constraints` and `search`, so no edit could change an existing optimization model's variables or objective, and neither the Canvas form nor the MCP `edit_model` tool could edit one. Not changed, and left for M6: no edit sets `domain`, and `POST /v1/projects` without a template creates a `process` model, so an optimization model can only start from a template or a whole-model `PUT`. (b) Spec 1 gives components an optional `label`, but no edit could set it: `add_component` takes `id`, `type`, `params` and `ui`, and `set_setting` works only inside `params`.
- **Alternatives considered:** For (b), allowing `set_path` on `/components/<n>/label` (rejected: addressing a component by its position breaks when components are added or removed); leaving `label` read-only in the interface (rejected: users could not name blocks in their own words).
- **Spec sections updated:** Spec 3 "Model edits", "Changes in this version". Spec 4's `edit_model` takes "edits as in spec 3", so it gains both without a change.
- **Dependencies added:** None.

### Awaiting owner: wireframe walkthrough

The owner's walkthrough with a student and a business user, or its fallback (spec 3 "Design before building"; owner question 7 above), is **not** recorded. M9 interface code may not start until it is, or its fallback is logged here. Tracked in AKS-82.

## 2026-11-06 · M2

### Random streams and distribution samplers (AKS-96)

- **Decision:**
  - `src/lcsim/model/streams.py` builds every generator from the spec 1 key `<seed>:<replication>:<component id>`: the SHA-256 of its UTF-8 bytes, read as a big-endian integer, seeds `numpy.random.SeedSequence`, which seeds `numpy.random.Generator(PCG64(...))`. `generator_for` gives one stream, `streams_for` one per component of a replication (a repeated id is refused, since two components would share a stream), and `optimizer_generator` the reserved key `<seed>:0:optimizer` of spec 2. `generator_info()` gives the manifest's `generator {name, numpy_version}`: `PCG64` and `numpy.__version__`. A seed outside 0 to 2⁶³ − 1, a negative replication, a boolean and an empty component id raise `ValueError`; loading never gives them, so they are programming errors, not user-facing issues.
  - `src/lcsim/model/distributions.py` holds one sampler per `dist` of spec 1. `sampler_for(model, distribution, values)` resolves parameter references once, the way `validation.distribution_mean` does (`values`, a scenario's `set`, replaces a parameter's `value`), and returns a function from a generator to one float in SI units. The samplers live in the model layer, next to the `Distribution` they read and the means validation computes, so the M2 adapter and the M5 search both import them without depending on each other.
  - Each sampler is one numpy `Generator` call per sample: `exponential(mean)` (the mean is the scale), `uniform`, `triangular`, `normal`, `lognormal(μ, σ)` with σ² = ln(1 + sd²/mean²) and μ = ln(mean) − σ²/2, `scale · weibull(shape)`, and `integers(n)` to pick an `empirical` value with equal probability and replacement. A `triangular` with `min` equal to `max` (allowed by spec 1) returns that value, because numpy refuses `left == right`. No numerical method is written (guide rule 7).
  - An `empirical` with `data` raises `DataNotYetSupportedError`, which carries code E162, a message naming the file, the column and milestone M6, and a hint; `Issue.from_problem` turns it into a spec 1 issue object. E162 is the code validation already gives every `data` reference until M6, so no new code is needed, and a validated model never reaches it.
- **Reason:** spec 1 "Random streams", "Distributions" and "Run folder and results"; spec 2 "Simulation-based optimization"; guide "Conventions" (Randomness, Errors); the AKS-96 acceptance list. Closes the known-gaps row "`weibull` and `empirical` with `values` have never run" (M2): both pass the sampling test. The guide's table is the verbatim build guide and is not edited; its row is closed by this entry.
- **Alternatives considered:**
  - Samplers in `src/lcsim/engines/process/`: only the process adapter could use them, while spec 2's simulation-based search and the model layer's means need the same definitions.
  - Drawing arrays of samples (`size=n`) for speed: a second code path whose sequence need not match one draw at a time. The sampling test calls the same one-at-a-time sampler the adapter will call.
  - A new issue code for `data` before M6: E162 already says the data reference cannot be read, and spec 1 has no free code for it.
- **Spec sections updated:** spec 1 "Distributions" (negative times, `data` before M6) and "Changes in this version" › "Since version 0.4"; see the next entry.
- **Dependencies added:** `numpy>=2.4.6` in `[project] dependencies`. Its licence is recorded in "Libraries for M2, confirmed from their licence files" above (BSD-3-Clause, with the bundled libraries listed there; compatible). The lower bound is 2.4.6, not the 2.5.4 installed on Python 3.13, because 2.4.6 is the newest numpy for Python 3.11 (same entry) and CI runs on 3.11; this follows `pint>=0.25.3` (AKS-85).
- **Tested:**
  - `tests/model/test_streams.py` (25 tests): the key, the construction against a hand-built SeedSequence and PCG64, UTF-8 encoding, the first three raw outputs for `12345:0:till` pinned, a separately started interpreter under `PYTHONHASHSEED` 0, 1 and `random` drawing the same 50 numbers, the coffee shop with a `delay` added leaving the other three streams unchanged, the optimizer key, `generator_info()`, and the refused seeds and replications.
  - `tests/model/test_distributions.py` (48 tests): the spec 1 sampling test for all eight distributions (20,000 samples from one stream, mean within four standard errors; `constant` exact; `normal` at mean 5 sd with no negative sample; `weibull` with `math.gamma`; `empirical` with the population sd), each theoretical mean equal to `distribution_mean`, each sampler matched against the numpy call it makes, `min` equal to `max`, equal probability of `empirical` values, parameter and scenario resolution, the clipping cases of the next entry, and `data` raising E162 that becomes an issue object.
  - `bash scripts/check.sh` exits 0 on Python 3.13.18 with numpy 2.5.4: 1,236 passed, line coverage of `src/lcsim` 100%. The two new test files also pass on Python 3.11 with numpy 2.4.6, with the same pinned raw outputs.
- **Review of PR #15 (Codex):** one finding, confirmed and fixed. The `lognormal` conversion squared `sd` and `mean`, so `mean` = `sd` = `1e-200 s` raised `ZeroDivisionError` and `1e200 s` gave NaN parameters, although both pass E160. σ² is now computed from ln(sd/mean), as log1p(r²) for r ≤ 1 and 2·ln r + log1p(1/r²) above, a closed form, not a numerical method. Four tests cover the two cases and a ratio that overflows or underflows.

### Negative sampled times are set to 0 s (AKS-96), proposed default, owner to confirm

- **Decision:** Every sampled time below 0 s is set to 0 s, for every distribution, as spec 1 already said for the `normal`. A `constant` of `-1 min` always gives 0 s; a `uniform` from `-1 min` to `1 min` gives 0 s about half the time; an `empirical` value below 0 s gives 0 s when drawn. Nothing reports such a distribution at load. W201 keeps using the theoretical mean of the written distribution (with the clipped mean only for the `normal`), so it underestimates the load of a server whose service time can fall below 0 s; this is stated in spec 1.
- **Reason:** Guide rule 5, simplest reading. This answers M1 Awaiting-owner item 9 ("Negative times are not reported", `docs/sessions/2026-11-06-M1.md`) and the matching "Left open" item of the AKS-90 entry above. Every Phase 1 distribution setting is a time, a time cannot be negative, and the `normal` already clips, so one rule covers all eight. It changes no issue code, so the 29 fixture codes and the M1 gates stay as they are.
- **Alternatives considered:** Rejecting a distribution that can give a negative time with a new issue code (an error, or a warning like W202): clearer to the modeller, but it needs a new code with its fixture, a change to the count of 29 codes that `tests/test_docs.py` checks, and a rule for parameter-fed fields at every case. The owner may still choose it; the sampler's clip would then never be reached for those models. Using the clipped mean in W201 for every distribution: more exact, but it changes M1 validation code for a case the owner may rule out.
- **Spec sections updated:** spec 1 "Distributions" (a paragraph after the fields that must agree) and "Changes in this version" › "Since version 0.4".
- **Dependencies added:** none.
- **Tested:** `tests/model/test_distributions.py`: a `constant` of −60 s, a `uniform` from −60 s to 60 s (share of zeros and clipped mean within four standard errors), an `empirical` holding −30 s and −1 s, a `triangular` from −60 s and a `normal` with mean 0 s never give a value below 0 s, and a clipped zero is +0.0.

### Engine adapter interface, discovery and the process adapter's capabilities (AKS-97)

- **Decision:**
  - `src/lcsim/engines/adapter.py` holds the spec 1 "Engine adapter interface" types as signed: `CancelToken` and `EngineAdapter` as `runtime_checkable` protocols, and frozen dataclasses `Capabilities`, `Progress(fraction, message, metrics=None)` and `Results(tables: dict[str, Table], warnings: list[Issue], solution: dict[str, Any] | None = None)`, with `Table = pyarrow.Table`. `Capabilities` has `domains`, `component_types` (type name to the model layer's `BlockType`, which holds settings and ports), `hardware`, `parallel_modes` (from `replications`, `threads`, `processes`, `gpu`), `licence` (SPDX) and `invocation` (`process` or `in-process`). An unknown parallel mode or invocation, an empty licence, and a `Progress` fraction outside 0 to 1 or NaN raise `ValueError`: they are adapter programming errors, not user-facing issues.
  - `hardware` is a tuple of words naming what the engine needs beyond a CPU and memory, such as `gpu`, empty for none. Spec 1 named "hardware needs" without a shape; this is the simplest reading. Proposed default, owner to confirm.
  - `src/lcsim/engines/registry.py`: `load_adapters()` lists `importlib.metadata.entry_points(group="lcsim.engines")` without importing, leaves out every entry point whose name is shared (without importing any of them, logged once per name), and loads the rest in name order inside a guard that covers importing, creating the class with no arguments and calling `capabilities()`. Any `Exception` there, an object that does not provide the `EngineAdapter` members with text `name` and `version`, a `capabilities()` that is not `Capabilities`, and a class `name` that differs from the entry-point name leave the entry point out with a warning on logger `lcsim.engines.registry`. `installed_adapters()` runs discovery once per process (`functools.cache`). `installed_engines()` turns adapters into the model layer's `InstalledEngine` records and adds the stand-in only for a Phase 1 domain no adapter handles. `select_adapter(domain, engine)` returns a `Selection(adapter, issues)` by the spec 1 "Top-level keys" rule through `engine_issues`, so E102 has the same messages and paths (`/domain` or `/run/engine`) as before.
  - A name mismatch leaves the entry point out. Spec 1 required the names to be equal but did not say what happens when they are not; `run.engine` could not name such an adapter reliably, so it is treated like the other faults. Proposed default, owner to confirm.
  - The process adapter (`src/lcsim/engines/process/adapter.py`, `ProcessAdapter`) is registered as entry point `simpy`, the engine library's name, as xarray names its engines and as the M1 tests already did. Its `version` is the product version, since it ships with the product; the manifest can add SimPy's own version when AKS-98 adds simpy. Proposed default, owner to confirm. `capabilities()` reports `process`, the model layer's `PROCESS_TYPES`, no hardware, `replications` (AKS-98 runs replications in parallel up to `workers`), `MIT` and `in-process`. `validate` returns no issues (no engine-specific check yet). `translate`, `run` and `collect` raise `NotImplementedError` naming AKS-98, which builds them; a test proves it, so no line is excluded from coverage.
  - The adapter reports the model layer's catalogue object rather than a second copy. Spec 1 "Validation" requires the two to be equal; one copy cannot drift, and the model layer must read component types before any engine is imported. The equality test (`tests/engines/process/test_capabilities.py`) also checks the twelve spec 2 type names, written out independently, and the source, sink and branch ports.
  - The model layer does not import `lcsim.engines` at module level, because `lcsim.engines` imports the model layer (`Model`, `Issue`, `BlockType`, `engine_issues`). The installed engines are injected: `load_model`, `load_text`, `load_document` and `build_document` take `engines: Sequence[InstalledEngine] | None = None`, and `engine_issues` now requires them. When `engines` is `None`, one private function in `loading.py` imports `lcsim.engines.registry` when first called and asks it for `installed_engines()`. `import lcsim.model.loading` leaves `lcsim.engines` unimported (checked with `sys.modules`); a load then imports it. So `run.engine` is checked for `process` from now on, everywhere a model loads, and a caller such as a test or the service can pass its own engines.
  - `STAND_IN_ENGINES` now holds the `optimization` stand-in only, until M5.
  - pyarrow 26.0.1 ships no `py.typed` and no stubs, so a mypy override (`ignore_missing_imports` for `pyarrow`) types its objects as `Any`. `pyarrow-stubs` exists (BSD-2-Clause) but follows pyarrow 20.0.0, six major versions behind, so it is not added.
- **Reason:** spec 1 "Engine contract", "Engine adapter interface", "Division of labour", "Top-level keys" and "Engine licence rule"; `docs/research/spec-1-plugin-mechanisms.md`; the AKS-97 acceptance list. This closes the M1 "Left" item that the process stand-in is replaced by the real adapter.
- **Alternatives considered:**
  - Importing `lcsim.engines.registry` at the top of `loading.py`: no import cycle today, since the registry does not import `loading`, but it makes `lcsim.model` and `lcsim.engines` depend on each other at import time, and any later import of `loading` from the engines package would break.
  - Injection only, with the stand-ins as the default: every existing caller would keep the `process` stand-in, so `run.engine` would not be checked for `process`, against the ticket and spec 1 "Top-level keys".
  - Discovering on every load: about 1.5 ms per call here, and a failing plugin would log on every load. Discovery once per process matches how a long-running service sees installed packages.
  - Keeping a name mismatch and registering it under its entry-point name (pluggy and xarray key plugins by entry-point name): `run.engine` and the class `name` (written to `manifest.json`) would then disagree.
  - Using the model layer's stand-in for `optimization` always, even with an installed optimization adapter: a third-party adapter before M5 would then give E102 for every optimization model without `run.engine`.
- **Spec sections updated:** spec 1 "Engine contract" (what the guard covers, name mismatch, duplicates not imported, discovery once per process, the `simpy` adapter and its version), "Engine adapter interface" (the `Capabilities` fields and the process adapter's values), "Top-level keys" (`run.engine` checked for `process` from M2; the `optimization` stand-in only while no adapter handles it) and "Changes in this version" › "Since version 0.4".
- **Dependencies added:** `pyarrow>=26.0.1` in `[project] dependencies`. Its licence is recorded in "Libraries for M2, confirmed from their licence files" above (Apache-2.0, with bundled Apache-2.0, BSD, MIT and ZPL-2.1 code; compatible). The lower bound is 26.0.1, the newest pyarrow, because it supports Python 3.11 (`Requires-Python >=3.11`; pip downloaded the `cp311` manylinux wheel on 2026-11-06), and CI runs on 3.11 and 3.13; this follows `numpy>=2.4.6` (AKS-96). No dev dependency is added.
- **Tested:**
  - `tests/engines/test_adapter.py` (25 tests): `multiprocessing.Event` and `threading.Event` are `CancelToken`s; the process adapter is an `EngineAdapter` and a class without `collect` is not; the parallel-mode and invocation words; every `Capabilities` field, its read-only copy of the component types, value equality and freezing; the refused modes, invocations and empty licence; `Progress` with and without metrics, its bounds, and NaN and infinity refused; `Table is pyarrow.Table`; `Results` with a `replications` table and a warning, and with a `solution`.
  - `tests/engines/test_registry.py` (31 tests), with `entry_points` replaced by stand-in entry points: a dummy adapter is found; a real `EntryPoint` value is imported; name order; a missing module (a real `ModuleNotFoundError`), `ImportError`, `SyntaxError` and `RuntimeError` on import, a constructor that raises, a `capabilities()` that raises or returns the wrong type, objects that are not adapters, a non-text version and a name mismatch are each left out with one warning while the other adapters load; two and three entry points with one name are left out, logged once and never loaded; discovery runs once per process and its result is read-only; the stand-in is added only for an unhandled domain; selection of the one adapter, by `run.engine`, of none for the `optimization` stand-in, and E102 at `/run/engine` or `/domain`, including when duplicates leave none; and the real installed metadata names `simpy = lcsim.engines.process.adapter:ProcessAdapter`.
  - `tests/engines/process/test_capabilities.py` (6 tests): the component types equal `PROCESS_TYPES` in content and order; the twelve spec 2 names, written out; the ports; `process`; MIT and `in-process`; `replications` and no hardware.
  - `tests/engines/process/test_process_adapter.py` (3 tests): name `simpy` and the product version; `validate` gives no issue on the coffee shop; `translate`, `run` and `collect` raise `NotImplementedError` naming AKS-98 and write nothing.
  - `tests/model/test_validation.py`: the stand-in is `optimization` only; `run.engine` `simpy` loads the coffee shop and `salabim` gives E102 at `/run/engine` with the hint "Name one of: 'simpy'."; an `optimization` model still accepts any `run.engine`; the four load functions use the engines they are given. The E102 fixture of `tests/model/test_issues.py` still passes.
  - `bash scripts/check.sh` exits 0 on Python 3.13.18 (1,304 passed, line coverage of `src/lcsim` 100%) and on Python 3.11.18 with numpy 2.4.6 and pyarrow 26.0.1 (1,304 passed, 100%).
