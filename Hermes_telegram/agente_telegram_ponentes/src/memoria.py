import json
from datetime import datetime
from zoneinfo import ZoneInfo

from config.fuentes import DATA_PATH
from config.settings import TIMEZONE

ESTADO_DIR = DATA_PATH / "estado"
ESTADO_EVENTOS_PATH = ESTADO_DIR / "eventos_activos_telegram.json"
ESTADO_CONTACTO_PATH = ESTADO_DIR / "solicitudes_contacto_telegram.json"


def _leer_json(ruta) -> dict:
    ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    if not ruta.exists():
        return {}
    try:
        contenido = json.loads(ruta.read_text(encoding="utf-8"))
        return contenido if isinstance(contenido, dict) else {}
    except Exception:
        return {}


def _guardar_json(ruta, estado: dict) -> None:
    ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")


def obtener_evento_activo_usuario(telegram_user_id: str) -> str | None:
    estado = _leer_json(ESTADO_EVENTOS_PATH)
    registro = estado.get(str(telegram_user_id)) or {}
    id_evento = registro.get("id_evento")
    return str(id_evento) if id_evento is not None else None


def guardar_evento_activo_usuario(
    telegram_user_id: str,
    id_ponente,
    id_evento,
    nombre_evento: str | None = None,
) -> dict:
    estado = _leer_json(ESTADO_EVENTOS_PATH)
    registro = {
        "telegram_user_id": str(telegram_user_id),
        "id_ponente": str(id_ponente) if id_ponente is not None else None,
        "id_evento": str(id_evento) if id_evento is not None else None,
        "nombre_evento": nombre_evento,
        "fecha_seleccion": datetime.now(ZoneInfo(TIMEZONE)).isoformat(),
    }
    estado[str(telegram_user_id)] = registro
    _guardar_json(ESTADO_EVENTOS_PATH, estado)
    return registro


def limpiar_evento_activo_usuario(telegram_user_id: str) -> None:
    estado = _leer_json(ESTADO_EVENTOS_PATH)
    estado.pop(str(telegram_user_id), None)
    _guardar_json(ESTADO_EVENTOS_PATH, estado)


def guardar_solicitud_contacto_pendiente(
    telegram_user_id: str,
    id_ponente,
    id_evento,
    motivo: str,
    mensaje_original: str | None = None,
) -> dict:
    estado = _leer_json(ESTADO_CONTACTO_PATH)
    registro = {
        "telegram_user_id": str(telegram_user_id),
        "id_ponente": str(id_ponente) if id_ponente is not None else None,
        "id_evento": str(id_evento) if id_evento is not None else None,
        "motivo": motivo,
        "mensaje_original": mensaje_original,
        "estado": "pendiente_confirmacion",
        "fecha_creacion": datetime.now(ZoneInfo(TIMEZONE)).isoformat(),
    }
    estado[str(telegram_user_id)] = registro
    _guardar_json(ESTADO_CONTACTO_PATH, estado)
    return registro


def obtener_solicitud_contacto_pendiente(telegram_user_id: str) -> dict | None:
    estado = _leer_json(ESTADO_CONTACTO_PATH)
    registro = estado.get(str(telegram_user_id))
    return dict(registro) if isinstance(registro, dict) else None


def confirmar_solicitud_contacto(telegram_user_id: str) -> dict | None:
    estado = _leer_json(ESTADO_CONTACTO_PATH)
    registro = estado.get(str(telegram_user_id))
    if not isinstance(registro, dict):
        return None
    registro["estado"] = "confirmada"
    registro["fecha_confirmacion"] = datetime.now(ZoneInfo(TIMEZONE)).isoformat()
    estado[str(telegram_user_id)] = registro
    _guardar_json(ESTADO_CONTACTO_PATH, estado)
    return dict(registro)


def limpiar_solicitud_contacto(telegram_user_id: str) -> None:
    estado = _leer_json(ESTADO_CONTACTO_PATH)
    estado.pop(str(telegram_user_id), None)
    _guardar_json(ESTADO_CONTACTO_PATH, estado)
