from __future__ import annotations
from html import escape
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import re


def _num(value) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _fmt(value) -> str:
    return 'N/D' if value is None else f'{_num(value):,}'.replace(',', '.')


def _bogota_tz():
    try:
        return ZoneInfo("America/Bogota")
    except ZoneInfoNotFoundError:
        from datetime import timedelta, timezone as dt_timezone
        return dt_timezone(timedelta(hours=-5), name="America/Bogota")


def _parse_aws_datetime(value):
    """Interpreta timestamps de CloudWatch como UTC y los convierte a Bogotá.

    Los valores que solo contienen HH:MM se conservan, porque no incluyen
    información suficiente para determinar si están en UTC o ya son locales.
    """
    text = str(value or "").strip()
    if not text or not re.search(r"\d{4}-\d{2}-\d{2}", text):
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        match = re.search(r"(\d{4}-\d{2}-\d{2})[T\s](\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?)", text)
        if not match:
            return None
        try:
            dt = datetime.fromisoformat(f"{match.group(1)}T{match.group(2)}")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_bogota_tz())


def _hour_label(value) -> str:
    local_dt = _parse_aws_datetime(value)
    if local_dt is not None:
        return local_dt.strftime("%H:%M")
    text = str(value or "").strip()
    simple = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if simple:
        return f"{int(simple.group(1)):02d}:{simple.group(2)}"
    matches = re.findall(r"(?:^|[T\s])(\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?", text)
    if matches:
        hour, minute = matches[-1]
        return f"{int(hour):02d}:{minute}"
    return text


def _datetime_label(value) -> str:
    local_dt = _parse_aws_datetime(value)
    if local_dt is not None:
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")
    return str(value or "")


def _series_sort_key(value):
    local_dt = _parse_aws_datetime(value)
    if local_dt is not None:
        return (0, local_dt)
    return (1, str(value or ''))


def _normalize_series(rows: list[dict]) -> list[dict]:
    normalized = []
    for row in rows or []:
        raw = row.get('hora') or row.get('@timestamp') or row.get('desde') or ''
        local_dt = _parse_aws_datetime(raw)
        hora_value = local_dt.isoformat() if local_dt is not None else str(raw)
        normalized.append({'hora': hora_value, 'count': _num(row.get('count'))})
    normalized.sort(key=lambda r: _series_sort_key(r.get('hora')))
    return normalized


def _detail_series_from_rows(detail_rows: list[dict]) -> list[dict]:
    points = []
    for row in detail_rows or []:
        raw = row.get('desde') or row.get('@timestamp') or row.get('hora') or ''
        local_dt = _parse_aws_datetime(raw)
        hora_value = local_dt.isoformat() if local_dt is not None else str(raw)
        points.append({'hora': hora_value, 'count': _num(row.get('count'))})
    points.sort(key=lambda r: _series_sort_key(r.get('hora')))
    return points


def _peak(rows):
    if not rows:
        return '', 0
    best = max(rows, key=lambda r: _num(r.get('count')))
    return _hour_label(best.get('hora', '')), _num(best.get('count'))



def _sr_summary(data: dict) -> dict:
    rows = (data.get("detalles") or {}).get("serviciosred_ultima_hora", []) or []
    if rows and isinstance(rows[0], dict):
        return rows[0]
    return {}


def _sr_last_label(data: dict) -> str:
    raw = _sr_summary(data).get("ultima_notificacion", "")
    return _datetime_label(raw) if raw else "Sin registro en la última hora"


def _sr_chart_rows(data: dict) -> list[tuple[str, int]]:
    rows = (data.get("detalles") or {}).get("serviciosred_10m_ultima_hora", []) or []
    series = _normalize_series(rows)
    return [(_hour_label(r.get('hora', '')), _num(r.get('count'))) for r in series]


def _sr_gap_label(data: dict) -> str:
    raw = _sr_summary(data).get('ultima_notificacion', '')
    end = _sr_summary(data).get('hasta', '')
    last_dt = _parse_aws_datetime(raw)
    end_dt = _parse_aws_datetime(end)
    if last_dt is None or end_dt is None:
        return 'N/D'
    minutes = max(0, int((end_dt - last_dt).total_seconds() / 60))
    return f"hace {minutes} min"

def _logo_block() -> str:
    return '''<div class="brand">
    <div class="brand-icon">
      <span class="dot orange"></span><span class="dot green"></span><span class="dot amber"></span>
    </div>
    <div class="brand-text"><strong>Compensar</strong><small>Monitoreo AWS</small></div>
  </div>'''


