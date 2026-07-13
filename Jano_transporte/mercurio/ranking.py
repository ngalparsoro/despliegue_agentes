"""Recomendación y redacción del informe de viaje.

Dos piezas, equivalentes al `relevance.py` de Vigil:

- `recomendar` es lógica pura (sin LLM): elige el mejor hotel y el transporte
  más conveniente y calcula el coste estimado. Se usa en modo real y en demo.
- `redactar_informe` redacta el resumen con el LLM (Groq) en modo real; si no
  hay clave o falla, cae en la versión heurística del modo demo.
"""

# importo las anotaciones modernas
from __future__ import annotations

# traigo logging para avisar de fallos del LLM sin romper el flujo
import logging

# traigo la configuración del LLM
from mercurio.config import GROQ_API_KEY, GROQ_MODEL
# traigo los moldes de datos
from mercurio.schemas import Hotel, OpcionTransporte, PropuestaViaje

# creo un registrador con el nombre de este módulo
logger = logging.getLogger(__name__)


# elijo el transporte más conveniente entre vuelos y trenes (el más barato)
def _mejor_transporte(propuesta: PropuestaViaje) -> OpcionTransporte | None:
    # junto todas las opciones de transporte disponibles
    todas = list(propuesta.vuelos) + list(propuesta.trenes)
    # si no hay ninguna, no puedo recomendar transporte
    if not todas:
        return None
    # devuelvo la de menor precio total
    return min(todas, key=lambda o: o.precio_total)


# uno una lista de textos en una frase natural: "a", "a y b", "a, b y c"
def _unir(partes: list[str]) -> str:
    # si hay una o ninguna, no hay nada que enlazar
    if len(partes) <= 1:
        return partes[0] if partes else ""
    # el resto: comas entre todas menos la última, que va con "y"
    return ", ".join(partes[:-1]) + " y " + partes[-1]


# convierto minutos en un texto "2h 15min" para las justificaciones
def _dur(minutos: int) -> str:
    # separo horas y minutos y los formateo
    h, m = divmod(minutos, 60)
    return f"{h}h {m:02d}min"


# saco la hora "HH:MM" de un datetime ISO (para describir horarios al ponente)
def _hora(dt_iso: str) -> str:
    # traigo datetime aquí para no cargarlo si no hace falta
    from datetime import datetime
    # intento parsear; si no puedo, devuelvo el texto tal cual
    try:
        return datetime.fromisoformat(dt_iso).strftime("%H:%M")
    except (ValueError, TypeError):
        return dt_iso


# explico por qué se recomienda este hotel frente a los demás (sin precios)
def _motivo_hotel(hotel: Hotel, hoteles: list[Hotel], preferencias: str | None) -> str:
    # si la búsqueda priorizó cercanía, ese es el motivo principal
    prefs = (preferencias or "").lower()
    if any(p in prefs for p in ("cerca", "céntric", "centric", "recinto", "andando", "a pie")):
        return f"es el más cercano al recinto ({hotel.distancia_recinto_km} km), como pediste"
    # miro si destaca por valoración o por cercanía respecto al resto
    mejor_valorado = hotel.valoracion >= max(h.valoracion for h in hoteles)
    mas_cercano = hotel.distancia_recinto_km <= min(h.distancia_recinto_km for h in hoteles)
    # combino los motivos que apliquen
    if mejor_valorado and mas_cercano:
        return f"es el mejor valorado ({hotel.valoracion}/10) y el más cercano al recinto ({hotel.distancia_recinto_km} km)"
    if mejor_valorado:
        return f"es el mejor valorado ({hotel.valoracion}/10), a {hotel.distancia_recinto_km} km del recinto"
    if mas_cercano:
        return f"es el más cercano al recinto ({hotel.distancia_recinto_km} km), con {hotel.valoracion}/10"
    # si no destaca en un extremo, lo presento como opción equilibrada (sin hablar de precio)
    return f"es una opción muy equilibrada ({hotel.valoracion}/10, a {hotel.distancia_recinto_km} km del recinto)"


