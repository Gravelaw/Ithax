"""``python tests/service/logged_service.py [service options]``: the service of
``python -m ithax.service``, its application wrapped in ``request_log.RequestLog`` so that
every call that reaches it is logged to the file ``LCSIM_TEST_REQUEST_LOG`` names (AKS-121,
the pointer-only end-to-end test's request log).

The wrapping is a test's: the product has no request log and no option for one. Everything
happens in the ``__main__`` block, so a run's worker, started with ``spawn``, which imports
this file again as its main module, does nothing here but import.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == "__main__":
    from fastapi import FastAPI

    from ithax.service import main as service_main
    from ithax.service.config import ServiceConfig
    from service.request_log import LOG_FILE_VARIABLE, RequestLog

    log = Path(os.environ[LOG_FILE_VARIABLE])
    # ``main`` builds its application with the ``create_app`` it imported; replace that one.
    namespace = vars(service_main)
    create_app = namespace["create_app"]

    def logged_app(config: ServiceConfig) -> FastAPI:
        # uvicorn takes any ASGI application; the type is FastAPI's for the patch only.
        return RequestLog(create_app(config), log)  # type: ignore[return-value]

    namespace["create_app"] = logged_app
    raise SystemExit(service_main.main(sys.argv[1:]))
