from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter

from api.runtime import list_runs


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


@router.get("/today")
def general_today() -> dict[str, Any]:
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

    general_status = "OK"

    statuses = [
        str(item["status"]).upper()
        for item in correlations
    ]

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
