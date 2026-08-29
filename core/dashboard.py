# SPRINT_13_8_CRITICAL_RULES_AND_FRESHNESS_OK
# HOTFIX_13_5_4_SERVICIOS_RED_GENERAL_OK
from __future__ import annotations

import html
import json
import math
from datetime import datetime
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

ORANGE = "#F26B1D"
ORANGE_2 = "#FF9254"
BLUE = "#0B5CAB"
NAVY = "#16324A"
GREEN = "#14834A"
YELLOW = "#A16A00"
RED = "#C93636"


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _esc(value) -> str:
    return html.escape("" if value is None else str(value))


def _num(value) -> int:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return 0
        return int(float(value))
    except Exception:
        return 0


def _flt(value) -> float:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _fmt_num(value) -> str:
    return f"{_num(value):,}".replace(",", ".")


def _fmt_prom(value) -> str:
    return f"{_flt(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pill(state: str) -> str:
    s = str(state or "SIN INFORMACIÓN").upper()
    if "ALERTA" in s or "ERROR" in s or "CRIT" in s:
        cls = "bad"
    elif "BAJA" in s or "REVIS" in s or "REGULAR" in s or "SEGU" in s or "APREND" in s:
        cls = "warn"
    elif "NORMAL" in s or s in {"OK", "OPERACIÓN", "OPERACION"}:
        cls = "ok"
    else:
        cls = "neutral"
    return f"<span class='status {cls}'><i class='dot'></i>{_esc(s.title())}</span>"


def _semaforo(state: str) -> str:
    s = str(state or 'SIN INFORMACIÓN').upper()
    if 'ALERTA' in s or 'ERROR' in s or 'CRIT' in s:
        cls, label = 'bad', 'Alerta'
    elif 'BAJA' in s or 'REVIS' in s or 'REGULAR' in s or 'SEGU' in s:
        cls, label = 'warn', 'Revisar'
    elif 'NORMAL' in s or s == 'OK':
        cls, label = 'ok', 'Normal'
    else:
        cls, label = 'neutral', 'Sin dato'
    return f"<span class='traffic {cls}' title='{_esc(label)}'></span><span class='traffic-label'>{_esc(label)}</span>"


def _is_weekend_or_holiday(root: Path, now: datetime) -> tuple[bool, str]:
    if now.weekday() >= 5:
        return True, "FIN DE SEMANA"
    holiday_file = root / "GENERAL" / "calendario_festivos.txt"
    if holiday_file.exists():
        try:
            days = {
                x.strip()
                for x in holiday_file.read_text(encoding="utf-8-sig").splitlines()
                if x.strip() and not x.lstrip().startswith("#")
            }
            if now.strftime("%Y-%m-%d") in days:
                return True, "FESTIVO"
        except Exception:
            pass
    return False, "ENTRE SEMANA"


def _fresh_file(path: Path, fresh_after=None, tolerance_seconds: int = 5) -> bool:
    """True si el archivo pertenece a la ejecución actual o no se pidió control."""
    if not path.exists():
        return False
    if fresh_after is None:
        return True

    try:
        cutoff = fresh_after.timestamp() if hasattr(fresh_after, "timestamp") else float(fresh_after)
        return path.stat().st_mtime >= (cutoff - tolerance_seconds)
    except Exception:
        return False


def _freshness_label(path: Path, fresh_after=None) -> str:
    if not path.exists():
        return "NO EXISTE"
    if fresh_after is None:
        return "OK"
    return "OK" if _fresh_file(path, fresh_after) else "ARCHIVO ANTERIOR"




# -----------------------------------------------------------------------------
# Pasarelas
# -----------------------------------------------------------------------------

def _load_pasarelas(root: Path, fresh_after=None) -> pd.DataFrame:
    candidates = [
        root / "ECOLLECT" / "resumen_verticales_diario.xlsx",
        root / "ECOLLECT" / "resumen_verticales_ultimo.xlsx",
    ]
    for path in candidates:
        if _fresh_file(path, fresh_after):
            try:
                df = pd.read_excel(path)
                if not df.empty:
                    for col in ["vertical", "codigo", "medio_salida", "promedio", "cantidad_ok", "estado"]:
                        if col not in df.columns:
                            if col in ("promedio", "cantidad_ok"):
                                df[col] = 0
                            else:
                                df[col] = ""
                    return df
            except Exception:
                continue
    return pd.DataFrame(columns=["vertical", "codigo", "medio_salida", "promedio", "cantidad_ok", "estado"])


def _is_41610_group(df: pd.DataFrame) -> bool:
    if df.empty or "codigo" not in df.columns:
        return False
    codes = df["codigo"].astype(str).str.replace(".0", "", regex=False)
    return (codes == "41610").any()


