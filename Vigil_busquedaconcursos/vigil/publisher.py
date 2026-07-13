"""Publicador hacia la plataforma Mitumi BackStage (versión sin email).

En vez de enviar un correo, esta versión escribe un "contrato" JSON con los
concursos relevantes del día, más un archivo .ics por concurso. La plataforma
lee ese JSON para su sección "Concursos Públicos".

El formato es autodescriptivo: incluye todos los datos estructurados (título,
organismo, fechas, importe, urgencia, etiquetas, si es modificación y el motivo
de encaje), para que la plataforma decida qué mostrar y cómo agruparlo.

De momento el destino es un fichero local; cuando el compañero de la plataforma
defina su mecanismo (API REST o base de datos), solo habría que cambiar la
función `publicar` para enviar el mismo JSON por ese canal.
"""

# traigo json para escribir el fichero de salida
import json
# traigo logging para avisar de lo que hago o de los fallos
import logging
# traigo os para crear las carpetas de salida
import os
# traigo utilidades de fecha para el sello de tiempo y las fechas ISO
from datetime import datetime

# traigo la carpeta de salida desde la configuración
from vigil.config import OUTPUT_DIR
# traigo las funciones que generan el archivo .ics de cada concurso
from vigil.calendar_ics import generar_ics, nombre_fichero_ics
# traigo el helper compartido que pasa el plazo a formato ISO
from vigil.dates import plazo_a_iso
# traigo el molde Alerta que agrupa todo lo de una convocatoria
from vigil.schemas import Alerta

# creo un registrador con el nombre de este módulo
logger = logging.getLogger(__name__)


# convierto una alerta en el diccionario que entiende la plataforma
def _alerta_a_dict(alerta: Alerta, archivo_ics: str | None) -> dict:
    # saco las piezas para escribir más corto
    conv = alerta.convocatoria
    ver = alerta.veredicto
    urg = alerta.urgencia
    # devuelvo el diccionario con todos los datos del concurso
    return {
        # el identificador único del expediente
        "id_expediente": conv.id_expediente,
        # el título del concurso (el objeto del contrato)
        "titulo": conv.objeto,
        # el organismo que convoca
        "organismo": conv.organo_convocante,
        # a qué diputación pertenece
        "diputacion": conv.diputacion,
        # la fecha de primera publicación (para que la plataforma agrupe por día)
        "fecha_publicacion": conv.fecha_publicacion,
        # la fecha de última publicación
        "fecha_ultima_publicacion": conv.fecha_ultima_publicacion,
        # el plazo tal como aparece en la web
        "plazo_presentacion": conv.plazo_presentacion,
        # el plazo en formato ISO, más cómodo para la plataforma
        "plazo_iso": plazo_a_iso(conv.plazo_presentacion),
        # el importe sin IVA
        "importe": conv.importe,
        # el enlace al pliego completo
        "enlace_pliego": conv.enlace_pliego,
        # el semáforo de urgencia (nivel, días y etiqueta)
        "urgencia": {
            "nivel": urg.nivel,
            "dias_habiles_restantes": urg.dias_habiles_restantes,
            "etiqueta": urg.etiqueta,
        },
        # las etiquetas temáticas
        "etiquetas": ver.etiquetas,
        # si es una modificación de un concurso ya avisado
        "es_modificacion": alerta.es_modificacion,
        # el motivo de encaje con Mitumi (lo que la plataforma muestra como análisis)
        "motivo": ver.motivo,
        # los requisitos que no se pudieron verificar contra el perfil
        "campos_no_verificables": ver.campos_no_verificables,
        # el nombre del archivo .ics asociado (o None si no hay plazo válido)
        "archivo_ics": archivo_ics,
    }


# escribo el archivo .ics de una alerta en la carpeta de salida
def _escribir_ics(alerta: Alerta, carpeta_ics: str) -> str | None:
    # genero el contenido del .ics de esta convocatoria
    ics = generar_ics(alerta.convocatoria)
    # si no hay .ics (sin fecha válida), no escribo nada
    if ics is None:
        return None
    # invento el nombre del archivo
    nombre = nombre_fichero_ics(alerta.convocatoria)
    # construyo la ruta completa del archivo
    ruta = os.path.join(carpeta_ics, nombre)
    # escribo el contenido del .ics en el archivo
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(ics)
    # devuelvo la ruta relativa con barra normal (más portable para la web)
    return f"ics/{nombre}"


# publico las alertas hacia la plataforma (escribe el JSON y los .ics)
def publicar(alertas: list[Alerta]) -> bool:
    """Escribe el JSON y los .ics en la carpeta de salida.

    Devuelve True si se escribió bien, False si falló (el error queda logueado).
    Se escribe siempre, aunque no haya concursos, para que la plataforma sepa
    que hoy no hubo novedades (lista vacía).
    """
    # intento escribir los archivos y capturo cualquier fallo
    try:
        # me aseguro de que existe la carpeta de salida
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        # preparo la subcarpeta para los .ics
        carpeta_ics = os.path.join(OUTPUT_DIR, "ics")
        # me aseguro de que existe la subcarpeta de .ics
        os.makedirs(carpeta_ics, exist_ok=True)

        # preparo la lista de concursos en formato de la plataforma
        concursos = []
        # recorro cada alerta
        for alerta in alertas:
            # escribo su archivo .ics y guardo la ruta
            ruta_ics = _escribir_ics(alerta, carpeta_ics)
            # convierto la alerta a diccionario y la añado a la lista
            concursos.append(_alerta_a_dict(alerta, ruta_ics))

        # armo el objeto completo que leerá la plataforma
        salida = {
            # el momento en que generé este archivo
            "generado_en": datetime.now().isoformat(),
            # de dónde vienen los datos
            "fuente": "KontratazioA — Diputaciones Forales (Araba, Gipuzkoa, Bizkaia)",
            # cuántos concursos relevantes hay hoy
            "total": len(concursos),
            # la lista de concursos
            "concursos": concursos,
        }

        # construyo la ruta del fichero JSON
        ruta_json = os.path.join(OUTPUT_DIR, "concursos.json")
        # escribo el JSON con tildes y bien indentado
        with open(ruta_json, "w", encoding="utf-8") as f:
            json.dump(salida, f, ensure_ascii=False, indent=2)

        # aviso de que todo fue bien
        logger.info("Publicados %d concursos en %s", len(concursos), ruta_json)
        # devuelvo True
        return True
    # si algo falló al escribir...
    except Exception:
        # apunto el error completo en el registro
        logger.exception("Fallo al publicar los concursos hacia la plataforma.")
        # aviso de que no se pudo publicar
        return False