def _svg_bars(rows, width=800, height=250, bar_color='#E36C0A') -> str:
    if not rows:
        return '<div class="empty">Sin datos para graficar.</div>'
    maxv = max([_num(v) for _, v in rows] + [1])
    left, right, top, bottom = 56, 22, 28, 56
    pw, ph = width - left - right, height - top - bottom
    bar_w = max(26, pw / max(len(rows) * 1.55, 1))
    gap = (pw - len(rows) * bar_w) / max(len(rows), 1)
    parts = [
        f'<svg viewBox="0 0 {width} {height}">',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" class="axis"/>',
        f'<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" class="axis"/>'
    ]
    for idx, (label, value) in enumerate(rows):
        n = _num(value)
        x = left + gap / 2 + idx * (bar_w + gap)
        h = (n / maxv) * ph if maxv else 0
        y = top + ph - h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="10" class="bar" fill="{bar_color}"/>')
        parts.append(f'<text x="{x + bar_w/2:.1f}" y="{max(y-8,14):.1f}" text-anchor="middle" class="value">{n}</text>')
        parts.append(f'<text x="{x + bar_w/2:.1f}" y="{height-bottom+20}" text-anchor="middle" class="label">{escape(label)}</text>')
    parts.append('</svg>')
    return ''.join(parts)


