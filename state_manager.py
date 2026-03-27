import json
import os
import pandas as pd

STATE_FILE = "vacantes_vistas.json"
EXCEL_FILE = "nuevas_plazas.xlsx"

def load_state():
    if not os.path.exists(STATE_FILE):
        return []
    with open(STATE_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=4, ensure_ascii=False)

def generate_id(plaza):
    # Municipio + Establecimiento + Area + Cierre_Vacante
    agrupador = f"{plaza.get('Municipio', '')}_{plaza.get('Establecimiento', '')}_{plaza.get('Area', '')}_{plaza.get('Cierre Vacante', '')}"
    # Remover espacios y pasar a mayúsculas para un ID consistente
    return agrupador.replace(" ", "").upper()

def filter_new_plazas(scraped_plazas):
    history = load_state()
    history_set = set(history)
    
    new_plazas = []
    
    for plaza in scraped_plazas:
        plaza_id = generate_id(plaza)
        if plaza_id not in history_set:
            new_plazas.append(plaza)
            history_set.add(plaza_id)
            
    # Guardar el historial actualizado
    if new_plazas:
        save_state(list(history_set))
        
    return new_plazas

def export_to_excel(new_plazas):
    if not new_plazas:
        return
        
    df_new = pd.DataFrame(new_plazas)
    
    if os.path.exists(EXCEL_FILE):
        try:
            df_existing = pd.read_excel(EXCEL_FILE)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        except Exception:
            df_combined = df_new
    else:
        df_combined = df_new
        
    df_combined.to_excel(EXCEL_FILE, index=False)
    print(f"Exportadas {len(new_plazas)} nuevas plazas a {EXCEL_FILE}")
