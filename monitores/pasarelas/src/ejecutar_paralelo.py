# HOTFIX_13_5_6_41605_JAVA_LAST_41610_HEADLESS_OK
from __future__ import annotations
import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import config
from src.main import procesar_archivos, cargar_verticales, rango_hoy


def _fecha_range(fecha, corte, modo, hora_inicio="00:00", hora_fin="23:59"):
    if modo == "acumulado-hoy":
        now = datetime.now()
        return now.strftime("%d/%m/%Y 00:00"), now.strftime("%d/%m/%Y %H:%M")
    if modo == "dia-anterior":
        d = datetime.now() - timedelta(days=1)
        return d.strftime(f"%d/%m/%Y {hora_inicio}"), d.strftime(f"%d/%m/%Y {hora_fin}")
    if modo == "fecha":
        if not fecha:
            raise SystemExit("--fecha es obligatorio en modo fecha")
        d = datetime.strptime(fecha, "%Y-%m-%d")
        return d.strftime(f"%d/%m/%Y {hora_inicio}"), d.strftime(f"%d/%m/%Y {hora_fin}")
    return rango_hoy(corte)


def _copy_state(name):
    src = config.STORAGE / "ecollect_session.json"
    dst = config.STORAGE / f"ecollect_session_{name}.json"
    if src.exists():
        shutil.copy2(src, dst)
    return str(dst)


def _worker_cmd(items, fi, ff, worker_name, visible):
    script = ROOT / "src" / "pasarela_worker.py"
    item_text = ",".join(f"{c}:{t}" for c, t in items)
    env = os.environ.copy()
    env["HEADLESS"] = "false" if visible else "true"
    env["ECOLLECT_STATE_PATH"] = _copy_state(worker_name)
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONUNBUFFERED"] = "1"
    cmd = [
        sys.executable, str(script),
        "--items", item_text,
        "--fecha-inicio", fi,
        "--fecha-fin", ff,
        "--worker", worker_name,
    ]
    return cmd, env



def ordenar_ecollect_para_ejecucion(all_items):
    """Mantiene el orden original, excepto 41605 JAVA que siempre va de último."""
    normales = []
    ultimo_41605_java = []

    for codigo, tipo in all_items:
        codigo = str(codigo)
        tipo = str(tipo).upper()
        item = (codigo, tipo)

        if item == ("41605", "JAVA"):
            ultimo_41605_java.append(item)
        else:
            normales.append(item)

    return normales + ultimo_41605_java


def ejecutar_ecollect_secuencial(all_items, fi, ff):
    failed = []
    print("")
    print("=" * 68)
    print("ECOLLECT - MODO SECUENCIAL")
    print(f"Total consultas: {len(all_items)}")
    print("Cada comercio termina antes de iniciar el siguiente.")
    print("=" * 68)

    for i, (codigo, tipo) in enumerate(all_items, 1):
        name = f"{codigo}_{tipo}"
        # Solo 41605 JAVA puede abrir navegador visible.
        # 41610 RED y todos los demás siempre se ejecutan headless.
        visible = (str(codigo), str(tipo).upper()) == ("41605", "JAVA")

        print("")
        print(f"[ECOLLECT {i}/{len(all_items)}] {codigo} {tipo}")
        print(f"Navegador visible={visible}")

        cmd, env = _worker_cmd([(codigo, tipo)], fi, ff, name, visible)
        proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env)
        worker_timeout_s = int(os.getenv("ECOLLECT_WORKER_TIMEOUT_SEGUNDOS", "720"))

        try:
            rc = proc.wait(timeout=worker_timeout_s)

        except subprocess.TimeoutExpired:
            print(
                f"TIMEOUT: {name} supero {worker_timeout_s} segundos. "
                "Se cerrara el worker y se continuara con el siguiente."
            )

            try:
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                )
            except Exception as exc:
                print(f"ADVERTENCIA cerrando {name}: {exc}")

            failed.append(f"{name}_TIMEOUT")
            continue

        print(f"[ECOLLECT {i}/{len(all_items)}] finalizado código={rc}")

        if rc != 0:
            failed.append(name)
            print(f"ADVERTENCIA: {name} falló. Se continúa con la siguiente consulta.")

    return failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", choices=["actual","acumulado-hoy","dia-anterior","fecha"], default="actual")
    ap.add_argument("--fecha")
    ap.add_argument("--corte", choices=["09","13","17"], default="09")
    ap.add_argument("--hora-inicio", default="00:00")
    ap.add_argument("--hora-fin", default="23:59")
    ap.add_argument(
        "--no-publicar",
        action="store_true",
        help="Genera resultados locales pero no copia archivos a SharePoint/OneDrive.",
    )
    args = ap.parse_args()

    for p in config.DESCARGAS.glob("*"):
        if p.is_file():
            try:
                p.unlink()
            except OSError:
                pass

    fi, ff = _fecha_range(
        args.fecha, args.corte, args.modo,
        args.hora_inicio, args.hora_fin
    )

    verticales = cargar_verticales()
    eco_items = (
        verticales[verticales.origen.eq("ECOLLECT")]
        [["codigo","tipo_reporte"]]
        .drop_duplicates()
    )
    all_items = [
        (str(r.codigo), str(r.tipo_reporte).upper())
        for r in eco_items.itertuples(index=False)
    ]

    # PayU sí puede trabajar simultáneamente.
    payu = subprocess.Popen(
        [
            sys.executable,
            str(ROOT / "src" / "payu_worker.py"),
            "--fecha-inicio", fi,
            "--fecha-fin", ff,
        ],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONUNBUFFERED": "1"},
    )

    print(f"PAYU iniciado en paralelo. PID={payu.pid}")

    # eCollect NO se paraleliza por el estado de comercio compartido.
    # 41605 JAVA se deja SIEMPRE de último para no frenar el resto.
    all_items = ordenar_ecollect_para_ejecucion(all_items)

    print("")
    print("Orden eCollect preparado.")
    print("41605 JAVA se ejecutará de último.")
    print("41610 RED se ejecutará oculto (headless).")

    failed = ejecutar_ecollect_secuencial(all_items, fi, ff)

    payu_rc = payu.wait()
    print(f"PAYU finalizado código={payu_rc}")
    if payu_rc != 0:
        failed.append("PAYU")

    # Consolidar únicamente cuando TODO terminó.
    df, html, excel = procesar_archivos(
        corte=args.corte,
        publicar=not args.no_publicar,
    )

    print("")
    print(f"Consolidado Pasarelas: {html}")
    print(f"Excel: {excel}")

    if failed:
        print("ADVERTENCIA - procesos con error:")
        for x in failed:
            print(f"  - {x}")


if __name__ == "__main__":
    main()
