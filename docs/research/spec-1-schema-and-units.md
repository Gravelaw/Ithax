# Schema and units

Research item: spec 1, "Research before building", M1 · Schema and units. Ticket AKS-85.
Date: 2026-11-06.

## Question

Which JSON Schema version and which Python validator should the M1 schema pass use? Which
library should handle units, and what are its limits? Spec 1 "Units" proposes pint.

## Finding

**JSON Schema version.** The current published version is 2020-12; the previous one was
2019-09 (json-schema.org, "Specification"). The project is working on a next release that
puts upgrade compatibility first. Known changes in it: `format` will validate by default,
`$dynamicRef` will be separated from `$ref`, vocabularies become a proposal, and unknown
keywords in schemas will be disallowed except with an `x-` prefix (blog post "Moving Toward
a Stable Spec", 13 January 2025). No release after 2020-12 had been published by
2026-11-06.

**Validators** (PyPI metadata read on 2026-11-06):

| Package | Version | Licence | 2020-12 | Notes |
| --- | --- | --- | --- | --- |
| jsonschema | 4.26.0 | MIT | yes | Pure Python plus `rpds-py` (compiled, MIT). Supports 2020-12, 2019-09, 7, 6, 4 and 3. `format` is not checked unless asked for, as the 2020-12 specification says |
| jsonschema-rs | 0.60.3 | MIT | yes | Rust extension. Supports 4, 6, 7, 2019-09 and 2020-12; errors carry `instance_path` |
| fastjsonschema | 2.22.3 | BSD-3-Clause | no | Drafts 04, 06 and 07 only |

jsonschema's dependencies: attrs 26.1.0 (MIT), jsonschema-specifications 2025.9.1 (MIT),
referencing 0.37.0 (MIT), rpds-py 2026.9.1 (MIT). Its optional `format` extra pulls in
`rfc3987` 1.3.8, which is GPL-3.0-or-later; the `format-nongpl` extra avoids it. Neither
extra is needed, because the spec 1 schema checks no formats. rpds-py is the only compiled
package in the set; its 2026.9.1 release ships Windows wheels (win32, win_amd64,
win_arm64) for CPython 3.11 to 3.15, so the spec 3 statement that every Phase 1 dependency
ships Windows wheels or is pure Python still holds (PyPI file list read 2026-11-06).

**Units libraries** (PyPI metadata read on 2026-11-06):

| Package | Version | Licence | Python | Notes |
| --- | --- | --- | --- | --- |
| pint | 0.26.2 | BSD-3-Clause | 3.12 or later | Pure Python. Dependencies flexcache 0.3 and flexparser 0.4 (BSD 3-clause text), platformdirs 4.14.5 (MIT), typing-extensions 4.16.0 (PSF-2.0) |
| pint | 0.25.3 | BSD-3-Clause | 3.11 or later | Last series for Python 3.11; pint 0.26.0 (2026-09-10) "Drop support for Python 3.11" |
| unyt | 3.2.0 | BSD-3-Clause | 3.11 or later | Needs numpy and sympy |
| astropy | 8.0.2 | BSD-3-Clause | 3.11 or later | Units are one part of a large astronomy package |

The project supports Python 3.11 or later (guide "Conventions"), and CI runs 3.11 and 3.13.
On 3.11 the resolver picks pint 0.25.3; on 3.13 it picks 0.26.2. This was confirmed by
installing both (see Tested).

**pint's limits, found by testing.** pint parses far more than the spec 1 grammar
("a number, one space, a unit") allows. All of these load without error in both versions:

| Text | pint reads it as | Spec 1 grammar |
| --- | --- | --- |
| `2min` | 2 minute | no space: not allowed |
| `2  min` | 2 minute | two spaces: not allowed |
| `2 minutes`, `2 mins` | 2 minute | not a Phase 1 unit symbol |
| `2 * min` | 2 minute | an expression, not a quantity |
| `2 min / min` | 2.0 dimensionless | an expression |
| `nan s`, `inf s` | NaN and infinite seconds | not finite numbers |
| `2 Min` | 2 megainch (a length) | case matters: a trap |
| `2 m` | 2 metre | a length, not a time |
| `2 ms` | 2 millisecond | a time, but not a Phase 1 unit |

pint reads the four Phase 1 symbols correctly: `s` second, `min` minute (not milli-inch),
`h` hour, `d` day. A wrong dimension raises `DimensionalityError` on conversion, which is
what E140 needs. pint returns an `int` magnitude for an integer input (`2 min` converts to
`120`), so the loader must convert to `float` (spec 1: internal time is seconds, as a
float).

Other costs: importing pint took 0.17 to 0.23 s and building a `UnitRegistry` 0.14 s. One
registry per process is enough.

**AGPL-3.0 compatibility.** The FSF licence list calls the Expat (MIT) licence and the
modified (3-clause) BSD licence "compatible with the GNU GPL", and the licence of Python
2.0.1 and later (the PSF licence) "compatible with the GNU GPL". The AGPL-3.0 entry says
that separate modules under GPLv3 and AGPLv3 may be combined in one project. A permissive
licence that is compatible with the GPL may be combined into an AGPL-3.0 work. This is not
legal advice (spec 1, engine licence rule).

## Sources

- JSON Schema "Specification" page (current version 2020-12):
  https://json-schema.org/specification (opened 2026-11-06)
- JSON Schema blog, "Moving Toward a Stable Spec", 13 January 2025:
  https://json-schema.org/blog/posts/stable-json-schema (opened 2026-11-06)
- JSON Schema blog index (no newer release announced): https://json-schema.org/blog
  (opened 2026-11-06)
- jsonschema documentation (drafts supported, `format` behaviour, extras):
  https://python-jsonschema.readthedocs.io/en/stable/ (opened 2026-11-06)
- jsonschema licence file: https://raw.githubusercontent.com/python-jsonschema/jsonschema/main/COPYING
  (opened 2026-11-06)
- jsonschema-rs Python bindings README:
  https://github.com/Stranger6667/jsonschema/tree/master/crates/jsonschema-py (opened
  2026-11-06)
