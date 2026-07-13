"""API HTTP de Vigil: la superficie que consumirá la plataforma del equipo full-stack.

Expone tres cosas:

- `GET /concursos` — consulta el histórico con filtros (texto, diputación,
  urgencia, solo en plazo, solo relevantes). Cubre el "filtro de búsqueda" y el
  "mostrar solo los que están en plazo".
- `POST /ejecuciones` — lanza el agente en vivo (scrape + LLM) en segundo plano.
  Cubre el "botón de búsqueda al instante". Devuelve un id con el que consultar
  el progreso, porque la ejecución tarda minutos.
- `GET /ejecuciones/{id}` — estado de una ejecución lanzada a mano.

Arranque en local:  `python serve_demo.py` (demo) o, en producción,
`waitress-serve --host=0.0.0.0 --port=8000 vigil.api:app`.

El seguimiento de ejecuciones se guarda en memoria (se pierde si se reinicia el
servidor); es suficiente para un disparo puntual desde un botón.
"""

# traigo subprocess y sys para lanzar el agente como proceso aparte
import subprocess
import sys
# traigo threading para vigilar el proceso sin bloquear la API
import threading
# traigo uuid para dar un identificador único a cada ejecución
import uuid
# traigo utilidades de fecha para los sellos de tiempo
from datetime import datetime
# traigo Path para localizar el fichero HTML de la web de demostración
from pathlib import Path

# traigo Flask y sus utilidades para declarar la API
from flask import Flask, Response, abort, jsonify, request
# traigo CORS para que el front (en otro dominio) pueda llamar a esta API
from flask_cors import CORS

# traigo el módulo de conexión (compartido con el dedupe) y el histórico
from vigil import dedupe, history
# traigo las funciones que generan el calendario .ics de un concurso
from vigil.calendar_ics import generar_ics, nombre_fichero_ics
# traigo las funciones que generan el PDF de resumen de un concurso
from vigil.pliego_pdf import generar_pliego_pdf, nombre_fichero_pliego
# traigo la ruta de la base de datos y los orígenes permitidos para CORS
from vigil.config import CORS_ORIGINS, SQLITE_PATH
# traigo el molde Convocatoria para reconstruirla desde el histórico
from vigil.schemas import Convocatoria

# creo la aplicación Flask
app = Flask(__name__)

# permito que el front de la plataforma (en otro dominio) llame a esta API
CORS(app, origins=CORS_ORIGINS)

# guardo en memoria el estado de las ejecuciones lanzadas a mano, por id
_EJECUCIONES: dict[str, dict] = {}

# localizo el fichero HTML de la web (la "plataforma" de demostración)
_INDEX_HTML = Path(__file__).parent / "static" / "index.html"


# si no encuentro algo, devuelvo el error en JSON (no en HTML) para el front
@app.errorhandler(404)
def _no_encontrado(err):
    return jsonify({"detail": getattr(err, "description", "No encontrado")}), 404


# interpreto un parámetro de query como booleano ("true", "1", "si"… → True)
def _a_bool(valor: str | None, por_defecto: bool = False) -> bool:
    # si no viene el parámetro, uso el valor por defecto
    if valor is None:
        return por_defecto
    # comparo en minúsculas contra las formas afirmativas habituales
    return valor.strip().lower() in {"1", "true", "yes", "on", "si", "sí"}


# interpreto un parámetro de query como entero, con defecto y límites
def _a_int(valor: str | None, por_defecto: int, minimo: int, maximo: int | None = None) -> int:
    # intento convertirlo a entero; si no puedo, uso el valor por defecto
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return por_defecto
    # nunca bajo del mínimo
    numero = max(minimo, numero)
    # si hay tope, tampoco lo supero
    if maximo is not None:
        numero = min(maximo, numero)
    return numero


# sirvo la web de concursos en la raíz (es lo que se ve al abrir el navegador)
@app.get("/")
def index() -> str:
    # leo el HTML en cada petición para reflejar cambios sin reiniciar
    return _INDEX_HTML.read_text(encoding="utf-8")


# sonda simple para comprobar que la API está viva
@app.get("/health")
def health():
    # devuelvo un ok y la hora actual
    return jsonify({"estado": "ok", "hora": datetime.now().isoformat()})


# consulto el histórico de concursos con filtros
@app.get("/concursos")
def listar_concursos():
    # leo los filtros de la query string
    q = request.args.get("q")
    diputacion = request.args.get("diputacion")
    urgencia = request.args.get("urgencia")
    # si True, solo los que siguen en plazo
    en_plazo = _a_bool(request.args.get("en_plazo"))
    # si True, solo los que el LLM marcó como relevantes
    relevante = _a_bool(request.args.get("relevante"))
    # cuántos devolver (entre 1 y 200) y desde qué posición (para paginar)
    limite = _a_int(request.args.get("limite"), por_defecto=50, minimo=1, maximo=200)
    offset = _a_int(request.args.get("offset"), por_defecto=0, minimo=0)

    # abro una conexión a la base de datos para esta consulta
    with dedupe.get_connection(SQLITE_PATH) as conn:
        # pido al histórico los concursos que cumplen los filtros
        concursos = history.consultar(
            conn,
            q=q,
            diputacion=diputacion,
            urgencia=urgencia,
            solo_en_plazo=en_plazo,
            solo_relevantes=relevante,
            limite=limite,
            offset=offset,
        )
    # devuelvo el total de esta página y la lista
    return jsonify({"total": len(concursos), "concursos": concursos})


