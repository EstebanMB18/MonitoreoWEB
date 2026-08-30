import argparse
from datetime import datetime, timedelta
from pathlib import Path
import shutil
import pandas as pd
from src import config
from src.utils.archivos import limpiar_temporales
from src.fuentes.payu_parser import resumir_payu
from src.fuentes.ecollect_parser import resumir_ecollect, archivo_publico_o_error, diagnostico_ecollect
from src.fuentes.ecollect_bot import descargar_ecollect, guardar_sesion_ecollect
from src.fuentes.payu_bot import descargar_payu, guardar_sesion_payu
from src.procesamiento.alertas import aplicar_alertas
from src.reportes.html import generar_html


def formato_fecha(dt, inicio=True):
    return dt.strftime('%d/%m/%Y ') + ('00:00' if inicio else dt.strftime('%H:%M'))


def rango_hoy(corte=None):
    now = datetime.now()
    if str(corte).startswith('09'):
        fin = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now < fin:
            fin = now
    elif str(corte).startswith('17'):
        fin = now.replace(hour=17, minute=0, second=0, microsecond=0)
        if now < fin:
            fin = now
    else:
        fin = now
    return formato_fecha(now, True), formato_fecha(fin, False)


def rango_dia_anterior():
    d = datetime.now() - timedelta(days=1)
    return d.strftime('%d/%m/%Y 00:00'), d.strftime('%d/%m/%Y 23:59')


def cargar_verticales():
    df = pd.read_csv(config.CONFIG / 'verticales.csv')
    if 'activo' in df.columns:
        df = df[df['activo'].astype(str).str.lower().eq('true')].copy()
    return df



def publicar_salida(out_html=None, out_excel=None):
    destino = str(config.SHAREPOINT_SALIDA or '').strip()
    if not destino:
        return
    dst = Path(destino)
    try:
        dst.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f'Advertencia: no pude crear carpeta SharePoint {dst}: {e}')
        return
    copias = []
    if out_html and Path(out_html).exists():
        copias.append((Path(out_html), dst / 'dashboard_verticales.html'))
    if out_excel and Path(out_excel).exists():
        copias.append((Path(out_excel), dst / 'resumen_verticales_diario.xlsx'))
    hist = config.HISTORICO / 'acumulado_por_corte.xlsx'
    if hist.exists():
        copias.append((hist, dst / 'acumulado_por_corte.xlsx'))
    mensuales = sorted(config.MENSUAL.glob('acumulado_verticales_*.xlsx'), key=lambda p: p.stat().st_mtime)
    if mensuales:
        copias.append((mensuales[-1], dst / 'acumulado_verticales_mensual.xlsx'))
    for src, target in copias:
        try:
            shutil.copy2(src, target)
        except Exception as e:
            print(f'Advertencia: no pude copiar {src.name} a SharePoint: {e}')


def actualizar_historico_corte(df, corte='09'):
    if df.empty:
        return None
    hoy = datetime.now().strftime('%Y-%m-%d')
    ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    corte_txt = '09' if str(corte).startswith('09') else ('17' if str(corte).startswith('17') else str(corte))
    hist = config.HISTORICO / 'acumulado_por_corte.xlsx'
    base = df.copy()
    base.insert(0, 'fecha_base', hoy)
    base.insert(1, 'corte', corte_txt)
    base.insert(2, 'fecha_ejecucion', ahora)
    if hist.exists():
        try:
            old = pd.read_excel(hist)
            if {'fecha_base','corte'}.issubset(old.columns):
                old = old[~((old['fecha_base'].astype(str) == hoy) & (old['corte'].astype(str) == corte_txt))]
            final = pd.concat([old, base], ignore_index=True)
        except Exception:
            final = base
    else:
        final = base
    final.to_excel(hist, index=False)
    return hist



