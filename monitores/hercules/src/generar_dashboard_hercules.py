from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import html
import re
import unicodedata

import pandas as pd

from config import REPORTS_DIR, SHAREPOINT_SYNC_DIR, HERCULES_DIAS_ATRAS_DIARIO, HERCULES_DIAS_ATRAS_ACUMULADO, MES_CONSOLIDAR


def _normalizar(texto: str) -> str:
    texto = "" if texto is None else str(texto)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower().strip()
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _buscar_columna(df: pd.DataFrame, posibles: list[str]) -> str | None:
    mapa = {_normalizar(c): c for c in df.columns}
    posibles_norm = [_normalizar(p) for p in posibles]
    for p in posibles_norm:
        if p in mapa:
            return mapa[p]
    for col_norm, col_real in mapa.items():
        for p in posibles_norm:
            if p in col_norm or col_norm in p:
                return col_real
    return None


def _normalizar_forma_pago(texto: str) -> str:
    t = _normalizar(texto).replace(".", " ")
    t = re.sub(r"\s+", " ", t).strip()
    if t in {"tc", "tarjeta credito", "tarjeta de credito", "credito"}:
        return "TC"
    if t in {"td", "tarjeta debito", "tarjeta de debito", "debito"}:
        return "TD"
    if t in {"t compensar", "tarjeta compensar", "compensar"}:
        return "T. Compensar"
    original = str(texto).strip()
    return original if original else "(en blanco)"


def _normalizar_canal(texto: str) -> str:
    t = _normalizar(texto)
    if t == "web":
        return "Web"
    if t == "pai":
        return "PAI"
    if t in {"modulos", "modulo", "módulos", "módulo"}:
        return "Módulos"
    if t in {"presencial", "precencial"}:
        return "Presencial"
    original = str(texto).strip()
    return original if original else "(en blanco)"


def _fmt_num(n) -> str:
    try:
        return f"{int(n):,}".replace(",", ".")
    except Exception:
        return str(n)


def _pct(value: int, total: int) -> str:
    if not total:
        return "0%"
    return f"{(value / total) * 100:.1f}%".replace(".", ",")


def _fecha_reporte() -> str:
    return (datetime.now() - timedelta(days=HERCULES_DIAS_ATRAS_DIARIO)).strftime("%Y-%m-%d")


def _mes_reporte() -> str:
    if MES_CONSOLIDAR:
        return MES_CONSOLIDAR.replace("-", "_")
    return (datetime.now() - timedelta(days=HERCULES_DIAS_ATRAS_ACUMULADO)).strftime("%Y_%m")


def _leer_base_resumen(path: Path) -> pd.DataFrame:
    hojas = pd.read_excel(path, sheet_name=None)
    if "Base_Consolidada" in hojas:
        df = hojas["Base_Consolidada"].copy()
    else:
        bases = []
        for nombre, hoja in hojas.items():
            if nombre.lower().startswith("base_"):
                temp = hoja.copy()
                if "Opción" not in temp.columns and "Opcion" not in temp.columns:
                    temp["Opción"] = nombre.replace("Base_", "")
                bases.append(temp)
        if not bases:
            raise RuntimeError("No encontré Base_Consolidada ni hojas Base_*")
        df = pd.concat(bases, ignore_index=True)
    return df.dropna(how="all").copy()


