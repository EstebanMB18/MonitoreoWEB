import re
from playwright.sync_api import sync_playwright
from config import (
    HERCULES_URL,
    HERCULES_REPORT_URL,
    STORAGE_STATE,
    TIMEOUT_MS,
    AUTO_LOGIN,
    HERCULES_USERNAME,
    HERCULES_PASSWORD,
)
from logger import log


def _login_automatico(page) -> bool:
    if not AUTO_LOGIN:
        return False
    if not HERCULES_USERNAME or not HERCULES_PASSWORD:
        log("AUTO_LOGIN=true, pero faltan HERCULES_USERNAME/HERCULES_PASSWORD en .env.")
        return False

    try:
        usuario = page.get_by_role("textbox", name=re.compile("Usuario", re.I)).first
        clave = page.get_by_role("textbox", name=re.compile("Clave", re.I)).first
        usuario.wait_for(state="visible", timeout=10000)
        usuario.fill(HERCULES_USERNAME)
        clave.fill(HERCULES_PASSWORD)
        page.get_by_role("button", name=re.compile("Ingresar", re.I)).click(timeout=15000)
        page.wait_for_timeout(5000)
        log("Login automático ejecutado.")
        return True
    except Exception as exc:
        log(f"No pude hacer login automático: {exc}")
        return False


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True, viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.set_default_timeout(TIMEOUT_MS)

        log("Abriendo Hércules para guardar sesión...")
        page.goto(HERCULES_URL, wait_until="networkidle", timeout=TIMEOUT_MS)
        page.wait_for_timeout(2000)

        if AUTO_LOGIN:
            _login_automatico(page)
            if "reportes/estadisticas" not in page.url:
                try:
                    page.goto(HERCULES_REPORT_URL, wait_until="networkidle", timeout=TIMEOUT_MS)
                    page.wait_for_timeout(3000)
                except Exception:
                    pass
        else:
            print("\nHaz login manualmente en la ventana del navegador.")
            print("Cuando ya estés dentro de Hércules, vuelve a esta consola y presiona ENTER.\n")
            input("Presiona ENTER cuando ya estés logueado: ")

        context.storage_state(path=str(STORAGE_STATE))
        log(f"Sesión guardada correctamente en: {STORAGE_STATE}")
        browser.close()


if __name__ == "__main__":
    main()
