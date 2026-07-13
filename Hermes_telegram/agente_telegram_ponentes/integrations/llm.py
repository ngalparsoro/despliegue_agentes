import json
import unicodedata

from config.settings import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
    LLM_TIMEOUT_SECONDS,
)

client = None

if LLM_API_KEY:
    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            timeout=LLM_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        print(f"[LLM] No se pudo crear cliente LLM: {exc}")
        client = None


def extraer_json_desde_texto(contenido: str) -> dict:
    if not contenido:
        raise ValueError("Respuesta vacía del LLM")

    texto = contenido.strip()
    texto = texto.replace("```json", "").replace("```JSON", "").replace("```", "").strip()

    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio == -1 or fin == -1 or fin <= inicio:
        raise ValueError(f"No se encontró JSON válido en la respuesta del LLM: {contenido}")

    return json.loads(texto[inicio:fin + 1])


def llamar_llm_json(system_prompt: str, user_payload: dict) -> dict:
    """Llama al LLM y espera JSON. Si falla, usa fallback determinista."""
    if client is None:
        return clasificador_simple(user_payload)

    try:
        respuesta = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        )
        contenido = respuesta.choices[0].message.content
        return extraer_json_desde_texto(contenido)
    except Exception as exc:
        print(f"[LLM] Error en llamada LLM: {exc}")
        return clasificador_simple(user_payload)


def _sin_acentos(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in normalizado if not unicodedata.combining(c))


def _detectar_servicio_adicional(texto: str) -> str | None:
    texto = _sin_acentos(texto)
    grupos = {
        "comida_restaurante": [
            "restaurante", "comida", "almuerzo", "cena", "desayuno",
            "catering", "menu", "dieta", "alergia", "intolerancia",
        ],
        "coche_alquiler": [
            "coche de alquiler", "coche alquiler", "alquilar coche",
            "rent a car", "vehiculo de alquiler",
        ],
        "bus": ["autobus", "bus", "minibus", "lanzadera", "shuttle"],
        "parking": ["parking", "aparcamiento", "garaje"],
        "accesibilidad": [
            "accesibilidad", "accesible", "silla de ruedas",
            "movilidad reducida",
        ],
        "wifi": ["wifi", "internet"],
    }
    for servicio, palabras in grupos.items():
        if any(palabra in texto for palabra in palabras):
            return servicio
    return None


def _es_urgencia_textual(texto: str) -> bool:
    """Detecta urgencias evidentes evitando expresiones negativas comunes."""
    texto = _sin_acentos(texto).strip()

    negaciones = [
        "no es urgente",
        "no es una urgencia",
        "sin urgencia",
        "no tengo urgencia",
    ]
    if any(frase in texto for frase in negaciones):
        return False

    patrones_fuertes = [
        "urgente",
        "urgencia",
        "emergencia",
        "vuelo cancelado",
        "avion cancelado",
        "tren cancelado",
        "cancelado",
        "cancelada",
        "cancelacion",
        "han cancelado mi vuelo",
        "han cancelado mi tren",
        "he perdido el billete",
        "no encuentro el billete",
        "estoy perdido",
        "problema grave",
        "retraso critico",
        "necesito ayuda inmediata",
    ]
    return any(patron in texto for patron in patrones_fuertes)


def clasificador_simple(payload: dict) -> dict:
    """Fallback determinista para mantener el agente operativo sin LLM."""
    texto_original = payload.get("texto") or payload.get("mensaje_ponente") or ""
    texto = texto_original.lower().strip()

    if "🚨" in texto or _es_urgencia_textual(texto):
        return _decision(
            "incidencia",
            "alta",
            True,
            "boton_urgencia_o_texto_urgente",
            0.95,
            "He avisado al equipo de MITUMI. Te contactarán lo antes posible. Si puedes, cuéntame brevemente qué ocurre.",
        )

    if "📅" in texto or "seleccionar evento" in texto or "cambiar evento" in texto:
        return _decision("seleccionar_evento", "normal", False, None, 0.95)

    if "🧭" in texto or any(p in texto for p in ["resumen viaje", "timeline", "itinerario", "agenda de viaje"]):
        return _decision("resumen_viaje", "normal", False, None, 0.95)

    if _pide_documento(texto):
        return _decision("solicitud_documento", "normal", False, None, 0.90)

    servicio_adicional = _detectar_servicio_adicional(texto)
    if servicio_adicional:
        return _decision(
            "consulta_servicio_adicional",
            "normal",
            False,
            None,
            0.95,
            servicio_consultado=servicio_adicional,
        )

    if "✈" in texto or any(p in texto for p in ["vuelo", "billete", "avión", "avion", "tren"]):
        intencion = "consulta_viaje"
    elif "🚕" in texto or any(p in texto for p in ["taxi", "traslado", "cómo voy", "como voy", "llegar al hotel", "ir al hotel"]):
        intencion = "consulta_taxi"
    elif "🏨" in texto or any(p in texto for p in ["hotel", "duermo", "alojamiento", "habitación", "habitacion", "check-in", "checkin"]):
        intencion = "consulta_alojamiento"
    elif "📍" in texto or any(p in texto for p in ["dónde es", "donde es", "lugar", "ubicación", "ubicacion", "dirección", "direccion"]):
        intencion = "consulta_lugar"
    elif "🕒" in texto or any(p in texto for p in ["hora", "horario", "charla", "ponencia", "empieza"]):
        intencion = "consulta_horario"
    elif "📄" in texto or any(p in texto for p in ["foto", "cv", "presentación", "presentacion", "ppt", "documento"]):
        intencion = "consulta_documentacion"
    elif any(p in texto for p in ["hola", "buenos días", "buenas", "buenas tardes", "buenos dias"]):
        intencion = "saludo"
    else:
        intencion = "otro"

    urgencia = "alta" if _es_urgencia_textual(texto) else "normal"

    requiere_escalado = intencion == "otro" or urgencia == "alta"
    return _decision(
        "incidencia" if urgencia == "alta" else intencion,
        urgencia,
        requiere_escalado,
        "fallback_reglas" if requiere_escalado else None,
        0.90 if intencion != "otro" else 0.50,
    )


def _pide_documento(texto: str) -> bool:
    verbos = [
        "descargar", "mandame", "mándame", "enviame", "envíame",
        "pasame", "pásame", "adjunta", "adjunto",
    ]
    objetos = [
        "billete", "vuelo", "agenda", "programa", "plano", "ubicacion",
        "ubicación", "ficha", "pdf", "documentacion", "documentación",
        "presentacion", "presentación",
    ]
    return any(v in texto for v in verbos) and any(o in texto for o in objetos)


def _decision(
    intencion: str,
    urgencia: str,
    requiere_escalado: bool,
    motivo: str | None,
    confianza: float,
    respuesta: str = "",
    servicio_consultado: str | None = None,
) -> dict:
    return {
        "intencion": intencion,
        "urgencia": urgencia,
        "respuesta_ponente": respuesta,
        "requiere_escalado": requiere_escalado,
        "motivo_escalado": motivo,
        "confianza": confianza,
        "servicio_consultado": servicio_consultado,
    }
