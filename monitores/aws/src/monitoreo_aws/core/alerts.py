from __future__ import annotations


def _num(value) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _hora_pico(rows: list[dict]) -> tuple[int, str]:
    if not rows:
        return 0, ""
    peak = max(rows, key=lambda r: _num(r.get("count")))
    return _num(peak.get("count")), str(peak.get("hora", ""))


def evaluar(cfg: dict, ventana, data: dict) -> list[dict]:
    m, d = data["metricas"], data["detalles"]
    t = cfg["thresholds"]
    alerts: list[dict] = []

    def add(nivel, grupo, servicio, metrica, valor, detalle):
        alerts.append({
            "nivel": nivel,
            "grupo": grupo,
            "servicio": servicio,
            "metrica": metrica,
            "valor": valor,
            "detalle": detalle,
        })

    # Replicador
    if m.get("replicador") is None:
        add("CRÍTICA", "MENSAJERÍA", "Replicador", "Consulta sin resultado", "N/D", "No fue posible consultar el servicio.")
    elif _num(m.get("replicador")) < t["replicador"]["minimo_replicaciones"]:
        add("CRÍTICA", "MENSAJERÍA", "Replicador", "Sin replicaciones", 0,
            f"No se registró ninguna replicación desde {ventana.inicio:%Y-%m-%d %H:%M} hasta {ventana.fin:%Y-%m-%d %H:%M}.")

    # Tarjeta TUP
    tup = _num(m.get("tup_error"))
    pico, hora = _hora_pico(d.get("tup_por_hora", []))
    if tup >= t["tarjeta_tup"]["preocupante_desde"]:
        add("CRÍTICA", "INTEROPPROD", "Tarjeta TUP", "Errores", tup,
            f"ALERTA CRÍTICA: {tup} errores de consumo TUP. Supera 250; pico de {pico} errores en {hora or 'franja no disponible'}.")
    elif tup > t["tarjeta_tup"]["regular_max"]:
        add("ALTA", "INTEROPPROD", "Tarjeta TUP", "Errores", tup,
            f"Nivel de atención (201–250). Pico de {pico} errores en {hora or 'franja no disponible'}.")
    elif tup > t["tarjeta_tup"]["normal_max"]:
        add("MEDIA", "INTEROPPROD", "Tarjeta TUP", "Errores", tup,
            f"Nivel regular (31–200). Pico de {pico} errores en {hora or 'franja no disponible'}.")

    # API pagos: solo errores operativos definidos, no todos los logs Error.
    payment_keys = ("err_creacion_payu", "err_creacion_ecollect", "err_estado_payu", "err_estado_ecollect", "err_receiver")
    pagos_errors = sum(_num(m.get(k)) for k in payment_keys)
    pico_pago, hp = _hora_pico(d.get("pagos_errores_por_hora", []))
    if pagos_errors >= t["api_pagos"]["errores_preocupantes_desde"]:
        add("CRÍTICA", "INTEROPPROD", "API Orquestador Pagos", "Errores operativos", pagos_errors,
            f"Supera el umbral de 40 errores. Pico de {pico_pago} en {hp or 'franja no disponible'}.")

    # Sin información aprobada en creación o estado.
    for nombre, keys in {
        "Creación": ("aprob_creacion_payu", "aprob_creacion_ecollect"),
        "Estado": ("aprob_estado_payu", "aprob_estado_ecollect"),
    }.items():
        vals = [m.get(k) for k in keys]
        if all(v is not None for v in vals) and sum(_num(v) for v in vals) == 0:
            add("CRÍTICA", "INTEROPPROD", "API Orquestador Pagos", f"Sin información en {nombre}", 0,
                f"No hubo registros aprobados de {nombre.lower()} durante {ventana.texto}.")

    # MongoDB
    mongo = _num(m.get("err_mongodb_update"))
    if mongo >= t["mongodb"]["errores_alarmantes_desde"]:
        add("CRÍTICA", "INTEROPPROD", "MongoDB", "Error Update MongoDB", mongo,
            "Supera el umbral alarmante de 10 errores.")

    # Mensajería: un mismo dato/error 400 por encima de 100.
    for row in d.get("mensajeria_errores", []):
        code = str(row.get("Httpcode", ""))
        count = _num(row.get("count"))
        if code == "400" and count >= t["mensajeria"]["error_400_mismo_dato_desde"]:
            dato = row.get("MessageOut.error") or row.get("MessageOut") or "Error 400 sin tipología"
            broker = row.get("MessageIn.configS3.Broker") or "N/D"
            operacion = row.get("OperationInvokerName") or "N/D"
            add("CRÍTICA", "MENSAJERÍA", "API Mensajería", "Error 400 repetitivo", count,
                f"Broker {broker}; operación {operacion}; {dato}. Desde {row.get('desde','N/D')} hasta {row.get('hasta','N/D')}.")

    for error in data.get("errores_consulta", []):
        add("ALTA", "TÉCNICO", "Consulta AWS", "Consulta incompleta", "N/D", error)

    order = {"CRÍTICA": 0, "ALTA": 1, "MEDIA": 2, "INFORMATIVA": 3}
    return sorted(alerts, key=lambda a: order.get(a["nivel"], 9))
