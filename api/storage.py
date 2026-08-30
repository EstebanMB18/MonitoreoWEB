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
                metadata_json TEXT
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
                metadata_json
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?
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
                metadata_json=excluded.metadata_json
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

        items.append(item)

    return items
