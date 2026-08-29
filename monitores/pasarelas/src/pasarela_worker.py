
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.fuentes.ecollect_bot import descargar_ecollect

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True)
    ap.add_argument("--fecha-inicio", required=True)
    ap.add_argument("--fecha-fin", required=True)
    ap.add_argument("--worker", default="worker")
    args = ap.parse_args()

    items = []
    for raw in args.items.split(","):
        codigo, tipo = raw.split(":", 1)
        items.append({"codigo": codigo, "tipo_reporte": tipo})
    print(f"[{args.worker}] {len(items)} consultas. Navegador visible={os.getenv('HEADLESS','true').lower() != 'true'}")
    descargar_ecollect(args.fecha_inicio, args.fecha_fin, items)

if __name__ == "__main__":
    main()
