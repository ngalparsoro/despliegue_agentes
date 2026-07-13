#!/bin/bash
# =====================================================================
# comprobar_salud.sh — smoke test de integración: ¿responde cada pieza?
# =====================================================================
# Golpea el health de cada servicio y marca ✓/✗. Sale con código 1 si
# algo esperado no responde (útil para detectar roturas al momento
# cuando alguien sustituya un stub por su agente definitivo).
# =====================================================================

FALLOS=0

comprobar() {
    local nombre="$1" url="$2"
    if curl -s -o /dev/null -m 3 -w "%{http_code}" "$url" | grep -q "200"; then
        echo "  ✓ $nombre  ($url)"
    else
        echo "  ✗ $nombre  ($url) — NO RESPONDE"
        FALLOS=$((FALLOS + 1))
    fi
}

echo "— salud de los servicios —"
comprobar "backend agentes :5004" "http://127.0.0.1:5004/"
comprobar "Lumen :5001         " "http://127.0.0.1:5001/"
comprobar "Operis :5002        " "http://127.0.0.1:5002/"
comprobar "Jano :8001          " "http://127.0.0.1:8001/health"
comprobar "Vigil :8000         " "http://127.0.0.1:8000/health"
comprobar "gateway :5003       " "http://127.0.0.1:5003/salud"

echo ""
echo "— salud vista desde el gateway (agentes reales + stubs) —"
curl -s -m 5 "http://127.0.0.1:5003/salud" | python3 -m json.tool 2>/dev/null || echo "  (gateway no disponible)"

if [ "$FALLOS" -gt 0 ]; then
    echo ""
    echo "⚠ $FALLOS servicio(s) sin responder — mira su log en .logs/"
    exit 1
fi
echo ""
echo "✓ todo responde"
