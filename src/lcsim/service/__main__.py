"""``python -m lcsim.service``: see ``lcsim.service.main``.

Guarded, because runs use the ``spawn`` start method, which imports the main module again.
"""

from lcsim.service.main import main

__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main())
