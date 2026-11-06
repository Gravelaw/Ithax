# Plugin mechanisms (spec 1, M2)

## Question

Spec 1 "Research before building", M2: how do mature Python projects discover and load
plugins? Spec 1 "Engine contract" proposes Python entry points in group `lcsim.engines`,
each naming a class that implements `EngineAdapter`; this note confirms or replaces that.
Spec 1 "Division of labour" also asks this note to confirm pyarrow, which carries the
`Results` tables, because the first adapter needs it at M2.

## Finding

The Python Packaging User Guide names three ways to discover plugins: a naming convention
(`pkgutil.iter_modules()` over modules named like `flask_*`), namespace packages
(`pkgutil.iter_modules()` under `myapp.plugins`), and package metadata (entry points).
Entry points are a packaging interoperability specification: a distribution declares
`group`, `name` and an object reference (`module:attr`), and `importlib.metadata`, which is
standard library and no longer provisional since Python 3.10, reads them at runtime. The
specification asks consumers that define a new group to start it with a PyPI name they own.

Mature projects that load backends this way:

- **xarray** loads I/O backends from group `xarray.backends`; the entry-point name is the
  `engine=` value users pass, and the object is a `BackendEntrypoint` subclass. This is the
  closest analogue to `run.engine` and `EngineAdapter`.
- **pytest** builds on **pluggy**, which loads plugins with
  `PluginManager.load_setuptools_entrypoints(group)`, and can block a plugin by name.
  pluggy adds hook calling across many plugins, which spec 1 does not need: the core picks
  one adapter per run.
- **stevedore** (OpenStack) wraps entry points with driver and extension managers; its
  author's essay lists the same reasons spec 1 gives (strategy pattern for drivers,
  separate packaging so users avoid unneeded dependencies).

Naming conventions and namespace packages need no metadata, but they import every
candidate module to discover it and cannot name a class. Entry points list plugins without
importing them, name the class directly, and work for the product's own adapters (declared
in its `pyproject.toml`) as well as for third-party ones. No extra dependency is needed.

Behaviours that spec 1 has to state, found by test (see Tested):

- Listing does not import. A plugin whose import fails (here, a missing engine library)
  shows up in the list and fails only at `EntryPoint.load()` with `ModuleNotFoundError`.
  The core must load each one inside a guard and carry on.
- Two distributions may declare the same entry-point name. Both are listed, and
  `EntryPoints["name"]` silently returns one of them. The core must detect the clash
  rather than pick one by installation order.
- Editable installs (`pip install -e`) register entry points, so the repository's own
  adapters are found in development and in CI, which already runs `pip install -e`.
- `lcsim` is taken on PyPI by an unrelated project ("LCSim - liquid crystal simulator",
  version 0.2.0). The package name is already a placeholder; the group follows it when the
  product is named.

pyarrow: version 26.0.1 is the newest release and installs on Python 3.11 and 3.13. Its
metadata says `License-Expression: Apache-2.0`, and the wheel's
`pyarrow-26.0.1.dist-info/licenses/LICENSE.txt` is the Apache License 2.0 followed by the
notices of bundled third-party code (Apache-2.0, 3-clause BSD, 2-clause BSD, MIT, Zope
Public License 2.1, and the LLVM-style Apache exception). The FSF lists Apache-2.0 as
compatible with GPLv3, and the AGPLv3 allows combining modules under GPLv3 and AGPLv3, so
importing pyarrow into the AGPL-3.0 product is allowed under spec 1's engine licence rule.
It ships `cp311` and `cp313` wheels for Windows (`win_amd64`), Linux (`manylinux`) and
macOS. The spec 1 `replications` table round-trips through Parquet exactly.

## Sources

- Python Packaging User Guide, "Creating and discovering plugins",
  https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/ (opened
  2026-11-06).
- Python Packaging User Guide, "Entry points specification",
  https://packaging.python.org/en/latest/specifications/entry-points/ (opened 2026-11-06):
  group naming advice and the data model.
