"""
servidor.py — API HTTP de agente_operis (autocompletar briefings) para el frontend React.

Mismo patron que Agente_04_Copilot_Raul/lumen_agente_04/servidor.py: una capa HTTP fina
pensada para que el frontend pueda mandar el texto de un briefing y recibir los campos del
evento ya extraidos, en JSON. No sustituye el contrato de integracion real del proyecto
(ejecutar_agente(payload) en src/agente.py, que sigue siendo lo que usaria el orquestador).

Arrancar:
    cd agente_operis_llm
    pip install -r requirements_servidor.txt   # flask + flask-cors (solo para este servidor)
    python servidor.py

Por defecto escucha en http://localhost:5002 (el mock de API_Nora usa el 5000 y Lumen el
5001, para poder tener los tres arrancados a la vez).

Endpoints:
    GET  /               -> estado del servidor (health check)
    POST /autocompletar  -> body flexible:
                            {
                                "id_evento": "...",              (opcional)
                                "texto_briefing": "...",         (opcional; tambien vale
                                                                   "texto", "contenido" o
                                                                   datos.texto_briefing)
                                "tipo_objetivo": "evento|cliente|ponente|espacio",
                                "bloques_a_actualizar": [...],   (opcional, ej. ["cliente"])
                                "historial_anterior": {...}      (opcional; solo se usa si
                                                                   hay id_evento)
                            }
                            Devuelve el contrato de salida comun del agente: datos_detectados
                            con los 4 bloques (evento, cliente, ponentes, nota_bene),
                            bloqueos_detectados con los campos que faltan, y
                            requiere_validacion_humana=True SIEMPRE — el front debe mostrar
                            los campos como PROPUESTA editable, nunca guardarlos solos.

Notas:
    - El unico motor disponible es "llm" (Groq); el motor de reglas se elimino. Requiere
      GROQ_API_KEY en .env — sin ella, el agente devuelve un error controlado (ver src/llm.py).
    - "id_evento" es opcional: si llega, se usa para localizar el historico del evento; si no
      llega, se procesa como extraccion inicial sin historico (util para Cliente/Espacio).
    - Este servidor no guarda estado propio: cada peticion es independiente (a diferencia
      del chat de Lumen, aqui no hay memoria de conversacion que mantener); el historico de
      actualizaciones vive en la BD del proyecto, no en este proceso.
"""

import json
import sys
from pathlib import Path

from flask import Flask, request, jsonify
from werkzeug.exceptions import HTTPException

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))  # permite "from src.agente import ..." y "from config import ..."

from src.agente import ejecutar_agente  # noqa: E402
from config import settings  # noqa: E402

app = Flask(__name__)

# CORS: permite que el frontend React (otro puerto, p.ej. localhost:3000) llame a esta API
# desde el navegador. Sin esto, el navegador bloquea las peticiones aunque el servidor responda.
try:
    from flask_cors import CORS
    CORS(app)
except ImportError:
    print("Aviso: flask-cors no instalado. El frontend en el navegador puede fallar por CORS.")


def _error(codigo, mensaje, http=400):
    return jsonify({"error": True, "codigo": codigo, "mensaje": mensaje}), http


