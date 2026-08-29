import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

DATA = ROOT / 'data'
DESCARGAS = DATA / 'temporal_descargas'
SALIDA = DATA / 'salida'
HISTORICO = DATA / 'historico'
MENSUAL = DATA / 'mensual'
REPORTES = ROOT / 'reportes'
CONFIG = ROOT / 'config'
ASSETS = ROOT / 'assets'
STORAGE = ROOT / 'storage_state'
ECOLLECT_STATE_OVERRIDE = os.getenv('ECOLLECT_STATE_PATH', '').strip()
LOGS = ROOT / 'logs'

for p in [DESCARGAS, SALIDA, HISTORICO, MENSUAL, REPORTES, CONFIG, ASSETS, STORAGE, LOGS]:
    p.mkdir(parents=True, exist_ok=True)

ECOLLECT_URL = os.getenv('ECOLLECT_URL', 'https://www.e-collect.com/app_express/admin/eCollectIndex.aspx')
PAYU_URL = os.getenv('PAYU_URL', 'https://secure.payulatam.com/login.zul')

HEADLESS = os.getenv('HEADLESS', 'true').lower() == 'true'
USAR_SESION = os.getenv('USAR_SESION', 'true').lower() == 'true'
LOGIN_AUTOMATICO = os.getenv('LOGIN_AUTOMATICO', 'true').lower() == 'true'

TIMEOUT_CARGA_SEGUNDOS = int(os.getenv('TIMEOUT_CARGA_SEGUNDOS', '480'))
REINTENTOS_CONSULTA = int(os.getenv('REINTENTOS_CONSULTA', '1'))

UMBRAL_BAJA = float(os.getenv('UMBRAL_BAJA', '0.70'))
UMBRAL_ALERTA = float(os.getenv('UMBRAL_ALERTA', '0.40'))
PROMEDIO_MINIMO_ALERTA = float(os.getenv('PROMEDIO_MINIMO_ALERTA', '5'))

SHAREPOINT_SALIDA = os.getenv(
    'SHAREPOINT_SALIDA',
    r'C:\Users\esteban\OneDrive - Compensar\COORDINACION SOPORTE SOLUCIONES - Monitoreo diario\ECOLLECT'
).strip()
ECOLLECT_SELECTOR_TIMEOUT_SEGUNDOS = int(os.getenv('ECOLLECT_SELECTOR_TIMEOUT_SEGUNDOS', '300'))
