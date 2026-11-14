"""``python -m ithax.mcp``: see ``ithax.mcp.server``.

Guarded, because the service and its runs use the ``spawn`` start method, which imports the
main module again.
"""

from ithax.mcp.server import main

__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main())
