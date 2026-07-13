from pathlib import Path

import requests

from config.settings import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_POLLING_TIMEOUT,
    TELEGRAM_REQUEST_TIMEOUT,
)
from config.permisos import ALLOW_SEND_TELEGRAM

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else None

BOTON_SELECCIONAR_EVENTO = "📅 Seleccionar evento"
BOTON_RESUMEN_VIAJE = "🧭 Resumen viaje"
BOTON_LUGAR_EVENTO = "📍 Lugar evento"
BOTON_URGENCIA = "🚨 Urgencia"
BOTON_CONTACTAR_MITUMI = "📞 Sí, contactar con MITUMI"

# Una sola tecla en la primera y última fila hace que ocupen todo el ancho.
BOTONES_MENU_PONENTE = [
    [BOTON_SELECCIONAR_EVENTO],
    ["✈️ Vuelo", "🏨 Hotel"],
    ["🚕 Taxi", BOTON_LUGAR_EVENTO],
    [BOTON_RESUMEN_VIAJE, "📄 Documentación"],
    [BOTON_URGENCIA],
]


def leer_updates(offset: int | None = None) -> list[dict]:
    if not BASE_URL:
        return []

    params = {"timeout": TELEGRAM_POLLING_TIMEOUT}
    if offset is not None:
        params["offset"] = offset

    r = requests.get(f"{BASE_URL}/getUpdates", params=params, timeout=TELEGRAM_REQUEST_TIMEOUT)
    data = r.json()
    return data.get("result", []) if data.get("ok") else []


def enviar_mensaje(chat_id: str | int, texto: str) -> dict:
    if not ALLOW_SEND_TELEGRAM:
        return {"ok": True, "modo": "envio_desactivado"}
    if not BASE_URL:
        return {"ok": False, "error": "telegram_token_no_configurado"}

    payload = {"chat_id": chat_id, "text": texto}
    r = requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=TELEGRAM_REQUEST_TIMEOUT)
    return r.json()


def enviar_mensaje_con_botones(chat_id: str | int, texto: str) -> dict:
    """Envía el panel operativo persistente del ponente."""
    if not ALLOW_SEND_TELEGRAM:
        return {"ok": True, "modo": "envio_desactivado"}
    if not BASE_URL:
        return {"ok": False, "error": "telegram_token_no_configurado"}

    payload = {
        "chat_id": chat_id,
        "text": texto,
        "reply_markup": {
            "keyboard": BOTONES_MENU_PONENTE,
            "resize_keyboard": True,
            "one_time_keyboard": False,
            "input_field_placeholder": "Escribe tu consulta o usa los botones...",
        },
    }
    r = requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=TELEGRAM_REQUEST_TIMEOUT)
    return r.json()


def enviar_mensaje_con_eventos(chat_id: str | int, texto: str, eventos: list[dict]) -> dict:
    """Envía los eventos disponibles como botones inline."""
    botones = []
    for evento in eventos:
        id_evento = evento.get("id_evento")
        nombre = evento.get("nombre_evento") or f"Evento {id_evento}"
        fecha = evento.get("fecha")
        etiqueta = f"{nombre} · {fecha}" if fecha else nombre
        botones.append([{"text": etiqueta[:64], "callback_data": f"EVT|{id_evento}"}])

    return _enviar_mensaje_inline(chat_id, texto, botones)


def enviar_mensaje_con_documentos(chat_id: str | int, texto: str, documentos: list[dict]) -> dict:
    """Envía respuesta con botones inline de descarga de documentos."""
    botones = []
    for doc in documentos:
        tipo = doc.get("tipo_documento") or doc.get("tipo") or "documento"
        id_evento = doc.get("id_evento") or ""
        titulo = doc.get("titulo_boton") or doc.get("nombre_archivo") or f"Descargar {tipo}"
        botones.append([{"text": f"📎 {titulo}"[:64], "callback_data": f"DOC|{id_evento}|{tipo}"}])

    return _enviar_mensaje_inline(chat_id, texto, botones)


def enviar_mensaje_con_contacto(chat_id: str | int, texto: str, id_evento: str) -> dict:
    """Ofrece al ponente solicitar contacto humano sobre un dato no disponible."""
    botones = [[{
        "text": BOTON_CONTACTAR_MITUMI,
        "callback_data": f"CNT|{id_evento}",
    }]]
    return _enviar_mensaje_inline(chat_id, texto, botones)


def _enviar_mensaje_inline(chat_id: str | int, texto: str, botones: list[list[dict]]) -> dict:
    if not ALLOW_SEND_TELEGRAM:
        return {"ok": True, "modo": "envio_desactivado"}
    if not BASE_URL:
        return {"ok": False, "error": "telegram_token_no_configurado"}

    payload = {
        "chat_id": chat_id,
        "text": texto,
        "reply_markup": {"inline_keyboard": botones},
    }
    r = requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=TELEGRAM_REQUEST_TIMEOUT)
    return r.json()


def responder_callback(callback_query_id: str, texto: str = "") -> dict:
    if not BASE_URL or not callback_query_id:
        return {"ok": False, "error": "callback_no_configurado"}

    payload = {"callback_query_id": callback_query_id}
    if texto:
        payload["text"] = texto

    r = requests.post(f"{BASE_URL}/answerCallbackQuery", json=payload, timeout=TELEGRAM_REQUEST_TIMEOUT)
    return r.json()


