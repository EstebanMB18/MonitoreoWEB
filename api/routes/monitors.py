from fastapi import APIRouter, HTTPException

from api.runtime import MONITOR_DEFINITIONS


router = APIRouter()


@router.get("/monitors")
def list_monitors():
    return {
        "items": MONITOR_DEFINITIONS,
        "total": len(MONITOR_DEFINITIONS),
    }


@router.get("/monitors/{monitor_id}")
def get_monitor(monitor_id: str):
    key = monitor_id.lower()

    for monitor in MONITOR_DEFINITIONS:
        if monitor["id"] == key:
            return monitor

    raise HTTPException(
        status_code=404,
        detail="Monitor no encontrado.",
    )
