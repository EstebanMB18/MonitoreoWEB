from __future__ import annotations

import os
import platform
from pathlib import Path


APP_NAME = "Nexus"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_platform_name() -> str:
    return platform.system().upper()


def get_user_data_dir() -> Path:
    system = get_platform_name()

    if system == "WINDOWS":
        base = Path(
            os.getenv(
                "LOCALAPPDATA",
                Path.home() / "AppData" / "Local",
            )
        )
        return base / APP_NAME

    if system == "LINUX":
        base = Path(
            os.getenv(
                "XDG_DATA_HOME",
                Path.home() / ".local" / "share",
            )
        )
        return base / APP_NAME.lower()

    return Path.home() / f".{APP_NAME.lower()}"


def ensure_user_directories() -> dict[str, Path]:
    root = get_user_data_dir()

    paths = {
        "root": root,
        "config": root / "config",
        "db": root / "db",
        "logs": root / "logs",
        "cache": root / "cache",
        "secrets": root / "secrets",
        "runtime": root / "runtime",
        "default_output": root / "outputs",
    }

    for path in paths.values():
        path.mkdir(
            parents=True,
            exist_ok=True,
        )

    return paths
