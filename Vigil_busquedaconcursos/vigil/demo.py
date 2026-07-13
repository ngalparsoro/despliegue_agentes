"""Modo demo de Vigil: ejecuta el pipeline completo SIN web ni LLM.

Sirve para enseñar el agente a otras personas (p. ej. el equipo full-stack) de
forma repetible y sin depender de `GROQ_API_KEY`, de Playwright ni de que la web
de KontratazioA tenga novedades ese día.

Cuando la variable de entorno `VIGIL_DEMO` está puesta, `main.run()` usa estas
tres funciones en lugar de las reales:

- `obtener_convocatorias()` → devuelve las convocatorias de ejemplo.
- `extraer_convocatoria()`  → estructura el crudo directamente (sin Groq).
- `evaluar_relevancia()`    → decide relevancia con una heurística simple (sin Groq).

El resto del flujo (dedupe, urgencia, histórico, publicación) es el de siempre.
"""

# traigo las convocatorias de ejemplo que ya venían con el proyecto
from vigil.examples.convocatorias_ejemplo import EJEMPLOS
# traigo los moldes de datos del pipeline
from vigil.schemas import Convocatoria, VeredictoRelevancia

# palabras que, si aparecen en el objeto, indican que NO encaja con Mitumi
# (obra pública, suministros… fuera del perfil de una agencia de eventos)
_PALABRAS_NO_RELEVANTES = (
    "obra", "carretera", "firme", "drenaje", "suministro", "sanitario", "material",
)

# asocio palabras del objeto con etiquetas temáticas, para imitar al LLM
_ETIQUETAS_POR_PALABRA = {
    "congreso": "Institucional",
    "gala": "Institucional",
    "premios": "Institucional",
    "gastron": "Gastronomía",
    "showcooking": "Gastronomía",
    "cata": "Gastronomía",
    "participación": "Formación",
    "taller": "Formación",
    "jornada": "Formación",
    "cultura": "Cultura",
    "energética": "Sostenibilidad",
    "movilidad": "Sostenibilidad",
}


# devuelvo las convocatorias de ejemplo como si las hubiera scrapeado la web
def obtener_convocatorias() -> list[dict]:
    # entrego una copia de la lista de ejemplos
    return list(EJEMPLOS)


# estructuro una convocatoria cruda sin llamar al LLM (los ejemplos ya vienen limpios)
def extraer_convocatoria(crudo: dict) -> Convocatoria:
    # construyo el objeto Convocatoria leyendo los campos del diccionario de ejemplo
    return Convocatoria(
        id_expediente=crudo["id_expediente"],
        diputacion=crudo["diputacion"],
        objeto=crudo["objeto"],
        organo_convocante=crudo["organo_convocante"],
        importe=crudo.get("importe"),
        plazo_presentacion=crudo.get("plazo_presentacion"),
        enlace_pliego=crudo["enlace_pliego"],
        fecha_publicacion=crudo.get("fecha_publicacion"),
        fecha_ultima_publicacion=crudo.get("fecha_ultima_publicacion"),
    )


# deduzco unas etiquetas temáticas a partir del texto del objeto
def _etiquetas(objeto: str) -> list[str]:
    # paso el objeto a minúsculas para comparar sin líos de mayúsculas
    texto = objeto.lower()
    # recojo cada etiqueta cuya palabra clave aparezca en el objeto, sin repetir
    encontradas: list[str] = []
    for palabra, etiqueta in _ETIQUETAS_POR_PALABRA.items():
        if palabra in texto and etiqueta not in encontradas:
            encontradas.append(etiqueta)
    # si no encontré ninguna, pongo una genérica para que nunca quede vacío
    return encontradas or ["Eventos"]


# decido si una convocatoria es relevante con una heurística simple (sin LLM)
def evaluar_relevancia(convocatoria: Convocatoria) -> VeredictoRelevancia:
    # paso el objeto a minúsculas
    texto = convocatoria.objeto.lower()
    # es relevante salvo que aparezca alguna palabra de las "no relevantes"
    relevante = not any(palabra in texto for palabra in _PALABRAS_NO_RELEVANTES)
    # redacto un motivo acorde, dirigido al equipo de Mitumi
    if relevante:
        motivo = (
            "Es un servicio de organización de eventos que encaja con vuestro perfil "
            "(gestión integral, producción y secretaría técnica). [demo]"
        )
    else:
        motivo = (
            "Es obra pública o suministro, fuera de vuestro perfil como agencia de "
            "eventos. [demo]"
        )
    # devuelvo el veredicto con las etiquetas deducidas del objeto
    return VeredictoRelevancia(
        relevante=relevante,
        motivo=motivo,
        etiquetas=_etiquetas(convocatoria.objeto),
    )
