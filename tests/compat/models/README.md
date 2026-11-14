# Model compatibility corpus

Build guide "Conventions", Compatibility (#99; docs/retrospective/proposed-agent-setup.md,
P24): a model file that loads in a released version loads in every later version, through
migration when its format version is older.

Each folder is a format version; each file a model as it was saved. The corpus only grows:
a file is added (for example, every template and example of a release) and never changed or
removed. `tests/compat/test_models_load.py` loads every file and requires zero errors.

It started on 2026-11-14 with every model of `examples/`, `templates/` and `benchmarks/` at
the close of Phase 1: 30 files, 27 at format 0.1 and 3 at format 0.2.
