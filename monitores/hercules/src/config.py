from pathlib import Path
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

HERCULES_URL = os.getenv("HERCULES_URL", "https://sistemahercules.bienestarcompensar.com/")
HERCULES_REPORT_URL = os.getenv(
    "HERCULES_REPORT_URL",
    "https://sistemahercules.bienestarcompensar.com/sistema.php/reportes/estadisticas#/",
)

AUTO_LOGIN = os.getenv("AUTO_LOGIN", "true").strip().lower() in ("1", "true", "yes", "si", "sí")
HERCULES_USERNAME = os.getenv("HERCULES_USERNAME", "").strip()
HERCULES_PASSWORD = os.getenv("HERCULES_PASSWORD", "").strip()

HEADLESS = os.getenv("HEADLESS", "true").strip().lower() in ("1", "true", "yes", "si", "sí")
TIMEOUT_MS = int(os.getenv("TIMEOUT_MS", "60000"))

# Flujo nuevo:
# - Diario/alertas: hoy.
# - Acumulado mensual: día anterior.
HERCULES_DIAS_ATRAS_DIARIO = int(os.getenv("HERCULES_DIAS_ATRAS_DIARIO", "0"))
HERCULES_DIAS_ATRAS_ACUMULADO = int(os.getenv("HERCULES_DIAS_ATRAS_ACUMULADO", "1"))

# Compatibilidad con scripts antiguos.
HERCULES_DIAS_ATRAS = HERCULES_DIAS_ATRAS_DIARIO

STORAGE_DIR = BASE_DIR / "storage"
STORAGE_STATE = STORAGE_DIR / "hercules_sesion.json"
DOWNLOADS_DIR = BASE_DIR / "downloads"
REPORTS_DIR = BASE_DIR / "reports"

# Compatibilidad exclusiva con scripts legacy.
# Nexus V2 publica mediante core.publisher y no depende
# de una ruta personal de SharePoint/OneDrive.
_sharepoint_raw = (
    os.getenv(
        "SHAREPOINT_SYNC_DIR",
        "",
    )
    .strip()
    .strip('"')
)

SHAREPOINT_SYNC_DIR = (
    Path(_sharepoint_raw)
    if _sharepoint_raw
    else None
)

MES_CONSOLIDAR = os.getenv(
    "MES_CONSOLIDAR",
    "",
).strip()

AUTO_CONFIGURAR_FILTROS = os.getenv("AUTO_CONFIGURAR_FILTROS", "true").strip().lower() in ("1", "true", "yes", "si", "sí")
HERCULES_REPORTE_TIPO = os.getenv("HERCULES_REPORTE_TIPO", "Reporte Personas").strip()

HERCULES_SECCIONES = [
    x.strip() for x in os.getenv(
        "HERCULES_SECCIONES",
        "Torneos,Gimnasios,Turnos,Citas,Materiales",
    ).split(",") if x.strip()
]

for folder in [STORAGE_DIR, DOWNLOADS_DIR, REPORTS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)
