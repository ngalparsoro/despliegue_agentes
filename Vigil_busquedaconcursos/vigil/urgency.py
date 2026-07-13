"""Semáforo de urgencia: calcula cuántos días hábiles quedan para presentarse.

Nota sobre "días hábiles": aquí cuento solo de lunes a viernes (excluyo fines
de semana). NO tengo en cuenta los festivos de Euskadi, así que la cuenta es
aproximada; para el MVP 2.0 es suficiente. Si en el futuro hace falta el
cálculo exacto, habría que añadir un calendario de festivos.
"""

# traigo utilidades de fecha y hora para trabajar con los plazos
from datetime import date, datetime, timedelta

# traigo el molde Urgencia que voy a devolver
from vigil.schemas import Urgencia

# marco qué palabras del estado de tramitación indican que aún se puede presentar
_ESTADOS_ABIERTOS = ("abierto", "plazo de presentaci")


# cuento los días hábiles (lunes a viernes) desde mañana hasta la fecha límite
def _dias_habiles(desde: date, hasta: date) -> int:
    # si la fecha límite ya pasó, devuelvo 0
    if hasta < desde:
        return 0
    # empiezo la cuenta a cero
    contador = 0
    # empiezo a mirar desde el día siguiente a hoy
    dia = desde + timedelta(days=1)
    # avanzo día a día hasta pasar la fecha límite
    while dia <= hasta:
        # si el día es de lunes (0) a viernes (4), lo cuento
        if dia.weekday() < 5:
            contador += 1
        # paso al día siguiente
        dia += timedelta(days=1)
    # devuelvo el total de días hábiles
    return contador


# convierto el texto del plazo en una fecha de verdad
def _parsear_plazo(plazo_texto: str | None) -> date | None:
    # si no hay texto, no puedo hacer nada
    if not plazo_texto:
        return None
    # pruebo los formatos que suele traer la web (con hora y sin hora)
    for formato in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        # intento interpretar el texto con este formato
        try:
            # si funciona, me quedo solo con la parte de la fecha
            return datetime.strptime(plazo_texto.strip(), formato).date()
        # si este formato no encaja, pruebo el siguiente
        except ValueError:
            continue
    # si ninguno encajó, devuelvo None
    return None


# calculo el semáforo de urgencia de una convocatoria
def calcular_urgencia(
    plazo_presentacion: str | None,
    estado_tramitacion: str | None = None,
    hoy: date | None = None,
) -> Urgencia:
    """Devuelve un objeto Urgencia con el nivel, los días hábiles y la etiqueta."""
    # si no me dan el día de hoy, uso la fecha actual
    hoy = hoy or date.today()

    # convierto el estado a minúsculas para compararlo cómodamente
    estado = (estado_tramitacion or "").lower()
    # si el estado existe pero no está entre los "abiertos", lo doy por cerrado
    if estado and not any(palabra in estado for palabra in _ESTADOS_ABIERTOS):
        # devuelvo urgencia "cerrado" (ya no se puede presentar)
        return Urgencia(nivel="cerrado", dias_habiles_restantes=None, etiqueta="CERRADO")

    # intento sacar la fecha límite del texto
    limite = _parsear_plazo(plazo_presentacion)
    # si no consigo la fecha, marco la urgencia como desconocida
    if limite is None:
        return Urgencia(
            nivel="desconocida", dias_habiles_restantes=None, etiqueta="PLAZO SIN DETERMINAR"
        )

    # si la fecha límite ya pasó, lo marco como cerrado
    if limite < hoy:
        return Urgencia(nivel="cerrado", dias_habiles_restantes=0, etiqueta="PLAZO CERRADO")

    # cuento los días hábiles que quedan hasta la fecha límite
    dias = _dias_habiles(hoy, limite)

    # si quedan 5 días hábiles o menos, es urgencia alta
    if dias <= 5:
        nivel = "alta"
    # si quedan entre 6 y 15, es urgencia media
    elif dias <= 15:
        nivel = "media"
    # si quedan más de 15, es urgencia baja
    else:
        nivel = "baja"

    # preparo un texto en singular o plural según los días
    palabra_dia = "día hábil" if dias == 1 else "días hábiles"
    # construyo la etiqueta que se verá en el email
    etiqueta = f"URGENCIA {nivel.upper()} · {dias} {palabra_dia}"
    # devuelvo el objeto Urgencia completo
    return Urgencia(nivel=nivel, dias_habiles_restantes=dias, etiqueta=etiqueta)
