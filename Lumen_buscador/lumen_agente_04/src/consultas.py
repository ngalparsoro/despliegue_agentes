"""
Alias de compatibilidad: la implementacion real del acceso de solo lectura a los datos vive en
src/lectura_datos.py. Este archivo solo re-exporta esas funciones por si algo externo importa
"src.consultas" por el nombre que se documento inicialmente.
"""

from src.lectura_datos import (
    TablaNoPermitida,
    tabla_existe,
    evento_existe,
    resumen_evento,
    ponentes_sin_billete_vuelta,
    ponentes_sin_billete_ida,
    contexto_completo_evento,
)

__all__ = [
    "TablaNoPermitida",
    "tabla_existe",
    "evento_existe",
    "resumen_evento",
    "ponentes_sin_billete_vuelta",
    "ponentes_sin_billete_ida",
    "contexto_completo_evento",
]
