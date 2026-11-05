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
are excluded from it: the specs stay byte-identical to their exports.

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
**Owner to supply them before M1**, or to approve writing them fresh from the spec 2
descriptions (the guide rule "if the real adapter and the prototype disagree, the specs
and theory values decide" would then apply to them too).

### Noted, not changed

Spec 0 (dated 5 November 2026) records the high-tier machine as "Recorded 6 November
2026". Left as written; owner to confirm the date.
