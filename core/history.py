from __future__ import annotations
import csv
from pathlib import Path

EXEC_FIELDS = ["fecha","corte","monitor","modo","estado","duracion_seg","detalle","ruta_reporte"]
MONTH_FIELDS = ["fecha","corte","monitor","modo","estado","duracion_seg","detalle","ruta_reporte"]


def _append_csv(path: Path, fields: list[str], row: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in fields})


def append_event(root: Path, event: dict, accumulate_month: bool = False):
    general = root / "GENERAL"
    general.mkdir(parents=True, exist_ok=True)
    exec_hist = general / "historico_ejecuciones.csv"
    _append_csv(exec_hist, EXEC_FIELDS, event)
    month_hist = None
    if accumulate_month:
        month_hist = general / "historico_mensual.csv"
        _append_csv(month_hist, MONTH_FIELDS, event)
    return exec_hist, month_hist


def _load_csv(path: Path):
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_events(root: Path):
    return _load_csv(root / "GENERAL" / "historico_ejecuciones.csv")


def load_monthly_events(root: Path):
    return _load_csv(root / "GENERAL" / "historico_mensual.csv")
