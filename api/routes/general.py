from __future__ import annotations

import calendar
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth_dependencies import require_roles
from api.runtime import (
    create_general_run,
    list_runs,
)
from api.storage import list_daily_closures


router = APIRouter(
    prefix="/general",
    tags=["general"],
)


TERMINAL_STATUSES = {
    "OK",
    "WARNING",
    "WARN",
    "ALERT",
    "ERROR",
    "NO_DATA",
    "LEARNING",
}


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _latest_completed(
    monitor: str,
) -> dict[str, Any] | None:
    key = monitor.upper()

    for item in list_runs():
        if str(item.get("monitor", "")).upper() != key:
            continue

        status = str(
            item.get("status", "")
        ).upper()

        if status not in TERMINAL_STATUSES:
            continue

        run_type = str(
            item.get("run_type", "")
        ).upper()

        is_official = bool(
            item.get("official")
        ) or run_type == "OFFICIAL"

        if not is_official:
            continue

        details = item.get("details") or {}

        if details:
            return item

    return None


def _series(
    run: dict[str, Any] | None,
) -> dict[str, Any]:
    if not run:
        return {}

    return (
        run.get("details", {})
        .get("series", {})
        or {}
    )


def _summary(
    run: dict[str, Any] | None,
) -> dict[str, Any]:
    if not run:
        return {}

    return (
        run.get("details", {})
        .get("summary", {})
        or {}
    )


def _find_pasarelas_41610(
    run: dict[str, Any] | None,
) -> dict[str, Any]:
    result = {
        "aprobadas": 0,
        "fallidas": 0,
        "total": 0,
        "ultima_ok": None,
        "status": "NO_DATA",
    }

    if not run:
        return result

    groups = (
        run.get("details", {})
        .get("groups", [])
        or []
    )

    statuses: list[str] = []
    ultima_ok: str | None = None

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

        for service in group.get(
            "services",
            [],
        ) or []:
            if not isinstance(service, dict):
                continue

            for metric in service.get(
                "metrics",
                [],
            ) or []:
                if not isinstance(metric, dict):
                    continue

                result["aprobadas"] += _int(
                    metric.get("cantidad_ok")
                )
                result["fallidas"] += _int(
                    metric.get(
                        "cantidad_fallida"
                    )
                )
                result["total"] += _int(
                    metric.get(
                        "cantidad_total"
                    )
                )

                status = str(
                    metric.get("status")
                    or ""
                ).upper()

                if status:
                    statuses.append(status)

                value = metric.get(
                    "ultima_ok"
                )

                if (
                    value
                    and "sin aprobadas"
                    not in str(value).lower()
                ):
                    ultima_ok = str(value)

    result["ultima_ok"] = ultima_ok

    if not statuses:
        return result

    if any(
        status
        not in {
            "OK",
            "LEARNING",
            "NO_DATA",
        }
        for status in statuses
    ):
        result["status"] = "WARNING"
    elif "LEARNING" in statuses:
        result["status"] = "LEARNING"
    elif set(statuses) == {"NO_DATA"}:
        result["status"] = "NO_DATA"
    else:
        result["status"] = "OK"

    return result


def _hercules_tcompensar(
    run: dict[str, Any] | None,
) -> dict[str, Any]:
    result = {
        "pago_realizado": 0,
        "checkout": 0,
        "pendiente_recaudo": 0,
        "pago_pendiente": 0,
        "status": "NO_DATA",
    }

    if not run:
        return result

    alertas = (
        _series(run)
        .get("alertas_web", [])
        or []
    )

    for item in alertas:
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

        result.update({
            "pago_realizado": _int(
                item.get("pago_realizado")
            ),
            "checkout": _int(
                item.get("checkout")
            ),
            "pendiente_recaudo": _int(
                item.get(
                    "pendiente_recaudo"
                )
            ),
            "pago_pendiente": _int(
                item.get("pago_pendiente")
            ),
            "status": str(
                item.get("status")
                or "NO_DATA"
            ),
        })
        break

    return result


def _count_rows(
    rows: Any,
) -> int:
    if not isinstance(rows, list):
        return 0

    total = 0

    for row in rows:
        if not isinstance(row, dict):
            continue

        count = (
            row.get("count")
            or row.get("cantidad")
            or row.get("total")
            or 1
        )

        total += _int(count)

    return total


def _otp_summary(
    aws_series: dict[str, Any],
) -> dict[str, Any]:
    result = {
        "available": False,
        "exitos": 0,
        "errores": 0,
        "total": 0,
    }

    for key, target in (
        ("mensajeria_exitos", "exitos"),
        ("mensajeria_errores", "errores"),
    ):
        rows = aws_series.get(key) or []

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

            result["available"] = True

            count = (
                row.get("count")
                or row.get("cantidad")
                or row.get("total")
                or 1
            )

            result[target] += _int(count)

    result["total"] = (
        result["exitos"]
        + result["errores"]
    )

    return result


