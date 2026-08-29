from __future__ import annotations

from pathlib import Path
from datetime import datetime
import pandas as pd

try:
    from config import REPORTS_DIR
except Exception:
    REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

OPCIONES = ["Torneos", "Gimnasios", "Turnos", "Citas", "Materiales"]

COLUMNAS_CLAVE = [
    "Cotización",
    "Estado Cotización",
    "Canal de Cotización",
    "Forma de Pago",
    "Franquicias",
]

ALIAS_COLUMNAS = {
    "Canal que Cotizó": "Canal de Cotización",
    "Canal Cotizó": "Canal de Cotización",
    "Canal": "Canal de Cotización",
    "Franquicia": "Franquicias",
    "Sedes": "Sede",
}

ORDEN_ESTADOS = [
    "Checkout",
    "Pago Pendiente",
    "Pago Realizado",
    "Pendiente Facturación",
    "Pendiente Recaudo",
    "Recaudado",
    "(en blanco)",
]

ORDEN_CANALES = ["Módulos", "Modulos", "PAI", "Web", "(en blanco)"]
ORDEN_FORMAS = [
    "CupoYa",
    "Efectivo",
    "Puntos Plataforma",
    "T. Compensar",
    "TC",
    "TD",
    "Presencial",
    "Efectivo,T. Compensar",
    "Efectivo,TC",
    "Efectivo,TD",
    "TD,Puntos Plataforma",
    "(en blanco)",
]

COLOR_AZUL = "#005E7A"
COLOR_VERDE = "#009B7A"
COLOR_CELESTE = "#BFEAF4"
COLOR_CELESTE_SUAVE = "#EAF7FA"
COLOR_GRIS = "#F4F6F8"
COLOR_BORDE = "#C9D7DE"
COLOR_TEXTO = "#1F2937"


def _limpiar_nombre_hoja(nombre: str) -> str:
    inval = ['\\', '/', '*', '?', ':', '[', ']']
    for ch in inval:
        nombre = nombre.replace(ch, " ")
    return nombre[:31]


def _normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns={c: ALIAS_COLUMNAS.get(c, c) for c in df.columns})
    return df


def _serie_texto(df: pd.DataFrame, columna: str) -> pd.Series:
    if columna not in df.columns:
        return pd.Series(["(en blanco)"] * len(df), index=df.index)
    return (
        df[columna]
        .fillna("(en blanco)")
        .astype(str)
        .str.strip()
        .replace({"": "(en blanco)", "nan": "(en blanco)", "None": "(en blanco)"})
    )


def _orden(valor: str, orden_preferido: list[str]) -> tuple[int, str]:
    valor = str(valor)
    return (orden_preferido.index(valor) if valor in orden_preferido else len(orden_preferido), valor)


def _tabla_estado_canal(df: pd.DataFrame) -> pd.DataFrame:
    base = pd.DataFrame({
        "Estado Cotización": _serie_texto(df, "Estado Cotización"),
        "Canal de Cotización": _serie_texto(df, "Canal de Cotización"),
    })

    conteo = (
        base.groupby(["Estado Cotización", "Canal de Cotización"], dropna=False)
        .size()
        .reset_index(name="Cantidad")
    )

    filas: list[list[object]] = []
    total = 0
    estados = sorted(conteo["Estado Cotización"].unique(), key=lambda x: _orden(x, ORDEN_ESTADOS))

    for estado in estados:
        sub = conteo[conteo["Estado Cotización"] == estado].copy()
        subtotal = int(sub["Cantidad"].sum())
        total += subtotal
        filas.append([estado, subtotal])

        sub = sub.sort_values("Canal de Cotización", key=lambda s: s.map(lambda x: _orden(x, ORDEN_CANALES)))
        for _, row in sub.iterrows():
            filas.append(["   " + str(row["Canal de Cotización"]), int(row["Cantidad"])])

    filas.append(["Total general", total])
    return pd.DataFrame(filas, columns=["Etiquetas de fila", "Cuenta de Estado Cotización"])


