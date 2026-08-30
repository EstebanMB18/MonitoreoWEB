from pathlib import Path
import base64
import pandas as pd
from src import config
from src.utils.limpieza import moneda


def estado_color(e):
    return {'NORMAL':'ok','BAJA TRANSACCIÓN':'warn','ALERTA':'bad','SIN PROMEDIO':'neutral','SIN DATOS':'neutral'}.get(str(e),'neutral')


def logo_b64():
    p = config.ASSETS / 'logo_compensar.png'
    if p.exists():
        return 'data:image/png;base64,' + base64.b64encode(p.read_bytes()).decode()
    return ''


def _num(x):
    try:
        return int(float(x or 0))
    except Exception:
        return 0


def _float(x):
    try:
        return float(x or 0)
    except Exception:
        return 0.0


def tabla_resumen_general(df):
    medios_orden = ['PSE','TARJ. CREDITO','PSE LINK DE PAGO','TARJ. CREDITO LINK PAGO','MODULOS AUTOSERVICIOS','REDES','SAP','TUP','CUPOYA','PSE (PAYU)','TARJ. CREDITO (PAYU)']
    usados = [m for m in medios_orden if m in set(df['medio_salida'].astype(str))]
    otros = [m for m in df['medio_salida'].astype(str).drop_duplicates().tolist() if m not in usados]
    medios = usados + otros
    resumen_head = ''.join(f"<th>{m}</th>" for m in medios)
    resumen_rows = ''
    for vertical, g in df.groupby('vertical', sort=False):
        estado = 'ALERTA' if g['estado'].eq('ALERTA').any() else ('BAJA TRANSACCIÓN' if g['estado'].eq('BAJA TRANSACCIÓN').any() else 'NORMAL')
        vals = []
        for m in medios:
            sub = g[g['medio_salida'].astype(str).eq(m)]
            vals.append(int(sub['cantidad_ok'].sum()) if not sub.empty else 0)
        celdas = ''.join(f"<td class='num'>{v}</td>" for v in vals)
        resumen_rows += f"<tr><td class='vert'>{vertical}</td>{celdas}<td class='num total'>{sum(vals)}</td><td><span class='pill {estado_color(estado)}'>{estado}</span></td></tr>"
    return f"""<div class='panel'><h2>Resumen general</h2><div class='matrix-wrap'><table class='matrix'><thead><tr><th>Vertical</th>{resumen_head}<th>Total</th><th>Estado</th></tr></thead><tbody>{resumen_rows}</tbody></table></div></div>"""


def tabla_zoom_creditos(df):
    if 'es_credito' in df.columns:
        cred = df[df['es_credito'].astype(str).str.lower().isin(['true','1','si','sí']) | df['es_credito'].eq(True)].copy()
    else:
        cred = df[df['vertical'].astype(str).str.upper().str.contains('CREDITO')].copy()
    if cred.empty:
        return ''
    for col in ['cantidad_ok','cantidad_total','cantidad_fallida','conteo_expired','conteo_rechazada','conteo_fallida_tecnica','conteo_pendiente','conteo_otra','valor_ok']:
        if col not in cred.columns:
            cred[col] = 0
    rows = ''
    for r in cred.itertuples():
        rows += f"""<tr>
<td>{r.vertical}</td><td>{r.medio_salida}</td>
<td class='num oknum'>{_num(r.cantidad_ok)}</td>
<td class='num'>{_num(r.cantidad_total)}</td>
<td class='num warnnum'>{_num(r.conteo_expired)}</td>
<td class='num warnnum'>{_num(r.conteo_rechazada)}</td>
<td class='num badnum'>{_num(r.conteo_fallida_tecnica)}</td>
<td class='num'>{_num(r.conteo_pendiente)}</td>
<td class='num'>{_num(r.conteo_otra)}</td>
<td>{r.ultima_ok}</td>
<td><span class='pill {estado_color(r.estado)}'>{r.estado}</span></td>
</tr>"""
    return f"""<div class='panel'><h2>Zoom créditos</h2><p class='hint'>Seguimiento especial para 41607 CREDITO BANCOR y 41612 CREDITO SIIF. Los rechazos o expirados suelen ser comportamiento de usuario/banco; las fallas técnicas se resaltan aparte.</p><div class='matrix-wrap'><table><thead><tr><th>Vertical</th><th>Medio</th><th>OK</th><th>Total</th><th>Expired</th><th>Rechazadas</th><th>Fallas técnicas</th><th>Pendientes</th><th>Otras</th><th>Última OK</th><th>Estado</th></tr></thead><tbody>{rows}</tbody></table></div></div>"""


