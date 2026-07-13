"""
servidor.py — API HTTP de Lumen (Agente 04 - Copilot) para el frontend React.

Expone el chat de Lumen por HTTP, con memoria de conversacion por sesion (ver src/memoria.py).
No sustituye el contrato de integracion real del proyecto (ejecutar_agente(payload) en
src/agente.py, que sigue siendo el punto de integracion estable) -- esta es una capa pensada
especificamente para que el frontend React pueda mandar preguntas y recibir respuestas en JSON,
con memoria conversacional igual que main.py, pero por sesion de navegador en vez de por
proceso de consola.

Arrancar:
    cd lumen_agente_04
    pip install -r requirements.txt
    python servidor.py

Por defecto escucha en http://localhost:5001. El puerto se puede cambiar con la variable de
entorno PORT en .env. (Se usa el 5001 para no chocar con otros servidores de desarrollo
habituales, como el 5000 de Flask por defecto o el 3000 del frontend React.)

Modo debug: OFF por defecto a proposito. El reloader/debugger de Flask (Werkzeug) expone una
consola interactiva que permite ejecutar codigo arbitrario si el servidor es accesible desde
fuera -- es una via de RCE, no debe quedarse activada por defecto ni llegar a produccion. Para
el desarrollo local, activa recarga automatica poniendo FLASK_DEBUG=true en .env.

Endpoints:
    GET  /              -> estado del servidor (health check)
    POST /chat           -> body: {"sesion_id": "..." (opcional), "pregunta": "..."}
                             Si no se manda sesion_id (o no existe todavia), se crea una nueva y
                             se devuelve en la respuesta -- el frontend debe guardarla (p.ej. en
                             el estado de React) y reenviarla en las siguientes peticiones de esa
                             misma conversacion para conservar la memoria.
                             Si "pregunta" es "salir" (o "exit"/"quit"), no se trata como una
                             pregunta sobre datos: se borra la entrada de _sesiones de esa sesion
                             (memoria eliminada de RAM por completo) y se devuelve una confirmacion
                             con "sesion_cerrada": true. Es memoria TEMPORAL por diseno: vive solo
                             mientras dura la conversacion, igual que en main.py (consola), donde
                             "salir" termina el proceso y con el, la memoria en RAM.
    POST /chat/reset      -> body: {"sesion_id": "..."} -> olvida el contexto de esa sesion (la
                             sesion sigue existiendo, solo se vacia id_evento_actual/historial) --
                             uso pensado para un boton "nueva conversacion" sin cerrar el chat.
                             Para borrar la sesion entera, usar la palabra "salir" en /chat.

Nota: una sesion que nadie cierra con "salir" tambien se borra sola tras SESION_TTL_HORAS de
inactividad (6h por defecto) -- ver "Expiracion de sesiones" mas abajo.

Nota de seguridad/alcance: las sesiones viven SOLO en memoria del proceso (un dict de Python).
Si el servidor se reinicia, todas las conversaciones en curso se pierden. Es una limitacion
aceptada para esta fase de demo -- no es un almacen productivo ni persistente. Cuando haya un
backend real, esto se sustituye por sesiones respaldadas por ese backend (Redis, BD, etc.), sin
tocar src/agente.py ni src/memoria.py.

Expiracion de sesiones (TTL): una sesion que nadie borra explicitamente con "salir" (p.ej. el
usuario simplemente cierra la pestaña del navegador) se queda en el diccionario _sesiones para
siempre mientras el proceso viva -- con trafico real eso es una fuga de memoria lenta. Para
evitarlo, cada sesion recuerda cuando fue su ultima peticion (_ultimo_acceso) y las sesiones
inactivas mas de SESION_TTL_HORAS (variable de entorno, 6 horas por defecto) se purgan solas en
cada peticion a GET / o POST /chat. Es deliberadamente una purga perezosa (sin hilo en segundo
plano ni scheduler) -- correcta y suficiente para el volumen de una demo; si el trafico creciera,
esto se moveria al mismo backend externo (Redis con expiracion nativa) mencionado arriba.
"""

import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify
from werkzeug.exceptions import HTTPException

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))  # permite "from src.agente import ..." y "from config import ..."

