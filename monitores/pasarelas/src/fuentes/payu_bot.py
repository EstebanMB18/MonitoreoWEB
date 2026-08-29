from pathlib import Path
import os
import re
import time
from datetime import datetime
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from src import config

load_dotenv(config.ROOT / '.env')

PAYU_USER = os.getenv('PAYU_USER', '')
PAYU_PASSWORD = os.getenv('PAYU_PASSWORD', '')


def _body_text(page, timeout=5000):
    try:
        return page.locator('body').inner_text(timeout=timeout)
    except Exception:
        return ''


def _es_sesion_activa_payu(texto: str) -> bool:
    t = (texto or '').lower()
    patrones = [
        'sesion ya activa', 'sesión ya activa', 'sesion activa', 'sesión activa',
        'usuario ya tiene una sesion', 'usuario ya tiene una sesión',
        'ya existe una sesion', 'ya existe una sesión',
        'session already active', 'active session',
    ]
    return any(p in t for p in patrones)


def salir_sesion_activa_payu(page) -> bool:
    """PayU a veces muestra una pantalla indicando que ya hay sesión activa.
    En ese caso hay que dar Salir/Cerrar y volver al login.
    """
    body = _body_text(page, timeout=6000)
    if not _es_sesion_activa_payu(body):
        return False

    print('PayU: detecté sesión activa previa. Saliendo para reingresar...')
    selectores_salir = [
        'a:has-text("Salir")', 'button:has-text("Salir")', 'input[value="Salir"]',
        'a:has-text("Cerrar")', 'button:has-text("Cerrar")', 'input[value*="Cerrar" i]',
        'text=/Salir/i', 'text=/Cerrar/i',
    ]
    clicked = False
    for sel in selectores_salir:
        try:
            loc = page.locator(sel)
            if loc.count() > 0:
                loc.first.click(timeout=30000, force=True)
                clicked = True
                break
        except Exception:
            pass

    if not clicked:
        # Último recurso: limpiar storage/cookies de contexto y volver al login.
        try:
            page.context.clear_cookies()
        except Exception:
            pass

    try:
        page.wait_for_load_state('domcontentloaded', timeout=90000)
    except Exception:
        pass
    page.wait_for_timeout(3000)
    page.goto(config.PAYU_URL, wait_until='domcontentloaded', timeout=120000)
    page.wait_for_timeout(2000)
    return True


def _state_path():
    return config.STORAGE / 'payu_session.json'


def diagnostico_payu(page, nombre):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    base = config.LOGS / f'{nombre}_{ts}'
    try:
        base.with_suffix('.html').write_text(page.content(), encoding='utf-8', errors='ignore')
    except Exception:
        pass
    try:
        page.screenshot(path=str(base.with_suffix('.png')), full_page=True)
    except Exception:
        pass
    return str(base)


