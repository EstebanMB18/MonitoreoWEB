
from __future__ import annotations
import argparse
import sys
from datetime import datetime, date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from monitoreo_hercules import main as ejecutar
from sharepoint_hercules import copiar_diario_a_sharepoint, copiar_dashboard_a_sharepoint
from generar_dashboard_hercules import generar_dashboard

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", choices=["actual","dia-anterior","fecha"], default="actual")
    ap.add_argument("--fecha")
    ap.add_argument("--hora-inicio", default="00:00")
    ap.add_argument("--hora-fin", default="23:59")
    args = ap.parse_args()

    if args.modo == "actual":
        dias = 0
        nombre = "hercules_diario.xlsx"
        resumen = "resumen_hercules_diario.xlsx"
    elif args.modo == "dia-anterior":
        dias = 1
        nombre = "hercules_dia_anterior.xlsx"
        resumen = "resumen_hercules_dia_anterior.xlsx"
    else:
        if not args.fecha:
            raise SystemExit("--fecha es obligatorio")
        objetivo = datetime.strptime(args.fecha, "%Y-%m-%d").date()
        dias = (date.today() - objetivo).days
        if dias < 0:
            raise SystemExit("La fecha no puede ser futura")
        nombre = f"hercules_{objetivo:%Y%m%d}.xlsx"
        resumen = f"resumen_hercules_{objetivo:%Y%m%d}.xlsx"

    ejecutar(dias_atras=dias, nombre_descarga=nombre, nombre_resumen=resumen, hora_inicio=args.hora_inicio, hora_fin=args.hora_fin)

    # Only current day replaces the official daily report.
    if args.modo == "actual":
        copiar_diario_a_sharepoint()

    dashboard = generar_dashboard()
    try:
        copiar_dashboard_a_sharepoint(dashboard)
    except Exception as exc:
        print(f"Advertencia al copiar dashboard: {exc}")
    print(f"Hércules terminado: modo={args.modo}, dias_atras={dias}")

if __name__ == "__main__":
    main()
