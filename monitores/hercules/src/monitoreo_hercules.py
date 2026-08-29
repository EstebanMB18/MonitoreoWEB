from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import re

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from config import (
    HERCULES_URL,
    HERCULES_REPORT_URL,
    STORAGE_STATE,
    DOWNLOADS_DIR,
    REPORTS_DIR,
    HEADLESS,
    TIMEOUT_MS,
    AUTO_LOGIN,
    HERCULES_USERNAME,
    HERCULES_PASSWORD,
    HERCULES_DIAS_ATRAS,
)
from logger import log

try:
    from procesar_reporte import procesar_excel
except Exception:
    procesar_excel = None


def _archivo_mas_reciente(carpeta: Path, extensiones: tuple[str, ...], desde_timestamp: float | None = None) -> Path | None:
    archivos = [p for p in carpeta.glob("*") if p.suffix.lower() in extensiones]
    if desde_timestamp is not None:
        archivos = [p for p in archivos if p.stat().st_mtime >= desde_timestamp]
    if not archivos:
        return None
    return max(archivos, key=lambda p: p.stat().st_mtime)


def _click_si_visible(locator, timeout: int = 5000) -> bool:
    try:
        if locator.count() > 0:
            primero = locator.first
            primero.wait_for(state="visible", timeout=timeout)
            primero.click(timeout=timeout)
            return True
    except Exception:
        return False
    return False


def configurar_fecha_personalizada(page, dias_atras: int) -> None:
    """
    Abre el calendario, entra por PERSONALIZADO y configura una sola fecha.
    Por defecto usa ayer (HERCULES_DIAS_ATRAS=1) para consolidar el día anterior.
    """
    fecha_objetivo = datetime.now() - timedelta(days=dias_atras)
    hoy = fecha_objetivo.strftime("%Y-%m-%d")
    rango = f"{hoy} - {hoy}"
    log(f"Configurando fechas por Personalizado: {rango}")

    # Abrir el daterangepicker.
    campo_fecha = page.get_by_role("searchbox", name=re.compile("Seleccione fechas|fechas", re.I)).first
    campo_fecha.click(timeout=10000)
    page.wait_for_timeout(800)

    # Muy importante: elegir Personalizado. Si no, Hércules deja Semana/Mes actual.
    personalizado = page.get_by_text("Personalizado", exact=True).first
    personalizado.click(timeout=10000)
    page.wait_for_timeout(800)

    # Llenar los inputs visibles del calendario.
    start = page.locator("input[name='daterangepicker_start']:visible").first
    end = page.locator("input[name='daterangepicker_end']:visible").first

    start.fill(hoy, timeout=10000)
    end.fill(hoy, timeout=10000)
    page.wait_for_timeout(500)

    # Dar aplicar dentro del calendario.
    aplicar = page.get_by_role("button", name=re.compile("Aplicar", re.I)).first
    aplicar.click(timeout=10000)
    page.wait_for_timeout(1200)

    log(f"Fechas configuradas correctamente: {rango}")


def seleccionar_filtros_superiores(page) -> None:
    """Selecciona los combos superiores que ya estaban funcionando."""
    filtros = [
        "(Todas las Líneas)",
        "(Todos los Deportes)",
        "(Todas las Pruebas)",
        "(Todas las Categorías)",
        "(Todos los Ciclos)",
        "Todas las sedes permitidas",
    ]

    for texto in filtros:
        try:
            loc = page.get_by_text(texto, exact=True).first
            loc.click(timeout=5000)
            page.wait_for_timeout(400)
            log(f"Filtro seleccionado/validado: {texto}")
        except Exception as exc:
            log(f"No pude validar filtro {texto}: {exc}")




def _normalizar_js() -> str:
    return """
        const normalizar = (s) => (s || '')
            .normalize('NFD').replace(/[\\u0300-\\u036f]/g, '')
            .replace(/\\s+/g, ' ')
            .trim()
            .toLowerCase();
        const visible = (el) => {
            if (!el) return false;
            const st = window.getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return st.display !== 'none' && st.visibility !== 'hidden' && r.width > 0 && r.height > 0;
        };
    """


