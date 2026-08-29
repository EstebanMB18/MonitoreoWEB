
from __future__ import annotations
import time
from pathlib import Path

def cleanup_tree(project_root: Path, output_root: Path, days_logs=3, days_downloads=2, max_logs=30):
    now = time.time()
    rules = [
        (project_root / "monitores" / "pasarelas" / "logs", days_logs),
        (project_root / "monitores" / "pasarelas" / "data" / "temporal_descargas", days_downloads),
        (project_root / "monitores" / "hercules" / "downloads", days_downloads),
        (project_root / "monitores" / "hercules" / "reports", 7),
        (project_root / "monitores" / "aws" / "salida" / "logs", days_logs),
    ]
    deleted = 0
    for folder, days in rules:
        if not folder.exists():
            continue
        files = [p for p in folder.rglob("*") if p.is_file() and p.name != ".gitkeep"]
        for p in files:
            try:
                if now - p.stat().st_mtime > days * 86400:
                    p.unlink()
                    deleted += 1
            except OSError:
                pass

        # Hard cap diagnostic/log file count only; newest survive.
        if "log" in folder.name.lower():
            files = sorted([p for p in folder.rglob("*") if p.is_file()], key=lambda x: x.stat().st_mtime, reverse=True)
            for p in files[max_logs:]:
                try:
                    p.unlink()
                    deleted += 1
                except OSError:
                    pass

    # Official output folders intentionally use fixed filenames. Clean accidental tmp files.
    for name in ["AWS","ECOLLECT","HERCULES","GENERAL"]:
        folder = output_root / name
        if not folder.exists(): continue
        for p in folder.glob("*.tmp*"):
            try:
                if now - p.stat().st_mtime > 86400:
                    p.unlink()
                    deleted += 1
            except OSError:
                pass
    return deleted
