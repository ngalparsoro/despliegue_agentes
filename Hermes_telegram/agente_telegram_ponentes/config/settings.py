import os
from pathlib import Path

from dotenv import load_dotenv

AGENT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(AGENT_ROOT / ".env")


def _bool(nombre: str, defecto: str = "false") -> bool:
    return os.getenv(nombre, defecto).strip().lower() in {"true", "1", "yes", "si", "sí"}


def _lista(nombre: str, defecto: str = "") -> tuple[str, ...]:
    return tuple(valor.strip() for valor in os.getenv(nombre, defecto).split(",") if valor.strip())


# Agente y zona horaria
AGENT_NAME = os.getenv("AGENT_NAME", "agente_telegram_ponentes")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Madrid")

# LLM compatible con API OpenAI (Groq en la configuración entregada)
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1200"))
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))

# Telegram
TELEGRAM_ENABLED = _bool("TELEGRAM_ENABLED", "false")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_POLLING_TIMEOUT = int(os.getenv("TELEGRAM_POLLING_TIMEOUT", "5"))
TELEGRAM_REQUEST_TIMEOUT = int(os.getenv("TELEGRAM_REQUEST_TIMEOUT", "15"))
TELEGRAM_CHECK_SECONDS = int(os.getenv("TELEGRAM_CHECK_SECONDS", "15"))

# PostgreSQL / Neon, única fuente operativa de datos
DATABASE_URL = os.getenv("DATABASE_URL")
DB_CONNECT_TIMEOUT_SECONDS = int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "10"))
# Hermes solo muestra eventos operativamente activos para el ponente.
# Finalizado y Cancelado quedan fuera porque ya no requieren seguimiento por Telegram.
EVENT_ACTIVE_STATES = _lista(
    "EVENT_ACTIVE_STATES",
    "Planificado,Reservado,Confirmado",
)

# Servicio local
ORDINARY_START_HOUR = int(os.getenv("ORDINARY_START_HOUR", "7"))
ORDINARY_END_HOUR = int(os.getenv("ORDINARY_END_HOUR", "23"))
SERVICE_LOOP_SECONDS = int(os.getenv("SERVICE_LOOP_SECONDS", "2"))
QUIET_MODE_ENABLED = _bool("QUIET_MODE_ENABLED", "true")

# Escalado humano
ADMIN_TELEGRAM_CHAT_ID = os.getenv("ADMIN_TELEGRAM_CHAT_ID")
MIN_CONFIDENCE_TO_REPLY = float(os.getenv("MIN_CONFIDENCE_TO_REPLY", "0.75"))

# Rutas y trazabilidad
DATA_DIR = os.getenv("DATA_DIR", "data")
OUTPUTS_DIR = os.getenv("OUTPUTS_DIR", "outputs")
LOG_DIR = os.getenv("LOG_DIR", "logs")
SHOW_STEPS = _bool("SHOW_STEPS", "true")
SAVE_CONVERSATION_LOG = _bool("SAVE_CONVERSATION_LOG", "true")
