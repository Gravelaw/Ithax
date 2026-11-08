"""``/v1/settings``: the user's settings (spec 3 "Endpoints"; AKS-119, owner to confirm).

``GET`` gives ``{settings, issues}``, the six settings of ``settings.json`` as the service
takes them; ``PUT`` writes any of them and gives the same body after the write. The
checks and the file are ``lcsim.service.settings_store``. The thresholds take effect at the
next summary, the tier and the run settings at the next start.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool

from lcsim.service.state import ServiceState, service_state

__all__ = ["router"]

router = APIRouter(prefix="/v1/settings")

State = Annotated[ServiceState, Depends(service_state)]


@router.get("")
def get_settings(state: State) -> dict[str, Any]:
    """The settings as the service takes them, and the issues of reading them."""
    return state.settings.read()


@router.put("")
async def put_settings(request: Request, state: State) -> dict[str, Any]:
    """Write the settings the body names."""
    body = await request.body()
    return await run_in_threadpool(state.settings.write, body)
