# lcsim (working name)

A free, open-source desktop tool to model, simulate and optimize processes, machines and
materials without writing code. It wraps proven open-source engines behind one visual
interface. The product name is not chosen yet; `lcsim` is a placeholder.

**Status: milestone M0 (repository skeleton).** No product features exist yet.

- Product brief and build specs: [`docs/specs/`](docs/specs/)
- How the build proceeds, milestone by milestone: [`CLAUDE.md`](CLAUDE.md)
- Decision log: [`docs/DECISIONS.md`](docs/DECISIONS.md)

## Development

Python 3.11 or later.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
bash scripts/check.sh   # format, lint, types, tests with the coverage gate
pytest tests/model      # the model layer only
pytest -m benchmark     # benchmarks with known answers
pytest -m perf          # performance checks, excluded from check.sh
```

Research notes live in `docs/research/`, session summaries in `docs/sessions/`.
The specs in `docs/specs/` are the source of truth and each carries a version line.

## Licence

AGPL version 3 only. See [`LICENSE`](LICENSE).
