"""Conexión con Composio y funciones directas de Gmail."""

import base64
import html
import json
import re
from email.utils import parsedate_to_datetime
from functools import lru_cache

from composio import (
    Composio,
    SESSION_PRESET_DIRECT_TOOLS,
)
from composio_openai import OpenAIProvider

from src.memoria import (
    obtener_ids_procesados,
    obtener_registro_correo,
)
from src.parametros import (
    ALLOW_CREATE_DRAFTS,
    ALLOW_MARK_AS_READ,
    COMPOSIO_API_KEY,
    COMPOSIO_USER_ID,
    GMAIL_QUERY,
    MAX_EMAILS_PER_RUN,
    REQUIRE_THREAD_FOR_DRAFT,
)


def convertir_resultado(resultado):
    """Convierte una respuesta externa en diccionario."""

    if hasattr(resultado, "model_dump"):
        resultado = resultado.model_dump()

    if isinstance(resultado, dict):
        return resultado

    if isinstance(resultado, str):
        try:
            return json.loads(resultado)
        except json.JSONDecodeError:
            return {"texto": resultado}

    return {"texto": str(resultado)}


def buscar_valor(objeto, claves):
    """Busca recursivamente el primer valor solicitado."""

    if isinstance(objeto, dict):
        for clave in claves:
            valor = objeto.get(clave)

            if valor not in [None, "", [], {}]:
                return valor

        for valor in objeto.values():
            encontrado = buscar_valor(
                valor,
                claves,
            )

            if encontrado not in [None, "", [], {}]:
                return encontrado

    elif isinstance(objeto, list):
        for elemento in objeto:
            encontrado = buscar_valor(
                elemento,
                claves,
            )

            if encontrado not in [None, "", [], {}]:
                return encontrado

    return None


def buscar_ids(objeto):
    """Busca identificadores de mensajes de Gmail."""

    ids = []

    if isinstance(objeto, dict):
        for clave, valor in objeto.items():
            if (
                clave in ["messageId", "message_id"]
                and isinstance(valor, str)
            ):
                ids.append(valor)

            elif (
                clave == "id"
                and isinstance(valor, str)
                and not valor.startswith("log_")
            ):
                ids.append(valor)

            elif isinstance(valor, (dict, list)):
                ids += buscar_ids(valor)

    elif isinstance(objeto, list):
        for elemento in objeto:
            ids += buscar_ids(elemento)

    return list(dict.fromkeys(ids))


def obtener_cabecera(headers, nombre):
    """Obtiene una cabecera de Gmail."""

    for header in headers:
        if header.get("name", "").lower() == nombre.lower():
            return header.get("value", "")

    return ""


def extraer_email(texto):
    """Extrae una dirección de correo."""

    coincidencia = re.search(
        r"[A-Za-z0-9._%+-]+"
        r"@[A-Za-z0-9.-]+"
        r"\.[A-Za-z]{2,}",
        texto or "",
    )

    if coincidencia:
        return coincidencia.group(0)

    return ""


def timestamp_fecha(texto):
    """Convierte una fecha de correo en timestamp."""

    try:
        return parsedate_to_datetime(texto).timestamp()
    except (TypeError, ValueError, OverflowError):
        return 0


def limpiar_texto(texto):
    """Convierte HTML sencillo en texto plano."""

    texto = texto or ""
    texto = re.sub(
        r"<br\s*/?>",
        "\n",
        texto,
        flags=re.IGNORECASE,
    )
    texto = re.sub(r"<[^>]+>", "", texto)
    texto = html.unescape(texto)
    texto = re.sub(r"\r\n?", "\n", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)

    return texto.strip()


def resultado_tiene_error(resultado):
    """Comprueba errores habituales de Composio."""

    resultado = convertir_resultado(resultado)

    if resultado.get("ok") is False:
        return True

    if resultado.get("success") is False:
        return True

    if resultado.get("successful") is False:
        return True

    if resultado.get("error") not in [None, "", False, {}]:
        return True

    return False


def crear_cliente_composio():
    """Crea el cliente de Composio."""

    if not COMPOSIO_API_KEY:
        raise ValueError(
            "Falta COMPOSIO_API_KEY en el archivo .env."
        )

    return Composio(
        provider=OpenAIProvider(),
        api_key=COMPOSIO_API_KEY,
    )


@lru_cache(maxsize=1)
def obtener_sesion_gmail():
    """Crea una sesión directa para Gmail."""

    composio = crear_cliente_composio()

    return composio.create(
        user_id=COMPOSIO_USER_ID,
        toolkits=["gmail"],
        session_preset=SESSION_PRESET_DIRECT_TOOLS,
    )


def decodificar_cuerpo(data):
    """Decodifica un cuerpo base64 URL-safe de Gmail."""

    if not data:
        return ""

    try:
        data += "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(data).decode(
            "utf-8",
            errors="ignore",
        )
    except (ValueError, TypeError):
        return ""