def _marcar_checkbox_por_texto_js(page, texto: str, seccion: str | None = None, marcar_todos: bool = False) -> bool:
    """
    Marca un checkbox por texto exacto.

    - Si seccion viene informado, limita la búsqueda al panel visible de esa sección.
    - Si marcar_todos=True, marca todos los checkboxes con ese mismo texto dentro del panel.
      Esto es necesario para campos duplicados como "Hora Registro".
    """
    resultado = page.evaluate(
        _normalizar_js() + """
        ({textoBuscado, seccionBuscada, marcarTodos}) => {
            const objetivo = normalizar(textoBuscado);
            const seccionObjetivo = normalizar(seccionBuscada || '');
            const principales = ['torneos', 'gimnasios', 'afiliaciones turnos devueltos', 'turnos', 'citas', 'materiales'];

            function docRect(el) {
                const r = el.getBoundingClientRect();
                return {
                    top: r.top + window.scrollY,
                    bottom: r.bottom + window.scrollY,
                    left: r.left + window.scrollX,
                    right: r.right + window.scrollX,
                    width: r.width,
                    height: r.height
                };
            }

            function centroY(el) {
                const r = docRect(el);
                return r.top + (r.height / 2);
            }

            function buscarHeadersPrincipales() {
                const nodos = Array.from(document.querySelectorAll('label, span, div, a, button'))
                    .filter(visible)
                    .map(el => ({ el, txt: normalizar(el.innerText || el.textContent), y: centroY(el), rect: docRect(el) }))
                    .filter(x => principales.includes(x.txt));

                const salida = [];
                for (const n of nodos.sort((a,b) => a.y - b.y)) {
                    if (!salida.some(s => s.txt === n.txt && Math.abs(s.y - n.y) < 80)) salida.push(n);
                }
                return salida;
            }

            let minY = -999999;
            let maxY = 999999;

            if (seccionObjetivo) {
                const headers = buscarHeadersPrincipales();
                const header = headers.find(h => h.txt === seccionObjetivo);
                if (header) {
                    minY = header.rect.bottom - 2;
                    const siguiente = headers.find(h => h.y > header.y + 120);
                    if (siguiente) {
                        maxY = siguiente.rect.top + 2;
                    } else {
                        maxY = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, header.rect.bottom + 3000);
                    }
                }
            }

            function buscarCandidatos(min, max) {
                return Array.from(document.querySelectorAll('label, span, div, a, button'))
                    .filter(visible)
                    .map(el => ({ el, txt: normalizar(el.innerText || el.textContent), y: centroY(el) }))
                    .filter(x => x.txt === objetivo)
                    .filter(x => x.y >= min && x.y <= max)
                    .sort((a,b) => a.y - b.y);
            }

            let candidatos = buscarCandidatos(minY, maxY);

            if (candidatos.length === 0 && seccionObjetivo === 'materiales') {
                const headers = buscarHeadersPrincipales();
                const headerMat = headers.find(h => h.txt === 'materiales');
                if (headerMat) {
                    minY = headerMat.rect.bottom - 2;
                    maxY = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, headerMat.rect.bottom + 3000);
                    candidatos = buscarCandidatos(minY, maxY);
                }
            }

            const marcados = [];
            const omitidos = [];

            function intentarMarcarDesde(cand) {
                let fila = cand.el;
                for (let i = 0; i < 14 && fila; i++) {
                    const helper = fila.querySelector && fila.querySelector('.iCheck-helper');
                    const wrapper = fila.querySelector && fila.querySelector('.icheckbox_flat-green');
                    const input = fila.querySelector && fila.querySelector("input[type='checkbox']");

                    if (helper && visible(helper)) {
                        const checked = wrapper && String(wrapper.className).includes('checked');
                        if (!checked) helper.click();
                        return checked ? 'ya_estaba_marcado_panel' : 'marcado_helper_panel';
                    }

                    if (input) {
                        const checked = !!input.checked;
                        if (!checked) input.click();
                        return checked ? 'ya_estaba_marcado_input_panel' : 'marcado_input_panel';
                    }

                    const previo = fila.previousElementSibling;
                    if (previo) {
                        const h2 = previo.querySelector && previo.querySelector('.iCheck-helper');
                        const w2 = previo.querySelector && previo.querySelector('.icheckbox_flat-green');
                        const i2 = previo.querySelector && previo.querySelector("input[type='checkbox']");
                        if (h2 && visible(h2)) {
                            const checked = w2 && String(w2.className).includes('checked');
                            if (!checked) h2.click();
                            return checked ? 'ya_estaba_marcado_previo_panel' : 'marcado_helper_previo_panel';
                        }
                        if (i2) {
                            const checked = !!i2.checked;
                            if (!checked) i2.click();
                            return checked ? 'ya_estaba_marcado_input_previo_panel' : 'input_previo_panel';
                        }
                    }
                    fila = fila.parentElement;
                }
                return null;
            }

            for (const cand of candidatos) {
                const accion = intentarMarcarDesde(cand);
                if (accion) {
                    marcados.push({accion, y: cand.y});
                    if (!marcarTodos) break;
                } else {
                    omitidos.push({y: cand.y});
                }
            }

            if (marcados.length > 0) {
                return {ok: true, accion: marcados.map(m => m.accion).join(','), cantidad: marcados.length, totalCandidatos: candidatos.length};
            }

            return {ok: false, accion: 'no_encontrado_panel', minY, maxY, total: candidatos.length, omitidos: omitidos.length};
        }
        """,
        {"textoBuscado": texto, "seccionBuscada": seccion or "", "marcarTodos": bool(marcar_todos)},
    )

    if resultado and resultado.get("ok"):
        cantidad = resultado.get("cantidad", 1)
        extra = f" x{cantidad}" if marcar_todos and cantidad and cantidad > 1 else ""
        if seccion:
            log(f"Checkbox marcado: {seccion} > {texto}{extra} ({resultado.get('accion')})")
        else:
            log(f"Checkbox marcado: {texto}{extra} ({resultado.get('accion')})")
        page.wait_for_timeout(350)
        return True

    if seccion:
        log(f"NO encontré checkbox: {seccion} > {texto} ({resultado})")
    else:
        log(f"NO encontré checkbox: {texto} ({resultado})")
    return False

