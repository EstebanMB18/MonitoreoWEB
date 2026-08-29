import re, pandas as pd

def limpiar_texto(x):
    if pd.isna(x): return ''
    return re.sub(r'\s+',' ',str(x).strip().upper())

def numero(x):
    if pd.isna(x): return 0.0
    s=str(x).strip().replace('$','').replace(' ','')
    if not s or s.upper() in ['NAN','NONE','#¡VALOR!','#VALOR!','-','$-']: return 0.0
    if ',' in s and '.' in s and s.rfind(',') > s.rfind('.'):
        s=s.replace('.','').replace(',','.')
    else:
        s=s.replace(',','')
    try: return float(s)
    except Exception: return 0.0

def moneda(v):
    return ('$ {:,.0f}'.format(float(v or 0))).replace(',', '.')

def normalizar_medio(m):
    t=limpiar_texto(m)
    t=t.replace('TARJETA CREDITO','TARJETA_CREDITO').replace('TARJ. CREDITO','TARJETA_CREDITO')
    t=t.replace('MÓDULOS AUTOSERVICIO','MODULOS AUTOSERVICIO')
    t=t.replace('MODULO AUTOSERVICIO','MODULOS AUTOSERVICIO')
    t=t.replace('MODULOS AUTOSERVICIOS','MODULOS AUTOSERVICIO')
    if 'AUTOSERVICIO' in t: return 'MODULOS AUTOSERVICIO'
    if t in ['SAC','SAP5','SAP'] or 'SAC (COMPENSAR)' in t: return 'SAP'
    if 'PSE' in t: return 'PSE'
    if any(x in t for x in ['MASTERCARD','VISA','AMEX','DINERS','CREDIBANCO','REDEBAN']): return 'TARJETA_CREDITO'
    return t
