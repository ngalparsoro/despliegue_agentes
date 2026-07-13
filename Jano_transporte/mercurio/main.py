"""CLI de demostración de Mercurio.

Como la búsqueda ya es bajo demanda (formulario → `POST /buscar`), no hay un
proceso batch. Este módulo solo sirve para probar el pipeline por línea de
comandos: ejecuta las solicitudes de ejemplo y genera sus dos PDFs en la
carpeta de salida. Para usar el agente de verdad, levanta la API.

    python -m mercurio.main        # genera los PDFs de los ejemplos (demo)
"""

# traigo logging para ir informando de lo que hace
import logging
# traigo os para forzar el modo demo y componer rutas
import os

# configuro el registro para que muestre fecha, nivel y mensaje
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
# creo mi registrador con un nombre claro
logger = logging.getLogger("mercurio.main")


# ejecuto las solicitudes de ejemplo y genero sus PDFs
def run() -> None:
    # esta demostración solo tiene sentido en modo demo
    os.environ.setdefault("MERCURIO_DEMO", "1")
    # importo lo necesario después de fijar el modo demo
    from mercurio import pdf_report, servicio
    from mercurio.config import OUTPUT_DIR
    from mercurio.examples.solicitudes_ejemplo import SOLICITUDES
    from mercurio.schemas import SolicitudBusqueda

    # carpeta donde dejo los PDFs
    carpeta_pdf = os.path.join(OUTPUT_DIR, "pdf")

    # recorro cada solicitud de ejemplo
    for datos in SOLICITUDES:
        # valido la solicitud con el molde
        solicitud = SolicitudBusqueda(**datos)
        # ejecuto la búsqueda
        propuesta = servicio.buscar(solicitud)
        # genero los dos PDFs
        rutas = pdf_report.generar_ambos(propuesta, carpeta_pdf)
        # dejo constancia del resultado
        logger.info(
            "%s (%s → %s): %d hoteles, %d vuelos, %d trenes · PDFs: %s",
            solicitud.nombre_ponente,
            solicitud.ciudad_origen or "—",
            solicitud.ciudad_evento,
            len(propuesta.hoteles), len(propuesta.vuelos), len(propuesta.trenes),
            "ok" if all(rutas.values()) else "parcial",
        )

    # aviso de dónde han quedado los PDFs
    logger.info("PDFs de ejemplo generados en %s", carpeta_pdf)


# si ejecuto este fichero directamente, arranco la demostración
if __name__ == "__main__":
    run()