def marcar_seccion_principal(page, nombre: str) -> bool:
    """Marca el cuadrito principal de Torneos/Gimnasios/Turnos/Citas/Materiales."""
    return _marcar_checkbox_por_texto_js(page, nombre, None)


def abrir_seccion(page, nombre: str, campo_esperado: str | None = None) -> None:
    """
    Abre/despliega una sección usando el botón real del acordeón.
    Codegen mostró que Hércules lo interpreta como role=button, por eso usamos esa vía.
    """
    log(f"Abriendo sección: {nombre}")

    try:
        boton = page.get_by_role("button", name=nombre, exact=True).first
        boton.scroll_into_view_if_needed(timeout=10000)
        page.wait_for_timeout(300)
        # Un doble clic abre de forma más estable este acordeón en Hércules.
        boton.dblclick(timeout=10000)
        page.wait_for_timeout(900)
    except Exception as exc:
        log(f"No pude abrir con role=button {nombre}: {exc}")
        try:
            page.get_by_text(nombre, exact=True).first.click(timeout=5000)
            page.wait_for_timeout(900)
        except Exception as exc2:
            log(f"No pude abrir con texto {nombre}: {exc2}")

    if campo_esperado:
        try:
            page.get_by_text(campo_esperado, exact=True).first.wait_for(state="visible", timeout=7000)
            log(f"Sección abierta/validada: {nombre}")
        except Exception:
            log(f"Sección {nombre} no mostró todavía el campo esperado: {campo_esperado}")
    else:
        log(f"Sección abierta/validada: {nombre}")