def _tup_41610_ok(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    work = df.copy()
    work["codigo"] = work["codigo"].astype(str).str.replace(".0", "", regex=False)
    tup = work[
        (work["codigo"] == "41610")
        & (work["medio_salida"].astype(str).str.upper() == "TUP")
    ]
    if tup.empty:
        return 0
    return int(pd.to_numeric(tup["cantidad_ok"], errors="coerce").fillna(0).sum())


def _critical_pasarelas_alerts(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []

    work = df.copy()
    work["codigo"] = work["codigo"].astype(str).str.replace(".0", "", regex=False)

    if not (work["codigo"] == "41610").any():
        return []

    tup_ok = _tup_41610_ok(work)
    if tup_ok == 0:
        return [{
            "nivel": "ALERTA",
            "titulo": "41610 RED TIENDA · TUP sin aprobaciones",
            "detalle": (
                "No se detectaron pagos TUP aprobados en 41610 RED TIENDA. "
                "Para esta vertical, TUP en cero es una condición de alarma."
            ),
        }]

    return []


def _pas_state(df: pd.DataFrame) -> str:
    if df.empty:
        return "SIN INFORMACIÓN"

    # Regla crítica: si el grupo contiene 41610 y no hay TUP OK, toda la
    # tarjeta/vertical debe quedar en ALERTA aunque PSE/Tarjeta Crédito tengan datos.
    if _is_41610_group(df) and _tup_41610_ok(df) == 0:
        return "ALERTA"

    states = df["estado"].astype(str).str.upper()
    if states.str.contains("ALERTA|ERROR", regex=True).any():
        return "ALERTA"
    if states.str.contains("BAJA|REVIS|REGULAR", regex=True).any():
        return "REVISAR"
    return "NORMALIDAD"


def _vertical_cards(df: pd.DataFrame, codes: list[str] | None = None, max_cards: int | None = None) -> str:
    if df.empty:
        return "<div class='empty'>Sin información de Pasarelas para el corte.</div>"
    work = df.copy()
    work["codigo"] = work["codigo"].astype(str).str.replace(".0", "", regex=False)
    if codes:
        work = work[work["codigo"].isin([str(x) for x in codes])]
    groups = list(work.groupby(["codigo", "vertical"], sort=False))
    if max_cards:
        groups = groups[:max_cards]
    cards = []
    for (code, vertical), g in groups:
        state = _pas_state(g)
        lines = []
        for r in g.itertuples(index=False):
            medio = getattr(r, "medio_salida", "")
            prom = getattr(r, "promedio", 0)
            actual = getattr(r, "cantidad_ok", 0)
            est = getattr(r, "estado", "")
            lines.append(
                "<div class='metric-line'>"
                f"<b>{_esc(medio)}</b>"
                f"<span>Prom. {_fmt_prom(prom)}</span>"
                f"<span>{_fmt_num(actual)}</span>"
                f"<span>{_esc(str(est).title())}</span>"
                "</div>"
            )
        cards.append(
            "<div class='vert'>"
            "<div class='vert-top'>"
            f"<div><div class='vert-name'>{_esc(vertical)}</div><div class='vert-code'>{_esc(code)}</div></div>"
            f"<div class='traffic-wrap'>{_semaforo(state)}</div>"
            "</div>"
            + "".join(lines)
            + "</div>"
        )
    if not cards:
        return "<div class='empty'>No hay verticales configuradas para esta vista.</div>"
    return "<div class='vert-grid'>" + "".join(cards) + "</div>"


def _pas_zoom(df: pd.DataFrame) -> str:
    if df.empty:
        return "<div class='empty'>Sin información.</div>"
    work = df.copy()
    work["codigo"] = work["codigo"].astype(str).str.replace(".0", "", regex=False)
    wanted = work[work["codigo"].isin(["41605", "41607", "41612", "41610", "41621"])]
    if wanted.empty:
        wanted = work.head(20)
    return _vertical_cards(wanted)


# -----------------------------------------------------------------------------
# AWS
# -----------------------------------------------------------------------------

def _load_aws(root: Path, fresh_after=None) -> dict:
    path = root / "GENERAL" / "data" / "aws_gerencial.json"
    if not _fresh_file(path, fresh_after):
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _aws_metric(aws: dict, key: str):
    return (aws.get("metricas") or {}).get(key)



def _aws_tup_state(aws: dict) -> tuple[str, str]:
    value = _aws_metric(aws, "tup_error")
    if value is None:
        return "SIN INFORMACIÓN", "No fue posible consultar Tarjeta TUP."
    try:
        n = int(float(value))
    except Exception:
        return "SIN INFORMACIÓN", "El valor de errores TUP no es válido."
    if n >= 251:
        return "ALERTA", f"{n:,} errores de consumo TUP; supera el umbral crítico de 250.".replace(",", ".")
    if n >= 201:
        return "ALERTA", f"{n:,} errores de consumo TUP; nivel de atención 201–250.".replace(",", ".")
    if n >= 31:
        return "REVISAR", f"{n:,} errores de consumo TUP; supera el rango normal de 0–30.".replace(",", ".")
    return "NORMALIDAD", f"{n} errores de consumo TUP; dentro del rango normal 0–30."


def _aws_alert_text(aws: dict) -> str:
    try:
        return json.dumps(aws.get("alertas", []), ensure_ascii=False).upper()
    except Exception:
        return str(aws.get("alertas", [])).upper()


def _aws_state(aws: dict, keywords: list[str] | None = None) -> str:
    if not aws:
        return "SIN INFORMACIÓN"

    text = _aws_alert_text(aws)
    if keywords:
        if any(k.upper() in text for k in keywords):
            return "REVISAR"
        # Tarjeta TUP se evalúa por umbral aunque el JSON de alertas venga incompleto.
        joined = " ".join(keywords).upper()
        if "TUP" in joined:
            return _aws_tup_state(aws)[0]
        return "NORMALIDAD"

    tup_state, _ = _aws_tup_state(aws)
    if tup_state == "ALERTA":
        return "ALERTA"

    alerts = aws.get("alertas") or []
    if alerts:
        levels = {str(a.get("nivel", "")).upper() for a in alerts if isinstance(a, dict)}
        if levels & {"CRÍTICA", "CRITICA", "ALTA"}:
            return "ALERTA"
        return "REVISAR"

    if tup_state == "REVISAR":
        return "REVISAR"
    return "NORMALIDAD"


def _aws_payment_table(aws: dict, errors: bool = False) -> str:
    if not aws:
        return "<div class='empty'>AWS aún no ha publicado datos gerenciales. Ejecuta AWS una vez después de instalar el Sprint 12.</div>"
    if not errors:
        rows = [
            ("Creación de pago · PayU", "aprob_creacion_payu"),
            ("Creación de pago · eCollect", "aprob_creacion_ecollect"),
            ("Estado transacciones · PayU", "aprob_estado_payu"),
            ("Estado transacciones · eCollect", "aprob_estado_ecollect"),
            ("Notificación al BUS · Receiver", "aprob_receiver"),
        ]
    else:
        rows = [
            ("Creación de pago · PayU", "err_creacion_payu"),
            ("Creación de pago · eCollect", "err_creacion_ecollect"),
            ("Estado transacciones · PayU", "err_estado_payu"),
            ("Estado transacciones · eCollect", "err_estado_ecollect"),
            ("Notificación al BUS · Receiver", "err_receiver"),
            ("Log level · Error", "err_log"),
            ("MongoDB update", "err_mongodb_update"),
        ]
    out = ["<div class='table-like'><div class='table-head'><span>Seguimiento</span><span></span><span>Cantidad</span><span class='estado'>Estado</span></div>"]
    for label, key in rows:
        value = _aws_metric(aws, key)
        state = _aws_state(aws, [key, label])
        out.append(
            "<div class='table-row'>"
            f"<span><b>{_esc(label)}</b></span><span></span>"
            f"<span>{'—' if value is None else _fmt_num(value)}</span>"
            f"<span class='estado'>{_esc(state.title())}</span>"
            "</div>"
        )
    out.append("</div>")
    return "".join(out)


def _aws_lambda_table(aws: dict) -> str:
    if not aws:
        return "<div class='empty'>Sin información AWS.</div>"
    rows = [
        ("Task timed · CSC", "csc_task_timed"),
        ("504 Gateway Time-out · CSC", "csc_504"),
        ("OTP Error 500", "otp_500"),
        ("OTP Error 408", "otp_408"),
        ("API Subsidios · ERROR CX", "error_cx"),
        ("Tarjeta TUP · Error consumo", "tup_error"),
    ]
    out = ["<div class='table-like'><div class='table-head'><span>Control</span><span></span><span>Cantidad</span><span class='estado'>Estado</span></div>"]
    for label, key in rows:
        value = _aws_metric(aws, key)
        if key == "tup_error":
            state, reason = _aws_tup_state(aws)
        else:
            state = _aws_state(aws, [key, label])
            reason = ""
        title = f" title='{_esc(reason)}'" if reason else ""
        out.append(
            "<div class='table-row'>"
            f"<span><b>{_esc(label)}</b></span><span></span>"
            f"<span>{'—' if value is None else _fmt_num(value)}</span>"
            f"<span class='estado'{title}>{_esc(state.title())}</span>"
            "</div>"
        )
    out.append("</div>")
    tup_state, tup_reason = _aws_tup_state(aws)
    if tup_state in {"ALERTA", "REVISAR"}:
        out.append(f"<div class='callout'><b>{_esc(tup_state)} Tarjeta TUP:</b> {_esc(tup_reason)}</div>")
    return "".join(out)


def _normalize_detail_rows(rows, max_rows=12) -> list[dict]:
    if not isinstance(rows, list):
        return []
    normalized = []
    for item in rows[:max_rows]:
        if isinstance(item, dict):
            normalized.append(item)
        elif isinstance(item, (list, tuple)):
            normalized.append({f"col_{i+1}": v for i, v in enumerate(item)})
        else:
            normalized.append({"detalle": item})
    return normalized


def _pick(d: dict, names: list[str], default=""):
    lowered = {str(k).lower().replace("_", " "): v for k, v in d.items()}
    for n in names:
        key = n.lower().replace("_", " ")
        if key in lowered:
            return lowered[key]
    for k, v in lowered.items():
        if any(n.lower().replace("_", " ") in k for n in names):
            return v
    return default


def _aws_messaging(aws: dict, key: str, title: str) -> str:
    details = (aws.get("detalles") or {}).get(key, []) if aws else []
    rows = _normalize_detail_rows(details)
    if not rows:
        total_key = "mens_error_400_total" if "errores" in key else "mens_exitos_200_total"
        value = _aws_metric(aws, total_key)
        return f"<div class='callout'><b>{_esc(title)}:</b> {'Sin detalle del corte' if value is None else _fmt_num(value)}</div>"
    out = ["<div class='table-like'><div class='table-head'><span>Operación</span><span>HTTP</span><span>Cantidad</span><span class='estado'>Check</span></div>"]
    for d in rows:
        op = _pick(d, ["operationinvokername", "operation", "operacion", "invoker", "funcion"], "Evento")
        http = _pick(d, ["http code", "httpcode", "status", "codigo"], "")
        qty = _pick(d, ["cantidad", "count", "total"], 0)
        out.append(
            "<div class='table-row'>"
            f"<span><b>{_esc(op)}</b></span><span>{_esc(http)}</span>"
            f"<span>{_fmt_num(qty)}</span><span class='estado'>✔</span></div>"
        )
    out.append("</div>")
    return "".join(out)


def _aws_transactionality(aws: dict) -> str:
    if not aws:
        return "<div class='empty'>Sin información AWS.</div>"
    rows = [
        ("ApiMensajeria (Report)", "mens_report"),
        ("Replicador", "replicador"),
        ("Validar error 500", "otp_500"),
        ("ApiModuloSeguridad", "seg_consulta_persona"),
    ]
    out = ["<div class='table-like'><div class='table-head'><span>Grupo</span><span></span><span>Cantidad</span><span class='estado'>Check</span></div>"]
    for label, key in rows:
        value = _aws_metric(aws, key)
        out.append(
            "<div class='table-row'>"
            f"<span><b>{_esc(label)}</b></span><span></span>"
            f"<span>{'—' if value is None else _fmt_num(value)}</span><span class='estado'>✔</span>"
            "</div>"
        )
    out.append("</div>")
    return "".join(out)


# -----------------------------------------------------------------------------
# Hércules
# -----------------------------------------------------------------------------

def _load_hercules(root: Path, fresh_after=None) -> dict:
    path = root / "HERCULES" / "HERCULES_RESUMEN_DIARIO.xlsx"
    if not _fresh_file(path, fresh_after):
        return {}
    try:
        raw = pd.read_excel(path, sheet_name="Consolidado", header=None)
    except Exception:
        return {}

    result = {
        "status": {},
        "status_channels": {},
        "payment_channels": {},
        "source": str(path),
    }

    # Col A/B: Estado cotización por canal.
    valid_status = {"Pago Realizado", "Checkout", "Pago Pendiente", "Inconsistente", "Pendiente Recaudo"}
    current = None
    for i in range(8, min(len(raw), 31)):
        label = raw.iat[i, 0] if raw.shape[1] > 0 else None
        value = raw.iat[i, 1] if raw.shape[1] > 1 else None
        if not isinstance(label, str):
            continue
        stripped = label.strip()
        if stripped in valid_status:
            current = stripped
            result["status"][current] = _num(value)
            result["status_channels"].setdefault(current, {})
        elif current and label.startswith(" ") and stripped:
            result["status_channels"][current][stripped] = _num(value)
        elif stripped == "Total general":
            current = None

    # Col D/E: Pago realizado por canal y forma de pago.
    current_channel = None
    for i in range(8, min(len(raw), 31)):
        label = raw.iat[i, 3] if raw.shape[1] > 3 else None
        value = raw.iat[i, 4] if raw.shape[1] > 4 else None
        if not isinstance(label, str):
            continue
        stripped = label.strip()
        if stripped in {"Web", "PAI", "Módulos", "Modulos"}:
            current_channel = "Módulos" if stripped == "Modulos" else stripped
            result["payment_channels"].setdefault(current_channel, {"total": _num(value), "formas": {}})
            result["payment_channels"][current_channel]["total"] = _num(value)
        elif current_channel and label.startswith(" ") and stripped:
            result["payment_channels"][current_channel]["formas"][stripped] = _num(value)
        elif stripped == "Total general":
            current_channel = None

    return result


def _hercules_tcompensar_count(h: dict) -> int:
    """Cuenta movimientos Tarjeta Compensar/TUP en formas de pago de Hércules."""
    total = 0
    for channel_data in (h.get("payment_channels") or {}).values():
        formas = (channel_data or {}).get("formas") or {}
        for key, value in formas.items():
            k = str(key).upper().replace(".", "").strip()
            if "COMPENSAR" in k or k == "TUP":
                total += _num(value)
    return total


def _critical_hercules_alerts(h: dict) -> list[dict]:
    if not h:
        return []

    total = _hercules_tcompensar_count(h)
    if total == 0:
        return [{
            "nivel": "ALERTA",
            "titulo": "Hércules · Tarjeta Compensar sin movimientos",
            "detalle": (
                "Hércules registra 0 movimientos de Tarjeta Compensar/TUP "
                "en Pago Realizado. Esta condición se considera alarma."
            ),
        }]
    return []


def _hercules_state(h: dict) -> str:
    if not h:
        return "SIN INFORMACIÓN"
    if _hercules_tcompensar_count(h) == 0:
        return "ALERTA"
    return "NORMALIDAD"


def _hercules_html(h: dict) -> str:
    if not h:
        return "<div class='empty'>Sin información de Hércules para el corte.</div>"
    status = h.get("status", {})
    channels = h.get("status_channels", {})
    pay = h.get("payment_channels", {})

    left = []
    for label in ["Pago Realizado", "Checkout", "Pago Pendiente", "Inconsistente", "Pendiente Recaudo"]:
        if label not in status:
            continue
        rows = "".join(
            f"<div class='metric-line'><b>{_esc(k)}</b><span></span><span>{_fmt_num(v)}</span><span></span></div>"
            for k, v in channels.get(label, {}).items()
        )
        left.append(
            "<div class='vert herc-card'>"
            f"<div class='vert-top'><div><div class='vert-code'>ESTADO</div><div class='vert-name'>{_esc(label)}</div></div>"
            f"<div class='num orange-number'>{_fmt_num(status[label])}</div></div>{rows}</div>"
        )

    right = []
    for channel in ["Web", "PAI", "Módulos"]:
        if channel not in pay:
            continue
        item = pay[channel]
        rows = "".join(
            f"<div class='metric-line'><b>{_esc(k)}</b><span></span><span>{_fmt_num(v)}</span><span></span></div>"
            for k, v in item.get("formas", {}).items()
        )
        right.append(
            "<div class='vert herc-card'>"
            f"<div class='vert-top'><div><div class='vert-code'>CANAL DE COTIZACIÓN</div><div class='vert-name'>{_esc(channel)}</div></div>"
            f"<div class='num orange-number'>{_fmt_num(item.get('total', 0))}</div></div>{rows}</div>"
        )

    return (
        "<div class='grid2'>"
        "<section class='card'><div class='card-head'><div><div class='eyebrow'>Hércules</div><h3>Estado cotización por canal</h3></div>"
        f"{_pill(_hercules_state(h))}</div><div class='card-body'>" + "".join(left) + "</div></section>"
        "<section class='card'><div class='card-head'><div><div class='eyebrow'>Hércules</div><h3>Pago realizado por canal y forma de pago</h3></div>"
        f"{_pill(_hercules_state(h))}</div><div class='card-body'>" + "".join(right) + "</div></section>"
        "</div>"
    )



def _credit_zoom_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "<div class='empty'>Sin información de créditos.</div>"
    work = df.copy()
    work['codigo'] = work['codigo'].astype(str).str.replace('.0', '', regex=False)
    work = work[work['codigo'].isin(['41607', '41612'])]
    if work.empty:
        return "<div class='empty'>Sin datos para 41607 / 41612.</div>"
    for col in ['cantidad_ok','conteo_rechazada','conteo_fallida_tecnica','conteo_expired','cantidad_total','conteo_pendiente','conteo_otra']:
        if col not in work.columns:
            work[col] = 0
    rows=[]
    for r in work.itertuples(index=False):
        estado=getattr(r,'estado','NORMAL')
        obs=str(getattr(r,'observacion','') or '')
        ok=_num(getattr(r,'cantidad_ok',0))
        rech=_num(getattr(r,'conteo_rechazada',0))
        fall=_num(getattr(r,'conteo_fallida_tecnica',0))
        exp=_num(getattr(r,'conteo_expired',0))
        total=_num(getattr(r,'cantidad_total',0))
        if total <= 0:
            total = ok + rech + fall + exp + _num(getattr(r,'conteo_pendiente',0)) + _num(getattr(r,'conteo_otra',0))
        # Motivo explícito incluso cuando el archivo de origen no trae observación.
        if not obs and (rech + fall) > ok:
            obs = f'Rechazadas/fallidas ({rech + fall}) superan las OK ({ok}).'
        elif not obs and fall > 0:
            obs = f'Se detectan {fall} fallas técnicas; revisar detalle de la vertical.'
        rows.append(
            "<div class='credit-row'>"
            f"<span><b>{_esc(getattr(r,'vertical',''))}</b><small>{_esc(getattr(r,'medio_salida',''))}</small></span>"
            f"<span class='n okn'>{_fmt_num(ok)}</span>"
            f"<span class='n'>{_fmt_num(rech)}</span>"
            f"<span class='n badn'>{_fmt_num(fall)}</span>"
            f"<span class='n'>{_fmt_num(exp)}</span>"
            f"<span class='n'>{_fmt_num(total)}</span>"
            f"<span class='state-cell'>{_semaforo(estado)}</span>"
            f"<span class='why'>{_esc(obs)}</span>"
            "</div>"
        )
    return "<div class='credit-table'><div class='credit-head'><span>Vertical / medio</span><span>OK</span><span>Rech.</span><span>Fallidas</span><span>Exp.</span><span>Total</span><span>Estado</span><span>Motivo</span></div>"+''.join(rows)+"</div>"


def _tup_cross_alert(pas: pd.DataFrame, her: dict) -> list[dict]:
    if pas.empty or not her:
        return []
    p = pas.copy()
    p['codigo'] = p['codigo'].astype(str).str.replace('.0','',regex=False)
    tup = p[(p['codigo']=='41610') & (p['medio_salida'].astype(str).str.upper()=='TUP')]
    if tup.empty:
        return []
    pas_ok = int(pd.to_numeric(tup['cantidad_ok'], errors='coerce').fillna(0).sum())
    formas = (((her.get('payment_channels') or {}).get('Web') or {}).get('formas') or {})
    her_tup = 0
    for k,v in formas.items():
        kk = str(k).upper()
        if 'COMPENSAR' in kk or kk.strip() == 'TUP':
            her_tup += _num(v)
    if pas_ok <= 0 and her_tup == 0:
        return [{
            'nivel':'ALERTA',
            'titulo':'TUP sin actividad en Pasarelas y Hércules',
            'detalle':'41610 TUP registra 0 aprobadas y Hércules registra 0 movimientos Tarjeta Compensar/TUP.'
        }]
    if pas_ok <= 0:
        return [{
            'nivel':'ALERTA',
            'titulo':'41610 TUP sin aprobaciones',
            'detalle':f'41610 RED TIENDA registra 0 TUP aprobadas, mientras Hércules registra {her_tup} movimientos Tarjeta Compensar/TUP.'
        }]
    if her_tup == 0:
        return [{
            'nivel':'ALERTA',
            'titulo':'Cruce TUP 41610 vs Hércules Web',
            'detalle':f'Pasarelas registra {pas_ok} aprobadas TUP, pero Hércules Web no registra pagos con Tarjeta Compensar/TUP.'
        }]
    diff = abs(pas_ok-her_tup)
    ratio = diff/max(pas_ok,1)
    if ratio >= 0.50 and diff >= 3:
        return [{
            'nivel':'REVISAR',
            'titulo':'Diferencia TUP 41610 vs Hércules Web',
            'detalle':f'Pasarelas: {pas_ok} OK TUP. Hércules Web: {her_tup} Tarjeta Compensar/TUP. Diferencia {diff} ({ratio*100:.0f}%).'
        }]
    return []



def _parse_dt_any(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _serviciosred_info(aws: dict) -> tuple[int | None, str, float | None]:
    """Retorna (notificaciones_ultima_hora, ultima_notificacion, minutos_sin_notificar)."""
    if not aws:
        return None, "", None
    metric = _aws_metric(aws, "serviciosred_ultima_hora")
    try:
        count = None if metric is None else int(float(metric))
    except Exception:
        count = None

    rows = ((aws.get("detalles") or {}).get("serviciosred_ultima_hora") or [])
    row = rows[0] if rows and isinstance(rows[0], dict) else {}
    last = str(row.get("ultima_notificacion") or "")
    end = row.get("hasta") or aws.get("fecha")
    last_dt = _parse_dt_any(last)
    end_dt = _parse_dt_any(end)
    minutes = None
    if last_dt is not None and end_dt is not None:
        try:
            minutes = max(0.0, (end_dt - last_dt).total_seconds() / 60.0)
        except Exception:
            minutes = None
    return count, last, minutes


def _serviciosred_last_label(last: str, minutes: float | None) -> str:
    dt = _parse_dt_any(last)
    label = last
    if dt is not None:
        label = dt.strftime('%Y-%m-%d %H:%M:%S')
    if minutes is None:
        return label or 'Sin registro en la última hora'
    if label:
        return f"{label} · hace {minutes:.0f} min"
    return f"Hace {minutes:.0f} min"


def _serviciosred_series_10m(aws: dict) -> list[tuple[str, int]]:
    rows = ((aws.get('detalles') or {}).get('serviciosred_10m_ultima_hora') or []) if aws else []
    data = []
    for row in rows:
        raw = row.get('hora') or row.get('@timestamp') or ''
        dt = _parse_dt_any(raw)
        label = dt.strftime('%H:%M') if dt is not None else str(raw or '')[-8:-3]
        data.append((label, _num(row.get('count'))))
    data.sort(key=lambda x: x[0])
    return data


def _serviciosred_state(aws: dict, pas: pd.DataFrame) -> tuple[str, str]:
    count, last, minutes = _serviciosred_info(aws)
    tup_ok = 0
    if not pas.empty:
        p = pas.copy()
        p['codigo'] = p['codigo'].astype(str).str.replace('.0', '', regex=False)
        tup = p[(p['codigo'] == '41610') & (p['medio_salida'].astype(str).str.upper() == 'TUP')]
        if not tup.empty:
            tup_ok = int(pd.to_numeric(tup['cantidad_ok'], errors='coerce').fillna(0).sum())

    if count is None:
        return 'REVISAR', 'Consulta de Servicios Red no disponible.'
    if tup_ok <= 0 and count == 0:
        return 'SIN INFORMACIÓN', 'Sin TUP aprobadas; cero notificaciones no genera alerta.'
    if tup_ok > 0 and count == 0:
        return 'ALERTA', f'Hay {tup_ok} TUP aprobadas en 41610 y 0 notificaciones en la última hora.'
    return 'NORMALIDAD', 'Hay actividad de Servicios Red en la última hora.'


def _serviciosred_chart(aws: dict) -> str:
    rows = _serviciosred_series_10m(aws)
    if not rows:
        return (
            "<div style='padding:18px;text-align:center;color:#6f7f8f;"
            "border:1px dashed #d8e3ee;border-radius:12px;background:#fff'>"
            "Sin datos por intervalos de 10 minutos.</div>"
        )

    # CloudWatch puede omitir buckets completamente vacíos. Para el General
    # mostramos los buckets recibidos sin fabricar cantidades.
    maxv = max([v for _, v in rows] + [1])
    cols = []

    for label, value in rows:
        height = 8 if value <= 0 else max(18, int((value / maxv) * 105))
        bar_bg = "#DCE7F2" if value <= 0 else "linear-gradient(180deg,#62A8EA,#0B5CAB)"
        cols.append(
            "<div style='flex:1;min-width:54px;display:flex;flex-direction:column;"
            "align-items:center;justify-content:flex-end;gap:6px'>"
            f"<div style='font-size:11px;font-weight:800;color:#50657A'>{_fmt_num(value)}</div>"
            f"<div title='{_esc(label)} · {_fmt_num(value)} notificaciones' "
            f"style='height:{height}px;width:34px;max-width:70%;background:{bar_bg};"
            "border-radius:9px 9px 4px 4px;box-shadow:0 3px 8px rgba(11,92,171,.12)'></div>"
            f"<div style='font-size:10px;color:#6F7F8F;white-space:nowrap'>{_esc(label)}</div>"
            "</div>"
        )

    return (
        "<div style='margin-top:12px;border:1px solid #E3EBF3;border-radius:14px;"
        "background:#FFFFFF;padding:12px 14px'>"
        "<div style='display:flex;align-items:center;justify-content:space-between;"
        "gap:12px;margin-bottom:10px'>"
        "<div style='font-size:12px;font-weight:900;color:#18324B'>"
        "Notificaciones por intervalos de 10 minutos</div>"
        "<div style='font-size:10px;color:#718195'>Última hora</div>"
        "</div>"
        "<div style='height:145px;display:flex;align-items:flex-end;justify-content:space-around;"
        "gap:10px;padding:4px 8px 0;overflow:hidden'>"
        + "".join(cols) +
        "</div></div>"
    )


def _serviciosred_pill(aws: dict, pas: pd.DataFrame) -> str:
    return _pill(_serviciosred_state(aws, pas)[0])


def _serviciosred_cross_alert(pas: pd.DataFrame, aws: dict) -> list[dict]:
    """Cruza 41610 TUP OK con actividad de Servicios Red.

    No alerta solo por ausencia de logs: exige que la pasarela tenga TUP aprobadas.
    """
    if pas.empty or not aws:
        return []

    p = pas.copy()
    p["codigo"] = p["codigo"].astype(str).str.replace(".0", "", regex=False)
    tup = p[(p["codigo"] == "41610") & (p["medio_salida"].astype(str).str.upper() == "TUP")]
    if tup.empty:
        return []

    tup_ok = int(pd.to_numeric(tup["cantidad_ok"], errors="coerce").fillna(0).sum())
    if tup_ok <= 0:
        return []

    count, last, minutes = _serviciosred_info(aws)
    if count is None:
        return [{
            "nivel": "REVISAR",
            "titulo": "Servicios Red · consulta no disponible",
            "detalle": f"41610 registra {tup_ok} TUP aprobadas, pero no fue posible obtener la actividad de Servicios Red."
        }]

    if count == 0:
        return [{
            "nivel": "ALERTA",
            "titulo": "Servicios Red · sin notificaciones",
            "detalle": (
                f"41610 registra {tup_ok} TUP aprobadas y Servicios Red no registra "
                f"notificaciones durante la última hora del periodo. Revisar flujo de notificación."
            )
        }]

    # Con actividad en la última hora no se genera alerta.
    return []


def _serviciosred_card(aws: dict, pas: pd.DataFrame) -> str:
    count, last, minutes = _serviciosred_info(aws)
    tup_ok = 0

    if not pas.empty:
        p = pas.copy()
        p["codigo"] = p["codigo"].astype(str).str.replace(".0", "", regex=False)
        tup = p[
            (p["codigo"] == "41610")
            & (p["medio_salida"].astype(str).str.upper() == "TUP")
        ]
        if not tup.empty:
            tup_ok = int(
                pd.to_numeric(tup["cantidad_ok"], errors="coerce")
                .fillna(0)
                .sum()
            )

    estado, motivo = _serviciosred_state(aws, pas)
    last_txt = _serviciosred_last_label(last, minutes)

    # Colores suaves según estado, sin depender de CSS global.
    estado_up = str(estado).upper()
    if "ALERTA" in estado_up:
        note_bg, note_border, note_fg = "#FFF0F0", "#F3C5C5", "#A11B1B"
    elif "REVIS" in estado_up:
        note_bg, note_border, note_fg = "#FFF8E7", "#F1D99A", "#8B6500"
    else:
        note_bg, note_border, note_fg = "#EDF9F2", "#BFE6CC", "#176A3A"

    kpi_style = (
        "flex:1;min-width:180px;border:1px solid #E4ECF3;border-radius:13px;"
        "background:#FFFFFF;padding:11px 13px;box-shadow:0 2px 7px rgba(28,52,74,.04)"
    )
    label_style = (
        "display:block;font-size:10px;text-transform:uppercase;letter-spacing:.04em;"
        "font-weight:800;color:#718195;margin-bottom:6px"
    )
    value_style = "display:block;font-size:18px;font-weight:900;color:#15344F;line-height:1.25"

    return (
        "<div style='border:1px solid #E4ECF3;border-radius:15px;background:#FAFCFE;"
        "padding:13px'>"
        "<div style='font-size:11px;color:#64778A;margin-bottom:10px'>"
        "Actividad reciente de Servicios Red para identificar huecos de notificación."
        "</div>"
        "<div style='display:flex;gap:10px;flex-wrap:wrap'>"
        f"<div style='{kpi_style}'><span style='{label_style}'>TUP 41610 aprobadas</span>"
        f"<strong style='{value_style}'>{_fmt_num(tup_ok)}</strong></div>"
        f"<div style='{kpi_style}'><span style='{label_style}'>Notificaciones última hora</span>"
        f"<strong style='{value_style}'>{'—' if count is None else _fmt_num(count)}</strong></div>"
        f"<div style='{kpi_style}'><span style='{label_style}'>Última notificación</span>"
        f"<strong style='display:block;font-size:14px;font-weight:900;color:#15344F;"
        f"line-height:1.35'>{_esc(last_txt)}</strong></div>"
        "</div>"
        f"{_serviciosred_chart(aws)}"
        f"<div style='margin-top:10px;padding:9px 11px;border-radius:11px;"
        f"background:{note_bg};border:1px solid {note_border};color:{note_fg};"
        "font-size:11px;line-height:1.45'>"
        f"<b>{_esc(estado.title())}:</b> {_esc(motivo)}</div>"
        "</div>"
    )


def _novedades(pas: pd.DataFrame, aws: dict, her: dict) -> list[dict]:
    items=[]
    if not pas.empty:
        for r in pas.itertuples(index=False):
            st=str(getattr(r,'estado','')).upper()
            if 'ALERTA' in st or 'BAJA' in st or 'REVIS' in st:
                items.append({
                    'nivel':'ALERTA' if 'ALERTA' in st else 'REVISAR',
                    'titulo':f"{getattr(r,'codigo','')} · {getattr(r,'medio_salida','')}",
                    'detalle':str(getattr(r,'observacion','Revisar comportamiento del corte.')),
                })
    for a in (aws.get('alertas') or []) if aws else []:
        if isinstance(a, dict):
            items.append({'nivel':'REVISAR','titulo':str(a.get('titulo') or a.get('metrica') or 'AWS'),'detalle':str(a.get('detalle') or a.get('mensaje') or a)})
        else:
            items.append({'nivel':'REVISAR','titulo':'AWS','detalle':str(a)})
    # Reglas críticas independientes del promedio.
    items.extend(_critical_pasarelas_alerts(pas))
    items.extend(_critical_hercules_alerts(her))

    items.extend(_tup_cross_alert(pas, her))
    items.extend(_serviciosred_cross_alert(pas, aws))

    tup_state, tup_reason = _aws_tup_state(aws)
    if tup_state in {"ALERTA", "REVISAR"}:
        items.append({
            "nivel": tup_state,
            "titulo": "AWS · Tarjeta TUP · Error consumo",
            "detalle": tup_reason
        })
    return items


def _alerts_html(items: list[dict]) -> str:
    if not items:
        return "<div class='empty ok-empty'>Sin novedades operativas relevantes en este corte.</div>"
    cards=[]
    for x in items:
        lvl=x.get('nivel','REVISAR')
        cards.append(
            f"<div class='alert-card {'bad' if lvl=='ALERTA' else 'warn'}'>"
            f"<div>{_semaforo(lvl)}<b>{_esc(x.get('titulo','Alerta'))}</b></div>"
            f"<p>{_esc(x.get('detalle',''))}</p></div>"
        )
    return "<div class='alerts-grid'>"+''.join(cards)+"</div>"

# -----------------------------------------------------------------------------
# Page sections
# -----------------------------------------------------------------------------

def _weekend_html(pas: pd.DataFrame, aws: dict, her: dict) -> str:
    # Vista operativa acordada para sábado, domingo y festivo.
    # El resumen principal NO mezcla créditos: solo estas seis verticales.
    priority = ["41605", "41623", "41610", "41620", "41631", "41632"]
    credit = pas.copy()
    if not credit.empty:
        credit['codigo'] = credit['codigo'].astype(str).str.replace('.0','',regex=False)
        credit = credit[credit['codigo'].isin(['41607','41612'])]
    credit_state = _pas_state(credit) if not credit.empty else 'SIN INFORMACIÓN'
    return f"""
    <div class='shot'>
      <div class='shot-label'><strong>Pantallazo 1 · Pasarelas eCollect</strong><span>Fin de semana / festivo · verticales operativas</span></div>
      <section class='card'><div class='card-head'><div><div class='eyebrow'>Pasarelas</div><h3>Monitoreo de verticales</h3></div>{_pill(_pas_state(pas))}</div>
        <div class='card-body'><div class='note-orange'>Se muestran únicamente transacciones OK/aprobadas. Vista de fin de semana/festivo: 41605, 41623, 41610, 41620, 41631 y 41632.</div>{_vertical_cards(pas, priority)}</div>
      </section>
    </div>

    <div class='shot'>
      <div class='shot-label'><strong>Pantallazo 2 · Zoom créditos</strong><span>41607 CREDITO BANCOR · 41612 CREDITO SIIF</span></div>
      <section class='card'><div class='card-head'><div><div class='eyebrow'>Pasarelas</div><h3>Aprobadas, rechazadas y fallidas</h3></div>{_pill(credit_state)}</div>
        <div class='card-body'><div class='note-orange'>Los créditos se revisan aparte del resumen. La vista muestra OK, rechazadas, fallidas técnicas, expiradas y total; si rechazadas + fallidas superan las OK, debe quedar explicado en el motivo de alerta.</div>{_credit_zoom_table(pas)}</div>
      </section>
    </div>

    <div class='shot'>
      <div class='shot-label'><strong>Pantallazo 3 · AWS</strong><span>Pagos · Lambda · Mensajería · Transaccionalidad</span></div>
      <div class='grid2'>
        <section class='card'><div class='card-head'><div><div class='eyebrow'>Monitoreo API Pagos</div><h3>Exitosos y con error</h3></div>{_pill(_aws_state(aws))}</div>
          <div class='card-body'><div class='section-title'>API de pagos exitosos</div>{_aws_payment_table(aws, False)}<div class='section-title top-gap'>API de pagos con error</div>{_aws_payment_table(aws, True)}</div>
        </section>
        <section class='card'><div class='card-head'><div><div class='eyebrow'>Monitoreo API Lambda</div><h3>CSC · OTP · API Subsidios · Tarjeta TUP</h3></div>{_pill(_aws_state(aws))}</div>
          <div class='card-body'>{_aws_lambda_table(aws)}<div class='section-title top-gap'>Monitoreo buzón</div>
            <div class='mini-grid'><div class='mini'><div class='t'>Superación de tasa</div><div class='n'>{_fmt_num(_aws_metric(aws,'superacion_tasa'))}</div></div><div class='mini'><div class='t'>Superación de quota</div><div class='n'>{_fmt_num(_aws_metric(aws,'superacion_quota'))}</div></div></div>
          </div>
        </section>
      </div>
      <div class='grid2 aws-second'>
        <section class='card'><div class='card-head'><div><div class='eyebrow'>Seguimiento APIMensajería</div><h3>Errores y exitosos</h3></div>{_pill(_aws_state(aws,['mens']))}</div>
          <div class='card-body'><div class='section-title'>Errores 400</div>{_aws_messaging(aws,'mensajeria_errores','Errores 400')}<div class='section-title top-gap'>Exitosos 200</div>{_aws_messaging(aws,'mensajeria_exitos','Exitosos 200')}</div>
        </section>
        <section class='card'><div class='card-head'><div><div class='eyebrow'>Transaccionalidad</div><h3>Replicador, seguridad y TUP</h3></div>{_pill(_aws_state(aws))}</div>
          <div class='card-body'>{_aws_transactionality(aws)}<div class='section-title top-gap'>Controles adicionales</div><div class='mini-grid'>
            <div class='mini'><div class='t'>Errores generales Tarjeta TUP</div><div class='n'>{_fmt_num(_aws_metric(aws,'tup_error'))}</div></div>
            <div class='mini'><div class='t'>API Subsidios · ERROR CX</div><div class='n'>{_fmt_num(_aws_metric(aws,'error_cx'))}</div></div>
          </div></div>
        </section>
      </div>
      <div class='aws-second'>
        <section class='card'>
          <div class='card-head'>
            <div><div class='eyebrow'>INTEROPPROD</div><h3>Servicios Red · notificaciones TUP</h3></div>
            {_serviciosred_pill(aws, pas)}
          </div>
          <div class='card-body'>{_serviciosred_card(aws, pas)}</div>
        </section>
      </div>
    </div>

    <div class='shot'>
      <div class='shot-label'><strong>Pantallazo 4 · Hércules</strong><span>Cotización, canales y formas de pago</span></div>
      {_hercules_html(her)}
    </div>
    """


def _weekday_html(pas: pd.DataFrame, aws: dict, her: dict) -> str:
    return f"""
    <div class='shot'>
      <div class='shot-label'><strong>Pantallazo 1 · Pasarelas</strong><span>OK del corte vs promedio por corte</span></div>
      <section class='card'><div class='card-head'><div><div class='eyebrow'>Pasarelas</div><h3>Verticales y medios de pago</h3></div>{_pill(_pas_state(pas))}</div>
        <div class='card-body'><div class='note-orange'>Se muestran únicamente transacciones OK/aprobadas. Las rechazadas y fallidas sí participan internamente en las alertas.</div>{_vertical_cards(pas)}</div>
      </section>
    </div>

    <div class='shot'>
      <div class='shot-label'><strong>Pantallazo 2 · Zoom créditos</strong><span>41607 CREDITO BANCOR · 41612 CREDITO SIIF</span></div>
      <section class='card'><div class='card-head'><div><div class='eyebrow'>Pasarelas</div><h3>Calidad de transacción en créditos</h3></div>{_pill(_pas_state(pas[pas['codigo'].astype(str).str.replace('.0','',regex=False).isin(['41607','41612'])]) if not pas.empty else 'SIN INFORMACIÓN')}</div>
        <div class='card-body'><div class='note-orange'>Alerta automática cuando rechazadas/declinadas/fallidas superan las OK. Expiradas se muestran como contexto.</div>{_credit_zoom_table(pas)}</div>
      </section>
    </div>

    <div class='shot'>
      <div class='shot-label'><strong>Pantallazo 3 · AWS</strong><span>Pagos · Lambda · Mensajería · Transaccionalidad</span></div>
      <div class='grid2'>
        <section class='card'><div class='card-head'><div><div class='eyebrow'>Monitoreo API Pagos</div><h3>Exitosos y con error</h3></div>{_pill(_aws_state(aws))}</div>
          <div class='card-body'><div class='section-title'>API de pagos exitosos</div>{_aws_payment_table(aws, False)}<div class='section-title top-gap'>API de pagos con error</div>{_aws_payment_table(aws, True)}</div>
        </section>
        <section class='card'><div class='card-head'><div><div class='eyebrow'>Monitoreo API Lambda</div><h3>CSC · OTP · API Subsidios · Tarjeta TUP</h3></div>{_pill(_aws_state(aws))}</div>
          <div class='card-body'>{_aws_lambda_table(aws)}<div class='section-title top-gap'>Monitoreo buzón</div>
            <div class='mini-grid'><div class='mini'><div class='t'>Superación de tasa</div><div class='n'>{_fmt_num(_aws_metric(aws,'superacion_tasa'))}</div></div><div class='mini'><div class='t'>Superación de quota</div><div class='n'>{_fmt_num(_aws_metric(aws,'superacion_quota'))}</div></div></div>
          </div>
        </section>
      </div>
      <div class='grid2 aws-second'>
        <section class='card'><div class='card-head'><div><div class='eyebrow'>Seguimiento APIMensajería</div><h3>Errores y exitosos</h3></div>{_pill(_aws_state(aws,['mens']))}</div>
          <div class='card-body'><div class='section-title'>Errores 400</div>{_aws_messaging(aws,'mensajeria_errores','Errores 400')}<div class='section-title top-gap'>Exitosos 200</div>{_aws_messaging(aws,'mensajeria_exitos','Exitosos 200')}</div>
        </section>
        <section class='card'><div class='card-head'><div><div class='eyebrow'>Transaccionalidad</div><h3>Replicador, seguridad y TUP</h3></div>{_pill(_aws_state(aws))}</div>
          <div class='card-body'>{_aws_transactionality(aws)}<div class='section-title top-gap'>Controles adicionales</div><div class='mini-grid'>
            <div class='mini'><div class='t'>Errores generales Tarjeta TUP</div><div class='n'>{_fmt_num(_aws_metric(aws,'tup_error'))}</div></div>
            <div class='mini'><div class='t'>API Subsidios · ERROR CX</div><div class='n'>{_fmt_num(_aws_metric(aws,'error_cx'))}</div></div>
          </div></div>
        </section>
      </div>
      <div class='aws-second'>
        <section class='card'>
          <div class='card-head'>
            <div><div class='eyebrow'>INTEROPPROD</div><h3>Servicios Red · notificaciones TUP</h3></div>
            {_serviciosred_pill(aws, pas)}
          </div>
          <div class='card-body'>{_serviciosred_card(aws, pas)}</div>
        </section>
      </div>
    </div>

    <div class='shot'>
      <div class='shot-label'><strong>Pantallazo 4 · Hércules</strong><span>Cotización, canales y formas de pago</span></div>
      {_hercules_html(her)}
    </div>
    """


# -----------------------------------------------------------------------------
# Public API used by core.orchestrator.finalize()
# -----------------------------------------------------------------------------

def generate_dashboard(root: Path, selected=None, fresh_after=None):
    root = Path(root)
    general = root / "GENERAL"
    general.mkdir(parents=True, exist_ok=True)
    (general / "data").mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    weekend, mode_label = _is_weekend_or_holiday(root, now)
    selected_set = {str(x).upper() for x in (selected or ['PASARELAS','AWS','HERCULES'])}

    # Solo se exige frescura para monitores ejecutados en este ciclo.
    pas = _load_pasarelas(root, fresh_after if 'PASARELAS' in selected_set else None)
    aws = _load_aws(root, fresh_after if 'AWS' in selected_set else None)
    her = _load_hercules(root, fresh_after if 'HERCULES' in selected_set else None)

    pas_state = _pas_state(pas)
    aws_state = _aws_state(aws)
    her_state = _hercules_state(her)
    novedades = _novedades(pas, aws, her)

    # Si un monitor fue seleccionado pero su fuente no es de esta ejecución,
    # no se reutiliza ayer: se informa explícitamente como dato no actualizado.
    if 'PASARELAS' in selected_set and pas.empty:
        novedades.append({
            'nivel': 'ALERTA',
            'titulo': 'Pasarelas · información no actualizada',
            'detalle': 'No se encontró un resumen de Pasarelas generado en esta ejecución. El General no reutilizó datos anteriores.'
        })
        pas_state = 'ALERTA'

    if 'AWS' in selected_set and not aws:
        novedades.append({
            'nivel': 'ALERTA',
            'titulo': 'AWS · información no actualizada',
            'detalle': 'No se encontró información AWS generada en esta ejecución. El General no reutilizó datos anteriores.'
        })
        aws_state = 'ALERTA'

    if 'HERCULES' in selected_set and not her:
        novedades.append({
            'nivel': 'ALERTA',
            'titulo': 'Hércules · información no actualizada',
            'detalle': 'No se encontró un resumen de Hércules generado en esta ejecución. El General no reutilizó datos anteriores.'
        })
        her_state = 'ALERTA'

    alerts = len(novedades)

    main_content = _weekend_html(pas, aws, her) if weekend else _weekday_html(pas, aws, her)
    if 'PASARELAS' not in selected_set: pas_state = 'NO EJECUTADO'
    if 'AWS' not in selected_set: aws_state = 'NO EJECUTADO'
    if 'HERCULES' not in selected_set: her_state = 'NO EJECUTADO'

    css = f"""
    :root{{--orange:{ORANGE};--orange2:{ORANGE_2};--blue:{BLUE};--navy:{NAVY};--green:{GREEN};--yellow:{YELLOW};--red:{RED};--bg:#f4f7fb;--card:#fff;--line:#ffd9c6;--ink:#18324b;--muted:#708197;--shadow:0 12px 30px rgba(20,48,77,.09)}}
    *{{box-sizing:border-box}} body{{margin:0;font-family:Segoe UI,Inter,Arial,sans-serif;background:var(--bg);color:var(--ink)}}
    .hero{{background:linear-gradient(112deg,#15304d 0%,#173b60 58%,#214d78 100%);border-bottom:5px solid var(--orange);color:white;padding:18px 26px;box-shadow:0 8px 28px rgba(10,35,58,.18)}}
    .hero-row{{display:flex;align-items:center;justify-content:space-between;gap:20px}} .brand{{display:flex;gap:14px;align-items:center}}
    .logo{{width:46px;height:46px;border-radius:15px;background:linear-gradient(135deg,var(--orange),var(--orange2));display:grid;place-items:center;font-size:28px;font-weight:900;box-shadow:0 8px 20px rgba(242,107,29,.28)}}
    .brand h1{{font-size:25px;margin:0}} .brand p{{margin:4px 0 0;color:#ccdaea;font-size:13px}} .head-right{{display:flex;gap:9px;flex-wrap:wrap;justify-content:flex-end}}
    .badge{{border-radius:999px;padding:8px 12px;font-size:12px;font-weight:800;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.15)}} .badge.mode{{background:var(--orange);border-color:transparent}}
    .shell{{max-width:1700px;margin:auto;padding:18px}} .summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:15px}}
    .kpi{{background:white;border:1px solid #ffd9c6;border-radius:18px;padding:15px 16px 15px 20px;box-shadow:var(--shadow);position:relative;overflow:hidden}} .kpi:before{{content:'';position:absolute;left:0;top:0;bottom:0;width:6px;background:linear-gradient(180deg,var(--orange),var(--orange2))}}
    .kpi .label{{font-size:11px;color:var(--muted);font-weight:900;text-transform:uppercase;letter-spacing:.06em}} .kpi .value{{font-size:24px;font-weight:900;margin-top:6px;color:var(--navy)}}
    .status{{display:inline-flex;gap:6px;align-items:center;font-size:11px;font-weight:900;border-radius:999px;padding:6px 10px}} .status.ok{{color:#147443;background:#e9f7ef}} .status.warn{{color:#966100;background:#fff4d6}} .status.bad{{color:#bb3030;background:#fdeaea}} .status.neutral{{color:#657487;background:#eef2f6}} .dot{{width:7px;height:7px;border-radius:50%;background:currentColor}}
    .shot{{margin-bottom:15px}} .shot-label{{display:flex;justify-content:space-between;align-items:center;margin:4px 2px 8px}} .shot-label strong{{font-size:14px;color:var(--navy)}} .shot-label span{{font-size:11px;color:var(--muted)}}
    .grid2{{display:grid;grid-template-columns:1fr 1fr;gap:14px}} .card{{background:white;border:1px solid #ffd9c6;border-radius:20px;box-shadow:var(--shadow);overflow:hidden}}
    .card-head{{padding:13px 15px;border-bottom:1px solid #ffe4d6;display:flex;align-items:center;justify-content:space-between;gap:12px;background:linear-gradient(180deg,#fff5ef,#fff)}} .card-head h3{{margin:0;font-size:17px}} .eyebrow{{font-size:10px;color:#9c4a18;font-weight:900;text-transform:uppercase;letter-spacing:.06em}}
    .card-body{{padding:13px 15px}} .section-title{{display:flex;align-items:center;gap:8px;margin:2px 0 9px;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:#365674;font-weight:900}} .section-title:before{{content:'';width:5px;height:17px;border-radius:6px;background:var(--orange)}} .top-gap{{margin-top:14px}}
    .vert-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}} .vert{{border:1px solid #ffd9c6;border-radius:14px;padding:9px;background:linear-gradient(180deg,#fff,#fffaf7)}} .herc-card+ .herc-card{{margin-top:10px}}
    .vert-top{{display:flex;justify-content:space-between;gap:10px;align-items:start;margin-bottom:7px}} .vert-name{{font-weight:900;color:#103c70;font-size:12px}} .vert-code{{font-size:10px;color:var(--muted);text-transform:uppercase;font-weight:800}} .orange-number{{color:var(--orange)!important;font-size:25px!important}}
    .metric-line{{display:grid;grid-template-columns:1.35fr .8fr .45fr .55fr;gap:5px;padding:4px 0;border-top:1px dashed #ecd9cc;font-size:11px}} .metric-line:first-of-type{{border-top:0}} .metric-line span:nth-child(n+2){{text-align:right}}
    .mini-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}} .mini{{background:linear-gradient(180deg,#fff,#fff8f3);border:1px solid #ffd9c6;border-radius:14px;padding:11px}} .mini .t{{font-size:10px;color:var(--muted);font-weight:800}} .mini .n{{font-size:22px;font-weight:900;margin-top:5px;color:var(--navy)}}
    .table-like{{display:grid;gap:7px}} .table-head,.table-row{{display:grid;grid-template-columns:1.5fr .7fr .55fr .75fr;gap:7px;align-items:center}} .table-head{{padding:8px 10px;border-radius:11px;background:#fff0e7;border:1px solid #ffd7bf;font-size:10px;font-weight:900;text-transform:uppercase;color:#9a4410}} .table-row{{padding:8px 10px;border-radius:11px;background:#fffaf6;border:1px solid #ffe2d2;font-size:11px}} .table-row span:nth-child(n+2),.table-head span:nth-child(n+2){{text-align:right}} .table-row .estado,.table-head .estado{{text-align:center}}
    .note-orange,.callout{{background:linear-gradient(135deg,#fff6ef,#fff);border:1px solid #ffd9c6;border-radius:15px;padding:11px 13px;color:#79401e;font-size:11px;line-height:1.45;margin-bottom:11px}} .empty{{padding:18px;border:1px dashed #d9e0e8;border-radius:14px;color:var(--muted);background:#fafcff;text-align:center}}
    .traffic-wrap,.state-cell{{display:flex;align-items:center;justify-content:flex-end;gap:5px}} .traffic{{width:13px;height:13px;border-radius:50%;display:inline-block;box-shadow:0 0 0 3px rgba(0,0,0,.04)}} .traffic.ok{{background:#20a05a}} .traffic.warn{{background:#e0a000}} .traffic.bad{{background:#d53b3b}} .traffic.neutral{{background:#9aa8b6}} .traffic-label{{font-size:10px;font-weight:800;color:#526477}}
    .credit-table{{display:grid;gap:6px}} .credit-head,.credit-row{{display:grid;grid-template-columns:1.35fr .32fr .38fr .40fr .32fr .38fr .52fr 1.8fr;gap:7px;align-items:center}} .credit-head{{background:#fff0e7;border:1px solid #ffd7bf;border-radius:10px;padding:8px;font-size:10px;font-weight:900;text-transform:uppercase}} .credit-row{{padding:8px;border:1px solid #ffe2d2;border-radius:10px;font-size:11px}} .credit-row small{{display:block;color:var(--muted);margin-top:2px}} .credit-row .n{{text-align:center;font-weight:800}} .credit-row .okn{{color:var(--green)}} .credit-row .badn{{color:var(--red)}} .credit-row .why{{color:#607083;line-height:1.3}}
    .aws-second{{margin-top:14px}} .alerts-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:9px}} .alert-card{{border-radius:13px;padding:11px 13px;border:1px solid #ead7c5;background:white}} .alert-card>div{{display:flex;align-items:center;gap:7px}} .alert-card p{{margin:7px 0 0;font-size:11px;color:#5b6672;line-height:1.45}} .alert-card.bad{{border-left:5px solid var(--red)}} .alert-card.warn{{border-left:5px solid #e0a000}} .detail-btn{{display:inline-block;margin-top:8px;padding:6px 9px;border-radius:8px;background:#edf4fb;color:var(--blue);text-decoration:none;font-size:10px;font-weight:800}}
    .footer{{padding:10px 0 3px;color:var(--muted);font-size:10px;text-align:right}}
    @media(max-width:1200px){{.vert-grid{{grid-template-columns:repeat(2,1fr)}}}} @media(max-width:900px){{.summary{{grid-template-columns:1fr 1fr}}.grid2{{grid-template-columns:1fr}}.vert-grid{{grid-template-columns:1fr}}.credit-head,.credit-row{{grid-template-columns:1fr .4fr .4fr .45fr .4fr .45fr .6fr}}.credit-head span:last-child,.credit-row .why{{display:none}}.alerts-grid{{grid-template-columns:1fr}}}}
    @media print{{.hero{{box-shadow:none}}.shell{{max-width:none;padding:9px}}.card,.kpi{{box-shadow:none}}.shot{{break-inside:avoid}}}}
    """

    html_page = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta http-equiv='Cache-Control' content='no-cache, no-store, must-revalidate'><meta http-equiv='Pragma' content='no-cache'><meta http-equiv='Expires' content='0'><title>Monitoreo Compensar · Vista Gerencial</title><style>{css}</style></head><body>
    <header class='hero'><div class='hero-row'><div class='brand'><div class='logo'>C</div><div><h1>Monitoreo Compensar</h1><p>Vista gerencial · estado operativo del corte</p></div></div><div class='head-right'><span class='badge'>{now:%d/%m/%Y · %H:%M}</span><span class='badge mode'>{_esc(mode_label)}</span></div></div></header>
    <main class='shell'>
      <section class='summary'>
        <div class='kpi'><div class='label'>Pasarelas</div><div class='value'>{_esc(pas_state.title())}</div>{_pill(pas_state)}<br><a class='detail-btn' href='../ECOLLECT/dashboard_verticales.html'>Ver detalle</a></div>
        <div class='kpi'><div class='label'>AWS</div><div class='value'>{_esc(aws_state.title())}</div>{_pill(aws_state)}<br><a class='detail-btn' href='../AWS/Dashboard_AWS.html'>Ver detalle</a></div>
        <div class='kpi'><div class='label'>Hércules</div><div class='value'>{_esc(her_state.title())}</div>{_pill(her_state)}<br><a class='detail-btn' href='../HERCULES/DASHBOARD_HERCULES.html'>Ver detalle</a></div>
        <div class='kpi'><div class='label'>Novedades relevantes</div><div class='value'>{alerts}</div><div style='margin-top:6px;color:var(--muted);font-size:11px'>Solo novedades operativas, no estado técnico del bot.</div></div>
      </section>
      {main_content}
      <div class='shot'><div class='shot-label'><strong>Alertas y motivos</strong><span>Explicación operativa del corte</span></div><section class='card'><div class='card-body'>{_alerts_html(novedades)}</div></section></div>
      <div class='footer'>Dashboard gerencial automático · sin logs, rutas, workers ni tiempos técnicos</div>
    </main></body></html>"""

    out = general / "Dashboard_General.html"
    out.write_text(html_page, encoding="utf-8")
    return out