def enviar_documento(chat_id: str | int, ruta_o_url: str, caption: str = "") -> dict:
    """Envía un documento local o una URL por Telegram."""
    if not ALLOW_SEND_TELEGRAM:
        return {"ok": True, "modo": "envio_desactivado"}
    if not BASE_URL:
        return {"ok": False, "error": "telegram_token_no_configurado"}

    ruta = Path(str(ruta_o_url))
    data = {"chat_id": chat_id, "caption": caption}

    if ruta.exists() and ruta.is_file():
        with ruta.open("rb") as f:
            files = {"document": (ruta.name, f)}
            r = requests.post(
                f"{BASE_URL}/sendDocument",
                data=data,
                files=files,
                timeout=TELEGRAM_REQUEST_TIMEOUT,
            )
            return r.json()

    data["document"] = ruta_o_url
    r = requests.post(f"{BASE_URL}/sendDocument", data=data, timeout=TELEGRAM_REQUEST_TIMEOUT)
    return r.json()


def obtener_file_path(file_id: str) -> str | None:
    if not BASE_URL or not file_id:
        return None

    r = requests.get(
        f"{BASE_URL}/getFile",
        params={"file_id": file_id},
        timeout=TELEGRAM_REQUEST_TIMEOUT,
    )
    data = r.json()
    if not data.get("ok"):
        return None
    return data.get("result", {}).get("file_path")


def descargar_archivo(file_id: str, ruta_destino: str | Path) -> bool:
    file_path = obtener_file_path(file_id)
    if not file_path or not TELEGRAM_BOT_TOKEN:
        return False

    url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
    r = requests.get(url, timeout=TELEGRAM_REQUEST_TIMEOUT)
    if r.status_code != 200:
        return False

    ruta = Path(ruta_destino)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(r.content)
    return True


def update_a_payload(update: dict) -> dict | None:
    """Convierte un update de Telegram al contrato común de entrada del agente."""
    callback = update.get("callback_query")
    if callback:
        usuario = callback.get("from", {})
        mensaje = callback.get("message", {}) or {}
        chat = mensaje.get("chat", {}) or {}
        data = callback.get("data", "")
        return {
            "id_evento": None,
            "id_registro": None,
            "tipo_peticion": "callback_telegram",
            "origen": "telegram",
            "usuario_solicitante": str(usuario.get("id")),
            "rol_usuario": "ponente",
            "datos": {
                "telegram_update_id": update.get("update_id"),
                "telegram_callback_query_id": callback.get("id"),
                "telegram_message_id": mensaje.get("message_id"),
                "telegram_user_id": str(usuario.get("id")),
                "telegram_chat_id": chat.get("id"),
                "nombre_usuario": usuario.get("first_name"),
                "texto": data,
                "callback_data": data,
            },
            "contexto": {"fase_evento": "ponentes", "canal": "telegram"},
            "modo": "ejecucion_controlada",
        }

    mensaje = update.get("message") or update.get("edited_message")
    if not mensaje:
        return None

    usuario = mensaje.get("from", {})
    chat = mensaje.get("chat", {})
    documento = _extraer_documento_mensaje(mensaje)

    datos = {
        "telegram_update_id": update.get("update_id"),
        "telegram_message_id": mensaje.get("message_id"),
        "telegram_user_id": str(usuario.get("id")),
        "telegram_chat_id": chat.get("id"),
        "nombre_usuario": usuario.get("first_name"),
        "texto": mensaje.get("text") or mensaje.get("caption") or "",
    }
    if documento:
        datos["documento"] = documento

    return {
        "id_evento": None,
        "id_registro": None,
        "tipo_peticion": "documento_recibido_telegram" if documento else "responder_consulta_ponente_telegram",
        "origen": "telegram",
        "usuario_solicitante": str(usuario.get("id")),
        "rol_usuario": "ponente",
        "datos": datos,
        "contexto": {"fase_evento": "ponentes", "canal": "telegram"},
        "modo": "ejecucion_controlada",
    }


def _extraer_documento_mensaje(mensaje: dict) -> dict | None:
    documento = mensaje.get("document")
    if documento:
        return {
            "tipo_telegram": "document",
            "file_id": documento.get("file_id"),
            "file_unique_id": documento.get("file_unique_id"),
            "file_name": documento.get("file_name"),
            "mime_type": documento.get("mime_type"),
            "file_size": documento.get("file_size"),
        }

    fotos = mensaje.get("photo") or []
    if fotos:
        foto = fotos[-1]
        return {
            "tipo_telegram": "photo",
            "file_id": foto.get("file_id"),
            "file_unique_id": foto.get("file_unique_id"),
            "file_name": "foto_ponente.jpg",
            "mime_type": "image/jpeg",
            "file_size": foto.get("file_size"),
        }

    return None


def extraer_texto_respuesta(resultado_agente: dict) -> str | None:
    for borrador in resultado_agente.get("borradores_generados", []):
        if borrador.get("canal") == "telegram":
            return borrador.get("texto")
    return None
