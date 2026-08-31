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

from core.execution_window import (
    resolve_monitor_execution_window,
)

from core.platform import config_manager


router = APIRouter()

ROOT = Path(__file__).resolve().parents[2]

STATIC_OUTPUT_ROOTS = [
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


def _allowed_output_roots() -> list[Path]:
    roots = list(STATIC_OUTPUT_ROOTS)

    try:
        config = config_manager.load()

        configured = str(
            config.get("output_directory")
            or ""
        ).strip()

        if configured:
            root = (
                Path(configured)
                .expanduser()
                .resolve()
            )

            if root not in roots:
                roots.append(root)

    except Exception:
        # Si settings no puede cargarse, se conservan
        # ?nicamente las rutas internas conocidas.
        pass

    return roots


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
        for root in _allowed_output_roots()
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

    window_mode: str = "TODAY_TO_NOW"

    data_date: str | None = None
    cut: str | None = None

    window_start: str | None = None
    window_end: str | None = None

    last_n_hours: int | None = None

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

    run_type = payload.run_type.value

    role = str(
        user.get("role")
        or ""
    ).upper()

    if (
        run_type == "OFFICIAL"
        and role not in {
            "ADMIN",
            "MONITOR_OFICIAL",
        }
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Solo ADMIN o MONITOR_OFICIAL "
                "pueden ejecutar cortes OFFICIAL."
            ),
        )

    if (
        run_type == "OFFICIAL"
        and str(
            payload.window_mode
            or ""
        ).upper() != "CUT"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Una ejecucion OFFICIAL "
                "debe usar window_mode=CUT."
            ),
        )

    if key not in MONITOR_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail="Monitor no encontrado.",
        )

    try:
        resolved = (
            resolve_monitor_execution_window(
                monitor=key,
                mode=payload.window_mode,
                data_date=payload.data_date,
                cut=payload.cut,
                window_start=
                    payload.window_start,
                window_end=
                    payload.window_end,
                last_n_hours=
                    payload.last_n_hours,
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return create_run(
        monitor_id=key,
        run_type=run_type,
        cut=resolved.cut,
        reason=payload.reason,
        execution_window=
            resolved.to_dict(),
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

