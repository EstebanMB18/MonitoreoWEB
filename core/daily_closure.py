from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from api.storage import (
    get_daily_closure,
    get_latest_daily_closure,
    list_saved_runs,
    save_daily_closure,
)


TERMINAL_STATUSES = {
    "OK",
    "WARNING",
    "ERROR",
    "TIMEOUT",
    "CANCELLED",
    "NO_DATA",
    "STALE",
}

SUCCESS_STATUSES = {
    "OK",
    "WARNING",
    "NO_DATA",
}


def _run_date(
    run: dict[str, Any],
) -> str | None:
    for field in (
        "finished_at",
        "started_at",
        "created_at",
    ):
        value = run.get(field)

        if value:
            return str(value)[:10]

    return None


def _compact_run(
    run: dict[str, Any],
) -> dict[str, Any]:
    return {
        "run_id": run.get("run_id"),
        "cut": run.get("cut"),
        "status": run.get("status"),
        "records": run.get("records"),
        "alerts_count": len(
            run.get("alerts") or []
        ),
        "errors_count": len(
            run.get("errors") or []
        ),
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "duration_seconds": run.get(
            "duration_seconds"
        ),
    }


def _overall_status(
    runs: list[dict[str, Any]],
) -> str:
    if not runs:
        return "SIN_EJECUCION"

    statuses = {
        str(run.get("status"))
        for run in runs
    }

    if statuses & {
        "ERROR",
        "TIMEOUT",
        "CANCELLED",
    }:
        return "ERROR"

    if "WARNING" in statuses:
        return "WARNING"

    if "NO_DATA" in statuses:
        return "NO_DATA"

    if statuses == {"OK"}:
        return "OK"

    return "WARNING"


def build_daily_closure(
    *,
    monitor: str,
    closure_date: str,
) -> dict[str, Any]:

    monitor = monitor.upper()

    runs = [
        run
        for run in list_saved_runs()
        if run.get("monitor") == monitor
        and run.get("run_type") == "OFFICIAL"
        and bool(run.get("official"))
        and bool(run.get("historical"))
        and run.get("status")
        in TERMINAL_STATUSES
        and _run_date(run) == closure_date
    ]

    runs.sort(
        key=lambda item: (
            item.get("finished_at")
            or item.get("started_at")
            or item.get("created_at")
            or ""
        )
    )

    official_runs = len(runs)

    successful_runs = sum(
        1
        for run in runs
        if run.get("status")
        in SUCCESS_STATUSES
    )

    total_records = sum(
        int(run.get("records") or 0)
        for run in runs
    )

    alerts_count = sum(
        len(run.get("alerts") or [])
        for run in runs
    )

    errors_count = sum(
        len(run.get("errors") or [])
        for run in runs
    )

    coverage_status = (
        "EXECUTED"
        if official_runs
        else "SIN_EJECUCION"
    )

    now = datetime.now().isoformat()

    snapshot = {
        "schema_version": 1,
        "monitor": monitor,
        "date": closure_date,
        "coverage": coverage_status,
        "overall_status": _overall_status(
            runs
        ),
        "official_runs": official_runs,
        "successful_runs": successful_runs,
        "records": total_records,
        "alerts": alerts_count,
        "errors": errors_count,
        "runs": [
            _compact_run(run)
            for run in runs
        ],
    }

    return {
        "monitor": monitor,
        "closure_date": closure_date,
        "coverage_status": coverage_status,
        "overall_status": snapshot[
            "overall_status"
        ],
        "official_runs": official_runs,
        "successful_runs": successful_runs,
        "total_records": total_records,
        "alerts_count": alerts_count,
        "errors_count": errors_count,
        "first_run_at": (
            runs[0].get("started_at")
            if runs
            else None
        ),
        "last_run_at": (
            runs[-1].get("finished_at")
            if runs
            else None
        ),
        "snapshot": snapshot,
        "created_at": now,
        "updated_at": now,
    }


def close_monitor_day(
    *,
    monitor: str,
    closure_date: str,
) -> dict[str, Any]:

    # Validate ISO date before touching storage.
    date.fromisoformat(closure_date)

    closure = build_daily_closure(
        monitor=monitor,
        closure_date=closure_date,
    )

    save_daily_closure(closure)

    saved = get_daily_closure(
        monitor,
        closure_date,
    )

    if saved is None:
        raise RuntimeError(
            "El cierre diario no pudo recuperarse "
            "despues de guardarlo."
        )

    return saved


def close_all_monitors(
    *,
    closure_date: str,
    monitors: tuple[str, ...] = (
        "AWS",
        "PASARELAS",
        "HERCULES",
    ),
) -> list[dict[str, Any]]:

    return [
        close_monitor_day(
            monitor=monitor,
            closure_date=closure_date,
        )
        for monitor in monitors
    ]



def catch_up_monitor_closures(
    *,
    monitor: str,
    start_date: str | None = None,
    until_date: str | None = None,
) -> list[dict[str, Any]]:

    monitor = monitor.upper()

    if until_date is None:
        end = date.today() - timedelta(days=1)
    else:
        end = date.fromisoformat(until_date)

    latest = get_latest_daily_closure(
        monitor
    )

    if latest is not None:
        start = (
            date.fromisoformat(
                latest["closure_date"]
            )
            + timedelta(days=1)
        )
    elif start_date is not None:
        start = date.fromisoformat(
            start_date
        )
    else:
        return []

    if start > end:
        return []

    results = []
    current = start

    while current <= end:
        results.append(
            close_monitor_day(
                monitor=monitor,
                closure_date=current.isoformat(),
            )
        )

        current += timedelta(days=1)

    return results


def catch_up_all_monitors(
    *,
    start_date: str | None = None,
    until_date: str | None = None,
    monitors: tuple[str, ...] = (
        "AWS",
        "PASARELAS",
        "HERCULES",
    ),
) -> dict[str, list[dict[str, Any]]]:

    return {
        monitor: catch_up_monitor_closures(
            monitor=monitor,
            start_date=start_date,
            until_date=until_date,
        )
        for monitor in monitors
    }
