from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth_dependencies import require_roles

from core.platform import (
    InstallationMode,
    config_manager,
    ensure_user_directories,
    get_platform_name,
    get_secret_store,
    get_user_data_dir,
)


router = APIRouter()


SECRET_PROVIDERS = {
    "AWS",
    "ECOLLECT",
    "PAYU",
    "HERCULES",
}


class SettingsUpdate(BaseModel):
    installation_mode: InstallationMode | None = None
    theme: str | None = None
    start_minimized: bool | None = None
    output_directory: str | None = None
    history_directory: str | None = None
    export_directory: str | None = None


class SecretUpdate(BaseModel):
    values: dict[str, str]


def _provider(value: str) -> str:
    provider = value.upper()

    if provider not in SECRET_PROVIDERS:
        raise HTTPException(
            status_code=404,
            detail="Proveedor no soportado.",
        )

    return provider


def _settings_payload(
    *,
    include_paths: bool = False,
) -> dict[str, Any]:
    config = config_manager.load()

    if include_paths:
        visible_config = config
    else:
        visible_config = {
            key: config.get(key)
            for key in (
                "schema_version",
                "installation_mode",
                "theme",
                "start_minimized",
            )
        }

    system = {
        "platform": get_platform_name(),
    }

    if include_paths:
        paths = ensure_user_directories()

        system.update(
            {
                "user_data_directory": str(
                    get_user_data_dir()
                ),
                "config_directory": str(
                    paths["config"]
                ),
                "logs_directory": str(
                    paths["logs"]
                ),
                "database_directory": str(
                    paths["db"]
                ),
            }
        )

    return {
        "config": visible_config,
        "system": system,
        "secret_providers": sorted(
            SECRET_PROVIDERS
        ),
    }


@router.get("/settings")
def get_settings(
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
            "OPERADOR",
            "CONSULTA",
        )
    ),
):
    role = str(
        user.get("role")
        or ""
    ).upper()

    return _settings_payload(
        include_paths=(
            role == "ADMIN"
        )
    )


@router.put("/settings")
def update_settings(
    payload: SettingsUpdate,
    user: dict = Depends(
        require_roles("ADMIN")
    ),
):
    values = payload.model_dump(
        exclude_unset=True
    )

    if (
        "installation_mode" in values
        and values["installation_mode"]
        is not None
    ):
        values["installation_mode"] = (
            values["installation_mode"].value
        )

    if "theme" in values:
        theme = (
            values["theme"] or ""
        ).upper()

        if theme not in {
            "AUTO",
            "LIGHT",
            "DARK",
        }:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Tema invalido. "
                    "Use AUTO, LIGHT o DARK."
                ),
            )

        values["theme"] = theme

    try:
        config_manager.update(
            values
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

    return _settings_payload(
        include_paths=True
    )


@router.get("/secrets/status")
def secrets_status(
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
            "OPERADOR",
            "CONSULTA",
        )
    ),
):
    store = get_secret_store()

    return {
        "items": [
            store.status(provider)
            for provider
            in sorted(SECRET_PROVIDERS)
        ],
        "total": len(
            SECRET_PROVIDERS
        ),
    }


@router.get(
    "/secrets/{provider}/status"
)
def secret_status(
    provider: str,
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
            "OPERADOR",
            "CONSULTA",
        )
    ),
):
    provider = _provider(
        provider
    )

    store = get_secret_store()

    return store.status(
        provider
    )


@router.put("/secrets/{provider}")
def update_secret(
    provider: str,
    payload: SecretUpdate,
    user: dict = Depends(
        require_roles("ADMIN")
    ),
):
    provider = _provider(
        provider
    )

    clean_values = {
        str(key).strip(): str(value)
        for key, value
        in payload.values.items()
        if (
            str(key).strip()
            and str(value)
        )
    }

    if not clean_values:
        raise HTTPException(
            status_code=400,
            detail=(
                "Debe enviar al menos "
                "un valor de credencial."
            ),
        )

    serialized = json.dumps(
        clean_values,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    try:
        store = get_secret_store()

        store.set(
            provider,
            serialized,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "No fue posible guardar "
                "la credencial de forma segura."
            ),
        ) from exc

    return store.status(
        provider
    )


@router.delete("/secrets/{provider}")
def delete_secret(
    provider: str,
    user: dict = Depends(
        require_roles("ADMIN")
    ),
):
    provider = _provider(
        provider
    )

    store = get_secret_store()

    deleted = store.delete(
        provider
    )

    return {
        "provider": provider,
        "configured": False,
        "deleted": deleted,
    }