def login_payu_si_necesario(page):
    # Bug normal de PayU: al reingresar puede avisar que hay una sesión activa.
    # Se debe dar Salir/Cerrar y volver a login antes de buscar usuario/clave.
    if salir_sesion_activa_payu(page):
        pass

    try:
        body = page.locator('body').inner_text(timeout=4000).lower()
    except Exception:
        body = ''
    hay_password = page.locator('input[type="password"]').count() > 0
    if not hay_password and ('usuario' not in body and 'contraseña' not in body and 'contrasena' not in body):
        return
    if not config.LOGIN_AUTOMATICO:
        input('Login PayU automático desactivado. Inicia sesión y presiona ENTER...')
        return
    if not PAYU_USER or not PAYU_PASSWORD:
        raise RuntimeError('Faltan PAYU_USER / PAYU_PASSWORD en .env')

    print('PayU: login automático...')
    page.wait_for_timeout(1000)

    # Usuario: buscar input visible que no sea password.
    user_ok = False
    for sel in [
        'input[name*="user" i]', 'input[name*="login" i]', 'input[name*="email" i]',
        'input[id*="user" i]', 'input[id*="login" i]', 'input[type="email"]', 'input[type="text"]'
    ]:
        try:
            loc = page.locator(sel)
            for i in range(min(loc.count(), 8)):
                el = loc.nth(i)
                if el.is_visible() and el.is_enabled():
                    el.fill(PAYU_USER)
                    user_ok = True
                    break
            if user_ok:
                break
        except Exception:
            pass

    if not user_ok:
        raise RuntimeError('PayU: no encontré campo de usuario visible')

    page.locator('input[type="password"]').first.fill(PAYU_PASSWORD)

    clicked = False
    for sel in [
        'input[value="Ingresar"]', 'button:has-text("Ingresar")', 'text=/Ingresar/i',
        'input[type="submit"]', 'button[type="submit"]'
    ]:
        try:
            loc = page.locator(sel)
            if loc.count() > 0:
                loc.first.click(timeout=30000, force=True)
                clicked = True
                break
        except Exception:
            pass
    if not clicked:
        page.keyboard.press('Enter')

    page.wait_for_load_state('domcontentloaded', timeout=120000)
    page.wait_for_timeout(5000)

    # Algunas veces PayU acepta usuario/clave pero responde con “sesión activa”.
    # En ese caso salimos y repetimos login una sola vez.
    if salir_sesion_activa_payu(page):
        try:
            body2 = page.locator('body').inner_text(timeout=4000).lower()
        except Exception:
            body2 = ''
        if page.locator('input[type="password"]').count() > 0 or 'usuario' in body2 or 'contraseña' in body2 or 'contrasena' in body2:
            # repetir el login sin quedar en bucle infinito: la pantalla ya fue limpiada.
            print('PayU: reintentando login después de cerrar sesión activa...')
            user_ok = False
            for sel in [
                'input[name*="user" i]', 'input[name*="login" i]', 'input[name*="email" i]',
                'input[id*="user" i]', 'input[id*="login" i]', 'input[type="email"]', 'input[type="text"]'
            ]:
                try:
                    loc = page.locator(sel)
                    for i in range(min(loc.count(), 8)):
                        el = loc.nth(i)
                        if el.is_visible() and el.is_enabled():
                            el.fill(PAYU_USER)
                            user_ok = True
                            break
                    if user_ok:
                        break
                except Exception:
                    pass
            if user_ok and page.locator('input[type="password"]').count() > 0:
                page.locator('input[type="password"]').first.fill(PAYU_PASSWORD)
                for sel in ['input[value="Ingresar"]', 'button:has-text("Ingresar")', 'text=/Ingresar/i', 'input[type="submit"]', 'button[type="submit"]']:
                    try:
                        loc = page.locator(sel)
                        if loc.count() > 0:
                            loc.first.click(timeout=30000, force=True)
                            break
                    except Exception:
                        pass
                page.wait_for_load_state('domcontentloaded', timeout=120000)
                page.wait_for_timeout(5000)


def ir_reporte_payu(page):
    REPORTS_URL = "https://secure.payulatam.com/reports/"
    def formulario_reportes():
        try:
            ini=page.locator('input[name="dateboxStartDate"]')
            fin=page.locator('input[name="dateboxEndDate"]')
            return ini.count()>0 and fin.count()>0 and ini.first.is_visible(timeout=1500) and fin.first.is_visible(timeout=1500)
        except Exception:
            return False
    def body():
        try: return page.locator("body").inner_text(timeout=8000).lower()
        except Exception: return ""
    def sesion_intermedia():
        t=body(); return "already logged into the system" in t or "already logged" in t or "welcome to your administrative module" in t
    def pulsar_enter():
        print("PayU: sesión existente detectada. Ingresando al módulo...")
        cands=[page.get_by_text("Enter",exact=True),page.get_by_role("link",name="Enter",exact=True),page.get_by_role("button",name="Enter",exact=True),page.locator("a:has-text('Enter')"),page.locator("input[value='Enter']")]
        for loc in cands:
            try:
                if loc.count()>0 and loc.first.is_visible(timeout=1500):
                    loc.first.click(timeout=10000,force=True); print("PayU: clic en Enter realizado.")
                    try: page.wait_for_load_state("domcontentloaded",timeout=30000)
                    except Exception: pass
                    page.wait_for_timeout(2500); return True
            except Exception: pass
        return False
    def login_real():
        try:
            pw=page.locator('input[type="password"]')
            pw_ok=any(pw.nth(i).is_visible(timeout=500) for i in range(min(pw.count(),4)))
        except Exception: pw_ok=False
        user_ok=False
        for sel in ['input[type="email"]','input[name*="user" i]','input[id*="user" i]','input[name*="login" i]','input[id*="login" i]']:
            try:
                loc=page.locator(sel)
                if any(loc.nth(i).is_visible(timeout=500) for i in range(min(loc.count(),4))): user_ok=True; break
            except Exception: pass
        return pw_ok and user_ok
    if formulario_reportes():
        print("PayU: formulario Transactions (New) ya abierto."); return True
    print("PayU: abriendo Reports / Transactions...")
    try: page.goto(REPORTS_URL,wait_until="domcontentloaded",timeout=120000); page.wait_for_timeout(2500)
    except Exception as exc: print(f"PayU: advertencia abriendo Reports: {exc}")
    if formulario_reportes(): print("PayU: formulario Transactions (New) encontrado."); return True
    if sesion_intermedia() and pulsar_enter():
        try: page.goto(REPORTS_URL,wait_until="domcontentloaded",timeout=120000); page.wait_for_timeout(2500)
        except Exception: pass
        if formulario_reportes(): print("PayU: formulario encontrado después de recuperar la sesión."); return True
    if login_real():
        print("PayU: pantalla real de login detectada."); login_payu_si_necesario(page); page.wait_for_timeout(2500)
        if sesion_intermedia(): pulsar_enter()
        try: page.goto(REPORTS_URL,wait_until="domcontentloaded",timeout=120000); page.wait_for_timeout(2500)
        except Exception: pass
        if formulario_reportes(): print("PayU: formulario encontrado después del login."); return True
    for sel in ['a[title="Transactions (New)"]','a:has-text("Transactions (New)")','a:has-text("Transacciones (Nuevo)")']:
        try:
            loc=page.locator(sel)
            if loc.count()>0 and loc.first.is_visible(timeout=1500):
                loc.first.click(timeout=10000,force=True); page.wait_for_timeout(3000)
                if formulario_reportes(): print("PayU: formulario encontrado mediante menú."); return True
        except Exception: pass
    base=diagnostico_payu(page,"payu_no_formulario")
    raise RuntimeError(f"PayU no llegó a Transactions (New). Diagnóstico: {base}.html/.png")

