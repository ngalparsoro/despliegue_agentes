import json
from pathlib import Path

from config.fuentes import DOCUMENTOS_RECIBIDOS_DIR
from config.permisos import ALLOW_DB_READ
from integrations.database import (
    obtener_documentos_ponente_evento_db,
    obtener_eventos_activos_ponente_db,
    obtener_info_ponente_evento_db,
    obtener_ponente_por_telegram_db,
)


def obtener_ponente_por_telegram(telegram_user_id: str) -> dict | None:
    if not ALLOW_DB_READ:
        return None
    return obtener_ponente_por_telegram_db(telegram_user_id)


def obtener_eventos_activos_ponente(id_ponente) -> list[dict]:
    if not ALLOW_DB_READ:
        return []
    return obtener_eventos_activos_ponente_db(id_ponente)


def obtener_info_ponente_evento(id_ponente, id_evento) -> dict | None:
    if not ALLOW_DB_READ:
        return None
    return obtener_info_ponente_evento_db(id_ponente, id_evento)


def obtener_documentos_ponente_evento(
    id_ponente,
    id_evento,
    tipo_documento: str | None = None,
    info: dict | None = None,
) -> list[dict]:
    if not ALLOW_DB_READ:
        return []
    return obtener_documentos_ponente_evento_db(
        id_ponente,
        id_evento,
        tipo_documento,
        info=info,
    )


def registrar_documento_pendiente(nombre_archivo: str, payload: dict) -> Path:
    """Guarda localmente un documento recibido para revisión humana posterior."""
    DOCUMENTOS_RECIBIDOS_DIR.mkdir(parents=True, exist_ok=True)
    ruta = DOCUMENTOS_RECIBIDOS_DIR / nombre_archivo
    ruta.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta


def registrar_comunicacion(payload: dict) -> dict:
    """La versión final no escribe comunicaciones en la BD."""
    return {"ok": True, "modo": "solo_lectura", "registrado": False}


def crear_incidencia(payload: dict) -> dict:
    """Registra la intención en el flujo del agente sin escribir en PostgreSQL."""
    return {"ok": True, "modo": "solo_lectura", "creada": False}
