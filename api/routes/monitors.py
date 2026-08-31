from fastapi import APIRouter, Depends, HTTPException

from api.auth_dependencies import require_roles

from api.runtime import MONITOR_DEFINITIONS


router = APIRouter()


@router.get("/monitors")
def list_monitors(
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
            "OPERADOR",
            "CONSULTA",
        )
    ),
):
    return {
        "items": MONITOR_DEFINITIONS,
        "total": len(MONITOR_DEFINITIONS),
    }


@router.get("/monitors/{monitor_id}")
def get_monitor(
    monitor_id: str,
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
            "OPERADOR",
            "CONSULTA",
        )
    ),
):
    key = monitor_id.lower()

    for monitor in MONITOR_DEFINITIONS:
        if monitor["id"] == key:
            return monitor

    raise HTTPException(
        status_code=404,
        detail="Monitor no encontrado.",
    )
