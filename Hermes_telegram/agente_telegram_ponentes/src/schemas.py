from typing import Any
from datetime import datetime
from zoneinfo import ZoneInfo
from config.settings import AGENT_NAME, TIMEZONE

CAMPOS_ENTRADA_OBLIGATORIOS = [
    "id_evento",
    "tipo_peticion",
    "origen",
    "usuario_solicitante",
    "rol_usuario",
    "datos",
    "contexto",
    "modo",
]


def validar_payload_entrada(payload: dict[str, Any]) -> list[str]:
    errores = []
    if not isinstance(payload, dict):
        return ["payload_no_es_diccionario"]

    for campo in CAMPOS_ENTRADA_OBLIGATORIOS:
        if campo not in payload:
            errores.append(f"falta_campo_obligatorio:{campo}")

    if "datos" in payload and not isinstance(payload["datos"], dict):
        errores.append("datos_debe_ser_diccionario")

    if "contexto" in payload and not isinstance(payload["contexto"], dict):
        errores.append("contexto_debe_ser_diccionario")

    return errores


def salida_base(payload: dict[str, Any] | None = None, ok: bool = True) -> dict[str, Any]:
    payload = payload or {}
    return {
        "ok": ok,
        "agente": AGENT_NAME,
        "tipo_peticion": payload.get("tipo_peticion"),
        "resumen": "",
        "datos_detectados": {},
        "acciones_propuestas": [],
        "bloqueos_detectados": [],
        "borradores_generados": [],
        "requiere_validacion_humana": True,
        "nivel_riesgo": "medio",
        "errores": [],
        "trazas": {
            "fuentes_consultadas": [],
            "timestamp": datetime.now(ZoneInfo(TIMEZONE)).isoformat(),
            "modo": payload.get("modo", "propuesta"),
            "origen": payload.get("origen"),
        },
    }


def extraer_datos_telegram(payload: dict[str, Any]) -> dict[str, Any]:
    """Extrae campos de Telegram desde el contrato común.

    Telegram coloca los datos específicos en payload["datos"].
    """
    datos = payload.get("datos", {}) or {}
    return {
        "telegram_user_id": str(datos.get("telegram_user_id") or ""),
        "telegram_chat_id": datos.get("telegram_chat_id"),
        "telegram_update_id": datos.get("telegram_update_id"),
        "telegram_message_id": datos.get("telegram_message_id"),
        "nombre_usuario": datos.get("nombre_usuario"),
        "texto": datos.get("texto") or datos.get("mensaje") or "",
    }
