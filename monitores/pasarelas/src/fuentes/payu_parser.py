import pandas as pd
from src.utils.limpieza import numero, limpiar_texto


def leer_payu(path):
    ultimo_error = None
    for enc in ["utf-8-sig", "utf-8", "latin1", "cp1252"]:
        for sep in [",", ";", "\t"]:
            try:
                df = pd.read_csv(path, sep=sep, encoding=enc, dtype=str, engine="python", on_bad_lines="skip")
                if df.shape[1] > 5:
                    return df
            except Exception as exc:
                ultimo_error = exc
    raise ValueError(f"No pude leer el archivo PayU: {ultimo_error}")


def _mapa_columnas(df):
    return {limpiar_texto(c): c for c in df.columns}


def _buscar_columna(cols, *nombres):
    for n in nombres:
        key = limpiar_texto(n)
        if key in cols:
            return cols[key]
    return None


def _es_pse(valor):
    """
    Regla operativa 41621 PayU:

    - Cualquier Payment method que contenga PSE
      se clasifica como PSE (PAYU).

    Ejemplos:
      PSE
      PSE_AVANZA
      PSE AVANZA

    - Todo lo demás se clasifica como
      TARJ. CREDITO (PAYU).
    """
    t = limpiar_texto(valor)

    return "PSE" in t



def _es_aprobado(valor):
    return limpiar_texto(valor) in {"APPROVED", "APROBADO", "APROBADA", "OK", "SUCCESS", "SUCCESSFUL"}


def resumir_payu(path, vertical="41621 RED TIENDA"):
    df = leer_payu(path)
    cols = _mapa_columnas(df)

    estado_col = _buscar_columna(cols, "ESTADO", "STATUS")
    medio_col = _buscar_columna(cols, "MEDIO DE PAGO", "PAYMENT METHOD")
    valor_col = _buscar_columna(
        cols,
        "VALOR TRANSACCION", "VALOR TRANSACCIÃ“N",
        "TRANSACTION VALUE", "PROCESSING VALUE", "CHARGED VALUE"
    )
    fecha_col = _buscar_columna(
        cols,
        "FECHA DE CREACION", "FECHA DE CREACIÃ“N",
        "FECHA OPERACION", "FECHA OPERACIÃ“N",
        "FECHA ULTIMA ACTUALIZACION", "FECHA ÃšLTIMA ACTUALIZACIÃ“N",
        "OPERATION DATE", "CREATION DATE", "UPDATE DATE"
    )

    faltantes = []
    if not estado_col: faltantes.append("Status/Estado")
    if not medio_col: faltantes.append("Payment method/Medio de pago")
    if not valor_col: faltantes.append("Transaction value/Valor")
    if faltantes:
        raise ValueError(
            "No encontrÃ© columnas PayU requeridas: " + ", ".join(faltantes)
            + f". Columnas recibidas: {list(df.columns)}"
        )

    d = df.copy()
    d["_estado_ok"] = d[estado_col].map(_es_aprobado)
    d["_es_pse"] = d[medio_col].map(_es_pse)
    d["_valor"] = d[valor_col].map(numero)
    d["_fecha"] = d[fecha_col].fillna("").astype(str) if fecha_col else ""

    ok = d[d["_estado_ok"]].copy()
    pse_ok = ok[ok["_es_pse"]]
    tarjeta_ok = ok[~ok["_es_pse"]]
    pse_total = d[d["_es_pse"]]
    tarjeta_total = d[~d["_es_pse"]]

    resultados = []
    for medio, etiqueta, sub_ok, sub_total in [
        ("PSE", "PSE (PAYU)", pse_ok, pse_total),
        ("TARJETA_CREDITO", "TARJ. CREDITO (PAYU)", tarjeta_ok, tarjeta_total),
    ]:
        resultados.append({
            "vertical": vertical,
            "codigo": "41621",
            "origen": "PAYU",
            "tipo_reporte": "PAYU",
            "medio_pago": medio,
            "medio_salida": etiqueta,
            "cantidad_ok": int(len(sub_ok)),
            "valor_ok": float(sub_ok["_valor"].sum()),
            "ultima_ok": str(sub_ok["_fecha"].max()) if not sub_ok.empty and fecha_col else "Sin aprobadas en el archivo actual",
            "cantidad_total": int(len(sub_total)),
            "cantidad_fallida": int(len(sub_total) - len(sub_ok)),
            "conteo_expired": 0,
            "conteo_rechazada": 0,
            "conteo_fallida_tecnica": 0,
            "conteo_pendiente": 0,
            "conteo_otra": 0,
        })

    print(f"PayU 41621 clasificado: PSE={len(pse_ok)} | TARJETA={len(tarjeta_ok)}")
    return pd.DataFrame(resultados)
