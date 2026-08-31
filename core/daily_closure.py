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
    # El hist?rico debe pertenecer al d?a de los
    # datos monitoreados, no necesariamente al d?a
    # en que termin? f?sicamente la ejecuci?n.
    data_date = run.get("data_date")

    if data_date:
        return str(data_date)[:10]

    # Compatibilidad con ejecuciones antiguas.
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


def _integer(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _details(
    run: dict[str, Any],
) -> dict[str, Any]:
    value = run.get("details") or {}
    return value if isinstance(value, dict) else {}


def _summary(
    run: dict[str, Any],
) -> dict[str, Any]:
    value = _details(run).get("summary") or {}
    return value if isinstance(value, dict) else {}


def _series(
    run: dict[str, Any],
) -> dict[str, Any]:
    value = _details(run).get("series") or {}
    return value if isinstance(value, dict) else {}


def _count_safe_rows(value: Any) -> int:
    if not isinstance(value, list):
        return 0

    total = 0

    for row in value:
        if not isinstance(row, dict):
            continue

        count = (
            row.get("count")
            or row.get("cantidad")
            or row.get("total")
            or 1
        )

        total += _integer(count)

    return total


def _aws_daily_kpis(
    run: dict[str, Any],
) -> dict[str, Any]:
    series = _series(run)

    tup = series.get("tup_resumen") or {}

    if isinstance(tup, list):
        tup = (
            tup[0]
            if tup
            and isinstance(tup[0], dict)
            else {}
        )

    if not isinstance(tup, dict):
        tup = {}

    servicios = (
        series.get("serviciosred_resumen")
        or {}
    )

    if isinstance(servicios, list):
        servicios = (
            servicios[0]
            if servicios
            and isinstance(
                servicios[0],
                dict,
            )
            else {}
        )

    if not isinstance(servicios, dict):
        servicios = {}

    servicios_total = 0

    for key in (
        "total",
        "notificaciones",
        "cantidad",
        "count",
    ):
        if servicios.get(key) is not None:
            servicios_total = _integer(
                servicios[key]
            )
            break

    ultima_notificacion = None

    for key in (
        "ultima_notificacion",
        "ultima_transaccion",
        "ultima_actividad",
        "ultima",
    ):
        if servicios.get(key):
            ultima_notificacion = str(
                servicios[key]
            )
            break

    otp_exitos = 0
    otp_errores = 0
    otp_available = False

    for key, target in (
        ("mensajeria_exitos", "ok"),
        ("mensajeria_errores", "error"),
    ):
        rows = series.get(key) or []

        if not isinstance(rows, list):
            continue

        for row in rows:
            if not isinstance(row, dict):
                continue

            searchable = " ".join(
                str(value)
                for value in row.values()
                if value is not None
            ).casefold()

            if "otp" not in searchable:
                continue

            otp_available = True

            count = _integer(
                row.get("count")
                or row.get("cantidad")
                or row.get("total")
                or 1
            )

            if target == "ok":
                otp_exitos += count
            else:
                otp_errores += count

    return {
        "tup": {
            "aprobadas": _integer(
                tup.get("aprobadas")
            ),
            "errores": _integer(
                tup.get("errores")
            ),
            "total": _integer(
                tup.get("total")
            ),
        },
        "servicios_red": {
            "total": servicios_total,
            "ultima_notificacion":
                ultima_notificacion,
        },
        "mensajeria": {
            "exitos": _count_safe_rows(
                series.get(
                    "mensajeria_exitos"
                )
            ),
            "errores": _count_safe_rows(
                series.get(
                    "mensajeria_errores"
                )
            ),
        },
        "otp": {
            "available": otp_available,
            "exitos": otp_exitos,
            "errores": otp_errores,
            "total":
                otp_exitos + otp_errores,
        },
    }


def _pasarelas_41610(
    run: dict[str, Any],
) -> dict[str, Any]:
    result = {
        "aprobadas": 0,
        "fallidas": 0,
        "total": 0,
        "status": "NO_DATA",
    }

    groups = (
        _details(run).get("groups")
        or []
    )

    statuses: list[str] = []

    for group in groups:
        if not isinstance(group, dict):
            continue

        code = str(
            group.get("code")
            or group.get("id")
            or ""
        )

        if code != "41610":
            continue

        for service in (
            group.get("services")
            or []
        ):
            if not isinstance(
                service,
                dict,
            ):
                continue

            for metric in (
                service.get("metrics")
                or []
            ):
                if not isinstance(
                    metric,
                    dict,
                ):
                    continue

                result["aprobadas"] += (
                    _integer(
                        metric.get(
                            "cantidad_ok"
                        )
                    )
                )

                result["fallidas"] += (
                    _integer(
                        metric.get(
                            "cantidad_fallida"
                        )
                    )
                )

                result["total"] += (
                    _integer(
                        metric.get(
                            "cantidad_total"
                        )
                    )
                )

                status = str(
                    metric.get("status")
                    or ""
                ).upper()

                if status:
                    statuses.append(status)

    if statuses:
        if any(
            value
            not in {
                "OK",
                "LEARNING",
                "NO_DATA",
            }
            for value in statuses
        ):
            result["status"] = "WARNING"
        elif "LEARNING" in statuses:
            result["status"] = "LEARNING"
        elif set(statuses) == {"NO_DATA"}:
            result["status"] = "NO_DATA"
        else:
            result["status"] = "OK"

    return result


def _pasarelas_daily_kpis(
    run: dict[str, Any],
) -> dict[str, Any]:
    summary = _summary(run)

    return {
        "aprobadas": _integer(
            summary.get("cantidad_ok")
        ),
        "fallidas": _integer(
            summary.get(
                "cantidad_fallida"
            )
        ),
        "tup_610":
            _pasarelas_41610(run),
    }


def _hercules_daily_kpis(
    run: dict[str, Any],
) -> dict[str, Any]:
    summary = _summary(run)
    series = _series(run)

    tarjeta = {
        "pago_realizado": 0,
        "checkout": 0,
        "pendiente_recaudo": 0,
        "pago_pendiente": 0,
        "status": "NO_DATA",
    }

    for item in (
        series.get("alertas_web")
        or []
    ):
        if not isinstance(item, dict):
            continue

        forma = str(
            item.get("forma_pago")
            or ""
        ).strip().casefold()

        if forma not in {
            "t. compensar",
            "tarjeta compensar",
            "tup",
        }:
            continue

        tarjeta = {
            "pago_realizado":
                _integer(
                    item.get(
                        "pago_realizado"
                    )
                ),
            "checkout":
                _integer(
                    item.get("checkout")
                ),
            "pendiente_recaudo":
                _integer(
                    item.get(
                        "pendiente_recaudo"
                    )
                ),
            "pago_pendiente":
                _integer(
                    item.get(
                        "pago_pendiente"
                    )
                ),
            "status": str(
                item.get("status")
                or "NO_DATA"
            ),
        }

        break

    return {
        "pago_realizado": _integer(
            summary.get(
                "pago_realizado"
            )
        ),
        "checkout": _integer(
            summary.get("checkout")
        ),
        "pendiente_recaudo": _integer(
            summary.get(
                "pendiente_recaudo"
            )
        ),
        "web_tcompensar": tarjeta,
    }


def _daily_kpis(
    monitor: str,
    runs: list[dict[str, Any]],
) -> dict[str, Any]:
    if not runs:
        return {}

    # Los monitores manejan cifras acumuladas
    # durante el d?a. Para evitar duplicar
    # transacciones entre cortes, el hist?rico
    # conserva el ?ltimo snapshot oficial.
    run = runs[-1]

    if monitor == "AWS":
        return _aws_daily_kpis(run)

    if monitor == "PASARELAS":
        return _pasarelas_daily_kpis(
            run
        )

    if monitor == "HERCULES":
        return _hercules_daily_kpis(
            run
        )

    return {}



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
        "schema_version": 2,
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
        "kpis": _daily_kpis(
            monitor,
            runs,
        ),
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
