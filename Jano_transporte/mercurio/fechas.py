"""Utilidades de fechas: calcular la ventana de viaje y formatear horarios.

A partir de las fechas del evento (inicio y fin) y de los márgenes configurados
(`DIAS_ANTES` / `DIAS_DESPUES`), calculo cuándo llega y cuándo se marcha el
ponente, y de ahí el número de noches de hotel.
"""

# importo las anotaciones modernas para escribir "str | None"
from __future__ import annotations

# traigo date/datetime/timedelta para operar con fechas
from datetime import date, datetime, timedelta

# traigo los márgenes de días configurados
from mercurio.config import DIAS_ANTES, DIAS_DESPUES


# convierto una fecha ISO (YYYY-MM-DD) en un objeto date; None si no se puede
def _a_date(iso: str | None) -> date | None:
    # si no hay fecha, no hay nada que convertir
    if not iso:
        return None
    # intento parsear la fecha; si falla, devuelvo None en vez de reventar
    try:
        return date.fromisoformat(iso[:10])
    except (ValueError, TypeError):
        return None


# calculo la ventana de viaje: (llegada, salida, noches)
def calcular_ventana(fecha_inicio: str, fecha_fin: str) -> tuple[str, str, int]:
    """Devuelve (fecha_llegada_iso, fecha_salida_iso, noches).

    El ponente llega `DIAS_ANTES` antes del inicio y se marcha `DIAS_DESPUES`
    después del fin. Las noches son los días entre llegada y salida (mínimo 1).
    """
    # convierto las fechas del evento a objetos date
    inicio = _a_date(fecha_inicio)
    fin = _a_date(fecha_fin)
    # si no tengo inicio, no puedo calcular nada coherente
    if inicio is None:
        # devuelvo las fechas tal cual y una noche por defecto
        return fecha_inicio, fecha_fin, 1
    # si no hay fin, asumo que el evento dura un solo día
    if fin is None or fin < inicio:
        fin = inicio
    # la llegada es unos días antes del inicio
    llegada = inicio - timedelta(days=DIAS_ANTES)
    # la salida es unos días después del fin
    salida = fin + timedelta(days=DIAS_DESPUES)
    # las noches son los días entre llegada y salida, con un mínimo de 1
    noches = max(1, (salida - llegada).days)
    # devuelvo las dos fechas en ISO y el número de noches
    return llegada.isoformat(), salida.isoformat(), noches


# combino una fecha ISO con una hora (h, m) y devuelvo un datetime ISO
def combinar(fecha_iso: str, hora: int, minuto: int = 0) -> str:
    """Une una fecha (YYYY-MM-DD) con una hora concreta y devuelve ISO datetime."""
    # parseo la fecha (si falla, uso hoy para no romper la demo)
    d = _a_date(fecha_iso) or date.today()
    # construyo el datetime con la hora y minuto indicados
    return datetime(d.year, d.month, d.day, hora, minuto).isoformat(timespec="minutes")


# sumo minutos a un datetime ISO y devuelvo el nuevo datetime ISO
def sumar_minutos(dt_iso: str, minutos: int) -> str:
    """Devuelve el datetime ISO resultante de sumar `minutos` a `dt_iso`."""
    # parseo el datetime de entrada
    dt = datetime.fromisoformat(dt_iso)
    # sumo los minutos y devuelvo en ISO
    return (dt + timedelta(minutes=minutos)).isoformat(timespec="minutes")
