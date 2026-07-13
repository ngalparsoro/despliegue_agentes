"""Servicio de búsqueda: de una `SolicitudBusqueda` a una `PropuestaViaje`.

Es el núcleo del agente ahora que la búsqueda se dispara con un formulario (ya
no lee de ninguna base de datos). Respeta las casillas del formulario: busca
hotel solo si se pidió, y viaje (vuelos + trenes) solo si se pidió. Elige las
funciones de búsqueda reales o las de demo según `MERCURIO_DEMO`.
"""

# importo las anotaciones modernas
from __future__ import annotations

# traigo hashlib para derivar una semilla estable de la solicitud (demo reproducible)
import hashlib
# traigo os para consultar el flag de modo demo
import os
# traigo uuid para dar un identificador único a cada búsqueda
import uuid
# traigo datetime para el sello de tiempo de la propuesta
from datetime import datetime

# traigo el cálculo de la ventana de viaje
from mercurio.fechas import calcular_ventana
# traigo la recomendación (lógica pura) y la redacción del informe
from mercurio import ranking
# traigo los moldes de datos
from mercurio.schemas import Evento, Ponente, PropuestaViaje, SolicitudBusqueda


# derivo una semilla estable de la solicitud (para que la demo sea reproducible)
def _semilla(solicitud: SolicitudBusqueda) -> str:
    # junto los campos que definen la búsqueda
    crudo = "|".join([
        solicitud.nombre_ponente,
        solicitud.ciudad_origen or "",
        solicitud.ciudad_evento,
        solicitud.fecha_inicio,
        solicitud.fecha_fin,
        str(solicitud.personas),
    ])
    # devuelvo un hash corto y estable
    return hashlib.sha256(crudo.encode()).hexdigest()[:16]


# ejecuto una búsqueda a partir de la solicitud del formulario
def buscar(solicitud: SolicitudBusqueda) -> PropuestaViaje:
    """Devuelve la propuesta de viaje para una solicitud (hotel y/o viaje)."""
    # elijo las funciones de búsqueda: demo o reales
    if os.environ.get("MERCURIO_DEMO"):
        from mercurio import demo as fuente
        # en demo, el resumen lo redacta la heurística de demo.py
        _informe = fuente.redactar_informe
    else:
        from mercurio import sources as fuente
        # en real, el resumen lo redacta el LLM (con respaldo en demo)
        _informe = ranking.redactar_informe

    # calculo la ventana de viaje a partir de las fechas del evento
    llegada, salida, noches = calcular_ventana(solicitud.fecha_inicio, solicitud.fecha_fin)
    # derivo la semilla de la solicitud
    semilla = _semilla(solicitud)

    # busco hoteles solo si se ha pedido hotel
    hoteles = []
    if solicitud.necesita_hotel:
        hoteles = fuente.buscar_hoteles(
            solicitud.ciudad_evento, llegada, salida, noches,
            solicitud.personas, solicitud.preferencias, semilla,
        )

    # busco vuelos y trenes solo si se ha pedido viaje
    vuelos = []
    trenes = []
    if solicitud.necesita_viaje:
        vuelos = fuente.buscar_vuelos(
            solicitud.ciudad_origen or "", solicitud.ciudad_evento, llegada, salida,
            solicitud.personas, solicitud.preferencias, semilla,
        )
        trenes = fuente.buscar_trenes(
            solicitud.ciudad_origen or "", solicitud.ciudad_evento, llegada, salida,
            solicitud.personas, solicitud.preferencias, semilla,
        )

    # busco taxi solo si se ha pedido (es un servicio en el destino)
    taxis = []
    if solicitud.necesita_taxi:
        taxis = fuente.buscar_taxis(
            solicitud.ciudad_evento, solicitud.personas, solicitud.preferencias, semilla,
        )

    # busco coche de alquiler solo si se ha pedido (en el destino, por días)
    coches = []
    if solicitud.necesita_coche:
        coches = fuente.buscar_coches(
            solicitud.ciudad_evento, llegada, salida, noches,
            solicitud.personas, solicitud.preferencias, semilla,
        )

    # armo la propuesta con todo lo encontrado
    propuesta = PropuestaViaje(
        id=uuid.uuid4().hex,
        ponente=Ponente(
            nombre=solicitud.nombre_ponente,
            email=solicitud.email_ponente,
            ciudad_origen=solicitud.ciudad_origen,
        ),
        evento=Evento(
            nombre=solicitud.nombre_evento,
            ciudad=solicitud.ciudad_evento,
            fecha_inicio=solicitud.fecha_inicio,
            fecha_fin=solicitud.fecha_fin,
        ),
        generado_en=datetime.now().isoformat(),
        fecha_llegada=llegada,
        fecha_salida=salida,
        noches=noches,
        personas=solicitud.personas,
        preferencias=solicitud.preferencias,
        necesita_hotel=solicitud.necesita_hotel,
        necesita_viaje=solicitud.necesita_viaje,
        necesita_taxi=solicitud.necesita_taxi,
        necesita_coche=solicitud.necesita_coche,
        hoteles=hoteles,
        vuelos=vuelos,
        trenes=trenes,
        taxis=taxis,
        coches=coches,
    )

    # calculo la recomendación (con y sin precios) y el coste estimado
    ranking.recomendar(propuesta)
    # redacto el resumen (heurística en demo, LLM en real)
    propuesta.resumen = _informe(propuesta)
    # devuelvo la propuesta completa
    return propuesta
