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
            args=["--no-sandbox", "--disable-dev-shm-usage"]  # necesario en Linux/CI
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

            # Esperar que el dropdown de Secretaria sea visible
            page.wait_for_selector(".ui-selectonemenu", timeout=15000)
            print("Página cargada. Seleccionando Secretaría = Antioquia...")

            # Hacer clic en el primer dropdown (Secretaria)
            page.locator(".ui-selectonemenu").first.click()
            time.sleep(1.5)
            save_debug_screenshot(page, "02_dropdown_abierto")

            # Seleccionar "Antioquia"
            try:
                page.locator("tr.ui-selectonemenu-item, li.ui-selectonemenu-item").filter(has_text="Antioquia").first.click(timeout=8000)
            except PlaywrightTimeoutError:
                # Fallback: buscar por texto exacto en cualquier elemento de lista
                page.locator("[class*='selectonemenu-item']").filter(has_text="Antioquia").first.click(timeout=5000)

            print("Opción Antioquia seleccionada. Esperando recarga AJAX...")

            # Esperar a que la red quede idle (AJAX completado)
            page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(2)
            save_debug_screenshot(page, "03_antioquia_seleccionada")

            # Verificar que existan resultados usando múltiples selectores posibles
            ver_detalle_selector = "a:text('Ver detalle'), button:text('Ver detalle'), a:text-is('Ver detalle'), [id*='verDetalle'], [id*='ver-detalle']"
            try:
                page.wait_for_selector(ver_detalle_selector, timeout=15000)
                print("Resultados de Antioquia cargados.")
            except PlaywrightTimeoutError:
                save_debug_screenshot(page, "04_error_sin_resultados")
                print("ADVERTENCIA: No se encontraron botones 'Ver detalle'. Revisar screenshot 04.")
                # Intentar igualmente continuar
                pass

            save_debug_screenshot(page, "04_resultados_listados")

            # --- Loop de paginación ---
            current_page = 1
            max_pages = 15

            while True:
                print(f"Extrayendo datos de la página {current_page}...")

                # Contar cuántos links de "Ver detalle" existen con selector más amplio
                detail_links = page.locator("a, button").filter(has_text="Ver detalle")
                count = detail_links.count()

                if count == 0:
                    # Intentar con texto parcial o insensible a mayúsculas
                    detail_links = page.locator("a, button").filter(has_text="detalle")
                    count = detail_links.count()

                if count == 0:
                    print(f"  No se encontraron vacantes en la página {current_page}. Fin.")
                    save_debug_screenshot(page, f"pag_{current_page}_sin_vacantes")
                    break

                print(f"  → {count} vacantes detectadas en página {current_page}")

                for i in range(count):
                    try:
                        # Re-localizar para evitar referencias DOM obsoletas
                        current_links = page.locator("a, button").filter(has_text="Ver detalle")
                        if current_links.count() <= i:
                            break
                        btn = current_links.nth(i)
                        btn.scroll_into_view_if_needed()
                        btn.click()
                        page.wait_for_load_state("networkidle", timeout=10000)
                        time.sleep(1)

                        # Extraer datos con JavaScript
                        plaza = extract_card_data(page)
                        if plaza:
                            print(f"    Extraída: {plaza.get('Cargo','?')} | {plaza.get('Municipio','?')} | {plaza.get('Area','?')}")
                            plazas.append(plaza)
                        else:
                            print(f"    Tarjeta {i}: no se pudo extraer datos.")

                        # Contraer expansión
                        ocultar_links = page.locator("a, button").filter(has_text="Ocultar")
                        if ocultar_links.count() > 0:
                            ocultar_links.first.click()
                            page.wait_for_load_state("networkidle", timeout=8000)
                            time.sleep(0.5)

                    except Exception as err:
                        print(f"  Error procesando vacante {i}: {err}")
                        continue

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


def extract_card_data(page):
    """Extrae datos de la tarjeta actualmente expandida (con 'Ocultar detalle' visible)."""
    try:
        plaza = page.evaluate("""
            () => {
                // Encontrar tarjeta expandida buscando el "Ocultar detalle"
                const allEls = Array.from(document.querySelectorAll('a, button'));
                const ocultar = allEls.find(el => el.innerText && el.innerText.trim().toLowerCase().includes('ocultar'));
                if (!ocultar) return null;

                // Subir varios niveles hasta el contenedor de la tarjeta
                let card = ocultar.parentElement;
                for (let i = 0; i < 8; i++) {
                    if (!card) break;
                    const cls = card.className || '';
                    if (cls.includes('p-grid') || cls.includes('ui-g') || cls.includes('vacante') || card.id.includes('tabla-vacantes')) break;
                    card = card.parentElement;
                }
                if (!card) return null;

                const text = card.innerText || '';
                const lines = text.split('\\n').map(l => l.trim()).filter(Boolean);

                function after(label) {
                    for (let i = 0; i < lines.length; i++) {
                        const l = lines[i].toLowerCase();
                        if (l.startsWith(label.toLowerCase())) {
                            const inline = lines[i].substring(label.length).replace(':', '').trim();
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
                    Establecimiento: after('Establecimiento educativo') !== 'N/A' ? after('Establecimiento educativo') : after('Establecimiento'),
                    Sede: after('Sede'),
                    'Cierre Vacante': after('Cierre vacante') !== 'N/A' ? after('Cierre vacante') : after('Cierre'),
                    Postulados: after('Postulados'),
                    Zona: after('Zona'),
                    Direccion: after('Dirección') !== 'N/A' ? after('Dirección') : after('Direccion'),
                    Secretaria: after('Secretaría de Educación') !== 'N/A' ? after('Secretaría de Educación') : after('Secretaria'),
                };
            }
        """)
        return plaza
    except Exception as e:
        print(f"  Error en extract_card_data: {e}")
        return None