def configurar_campos_reporte(page) -> None:
    """
    Flujo correcto:
    1. Marcar los cuadros principales: Torneos, Gimnasios, Turnos, Citas, Materiales.
    2. Abrir sección por sección y marcar los campos solicitados.
    """
    secciones_principales = [
        "Torneos",
        "Gimnasios",
        "Turnos",
        "Citas",
        "Materiales",
    ]

    # Campos internos solicitados por sección.
    # Nota: "Hora Registro" puede aparecer duplicado en Hércules; se marca con marcar_todos=True.
    campos_comunes = [
        "Cotización",
        "Estado Cotización",
        "Franquicia",
        "Forma de Pago",
        "Canal que Cotizó",
        "Canal de Pago",
        "Fecha Transacción",
        "Fecha Cotización",
        "Hora Registro",
    ]

    campos_por_seccion = {
        "Torneos": ["Sedes", *campos_comunes],
        "Gimnasios": ["Planes", *campos_comunes],
        "Turnos": ["Sedes", *campos_comunes],
        "Citas": ["Sedes", *campos_comunes],
        "Materiales": ["Sedes", *campos_comunes],
    }

    log("Marcando cuadros principales de secciones...")
    for seccion in secciones_principales:
        marcar_seccion_principal(page, seccion)

    page.wait_for_timeout(700)

    log("Marcando campos internos por sección...")
    for seccion, campos in campos_por_seccion.items():
        abrir_seccion(page, seccion, campos[0])
        page.wait_for_timeout(600)

        for campo in campos:
            # Asegura que el campo esté en pantalla antes de marcarlo.
            try:
                page.get_by_text(campo, exact=True).first.scroll_into_view_if_needed(timeout=3000)
                page.wait_for_timeout(150)
            except Exception:
                pass
            _marcar_checkbox_por_texto_js(page, campo, seccion, marcar_todos=(campo == "Hora Registro"))

        page.wait_for_timeout(500)

    log("Configuración de secciones y campos finalizada.")

def generar_y_descargar(page, fecha: str, nombre_descarga: str = "hercules_diario.xlsx") -> Path | None:
    """Genera y descarga el Excel de Hércules de forma más robusta.

    Después de marcar Materiales la pantalla queda muy abajo y Playwright a veces
    no encuentra el botón por rol. Por eso buscamos el botón con varios selectores,
    hacemos scroll al final y usamos click forzado.
    """
    log("Buscando botón Generar Reporte...")

    # Asegura que estemos en la parte baja de la página donde queda el botón.
    try:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)
    except Exception:
        pass

    selectores = [
        "button:has-text('Generar Reporte')",
        "input[value='Generar Reporte']",
        "a:has-text('Generar Reporte')",
        "text=Generar Reporte",
    ]

    boton = None
    selector_usado = None

    for selector in selectores:
        try:
            candidato = page.locator(selector).first
            if candidato.count() > 0:
                candidato.scroll_into_view_if_needed(timeout=10000)
                page.wait_for_timeout(700)
                boton = candidato
                selector_usado = selector
                log(f"Botón Generar Reporte encontrado con selector: {selector}")
                break
        except Exception as exc:
            log(f"No encontré Generar Reporte con selector {selector}: {exc}")

    if boton is None:
        log("No encontré el botón Generar Reporte.")
        return None

    # Algunos flujos de Hércules requieren un clic inicial para preparar/validar.
    try:
        log("Primer clic en Generar Reporte para preparar/validar.")
        boton.click(force=True, timeout=15000)
        page.wait_for_timeout(3500)
    except Exception as exc:
        log(f"No pude hacer primer clic en Generar Reporte con {selector_usado}: {exc}")

    # Después del primer clic el DOM puede cambiar; se vuelve a ubicar el botón.
    try:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)
        boton = page.locator(selector_usado).first
        boton.scroll_into_view_if_needed(timeout=10000)
        page.wait_for_timeout(500)
    except Exception:
        pass

    try:
        log("Segundo clic en Generar Reporte esperando descarga.")
        with page.expect_download(timeout=120000) as download_info:
            boton.click(force=True, timeout=15000)
        download = download_info.value
        # Solo conservamos el Excel diario actual para no llenar la carpeta.
        for viejo in DOWNLOADS_DIR.glob("*.xlsx"):
            try:
                viejo.unlink()
            except Exception:
                pass
        destino = DOWNLOADS_DIR / nombre_descarga
        download.save_as(str(destino))
        log(f"Archivo descargado: {destino}")
        return destino
    except Exception as exc:
        log(f"No hubo descarga después del segundo clic: {exc}")
        return None