from src.agente import ejecutar_agente  # noqa: E402
from src.memoria import MemoriaConversacion, construir_payload  # noqa: E402
from config.settings import SETTINGS  # noqa: E402

app = Flask(__name__)

# CORS: permite que el frontend React (otro puerto, p.ej. localhost:3000) llame a esta API desde
# el navegador. Sin esto, el navegador bloquea las peticiones aunque el servidor si responda.
try:
    from flask_cors import CORS
    CORS(app)
except ImportError:
    print("Aviso: flask-cors no instalado. El frontend en el navegador puede fallar por CORS.")

# Memoria de conversacion por sesion (sesion_id -> MemoriaConversacion). Vive solo en RAM del
# proceso -- ver nota de seguridad/alcance en la cabecera del archivo.
_sesiones = {}

# Timestamp (time.time()) de la ultima peticion de cada sesion -- se usa solo para calcular que
# sesiones llevan inactivas mas de SESION_TTL_HORAS y purgarlas. Diccionario aparte en vez de
# meter el timestamp dentro de MemoriaConversacion para no tocar src/memoria.py (compartido con
# main.py, que no tiene ni necesita este concepto de expiracion).
_ultimo_acceso = {}

# Cuanto tiempo de inactividad tiene que pasar para considerar una sesion abandonada y borrarla.
# Configurable via .env (SESION_TTL_HORAS); 6 horas por defecto -- suficiente para una sesion de
# trabajo normal sin dejar sesiones abandonadas acumulandose indefinidamente.
SESION_TTL_SEGUNDOS = int(SETTINGS.get("SESION_TTL_HORAS", "6") or "6") * 3600

# Palabras que el usuario puede escribir DENTRO del chat (no como llamada aparte a /chat/reset)
# para cerrar su sesion y borrar su memoria de conversacion. Mismo vocabulario que main.py
# (chat de consola) para que el comportamiento sea identico en los dos frontends de Lumen.
PALABRAS_SALIR = {"salir", "exit", "quit"}


def _flag_activado(valor) -> bool:
    """True si una variable de entorno de tipo booleano esta activada ('1', 'true', 'yes', 'on')."""
    return str(valor or "").strip().lower() in {"1", "true", "yes", "on"}


def _purgar_sesiones_expiradas():
    """
    Borra sesiones cuya ultima peticion fue hace mas de SESION_TTL_SEGUNDOS. Se llama al
    principio de cada peticion a GET / y POST /chat -- purga perezosa, sin hilo en segundo plano
    (ver nota de expiracion de sesiones en la cabecera del archivo).
    """
    ahora = time.time()
    expiradas = [
        sid for sid, ultimo in _ultimo_acceso.items()
        if ahora - ultimo > SESION_TTL_SEGUNDOS
    ]
    for sid in expiradas:
        _sesiones.pop(sid, None)
        _ultimo_acceso.pop(sid, None)


def _obtener_memoria(sesion_id):
    if sesion_id not in _sesiones:
        _sesiones[sesion_id] = MemoriaConversacion()
    _ultimo_acceso[sesion_id] = time.time()
    return _sesiones[sesion_id]


def _error(codigo, mensaje, http=400):
    return jsonify({"error": True, "codigo": codigo, "mensaje": mensaje}), http


@app.get("/")
def inicio():
    _purgar_sesiones_expiradas()
    return jsonify({
        "servicio": "Lumen - Agente 04 - Copilot",
        "estado": "en marcha",
        "sesiones_activas": len(_sesiones),
        "sesion_ttl_horas": SESION_TTL_SEGUNDOS / 3600,
        "prueba": 'POST /chat con {"pregunta": "..."}',
    })


