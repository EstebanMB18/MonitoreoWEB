from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from pydantic import BaseModel

from api.auth_dependencies import (
    require_roles,
)
from api.manual_batches import (
    create_manual_batch,
    get_manual_batch,
    list_manual_batches,
)


router = APIRouter()


class ManualBatchRequest(BaseModel):
    monitor: str
    start_date: str
    end_date: str
    reason: str | None = None


@router.post("/manual/batches")
def create_batch(
    payload: ManualBatchRequest,
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
            "OPERADOR",
        )
    ),
):
    requested_by = str(
        user.get("user_id")
        or user.get("email")
        or ""
    ) or None

    try:
        return create_manual_batch(
            monitor_id=payload.monitor,
            start_date=payload.start_date,
            end_date=payload.end_date,
            reason=payload.reason,
            requested_by=requested_by,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/manual/batches")
def batches(
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
            "OPERADOR",
            "CONSULTA",
        )
    ),
):
    items = list_manual_batches()

    return {
        "items": items,
        "total": len(items),
    }


@router.get(
    "/manual/batches/{batch_id}"
)
def batch_detail(
    batch_id: str,
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
            "OPERADOR",
            "CONSULTA",
        )
    ),
):
    item = get_manual_batch(
        batch_id
    )

    if item is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Consulta manual "
                "no encontrada."
            ),
        )

    return item
