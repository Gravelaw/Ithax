#!/usr/bin/env bash
# The project's checks. Run before every commit; CI runs the same script.
# Subsets from the Build guide's Session procedure: pytest tests/model,
# pytest -m benchmark, pytest -m perf (perf is excluded from this script).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== format (ruff format --check)"
ruff format --check .
echo "== lint (ruff check)"
ruff check .
echo "== types (mypy --strict)"
mypy
echo "== tests (pytest)"
pytest --cov=lcsim --cov-report=term-missing --cov-fail-under=90