@app.post("/chat")
def chat():
    _purgar_sesiones_expiradas()

    cuerpo = request.get_json(silent=True) or {}
    pregunta = (cuerpo.get("pregunta") or "").strip()

    if not pregunta:
        return _error("PREGUNTA_VACIA", "Falta el campo 'pregunta'.")

    sesion_id = cuerpo.get("sesion_id") or str(uuid.uuid4())

    # "salir" (o sinonimos) escrito como mensaje normal del chat: a diferencia de POST
    # /chat/reset (que solo reinicia el contexto pero mantiene la sesion viva para seguir
    # preguntando), esto BORRA la entrada de _sesiones por completo -- la memoria de esa
    # conversacion deja de existir en RAM, no solo se vacia. No se llama a ejecutar_agente:
    # es una instruccion de la capa de chat, no una pregunta sobre datos de Agora.
    if pregunta.lower() in PALABRAS_SALIR:
        _sesiones.pop(sesion_id, None)
        _ultimo_acceso.pop(sesion_id, None)
        return jsonify({
            "sesion_id": sesion_id,
            "resumen": "Sesion cerrada: se ha eliminado la memoria de esta conversacion.",
            "bloqueos_detectados": [],
            "requiere_validacion_humana": False,
            "nivel_riesgo": "bajo",
            "datos_detectados": {},
            "id_evento_actual": None,
            "sesion_cerrada": True,
            "errores": [],
        })

    memoria = _obtener_memoria(sesion_id)

    id_evento, _usando_memoria, nombres_ambiguos = memoria.resolver_id_evento(pregunta)
    if nombres_ambiguos:
        return jsonify({
            "sesion_id": sesion_id,
            "resumen": (
                "Hay mas de un evento que coincide con lo que preguntas: " +
                ", ".join(nombres_ambiguos) + ". ¿A cual te refieres?"
            ),
            "bloqueos_detectados": ["nombre de evento ambiguo"],
            "requiere_validacion_humana": False,
            "nivel_riesgo": "bajo",
            "datos_detectados": {"eventos_candidatos": nombres_ambiguos},
            "id_evento_actual": memoria.id_evento_actual,
            "errores": [],
        })

    payload = construir_payload(
        id_evento, memoria.historial_para_payload(), pregunta, origen="frontend_react"
    )

    respuesta = ejecutar_agente(payload)
    memoria.registrar_turno(pregunta, respuesta, id_evento)

    return jsonify({
        "sesion_id": sesion_id,
        "resumen": respuesta.get("resumen", ""),
        "bloqueos_detectados": respuesta.get("bloqueos_detectados", []),
        "requiere_validacion_humana": respuesta.get("requiere_validacion_humana", False),
        "nivel_riesgo": respuesta.get("nivel_riesgo", "bajo"),
        "datos_detectados": respuesta.get("datos_detectados", {}),
        # Estado de memoria DESPUES de este turno -- util para que el frontend muestre algo tipo
        # "hablando del evento 12" de forma persistente, no solo en el turno que lo detecto.
        "id_evento_actual": memoria.id_evento_actual,
        "errores": respuesta.get("errores", []),
    })


@app.post("/chat/reset")
def chat_reset():
    cuerpo = request.get_json(silent=True) or {}
    sesion_id = cuerpo.get("sesion_id")

    if not sesion_id:
        return _error("FALTA_SESION_ID", "Falta el campo 'sesion_id'.")

    if sesion_id in _sesiones:
        _sesiones[sesion_id].reiniciar()
        _ultimo_acceso[sesion_id] = time.time()

    return jsonify({"ok": True, "sesion_id": sesion_id})


# Sonda uniforme del sistema (misma forma que Jano, Vigil y Operis): la usan
# el gateway y comprobar_salud.sh.
@app.get("/health")
def health():
    return jsonify({"estado": "ok", "hora": datetime.now().isoformat()})


@app.errorhandler(404)
def no_encontrado(e):
    return _error("RUTA_NO_ENCONTRADA", "Esa ruta no existe.", 404)


# Los demas errores HTTP (405...) tambien salen en JSON conservando su codigo.
@app.errorhandler(HTTPException)
def error_http(e):
    return _error(f"HTTP_{e.code}", e.description, e.code)


# Si el agente revienta, el front recibe el contrato de error en JSON, nunca
# la pagina HTML de error de Flask.
@app.errorhandler(Exception)
def error_interno(e):
    return _error("ERROR_INTERNO", str(e), 500)


if __name__ == "__main__":
    # debug OFF por defecto (el debugger de Werkzeug es una via de RCE si el servidor es
    # accesible). Para recarga automatica en desarrollo local: FLASK_DEBUG=true en .env.
    debug = _flag_activado(SETTINGS.get("FLASK_DEBUG"))
    port = int(SETTINGS.get("PORT", "5001") or "5001")
    app.run(debug=debug, port=port)