- Python documentation, `importlib.metadata`,
  https://docs.python.org/3/library/importlib.metadata.html (opened 2026-11-06).
- xarray, "How to add a new backend",
  https://docs.xarray.dev/en/stable/internals/how-to-add-new-backend.html (opened
  2026-11-06).
- pluggy documentation, https://pluggy.readthedocs.io/en/latest/ (opened 2026-11-06).
- stevedore, "Dynamic Code Patterns: Extending Your Applications with Plugins",
  https://docs.openstack.org/stevedore/latest/user/essays/pycon2013.html (opened
  2026-11-06).
- PyPI JSON API, https://pypi.org/pypi/lcsim/json and https://pypi.org/pypi/pyarrow/json
  (read 2026-11-06).
- Free Software Foundation, "Various Licenses and Comments about Them",
  https://www.gnu.org/licenses/license-list.en.html (read 2026-11-06): Apache-2.0
  "compatible with version 3 of the GNU GPL"; AGPLv3 allows combining "separate modules or
  source files released under both of those licenses in a single project".

## Decision

Spec 1's discovery mechanism is confirmed: entry points in group `lcsim.engines`, read with
the standard library's `importlib.metadata`, with the entry-point name as the adapter name,
failing imports and duplicate names left out and logged, and the group renamed with the
placeholder package; pyarrow 26.0.1 (Apache-2.0) is confirmed for `Results` tables.

## Tested

Scratch virtual environments outside the repository, 2026-11-06, Python 3.11.18 (the
project's minimum) and 3.13.18.

- **Discovery.** Three throwaway distributions were built with hatchling (the project's
  build backend) and installed into a Python 3.11.18 environment: `good-engine` (entry
  point `process = good_engine:GoodAdapter`), `broken-engine` (`broken =
  broken_engine:BrokenAdapter`, whose module imports a library that is not installed) and,
  later and editable, `dup-engine` (`process = dup_engine:DupAdapter`). A script called
  `importlib.metadata.entry_points(group="lcsim.engines")`.
  - With good and broken installed, both were listed. `load()` on `process` returned
    `good_engine.GoodAdapter`. `load()` on `broken` raised `ModuleNotFoundError: No module
    named 'engine_library_that_is_not_installed'`.
  - With `dup-engine` added in editable mode, both `process` entries were listed, from
    `dup-engine` and `good-engine`, and `EntryPoints.names` showed `process` once.
    `eps["process"]` returned `dup_engine:DupAdapter` without any warning.
  - After uninstalling `good-engine`, only `dup-engine`'s `process` remained.
- **pyarrow licence.** `importlib.metadata` on pyarrow 26.0.1 (both Python versions):
  `License-Expression: Apache-2.0`; `LICENSE.txt` is 110,383 bytes and starts "Apache
  License / Version 2.0, January 2004". Its bundled-code `License:` lines are Apache 2.0,
  3-clause BSD, 2-clause BSD, MIT and Zope Public License 2.1. The only "GPL" text is
  the LLVM-style exception for combining with GPLv2 code.
- **pyarrow wheels.** The PyPI JSON for 26.0.1 lists `cp311` and `cp313` wheels for
  `win_amd64`, `manylinux` and `macosx`.
- **pyarrow round trip.** A table with the spec 1 `replications` columns (`scenario`
  string, `replication` int64, `metric` string, `value` float64, `unit` string) was written
  to Parquet twice and read back. Schema equal: true. Table equal: true. Float values
  bit-equal: true. The two files were byte-identical within one process (SHA-256 prefix
  `cf0c98bdc1029f9c`, the same on Python 3.11 and 3.13). Spec 1 does not require identical
  bytes.
- **`lcsim` on PyPI.** `https://pypi.org/pypi/lcsim/json` returned HTTP 200: name `lcsim`,
  version 0.2.0, summary "LCSim - liquid crystal simulator".
