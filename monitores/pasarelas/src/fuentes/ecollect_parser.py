import pandas as pd
import re
import csv
import io
from pathlib import Path
from bs4 import BeautifulSoup
from src.utils.limpieza import numero, normalizar_medio, limpiar_texto

PUBLIC_MARKERS = [
    'IR AL CONTENIDO PRINCIPAL', 'CLIENTES HABLEMOS', 'INTEGRA TODOS LOS CANALES',
    'WIX.COM WEBSITE BUILDER', 'PLANES MEDIOS DE PAGO BLOG', 'ASPXERRORPATH'
]
SIN_DATOS_MARKERS = [
    'NO SE ENCONTRARON DATOS', 'NO SE ENCUENTRAN DATOS',
    'NO SE ENCONTRARON REGISTROS', 'NO SE ENCONTRARON REGISTROS QUE CUMPLAN ESTE CRITERIO',
    'NO HAY REGISTROS', 'SIN DATOS'
]
OK_ESTADOS = ['OK', 'APROBADA', 'APROBADO', 'APPROVED']


def leer_texto_archivo(path, max_chars=None):
    data = Path(path).read_bytes()
    for enc in ['utf-8-sig', 'utf-8', 'latin1', 'cp1252']:
        try:
            txt = data.decode(enc, errors='ignore')
            return txt if max_chars is None else txt[:max_chars]
        except Exception:
            pass
    txt = data.decode('latin1', errors='ignore')
    return txt if max_chars is None else txt[:max_chars]


def archivo_publico_o_error(path):
    txt = limpiar_texto(leer_texto_archivo(path, 25000))
    return any(m in txt for m in PUBLIC_MARKERS)


def archivo_sin_datos(path):
    txt = limpiar_texto(leer_texto_archivo(path, 25000))
    return any(m in txt for m in SIN_DATOS_MARKERS)


def _reparar_filas_ecollect(rows):
    """Repara exportaciones eCollect con comas internas sin comillas.

    El formato RED observado tiene 31 columnas. Algunas descripciones de servicio
    contienen una coma (p.ej. "Servicios de Recreación, Educación y Deportes")
    y el portal la exporta sin encapsular, desplazando el resto de la fila.
    En vez de descartar la fila, unimos el exceso en la columna descriptiva 4.
    """
    if not rows:
        return rows
    lens = [len(r) for r in rows if len(r) > 5]
    if not lens:
        return rows
    # La longitud mínima frecuente suele ser la estructura real del archivo.
    expected = min(lens)
    repaired = []
    for row in rows:
        r = list(row)
        if len(r) > expected and expected >= 10:
            extra = len(r) - expected
            # Las columnas 0..3 son identificadores; la descripción inicia en 4.
            merged = ', '.join(r[4:5 + extra])
            r = r[:4] + [merged] + r[5 + extra:]
        if len(r) < expected:
            r = r + [''] * (expected - len(r))
        repaired.append(r[:expected])
    return repaired


def leer_csv_ecollect(path):
    data = Path(path).read_bytes()
    candidatos = []
    for enc in ['utf-8-sig', 'utf-8', 'latin1', 'cp1252']:
        try:
            text = data.decode(enc)
        except Exception:
            continue
        for sep in [',', ';', '\t']:
            try:
                rows = list(csv.reader(io.StringIO(text), delimiter=sep))
                rows = [r for r in rows if any(str(x).strip() for x in r)]
                if not rows:
                    continue
                fixed = _reparar_filas_ecollect(rows)
                df = pd.DataFrame(fixed, dtype=str)
                if df.shape[1] > 5 and df.shape[0] > 0:
                    # Priorizamos conservar filas; ya no se usa on_bad_lines=skip.
                    candidatos.append((df.shape[0], df.shape[1], df))
            except Exception:
                pass
    if not candidatos:
        return pd.DataFrame()
    candidatos.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidatos[0][2]


