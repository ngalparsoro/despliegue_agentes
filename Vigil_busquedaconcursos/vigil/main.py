"""Entry point de Vigil (versión plataforma): orquesta el flujo end-to-end.

Igual que la 2.0 (urgencia, modificaciones, etiquetas y calendario), pero el
último paso no manda email: publica un JSON hacia la plataforma Mitumi
BackStage (ver publisher.py).
"""

# traigo logging para ir dejando mensajes de lo que va pasando
import logging
# traigo os para poder leer el flag de modo demo del entorno
import os

# traigo los módulos de deduplicado, histórico y publicación hacia la plataforma
from vigil import dedupe, history, publisher
# traigo la ruta del fichero de base de datos
from vigil.config import SQLITE_PATH
# traigo la función que estructura cada convocatoria con el LLM
from vigil.extractor import extraer_convocatoria
# traigo la función que decide si una convocatoria es relevante
from vigil.relevance import evaluar_relevancia
# traigo el molde Alerta que junta todo para el email
from vigil.schemas import Alerta
# traigo la función que lee la web y devuelve las convocatorias crudas
from vigil.sources import obtener_convocatorias
# traigo la función que calcula el semáforo de urgencia
from vigil.urgency import calcular_urgencia

# configuro el registro para que muestre fecha, nivel y mensaje
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
# creo mi registrador con un nombre claro
logger = logging.getLogger("vigil.main")


# esta es la función principal que ejecuta todo el proceso
def run() -> None:
    # decido qué funciones uso: las reales o las del modo demo (VIGIL_DEMO)
    # (leo los nombres del módulo para respetar el monkeypatch de los tests)
    if os.environ.get("VIGIL_DEMO"):
        # en modo demo tiro de los datos de ejemplo y salto el LLM
        from vigil import demo
        logger.info("Modo DEMO activado: datos de ejemplo, sin web ni LLM.")
        _obtener, _extraer, _evaluar = (
            demo.obtener_convocatorias, demo.extraer_convocatoria, demo.evaluar_relevancia
        )
    else:
        # en modo normal uso el scraper y los pasos con Groq
        _obtener, _extraer, _evaluar = (
            obtener_convocatorias, extraer_convocatoria, evaluar_relevancia
        )

    # intento leer las convocatorias de la web
    try:
        # llamo al scraper y guardo las convocatorias crudas
        crudas = _obtener()
    # si falla la lectura de la web...
    except Exception:
        # apunto el error y termino sin enviar nada
        logger.exception("Fallo al leer KontratazioA — se aborta sin enviar email.")
        return

    # dejo constancia de cuántas convocatorias he encontrado
    logger.info("Encontradas %d convocatorias en las tres diputaciones.", len(crudas))

    # preparo una lista vacía donde iré metiendo las alertas relevantes
    alertas: list[Alerta] = []

    # abro la base de datos para consultar y guardar lo ya procesado
    with dedupe.get_connection(SQLITE_PATH) as conn:
        # recorro una a una todas las convocatorias crudas
        for cruda in crudas:
            # saco el id de expediente de la convocatoria
            id_expediente = cruda.get("id_expediente")
            # saco el enlace al pliego (o cadena vacía si no hay)
            url = cruda.get("enlace_pliego") or ""
            # saco la fecha de última publicación (para detectar modificaciones)
            fecha_ultima = cruda.get("fecha_ultima_publicacion")

            # si la convocatoria no tiene id, no puedo deduplicarla: la salto
            if not id_expediente:
                # aviso en el registro de que la ignoro
                logger.warning(
                    "Convocatoria sin id_expediente, se ignora: %s", cruda.get("objeto")
                )
                # paso a la siguiente
                continue

            # miro si es nueva, una modificación o ya vista sin cambios
            estado = dedupe.estado_convocatoria(conn, id_expediente, fecha_ultima)
            # si ya la había visto y no ha cambiado, la salto
            if estado == "vista":
                continue

            # intento estructurar la convocatoria con el LLM
            try:
                # convierto la convocatoria cruda en un objeto limpio
                convocatoria = _extraer(cruda)
            # si falla la extracción...
            except Exception:
                # apunto el error y NO la marco como procesada, para reintentar mañana
                logger.exception(
                    "Fallo al extraer la convocatoria %s — se reintentará mañana.",
                    id_expediente,
                )
                # paso a la siguiente
                continue

            # intento evaluar si la convocatoria es relevante
            try:
                # pido el veredicto de relevancia (con etiquetas) al LLM
                veredicto = _evaluar(convocatoria)
            # si falla la evaluación...
            except Exception:
                # apunto el error y NO la marco como procesada, para reintentar mañana
                logger.exception(
                    "Fallo al evaluar relevancia de %s — se reintentará mañana.",
                    id_expediente,
                )
                # paso a la siguiente
                continue

            # llegué hasta aquí sin fallos, así que la registro (nueva o modificada)
            dedupe.registrar(conn, id_expediente, url, fecha_ultima)

            # calculo el semáforo de urgencia con el plazo y el estado (para todas,
            # relevantes o no, porque el histórico también lo guarda)
            urgencia = calcular_urgencia(
                convocatoria.plazo_presentacion, cruda.get("estado_tramitacion")
            )

            # guardo el concurso en el histórico (sea relevante o no) para que la
            # plataforma pueda ofrecerlo con filtros y "solo en plazo"
            history.guardar_concurso(
                conn, convocatoria, veredicto, urgencia, veredicto.relevante
            )

            # si el veredicto dice que es relevante...
            if veredicto.relevante:
                # armo la alerta juntando todo, marcando si es una modificación
                alerta = Alerta(
                    convocatoria=convocatoria,
                    veredicto=veredicto,
                    urgencia=urgencia,
                    es_modificacion=(estado == "modificada"),
                )
                # la añado a la lista de alertas
                alertas.append(alerta)
                # dejo constancia de que es relevante
                logger.info(
                    "Relevante (%s, %s): %s",
                    estado,
                    urgencia.nivel,
                    id_expediente,
                )
            # si no es relevante...
            else:
                # dejo constancia de que no lo es y por qué
                logger.info("No relevante: %s — %s", id_expediente, veredicto.motivo)

    # publico siempre el resultado hacia la plataforma (aunque la lista esté vacía,
    # para que la plataforma sepa que hoy no hubo novedades)
    if publisher.publicar(alertas):
        # si se publicó bien, lo apunto
        logger.info("Publicadas %d alertas relevantes hacia la plataforma.", len(alertas))
    # si no se pudo publicar...
    else:
        # apunto el error (el detalle ya quedó en el log anterior)
        logger.error("No se pudo publicar hacia la plataforma (ver log anterior).")


# si ejecuto este fichero directamente, arranco el proceso
if __name__ == "__main__":
    run()
