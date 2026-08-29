from __future__ import annotations

from monitoreo_hercules import main as ejecutar_monitoreo
from sharepoint_hercules import (
    copiar_diario_a_sharepoint,
    actualizar_acumulado_mensual,
    copiar_dashboard_a_sharepoint,
)
from generar_dashboard_hercules import generar_dashboard
from config import HERCULES_DIAS_ATRAS_DIARIO, HERCULES_DIAS_ATRAS_ACUMULADO
from logger import log


def _generar_y_subir_dashboard(etapa: str) -> None:
    """Genera y copia el dashboard a SharePoint sin tumbar todo el flujo si algo falla."""
    try:
        log(f"Generando dashboard ({etapa})...")
        dashboard = generar_dashboard()
        copiar_dashboard_a_sharepoint(dashboard)
        log(f"Dashboard generado y copiado a SharePoint ({etapa}).")
    except Exception as exc:
        log(f"ADVERTENCIA: No se pudo generar/copiar dashboard ({etapa}): {exc}")


def main() -> None:
    log("Iniciando flujo completo Hércules")

    # 1) Descargar HOY para alertas y dashboard diario.
    log(f"Descargando reporte DIARIO para alertas. Dias atras={HERCULES_DIAS_ATRAS_DIARIO}")
    ejecutar_monitoreo(
        dias_atras=HERCULES_DIAS_ATRAS_DIARIO,
        nombre_descarga="hercules_diario.xlsx",
        nombre_resumen="resumen_hercules_diario.xlsx",
    )

    # 2) Copiar el diario de HOY a SharePoint. Se sobrescribe siempre.
    copiar_diario_a_sharepoint()

    # 3) Generar dashboard inmediatamente con la información diaria.
    # Esto evita que el dashboard no suba si después falla la descarga de ayer o el acumulado.
    _generar_y_subir_dashboard("diario")

    # 4) Descargar AYER y alimentar el acumulado mensual.
    # Si falla esta parte, no debe impedir que el dashboard diario quede en SharePoint.
    mensual = None
    try:
        log(f"Descargando reporte para ACUMULADO mensual. Dias atras={HERCULES_DIAS_ATRAS_ACUMULADO}")
        ejecutar_monitoreo(
            dias_atras=HERCULES_DIAS_ATRAS_ACUMULADO,
            nombre_descarga="hercules_acumulado_fuente.xlsx",
            nombre_resumen="resumen_hercules_acumulado_fuente.xlsx",
        )

        mensual = actualizar_acumulado_mensual()

        # 5) Regenerar dashboard para que la pestaña mensual quede actualizada.
        _generar_y_subir_dashboard("mensual actualizado")

    except Exception as exc:
        log(f"ADVERTENCIA: Falló la parte de acumulado mensual, pero el diario quedó procesado: {exc}")

    log(f"Flujo completo finalizado. Acumulado mensual: {mensual}")


if __name__ == "__main__":
    main()
