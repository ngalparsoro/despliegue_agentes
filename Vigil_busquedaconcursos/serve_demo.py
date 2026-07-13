"""Arranque de la DEMO en un solo comando: web + API, con datos ya cargados.

Pensado para enseñar Vigil (p. ej. al equipo full-stack) sin `GROQ_API_KEY`,
sin Playwright y sin depender de la web real. Hace tres cosas:

1. Activa el modo demo (datos de ejemplo, sin LLM) y usa una base de datos y una
   carpeta de salida aparte, para no tocar las reales.
2. Si el histórico está vacío, ejecuta el agente (en demo) una vez para que la
   web ya tenga concursos que mostrar.
3. Levanta el servidor: web en http://127.0.0.1:8000/  y API bajo esa misma URL.

Uso:
    python serve_demo.py
"""

# traigo os para preparar las variables de entorno antes de importar el resto
import os

# activo el modo demo (si no estaba puesto ya)
os.environ.setdefault("VIGIL_DEMO", "1")
# localizo la carpeta de este fichero para poner ahí la BD y la salida de demo
_AQUI = os.path.dirname(os.path.abspath(__file__))
# uso una base de datos de demo separada de la real (vigil.db)
os.environ.setdefault("VIGIL_DB_PATH", os.path.join(_AQUI, "vigil_demo.db"))
# uso una carpeta de salida de demo separada de la real
os.environ.setdefault("VIGIL_OUTPUT_DIR", os.path.join(_AQUI, "salida_demo"))

# ahora sí importo lo que depende de esas variables
from vigil import dedupe, history
from vigil.config import SQLITE_PATH


# me aseguro de que hay datos que enseñar: si el histórico está vacío, siembro
def _sembrar_si_hace_falta() -> None:
    # miro cuántos concursos hay guardados
    with dedupe.get_connection(SQLITE_PATH) as conn:
        vacio = history.contar(conn) == 0
    # si no hay ninguno, ejecuto el agente en modo demo una vez
    if vacio:
        from vigil.main import run
        run()


# punto de entrada
if __name__ == "__main__":
    # cargo datos de ejemplo si aún no los hay
    _sembrar_si_hace_falta()
    # traigo la app Flask (ya con el modo demo activado por las variables de arriba)
    from vigil.api import app
    # levanto el servidor con la web y la API
    app.run(host="127.0.0.1", port=8000)