def _servicios_red_summary(
    aws_series: dict[str, Any],
) -> dict[str, Any]:
    raw = (
        aws_series.get(
            "serviciosred_resumen"
        )
        or {}
    )

    if isinstance(raw, list):
        raw = (
            raw[0]
            if raw
            and isinstance(raw[0], dict)
            else {}
        )

    if not isinstance(raw, dict):
        raw = {}

    minutos = None

    for key in (
        "minutos_sin_actividad",
        "minutos_sin_notificaciones",
        "minutos_sin_notificacion",
    ):
        if raw.get(key) is not None:
            try:
                minutos = int(
                    float(raw[key])
                )
            except (
                TypeError,
                ValueError,
            ):
                pass
            break

    total = 0

    for key in (
        "total",
        "notificaciones",
        "cantidad",
        "count",
    ):
        if raw.get(key) is not None:
            total = _int(raw[key])
            break

    ultima = None

    for key in (
        "ultima_notificacion",
        "ultima_transaccion",
        "ultima_actividad",
        "ultima",
    ):
        if raw.get(key):
            ultima = str(raw[key])
            break

    if minutos is None and ultima:
        try:
            last_dt = datetime.fromisoformat(
                ultima.replace("Z", "+00:00")
            )

            now = datetime.now(
                tz=last_dt.tzinfo
            ) if last_dt.tzinfo else datetime.now()

            minutos = max(
                0,
                int(
                    (now - last_dt)
                    .total_seconds()
                    // 60
                ),
            )
        except (TypeError, ValueError):
            minutos = None

    return {
        "total": total,
        "ultima_notificacion": ultima,
        "minutos_sin_actividad": minutos,
        "raw": raw,
    }


def _correlation(
    correlation_id: str,
    name: str,
    status: str,
    message: str,
    values: dict[str, Any],
    delta: int | None,
) -> dict[str, Any]:
    return {
        "id": correlation_id,
        "name": name,
        "status": status,
        "message": message,
        "values": values,
        "delta": delta,
    }



class GeneralRunRequest(BaseModel):
    run_type: str = "MANUAL"

    window_mode: str = "TODAY_TO_NOW"

    data_date: str | None = None
    cut: str | None = None

    window_start: str | None = None
    window_end: str | None = None

    last_n_hours: int | None = None

    reason: str | None = None


