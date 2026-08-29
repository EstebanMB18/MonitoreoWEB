from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import re
import shutil
import unicodedata

import pandas as pd

from config import (
    DOWNLOADS_DIR,
    REPORTS_DIR,
    SHAREPOINT_SYNC_DIR,
    HERCULES_DIAS_ATRAS_DIARIO,
    HERCULES_DIAS_ATRAS_ACUMULADO,
    MES_CONSOLIDAR,
)
from logger import log


DAILY_ORIGINAL_NAME = "HERCULES_DIARIO.xlsx"
DAILY_SUMMARY_NAME = "HERCULES_RESUMEN_DIARIO.xlsx"
DASHBOARD_NAME = "DASHBOARD_HERCULES.html"

LOCAL_DAILY_ORIGINAL = DOWNLOADS_DIR / "hercules_diario.xlsx"
LOCAL_DAILY_SUMMARY = REPORTS_DIR / "resumen_hercules_diario.xlsx"
LOCAL_ACCUM_SOURCE = REPORTS_DIR / "resumen_hercules_acumulado_fuente.xlsx"
LOCAL_DASHBOARD = REPORTS_DIR / "dashboard_hercules.html"


def fecha_diaria() -> datetime:
    return datetime.now() - timedelta(days=HERCULES_DIAS_ATRAS_DIARIO)


def fecha_acumulado() -> datetime:
    return datetime.now() - timedelta(days=HERCULES_DIAS_ATRAS_ACUMULADO)


def mes_reporte() -> str:
    if MES_CONSOLIDAR:
        return MES_CONSOLIDAR.replace("-", "_")
    return fecha_acumulado().strftime("%Y_%m")


def ruta_sharepoint() -> Path:
    if not SHAREPOINT_SYNC_DIR:
        raise RuntimeError("Falta SHAREPOINT_SYNC_DIR en .env")
    ruta = Path(SHAREPOINT_SYNC_DIR)
    if not ruta.exists():
        raise RuntimeError(f"No existe SHAREPOINT_SYNC_DIR: {ruta}")
    return ruta


def ruta_mensual() -> Path:
    return ruta_sharepoint() / f"HERCULES_ACUMULADO_{mes_reporte()}.xlsx"


def _normalizar(texto: str) -> str:
    texto = "" if texto is None else str(texto)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower().strip()
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _buscar_columna(df: pd.DataFrame, posibles: list[str]) -> str | None:
    mapa = {_normalizar(c): c for c in df.columns}
    posibles_norm = [_normalizar(p) for p in posibles]

    for p in posibles_norm:
        if p in mapa:
            return mapa[p]

    for col_norm, col_real in mapa.items():
        for p in posibles_norm:
            if p in col_norm or col_norm in p:
                return col_real
    return None


def _leer_base_resumen(path: Path) -> pd.DataFrame:
    hojas = pd.read_excel(path, sheet_name=None)
    if "Base_Consolidada" in hojas:
        df = hojas["Base_Consolidada"].copy()
    else:
        bases = []
        for nombre, hoja in hojas.items():
            if nombre.lower().startswith("base_"):
                temp = hoja.copy()
                if "Opción" not in temp.columns and "Opcion" not in temp.columns:
                    temp["Opción"] = nombre.replace("Base_", "")
                bases.append(temp)
        if not bases:
            raise RuntimeError(f"No encontré Base_Consolidada ni Base_* en {path.name}")
        df = pd.concat(bases, ignore_index=True)

    return df.dropna(how="all").copy()


