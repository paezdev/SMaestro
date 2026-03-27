from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from tenacity import retry, stop_after_attempt, wait_fixed
import time
import os

URL = "https://sistemamaestro.mineducacion.gov.co/SistemaMaestro/busquedaVacantes.xhtml"
DEBUG_DIR = "debug_screenshots"

def save_debug_screenshot(page, name):
    """Guarda screenshot para diagnosticar problemas en GitHub Actions."""
    os.makedirs(DEBUG_DIR, exist_ok=True)
    path = os.path.join(DEBUG_DIR, f"{name}.png")
    try:
        page.screenshot(path=path)
        print(f"  [DEBUG] Screenshot guardado: {path}")
    except Exception as e:
        print(f"  [DEBUG] No se pudo guardar screenshot: {e}")

@retry(stop=stop_after_attempt(2), wait=wait_fixed(5))
def run_scraper():
    plazas = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        try:
            print("Accediendo al Sistema Maestro...")
            page.goto(URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=30000)
            save_debug_screenshot(page, "01_pagina_inicial")

            # Esperar que los dropdowns sean visibles
            page.wait_for_selector(".ui-selectonemenu", timeout=15000)
            print("Página cargada. Seleccionando Departamento/Municipio = Antioquia...")

            # 1) Clic en el trigger (flecha) del segundo dropdown: Departamento/Municipio (índice 1)
            page.locator(".ui-selectonemenu").nth(1).locator(".ui-selectonemenu-trigger").click()

            # 2) Esperar que el panel flotante sea visible
            page.wait_for_selector(".ui-selectonemenu-panel:visible", timeout=10000)
            time.sleep(0.5)
            save_debug_screenshot(page, "02_dropdown_abierto")

            # 3) Escribir "Antioquia" en el input de búsqueda del panel para filtrar opciones
            filter_input = page.locator("#form-busqueda\\:idInputDepartamento_filter")
            filter_input.fill("Antioquia")
            time.sleep(1.5)  # esperar que PrimeFaces filtre los resultados
            save_debug_screenshot(page, "03_antioquia_filtrado")

            # 4) Clic en la fila EXACTAMENTE "Antioquia" usando JavaScript para evitar
            #    seleccionar "Antioquia/Abejorral" u otras opciones que también la contienen.
            clicked = page.evaluate("""
                () => {
                    const panel = document.querySelector('.ui-selectonemenu-panel');
                    if (!panel) return 'panel_not_found';
                    const rows = panel.querySelectorAll('tr, li');
                    for (const row of rows) {
                        const txt = row.innerText ? row.innerText.trim() : '';
                        if (txt === 'Antioquia') {
                            row.click();
                            return 'clicked:' + txt;
                        }
                    }
                    // Si no hay exacta, mostrar las opciones disponibles para diagnóstico
                    const available = Array.from(rows).map(r => r.innerText ? r.innerText.trim() : '').filter(Boolean).join(', ');
                    return 'not_found. Available: ' + available.substring(0, 300);
                }
            """)
            print(f"  Selección dropdown resultado: {clicked}")

            print("Esperando recarga AJAX tras seleccionar Antioquia...")
            page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(2)
            save_debug_screenshot(page, "04_antioquia_seleccionada")

            # Verificar que existan resultados
            try:
                page.wait_for_selector("a, button", timeout=5000)
                # verificar si hay "Ver detalle"
                count_vd = page.locator("a, button").filter(has_text="Ver detalle").count()
                print(f"Resultados cargados. Botones 'Ver detalle' visibles: {count_vd}")
            except Exception:
                pass

            save_debug_screenshot(page, "05_resultados_listados")

            # --- Loop de paginación ---
            current_page = 1
            max_pages = 15

            while True:
                print(f"Extrayendo datos de la página {current_page}...")

                # Esperar que aparezcan los botones de detalle
                try:
                    page.wait_for_selector("a:has-text('Ver detalle'), button:has-text('Ver detalle')", timeout=10000)
                except PlaywrightTimeoutError:
                    print(f"  No se encontraron botones 'Ver detalle' en página {current_page}. Fin.")
                    save_debug_screenshot(page, f"pag_{current_page}_sin_vacantes")
                    break

                # Extraer todas las tarjetas de la página actual de una sola vez usando JS
                cards_data = extract_all_cards_js(page)
                print(f"  → {len(cards_data)} vacantes extraídas en página {current_page}")
                for plaza in cards_data:
                    if plaza:
                        print(f"    + {plaza.get('Cargo','?')} | {plaza.get('Municipio','?')} | {plaza.get('Area','?')}")
                        plazas.append(plaza)

                # Si hay 0 tarjetas, diagnóstico
                if len(cards_data) == 0:
                    save_debug_screenshot(page, f"pag_{current_page}_extraccion_fallida")

                save_debug_screenshot(page, f"pag_{current_page}_extraida")

                # --- Avanzar de página ---
                next_btn = page.locator(".ui-paginator-next")
                if next_btn.count() == 0:
                    print("No hay paginador. Fin.")
                    break

                next_class = next_btn.first.get_attribute("class") or ""
                if "ui-state-disabled" in next_class or current_page >= max_pages:
                    print(f"Última página alcanzada ({current_page}). Fin.")
                    break

                print(f"  Avanzando a página {current_page + 1}...")
                next_btn.first.click()
                page.wait_for_load_state("networkidle", timeout=20000)
                time.sleep(2)
                current_page += 1

        except Exception as e:
            save_debug_screenshot(page, "ERROR_fatal")
            print(f"Error durante el scraping: {e}")
            raise
        finally:
            browser.close()

    print(f"Scraping finalizado. Total vacantes recolectadas: {len(plazas)}")
    return plazas


