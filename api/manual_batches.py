from __future__ import annotations

import threading
import time
from datetime import date, datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from api.runtime import (
    MONITOR_REGISTRY,
    create_run,
    get_run,
)
from api.storage import (
    get_run_batch,
    list_run_batches,
    list_runs_by_batch,
    save_run,
    save_run_batch,
)
from core.execution_window import (
    DEFAULT_TIMEZONE,
    resolve_monitor_execution_window,
)


MAX_MANUAL_RANGE_DAYS = 31

TERMINAL_STATUSES = {
    "OK",
    "WARNING",
    "ERROR",
    "TIMEOUT",
    "CANCELLED",
    "NO_DATA",
    "STALE",
}

FAILED_STATUSES = {
    "ERROR",
    "TIMEOUT",
    "CANCELLED",
}


def _parse_date(
    value: str,
    *,
    field: str,
) -> date:
    try:
        return date.fromisoformat(value)
    except Exception as exc:
        raise ValueError(
            f"{field} debe usar YYYY-MM-DD."
        ) from exc


def _date_range(
    start: date,
    end: date,
) -> list[date]:
    total = (
        end - start
    ).days + 1

    return [
        start + timedelta(days=index)
        for index in range(total)
    ]


def create_manual_batch(
    *,
    monitor_id: str,
    start_date: str,
    end_date: str,
    reason: str | None,
    requested_by: str | None,
) -> dict[str, Any]:

    monitor = str(
        monitor_id
    ).lower().strip()

    if monitor not in MONITOR_REGISTRY:
        raise ValueError(
            "Monitor invalido."
        )

    start = _parse_date(
        start_date,
        field="start_date",
    )

    end = _parse_date(
        end_date,
        field="end_date",
    )

    if end < start:
        raise ValueError(
            "end_date no puede ser anterior "
            "a start_date."
        )

    days = (
        end - start
    ).days + 1

    if days > MAX_MANUAL_RANGE_DAYS:
        raise ValueError(
            "El rango manual no puede superar "
            f"{MAX_MANUAL_RANGE_DAYS} dias."
        )

    tz = ZoneInfo(
        DEFAULT_TIMEZONE
    )

    today = datetime.now(
        tz
    ).date()

    if end > today:
        raise ValueError(
            "No se permiten fechas futuras."
        )

    batch_id = str(
        uuid4()
    )

    item = {
        "batch_id": batch_id,
        "batch_type": "MANUAL",
        "monitor": monitor.upper(),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "reason": reason,
        "status": "PENDING",
        "progress": 0,
        "total_days": days,
        "completed_days": 0,
        "failed_days": 0,
        "requested_by": requested_by,
        "created_at": datetime.now(
            tz
        ).isoformat(),
        "started_at": None,
        "finished_at": None,
        "metadata": {
            "execution_mode": "SEQUENTIAL_DATE",
            "max_days": MAX_MANUAL_RANGE_DAYS,
            "current_date": None,
            "errors": [],
        },
    }

    save_run_batch(item)

    thread = threading.Thread(
        target=_execute_manual_batch,
        args=(batch_id,),
        daemon=True,
        name=(
            "manual-batch-"
            + batch_id[:8]
        ),
    )

    thread.start()

    return get_manual_batch(
        batch_id
    )


