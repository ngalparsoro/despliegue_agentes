"""
Carga de configuracion de Lumen desde .env (sin dependencias externas).
Si no existe .env (solo .env.example), se usan valores por defecto de modo demo.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def cargar_env(ruta_env: Path = None) -> dict:
    ruta_env = ruta_env or (BASE_DIR / ".env")
    valores = dict(os.environ)

    if not ruta_env.exists():
        ruta_env = BASE_DIR / ".env.example"

    if ruta_env.exists():
        for linea in ruta_env.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, _, valor = linea.partition("=")
            valor = valor.split("#", 1)[0].strip()  # quita comentarios en linea
            valores.setdefault(clave.strip(), valor)

    return valores


SETTINGS = cargar_env()
LLM_PROVIDER = SETTINGS.get("LLM_PROVIDER", "")
LLM_MODEL = SETTINGS.get("LLM_MODEL", "")

# --- Base de datos real (Postgres) - fuente unica de datos de negocio para Lumen ------------
# Sin mock JSON ni API HTTP intermedia: src/lectura_datos.py lee siempre de aqui a traves de
# integrations/db_backend.py (solo lectura, conexion en modo readonly).
DATABASE_URL = SETTINGS.get("DATABASE_URL", "")