def _texto_limpio(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def _extraer_texto(cuerpo):
    datos = cuerpo.get("datos") if isinstance(cuerpo.get("datos"), dict) else {}
    for clave in ("texto_briefing", "texto", "contenido", "descripcion", "prompt"):
        texto = _texto_limpio(cuerpo.get(clave))
        if texto:
            return texto
        texto = _texto_limpio(datos.get(clave))
        if texto:
            return texto
    return ""


def _parsear_lista(valor):
    if valor is None or valor == "":
        return None
    if isinstance(valor, list):
        return [str(item).strip() for item in valor if str(item).strip()]
    if isinstance(valor, tuple):
        return [str(item).strip() for item in valor if str(item).strip()]
    texto = str(valor).strip()
    if not texto:
        return None
    try:
        parsed = json.loads(texto)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass
    return [item.strip() for item in texto.split(",") if item.strip()]


def _valor_formulario(nombre, cuerpo=None, datos=None):
    cuerpo = cuerpo or {}
    datos = datos or {}
    return (
        cuerpo.get(nombre)
        or datos.get(nombre)
        or request.form.get(nombre)
        or request.args.get(nombre)
    )


def _decodificar_archivo_subido(archivo):
    contenido = archivo.read()
    if not contenido:
        return ""
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return contenido.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return contenido.decode("utf-8", errors="ignore").strip()


def _extraer_texto_archivo():
    if not request.files:
        return ""
    for nombre in ("archivo", "file", "documento", "upload"):
        archivo = request.files.get(nombre)
        if archivo:
            return _decodificar_archivo_subido(archivo)
    primer_archivo = next(iter(request.files.values()), None)
    return _decodificar_archivo_subido(primer_archivo) if primer_archivo else ""


@app.get("/")
def inicio():
    return jsonify({
        "servicio": "agente_operis - autocompletar briefings",
        "estado": "en marcha",
        "motor_por_defecto": settings.MOTOR_POR_DEFECTO,
        "prueba": 'POST /autocompletar con {"texto": "...", "tipo_objetivo": "cliente"}',
    })


# sonda uniforme del sistema (misma forma que Jano y Vigil): la usan el
# gateway y comprobar_salud.sh
@app.get("/health")
def health():
    from datetime import datetime
    return jsonify({"estado": "ok", "hora": datetime.now().isoformat()})


# los errores HTTP (404, 405...) salen en JSON conservando su codigo
@app.errorhandler(HTTPException)
def _error_http(exc):
    return _error(f"HTTP_{exc.code}", exc.description, http=exc.code)


# si el agente revienta, el front recibe el contrato de error en JSON,
# nunca la pagina HTML de error de Flask
@app.errorhandler(Exception)
def _error_interno(exc):
    return _error("ERROR_INTERNO", str(exc), http=500)


@app.post("/autocompletar")
def autocompletar():
    cuerpo = request.get_json(silent=True) if request.is_json else None
    if cuerpo is None:
        cuerpo = {}
    if not isinstance(cuerpo, dict):
        return _error("CUERPO_INVALIDO", "El cuerpo debe ser un objeto JSON.")

    datos = cuerpo.get("datos") if isinstance(cuerpo.get("datos"), dict) else {}
    contexto = cuerpo.get("contexto") if isinstance(cuerpo.get("contexto"), dict) else {}

    id_evento = _texto_limpio(_valor_formulario("id_evento", cuerpo, datos)) or None
    texto_briefing = (
        _extraer_texto(cuerpo)
        or _texto_limpio(
            request.form.get("texto_briefing")
            or request.form.get("texto")
            or request.form.get("contenido")
            or request.form.get("descripcion")
            or request.args.get("texto_briefing")
            or request.args.get("texto")
            or request.args.get("contenido")
        )
        or _extraer_texto_archivo()
    )
    if not texto_briefing:
        return _error(
            "TEXTO_NO_RECIBIDO",
            "No se ha recibido texto para autocompletar. Envia 'texto', 'texto_briefing', 'contenido', 'datos.texto_briefing' o un archivo multipart.",
            http=422,
        )

    # El unico motor disponible es "llm" (el motor de reglas se elimino).
    motor = _valor_formulario("motor", cuerpo, datos) or settings.MOTOR_POR_DEFECTO
    if motor != "llm":
        return _error("MOTOR_INVALIDO", "El unico motor disponible es 'llm'.")

    bloques_a_actualizar = _parsear_lista(_valor_formulario("bloques_a_actualizar", cuerpo, datos))
    if bloques_a_actualizar is not None and not isinstance(bloques_a_actualizar, list):
        return _error("CAMPO_INVALIDO", "'bloques_a_actualizar' debe ser una lista, ej. [\"nota_bene\"].")

    campos_objetivo = _parsear_lista(_valor_formulario("campos_objetivo", cuerpo, datos))

    historial_anterior = cuerpo.get("historial_anterior", contexto.get("historial_anterior"))
    if historial_anterior is not None and not isinstance(historial_anterior, dict):
        return _error("CAMPO_INVALIDO", "'historial_anterior' debe ser un objeto JSON.")

    tipo_objetivo = _texto_limpio(
        _valor_formulario("tipo_objetivo", cuerpo, datos)
        or _valor_formulario("objetivo", cuerpo, datos)
        or "evento"
    )

    # Se construye el contrato de entrada comun del agente (README.md, seccion 9.2):
    # el front puede mandar id_evento + texto si trabaja sobre un evento ya creado,
    # o solo texto/tipo_objetivo para pantallas independientes como Cliente/Espacio.
    # Si llega id_evento y no llega historial_anterior, src/nucleo.py intentara
    # autocargarlo desde la BD real (ver src/lectura_bd.py).
    payload = {
        "id_evento": id_evento,
        "id_registro": None,
        "tipo_peticion": "extraer_briefing",
        "origen": "frontend",
        "usuario_solicitante": "frontend",
        "rol_usuario": "organizador",
        "datos": {
            "texto_briefing": texto_briefing,
            "motor": motor,
            "bloques_a_actualizar": bloques_a_actualizar,
            "tipo_objetivo": tipo_objetivo,
            "campos_objetivo": campos_objetivo,
        },
        "contexto": {
            "historial_anterior": historial_anterior,
        },
        "modo": "propuesta",
    }

    salida = ejecutar_agente(payload)
    http = 200 if salida.get("ok") else 422
    return jsonify(salida), http


if __name__ == "__main__":
    print("agente_operis — servidor HTTP para el frontend")
    print("Escuchando en http://localhost:5002  (Ctrl+C para parar)")
    # 127.0.0.1 como el resto de agentes: la puerta de entrada es el gateway
    # (:5003); no exponemos el agente a toda la red local sin autenticacion
    app.run(host="127.0.0.1", port=5002, debug=False)
