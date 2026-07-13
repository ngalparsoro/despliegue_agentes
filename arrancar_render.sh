#!/bin/bash
# =====================================================================
# arrancar_render.sh — arranque DENTRO del contenedor (Render/Docker)
# =====================================================================
# Igual que arrancar_todo.sh pero pensado para un contenedor:
# - los agentes y el backend quedan en segundo plano en sus puertos
#   internos de siempre (127.0.0.1), y sus logs salen por la consola
#   del contenedor (el stream de logs de Render);
# - el gateway corre en PRIMER plano escuchando en 0.0.0.0:$PORT, que
#   es lo que Render exige para dar por vivo el servicio.
#
# Credenciales: por variables de entorno del contenedor (panel de
# Render o -e en docker run), nunca por .env dentro de la imagen.
# =====================================================================

set -u
RAIZ="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"

# Hermes y Garum llaman LLM_API_KEY a su clave de Groq: si está vacía,
# se rellena con GROQ_API_KEY (mismo criterio que arrancar_todo.sh)
export LLM_API_KEY="${LLM_API_KEY:-${GROQ_API_KEY:-}}"

# OJO: Render define PORT global (el del gateway). Backend y Lumen leen
# esa misma variable, así que se les pasa la suya inline, como en local.
(cd "$RAIZ/backend" && PORT=5004 HOST=127.0.0.1 "$PYTHON" app.py) &
(cd "$RAIZ/Lumen_buscador/lumen_agente_04" && PORT=5001 "$PYTHON" servidor.py) &
(cd "$RAIZ/Operis_autocompletado/agente_operis_llm" && "$PYTHON" servidor.py) &
(cd "$RAIZ/Jano_transporte" && "$PYTHON" serve_demo_mercurio.py) &
(cd "$RAIZ/Vigil_busquedaconcursos" && "$PYTHON" serve_demo.py) &

# Hermes (bot de Telegram) es opcional: solo si se pide explícitamente
# y hay token. Solo UNA instancia del bot en el mundo a la vez (si ya
# corre en un portátil, no activarlo también aquí: se pisan el polling).
if [ "${ARRANCAR_HERMES:-false}" = "true" ] && [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    (cd "$RAIZ/Hermes_telegram/agente_telegram_ponentes" && "$PYTHON" servicio.py) &
fi

# El gateway, en primer plano y en 0.0.0.0:$PORT (Render lo exige).
# exec: el gateway pasa a ser el proceso principal del contenedor.
exec uvicorn app:app --host 0.0.0.0 --port "${PORT:-5003}" --app-dir "$RAIZ/gateway"
