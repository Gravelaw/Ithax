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
bash scripts/check.sh   # format, lint, types, tests
```

## Licence

AGPL version 3 only. See [`LICENSE`](LICENSE).
