"""Filtro semántico de relevancia: LLM + business_profile.py → VeredictoRelevancia."""

# traigo json para convertir el texto de la respuesta en diccionario
import json

# traigo el cliente de Groq para hablar con el modelo de lenguaje
from groq import Groq

# traigo el texto del perfil de Mitumi que uso como contexto
from vigil.business_profile import get_business_profile
# traigo mi clave de API y el nombre del modelo desde la configuración
from vigil.config import GROQ_API_KEY, GROQ_MODEL
# traigo el molde de la convocatoria (entrada) y el del veredicto (salida)
from vigil.schemas import Convocatoria, VeredictoRelevancia

# escribo la plantilla de instrucciones; el {perfil} lo relleno luego
_SYSTEM_PROMPT_TEMPLATE = """Eres un analista que decide si una licitación pública encaja \
con el perfil de negocio de Mitumi, una agencia de eventos. Te doy el perfil de Mitumi y \
los datos ya estructurados de una convocatoria. Decide si es relevante para que Mitumi se \
presente, basándote en el encaje real (tipo de evento/servicio, escala, zona geográfica, \
trayectoria con el sector público) — no en la simple coincidencia de palabras sueltas.

PERFIL DE MITUMI:
{perfil}

Devuelve ÚNICAMENTE un objeto JSON con estas claves:
- relevante (boolean)
- motivo (string): explica el encaje o desencaje concreto — qué tipo de evento/servicio es \
y por qué sí o por qué no encaja, y si aplica, qué juega a favor o en contra dado el perfil. \
No basta con decir "es relevante" o "no es relevante". Escribe el motivo dirigiéndote \
directamente al equipo de Mitumi, en segunda persona del plural ("vosotras", "vuestro perfil", \
"os encaja") — no hables de Mitumi en tercera persona ni la nombres como si fuera otra \
empresa.
- etiquetas (array de strings): de 1 a 3 etiquetas temáticas cortas que resuman el área del \
concurso, para que el equipo se reparta la revisión. Usa etiquetas del estilo de estas (o \
parecidas si encajan mejor): "Institucional", "Cultura", "Gastronomía", "Marketing", \
"Formación", "Deporte", "Turismo", "Sostenibilidad", "Tecnología". Pon las etiquetas aunque \
la convocatoria no sea relevante.
- campos_no_verificables (array de strings): requisitos del pliego que no se pueden \
confirmar ni descartar contra el perfil de Mitumi (p. ej. una certificación ISO exigida, un \
mínimo de facturación). Si no hay ninguno, devuelve una lista vacía.

No añadas ninguna clave más."""


# decido si una convocatoria es relevante para Mitumi
def evaluar_relevancia(convocatoria: Convocatoria) -> VeredictoRelevancia:
    """Evalúa si una convocatoria es relevante para Mitumi.

    Lanza una excepción si la llamada al LLM falla o si la respuesta no
    encaja con el schema. Quien llame debe tratarlo igual que un fallo de
    extractor.py: loguear, no marcar la convocatoria como procesada, y
    reintentar al día siguiente (ver sección 9 del build brief).
    """
    # creo el cliente de Groq con mi clave
    client = Groq(api_key=GROQ_API_KEY)
    # relleno la plantilla metiendo dentro el perfil de Mitumi
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(perfil=get_business_profile())
    # pido al modelo su veredicto sobre esta convocatoria
    respuesta = client.chat.completions.create(
        # elijo el modelo que voy a usar
        model=GROQ_MODEL,
        # le paso sus instrucciones y la convocatoria en texto JSON
        messages=[
            # el mensaje de sistema con el perfil y las reglas
            {"role": "system", "content": system_prompt},
            # el mensaje del usuario con los datos de la convocatoria
            {"role": "user", "content": convocatoria.model_dump_json(indent=2)},
        ],
        # obligo al modelo a responder en formato JSON
        response_format={"type": "json_object"},
        # pongo la creatividad a cero para respuestas constantes
        temperature=0,
    )
    # saco el texto de la respuesta del modelo
    contenido = respuesta.choices[0].message.content
    # convierto ese texto JSON en un diccionario de Python
    datos = json.loads(contenido)
    # valido el diccionario contra el molde VeredictoRelevancia y lo devuelvo
    return VeredictoRelevancia.model_validate(datos)
