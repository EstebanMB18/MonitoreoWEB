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


def _fecha_contexto(
    fecha_referencia=None,
):
    if fecha_referencia is None:
        return datetime.now()

    if isinstance(
        fecha_referencia,
        datetime,
    ):
        return fecha_referencia

    value = str(
        fecha_referencia
    )[:10]

    return datetime.strptime(
        value,
        "%Y-%m-%d",
    )


def _medio_key(value) -> str:
    return (
        str(value or "")
        .strip()
        .upper()
    )


def _ramss_baseline_path() -> Path:
    # HU-23:
    # Se mantiene junto al baseline legacy mientras HU-29
    # migra de forma controlada Nexus -> RAMSS.
    return _baseline_path().with_name(
        "pasarelas_ramss.json"
    )


def _ramss_freshness(
    age_days: int,
) -> str:
    if age_days <= 45:
        return "FRESH"

    if age_days <= 90:
        return "AGING"

    return "STALE"


def _ramss_stats(
    frame: pd.DataFrame,
) -> dict:
    values = pd.to_numeric(
        frame["quantity"],
        errors="coerce",
    ).dropna()

    if values.empty:
        return {
            "samples": 0,
            "average": 0.0,
            "p10": 0.0,
            "p25": 0.0,
        }

    return {
        "samples": int(
            len(values)
        ),
        "average": float(
            values.mean()
        ),
        "p10": float(
            values.quantile(
                0.10
            )
        ),
        "p25": float(
            values.quantile(
                0.25
            )
        ),
    }


