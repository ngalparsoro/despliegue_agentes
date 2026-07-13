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
    return jsonify({"detail": err.errors(include_url=False, include_context=False)}), 422


# si no encuentro algo, devuelvo el error en JSON (no en HTML) para el front
@app.errorhandler(404)
def _no_encontrado(err):
    return jsonify({"detail": getattr(err, "description", "No encontrado")}), 404


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
    # valido el cuerpo JSON contra el molde (Pydantic sigue validando)
    solicitud = SolicitudBusqueda(**(request.get_json(silent=True) or {}))
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
