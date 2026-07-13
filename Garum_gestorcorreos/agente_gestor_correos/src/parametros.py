"""Parámetros del proyecto cargados desde .env."""

import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(override=True)


AGENTE_VERSION = "0.4.0-mitumi-final-simple"

# LLM
LLM_API_KEY = os.getenv(
    "LLM_API_KEY",
    "",
)
LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL",
    "https://api.groq.com/openai/v1",
)
LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "llama-3.1-8b-instant",
)
LLM_TEMPERATURE = float(
    os.getenv(
        "LLM_TEMPERATURE",
        "0.2",
    )
)
LLM_MAX_TOKENS = int(
    os.getenv(
        "LLM_MAX_TOKENS",
        "1200",
    )
)
CLASSIFICATION_MIN_CONFIDENCE = float(
    os.getenv(
        "CLASSIFICATION_MIN_CONFIDENCE",
        "0.80",
    )
)

# Composio
COMPOSIO_API_KEY = os.getenv(
    "COMPOSIO_API_KEY",
    "",
)
COMPOSIO_USER_ID = os.getenv(
    "COMPOSIO_USER_ID",
    "mitumi_correo_pruebas",
)

# Gmail
GMAIL_QUERY = os.getenv(
    "GMAIL_QUERY",
    "is:unread in:inbox newer_than:7d",
)
MAX_EMAILS_PER_RUN = int(
    os.getenv(
        "MAX_EMAILS_PER_RUN",
        "5",
    )
)
ALLOW_CREATE_DRAFTS = (
    os.getenv(
        "ALLOW_CREATE_DRAFTS",
        "true",
    ).lower()
    == "true"
)
REQUIRE_THREAD_FOR_DRAFT = (
    os.getenv(
        "REQUIRE_THREAD_FOR_DRAFT",
        "true",
    ).lower()
    == "true"
)
ALLOW_MARK_AS_READ = (
    os.getenv(
        "ALLOW_MARK_AS_READ",
        "true",
    ).lower()
    == "true"
)
ALLOW_EMAIL_SEND = (
    os.getenv(
        "ALLOW_EMAIL_SEND",
        "false",
    ).lower()
    == "true"
)

# Salida
SHOW_STEPS = (
    os.getenv(
        "SHOW_STEPS",
        "true",
    ).lower()
    == "true"
)

# Rutas
PROMPTS_DIR = Path("prompts")
DATABASE_PATH = Path(
    "data/gestor_correos_mitumi.db"
)
OUTPUTS_DIR = Path(
    "outputs/respuestas_json"
)
