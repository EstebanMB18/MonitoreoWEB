from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from core.platform import ensure_user_directories


MIN_SAMPLES = 5

RAMSS_FILES = (
    "RAMSS_RECAUDO_2024_NORMALIZADO.xlsx",
    "RAMSS_RECAUDO_2025_H1_NORMALIZADO.xlsx",
    "RAMSS_RECAUDO_2025_H2_NORMALIZADO.xlsx",
    "RAMSS_RECAUDO_2026_NORMALIZADO.xlsx",
)


def _output_path() -> Path:
    paths = ensure_user_directories()

    path = (
        Path(paths["config"])
        / "baselines"
        / "pasarelas_ramss.json"
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    return path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _festivos() -> set[str]:
    path = (
        _project_root()
        / "GENERAL"
        / "calendario_festivos.txt"
    )

    if not path.exists():
        return set()

    try:
        return {
            line.strip()
            for line in path.read_text(
                encoding="utf-8-sig"
            ).splitlines()
            if line.strip()
            and not line.lstrip().startswith("#")
        }
    except Exception:
        return set()


def _tipo_dia(
    value,
    festivos: set[str],
) -> str:
    if (
        value.weekday() >= 5
        or value.isoformat() in festivos
    ):
        return "FIN_SEMANA_FESTIVO"

    return "HABIL"


def _percentile(
    values: list[float],
    percentile: float,
) -> float:
    ordered = sorted(values)

    if not ordered:
        return 0.0

    if len(ordered) == 1:
        return float(ordered[0])

    position = (
        len(ordered) - 1
    ) * percentile

    lower = int(position)
    upper = min(
        lower + 1,
        len(ordered) - 1,
    )

    fraction = position - lower

    return (
        ordered[lower]
        + (
            ordered[upper]
            - ordered[lower]
        )
        * fraction
    )


def _stats(
    values: list[float],
) -> dict[str, Any]:
    ordered = sorted(values)

    return {
        "samples": len(ordered),
        "average": round(
            statistics.mean(ordered),
            2,
        ),
        "median": round(
            statistics.median(ordered),
            2,
        ),
        "min": round(
            min(ordered),
            2,
        ),
        "max": round(
            max(ordered),
            2,
        ),
        "p10": round(
            _percentile(
                ordered,
                0.10,
            ),
            2,
        ),
        "p25": round(
            _percentile(
                ordered,
                0.25,
            ),
            2,
        ),
        "p75": round(
            _percentile(
                ordered,
                0.75,
            ),
            2,
        ),
        "p90": round(
            _percentile(
                ordered,
                0.90,
            ),
            2,
        ),
    }


def _monitor_medio_key(
    codigo: str,
    ruta: str,
    medio_base: str,
) -> str | None:
    codigo = str(codigo).strip()
    ruta = str(ruta or "").strip().upper()
    medio = str(
        medio_base or ""
    ).strip().upper()

    # Separaciones comprobadas.
    if ruta == "PSE_LINK_PAGO":
        return "PSE LINK DE PAGO"

    if ruta == "TARJETA_CREDITO_LINK_PAGO":
        return "TARJ. CREDITO LINK PAGO"

    # 41621 usa PAYU para PSE/Tarjeta en el monitor.
    # El historico RAMSS 08:00 reporta rutas RED que
    # no deben convertirse artificialmente a PAYU.
    if codigo == "41621" and medio in {
        "PSE",
        "TARJETA_CREDITO",
    }:
        return None

    # 41604 separa REDES PRESENCIAL y SAC PRESENCIAL,
    # pero el historico solo contiene REDES_JAVA.
    # No existe informacion suficiente para repartirlo.
    if codigo == "41604" and medio == "REDES":
        return None

    if medio == "MODULOS_AUTOSERVICIO":
        return "MODULOS AUTOSERVICIOS"

    if medio == "TARJETA_CREDITO":
        return "TARJ. CREDITO"

    if medio == "REDES":
        if codigo == "41611":
            return "REDES / SAC"

        return "REDES"

    if medio in {
        "PSE",
        "SAP",
        "TUP",
        "CUPOYA",
    }:
        return medio

    return None


def build_ramss_pasarelas_baseline(
    directory: str | Path,
) -> dict[str, Any]:
    base = Path(directory)

    frames = []
    files_used = []

    for filename in RAMSS_FILES:
        path = base / filename

        if not path.exists():
            continue

        excel = pd.ExcelFile(path)

        df = pd.read_excel(
            path,
            sheet_name=excel.sheet_names[0],
        )

        frames.append(df)
        files_used.append(filename)

    if not frames:
        raise RuntimeError(
            "No se encontraron historicos "
            "normalizados RAMSS."
        )

    df = pd.concat(
        frames,
        ignore_index=True,
    )

    required = {
        "FECHA",
        "CODIGO_VERTICAL",
        "RUTA_PAGO",
        "MEDIO_PAGO_BASE",
        "CANTIDAD_PAGOS",
        "TIPO_REGISTRO",
        "CORTE_SELECCIONADO",
    }

    missing = (
        required
        - set(df.columns)
    )

    if missing:
        raise RuntimeError(
            "Faltan columnas RAMSS: "
            + ", ".join(
                sorted(missing)
            )
        )

    df = df.copy()

    df["FECHA"] = pd.to_datetime(
        df["FECHA"],
        errors="coerce",
    )

    df["CANTIDAD_PAGOS"] = pd.to_numeric(
        df["CANTIDAD_PAGOS"],
        errors="coerce",
    )

    df["CORTE_SELECCIONADO"] = (
        df["CORTE_SELECCIONADO"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # HU-23:
    # RAMSS tiene profundidad suficiente para el corte 09
    # usando el snapshot historico de las 08:00.
    df = df[
        df["TIPO_REGISTRO"]
        .astype(str)
        .eq("ULTIMO_CORTE_HISTORICO")
        & df["CORTE_SELECCIONADO"]
        .eq("08:00")
    ].copy()

    df = df.dropna(
        subset=[
            "FECHA",
            "CANTIDAD_PAGOS",
        ]
    )

    if df.empty:
        raise RuntimeError(
            "RAMSS no contiene muestras validas "
            "del corte historico 08:00."
        )

    df["codigo"] = (
        df["CODIGO_VERTICAL"]
        .astype(str)
        .str.replace(
            ".0",
            "",
            regex=False,
        )
        .str.strip()
    )

    df["medio_key"] = df.apply(
        lambda row:
            _monitor_medio_key(
                row["codigo"],
                row.get(
                    "RUTA_PAGO"
                ),
                row.get(
                    "MEDIO_PAGO_BASE"
                ),
            ),
        axis=1,
    )

    source_rows = len(df)

    unsupported_rows = int(
        df["medio_key"]
        .isna()
        .sum()
    )

    df = df[
        df["medio_key"]
        .notna()
    ].copy()

    festivos = _festivos()

    df["fecha_iso"] = (
        df["FECHA"]
        .dt.date
        .astype(str)
    )

    df["day_of_month"] = (
        df["FECHA"]
        .dt.day
    )

    df["weekday"] = (
        df["FECHA"]
        .dt.weekday
    )

    df["tipo_dia"] = (
        df["FECHA"]
        .dt.date
        .map(
            lambda value:
                _tipo_dia(
                    value,
                    festivos,
                )
        )
    )

    exact = defaultdict(list)
    weekday = defaultdict(list)
    tipo_dia = defaultdict(list)
    fallback = defaultdict(list)

    observations = []

    for row in df.itertuples(
        index=False
    ):
        codigo = str(row.codigo)
        medio_key = str(
            row.medio_key
        )
        value = float(
            row.CANTIDAD_PAGOS
        )

        observation = {
            "date": str(
                row.fecha_iso
            ),
            "codigo": codigo,
            "medio_key":
                medio_key,
            "quantity": value,
            "day_of_month":
                int(
                    row.day_of_month
                ),
            "weekday":
                int(
                    row.weekday
                ),
            "tipo_dia":
                str(
                    row.tipo_dia
                ),
        }

        observations.append(
            observation
        )

        exact[
            (
                codigo,
                medio_key,
                int(
                    row.day_of_month
                ),
            )
        ].append(value)

        weekday[
            (
                codigo,
                medio_key,
                int(
                    row.weekday
                ),
            )
        ].append(value)

        tipo_dia[
            (
                codigo,
                medio_key,
                str(
                    row.tipo_dia
                ),
            )
        ].append(value)

        fallback[
            (
                codigo,
                medio_key,
            )
        ].append(value)

    def build_items(
        grouped,
        names,
    ):
        items = []

        for key, values in sorted(
            grouped.items()
        ):
            item = {
                name: value
                for name, value
                in zip(
                    names,
                    key,
                )
            }

            item.update(
                _stats(values)
            )

            items.append(item)

        return items

    baseline = {
        "schema_version": 2,
        "monitor": "PASARELAS",
        "source_type":
            "RAMSS_NORMALIZED",
        "source_files":
            files_used,
        "cut": "09",
        "source_cut": "08:00",
        "minimum_samples":
            MIN_SAMPLES,
        "coverage": {
            "source_rows":
                int(source_rows),
            "mapped_rows":
                int(len(df)),
            "unsupported_rows":
                unsupported_rows,
            "first_date":
                df["FECHA"]
                .min()
                .date()
                .isoformat(),
            "last_date":
                df["FECHA"]
                .max()
                .date()
                .isoformat(),
            "unique_dates":
                int(
                    df["FECHA"]
                    .dt.date
                    .nunique()
                ),
            "combinations":
                int(
                    df[
                        [
                            "codigo",
                            "medio_key",
                        ]
                    ]
                    .drop_duplicates()
                    .shape[0]
                ),
        },
        # Se conservan agregados para diagnostico y
        # ejecuciones corrientes.
        "exact_items":
            build_items(
                exact,
                (
                    "codigo",
                    "medio_key",
                    "day_of_month",
                ),
            ),
        "weekday_items":
            build_items(
                weekday,
                (
                    "codigo",
                    "medio_key",
                    "weekday",
                ),
            ),
        "tipo_dia_items":
            build_items(
                tipo_dia,
                (
                    "codigo",
                    "medio_key",
                    "tipo_dia",
                ),
            ),
        "fallback_items":
            build_items(
                fallback,
                (
                    "codigo",
                    "medio_key",
                ),
            ),
        # Fuente cronologica para evitar usar muestras
        # posteriores a la fecha monitoreada.
        "observations":
            observations,
    }

    return baseline


def save_ramss_pasarelas_baseline(
    baseline: dict[str, Any],
    path: str | Path | None = None,
) -> Path:
    target = (
        Path(path)
        if path
        else _output_path()
    )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = target.with_suffix(
        ".tmp"
    )

    tmp.write_text(
        json.dumps(
            baseline,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    tmp.replace(target)

    return target
