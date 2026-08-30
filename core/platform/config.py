from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from core.platform.base import InstallationMode
from core.platform.paths import (
    ensure_user_directories,
)


DEFAULT_CONFIG = {
    "schema_version": 1,
    "installation_mode": InstallationMode.USER.value,
    "theme": "AUTO",
    "start_minimized": False,
    "output_directory": None,
    "history_directory": None,
    "export_directory": None,
}


class ConfigManager:
    def __init__(
        self,
        path: Path | None = None,
    ):
        paths = ensure_user_directories()

        self.path = (
            path
            or paths["config"] / "settings.json"
        )

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            config = deepcopy(
                DEFAULT_CONFIG
            )

            config["output_directory"] = str(
                ensure_user_directories()[
                    "default_output"
                ]
            )

            self.save(config)

            return config

        try:
            raw = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            raise RuntimeError(
                "La configuracion local "
                "no es valida."
            )

        config = deepcopy(
            DEFAULT_CONFIG
        )

        config.update(raw)

        return config

    def save(
        self,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = deepcopy(
            DEFAULT_CONFIG
        )

        normalized.update(config)

        mode = normalized.get(
            "installation_mode"
        )

        if mode not in {
            InstallationMode.USER.value,
            InstallationMode.DEVELOPMENT.value,
        }:
            raise ValueError(
                "installation_mode invalido."
            )

        for key in (
            "output_directory",
            "history_directory",
            "export_directory",
        ):
            value = normalized.get(key)

            if value:
                path = Path(value).expanduser()

                path.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                normalized[key] = str(
                    path.resolve()
                )

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        tmp = self.path.with_suffix(
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

        tmp.replace(
            self.path
        )

        return normalized

    def update(
        self,
        values: dict[str, Any],
    ) -> dict[str, Any]:
        config = self.load()

        config.update(values)

        return self.save(
            config
        )


config_manager = ConfigManager()
