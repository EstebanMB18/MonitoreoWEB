from __future__ import annotations

import shutil
import sqlite3

from core.platform.paths import (
    PROJECT_ROOT,
    ensure_user_directories,
)


LEGACY_DB_PATH = (
    PROJECT_ROOT
    / "storage"
    / "db"
    / "monitoreo.db"
)

DB_PATH = (
    ensure_user_directories()["db"]
    / "monitoreo.db"
)


def _ensure_db_location() -> None:
    """
    Garantiza la ubicacion local de la base de datos RAMSS.

    Si existe una base antigua dentro del repositorio y todavia
    no existe la base de datos del usuario, la copia al directorio
    de datos local.

    Nunca sobrescribe una base existente.
    """

    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if DB_PATH.exists():
        return

    if (
        LEGACY_DB_PATH.exists()
        and LEGACY_DB_PATH.is_file()
    ):
        shutil.copy2(
            LEGACY_DB_PATH,
            DB_PATH,
        )


def get_connection() -> sqlite3.Connection:
    """
    Punto unico de acceso fisico a SQLite para RAMSS.

    Las capas superiores no deben abrir conexiones SQLite
    directamente. Esto permitira incorporar PostgreSQL para
    una futura instalacion centralizada en servidor.
    """

    _ensure_db_location()

    conn = sqlite3.connect(
        DB_PATH,
        check_same_thread=False,
    )

    conn.row_factory = sqlite3.Row

    conn.execute(
        "PRAGMA foreign_keys = ON"
    )

    return conn