- fastjsonschema documentation: https://horejsek.github.io/python-fastjsonschema/ (opened
  2026-11-06)
- pint tutorial (string parsing, `DimensionalityError`):
  https://pint.readthedocs.io/en/stable/getting/tutorial.html (opened 2026-11-06)
- pint changelog (0.25.0 minimum Python 3.11; 0.26.0 drops 3.11):
  https://raw.githubusercontent.com/hgrecco/pint/master/CHANGES (opened 2026-11-06)
- pint licence file: https://raw.githubusercontent.com/hgrecco/pint/master/LICENSE (opened
  2026-11-06)
- PyPI JSON metadata, read on 2026-11-06 with `curl https://pypi.org/pypi/<name>/json`, for
  jsonschema, jsonschema-rs, fastjsonschema, referencing, jsonschema-specifications, attrs,
  rpds-py, rfc3987, rfc3987-syntax, pint (all releases from 0.20), flexcache, flexparser,
  platformdirs, typing-extensions, unyt, astropy
- FSF, "Various Licenses and Comments about Them" (Expat, modified BSD, Python 2.0.1 and
  later, AGPLv3 entries): https://www.gnu.org/licenses/license-list.html (downloaded
  2026-11-06)

## Decision

1. **JSON Schema 2020-12.** The schema declares
   `"$schema": "https://json-schema.org/draft/2020-12/schema"`. It uses no `format`
   keyword, so its meaning does not change when the next release makes `format` validate
   by default.
