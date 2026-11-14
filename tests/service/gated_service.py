"""``python tests/service/gated_service.py [service options]``: the service of
``python -m ithax.service`` with the test adapter ``gated`` (``run_adapters.py``) installed
beside the product's adapters, so a test can hold a run of a real service process unfinished
for as long as it needs (AKS-112).

The run's worker is started with ``spawn``, which imports this file again as the worker's
main module; the guard keeps the service from starting there, and the worker finds
``service.run_adapters`` on the ``sys.path`` it inherits.
"""

import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from ithax.engines.registry import installed_adapters
    from ithax.service import app
    from ithax.service.main import main
    from service.run_adapters import GatedAdapter

    adapters = {**installed_adapters(), "gated": GatedAdapter()}
    # Replace the name create_app calls (a module attribute, so not a typed assignment).
    vars(app)["installed_adapters"] = lambda: adapters
    raise SystemExit(main(sys.argv[1:]))
