from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from tenacity import retry, stop_after_attempt, wait_fixed
import time

URL = "https://sistemamaestro.mineducacion.gov.co/SistemaMaestro/busquedaVacantes.xhtml"

@retry(stop=stop_after_attempt(2), wait=wait_fixed(3))
def run_scraper():
    plazas = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            print("Accediendo al Sistema Maestro...")
            page.goto(URL, timeout=60000)

            # Esperar a que el dropdown de Secretaria sea visible
            page.wait_for_selector(".ui-selectonemenu", timeout=15000)
            print("Página cargada. Seleccionando Secretaría = Antioquia...")

            # Hacer clic en el trigger del primer dropdown (Secretaria)
            page.locator(".ui-selectonemenu").first.click()
            time.sleep(1)

            # Seleccionar "Antioquia" — el sitio usa <tr> en PrimeFaces para las opciones
            page.locator("tr.ui-selectonemenu-item, li.ui-selectonemenu-item").filter(has_text="Antioquia").first.click()

            # Esperar a que la tabla se recargue (AJAX reactivo — no hay botón Buscar)
            print("Esperando recarga AJAX tras seleccionar Antioquia...")
            time.sleep(3)

            # Verificar que los resultados cargaron correctamente
            page.wait_for_selector(".vacantes-disponibles, #form-busqueda\\:tabla-vacantes, .ui-g.vacante, a:has-text('Ver detalle')", timeout=15000)
            print("Resultados de Antioquia cargados.")

            # --- Loop de paginación ---
            current_page = 1
            max_pages = 15  # límite seguro de seguridad

            while True:
                print(f"Extrayendo datos de la página {current_page}...")

                # Esperar que haya al menos un botón "Ver detalle"
                try:
                    page.wait_for_selector("a:has-text('Ver detalle'), button:has-text('Ver detalle')", timeout=10000)
                except PlaywrightTimeoutError:
                    print("No hay botones 'Ver detalle' en esta página. Fin.")
                    break

                # Obtener todos los botones/links "Ver detalle" visibles
                detail_links = page.locator("a:has-text('Ver detalle'), button:has-text('Ver detalle')")
                count = detail_links.count()
                print(f"  → {count} vacantes en esta página")

                for i in range(count):
                    try:
                        # Re-localizar para evitar referencias obsoletas del DOM
                        current_links = page.locator("a:has-text('Ver detalle'), button:has-text('Ver detalle')")
                        btn = current_links.nth(i)

                        # Desplazarse hasta el botón y hacer clic
                        btn.scroll_into_view_if_needed()
                        btn.click()
                        time.sleep(1.5)  # esperar expansión AJAX

                        # El detalle se expande inline. Buscamos el contenedor padre de este botón
                        # que ahora dice "Ocultar detalle". Extraemos desde las tarjetas visibles por índice.
                        plaza = extract_current_card_data(page, i)
                        if plaza:
                            plazas.append(plaza)

                        # Cerrar (contraer) la expansión haciendo clic en "Ocultar detalle"
                        hide_links = page.locator("a:has-text('Ocultar detalle'), button:has-text('Ocultar detalle')")
                        if hide_links.count() > 0:
                            hide_links.first.click()
                            time.sleep(0.8)

                    except Exception as err:
                        print(f"  Error en vacante {i}: {err}")
                        continue

                # --- Paginación ---
                next_btn = page.locator(".ui-paginator-next")
                if next_btn.count() == 0:
                    print("No se encontró botón de siguiente página. Fin.")
                    break

                next_class = next_btn.first.get_attribute("class") or ""
                if "ui-state-disabled" in next_class or current_page >= max_pages:
                    print(f"Fin de paginación en la página {current_page}.")
                    break

                print(f"Avanzando a la página {current_page + 1}...")
                next_btn.first.click()
                time.sleep(3)
                current_page += 1

        except Exception as e:
            print(f"Error durante el scraping: {e}")
            raise  # Activar reintento de tenacity
        finally:
            browser.close()

    print(f"Scraping finalizado. Total vacantes recolectadas: {len(plazas)}")
    return plazas


def extract_current_card_data(page, card_index):
    """
    Extrae los datos de la tarjeta que fue expandida (el 'Ver detalle' fue clickeado).
    Los datos visibles y los datos del detalle expandido se leen del DOM.
    """
    try:
        # Usar JavaScript para extraer texto de la tarjeta expandida (la que tiene "Ocultar detalle")
        plaza_js = page.evaluate("""
            () => {
                // Encontrar la tarjeta que está actualmente expandida (tiene "Ocultar detalle")
                const allLinks = Array.from(document.querySelectorAll('a, button'));
                const ocultarLink = allLinks.find(el => el.innerText && el.innerText.trim() === 'Ocultar detalle');
                if (!ocultarLink) return null;

                // Subir al contenedor padre de la tarjeta
                const card = ocultarLink.closest('.p-grid, .ui-g, div[id*="tabla-vacantes"]');
                if (!card) return null;

                // Función auxiliar para extraer texto siguiente al label
                function getField(parentEl, labelText) {
                    const allText = parentEl.innerText || '';
                    const lines = allText.split('\\n').map(l => l.trim()).filter(Boolean);
                    for (let i = 0; i < lines.length; i++) {
                        if (lines[i].includes(labelText) && i + 1 < lines.length) {
                            // Si la línea contiene el label seguido de un valor en la misma línea
                            const same = lines[i].replace(labelText + ':', '').replace(labelText, '').trim();
                            if (same) return same;
                            return lines[i+1];
                        }
                    }
                    return 'N/A';
                }

                return {
                    'Cargo': getField(card, 'Cargo'),
                    'Area': getField(card, 'Área') || getField(card, 'Area'),
                    'Municipio': getField(card, 'Municipio'),
                    'Establecimiento': getField(card, 'Establecimiento educativo') || getField(card, 'Establecimiento'),
                    'Sede': getField(card, 'Sede'),
                    'Cierre Vacante': getField(card, 'Cierre vacante') || getField(card, 'Cierre'),
                    'Postulados': getField(card, 'Postulados'),
                    'Zona': getField(card, 'Zona'),
                    'Direccion': getField(card, 'Dirección') || getField(card, 'Direccion'),
                    'Secretaria': getField(card, 'Secretaría de Educación') || getField(card, 'Secretaria'),
                };
            }
        """)
        return plaza_js
    except Exception as e:
        print(f"  Error extracting JS card data: {e}")
        return None
