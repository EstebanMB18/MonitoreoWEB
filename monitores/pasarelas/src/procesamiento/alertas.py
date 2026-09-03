from __future__ import annotations
import json
import os
from pathlib import Path

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



MIN_MUESTRAS_BASELINE = 5


def _baseline_path() -> Path:
    base = Path(
        os.getenv(
            "LOCALAPPDATA",
            str(
                Path.home()
                / "AppData"
                / "Local"
            ),
        )
    )

    return (
        base
        / "Nexus"
        / "config"
        / "baselines"
        / "pasarelas.json"
    )


def _baseline_hour(corte: str) -> int:
    return {
        "09": 8,
        "13": 12,
        "17": 16,
    }.get(
        _corte_normalizado(corte),
        datetime.now().hour,
    )


def _codigo_vertical(value) -> str:
    txt = str(
        value or ""
    ).strip()

    for part in txt.split():
        if (
            len(part) == 5
            and part.isdigit()
        ):
            return part

    return txt[:5]


def _medio_key(value) -> str:
    return (
        str(value or "")
        .strip()
        .upper()
    )


def _baseline_nexus(
    corte: str,
) -> pd.DataFrame:
    columns = [
        "codigo",
        "medio_key",
        "promedio_baseline",
        "muestras_baseline",
        "p10_baseline",
        "p25_baseline",
        "baseline_source",
        "baseline_hour",
        "baseline_day",
    ]

    path = _baseline_path()

    if not path.exists():
        return pd.DataFrame(
            columns=columns
        )

    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return pd.DataFrame(
            columns=columns
        )

    hour = _baseline_hour(
        corte
    )

    day = datetime.now().day

    exact = {}

    for item in (
        data.get("items")
        or []
    ):
        try:
            if int(
                item.get("hour")
            ) != hour:
                continue

            if int(
                item.get(
                    "day_of_month"
                )
            ) != day:
                continue

            samples = int(
                item.get("samples")
                or 0
            )

            if samples < MIN_MUESTRAS_BASELINE:
                continue

            key = (
                _codigo_vertical(
                    item.get("vertical")
                ),
                _medio_key(
                    item.get("medio")
                ),
            )

            exact[key] = {
                "codigo": key[0],
                "medio_key": key[1],
                "promedio_baseline":
                    float(
                        item.get(
                            "average"
                        )
                        or 0
                    ),
                "muestras_baseline":
                    samples,
                "p10_baseline":
                    float(
                        item.get("p10")
                        or 0
                    ),
                "p25_baseline":
                    float(
                        item.get("p25")
                        or 0
                    ),
                "baseline_source":
                    "NEXUS_EXACT",
                "baseline_hour":
                    hour,
                "baseline_day":
                    day,
            }

        except Exception:
            continue

    fallback = {}

    for item in (
        data.get(
            "fallback_items"
        )
        or []
    ):
        try:
            if int(
                item.get("hour")
            ) != hour:
                continue

            samples = int(
                item.get("samples")
                or 0
            )

            if samples < MIN_MUESTRAS_BASELINE:
                continue

            key = (
                _codigo_vertical(
                    item.get("vertical")
                ),
                _medio_key(
                    item.get("medio")
                ),
            )

            if key in exact:
                continue

            fallback[key] = {
                "codigo": key[0],
                "medio_key": key[1],
                "promedio_baseline":
                    float(
                        item.get(
                            "average"
                        )
                        or 0
                    ),
                "muestras_baseline":
                    samples,
                "p10_baseline":
                    float(
                        item.get("p10")
                        or 0
                    ),
                "p25_baseline":
                    float(
                        item.get("p25")
                        or 0
                    ),
                "baseline_source":
                    "NEXUS_FALLBACK",
                "baseline_hour":
                    hour,
                "baseline_day":
                    day,
            }

        except Exception:
            continue

    rows = (
        list(exact.values())
        + list(fallback.values())
    )

    if not rows:
        return pd.DataFrame(
            columns=columns
        )

    return pd.DataFrame(
        rows,
        columns=columns,
    )


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

    if "codigo" not in out.columns:
        out["codigo"] = ""

    out["codigo"] = (
        out["codigo"]
        .astype(str)
        .str.replace(
            ".0",
            "",
            regex=False,
        )
    )

    if "medio_salida" in out.columns:
        medio_base = out["medio_salida"]
    elif "medio_pago" in out.columns:
        medio_base = out["medio_pago"]
    else:
        medio_base = pd.Series(
            "",
            index=out.index,
        )

    out["medio_key"] = (
        medio_base
        .astype(str)
        .str.strip()
        .str.upper()
    )

    baseline = _baseline_nexus(
        corte
    )

    if not baseline.empty:
        out = out.merge(
            baseline,
            on=[
                "codigo",
                "medio_key",
            ],
            how="left",
        )
    else:
        out["promedio_baseline"] = pd.NA
        out["muestras_baseline"] = 0
        out["p10_baseline"] = pd.NA
        out["p25_baseline"] = pd.NA
        out["baseline_source"] = pd.NA
        out["baseline_hour"] = pd.NA
        out["baseline_day"] = pd.NA

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

    pb = pd.to_numeric(
        out.get(
            'promedio_baseline'
        ),
        errors='coerce'
    )

    mb = pd.to_numeric(
        out.get(
            'muestras_baseline'
        ),
        errors='coerce'
    ).fillna(0)

    baseline_ok = (
        (mb >= MIN_MUESTRAS_BASELINE)
        & pb.notna()
        & (pb > 0)
    )

    out.loc[
        baseline_ok,
        'promedio'
    ] = pb[baseline_ok]

    out.loc[
        baseline_ok,
        'fuente_promedio'
    ] = out.loc[
        baseline_ok,
        'baseline_source'
    ].fillna(
        'NEXUS_BASELINE'
    )

    suficiente = (
        out['muestras_hist']
        >= MIN_MUESTRAS_TIPO_DIA
    )

    hist_mask = (
        (out['fuente_promedio'] == 'APRENDIENDO')
        & suficiente
        & ph.notna()
    )

    out.loc[
        hist_mask,
        'promedio'
    ] = ph[hist_mask]

    out.loc[
        hist_mask,
        'fuente_promedio'
    ] = (
        'HIST?RICO '
        + tipo_actual
    )

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

        baseline_source = str(
            r.get(
                'baseline_source',
                ''
            )
            or ''
        ).upper()

        p10 = pd.to_numeric(
            pd.Series([
                r.get(
                    'p10_baseline'
                )
            ]),
            errors='coerce'
        ).iloc[0]

        p25 = pd.to_numeric(
            pd.Series([
                r.get(
                    'p25_baseline'
                )
            ]),
            errors='coerce'
        ).iloc[0]

        if (
            baseline_source.startswith(
                'NEXUS_'
            )
            and pd.notna(p10)
            and pd.notna(p25)
            and prom >= config.PROMEDIO_MINIMO_ALERTA
        ):
            muestras = int(
                r.get(
                    'muestras_baseline'
                )
                or 0
            )

            if ok < float(p10):
                out.at[idx, 'estado'] = 'ALERTA'
                out.at[idx, 'observacion'] = (
                    f'Tr\u00e1fico anormalmente bajo seg\u00fan baseline Nexus: '
                    f'{int(ok)} OK; esperado {prom:.2f}; '
                    f'P10 {float(p10):.2f}; '
                    f'{muestras} muestras; '
                    f'fuente {baseline_source}.'
                )
                continue

            if ok < float(p25):
                out.at[idx, 'estado'] = 'BAJA TRANSACCI\u00d3N'
                out.at[idx, 'observacion'] = (
                    f'Tr\u00e1fico bajo seg\u00fan baseline Nexus: '
                    f'{int(ok)} OK; esperado {prom:.2f}; '
                    f'P25 {float(p25):.2f}; '
                    f'{muestras} muestras; '
                    f'fuente {baseline_source}.'
                )
                continue

            # Si Nexus tiene baseline confiable y el valor
            # esta por encima de P25, el volumen se considera
            # normal. No se debe volver a evaluar con los
            # umbrales porcentuales legacy.
            out.at[idx, 'estado'] = 'NORMAL'
            out.at[idx, 'observacion'] = (
                f'Comportamiento dentro del rango esperado seg\u00fan '
                f'baseline Nexus: {int(ok)} OK; '
                f'esperado {prom:.2f}; '
                f'P25 {float(p25):.2f}; '
                f'{muestras} muestras; '
                f'fuente {baseline_source}.'
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