# motivo del transporte para el ORGANIZADOR (puede hablar de coste)
def _motivo_transporte(op: OpcionTransporte, todas: list[OpcionTransporte]) -> str:
    # nombro el modo en español
    modo = "vuelo" if op.modo == "vuelo" else "tren"
    # parto de que es el más económico (así lo eligió recomendar)
    motivos = [f"es el {modo} más económico"]
    # si es directo, lo destaco
    if op.ida.escalas == 0 and op.vuelta.escalas == 0:
        motivos.append("sin escalas")
    # si además es el más rápido de todas las opciones, lo destaco
    if op.ida.duracion_min <= min(o.ida.duracion_min for o in todas):
        motivos.append(f"y el más rápido ({_dur(op.ida.duracion_min)} por trayecto)")
    # uno los motivos en una frase
    return ", ".join(motivos)


# motivo del transporte para el PONENTE: comodidad/conveniencia, SIN hablar de precio
def _motivo_transporte_ponente(op: OpcionTransporte, todas: list[OpcionTransporte]) -> str:
    # nombro el modo en español
    modo = "vuelo" if op.modo == "vuelo" else "tren"
    # compruebo si es directo (ida y vuelta) y si es el más rápido
    directo = op.ida.escalas == 0 and op.vuelta.escalas == 0
    mas_rapido = op.ida.duracion_min <= min(o.ida.duracion_min for o in todas)
    # caso ideal: directo y el más rápido
    if directo and mas_rapido:
        return f"es un {modo} directo y el más rápido ({_dur(op.ida.duracion_min)} por trayecto)"
    # solo directo
    if directo:
        return f"es un {modo} directo, sin escalas ({_dur(op.ida.duracion_min)} por trayecto)"
    # solo el más rápido
    if mas_rapido:
        return f"es el {modo} más rápido ({_dur(op.ida.duracion_min)} por trayecto)"
    # si no destaca en comodidad, describo el horario (dato útil y neutro, sin precio)
    return f"sale a las {_hora(op.ida.salida)} y regresa a las {_hora(op.vuelta.salida)}"


# relleno la recomendación y el coste estimado de una propuesta (sin LLM)
def recomendar(propuesta: PropuestaViaje) -> PropuestaViaje:
    """Elige hotel y transporte, calcula el coste y escribe la recomendación."""
    # el mejor hotel es el primero (las búsquedas ya vienen ordenadas por calidad)
    hotel: Hotel | None = propuesta.hoteles[0] if propuesta.hoteles else None
    # el mejor transporte es el más barato entre vuelos y trenes
    transporte = _mejor_transporte(propuesta)
    # el mejor taxi y el mejor coche son los más económicos (ya vienen ordenados)
    taxi = propuesta.taxis[0] if propuesta.taxis else None
    coche = propuesta.coches[0] if propuesta.coches else None

    # calculo el coste estimado sumando todos los servicios recomendados
    coste = 0.0
    if hotel:
        coste += hotel.precio_total
    if transporte:
        coste += transporte.precio_total
    if taxi:
        coste += taxi.precio_estimado
    if coche:
        coste += coche.precio_total
    # guardo el coste solo si hay al menos un servicio
    propuesta.coste_estimado = round(coste, 2) if (hotel or transporte or taxi or coche) else None

    # redacto la recomendación en dos versiones: con importes (organizador) y
    # sin importes (para el PDF del ponente, que no debe ver precios)
    partes: list[str] = []
    partes_sin_precio: list[str] = []
    if hotel:
        partes.append(
            f"alojarse en {hotel.nombre} ({hotel.estrellas}★, "
            f"{hotel.precio_total:.0f} {hotel.moneda} las {propuesta.noches} noches)"
        )
        partes_sin_precio.append(f"alojarse en {hotel.nombre} ({hotel.estrellas}★)")
    if transporte:
        # nombro el modo en español para la frase
        modo = "avión" if transporte.modo == "vuelo" else "tren"
        partes.append(
            f"viajar en {modo} con {transporte.proveedor} "
            f"({transporte.precio_total:.0f} {transporte.moneda} ida y vuelta)"
        )
        partes_sin_precio.append(f"viajar en {modo} con {transporte.proveedor}")
    if taxi:
        # el taxi recomendado (el más económico)
        partes.append(f"taxi con {taxi.proveedor} ({taxi.precio_estimado:.0f} {taxi.moneda})")
        partes_sin_precio.append(f"taxi con {taxi.proveedor}")
    if coche:
        # el coche de alquiler recomendado (el más económico)
        partes.append(
            f"coche de alquiler con {coche.compania} "
            f"({coche.precio_total:.0f} {coche.moneda} los {coche.dias} días)"
        )
        partes_sin_precio.append(f"coche de alquiler con {coche.compania}")
    # uno las partes en una frase natural; si no hay nada, dejo un aviso
    if partes:
        propuesta.recomendacion = "Se recomienda " + _unir(partes) + "."
        propuesta.recomendacion_sin_precio = "Se recomienda " + _unir(partes_sin_precio) + "."
    else:
        propuesta.recomendacion = "No se han encontrado opciones para recomendar."
        propuesta.recomendacion_sin_precio = "No se han encontrado opciones para recomendar."

    # explico el PORQUÉ en dos versiones: para el organizador (con coste) y para
    # el ponente (por comodidad, sin hablar nunca de precio)
    motivos_org: list[str] = []
    motivos_pon: list[str] = []
    if hotel:
        # el motivo del hotel es el mismo (no menciona precio en ningún caso)
        motivo_h = _motivo_hotel(hotel, propuesta.hoteles, propuesta.preferencias)
        motivos_org.append(f"El alojamiento {hotel.nombre} {motivo_h}")
        motivos_pon.append(f"El alojamiento {hotel.nombre} {motivo_h}")
    if transporte:
        # junto todas las opciones de transporte para comparar el elegido
        todas = list(propuesta.vuelos) + list(propuesta.trenes)
        modo = "avión" if transporte.modo == "vuelo" else "tren"
        # al organizador le hablo de coste; al ponente, de comodidad
        motivos_org.append(f"El {modo} con {transporte.proveedor} {_motivo_transporte(transporte, todas)}")
        motivos_pon.append(f"El {modo} con {transporte.proveedor} {_motivo_transporte_ponente(transporte, todas)}")
    # monto las dos justificaciones (o vacías si no hay nada que justificar)
    propuesta.justificacion = ". ".join(motivos_org) + "." if motivos_org else ""
    propuesta.justificacion_ponente = ". ".join(motivos_pon) + "." if motivos_pon else ""

    # devuelvo la propuesta ya completada
    return propuesta