def inferir_columnas(df, tipo='RED'):
    tipo = str(tipo or '').upper()
    cols = set(df.columns)
    def tiene(col, opciones):
        if col not in cols:
            return False
        joined = ' | '.join(df[col].dropna().astype(str).map(limpiar_texto).head(100).tolist())
        return any(o in joined for o in opciones)

    if tipo == 'JAVA' or tiene(27, ['PSE', 'TARJ', 'AUTOSERVICIO', 'SAC', 'REDES']) or tiene(17, OK_ESTADOS + ['BANK', 'NOT_AUTHORIZED', 'EXPIRED']):
        return {'valor': 4 if 4 in cols else 2, 'estado': 17 if 17 in cols else 10, 'medio': 27 if 27 in cols else 23, 'fecha': 25 if 25 in cols else (13 if 13 in cols else None)}
    return {'valor': 2 if 2 in cols else 4, 'estado': 10 if 10 in cols else 17, 'medio': 23 if 23 in cols else 27, 'fecha': 18 if 18 in cols else (19 if 19 in cols else (7 if 7 in cols else None))}


def normalizar_celda_medio(x):
    t = limpiar_texto(x)
    if not t or t in ['NAN', 'NONE', '0', '0.0', '0.00']:
        return ''
    if t == 'TUP':
        return 'TUP'
    if t in ['PSE', 'PSE_AVANZA']:
        return 'PSE'
    if 'AUTOSERVICIO' in t:
        return 'MODULOS AUTOSERVICIO'
    if t in ['SAC', 'SAP', 'SAP5'] or 'SAC (COMPENSAR)' in t or 'SAP5' in t:
        return 'SAP'
    if t == 'REDES' or t == 'REDES /SAC':
        return 'REDES'
    if t == 'CUPOYA':
        return 'CUPOYA'
    if 'TARJ. CREDITO' in t or 'TARJETA_CREDITO' in t or 'TARJETA CREDITO' in t:
        return 'TARJETA_CREDITO'
    return ''


def detectar_estado_fila(row):
    """Detecta el estado real de la transacción sin confundir textos auxiliares.

    En 41610 RED se observó un formato desplazado donde una celda contiene
    ``TARJETA COMPENSAR`` y la celda inmediatamente a la derecha contiene el
    estado real (OK, NOT_AUTHORIZED, FAILED, etc.). Esa relación tiene prioridad
    sobre cualquier otro texto encontrado en la fila.
    """
    estados_no_ok = {
        'BANK', 'NOT_AUTHORIZED', 'NOT AUTHORIZED', 'EXPIRED', 'CREATED',
        'DECLINED', 'REJECTED', 'FAILED', 'PENDING', 'ERROR', 'CANCELLED',
        'CANCELED', 'ABANDONED'
    }
    estados_validos = set(OK_ESTADOS) | estados_no_ok

    # 1) Caso crítico observado: medio/autorizador seguido por estado.
    #    Recorremos por posición, no por nombre de columna, porque el CSV puede
    #    venir corrido una columna por comas internas sin comillas.
    vals = list(row.values)
    for i, x in enumerate(vals[:-1]):
        t = limpiar_texto(x)
        if (
            'TARJETA COMPENSAR' in t
            or t == 'TUP'
            or 'MONEDERO' in t
            or 'BONOS' in t
            or 'BOLSILLO SUBSIDIO' in t
        ):
            siguiente = limpiar_texto(vals[i + 1])
            if siguiente in estados_validos:
                return siguiente

    # 2) Columnas de estado observadas en los dos layouts eCollect.
    for idx in [10, 11, 17, 18]:
        if idx in row.index:
            t = limpiar_texto(row.get(idx))
            if t in estados_validos:
                return t

    # 3) Defensa final: busca estados en toda la fila, preservando primero los
    #    no exitosos para no convertir una transacción rechazada en OK por un
    #    texto auxiliar que también contenga la palabra OK.
    for x in row.values:
        t = limpiar_texto(x)
        if t in estados_no_ok:
            return t
    for x in row.values:
        t = limpiar_texto(x)
        if t in OK_ESTADOS:
            return t
    return ''




def clasificar_estado_resumen(estado):
    t = limpiar_texto(estado)
    if t in OK_ESTADOS:
        return 'OK'
    if 'EXPIRED' in t or 'VENCID' in t:
        return 'EXPIRED'
    if t in ['REJECTED', 'DECLINED', 'NOT_AUTHORIZED', 'NOT AUTHORIZED', 'BANK']:
        return 'RECHAZADA'
    if t in ['FAILED', 'ERROR', 'CANCELLED', 'CANCELED']:
        return 'FALLIDA'
    if t in ['CREATED', 'PENDING', 'ABANDONED']:
        return 'PENDIENTE'
    if not t:
        return 'SIN_ESTADO'
    return 'OTRA'


