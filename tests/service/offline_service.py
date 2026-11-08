"""``python tests/service/offline_service.py [service options]``: the service of
``python -m lcsim.service`` with the network guard of ``offline_guard.py`` installed when
``LCSIM_TEST_OFFLINE_DIR`` is set (AKS-114, the offline test).

The guard is installed at import, outside the ``__main__`` block, because a run's worker is
started with ``spawn``, which imports this file again as the worker's main module (and the
worker's own pool processes import it from there): so every process of the service installs
the guard before it does anything else. The ``__main__`` block keeps the service from
starting in those processes.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.offline_guard import install_from_environment

install_from_environment()

if __name__ == "__main__":
    from lcsim.service.main import main

    raise SystemExit(main(sys.argv[1:]))
