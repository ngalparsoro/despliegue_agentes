"""Arranque de la DEMO de Mercurio en un solo comando: web + API.

Levanta el formulario de búsqueda y su API en modo demo (resultados simulados,
sin APIs de proveedores ni LLM). No hay nada que "sembrar": la web arranca con
el formulario y las búsquedas se hacen al vuelo.

Uso:
    python serve_demo_mercurio.py
"""

# traigo os para preparar las variables de entorno antes de importar el resto
import os

# activo el modo demo (si no estaba puesto ya)
os.environ.setdefault("MERCURIO_DEMO", "1")
# localizo la carpeta de este fichero para poner ahí la salida de demo
_AQUI = os.path.dirname(os.path.abspath(__file__))
# uso una carpeta de salida de demo separada (donde se guardan los PDFs)
os.environ.setdefault("MERCURIO_OUTPUT_DIR", os.path.join(_AQUI, "salida_mercurio_demo"))


# punto de entrada
if __name__ == "__main__":
    # traigo la app Flask (ya con el modo demo activado por las variables de arriba)
    from mercurio.api import app
    # levanto el servidor con la web y la API (puerto 8001 para no chocar con Vigil)
    app.run(host="127.0.0.1", port=8001)
