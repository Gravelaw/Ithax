"""``python -m lcsim.mcp``: see ``lcsim.mcp.server``.

Guarded, because the service and its runs use the ``spawn`` start method, which imports the
main module again.
"""

from lcsim.mcp.server import main

__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main())
