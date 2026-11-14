#!/usr/bin/env bash
# The fast inner gate (docs/retrospective/proposed-agent-setup.md, P2 and tier 2; #99). Not a
# substitute for scripts/check.sh, which CI runs: no coverage, no benchmarks, no templates.
#   bash scripts/fast.sh          lint, types and the fast tests
#   bash scripts/fast.sh --lint   lint and types only (the Stop hook in .claude/settings.json)
# `python -m` is deliberate: the first ruff or pytest on PATH need not be the project's. The
# repository's .venv is used when there is one, so the hooks work without an activated shell.
set -euo pipefail
cd "$(dirname "$0")/.."

python=python
if [[ -x .venv/bin/python ]]; then
    python=.venv/bin/python
fi
"$python" -m ruff format --check .
"$python" -m ruff check .
"$python" -m mypy
if [[ "${1:-}" != "--lint" ]]; then
    # This -m replaces the one in pyproject's addopts, so it repeats every exclusion there
    # (tests/test_hooks.py checks it) and adds benchmark and template.
    "$python" -m pytest -q -x -n auto \
        -m "not benchmark and not template and not benchmark_coverage and not perf and not remote and not cluster and not desktop and not package"
fi
