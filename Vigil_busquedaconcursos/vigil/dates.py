"""Utilidades de fechas compartidas por varios módulos de Vigil.

Aquí vive la conversión del plazo de presentación (tal como viene de la web,
p. ej. "25/07/2026 23:59:00") a formato ISO ("2026-07-25T23:59:00"), que usan
tanto el publicador (para el JSON) como el histórico (para poder filtrar y
ordenar por plazo, y decidir qué concursos siguen "en plazo").
"""

# traigo datetime para interpretar y reformatear las fechas
from datetime import datetime


# convierto el texto del plazo a formato ISO para que sea fácil de ordenar/filtrar
def plazo_a_iso(plazo_texto: str | None) -> str | None:
    # si no hay plazo, devuelvo None
    if not plazo_texto:
        return None
    # pruebo los formatos que suele traer la web (con hora y sin hora)
    for formato in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        # intento interpretar el texto con este formato
        try:
            # si funciona, lo devuelvo en formato ISO (2026-07-25T23:59:00)
            return datetime.strptime(plazo_texto.strip(), formato).isoformat()
        # si este formato no encaja, pruebo el siguiente
        except ValueError:
            continue
    # si ninguno encajó, devuelvo None
    return None