def _parece_pantalla_login(page) -> bool:
    """Detecta si Hércules está pidiendo usuario/clave."""
    try:
        usuario = page.get_by_role("textbox", name=re.compile("Usuario", re.I)).first
        clave = page.get_by_role("textbox", name=re.compile("Clave", re.I)).first
        return usuario.count() > 0 and clave.count() > 0 and usuario.is_visible(timeout=2000)
    except Exception:
        return False


def _login_automatico_si_es_necesario(page, context) -> bool:
    """Hace login automático si la sesión expiró y AUTO_LOGIN=true."""
    if not _parece_pantalla_login(page):
        return True

    log("Hércules solicitó login.")
    if not AUTO_LOGIN:
        log("AUTO_LOGIN=false. Debes ejecutar guardar_sesion.py o activar AUTO_LOGIN en .env.")
        return False

    if not HERCULES_USERNAME or not HERCULES_PASSWORD:
        log("AUTO_LOGIN=true, pero faltan HERCULES_USERNAME/HERCULES_PASSWORD en .env.")
        return False

    log("Realizando login automático con credenciales del .env...")
    page.get_by_role("textbox", name=re.compile("Usuario", re.I)).fill(HERCULES_USERNAME, timeout=15000)
    page.get_by_role("textbox", name=re.compile("Clave", re.I)).fill(HERCULES_PASSWORD, timeout=15000)
    page.get_by_role("button", name=re.compile("Ingresar", re.I)).click(timeout=15000)
    page.wait_for_timeout(5000)

    if _parece_pantalla_login(page):
        log("El login automático no avanzó. Revisa usuario/clave o bloqueo de sesión.")
        return False

    try:
        context.storage_state(path=str(STORAGE_STATE))
        log(f"Sesión actualizada automáticamente en: {STORAGE_STATE}")
    except Exception as exc:
        log(f"No pude guardar la sesión luego del login automático: {exc}")

    return True


def _crear_contexto(browser):
    kwargs = {
        "accept_downloads": True,
        "viewport": {"width": 1620, "height": 900},
    }
    if STORAGE_STATE.exists():
        kwargs["storage_state"] = str(STORAGE_STATE)
    return browser.new_context(**kwargs)


def _filtrar_archivo_por_hora(ruta: Path, hora_inicio: str | None, hora_fin: str | None) -> Path:
    """Filtra el Excel descargado de Hércules por hora sin modificar el archivo original.
    Si no se solicita rango, devuelve la misma ruta.
    """
    if not hora_inicio or not hora_fin or (hora_inicio == "00:00" and hora_fin == "23:59"):
        return ruta

    def _mins(value):
        if pd.isna(value):
            return None
        s = str(value).strip()
        # Excel puede entregar HH:MM:SS, datetime, o decimal.
        m = re.search(r'(\d{1,2}):(\d{2})', s)
        if m:
            return int(m.group(1)) * 60 + int(m.group(2))
        try:
            if isinstance(value, (int, float)) and 0 <= float(value) < 1:
                return int(round(float(value) * 24 * 60))
        except Exception:
            pass
        return None

    hi_h, hi_m = [int(x) for x in hora_inicio.split(":", 1)]
    hf_h, hf_m = [int(x) for x in hora_fin.split(":", 1)]
    desde, hasta = hi_h * 60 + hi_m, hf_h * 60 + hf_m
    if hasta <= desde:
        raise ValueError("La hora final debe ser mayor que la hora inicial.")

    hojas = pd.read_excel(ruta, sheet_name=None)
    salida = ruta.with_name(ruta.stem + "_rango.xlsx")
    posibles = ["Hora Registro", "Hora Transacción", "Hora Transaccion", "Hora", "Hora Cotización", "Hora Cotizacion"]

    with pd.ExcelWriter(salida, engine="xlsxwriter") as writer:
        for nombre, df in hojas.items():
            col = next((c for c in posibles if c in df.columns), None)
            if col and not df.empty:
                mins = df[col].map(_mins)
                mask = mins.map(lambda x: x is not None and desde <= x <= hasta)
                df = df.loc[mask].copy()
            df.to_excel(writer, sheet_name=str(nombre)[:31], index=False)

    log(f"Hércules filtrado por hora: {hora_inicio} a {hora_fin} -> {salida.name}")
    return salida


