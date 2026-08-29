# SPRINT_13_8_AUTO_GENERAL_COORDINATED_OK
from __future__ import annotations
import argparse
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.orchestrator import run_monitor, finalize


def _hay_procesos_previos():
    if os.name != "nt":
        return False

    ps = r"""
$procs = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^python(w)?\.exe$' -and $_.CommandLine -and (
        $_.CommandLine -like '*ejecutar_paralelo.py*' -or
        $_.CommandLine -like '*pasarela_worker.py*' -or
        $_.CommandLine -like '*payu_worker.py*' -or
        $_.CommandLine -like '*monitores*aws*main.py*'
    )
}
if ($procs) { exit 10 } else { exit 0 }
"""

    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return r.returncode == 10


def _esperar_previos(timeout_seg=1800):
    inicio = time.time()

    while _hay_procesos_previos():
        if time.time() - inicio >= timeout_seg:
            print(
                "GENERAL: se agotó el tiempo esperando Pasarelas/AWS. "
                "Se genera con la información disponible.",
                flush=True,
            )
            return False

        print(
            "GENERAL: esperando que terminen Pasarelas/AWS...",
            flush=True,
        )
        time.sleep(10)

    return True


def _publicar_general(selected=None, fresh_after=None):
    deleted, dash, excel = finalize(
        selected=selected,
        run_started_at=fresh_after,
    )
    print("")
    print("=" * 70)
    print("DASHBOARD GENERAL GENERADO")
    print(f"Dashboard: {dash}")
    print(f"Excel mensual: {excel}")
    print(f"Archivos limpiados: {deleted}")
    print("=" * 70)
    return dash


def main():
    p = argparse.ArgumentParser(description="Monitoreo Compensar unificado")
    p.add_argument("--monitor", choices=["todos","pasarelas","aws","hercules"], default="todos")
    p.add_argument("--modo", choices=["actual","acumulado-hoy","dia-anterior","fecha"], default="actual")
    p.add_argument("--fecha")
    p.add_argument("--corte", choices=["09","13","17"], default="09")
    p.add_argument("--hora-inicio", default="00:00")
    p.add_argument("--hora-fin", default="23:59")
    p.add_argument("--no-finalize", action="store_true")
    p.add_argument("--finalize-only", action="store_true")
    p.add_argument("--fresh-after", default="", help="ISO datetime mínimo aceptado para fuentes del General")
    p.add_argument("--selected", default="PASARELAS,AWS,HERCULES", help="Monitores esperados por el General")
    a = p.parse_args()

    if a.finalize_only:
        fresh_after = None
        if a.fresh_after:
            from datetime import datetime
            fresh_after = datetime.fromisoformat(a.fresh_after)

        selected = [
            x.strip().upper()
            for x in str(a.selected).split(",")
            if x.strip()
        ]

        # Si el coordinador automático aporta fresh-after, YA esperó los
        # estados del mismo corte. No volvemos a esperar procesos.
        if fresh_after is None:
            _esperar_previos()

        _publicar_general(
            selected=selected,
            fresh_after=fresh_after,
        )
        return 0

    mons = ["PASARELAS","AWS","HERCULES"] if a.monitor == "todos" else [a.monitor.upper()]
    errores = []

    with ThreadPoolExecutor(max_workers=len(mons)) as ex:
        future_map = {
            ex.submit(
                run_monitor, m, a.modo, a.corte, a.fecha,
                a.hora_inicio, a.hora_fin
            ): m
            for m in mons
        }

        for future in as_completed(future_map):
            monitor = future_map[future]
            try:
                rc = future.result()
            except Exception as exc:
                rc = 1
                print(
                    f"{monitor}: ERROR NO CONTROLADO: "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )

            if rc != 0:
                errores.append((monitor, rc))

    if not a.no_finalize:
        if a.monitor == "hercules":
            _esperar_previos()

        try:
            _publicar_general()
        except Exception as exc:
            print(
                f"ERROR GENERANDO DASHBOARD GENERAL: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
            errores.append(("GENERAL", 1))
    else:
        print(
            "Monitor finalizado. GENERAL queda pendiente hasta HERCULES.",
            flush=True,
        )

    if errores:
        print("ERRORES DEL CORTE:")
        for monitor, rc in errores:
            print(f"  - {monitor}: código {rc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

