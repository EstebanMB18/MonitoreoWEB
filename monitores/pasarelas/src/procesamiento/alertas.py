from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from src import config


MIN_MUESTRAS_TIPO_DIA = 3


def _project_root() -> Path:
    # config.ROOT = <proyecto>/monitores/pasarelas
    try:
        return config.ROOT.parents[1]
    except Exception:
        return Path(__file__).resolve().parents[5]


def _festivos() -> set[str]:
    p = _project_root() / 'GENERAL' / 'calendario_festivos.txt'
    if not p.exists():
        return set()
    try:
        return {
            x.strip() for x in p.read_text(encoding='utf-8-sig').splitlines()
            if x.strip() and not x.lstrip().startswith('#')
        }
    except Exception:
        return set()


def _tipo_dia(fecha) -> str:
    try:
        dt = pd.to_datetime(fecha, errors='coerce')
        if pd.isna(dt):
            return 'HABIL'
        iso = dt.strftime('%Y-%m-%d')
        if dt.weekday() >= 5 or iso in _festivos():
            return 'FIN_SEMANA_FESTIVO'
        return 'HABIL'
    except Exception:
        return 'HABIL'


def _tipo_dia_actual() -> str:
    return _tipo_dia(datetime.now())



def _corte_normalizado(corte) -> str:
    txt = str(corte or '').strip().lower()
    if txt.startswith('09') or txt.startswith('man'):
        return '09'
    if txt.startswith('13'):
        return '13'
    if txt.startswith('17') or txt.startswith('18'):
        return '17'
    return str(corte or '09')


def _promedios_estaticos(corte: str) -> pd.DataFrame:
    # Compatibilidad: mientras el histórico aprende, 13 usa el mejor histórico
    # disponible y, si no existe, no inventa un promedio fijo.
    if corte == '09':
        p = config.CONFIG / 'promedios_09.csv'
    elif corte == '17':
        p = config.CONFIG / 'promedios_17.csv'
    else:
        return pd.DataFrame(columns=['vertical', 'medio_pago', 'promedio'])
    try:
        return pd.read_csv(p) if p.exists() else pd.DataFrame(columns=['vertical', 'medio_pago', 'promedio'])
    except Exception:
        return pd.DataFrame(columns=['vertical', 'medio_pago', 'promedio'])


def _promedios_historicos(corte: str, tipo_dia_actual: str) -> pd.DataFrame:
    """Promedio aprendido por vertical + medio + corte + tipo de día.

    Para fin de semana/festivo NO mezcla días hábiles.
    Excluye el día actual para no contaminar el promedio con la muestra en curso.
    """
    path = config.HISTORICO / 'acumulado_por_corte.xlsx'
    empty = pd.DataFrame(columns=['vertical', 'medio_salida', 'promedio_hist', 'muestras_hist'])
    if not path.exists():
        return empty
    try:
        h = pd.read_excel(path)
    except Exception:
        return empty
    needed = {'fecha_base', 'corte', 'vertical', 'medio_salida', 'cantidad_ok'}
    if h.empty or not needed.issubset(h.columns):
        return empty

    hoy = datetime.now().strftime('%Y-%m-%d')
    h = h.copy()
    h['fecha_base'] = h['fecha_base'].astype(str).str[:10]
    h['corte'] = h['corte'].astype(str).str.replace('.0', '', regex=False).str.zfill(2)
    h['tipo_dia'] = h['fecha_base'].map(_tipo_dia)
    h = h[
        (h['corte'] == corte) &
        (h['fecha_base'] != hoy) &
        (h['tipo_dia'] == tipo_dia_actual)
    ]
    h['cantidad_ok'] = pd.to_numeric(h['cantidad_ok'], errors='coerce')
    h = h.dropna(subset=['cantidad_ok'])
    if h.empty:
        return empty

    return (
        h.groupby(['vertical', 'medio_salida'], dropna=False)['cantidad_ok']
         .agg(promedio_hist='mean', muestras_hist='count')
         .reset_index()
    )