def _copiar_sobrescribir(origen: Path, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        try:
            destino.unlink()
        except Exception:
            pass
    shutil.copy2(origen, destino)
    return destino


def copiar_diario_a_sharepoint() -> tuple[Path, Path]:
    """Copia el reporte de HOY a SharePoint. Estos archivos se sobrescriben siempre."""
    sp = ruta_sharepoint()

    if not LOCAL_DAILY_ORIGINAL.exists():
        raise RuntimeError(f"No existe Excel original diario: {LOCAL_DAILY_ORIGINAL}")
    if not LOCAL_DAILY_SUMMARY.exists():
        raise RuntimeError(f"No existe resumen diario: {LOCAL_DAILY_SUMMARY}")

    destino_original = _copiar_sobrescribir(LOCAL_DAILY_ORIGINAL, sp / DAILY_ORIGINAL_NAME)
    destino_resumen = _copiar_sobrescribir(LOCAL_DAILY_SUMMARY, sp / DAILY_SUMMARY_NAME)

    log(f"Excel diario copiado a SharePoint: {destino_original}")
    log(f"Resumen diario copiado a SharePoint: {destino_resumen}")
    return destino_original, destino_resumen


def _count_table(base: pd.DataFrame, cols: list[str | None]) -> pd.DataFrame:
    real_cols = [c for c in cols if c]
    if not real_cols:
        return pd.DataFrame({"Mensaje": ["Sin columnas disponibles"]})
    return (
        base.groupby(real_cols, dropna=False)
        .size()
        .reset_index(name="Cantidad")
        .sort_values("Cantidad", ascending=False)
    )


def actualizar_acumulado_mensual(resumen_acumulado: Path | None = None) -> Path:
    """
    Agrega el reporte del DÍA ANTERIOR al acumulado mensual.
    Si se ejecuta varias veces, reemplaza la misma Fecha_Reporte para no duplicar.
    """
    resumen = Path(resumen_acumulado) if resumen_acumulado else LOCAL_ACCUM_SOURCE
    if not resumen.exists():
        raise RuntimeError(f"No existe resumen para acumular: {resumen}")

    fecha = fecha_acumulado().strftime("%Y-%m-%d")
    mes = mes_reporte()
    mensual = ruta_mensual()

    diario = _leer_base_resumen(resumen)
    diario.insert(0, "Fecha_Reporte", fecha)
    diario.insert(1, "Mes_Reporte", mes.replace("_", "-"))

    if mensual.exists():
        try:
            base_actual = pd.read_excel(mensual, sheet_name="Base_Mensual")
        except Exception:
            base_actual = pd.DataFrame()
    else:
        base_actual = pd.DataFrame()

    if not base_actual.empty and "Fecha_Reporte" in base_actual.columns:
        base_actual = base_actual[base_actual["Fecha_Reporte"].astype(str) != fecha]

    base = pd.concat([base_actual, diario], ignore_index=True)

    col_estado = _buscar_columna(base, ["Estado Cotización", "Estado Cotizacion"])
    col_canal = _buscar_columna(base, ["Canal de Cotización", "Canal que Cotizó", "Canal que Cotizo", "Canal"])
    col_forma = _buscar_columna(base, ["Forma de Pago", "Pago Realizado", "Medio de Pago"])
    col_fecha_tx = _buscar_columna(base, ["Fecha Transacción", "Fecha Transaccion", "Fecha Cotización", "Fecha Cotizacion", "Fecha_Reporte"])
    col_hora = _buscar_columna(base, ["Hora Registro", "Hora Transacción", "Hora Transaccion"])
    col_opcion = _buscar_columna(base, ["Opción", "Opcion", "Modulo", "Módulo", "Fuente"])

    resumen_estado = _count_table(base, [col_estado])
    resumen_canal = _count_table(base, [col_canal])
    resumen_forma = _count_table(base, [col_forma])
    resumen_fecha = _count_table(base, [col_fecha_tx])
    resumen_hora = _count_table(base, [col_hora])
    resumen_opcion = _count_table(base, [col_opcion])

    with pd.ExcelWriter(mensual, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({"bold": True, "font_color": "white", "bg_color": "#005E7A", "border": 1})
        title_fmt = workbook.add_format({"bold": True, "font_color": "white", "bg_color": "#F26A21", "font_size": 14, "align": "center"})

        resumen_general = pd.DataFrame([
            ["Mes", mes.replace("_", "-")],
            ["Días cargados", base["Fecha_Reporte"].nunique() if "Fecha_Reporte" in base.columns else 0],
            ["Total registros", len(base)],
            ["Última fecha cargada", fecha],
            ["Última actualización", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ], columns=["Indicador", "Valor"])

        resumen_general.to_excel(writer, sheet_name="Resumen", index=False, startrow=2)
        base.to_excel(writer, sheet_name="Base_Mensual", index=False)
        resumen_estado.to_excel(writer, sheet_name="Estados", index=False)
        resumen_canal.to_excel(writer, sheet_name="Canales", index=False)
        resumen_forma.to_excel(writer, sheet_name="Formas_Pago", index=False)
        resumen_fecha.to_excel(writer, sheet_name="Fechas", index=False)
        resumen_hora.to_excel(writer, sheet_name="Horas", index=False)
        resumen_opcion.to_excel(writer, sheet_name="Opciones", index=False)

        ws_resumen = writer.sheets["Resumen"]
        ws_resumen.merge_range("A1:D1", "Acumulado mensual Hércules", title_fmt)

        for sheet_name, ws in writer.sheets.items():
            ws.hide_gridlines(2)
            ws.freeze_panes(1, 0)
            ws.set_column(0, 40, 18)
            try:
                ws.set_row(0, None, header_fmt)
            except Exception:
                pass

    log(f"Acumulado mensual actualizado: {mensual}")

    # Evita dejar archivos temporales locales del acumulado.
    for temporal in [DOWNLOADS_DIR / "hercules_acumulado_fuente.xlsx", REPORTS_DIR / "resumen_hercules_acumulado_fuente.xlsx"]:
        try:
            if temporal.exists():
                temporal.unlink()
        except Exception:
            pass

    return mensual


def copiar_dashboard_a_sharepoint(dashboard_path: Path | None = None) -> Path:
    sp = ruta_sharepoint()
    dashboard_path = Path(dashboard_path) if dashboard_path else LOCAL_DASHBOARD

    if not dashboard_path.exists():
        raise RuntimeError(f"No existe dashboard HTML: {dashboard_path}")

    # SharePoint/OneDrive a veces tarda en reflejar el archivo, pero localmente debe quedar copiado.
    destino = _copiar_sobrescribir(dashboard_path, sp / DASHBOARD_NAME)

    if not destino.exists():
        raise RuntimeError(f"Se intentó copiar el dashboard, pero no aparece en destino: {destino}")

    log(f"Dashboard copiado a SharePoint: {destino}")
    return destino


if __name__ == "__main__":
    copiar_diario_a_sharepoint()
    actualizar_acumulado_mensual()
    copiar_dashboard_a_sharepoint()
