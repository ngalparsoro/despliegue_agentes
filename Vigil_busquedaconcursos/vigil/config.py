"""Configuración de Vigil: fuentes activas, umbrales, destinatarios y credenciales.

Todas las credenciales y datos de despliegue vienen de variables de entorno
(ver sección 9 del build brief). Nada de secretos hardcodeados.
"""

# traigo os para poder leer variables de entorno del sistema
import os
# traigo dataclass para crear una pequeña clase de datos de forma cómoda
from dataclasses import dataclass


# creo una clase sencilla que guarda los datos de una diputación
@dataclass(frozen=True)
class Diputacion:
    # el nombre oficial completo de la diputación
    nombre: str
    # el número interno con el que la web identifica a esta diputación
    id_poder: int
    # el término que sí funciona al buscarla en el autocompletado (ver sources.py)
    busqueda: str


# Las tres diputaciones forales objetivo (sección 1 y 5 del brief).
# id_poder identifica a cada entidad dentro de KontratazioA; se obtuvo
# consultando en vivo el endpoint de autocompletado de poder adjudicador
# del propio portal (busquedaAnuncios/autocompletePoderesEntidades).
#
# `busqueda` no siempre coincide con `nombre`: probado en vivo, el
# autocompletado del portal es inconsistente — buscar el nombre oficial
# completo y con tilde ("Diputación Foral de Gipuzkoa") no devuelve NINGÚN
# resultado, mientras que buscar solo el territorio ("Gipuzkoa") sí la
# incluye entre las sugerencias. Por eso se busca por `busqueda` y se
# selecciona la sugerencia cuyo texto coincide exactamente con `nombre`
# (ver sources._seleccionar_diputacion), en vez de asumir que es la primera.
# creo la lista con las tres diputaciones que voy a vigilar
DIPUTACIONES: list[Diputacion] = [
    # guardo Álava con su id interno y el término de búsqueda que funciona
    Diputacion(nombre="Diputación Foral de Álava", id_poder=17585, busqueda="Álava"),
    # guardo Gipuzkoa igual
    Diputacion(nombre="Diputación Foral de Gipuzkoa", id_poder=17263, busqueda="Gipuzkoa"),
    # guardo Bizkaia igual
    Diputacion(nombre="Diputación Foral de Bizkaia", id_poder=18269, busqueda="Bizkaia"),
]

# guardo la dirección web de la página de búsqueda del portal
KONTRATAZIOA_URL = (
    "https://www.contratacion.euskadi.eus/webkpe00-kpeperfi/es/"
    "ac70cPublicidadWar/busquedaAnuncios?locale=es"
)

# --- LLM (Groq) ---
# leo la clave de la API de Groq desde el entorno (vacía si no está puesta)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
# Modelo elegido para la demo (antes de mediados de agosto de 2026 — ver aviso
# en la sección 2 del build brief). Si Vigil sigue en uso después de esa
# fecha, migrar a "openai/gpt-oss-120b".
# leo qué modelo usar; si no me lo dan, uso el de la demo por defecto
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# --- Salida hacia la plataforma ---
# Esta versión no manda email: escribe un JSON (y los .ics) que la plataforma
# Mitumi BackStage lee para su sección "Concursos Públicos".
# decido en qué carpeta dejo los archivos de salida; por defecto "salida"
OUTPUT_DIR = os.environ.get("VIGIL_OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "..", "salida"))

# --- Programación ---
# leo la hora a la que se debe lanzar el agente
CRON_HORA = os.environ.get("CRON_HORA", "07:00")
# leo la zona horaria en la que interpreto esa hora
CRON_TIMEZONE = os.environ.get("CRON_TIMEZONE", "Europe/Madrid")

# --- Persistencia ---
# decido dónde guardar la base de datos; por defecto, un fichero junto a este
SQLITE_PATH = os.environ.get("VIGIL_DB_PATH", os.path.join(os.path.dirname(__file__), "vigil.db"))

# --- CORS (para que el front de la plataforma pueda llamar a esta API) ---
# leo los orígenes permitidos separados por comas; por defecto "*" (cualquiera),
# cómodo para la demo. En producción pongo aquí solo el dominio de la plataforma.
CORS_ORIGINS = [
    origen.strip()
    for origen in os.environ.get("VIGIL_CORS_ORIGINS", "*").split(",")
    if origen.strip()
]