def extract_all_cards_js(page):
    """
    Extrae todos los datos visibles de las tarjetas de la página actual
    directamente with JavaScript, sin necesitar expandir cada una.
    Los datos de Cargo, Área, Municipio, Cierre, Postulados son visibles sin expandir.
    Para Establecimiento y Sede, expande cada tarjeta y cierra.
    """
    try:
        # Primero: extraer los datos básicos visibles de cada tarjeta
        basic_data = page.evaluate("""
            () => {
                // Los botones "Ver detalle" son la referencia para encontrar cada tarjeta
                const detalleBtns = Array.from(document.querySelectorAll('a, button'))
                    .filter(el => el.innerText && el.innerText.trim() === 'Ver detalle');

                function getCardText(btn) {
                    // Subir hasta el contenedor de la tarjeta
                    let card = btn;
                    for (let i = 0; i < 12; i++) {
                        if (!card.parentElement) break;
                        card = card.parentElement;
                        const cls = card.className || '';
                        // Buscar un contenedor que tenga múltiples campos (tarjeta completa)
                        if (card.querySelectorAll('a, button').length >= 2) break;
                    }

                    const lines = (card.innerText || '').split('\n')
                        .map(l => l.trim()).filter(Boolean);

                    function after(label) {
                        for (let i = 0; i < lines.length; i++) {
                            if (lines[i].toLowerCase().startsWith(label.toLowerCase())) {
                                const inline = lines[i].substring(label.length).replace(/^\\s*:\\s*/, '').trim();
                                if (inline) return inline;
                                if (i + 1 < lines.length) return lines[i + 1];
                            }
                        }
                        return 'N/A';
                    }

                    return {
                        Cargo: after('Cargo'),
                        Area: after('Área') !== 'N/A' ? after('Área') : after('Area'),
                        Municipio: after('Municipio'),
                        'Cierre Vacante': after('Cierre vacante') !== 'N/A' ? after('Cierre vacante') : after('Cierre'),
                        Postulados: after('Postulados'),
                        Zona: after('Zona'),
                        Secretaria: after('Secretaría de Educación') !== 'N/A' ? after('Secretaría de Educación') : after('Secretaria'),
                        Departamento: after('Departamento'),
                        raw_lines: lines.slice(0, 20).join(' | ')
                    };
                }

                return detalleBtns.map(btn => getCardText(btn));
            }
        """)

        if not basic_data:
            return []

        # Segundo: expandir cada tarjeta para obtener Establecimiento y Sede
        detail_btns = page.locator("a, button").filter(has_text="Ver detalle")
        count = detail_btns.count()

        for i in range(min(count, len(basic_data))):
            try:
                # Re-localizar (el DOM cambia al expandir/colapsar)
                btns = page.locator("a, button").filter(has_text="Ver detalle")
                if btns.count() == 0:
                    break
                btn = btns.first  # siempre tomamos el primero disponible
                btn.scroll_into_view_if_needed()
                btn.click()

                # Esperar que aparezca "Ocultar detalle" (señal de que se expandió)
                try:
                    page.wait_for_selector("a:has-text('Ocultar'), button:has-text('Ocultar')", timeout=5000)
                except PlaywrightTimeoutError:
                    pass

                # Extraer datos adicionales de la tarjeta expandida
                extra = page.evaluate("""
                    () => {
                        const ocultarBtns = Array.from(document.querySelectorAll('a, button'))
                            .filter(el => el.innerText && el.innerText.trim().toLowerCase().includes('ocultar'));
                        if (ocultarBtns.length === 0) return null;

                        const btn = ocultarBtns[0];
                        let card = btn;
                        for (let j = 0; j < 12; j++) {
                            if (!card.parentElement) break;
                            card = card.parentElement;
                            if (card.querySelectorAll('a, button').length >= 2) break;
                        }

                        const lines = (card.innerText || '').split('\n')
                            .map(l => l.trim()).filter(Boolean);

                        function after(label) {
                            for (let i = 0; i < lines.length; i++) {
                                if (lines[i].toLowerCase().startsWith(label.toLowerCase())) {
                                    const inline = lines[i].substring(label.length).replace(/^\\s*:\\s*/, '').trim();
                                    if (inline) return inline;
                                    if (i + 1 < lines.length) return lines[i + 1];
                                }
                            }
                            return 'N/A';
                        }

                        return {
                            Establecimiento: after('Establecimiento educativo') !== 'N/A'
                                ? after('Establecimiento educativo') : after('Establecimiento'),
                            Sede: after('Sede'),
                            Direccion: after('Dirección') !== 'N/A' ? after('Dirección') : after('Direccion'),
                        };
                    }
                """)

                if extra and i < len(basic_data):
                    basic_data[i].update(extra)

                # Colapsar: clic en "Ocultar detalle"
                ocultar = page.locator("a, button").filter(has_text="Ocultar").first
                if ocultar.count() > 0:
                    ocultar.click()
                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass
                    time.sleep(0.5)

            except Exception as err:
                print(f"    Error expandiendo tarjeta {i}: {err}")
                continue

        return [d for d in basic_data if d]

    except Exception as e:
        print(f"  Error en extract_all_cards_js: {e}")
        return []