# redacto el resumen del viaje con el LLM (Groq); si no hay clave, uso el demo
def redactar_informe(propuesta: PropuestaViaje) -> str:
    """Redacta un resumen del viaje con Groq; cae en la heurística si no puede."""
    # si no hay clave de Groq, no intento el LLM: uso la versión demo
    if not GROQ_API_KEY:
        # importo aquí para no crear dependencia circular al cargar el módulo
        from mercurio import demo
        return demo.redactar_informe(propuesta)

    # intento redactar con el LLM y, si algo falla, caigo en el demo
    try:
        # importo el cliente de Groq solo cuando de verdad lo voy a usar
        from groq import Groq
        # creo el cliente con la clave configurada
        cliente = Groq(api_key=GROQ_API_KEY)
        # armo el mensaje con los datos clave del viaje. IMPORTANTE: este resumen
        # acaba en el PDF que se envía al ponente, así que NO debe incluir precios
        # (por eso paso la recomendación sin importes y lo pido explícitamente).
        prompt = (
            "Redacta en español un resumen breve (2-3 frases) para el ponente "
            "sobre su viaje. Sé concreto y práctico. NO menciones precios, "
            "importes ni costes en ningún caso.\n\n"
            f"Ponente: {propuesta.ponente.nombre}\n"
            f"Evento: {propuesta.evento.nombre}\n"
            f"Ruta: {propuesta.ponente.ciudad_origen or 'origen sin definir'} → {propuesta.evento.ciudad}\n"
            f"Fechas: {propuesta.fecha_llegada} a {propuesta.fecha_salida} "
            f"({propuesta.noches} noches)\n"
            f"Personas: {propuesta.personas}\n"
            f"Preferencias: {propuesta.preferencias or 'ninguna'}\n"
            f"Hoteles propuestos: {len(propuesta.hoteles)}\n"
            f"Vuelos: {len(propuesta.vuelos)} · Trenes: {len(propuesta.trenes)}\n"
            f"Recomendación (sin precios): {propuesta.recomendacion_sin_precio}"
        )
        # pido al modelo la redacción
        respuesta = cliente.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        # devuelvo el texto redactado, sin espacios sobrantes
        return respuesta.choices[0].message.content.strip()
    # si el LLM falla por lo que sea...
    except Exception:
        # dejo constancia y caigo en la versión heurística
        logger.exception("Fallo al redactar el informe con Groq — uso el resumen demo.")
        from mercurio import demo
        return demo.redactar_informe(propuesta)