def extraer_textos_payload(objeto):
    """Extrae texto plano o HTML del payload multipart."""

    textos = []

    if isinstance(objeto, dict):
        mime_type = objeto.get("mimeType", "")
        body = objeto.get("body", {})

        if isinstance(body, dict):
            data = body.get("data")

            if data and (
                mime_type.startswith("text/plain")
                or mime_type.startswith("text/html")
            ):
                texto = limpiar_texto(
                    decodificar_cuerpo(data)
                )

                if texto:
                    textos.append(texto)

        for valor in objeto.values():
            textos += extraer_textos_payload(valor)

    elif isinstance(objeto, list):
        for elemento in objeto:
            textos += extraer_textos_payload(elemento)

    return textos


def extraer_adjuntos_payload(objeto):
    """Extrae metadatos de adjuntos sin descargarlos."""

    adjuntos = []

    if isinstance(objeto, dict):
        nombre = objeto.get("filename") or objeto.get("name")

        if nombre:
            body = objeto.get("body", {})
            body = body if isinstance(body, dict) else {}

            adjuntos.append(
                {
                    "nombre": nombre,
                    "mime_type": objeto.get("mimeType", ""),
                    "size_bytes": body.get("size", 0),
                    "attachment_id": body.get("attachmentId", ""),
                }
            )

        for valor in objeto.values():
            adjuntos += extraer_adjuntos_payload(valor)

    elif isinstance(objeto, list):
        for elemento in objeto:
            adjuntos += extraer_adjuntos_payload(elemento)

    return adjuntos


def preparar_correo(resultado):
    """Reduce una respuesta de Gmail al formato interno."""

    respuesta = convertir_resultado(resultado)
    datos = respuesta.get("data", respuesta)
    datos = datos if isinstance(datos, dict) else {}
    payload = datos.get("payload", {})
    payload = payload if isinstance(payload, dict) else {}
    headers = payload.get("headers", [])
    headers = headers if isinstance(headers, list) else []

    cuerpo = (
        datos.get("messageText")
        or datos.get("body")
        or datos.get("text")
        or datos.get("snippet")
        or ""
    )

    if isinstance(cuerpo, dict):
        data_cuerpo = cuerpo.get("data")

        if data_cuerpo:
            cuerpo = decodificar_cuerpo(data_cuerpo)
        else:
            cuerpo = (
                cuerpo.get("text")
                or cuerpo.get("content")
                or ""
            )

    cuerpo = limpiar_texto(cuerpo)

    if not cuerpo:
        textos = extraer_textos_payload(payload)
        cuerpo = "\n\n".join(
            dict.fromkeys(textos)
        )

    adjuntos = []

    for adjunto in datos.get("attachments", []) or []:
        if isinstance(adjunto, dict):
            adjuntos.append(
                {
                    "nombre": (
                        adjunto.get("filename")
                        or adjunto.get("name")
                        or "adjunto_sin_nombre"
                    ),
                    "mime_type": (
                        adjunto.get("mimeType")
                        or adjunto.get("mime_type")
                        or ""
                    ),
                    "size_bytes": (
                        adjunto.get("size")
                        or adjunto.get("size_bytes")
                        or 0
                    ),
                    "attachment_id": (
                        adjunto.get("attachmentId")
                        or adjunto.get("attachment_id")
                        or ""
                    ),
                }
            )

    adjuntos += extraer_adjuntos_payload(payload)

    adjuntos_unicos = []
    vistos = set()

    for adjunto in adjuntos:
        clave = (
            adjunto.get("nombre"),
            adjunto.get("size_bytes"),
            adjunto.get("attachment_id"),
        )

        if clave not in vistos:
            vistos.add(clave)
            adjuntos_unicos.append(adjunto)

    labels = (
        datos.get("labelIds")
        or datos.get("label_ids")
        or buscar_valor(
            respuesta,
            ["labelIds", "label_ids", "labels"],
        )
        or []
    )

    if isinstance(labels, str):
        labels = [labels]

    return {
        "message_id": (
            datos.get("messageId")
            or datos.get("id")
            or ""
        ),
        "thread_id": (
            datos.get("threadId")
            or datos.get("thread_id")
            or ""
        ),
        "remitente": obtener_cabecera(
            headers,
            "From",
        ) or datos.get("sender", ""),
        "destinatario": obtener_cabecera(
            headers,
            "To",
        ),
        "fecha": obtener_cabecera(
            headers,
            "Date",
        ),
        "asunto": obtener_cabecera(
            headers,
            "Subject",
        ) or datos.get("subject", ""),
        "cuerpo": cuerpo[:6000],
        "adjuntos": adjuntos_unicos,
        "labels": labels,
    }


def obtener_correo_por_id(message_id):
    """Lee un correo concreto."""

    sesion = obtener_sesion_gmail()

    resultado = sesion.execute(
        "GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID",
        arguments={
            "format": "full",
            "message_id": message_id,
            "user_id": "me",
        },
    )

    correo = preparar_correo(resultado)
    correo["message_id"] = correo["message_id"] or message_id

    return correo


