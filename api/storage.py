from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "storage"
    / "db"
    / "monitoreo.db"
)


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT(run_id)
            DO UPDATE SET
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
