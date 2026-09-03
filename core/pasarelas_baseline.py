from __future__ import annotations

import json
import re
import statistics
import zipfile
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from core.platform import ensure_user_directories


XML_NS = (
    "http://schemas.openxmlformats.org/"
    "spreadsheetml/2006/main"
)

NS = {
    "main": XML_NS,
}

REQUIRED_FIELDS = {
    "FECHA",
    "HORA",
    "VERTICAL",
    "MEDIO_PAGO",
    "CANTIDAD",
    "FORMATODIA",
}


def _baseline_path() -> Path:
    paths = ensure_user_directories()

    path = (
        Path(paths["config"])
        / "baselines"
        / "pasarelas.json"
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    return path


def _normalize_name(
    value: Any,
) -> str:
    return str(
        value or ""
    ).strip()


def _normalize_hour(
    value: str,
) -> int:
    parsed = datetime.fromisoformat(
        value
    )

    return parsed.hour


def _percentile(
    values: list[float],
    percentile: float,
) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)

    if len(ordered) == 1:
        return float(
            ordered[0]
        )

    position = (
        len(ordered) - 1
    ) * percentile

    lower = int(position)
    upper = min(
        lower + 1,
        len(ordered) - 1,
    )

    fraction = (
        position - lower
    )

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
            statistics.mean(
                ordered
            ),
            2,
        ),
        "median": round(
            statistics.median(
                ordered
            ),
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


def _shared_values(
    field: ET.Element,
) -> list[Any]:
    shared = field.find(
        "main:sharedItems",
        NS,
    )

    if shared is None:
        return []

    values = []

    for child in list(shared):
        kind = (
            child.tag
            .split("}")[-1]
        )

        raw = child.attrib.get(
            "v"
        )

        if kind == "m":
            values.append(None)

        elif kind == "n":
            try:
                number = float(raw)

                values.append(
                    int(number)
                    if number.is_integer()
                    else number
                )
            except Exception:
                values.append(raw)

        else:
            values.append(raw)

    return values


def _decode_value(
    element: ET.Element,
    shared: list[Any],
) -> Any:
    kind = (
        element.tag
        .split("}")[-1]
    )

    raw = element.attrib.get(
        "v"
    )

    if kind == "x":
        index = int(
            raw or 0
        )

        if (
            0 <= index
            < len(shared)
        ):
            return shared[index]

        return None

    if kind == "m":
        return None

    if kind == "n":
        try:
            number = float(raw)

            return (
                int(number)
                if number.is_integer()
                else number
            )
        except Exception:
            return raw

    return raw


def _find_historical_cache(
    archive: zipfile.ZipFile,
) -> tuple[
    str,
    str,
    list[str],
    list[list[Any]],
]:
    definitions = sorted(
        name
        for name in archive.namelist()
        if re.fullmatch(
            r"xl/pivotCache/"
            r"pivotCacheDefinition\d+\.xml",
            name,
        )
    )

    for definition_path in definitions:
        root = ET.fromstring(
            archive.read(
                definition_path
            )
        )

        cache_fields = root.find(
            "main:cacheFields",
            NS,
        )

        if cache_fields is None:
            continue

        fields = list(
            cache_fields
        )

        names = [
            _normalize_name(
                field.attrib.get(
                    "name"
                )
            )
            for field in fields
        ]

        if not REQUIRED_FIELDS.issubset(
            set(names)
        ):
            continue

        match = re.search(
            r"Definition(\d+)",
            definition_path,
        )

        if not match:
            continue

        cache_id = match.group(1)

        records_path = (
            "xl/pivotCache/"
            f"pivotCacheRecords{cache_id}.xml"
        )

        if (
            records_path
            not in archive.namelist()
        ):
            continue

        shared_maps = [
            _shared_values(
                field
            )
            for field in fields
        ]

        records_root = ET.fromstring(
            archive.read(
                records_path
            )
        )

        rows = []

        for record in records_root:
            cells = list(
                record
            )

            row = []

            for index in range(
                len(names)
            ):
                if index >= len(cells):
                    row.append(None)
                    continue

                row.append(
                    _decode_value(
                        cells[index],
                        shared_maps[index],
                    )
                )

            rows.append(row)

        return (
            definition_path,
            records_path,
            names,
            rows,
        )

    raise RuntimeError(
        "No se encontro un PivotCache "
        "historico compatible con Pasarelas."
    )


def build_pasarelas_baseline(
    workbook_path: str | Path,
) -> dict[str, Any]:
    source = Path(
        workbook_path
    ).expanduser()

    if not source.exists():
        raise FileNotFoundError(
            source
        )

    with zipfile.ZipFile(
        source,
        "r",
    ) as archive:
        (
            definition_path,
            records_path,
            fields,
            rows,
        ) = _find_historical_cache(
            archive
        )

    indexes = {
        name: fields.index(name)
        for name in REQUIRED_FIELDS
    }

    grouped: dict[
        tuple[str, str, int, int],
        list[float],
    ] = defaultdict(list)

    fallback_grouped: dict[
        tuple[str, str, int],
        list[float],
    ] = defaultdict(list)

    valid_dates = []
    invalid_rows = 0

    verticals = set()
    medios = set()
    hours = set()

    for row in rows:
        try:
            raw_date = row[
                indexes["FECHA"]
            ]

            raw_hour = row[
                indexes["HORA"]
            ]

            vertical = _normalize_name(
                row[
                    indexes["VERTICAL"]
                ]
            )

            medio = _normalize_name(
                row[
                    indexes["MEDIO_PAGO"]
                ]
            )

            cantidad = row[
                indexes["CANTIDAD"]
            ]

            raw_day = row[
                indexes["FORMATODIA"]
            ]

            if not (
                raw_date
                and raw_hour
                and vertical
                and medio
            ):
                invalid_rows += 1
                continue

            parsed_date = (
                datetime.fromisoformat(
                    str(raw_date)
                ).date()
            )

            # Descarta registros da?ados del
            # cache hist?rico (ej. a?o 1900).
            if parsed_date.year < 2000:
                invalid_rows += 1
                continue

            hour = _normalize_hour(
                str(raw_hour)
            )

            day_of_month = int(
                raw_day
            )

            quantity = float(
                cantidad or 0
            )

        except Exception:
            invalid_rows += 1
            continue

        valid_dates.append(
            parsed_date
        )

        verticals.add(
            vertical
        )

        medios.add(
            medio
        )

        hours.add(
            hour
        )

        grouped[
            (
                vertical,
                medio,
                hour,
                day_of_month,
            )
        ].append(
            quantity
        )

        fallback_grouped[
            (
                vertical,
                medio,
                hour,
            )
        ].append(
            quantity
        )

    if not valid_dates:
        raise RuntimeError(
            "No se encontraron registros "
            "historicos validos."
        )

    baseline_items = []

    for (
        vertical,
        medio,
        hour,
        day_of_month,
    ), values in sorted(
        grouped.items()
    ):
        stats = _stats(
            values
        )

        baseline_items.append({
            "vertical": vertical,
            "medio": medio,
            "hour": hour,
            "day_of_month":
                day_of_month,
            **stats,
        })

    fallback_items = []

    for (
        vertical,
        medio,
        hour,
    ), values in sorted(
        fallback_grouped.items()
    ):
        fallback_items.append({
            "vertical": vertical,
            "medio": medio,
            "hour": hour,
            **_stats(values),
        })

    baseline = {
        "schema_version": 1,
        "monitor": "PASARELAS",
        "source": {
            "file_name":
                source.name,
            "pivot_definition":
                definition_path,
            "pivot_records":
                records_path,
        },
        "coverage": {
            "records_valid":
                sum(
                    len(values)
                    for values
                    in grouped.values()
                ),
            "records_invalid":
                invalid_rows,
            "first_date":
                min(
                    valid_dates
                ).isoformat(),
            "last_date":
                max(
                    valid_dates
                ).isoformat(),
            "unique_dates":
                len(
                    set(valid_dates)
                ),
            "verticals":
                len(verticals),
            "medios":
                len(medios),
            "hours":
                sorted(hours),
        },
        "key": [
            "vertical",
            "medio",
            "hour",
            "day_of_month",
        ],
        "items":
            baseline_items,
        "fallback_key": [
            "vertical",
            "medio",
            "hour",
        ],
        "fallback_items":
            fallback_items,
    }

    return baseline


def save_pasarelas_baseline(
    baseline: dict[str, Any],
    path: str | Path | None = None,
) -> Path:
    target = (
        Path(path)
        if path
        else _baseline_path()
    )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = target.with_suffix(
        ".tmp"
    )

    # El baseline se consulta por Nexus, no necesita
    # formato visual con indentacion. Mantenerlo compacto
    # reduce considerablemente el espacio ocupado sin
    # perder informacion estadistica.
    tmp.write_text(
        json.dumps(
            baseline,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    tmp.replace(
        target
    )

    return target


def import_pasarelas_baseline(
    workbook_path: str | Path,
) -> dict[str, Any]:
    baseline = (
        build_pasarelas_baseline(
            workbook_path
        )
    )

    target = save_pasarelas_baseline(
        baseline
    )

    return {
        "path": str(target),
        "coverage":
            baseline["coverage"],
        "items":
            len(
                baseline["items"]
            ),
        "fallback_items":
            len(
                baseline[
                    "fallback_items"
                ]
            ),
    }