def detectar_medio_fila(row, medio_col=None):
    """Clasifica el medio de pago de una fila eCollect de forma tolerante a columnas corridas.

    Importante:
    - La selección de aprobadas se hace DESPUÉS por _estado = OK/APROBADA.
    - Para 41610 RED, eCollect puede mover el medio entre columnas vecinas.
    - "TUP", "Tarjeta Compensar", "Bolsillo Subsidio" y "Bolsillo Bonos" se consideran TUP.
    - Se revisan explícitamente la columna inferida y sus dos vecinas, además de toda la fila.
    """
    candidatos = []

    # Prioridad 1: columna de medio inferida y sus vecinas (las "dos columnas" que suelen moverse).
    if medio_col is not None:
        for idx in [medio_col - 1, medio_col, medio_col + 1]:
            if idx in row.index:
                candidatos.append(row.get(idx))

    # Prioridad 2: columnas conocidas del formato RED/JAVA y alrededores.
    for idx in [22, 23, 24, 25, 26, 27, 28, 8, 9]:
        if idx in row.index:
            candidatos.append(row.get(idx))

    # Prioridad 3: fila completa como defensa ante CSV con comas/desplazamientos.
    candidatos.extend(list(row.values))

    encontrados = []
    for x in candidatos:
        t = limpiar_texto(x)
        if not t:
            continue

        if (
            t == 'TUP'
            or 'TARJETA COMPENSAR' in t
            or 'TARJETA UNICA' in t
            or 'TARJETA ÚNICA' in t
            or 'BOLSILLO SUBSIDIO' in t
            or 'BOLSILLO BONOS' in t
        ):
            encontrados.append('TUP')
            continue

        m = normalizar_celda_medio(x)
        if m:
            encontrados.append(m)

    # TUP debe ganar cuando la fila trae textos auxiliares que también contienen PSE/Tarjeta.
    for prioridad in [
        'TUP', 'MODULOS AUTOSERVICIO', 'SAP', 'REDES', 'CUPOYA',
        'PSE', 'TARJETA_CREDITO'
    ]:
        if prioridad in encontrados:
            return prioridad

    return ''

def detectar_fecha_fila(row, fecha_col=None):
    if fecha_col is not None and fecha_col in row.index:
        val = row.get(fecha_col)
        if limpiar_texto(val):
            return str(val)
    patron = re.compile(r'\d{1,2}/\d{1,2}/\d{4}(?:\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]\.?M\.?)?)?', re.I)
    for x in row.values:
        s = '' if pd.isna(x) else str(x)
        if patron.search(s):
            return s
    return ''


def detectar_valor_fila(row, valor_col=None):
    if valor_col is not None and valor_col in row.index:
        return numero(row.get(valor_col))
    for idx in [2, 4, 3, 5]:
        if idx in row.index:
            v = numero(row.get(idx))
            if v:
                return v
    return 0.0


