#!/bin/bash
# =====================================================================
# arrancar_todo.sh — levanta todos los servicios del repo con el .env común
# =====================================================================
# Uso:
#   ./arrancar_todo.sh              # backend :5004 + Operis :5002 + Jano :8001 + Vigil :8000 + gateway :5003
#   ./arrancar_todo.sh --con-hermes # además arranca el bot de Telegram (necesita TELEGRAM_BOT_TOKEN)
#   ./arrancar_todo.sh --parar      # para todo lo arrancado por este script
#
# Los logs de cada servicio quedan en .logs/<servicio>.log
# Ctrl+C (o --parar) detiene todos los procesos lanzados.
# =====================================================================

set -u
RAIZ="$(cd "$(dirname "$0")" && pwd)"
LOGS="$RAIZ/.logs"
PIDS="$LOGS/pids.txt"
mkdir -p "$LOGS"

# --- parar lo arrancado previamente ---------------------------------
if [ "${1:-}" = "--parar" ]; then
    if [ -f "$PIDS" ]; then
        while read -r pid nombre; do
            kill "$pid" 2>/dev/null && echo "parado: $nombre (pid $pid)"
        done < "$PIDS"
        rm -f "$PIDS"
    else
        echo "no hay nada arrancado por este script"
    fi
    exit 0
fi

# --- cargo y EXPORTO el .env común (manda sobre los .env locales) ----
if [ -f "$RAIZ/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$RAIZ/.env"
    set +a
    echo "✓ .env común cargado"
else
    echo "⚠ no existe $RAIZ/.env — copia .env.example a .env y rellénalo."
    echo "  Sigo sin él: cada agente usará su .env local si lo tiene."
fi

# Hermes llama LLM_API_KEY a su clave de Groq: si está vacía, uso GROQ_API_KEY
export LLM_API_KEY="${LLM_API_KEY:-${GROQ_API_KEY:-}}"

# los agentes piden Python 3.10+: uso python3.12 si existe (el python3 del
# sistema es 3.9); se puede forzar otro con PYTHON=... ./arrancar_todo.sh
PYTHON="${PYTHON:-$(command -v python3.12 || command -v python3)}"
echo "✓ usando $PYTHON ($("$PYTHON" --version 2>&1))"

# --- función de arranque: lanza, apunta el pid y avisa ---------------
: > "$PIDS"
lanzar() {
    local nombre="$1" carpeta="$2" comando="$3"
    (cd "$RAIZ/$carpeta" && eval "$comando" > "$LOGS/$nombre.log" 2>&1) &
    local pid=$!
    echo "$pid $nombre" >> "$PIDS"
    echo "→ $nombre arrancando (pid $pid, log en .logs/$nombre.log)"
}

# --- servicios -------------------------------------------------------
# (Garum, el gestor de correos, NO se arranca aquí: no es residente.
#  Se dispara por ciclos con POST :5003/agentes/garum/ciclos o con
#  "python3 main.py" en Garum_gestorcorreos/agente_gestor_correos/)
lanzar backend_5004  backend                                   "$PYTHON app.py"
lanzar lumen_5001    Lumen_buscador/lumen_agente_04             "$PYTHON servidor.py"
lanzar operis_5002   Operis_autocompletado/agente_operis_llm   "$PYTHON servidor.py"
lanzar jano_8001     Jano_transporte                           "$PYTHON serve_demo_mercurio.py"
lanzar vigil_8000    Vigil_busquedaconcursos                   "$PYTHON serve_demo.py"
lanzar gateway_5003  gateway                                   "$PYTHON app.py"

if [ "${1:-}" = "--con-hermes" ]; then
    if [ -z "${TELEGRAM_BOT_TOKEN:-}" ]; then
        echo "⚠ --con-hermes pedido pero TELEGRAM_BOT_TOKEN está vacío: no arranco Hermes"
    else
        lanzar hermes_bot Hermes_telegram/agente_telegram_ponentes "$PYTHON servicio.py"
    fi
fi

# --- al salir con Ctrl+C, paro todo ----------------------------------
parar_todo() {
    echo ""
    while read -r pid nombre; do
        kill "$pid" 2>/dev/null && echo "parado: $nombre"
    done < "$PIDS"
    rm -f "$PIDS"
    exit 0
}
trap parar_todo INT TERM

# --- espero un poco y compruebo la salud de todo ---------------------
echo ""
echo "esperando 4s a que los servicios arranquen…"
sleep 4
"$RAIZ/comprobar_salud.sh" || true

echo ""
echo "todo lanzado. Ctrl+C para parar todo, o ./arrancar_todo.sh --parar desde otra terminal."
wait