def _svg_line(rows, width=800, height=270, stroke='#78BE20') -> str:
    ordered_rows = sorted(rows or [], key=lambda r: _series_sort_key(r.get('hora')))
    pts = [(_hour_label(r.get('hora', '')), _num(r.get('count'))) for r in ordered_rows]
    if not pts:
        return '<div class="empty">Sin datos horarios para graficar.</div>'
    maxv = max([v for _, v in pts] + [1])
    peak_index = max(range(len(pts)), key=lambda i: pts[i][1])
    left, right, top, bottom = 58, 24, 38, 68
    pw, ph = width - left - right, height - top - bottom
    coords = []
    for i, (_, v) in enumerate(pts):
        x = left + (pw * i / max(len(pts) - 1, 1))
        y = top + ph - (v / maxv) * ph
        coords.append((x, y, v))
    poly = ' '.join(f'{x:.1f},{y:.1f}' for x, y, _ in coords)
    out = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Tendencia por hora">',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" class="axis"/>',
        f'<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" class="axis"/>',
        f'<text x="{left-34}" y="{top+ph/2:.1f}" text-anchor="middle" class="axis-title" transform="rotate(-90 {left-34} {top+ph/2:.1f})">Cantidad</text>',
        f'<text x="{left+pw/2:.1f}" y="{height-8}" text-anchor="middle" class="axis-title">Hora</text>',
        f'<polyline points="{poly}" class="line" stroke="{stroke}"/>'
    ]
    show_every = 1 if len(pts) <= 16 else max(1, len(pts) // 12)
    for i, (x, y, v) in enumerate(coords):
        is_peak = i == peak_index
        radius = 7 if is_peak else 4.5
        css = 'dot peak-dot' if is_peak else 'dot'
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" class="{css}" stroke="{stroke}"><title>{pts[i][0]}: {v}</title></circle>')
        out.append(f'<text x="{x:.1f}" y="{max(y-10,16):.1f}" text-anchor="middle" class="{"point-value peak-value" if is_peak else "point-value"}">{v}</text>')
        if i % show_every == 0 or i == len(pts) - 1:
            out.append(f'<text x="{x:.1f}" y="{height-bottom+23}" text-anchor="middle" class="label hour-label">{escape(pts[i][0])}</text>')
        if is_peak:
            out.append(f'<text x="{x:.1f}" y="{max(y-25,12):.1f}" text-anchor="middle" class="peak-caption">Pico</text>')
    out.append('</svg>')
    return ''.join(out)


def _status_text(n, warn=None, zero_bad=False):
    if n is None:
        return 'SIN DATO', 'nodata'
    value = _num(n)
    if zero_bad and value == 0:
        return 'SIN INFORMACIÓN', 'bad'
    if warn is not None and value >= warn:
        return 'ALERTA', 'bad'
    return 'NORMALIDAD', 'good'



def _tup_status(value):
    if value is None:
        return 'SIN DATO', 'nodata', 'No fue posible consultar los errores de Tarjeta TUP.'
    n = _num(value)
    if n >= 251:
        return 'ALERTA CRÍTICA', 'bad', f'{n} errores: supera el umbral crítico de 250.'
    if n >= 201:
        return 'ALERTA', 'bad', f'{n} errores: nivel de atención 201–250.'
    if n >= 31:
        return 'REVISAR', 'warn', f'{n} errores: supera el nivel normal (máximo 30).'
    return 'NORMALIDAD', 'good', f'{n} errores: dentro del rango normal configurado (0–30).'


def _group_error_rows(detail_rows: list[dict]) -> list[dict]:
    return _detail_series_from_rows(detail_rows)


def _panel_message(total_errors: int) -> str:
    if total_errors <= 0:
        return '<div class="ok-panel"><span class="ok-badge">FUNCIONANDO CORRECTAMENTE</span><p>Sin errores en el corte.</p></div>'
    return '<div class="warn-panel"><span class="warn-badge">SIN SERIE HORARIA</span><p>Se detectaron errores, pero no fue posible construir la gráfica por hora.</p></div>'


def generar_html(path: Path, cfg: dict, ventana, data: dict, alertas: list[dict]) -> Path:
    m = data['metricas']
    d = data['detalles']

    pagos_ok = sum(_num(m.get(k)) for k in ('aprob_creacion_payu', 'aprob_creacion_ecollect', 'aprob_estado_payu', 'aprob_estado_ecollect', 'aprob_receiver'))
    pagos_err = sum(_num(m.get(k)) for k in ('err_creacion_payu', 'err_creacion_ecollect', 'err_estado_payu', 'err_estado_ecollect', 'err_receiver'))
    mens_err = _num(m.get('mens_timeout')) + _num(m.get('mens_503')) + _num(m.get('mens_502')) + _num(m.get('mens_cannot')) + _num(m.get('mens_sms_failed')) + _num(m.get('mens_error_400_total')) + _num(m.get('otp_408'))
    csc_total = _num(m.get('csc_504')) + _num(m.get('csc_task_timed'))
    tup_status, tup_status_cls, tup_status_reason = _tup_status(m.get('tup_error'))

    # Serie de errores de mensajería: primero intenta una serie dedicada; si no existe,
    # la arma con el detalle de errores (útil cuando hay 408/500/etc. aunque no haya 400).
    pagos_series = _normalize_series(d.get('pagos_errores_por_hora') or [])
    tup_series = _normalize_series(d.get('tup_por_hora') or [])
    mens_error_series = _normalize_series(d.get('mensajeria_errores_por_hora') or [])
    if not mens_error_series:
        mens_error_series = _group_error_rows(d.get('mensajeria_errores', []))

    tup_peak_h, tup_peak_n = _peak(tup_series)
    pay_peak_h, pay_peak_n = _peak(pagos_series)
    menerr_peak_h, menerr_peak_n = _peak(mens_error_series)
    mens_detail_total = sum(_num(r.get('count')) for r in mens_error_series)

    cards = [
        ('API Pagos aprobadas', pagos_ok, 'INTEROPPROD', 'ok'),
        ('API Pagos errores', pagos_err, 'INTEROPPROD', 'bad' if pagos_err >= 41 else 'ok'),
        ('CSC errores', csc_total, 'CSC', 'warn' if csc_total > 0 else 'ok'),
        ('Mensajería total sent', _num(m.get('mens_total_send')), 'MENSAJERÍA', 'ok'),
        ('Mensajería errores', mens_err, 'MENSAJERÍA', 'warn' if mens_err > 0 else 'ok'),
        ('Replicaciones', _num(m.get('replicador')), 'REPLICADOR', 'bad' if _num(m.get('replicador')) == 0 else 'ok'),
        ('Tarjeta TUP errores', _num(m.get('tup_error')), 'TARJETA TUP', 'bad' if _num(m.get('tup_error')) > 250 else 'warn' if _num(m.get('tup_error')) > 30 else 'ok'),
        ('Error archivo CX', _num(m.get('error_cx')), 'API SUBSIDIOS', 'bad' if _num(m.get('error_cx')) > 0 else 'ok'),
    ]
    cards_html = ''.join(
        f'<article class="kpi {state}"><span>{escape(group)}</span><h3>{escape(title)}</h3><strong>{_fmt(value)}</strong></article>'
        for title, value, group, state in cards
    )

    if alertas:
        alerts_html = ''.join(
            f'<div class="alert {a["nivel"].lower().replace("í", "i")}"><div><b>{escape(a["nivel"])} · {escape(a["grupo"])} / {escape(a["servicio"])} </b><span>{escape(a["metrica"])}: {escape(str(a["valor"]))}</span></div><p>{escape(a["detalle"])}</p></div>'
            for a in alertas[:10]
        )
    else:
        alerts_html = '<div class="all-ok">✓ Sin alertas activas en el corte.</div>'

    capture_cards = [
        ('Pagos', f'Aprobadas {_fmt(pagos_ok)} · Errores {_fmt(pagos_err)}'),
        ('CSC', f'Errores {_fmt(csc_total)}'),
        ('Mensajería', f'Total {_fmt(m.get("mens_total_send"))} · Errores {_fmt(mens_err)}'),
        ('Replicador', f'Replicaciones {_fmt(m.get("replicador"))}'),
        ('TUP', f'Errores {_fmt(m.get("tup_error"))} · Pico {escape(tup_peak_h or "N/D")} / {_fmt(tup_peak_n)}'),
        ('API Subsidios', f'Error CX {_fmt(m.get("error_cx"))}'),
    ]
    capture_html = ''.join(f'<div class="cap-item"><b>{escape(a)}</b><span>{escape(b)}</span></div>' for a, b in capture_cards)

    charts = {
        'volumen': _svg_bars([
            ('Pagos OK', pagos_ok), ('Pagos Error', pagos_err), ('CSC', csc_total), ('Mens 200', _num(m.get('mens_exitos_200_total'))),
            ('Mens Error', mens_err), ('Replicador', _num(m.get('replicador'))), ('TUP', _num(m.get('tup_error'))), ('CX', _num(m.get('error_cx'))),
        ], bar_color='#E36C0A'),
        'pagos_hora': _svg_line(pagos_series, stroke='#E36C0A') if pagos_series else _panel_message(pagos_err),
        'tup_hora': _svg_line(tup_series, stroke='#F6A53A') if tup_series else _panel_message(_num(m.get('tup_error'))),
        'mens_error_hora': _svg_line(mens_error_series, stroke='#C62828') if mens_error_series else _panel_message(mens_err),
    }

    pagos_200_rows = []
    for proceso, prov, key in [
        ('Creación de pago', 'PayU', 'aprob_creacion_payu'),
        ('Creación de pago', 'Ecollect', 'aprob_creacion_ecollect'),
        ('Estado de transacciones', 'PayU', 'aprob_estado_payu'),
        ('Estado de transacciones', 'Ecollect', 'aprob_estado_ecollect'),
        ('Notificación al bus', 'Receiver', 'aprob_receiver'),
    ]:
        st, cls = _status_text(m.get(key), zero_bad=True)
        pagos_200_rows.append(f'<tr><td>{escape(proceso)}</td><td>{escape(prov)}</td><td>{_fmt(m.get(key))}</td><td><span class="pill {cls}">{st}</span></td></tr>')

    pagos_error_rows = []
    for proceso, prov, key in [
        ('Creación de pago', 'PayU', 'err_creacion_payu'),
        ('Creación de pago', 'Ecollect', 'err_creacion_ecollect'),
        ('Estado de transacciones', 'PayU', 'err_estado_payu'),
        ('Estado de transacciones', 'Ecollect', 'err_estado_ecollect'),
        ('Notificación al bus', 'Receiver', 'err_receiver'),
    ]:
        st, cls = _status_text(m.get(key), warn=41)
        pagos_error_rows.append(f'<tr><td>{escape(proceso)}</td><td>{escape(prov)}</td><td>{_fmt(m.get(key))}</td><td><span class="pill {cls}">{st}</span></td></tr>')

    mens_trans_rows = ''.join([
        f'<tr><td>API Mensajería (REPORT)</td><td>{_fmt(m.get("mens_total_send"))}</td><td><span class="pill good">NORMALIDAD</span></td><td>Total sent del corte</td></tr>',
        f'<tr><td>Replicador corporativo</td><td>{_fmt(m.get("replicador"))}</td><td><span class="pill {"good" if _num(m.get("replicador")) > 0 else "bad"}">{"NORMALIDAD" if _num(m.get("replicador")) > 0 else "ALERTA"}</span></td><td>Debe replicar mínimo 1 vez</td></tr>',
        f'<tr><td>Validar OTP 500</td><td>{_fmt(m.get("otp_500"))}</td><td><span class="pill {"good" if _num(m.get("otp_500")) == 0 else "bad"}">{"NORMALIDAD" if _num(m.get("otp_500")) == 0 else "ALERTA"}</span></td><td>Error 500 de ValidarOTP</td></tr>',
        f'<tr><td>EXITOSOS 200</td><td>{_fmt(m.get("mens_exitos_200_total"))}</td><td><span class="pill good">REGISTRADO</span></td><td>Consolidado de 200</td></tr>',
    ])

    mens_error_rows = ''.join([
        f'<tr><td>Timeout</td><td>{_fmt(m.get("mens_timeout"))}</td><td>Timeout general</td></tr>',
        f'<tr><td>Error 503</td><td>{_fmt(m.get("mens_503"))}</td><td>Service Temporarily Unavailable</td></tr>',
        f'<tr><td>Error 502</td><td>{_fmt(m.get("mens_502"))}</td><td>Bad Gateway</td></tr>',
        f'<tr><td>Error Cannot</td><td>{_fmt(m.get("mens_cannot"))}</td><td>Broker SD / Httpcode != 200</td></tr>',
        f'<tr><td>SMS failed</td><td>{_fmt(m.get("mens_sms_failed"))}</td><td>Falla de envío SMS</td></tr>',
        f'<tr><td>Error 400</td><td>{_fmt(m.get("mens_error_400_total"))}</td><td>Mayor a 100 del mismo dato = alerta crítica</td></tr>',
        f'<tr><td>OTP 408</td><td>{_fmt(m.get("otp_408"))}</td><td>Errores 408 de OTP</td></tr>',
    ])

    mens_200_rows = ''.join(
        f'<tr><td>{escape(str(r.get("IdConsumer", "")))}</td><td>{escape(str(r.get("MessageIn.configS3.Broker", "")))}</td><td>{escape(str(r.get("OperationInvokerName", "")))}</td><td>{_fmt(r.get("count"))}</td></tr>'
        for r in d.get('mensajeria_exitos', [])[:12]
    ) or '<tr><td colspan="4" class="empty-cell">Sin detalle de 200 para mostrar.</td></tr>'

    mens_detail_rows = ''.join(
        f'<tr><td>{escape(str(r.get("IdConsumer", "")))}</td><td>{escape(str(r.get("MessageIn.configS3.Broker", "")))}</td><td>{escape(str(r.get("Httpcode", "")))}</td><td>{escape(str(r.get("OperationInvokerName", "")))}</td><td>{escape(str(r.get("MessageOut.error") or r.get("MessageOut") or ""))}</td><td>{_fmt(r.get("count"))}</td><td>{escape(_datetime_label(r.get("desde", "")))}</td><td>{escape(_datetime_label(r.get("hasta", "")))}</td></tr>'
        for r in d.get('mensajeria_errores', [])[:18]
    ) or '<tr><td colspan="8" class="empty-cell">Sin detalle de errores.</td></tr>'

    csc_rows = ''.join([
        f'<tr><td>Lambda Proxy PaymentsPost</td><td>504 Gateway Time-out</td><td>{_fmt(m.get("csc_504"))}</td><td><span class="pill {_status_text(m.get("csc_504"), warn=1)[1]}">{_status_text(m.get("csc_504"), warn=1)[0]}</span></td></tr>',
        f'<tr><td>Lambda Proxy PaymentsPost</td><td>Task timed</td><td>{_fmt(m.get("csc_task_timed"))}</td><td><span class="pill {_status_text(m.get("csc_task_timed"), warn=1)[1]}">{_status_text(m.get("csc_task_timed"), warn=1)[0]}</span></td></tr>',
    ])
    subsidios_rows = ''.join([
        f'<tr><td>API Subsidios - Error archivo CX</td><td>{_fmt(m.get("error_cx"))}</td><td><span class="pill {"bad" if _num(m.get("error_cx")) > 0 else "good"}">{"ALERTA" if _num(m.get("error_cx")) > 0 else "NORMALIDAD"}</span></td></tr>',
    ])
    seguridad_rows = ''.join([
        f'<tr><td>API Módulo Seguridad - ConsultaPersona</td><td>{_fmt(m.get("seg_consulta_persona"))}</td><td><span class="pill good">REGISTRADO</span></td></tr>',
    ])

    html = f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Monitoreo AWS</title>
<style>
:root{{--orange:#E36C0A;--orange2:#F28C28;--amber:#F6A53A;--green:#78BE20;--green2:#5A9E1F;--bg:#FFF8F1;--card:#FFFFFF;--text:#4D3C28;--muted:#7A6A57;--line:#EADCCF;--good:#5A9E1F;--goodbg:#EEF7E8;--warn:#F29E21;--warnbg:#FFF4E6;--bad:#C62828;--badbg:#FDECEC;--shadow:0 10px 24px rgba(152,82,20,.08)}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);font-family:Segoe UI,Arial,sans-serif;color:var(--text)}}
header{{background:linear-gradient(120deg,#E36C0A,#F28C28 55%,#78BE20);color:white;padding:24px 3vw 20px}}
header .top{{display:flex;justify-content:space-between;align-items:center;gap:20px;flex-wrap:wrap}}header h1{{margin:0 0 6px;font-size:34px;letter-spacing:.2px}}header p{{margin:3px 0;opacity:.96}}
.brand{{display:flex;align-items:center;gap:12px;background:rgba(255,255,255,.18);padding:10px 14px;border-radius:16px;backdrop-filter:blur(4px)}}.brand-icon{{position:relative;width:36px;height:36px}}.dot{{position:absolute;border-radius:50%}}.dot.orange{{width:24px;height:24px;left:0;top:10px;background:#fff}}.dot.green{{width:16px;height:16px;left:16px;top:2px;background:#DAF0B8}}.dot.amber{{width:18px;height:18px;left:10px;top:18px;background:#FFE0B5;opacity:.9}}.brand-text strong{{display:block;font-size:20px;color:#fff}}.brand-text small{{display:block;color:#fff;opacity:.92}}
main{{max-width:1800px;margin:auto;padding:18px 3vw 36px}}section{{margin-bottom:18px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}.kpi,.panel,.cap-board,.mini-panel{{background:var(--card);border:1px solid #F0E3D6;border-radius:18px;box-shadow:var(--shadow)}}
.kpi{{padding:15px 16px;position:relative;overflow:hidden}}.kpi:before{{content:"";position:absolute;left:0;top:0;bottom:0;width:6px;background:var(--orange2)}}.kpi.ok:before{{background:var(--good)}}.kpi.warn:before{{background:var(--warn)}}.kpi.bad:before{{background:var(--bad)}}.kpi span{{font-size:11px;font-weight:700;color:var(--muted);letter-spacing:.7px}}.kpi h3{{font-size:15px;margin:7px 0 9px}}.kpi strong{{font-size:28px;color:#6A3A12}}
.h2{{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:10px;flex-wrap:wrap}}h2{{margin:0;font-size:24px;color:#7A3F0E}}.tag{{padding:6px 10px;border-radius:999px;background:#FFF0DE;color:#9A5B1A;font-size:12px;font-weight:700}}
.cap-board{{padding:16px}}.cap-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}.cap-item{{background:#FFF7ED;border:1px solid #F2DEC6;border-radius:14px;padding:12px}}.cap-item b{{display:block;font-size:13px;color:#9C560F;margin-bottom:6px}}.cap-item span{{font-size:13px;color:#5A4A35}}
.alert{{background:white;border-radius:14px;padding:13px 16px;margin-bottom:9px;border-left:6px solid var(--warn);box-shadow:0 6px 16px rgba(152,82,20,.06)}}.alert.critica{{border-color:var(--bad)}}.alert.alta{{border-color:#D86B2B}}.alert.media{{border-color:var(--warn)}}.alert div{{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}}.alert p{{margin:8px 0 0;color:var(--muted)}}.all-ok{{background:var(--goodbg);color:var(--good);padding:16px;border-radius:14px;font-weight:700}}
.grid-2{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}.grid-3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}}.panel{{padding:16px;overflow:auto}}.panel h3{{margin:0 0 10px;color:#7A3F0E;font-size:20px}}.panel h4{{margin:16px 0 8px;color:#9A5B1A;font-size:15px;text-transform:uppercase;letter-spacing:.4px}}.mini-panel{{padding:14px}}
svg{{width:100%;min-width:520px;height:auto}}.axis{{stroke:#E2D4C5;stroke-width:1.1}}.line{{fill:none;stroke-width:4;stroke-linejoin:round;stroke-linecap:round}}.dot{{fill:white;stroke-width:3}}.peak-dot{{fill:#fff6f3}}.axis-title{{font-size:13px;fill:#7A6A57;font-weight:700}}.point-value{{font-size:12px;fill:#1D1D1D;font-weight:700}}.peak-value{{font-size:14px;fill:#000;font-weight:800}}.peak-caption{{font-size:12px;fill:#000;font-weight:800}}.value{{font-size:12px;fill:#7A3F0E;font-weight:700}}.label{{font-size:11px;fill:#8A765F}}
.table-wrap{{overflow:auto}}table{{width:100%;border-collapse:collapse;font-size:13px}}th{{background:#E36C0A;color:white;padding:10px;text-align:left;position:sticky;top:0}}td{{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}}tr:nth-child(even) td{{background:#FFFDF9}}.subtable.teal th{{background:#78BE20}}.subtable.red th{{background:#C62828}}.subtable.orange th{{background:#F28C28}}
.pill{{display:inline-block;padding:4px 9px;border-radius:999px;font-size:11px;font-weight:800}}.pill.good{{background:var(--goodbg);color:var(--good)}}.pill.bad{{background:var(--badbg);color:var(--bad)}}.pill.warn{{background:var(--warnbg);color:var(--warn)}}.pill.nodata{{background:#F2F0EC;color:#7A6A57}}
.highlight{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}}.stat{{padding:12px;border-radius:14px;background:#FFF7ED;border:1px solid #F2DEC6}}.stat b{{display:block;color:var(--muted);font-size:12px;margin-bottom:6px}}.stat strong{{font-size:20px;color:#7A3F0E}}
.ok-panel,.warn-panel{{padding:24px 18px;text-align:center;border-radius:16px;border:1px solid #F2DEC6;background:#FFF7ED;min-height:220px;display:flex;flex-direction:column;justify-content:center;align-items:center}}.ok-badge,.warn-badge{{display:inline-block;padding:10px 16px;border-radius:999px;font-weight:800;margin-bottom:10px}}.ok-badge{{background:var(--goodbg);color:var(--good)}}.warn-badge{{background:var(--warnbg);color:var(--warn)}}
.empty,.empty-cell{{padding:16px;color:var(--muted);text-align:center}}footer{{padding:18px 3vw 30px;color:var(--muted);font-size:12px}}
@media(max-width:1100px){{.grid-2,.grid-3,.highlight,.cap-grid{{grid-template-columns:1fr}}svg{{min-width:unset}}}}
</style></head><body>
<header><div class="top"><div><h1>Monitoreo AWS</h1><p>{escape(ventana.nombre)} · {escape(ventana.texto)}</p><p>Analista: {escape(cfg['app']['analista'])}</p></div>{_logo_block()}</div></header>
<main>
<section class="cap-board"><div class="h2"><h2>Vista rápida del monitoreo</h2><span class="tag">Lista para captura</span></div><div class="cap-grid">{capture_html}</div></section>
<section class="kpis">{cards_html}</section>
<section><div class="h2"><h2>Alertas detectadas</h2><span class="tag">{len(alertas)} activas</span></div>{alerts_html}</section>
<section class="grid-2"><article class="panel"><h3>Resumen visual del corte</h3>{charts['volumen']}</article><article class="panel"><h3>Tarjeta TUP por hora</h3>{charts['tup_hora']}<div class="highlight"><div class="stat"><b>Total errores TUP</b><strong>{_fmt(m.get('tup_error'))}</strong></div><div class="stat"><b>Hora pico</b><strong>{escape(tup_peak_h or 'N/D')}</strong></div><div class="stat"><b>Pico</b><strong>{_fmt(tup_peak_n)}</strong></div></div></article></section>
<section class="grid-2"><article class="panel"><h3>Pagos por hora</h3>{charts['pagos_hora']}<div class="highlight"><div class="stat"><b>Pico pagos</b><strong>{escape(pay_peak_h or 'N/D')}</strong></div><div class="stat"><b>Valor pico</b><strong>{_fmt(pay_peak_n)}</strong></div><div class="stat"><b>Errores totales pagos</b><strong>{_fmt(pagos_err)}</strong></div></div></article><article class="panel"><h3>Mensajería · detalle de errores por hora</h3>{charts['mens_error_hora']}<div class="highlight"><div class="stat"><b>Hora pico detalle</b><strong>{escape(menerr_peak_h or 'N/D')}</strong></div><div class="stat"><b>Valor pico detalle</b><strong>{_fmt(menerr_peak_n)}</strong></div><div class="stat"><b>Total detalle errores</b><strong>{_fmt(mens_detail_total)}</strong></div></div></article></section>
<section class="panel"><div class="h2"><h2>API Pagos</h2><span class="tag">Separado en 200 y errores</span></div><h4>200 / TRANSACCIONES APROBADAS</h4><div class="table-wrap"><table class="subtable orange"><thead><tr><th>Proceso</th><th>Proveedor</th><th>Resultado</th><th>Estado</th></tr></thead><tbody>{''.join(pagos_200_rows)}</tbody></table></div><h4>ERRORES</h4><div class="table-wrap"><table class="subtable red"><thead><tr><th>Proceso</th><th>Proveedor</th><th>Resultado</th><th>Estado</th></tr></thead><tbody>{''.join(pagos_error_rows)}</tbody></table></div></section>
<section class="grid-3"><article class="panel"><div class="h2"><h2>CSC</h2><span class="tag">Detalle</span></div><div class="table-wrap"><table class="subtable orange"><thead><tr><th>Componente</th><th>Métrica</th><th>Resultado</th><th>Estado</th></tr></thead><tbody>{csc_rows}</tbody></table></div></article><article class="panel"><div class="h2"><h2>API Subsidios</h2><span class="tag">Control</span></div><div class="table-wrap"><table class="subtable teal"><thead><tr><th>Servicio</th><th>Resultado</th><th>Estado</th></tr></thead><tbody>{subsidios_rows}</tbody></table></div></article><article class="panel"><div class="h2"><h2>Módulo de Seguridad</h2><span class="tag">Transaccionalidad</span></div><div class="table-wrap"><table class="subtable teal"><thead><tr><th>Servicio</th><th>Resultado</th><th>Estado</th></tr></thead><tbody>{seguridad_rows}</tbody></table></div></article></section>
<section class="panel"><div class="h2"><h2>Servicios Red · notificaciones TUP</h2><span class="tag">INTEROPPROD · última hora · cada 10 minutos</span></div>
<div class="highlight">
<div class="stat"><b>Notificaciones última hora</b><strong>{_fmt(m.get('serviciosred_ultima_hora'))}</strong></div>
<div class="stat"><b>Última notificación</b><strong>{escape(_sr_last_label(data))}</strong></div>
<div class="stat"><b>Tiempo desde la última</b><strong>{escape(_sr_gap_label(data))}</strong></div>
</div>
<div class="sr-chart-wrap"><p class="sr-caption">Comportamiento de notificaciones en la última hora. Sirve para ver huecos o caída de actividad.</p>{_svg_bars(_sr_chart_rows(data), width=820, height=260, bar_color='#0B5CAB')}<div class="sr-legend"><span><i class="sr-dot"></i> Cada barra representa 10 minutos</span><span><i class="sr-dot" style="background:#F26B1D"></i> El cruce funcional con 41610 TUP se evalúa en el Dashboard General</span></div></div>
<p style="color:var(--muted);font-size:12px;margin:12px 0 0">AWS por sí solo no genera alerta por cero actividad. El Dashboard General cruza este dato con 41610 · TUP aprobadas para evitar falsas alertas en periodos sin compras.</p>
</section>
<section class="panel"><div class="h2"><h2>Mensajería</h2><span class="tag">Transaccionalidad, 200, errores y detalle</span></div><div class="grid-3"><article class="mini-panel"><h4>TRANSACCIONALIDAD</h4><div class="table-wrap"><table class="subtable teal"><thead><tr><th>Servicio</th><th>Resultado</th><th>Estado</th><th>Observación</th></tr></thead><tbody>{mens_trans_rows}</tbody></table></div></article><article class="mini-panel"><h4>ERRORES</h4><div class="table-wrap"><table class="subtable red"><thead><tr><th>Métrica</th><th>Resultado</th><th>Detalle</th></tr></thead><tbody>{mens_error_rows}</tbody></table></div></article><article class="mini-panel"><h4>EXITOSOS 200</h4><div class="table-wrap"><table class="subtable orange"><thead><tr><th>IdConsumer</th><th>Broker</th><th>Operación</th><th>Cantidad</th></tr></thead><tbody>{mens_200_rows}</tbody></table></div></article></div><h4>DETALLE DE ERRORES</h4><div class="table-wrap"><table><thead><tr><th>IdConsumer</th><th>Broker</th><th>HTTP</th><th>Operación</th><th>Tipología</th><th>Cantidad</th><th>Desde</th><th>Hasta</th></tr></thead><tbody>{mens_detail_rows}</tbody></table></div></section>
</main><footer>Reporte generado automáticamente. Umbrales configurables en config/config.yaml.</footer></body></html>'''

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding='utf-8')
    return path
