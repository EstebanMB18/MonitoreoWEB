from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

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
    Migra una base local antigua del repositorio
    al directorio de datos del usuario.

    Nunca sobrescribe una base nueva existente.
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
    _ensure_db_location()

    conn = sqlite3.connect(
        DB_PATH,
        check_same_thread=False,
    )

    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                monitor TEXT NOT NULL,
                run_type TEXT NOT NULL,
                cut TEXT,
                reason TEXT,

                window_mode TEXT,
                execution_date TEXT,
                data_date TEXT,
                window_start TEXT,
                window_end TEXT,

                status TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,

                official INTEGER NOT NULL DEFAULT 0,
                historical INTEGER NOT NULL DEFAULT 0,
                publish_allowed INTEGER NOT NULL DEFAULT 0,

                created_at TEXT,
                started_at TEXT,
                finished_at TEXT,
                duration_seconds REAL,
                records INTEGER,

                alerts_json TEXT,
                errors_json TEXT,
                outputs_json TEXT,
                metadata_json TEXT,
                details_json TEXT
            )
            """
        )

        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(runs)"
            ).fetchall()
        }

        if "details_json" not in columns:
            conn.execute(
                "ALTER TABLE runs "
                "ADD COLUMN details_json TEXT"
            )

        window_columns = {
            "window_mode": "TEXT",
            "execution_date": "TEXT",
            "data_date": "TEXT",
            "window_start": "TEXT",
            "window_end": "TEXT",
        }

        for column, sql_type in (
            window_columns.items()
        ):
            if column not in columns:
                conn.execute(
                    f"ALTER TABLE runs "
                    f"ADD COLUMN {column} "
                    f"{sql_type}"
                )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                display_name TEXT,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                mfa_enabled INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_login_at TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_users_email
            ON users(email)
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT,
                FOREIGN KEY(user_id)
                    REFERENCES users(user_id)
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_auth_sessions_user
            ON auth_sessions(user_id)
            """
        )


        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_closures (
                monitor TEXT NOT NULL,
                closure_date TEXT NOT NULL,

                coverage_status TEXT NOT NULL,
                overall_status TEXT NOT NULL,

                official_runs INTEGER NOT NULL DEFAULT 0,
                successful_runs INTEGER NOT NULL DEFAULT 0,

                total_records INTEGER NOT NULL DEFAULT 0,
                alerts_count INTEGER NOT NULL DEFAULT 0,
                errors_count INTEGER NOT NULL DEFAULT 0,

                first_run_at TEXT,
                last_run_at TEXT,

                snapshot_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                PRIMARY KEY (
                    monitor,
                    closure_date
                )
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_daily_closures_date
            ON daily_closures (
                closure_date
            )
            """
        )

        conn.commit()


def save_run(run: dict[str, Any]) -> None:
    init_db()

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO runs (
                run_id,
                monitor,
                run_type,
                cut,
                reason,
                window_mode,
                execution_date,
                data_date,
                window_start,
                window_end,
                status,
                progress,
                official,
                historical,
                publish_allowed,
                created_at,
                started_at,
                finished_at,
                duration_seconds,
                records,
                alerts_json,
                errors_json,
                outputs_json,
                metadata_json,
                details_json
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?
            )
            ON CONFLICT(run_id)
            DO UPDATE SET
                window_mode=
                    excluded.window_mode,
                execution_date=
                    excluded.execution_date,
                data_date=
                    excluded.data_date,
                window_start=
                    excluded.window_start,
                window_end=
                    excluded.window_end,
                status=excluded.status,
                progress=excluded.progress,
                started_at=excluded.started_at,
                finished_at=excluded.finished_at,
                duration_seconds=excluded.duration_seconds,
                records=excluded.records,
                alerts_json=excluded.alerts_json,
                errors_json=excluded.errors_json,
                outputs_json=excluded.outputs_json,
                metadata_json=excluded.metadata_json,
                details_json=excluded.details_json
            """,
            (
                run.get("run_id"),
                run.get("monitor"),
                run.get("run_type"),
                run.get("cut"),
                run.get("reason"),
                run.get("window_mode"),
                run.get("execution_date"),
                run.get("data_date"),
                run.get("window_start"),
                run.get("window_end"),
                run.get("status"),
                run.get("progress", 0),
                int(bool(run.get("official"))),
                int(bool(run.get("historical"))),
                int(bool(run.get("publish_allowed"))),
                run.get("created_at"),
                run.get("started_at"),
                run.get("finished_at"),
                run.get("duration_seconds"),
                run.get("records"),
                json.dumps(
                    run.get("alerts", []),
                    ensure_ascii=False,
                ),
                json.dumps(
                    run.get("errors", []),
                    ensure_ascii=False,
                ),
                json.dumps(
                    run.get("outputs", {}),
                    ensure_ascii=False,
                ),
                json.dumps(
                    run.get("metadata", {}),
                    ensure_ascii=False,
                ),
                json.dumps(
                    run.get("details", {}),
                    ensure_ascii=False,
                ),
            ),
        )

        conn.commit()


