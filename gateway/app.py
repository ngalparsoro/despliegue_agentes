"""Gateway de data (:5003) — una sola URL para el front, agentes detrás.

Sigue el patrón del backend unificado de la v4 (endpoints_v4.md): los agentes
se consumen bajo `/agentes/<nombre>/...`, pero aquí NO se cargan en el mismo
proceso (aquello obligaba a resolver colisiones de paquetes `src`/`config`
entre agentes): cada agente sigue siendo su propio servidor y el gateway
reenvía la petición por HTTP. Ventajas para la integración:

- El front integra contra UNA base (`http://localhost:5003`) y rutas
  definitivas, aunque el agente de detrás aún no exista.
- Los agentes que faltan por llegar responden con un STUB que tiene la
  forma real del contrato (marcado con `"_stub": true`); cuando llegue el
  definitivo, se registra su URL en AGENTES y el stub se retira SIN que el
  front cambie nada.

Arrancar:  pip install -r requirements.txt && python app.py   (o vía
../arrancar_todo.sh, que lo levanta junto al resto con el .env común).
"""

# traigo os para leer el puerto del entorno
import os
# traigo lo necesario para lanzar y vigilar los ciclos de Garum
import json
import subprocess
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path

# traigo FastAPI para declarar la API y httpx para reenviar peticiones
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

app = FastAPI(
    title="Agentes_Eventos — gateway de data",
    description="Una sola URL para el front: agentes reales por proxy y stubs de los pendientes.",
    version="1.0.0",
)

# CORS abierto (fase demo): el front en otro puerto puede llamar sin bloqueo
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---------------------------------------------------------------------
# Registro de agentes REALES: nombre → (url base, ruta de health)
# Cuando llegue un agente definitivo que hoy es stub, se añade aquí y se
# borra su entrada de STUBS_PENDIENTES. Nada más.
# ---------------------------------------------------------------------
AGENTES = {
    "lumen": {"base": "http://127.0.0.1:5001", "health": "/"},
    "operis": {"base": "http://127.0.0.1:5002", "health": "/"},
    "jano": {"base": "http://127.0.0.1:8001", "health": "/health"},
    "vigil": {"base": "http://127.0.0.1:8000", "health": "/health"},
}

# Backend de datos para agentes (no es un agente, pero es parte del mapa)
BACKEND_AGENTES = {"base": "http://127.0.0.1:5004", "health": "/"}

# Agentes PENDIENTES de recibir en versión definitiva: responden 501 con
# un mensaje claro. Vacío desde el 13/07: confirmado que Vigil ES el agente
# de alertas de la v4 (con su nombre definitivo) — los 6 agentes están.
STUBS_PENDIENTES: dict[str, str] = {}

# Garum (gestor de correos) no es un servidor: se ejecuta por CICLOS
# (lee Gmail vía Composio, clasifica y deja borradores; nunca envía).
# El gateway lo lanza como proceso aparte, igual que hace Vigil con sus
# ejecuciones, y guarda el estado en memoria por id.
GARUM_DIR = Path(__file__).resolve().parent.parent / "Garum_gestorcorreos" / "agente_gestor_correos"
_CICLOS_GARUM: dict[str, dict] = {}

# tiempo máximo de espera al reenviar (Operis con LLM puede tardar)
TIMEOUT_PROXY = 60.0


def _error(codigo: str, mensaje: str, http: int = 400) -> JSONResponse:
    # mismo formato de error común que en v3/v4
    return JSONResponse({"error": True, "codigo": codigo, "mensaje": mensaje}, status_code=http)


# ---------------------------------------------------------------------
# Garum: POST /agentes/garum/ciclos lanza un ciclo de gestión de correos
# en segundo plano y devuelve un id; GET /agentes/garum/ciclos/{id}
# consulta cómo va. Mismo patrón que las ejecuciones de Vigil.
# ---------------------------------------------------------------------
def _vigilar_ciclo_garum(id_ciclo: str, proceso: subprocess.Popen):
    # espero al proceso sin bloquear la API y guardo su resultado
    salida, _ = proceso.communicate()
    ciclo = _CICLOS_GARUM[id_ciclo]
    ciclo["terminado_en"] = datetime.now().isoformat()
    if proceso.returncode != 0:
        ciclo["estado"] = "error"
        ciclo["detalle"] = salida[-2000:]  # el final del log, donde está el error
        return
    ciclo["estado"] = "terminado"
    # main.py imprime trazas y al final el JSON del resultado: me quedo
    # con lo que hay tras la última línea de "RESULTADO DEL CICLO"
    try:
        _, _, cola = salida.rpartition("RESULTADO DEL CICLO =====")
        ciclo["resultado"] = json.loads(cola.strip())
    except (ValueError, json.JSONDecodeError):
        ciclo["detalle"] = salida[-2000:]


@app.post("/agentes/garum/ciclos", status_code=202)
def lanzar_ciclo_garum():
    if not (GARUM_DIR / "main.py").exists():
        return _error("AGENTE_NO_ENCONTRADO", f"No encuentro main.py de Garum en {GARUM_DIR}.", http=500)
    # si ya hay un ciclo en marcha, no lanzo otro encima (Gmail es compartido)
    for id_previo, ciclo in _CICLOS_GARUM.items():
        if ciclo["estado"] == "en_marcha":
            return _error("CICLO_EN_MARCHA", f"Ya hay un ciclo en marcha ({id_previo}). Espera a que termine.", http=409)
    id_ciclo = uuid.uuid4().hex[:12]
    proceso = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=GARUM_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    _CICLOS_GARUM[id_ciclo] = {"estado": "en_marcha", "lanzado_en": datetime.now().isoformat()}
    threading.Thread(target=_vigilar_ciclo_garum, args=(id_ciclo, proceso), daemon=True).start()
    return {"id_ciclo": id_ciclo, "estado": "en_marcha", "consultar": f"/agentes/garum/ciclos/{id_ciclo}"}


