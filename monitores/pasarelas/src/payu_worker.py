
from __future__ import annotations
import argparse
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.main import ejecutar_web_payu

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fecha-inicio", required=True)
    ap.add_argument("--fecha-fin", required=True)
    a = ap.parse_args()
    ejecutar_web_payu(a.fecha_inicio, a.fecha_fin)

if __name__ == "__main__":
    main()