def tabla_mensual():
    mensuales = sorted(config.MENSUAL.glob('acumulado_verticales_*.xlsx'), key=lambda p: p.stat().st_mtime)
    if not mensuales:
        return "<div class='panel'><h2>Acumulado mensual</h2><p class='hint'>Aún no hay acumulado mensual. Se genera con el proceso de día anterior.</p></div>"
    try:
        mdf = pd.read_excel(mensuales[-1])
    except Exception:
        return "<div class='panel'><h2>Acumulado mensual</h2><p class='hint'>No se pudo leer el acumulado mensual.</p></div>"
    if mdf.empty:
        return "<div class='panel'><h2>Acumulado mensual</h2><p class='hint'>El acumulado mensual está vacío.</p></div>"
    for col in ['cantidad_ok','valor_ok','cantidad_fallida','cantidad_total']:
        if col not in mdf.columns:
            mdf[col] = 0
    agg = mdf.groupby('vertical', dropna=False).agg(
        pagos_ok=('cantidad_ok','sum'),
        valor_ok=('valor_ok','sum'),
        total=('cantidad_total','sum'),
        fallidas=('cantidad_fallida','sum')
    ).reset_index().sort_values('pagos_ok', ascending=False)
    rows = ''.join([f"<tr><td class='vert'>{r.vertical}</td><td class='num'>{_num(r.pagos_ok)}</td><td class='num'>{moneda(_float(r.valor_ok))}</td><td class='num'>{_num(r.total)}</td><td class='num'>{_num(r.fallidas)}</td></tr>" for r in agg.itertuples()])
    nombre = mensuales[-1].name.replace('acumulado_verticales_','').replace('.xlsx','').replace('_','-')
    return f"""<div class='panel'><h2>Acumulado mensual</h2><p class='hint'>Mes base: {nombre}. Este bloque se actualiza con el proceso diario de día anterior.</p><div class='matrix-wrap'><table><thead><tr><th>Vertical</th><th>OK mes</th><th>Valor OK mes</th><th>Total registros</th><th>Fallidas/no OK</th></tr></thead><tbody>{rows}</tbody></table></div></div>"""


def generar_html(df, modo='diario'):
    total_ok = int(df['cantidad_ok'].sum()) if not df.empty else 0
    total_valor = float(df['valor_ok'].sum()) if not df.empty else 0
    estado_general = 'NORMAL' if not (df['estado'].eq('ALERTA').any()) else 'ALERTA'

    cards = ''
    for vertical, g in df.groupby('vertical', sort=False):
        estado = 'ALERTA' if g['estado'].eq('ALERTA').any() else ('BAJA TRANSACCIÓN' if g['estado'].eq('BAJA TRANSACCIÓN').any() else 'NORMAL')
        rows = ''.join([f"<div class='payrow'><span>{r.medio_salida}</span><b>{int(r.cantidad_ok)} OK</b></div>" for r in g.itertuples()])
        cards += f"<div class='vcard'><div class='vtitle'>{vertical}</div><div class='pill {estado_color(estado)}'>{estado}</div>{rows}</div>"

    detalle = ''.join([f"<tr><td>{r.vertical}</td><td>{r.medio_salida}</td><td>{r.promedio:.2f}</td><td>{int(r.cantidad_ok)}</td><td>{moneda(r.valor_ok)}</td><td>{r.ultima_ok}</td><td><span class='pill {estado_color(r.estado)}'>{r.estado}</span></td><td>{r.observacion}</td></tr>" for r in df.itertuples()])

    html=f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><title>MONITOREO VERTICALES</title><style>
