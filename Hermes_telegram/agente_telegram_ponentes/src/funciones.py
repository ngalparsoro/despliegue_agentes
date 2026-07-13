import json
from datetime import datetime
from zoneinfo import ZoneInfo

from config.settings import TIMEZONE, ORDINARY_START_HOUR, ORDINARY_END_HOUR, QUIET_MODE_ENABLED
from config.fuentes import PROMPTS_DIR, LOGS_PATH


def cargar_prompt(nombre_archivo: str) -> str:
    ruta = PROMPTS_DIR / nombre_archivo
    if not ruta.exists():
        return ""
    return ruta.read_text(encoding="utf-8")


def cargar_prompt_compuesto() -> str:
    partes = [
        cargar_prompt("prompt_sistema.md"),
        cargar_prompt("prompt_analisis.md"),
        cargar_prompt("prompt_validacion.md"),
    ]
    return "\n\n".join([p for p in partes if p])


def en_horario_ordinario() -> bool:
    ahora = datetime.now(ZoneInfo(TIMEZONE))
    return ORDINARY_START_HOUR <= ahora.hour <= ORDINARY_END_HOUR


def puede_responder_automaticamente() -> bool:
    if not QUIET_MODE_ENABLED:
        return True
    return en_horario_ordinario()


def guardar_log(nombre: str, datos: dict) -> None:
    LOGS_PATH.mkdir(parents=True, exist_ok=True)
    ruta = LOGS_PATH / nombre
    registro = {
        "timestamp": datetime.now(ZoneInfo(TIMEZONE)).isoformat(),
        **datos,
    }
    with ruta.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def construir_borrador_telegram(chat_id, texto: str, apto_envio_automatico: bool) -> dict:
    return {
        "canal": "telegram",
        "destinatario": chat_id,
        "texto": texto,
        "apto_envio_automatico": apto_envio_automatico,
        "requiere_revision": not apto_envio_automatico,
    }
