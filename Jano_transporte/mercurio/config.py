"""Configuración de Mercurio: salida, LLM y CORS.

A diferencia de Vigil, este agente **no tiene base de datos** ni lee de ninguna
fuente externa: la búsqueda se dispara con un formulario (`POST /buscar`) y su
única salida son la respuesta JSON y los dos PDFs en disco. Todo lo sensible
viene de variables de entorno; nada de secretos hardcodeados.
"""

# traigo os para poder leer variables de entorno del sistema
import os

# --- LLM (Groq), opcional: solo se usa para redactar el informe en modo real ---
# leo la clave de la API de Groq desde el entorno (vacía si no está puesta)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
# leo qué modelo usar; si no me lo dan, uso el mismo que la demo de Vigil
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# --- Salida (PDFs generados) ---
# aquí se guardan los dos informes en PDF de cada búsqueda; el resto de la
# respuesta viaja en el JSON de la API, no en disco.
# decido en qué carpeta dejo los PDFs; por defecto "salida_mercurio"
OUTPUT_DIR = os.environ.get(
    "MERCURIO_OUTPUT_DIR",
    os.path.join(os.path.dirname(__file__), "..", "salida_mercurio"),
)

# --- Parámetros del viaje ---
# cuántos días antes del inicio del evento llega el ponente (para descansar)
DIAS_ANTES = int(os.environ.get("MERCURIO_DIAS_ANTES", "1"))
# cuántos días después del fin del evento se marcha el ponente
DIAS_DESPUES = int(os.environ.get("MERCURIO_DIAS_DESPUES", "1"))
# cuántas sugerencias de cada tipo (hoteles, vuelos, trenes) ofrezco
SUGERENCIAS_POR_TIPO = int(os.environ.get("MERCURIO_SUGERENCIAS", "3"))

# --- CORS (para que el front de la plataforma pueda llamar a esta API) ---
# leo los orígenes permitidos separados por comas; por defecto "*" (cualquiera),
# cómodo para la demo. En producción pongo aquí solo el dominio de la plataforma.
CORS_ORIGINS = [
    origen.strip()
    for origen in os.environ.get("MERCURIO_CORS_ORIGINS", "*").split(",")
    if origen.strip()
]