def _tabla_estado_canal_forma(df: pd.DataFrame, estado_objetivo: str) -> pd.DataFrame:
    """Tabla de diagnóstico para un estado específico, agrupada por canal y forma de pago."""
    base = pd.DataFrame({
        "Estado Cotización": _serie_texto(df, "Estado Cotización"),
        "Canal de Cotización": _serie_texto(df, "Canal de Cotización"),
        "Forma de Pago": _serie_texto(df, "Forma de Pago"),
    })
    base = base[base["Estado Cotización"] == estado_objetivo]

    if base.empty:
        return pd.DataFrame([["Sin registros", 0]], columns=["Etiquetas de fila", "Cuenta de Estado Cotización"])

    conteo = (
        base.groupby(["Canal de Cotización", "Forma de Pago"], dropna=False)
        .size()
        .reset_index(name="Cantidad")
    )

    filas: list[list[object]] = []
    total = 0
    canales = sorted(conteo["Canal de Cotización"].unique(), key=lambda x: _orden(x, ORDEN_CANALES))

    for canal in canales:
        sub = conteo[conteo["Canal de Cotización"] == canal].copy()
        subtotal = int(sub["Cantidad"].sum())
        total += subtotal
        filas.append([canal, subtotal])

        sub = sub.sort_values("Forma de Pago", key=lambda s: s.map(lambda x: _orden(x, ORDEN_FORMAS)))
        for _, row in sub.iterrows():
            filas.append(["   " + str(row["Forma de Pago"]), int(row["Cantidad"])])

    filas.append(["Total general", total])
    return pd.DataFrame(filas, columns=["Etiquetas de fila", "Cuenta de Estado Cotización"])


def _tabla_pago_realizado(df: pd.DataFrame) -> pd.DataFrame:
    return _tabla_estado_canal_forma(df, "Pago Realizado")


def _kpis(df: pd.DataFrame) -> dict[str, int]:
    estado = _serie_texto(df, "Estado Cotización")
    return {
        "Total general": int(len(df)),
        "Pago Realizado": int((estado == "Pago Realizado").sum()),
        "Pago Pendiente": int((estado == "Pago Pendiente").sum()),
        "Checkout": int((estado == "Checkout").sum()),
        "Pendiente Recaudo": int((estado == "Pendiente Recaudo").sum()),
    }


def _set_ancho_base(worksheet, df: pd.DataFrame) -> None:
    for idx, col in enumerate(df.columns):
        serie = df[col].astype(str).head(500)
        max_len = max([len(str(col))] + [len(x) for x in serie.tolist()]) if len(df) else len(str(col))
        worksheet.set_column(idx, idx, min(max(max_len + 2, 10), 36))


def _formatos(wb):
    return {
        "titulo": wb.add_format({
            "bold": True, "font_color": "white", "bg_color": COLOR_AZUL,
            "font_size": 15, "align": "left", "valign": "vcenter"
        }),
        "subtitulo": wb.add_format({"font_color": "#55616A", "font_size": 9}),
        "kpi_label": wb.add_format({
            "bold": True, "font_color": "#52616B", "bg_color": "white", "align": "center",
            "border": 1, "border_color": "#D8E2E7", "font_size": 9
        }),
        "kpi_num": wb.add_format({
            "bold": True, "font_color": COLOR_AZUL, "bg_color": "white", "align": "center",
            "border": 1, "border_color": "#D8E2E7", "font_size": 16, "num_format": "#,##0"
        }),
        "bloque_azul": wb.add_format({
            "bold": True, "font_color": "white", "bg_color": COLOR_AZUL,
            "align": "center", "valign": "vcenter", "border": 1, "border_color": COLOR_AZUL
        }),
        "bloque_verde": wb.add_format({
            "bold": True, "font_color": "white", "bg_color": COLOR_VERDE,
            "align": "center", "valign": "vcenter", "border": 1, "border_color": COLOR_VERDE
        }),
        "header": wb.add_format({
            "bold": True, "bg_color": COLOR_CELESTE, "font_color": "black",
            "border": 1, "border_color": COLOR_BORDE, "align": "center", "valign": "vcenter"
        }),
        "parent": wb.add_format({
            "bold": True, "border": 1, "border_color": COLOR_BORDE, "font_color": "black"
        }),
        "detail": wb.add_format({
            "border": 1, "border_color": COLOR_BORDE, "font_color": COLOR_TEXTO
        }),
        "total": wb.add_format({
            "bold": True, "bg_color": COLOR_CELESTE, "border": 1, "border_color": COLOR_BORDE
        }),
        "num": wb.add_format({
            "border": 1, "border_color": COLOR_BORDE, "num_format": "#,##0", "align": "right"
        }),
        "num_total": wb.add_format({
            "bold": True, "bg_color": COLOR_CELESTE, "border": 1,
            "border_color": COLOR_BORDE, "num_format": "#,##0", "align": "right"
        }),
        "nota": wb.add_format({
            "italic": True, "font_color": "#6B7280", "font_size": 9,
            "bg_color": COLOR_GRIS, "border": 1, "border_color": "#E5E7EB"
        }),
        "header_base": wb.add_format({
            "bold": True, "font_color": "white", "bg_color": COLOR_AZUL,
            "border": 1, "border_color": COLOR_AZUL
        }),
    }


