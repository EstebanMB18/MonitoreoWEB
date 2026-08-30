from __future__ import annotations

from monitoreo_aws.core.aws import contar, crear_cliente, ejecutar_query
from monitoreo_aws.services.queries import COUNT_QUERIES, DETAIL_QUERIES


def recolectar(cfg: dict, ventana) -> dict:
    region = cfg["app"]["region"]
    profiles = cfg["profiles"]
    groups = cfg["services"]
    clientes = {
        "interopprod": crear_cliente(profiles["interopprod"], region),
        "cscprod": crear_cliente(profiles["cscprod"], region),
        "corporativoprod": crear_cliente(profiles["corporativoprod"], region),
    }
    i, c, p = clientes["interopprod"], clientes["cscprod"], clientes["corporativoprod"]
    ini, fin = ventana.inicio, ventana.fin
    result = {"metricas": {}, "detalles": {}, "errores_consulta": []}

    jobs = [
        # INTEROPPROD
        *((key, i, groups["interopprod"]["apiorqpagos"]) for key in [
            "aprob_creacion_payu", "aprob_creacion_ecollect", "aprob_estado_payu",
            "aprob_estado_ecollect", "aprob_receiver", "err_creacion_payu",
            "err_creacion_ecollect", "err_estado_payu", "err_estado_ecollect",
            "err_receiver", "err_log", "err_mongodb_update"
        ]),
        ("seg_consulta_persona", i, groups["interopprod"]["apimoduloseguridad"]),
        ("error_cx", i, groups["interopprod"]["apisubsidios"]),
        ("tup_error", i, groups["interopprod"]["tarjetatup"]),
        ("serviciosred_total", i, groups["interopprod"]["serviciosred"]),
        # CSC
        ("csc_task_timed", c, groups["cscprod"]["apiorqpagos_proxy"]),
        ("csc_504", c, groups["cscprod"]["apiorqpagos_proxy"]),
        # Mensajería (el perfil corporativo es el que contiene actualmente los log groups)
        *((key, p, groups["corporativoprod"]["apimensajeria"]) for key in [
            "mens_timeout", "mens_503", "mens_502", "mens_report", "mens_cannot",
            "mens_sms_failed", "mens_error_400_total", "mens_exitos_200_total", "otp_408"
        ]),
        ("replicador", p, groups["corporativoprod"]["replicador"]),
        ("otp_500", p, groups["corporativoprod"]["validarotp"]),
    ]

    for key, client, group in jobs:
        try:
            print(f"  - {key}")
            result["metricas"][key] = contar(client, group, COUNT_QUERIES[key], ini, fin)
        except Exception as exc:
            result["metricas"][key] = None
            result["errores_consulta"].append(f"{key}: {exc}")

    # Total sent corresponde únicamente a los REPORT de Lambda, no se suma Request Received.
    result["metricas"]["mens_total_send"] = result["metricas"].get("mens_report")

    detail_jobs = [
        ("consulta_persona", i, groups["interopprod"]["apimoduloseguridad"]),
        ("mensajeria_errores", p, groups["corporativoprod"]["apimensajeria"]),
        ("mensajeria_exitos", p, groups["corporativoprod"]["apimensajeria"]),
        ("mensajeria_400_por_hora", p, groups["corporativoprod"]["apimensajeria"]),
        ("mensajeria_errores_por_hora", p, groups["corporativoprod"]["apimensajeria"]),
        ("mensajeria_200_por_hora", p, groups["corporativoprod"]["apimensajeria"]),
        ("tup_por_hora", i, groups["interopprod"]["tarjetatup"]),
        ("tup_total_por_hora", i, groups["interopprod"]["tarjetatup"]),
        ("tup_resumen", i, groups["interopprod"]["tarjetatup"]),
        ("pagos_errores_por_hora", i, groups["interopprod"]["apiorqpagos"]),
        ("replicador_por_hora", p, groups["corporativoprod"]["replicador"]),
        ("serviciosred_resumen", i, groups["interopprod"]["serviciosred"]),
        ("serviciosred_por_hora", i, groups["interopprod"]["serviciosred"]),
    ]
    for key, client, group in detail_jobs:
        try:
            result["detalles"][key] = ejecutar_query(client, group, DETAIL_QUERIES[key], ini, fin)
        except Exception as exc:
            result["detalles"][key] = []
            result["errores_consulta"].append(f"{key}: {exc}")

    # Servicios Red: además del rango completo, siempre se revisa la última hora
    # del periodo seleccionado. En una ejecución actual equivale a "últimos 60 min".
    try:
        from datetime import timedelta
        sr_ini = max(ini, fin - timedelta(minutes=60))
        sr_rows = ejecutar_query(
            i,
            groups["interopprod"]["serviciosred"],
            DETAIL_QUERIES["serviciosred_resumen"],
            sr_ini,
            fin,
        )
        sr = sr_rows[0] if sr_rows else {}
        try:
            sr_count = int(float(sr.get("count", 0) or 0))
        except (TypeError, ValueError):
            sr_count = 0
        result["metricas"]["serviciosred_ultima_hora"] = sr_count
        result["detalles"]["serviciosred_ultima_hora"] = [{
            "count": sr_count,
            "ultima_notificacion": sr.get("ultima_notificacion", ""),
            "desde": sr_ini.isoformat(),
            "hasta": fin.isoformat(),
        }]
        try:
            result["detalles"]["serviciosred_10m_ultima_hora"] = ejecutar_query(
                i,
                groups["interopprod"]["serviciosred"],
                DETAIL_QUERIES["serviciosred_10m"],
                sr_ini,
                fin,
            )
        except Exception as exc_10:
            result["detalles"]["serviciosred_10m_ultima_hora"] = []
            result["errores_consulta"].append(f"serviciosred_10m_ultima_hora: {exc_10}")
    except Exception as exc:
        result["metricas"]["serviciosred_ultima_hora"] = None
        result["detalles"]["serviciosred_ultima_hora"] = []
        result["detalles"]["serviciosred_10m_ultima_hora"] = []
        result["errores_consulta"].append(f"serviciosred_ultima_hora: {exc}")

    # Tarjeta TUP: agregados de los ultimos 60 minutos.
    # Solo se conservan buckets numericos; no payloads crudos.
    try:
        from datetime import timedelta

        tup_ini = max(
            ini,
            fin - timedelta(minutes=60),
        )

        result["detalles"]["tup_total_10m_ultima_hora"] = (
            ejecutar_query(
                i,
                groups["interopprod"]["tarjetatup"],
                DETAIL_QUERIES["tup_total_10m"],
                tup_ini,
                fin,
            )
        )

        result["detalles"]["tup_errores_10m_ultima_hora"] = (
            ejecutar_query(
                i,
                groups["interopprod"]["tarjetatup"],
                DETAIL_QUERIES["tup_errores_10m"],
                tup_ini,
                fin,
            )
        )

    except Exception as exc:
        result["detalles"][
            "tup_total_10m_ultima_hora"
        ] = []

        result["detalles"][
            "tup_errores_10m_ultima_hora"
        ] = []

        result["errores_consulta"].append(
            f"tup_10m_ultima_hora: {exc}"
        )


    return result
