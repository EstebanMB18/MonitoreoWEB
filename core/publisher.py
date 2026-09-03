from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

from core.platform import ensure_user_directories


DEFAULT_PUBLISHER_CONFIG: dict[str, Any] = {
    "schema_version": 1,
    "enabled": False,
    "provider": "LOCAL_SYNC",
    "destinations": {
        "AWS": None,
        "PASARELAS": None,
        "HERCULES": None,
        "GENERAL": None,
    },
    "allowed_outputs": [
        "dashboard",
        "excel",
    ],
}


def _config_path() -> Path:
    paths = ensure_user_directories()

    return (
        Path(paths["config"])
        / "publisher.json"
    )


def load_publisher_config() -> dict[str, Any]:
    path = _config_path()

    if not path.exists():
        cfg = deepcopy(
            DEFAULT_PUBLISHER_CONFIG
        )

        save_publisher_config(cfg)

        return cfg

    try:
        raw = json.loads(
            path.read_text(
                encoding="utf-8-sig"
            )
        )
    except Exception as exc:
        raise RuntimeError(
            "La configuracion del publisher "
            "no es valida."
        ) from exc

    if not isinstance(raw, dict):
        raise RuntimeError(
            "publisher.json debe ser "
            "un objeto JSON."
        )

    cfg = deepcopy(
        DEFAULT_PUBLISHER_CONFIG
    )

    destinations = raw.get(
        "destinations"
    )

    cfg.update(
        {
            key: value
            for key, value in raw.items()
            if key != "destinations"
        }
    )

    if destinations is not None:
        if not isinstance(
            destinations,
            dict,
        ):
            raise RuntimeError(
                "publisher.destinations "
                "debe ser un objeto."
            )

        cfg[
            "destinations"
        ].update(
            destinations
        )

    return cfg


def save_publisher_config(
    config: dict[str, Any],
) -> dict[str, Any]:
    cfg = deepcopy(
        DEFAULT_PUBLISHER_CONFIG
    )

    cfg.update(config)

    destinations = cfg.get(
        "destinations"
    )

    if not isinstance(
        destinations,
        dict,
    ):
        raise ValueError(
            "destinations debe ser "
            "un objeto."
        )

    normalized_destinations = {}

    for monitor in (
        "AWS",
        "PASARELAS",
        "HERCULES",
        "GENERAL",
    ):
        value = destinations.get(
            monitor
        )

        normalized_destinations[
            monitor
        ] = (
            str(
                Path(value)
                .expanduser()
            )
            if value
            else None
        )

    cfg[
        "destinations"
    ] = normalized_destinations

    allowed = cfg.get(
        "allowed_outputs"
    )

    if not isinstance(
        allowed,
        list,
    ):
        raise ValueError(
            "allowed_outputs debe ser "
            "una lista."
        )

    allowed = [
        str(item).lower()
        for item in allowed
        if str(item).lower()
        in {
            "dashboard",
            "excel",
        }
    ]

    cfg[
        "allowed_outputs"
    ] = sorted(
        set(allowed)
    )

    path = _config_path()

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = path.with_suffix(
        ".tmp"
    )

    tmp.write_text(
        json.dumps(
            cfg,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    tmp.replace(path)

    return cfg


def publication_eligibility(
    run: dict[str, Any],
) -> tuple[bool, str]:

    run_type = str(
        run.get("run_type")
        or ""
    ).upper()

    if run_type != "OFFICIAL":
        return (
            False,
            "Solo ejecuciones OFFICIAL "
            "pueden publicarse.",
        )

    if not bool(
        run.get("official")
    ):
        return (
            False,
            "La ejecucion no esta marcada "
            "como oficial.",
        )

    if not bool(
        run.get("publish_allowed")
    ):
        return (
            False,
            "publish_allowed esta "
            "deshabilitado.",
        )

    monitor = str(
        run.get("monitor")
        or ""
    ).upper()

    if monitor not in {
        "AWS",
        "PASARELAS",
        "HERCULES",
        "GENERAL",
    }:
        return (
            False,
            "Monitor no publicable.",
        )

    status = str(
        run.get("status")
        or ""
    ).upper()

    if status not in {
        "OK",
        "WARNING",
        "NO_DATA",
    }:
        return (
            False,
            "El estado de la ejecucion "
            "no permite publicacion.",
        )

    return True, "OK"


def publish_run(
    run: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:

    cfg = (
        config
        or load_publisher_config()
    )

    if not cfg.get(
        "enabled",
        False,
    ):
        return {
            "published": False,
            "reason":
                "Publisher deshabilitado.",
            "files": [],
        }

    eligible, reason = (
        publication_eligibility(
            run
        )
    )

    if not eligible:
        return {
            "published": False,
            "reason": reason,
            "files": [],
        }

    monitor = str(
        run["monitor"]
    ).upper()

    raw_destination = (
        cfg.get(
            "destinations",
            {}
        ).get(
            monitor
        )
    )

    if not raw_destination:
        return {
            "published": False,
            "reason": (
                f"Destino no configurado "
                f"para {monitor}."
            ),
            "files": [],
        }

    destination = Path(
        raw_destination
    ).expanduser()

    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    outputs = (
        run.get("outputs")
        or {}
    )

    allowed_outputs = set(
        cfg.get(
            "allowed_outputs"
        )
        or []
    )

    published_files = []

    for output_id in (
        "dashboard",
        "excel",
    ):
        if (
            output_id
            not in allowed_outputs
        ):
            continue

        raw_source = outputs.get(
            output_id
        )

        if not raw_source:
            continue

        source = Path(
            raw_source
        ).expanduser()

        if (
            not source.exists()
            or not source.is_file()
        ):
            continue

        # Nunca publicar temporales.
        name_lower = (
            source.name.lower()
        )

        if (
            name_lower.startswith(".")
            or ".tmp" in name_lower
            or name_lower.endswith(
                ".tmp"
            )
        ):
            continue

        target = (
            destination
            / source.name
        )

        shutil.copy2(
            source,
            target,
        )

        published_files.append({
            "output_id": output_id,
            "source": str(
                source.resolve()
            ),
            "destination": str(
                target.resolve()
            ),
        })

    if not published_files:
        return {
            "published": False,
            "reason": (
                "No hay outputs finales "
                "publicables."
            ),
            "files": [],
        }

    return {
        "published": True,
        "reason": "OK",
        "files": published_files,
    }
