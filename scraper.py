from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from tenacity import retry, stop_after_attempt, wait_fixed
import time
import os

URL = "https://sistemamaestro.mineducacion.gov.co/SistemaMaestro/busquedaVacantes.xhtml"
DEBUG_DIR = "debug_screenshots"

def save_debug_screenshot(page, name):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    path = os.path.join(DEBUG_DIR, f"{name}.png")
    try:
        page.screenshot(path=path)
        print(f"  [DEBUG] Screenshot: {path}")
    except Exception as e:
        print(f"  [DEBUG] Screenshot error: {e}")

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

            # Esperar que los dropdowns estén listos
            page.wait_for_selector("#form-busqueda\\:idInputDepartamento", timeout=15000)
            print("Página cargada. Abriendo dropdown Departamento/Municipio...")

            # 1) Clic en el label del dropdown Departamento/Municipio para abrirlo
            page.locator("#form-busqueda\\:idInputDepartamento_label").click()

            # 2) Esperar que el panel sea visible (por ID exacto del panel)
            page.wait_for_selector("#form-busqueda\\:idInputDepartamento_panel", timeout=10000)
            time.sleep(0.5)
            save_debug_screenshot(page, "02_dropdown_abierto")

            # 3) Clic en el input filtro para enfocarlo y escribir
            filter_input = page.locator("#form-busqueda\\:idInputDepartamento_filter")
            filter_input.click()
            time.sleep(0.3)

            # 4) Escribir "Antioquia" carácter a carácter — PrimeFaces filtra en tiempo real
            filter_input.type("Antioquia", delay=80)
            time.sleep(1.5)
            save_debug_screenshot(page, "03_antioquia_escrito")

            # 5) Clic DIRECTO en la primera fila visible del panel (exactamente "Antioquia")
            #    Usamos JS para hacer clic en la primera <td> o <li> cuyo texto sea EXACTAMENTE "Antioquia"
            clicked = page.evaluate("""
                (function() {
                    var panel = document.getElementById('form-busqueda:idInputDepartamento_panel');
                    if (!panel) return 'ERROR: panel not found';
                    var rows = Array.from(panel.querySelectorAll('tr td, li'));
                    var visible = rows.filter(function(r) { return r.offsetParent !== null; });
                    for (var i = 0; i < visible.length; i++) {
                        var txt = visible[i].innerText ? visible[i].innerText.trim() : '';
                        if (txt === 'Antioquia') {
                            visible[i].click();
                            return 'clicked: ' + txt;
                        }
                    }
                    var avail = visible.slice(0,5).map(function(r){ return r.innerText ? r.innerText.trim() : ''; }).join(' | ');
                    return 'not_found. Visible rows: ' + avail;
                })()
            """)
            print(f"  Selección Antioquia: {clicked}")

            # 6) Esperar que el panel se cierre y el AJAX de resultados complete
            page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(2)
            save_debug_screenshot(page, "04_antioquia_seleccionada")


            # Verificar que el label del dropdown ya muestre "Antioquia"
            label_text = page.locator("#form-busqueda\\:idInputDepartamento_label").inner_text()
            print(f"  Label Departamento/Municipio ahora muestra: '{label_text}'")

            # Confirmar resultados
            count_vd = page.locator("a, button").filter(has_text="Ver detalle").count()
            print(f"  Botones 'Ver detalle' en pantalla: {count_vd}")
            save_debug_screenshot(page, "05_resultados_listados")

            # --- Loop de paginación ---
            current_page = 1
            max_pages = 20

            while True:
                print(f"Extrayendo datos de la página {current_page}...")

                try:
                    page.wait_for_selector("a:has-text('Ver detalle'), button:has-text('Ver detalle')", timeout=10000)
                except PlaywrightTimeoutError:
                    print(f"  Sin vacantes en página {current_page}. Fin.")
                    break

                # Extraer datos básicos visibles en todas las tarjetas (sin expandir)
                basic_cards = get_visible_card_data(page)
                print(f"  → {len(basic_cards)} vacantes en página {current_page}")

                # Expandir cada tarjeta para obtener Establecimiento/Sede
                for i, card_data in enumerate(basic_cards):
                    try:
                        # Tomar siempre el primer "Ver detalle" disponible
                        ver_btn = page.locator("a, button").filter(has_text="Ver detalle").first
                        ver_btn.scroll_into_view_if_needed()
                        ver_btn.click()

                        # Esperar que aparezca "Ocultar detalle"
                        try:
                            page.wait_for_selector("a:has-text('Ocultar'), button:has-text('Ocultar')", timeout=5000)
                            time.sleep(0.5)
                        except PlaywrightTimeoutError:
                            pass

                        # Extraer datos del detalle expandido
                        extra = get_expanded_card_details(page)
                        if extra:
                            card_data.update(extra)

                        print(f"    + {card_data.get('Cargo','?')} | {card_data.get('Municipio','?')} | {card_data.get('Establecimiento','?')}")
                        plazas.append(card_data)

                        # Contraer
                        ocultar = page.locator("a, button").filter(has_text="Ocultar").first
                        if ocultar.is_visible():
                            ocultar.click()
                            time.sleep(0.5)

                    except Exception as err:
                        print(f"    Error tarjeta {i}: {err}")
                        plazas.append(card_data)  # Guardar al menos los básicos
                        continue

                save_debug_screenshot(page, f"pag_{current_page}_extraida")

                # Paginar
                next_btn = page.locator(".ui-paginator-next")
                if next_btn.count() == 0:
                    break
                next_class = next_btn.first.get_attribute("class") or ""
                if "ui-state-disabled" in next_class or current_page >= max_pages:
                    print(f"Última página ({current_page}). Fin.")
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

    print(f"Scraping finalizado. Total vacantes: {len(plazas)}")
    return plazas


