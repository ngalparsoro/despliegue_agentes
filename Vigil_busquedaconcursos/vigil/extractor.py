"""LLM (Groq) + Pydantic: convocatoria cruda de sources.py → Convocatoria estructurada."""

# traigo json para convertir texto a diccionario y al revés
import json

# traigo el cliente de Groq para hablar con el modelo de lenguaje
from groq import Groq

# traigo mi clave de API y el nombre del modelo desde la configuración
from vigil.config import GROQ_API_KEY, GROQ_MODEL
# traigo el molde Convocatoria para validar lo que devuelve el modelo
from vigil.schemas import Convocatoria

# escribo las instrucciones fijas que le doy al modelo (su "rol")
_SYSTEM_PROMPT = """Eres un asistente que estructura convocatorias de licitación pública \
extraídas de la Plataforma de Contratación Pública de Euskadi. A partir de los campos \
crudos que te paso (ya extraídos del HTML de la web, en español), devuelve ÚNICAMENTE un \
objeto JSON con estas claves exactas:

- id_expediente (string)
- diputacion (string): exactamente uno de "Araba", "Gipuzkoa" o "Bizkaia", según a qué \
diputación foral pertenece el poder adjudicador o la entidad impulsora.
- objeto (string): el objeto del contrato, tal cual.
- organo_convocante (string): el poder adjudicador.
- importe (string o null): el importe si hay uno claro en los datos de entrada, si no null. \
No inventes ni calcules un importe que no esté explícito en la entrada.
- plazo_presentacion (string o null): la fecha límite de presentación tal cual aparece en \
la entrada, o null si no hay una fecha clara.
- enlace_pliego (string): la URL al pliego, tal cual aparece en la entrada.
- fecha_publicacion (string o null): la fecha de primera publicación si está disponible.
- fecha_ultima_publicacion (string o null): la fecha de última publicación si está disponible.

No añadas ninguna clave más. No inventes datos que no estén en la entrada — si un campo no \
se puede determinar con lo que te doy, usa null."""


# convierto el diccionario crudo en un texto bonito para enviárselo al modelo
def _construir_mensaje_usuario(crudo: dict) -> str:
    # transformo el diccionario a texto JSON, respetando tildes y con sangría
    return json.dumps(crudo, ensure_ascii=False, indent=2)


# convierto una convocatoria cruda en un objeto Convocatoria limpio
def extraer_convocatoria(crudo: dict) -> Convocatoria:
    """Convierte un diccionario crudo de sources.py en un objeto Convocatoria.

    Lanza una excepción si la llamada al LLM falla, si la respuesta no es
    JSON válido, o si no encaja con el schema. Quien llame debe capturarla,
    loguear el error y NO marcar la convocatoria como procesada (ver sección
    9 del build brief), para reintentar al día siguiente.
    """
    # creo el cliente de Groq con mi clave
    client = Groq(api_key=GROQ_API_KEY)
    # pido al modelo que me estructure la convocatoria
    respuesta = client.chat.completions.create(
        # elijo el modelo que voy a usar
        model=GROQ_MODEL,
        # le paso dos mensajes: sus instrucciones y los datos crudos
        messages=[
            # el mensaje de sistema con las reglas
            {"role": "system", "content": _SYSTEM_PROMPT},
            # el mensaje del usuario con los datos de la convocatoria
            {"role": "user", "content": _construir_mensaje_usuario(crudo)},
        ],
        # obligo al modelo a responder en formato JSON
        response_format={"type": "json_object"},
        # pongo la creatividad a cero para que sea constante y fiel a los datos
        temperature=0,
    )
    # saco el texto de la respuesta del modelo
    contenido = respuesta.choices[0].message.content
    # convierto ese texto JSON en un diccionario de Python
    datos = json.loads(contenido)
    # valido el diccionario contra el molde Convocatoria y lo devuelvo
    return Convocatoria.model_validate(datos)
