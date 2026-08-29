# SPRINT_13_8_ORCHESTRATOR_FRESHNESS_OK
from __future__ import annotations
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from .cleanup import cleanup_tree
from .history import append_event
from .dashboard import generate_dashboard
from .excel_history import export_monthly_excel
from .branding import apply_branding

PROJECT = Path(__file__).resolve().parents[1]


def load_config():
    return json.loads((PROJECT / "config" / "app.json").read_text(encoding="utf-8"))


def output_root():
    cfg = load_config()
    root = Path(os.path.expandvars(cfg["output_root"])).expanduser()
    for d in ["AWS", "ECOLLECT", "HERCULES", "GENERAL"]:
        (root / d).mkdir(parents=True, exist_ok=True)
    return root


def _run(name, cmd, cwd, modo, corte, target_date=None, live_cb=None):
    root = output_root()
    start = time.time()

    logs_dir = root / "GENERAL" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"{name}_{stamp}_{modo}_corte_{corte}.log"

    if live_cb:
        live_cb(name, "EJECUTANDO", "Iniciando...")

    env = {**os.environ, "PYTHONUNBUFFERED": "1"}

    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        log.write(f"MONITOR={name}\n")
        log.write(f"INICIO={datetime.now().isoformat()}\n")
        log.write(f"MODO={modo}\n")
        log.write(f"CORTE={corte}\n")
        log.write(f"CWD={cwd}\n")
        log.write("COMANDO=" + " ".join(str(x) for x in cmd) + "\n")
        log.write("=" * 90 + "\n")
        log.flush()

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            lines = []
            assert proc.stdout is not None

            for line in proc.stdout:
                clean = line.rstrip("\r\n")
                lines.append(clean)
                print(clean, flush=True)
                log.write(clean + "\n")
                log.flush()
                if live_cb:
                    live_cb(name, "EJECUTANDO", clean)

            rc = proc.wait()

        except Exception as exc:
            rc = 1
            lines = [f"ERROR ORQUESTADOR: {type(exc).__name__}: {exc}"]
            log.write(lines[-1] + "\n")
            log.flush()

        duration = round(time.time() - start, 1)
        estado = "OK" if rc == 0 else "ERROR"
        detail = (lines[-1] if lines else f"Codigo {rc}")[:250]

        log.write("=" * 90 + "\n")
        log.write(f"FIN={datetime.now().isoformat()}\n")
        log.write(f"RC={rc}\n")
        log.write(f"ESTADO={estado}\n")
        log.write(f"DURACION_SEG={duration}\n")

    fecha = target_date or datetime.now().strftime("%Y-%m-%d")

    append_event(
        root,
        {
            "fecha": fecha,
            "corte": corte,
            "monitor": name,
            "modo": modo,
            "estado": estado,
            "duracion_seg": duration,
            "detalle": detail,
            "ruta_reporte": str(log_path),
        },
        accumulate_month=(modo == "dia-anterior"),
    )

    print(f"[LOG {name}] {log_path}", flush=True)

    if live_cb:
        live_cb(name, estado, detail)

    return rc