2. **Validator: jsonschema 4.26.0 (MIT)**, with no extras. The schema pass uses
   `Draft202012Validator` and `iter_errors`, so every schema problem is reported, not just
   the first. The issue `path` is built from `error.absolute_path` as a JSON Pointer. The
   issue `message` is written by lcsim, not copied from `error.message`, because spec 1
   requires messages that name the key and contain no exception text: for
   `additionalProperties` the unexpected keys are `set(error.instance)` minus the schema's
   `properties`; for `required` the missing keys are `error.validator_value` minus the
   instance's keys (both checked; see Tested). jsonschema-rs was not chosen: models are
   small, so its speed does not matter, and it would add a compiled dependency. fastjsonschema
   cannot read 2020-12.
3. **Units: pint confirmed**, declared as `pint>=0.25.3` when M1 adds it, so that Python
   3.11 gets 0.25.3 and 3.12 or later gets the current release. pint stays inside the model
   layer (guide "Conventions", Units). Because pint accepts much more than spec 1 allows,
   the loader first matches the whole string against the spec 1 grammar and only then asks
   pint to convert:
   - the number follows the JSON number grammar,
     `-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?`, so `nan`, `inf`, `+2` and `.5` are
     not numbers;
   - exactly one space (U+0020) separates number and unit, with nothing before or after;
   - the unit is a Phase 1 symbol written exactly (`s`, `min`, `h`, `d`; case matters).
   A unit symbol that pint knows, with a dimension other than the one the setting expects
   (`5 m` for a time), is E140. Any other string (`2min`, `2 minutes`, `2 ms`, `nan s`) is
   E141. The SI value is stored as a `float`.
4. **Not chosen.** unyt brings numpy and sympy into the model layer; astropy is a large
   astronomy package. A hand-written table of the four time units would be smaller, but it
   cannot tell a known unit of the wrong dimension (E140) from an unreadable string (E141),
   and the physics phases need a full unit system.
5. **Spec 1 updated** in the same change: "Units" names pint and the Python 3.11 note;
   "Validation" names draft 2020-12 and jsonschema; "Quantities" states the exact grammar
   and how E140 and E141 divide. A dated line is added under "Changes in this version". The
   libraries are recorded in `docs/DECISIONS.md` with licences. Neither is added to
   `pyproject.toml` in this change; the first M1 code change adds them.

## Tested

Scratch virtual environments were made with `uv venv` on Python 3.11.18 and 3.13.18, and
`uv pip install jsonschema pint` was run in each. Results:

- Python 3.11 resolved jsonschema 4.26.0 and pint 0.25.3; Python 3.13 resolved jsonschema
  4.26.0 and pint 0.26.2. The installed licence files were read: jsonschema `COPYING` (MIT,
  "Copyright (c) 2013 Julian Berman"); pint `LICENSE` (BSD 3-clause text, the same file in
  0.25.3 and 0.26.2); flexcache and flexparser `LICENSE` (the same BSD 3-clause text);
  attrs, referencing, jsonschema-specifications, rpds-py and platformdirs (MIT);
  typing-extensions (PSF-2.0).
- 23 strings were parsed with `UnitRegistry().Quantity(text)` and converted with
  `.to("s")`: those in the pint table above, the Phase 1 examples (`2 min`, `1.5 min`,
  `200 h`, `10 h`, `3 d`, `45 s`, `0 s`, `1e3 s`), and `-2 min`, `2 hr`, `2 day` and `2`.
  Results were the same on both versions and are as stated in Finding.
- 8,036 conversions (2,009 decimal strings times the four Phase 1 units) through pint gave
  exactly the same float as `float(number) × factor` (60, 3600, 86400) on both pint
  versions.
- A cut-down spec 1 schema with `additionalProperties: false` was checked with
  `Draft202012Validator.check_schema`. The `examples/coffee_shop.json` subset it covers
  gave no errors. A broken file gave one error each for an unknown top-level key, an
  unknown component key, a wrong type and a missing `meta.name`, each with the right
  `absolute_path`. The unexpected and missing key names were recovered from
  `error.instance`, `error.schema` and `error.validator_value` as described in Decision. A
  `ui` object with arbitrary content passed.
