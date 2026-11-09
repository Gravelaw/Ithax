# Proposed agent coding setup for Phase 1a and Phase 2

AKS-143, 2026-11-09. Draft for the owner's approval: **nothing here has been applied.**
- The owner decided on 2026-11-09 (B2) that changes to `CLAUDE.md`, the build guide, CI and tooling are drafted first. Each change below is given as exact text or a diff, for a later session to apply once it is approved.
- The diffs are written against `main` at `f36a6f5` (after PR #56). M11 is changing `CLAUDE.md`, `docs/specs/`, `.github/` and the code in parallel, so whoever applies them must rebase them onto `main` after M11 merges.
- The evidence for every proposal is in [`phase-1-engineering-review.md`](phase-1-engineering-review.md), cited as W1 to W8.
- Outside sources are linked where they are used. Where a statement is a recommendation rather than a sourced fact, it is marked *(judgement)*.

## Contents

1. [Ranking](#1-ranking)
2. [Python tooling and configuration](#2-python-tooling-and-configuration) (P1, P9)
3. [Repository conventions](#3-repository-conventions) (P5, P16, P17)
4. [Testing strategy](#4-testing-strategy) (P1, P6, P12, P18)
5. [CI design and cost](#5-ci-design-and-cost) (P3, P4)
6. [The review loop](#6-the-review-loop) (P7)
7. [Sessions, sub-agents and merging](#7-sessions-sub-agents-and-merging) (P10, P11, P19)
8. [CLAUDE.md, the build guide, hooks and skills](#8-claudemd-the-build-guide-hooks-and-skills) (P2, P8, P15)
9. [Owner decisions](#9-owner-decisions) (P13, P14)
10. [From the Power of Ten, curl and the Linux kernel](#10-from-the-power-of-ten-curl-and-the-linux-kernel) (P20 to P25)
11. [Order of adoption](#11-order-of-adoption)

## 1. Ranking

Ratings are *(judgement)*, each based on the evidence cited.
- **Benefit:** how much of a measured Phase 1 cost the proposal removes.
- **Cost:** the work to adopt it. XS is under an hour, S under half a day, M one or two tickets, L a milestone-sized effort.
- **Risk:** what could go wrong in adopting it.
- **Quick win:** benefit H or M at cost XS or S, with low risk.

The **Source** column marks proposals that come from the three reference points the owner added on 2026-11-09 (section 10, and the review's "Safety-critical and long-lived practice"):
- **P10**: NASA/JPL "Power of Ten" and NASA practice (JPL D-60411, NPR 7150.2D);
- **curl**;
- **kernel**: the Linux kernel's development process.

A dash means the proposal comes from the Phase 1 evidence and the other sources in section 2 to 9 alone.

| Rank | ID | Proposal | Source | Fixes | Benefit | Cost | Risk | Quick win |
|---|---|---|---|---|---|---|---|---|
| 1 | P4 | Turn on "Automatically delete head branches", require one `all-green` check before merging, and stop Linear moving issues that a PR title merely names | curl ("We do not merge commits that have unexplained test failures") | W4 | H | XS | L | **Yes** |
| 2 | P13 | Collect the blocking owner questions **before** a milestone starts; a milestone does not build on an unanswered one | — | W1 | H | XS | L | **Yes** |
| 3 | P3 | CI: drop the duplicate benchmark job, add job timeouts, stop cancelling `main` runs, add the `all-green` job | curl | W3, W4 | H | S | L | **Yes** |
| 4 | P1 | Run pytest in parallel (`-n auto`), and make the one route test safe for it | — | W3 | H | S | L | **Yes** |
| 5 | P7 | Give Codex review guidelines in `AGENTS.md`; redesign after the **second** finding of a class; turn each recurring finding into a check | — | W2 | H | S | L | **Yes** |
| 6 | P21 | Complexity at most 15, no `exec` or `eval`, no `global`, and no new function over 60 lines: all at zero violations today | P10 (rules 4, 6, 8), NPR 7150.2D SWE-220 | W7, W8 | M | XS | L | **Yes** |
| 7 | P2 | Agent hooks: format on edit, lint and types on stop; a fast inner gate (`scripts/fast.sh`) | P10 (rule 10) | W8, W3 | M | S | L | **Yes** |
| 8 | P19 | The monitor merges nothing on a message's word: a merge-readiness checklist read from GitHub facts | kernel ("Indicate what could not be done") | W4, W5 | M | XS | L | **Yes** |
| 9 | P14 | Triage readings: reversible defaults are logged, not queued; owner items go in a weekly digest of at most 10 with a default date | — | W1 | H | S | M | No |
| 10 | P5 | One shared helper per house rule, enforced by ruff `banned-api` and a conventions test | curl (checksrc), kernel (checkpatch) | W2, W8 | H | M | L | No |
| 11 | P6 | Hypothesis property tests: no file, body or setting makes a loader raise | curl (fuzzing) | W2 | H | M | L | No |
| 12 | P20 | Runtime warnings are errors in tests (`filterwarnings = ["error"]`), after fixing the 10 tests that fail on a `ResourceWarning` today | P10 (rule 10), curl (`-Werror`) | W2, W8 | H | M | L | No |
| 13 | P24 | A compatibility contract: no saved model file and no `/v1` client breaks; a golden corpus checks it | kernel ("We don't cause regressions"), curl (ABI) | W5, Phase 2 | H | M | L | No |
| 14 | P12 | Fault injection for process lifetime, and torture tests that fail each file write and process start in turn | curl (torture tests) | W2 | H | M | L | No |
| 15 | P10 | Small PRs merged to `main` one at a time; at most one level of stacking; a size budget per PR | kernel ("one logical change per patch") | W4, W6 | H | M | M | No |
| 16 | P8 | `CLAUDE.md` becomes a map of under 100 lines; status and known gaps move to `docs/` | — | W5, W8 | M | M | M | No |
| 17 | P9 | Tooling baseline: uv with `uv.lock`, branch coverage gated, pydantic declared | NPR 7150.2D (SWE-189, SWE-190) | W3, W7 | M | S | M | No |
| 18 | P22 | Bounded loops and waits: every `while True` names its bound, every wait has a timeout, JSON nesting has a depth limit, no sleep-based synchronisation | P10 (rules 1, 2), JPL D-60411 (rules 3, 7) | W2, W7 | M | S | L | No |
| 19 | P25 | A maintainer role per area, a fix-only stabilisation step before a milestone closes, and a "Not verified" section in every PR and summary | kernel | W4, W5 | M | S | M | No |
| 20 | P11 | A separate GitHub identity for agents, and a rule that only the owner merges | kernel ("AI agents MUST NOT add Signed-off-by tags") | W4 | M | M | L | No |
| 21 | P23 | A scheduled long fuzzing run of the property tests, with the example database cached | curl (OSS-Fuzz), kernel (syzbot) | W2 | M | S | L | No (needs P6) |
| 22 | P15 | One file per decision instead of one 610 KB log; counts and CI states taken from the source | — | W5 | M | M | L | No |
| 23 | P16 | Split `validation.py` and `loading.py`; a service-protocol module for MCP and the launcher; import-linter contracts | — | W7 | M | M | M | No |
| 24 | P17 | Typed boundaries: `TypedDict` and `response_model` for the routes; interface types generated from OpenAPI | — | W7 | M | L | M | No |
| 25 | P18 | Weekly mutation testing (mutmut) on `model/` and `strict_json.py`, as a report rather than a gate | — | W2 | L | S | L | No |

## 2. Python tooling and configuration

### P1. Parallel tests

**Measured on 4 cores of the agent container on 2026-11-09:**

| Run | Wall time |
|---|---|
| Full suite, serial, no coverage | 384.6 s |
| Full suite, `pytest -n 4` (pytest-xdist 3.8.0), no coverage | 193.0 s (1.99× faster) |
| Without the `benchmark` and `template` markers, `-n 4` | 99.7 s for 3,852 tests |

In both parallel runs one test failed: `tests/service/test_routes.py::test_every_row_of_the_endpoint_table_has_a_request_test`. It checks a request recorder held in one process, so under xdist it cannot see the requests made in other workers.

**Peers.** FastAPI runs `pytest -n auto --dist loadgroup`; attrs runs `-n auto`; pandas uses `--dist=worksteal`, with `single_cpu` tests in a separate serial step ([FastAPI `scripts/test.sh`](https://raw.githubusercontent.com/fastapi/fastapi/master/scripts/test.sh), [pandas `pyproject.toml`](https://raw.githubusercontent.com/pandas-dev/pandas/main/pyproject.toml)).

**Changes:**
- Add `pytest-xdist` to the dev extra (diff under P9).
- Change the pytest line of `scripts/check.sh` (diff under P2).
- Fix the route test by moving its check out of a test and into the controller's `pytest_sessionfinish`. Today `tests/service/conftest.py` only moves the test to the end of collection, which under xdist does not wait for the other workers. In the fix, each worker already writes its record in its own `pytest_sessionfinish` (the `route_recorder.write_record` hook exists), and the controller, which is the process without `config.workerinput`, runs after every worker has finished. It reads all the worker records, asserts that every endpoint row was reached, and sets a failing exit status if not. The other way is to mark the test and its request tests `@pytest.mark.xdist_group("routes")` and run with `--dist loadgroup`, which keeps them on one worker. The controller check keeps the load balanced, so it is the better choice *(judgement)*. Codex found the first draft of this fix incomplete on PR #60.
- pytest-cov combines coverage from xdist workers by itself, so nothing else changes.

### P9. Tooling baseline

**Exact diff to `pyproject.toml`:**

```diff
 dependencies = [
     "defusedxml>=0.7.1",
     "fastapi>=0.162.1",
     "highspy>=1.15.1",
     "jsonschema>=4.26.0",
     "mcp>=2.3.0",
     "numpy>=2.4.6",
     "openpyxl>=3.1.5",
     "optuna>=5.0.0",
     "pint>=0.25.3",
     "pyarrow>=26.0.1",
+    # Imported directly by lcsim.service (request bodies); was only a transitive
+    # dependency of fastapi. Version is the one installed on 2026-11-09.
+    "pydantic>=2.13.5",
     "pyomo>=6.10.1",
     "python-multipart>=0.0.33",
     "scipy>=1.17.1",
     "simpy>=4.1.2",
     "uvicorn>=0.54.0",
     "websockets>=17.4",
 ]

 [project.optional-dependencies]
 dev = [
     "pytest>=9.2",
+    "pytest-xdist>=3.8.0",
+    "hypothesis>=6.170.15",
+    "import-linter>=2.16",
     "ruff>=0.17.4",
     "mypy>=2.4.1",
     "pytest-cov>=7.1",
     "types-jsonschema>=4.26.0.20261006",
     "httpx2>=2.16.0",
 ]
@@
 [tool.coverage.report]
 # `python -m lcsim.runs.worker` runs its guarded line only as a script; main() itself is
 # tested in process, and the module is run as a real subprocess (tests/runs/test_worker.py).
 exclude_also = ['if __name__ == "__main__":']
+
+[tool.coverage.run]
+# Branches as well as lines (docs/retrospective/proposed-agent-setup.md, P9). Measured on
+# 2026-11-09: 2,899 of 2,910 branches (99.6%), 99.92% combined.
+branch = true
```

**Lockfile (uv).**

- **What changes.**
  - Commit a `uv.lock`, made with `uv lock`.
  - CI installs with `uv sync --frozen --extra dev`, and `setup-uv` caches the downloads.
  - The `>=` floors in `pyproject.toml` stay, so the package still installs as a library. The lockfile only fixes what the gates run against.
- **What it costs.** A dependency update becomes a deliberate PR, made with `uv lock --upgrade`.
- **Why.**
  - Several tests pin seeded simulation output to 3 or 4 decimals, so an unpinned numpy or simpy release can fail them with no product change (W7). numpy 2.5.3 is already installed against the floor `>=2.4.6`.
  - pydantic installs from `uv.lock` in CI with `UV_FROZEN: true`, and attrs adds a one-week cooldown on new releases (`exclude-newer = "1 week"`). uv: "`uv.lock` … should be checked into version control" ([uv docs](https://docs.astral.sh/uv/concepts/projects/layout/)).
- **Risk.** The guide's documented install command, `pip install -e ".[dev]"`, must keep working for the owner on Windows. It does, because the lockfile adds a path and removes none.
- **Rule.** Recording each dependency with its licence (guide "Conventions") applies to uv and to each tool added here. The proposed versions and licences are:
  - pytest-xdist 3.8.0, MIT;
  - hypothesis 6.170.15, MPL-2.0;
  - import-linter 2.16, BSD-2-Clause;
  - uv 0.13.7, MIT or Apache-2.0, a tool rather than a dependency;
  - mutmut 3.8.1, BSD-3-Clause, for P18 and not in the dev extra.

  Check each licence against spec 1's licence rule when the change is applied *(judgement: licences from the projects' PyPI metadata as generally known; confirm on PyPI)*.

**Branch-coverage gate.** Use `--cov-fail-under=99` on combined line and branch coverage. That sits under the 99.92% measured, so it is a real gate. Today's gate is `--cov-fail-under=90` against a 100% that nothing enforces (W8). attrs gates on 100% branch coverage ([attrs `pyproject.toml`](https://raw.githubusercontent.com/python-attrs/attrs/main/pyproject.toml)). Google's guidance calls "per-commit coverage goals of 99% … reasonable" and project-wide goals above 90% "most likely not worth it" ([Google Testing Blog](https://testing.googleblog.com/2020/08/code-coverage-best-practices.html)). So **do not** spend effort raising the number; spend it on P6 and P18 *(judgement)*.

**Type checker.** Keep mypy `--strict`; it is ahead of most peers. Adding pyrefly 1.x as a second, non-gating checker, as NumPy, SciPy and attrs do ([pyrefly 1.0](https://pyrefly.org/blog/v1.0/)), is optional and not ranked. ty is still 0.0.x and not recommended yet.

## 3. Repository conventions

### P5. One shared helper per house rule, enforced mechanically

**Why.** W2: the same check was hand-written in many places, and each Codex fix patched one place.

**Step 1, a ticket.** Consolidate the helpers that already exist:

| Rule | Helper (one place) | Sites to move (2026-11-09) |
|---|---|---|
| JSON in | `lcsim.strict_json.read_json` / `read_json_file`, extended with the model loader's duplicate-key and digit-limit checks | 10 `json.loads` sites in `src` outside `strict_json.py`, among them `model/schema.py:52` (`model/loading.py`'s strict reader moves into `strict_json`) |
| JSON out | `lcsim.strict_json.encode_json` | 5 verbatim copies (`engines/process/translate.py:88`, `engines/optimize/adapter.py:111`, `engines/optimize/translate.py:74`, `runs/tables.py:66`, `runs/manifest.py:140`) |
| Whole number, not bool | `lcsim.strict_json.is_whole(value) -> TypeGuard[int]`, new, next to `whole_in` | 2 private helpers (`model/streams.py:66`, `mcp/tools.py:80`) and about 8 inline copies; `model/units.py:215` is the int-or-float variant and moves to the next row |
| Finite real | `lcsim.strict_json.is_finite_real(value) -> TypeGuard[float]`, new | about 12 separate `isfinite` and `isnan` checks |
| Atomic file write | `lcsim.files.atomic_write(path, data)`, new: temp file in the same folder, `fsync`, `os.replace` | 8 hand-rolled sites, with 3 naming schemes |
| Literal narrowing | one `TypeGuard` per `Literal` set in `model/loading.py` | 6 `# type: ignore[arg-type]` |

**Step 2.** Turn on enforcement once the sites are moved. The ruff `banned-api` rule (TID251) "enforces certain import conventions project-wide automatically" ([ruff](https://docs.astral.sh/ruff/rules/banned-api/)), and pandas uses it for exactly this ([pandas `pyproject.toml`](https://raw.githubusercontent.com/pandas-dev/pandas/main/pyproject.toml)).

Exact diff to `pyproject.toml`:

```diff
 [tool.ruff.lint]
-select = ["E", "F", "W", "I", "B", "UP", "ANN", "RUF"]
+select = ["E", "F", "W", "I", "B", "UP", "ANN", "RUF", "TID251"]

 # tests/mcp mirrors src/lcsim/mcp; without this, isort would take the MCP SDK, `mcp`, for a
 # first-party package because `src` lists `tests`.
 [tool.ruff.lint.isort]
 known-third-party = ["mcp"]
+
+# House helpers (docs/retrospective/proposed-agent-setup.md, P5). Each message tells the
+# agent what to use instead, so a lint failure carries its own fix.
+[tool.ruff.lint.flake8-tidy-imports.banned-api]
+"random".msg = "Randomness only through the spec 1 stream scheme: lcsim.model.streams.generator_for."
+"numpy.random.seed".msg = "Randomness only through the spec 1 stream scheme: lcsim.model.streams.generator_for."
+"numpy.random.default_rng".msg = "Randomness only through the spec 1 stream scheme: lcsim.model.streams.generator_for."
+"json.loads".msg = "Read JSON with lcsim.strict_json.read_json: it rejects NaN, infinity, lone surrogates and duplicate keys."
+"json.load".msg = "Read JSON with lcsim.strict_json.read_json_file."
+"json.dumps".msg = "Write JSON with lcsim.strict_json.encode_json."
+"os.replace".msg = "Write files with lcsim.files.atomic_write (one helper, one naming scheme, fsync)."

 [tool.ruff.lint.per-file-ignores]
-"tests/**" = ["ANN"]
+"tests/**" = ["ANN", "TID251"]
+"src/lcsim/strict_json.py" = ["TID251"]
+"src/lcsim/files.py" = ["TID251"]
```

**A conventions test** for the rules ruff cannot express. Proposed new file `tests/test_conventions.py`. It matches only the numeric pattern, so genuine boolean checks such as `service/settings_store.py:94` and `model/loading.py:394` (the `_show` renderer) are not flagged:

```python
"""House rules that ruff cannot express (docs/retrospective/proposed-agent-setup.md, P5)."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "lcsim"
HELPERS = {SRC / "strict_json.py"}


def _isinstance_of(node: ast.AST, name: str) -> bool:
    """Whether ``node`` is ``isinstance(x, name)`` or ``isinstance(x, (..., name, ...))``."""
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "isinstance"
        and len(node.args) == 2
    ):
        return False
    types = node.args[1]
    options = types.elts if isinstance(types, ast.Tuple) else [types]
    return any(isinstance(option, ast.Name) and option.id == name for option in options)


def _whole_number_checks(tree: ast.AST) -> list[int]:
    """Lines of ``isinstance(x, int) and not isinstance(x, bool)``: the hand-written
    'JSON number, not a bool' test. A plain ``isinstance(x, bool)``, which validates or
    renders a real boolean, is not matched."""
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.BoolOp)
        and isinstance(node.op, ast.And)
        and any(_isinstance_of(value, "int") for value in node.values)
        and any(
            isinstance(value, ast.UnaryOp)
            and isinstance(value.op, ast.Not)
            and _isinstance_of(value.operand, "bool")
            for value in node.values
        )
    ]


def test_whole_number_checks_go_through_strict_json() -> None:
    offenders = [
        f"{path.relative_to(SRC)}:{line}"
        for path in sorted(SRC.rglob("*.py"))
        if path not in HELPERS
        for line in _whole_number_checks(ast.parse(path.read_text(encoding="utf-8")))
    ]
    assert not offenders, (
        "Use lcsim.strict_json.is_whole or whole_in instead of "
        "isinstance(..., int) and not isinstance(..., bool): " + ", ".join(offenders)
    )
```

**Tried on 2026-11-09** against `f36a6f5`, from outside the repository. It flags 4 sites: `mcp/tools.py:82`, `model/schema.py:212`, `model/streams.py:67` and `service/discovery.py:81`. Hand-written variants of other shapes, such as an early `if isinstance(value, bool): return` before an integer check, are not matched. So the test is a backstop for the common shape, and the step 1 migration still has to find the rest by review.

**Risk.** Low. Each rule fails with a message that names the fix. The migration in step 1 must come first, or the lint gate fails on existing code.

### P16. Structure

1. **Split the two oversized modules.**
   - Split `model/validation.py` (2,105 effective lines, maintainability index 0) by the rule groups its own docstring lists, one module per group under `model/validation/`.
   - Split `model/loading.py` (1,458 lines) into reading (`load_text`), building (`_Builder`) and the public entry points.
   - Keep the public names in `model/__init__.py`, so callers do not change.
   - Do this in Phase 2's first milestone, before new validation rules are added *(judgement)*.
2. **Add a service-protocol module.**
   - Create `lcsim/service_protocol.py` holding `LOCAL_ADDRESS`, `STARTUP_WAIT_S`, the service-file format and `canonical()`.
   - Then `mcp/client.py` and the launcher no longer import `service.main`, which today pulls in 72 of 97 modules (W7).
   - Pass the installed engines into the model loader from `runs` and `service`, which removes the lazy `model` → `engines` import.
3. **Add layer contracts.** OpenAI's agent-built product enforces its layers "mechanically via custom linters … and structural tests" ([OpenAI](https://openai.com/index/harness-engineering/)); import-linter does this for Python ([import-linter](https://import-linter.readthedocs.io/en/stable/)). Proposed addition to `pyproject.toml`:

```toml
[tool.importlinter]
root_package = "lcsim"

[[tool.importlinter.contracts]]
name = "Layers: model < engines < runs, templates, findings < service < mcp, launcher"
type = "layers"
layers = [
    "lcsim.mcp | lcsim.launcher",
    "lcsim.service",
    "lcsim.runs | lcsim.templates | lcsim.findings",
    "lcsim.engines",
    "lcsim.model",
]
# Remove once P16 item 2 passes the engines in (docs/retrospective/proposed-agent-setup.md).
ignore_imports = ["lcsim.model.loading -> lcsim.engines.registry"]

[[tool.importlinter.contracts]]
name = "MCP is a client: it never loads the run manager"
type = "forbidden"
source_modules = ["lcsim.mcp"]
forbidden_modules = ["lcsim.runs"]
```

Add `lint-imports` to `scripts/check.sh` after `mypy`. Before applying, check the `|` syntax for independent siblings against the installed import-linter version. The second contract fails until item 2 is done, so add it with item 2.

### P17. Typed boundaries

- Describe each response, manifest, summary and settings file with a `TypedDict` or a pydantic model.
- Declare `response_model` on the 24 routes that return `dict[str, Any]`.
- Generate `ui/src/api/types.ts` from the OpenAPI document FastAPI then produces, and check in CI that the generated file is current. Today `ui/src/api/types.ts` is a hand-written mirror. Several spec or contract findings were the interface disagreeing with the service or the spec (#47, #48, #53, #55).
- Cost is L. Do it route by route as Phase 2 touches each route *(judgement)*.

## 4. Testing strategy

### Tiers: fast inside, complete outside

| Tier | When | What | Time measured or expected |
|---|---|---|---|
| 0 | After each edit (hook, P2) | `ruff format` and `ruff check --fix` on the edited file | under 1 s |
| 1 | When the agent stops (hook, P2) | `scripts/fast.sh --lint`: ruff and mypy | ruff 0.2 s; mypy 13 s cold, 0.3 s warm |
| 2 | Before every push | `scripts/fast.sh`: tier 1, then pytest `-n auto -x`, no coverage, without `benchmark` and `template` | 99.7 s measured on 4 cores |
| 3 | CI on every push, and before merge | `scripts/check.sh`: everything, `-n auto`, coverage of lines and branches, benchmarks and templates | about 3.5 to 4.5 min expected *(judgement: 193 s measured without coverage)* |
| 4 | Weekly, or before a milestone closes | mutation testing (P18), Hypothesis at many more examples, `pytest -m perf` | report only |

**Proposed new file `scripts/fast.sh`:**

```bash
#!/usr/bin/env bash
# The fast inner gate (docs/retrospective/proposed-agent-setup.md, tier 2). Not a substitute
# for scripts/check.sh, which CI runs: no coverage, no benchmarks, no templates.
#   bash scripts/fast.sh          lint, types and the fast tests
#   bash scripts/fast.sh --lint   lint and types only (the Stop hook)
set -euo pipefail
cd "$(dirname "$0")/.."

python -m ruff format --check .
python -m ruff check .
python -m mypy
if [[ "${1:-}" != "--lint" ]]; then
    python -m pytest -q -x -n auto \
        -m "not benchmark and not template and not benchmark_coverage and not perf and not remote and not cluster"
fi
```

`python -m` is deliberate: in the agent container the `ruff` first on `PATH` is 0.16.9, not the project's 0.17.4, and the `pytest` first on `PATH` cannot import `lcsim`. The code-analysis and CI mining found both.

### P6. Property-based tests for the classes Codex kept finding

**Why.** 29 of the 100 Codex findings were input robustness: extreme or hostile values making a code path raise instead of returning an issue (W2). There is no generated test. In a study of 426 Python projects, "each property-based test finds about 50 times as many mutations as the average unit test", with a small effect size ([Ravi and Coblenz, OOPSLA 2025](https://dl.acm.org/doi/full/10.1145/3764068)). NumPy and SciPy use Hypothesis, and CPython caches the Hypothesis database across CI runs.

**The properties.** Each is one test file under `tests/properties/`:

| Property | Generator | Finding classes it covers |
|---|---|---|
| `load_document` and `load_text` never raise; they return a model or at least one issue | arbitrary JSON values, plus the coffee-shop example with one leaf replaced by an extreme value | #4, #5, #9, #10, #15, #18, #35, #53 |
| Every service route answers any JSON body with 2xx or 4xx and an issue body, never 5xx | per-route bodies built from the same extreme values, through `TestClient` | #35, #36, #39, #50 |
| Every file the product reads back (`settings.json`, `manifest.json`, `summary.json`, template packages) gives an issue, never an exception, on any content | the same values, written to `tmp_path` | #36, #37, #50 |
| `strict_json.encode_json(read_json(x))` round-trips every accepted value, and `read_json` rejects NaN, infinity, lone surrogates and duplicate keys | `st.recursive` JSON | #35, #50 |
| Path helpers: `canonical(a) == canonical(b)` exactly when `a` and `b` name the same folder | `st.sampled_from` over relative, drive-less, symlinked and `..`-after-link forms built in `tmp_path` | #34 (4 findings) |

**Proposed first file, `tests/properties/test_loading_never_raises.py`.** It uses the API as it stands on `f36a6f5`:

```python
"""Property: no document makes the model loader raise; it returns a model or an issue.

Covers the input-robustness findings of Phase 1 (docs/retrospective/
phase-1-engineering-review.md, W2).
"""

import copy
import json
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from lcsim.model.loading import load_document, load_text

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = json.loads((ROOT / "examples" / "coffee_shop.json").read_text(encoding="utf-8"))

EXTREME_NUMBERS = st.one_of(
    st.integers(min_value=-(10**400), max_value=10**400),
    st.floats(allow_nan=True, allow_infinity=True),
    st.sampled_from([0, -1, 10**309, 1e308, -1e308, 5e-324]),
)
HOSTILE_STRINGS = st.one_of(
    st.text(max_size=20),
    st.sampled_from(["", "\ud800", "constructor", "__proto__", "..", "C:", "\\projects"]),
)
JSON_VALUES = st.recursive(
    st.none() | st.booleans() | EXTREME_NUMBERS | HOSTILE_STRINGS,
    lambda inner: st.lists(inner, max_size=4) | st.dictionaries(HOSTILE_STRINGS, inner, max_size=4),
    max_leaves=25,
)


def _leaf_paths(value: object, path: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
    if isinstance(value, dict):
        return [p for k, v in value.items() for p in _leaf_paths(v, (*path, k))] or [path]
    if isinstance(value, list):
        return [p for i, v in enumerate(value) for p in _leaf_paths(v, (*path, i))] or [path]
    return [path]


LEAVES = _leaf_paths(EXAMPLE)


@given(JSON_VALUES)
def test_any_document_gives_a_model_or_an_issue(document: object) -> None:
    result = load_document(document)
    assert result.model is not None or result.issues


# No deadline: a valid model reaches the engine discovery and the meaning pass, and the first
# such call took 920 ms when this test was tried on 2026-11-09.
@settings(max_examples=300, deadline=None)
@given(st.sampled_from(LEAVES), JSON_VALUES)
def test_the_example_with_one_hostile_leaf_gives_a_model_or_an_issue(
    path: tuple[object, ...], value: object
) -> None:
    document = copy.deepcopy(EXAMPLE)
    target: object = document
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    if path:
        target[path[-1]] = value  # type: ignore[index]
    result = load_document(document)
    assert result.model is not None or result.issues


@given(st.binary(max_size=200) | st.text(max_size=200))
def test_any_bytes_or_text_gives_a_model_or_an_issue(text: bytes | str) -> None:
    result = load_text(text)
    assert result.model is not None or result.issues
```

**Tried on 2026-11-09.** The file above was run against `main` at `f36a6f5`, with Hypothesis 6.170.15 installed into the session's environment only, from outside the repository. All three tests pass:
- at the default 100 examples (with the first call to the second test tripping Hypothesis's 200 ms deadline until `deadline=None` was added);
- at 10,000, 3,000 and 10,000 examples, in 33 s.

So the model loader has no open defect of this class today: the Phase 1 fixes hold. The test's value is in catching the next new site or regression before review does, which is what kept happening in Phase 1. The service-route and read-back properties are untried.

**Settings for CI.**
- Register a Hypothesis profile in `tests/conftest.py`: `settings.register_profile("ci", derandomize=True, deadline=None)`, loaded when `CI` is set. A failure is then reproducible, and a slow runner does not trip the deadline.
- Tier 4 runs a `"thorough"` profile with `max_examples=2000`.
- Keep `.hypothesis/` out of git, which needs an addition to `.gitignore`.

**The interface.** The canvas races (22 findings, 17 of them on #45) suit stateful, model-based tests of `ui/src/canvas/session.ts` with fast-check: random sequences of edit, rename, move, undo and slow responses, checked against a simple model of the expected document. fast-check was not part of the industry research, so this is *(judgement)*. Check its licence and fit before adopting it.

### P12. Fault injection for process lifetime, and torture tests (from curl)

11 Codex findings and the one late bug (`service.json` left after SIGTERM, M6 to M9) were about processes not cleaning up. The M6 tests "stop services without asserting the removal" (`docs/sessions/2026-11-08-M7.md:100`).

Add one parametrised test per supervisor: the service, the run worker and the search. It stops the process each way:

- SIGTERM;
- SIGINT;
- SIGKILL of a child;
- `OSError` raised on start;
- a worker that ignores SIGTERM;
- a cancel during result writing.

After each, it asserts the same invariants:

- no `service.json` and no lock left behind;
- no descendant process alive;
- the run state is final;
- the slot is released.

Run them in tier 3.

**Torture tests.** curl reruns each test so as "to have every invoked fallible function call fail once each, to make sure curl never leaks memory or crashes due to this" ([curl `docs/VERIFY.md`](https://github.com/curl/curl/blob/master/docs/VERIFY.md)). The Python equivalent here:

1. Once P5 routes every file write through `lcsim.files.atomic_write`, a fixture can count the fallible calls a test makes (writes, `os.replace`, process starts) and rerun the test once per call, raising `OSError` at that call.
2. Each run must end in an issue or a clean failure, with no partial file, lock or child process left.
3. Run this for the run-folder, project-store and service-file tests, in tier 4 (weekly). It multiplies run time by the number of calls.

### Seeded exact values

- Either rely on the P9 lockfile, or replace the exact assertions on seeded output (for example `tests/findings/test_rules.py:110`, `tests/service/test_summary_findings.py:114-174`) with the spec 2 statistical pass rule or a tolerance.
- The lockfile is cheaper, and keeps the cross-process identity tests meaningful *(judgement)*.

### Flaky tests

- Fixed sleeps of 0.2 to 1.0 s widen race windows (`tests/service/test_runs.py:543,1210`, `tests/runs/test_local_search.py:138`, `tests/mcp/test_mcp_write_tools.py:987`, `tests/service/test_models.py:337`). Replace them with events or barriers that the code under test exposes to tests.
- The Vitest timeout that turned `main` red (W4) was fixed with an explicit timeout (7919636). Do the same for every jsdom test that renders a full screen, and give the reason in a comment.
- Never skip a test to get green.

### P18. Mutation testing, reported and not gated

- Run mutmut weekly on `src/lcsim/model/` and `src/lcsim/strict_json.py`, and file the surviving mutants as tickets.
- mutmut "remembers work that has been done, so you can work incrementally" ([mutmut](https://github.com/boxed/mutmut)). It needs `fork`, so it runs in Linux CI or WSL.
- Google runs diff-based mutation testing for 6,000 engineers ([Petrović and Ivanković, ICSE-SEIP 2018](https://research.google/pubs/state-of-mutation-testing-at-google/)), and reports that mutants "are indeed coupled with real faults" ([Petrović et al., ICSE 2021](https://ieeexplore.ieee.org/document/9402038)).
- Ranked last because Codex and P6 cover most of the same ground at lower cost *(judgement)*.

## 5. CI design and cost

### What Phase 1 spent

| | |
|---|---|
| Raw minutes | 2,645 |
| Billed minutes (each job rounded up) | 3,289 |
| `checks` (3.11 and 3.13) | 1,969 raw |
| `benchmarks` (a duplicate of what `checks` already runs) | 368 raw |
| `interface` | 294 raw |
| `pr-title` | 14 raw, about 245 billed |
| Cancelled jobs | 125 raw |

The repository is now public, and "standard GitHub-hosted runners in public repositories" are free ([GitHub billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)). Cost matters again only if it goes private. Speed matters either way.

### P3. Proposed `.github/workflows/checks.yml` (full text)

```yaml
name: checks

# Design: docs/DECISIONS.md, 2026-11-06 · M0, "CI workflow (AKS-73)"; revised by
# docs/retrospective/proposed-agent-setup.md, P3 (no duplicate benchmark job, timeouts,
# main runs never cancelled, one all-green check for branch protection).

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

# PR runs: a newer push cancels the older run. Pushes to main: one group per commit, so
# every merge to main is tested and none is cancelled by the next merge.
concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.sha }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  checks:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
          cache-dependency-path: pyproject.toml
      - run: python -m pip install -e ".[dev]"
      # The single gate. It includes the benchmarks (guide rule 8) and the templates.
      - run: bash scripts/check.sh

  interface:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    defaults:
      run:
        working-directory: ui
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip
          cache-dependency-path: pyproject.toml
      - run: python -m pip install -e ".[dev]"
        working-directory: .
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: ui/package-lock.json
      - run: npm ci
      - run: npm run check
      - run: npm run build
      - run: npx playwright install --with-deps chromium
      - run: npm run e2e
        env:
          LCSIM_PYTHON: python

  # The one check that branch protection requires (P4). A skipped or cancelled job counts
  # as a failure here, so a red or missing job can never be merged past.
  all-green:
    if: always()
    needs: [checks, interface]
    runs-on: ubuntu-latest
    timeout-minutes: 2
    steps:
      - env:
          RESULTS: ${{ join(needs.*.result, ' ') }}
        run: |
          echo "needs: $RESULTS"
          for result in $RESULTS; do
            [[ "$result" == "success" ]] || { echo "::error::a required job did not succeed"; exit 1; }
          done
```

**What changes from today:**

- **The `benchmarks` job is removed.** The `benchmark` marker is not excluded in `addopts`, so `check.sh` already runs every benchmark, on both Python versions. This saves about 14% of minutes, with no loss of gating.
- **`timeout-minutes` is set on every job.** Today there are none, so the default of 360 minutes applies.
- **Pushes to `main` get one concurrency group per commit.** Today 41 of 67 `main` runs (61%) were cancelled.
- **There is one `all-green` job for branch protection.** FastAPI and attrs use the same pattern, with `re-actors/alls-green` ([FastAPI `test.yml`](https://raw.githubusercontent.com/fastapi/fastapi/master/.github/workflows/test.yml), [attrs `ci.yml`](https://raw.githubusercontent.com/python-attrs/attrs/main/.github/workflows/ci.yml)). It is written inline here to avoid a third-party action *(judgement)*.
- **`pr-title.yml` is unchanged.** It is cheap now that the repository is public.

**After P9 (uv).** Replace the `setup-python` and `pip install` steps with `astral-sh/setup-uv` (`enable-cache: true`) and `uv sync --frozen --extra dev`, as pydantic and FastAPI do. Use the action version current on the day; it is not given here because it was not checked.

`uv sync` creates `.venv` but does not activate it for later steps, so every later command must use that environment:
- `checks` job: `uv run bash scripts/check.sh`.
- `interface` job:
  - Set `LCSIM_PYTHON: ${{ github.workspace }}/.venv/bin/python`, or remove `LCSIM_PYTHON`. `ui/e2e/service.ts::python()` uses `LCSIM_PYTHON` first and falls back to the repository's `.venv` only when it is unset, so today's `LCSIM_PYTHON: python` would bypass the environment.
  - Run the Python install step as `uv sync --frozen --extra dev` in the repository root.

Codex found the first draft of this paragraph incomplete on PR #60.

**Not proposed.** Path filters for docs-only pushes.
- A workflow skipped by a path filter leaves its required check "Pending" and blocks the merge ([GitHub docs](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks)).
- The safe pattern (a `paths-filter` job plus `if:` on each job) adds moving parts for little gain once runs are fast and free *(judgement)*.

**If the repository goes private again:**
- Add a payment method with a budget alert. Without one, "usage is blocked once you consume the included compute usage" (GitHub billing, above).
- Forward GitHub's 90% usage mail to wherever the monitor reads. In Phase 1 that mail arrived 4 h 21 min before the stop, and no agent saw it.

### P4. Repository settings, done once by the owner in GitHub and Linear

1. **Settings → General → Pull Requests → "Automatically delete head branches": on.** When a merged PR's head branch is deleted, "GitHub automatically updates any such pull requests, changing their base branch to the merged pull request's base branch" ([GitHub docs](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-and-deleting-branches-within-your-repository)). This removes the 17 hand retargets and the git-proxy 403 on branch deletion, because GitHub deletes the branch, not the agent.
2. **Add a branch protection rule or ruleset on `main`.**
   - Require a pull request.
   - Require the status check `all-green` to pass, with the branch up to date before merging.
   - Block force pushes and deletion.

   This would have stopped #49, which was merged 37 s after its last push with the head still running and later red. Check that the account's plan offers rulesets or branch protection for this repository's visibility when applying.
3. **Linear → Settings → Integrations → GitHub.** Make "pull request opened" move only the issue named in the branch name, not every issue the title or body mentions. Otherwise, name only the worked issue in the PR title and refer to others in the body without Linear's magic words. AKS-130 and AKS-133 sat falsely In Progress for 21.6 h and 14.5 h. The exact option names in Linear's GitHub settings were not checked *(judgement)*.

## 6. The review loop

### P7. Stop repeat findings

**1. Steer Codex with `AGENTS.md`.** OpenAI's documentation for Codex code review on GitHub says Codex looks for `AGENTS.md` files in the repository and follows a "Review guidelines" section in them ([OpenAI, Codex GitHub integration](https://developers.openai.com/codex/integrations/github); read through a search summary on 2026-11-09, so check the exact heading name on the page before applying).
- Claude Code reads `AGENTS.md` only when there is no `CLAUDE.md` ([Claude Code memory docs](https://code.claude.com/docs/en/memory)), so the file steers Codex without changing what sessions read.
- Proposed new root file `AGENTS.md`:

```markdown
# AGENTS.md

Coding sessions in this repository follow `CLAUDE.md`. This file steers automated review.

## Review guidelines

- Review against the specs in `docs/specs/` and the build guide in `CLAUDE.md`. Do not comment
  on formatting or style: ruff and mypy --strict gate those.
- Treat as P1: a process, worker or lock left behind after a stop, cancel or failure; any
  file, request body or setting whose content makes a code path raise instead of returning
  an issue object (spec 1 "Issues"); a write outside the project folder or the run folder.
- These classes recurred in Phase 1 (docs/retrospective/phase-1-engineering-review.md). Look
  for them on every change that reads input, and say whether the shared helper was bypassed:
  - integers beyond float range, values near 1e308 and their sums, NaN and infinity
    (helper: `lcsim.strict_json.real_in`, `whole_in`, `is_finite_real`);
  - lone surrogate strings, JSON `null` where an object is expected, duplicate keys, and keys
    such as `constructor` in the interface (helper: `lcsim.strict_json.read_json`);
  - Windows paths without a drive, symlink or junction aliases, `..` after a link
    (helper: `lcsim.service.paths.canonical`);
  - loops that never check for cancellation; waits with no time limit;
  - interface state written from a stale draft or after a screen has closed.
- Do not ask for a guard against input that the spec says cannot reach that code.
```

**2. Redesign after the second finding, not the third.** Proposed addition to the build guide's "Session procedure":

> **Review findings.** When a review finds a second defect of the same class in one PR, stop patching. Find every site of that class in the repository, fix them through one shared helper, and add a check that would have caught the next one: a lint rule, a conventions test or a property test (P5, P6). Say so in the reply to the second finding.

The evidence: #34 redesigned path handling after the third path finding, and a fourth then came against the new module. #45 needed five redesigns.

**3. Promote recurring classes into code.** OpenAI's agent team: "When documentation falls short, we promote the rule into code", with lint messages written "to inject remediation instructions into agent context" ([OpenAI](https://openai.com/index/harness-engineering/)). Each new class found twice gets an `AGENTS.md` bullet and a `banned-api` message or test (P5).

**4. Review against the spec, and say no when it is right to.**
- No finding was rejected in Phase 1. Anthropic: "A reviewer that's asked to find problems will always find something. If you fix every finding, you end up with extra abstraction layers and tests for cases that can't happen" ([Claude Code best practices](https://code.claude.com/docs/en/best-practices)).
- Proposed guide text: "Reply to each finding with *Fixed in `<sha>`*, *Fixed for the whole class in `<sha>`*, or *Not a defect: `<the spec section or invariant that makes it unreachable>`*."

**5. Author checklist before the first push** (a skill, see P8): run `scripts/fast.sh`, then walk the `AGENTS.md` classes against the diff. Catching a class before review saves a round. Rounds were 7 to 25 minutes apart, and #45 had 10 of them.

## 7. Sessions, sub-agents and merging

### P10. Small PRs, merged one at a time

**Why.**
- W4 and W6. 38 commits exceeded 1,000 lines. M9's six stacked PRs (#44 to #49) changed about 37,300 lines (+36,437/−878) and merged together after an overnight wait.
- Google's median change is 24 lines, and "the number of useful comments decreases … as the size of the change increases" ([Sadowski et al.](https://doi.org/10.1145/3183519.3183525)).
- DORA: working in small batches "acts as a safety net for AI adoption", and branches in trunk-based development "typically last no more than a few hours" ([DORA small batches](https://dora.dev/capabilities/working-in-small-batches/), [DORA trunk-based](https://dora.dev/capabilities/trunk-based-development/)).

**Proposed rules,** for the build guide's "Session procedure" and each kickoff prompt:

> **Pull requests.** One ticket is one or more PRs; each PR does one thing and stays under about 400 changed lines of product code (tests, fixtures and docs not counted). A PR whose work depends on another waits for that PR to merge, or stacks on it one level only, with "Automatically delete head branches" retargeting it when the parent merges. A PR is merged when it is green (`all-green`), its review threads are resolved, and the monitor's readiness check (P19) passes; a milestone closes when its last PR merges, not when a stack merges.

The 400-line figure is *(judgement)*, not derived from Phase 1 data. It is well above Google's median, and well below the 1,000-line commits behind most review rounds. Tune it after a milestone.

**Ticket size.** A ticket a sub-agent can finish, with its tests, within one session's context, and that names its acceptance rows. GitHub's guidance for its coding agent: "An ideal task includes: A clear description … Complete acceptance criteria … Directions about which files need to be changed", and avoid "Ambiguous tasks" ([GitHub](https://docs.github.com/en/copilot/tutorials/coding-agent/get-the-best-results)).

**Sub-agents.**
- Keep one sub-agent per independent ticket.
- Do not parallelise tickets that touch the same files: in Phase 1 they became stacks.
- Multi-agent runs use "about 15× more tokens than chats", and "most coding tasks involve fewer truly parallelizable tasks than research" ([Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)).

### P11. Who merges

- **Rule:** sessions and sub-agents never merge. The owner merges, or turns on GitHub auto-merge for a PR that passes P19.
- **The problem.** This cannot be enforced or audited today: agents use the owner's GitHub and Linear accounts, so all 56 merges and every agent-written Linear comment look like the owner's (W4).
- **The fix.** Give agents their own identity, such as a machine user or a GitHub App with write access but no admin rights, and require an approving review from the owner on `main`. Agent merges are then impossible rather than forbidden.
- **Cost.** One account or app, and switching the agent git and GitHub credentials. That needs the owner, and is M.

### P19. The monitor checks facts, not messages

The M9 close recorded "CI passed on #48 and #49" in a commit (bc17810) that was itself then red (W4, W5).

**Proposed monitor checklist,** run against GitHub through the API for each PR before reporting it ready or merging it:

1. The PR's head SHA is the SHA the checks below refer to.
2. Every check run on that head SHA has `conclusion: success`. `all-green` alone is enough once P3 is in.
3. Codex's last summary refers to that head SHA, and the PR has zero unresolved review threads.
4. The base is `main`, and the PR is not a draft.
5. No commit was pushed after items 1 to 3 were read. If one was, start again.

**Rule:** a session summary, `CLAUDE.md` or a decision may state a CI result only with the run ID and head SHA it was read from.

## 8. CLAUDE.md, the build guide, hooks and skills

### P8. `CLAUDE.md` becomes a map

**Evidence.**
- `CLAUDE.md` is 172 lines but 24 KB. "Known gaps" is 6.5 KB and "Current state" 7.8 KB of per-milestone prose.
- It must equal `docs/specs/build-guide.md`, which `tests/test_docs.py` enforces.

**Guidance.**
- Anthropic: "target under 200 lines per CLAUDE.md file. Longer files consume more context and reduce adherence" ([memory docs](https://code.claude.com/docs/en/memory)).
- Anthropic also says to include "the exact test, typecheck, and lint commands" and "Anything you've had to correct twice already", and to stop describing "your architecture and file layout" ([best practices](https://code.claude.com/docs/en/best-practices)).
- OpenAI: "one big AGENTS.md … failed", so they use "roughly 100 lines … as a map" ([OpenAI](https://openai.com/index/harness-engineering/)).

**Proposal.**
- The full guide stays in `docs/specs/build-guide.md`, where it is the source of truth.
- "Current state" moves to a new `docs/STATUS.md`.
- "Known gaps" moves to the build guide only.
- `CLAUDE.md` becomes the short map below.
- `tests/test_docs.py` check 1 (the guide part of `CLAUDE.md` equals the build guide) is replaced by a check that every file `CLAUDE.md` links to exists, and that `CLAUDE.md` is under 120 lines.

**Proposed `CLAUDE.md`** (full text, 76 lines):

```markdown
# Ithax (lcsim): guide for coding sessions

This file is a map. The build guide is `docs/specs/build-guide.md` (rules, milestones, known
gaps, procedures); milestone status is `docs/STATUS.md`; decisions are in `docs/decisions/`.
Read the guide sections your ticket names, not the whole guide. Specs are in `docs/specs/`.

## Commands

- Install: `pip install -e ".[dev]"` (after P9: `uv sync --frozen --extra dev`).
- While working: `bash scripts/fast.sh` (lint, types, fast tests in parallel; about 2 min).
- Before every push, and what CI runs: `bash scripts/check.sh`; judge it by its exit code.
- Subsets: `python -m pytest tests/model`, `python -m pytest -m benchmark`;
  performance: `taskset -c 0-3 python -m pytest -m perf`.
- Interface: `cd ui && npm run check && npm run build && npm run e2e`.
- In the agent container use `python -m ruff` and `python -m pytest`: the `ruff` and
  `pytest` first on PATH are other installs.

## Rules (the guide's session rules, short form)

1. Read the guide sections and the spec for your ticket first.
2. One ticket per session or sub-agent; one milestone at a time; research notes before code
   (`docs/research/`, headings Question, Finding, Sources, Decision, Tested).
3. Tests before implementation. Acceptance rows tagged with the milestone are the gates;
   benchmarks are gates; rows marked "owner" are listed, not gated.
4. Unclear spec: sort the question first (guide rule 5). Blocking questions go to the owner
   before the work; reversible readings are logged in one line and not queued.
5. A decision that departs from a spec changes the spec in the same PR, with a dated line under
   its "Changes in this version". Never write to the owner's Claude Docs.
6. Wrap engines; never write a numerical solver. Calculators cite a formula and a published
   worked example.
7. Pull requests: one purpose, under about 400 changed lines of product code, merged one at a
   time. Never merge a PR yourself; the owner merges.
8. A second review finding of the same class in one PR means: fix the whole class through one
   helper and add a check that catches the next one (guide "Review findings").
9. State a CI result only with its run ID and head SHA.
10. End with a summary (`docs/sessions/<yyyy-mm-dd>-M<n>.md`: Built, Checks passing,
    Decisions logged, Awaiting owner, Left) and update `docs/STATUS.md`.

## Rules the tools enforce (do not work around them)

| Rule | Enforced by |
|---|---|
| Randomness only through the spec 1 stream scheme (`lcsim.model.streams`) | ruff TID251 |
| JSON read and written only through `lcsim.strict_json` | ruff TID251 |
| Files written only through `lcsim.files.atomic_write` | ruff TID251 |
| Whole numbers checked with `strict_json.is_whole` / `whole_in` | `tests/test_conventions.py` |
| No input makes a loader or route raise; problems are issue objects with a code | `tests/properties/` |
| Layers: model < engines < runs, templates, findings < service < mcp, launcher | import-linter |
| Format, lint, types | hooks in `.claude/settings.json`, then `scripts/check.sh` |

## Conventions the tools do not check

- Python 3.11 or later; full type hints; mypy --strict over `src` and `tests`.
- Units are converted at load; no unit strings past the model layer.
- Engines write only inside their run folder.
- Each new dependency gets a decision record with its licence (spec 1 engine licence rule).
- Commits: small, one purpose, `M<n>: <imperative summary>` or `specs: ...`.

## Where things are

- `src/lcsim/`: `model/` (schema, loading, validation, edits), `engines/` (adapter, plugins
  `process/` SimPy and `optimize/` HiGHS), `runs/`, `service/`, `mcp/`, `findings/`,
  `templates/`; `tests/` mirrors `src/`.
- `ui/`: the interface (React, React Flow; its own `npm run check`).
- `benchmarks/<case>/`, `examples/`, `templates/`: data with known answers.
- `docs/research/`, `docs/design/`, `docs/sessions/`, `docs/decisions/`, `docs/specs/`.

## Things the code does not show

- uvicorn re-raises SIGTERM and SIGINT after shutdown; cleanup must not rely on `finally`
  after `server.run()` (M6 bug, fixed at M9).
- Seeded simulation outputs are asserted exactly in a few tests; a numpy or simpy upgrade can
  change them. Upgrade dependencies in their own PR.
- Linux first (owner decision B4, 2026-11-09): keep the code platform-neutral as built;
  Windows packaging is deferred, and the Phase 1 review sets its phase.
- The package name `lcsim` is a placeholder.
```

The concrete text of hard rules marked as tool-enforced assumes P5, P6 and P16 have landed. Until each lands, its row reads "review" instead.

### P2. Hooks

Claude Code hooks are deterministic, unlike instructions: "Claude Code applies this every time". A Stop hook that exits 2 blocks Claude from finishing ([best practices](https://code.claude.com/docs/en/best-practices)). The set is kept small. Anthropic warns that "If you ever find yourself at forty of them, most are probably preferences."

**Proposed new file `.claude/settings.json`:**

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR/scripts/hooks/format_edited.py\""
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "cd \"$CLAUDE_PROJECT_DIR\" && { git diff --quiet HEAD -- '*.py' && git diff --cached --quiet -- '*.py'; } || bash scripts/fast.sh --lint 1>&2 || exit 2"
          }
        ]
      }
    ]
  }
}
```

**Proposed new file `scripts/hooks/format_edited.py`:**

```python
"""PostToolUse hook: format and lint-fix the Python file that was just edited.

docs/retrospective/proposed-agent-setup.md, P2. Never fails the edit: problems that ruff
cannot fix are left for the Stop hook and scripts/check.sh to report.
"""

import json
import subprocess
import sys

path = str(json.load(sys.stdin).get("tool_input", {}).get("file_path", ""))
if path.endswith(".py"):
    subprocess.run([sys.executable, "-m", "ruff", "format", "--quiet", path], check=False)
    subprocess.run([sys.executable, "-m", "ruff", "check", "--fix", "--quiet", path], check=False)
```

**How they behave.**
- The Stop hook runs only when tracked Python files differ from `HEAD`, so a docs-only turn is not delayed.
- With a warm mypy cache it costs about 1 s; cold, about 15 s.
- A new, untracked file is not seen until it is staged. That is a known gap, and `check.sh` still covers it.
- Claude Code overrides a Stop hook that blocks "eight stops in a row" (best practices, above), so a stuck lint error cannot trap a session.
- `sys.executable` assumes the hook's `python3` is the project's interpreter. In the agent container, the interpreter where `pip install -e ".[dev]"` ran.

### Skills

These are proposed as `.claude/skills/<name>/SKILL.md`. Each is a procedure that is today repeated in kickoff prompts and summaries:

| Skill | What it does |
|---|---|
| `close-milestone` | Run `check.sh` and the benchmarks, write the session summary from the template, update `docs/STATUS.md`, list the "Awaiting owner" items in the digest format (P14). `disable-model-invocation: true` |
| `review-reply` | For a review thread: classify the finding against the `AGENTS.md` classes, apply rule 8 of `CLAUDE.md`, reply with the fixed-in SHA, resolve |
| `pre-push` | `scripts/fast.sh`, then the `AGENTS.md` classes checked against `git diff main...` |
| `owner-question` | Write a blocking question as a Linear `owner-decision` issue: the question, options, recommended default, what it blocks, the date the default applies |

`disable-model-invocation: true` is for workflows with side effects, and procedures belong in skills rather than `CLAUDE.md` ([best practices](https://code.claude.com/docs/en/best-practices)).

### P15. Decision records

`docs/DECISIONS.md` is 610 KB, about 150,000 tokens. No session can read it whole, yet rule 6 asks sessions to keep it consistent (W5). Nygard: "Large documents are never kept up to date. Small, modular documents have at least a chance" ([Nygard](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions)).

**Proposal.**
- From Phase 2, one file per decision: `docs/decisions/NNNN-<slug>.md`, adapted from MADR's minimal template ([MADR](https://adr.github.io/madr/)). The proposed fields are Status, Context, Decision, Consequences, and Dependencies added (name, version, licence, how checked).
- An index `docs/decisions/README.md` lists one line per record.
- `docs/DECISIONS.md` is frozen as the Phase 1 log and keeps its anchors. It is not split retroactively; that costs much and gains little *(judgement)*.

**Counts.** Counts that the record states, such as tests passed, findings and readings, are copied from command output with the command named, never retyped. Several such figures in the Phase 1 record are wrong (W5).

**Build-guide diff for "Session procedure":**

```diff
-- **DECISIONS entry template.** A date and milestone heading, then Decision, Reason, Alternatives considered, Spec sections updated, Dependencies added (name, version, licence, how checked).
+- **Decision records.** One file per decision, `docs/decisions/NNNN-<slug>.md` (adapted from MADR's minimal template: Status, Context, Decision, Consequences, Dependencies added with name, version, licence and how checked), and one line in `docs/decisions/README.md`. `docs/DECISIONS.md` is the frozen Phase 1 log.
+- **Numbers in the record.** A count or a CI result in a summary, a status line or a decision is copied from the output of a named command or API call (with the run ID and head SHA for CI), never retyped.
```

## 9. Owner decisions

### P13. Ask blocking questions before the milestone, not during it

**Evidence (W1).**
- Eight of the ten council questions waited 76.4 h. Meanwhile M4, M6 and M9 built to the defaults. Two of those defaults were then changed: B5 made the idle exit a setting (rework at M11), and B4 deferred the Windows work already built.
- 6 of 14 explicit owner verdicts overturned or modified the default.

**Proposed build-guide text,** a new step in "Session procedure", run by the orchestrator before each kickoff:

> **Questions before a milestone.** Before a milestone starts, its session lists every question whose answer would change an interface, a file format, a target platform, or more than a day of work, and files each as a Linear `owner-decision` issue (skill `owner-question`): the question, the options, a recommended default, what it blocks, and the date on which the default applies if unanswered. Work that depends on an open blocking question is not started; the rest of the milestone proceeds.

### P14. Triage readings, and a digest of at most 10

**Evidence (W1).**
- 402 "Awaiting owner" items, of which 386 are readings, and the owner has ruled on 4.
- The orchestrator's own estimate: of about 250, "about 20 … need a real owner choice" (AKS-130, 2026-11-08).

**Proposed replacement for guide rule 5:**

```diff
-5. **Never guess silently.** If a spec is unclear or seems wrong, stop and ask. If the owner is not available, take the simplest reading, record it in `docs/DECISIONS.md`, and flag it in the session summary.
+5. **Never guess silently; sort before you ask.** If a spec is unclear or seems wrong, sort the question.
+   - **Blocking** (it changes an interface, a file format, a target platform, or more than a day of work): it should have been asked before the milestone (procedure "Questions before a milestone"); if it arises during the work, file it as an `owner-decision` issue with a recommended default and a date, and build only what does not depend on it.
+   - **Reversible** (anything else): take the simplest reading, change the spec with a dated line, and list it under "Readings" in the session summary, one line each. Readings are not "Awaiting owner" items; the owner may sample them.
```

**Proposed change to the session summary headings in "Session procedure":**

```diff
-- **Session summary.** `docs/sessions/<yyyy-mm-dd>-M<n>.md` with the headings Built, Checks passing, Decisions logged, Awaiting owner, Left. The session's last act updates "Current state" in `CLAUDE.md`.
+- **Session summary.** `docs/sessions/<yyyy-mm-dd>-M<n>.md` with the headings Built, Checks passing, Decisions logged, Awaiting owner, Readings, Left. "Awaiting owner" holds only blocking questions and owner checks, at most ten, each with its recommended default and the date it applies; "Readings" lists reversible readings, one line each. The session's last act updates `docs/STATUS.md`.
```

**The digest.**
- The orchestrator sends the owner one digest a week, or at each milestone close if that comes sooner.
- It holds the open blocking questions, at most 10, each with a one-line recommendation and its default date, plus the count of readings since the last digest and a link to them.
- A default that passes its date unanswered is recorded as a decision with Status "default applied".
- The owner can turn any reading into a question.

**Risk (M).** Sorting a question as reversible that is really blocking. Mitigations:
- The four criteria in the rule.
- The owner's sampling of readings.
- Any reading the owner overturns is recorded with the criterion it missed, so the criteria can be improved.

## 10. From the Power of Ten, curl and the Linux kernel

The owner added these three reference points on 2026-11-09. The review's section "Safety-critical and long-lived practice" maps each rule and practice onto this project, with sources, and says where a rule does not transfer because Python is not C:
- Power of Ten rule 3 (no dynamic allocation) and rule 9 (pointers) do not transfer.
- Rule 5 (assertion density) does not transfer as written.
- Rule 8 (the preprocessor) has only a weak analogue.

The proposals below are the new ones. The ones that already existed and gained a source are marked in the ranking table: P3, P4, P5, P6, P9, P10, P11, P12 and P19.

### P20. Runtime warnings are errors (Power of Ten rule 10; curl `-Werror`)

**Evidence.** Holzmann: "All code must compile with these setting without any warnings" ([P10 paper](https://spinroot.com/gerard/pdf/P10.pdf)). curl: "We always use `-Werror` that converts warnings to errors" ([`docs/VERIFY.md`](https://github.com/curl/curl/blob/master/docs/VERIFY.md)). The project's static tools are already at zero warnings; its tests are not.

On 2026-11-09 the fast tier was run with `-W error` (`python -m pytest -n 4 -W error`, without benchmarks and templates). **10 tests fail, every one on a `ResourceWarning`**: seven say a subprocess "is still running" when its `Popen` object is collected, and the rest are unclosed files. They are in `tests/launcher/test_launch.py`, `tests/runs/test_limits.py` and `tests/runs/test_lock.py`. That is the process-lifetime class Codex kept finding (W2), raised by the interpreter. Whether each leak is in the product or in the test was not determined.

**Step 1, a ticket.** Triage and fix the 10. A deliberate detach, such as the launcher starting a service that outlives it, should keep its `Popen` handle or close it explicitly, rather than silence the warning.

**Step 2, exact diff to `pyproject.toml`:**

```diff
 addopts = "-ra --strict-markers -m 'not benchmark_coverage and not perf and not remote and not cluster'"
+# Warnings are errors (Power of Ten rule 10; docs/retrospective/proposed-agent-setup.md,
+# P20). A third-party warning that cannot be fixed here gets its own "ignore:" entry
+# with the reason.
+filterwarnings = ["error"]
```

pydantic and FastAPI set the same option (industry digest A1 and A2).

### P21. Complexity, length, scope and dynamic code (Power of Ten rules 4, 6 and 8; NPR 7150.2D SWE-220)

NPR 7150.2D caps safety-critical components at "a cyclomatic complexity value of 15 or lower" (SWE-220, [Chapter 3](https://nodis3.gsfc.nasa.gov/displayDir.cfm?Internal_ID=N_PR_7150_002D_&page_name=Chapter3)). lcsim is not safety-critical, but **no function exceeds 15 today**: ruff's mccabe finds 12 above 10, 2 above 12 and 1 above 14. Nor are there any `exec` or `eval` calls (ruff `S102`, `S307`) or `global` statements (`PLW0603`) in `src` or `tests`. So these rules cost nothing to adopt and stop the code drifting.

**Exact diff to `pyproject.toml`** (it combines with P5's diff, which adds `TID251` to the same line):

```diff
 [tool.ruff.lint]
-select = ["E", "F", "W", "I", "B", "UP", "ANN", "RUF"]
+select = ["E", "F", "W", "I", "B", "UP", "ANN", "RUF", "C90", "S102", "S307", "PLW0603"]
+
+# Power of Ten rule 4 in spirit, and NPR 7150.2D SWE-220's cap for safety-critical code.
+# No function exceeded it on 2026-11-09 (P21).
+[tool.ruff.lint.mccabe]
+max-complexity = 15
```

**Function length, rule 4.** 20 of 1,094 functions exceed 60 lines. Proposed new file `tests/test_function_length.py`, a ratchet whose allow-list may only shrink. It was tried on 2026-11-09 against `f36a6f5`, from outside the repository: it passes, and mypy `--strict` is clean.

```python
"""Power of Ten rule 4 for Python: no function longer than 60 lines (P21).

The allow-list holds the functions that were longer on 2026-11-09. It may only shrink:
splitting one of them means deleting its line here, and no new name may be added.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "lcsim"
MAX_LINES = 60
ALLOWED = {
    "model/loading.py::_Builder.build",
    "model/loading.py::_Builder.component",
    "model/loading.py::_Builder.distribution",
    "model/loading.py::_Builder.program",
    "model/migration.py::migrate",
    "model/schema.py::_issues_from_error",
    "model/validation.py::identifier_issues",
    "model/validation.py::setting_issues",
    "model/validation.py::connection_issues",
    "model/validation.py::_setting_values",
    "model/validation.py::_distribution_issues",
    "model/validation.py::data_issues",
    "model/validation.py::experiment_issues",
    "model/validation.py::_experiment_values",
    "runs/snapshots.py::read_columns",
    "runs/summary.py::build_summary",
    "runs/targets.py::LocalRun.__init__",
    "service/app.py::create_app",
    "templates/package.py::_Loader.template",
    "templates/package.py::_Loader.runnable",
}


def _long_functions(path: Path) -> set[str]:
    found: set[str] = set()

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, f"{prefix}{child.name}.")
            elif isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                end = child.end_lineno if child.end_lineno is not None else child.lineno
                if end - child.lineno + 1 > MAX_LINES:
                    found.add(f"{path.relative_to(SRC).as_posix()}::{prefix}{child.name}")
                visit(child, f"{prefix}{child.name}.")

    visit(ast.parse(path.read_text(encoding="utf-8")), "")
    return found


def test_no_new_function_is_longer_than_60_lines() -> None:
    long: set[str] = set()
    for path in sorted(SRC.rglob("*.py")):
        long |= _long_functions(path)
    assert not long - ALLOWED, (
        f"Split these functions (at most {MAX_LINES} lines): {sorted(long - ALLOWED)}"
    )
    assert not ALLOWED - long, f"Now short enough; remove from ALLOWED: {sorted(ALLOWED - long)}"
```

**Not adopted:**
- **Rule 5's two assertions per function.** Python drops `assert` under `-O`, and errors here must be issue objects; P6's properties are the analogue.
- **Rule 3 and rule 9.** There is nothing to enforce in Python, and banning callables would forbid the engine plug-ins.

### P22. Bounded loops and waits (Power of Ten rules 1 and 2; JPL D-60411 rules 3 and 7)

- **Rule 2:** "All loops must have a fixed upper-bound", except loops "meant to be non-terminating (e.g., in a process scheduler)" ([P10 paper](https://spinroot.com/gerard/pdf/P10.pdf)).
- **JPL D-60411 rule 3:** "Use verifiable loop bounds for all loops meant to be terminating".
- **JPL D-60411 rule 7:** "Do not use task delays for task synchronization" ([D-60411, mirror](https://yurichev.com/mirrors/C/JPL_Coding_Standard_C.pdf)).

These name the process-lifetime findings (unbounded joins, a cancel deadline that reset, a queue loop that never yields: #24, #27) and the fixed-sleep tests of W7.

1. **Every `while True` names its bound.** Each of the 11 `while True` loops in `src` gets a comment on the loop line, `# bound: <deadline, cancel check or count that ends it>`, or `# bound: none, a server loop ended by <signal>`. Add to `tests/test_conventions.py` (P5) a test that every `while True` line carries `# bound:`. A reviewer then checks the stated bound instead of searching for it.
2. **Every wait has a timeout.** Add an `AGENTS.md` review-guidelines bullet, and the same line in `CLAUDE.md`'s "Conventions the tools do not check": every `join`, `wait`, `communicate`, queue `get` and lock acquisition in `src` passes a timeout, or carries a comment naming what ends it. A lint rule for this would match too much (`str.join`), so it stays a review rule *(judgement)*.
3. **JSON nesting has a depth limit.** `lcsim.strict_json.read_json` rejects nesting deeper than a fixed limit (for example 64 levels) with a coded issue, instead of relying on catching `RecursionError`. The 10 recursive walkers in `src` then have a proven bound (rule 1's purpose). Codex found two `RecursionError` crashes (#18, #27).
4. **No sleep-based synchronisation.** Replace the fixed sleeps that widen race windows in tests (W7) with events or barriers. Keep sleeps only as polling intervals inside a loop that has a deadline.

### P23. A scheduled fuzzing run (curl and OSS-Fuzz; kernel syzbot)

- curl fuzzes "non-stop as part of Google's OSS-Fuzz project, but also briefly as part of the CI setup for every commit and PR" ([`docs/VERIFY.md`](https://github.com/curl/curl/blob/master/docs/VERIFY.md)).
- The kernel's syzbot "continuously fuzzes main Linux kernel branches and automatically reports found bugs" ([syzbot](https://github.com/google/syzkaller/blob/master/docs/syzbot.md)).
- The short version is P6 in every CI run. The long version is a nightly job that runs the same properties with many more examples and keeps Hypothesis's example database between runs, as CPython does (industry digest A6).
- Standard runners are free for this public repository.
- Whether lcsim qualifies for OSS-Fuzz itself was not checked.

**Proposed new file `.github/workflows/fuzz.yml`** (needs P6's `tests/properties/` and its `thorough` profile):

```yaml
name: fuzz

# Long property-based runs (docs/retrospective/proposed-agent-setup.md, P23). A failure is
# filed as a ticket with the falsifying example Hypothesis prints.
on:
  schedule:
    - cron: "17 3 * * *"
  workflow_dispatch:

permissions:
  contents: read

jobs:
  properties:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip
          cache-dependency-path: pyproject.toml
      - uses: actions/cache@v4
        with:
          path: .hypothesis
          key: hypothesis-${{ github.run_id }}
          restore-keys: hypothesis-
      - run: python -m pip install -e ".[dev]"
      - run: python -m pytest tests/properties --hypothesis-profile=thorough
```

### P24. A compatibility contract (kernel "no regressions"; curl's ABI promise)

**The two models.**
- The kernel's "first rule": "*We don't cause regressions*"; "If the kernel used to work for you, the rule is that it continues to work for you" ([handling-regressions](https://docs.kernel.org/process/handling-regressions.html)).
- curl: "A libcurl upgrade does not break the ABI or change established and documented behavior" ([`docs/libcurl/ABI.md`](https://github.com/curl/curl/blob/master/docs/libcurl/ABI.md)).

**Why now.**
- In Phase 1 the specs changed 166 times, and nothing outside the specs depended on them.
- From Phase 2, saved models, template packages and assistants calling `/v1` through MCP do depend on them.
- The model format already has versions and a migration test (M1). The `/v1` API has no compatibility check.

**Proposed build-guide rule** (a new item under "Conventions"):

> **Compatibility.** A model file that loads in a released version loads in every later version, through migration if its format version is older. A `/v1` request that works keeps working, and a `/v1` response keeps every field it had, with the same JSON type; new fields may be added. A change that cannot meet this needs a new format version with a migration, or a new API version, and an owner decision record.

**Proposed tests** (`tests/compat/`):
- `models/<format_version>/`: a corpus that only grows. It starts with every file in `examples/`, `templates/` and `benchmarks/` as they are at the Phase 1 close. Each file must load with zero errors in the current version.
- `api/v1/<route>.json`: for one fixed, seeded scenario, the key paths and JSON types of each route's response. The test fails when a recorded key disappears or changes type, and passes when one is added.

### P25. Maintainers, a stabilisation step, and what was not verified (the kernel process)

1. **A maintainer per area.**
   - The kernel routes every patch to the maintainers of the code it touches (`MAINTAINERS`, `scripts/get_maintainer.pl`; [submitting-patches](https://docs.kernel.org/process/submitting-patches.html)).
   - Here, the orchestrating session acts as maintainer. For each PR it checks the diff against the spec of the area touched: model format (spec 1), engines (spec 2), service and interface (spec 3), MCP and findings (spec 4).
   - It reports readiness by P19, and the owner merges (P11).
   - Proposed kickoff-prompt line: "Before the PR is reported ready, the maintainer reads the spec sections for the areas the diff touches and lists in the PR any behaviour that differs from them."
2. **A fix-only stabilisation step.**
   - The kernel follows a merge window of "approximately two weeks" with "six to ten weeks" in which "only patches which fix problems should be submitted", and takes stable fixes only if "obviously correct and tested" and at most "100 lines, with context" ([2.Process](https://docs.kernel.org/process/2.Process.html), [stable rules](https://docs.kernel.org/process/stable-kernel-rules.html)).
   - Proposed build-guide addition to "Milestones": "A milestone closes in two steps. Its feature PRs merge first; then one stabilisation ticket runs the full gate, the benchmarks and the scheduled fuzzing on `main`, and accepts only fixes, each under about 100 changed lines, until all are green. The session summary is written at the end of that ticket."
   - This would have caught the red `main` after M9 before M10 began (W4).
3. **"Not verified" in every PR and summary.**
   - The kernel's rules for AI assistants: "Indicate what could not be done. If the fix could not be built or tested, or if no reproducer could be produced, say so explicitly" ([coding-assistants](https://docs.kernel.org/process/coding-assistants.html)).
   - Proposed: every PR body and session summary has a "Not verified" heading, listing what was not run or not checked, or "Nothing".
   - The kernel also says "AI agents MUST NOT add Signed-off-by tags" (same page), which supports P11's separate identity. A Developer Certificate of Origin is not proposed: there is one owner and no outside contributors *(judgement)*.

**Not proposed: curl's large CI matrix.** curl runs "over two hundred CI jobs … for every commit and every PR" because it ships on dozens of platforms. This project is Linux-first (B4), so two Python versions and the interface job are proportionate *(judgement)*.

## 11. Order of adoption

**Before or alongside M11's merge** (settings only, no repository change, no conflict with M11):

1. P4: auto-delete head branches, the Linear setting, and branch protection once `all-green` exists.
2. P13 and P14 as orchestration practice for M11's remaining owner items. They become guide text with Phase 1a.

**Phase 1a, the setup milestone after M11 merges.** One small PR per row, in this order:

| PR | Contents | Proposals |
|---|---|---|
| 1 | `checks.yml` and the branch-protection check; the ruff complexity, `exec`, `eval` and `global` rules and the function-length test (zero violations today) | P3 (then finish P4 item 2), P21 |
| 2 | xdist in `check.sh`, the route-test fix, the branch-coverage gate, pydantic declared | P1, part of P9 |
| 3 | `scripts/fast.sh`, `.claude/settings.json`, `scripts/hooks/format_edited.py` | P2 |
| 4 | `AGENTS.md`, plus the guide text on review findings | P7 |
| 5 | the guide text for rule 5, questions before a milestone, the summary headings and decision records | P13, P14, P15 |
| 6 | `CLAUDE.md` as a map, `docs/STATUS.md`, the `test_docs.py` change | P8 |
| 7 | `uv.lock` and the uv CI steps | rest of P9 |
| 8 | the helper consolidation, then `banned-api` and `tests/test_conventions.py` | P5 |
| 9 | the first property tests (`tests/properties/`) | P6 |
| 10 | fix the 10 tests that fail with `-W error`, then `filterwarnings = ["error"]` | P20 |
| 11 | the compatibility corpus and the `/v1` shape records, plus the guide rule | P24 |

**Phase 2, as each area is touched:** P25 (from the first Phase 2 milestone), P22 (bounded loops and waits), P23 (after P6), P12 (fault injection and torture tests), P16 (module splits, the service-protocol module, import-linter), P17 (typed boundaries), P11 (agent identity, which needs the owner), P18 (weekly mutation report).

**Measure after Phase 1a,** to check that the proposals worked *(judgement: the targets are starting points)*:

| Measure | Phase 1 value | Target |
|---|---|---|
| Median `checks` job time | 4.8 to 6.2 min | under 4 min |
| `main` runs cancelled | 61% | none |
| Findings per PR in the input-robustness, process-lifetime and paths classes | 0.84 (47 findings over 56 PRs) | under 0.2 |
| PRs merged with a red or unfinished head | 1 | 0 |
| Manual base changes | 17 | 0 |
| "Awaiting owner" items per milestone | 40 (median, M4 to M10) | at most 10 |
| Owner wait on a blocking question | 76 h | under 24 h, or the default date |
| Tests failing with `-W error` (fast tier) | 10 | 0, then gated (P20) |
| Functions over complexity 15, and new functions over 60 lines | 0, and 20 old ones over 60 | 0, and the 20 shrinking |