def _escribir_bloque(writer, hoja: str, titulo: str, tabla: pd.DataFrame, fila: int, col: int, color: str = "azul") -> int:
    wb = writer.book
    ws = writer.sheets[hoja]
    fmt = _formatos(wb)
    fmt_titulo = fmt["bloque_verde"] if color == "verde" else fmt["bloque_azul"]

    ws.merge_range(fila, col, fila, col + 1, titulo, fmt_titulo)
    ws.write(fila + 1, col, tabla.columns[0], fmt["header"])
    ws.write(fila + 1, col + 1, tabla.columns[1], fmt["header"])

    for i, row in tabla.iterrows():
        r = fila + 2 + i
        etiqueta = row.iloc[0]
        cantidad = int(row.iloc[1])
        es_total = etiqueta == "Total general"
        es_detalle = isinstance(etiqueta, str) and etiqueta.startswith("   ")

        if es_total:
            ws.write(r, col, etiqueta, fmt["total"])
            ws.write_number(r, col + 1, cantidad, fmt["num_total"])
        elif es_detalle:
            ws.write(r, col, etiqueta, fmt["detail"])
            ws.write_number(r, col + 1, cantidad, fmt["num"])
        else:
            ws.write(r, col, etiqueta, fmt["parent"])
            ws.write_number(r, col + 1, cantidad, fmt["num"])

    ws.set_column(col, col, 30)
    ws.set_column(col + 1, col + 1, 18)
    return fila + len(tabla) + 4


def _diagnostico(disponibles: dict[str, pd.DataFrame]) -> pd.DataFrame:
    filas = []
    for opcion, df in disponibles.items():
        faltantes = [c for c in COLUMNAS_CLAVE if c not in df.columns]
        estado = _serie_texto(df, "Estado Cotización")
        filas.append({
            "Opción": opcion,
            "Filas base": len(df),
            "Pago Realizado": int((estado == "Pago Realizado").sum()),
            "Checkout": int((estado == "Checkout").sum()),
            "Pendiente Recaudo": int((estado == "Pendiente Recaudo").sum()),
            "Columnas faltantes": ", ".join(faltantes) if faltantes else "OK",
            "Columnas descargadas": ", ".join(map(str, df.columns)),
        })
    out = pd.DataFrame(filas)
    if not out.empty:
        out.loc[len(out)] = [
            "Total general",
            int(out["Filas base"].sum()),
            int(out["Pago Realizado"].sum()),
            int(out["Checkout"].sum()),
            int(out["Pendiente Recaudo"].sum()),
            "",
            "",
        ]
    return out


def _crear_consolidado(writer, ruta_excel: Path, consolidado: pd.DataFrame) -> None:
    wb = writer.book
    fmt = _formatos(wb)
    hoja = "Consolidado"
    pd.DataFrame().to_excel(writer, sheet_name=hoja, index=False)
    ws = writer.sheets[hoja]
    ws.hide_gridlines(2)
    ws.freeze_panes(8, 0)

    ws.set_row(0, 24)
    ws.merge_range(0, 0, 0, 4, "Monitoreo Hércules - Consolidado Gerencial", fmt["titulo"])
    ws.write(1, 0, f"Fuente: {ruta_excel.name}   |   Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", fmt["subtitulo"])

    # Columnas compactas para evitar espacios raros.
    ws.set_column(0, 0, 30)
    ws.set_column(1, 1, 18)
    ws.set_column(2, 2, 3)
    ws.set_column(3, 3, 30)
    ws.set_column(4, 4, 18)
    ws.set_column(5, 5, 3)
    ws.set_column(6, 6, 30)
    ws.set_column(7, 7, 18)

    # KPIs compactos arriba.
    kpis = _kpis(consolidado)
    col = 0
    for label, valor in kpis.items():
        ws.merge_range(3, col, 3, col + 1, label, fmt["kpi_label"])
        ws.merge_range(4, col, 4, col + 1, valor, fmt["kpi_num"])
        col += 2
        if col == 4:
            col += 1  # separador visual entre KPIs

    # Tablas principales: sin espacios grandes.
    fin_izq = _escribir_bloque(writer, hoja, "Estado Cotización por Canal", _tabla_estado_canal(consolidado), 7, 0, "azul")
    fin_der = _escribir_bloque(writer, hoja, "Pago Realizado por Canal y Forma de Pago", _tabla_pago_realizado(consolidado), 7, 3, "verde")

    # Diagnóstico abajo: checkout y pendiente recaudo por forma de pago.
    fila_extra = max(fin_izq, fin_der) + 1
    ws.merge_range(fila_extra, 0, fila_extra, 4, "Diagnóstico de posibles fallas por forma de pago", fmt["nota"])
    fila_extra += 2
    fin_checkout = _escribir_bloque(writer, hoja, "Checkout por Canal y Forma de Pago", _tabla_estado_canal_forma(consolidado, "Checkout"), fila_extra, 0, "azul")
    fin_recaudo = _escribir_bloque(writer, hoja, "Pendiente Recaudo por Canal y Forma de Pago", _tabla_estado_canal_forma(consolidado, "Pendiente Recaudo"), fila_extra, 3, "verde")

    # Deja la hoja limpia y con zoom cómodo.
    ws.set_zoom(90)
    ws.set_row(1, 18)
    for r in range(2, max(fin_checkout, fin_recaudo) + 2):
        ws.set_row(r, 18)