def procesar_archivos(corte='09', publicar=True):
    verticales = cargar_verticales()
    resultados = []
    files = list(config.DESCARGAS.glob('*'))

    # PayU: procesar el último CSV/Excel de PayU descargado.
    payu_files = [f for f in files if ('transaction' in f.name.lower() or 'payu' in f.name.lower()) and f.suffix.lower() in ['.csv', '.xlsx', '.xls']]
    if payu_files:
        payu_files.sort(key=lambda p: p.stat().st_mtime)
        try:
            resultados.append(resumir_payu(payu_files[-1]))
        except Exception as e:
            print(f'Advertencia PayU: {e}')

    # eCollect: un archivo por codigo/tipo; si falta, queda cero.
    eco_cfg = verticales[verticales.origen.eq('ECOLLECT')]
    for (codigo, tipo), cfg in eco_cfg.groupby(['codigo', 'tipo_reporte'], sort=False):
        medios_salida = cfg['medio_salida'].tolist()
        cand = [f for f in files if f'_{codigo}_' in f.name and f'_{tipo}_' in f.name and f.suffix.lower() in ['.csv']]
        # v8: eCollect se procesa ÚNICAMENTE desde CSV descargado.
        # No se toma HTML como resultado porque la página pagina/recorta datos.
        if not cand:
            df = pd.DataFrame([{
                'vertical': cfg.iloc[0].vertical,
                'codigo': codigo,
                'origen': 'ECOLLECT',
                'tipo_reporte': tipo,
                'medio_pago': str(ms).upper(),
                'medio_salida': ms,
                'cantidad_ok': 0,
                'valor_ok': 0.0,
                'ultima_ok': 'Sin archivo descargado',
                'cantidad_total': 0,
                'cantidad_fallida': 0,
            } for ms in medios_salida])
        else:
            cand.sort(key=lambda p: p.stat().st_mtime)
            try:
                fuente_actual = cand[-1]
                df = resumir_ecollect(fuente_actual, medios_salida, cfg.iloc[0].vertical, codigo, 'ECOLLECT', tipo)
                # Auditoría especial de 41610: deja evidencia fila a fila de la
                # clasificación TUP/estado para resolver diferencias manuales.
                if str(codigo).replace('.0', '') == '41610':
                    try:
                        diag = diagnostico_ecollect(fuente_actual, tipo)
                        if not diag.empty:
                            diag_path = config.SALIDA / 'diagnostico_41610_tup_ultimo.xlsx'
                            with pd.ExcelWriter(diag_path, engine='openpyxl') as writer:
                                diag.to_excel(writer, sheet_name='Detalle', index=False)
                                resumen = (diag.groupby(['medio_detectado','estado_resumen'], dropna=False)
                                             .size().reset_index(name='cantidad'))
                                resumen.to_excel(writer, sheet_name='Resumen', index=False)
                            print(f'Diagnóstico 41610 generado: {diag_path}')
                    except Exception as de:
                        print(f'Advertencia diagnóstico 41610: {de}')
            except Exception as e:
                print(f'Advertencia eCollect {codigo} {tipo}: no pude procesar {cand[-1].name}: {e}')
                df = pd.DataFrame([{
                    'vertical': cfg.iloc[0].vertical,
                    'codigo': codigo,
                    'origen': 'ECOLLECT',
                    'tipo_reporte': tipo,
                    'medio_pago': str(ms).upper(),
                    'medio_salida': ms,
                    'cantidad_ok': 0,
                    'valor_ok': 0.0,
                    'ultima_ok': 'Archivo no procesado; revisar log',
                    'cantidad_total': 0,
                    'cantidad_fallida': 0,
                } for ms in medios_salida])
        resultados.append(df)

    if not resultados:
        raise RuntimeError('No hay archivos para procesar en data/temporal_descargas')

    df = pd.concat(resultados, ignore_index=True)
    # Columnas de control para el zoom de créditos; si un parser no las trae, quedan en cero.
    for col in ['conteo_expired', 'conteo_rechazada', 'conteo_fallida_tecnica', 'conteo_pendiente', 'conteo_otra']:
        if col not in df.columns:
            df[col] = 0
    # Marcar verticales de crédito según configuración para mostrarlas en el HTML.
    try:
        mapa_credito = verticales[['vertical','codigo','es_credito']].drop_duplicates()
        mapa_credito['codigo'] = mapa_credito['codigo'].astype(str)
        df['codigo'] = df['codigo'].astype(str)
        df = df.merge(mapa_credito, on=['vertical','codigo'], how='left')
        df['es_credito'] = df['es_credito'].astype(str).str.lower().eq('true') | df['vertical'].astype(str).str.upper().str.contains('CREDITO')
    except Exception:
        df['es_credito'] = df['vertical'].astype(str).str.upper().str.contains('CREDITO')
    df = aplicar_alertas(df, corte=corte)
    actualizar_historico_corte(df, corte=corte)

    out_excel = config.SALIDA / 'resumen_verticales_ultimo.xlsx'
    df.to_excel(out_excel, index=False)
    out_html = generar_html(df)
    print(f'HTML generado: {out_html}')
    print(f'Excel generado: {out_excel}')
    if publicar:
        publicar_salida(out_html, out_excel)
    else:
        print('Publicacion oficial omitida: ejecucion en modo local/operator.')
    return df, out_html, out_excel


