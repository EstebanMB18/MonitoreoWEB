from __future__ import annotations

from calendar import monthrange
from collections import Counter
from typing import Any

from api.storage import list_daily_closures


VALID_MONITORS = (
    "AWS",
    "PASARELAS",
    "HERCULES",
)


def _integer(
    value: Any,
) -> int:
    try:
        return int(
            float(value or 0)
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0


def _snapshot(
    closure: dict[str, Any],
) -> dict[str, Any]:
    value = (
        closure.get("snapshot")
        or {}
    )

    return (
        value
        if isinstance(value, dict)
        else {}
    )


def _kpis(
    closure: dict[str, Any],
) -> dict[str, Any]:
    value = (
        _snapshot(closure)
        .get("kpis")
        or {}
    )

    return (
        value
        if isinstance(value, dict)
        else {}
    )


def _daily_item(
    closure: dict[str, Any],
) -> dict[str, Any]:
    return {
        "date":
            closure.get(
                "closure_date"
            ),
        "monitor":
            closure.get("monitor"),
        "coverage":
            closure.get(
                "coverage_status"
            ),
        "status":
            closure.get(
                "overall_status"
            ),
        "official_runs":
            _integer(
                closure.get(
                    "official_runs"
                )
            ),
        "successful_runs":
            _integer(
                closure.get(
                    "successful_runs"
                )
            ),
        "records":
            _integer(
                closure.get(
                    "total_records"
                )
            ),
        "alerts":
            _integer(
                closure.get(
                    "alerts_count"
                )
            ),
        "errors":
            _integer(
                closure.get(
                    "errors_count"
                )
            ),
        "kpis":
            _kpis(closure),
    }


def _monitor_totals(
    monitor: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:

    statuses = Counter(
        str(
            item.get("status")
            or "UNKNOWN"
        )
        for item in items
    )

    coverage = Counter(
        str(
            item.get("coverage")
            or "UNKNOWN"
        )
        for item in items
    )

    result: dict[str, Any] = {
        "monitor": monitor,
        "days": len(items),
        "days_executed":
            coverage.get(
                "EXECUTED",
                0,
            ),
        "days_without_execution":
            coverage.get(
                "SIN_EJECUCION",
                0,
            ),
        "official_runs": sum(
            _integer(
                item.get(
                    "official_runs"
                )
            )
            for item in items
        ),
        "successful_runs": sum(
            _integer(
                item.get(
                    "successful_runs"
                )
            )
            for item in items
        ),
        "records": sum(
            _integer(
                item.get("records")
            )
            for item in items
        ),
        "alerts": sum(
            _integer(
                item.get("alerts")
            )
            for item in items
        ),
        "errors": sum(
            _integer(
                item.get("errors")
            )
            for item in items
        ),
        "statuses":
            dict(statuses),
    }

    if monitor == "PASARELAS":
        result["kpis"] = {
            "aprobadas": sum(
                _integer(
                    item.get(
                        "kpis",
                        {},
                    ).get(
                        "aprobadas"
                    )
                )
                for item in items
            ),
            "fallidas": sum(
                _integer(
                    item.get(
                        "kpis",
                        {},
                    ).get(
                        "fallidas"
                    )
                )
                for item in items
            ),
            "tup_610_aprobadas": sum(
                _integer(
                    item.get(
                        "kpis",
                        {},
                    ).get(
                        "tup_610",
                        {},
                    ).get(
                        "aprobadas"
                    )
                )
                for item in items
            ),
            "tup_610_fallidas": sum(
                _integer(
                    item.get(
                        "kpis",
                        {},
                    ).get(
                        "tup_610",
                        {},
                    ).get(
                        "fallidas"
                    )
                )
                for item in items
            ),
        }

    elif monitor == "AWS":
        result["kpis"] = {
            "tup_aprobadas": sum(
                _integer(
                    item.get(
                        "kpis",
                        {},
                    ).get(
                        "tup",
                        {},
                    ).get(
                        "aprobadas"
                    )
                )
                for item in items
            ),
            "tup_errores": sum(
                _integer(
                    item.get(
                        "kpis",
                        {},
                    ).get(
                        "tup",
                        {},
                    ).get(
                        "errores"
                    )
                )
                for item in items
            ),
            "servicios_red": sum(
                _integer(
                    item.get(
                        "kpis",
                        {},
                    ).get(
                        "servicios_red",
                        {},
                    ).get(
                        "total"
                    )
                )
                for item in items
            ),
            "mensajeria_exitos": sum(
                _integer(
                    item.get(
                        "kpis",
                        {},
                    ).get(
                        "mensajeria",
                        {},
                    ).get(
                        "exitos"
                    )
                )
                for item in items
            ),
            "mensajeria_errores": sum(
                _integer(
                    item.get(
                        "kpis",
                        {},
                    ).get(
                        "mensajeria",
                        {},
                    ).get(
                        "errores"
                    )
                )
                for item in items
            ),
        }

    elif monitor == "HERCULES":
        result["kpis"] = {
            "pago_realizado": sum(
                _integer(
                    item.get(
                        "kpis",
                        {},
                    ).get(
                        "pago_realizado"
                    )
                )
                for item in items
            ),
            "checkout": sum(
                _integer(
                    item.get(
                        "kpis",
                        {},
                    ).get(
                        "checkout"
                    )
                )
                for item in items
            ),
            "pendiente_recaudo": sum(
                _integer(
                    item.get(
                        "kpis",
                        {},
                    ).get(
                        "pendiente_recaudo"
                    )
                )
                for item in items
            ),
            "web_tcompensar_pago_realizado": sum(
                _integer(
                    item.get(
                        "kpis",
                        {},
                    ).get(
                        "web_tcompensar",
                        {},
                    ).get(
                        "pago_realizado"
                    )
                )
                for item in items
            ),
        }

    return result


def build_monthly_history(
    *,
    year: int,
    month: int,
    monitor: str | None = None,
) -> dict[str, Any]:

    if year < 2000:
        raise ValueError(
            "year invalido"
        )

    if month < 1 or month > 12:
        raise ValueError(
            "month invalido"
        )

    normalized_monitor = (
        monitor.upper()
        if monitor
        else None
    )

    if (
        normalized_monitor
        and normalized_monitor
        not in VALID_MONITORS
    ):
        raise ValueError(
            "monitor invalido"
        )

    last_day = monthrange(
        year,
        month,
    )[1]

    start_date = (
        f"{year:04d}-"
        f"{month:02d}-01"
    )

    end_date = (
        f"{year:04d}-"
        f"{month:02d}-"
        f"{last_day:02d}"
    )

    closures = list_daily_closures(
        monitor=normalized_monitor,
        start_date=start_date,
        end_date=end_date,
    )

    daily = [
        _daily_item(item)
        for item in closures
    ]

    daily.sort(
        key=lambda item: (
            item.get("date") or "",
            item.get("monitor") or "",
        )
    )

    monitors = (
        [normalized_monitor]
        if normalized_monitor
        else list(VALID_MONITORS)
    )

    by_monitor = {}

    for monitor_name in monitors:
        monitor_items = [
            item
            for item in daily
            if item.get("monitor")
            == monitor_name
        ]

        by_monitor[
            monitor_name
        ] = _monitor_totals(
            monitor_name,
            monitor_items,
        )

    overall_statuses = Counter(
        str(
            item.get("status")
            or "UNKNOWN"
        )
        for item in daily
    )

    return {
        "schema_version": 1,
        "period": {
            "year": year,
            "month": month,
            "start_date":
                start_date,
            "end_date":
                end_date,
            "calendar_days":
                last_day,
        },
        "monitor":
            normalized_monitor,
        "summary": {
            "closures":
                len(daily),
            "days_with_execution":
                len({
                    item["date"]
                    for item in daily
                    if item.get(
                        "coverage"
                    ) == "EXECUTED"
                }),
            "official_runs": sum(
                _integer(
                    item.get(
                        "official_runs"
                    )
                )
                for item in daily
            ),
            "records": sum(
                _integer(
                    item.get(
                        "records"
                    )
                )
                for item in daily
            ),
            "alerts": sum(
                _integer(
                    item.get(
                        "alerts"
                    )
                )
                for item in daily
            ),
            "errors": sum(
                _integer(
                    item.get(
                        "errors"
                    )
                )
                for item in daily
            ),
            "statuses":
                dict(
                    overall_statuses
                ),
        },
        "monitors":
            by_monitor,
        "daily":
            daily,
    }