def _execute_manual_batch(
    batch_id: str,
) -> None:

    batch = get_run_batch(
        batch_id
    )

    if batch is None:
        return

    tz = ZoneInfo(
        DEFAULT_TIMEZONE
    )

    started = datetime.now(
        tz
    )

    batch["status"] = "RUNNING"
    batch["started_at"] = (
        started.isoformat()
    )

    save_run_batch(batch)

    start = date.fromisoformat(
        batch["start_date"]
    )

    end = date.fromisoformat(
        batch["end_date"]
    )

    dates = _date_range(
        start,
        end,
    )

    completed = 0
    failed = 0

    for target in dates:

        batch = get_run_batch(
            batch_id
        )

        if batch is None:
            return

        metadata = (
            batch.get("metadata")
            or {}
        )

        metadata["current_date"] = (
            target.isoformat()
        )

        batch["metadata"] = metadata

        save_run_batch(batch)

        try:
            window = (
                resolve_monitor_execution_window(
                    monitor=batch["monitor"],
                    mode="DATE",
                    data_date=target.isoformat(),
                )
            )

            child = create_run(
                monitor_id=batch["monitor"],
                run_type="MANUAL",
                cut=None,
                reason=batch.get("reason"),
                execution_window=
                    window.to_dict(),
                batch_id=batch_id,
            )

            run_id = child[
                "run_id"
            ]

            while True:

                current = get_run(
                    run_id
                )

                if current is None:
                    raise RuntimeError(
                        "El run hijo desaparecio "
                        "durante la ejecucion."
                    )

                status = str(
                    current.get("status")
                    or ""
                ).upper()

                if (
                    status
                    in TERMINAL_STATUSES
                ):
                    break

                time.sleep(1)

            if status in FAILED_STATUSES:
                failed += 1
            else:
                completed += 1

        except Exception as exc:
            failed += 1

            batch = get_run_batch(
                batch_id
            )

            if batch is None:
                return

            metadata = (
                batch.get("metadata")
                or {}
            )

            errors = list(
                metadata.get("errors")
                or []
            )

            errors.append(
                {
                    "date":
                        target.isoformat(),
                    "error":
                        str(exc),
                }
            )

            metadata["errors"] = errors
            batch["metadata"] = metadata

        processed = (
            completed + failed
        )

        batch = get_run_batch(
            batch_id
        )

        if batch is None:
            return

        batch[
            "completed_days"
        ] = completed

        batch[
            "failed_days"
        ] = failed

        batch[
            "progress"
        ] = int(
            processed
            * 100
            / len(dates)
        )

        save_run_batch(batch)

    batch = get_run_batch(
        batch_id
    )

    if batch is None:
        return

    batch["status"] = (
        "COMPLETED_WITH_ERRORS"
        if failed
        else "COMPLETED"
    )

    batch["progress"] = 100

    batch["finished_at"] = (
        datetime.now(
            tz
        ).isoformat()
    )

    metadata = (
        batch.get("metadata")
        or {}
    )

    metadata["current_date"] = None

    batch["metadata"] = metadata

    save_run_batch(batch)


def get_manual_batch(
    batch_id: str,
) -> dict[str, Any] | None:

    batch = get_run_batch(
        batch_id
    )

    if batch is None:
        return None

    children = (
        list_runs_by_batch(
            batch_id
        )
    )

    children.sort(
        key=lambda item: (
            str(
                item.get("data_date")
                or ""
            ),
            str(
                item.get("created_at")
                or ""
            ),
        )
    )

    result = dict(batch)

    result["runs"] = children

    return result


def list_manual_batches(
) -> list[dict[str, Any]]:

    result = []

    for batch in list_run_batches():

        if str(
            batch.get("batch_type")
            or ""
        ).upper() != "MANUAL":
            continue

        item = dict(batch)

        children = (
            list_runs_by_batch(
                batch["batch_id"]
            )
        )

        item["runs_count"] = len(
            children
        )

        result.append(item)

    return result


def recover_orphaned_manual_batches() -> int:
    """
    Marca como CANCELLED los batches MANUAL que quedaron
    PENDING/RUNNING despues de un reinicio del proceso.

    Tambien cancela sus runs hijos no terminales para evitar
    estados PENDING/PREPARING/RUNNING sin worker activo.
    """

    tz = ZoneInfo(
        DEFAULT_TIMEZONE
    )

    now = datetime.now(
        tz
    ).isoformat()

    recovered = 0

    active_batch_statuses = {
        "PENDING",
        "RUNNING",
    }

    active_run_statuses = {
        "PENDING",
        "PREPARING",
        "RUNNING",
    }

    for batch in list_run_batches():

        if str(
            batch.get("batch_type")
            or ""
        ).upper() != "MANUAL":
            continue

        status = str(
            batch.get("status")
            or ""
        ).upper()

        if status not in active_batch_statuses:
            continue

        batch_id = str(
            batch.get("batch_id")
            or ""
        )

        if not batch_id:
            continue

        for run in list_runs_by_batch(
            batch_id
        ):
            run_status = str(
                run.get("status")
                or ""
            ).upper()

            if (
                run_status
                not in active_run_statuses
            ):
                continue

            run["status"] = "CANCELLED"
            run["progress"] = 100
            run["finished_at"] = now

            errors = list(
                run.get("errors")
                or []
            )

            errors.append(
                "Ejecucion cancelada durante "
                "recuperacion de inicio: "
                "el proceso anterior finalizo "
                "sin completar el run."
            )

            run["errors"] = errors

            save_run(run)

        batch["status"] = "CANCELLED"
        batch["finished_at"] = now

        metadata = (
            batch.get("metadata")
            or {}
        )

        metadata["current_date"] = None

        errors = list(
            metadata.get("errors")
            or []
        )

        errors.append(
            {
                "date": None,
                "error": (
                    "Batch cancelado durante "
                    "recuperacion de inicio: "
                    "el proceso anterior finalizo "
                    "antes de completar la consulta."
                ),
            }
        )

        metadata["errors"] = errors
        metadata["recovered_on_startup"] = True

        batch["metadata"] = metadata

        save_run_batch(batch)

        recovered += 1

    return recovered