def list_saved_runs() -> list[dict[str, Any]]:
    init_db()

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM runs
            ORDER BY created_at DESC
            """
        ).fetchall()

    items = []

    for row in rows:
        item = dict(row)

        item["official"] = bool(
            item["official"]
        )
        item["historical"] = bool(
            item["historical"]
        )
        item["publish_allowed"] = bool(
            item["publish_allowed"]
        )

        item["alerts"] = json.loads(
            item.pop("alerts_json") or "[]"
        )
        item["errors"] = json.loads(
            item.pop("errors_json") or "[]"
        )
        item["outputs"] = json.loads(
            item.pop("outputs_json") or "{}"
        )
        item["metadata"] = json.loads(
            item.pop("metadata_json") or "{}"
        )
        item["details"] = json.loads(
            item.pop("details_json", None) or "{}"
        )

        items.append(item)

    return items


def save_daily_closure(
    closure: dict[str, Any],
) -> None:
    init_db()

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO daily_closures (
                monitor,
                closure_date,
                coverage_status,
                overall_status,
                official_runs,
                successful_runs,
                total_records,
                alerts_count,
                errors_count,
                first_run_at,
                last_run_at,
                snapshot_json,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(
                monitor,
                closure_date
            )
            DO UPDATE SET
                coverage_status=excluded.coverage_status,
                overall_status=excluded.overall_status,
                official_runs=excluded.official_runs,
                successful_runs=excluded.successful_runs,
                total_records=excluded.total_records,
                alerts_count=excluded.alerts_count,
                errors_count=excluded.errors_count,
                first_run_at=excluded.first_run_at,
                last_run_at=excluded.last_run_at,
                snapshot_json=excluded.snapshot_json,
                updated_at=excluded.updated_at
            """,
            (
                closure["monitor"],
                closure["closure_date"],
                closure["coverage_status"],
                closure["overall_status"],
                closure["official_runs"],
                closure["successful_runs"],
                closure["total_records"],
                closure["alerts_count"],
                closure["errors_count"],
                closure.get("first_run_at"),
                closure.get("last_run_at"),
                json.dumps(
                    closure.get("snapshot", {}),
                    ensure_ascii=False,
                ),
                closure["created_at"],
                closure["updated_at"],
            ),
        )

        conn.commit()


def get_daily_closure(
    monitor: str,
    closure_date: str,
) -> dict[str, Any] | None:
    init_db()

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM daily_closures
            WHERE monitor = ?
              AND closure_date = ?
            """,
            (
                monitor.upper(),
                closure_date,
            ),
        ).fetchone()

    if row is None:
        return None

    item = dict(row)

    item["snapshot"] = json.loads(
        item.pop("snapshot_json") or "{}"
    )

    return item


def list_daily_closures(
    *,
    monitor: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    init_db()

    clauses = []
    params: list[Any] = []

    if monitor:
        clauses.append("monitor = ?")
        params.append(monitor.upper())

    if start_date:
        clauses.append("closure_date >= ?")
        params.append(start_date)

    if end_date:
        clauses.append("closure_date <= ?")
        params.append(end_date)

    where = ""

    if clauses:
        where = (
            " WHERE "
            + " AND ".join(clauses)
        )

    sql = (
        "SELECT * "
        "FROM daily_closures"
        + where
        + " ORDER BY closure_date DESC, monitor ASC"
    )

    with get_connection() as conn:
        rows = conn.execute(
            sql,
            params,
        ).fetchall()

    items = []

    for row in rows:
        item = dict(row)

        item["snapshot"] = json.loads(
            item.pop("snapshot_json") or "{}"
        )

        items.append(item)

    return items



def get_latest_daily_closure(
    monitor: str,
) -> dict[str, Any] | None:
    init_db()

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM daily_closures
            WHERE monitor = ?
            ORDER BY closure_date DESC
            LIMIT 1
            """,
            (monitor.upper(),),
        ).fetchone()

    if row is None:
        return None

    item = dict(row)

    item["snapshot"] = json.loads(
        item.pop("snapshot_json") or "{}"
    )

    return item
