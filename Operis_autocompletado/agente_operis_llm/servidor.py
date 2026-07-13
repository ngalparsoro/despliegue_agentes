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
    POST /autocompletar  -> body: {
                                "id_evento": "...",              (obligatorio)
                                "texto_briefing": "...",         (obligatorio)
                                "bloques_a_actualizar": [...],   (opcional, ej. ["nota_bene"])
                                "historial_anterior": {...}      (opcional; si no se manda y
                                                                   el evento ya existe en BD,
                                                                   se autocarga desde ahi)
                            }
                            Devuelve el contrato de salida comun del agente: datos_detectados
                            con los 4 bloques (evento, cliente, ponentes, nota_bene),
                            bloqueos_detectados con los campos que faltan, y
                            requiere_validacion_humana=True SIEMPRE — el front debe mostrar
                            los campos como PROPUESTA editable, nunca guardarlos solos.

Notas:
    - El unico motor disponible es "llm" (Groq); el motor de reglas se elimino. Requiere
      GROQ_API_KEY en .env — sin ella, el agente devuelve un error controlado (ver src/llm.py).
    - "id_evento" es obligatorio: el agente solo funciona sobre eventos existentes, porque
      lo usa para localizar el historico (ver src/lectura_bd.py / src/nucleo.py).
    - Este servidor no guarda estado propio: cada peticion es independiente (a diferencia
      del chat de Lumen, aqui no hay memoria de conversacion que mantener); el historico de
      actualizaciones vive en la BD del proyecto, no en este proceso.
"""

import sys
from pathlib import Path

from flask import Flask, request, jsonify

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


@app.get("/")
def inicio():
    return jsonify({
        "servicio": "agente_operis - autocompletar briefings",
        "estado": "en marcha",
        "motor_por_defecto": settings.MOTOR_POR_DEFECTO,
        "prueba": 'POST /autocompletar con {"texto_briefing": "..."}',
    })


@app.post("/autocompletar")
def autocompletar():
    cuerpo = request.get_json(silent=True)
    if not cuerpo or not isinstance(cuerpo, dict):
        return _error("CUERPO_INVALIDO", "Manda un JSON con al menos 'id_evento' y 'texto_briefing'.")

    id_evento = cuerpo.get("id_evento")
    if not id_evento:
        return _error("CAMPO_OBLIGATORIO", "El campo 'id_evento' es obligatorio: el agente solo funciona sobre eventos existentes.")

    texto_briefing = (cuerpo.get("texto_briefing") or "").strip()
    if not texto_briefing:
        return _error("CAMPO_OBLIGATORIO", "El campo 'texto_briefing' es obligatorio.")

    # El unico motor disponible es "llm" (el motor de reglas se elimino).
    motor = cuerpo.get("motor") or settings.MOTOR_POR_DEFECTO
    if motor != "llm":
        return _error("MOTOR_INVALIDO", "El unico motor disponible es 'llm'.")

    bloques_a_actualizar = cuerpo.get("bloques_a_actualizar")
    if bloques_a_actualizar is not None and not isinstance(bloques_a_actualizar, list):
        return _error("CAMPO_INVALIDO", "'bloques_a_actualizar' debe ser una lista, ej. [\"nota_bene\"].")

    historial_anterior = cuerpo.get("historial_anterior")
    if historial_anterior is not None and not isinstance(historial_anterior, dict):
        return _error("CAMPO_INVALIDO", "'historial_anterior' debe ser un objeto JSON.")

    # Se construye el contrato de entrada comun del agente (README.md, seccion 9.2):
    # el front manda id_evento + texto (+ opcionalmente bloques_a_actualizar/historial_anterior),
    # el resto lo fija esta capa. Si no se manda historial_anterior, src/nucleo.py intenta
    # autocargarlo desde la BD real a partir de id_evento (ver src/lectura_bd.py).
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
    app.run(host="0.0.0.0", port=5002, debug=False)
