from scraper import run_scraper
from state_manager import filter_new_plazas, export_to_excel
from notifier import send_telegram_message

def main():
    print("Iniciando proceso de recolección de vacantes en Sistema Maestro...")
    try:
        scraped_plazas = run_scraper()
        
        if not scraped_plazas:
            print("No se han extraído vacantes en esta ejecución o hubo un problema cargando la tabla.")
            return

        print(f"Búsqueda inicializada con éxito. Se capturaron {len(scraped_plazas)} vacantes en las páginas exploradas.")
        
        new_plazas = filter_new_plazas(scraped_plazas)
        
        if len(new_plazas) > 0:
            print(f"¡Atención! Se han encontrado {len(new_plazas)} vacantes completamente NUEVAS.")
            export_to_excel(new_plazas)
            send_telegram_message(new_plazas)
        else:
            print("No hay plazas nuevas en esta ejecución. El estado se mantiene igual. Finalizando de forma silenciosa...")
            
    except Exception as e:
        print(f"El proceso falló de forma crítica tras los reintentos automáticos: {e}")

if __name__ == "__main__":
    main()
