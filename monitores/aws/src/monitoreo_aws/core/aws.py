from __future__ import annotations

import time
import shutil
import subprocess
from typing import Any

import boto3



def _probar_profile(profile: str, region: str) -> tuple[bool, str]:
    try:
        session = boto3.Session(profile_name=profile, region_name=region)
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        account = str(identity.get("Account", ""))
        arn = str(identity.get("Arn", ""))
        return True, f"Account={account} | Arn={arn}"
    except Exception as exc:
        return False, str(exc)


def _login_sso(profile: str) -> None:
    aws_cli = shutil.which("aws")
    if not aws_cli:
        raise RuntimeError("No encuentro AWS CLI en PATH.")
    print("")
    print("=" * 68)
    print(f"AWS SSO: iniciando sesión para profile '{profile}'")
    print("Se abrirá el navegador porque la sesión está vencida.")
    print("=" * 68)
    print("")
    result = subprocess.run([aws_cli, "sso", "login", "--profile", profile], check=False)
    if result.returncode != 0:
        raise RuntimeError(f"AWS SSO login falló para '{profile}'. Código={result.returncode}")


def asegurar_sso_profiles(profiles: dict, region: str) -> None:
    requeridos = []
    for key in ("interopprod", "cscprod", "corporativoprod"):
        profile = str(profiles.get(key, "")).strip()
        if profile and profile not in requeridos:
            requeridos.append(profile)
    if not requeridos:
        raise RuntimeError("No hay profiles AWS configurados.")
    print("")
    print("=" * 68)
    print("VERIFICACION AWS SSO")
    print("Profiles requeridos: " + ", ".join(requeridos))
    print("=" * 68)
    for profile in requeridos:
        ok, detalle = _probar_profile(profile, region)
        if ok:
            print(f"[AWS SSO OK] {profile}: {detalle}")
            continue
        print(f"[AWS SSO VENCIDO/INVALIDO] {profile}")
        print(f"  Motivo: {detalle}")
        _login_sso(profile)
        ok2, detalle2 = _probar_profile(profile, region)
        if not ok2:
            raise RuntimeError(f"El profile '{profile}' sigue sin conexión después del login: {detalle2}")
        print(f"[AWS SSO RECONECTADO] {profile}: {detalle2}")
    print("")
    print("AWS SSO: todos los profiles requeridos están conectados.")
    print("=" * 68)
    print("")

def crear_cliente(profile: str, region: str):
    return boto3.Session(profile_name=profile, region_name=region).client("logs")


def ejecutar_query(client, log_group: str, query: str, inicio, fin, limit: int = 10000) -> list[dict[str, Any]]:
    response = client.start_query(
        logGroupName=log_group,
        startTime=int(inicio.timestamp()),
        endTime=int(fin.timestamp()),
        queryString=query,
        limit=limit,
    )
    query_id = response["queryId"]
    while True:
        result = client.get_query_results(queryId=query_id)
        status = result["status"]
        if status == "Complete":
            return [
                {cell.get("field", ""): cell.get("value", "") for cell in row}
                for row in result.get("results", [])
            ]
        if status in {"Failed", "Cancelled", "Timeout", "Unknown"}:
            raise RuntimeError(f"Consulta fallida en {log_group}: {status}")
        time.sleep(1)


def contar(client, log_group: str, query: str, inicio, fin) -> int:
    rows = ejecutar_query(client, log_group, query, inicio, fin)
    if not rows:
        return 0
    for key in ("count", "total", "cantidad"):
        if key in rows[0]:
            try:
                return int(float(rows[0][key]))
            except (TypeError, ValueError):
                pass
    return len(rows)