@router.post("/run")
def run_general(
    payload: GeneralRunRequest,
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
            "OPERADOR",
        )
    ),
):
    run_type = str(
        payload.run_type
    ).upper()

    if run_type not in {
        "OFFICIAL",
        "MANUAL",
        "INCIDENT",
        "TEST",
    }:
        raise HTTPException(
            status_code=400,
            detail=(
                "run_type invalido. "
                "Permitidos: OFFICIAL, "
                "MANUAL, INCIDENT, TEST."
            ),
        )

    role = str(
        user.get("role")
        or ""
    ).upper()

    if (
        run_type == "OFFICIAL"
        and role not in {
            "ADMIN",
            "MONITOR_OFICIAL",
        }
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Solo ADMIN o MONITOR_OFICIAL "
                "pueden ejecutar cortes OFFICIAL."
            ),
        )

    if (
        run_type == "OFFICIAL"
        and str(
            payload.window_mode
            or ""
        ).upper() != "CUT"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Una ejecucion OFFICIAL "
                "debe usar window_mode=CUT."
            ),
        )

    try:
        return create_general_run(
            run_type=run_type,
            window_mode=
                payload.window_mode,
            data_date=
                payload.data_date,
            cut=payload.cut,
            window_start=
                payload.window_start,
            window_end=
                payload.window_end,
            last_n_hours=
                payload.last_n_hours,
            reason=payload.reason,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc




# ============================================================
# General operational safe aggregates
# ============================================================

_SIGNAL_RANK = {
    "OK": 0,
    "WARNING": 1,
    "ERROR": 2,
}


def _normalize_signal_status(
    value: Any,
) -> str:
    raw = str(value or "").strip().upper()

    if raw in {
        "ERROR",
        "ALERT",
        "ALERTA",
        "CRITICAL",
        "CRITICA",
        "CR?TICA",
        "FAILED",
    }:
        return "ERROR"

    if raw in {
        "WARNING",
        "WARN",
        "REVISAR",
        "LEARNING",
        "NO_DATA",
        "STALE",
    }:
        return "WARNING"

    return "OK"


def _worst_signal_status(
    values: list[Any],
) -> str:
    statuses = [
        _normalize_signal_status(value)
        for value in values
    ]

    if not statuses:
        return "WARNING"

    return max(
        statuses,
        key=lambda value:
            _SIGNAL_RANK[value],
    )


def _run_signal_status(
    run: dict[str, Any] | None,
) -> str:
    if not run:
        return "WARNING"

    return _normalize_signal_status(
        run.get("status")
    )


def _count_signal_status(
    *,
    ok: int,
    errors: int,
    label: str,
    available: bool = True,
) -> dict[str, Any]:
    if not available:
        return {
            "status": "WARNING",
            "message":
                f"{label} no tiene m?trica segura disponible.",
        }

    if ok <= 0 and errors > 0:
        return {
            "status": "ERROR",
            "message":
                f"{label} registra errores y no registra ?xitos.",
        }

    if errors > ok and errors > 0:
        return {
            "status": "ERROR",
            "message":
                f"{label} registra m?s errores que ?xitos.",
        }

    if errors > 0:
        return {
            "status": "WARNING",
            "message":
                f"{label} registra errores durante la ventana.",
        }

    return {
        "status": "OK",
        "message": None,
    }


def _pasarelas_verticales(
    run: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not run:
        return []

    details = run.get("details") or {}
    groups = details.get("groups") or []

    result: list[dict[str, Any]] = []

    for group in groups:
        if not isinstance(group, dict):
            continue

        codigo = str(
            group.get("id")
            or group.get("code")
            or group.get("codigo")
            or ""
        )

        vertical = str(
            group.get("name")
            or group.get("vertical")
            or codigo
        )

        services = (
            group.get("services")
            or group.get("medios")
            or []
        )

        # Clave:
        # (fuente, canal, medio funcional)
        consolidated: dict[
            tuple[str, str, str],
            dict[str, Any],
        ] = {}

        vertical_statuses: list[Any] = []
        vertical_reason: str | None = None

        for service in services:
            if not isinstance(service, dict):
                continue

            technical_name = str(
                service.get("name")
                or service.get("id")
                or ""
            ).strip()

            fuente = ""
            canal = ""

            if "/" in technical_name:
                parts = [
                    part.strip()
                    for part
                    in technical_name.split("/", 1)
                ]

                fuente = parts[0]

                if len(parts) > 1:
                    canal = parts[1]

            else:
                service_id = str(
                    service.get("id")
                    or ""
                ).lower()

                if "ecollect" in service_id:
                    fuente = "ECOLLECT"

                    if "java" in service_id:
                        canal = "JAVA"
                    elif "red" in service_id:
                        canal = "RED"

                elif "payu" in service_id:
                    fuente = "PAYU"
                    canal = "PAYU"

                else:
                    fuente = technical_name

            metrics = (
                service.get("metrics")
                or []
            )

            # Contrato actual Pasarelas:
            # cada metric representa un medio
            # funcional de negocio.
            for metric in metrics:
                if not isinstance(metric, dict):
                    continue

                medio = str(
                    metric.get("medio_salida")
                    or metric.get("medio_pago")
                    or metric.get("metric")
                    or ""
                ).strip()

                if not medio:
                    continue

                status = (
                    _normalize_signal_status(
                        metric.get("status")
                    )
                )

                ok = _int(
                    metric.get("cantidad_ok")
                )

                total = _int(
                    metric.get("cantidad_total")
                )

                fallidas = _int(
                    metric.get("cantidad_fallida")
                )

                if (
                    fallidas <= 0
                    and total >= ok
                ):
                    fallidas = total - ok

                promedio_raw = metric.get(
                    "promedio"
                )

                try:
                    promedio = (
                        float(promedio_raw)
                        if promedio_raw is not None
                        else None
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    promedio = None

                motivo = (
                    metric.get("detail")
                    or metric.get(
                        "technical_error"
                    )
                )

                key = (
                    fuente,
                    canal,
                    medio,
                )

                entry = consolidated.get(
                    key
                )

                if entry is None:
                    entry = {
                        # Campo funcional obligatorio.
                        "medio": medio,

                        # Compatibilidad temporal.
                        "nombre": medio,

                        # Datos t?cnicos separados.
                        "fuente": fuente,
                        "canal": canal,

                        "ok": 0,
                        "total": 0,
                        "fallidas": 0,
                        "promedio": promedio,
                        "status": status,
                        "motivo": (
                            str(motivo)
                            if motivo
                            else None
                        ),
                    }

                    consolidated[key] = entry

                else:
                    entry["status"] = (
                        _worst_signal_status(
                            [
                                entry["status"],
                                status,
                            ]
                        )
                    )

                    if (
                        entry["motivo"] is None
                        and motivo
                    ):
                        entry["motivo"] = str(
                            motivo
                        )

                    if (
                        entry["promedio"] is None
                        and promedio is not None
                    ):
                        entry[
                            "promedio"
                        ] = promedio

                entry["ok"] += ok
                entry["total"] += total
                entry["fallidas"] += (
                    fallidas
                )

                vertical_statuses.append(
                    status
                )

                if (
                    vertical_reason is None
                    and status != "OK"
                    and motivo
                ):
                    vertical_reason = str(
                        motivo
                    )

            # Compatibilidad futura/antigua:
            # servicio agregado sin metrics.
            if not metrics:
                medio = str(
                    service.get("medio")
                    or service.get("name")
                    or service.get("id")
                    or "SIN_MEDIO"
                )

                status = (
                    _normalize_signal_status(
                        service.get("status")
                    )
                )

                ok = _int(
                    service.get("cantidad_ok")
                    if "cantidad_ok" in service
                    else service.get("ok")
                )

                total = _int(
                    service.get("cantidad_total")
                    if "cantidad_total" in service
                    else service.get("total")
                )

                fallidas = _int(
                    service.get("cantidad_fallida")
                    if "cantidad_fallida" in service
                    else service.get("fallidas")
                )

                if (
                    fallidas <= 0
                    and total >= ok
                ):
                    fallidas = total - ok

                motivo = (
                    service.get("detail")
                    or service.get("motivo")
                )

                key = (
                    fuente,
                    canal,
                    medio,
                )

                consolidated[key] = {
                    "medio": medio,
                    "nombre": medio,
                    "fuente": fuente,
                    "canal": canal,
                    "ok": ok,
                    "total": total,
                    "fallidas": fallidas,
                    "promedio":
                        service.get(
                            "promedio"
                        ),
                    "status": status,
                    "motivo": (
                        str(motivo)
                        if motivo
                        else None
                    ),
                }

                vertical_statuses.append(
                    status
                )

        vertical_status = (
            _worst_signal_status(
                vertical_statuses
            )
            if vertical_statuses
            else "WARNING"
        )

        result.append(
            {
                "codigo": codigo,
                "vertical": vertical,
                "status": vertical_status,
                "motivo": vertical_reason,
                "medios": list(
                    consolidated.values()
                ),
            }
        )

    return result


def _hercules_distribution(
    summary: dict[str, Any],
) -> list[dict[str, Any]]:
    fields = (
        (
            "Pago realizado",
            "pago_realizado",
        ),
        (
            "Checkout",
            "checkout",
        ),
        (
            "Pago pendiente",
            "pago_pendiente",
        ),
        (
            "Pendiente recaudo",
            "pendiente_recaudo",
        ),
        (
            "Pendiente facturaci?n",
            "pendiente_facturacion",
        ),
        (
            "Recaudado",
            "recaudado",
        ),
        (
            "Inconsistentes",
            "inconsistentes",
        ),
    )

    return [
        {
            "label": label,
            "count": _int(
                summary.get(key)
            ),
        }
        for label, key in fields
    ]


def _hour_key(
    value: Any,
) -> str | None:
    if value is None:
        return None

    raw = str(value).strip()

    if not raw:
        return None

    # AWS puede devolver:
    # 2026-08-30 01:00:00.000
    # 2026-08-30T01:00:00-05:00
    # Para comparar actividad solo necesitamos
    # YYYY-MM-DDTHH.
    normalized = raw.replace(" ", "T")

    if len(normalized) >= 13:
        candidate = normalized[:13]

        try:
            datetime.strptime(
                candidate,
                "%Y-%m-%dT%H",
            )

            return candidate
        except ValueError:
            pass

    try:
        parsed = datetime.fromisoformat(
            normalized.replace("Z", "+00:00")
        )

        return parsed.strftime(
            "%Y-%m-%dT%H"
        )

    except ValueError:
        return None


def _replicador_operational_status(
    aws_run: dict[str, Any] | None,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    from datetime import timedelta

    if not aws_run:
        return {
            "status": "WARNING",
            "message":
                "Replicador no tiene ejecuci?n AWS disponible.",
            "missing_hours": [],
        }

    counts: dict[str, int] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue

        hour = _hour_key(
            row.get("hora")
        )

        if hour:
            counts[hour] = (
                counts.get(hour, 0)
                + _int(row.get("count"))
            )

    if not counts:
        return {
            "status": "WARNING",
            "message":
                "Replicador no tiene datos horarios disponibles.",
            "missing_hours": [],
        }

    start_raw = aws_run.get(
        "window_start"
    )

    end_raw = aws_run.get(
        "window_end"
    )

    # Compatibilidad con runs antiguos sin ventana.
    if not start_raw or not end_raw:
        zero_hours = [
            hour
            for hour, count
            in counts.items()
            if count <= 0
        ]

        if zero_hours:
            return {
                "status": "ERROR",
                "message":
                    "Replicador dej? de registrar datos durante al menos una hora.",
                "missing_hours":
                    sorted(zero_hours),
            }

        return {
            "status": "OK",
            "message": None,
            "missing_hours": [],
        }

    try:
        start_dt = datetime.fromisoformat(
            str(start_raw).replace(
                "Z",
                "+00:00",
            )
        )

        end_dt = datetime.fromisoformat(
            str(end_raw).replace(
                "Z",
                "+00:00",
            )
        )

    except ValueError:
        return {
            "status": "WARNING",
            "message":
                "No fue posible interpretar la ventana AWS del Replicador.",
            "missing_hours": [],
        }

    # Primera hora completa.
    current = start_dt.replace(
        minute=0,
        second=0,
        microsecond=0,
    )

    if (
        start_dt.minute
        or start_dt.second
        or start_dt.microsecond
    ):
        current += timedelta(
            hours=1
        )

    missing_hours: list[str] = []

    # Una hora solo se eval?a si su intervalo
    # [HH:00, HH+1:00] est? completamente dentro
    # de la ventana.
    while (
        current
        + timedelta(hours=1)
        <= end_dt
    ):
        key = _hour_key(
            current.isoformat()
        )

        if (
            key is not None
            and counts.get(key, 0) <= 0
        ):
            missing_hours.append(
                current.isoformat()
            )

        current += timedelta(
            hours=1
        )

    if missing_hours:
        return {
            "status": "ERROR",
            "message":
                "Replicador dej? de registrar datos durante al menos una hora.",
            "missing_hours":
                missing_hours,
        }

    return {
        "status": "OK",
        "message": None,
        "missing_hours": [],
    }


@router.get("/today")
def general_today(
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
            "OPERADOR",
            "CONSULTA",
        )
    ),
) -> dict[str, Any]:
    aws = _latest_completed("AWS")
    pasarelas = _latest_completed(
        "PASARELAS"
    )
    hercules = _latest_completed(
        "HERCULES"
    )

    aws_series = _series(aws)
    hercules_summary = _summary(
        hercules
    )
    pasarelas_summary = _summary(
        pasarelas
    )

    tup_610 = _find_pasarelas_41610(
        pasarelas
    )

    tcompensar = (
        _hercules_tcompensar(
            hercules
        )
    )

    servicios_red = (
        _servicios_red_summary(
            aws_series
        )
    )

    mensajeria_exitos = _count_rows(
        aws_series.get(
            "mensajeria_exitos"
        )
    )

    mensajeria_errores = _count_rows(
        aws_series.get(
            "mensajeria_errores"
        )
    )

    otp = _otp_summary(
        aws_series
    )

    pasarelas_verticales = (
        _pasarelas_verticales(
            pasarelas
        )
    )

    replicador_por_hora = []

    aws_window_start = (
        aws.get("window_start")
        if aws
        else None
    )

    aws_window_end = (
        aws.get("window_end")
        if aws
        else None
    )

    try:
        aws_window_start_dt = (
            datetime.fromisoformat(
                str(
                    aws_window_start
                ).replace(
                    "Z",
                    "+00:00",
                )
            )
            if aws_window_start
            else None
        )

        aws_window_end_dt = (
            datetime.fromisoformat(
                str(
                    aws_window_end
                ).replace(
                    "Z",
                    "+00:00",
                )
            )
            if aws_window_end
            else None
        )

    except ValueError:
        aws_window_start_dt = None
        aws_window_end_dt = None

    for row in (
        aws_series.get(
            "replicador_por_hora",
            [],
        )
        or []
    ):
        if not isinstance(row, dict):
            continue

        hora_raw = row.get("hora")

        include = True

        if (
            hora_raw
            and aws_window_start_dt
            and aws_window_end_dt
        ):
            try:
                hora_dt = datetime.fromisoformat(
                    str(
                        hora_raw
                    )
                    .replace(
                        " ",
                        "T",
                    )
                    .replace(
                        "Z",
                        "+00:00",
                    )
                )

                # La serie representa el inicio
                # de cada bloque horario.
                include = (
                    aws_window_start_dt.replace(
                        tzinfo=None
                    )
                    <= hora_dt.replace(
                        tzinfo=None
                    )
                    < aws_window_end_dt.replace(
                        tzinfo=None
                    )
                )

            except ValueError:
                include = False

        if include:
            replicador_por_hora.append(
                {
                    "hora": hora_raw,
                    "count": _int(
                        row.get("count")
                    ),
                }
            )

    replicador_signal = (
        _replicador_operational_status(
            aws,
            replicador_por_hora,
        )
    )

    hercules_distribucion = (
        _hercules_distribution(
            hercules_summary
        )
    )

    correlations = []
    business_alerts = []

    tup_value = tup_610["aprobadas"]
    hercules_value = (
        tcompensar["pago_realizado"]
    )

    delta = tup_value - hercules_value

    if (
        tup_value > 0
        and hercules_value == 0
    ):
        status = "ERROR"
        message = (
            "Hay aprobaciones TUP 610 "
            "pero H?rcules Web/T. Compensar "
            "no registra pagos."
        )
    elif tup_value == 0:
        status = "NO_DATA"
        message = (
            "No hay aprobaciones TUP 610 "
            "para correlacionar."
        )
    else:
        status = "OK"

        if delta == 0:
            message = (
                "TUP 610 y H?rcules "
                "Web/T. Compensar son "
                "consistentes."
            )
        else:
            message = (
                "Existe una diferencia "
                "informativa entre TUP 610 "
                "y H?rcules Web/T. Compensar."
            )

    correlations.append(
        _correlation(
            "TUP610_HERCULES",
            "TUP 610 ? H?rcules Web",
            status,
            message,
            {
                "tup_610_aprobadas":
                    tup_value,
                "hercules_tcompensar":
                    hercules_value,
            },
            delta,
        )
    )

    if status in {
        "ERROR",
        "WARNING",
    }:
        business_alerts.append({
            "id":
                "TUP610_HERCULES",
            "severity": status,
            "title":
                "TUP 610 vs H?rcules",
            "message": message,
            "source":
                "GENERAL_CORRELATION",
        })

    minutos = servicios_red[
        "minutos_sin_actividad"
    ]

    if (
        tup_value > 0
        and minutos is not None
        and minutos > 60
    ):
        sr_status = "ERROR"
        sr_message = (
            "Hay compras TUP 610 y "
            "Servicios Red lleva m?s "
            "de una hora sin "
            "notificaciones."
        )
    elif tup_value == 0:
        sr_status = "NO_DATA"
        sr_message = (
            "No hay compras TUP 610 "
            "para correlacionar con "
            "Servicios Red."
        )
    elif minutos is None:
        sr_status = "NO_DATA"
        sr_message = (
            "Servicios Red no expone "
            "a?n minutos sin actividad "
            "en el resumen seguro."
        )
    else:
        sr_status = "OK"
        sr_message = (
            "Servicios Red mantiene "
            "actividad compatible con "
            "el flujo TUP 610."
        )

    correlations.append(
        _correlation(
            "TUP610_SERVICIOS_RED",
            "TUP 610 ? Servicios Red",
            sr_status,
            sr_message,
            {
                "tup_610_aprobadas":
                    tup_value,
                "servicios_red_total":
                    servicios_red["total"],
                "minutos_sin_actividad":
                    minutos,
            },
            None,
        )
    )

    if sr_status == "ERROR":
        business_alerts.append({
            "id":
                "TUP610_SERVICIOS_RED",
            "severity": "ERROR",
            "title":
                "TUP 610 sin notificaci?n",
            "message": sr_message,
            "source":
                "GENERAL_CORRELATION",
        })

    correlations.append(
        _correlation(
            "TUP610_HERCULES_DELTA",
            (
                "Tarjeta Compensar "
                "Pasarela vs H?rcules"
            ),
            status,
            message,
            {
                "pasarela_tup":
                    tup_value,
                "hercules_tcompensar":
                    hercules_value,
            },
            delta,
        )
    )

    end_status = "OK"

    for value in (
        status,
        sr_status,
        tcompensar["status"],
    ):
        value = str(value).upper()

        if value == "ERROR":
            end_status = "ERROR"
            break

        if (
            value == "WARNING"
            and end_status != "ERROR"
        ):
            end_status = "WARNING"

        if (
            value in {
                "NO_DATA",
                "LEARNING",
            }
            and end_status == "OK"
        ):
            end_status = value

    end_message = (
        "Flujo Tarjeta Compensar "
        "sin hallazgos cr?ticos."
    )

    if end_status == "ERROR":
        end_message = (
            "Se detecta una posible "
            "ruptura en el flujo "
            "Tarjeta Compensar."
        )
    elif end_status == "WARNING":
        end_message = (
            "El flujo Tarjeta Compensar "
            "presenta diferencias para "
            "revisi?n."
        )
    elif end_status in {
        "NO_DATA",
        "LEARNING",
    }:
        end_message = (
            "No hay informaci?n "
            "suficiente para concluir "
            "el estado completo del flujo."
        )

    correlations.append(
        _correlation(
            "FLUJO_TUP_END_TO_END",
            "Flujo Tarjeta Compensar",
            end_status,
            end_message,
            {
                "pasarela_aprobadas":
                    tup_value,
                "servicios_red":
                    servicios_red["total"],
                "hercules_pago_realizado":
                    hercules_value,
                "hercules_checkout":
                    tcompensar["checkout"],
            },
            delta,
        )
    )

    tup_signal_status = (
        _normalize_signal_status(
            tup_610.get("status")
        )
    )

    signal_statuses = {
        "tup_610": {
            "status":
                tup_signal_status,
            "message":
                (
                    tup_610.get("motivo")
                    if tup_signal_status
                    != "OK"
                    else None
                ),
        },

        "servicios_red": {
            "status":
                _normalize_signal_status(
                    sr_status
                ),
            "message":
                (
                    sr_message
                    if sr_status != "OK"
                    else None
                ),
        },

        "mensajeria":
            _count_signal_status(
                ok=mensajeria_exitos,
                errors=mensajeria_errores,
                label="Mensajer?a",
            ),

        "otp":
            _count_signal_status(
                ok=_int(
                    otp.get("exitos")
                ),
                errors=_int(
                    otp.get("errores")
                ),
                label="OTP",
                available=bool(
                    otp.get("available")
                ),
            ),

        "hercules": {
            "status":
                _worst_signal_status([
                    _run_signal_status(
                        hercules
                    ),
                    tcompensar.get(
                        "status"
                    ),
                ]),
            "message":
                None,
        },

        "pasarelas": {
            "status":
                _run_signal_status(
                    pasarelas
                ),
            "message":
                (
                    "Pasarelas requiere revisi?n."
                    if _run_signal_status(
                        pasarelas
                    ) != "OK"
                    else None
                ),
        },

        "replicador": {
            "status":
                replicador_signal[
                    "status"
                ],
            "message":
                replicador_signal[
                    "message"
                ],
        },
    }

    if (
        replicador_signal["status"]
        == "ERROR"
    ):
        business_alerts.append({
            "id":
                "REPLICADOR_SIN_ACTIVIDAD",
            "severity": "ERROR",
            "title":
                "Replicador sin actividad",
            "message":
                replicador_signal[
                    "message"
                ],
            "source": "AWS",
            "values": {
                "missing_hours":
                    replicador_signal[
                        "missing_hours"
                    ],
            },
        })

    general_status = "OK"

    statuses = [
        str(item["status"]).upper()
        for item in correlations
    ]

    statuses.extend(
        item["status"]
        for item
        in signal_statuses.values()
    )

    if "ERROR" in statuses:
        general_status = "ERROR"
    elif "WARNING" in statuses:
        general_status = "WARNING"
    elif "LEARNING" in statuses:
        general_status = "LEARNING"
    elif "NO_DATA" in statuses:
        general_status = "NO_DATA"

    return {
        "summary": {
            "status": general_status,
            "signal_statuses":
                signal_statuses,

            "tup_610_aprobadas":
                tup_610["aprobadas"],
            "tup_610_fallidas":
                tup_610["fallidas"],

            "servicios_red_total":
                servicios_red["total"],
            "servicios_red_ultima_notificacion":
                servicios_red[
                    "ultima_notificacion"
                ],
            "servicios_red_minutos_sin_actividad":
                minutos,

            "mensajeria_exitos":
                mensajeria_exitos,
            "mensajeria_errores":
                mensajeria_errores,

            "otp": otp,

            "hercules_pago_realizado":
                _int(
                    hercules_summary.get(
                        "pago_realizado"
                    )
                ),
            "hercules_checkout":
                _int(
                    hercules_summary.get(
                        "checkout"
                    )
                ),
            "hercules_pendiente_recaudo":
                _int(
                    hercules_summary.get(
                        "pendiente_recaudo"
                    )
                ),

            "hercules_web_tcompensar":
                tcompensar,

            "pasarelas_aprobadas":
                _int(
                    pasarelas_summary.get(
                        "cantidad_ok"
                    )
                ),
            "pasarelas_fallidas":
                _int(
                    pasarelas_summary.get(
                        "cantidad_fallida"
                    )
                ),
        },

        "series": {
            "tup_610": tup_610,

            "pasarelas_verticales":
                pasarelas_verticales,

            "replicador_por_hora":
                replicador_por_hora,

            "hercules_distribucion":
                hercules_distribucion,

            "tup_aws_por_hora":
                aws_series.get(
                    "tup_por_hora",
                    [],
                ),

            "servicios_red_por_hora":
                aws_series.get(
                    "serviciosred_por_hora",
                    [],
                ),

            "servicios_red_10m":
                aws_series.get(
                    "serviciosred_10m_ultima_hora",
                    [],
                ),

            "mensajeria_errores_por_hora":
                aws_series.get(
                    "mensajeria_errores_por_hora",
                    [],
                ),

            "hercules_web_tcompensar":
                tcompensar,

            "hercules_estados": {
                "pago_realizado":
                    _int(
                        hercules_summary.get(
                            "pago_realizado"
                        )
                    ),
                "checkout":
                    _int(
                        hercules_summary.get(
                            "checkout"
                        )
                    ),
                "pendiente_recaudo":
                    _int(
                        hercules_summary.get(
                            "pendiente_recaudo"
                        )
                    ),
            },

            "pasarelas_creditos":
                _series(
                    pasarelas
                ).get(
                    "creditos_zoom",
                    [],
                ),
        },

        "correlations": correlations,
        "business_alerts":
            business_alerts,

        "sources": {
            "aws_run_id":
                aws.get("run_id")
                if aws else None,
            "pasarelas_run_id":
                pasarelas.get("run_id")
                if pasarelas else None,
            "hercules_run_id":
                hercules.get("run_id")
                if hercules else None,
        },

        "generated_at":
            datetime.now().isoformat(),
    }



def _month_monitor_map(
    closures: list[dict[str, Any]],
    monitor: str,
) -> dict[str, dict[str, Any]]:
    key = monitor.upper()

    return {
        str(item.get("closure_date")):
            item
        for item in closures
        if str(
            item.get("monitor", "")
        ).upper() == key
    }


def _closure_kpis(
    item: dict[str, Any] | None,
) -> dict[str, Any]:
    if not item:
        return {}

    snapshot = item.get("snapshot") or {}

    if not isinstance(snapshot, dict):
        return {}

    value = snapshot.get("kpis") or {}

    return (
        value
        if isinstance(value, dict)
        else {}
    )


def _executed(
    item: dict[str, Any] | None,
) -> bool:
    if not item:
        return False

    return str(
        item.get("coverage_status")
        or "SIN_EJECUCION"
    ).upper() == "EXECUTED"


def _coverage(
    item: dict[str, Any] | None,
) -> str:
    if not item:
        return "SIN_EJECUCION"

    return str(
        item.get("coverage_status")
        or "SIN_EJECUCION"
    )


def _daily_general_status(
    *,
    pasarelas:
        dict[str, Any] | None,
    aws:
        dict[str, Any] | None,
    hercules:
        dict[str, Any] | None,
    tup_aprobadas: int,
    hercules_tcompensar: int,
) -> tuple[str, str]:

    executed_pasarelas = _executed(
        pasarelas
    )
    executed_aws = _executed(aws)
    executed_hercules = _executed(
        hercules
    )

    if not any(
        (
            executed_pasarelas,
            executed_aws,
            executed_hercules,
        )
    ):
        return (
            "SIN_EJECUCION",
            "Sin ejecuciones oficiales "
            "registradas para el d?a.",
        )

    missing = []

    if not executed_pasarelas:
        missing.append("Pasarelas")

    if not executed_aws:
        missing.append("AWS")

    if not executed_hercules:
        missing.append("H?rcules")

    if missing:
        return (
            "NO_DATA",
            (
                "Cobertura incompleta: "
                + ", ".join(missing)
                + "."
            ),
        )

    if (
        tup_aprobadas > 0
        and hercules_tcompensar == 0
    ):
        return (
            "ERROR",
            "Hay aprobaciones TUP 610 "
            "pero H?rcules Web/T. "
            "Compensar registra 0.",
        )

    return (
        "OK",
        "Sin hallazgos cr?ticos en "
        "la correlaci?n diaria.",
    )


@router.get("/month")
def general_month(
    year: int,
    month: int,
    user: dict = Depends(
        require_roles(
            "ADMIN",
            "MONITOR_OFICIAL",
            "OPERADOR",
            "CONSULTA",
        )
    ),
) -> dict[str, Any]:

    if year < 2000 or year > 2100:
        return {
            "error": "year fuera de rango"
        }

    if month < 1 or month > 12:
        return {
            "error": "month debe estar entre 1 y 12"
        }

    _, last_day = calendar.monthrange(
        year,
        month,
    )

    start_date = (
        f"{year:04d}-{month:02d}-01"
    )

    end_date = (
        f"{year:04d}-{month:02d}-"
        f"{last_day:02d}"
    )

    closures = list_daily_closures(
        start_date=start_date,
        end_date=end_date,
    )

    aws_map = _month_monitor_map(
        closures,
        "AWS",
    )

    pasarelas_map = _month_monitor_map(
        closures,
        "PASARELAS",
    )

    hercules_map = _month_monitor_map(
        closures,
        "HERCULES",
    )

    tup_610_daily = []
    servicios_red_daily = []
    mensajeria_daily = []
    otp_daily = []
    hercules_daily = []
    pasarelas_daily = []
    delta_daily = []
    correlations_daily = []
    coverage_daily = []

    status_totals = {
        "OK": 0,
        "WARNING": 0,
        "ERROR": 0,
        "NO_DATA": 0,
        "SIN_EJECUCION": 0,
    }

    days_with_execution = 0

    for day in range(
        1,
        last_day + 1,
    ):
        current_date = (
            f"{year:04d}-"
            f"{month:02d}-"
            f"{day:02d}"
        )

        aws_item = aws_map.get(
            current_date
        )

        pasarelas_item = (
            pasarelas_map.get(
                current_date
            )
        )

        hercules_item = (
            hercules_map.get(
                current_date
            )
        )

        aws_kpis = _closure_kpis(
            aws_item
        )

        pasarelas_kpis = (
            _closure_kpis(
                pasarelas_item
            )
        )

        hercules_kpis = (
            _closure_kpis(
                hercules_item
            )
        )

        tup = (
            pasarelas_kpis.get(
                "tup_610"
            )
            or {}
        )

        servicios_red = (
            aws_kpis.get(
                "servicios_red"
            )
            or {}
        )

        mensajeria = (
            aws_kpis.get(
                "mensajeria"
            )
            or {}
        )

        otp = (
            aws_kpis.get("otp")
            or {}
        )

        web_tcompensar = (
            hercules_kpis.get(
                "web_tcompensar"
            )
            or {}
        )

        tup_ok = _int(
            tup.get("aprobadas")
        )

        hercules_tup = _int(
            web_tcompensar.get(
                "pago_realizado"
            )
        )

        delta = (
            tup_ok
            - hercules_tup
        )

        day_status, message = (
            _daily_general_status(
                pasarelas=
                    pasarelas_item,
                aws=aws_item,
                hercules=
                    hercules_item,
                tup_aprobadas=tup_ok,
                hercules_tcompensar=
                    hercules_tup,
            )
        )

        status_totals.setdefault(
            day_status,
            0,
        )

        status_totals[
            day_status
        ] += 1

        if any(
            (
                _executed(aws_item),
                _executed(
                    pasarelas_item
                ),
                _executed(
                    hercules_item
                ),
            )
        ):
            days_with_execution += 1

        tup_610_daily.append({
            "date": current_date,
            "aprobadas": tup_ok,
            "fallidas": _int(
                tup.get("fallidas")
            ),
            "total": _int(
                tup.get("total")
            ),
            "status": (
                tup.get("status")
                or (
                    "SIN_EJECUCION"
                    if not pasarelas_item
                    else "NO_DATA"
                )
            ),
        })

        servicios_red_daily.append({
            "date": current_date,
            "total": _int(
                servicios_red.get(
                    "total"
                )
            ),
            "ultima_notificacion":
                servicios_red.get(
                    "ultima_notificacion"
                ),
            "coverage":
                _coverage(aws_item),
        })

        mensajeria_daily.append({
            "date": current_date,
            "exitos": _int(
                mensajeria.get(
                    "exitos"
                )
            ),
            "errores": _int(
                mensajeria.get(
                    "errores"
                )
            ),
            "coverage":
                _coverage(aws_item),
        })

        otp_daily.append({
            "date": current_date,
            "available": bool(
                otp.get("available")
            ),
            "exitos": _int(
                otp.get("exitos")
            ),
            "errores": _int(
                otp.get("errores")
            ),
            "total": _int(
                otp.get("total")
            ),
            "coverage":
                _coverage(aws_item),
        })

        hercules_daily.append({
            "date": current_date,
            "pago_realizado": _int(
                hercules_kpis.get(
                    "pago_realizado"
                )
            ),
            "checkout": _int(
                hercules_kpis.get(
                    "checkout"
                )
            ),
            "pendiente_recaudo":
                _int(
                    hercules_kpis.get(
                        "pendiente_recaudo"
                    )
                ),
            "web_tcompensar": {
                "pago_realizado":
                    hercules_tup,
                "checkout": _int(
                    web_tcompensar.get(
                        "checkout"
                    )
                ),
                "pendiente_recaudo":
                    _int(
                        web_tcompensar.get(
                            "pendiente_recaudo"
                        )
                    ),
                "pago_pendiente":
                    _int(
                        web_tcompensar.get(
                            "pago_pendiente"
                        )
                    ),
                "status":
                    web_tcompensar.get(
                        "status"
                    )
                    or (
                        "SIN_EJECUCION"
                        if not hercules_item
                        else "NO_DATA"
                    ),
            },
            "coverage":
                _coverage(
                    hercules_item
                ),
        })

        pasarelas_daily.append({
            "date": current_date,
            "aprobadas": _int(
                pasarelas_kpis.get(
                    "aprobadas"
                )
            ),
            "fallidas": _int(
                pasarelas_kpis.get(
                    "fallidas"
                )
            ),
            "coverage":
                _coverage(
                    pasarelas_item
                ),
        })

        delta_daily.append({
            "date": current_date,
            "tup_610_aprobadas":
                tup_ok,
            "hercules_tcompensar":
                hercules_tup,
            "delta": delta,
            "status": day_status,
        })

        correlations_daily.append({
            "date": current_date,
            "id":
                "TUP610_HERCULES",
            "name":
                "TUP 610 -> H?rcules Web",
            "status": day_status,
            "message": message,
            "values": {
                "tup_610_aprobadas":
                    tup_ok,
                "hercules_tcompensar":
                    hercules_tup,
            },
            "delta": delta,
        })

        coverage_daily.append({
            "date": current_date,
            "aws": _coverage(
                aws_item
            ),
            "pasarelas": _coverage(
                pasarelas_item
            ),
            "hercules": _coverage(
                hercules_item
            ),
        })

    return {
        "period": {
            "year": year,
            "month": month,
            "start_date": start_date,
            "end_date": end_date,
            "days": last_day,
        },

        "summary": {
            "days_with_execution":
                days_with_execution,
            "status_totals":
                status_totals,
        },

        "series": {
            "tup_610_daily":
                tup_610_daily,
            "servicios_red_daily":
                servicios_red_daily,
            "mensajeria_daily":
                mensajeria_daily,
            "otp_daily":
                otp_daily,
            "hercules_daily":
                hercules_daily,
            "pasarelas_daily":
                pasarelas_daily,
            "tup_hercules_delta_daily":
                delta_daily,
        },

        "correlations_daily":
            correlations_daily,

        "coverage_daily":
            coverage_daily,

        "generated_at":
            datetime.now().isoformat(),
    }