def _agregar_promedio(df: pd.DataFrame, corte: str) -> pd.DataFrame:
    out = df.copy()
    tipo_actual = _tipo_dia_actual()
    hist = _promedios_historicos(corte, tipo_actual)

    if not hist.empty:
        out = out.merge(hist, on=['vertical', 'medio_salida'], how='left')
    else:
        out['promedio_hist'] = pd.NA
        out['muestras_hist'] = 0

    # Los promedios estáticos existentes fueron construidos con comportamiento
    # general/laboral. No se usan como fallback en fin de semana/festivo.
    if tipo_actual == 'HABIL':
        static = _promedios_estaticos(corte)
    else:
        static = pd.DataFrame(columns=['vertical', 'medio_pago', 'promedio'])

    if not static.empty:
        static = static.rename(columns={'medio_pago': 'medio_salida', 'promedio': 'promedio_static'})
        out = out.merge(
            static[['vertical', 'medio_salida', 'promedio_static']],
            on=['vertical', 'medio_salida'],
            how='left'
        )
    else:
        out['promedio_static'] = pd.NA

    out['muestras_hist'] = pd.to_numeric(out.get('muestras_hist'), errors='coerce').fillna(0).astype(int)
    ph = pd.to_numeric(out.get('promedio_hist'), errors='coerce')
    ps = pd.to_numeric(out.get('promedio_static'), errors='coerce')

    out['tipo_dia_promedio'] = tipo_actual
    out['promedio'] = 0.0
    out['fuente_promedio'] = 'APRENDIENDO'

    suficiente = out['muestras_hist'] >= MIN_MUESTRAS_TIPO_DIA
    out.loc[suficiente & ph.notna(), 'promedio'] = ph[suficiente & ph.notna()]
    out.loc[suficiente & ph.notna(), 'fuente_promedio'] = 'HISTÓRICO ' + tipo_actual

    # Solo día hábil puede usar la base estática mientras aprende.
    base_mask = (
        (tipo_actual == 'HABIL') &
        (out['fuente_promedio'] == 'APRENDIENDO') &
        ps.notna()
    )
    if hasattr(base_mask, 'any'):
        out.loc[base_mask, 'promedio'] = ps[base_mask]
        out.loc[base_mask, 'fuente_promedio'] = 'BASE HÁBIL'

    return out


