from pathlib import Path
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api.auth_dependencies import require_roles

from api.runtime import (
    MONITOR_REGISTRY,
    create_run,
    get_run,
    list_runs,
)


router = APIRouter()

ROOT = Path(__file__).resolve().parents[2]

ALLOWED_OUTPUT_ROOTS = [
    (ROOT / "runtime" / "output").resolve(),
    (
        ROOT
        / "monitores"
        / "pasarelas"
        / "data"
        / "salida"
    ).resolve(),
    (
        ROOT
        / "monitores"
        / "hercules"
        / "reports"
    ).resolve(),
]


def _resolve_safe_output(
    run_id: str,
    output_id: str,
) -> Path:
    item = get_run(run_id)

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Ejecucion no encontrada.",
        )

    if output_id not in {"dashboard", "excel"}:
        raise HTTPException(
            status_code=404,
            detail="Output no permitido.",
        )

    outputs = item.get("outputs") or {}
    raw_path = outputs.get(output_id)

    if not raw_path:
        raise HTTPException(
            status_code=404,
            detail="Output no disponible.",
        )

    try:
        target = Path(raw_path).resolve()
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Ruta de output invalida.",
        )

    allowed = any(
        target == root
        or root in target.parents
        for root in ALLOWED_OUTPUT_ROOTS
    )

    if not allowed:
        raise HTTPException(
            status_code=403,
            detail="Output fuera de directorios permitidos.",
        )

    if not target.is_file():
        raise HTTPException(
            status_code=404,
            detail="Archivo de output no encontrado.",
        )

    return target


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
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
            "OPERADOR",
        )
    ),
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

@router.get("/runs/{run_id}/outputs/{output_id}")
def run_output(
    run_id: str,
    output_id: str,
):
    target = _resolve_safe_output(
        run_id,
        output_id,
    )

    if output_id == "dashboard":
        return FileResponse(
            path=target,
            media_type="text/html",
        )

    return FileResponse(
        path=target,
        filename=target.name,
        media_type=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),
    )