# sirvo el calendario .ics de un concurso para añadirlo a la agenda
@app.get("/concursos/<id_expediente>/calendario.ics")
def calendario(id_expediente: str):
    # busco el concurso en el histórico
    with dedupe.get_connection(SQLITE_PATH) as conn:
        registro = history.obtener(conn, id_expediente)
    # si no existe ese expediente, devuelvo 404
    if registro is None:
        abort(404, description="Concurso no encontrado.")
    # reconstruyo una Convocatoria con lo justo para generar el .ics
    convocatoria = Convocatoria(
        id_expediente=registro["id_expediente"],
        diputacion=registro["diputacion"],
        objeto=registro["objeto"],
        organo_convocante=registro["organo_convocante"],
        enlace_pliego=registro["enlace_pliego"],
        plazo_presentacion=registro["plazo_presentacion"],
    )
    # genero el contenido del calendario
    ics = generar_ics(convocatoria)
    # si no hay una fecha de plazo válida, no hay calendario que ofrecer
    if ics is None:
        abort(404, description="El concurso no tiene un plazo con fecha válida.")
    # devuelvo el .ics como descarga, con el nombre de archivo del concurso
    return Response(
        ics,
        mimetype="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{nombre_fichero_ics(convocatoria)}"'},
    )


# sirvo el resumen (PDF) de un expediente: es lo que muestra "Ver pliego"
@app.get("/concursos/<id_expediente>/pliego.pdf")
def pliego(id_expediente: str):
    # busco el concurso en el histórico
    with dedupe.get_connection(SQLITE_PATH) as conn:
        registro = history.obtener(conn, id_expediente)
    # si no existe ese expediente, devuelvo 404
    if registro is None:
        abort(404, description="Concurso no encontrado.")
    # genero el PDF de resumen a partir de los datos del histórico
    pdf = generar_pliego_pdf(registro)
    # lo devuelvo en línea (se abre en el navegador y se puede descargar)
    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{nombre_fichero_pliego(registro)}"'},
    )


# lanzo el agente como un proceso aparte (aísla Playwright del servidor web)
def _lanzar_proceso() -> subprocess.Popen:
    # ejecuto "python -m vigil.main" con el mismo intérprete que corre la API
    return subprocess.Popen([sys.executable, "-m", "vigil.main"])


# vigilo el proceso hasta que termine y actualizo el estado de la ejecución
def _vigilar(run_id: str, proc: subprocess.Popen, contados_antes: int) -> None:
    # espero a que el proceso del agente termine
    codigo = proc.wait()
    # cuento cuántos concursos hay ahora para saber cuántos son nuevos
    with dedupe.get_connection(SQLITE_PATH) as conn:
        contados_despues = history.contar(conn)
    # recupero el registro de esta ejecución
    registro = _EJECUCIONES[run_id]
    # apunto la hora de fin
    registro["terminado_en"] = datetime.now().isoformat()
    # si el agente terminó bien, marco terminada y calculo los nuevos
    if codigo == 0:
        registro["estado"] = "terminada"
        registro["nuevos"] = max(0, contados_despues - contados_antes)
    # si terminó con error, lo marco como error con el código de salida
    else:
        registro["estado"] = "error"
        registro["error"] = f"El agente terminó con código {codigo}."


# lanzo una ejecución del agente en vivo y devuelvo su identificador
@app.post("/ejecuciones")
def crear_ejecucion():
    # cuento cuántos concursos hay antes de lanzar, para calcular los nuevos
    with dedupe.get_connection(SQLITE_PATH) as conn:
        contados_antes = history.contar(conn)
    # invento un identificador único para esta ejecución
    run_id = uuid.uuid4().hex
    # guardo el estado inicial de la ejecución
    _EJECUCIONES[run_id] = {
        "id": run_id,
        "estado": "en_curso",
        "iniciado_en": datetime.now().isoformat(),
        "terminado_en": None,
        "nuevos": None,
        "error": None,
    }
    # lanzo el agente en un proceso aparte
    proc = _lanzar_proceso()
    # arranco un hilo que vigila ese proceso sin bloquear la respuesta
    threading.Thread(
        target=_vigilar, args=(run_id, proc, contados_antes), daemon=True
    ).start()
    # devuelvo el id y el estado inicial (202) para que la UI haga polling
    return jsonify(_EJECUCIONES[run_id]), 202


# consulto el estado de una ejecución lanzada a mano
@app.get("/ejecuciones/<run_id>")
def estado_ejecucion(run_id: str):
    # busco la ejecución por su id
    registro = _EJECUCIONES.get(run_id)
    # si no existe, devuelvo un 404 claro
    if registro is None:
        abort(404, description="Ejecución no encontrada.")
    # devuelvo el estado actual
    return jsonify(registro)
