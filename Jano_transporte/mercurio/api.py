"""API HTTP de Mercurio: la superficie que consume la plataforma.

La búsqueda se dispara con un formulario: la plataforma envía los campos a
`POST /buscar` y recibe al momento las sugerencias de hotel y/o viaje, más los
enlaces para descargar los dos informes en PDF (el del ponente, sin precios, y
el de Mitumi, con precios). No hay base de datos: la entrada es la petición y la
salida son la respuesta JSON y los PDFs en disco.

Arranque en local:  `python serve_demo_mercurio.py` (demo) o, en producción,
`waitress-serve --host=0.0.0.0 --port=8001 mercurio.api:app`.
"""

# traigo os para componer la ruta de los PDFs
import os
# traigo time para calcular la antigüedad de los PDFs al purgarlos
import time
# traigo utilidades de fecha para el sello de tiempo del health
from datetime import datetime
# traigo Path para localizar el HTML de la web
from pathlib import Path

# traigo Flask y sus utilidades para declarar la API
from flask import Flask, abort, jsonify, request, send_file
# traigo CORS para que el front (en otro dominio) pueda llamar a esta API
from flask_cors import CORS
# traigo el error de validación de Pydantic para responder 422 como antes
from pydantic import ValidationError
# traigo la excepción base de los errores HTTP para responderlos en JSON
from werkzeug.exceptions import HTTPException

# traigo el servicio de búsqueda y el generador de PDFs
from mercurio import pdf_report, servicio
# traigo la carpeta de salida y los orígenes permitidos para CORS
from mercurio.config import CORS_ORIGINS, OUTPUT_DIR
# traigo el molde de la solicitud
from mercurio.schemas import SolicitudBusqueda

# creo la aplicación Flask
app = Flask(__name__)

# permito que el front de la plataforma (en otro dominio) llame a esta API
CORS(app, origins=CORS_ORIGINS)

# localizo el fichero HTML de la web (la "plataforma" de demostración)
_INDEX_HTML = Path(__file__).parent / "static" / "index.html"
# carpeta donde se guardan los PDFs generados
_CARPETA_PDF = os.path.join(OUTPUT_DIR, "pdf")


# si el cuerpo no valida contra el molde, respondo 422 con el detalle (como FastAPI)
@app.errorhandler(ValidationError)
def _error_validacion(err: ValidationError):
    # pido los errores sin la url ni el contexto (que puede llevar la excepción
    # original, no serializable a JSON) para poder devolverlos limpios
    errores = err.errors(include_url=False, include_context=False)
    # formato común de los agentes + "detail" para la web de demostración
    return jsonify({
        "error": True,
        "codigo": "VALIDACION",
        "mensaje": "El cuerpo de la petición no pasa la validación.",
        "detail": errores,
    }), 422


# cualquier error HTTP (404…) sale en JSON con el formato común de los
# agentes ({"error": true, codigo, mensaje}); conservo "detail" porque la web
# de demostración lee ese campo
@app.errorhandler(HTTPException)
def _error_http(err: HTTPException):
    descripcion = getattr(err, "description", "Error")
    return jsonify({
        "error": True,
        "codigo": f"HTTP_{err.code}",
        "mensaje": descripcion,
        "detail": descripcion,
    }), err.code


# si algo revienta de verdad, el front recibe JSON con el contrato de error,
# nunca la página HTML de error de Flask
@app.errorhandler(Exception)
def _error_interno(err: Exception):
    return jsonify({
        "error": True,
        "codigo": "ERROR_INTERNO",
        "mensaje": str(err),
        "detail": str(err),
    }), 500


# borro los informes con más de 7 días para que la carpeta no crezca sin
# límite (los enlaces de descarga son efímeros: acompañan a cada búsqueda)
def _purgar_pdfs_antiguos(max_dias: int = 7) -> None:
    limite = time.time() - max_dias * 86400
    try:
        for nombre in os.listdir(_CARPETA_PDF):
            ruta = os.path.join(_CARPETA_PDF, nombre)
            if nombre.endswith(".pdf") and os.path.getmtime(ruta) < limite:
                os.remove(ruta)
    except OSError:
        # si la carpeta aún no existe o un borrado falla, no rompo la búsqueda
        pass


# sirvo la web en la raíz (el formulario de búsqueda)
@app.get("/")
def index() -> str:
    # leo el HTML en cada petición para reflejar cambios sin reiniciar
    return _INDEX_HTML.read_text(encoding="utf-8")


# sonda simple para comprobar que la API está viva
@app.get("/health")
def health():
    # devuelvo un ok y la hora actual
    return jsonify({"estado": "ok", "hora": datetime.now().isoformat()})


# ejecuto una búsqueda a partir de los campos del formulario
@app.post("/buscar")
def buscar():
    # aprovecho cada búsqueda para limpiar informes antiguos del disco
    _purgar_pdfs_antiguos()
    # si el cuerpo no es un objeto JSON, lo digo claro (en vez de un 500)
    cuerpo = request.get_json(silent=True)
    if not isinstance(cuerpo, dict):
        abort(400, description="Manda un objeto JSON con los campos del formulario de búsqueda.")
    # valido el cuerpo JSON contra el molde (Pydantic sigue validando)
    solicitud = SolicitudBusqueda(**cuerpo)
    # ejecuto la búsqueda (hotel y/o viaje según las casillas)
    propuesta = servicio.buscar(solicitud)
    # genero los dos informes en PDF (ponente y Mitumi)
    rutas = pdf_report.generar_ambos(propuesta, _CARPETA_PDF)
    # devuelvo la propuesta y los enlaces de descarga de cada PDF
    return jsonify({
        "propuesta": propuesta.model_dump(),
        "pdf_ponente": f"/informes/{propuesta.id}/ponente.pdf" if rutas["ponente"] else None,
        "pdf_mitumi": f"/informes/{propuesta.id}/mitumi.pdf" if rutas["mitumi"] else None,
    })


# sirvo uno de los PDFs generados (variante ponente o mitumi)
def _servir_pdf(id_busqueda: str, variante: str, nombre_descarga: str):
    # compongo la ruta del PDF pedido
    ruta_abs = os.path.join(_CARPETA_PDF, f"{id_busqueda}_{variante}.pdf")
    # si el archivo no está en disco, devuelvo 404
    if not os.path.exists(ruta_abs):
        abort(404, description="Informe no encontrado (¿ha caducado la búsqueda?).")
    # devuelvo el PDF como descarga con un nombre claro
    return send_file(
        ruta_abs,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=nombre_descarga,
    )


# descarga del informe del ponente (sin precios)
@app.get("/informes/<id_busqueda>/ponente.pdf")
def informe_ponente(id_busqueda: str):
    return _servir_pdf(id_busqueda, "ponente", f"informe_ponente_{id_busqueda}.pdf")


# descarga del informe para Mitumi (con precios)
@app.get("/informes/<id_busqueda>/mitumi.pdf")
def informe_mitumi(id_busqueda: str):
    return _servir_pdf(id_busqueda, "mitumi", f"informe_mitumi_{id_busqueda}.pdf")
