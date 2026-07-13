import os
import logging
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

import database

# Cargar variables de entorno
load_dotenv()

# Configuración de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend_agentes")

app = FastAPI(
    title="Backstage — API de datos para Agentes",
    description="Servicio API intermedio para entregar los datos de la base de datos a los agentes (Telegram, correos).",
    version="1.0.0"
)

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos Pydantic para peticiones
class ComunicacionPayload(BaseModel):
    id_ponente: Optional[str] = None
    canal: str = Field(..., description="Canal de comunicación (telegram, email, etc.)")
    direccion: str = Field(..., description="Dirección del mensaje (entrante, saliente)")
    mensaje: str = Field(..., description="Contenido de la comunicación")
    meta: Optional[Dict[str, Any]] = None

class IncidenciaPayload(BaseModel):
    id_ponente: Optional[str] = None
    id_evento: Optional[str] = None
    tipo: str = Field(..., description="Tipo de incidencia")
    descripcion: str = Field(..., description="Detalles de la incidencia")
    urgencia: str = Field("normal", description="Urgencia (baja, normal, alta)")

# Memoria local para POSTs (dado que no tenemos permisos de escritura en el rol del agente)
registro_comunicaciones = []
registro_incidencias = []

@app.get("/")
def read_root():
    return {
        "servicio": "Backstage — API de datos para Agentes",
        "estado": "activo",
        "version": "1.0.0",
        "documentacion": "/docs",
        "endpoints": [
            "GET /api/ponentes/by-telegram/{telegram_user_id}",
            "GET /api/ponentes/{id_ponente}/eventos-activos",
            "GET /api/eventos/{id_evento}/ponentes/{id_ponente}",
            "GET /api/eventos/{id_evento}/ponentes",
            "POST /api/comunicaciones",
            "POST /api/incidencias"
        ]
    }

@app.get("/api/ponentes/by-telegram/{telegram_user_id}")
def get_ponente_by_telegram(telegram_user_id: str):
    logger.info(f"Petición GET /api/ponentes/by-telegram/{telegram_user_id}")
    ponente = database.obtener_ponente_por_telegram(telegram_user_id)
    if not ponente:
        raise HTTPException(
            status_code=404, 
            detail=f"Ningún ponente está vinculado al usuario de Telegram {telegram_user_id}"
        )
    return ponente

@app.get("/api/ponentes/{id_ponente}/eventos-activos")
def get_eventos_activos_ponente(id_ponente: str):
    logger.info(f"Petición GET /api/ponentes/{id_ponente}/eventos-activos")
    # Intentamos retornar la lista de eventos activos. Si no hay eventos, devuelve []
    return database.obtener_eventos_activos_ponente(id_ponente)

@app.get("/api/eventos/{id_evento}/ponentes/{id_ponente}")
def get_info_ponente_evento(id_evento: str, id_ponente: str):
    logger.info(f"Petición GET /api/eventos/{id_evento}/ponentes/{id_ponente}")
    info = database.obtener_info_ponente_evento(id_ponente, id_evento)
    if not info:
        raise HTTPException(
            status_code=404, 
            detail=f"No se encontró logística para el ponente {id_ponente} en el evento {id_evento}"
        )
    return info

@app.get("/api/eventos/{id_evento}/ponentes")
def get_ponentes_evento(id_evento: str):
    logger.info(f"Petición GET /api/eventos/{id_evento}/ponentes")
    ponentes = database.obtener_ponentes_evento(id_evento)
    return {
        "ok": True,
        "data": ponentes
    }

@app.post("/api/comunicaciones", status_code=status.HTTP_201_CREATED)
def post_comunicacion(payload: ComunicacionPayload):
    logger.info(f"Petición POST /api/comunicaciones: {payload}")
    comunicacion = payload.model_dump()
    comunicacion["id"] = len(registro_comunicaciones) + 1
    registro_comunicaciones.append(comunicacion)
    
    # También lo sacamos por consola como log
    logger.info(f"[COMUNICACIÓN REGISTRADA] {comunicacion}")
    
    return {
        "ok": True,
        "mensaje": "Comunicación registrada con éxito (memoria local)",
        "data": comunicacion
    }

@app.post("/api/incidencias", status_code=status.HTTP_201_CREATED)
def post_incidencia(payload: IncidenciaPayload):
    logger.info(f"Petición POST /api/incidencias: {payload}")
    incidencia = payload.model_dump()
    incidencia["id"] = len(registro_incidencias) + 1
    registro_incidencias.append(incidencia)
    
    # También lo sacamos por consola como log
    logger.warning(f"[INCIDENCIA REGISTRADA] {incidencia}")
    
    return {
        "ok": True,
        "mensaje": "Incidencia registrada con éxito (memoria local)",
        "data": incidencia
    }

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Error interno no controlado: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"ok": False, "message": "Error interno del servidor de agentes", "detail": str(exc)}
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "5004"))
    host = os.getenv("HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=port)