def resumir_desde_dataframe_tabular(df, medios, vertical, codigo, origen, tipo):
    cols = inferir_columnas(df, tipo)
    d = df.copy()
    valor_col = cols.get('valor')
    medio_col = cols.get('medio')
    fecha_col = cols.get('fecha')

    d['_estado'] = d.apply(lambda r: detectar_estado_fila(r), axis=1)
    d['_valor'] = d.apply(lambda r: detectar_valor_fila(r, valor_col), axis=1)
    d['_medio'] = d.apply(lambda r: detectar_medio_fila(r, medio_col), axis=1)
    d['_fecha'] = d.apply(lambda r: detectar_fecha_fila(r, fecha_col), axis=1)

    ok = d[d['_estado'].isin(OK_ESTADOS)].copy()
    out = []
    for m in medios:
        mn = normalizar_medio(m)
        sub = ok[ok['_medio'].eq(mn)]
        total = d[d['_medio'].eq(mn)]
        fall = total[~total['_estado'].isin(OK_ESTADOS)]
        clases = total['_estado'].map(clasificar_estado_resumen) if not total.empty else pd.Series(dtype=str)
        out.append({
            'vertical': vertical, 'codigo': codigo, 'origen': origen, 'tipo_reporte': tipo,
            'medio_pago': mn, 'medio_salida': m,
            'cantidad_ok': int(len(sub)), 'valor_ok': float(sub['_valor'].sum()),
            'ultima_ok': str(sub['_fecha'].max()) if not sub.empty else 'Sin aprobadas en el archivo actual',
            'cantidad_total': int(len(total)), 'cantidad_fallida': int(len(fall)),
            'conteo_expired': int((clases == 'EXPIRED').sum()),
            'conteo_rechazada': int((clases == 'RECHAZADA').sum()),
            'conteo_fallida_tecnica': int((clases == 'FALLIDA').sum()),
            'conteo_pendiente': int((clases == 'PENDIENTE').sum()),
            'conteo_otra': int((clases == 'OTRA').sum() + (clases == 'SIN_ESTADO').sum()),
        })
    return pd.DataFrame(out)



def diagnostico_ecollect(path, tipo='RED'):
    """Devuelve el detalle clasificado fila a fila para auditoría operativa.

    No altera el cálculo del dashboard. Sirve para comprobar exactamente qué
    registros se clasificaron como PSE, Tarjeta Crédito o TUP y cuál fue el
    estado detectado en cada uno.
    """
    p = Path(path)
    df = leer_csv_ecollect(p)
    if df.empty:
        return pd.DataFrame()
    cols = inferir_columnas(df, tipo)
    valor_col = cols.get('valor')
    medio_col = cols.get('medio')
    fecha_col = cols.get('fecha')
    out = pd.DataFrame({
        'fila_origen': range(1, len(df) + 1),
        'medio_detectado': df.apply(lambda r: detectar_medio_fila(r, medio_col), axis=1),
        'estado_detectado': df.apply(lambda r: detectar_estado_fila(r), axis=1),
        'estado_resumen': df.apply(lambda r: clasificar_estado_resumen(detectar_estado_fila(r)), axis=1),
        'valor': df.apply(lambda r: detectar_valor_fila(r, valor_col), axis=1),
        'fecha': df.apply(lambda r: detectar_fecha_fila(r, fecha_col), axis=1),
        'contiene_tarjeta_compensar': df.apply(
            lambda r: any('TARJETA COMPENSAR' in limpiar_texto(x) for x in r.values), axis=1
        ),
    })
    return out

def resumir_ecollect(path, medios, vertical='', codigo='', origen='ECOLLECT', tipo='RED'):
    medios = list(medios)
    p = Path(path)
    if archivo_publico_o_error(p):
        return pd.DataFrame([fila_cero(vertical, codigo, tipo, m, 'Archivo público/error de sesión; no usar como dato') for m in medios])
    if archivo_sin_datos(p):
        return pd.DataFrame([fila_cero(vertical, codigo, tipo, m, 'Sin registros en eCollect') for m in medios])
    if p.suffix.lower() in ['.html', '.htm', '.txt']:
        return pd.DataFrame([fila_cero(vertical, codigo, tipo, m, 'HTML no usado como fuente; se requiere CSV') for m in medios])
    df = leer_csv_ecollect(p)
    if df.empty:
        return pd.DataFrame([fila_cero(vertical, codigo, tipo, m, 'CSV vacío/no leído') for m in medios])
    return resumir_desde_dataframe_tabular(df, medios, vertical, codigo, origen, tipo)


def fila_cero(vertical, codigo, tipo, m, motivo=''):
    return {'vertical': vertical, 'codigo': codigo, 'origen': 'ECOLLECT', 'tipo_reporte': tipo,
            'medio_pago': normalizar_medio(m), 'medio_salida': m, 'cantidad_ok': 0,
            'valor_ok': 0.0, 'ultima_ok': motivo or 'Sin aprobadas en el archivo actual',
            'cantidad_total': 0, 'cantidad_fallida': 0,
            'conteo_expired': 0, 'conteo_rechazada': 0, 'conteo_fallida_tecnica': 0,
            'conteo_pendiente': 0, 'conteo_otra': 0}
