from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from tenacity import retry, stop_after_attempt, wait_fixed
import time

URL = "https://sistemamaestro.mineducacion.gov.co/SistemaMaestro/busquedaVacantes.xhtml" # URL base aproximada, asumiendo la ruta correcta

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
            
            # Localizar el dropdown de departamento. Usamos selectores resilientes que capturan etiquetas
            print("Seleccionando Departamento ANTIOQUIA...")
            
            # Una estrategia común en Primefaces es hacer clic en la etiqueta o el trigger asociado
            try:
                # Buscamos el contenedor del menú que esté cerca del texto 'Departamento'
                page.locator("label:has-text('Departamento')").locator("..").locator(".ui-selectonemenu-trigger").first.click(timeout=10000)
            except PlaywrightTimeoutError:
                # Fallback: intentar solo con selectores de primefaces crudos si la estructura varía
                page.locator(".ui-selectonemenu-trigger").first.click()
                 
            time.sleep(1) # Esperar animación de Primefaces
            page.locator("li.ui-selectonemenu-item:has-text('ANTIOQUIA')").click()
            
            print("Haciendo clic en Buscar...")
            page.locator("button:has-text('Buscar')").click()
            
            # Esperas de 3 segundos para el AJAX de PrimeFaces
            print("Esperando 3 segundos a que cargue el data table...")
            time.sleep(3)
            page.wait_for_selector(".ui-datatable", timeout=15000)
            
            # Loop de Paginación (11 páginas o las que existan)
            current_page = 1
            max_pages = 11
            
            while True:
                print(f"Procesando página {current_page}...")
                
                # Esperar a que las filas existan
                try:
                    page.wait_for_selector(".ui-datatable-data tr.ui-widget-content", timeout=10000)
                except PlaywrightTimeoutError:
                    print("No se encontró la tabla de datos en esta página. Puede que esté vacía.")
                    break
                    
                count_rows = page.locator(".ui-datatable-data tr.ui-widget-content").count()
                
                for i in range(count_rows):
                    row = page.locator(".ui-datatable-data tr.ui-widget-content").nth(i)
                    
                    # Clic en "Ver detalle"
                    detail_btn = row.locator("button:has-text('Ver detalle'), button[title='Ver detalle'], a:has-text('Ver detalle'), button span.ui-icon-search, button:has(span:text-matches('(?i)detalle'))")
                    
                    if detail_btn.count() > 0:
                        detail_btn.first.click()
                        time.sleep(2) # Primefaces AJAX dialog loading
                        
                        try:
                            dialog = page.locator(".ui-dialog:visible")
                            dialog.wait_for(timeout=5000)
                            
                            def get_field(label_val):
                                try:
                                    # Intentar encontrar un strong, b o label que contenga el texto y buscar su valor hermano
                                    field = dialog.locator(f"*:has-text('{label_val}')").last
                                    text = field.locator("xpath=parent::*").inner_text()
                                    # Limpiar la etiqueta del texto original
                                    return text.replace(label_val, "").replace(":", "").strip()
                                except Exception:
                                    return "N/A"

                            plaza = {
                                "Cargo": get_field("Cargo"),
                                "Area": get_field("Área") or get_field("Area"),
                                "Municipio": get_field("Municipio"),
                                "Establecimiento": get_field("Establecimiento") or get_field("Sede"),
                                "Cierre Vacante": get_field("Cierre"),
                                "Postulados": get_field("Postulados")
                            }
                            
                            plazas.append(plaza)
                            
                            # Cerrar el diálogo modal
                            close_btn = dialog.locator(".ui-dialog-titlebar-close")
                            if close_btn.count() > 0:
                                close_btn.click()
                            else:
                                page.keyboard.press("Escape")
                                
                            time.sleep(1) # animacion de cerrado
                        except Exception as inner_e:
                            print(f"Error procesando fila {i}: {inner_e}")
                            page.keyboard.press("Escape") # Intentar asegurar el cierre
                
                # Validar paginación
                next_btn = page.locator(".ui-paginator-next")
                if next_btn.count() == 0 or "ui-state-disabled" in next_btn.first.get_attribute("class") or current_page >= max_pages:
                    print("Se alcanzó el límite de páginas o no hay botón 'Siguiente'. Fin de la paginación.")
                    break
                    
                print("Avanzando a la siguiente página...")
                next_btn.first.click()
                time.sleep(3) # Esperar a AJAX
                current_page += 1
                
        except Exception as e:
            print(f"Error durante el scraping: {e}")
            raise # Lanzar la excepción para activar el reintento de tenacity
        finally:
            browser.close()
            
    return plazas
