# Ithax

A free, open-source desktop tool that lets people model, simulate and optimize processes,
machines and materials without writing code. It wraps proven open-source engines behind one
visual interface. Commercial tools in this field are priced by quote and built for
specialists, and their free editions cap model size or forbid real use; open-source engines
match them on capability but need programming and Linux skills. This product closes that
gap. Its package, commands and folders are named `ithax`; folders made under the earlier
working name, `lcsim`, are still used while no `ithax` folder exists.

**Status: Phase 1 complete (milestone M11, 2026-11-09), on Linux.** Process simulation
(SimPy) and optimization (HiGHS through Pyomo, simulation-based search with Optuna) in a
desktop app with a canvas, ten templates with Learn and Build modes, plain-language findings,
and an MCP server so an AI assistant can build and run models. The Windows version is
deferred until the Phase 1 review. The owner's acceptance checks are listed in
[`docs/sessions/2026-11-09-M11.md`](docs/sessions/2026-11-09-M11.md).

## Install on Linux

The package is one archive for Linux on x86_64, `ithax-<version>-linux-x86_64.tar.gz`, with
its checksum file `ithax-<version>-linux-x86_64.tar.gz.sha256`. It brings its own Python,
the engine service, the engines, the interface, the templates and the desktop window, so it
needs no network and no administrator rights to install or run. Get both files from the
`ithax-linux-x86_64` artifact of the `package` job of a CI run (until releases are
published), or build them (see Development).

**The package is not signed.** Check the archive against its checksum before installing; if
the check does not print `OK`, do not install it:

```bash
sha256sum -c ithax-<version>-linux-x86_64.tar.gz.sha256
```

Install as yourself, not as root:

```bash
mkdir -p ~/.local/opt
tar -xzf ithax-<version>-linux-x86_64.tar.gz -C ~/.local/opt
~/.local/opt/ithax-<version>-linux-x86_64/install.sh
```

`install.sh` checks the engines, links `ithax`, `ithax-launcher` and `ithax-mcp` into
`~/.local/bin` and adds Ithax to your desktop's applications.

Start it with `ithax` (or from the applications menu). It opens the desktop window; where the
window's system libraries are missing it opens the interface in your browser instead (on
Ubuntu or Debian, `sudo apt install libwebkit2gtk-4.1-0` brings them). On a machine without
a display, `ithax-launcher --print-url` starts the engine service and prints the interface's
address. `ithax-mcp` is the MCP server for an AI assistant.

Your first result: press **Continue** on the welcome notice, then **Learn**, then **Start
the lesson** on "Coffee shop queue", and follow the steps to the results.

Requirements: Linux on x86_64 with glibc 2.39 or later for the desktop window (Ubuntu 24.04
or later) and glibc 2.34 or later for the browser (Ubuntu 22.04, Debian 12); tested on
Ubuntu 24.04. To remove it, run `uninstall.sh` in its folder and delete the folder; your
projects and settings stay in `~/.local/share/ithax` and `~/.config/ithax`.

## Development

Python 3.11 or later, Node 22, and for the desktop shell Rust with Tauri's Linux packages
(see `.github/workflows/checks.yml`, job `desktop`).

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"   # or, the exact versions CI runs: uv sync --locked --extra dev
bash scripts/check.sh   # format, lint, types, tests with the coverage gate
bash scripts/fast.sh    # the quicker gate while working: no coverage, benchmarks or templates
pytest -m benchmark     # benchmarks with known answers
pytest -m template      # the ten templates against their expected results
pytest -m perf          # performance checks, excluded from check.sh
uv lock --upgrade       # a dependency update, in its own PR (uv.lock pins what CI runs)

(cd ui && npm ci && npm run check && npm run build && npm run e2e)   # the interface
(cd desktop && npm ci && npm run build && npm test)                  # the desktop shell
pytest -m desktop       # the shell driven to Home (tauri-driver, Xvfb)

python scripts/package_linux.py   # the Linux package, into dist/
pytest -m package                 # install it in a clean container, online and offline
```

Run the app from a checkout with `python -m ithax.launcher` once `ui/` is built.

- Product brief and build specs: [`docs/specs/`](docs/specs/), the source of truth, each with
  a version line
- How the build proceeds, milestone by milestone: [`docs/specs/build-guide.md`](docs/specs/build-guide.md); where it stands: [`docs/STATUS.md`](docs/STATUS.md); the map for coding sessions: [`CLAUDE.md`](CLAUDE.md)
- Decision log: [`docs/DECISIONS.md`](docs/DECISIONS.md); research notes in
  `docs/research/`, session summaries in `docs/sessions/`

## Licence

GNU Affero General Public License version 3 only. See [`LICENSE`](LICENSE). The Linux
package lists every bundled component and its licence in `THIRD-PARTY-LICENSES.txt`.
Simulation results are estimates and carry no warranty.
