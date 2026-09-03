from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from api.auth_dependencies import require_roles
from pydantic import BaseModel

from api.storage import (
    get_daily_closure,
    list_daily_closures,
)
from core.daily_closure import (
    catch_up_all_monitors,
    close_all_monitors,
    close_monitor_day,
)
from core.monthly_history import (
    build_monthly_history,
)
from core.monthly_report import (
    export_monthly_report,
)


router = APIRouter()


VALID_MONITORS = {
    "AWS",
    "PASARELAS",
    "HERCULES",
}


class DailyCloseRequest(BaseModel):
    closure_date: str | None = None
    monitor: str | None = None
    catch_up: bool = False
    start_date: str | None = None


def _validate_monitor(
    monitor: str,
) -> str:
    value = monitor.upper()

    if value not in VALID_MONITORS:
        raise HTTPException(
            status_code=404,
            detail="Monitor no encontrado.",
        )

    return value


def _validate_date(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    try:
        return date.fromisoformat(
            value
        ).isoformat()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=(
                "Fecha invalida. "
                "Use formato YYYY-MM-DD."
            ),
        )


@router.get("/history/daily")
def daily_history(
    monitor: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
            "OPERADOR",
            "CONSULTA",
        )
    ),
):
    normalized_monitor = None

    if monitor:
        normalized_monitor = (
            _validate_monitor(
                monitor
            )
        )

    start_date = _validate_date(
        start_date
    )
    end_date = _validate_date(
        end_date
    )

    if (
        start_date
        and end_date
        and start_date > end_date
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "start_date no puede ser "
                "posterior a end_date."
            ),
        )

    items = list_daily_closures(
        monitor=normalized_monitor,
        start_date=start_date,
        end_date=end_date,
    )

    return {
        "items": items,
        "total": len(items),
    }


@router.get(
    "/history/daily/{monitor}"
)
def daily_history_monitor(
    monitor: str,
    closure_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
            "OPERADOR",
            "CONSULTA",
        )
    ),
):
    normalized_monitor = (
        _validate_monitor(
            monitor
        )
    )

    if closure_date:
        closure_date = _validate_date(
            closure_date
        )

        item = get_daily_closure(
            normalized_monitor,
            closure_date,
        )

        if item is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Cierre diario "
                    "no encontrado."
                ),
            )

        return item

    start_date = _validate_date(
        start_date
    )
    end_date = _validate_date(
        end_date
    )

    if (
        start_date
        and end_date
        and start_date > end_date
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "start_date no puede ser "
                "posterior a end_date."
            ),
        )

    items = list_daily_closures(
        monitor=normalized_monitor,
        start_date=start_date,
        end_date=end_date,
    )

    return {
        "monitor": normalized_monitor,
        "items": items,
        "total": len(items),
    }




@router.get("/history/monthly")
def monthly_history(
    year: int,
    month: int,
    monitor: str | None = None,
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
            "OPERADOR",
            "CONSULTA",
        )
    ),
):
    normalized_monitor = None

    if monitor:
        normalized_monitor = (
            _validate_monitor(
                monitor
            )
        )

    if year < 2000:
        raise HTTPException(
            status_code=400,
            detail="year invalido.",
        )

    if month < 1 or month > 12:
        raise HTTPException(
            status_code=400,
            detail=(
                "month debe estar "
                "entre 1 y 12."
            ),
        )

    return build_monthly_history(
        year=year,
        month=month,
        monitor=normalized_monitor,
    )




@router.get("/history/monthly/export")
def monthly_history_export(
    year: int,
    month: int,
    monitor: str | None = None,
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
            "OPERADOR",
            "CONSULTA",
        )
    ),
):
    normalized_monitor = None

    if monitor:
        normalized_monitor = (
            _validate_monitor(
                monitor
            )
        )

    if year < 2000:
        raise HTTPException(
            status_code=400,
            detail="year invalido.",
        )

    if month < 1 or month > 12:
        raise HTTPException(
            status_code=400,
            detail=(
                "month debe estar "
                "entre 1 y 12."
            ),
        )

    try:
        target = export_monthly_report(
            year=year,
            month=month,
            monitor=normalized_monitor,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "No fue posible generar "
                "el reporte mensual."
            ),
        ) from exc

    if not target.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                "El reporte mensual "
                "no fue generado."
            ),
        )

    filename = (
        f"Nexus_Mensual_"
        f"{year:04d}_{month:02d}"
    )

    if normalized_monitor:
        filename += (
            f"_{normalized_monitor}"
        )

    filename += ".xlsx"

    return FileResponse(
        path=str(target),
        filename=filename,
        media_type=(
            "application/"
            "vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )


@router.post("/history/close")
def close_history(
    payload: DailyCloseRequest,
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
        )
    ),
):
    target_date = (
        _validate_date(
            payload.closure_date
        )
        if payload.closure_date
        else (
            date.today()
            - timedelta(days=1)
        ).isoformat()
    )

    if target_date >= date.today().isoformat():
        raise HTTPException(
            status_code=400,
            detail=(
                "El cierre diario solo puede "
                "realizarse hasta ayer."
            ),
        )

    if payload.catch_up:
        start_date = _validate_date(
            payload.start_date
        )

        if payload.monitor:
            monitor = _validate_monitor(
                payload.monitor
            )

            from core.daily_closure import (
                catch_up_monitor_closures,
            )

            items = (
                catch_up_monitor_closures(
                    monitor=monitor,
                    start_date=start_date,
                    until_date=target_date,
                )
            )

            return {
                "mode": "catch_up",
                "monitor": monitor,
                "until_date": target_date,
                "items": items,
                "total": len(items),
            }

        result = catch_up_all_monitors(
            start_date=start_date,
            until_date=target_date,
        )

        return {
            "mode": "catch_up",
            "until_date": target_date,
            "items": result,
            "total": sum(
                len(items)
                for items in result.values()
            ),
        }

    if payload.monitor:
        monitor = _validate_monitor(
            payload.monitor
        )

        item = close_monitor_day(
            monitor=monitor,
            closure_date=target_date,
        )

        return {
            "mode": "single",
            "item": item,
        }

    items = close_all_monitors(
        closure_date=target_date,
    )

    return {
        "mode": "all",
        "items": items,
        "total": len(items),
    }
