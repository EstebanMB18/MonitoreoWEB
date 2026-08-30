from enum import Enum

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.runtime import (
    MONITOR_REGISTRY,
    create_run,
    get_run,
    list_runs,
)


router = APIRouter()


class RunType(str, Enum):
    OFFICIAL = "OFFICIAL"
    MANUAL = "MANUAL"
    INCIDENT = "INCIDENT"
    TEST = "TEST"


class RunRequest(BaseModel):
    run_type: RunType = RunType.MANUAL
    cut: str | None = None
    reason: str | None = None


@router.post("/monitors/{monitor_id}/run")
def run_monitor(
    monitor_id: str,
    payload: RunRequest,
):
    key = monitor_id.lower()

    if key not in MONITOR_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail="Monitor no encontrado.",
        )

    return create_run(
        monitor_id=key,
        run_type=payload.run_type.value,
        cut=payload.cut,
        reason=payload.reason,
    )


@router.get("/runs")
def runs():
    items = list_runs()

    return {
        "items": items,
        "total": len(items),
    }


@router.get("/runs/{run_id}")
def run_detail(run_id: str):
    item = get_run(run_id)

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Ejecuci?n no encontrada.",
        )

    return item
