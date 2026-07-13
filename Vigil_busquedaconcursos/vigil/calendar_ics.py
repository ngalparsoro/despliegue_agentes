"""Generación de archivos .ics (calendario) para las convocatorias relevantes.

Un .ics es simplemente un archivo de texto con un formato estándar que
entienden Google Calendar, Outlook, etc. Lo construyo a mano (sin librería
externa) porque es sencillo y así no añado dependencias.
"""

# traigo utilidades de fecha para dar formato a las fechas del calendario
from datetime import datetime

# traigo el molde Convocatoria para saber qué datos tengo
from vigil.schemas import Convocatoria


# escapo los caracteres especiales que el formato .ics no admite tal cual
def _escapar(texto: str) -> str:
    # cambio las barras invertidas primero para no pisar los siguientes cambios
    texto = texto.replace("\\", "\\\\")
    # escapo los puntos y comas
    texto = texto.replace(";", "\\;")
    # escapo las comas
    texto = texto.replace(",", "\\,")
    # convierto los saltos de línea en el código especial \n
    texto = texto.replace("\n", "\\n")
    # devuelvo el texto ya limpio
    return texto


# convierto el texto del plazo en el formato de fecha que usa el .ics
def _fecha_ics(plazo_texto: str | None) -> str | None:
    # si no hay plazo, no puedo crear la fecha
    if not plazo_texto:
        return None
    # pruebo los formatos que suele traer la web (con hora y sin hora)
    for formato in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        # intento interpretar el texto con este formato
        try:
            # si funciona, convierto la fecha al formato del calendario (aaaammddThhmmss)
            return datetime.strptime(plazo_texto.strip(), formato).strftime("%Y%m%dT%H%M%S")
        # si este formato no encaja, pruebo el siguiente
        except ValueError:
            continue
    # si ninguno encajó, devuelvo None
    return None


# creo el contenido de un archivo .ics para una convocatoria
def generar_ics(convocatoria: Convocatoria) -> str | None:
    """Devuelve el texto de un archivo .ics, o None si no hay fecha límite válida."""
    # convierto el plazo a formato de calendario
    fecha = _fecha_ics(convocatoria.plazo_presentacion)
    # si no consigo una fecha válida, no genero nada
    if fecha is None:
        return None

    # preparo el título del evento (fecha límite + objeto del concurso)
    titulo = _escapar(f"Fecha límite: {convocatoria.objeto}")
    # preparo la descripción con el órgano y el enlace al pliego
    descripcion = _escapar(
        f"Órgano convocante: {convocatoria.organo_convocante}\n"
        f"Enlace al pliego: {convocatoria.enlace_pliego}"
    )
    # apunto el momento en que genero el archivo (en formato calendario)
    ahora = datetime.now().strftime("%Y%m%dT%H%M%S")

    # armo el texto del .ics juntando todas las líneas obligatorias
    lineas = [
        # abro el calendario
        "BEGIN:VCALENDAR",
        # indico la versión del formato
        "VERSION:2.0",
        # identifico quién genera el archivo
        "PRODID:-//Vigil//Agente de licitaciones//ES",
        # abro el evento
        "BEGIN:VEVENT",
        # pongo un identificador único usando el expediente
        f"UID:{convocatoria.id_expediente}@vigil",
        # pongo la fecha en la que se creó el evento
        f"DTSTAMP:{ahora}",
        # pongo la fecha de inicio (la fecha límite del concurso)
        f"DTSTART:{fecha}",
        # pongo la fecha de fin igual a la de inicio (es un aviso puntual)
        f"DTEND:{fecha}",
        # pongo el título del evento
        f"SUMMARY:{titulo}",
        # pongo la descripción del evento
        f"DESCRIPTION:{descripcion}",
        # añado un recordatorio que avisa 1 día antes
        "BEGIN:VALARM",
        "TRIGGER:-P1D",
        "ACTION:DISPLAY",
        "DESCRIPTION:Recordatorio: fecha límite de licitación",
        "END:VALARM",
        # cierro el evento
        "END:VEVENT",
        # cierro el calendario
        "END:VCALENDAR",
    ]
    # uno todas las líneas con saltos de línea al estilo de los .ics
    return "\r\n".join(lineas)


# invento un nombre de archivo limpio para el .ics
def nombre_fichero_ics(convocatoria: Convocatoria) -> str:
    # cojo el id de expediente y cambio los caracteres raros por guiones bajos
    seguro = "".join(c if c.isalnum() else "_" for c in convocatoria.id_expediente)
    # devuelvo el nombre con la extensión .ics
    return f"{seguro}.ics"
