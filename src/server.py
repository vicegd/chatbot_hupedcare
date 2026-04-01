import os
import time
import yaml
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# CARGADOR DE CONFIGURACIÓN
def cargar_config():
    with open("./config/config.yaml", "r") as f:
        return yaml.safe_load(f)

config = cargar_config()

app = FastAPI()
client = OpenAI(
    base_url=config['ai']['base_url'], 
    api_key=os.getenv("GROQ_API_KEY")
)

# MEMORIA COMPARTIDA
class SistemaIA:
    contexto = ""
    ultima_actualizacion = 0

    @classmethod
    def cargar_contexto(cls):
        print(f"--- [SISTEMA] Leyendo {config['storage']['data_folder']} ---")
        path = config['storage']['data_folder']
        nuevo_contexto = ""
        if os.path.exists(path):
            for f in os.listdir(path):
                if f.endswith(".txt"): # Filtro simple para solo leer texto
                    with open(os.path.join(path, f), "r", encoding="utf-8") as file:
                        nuevo_contexto += f"\nORIGEN: {f}\n{file.read()}\n"
        cls.contexto = nuevo_contexto
        cls.ultima_actualizacion = time.time()

@app.on_event("startup")
async def startup_event():
    SistemaIA.cargar_contexto()

class Consulta(BaseModel):
    pregunta: str

@app.post("/preguntar")
async def responder_usuario(item: Consulta):
    # Verificamos si toca refrescar según el YAML
    if time.time() - SistemaIA.ultima_actualizacion > config['storage']['refresh_interval_seconds']:
        SistemaIA.cargar_contexto()

    try:
        response = client.chat.completions.create(
            model=config['ai']['model'],
            messages=[
                {"role": "system", "content": f"{config['ai']['system_prompt']}\nContexto:\n{SistemaIA.contexto}"},
                {"role": "user", "content": item.pregunta}
            ]
        )
        return {"respuesta": response.choices[0].message.content}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config['server']['host'], port=config['server']['port'])