def llenar_fechas_payu(page, fecha_inicio, fecha_fin):
    ini=page.locator('input[name="dateboxStartDate"]'); fin=page.locator('input[name="dateboxEndDate"]')
    ini.wait_for(state="visible",timeout=30000); fin.wait_for(state="visible",timeout=30000)
    print(f"PayU: fecha inicio -> {fecha_inicio}"); ini.click(); ini.fill(fecha_inicio)
    print(f"PayU: fecha fin -> {fecha_fin}"); fin.click(); fin.fill(fecha_fin)
    page.keyboard.press("Tab"); page.wait_for_timeout(1000)
    print("PayU: fechas diligenciadas correctamente.")

def descargar_payu(fecha_inicio, fecha_fin):
    p=sync_playwright().start(); browser=None
    try:
        state=_state_path(); browser=p.chromium.launch(headless=config.HEADLESS)
        context=browser.new_context(accept_downloads=True,storage_state=str(state) if config.USAR_SESION and state.exists() else None)
        page=context.new_page(); page.set_default_timeout(90000)
        print("PayU: abriendo login..."); page.goto(config.PAYU_URL,wait_until="domcontentloaded",timeout=120000)
        ir_reporte_payu(page); context.storage_state(path=str(state)); llenar_fechas_payu(page,fecha_inicio,fecha_fin)
        print("PayU: iniciando descarga directa del reporte...")
        boton=page.locator('button.transactions-report-download-report-button')
        if boton.count()==0: boton=page.get_by_role("button",name="Download",exact=True)
        if boton.count()==0:
            base=diagnostico_payu(page,"payu_sin_boton_download"); raise RuntimeError(f"PayU: no encontré Download. Diagnóstico: {base}.html/.png")
        boton.first.wait_for(state="visible",timeout=30000); print("PayU: botón Download encontrado.")
        with page.expect_download(timeout=45000) as info:
            print("PayU: haciendo clic en Download y esperando archivo..."); boton.first.click(timeout=30000,force=True)
        d=info.value; print("PayU: descarga directa detectada.")
        ext=Path(d.suggested_filename or "payu.csv").suffix or ".csv"
        target=config.DESCARGAS/f'payu_41621_{datetime.now().strftime("%Y%m%d_%H%M%S")}_transactions{ext}'
        d.save_as(str(target))
        if not target.exists() or target.stat().st_size==0: raise RuntimeError("PayU descargó archivo vacío.")
        print(f"PayU: archivo guardado correctamente: {target}"); print(f"PayU: tamaño archivo: {target.stat().st_size/1024:.1f} KB")
        context.storage_state(path=str(state)); return target
    finally:
        try:
            if browser: browser.close()
        finally: p.stop()

def guardar_sesion_payu():
    p=sync_playwright().start(); browser=None
    try:
        browser=p.chromium.launch(headless=False); context=browser.new_context(accept_downloads=True); page=context.new_page()
        page.goto(config.PAYU_URL,wait_until="domcontentloaded",timeout=120000); ir_reporte_payu(page)
        context.storage_state(path=str(_state_path())); print(f"Sesión PayU guardada automáticamente en {_state_path()}")
    finally:
        try:
            if browser: browser.close()
        finally: p.stop()