:root{{--naranja:#ff6600;--azul:#052b6c;--verde:#7ac143;--crema:#fff4e8;--pastel:#f3f7ee;--card:#fffaf2;--line:#eadccc}}
*{{box-sizing:border-box}} body{{margin:0;font-family:Segoe UI,Arial;background:linear-gradient(135deg,#fff1df,#edf6ff 45%,#f4f8e8);color:#071f4f}}
.header{{padding:24px 34px;background:linear-gradient(135deg,#ff6600,#ff8b2c);color:white;display:flex;align-items:center;gap:22px;box-shadow:0 16px 40px rgba(255,102,0,.25)}}
.logo{{width:92px;height:92px;border-radius:24px;box-shadow:0 18px 35px rgba(0,0,0,.18)}} h1{{margin:0;font-size:34px;letter-spacing:.5px}} .sub{{opacity:.95;font-size:14px;margin-top:6px}}
.wrap{{padding:24px 30px}} .hero{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-bottom:22px}}
.kpi{{background:rgba(255,250,242,.92);border:1px solid #ffe0bd;border-radius:24px;padding:22px;box-shadow:0 18px 40px rgba(5,43,108,.12), inset 0 1px 0 rgba(255,255,255,.8)}}
.kpi .label{{font-size:13px;color:#6d5b48}} .kpi .val{{font-size:30px;font-weight:900;margin-top:8px;color:var(--azul)}}
.panel{{background:rgba(255,250,242,.72);backdrop-filter:blur(5px);border:1px solid #ecd8bd;border-radius:28px;padding:22px;box-shadow:0 22px 50px rgba(5,43,108,.12);margin-bottom:24px}}
.panel h2{{margin-top:0;color:#052b6c}} .hint{{margin-top:-6px;color:#6d5b48;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(360px,1fr));gap:16px}} .vcard{{background:linear-gradient(145deg,#fffaf2,#eef7ff);border:1px solid #d9e2ec;border-radius:22px;padding:16px;min-height:150px;box-shadow:8px 12px 28px rgba(5,43,108,.10)}}
.vtitle{{font-weight:900;color:var(--azul);font-size:15px;margin-bottom:10px}} .pill{{display:inline-block;border-radius:999px;padding:8px 14px;font-weight:900;font-size:12px;margin-bottom:10px}} .ok{{background:#dff7d9;color:#21620a}} .warn{{background:#fff0b8;color:#8a6200}} .bad{{background:#ffd3d3;color:#a60f22}} .neutral{{background:#e8eaf1;color:#4a5366}}
.payrow{{display:flex;justify-content:space-between;border-top:1px dashed #c9d4e5;padding:8px 0;font-size:13px}} .payrow b{{font-size:14px}}
table{{width:100%;border-collapse:collapse;background:#fffdf8;border-radius:18px;overflow:hidden}} th{{background:#052b6c;color:#fff;text-align:left;padding:10px;font-size:12px}} td{{padding:9px;border-bottom:1px solid #eee1d1;font-size:12px}} tr:hover{{background:#fff6e7}} .matrix-wrap{{overflow:auto}} .matrix th{{font-size:11px;white-space:nowrap}} .matrix .vert,.vert{{font-weight:900;color:#052b6c;min-width:260px}} .num{{text-align:right;font-weight:800}} .matrix .total{{background:#fff0d7;color:#d95500}} .oknum{{color:#21620a}} .warnnum{{color:#8a6200}} .badnum{{color:#a60f22}}
.footer{{text-align:center;color:#7b6b58;font-size:12px;margin:30px}}
</style></head><body><div class='header'><img class='logo' src='{logo_b64()}'><div><h1>MONITOREO VERTICALES</h1><div class='sub'>Resumen diario y detalle de pasarelas · eCollect + PayU</div></div></div><div class='wrap'>
<div class='hero'><div class='kpi'><div class='label'>Estado general</div><div class='val'>{estado_general}</div></div><div class='kpi'><div class='label'>Pagos OK</div><div class='val'>{total_ok:,}</div></div><div class='kpi'><div class='label'>Valor OK</div><div class='val'>{moneda(total_valor)}</div></div></div>
{tabla_resumen_general(df)}
<div class='panel'><h2>Resumen del día</h2><div class='grid'>{cards}</div></div>
{tabla_zoom_creditos(df)}
{tabla_mensual()}
<div class='panel'><h2>Detalle del día</h2><table><thead><tr><th>Vertical</th><th>Medio</th><th>Promedio</th><th>Actual</th><th>Valor</th><th>Última OK</th><th>Estado</th><th>Observación</th></tr></thead><tbody>{detalle}</tbody></table></div>
<div class='footer'>Generado automáticamente por Monitoreo Verticales</div></div></body></html>"""
    out = config.SALIDA / 'reporte_verticales_diario_ultimo.html'
    out.write_text(html, encoding='utf-8')
    (config.REPORTES / 'diario').mkdir(exist_ok=True, parents=True)
    (config.REPORTES / 'diario' / 'reporte_verticales_diario_ultimo.html').write_text(html, encoding='utf-8')
    return out
