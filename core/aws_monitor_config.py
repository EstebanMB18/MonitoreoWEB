from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from core.platform import ensure_user_directories


DEFAULT_AWS_MONITOR_CONFIG: dict[str, Any] = {
    "schema_version": 1,
    "seed_version": 0,
    "region": "us-east-1",
    "services": [],
}


def _config_path() -> Path:
    paths = ensure_user_directories()

    target = (
        Path(paths["config"])
        / "monitors"
        / "aws.json"
    )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    return target


def load_aws_monitor_config() -> dict[str, Any]:
    path = _config_path()

    if not path.exists():
        config = deepcopy(
            DEFAULT_AWS_MONITOR_CONFIG
        )

        save_aws_monitor_config(
            config
        )

        return config

    try:
        raw = json.loads(
            path.read_text(
                encoding="utf-8-sig"
            )
        )
    except Exception as exc:
        raise RuntimeError(
            "La configuración dinámica AWS "
            "no es válida."
        ) from exc

    if not isinstance(raw, dict):
        raise RuntimeError(
            "La configuración dinámica AWS "
            "debe ser un objeto JSON."
        )

    config = deepcopy(
        DEFAULT_AWS_MONITOR_CONFIG
    )

    config.update(raw)

    if not isinstance(
        config.get("services"),
        list,
    ):
        raise RuntimeError(
            "AWS services debe ser una lista."
        )

    return config


def save_aws_monitor_config(
    config: dict[str, Any],
) -> dict[str, Any]:
    path = _config_path()

    normalized = deepcopy(
        DEFAULT_AWS_MONITOR_CONFIG
    )

    normalized.update(config)

    services = normalized.get(
        "services",
        [],
    )

    if not isinstance(services, list):
        raise ValueError(
            "services debe ser una lista."
        )

    path.write_text(
        json.dumps(
            normalized,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return normalized


def find_aws_service(
    service_id: str,
) -> dict[str, Any] | None:
    config = load_aws_monitor_config()

    key = service_id.strip().lower()

    for service in config["services"]:
        if not isinstance(service, dict):
            continue

        if str(
            service.get("id")
            or ""
        ).strip().lower() == key:
            return service

    return None



def ensure_aws_monitor_config_seeded() -> dict[str, Any]:
    """Aplica una sola vez la semilla legacy de AWS.

    Reglas:
    - Si seed_version >= 1, no hace nada.
    - Si ya existen servicios, los conserva exactamente.
    - Si services est? vac?o, carga la semilla legacy.
    - Nunca reemplaza region personalizada.
    """
    from core.aws_monitor_seed import (
        LEGACY_AWS_MONITOR_SEED,
    )

    config = load_aws_monitor_config()

    try:
        seed_version = int(
            config.get("seed_version", 0)
            or 0
        )
    except (TypeError, ValueError):
        seed_version = 0

    if seed_version >= 1:
        return config

    current_services = config.get(
        "services",
        [],
    )

    if not current_services:
        config["services"] = deepcopy(
            LEGACY_AWS_MONITOR_SEED[
                "services"
            ]
        )

        if not str(
            config.get("region")
            or ""
        ).strip():
            config["region"] = (
                LEGACY_AWS_MONITOR_SEED[
                    "region"
                ]
            )

    config["seed_version"] = 1

    return save_aws_monitor_config(
        config
    )
