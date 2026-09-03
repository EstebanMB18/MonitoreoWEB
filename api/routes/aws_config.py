from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from pydantic import BaseModel, Field

from api.auth_dependencies import require_roles
from core.aws_monitor_config import (
    find_aws_service,
    load_aws_monitor_config,
    save_aws_monitor_config,
)


router = APIRouter()


class AWSQueryConfig(BaseModel):
    id: str
    nombre: str
    tipo: str = Field(
        pattern="^(COUNT|DETAIL)$"
    )
    query: str
    activo: bool = True


class AWSServiceConfig(BaseModel):
    id: str
    nombre: str
    activo: bool = True
    profile: str
    log_group: str
    queries: list[AWSQueryConfig] = []
    thresholds: dict[str, Any] = {}


class AWSConfigUpdate(BaseModel):
    region: str | None = None


def _normalize_service(
    service: AWSServiceConfig,
) -> dict[str, Any]:
    payload = service.model_dump()

    payload["id"] = (
        payload["id"]
        .strip()
        .lower()
    )

    payload["nombre"] = (
        payload["nombre"]
        .strip()
    )

    payload["profile"] = (
        payload["profile"]
        .strip()
    )

    payload["log_group"] = (
        payload["log_group"]
        .strip()
    )

    for query in payload["queries"]:
        query["id"] = (
            str(query["id"])
            .strip()
            .lower()
        )

        query["tipo"] = (
            str(query["tipo"])
            .strip()
            .upper()
        )

        query["nombre"] = (
            str(query["nombre"])
            .strip()
        )

        query["query"] = (
            str(query["query"])
            .strip()
        )

        if not query["query"]:
            raise HTTPException(
                status_code=400,
                detail=(
                    "La consulta AWS "
                    "no puede estar vacía."
                ),
            )

    if not payload["id"]:
        raise HTTPException(
            status_code=400,
            detail="service id requerido.",
        )

    if not payload["profile"]:
        raise HTTPException(
            status_code=400,
            detail="profile requerido.",
        )

    if not payload["log_group"]:
        raise HTTPException(
            status_code=400,
            detail="log_group requerido.",
        )

    query_ids = [
        q["id"]
        for q
        in payload["queries"]
    ]

    if len(query_ids) != len(
        set(query_ids)
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "No puede haber queries "
                "AWS duplicadas."
            ),
        )

    return payload


@router.get(
    "/monitors/aws/config"
)
def get_aws_config(
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
            "OPERADOR",
            "CONSULTA",
        )
    ),
):
    return load_aws_monitor_config()


@router.put(
    "/monitors/aws/config"
)
def update_aws_config(
    payload: AWSConfigUpdate,
    user: dict = Depends(
        require_roles("ADMIN")
    ),
):
    config = load_aws_monitor_config()

    values = payload.model_dump(
        exclude_none=True
    )

    if "region" in values:
        region = str(
            values["region"]
        ).strip()

        if not region:
            raise HTTPException(
                status_code=400,
                detail="region requerida.",
            )

        config["region"] = region

    return save_aws_monitor_config(
        config
    )


@router.get(
    "/monitors/aws/services"
)
def list_aws_services(
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
            "OPERADOR",
            "CONSULTA",
        )
    ),
):
    config = load_aws_monitor_config()

    return {
        "items": config["services"],
        "total": len(
            config["services"]
        ),
    }


@router.post(
    "/monitors/aws/services"
)
def create_aws_service(
    payload: AWSServiceConfig,
    user: dict = Depends(
        require_roles("ADMIN")
    ),
):
    service = _normalize_service(
        payload
    )

    if find_aws_service(
        service["id"]
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "El servicio AWS "
                "ya existe."
            ),
        )

    config = load_aws_monitor_config()

    config["services"].append(
        service
    )

    save_aws_monitor_config(
        config
    )

    return service


@router.put(
    "/monitors/aws/services/{service_id}"
)
def update_aws_service(
    service_id: str,
    payload: AWSServiceConfig,
    user: dict = Depends(
        require_roles("ADMIN")
    ),
):
    service = _normalize_service(
        payload
    )

    config = load_aws_monitor_config()

    key = service_id.strip().lower()

    found = False

    for index, current in enumerate(
        config["services"]
    ):
        if str(
            current.get("id")
            or ""
        ).strip().lower() != key:
            continue

        config["services"][index] = (
            service
        )

        found = True
        break

    if not found:
        raise HTTPException(
            status_code=404,
            detail=(
                "Servicio AWS "
                "no encontrado."
            ),
        )

    save_aws_monitor_config(
        config
    )

    return service


@router.delete(
    "/monitors/aws/services/{service_id}"
)
def delete_aws_service(
    service_id: str,
    user: dict = Depends(
        require_roles("ADMIN")
    ),
):
    config = load_aws_monitor_config()

    key = service_id.strip().lower()

    before = len(
        config["services"]
    )

    config["services"] = [
        service
        for service
        in config["services"]
        if str(
            service.get("id")
            or ""
        ).strip().lower() != key
    ]

    deleted = (
        len(config["services"])
        < before
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=(
                "Servicio AWS "
                "no encontrado."
            ),
        )

    save_aws_monitor_config(
        config
    )

    return {
        "service_id": key,
        "deleted": True,
    }
