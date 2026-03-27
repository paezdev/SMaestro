import os
import requests

def send_telegram_message(new_plazas):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("Credenciales de Telegram no encontradas en las variables de entorno. Evadiendo notificación.")
        return
        
    if not new_plazas:
        print("No hay plazas nuevas para notificar.")
        return
        
    count = len(new_plazas)
    message = f"🚨 *Nuevas Vacantes Docentes en Sistema Maestro: {count}* 🚨\n\n"
    
    # Mostrar solo las primeras 10 para no exceder límites de mensaje en Telegram
    limit = 10
    for idx, plaza in enumerate(new_plazas[:limit]):
        message += f"🔹 *Cargo:* {plaza.get('Cargo', 'N/A')}\n"
        message += f"📊 *Postulados:* {plaza.get('Postulados', 'N/A')}\n"
        message += f"⭐ *Priorización:* {plaza.get('Tipo Priorización', 'N/A')}\n"
        message += f"📅 *Cierre:* {plaza.get('Cierre Vacante', 'N/A')}\n"
        message += f"📚 *Área:* {plaza.get('Area', 'N/A')}\n"
        message += f"🏢 *Secretaría:* {plaza.get('Secretaria', 'N/A')}\n"
        message += f"📍 *Municipio:* {plaza.get('Municipio', 'N/A')} ({plaza.get('Departamento', 'N/A')})\n"
        message += f"🏫 *Establecimiento:* {plaza.get('Establecimiento', 'N/A')}\n"
        message += f"🚪 *Sede:* {plaza.get('Sede', 'N/A')}\n"
        message += f"🗺️ *Zona:* {plaza.get('Zona', 'N/A')} (Detalle: {plaza.get('Zona Detalle', 'N/A')})\n"
        message += f"🏘️ *Barrio:* {plaza.get('Barrio', 'N/A')} | *Dir:* {plaza.get('Direccion', 'N/A')}\n"
        message += f"🗓️ *Calendario:* {plaza.get('Calendario Educativo', 'N/A')}\n"
        message += "------\n"
        
    if count > limit:
        message += f"\n... y {count - limit} vacantes más. Revisa el archivo de Excel en el repositorio de GitHub."
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("Notificación de Telegram enviada exitosamente.")
    except requests.exceptions.HTTPError as errh:
        print ("Http Error:",errh)
    except requests.exceptions.ConnectionError as errc:
        print ("Error Connecting:",errc)
    except requests.exceptions.Timeout as errt:
        print ("Timeout Error:",errt)
    except requests.exceptions.RequestException as err:
        print ("Oops: Something Else",err)