def procesar_excel(ruta_excel: str | Path, salida_nombre: str = "resumen_hercules_diario.xlsx") -> Path:
    ruta_excel = Path(ruta_excel)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    hojas = pd.read_excel(ruta_excel, sheet_name=None)
    disponibles: dict[str, pd.DataFrame] = {}
    for nombre, df in hojas.items():
        if nombre in OPCIONES:
            disponibles[nombre] = _normalizar_df(df)

    if not disponibles:
        raise ValueError("No encontré hojas de Hércules: Torneos, Gimnasios, Turnos, Citas o Materiales.")

    salida = REPORTS_DIR / salida_nombre
    if salida.exists():
        try:
            salida.unlink()
        except Exception:
            pass
    consolidado = pd.concat([df.assign(Opción=opcion) for opcion, df in disponibles.items()], ignore_index=True)

    with pd.ExcelWriter(salida, engine="xlsxwriter") as writer:
        wb = writer.book
        fmt = _formatos(wb)

        # 1. Hoja gerencial.
        _crear_consolidado(writer, ruta_excel, consolidado)

        # 2. Diagnóstico para saber si alguna opción no descargó columnas.
        diag = _diagnostico(disponibles)
        diag.to_excel(writer, sheet_name="Diagnóstico", index=False)
        ws_diag = writer.sheets["Diagnóstico"]
        ws_diag.hide_gridlines(2)
        for c, col_name in enumerate(diag.columns):
            ws_diag.write(0, c, col_name, fmt["header_base"])
        ws_diag.set_column(0, 0, 18)
        ws_diag.set_column(1, 4, 16)
        ws_diag.set_column(5, 6, 60)
        ws_diag.freeze_panes(1, 0)
        try:
            ws_diag.autofilter(0, 0, len(diag), max(len(diag.columns) - 1, 0))
        except Exception:
            pass

        # 3. Resumen separado por opción, en una sola hoja.
        hoja = "Resumen_5_opciones"
        pd.DataFrame().to_excel(writer, sheet_name=hoja, index=False)
        ws5 = writer.sheets[hoja]
        ws5.hide_gridlines(2)
        ws5.merge_range(0, 0, 0, 4, "Resumen separado por opción", fmt["titulo"])
        ws5.set_column(0, 0, 30)
        ws5.set_column(1, 1, 18)
        ws5.set_column(2, 2, 3)
        ws5.set_column(3, 3, 30)
        ws5.set_column(4, 4, 18)
        fila = 3
        for opcion in OPCIONES:
            if opcion not in disponibles:
                continue
            df = disponibles[opcion]
            fin_izq = _escribir_bloque(writer, hoja, f"{opcion} - Estado Cotización por Canal", _tabla_estado_canal(df), fila, 0, "azul")
            fin_der = _escribir_bloque(writer, hoja, f"{opcion} - Pago Realizado Canal/Forma", _tabla_pago_realizado(df), fila, 3, "verde")
            fila = max(fin_izq, fin_der) + 1

        # 4. Hojas BASE tal cual salen de Hércules por cada opción.
        for opcion in OPCIONES:
            if opcion not in disponibles:
                continue
            df = disponibles[opcion]
            hoja_base = _limpiar_nombre_hoja(f"Base_{opcion}")
            df.to_excel(writer, sheet_name=hoja_base, index=False)
            ws_base = writer.sheets[hoja_base]
            ws_base.hide_gridlines(2)
            for c, col_name in enumerate(df.columns):
                ws_base.write(0, c, col_name, fmt["header_base"])
            _set_ancho_base(ws_base, df)
            ws_base.freeze_panes(1, 0)
            try:
                ws_base.autofilter(0, 0, len(df), max(len(df.columns) - 1, 0))
            except Exception:
                pass

        # 5. Base consolidada con columna Opción para revisar todo junto.
        consolidado.to_excel(writer, sheet_name="Base_Consolidada", index=False)
        ws_bc = writer.sheets["Base_Consolidada"]
        ws_bc.hide_gridlines(2)
        for c, col_name in enumerate(consolidado.columns):
            ws_bc.write(0, c, col_name, fmt["header_base"])
        _set_ancho_base(ws_bc, consolidado)
        ws_bc.freeze_panes(1, 0)
        try:
            ws_bc.autofilter(0, 0, len(consolidado), max(len(consolidado.columns) - 1, 0))
        except Exception:
            pass

    print(f"Resumen Excel generado: {salida}")
    return salida


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python procesar_reporte.py <ruta_excel_hercules>")
    procesar_excel(sys.argv[1])
