#!/usr/bin/env bash
# The project's checks. Run before every commit; CI runs the same script.
# Subsets from the Build guide's Session procedure: pytest tests/model,
# pytest -m benchmark, pytest -m perf (perf is excluded from this script).
# The repository's .venv is used when there is one, as in scripts/fast.sh: the first ruff,
# mypy or pytest on PATH need not be the project's (#99, P8).
set -euo pipefail
cd "$(dirname "$0")/.."

python=python
if [[ -x .venv/bin/python ]]; then
    python=.venv/bin/python
fi
echo "== format (ruff format --check)"
"$python" -m ruff format --check .
echo "== lint (ruff check)"
"$python" -m ruff check .
echo "== types (mypy --strict)"
"$python" -m mypy
echo "== tests (pytest)"
# In parallel (pytest-xdist), with line and branch coverage gated at 99% ([tool.coverage.run]
# branch = true); docs/retrospective/proposed-agent-setup.md, P1 and P9 (#99).
"$python" -m pytest -n auto --cov=lcsim --cov-report=term-missing --cov-fail-under=99
