"""``GET /v1/system``: detected hardware and the active tier (spec 3 "Endpoints" and
"Hardware tiers").

The response is ``{cores, memory, graphics, tier, workers}``: ``memory`` in bytes (or
``null``), ``graphics`` the vendors found (or ``null``), ``workers`` what a run receives
on the active tier. The second start of the service probes this route (spec 3 "One
service per user").
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from ithax.service.hardware import tier_workers
from ithax.service.state import ServiceState, service_state

__all__ = ["router"]

router = APIRouter(prefix="/v1")


@router.get("/system")
def get_system(state: Annotated[ServiceState, Depends(service_state)]) -> dict[str, Any]:
    """Cores, memory, graphics, the active tier and its workers."""
    hardware = state.hardware
    return {
        "cores": hardware.cores,
        "memory": hardware.memory,
        "graphics": None if hardware.graphics is None else list(hardware.graphics),
        "tier": state.tier,
        "workers": tier_workers(state.tier, hardware.cores),
    }