def ejecutar_web_ecollect(fecha_inicio, fecha_fin):
    verticales = cargar_verticales()
    items = verticales[verticales.origen.eq('ECOLLECT')][['codigo', 'tipo_reporte']].drop_duplicates().to_dict('records')
    return descargar_ecollect(fecha_inicio, fecha_fin, items)


def ejecutar_web_payu(fecha_inicio, fecha_fin):
    return descargar_payu(fecha_inicio, fecha_fin)


def web_completo(corte='09', fecha_inicio=None, fecha_fin=None, limpiar=True):
    if limpiar:
        print('Limpiando descargas temporales...')
        limpiar_temporales(config.DESCARGAS)
    if not fecha_inicio or not fecha_fin:
        fecha_inicio, fecha_fin = rango_hoy(corte)
    print(f'Rango monitoreo: {fecha_inicio} -> {fecha_fin}')

    # v7.8: PayU se descarga primero.
    # Motivo: algunos reportes de eCollect pueden demorarse varios minutos;
    # si PayU queda al final parece que no se ejecuta y se retrasa el consolidado.
    print('Descargando PayU...')
    payu_antes = set(config.DESCARGAS.glob('*'))
    try:
        ejecutar_web_payu(fecha_inicio, fecha_fin)
    except Exception as e:
        print(f'Advertencia: PayU no descargó: {e}')
    payu_despues = [f for f in config.DESCARGAS.glob('*') if f not in payu_antes and ('transaction' in f.name.lower() or 'payu' in f.name.lower())]
    if payu_despues:
        print('PayU OK: archivo detectado para consolidar: ' + payu_despues[-1].name)
    else:
        print('ADVERTENCIA PAYU: no quedó archivo nuevo en temporal_descargas. Revisa logs/payu_*.png o ejecuta solo PayU en modo visible.')

    print('Descargando eCollect...')
    try:
        ejecutar_web_ecollect(fecha_inicio, fecha_fin)
    except Exception as e:
        print(f'Advertencia: eCollect tuvo error general, se procesará lo descargado hasta ahora: {e}')

    return procesar_archivos(corte=corte)


def dia_anterior(corte='17'):
    fecha_inicio, fecha_fin = rango_dia_anterior()
    df, _, _ = web_completo(corte=corte, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, limpiar=True)
    fecha = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    mes = (datetime.now() - timedelta(days=1)).strftime('%Y_%m')
    df2 = df.copy()
    df2.insert(0, 'fecha_base', fecha)
    mensual = config.MENSUAL / f'acumulado_verticales_{mes}.xlsx'
    if mensual.exists():
        old = pd.read_excel(mensual)
        old = old[old['fecha_base'].astype(str) != fecha]
        final = pd.concat([old, df2], ignore_index=True)
    else:
        final = df2
    final.to_excel(mensual, index=False)
    print(f'Acumulado mensual actualizado: {mensual}')
    publicar_salida()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--modo', default='procesar-local', choices=['procesar-local', 'web-ecollect', 'web-payu', 'web-completo', 'dia-anterior', 'guardar-sesion-ecollect', 'guardar-sesion-payu'])
    ap.add_argument('--corte', default='09', help='09 o 17')
    ap.add_argument('--fecha-inicio', default=None, help='dd/mm/yyyy HH:MM')
    ap.add_argument('--fecha-fin', default=None, help='dd/mm/yyyy HH:MM')
    ap.add_argument('--no-limpiar', action='store_true')
    args = ap.parse_args()

    if args.modo == 'procesar-local':
        procesar_archivos(args.corte)
    elif args.modo == 'web-ecollect':
        fi, ff = (args.fecha_inicio, args.fecha_fin) if args.fecha_inicio and args.fecha_fin else rango_hoy(args.corte)
        if not args.no_limpiar:
            limpiar_temporales(config.DESCARGAS)
        ejecutar_web_ecollect(fi, ff)
        procesar_archivos(args.corte)
    elif args.modo == 'web-payu':
        fi, ff = (args.fecha_inicio, args.fecha_fin) if args.fecha_inicio and args.fecha_fin else rango_hoy(args.corte)
        if not args.no_limpiar:
            limpiar_temporales(config.DESCARGAS)
        ejecutar_web_payu(fi, ff)
        procesar_archivos(args.corte)
    elif args.modo == 'web-completo':
        web_completo(args.corte, args.fecha_inicio, args.fecha_fin, limpiar=not args.no_limpiar)
    elif args.modo == 'dia-anterior':
        dia_anterior(args.corte)
    elif args.modo == 'guardar-sesion-ecollect':
        guardar_sesion_ecollect()
    elif args.modo == 'guardar-sesion-payu':
        guardar_sesion_payu()


if __name__ == '__main__':
    main()