def _baseline_ramss(
    corte: str,
    fecha_referencia=None,
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
        "baseline_weekday",
        "baseline_tipo_dia",
        "baseline_last_sample",
        "baseline_age_days",
        "baseline_freshness",
    ]

    if _corte_normalizado(
        corte
    ) != "09":
        return pd.DataFrame(
            columns=columns
        )

    path = _ramss_baseline_path()

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

    observations = (
        data.get("observations")
        or []
    )

    if not observations:
        return pd.DataFrame(
            columns=columns
        )

    reference = _fecha_contexto(
        fecha_referencia
    )

    reference_date = (
        reference.date()
    )

    day = reference.day
    weekday = reference.weekday()
    tipo_dia = _tipo_dia(
        reference
    )

    frame = pd.DataFrame(
        observations
    )

    required = {
        "date",
        "codigo",
        "medio_key",
        "quantity",
        "day_of_month",
        "weekday",
        "tipo_dia",
    }

    if (
        frame.empty
        or not required.issubset(
            frame.columns
        )
    ):
        return pd.DataFrame(
            columns=columns
        )

    frame = frame.copy()

    frame["date_dt"] = pd.to_datetime(
        frame["date"],
        errors="coerce",
    )

    frame["quantity"] = pd.to_numeric(
        frame["quantity"],
        errors="coerce",
    )

    frame["codigo"] = (
        frame["codigo"]
        .astype(str)
        .str.replace(
            ".0",
            "",
            regex=False,
        )
        .str.strip()
    )

    frame["medio_key"] = (
        frame["medio_key"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    frame = frame.dropna(
        subset=[
            "date_dt",
            "quantity",
        ]
    )

    # Nunca usar el dia evaluado ni muestras futuras.
    frame = frame[
        frame["date_dt"].dt.date
        < reference_date
    ].copy()

    if frame.empty:
        return pd.DataFrame(
            columns=columns
        )

    rows = []

    for (
        codigo,
        medio_key,
    ), group in frame.groupby(
        [
            "codigo",
            "medio_key",
        ],
        dropna=False,
    ):
        candidates = [
            (
                "RAMSS_EXACT",
                group[
                    pd.to_numeric(
                        group[
                            "day_of_month"
                        ],
                        errors="coerce",
                    )
                    == day
                ],
            ),
            (
                "RAMSS_WEEKDAY",
                group[
                    pd.to_numeric(
                        group[
                            "weekday"
                        ],
                        errors="coerce",
                    )
                    == weekday
                ],
            ),
            (
                "RAMSS_TIPO_DIA",
                group[
                    group[
                        "tipo_dia"
                    ]
                    .astype(str)
                    .eq(
                        tipo_dia
                    )
                ],
            ),
            (
                "RAMSS_FALLBACK",
                group,
            ),
        ]

        selected_source = None
        selected = None
        selected_stats = None

        for (
            source,
            candidate,
        ) in candidates:
            stats = _ramss_stats(
                candidate
            )

            if (
                stats["samples"]
                >= MIN_MUESTRAS_BASELINE
            ):
                selected_source = source
                selected = candidate
                selected_stats = stats
                break

        if (
            selected is None
            or selected.empty
            or selected_stats is None
        ):
            continue

        last_sample = (
            selected[
                "date_dt"
            ]
            .max()
            .date()
        )

        age_days = (
            reference_date
            - last_sample
        ).days

        rows.append({
            "codigo":
                str(codigo),
            "medio_key":
                str(medio_key),
            "promedio_baseline":
                selected_stats[
                    "average"
                ],
            "muestras_baseline":
                selected_stats[
                    "samples"
                ],
            "p10_baseline":
                selected_stats[
                    "p10"
                ],
            "p25_baseline":
                selected_stats[
                    "p25"
                ],
            "baseline_source":
                selected_source,
            "baseline_hour":
                8,
            "baseline_day":
                day,
            "baseline_weekday":
                weekday,
            "baseline_tipo_dia":
                tipo_dia,
            "baseline_last_sample":
                last_sample.isoformat(),
            "baseline_age_days":
                age_days,
            "baseline_freshness":
                _ramss_freshness(
                    age_days
                ),
        })

    if not rows:
        return pd.DataFrame(
            columns=columns
        )

    return pd.DataFrame(
        rows,
        columns=columns,
    )


def _baseline_nexus(
    corte: str,
    fecha_referencia=None,
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
        "baseline_weekday",
        "baseline_tipo_dia",
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

    referencia = _fecha_contexto(
        fecha_referencia
    )

    day = referencia.day
    weekday = referencia.weekday()
    tipo_dia = _tipo_dia(
        referencia
    )

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
                "baseline_weekday":
                    weekday,
                "baseline_tipo_dia":
                    tipo_dia,
            }

        except Exception:
            continue

    weekday_rows = {}

    for item in (
        data.get("weekday_items")
        or []
    ):
        try:
            if int(
                item.get("hour")
            ) != hour:
                continue

            if int(
                item.get("weekday")
            ) != weekday:
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

            weekday_rows[key] = {
                "codigo": key[0],
                "medio_key": key[1],
                "promedio_baseline":
                    float(
                        item.get("average")
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
                    "NEXUS_WEEKDAY",
                "baseline_hour":
                    hour,
                "baseline_day":
                    day,
                "baseline_weekday":
                    weekday,
                "baseline_tipo_dia":
                    tipo_dia,
            }

        except Exception:
            continue

    tipo_dia_rows = {}

    for item in (
        data.get("tipo_dia_items")
        or []
    ):
        try:
            if int(
                item.get("hour")
            ) != hour:
                continue

            if str(
                item.get("tipo_dia")
                or ""
            ) != tipo_dia:
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

            if (
                key in exact
                or key in weekday_rows
            ):
                continue

            tipo_dia_rows[key] = {
                "codigo": key[0],
                "medio_key": key[1],
                "promedio_baseline":
                    float(
                        item.get("average")
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
                    "NEXUS_TIPO_DIA",
                "baseline_hour":
                    hour,
                "baseline_day":
                    day,
                "baseline_weekday":
                    weekday,
                "baseline_tipo_dia":
                    tipo_dia,
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

            if (
                key in exact
                or key in weekday_rows
                or key in tipo_dia_rows
            ):
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
                "baseline_weekday":
                    weekday,
                "baseline_tipo_dia":
                    tipo_dia,
            }

        except Exception:
            continue

    rows = (
        list(exact.values())
        + list(weekday_rows.values())
        + list(tipo_dia_rows.values())
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


def _baseline_hibrido(
    corte: str,
    fecha_referencia=None,
) -> pd.DataFrame:
    ramss = _baseline_ramss(
        corte,
        fecha_referencia=
            fecha_referencia,
    )

    legacy = _baseline_nexus(
        corte,
        fecha_referencia=
            fecha_referencia,
    )

    extra_columns = {
        "baseline_last_sample":
            pd.NA,
        "baseline_age_days":
            pd.NA,
        "baseline_freshness":
            "LEGACY",
    }

    for (
        column,
        default,
    ) in extra_columns.items():
        if column not in legacy.columns:
            legacy[column] = default

    if _corte_normalizado(
        corte
    ) != "09":
        return legacy

    if ramss.empty:
        return legacy

    if legacy.empty:
        return ramss

    selected = {}

    for row in ramss.to_dict(
        "records"
    ):
        key = (
            str(
                row.get("codigo")
                or ""
            ),
            str(
                row.get("medio_key")
                or ""
            ),
        )

        selected[key] = row

    # Legacy reemplaza RAMSS solo cuando RAMSS esta STALE.
    for row in legacy.to_dict(
        "records"
    ):
        key = (
            str(
                row.get("codigo")
                or ""
            ),
            str(
                row.get("medio_key")
                or ""
            ),
        )

        current = selected.get(
            key
        )

        if (
            current is None
            or str(
                current.get(
                    "baseline_freshness"
                )
                or ""
            ).upper()
            == "STALE"
        ):
            selected[key] = row

    return pd.DataFrame(
        list(
            selected.values()
        )
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


def _promedios_historicos(
    corte: str,
    tipo_dia_actual: str,
    fecha_referencia=None,
) -> pd.DataFrame:
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

    hoy = (
        _fecha_contexto(
            fecha_referencia
        )
        .date()
        .isoformat()
    )
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


def _agregar_promedio(
    df: pd.DataFrame,
    corte: str,
    fecha_referencia=None,
) -> pd.DataFrame:
    out = df.copy()

    referencia = _fecha_contexto(
        fecha_referencia
    )

    tipo_actual = _tipo_dia(
        referencia
    )

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

    baseline = _baseline_hibrido(
        corte,
        fecha_referencia=fecha_referencia,
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
        out["baseline_weekday"] = pd.NA
        out["baseline_tipo_dia"] = pd.NA
        out["baseline_last_sample"] = pd.NA
        out["baseline_age_days"] = pd.NA
        out["baseline_freshness"] = pd.NA

    hist = _promedios_historicos(
        corte,
        tipo_actual,
        fecha_referencia=fecha_referencia,
    )

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
        'HISTORICO '
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
    fecha_referencia = kwargs.get(
        "fecha_referencia"
    )

    out = _agregar_promedio(
        df,
        corte,
        fecha_referencia=fecha_referencia,
    )

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
