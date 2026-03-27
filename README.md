<div align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Playwright-45ba4b?style=for-the-badge&logo=Playwright&logoColor=white" alt="Playwright">
  <img src="https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white" alt="GitHub Actions">
  <img src="https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram">
  
  <h1>🤖 Automatización Sistema Maestro (Antioquia)</h1>
  <p>Un bot resiliente para la extracción automática, deduplicación y notificación instantánea de vacantes docentes enviadas a Telegram.</p>
</div>

---

## ✨ Características Principales

*   **🕵️‍♂️ Web Scraping Avanzado**: Utiliza Playwright para domar la web dinámica en _PrimeFaces_ del Ministerio de Educación.
*   **⚡ Extracción Súper Rápida**: Lógica interna ultra optimizada que simula la apertura masiva de las tarjetas en paralelo para una lectura global y sin interrupciones asíncronas de lectura.
*   **💾 Memoria de Hierro (Deduplicación)**: Guarda la huella exacta de cada vacante analizada anteriormente para **NUNCA** enviarte un mensaje duplicado. 
*   **📱 Alertas Push vía Telegram**: Redacta mensajes con formato _markdown_ impecable enviando todos los datos detallados (`Cargo`, `Municipio`, `Sede`, `Zona`, `Colegio`, `Cierre` y más).
*   **☁️ Despliegue en la Nube (Serverless)**: Corre sin descanso desde GitHub Actions en un ciclo periódico (_Cron Job_), sin consumir memoria o energía de tu PC local.

---

## 🚀 ¿Cómo funciona?

1.   Abre la web oculta del **Sistema Maestro**.
2.   Despega la lista de departamentos y localiza matemáticamente a **"Antioquia"** mediante clics nativos para activar la actualización asíncrona de las plazas disponibles en dicha zona.
3.   Navega por el esquema dinámico expandiendo la información de **Ocultar detalle** para leer cada mínimo detalle de todos los colegios a la vez.
4.   Compara los postulados con los de turnos anteriores (`vacantes_vistas.json`).
5.   Si ve colegios nuevos, las guarda en un archivo Excel (`nuevas_plazas.xlsx`) y orquesta todo hacia tu celular en el chat de Telegram. 🎉

---

## 🛠️ Instalación y Uso Local

¿Quieres probar el código de manera local en tu computador antes de pasarlo a la nube? 

1. **Clona el repositorio**
```bash
git clone https://github.com/paezdev/SMaestro.git
cd SMaestro
```

2. **Instala las dependencias principales**
```bash
pip install playwright pandas openpyxl tenacity requests
```

3. **Descarga los navegadores fantasma (Headless Browsers)**
```bash
playwright install chromium
```

4. **Agrega tus credenciales de Telegram**
Si estás en Windows, abre una consola de _PowerShell_ y pega:
```powershell
$env:TELEGRAM_BOT_TOKEN="AQUÍ_TU_TOKEN"
$env:TELEGRAM_CHAT_ID="AQUÍ_TU_ID"
```

5. **¡Enciende el Bot!**
```bash
python main.py
```

---

## ⚙️ Configuración para GitHub Actions

En tu repositorio de GitHub, dirígete a **Settings > Secrets and variables > Actions** y crea dos secretos de entorno llamados:
*   `TELEGRAM_BOT_TOKEN`: El token secreto entregado por *BotFather*.
*   `TELEGRAM_CHAT_ID`: Tu ID numérico privado.

¡Una vez guardados, el archivo de flujos automáticos `.github/workflows/scraper.yml` se encargará de hacer todo todos los días, sin que muevas un solo dedo!

---

<div align="center">
  <p><i>Construido con Python y mucha paciencia enfrentando a PrimeFaces 🚀💥</i></p>
</div>