def obtener_correos_no_leidos():
    """Obtiene correos no leídos por orden cronológico."""

    sesion = obtener_sesion_gmail()

    listado = sesion.execute(
        "GMAIL_FETCH_EMAILS",
        arguments={
            "ids_only": True,
            "include_payload": False,
            "include_spam_trash": False,
            "label_ids": ["INBOX", "UNREAD"],
            "max_results": MAX_EMAILS_PER_RUN,
            "page_token": "",
            "query": GMAIL_QUERY,
            "user_id": "me",
            "verbose": False,
        },
    )

    ids = buscar_ids(
        convertir_resultado(listado)
    )
    procesados = set(
        obtener_ids_procesados()
    )
    correos = []

    for message_id in ids:
        if message_id in procesados:
            continue

        correo = obtener_correo_por_id(message_id)
        correo["_registro_previo"] = obtener_registro_correo(
            message_id
        )
        correo["_orden"] = timestamp_fecha(
            correo.get("fecha")
        )
        correos.append(correo)

    correos.sort(
        key=lambda correo: correo["_orden"]
    )

    for correo in correos:
        correo.pop("_orden", None)

    return correos


def crear_borrador(message_id, asunto, cuerpo):
    """Crea un borrador. Nunca lo envía."""

    if not ALLOW_CREATE_DRAFTS:
        return {
            "ok": False,
            "estado": "borradores_desactivados",
        }

    if not cuerpo.strip():
        return {
            "ok": False,
            "estado": "cuerpo_vacio",
        }

    correo = obtener_correo_por_id(message_id)
    destinatario = extraer_email(
        correo.get("remitente")
    )
    thread_id = correo.get("thread_id")

    if not destinatario:
        return {
            "ok": False,
            "estado": "sin_destinatario",
        }

    if REQUIRE_THREAD_FOR_DRAFT and not thread_id:
        return {
            "ok": False,
            "estado": "sin_thread_id",
        }

    argumentos = {
        "recipient_email": destinatario,
        "extra_recipients": [],
        "cc": [],
        "bcc": [],
        "body": limpiar_texto(cuerpo),
        "is_html": False,
        "user_id": "me",
    }

    if thread_id:
        argumentos["thread_id"] = thread_id
        argumentos["subject"] = ""
    else:
        argumentos["subject"] = asunto

    sesion = obtener_sesion_gmail()
    resultado = convertir_resultado(
        sesion.execute(
            "GMAIL_CREATE_EMAIL_DRAFT",
            arguments=argumentos,
        )
    )

    if resultado_tiene_error(resultado):
        return {
            "ok": False,
            "estado": "error_creando_borrador",
            "resultado": resultado,
        }

    draft_id = buscar_valor(
        resultado,
        ["draft_id", "draftId", "id"],
    )

    return {
        "ok": True,
        "estado": "borrador_creado",
        "draft_id": draft_id or "",
        "destinatario": destinatario,
        "thread_id": thread_id,
        "hilo_mantenido": bool(thread_id),
    }


def correo_esta_leido(message_id):
    """Comprueba que Gmail ya no devuelve UNREAD."""

    correo = obtener_correo_por_id(message_id)
    labels = {
        str(label).upper()
        for label in correo.get("labels", [])
    }

    return "UNREAD" not in labels


def marcar_como_leido(message_id, thread_id=""):
    """Quita UNREAD y verifica el resultado."""

    if not ALLOW_MARK_AS_READ:
        return {
            "ok": False,
            "estado": "cambio_estado_desactivado",
        }

    sesion = obtener_sesion_gmail()
    intentos = []

    if thread_id:
        intentos.append(
            (
                "GMAIL_MODIFY_THREAD_LABELS",
                {
                    "thread_id": thread_id,
                    "add_label_ids": [],
                    "remove_label_ids": ["UNREAD"],
                    "user_id": "me",
                },
            )
        )

    intentos.append(
        (
            "GMAIL_MODIFY_EMAIL_LABELS",
            {
                "message_id": message_id,
                "add_label_ids": [],
                "remove_label_ids": ["UNREAD"],
                "user_id": "me",
            },
        )
    )

    errores = []

    for nombre, argumentos in intentos:
        try:
            resultado = convertir_resultado(
                sesion.execute(
                    nombre,
                    arguments=argumentos,
                )
            )

            if resultado_tiene_error(resultado):
                errores.append(
                    {
                        "tool": nombre,
                        "resultado": resultado,
                    }
                )
                continue

            verificado = correo_esta_leido(
                message_id
            )

            if verificado:
                return {
                    "ok": True,
                    "estado": "correo_marcado_leido",
                    "tool": nombre,
                    "verificado": True,
                }

            errores.append(
                {
                    "tool": nombre,
                    "resultado": "UNREAD sigue presente",
                }
            )

        except Exception as error:
            errores.append(
                {
                    "tool": nombre,
                    "error": str(error),
                }
            )

    return {
        "ok": False,
        "estado": "error_marcando_leido",
        "errores": errores,
    }