def _ensure_session(name, live_cb=None):
    """
    Crea automáticamente las sesiones necesarias cuando no existen.

    El usuario normal no necesita abrir PowerShell ni ejecutar
    guardar_sesion.py manualmente.
    """
    name = name.upper()

    py = sys.executable

    # --------------------------------------------------------
    # HÉRCULES
    # --------------------------------------------------------
    if name == "HERCULES":

        her_root = PROJECT / "monitores" / "hercules"
        sesion = her_root / "storage" / "hercules_sesion.json"

        if sesion.exists() and sesion.stat().st_size > 100:
            return True

        if live_cb:
            live_cb(
                "HERCULES",
                "PREPARANDO",
                "Primera ejecución: creando sesión automáticamente..."
            )

        cmd = [
            py,
            str(her_root / "src" / "guardar_sesion.py")
        ]

        env = {
            **os.environ,
            "PYTHONPATH": str(her_root),
        }

        r = subprocess.run(
            cmd,
            cwd=str(her_root),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        if r.returncode != 0:
            raise RuntimeError(
                "No fue posible preparar la sesión de Hércules. "
                "Verifica el usuario y la clave guardados."
            )

        if not sesion.exists():
            raise RuntimeError(
                "Hércules terminó la preparación pero no creó "
                "el archivo de sesión."
            )

        if live_cb:
            live_cb(
                "HERCULES",
                "PREPARANDO",
                "Sesión creada correctamente ✓"
            )

        return True

    # --------------------------------------------------------
    # PASARELAS / ECOLLECT
    # --------------------------------------------------------
    if name == "PASARELAS":

        pas_root = PROJECT / "monitores" / "pasarelas"

        # Buscar alguno de los nombres usados por las versiones
        # del bot para la sesión persistente.
        candidatos = [
            pas_root / "storage" / "ecollect_sesion.json",
            pas_root / "storage" / "ecollect_state.json",
            pas_root / "storage" / "ecollect_storage_state.json",
            pas_root / "storage_state_ecollect.json",
        ]

        if any(
            p.exists() and p.stat().st_size > 100
            for p in candidatos
        ):
            return True

        if live_cb:
            live_cb(
                "PASARELAS",
                "PREPARANDO",
                "Primera ejecución: preparando sesión eCollect automáticamente..."
            )

        cmd = [
            py,
            str(pas_root / "src" / "main.py"),
            "--modo",
            "guardar-sesion-ecollect",
        ]

        # ESTE era el error:
        # main.py importa "from src import config", por lo cual
        # pasarelas debe estar en PYTHONPATH y debe ser el cwd.
        env = {
            **os.environ,
            "PYTHONPATH": str(pas_root),
        }

        r = subprocess.run(
            cmd,
            cwd=str(pas_root),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        if r.returncode != 0:
            raise RuntimeError(
                "No fue posible preparar automáticamente eCollect. "
                "Verifica el usuario y la clave guardados."
            )

        if live_cb:
            live_cb(
                "PASARELAS",
                "PREPARANDO",
                "Sesión eCollect preparada correctamente ✓"
            )

        return True

    return True



def run_monitor(name, modo="actual", corte="09", fecha=None, hora_inicio="00:00", hora_fin="23:59", live_cb=None):
    name = name.upper()
    py = sys.executable
    _ensure_session(name, live_cb)
    if name == "PASARELAS":
        cmd = [py, str(PROJECT / "monitores" / "pasarelas" / "src" / "ejecutar_paralelo.py"), "--modo", modo, "--corte", corte]
        if fecha:
            cmd += ["--fecha", fecha]
        if modo in ("dia-anterior", "fecha"):
            cmd += ["--hora-inicio", hora_inicio, "--hora-fin", hora_fin]
        target = fecha or ((datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d") if modo == "dia-anterior" else None)
        return _run(name, cmd, PROJECT / "monitores" / "pasarelas", modo, corte, target, live_cb)
    if name == "AWS":
        target = fecha
        if modo == "dia-anterior":
            target = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if modo == "acumulado-hoy":
            aws_corte = "dia"
        elif modo in ("dia-anterior", "fecha"):
            aws_corte = "rango"
        else:
            aws_corte = {"09": "1", "13": "2", "17": "3"}[corte]
        cmd = [py, str(PROJECT / "monitores" / "aws" / "main.py"), "--corte", aws_corte, "--no-abrir"]
        if target:
            cmd += ["--fecha", target]
        if modo in ("dia-anterior", "fecha"):
            cmd += ["--hora-inicio", hora_inicio, "--hora-fin", hora_fin]
        return _run(name, cmd, PROJECT / "monitores" / "aws", modo, corte, target, live_cb)
    if name == "HERCULES":
        her_mode = "actual" if modo == "acumulado-hoy" else modo
        cmd = [py, str(PROJECT / "monitores" / "hercules" / "src" / "run_mode.py"), "--modo", her_mode]
        if fecha:
            cmd += ["--fecha", fecha]
        if modo in ("dia-anterior", "fecha"):
            cmd += ["--hora-inicio", hora_inicio, "--hora-fin", hora_fin]
        target = fecha or ((datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d") if modo == "dia-anterior" else None)
        return _run(name, cmd, PROJECT / "monitores" / "hercules", modo, corte, target, live_cb)
    raise ValueError(name)


def finalize(selected=None, run_started_at=None):
    """Consolida únicamente después del cierre del ciclo de monitoreo.

    `run_started_at` se usa para impedir que el Dashboard General reutilice
    silenciosamente archivos de una ejecución anterior.
    """
    cfg = load_config()
    root = output_root()

    deleted = cleanup_tree(
        PROJECT,
        root,
        cfg["retention"]["logs_days"],
        cfg["retention"]["downloads_days"],
        cfg["retention"]["max_log_files_per_folder"],
    )

    dash = generate_dashboard(
        root,
        selected=selected,
        fresh_after=run_started_at,
    )

    excel = export_monthly_excel(root)
    apply_branding(root)
    return deleted, dash, excel