def get_visible_card_data(page):
    """Extrae datos básicos visibles de todas las tarjetas sin expandir."""
    # Nota: usamos un string JS sin comillas simples con \n para evitar SyntaxError
    JS = """
    (function() {
        var detailBtns = Array.from(document.querySelectorAll('a, button')).filter(function(el) {
            return el.innerText && el.innerText.trim() === 'Ver detalle';
        });

        function extractFromCard(btn) {
            var card = btn;
            for (var j = 0; j < 12; j++) {
                if (!card.parentElement) break;
                card = card.parentElement;
                if (card.querySelectorAll('a, button').length >= 2) break;
            }

            var rawText = (card.innerText || '');
            var lines = rawText.split(/\\r?\\n/).map(function(l) { return l.trim(); }).filter(Boolean);

            function after(label) {
                var lLabel = label.toLowerCase();
                for (var i = 0; i < lines.length; i++) {
                    var lLine = lines[i].toLowerCase();
                    if (lLine.indexOf(lLabel) === 0) {
                        var inline = lines[i].substring(label.length).replace(/^\\s*:\\s*/, '').trim();
                        if (inline) return inline;
                        if (i + 1 < lines.length) return lines[i + 1];
                    }
                }
                return 'N/A';
            }
            return {
                Cargo: lines.length > 0 ? lines[0] : after('Cargo'),
                'Tipo Priorización': after('tipo priorizaci') !== 'N/A' ? after('tipo priorizaci') : 'N/A',
                Area: after('área') !== 'N/A' ? after('área') : (after('area') !== 'N/A' ? after('area') : 'N/A'),
                Municipio: after('municipio'),
                'Cierre Vacante': after('cierre vacante') !== 'N/A' ? after('cierre vacante') : after('cierre'),
                Postulados: after('postulados'),
                Zona: after('zona'),
                Departamento: after('departamento'),
                Secretaria: after('secretar')
            };
        }

        return detailBtns.map(function(btn) { return extractFromCard(btn); });
    })()
    """
    try:
        return page.evaluate(JS) or []
    except Exception as e:
        print(f"  Error get_visible_card_data: {e}")
        return []


def get_expanded_card_details(page):
    """Extrae datos del detalle expandido (Establecimiento, Sede, Dirección)."""
    JS = """
    (function() {
        var ocultarBtns = Array.from(document.querySelectorAll('a, button')).filter(function(el) {
            return el.innerText && el.innerText.trim().toLowerCase().indexOf('ocultar') >= 0;
        });
        if (ocultarBtns.length === 0) return null;

        var btn = ocultarBtns[0];
        var card = btn;
        for (var j = 0; j < 12; j++) {
            if (!card.parentElement) break;
            card = card.parentElement;
            if (card.querySelectorAll('a, button').length >= 2) break;
        }

        var lines = (card.innerText || '').split(/\\r?\\n/).map(function(l) { return l.trim(); }).filter(Boolean);

        function after(label) {
            var lLabel = label.toLowerCase();
            for (var i = 0; i < lines.length; i++) {
                var lLine = lines[i].toLowerCase();
                if (lLine.indexOf(lLabel) === 0) {
                    var inline = lines[i].substring(label.length).replace(/^\\s*:\\s*/, '').trim();
                    if (inline) return inline;
                    if (i + 1 < lines.length) return lines[i + 1];
                }
            }
            return 'N/A';
        }

        return {
            Establecimiento: after('establecimiento educativo') !== 'N/A' ? after('establecimiento educativo') : after('establecimiento'),
            Sede: after('sede'),
            'Zona Detalle': after('zona'),
            Barrio: after('barrio'),
            Direccion: after('direcci') !== 'N/A' ? after('direcci') : 'N/A',
            'Calendario Educativo': after('calendario educativo')
        };
    })()
    """
    try:
        return page.evaluate(JS)
    except Exception as e:
        print(f"  Error get_expanded_card_details: {e}")
        return None
