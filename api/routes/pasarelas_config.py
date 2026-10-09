from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth_dependencies import require_roles
from core.pasarelas_config import (
    load_pasarelas_config,
    update_pasarelas_config,
)


router = APIRouter()


class PasarelasConfigUpdate(BaseModel):
    vertical_41621_source_mode: str


@router.get("/monitors/pasarelas/config")
def get_pasarelas_config(
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
            "OPERADOR",
            "CONSULTA",
        )
    ),
):
    return load_pasarelas_config()


@router.put("/monitors/pasarelas/config")
def update_pasarelas_config_route(
    payload: PasarelasConfigUpdate,
    user: dict = Depends(
        require_roles("ADMIN")
    ),
):
    mode = (
        payload.vertical_41621_source_mode
        or ""
    ).strip().upper()

    try:
        return update_pasarelas_config(
            {
                "vertical_41621_source_mode":
                    mode,
            }
        )
    except (
        ValueError,
        OSError,
        RuntimeError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )
