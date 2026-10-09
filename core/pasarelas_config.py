from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from core.platform.paths import ensure_user_directories


DEFAULT_PASARELAS_CONFIG = {
    "schema_version": 1,
    "vertical_41621_source_mode": "PAYU",
}


def _config_path() -> Path:
    paths = ensure_user_directories()

    return (
        Path(paths["config"])
        / "pasarelas.json"
    )


def load_pasarelas_config() -> dict[str, Any]:
    path = _config_path()

    if not path.exists():
        return save_pasarelas_config(
            DEFAULT_PASARELAS_CONFIG
        )

    try:
        raw = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        raise RuntimeError(
            "La configuracion de Pasarelas no es valida."
        ) from exc

    config = deepcopy(
        DEFAULT_PASARELAS_CONFIG
    )

    config.update(raw)

    return _validate_config(config)


def _validate_config(
    config: dict[str, Any],
) -> dict[str, Any]:
    normalized = deepcopy(
        DEFAULT_PASARELAS_CONFIG
    )

    normalized.update(config)

    mode = str(
        normalized.get(
            "vertical_41621_source_mode",
            "PAYU",
        )
    ).strip().upper()

    if mode not in {
        "PAYU",
        "ECOLLECT",
    }:
        raise ValueError(
            "vertical_41621_source_mode invalido. "
            "Use PAYU o ECOLLECT."
        )

    normalized[
        "vertical_41621_source_mode"
    ] = mode

    return normalized


def save_pasarelas_config(
    config: dict[str, Any],
) -> dict[str, Any]:
    normalized = _validate_config(
        config
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
            normalized,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    tmp.replace(path)

    return normalized


def update_pasarelas_config(
    values: dict[str, Any],
) -> dict[str, Any]:
    config = load_pasarelas_config()

    config.update(values)

    return save_pasarelas_config(
        config
    )
