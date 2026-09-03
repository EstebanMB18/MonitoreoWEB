from __future__ import annotations

from pathlib import Path
from typing import Any

from core.monthly_history import (
    build_monthly_history,
)
from core.platform import (
    ensure_user_directories,
)


def _output_path(
    year: int,
    month: int,
) -> Path:
    paths = ensure_user_directories()

    root = (
        Path(paths["default_output"])
        / "reports"
        / "monthly"
        / f"{year:04d}"
    )

    root.mkdir(
        parents=True,
        exist_ok=True,
    )

    return (
        root
        / (
            "Nexus_Mensual_"
            f"{year:04d}_{month:02d}.xlsx"
        )
    )


def _write_sheet(
    workbook,
    name: str,
    rows: list[dict[str, Any]],
) -> None:
    worksheet = workbook.add_worksheet(
        name[:31]
    )

    header_format = workbook.add_format({
        "bold": True,
        "border": 1,
        "align": "center",
        "valign": "vcenter",
    })

    cell_format = workbook.add_format({
        "border": 1,
    })

    if not rows:
        worksheet.write(
            0,
            0,
            "Sin datos",
            header_format,
        )
        return

    columns = list(
        rows[0].keys()
    )

    for col, column in enumerate(
        columns
    ):
        worksheet.write(
            0,
            col,
            column,
            header_format,
        )

    for row_index, row in enumerate(
        rows,
        start=1,
    ):
        for col_index, column in enumerate(
            columns
        ):
            value = row.get(
                column
            )

            if isinstance(
                value,
                (dict, list),
            ):
                value = str(value)

            worksheet.write(
                row_index,
                col_index,
                value,
                cell_format,
            )

    worksheet.freeze_panes(
        1,
        0,
    )

    worksheet.autofilter(
        0,
        0,
        max(
            len(rows),
            1,
        ),
        len(columns) - 1,
    )

    for index, column in enumerate(
        columns
    ):
        width = max(
            len(str(column)),
            *[
                len(
                    str(
                        row.get(
                            column,
                            "",
                        )
                    )
                )
                for row in rows[:200]
            ],
        )

        worksheet.set_column(
            index,
            index,
            min(
                max(
                    width + 2,
                    12,
                ),
                42,
            ),
        )


def _daily_rows(
    data: dict[str, Any],
) -> list[dict[str, Any]]:

    rows = []

    for item in (
        data.get("daily")
        or []
    ):
        kpis = (
            item.get("kpis")
            or {}
        )

        rows.append({
            "fecha":
                item.get("date"),
            "monitor":
                item.get("monitor"),
            "cobertura":
                item.get("coverage"),
            "estado":
                item.get("status"),
            "ejecuciones_oficiales":
                item.get(
                    "official_runs"
                ),
            "ejecuciones_exitosas":
                item.get(
                    "successful_runs"
                ),
            "registros":
                item.get("records"),
            "alertas":
                item.get("alerts"),
            "errores":
                item.get("errors"),
            "kpis":
                kpis,
        })

    return rows


def _monitor_rows(
    data: dict[str, Any],
) -> list[dict[str, Any]]:

    rows = []

    for monitor, item in (
        data.get("monitors")
        or {}
    ).items():

        row = {
            "monitor":
                monitor,
            "dias":
                item.get("days"),
            "dias_ejecutados":
                item.get(
                    "days_executed"
                ),
            "dias_sin_ejecucion":
                item.get(
                    "days_without_execution"
                ),
            "ejecuciones_oficiales":
                item.get(
                    "official_runs"
                ),
            "ejecuciones_exitosas":
                item.get(
                    "successful_runs"
                ),
            "registros":
                item.get("records"),
            "alertas":
                item.get("alerts"),
            "errores":
                item.get("errors"),
            "estados":
                item.get("statuses"),
        }

        for key, value in (
            item.get("kpis")
            or {}
        ).items():
            row[f"kpi_{key}"] = value

        rows.append(row)

    return rows


def export_monthly_report(
    *,
    year: int,
    month: int,
    monitor: str | None = None,
    output_path: str | Path | None = None,
) -> Path:

    try:
        import xlsxwriter
    except ImportError as exc:
        raise RuntimeError(
            "xlsxwriter no esta disponible."
        ) from exc

    data = build_monthly_history(
        year=year,
        month=month,
        monitor=monitor,
    )

    target = (
        Path(output_path)
        if output_path
        else _output_path(
            year,
            month,
        )
    )

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    workbook = (
        xlsxwriter.Workbook(
            str(target)
        )
    )

    summary = workbook.add_worksheet(
        "Resumen"
    )

    title_format = workbook.add_format({
        "bold": True,
        "font_size": 16,
    })

    header_format = workbook.add_format({
        "bold": True,
        "border": 1,
    })

    value_format = workbook.add_format({
        "border": 1,
    })

    summary.merge_range(
        "A1:D2",
        (
            "NEXUS - REPORTE MENSUAL "
            f"{year:04d}-{month:02d}"
        ),
        title_format,
    )

    period = (
        data.get("period")
        or {}
    )

    summary_rows = [
        (
            "Periodo",
            (
                f'{period.get("start_date")} '
                f'a {period.get("end_date")}'
            ),
        ),
        (
            "Monitor",
            data.get("monitor")
            or "TODOS",
        ),
        (
            "Cierres",
            data.get(
                "summary",
                {},
            ).get(
                "closures",
                0,
            ),
        ),
        (
            "Dias con ejecucion",
            data.get(
                "summary",
                {},
            ).get(
                "days_with_execution",
                0,
            ),
        ),
        (
            "Ejecuciones oficiales",
            data.get(
                "summary",
                {},
            ).get(
                "official_runs",
                0,
            ),
        ),
        (
            "Registros",
            data.get(
                "summary",
                {},
            ).get(
                "records",
                0,
            ),
        ),
        (
            "Alertas",
            data.get(
                "summary",
                {},
            ).get(
                "alerts",
                0,
            ),
        ),
        (
            "Errores",
            data.get(
                "summary",
                {},
            ).get(
                "errors",
                0,
            ),
        ),
    ]

    summary.write(
        3,
        0,
        "Indicador",
        header_format,
    )

    summary.write(
        3,
        1,
        "Valor",
        header_format,
    )

    for row, (
        label,
        value,
    ) in enumerate(
        summary_rows,
        start=4,
    ):
        summary.write(
            row,
            0,
            label,
            value_format,
        )

        summary.write(
            row,
            1,
            value,
            value_format,
        )

    summary.set_column(
        0,
        0,
        28,
    )

    summary.set_column(
        1,
        1,
        32,
    )

    _write_sheet(
        workbook,
        "Monitores",
        _monitor_rows(data),
    )

    _write_sheet(
        workbook,
        "Diario",
        _daily_rows(data),
    )

    workbook.close()

    return target