def main(dias_atras: int | None = None, nombre_descarga: str = "hercules_diario.xlsx", nombre_resumen: str = "resumen_hercules_diario.xlsx", hora_inicio: str | None = None, hora_fin: str | None = None) -> Path:
    dias_atras = HERCULES_DIAS_ATRAS if dias_atras is None else dias_atras
    fecha = (datetime.now() - timedelta(days=dias_atras)).strftime("%Y%m%d")
    inicio_run_ts = datetime.now().timestamp()

    if not STORAGE_STATE.exists():
        raise FileNotFoundError(
            "No existe la sesión guardada. Ejecuta primero: python .\\src\\guardar_sesion.py"
        )

    DOWNLOADS_DIR.mkdir(exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)

    resumen_generado: Path | None = None

    with sync_playwright() as p:
        log(f"Iniciando navegador. HEADLESS={HEADLESS}")
        browser = p.chromium.launch(headless=HEADLESS)
        context = _crear_contexto(browser)
        page = context.new_page()
        page.set_default_timeout(TIMEOUT_MS)

        try:
            log("Entrando al reporte de Hércules...")
            page.goto(HERCULES_REPORT_URL, wait_until="networkidle", timeout=TIMEOUT_MS)
            page.wait_for_timeout(5000)

            if not _login_automatico_si_es_necesario(page, context):
                raise RuntimeError("Hércules pidió login y no fue posible iniciar sesión automáticamente.")

            if "reportes/estadisticas" not in page.url:
                page.goto(HERCULES_REPORT_URL, wait_until="networkidle", timeout=TIMEOUT_MS)
                page.wait_for_timeout(5000)

            seleccionar_filtros_superiores(page)
            configurar_fecha_personalizada(page, dias_atras)
            configurar_campos_reporte(page)

            archivo_descargado = generar_y_descargar(page, fecha, nombre_descarga)

            if not archivo_descargado:
                archivo_descargado = _archivo_mas_reciente(DOWNLOADS_DIR, (".xlsx", ".xls", ".csv"), desde_timestamp=inicio_run_ts)
                if archivo_descargado:
                    log(f"Usando archivo más reciente en downloads: {archivo_descargado}")

            if not archivo_descargado:
                raise RuntimeError("No se descargó archivo de Hércules.")

            if procesar_excel and archivo_descargado.suffix.lower() in (".xlsx", ".xls"):
                archivo_para_procesar = _filtrar_archivo_por_hora(archivo_descargado, hora_inicio, hora_fin)
                resumen_generado = procesar_excel(archivo_para_procesar, salida_nombre=nombre_resumen)
            else:
                resumen_generado = archivo_descargado

        except PlaywrightTimeoutError as exc:
            log(f"Timeout en Hércules: {exc}")
            raise
        except Exception as exc:
            log(f"Error general en monitoreo Hércules: {exc}")
            raise
        finally:
            browser.close()
            log("Navegador cerrado.")

    log("Monitoreo finalizado.")
    if resumen_generado is None:
        raise RuntimeError("No se generó resumen del monitoreo.")
    return resumen_generado


if __name__ == "__main__":
    main()
