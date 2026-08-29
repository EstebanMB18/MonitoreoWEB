from __future__ import annotations
import csv
from collections import Counter
from datetime import datetime
from pathlib import Path


def export_monthly_excel(output_root: Path):
    """Creates a compact monthly Excel from the validated historical daily runs only.
    This file is fed by the day-before job so hourly/operational tests do not pollute the monthly record."""
    try:
        import xlsxwriter
    except ImportError:
        return None

    general = output_root / "GENERAL"
    general.mkdir(parents=True, exist_ok=True)
    hist = general / "historico_mensual.csv"
    rows = []
    if hist.exists():
        with hist.open("r", newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

    month = datetime.now().strftime("%Y-%m")
    rows = [r for r in rows if str(r.get("fecha", "")).startswith(month)]
    target = general / f"Acumulado_Mensual_{datetime.now():%Y_%m}.xlsx"

    wb = xlsxwriter.Workbook(target)
    ws = wb.add_worksheet("Historico")
    dash = wb.add_worksheet("Dashboard")

    blue = "#0057B8"; orange = "#F58220"
    hdr = wb.add_format({"bold": True, "bg_color": blue, "font_color": "white", "border": 1, "align": "center"})
    title = wb.add_format({"bold": True, "font_size": 18, "font_color": blue})
    kpi = wb.add_format({"bold": True, "font_size": 22, "align": "center", "valign": "vcenter", "bg_color": "#F2F7FC", "border": 1})
    ok_fmt = wb.add_format({"bg_color": "#E7F4D8"})
    err_fmt = wb.add_format({"bg_color": "#FDE7E7"})
    note_fmt = wb.add_format({"italic": True, "font_color": "#5A6776"})

    fields = ["fecha", "corte", "monitor", "modo", "estado", "duracion_seg", "detalle", "ruta_reporte"]
    for c, h in enumerate(fields):
        ws.write(0, c, h, hdr)
    for r, row in enumerate(rows, start=1):
        for c, h in enumerate(fields):
            ws.write(r, c, row.get(h, ""))
        ws.set_row(r, None, ok_fmt if row.get("estado") == "OK" else err_fmt)
    ws.freeze_panes(1, 0)
    ws.autofilter(0, 0, max(len(rows), 1), len(fields) - 1)
    ws.set_column(0, 0, 12)
    ws.set_column(1, 5, 14)
    ws.set_column(6, 7, 44)

    dash.merge_range("A1:H2", f"MONITOREO COMPENSAR · ACUMULADO VALIDADO {month}", title)
    dash.write("A4", "Este consolidado se alimenta con la ejecución de día anterior; no mezcla cortes horarios ni pruebas manuales.", note_fmt)
    counts = Counter(r.get("monitor", "") for r in rows)
    oks = sum(1 for r in rows if r.get("estado") == "OK")
    errs = len(rows) - oks
    labels = [("Pasarelas", counts["PASARELAS"]), ("AWS", counts["AWS"]), ("Hércules", counts["HERCULES"]), ("OK", oks), ("Novedades", errs)]
    col = 0
    for name, val in labels:
        dash.write(6, col, name, hdr)
        dash.write(7, col, val, kpi)
        dash.set_column(col, col, 18)
        col += 1

    dash.write_row("A11", ["Monitor", "Ejecuciones"], hdr)
    for i, m in enumerate(["PASARELAS", "AWS", "HERCULES"], start=12):
        dash.write(i - 1, 0, m)
        dash.write(i - 1, 1, counts[m])
    chart = wb.add_chart({"type": "column"})
    chart.add_series({"name": "Ejecuciones", "categories": "=Dashboard!$A$12:$A$14", "values": "=Dashboard!$B$12:$B$14", "fill": {"color": orange}, "border": {"color": orange}})
    chart.set_title({"name": "Movimientos validados por monitor"})
    chart.set_legend({"none": True})
    dash.insert_chart("D11", chart, {"x_scale": 1.2, "y_scale": 1.2})

    wb.close()
    return target