def aplicar_alertas(df, corte='09', *args, **kwargs):
    """Alertas operativas usando solo OK como volumen visible.

    Reglas internas adicionales:
    - Si rechazadas/declinadas/fallidas superan a las OK -> ALERTA.
    - El promedio se aprende por corte desde acumulado_por_corte.xlsx.
    - En primer corte se evita castigar un volumen pequeño si sí hay movimiento,
      salvo una relación de errores claramente adversa o flujo crítico en cero.
    """
    if df is None or df.empty:
        return df
    corte = _corte_normalizado(corte)
    out = _agregar_promedio(df, corte)

    for col in ['cantidad_ok', 'cantidad_total', 'cantidad_fallida', 'conteo_rechazada',
                'conteo_fallida_tecnica', 'conteo_expired', 'conteo_pendiente']:
        if col not in out.columns:
            out[col] = 0
        out[col] = pd.to_numeric(out[col], errors='coerce').fillna(0)

    out['codigo'] = out.get('codigo', '').astype(str).str.replace('.0', '', regex=False)
    out['estado'] = 'NORMAL'
    out['observacion'] = 'Comportamiento dentro de rango operativo.'
    out['ratio_promedio'] = 1.0

    for idx, r in out.iterrows():
        ok = float(r['cantidad_ok'])
        total = float(r['cantidad_total'])
        rechazadas = float(r['conteo_rechazada'])
        fall_tecnica = float(r['conteo_fallida_tecnica'])
        expired = float(r['conteo_expired'])
        # Para la regla pedida, rechazadas/declinadas/fallidas son las que compiten contra OK.
        adversas = rechazadas + fall_tecnica
        prom = float(r.get('promedio') or 0)
        ratio = ok / prom if prom > 0 else 1.0
        out.at[idx, 'ratio_promedio'] = ratio

        # Regla de calidad: prima sobre el bajo volumen y aplica en cualquier corte.
        if adversas > ok and adversas > 0:
            out.at[idx, 'estado'] = 'ALERTA'
            out.at[idx, 'observacion'] = (
                f'Alerta por calidad: rechazadas/declinadas/fallidas ({int(adversas)}) '
                f'superan las aprobadas/OK ({int(ok)}). Total observado: {int(total)}.'
            )
            continue

        # Si aún no hay suficientes muestras del mismo tipo de día,
        # el volumen bajo NO genera alerta. Las reglas de calidad sí aplican arriba.
        if str(r.get('fuente_promedio', '')).upper().startswith('APRENDIENDO'):
            out.at[idx, 'estado'] = 'APRENDIENDO'
            out.at[idx, 'observacion'] = (
                f'Aprendiendo comportamiento de {r.get("tipo_dia_promedio", "este tipo de día")}: '
                f'{int(r.get("muestras_hist", 0))}/{MIN_MUESTRAS_TIPO_DIA} muestras históricas del mismo corte.'
            )
            continue

        if prom >= config.PROMEDIO_MINIMO_ALERTA:
            if ratio < config.UMBRAL_ALERTA:
                out.at[idx, 'estado'] = 'ALERTA'
                out.at[idx, 'observacion'] = (
                    f'Volumen OK muy por debajo de lo esperado: {int(ok)} vs promedio '
                    f'{prom:.2f} ({ratio*100:.0f}% del esperado; fuente {r.get("fuente_promedio", "")}).'
                )
            elif ratio < config.UMBRAL_BAJA:
                out.at[idx, 'estado'] = 'BAJA TRANSACCIÓN'
                out.at[idx, 'observacion'] = (
                    f'Volumen OK bajo: {int(ok)} vs promedio {prom:.2f} '
                    f'({ratio*100:.0f}% del esperado; fuente {r.get("fuente_promedio", "")}).'
                )

    # Primer corte: el bajo volumen por sí solo no es afectación si existe movimiento.
    if corte == '09':
        actual = out['cantidad_ok']
        quality_alert = (out['conteo_rechazada'] + out['conteo_fallida_tecnica']) > actual
        low = out['estado'].astype(str).str.upper().str.contains('ALERTA|BAJA TRANSAC', regex=True)
        out.loc[(actual > 0) & low & ~quality_alert, 'estado'] = 'NORMAL'
        out.loc[(actual > 0) & low & ~quality_alert, 'observacion'] = (
            'Primer corte: existe transaccionalidad OK. El bajo volumen temprano se mantiene en observación.'
        )

        critical = {
            '41605': ['PSE', 'TARJ. CREDITO', 'PSE LINK DE PAGO', 'TARJ. CREDITO LINK PAGO'],
            '41610': ['PSE', 'TARJ. CREDITO', 'TUP'],
            '41621': ['PSE (PAYU)', 'TARJ. CREDITO (PAYU)', 'REDES', 'CUPOYA'],
        }
        for code, medios in critical.items():
            code_mask = out['codigo'].eq(code)
            if not code_mask.any():
                continue
            medium_mask = out['medio_salida'].astype(str).str.upper().isin([m.upper() for m in medios])
            crit_mask = code_mask & medium_mask
            if not crit_mask.any():
                continue
            flujo_total = out.loc[crit_mask, 'cantidad_total'].sum()
            if flujo_total == 0:
                out.loc[crit_mask, 'estado'] = 'ALERTA'
                out.loc[crit_mask, 'observacion'] = 'Alerta primer corte: no se detectó ninguna transacción en el flujo crítico.'
            else:
                qmask = (out['conteo_rechazada'] + out['conteo_fallida_tecnica']) > out['cantidad_ok']
                volume_only = code_mask & ~qmask & out['estado'].astype(str).str.upper().str.contains('ALERTA|BAJA TRANSAC', regex=True)
                out.loc[volume_only, 'estado'] = 'NORMAL'
                out.loc[volume_only, 'observacion'] = 'Primer corte: el flujo crítico presenta movimiento; se evita falsa alerta por volumen temprano.'

    return out
