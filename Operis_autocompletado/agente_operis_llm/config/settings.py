# config/settings.py
# =====================================================================
# SETTINGS - CONFIGURACIÓN DEL AGENTE OPERIS
# =====================================================================
# Carga variables de entorno desde .env y proporciona valores por defecto.
#
# Cambios principales:
#   - Eliminada variable MOTOR_POR_DEFECTO (ya no se usa, siempre "llm")
#   - Se mantienen GROQ_API_KEY y GROQ_MODEL para el motor LLM
# =====================================================================

import os
from pathlib import Path

# =====================================================================
# 1. CARGAR .ENV MANUALMENTE (SIN DEPENDENCIAS EXTERNAS)
# =====================================================================
def cargar_env():
    """
    Carga variables de entorno desde un archivo .env en el directorio raíz.
    
    Formato esperado:
        CLAVE=valor
        # Comentarios
        CLAVE_CON_ESPACIOS="valor con espacios"
    
    Returns:
        dict: Diccionario con las variables cargadas
    """
    env_vars = {}
    
    # Buscar .env en el directorio raíz del proyecto
    base_dir = Path(__file__).resolve().parent.parent
    env_path = base_dir / ".env"
    
    if not env_path.exists():
        return env_vars
    
    with open(env_path, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            
            # Saltar líneas vacías y comentarios
            if not linea or linea.startswith("#"):
                continue
            
            # Separar clave y valor
            if "=" in linea:
                clave, valor = linea.split("=", 1)
                clave = clave.strip()
                valor = valor.strip()
                
                # Quitar comillas si existen
                if valor.startswith('"') and valor.endswith('"'):
                    valor = valor[1:-1]
                elif valor.startswith("'") and valor.endswith("'"):
                    valor = valor[1:-1]
                
                env_vars[clave] = valor
    
    return env_vars


# =====================================================================
# 2. CARGAR VARIABLES DE ENTORNO
# =====================================================================
_env = cargar_env()

# ----- Variables de Groq (motor LLM) -----
# Clave API de Groq. Obligatoria para usar el motor LLM.
GROQ_API_KEY = _env.get("GROQ_API_KEY", os.environ.get("GROQ_API_KEY", ""))

# Modelo de Groq a usar. Por defecto: openai/gpt-oss-120b
GROQ_MODEL = _env.get("GROQ_MODEL", os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"))

# ----- BD real (Neon Postgres), solo lectura -----
# Cadena del rol agente_readonly -- pídesela a Nora, NUNCA la de neondb_owner.
# Ver kit_conexion_agentes_Nora/README.md (DESAFIO_MITUMI/) y src/lectura_bd.py.
# Opcional: si no está configurada, el agente sigue funcionando (no autocarga
# histórico desde BD ni verifica id_evento contra la BD real).
DATABASE_URL = _env.get("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

# ----- Otras variables (mantenidas por compatibilidad) -----
# Estas variables ya no se usan pero se mantienen por si acaso
MOTOR_POR_DEFECTO = "llm"  # Siempre "llm". El motor de reglas ha sido eliminado.

# =====================================================================
# 3. VALIDACIÓN DE CONFIGURACIÓN
# =====================================================================
def validar_configuracion():
    """
    Verifica que la configuración sea válida para ejecutar el agente.
    
    Returns:
        tuple: (es_valida, mensaje_error)
    """
    if not GROQ_API_KEY:
        return False, "Falta GROQ_API_KEY. Defínela en .env o como variable de entorno."
    
    if not GROQ_MODEL:
        return False, "Falta GROQ_MODEL. Defínelo en .env o como variable de entorno."
    
    return True, "Configuración válida"


# =====================================================================
# 4. EXPORTACIÓN EXPLÍCITA
# =====================================================================
__all__ = [
    "GROQ_API_KEY",
    "GROQ_MODEL",
    "DATABASE_URL",
    "MOTOR_POR_DEFECTO",
    "validar_configuracion"
]