@app.get("/agentes/garum/ciclos/{id_ciclo}")
def estado_ciclo_garum(id_ciclo: str):
    ciclo = _CICLOS_GARUM.get(id_ciclo)
    if not ciclo:
        return _error("CICLO_NO_ENCONTRADO", f"No conozco el ciclo '{id_ciclo}' (el registro vive en memoria: se pierde al reiniciar).", http=404)
    return {"id_ciclo": id_ciclo, **ciclo}


# ---------------------------------------------------------------------
# Alias de compatibilidad v4 (mismas rutas en la raíz): el front actual
# puede migrar al gateway cambiando solo la URL base.
# ---------------------------------------------------------------------
@app.post("/chat")
async def alias_chat(request: Request):
    return await proxy_agente("lumen", "chat", request)


@app.post("/chat/reset")
async def alias_chat_reset(request: Request):
    return await proxy_agente("lumen", "chat/reset", request)


@app.post("/autocompletar")
async def alias_autocompletar(request: Request):
    return await proxy_agente("operis", "autocompletar", request)


# la v4 reservó /agentes/alertas/... para el agente de Roberto; confirmado
# que ese agente es Vigil con su nombre final, la ruta queda como alias
@app.api_route("/agentes/alertas/{ruta:path}", methods=["GET", "POST"])
async def alias_alertas(ruta: str, request: Request):
    return await proxy_agente("vigil", ruta, request)


# ---------------------------------------------------------------------
# Salud agregada: el smoke test y el front pueden ver todo de un vistazo
# ---------------------------------------------------------------------
@app.get("/salud")
async def salud():
    estado = {}
    async with httpx.AsyncClient(timeout=3.0) as cliente:
        # pregunto a cada agente real y al backend de agentes
        piezas = dict(AGENTES)
        piezas["backend_agentes"] = BACKEND_AGENTES
        for nombre, datos in piezas.items():
            try:
                r = await cliente.get(datos["base"] + datos["health"])
                estado[nombre] = "ok" if r.status_code == 200 else f"http {r.status_code}"
            except httpx.HTTPError:
                estado[nombre] = "no responde"
    # Garum no es residente: informo de si hay ciclo en marcha o no
    en_marcha = any(c["estado"] == "en_marcha" for c in _CICLOS_GARUM.values())
    estado["garum"] = "ciclo en marcha" if en_marcha else "bajo demanda"
    # los pendientes sin agente detrás se marcan como tales
    for nombre in STUBS_PENDIENTES:
        estado[nombre] = "pendiente"
    return {"servicio": "gateway de data", "puerto": os.getenv("PUERTO_GATEWAY", "5003"), "agentes": estado}


@app.get("/")
def raiz():
    return {
        "servicio": "Agentes_Eventos — gateway de data",
        "documentacion": "/docs",
        "salud": "/salud",
        "agentes_reales": sorted(AGENTES),
        "bajo_demanda": ["garum (POST /agentes/garum/ciclos)"],
        "pendientes": sorted(STUBS_PENDIENTES),
    }


# ---------------------------------------------------------------------
# Proxy genérico: /agentes/<nombre>/<lo que sea> → servidor del agente
# (declarado el último para no tapar las rutas de stub de arriba)
# ---------------------------------------------------------------------
@app.api_route("/agentes/{agente}/{ruta:path}", methods=["GET", "POST"])
async def proxy_agente(agente: str, ruta: str, request: Request):
    # si es un pendiente sin stub, lo digo claro (el front sabe a qué atenerse)
    if agente in STUBS_PENDIENTES:
        return _error("AGENTE_PENDIENTE", STUBS_PENDIENTES[agente], http=501)
    if agente not in AGENTES:
        return _error("RUTA_NO_ENCONTRADA", f"No conozco el agente '{agente}'. Reales: {sorted(AGENTES)}; bajo demanda: garum.", http=404)

    destino = AGENTES[agente]["base"] + "/" + ruta
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_PROXY) as cliente:
            respuesta = await cliente.request(
                request.method,
                destino,
                params=dict(request.query_params),
                content=await request.body(),
                headers={"Content-Type": request.headers.get("Content-Type", "application/json")},
            )
    except httpx.HTTPError:
        return _error("AGENTE_CAIDO", f"El agente '{agente}' no responde en {AGENTES[agente]['base']}. ¿Está arrancado?", http=502)

    # devuelvo el cuerpo tal cual (JSON, PDF, ICS…) con su tipo y su código
    return Response(
        content=respuesta.content,
        status_code=respuesta.status_code,
        media_type=respuesta.headers.get("Content-Type", "application/json"),
    )


if __name__ == "__main__":
    import uvicorn

    puerto = int(os.getenv("PUERTO_GATEWAY", "5003"))
    print(f"gateway de data — escuchando en http://127.0.0.1:{puerto}  (docs en /docs)")
    uvicorn.run(app, host="127.0.0.1", port=puerto)
