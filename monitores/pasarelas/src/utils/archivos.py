from pathlib import Path
import shutil
from datetime import datetime, timedelta


def limpiar_temporales(carpeta: Path, conservar_ultimos: int = 0) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    archivos = [p for p in carpeta.iterdir() if p.is_file() and p.name != '.gitkeep']
    archivos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for p in archivos[conservar_ultimos:]:
        try:
            p.unlink()
        except Exception:
            pass


def asegurar_carpetas(*carpetas: Path) -> None:
    for c in carpetas:
        c.mkdir(parents=True, exist_ok=True)


def copiar_ultimo(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