def _preparar(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    col_estado = _buscar_columna(df, ["Estado Cotización", "Estado Cotizacion"])
    col_canal = _buscar_columna(df, ["Canal de Cotización", "Canal de Cotizacion", "Canal que Cotizó", "Canal que Cotizo", "Canal"])
    col_forma = _buscar_columna(df, ["Forma de Pago", "Pago Realizado", "Medio de Pago"])
    col_opcion = _buscar_columna(df, ["Opción", "Opcion", "Módulo", "Modulo", "Fuente"])
    col_fecha_tx = _buscar_columna(df, ["Fecha Transacción", "Fecha Transaccion", "Fecha Cotización", "Fecha Cotizacion", "Fecha_Reporte"])
    col_hora = _buscar_columna(df, ["Hora Registro", "Hora Transacción", "Hora Transaccion"])

    df["__estado"] = df[col_estado].fillna("(en blanco)").astype(str).str.strip() if col_estado else "(en blanco)"
    df["__estado_norm"] = df["__estado"].map(_normalizar)
    df["__canal"] = df[col_canal].fillna("(en blanco)").astype(str).map(_normalizar_canal) if col_canal else "(en blanco)"
    df["__forma"] = df[col_forma].fillna("(en blanco)").astype(str).map(_normalizar_forma_pago) if col_forma else "(en blanco)"
    df["__opcion"] = df[col_opcion].fillna("(en blanco)").astype(str).str.strip() if col_opcion else "Consolidado"
    df["__fecha"] = df[col_fecha_tx].fillna("").astype(str).str.strip() if col_fecha_tx else ""
    df["__hora"] = df[col_hora].fillna("").astype(str).str.strip() if col_hora else ""
    return df


def _top_items(series: pd.Series, top: int = 12) -> list[dict]:
    if series.empty:
        return []
    s = series.sort_values(ascending=False).head(top)
    maxv = max(int(s.max()), 1)
    return [{"label": str(i), "value": int(v), "pct": max((int(v) / maxv) * 100, 2)} for i, v in s.items()]


def _bar_chart(title: str, series: pd.Series, subtitle: str = "") -> str:
    rows = []
    for item in _top_items(series):
        rows.append(f"""
        <div class='bar-row'>
          <div class='bar-label'>{html.escape(item['label'])}</div>
          <div class='bar-track'><div class='bar-fill' style='width:{item['pct']:.1f}%'></div></div>
          <div class='bar-value'>{_fmt_num(item['value'])}</div>
        </div>
        """)
    body = "".join(rows) if rows else "<div class='empty'>Sin datos</div>"
    return f"<section class='card'><h3>{html.escape(title)}</h3><p class='sub'>{html.escape(subtitle)}</p>{body}</section>"


def _kpi(title: str, value: int, note: str = "") -> str:
    return f"<div class='kpi'><span>{html.escape(title)}</span><strong>{_fmt_num(value)}</strong><small>{html.escape(note)}</small></div>"


def _state_cards(df: pd.DataFrame) -> str:
    counts = df["__estado"].value_counts()
    orden = ["Pago Realizado", "Checkout", "Pago Pendiente", "Pendiente Recaudo", "Pendiente Facturación", "Recaudado", "Inconsistente"]
    estados = [e for e in orden if e in counts.index] + [e for e in counts.index if e not in orden]
    total = len(df)
    cards = []
    for estado in estados:
        sub = df[df["__estado"].eq(estado)]
        detail = sub["__canal"].value_counts()
        rows = "".join(f"<div><span>{html.escape(str(c))}</span><b>{_fmt_num(v)}</b></div>" for c, v in detail.items())
        cards.append(f"""
        <article class='state'>
          <header><div><h3>{html.escape(str(estado))}</h3><small>{_pct(int(counts[estado]), total)} del total</small></div><strong>{_fmt_num(counts[estado])}</strong></header>
          <section>{rows}</section>
        </article>
        """)
    return "".join(cards)


def _alertas_web(df: pd.DataFrame) -> str:
    formas = ["TC", "TD", "T. Compensar"]
    cards = []
    for forma in formas:
        web = df[df["__canal"].eq("Web") & df["__forma"].eq(forma)]
        pago = int(web[web["__estado_norm"].eq(_normalizar("Pago Realizado"))].shape[0])
        checkout = int(web[web["__estado_norm"].eq(_normalizar("Checkout"))].shape[0])
        recaudo = int(web[web["__estado_norm"].eq(_normalizar("Pendiente Recaudo"))].shape[0])
        pendiente = int(web[web["__estado_norm"].eq(_normalizar("Pago Pendiente"))].shape[0])
        otros = {"Checkout": checkout, "Pendiente recaudo": recaudo, "Pago pendiente": pendiente}
        mayores = [k for k, v in otros.items() if v > pago]
        if pago == 0 and sum(otros.values()) > 0:
            level, title, msg = "critica", f"{forma} sin pagos realizados en Web", "Hay registros en otros estados y no hay pagos realizados."
        elif mayores:
            level, title, msg = "revision", f"{forma} con estados superiores al pago realizado", "Revisar: " + ", ".join(mayores) + " supera Pago realizado."
        else:
            level, title, msg = "ok", f"{forma} sin alerta en Web", "Pago realizado es mayor o igual que los otros estados principales."
        cards.append(f"""
        <article class='alert {level}'>
          <div class='alert-top'><div><small>Web · {html.escape(forma)}</small><h3>{html.escape(title)}</h3></div><b>{level.upper()}</b></div>
          <p>{html.escape(msg)}</p>
          <div class='metrics'><div><span>Pago realizado</span><strong>{_fmt_num(pago)}</strong></div><div><span>Checkout</span><strong>{_fmt_num(checkout)}</strong></div><div><span>Pendiente recaudo</span><strong>{_fmt_num(recaudo)}</strong></div><div><span>Pago pendiente</span><strong>{_fmt_num(pendiente)}</strong></div></div>
        </article>
        """)
    return "".join(cards)


def _grouped_table(title: str, groups: list[dict], group_label: str, detail_label: str) -> str:
    if not groups:
        return f"<section class='card'><h3>{html.escape(title)}</h3><div class='empty'>Sin datos</div></section>"
    html_groups = []
    for g in groups:
        rows = "".join(f"<div class='group-row'><span>{html.escape(str(d['name']))}</span><b>{_fmt_num(d['value'])}</b></div>" for d in g["details"])
        html_groups.append(f"""
        <article class='group'>
          <header><div><small>{html.escape(group_label)}</small><h4>{html.escape(str(g['name']))}</h4></div><strong>{_fmt_num(g['total'])}</strong></header>
          <div class='group-sub'><span>{html.escape(detail_label)}</span><span>Cantidad</span></div>
          {rows}
        </article>
        """)
    return f"<section class='card'><h3>{html.escape(title)}</h3><div class='groups'>{''.join(html_groups)}</div></section>"


def _groups_estado_canal(df: pd.DataFrame) -> list[dict]:
    counts = df.groupby(["__estado", "__canal"]).size().reset_index(name="Cantidad")
    totals = df["__estado"].value_counts().to_dict()
    orden = ["Pago Realizado", "Checkout", "Pago Pendiente", "Pendiente Recaudo", "Pendiente Facturación", "Recaudado", "Inconsistente"]
    estados = [e for e in orden if e in totals] + [e for e in totals if e not in orden]
    out = []
    for estado in estados:
        sub = counts[counts["__estado"].eq(estado)].sort_values("Cantidad", ascending=False)
        out.append({"name": estado, "total": int(totals[estado]), "details": [{"name": r["__canal"], "value": int(r["Cantidad"])} for _, r in sub.iterrows()]})
    return out


def _groups_canal_forma(df: pd.DataFrame, estado: str) -> list[dict]:
    sub = df[df["__estado_norm"].eq(_normalizar(estado))]
    if sub.empty:
        return []
    counts = sub.groupby(["__canal", "__forma"]).size().reset_index(name="Cantidad")
    out = []
    for canal, g in counts.groupby("__canal"):
        g = g.sort_values("Cantidad", ascending=False)
        out.append({"name": canal, "total": int(g["Cantidad"].sum()), "details": [{"name": r["__forma"], "value": int(r["Cantidad"])} for _, r in g.iterrows()]})
    return sorted(out, key=lambda x: x["total"], reverse=True)


def _monthly_path() -> Path | None:
    if not SHAREPOINT_SYNC_DIR:
        return None
    p = Path(SHAREPOINT_SYNC_DIR) / f"HERCULES_ACUMULADO_{_mes_reporte()}.xlsx"
    return p if p.exists() else None


def _monthly_section() -> str:
    path = _monthly_path()
    if not path:
        return "<div class='empty'>Aún no hay acumulado mensual disponible.</div>"
    try:
        df = pd.read_excel(path, sheet_name="Base_Mensual")
        df = _preparar(df)
    except Exception as exc:
        return f"<div class='empty'>No pude leer mensual: {html.escape(str(exc))}</div>"

    col_fecha_reporte = "Fecha_Reporte" if "Fecha_Reporte" in df.columns else None
    dias = df[col_fecha_reporte].nunique() if col_fecha_reporte else 0
    total = len(df)
    inconsist = int(df["__estado_norm"].str.contains("inconsist", na=False).sum())

    kpis = "".join([
        _kpi("Total mes", total, "Registros acumulados"),
        _kpi("Días cargados", int(dias), "Fechas en el acumulado"),
        _kpi("Pago realizado", int((df["__estado_norm"] == _normalizar("Pago Realizado")).sum()), "Acumulado del mes"),
        _kpi("Inconsistentes", inconsist, "Acumulado del mes"),
    ])

    charts = "".join([
        _bar_chart("Estados de cotización", df["__estado"].value_counts(), "Acumulado mensual por estado."),
        _bar_chart("Canal que cotizó", df["__canal"].value_counts(), "Canales con más registros en el mes."),
        _bar_chart("Formas de pago", df["__forma"].value_counts(), "Medios de pago con mayor uso."),
        _bar_chart("Opciones", df["__opcion"].value_counts(), "Torneos, Gimnasios, Turnos, Citas y Materiales."),
        _bar_chart("Fechas con más transacciones", df["__fecha"].replace("", pd.NA).dropna().value_counts().head(12), "Días de mayor carga."),
        _bar_chart("Horas con más transacciones", df["__hora"].replace("", pd.NA).dropna().value_counts().head(12), "Horas donde se concentra la operación."),
    ])

    lows = "".join([
        _bar_chart("Fechas con menos transacciones", df["__fecha"].replace("", pd.NA).dropna().value_counts().sort_values(ascending=True).head(10), "Días con menor volumen."),
        _bar_chart("Horas con menos transacciones", df["__hora"].replace("", pd.NA).dropna().value_counts().sort_values(ascending=True).head(10), "Horas de menor movimiento."),
    ])

    return f"""
    <section class='kpi-grid'>{kpis}</section>
    <section class='chart-grid'>{charts}</section>
    <div class='section-heading'><h2>Menor volumen</h2><span>Fechas y horas con menos transacciones</span></div>
    <section class='chart-grid'>{lows}</section>
    """


def generar_dashboard() -> Path:
    resumen = REPORTS_DIR / "resumen_hercules_diario.xlsx"
    if not resumen.exists():
        raise FileNotFoundError(f"No existe {resumen}")
    df = _preparar(_leer_base_resumen(resumen))

    total = len(df)
    estado = df["__estado_norm"]
    kpis = "".join([
        _kpi("Total", total, "Registros descargados"),
        _kpi("Pago realizado", int((estado == _normalizar("Pago Realizado")).sum()), "Detalle por canal y forma de pago"),
        _kpi("Checkout", int((estado == _normalizar("Checkout")).sum()), "Detalle por canal"),
        _kpi("Pago pendiente", int((estado == _normalizar("Pago Pendiente")).sum()), "Pendiente de finalizar"),
        _kpi("Pendiente recaudo", int((estado == _normalizar("Pendiente Recaudo")).sum()), "Detalle por canal y forma de pago"),
        _kpi("Inconsistentes", int(estado.str.contains("inconsist", na=False).sum()), "Registros con estado inconsistente"),
    ])

    daily = f"""
    <section class='kpi-grid'>{kpis}</section>
    <div class='section-heading'><h2>Alertas Web · formas de pago principales</h2><span>TC, TD y T. Compensar</span></div>
    <section class='alert-grid'>{_alertas_web(df)}</section>
    <div class='section-heading'><h2>Estados y detalle por canal</h2><span>Total y detalle por Web, PAI, Módulos u otros canales</span></div>
    <section class='state-grid'>{_state_cards(df)}</section>
    <div class='section-heading'><h2>Gráficas</h2><span>Vista rápida del día</span></div>
    <section class='chart-grid'>
      {_bar_chart('Canal que cotizó', df['__canal'].value_counts(), 'Distribución por canal.')}
      {_bar_chart('Opciones', df['__opcion'].value_counts(), 'Torneos, Gimnasios, Turnos, Citas y Materiales.')}
      {_bar_chart('Pago realizado por forma de pago', df[df['__estado_norm'].eq(_normalizar('Pago Realizado'))]['__forma'].value_counts(), 'Formas de pago finalizadas.')}
      {_bar_chart('Checkout por forma de pago', df[df['__estado_norm'].eq(_normalizar('Checkout'))]['__forma'].value_counts(), 'Apoyo para identificar fallas antes del pago.')}
    </section>
    <div class='section-heading'><h2>Tablas de detalle</h2><span>Agrupadas sin repetición innecesaria</span></div>
    <section class='table-grid'>
      {_grouped_table('Estado cotización por canal', _groups_estado_canal(df), 'Estado', 'Canal de cotización')}
      {_grouped_table('Pago realizado por canal y forma de pago', _groups_canal_forma(df, 'Pago Realizado'), 'Canal de cotización', 'Forma de pago')}
      {_grouped_table('Checkout por canal y forma de pago', _groups_canal_forma(df, 'Checkout'), 'Canal de cotización', 'Forma de pago')}
      {_grouped_table('Pendiente recaudo por canal y forma de pago', _groups_canal_forma(df, 'Pendiente Recaudo'), 'Canal de cotización', 'Forma de pago')}
    </section>
    """

    monthly = _monthly_section()
    salida = REPORTS_DIR / "dashboard_hercules.html"

    css = """
    :root{--naranja:#F26A21;--amarillo:#FDB913;--negro:#101820;--rojo:#E5402A;--azul:#005E7A;--turq:#00A6B8;--verde:#20B486;--muted:#64748B;--linea:#DDE7EE;--bg:#F3F6F8;--card:#fff;--alerta:#EF4444;--rev:#F59E0B;--ok:#10B981}*{box-sizing:border-box}body{margin:0;font-family:Arial,Helvetica,sans-serif;color:#172033;background:radial-gradient(circle at top left,rgba(242,106,33,.13),transparent 24%),radial-gradient(circle at top right,rgba(0,166,184,.16),transparent 26%),linear-gradient(135deg,#F7FAFC,#EEF4F7)}.page{max-width:1600px;margin:0 auto;padding:28px}.hero{border-radius:26px;background:linear-gradient(135deg,rgba(16,24,32,.98),rgba(0,94,122,.98) 55%,rgba(0,166,184,.92));color:white;padding:30px 34px;box-shadow:0 20px 45px rgba(16,24,32,.22);border-top:5px solid var(--naranja);margin-bottom:18px}.brand{display:flex;align-items:center;gap:12px;margin-bottom:10px;color:#E8F9FB;font-size:13px;letter-spacing:.12em;text-transform:uppercase;font-weight:800}.mark{width:38px;height:16px;border-radius:20px 20px 20px 4px;background:linear-gradient(90deg,var(--rojo),var(--naranja));display:inline-block;transform:skew(-18deg)}h1{margin:0;font-size:34px}.hero p{opacity:.92}.meta{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}.pill{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.25);border-radius:999px;padding:8px 12px;font-size:12px}.tabs{display:flex;gap:10px;margin:18px 0}.tabbtn{border:1px solid var(--linea);background:white;color:var(--azul);font-weight:900;border-radius:999px;padding:12px 18px;cursor:pointer}.tabbtn.active{background:linear-gradient(90deg,var(--naranja),var(--amarillo));color:#101820}.tab{display:none}.tab.active{display:block}.kpi-grid{display:grid;grid-template-columns:repeat(3,minmax(180px,1fr));gap:14px;margin-bottom:20px}.kpi{background:white;border:1px solid var(--linea);border-radius:20px;padding:18px 16px;box-shadow:0 12px 30px rgba(15,23,42,.07);border-top:5px solid var(--naranja)}.kpi span{display:block;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.08em;font-weight:800}.kpi strong{display:block;margin-top:8px;font-size:30px;font-weight:900;color:var(--azul)}.kpi small{display:block;margin-top:7px;color:var(--muted)}.section-heading{display:flex;align-items:end;justify-content:space-between;margin:24px 0 12px;gap:10px}.section-heading h2{margin:0;font-size:21px;color:#0F3344}.section-heading span{color:var(--muted);font-size:13px}.alert-grid,.state-grid{display:grid;grid-template-columns:repeat(3,minmax(280px,1fr));gap:16px;margin-bottom:20px}.alert,.state,.card{background:white;border:1px solid var(--linea);border-radius:22px;padding:18px;box-shadow:0 12px 30px rgba(15,23,42,.07)}.alert{border-left:7px solid var(--ok)}.alert.critica{border-left-color:var(--alerta);background:linear-gradient(180deg,#FFF5F5,#fff)}.alert.revision,.alert.advertencia{border-left-color:var(--rev);background:linear-gradient(180deg,#FFFBEB,#fff)}.alert.ok{border-left-color:var(--ok);background:linear-gradient(180deg,#ECFDF5,#fff)}.alert-top{display:flex;justify-content:space-between;gap:10px}.alert-top small{font-size:12px;color:var(--muted);font-weight:800;text-transform:uppercase;letter-spacing:.07em}.alert h3,.state h3,.card h3{margin:4px 0;font-size:17px;color:#102A3A}.alert-top b{font-size:11px;border-radius:999px;padding:6px 8px;background:#EFF6FF;color:var(--azul);height:max-content}.alert.critica .alert-top b{background:#FEE2E2;color:#B91C1C}.alert.revision .alert-top b{background:#FEF3C7;color:#92400E}.alert.ok .alert-top b{background:#D1FAE5;color:#047857}.metrics{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}.metrics div{background:#F8FAFC;border:1px solid #E5EDF3;border-radius:12px;padding:9px}.metrics span{display:block;color:var(--muted);font-size:11px}.metrics strong{color:var(--azul);font-size:18px;font-weight:900}.state{padding:0;overflow:hidden}.state header{display:flex;justify-content:space-between;gap:14px;padding:18px;background:linear-gradient(135deg,#F8FBFD,#EDF8FA);border-bottom:1px solid var(--linea)}.state header strong{font-size:28px;color:var(--azul)}.state section{padding:12px 16px}.state section div{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px dashed #E5EDF3}.state b{color:var(--naranja)}.chart-grid,.table-grid{display:grid;grid-template-columns:repeat(2,minmax(420px,1fr));gap:18px;margin-bottom:22px}.card h3{font-size:17px;font-weight:900}.sub{font-size:12px;color:var(--muted);margin:0 0 16px}.bar-row{display:grid;grid-template-columns:190px 1fr 76px;align-items:center;gap:12px;margin:10px 0}.bar-label{font-size:13px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.bar-track{background:#EDF4F8;height:14px;border-radius:999px;overflow:hidden}.bar-fill{height:100%;border-radius:999px;background:linear-gradient(90deg,var(--naranja),var(--amarillo),var(--turq))}.bar-value{text-align:right;font-weight:900;color:var(--azul)}.groups{display:flex;flex-direction:column;gap:16px;margin-top:12px}.group{border:1px solid #E4EDF4;border-radius:18px;overflow:hidden;background:#FBFDFF}.group header{display:flex;justify-content:space-between;align-items:center;gap:14px;padding:14px 16px;background:linear-gradient(90deg,#E8F5F8,#F7FCFD);border-bottom:1px solid #D8EAF0}.group h4{margin:0;font-size:19px}.group header small{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:800}.group header strong{font-size:28px;color:var(--naranja)}.group-sub,.group-row{display:grid;grid-template-columns:1fr 110px;gap:12px;padding:10px 16px;border-bottom:1px solid #EDF2F7}.group-sub{font-size:12px;color:var(--azul);font-weight:900;background:#F4FAFC}.group-row b{text-align:right;color:var(--azul)}.empty{color:var(--muted);font-size:14px;padding:18px}.footer{text-align:center;color:var(--muted);font-size:12px;margin-top:22px}@media(max-width:1000px){.kpi-grid,.alert-grid,.state-grid,.chart-grid,.table-grid{grid-template-columns:1fr}.page{padding:16px}}
    """

    html_doc = f"""<!DOCTYPE html><html lang='es'><head><meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1.0'><title>Monitoreo Hércules</title><style>{css}</style></head><body><main class='page'>
    <header class='hero'><div class='brand'><span class='mark'></span><span>Hércules · Compensar</span></div><h1>Monitoreo Hércules</h1><p>Resumen diario y acumulado mensual de estados, canales y formas de pago.</p><div class='meta'><div class='pill'><b>Generado:</b> {html.escape(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</div><div class='pill'><b>Fecha reporte:</b> {html.escape(_fecha_reporte())}</div><div class='pill'><b>Registros día:</b> {_fmt_num(total)}</div></div></header>
    <nav class='tabs'><button class='tabbtn active' onclick="showTab('diario', this)">Diario</button><button class='tabbtn' onclick="showTab('mensual', this)">Mensual</button></nav>
    <section id='diario' class='tab active'>{daily}</section>
    <section id='mensual' class='tab'><div class='section-heading'><h2>Mensual</h2><span>Acumulado del mes {html.escape(_mes_reporte().replace('_','-'))}</span></div>{monthly}</section>
    <div class='footer'>Monitoreo automático · Hércules</div>
    </main><script>function showTab(id, btn){{document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));document.querySelectorAll('.tabbtn').forEach(b=>b.classList.remove('active'));document.getElementById(id).classList.add('active');btn.classList.add('active');}}</script></body></html>"""

    salida.write_text(html_doc, encoding="utf-8")
    print(f"Dashboard HTML generado: {salida}")
    return salida


if __name__ == "__main__":
    generar_dashboard()
