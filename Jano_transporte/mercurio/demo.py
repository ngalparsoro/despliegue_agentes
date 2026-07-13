"""Modo demo de Mercurio: genera resultados de viaje SIN APIs ni claves.

Cuando `MERCURIO_DEMO` está puesto, el servicio de búsqueda usa estas
funciones en lugar de las de `sources.py`. Los resultados son **deterministas**:
para una misma búsqueda (misma semilla y fechas) siempre salen los mismos
hoteles, vuelos y trenes. Los precios y horarios son verosímiles pero
inventados; los enlaces de "Reservar/Comprar" apuntan a búsquedas reales.

Las `preferencias` en texto libre afinan un poco los resultados (p. ej.
"sin escalas" prioriza vuelos directos; "cerca del recinto" ordena por
cercanía), para que se note que el campo se tiene en cuenta.
"""

# importo las anotaciones modernas
from __future__ import annotations

# traigo hashlib para derivar una semilla estable de la búsqueda
import hashlib
# traigo math para calcular el número de habitaciones
import math
# traigo random para generar los resultados de forma controlada
import random

# traigo cuántas sugerencias dar de cada tipo
from mercurio.config import SUGERENCIAS_POR_TIPO
# traigo los constructores de enlaces de compra reales
from mercurio.enlaces import (
    enlace_coche, enlace_hotel, enlace_taxi, enlace_tren, enlace_vuelo,
)
# traigo las utilidades de fecha/hora
from mercurio.fechas import combinar, sumar_minutos
# traigo los moldes de datos que devuelvo
from mercurio.schemas import (
    Hotel, OpcionCoche, OpcionTaxi, OpcionTransporte, Trayecto,
)

# ciudades españolas con buena conexión de alta velocidad (para ofrecer tren).
# si el origen o el destino no está aquí, asumo que no hay ruta de tren razonable.
CIUDADES_TREN = {
    "madrid", "barcelona", "sevilla", "san sebastián", "san sebastian",
    "bilbao", "vitoria-gasteiz", "vitoria", "valencia", "zaragoza",
    "málaga", "malaga", "córdoba", "cordoba", "valladolid", "alicante",
    "girona", "tarragona", "lleida", "burgos", "león", "leon",
}

# nombres de hotel de muestra (se eligen unos cuantos distintos por ciudad)
_HOTELES = [
    "Gran Hotel Central", "Hotel Boutique Ría", "Hotel Plaza Mayor",
    "URH Palacio", "Sercotel Ensanche", "NH Collection", "Barceló Costa",
    "Silken Indautxu", "Hotel Ercilla", "Meliá Centro", "Ilunion Ría",
    "Occidental Puerta", "Vincci Consulado", "Eurostars Gran",
]

# aerolíneas para vuelos nacionales
_AEROLINEAS_NAC = ["Iberia", "Vueling", "Air Europa", "Ryanair", "Iberia Express"]
# aerolíneas para vuelos internacionales
_AEROLINEAS_INT = ["Iberia", "British Airways", "Vueling", "easyJet", "Air Europa"]
# operadores ferroviarios de alta velocidad en España
_OPERADORES_TREN = ["Renfe AVE", "Renfe Avlo", "Iryo", "Ouigo"]

# servicios de taxi/traslado de muestra
_TAXIS = ["Cabify", "Uber", "Bolt", "Radio Taxi"]
# tipos de servicio de taxi
_TAXI_SERVICIOS = ["Traslado aeropuerto ↔ hotel", "Traslado estación ↔ hotel", "Servicio a demanda (por carrera)"]
# compañías de alquiler de coche de muestra
_COCHES = ["Europcar", "Hertz", "Sixt", "Avis", "Enterprise"]


# derivo un generador de azar estable a partir de unas piezas (semilla, fechas...)
def _rng(*partes: object) -> random.Random:
    # concateno las piezas y saco un hash reproducible
    semilla = hashlib.sha256("|".join(str(p) for p in partes).encode()).hexdigest()
    # uso los primeros dígitos del hash como semilla del generador
    return random.Random(int(semilla[:16], 16))


# normalizo el nombre de una ciudad para comparar (minúsculas, sin espacios extra)
def _clave_ciudad(ciudad: str | None) -> str:
    return (ciudad or "").strip().lower()


# redondeo un precio a múltiplos de 5 para que se vea más creíble
def _precio_bonito(valor: float) -> float:
    return float(round(valor / 5.0) * 5)


# miro si las preferencias piden algo concreto (devuelvo el texto en minúsculas)
def _prefs(preferencias: str | None) -> str:
    return (preferencias or "").lower()


# --- Hoteles ---------------------------------------------------------------

# genero las sugerencias de hotel para la ciudad del evento y las fechas dadas
def buscar_hoteles(
    ciudad_destino: str, llegada_iso: str, salida_iso: str, noches: int,
    personas: int, preferencias: str | None, semilla: str,
) -> list[Hotel]:
    # siembro el azar con la semilla de la búsqueda y las fechas
    rng = _rng(semilla, "hotel", llegada_iso, salida_iso)
    # fijo un precio base para la ciudad (unas ciudades son más caras que otras)
    base = 70 + _rng(ciudad_destino, "base").randint(0, 90)
    # calculo cuántas habitaciones hacen falta (2 personas por habitación)
    habitaciones = max(1, math.ceil(personas / 2))
    # elijo nombres de hotel distintos del catálogo
    nombres = rng.sample(_HOTELES, k=min(SUGERENCIAS_POR_TIPO + 2, len(_HOTELES)))

    # preparo la lista de hoteles candidatos
    candidatos: list[Hotel] = []
    # genero un candidato por cada nombre elegido
    for nombre in nombres:
        # decido categoría en estrellas (3, 4 o 5)
        estrellas = rng.choice([3, 4, 4, 5])
        # el precio por noche sube con las estrellas y con un poco de azar
        precio_noche = _precio_bonito(base + (estrellas - 3) * 45 + rng.randint(-15, 40))
        # la valoración media, mejor cuantas más estrellas
        valoracion = round(min(9.7, 7.4 + (estrellas - 3) * 0.5 + rng.uniform(0, 0.8)), 1)
        # la distancia al recinto del evento en km
        distancia = round(rng.uniform(0.2, 4.5), 1)
        # armo el hotel con su precio total (por habitaciones) y su enlace
        candidatos.append(
            Hotel(
                nombre=f"{nombre} {ciudad_destino}",
                estrellas=estrellas,
                valoracion=valoracion,
                distancia_recinto_km=distancia,
                precio_noche=precio_noche,
                noches=noches,
                habitaciones=habitaciones,
                precio_total=_precio_bonito(precio_noche * noches * habitaciones),
                enlace_reserva=enlace_hotel(ciudad_destino, llegada_iso, salida_iso, personas),
            )
        )

    # si piden cercanía, ordeno por distancia al recinto (más cerca primero)
    prefs = _prefs(preferencias)
    if any(p in prefs for p in ("cerca", "céntric", "centric", "recinto", "andando", "a pie")):
        candidatos.sort(key=lambda h: h.distancia_recinto_km)
    else:
        # si no, puntúo premiando valoración y penalizando precio y distancia
        candidatos.sort(
            key=lambda h: h.valoracion * 12 - h.precio_noche * 0.08 - h.distancia_recinto_km * 2,
            reverse=True,
        )
    # devuelvo solo las primeras sugerencias
    return candidatos[:SUGERENCIAS_POR_TIPO]


# --- Transporte (vuelos y trenes) -----------------------------------------

# construyo un tramo (ida o vuelta) con salida, llegada y duración
def _trayecto(
    origen: str, destino: str, fecha_iso: str, hora: int, dur_min: int, escalas: int
) -> Trayecto:
    # calculo el datetime de salida combinando la fecha con la hora
    salida = combinar(fecha_iso, hora, 0)
    # la llegada es la salida más la duración del tramo
    llegada = sumar_minutos(salida, dur_min)
    # devuelvo el tramo montado
    return Trayecto(
        origen=origen, destino=destino, salida=salida, llegada=llegada,
        duracion_min=dur_min, escalas=escalas,
    )


# aplico la preferencia "sin escalas": si la piden y hay directos, me quedo con ellos
def _preferir_directos(opciones: list[OpcionTransporte], preferencias: str | None) -> list[OpcionTransporte]:
    # miro si el texto pide vuelos/trenes directos
    prefs = _prefs(preferencias)
    if any(p in prefs for p in ("sin escala", "directo", "directa", "sin transbordo")):
        # me quedo con los directos si hay alguno
        directos = [o for o in opciones if o.ida.escalas == 0 and o.vuelta.escalas == 0]
        if directos:
            return directos
    # si no aplica, devuelvo las opciones tal cual
    return opciones


# genero las sugerencias de vuelo (ida y vuelta) entre origen y ciudad del evento
def buscar_vuelos(
    origen: str, destino: str, llegada_iso: str, salida_iso: str,
    personas: int, preferencias: str | None, semilla: str,
) -> list[OpcionTransporte]:
    # sin ciudad de origen no puedo calcular vuelos: devuelvo lista vacía
    if not origen:
        return []
    # siembro el azar de forma reproducible
    rng = _rng(semilla, "vuelo", llegada_iso, salida_iso)
    # detecto si el viaje es internacional (origen fuera de las ciudades españolas)
    internacional = _clave_ciudad(origen) not in CIUDADES_TREN
    # elijo el catálogo de aerolíneas según sea nacional o internacional
    aerolineas = rng.sample(
        _AEROLINEAS_INT if internacional else _AEROLINEAS_NAC,
        k=min(SUGERENCIAS_POR_TIPO, len(_AEROLINEAS_NAC)),
    )

    # preparo la lista de opciones
    opciones: list[OpcionTransporte] = []
    # genero una opción por aerolínea
    for aerolinea in aerolineas:
        # decido si el vuelo es directo o con una escala
        escalas = rng.choice([0, 0, 1])
        # la duración base depende de si es internacional, más lo que añada la escala
        base = rng.randint(120, 200) if internacional else rng.randint(65, 130)
        dur = base + (rng.randint(70, 140) if escalas else 0)
        # elijo horas de salida verosímiles para ida y vuelta
        hora_ida = rng.randint(7, 18)
        hora_vuelta = rng.randint(9, 20)
        # el precio por persona, más caro si es internacional; lo multiplico por personas
        por_persona = rng.randint(90, 320) if internacional else rng.randint(55, 240)
        precio = _precio_bonito(por_persona * personas)
        # monto la opción con sus dos tramos y su enlace de compra
        opciones.append(
            OpcionTransporte(
                modo="vuelo",
                proveedor=aerolinea,
                ida=_trayecto(origen, destino, llegada_iso, hora_ida, dur, escalas),
                vuelta=_trayecto(destino, origen, salida_iso, hora_vuelta, dur, escalas),
                precio_total=precio,
                enlace_reserva=enlace_vuelo(origen, destino, llegada_iso, salida_iso),
            )
        )

    # aplico la preferencia de directos si la piden
    opciones = _preferir_directos(opciones, preferencias)
    # ordeno de más barato a más caro
    opciones.sort(key=lambda o: o.precio_total)
    return opciones


# genero las sugerencias de tren (ida y vuelta), si la ruta tiene sentido
def buscar_trenes(
    origen: str, destino: str, llegada_iso: str, salida_iso: str,
    personas: int, preferencias: str | None, semilla: str,
) -> list[OpcionTransporte]:
    # si falta el origen, o el origen/destino no tienen alta velocidad, no ofrezco tren
    if (
        not origen
        or _clave_ciudad(origen) not in CIUDADES_TREN
        or _clave_ciudad(destino) not in CIUDADES_TREN
    ):
        return []

    # siembro el azar de forma reproducible
    rng = _rng(semilla, "tren", llegada_iso, salida_iso)
    # elijo operadores distintos del catálogo
    operadores = rng.sample(_OPERADORES_TREN, k=min(SUGERENCIAS_POR_TIPO, len(_OPERADORES_TREN)))

    # preparo la lista de opciones
    opciones: list[OpcionTransporte] = []
    # genero una opción por operador
    for operador in operadores:
        # el tren suele tardar más que el avión puerta a puerta
        dur = rng.randint(150, 360)
        # decido transbordos (0 o 1)
        escalas = rng.choice([0, 0, 1])
        # horas de salida de ida y vuelta
        hora_ida = rng.randint(6, 18)
        hora_vuelta = rng.randint(9, 20)
        # precio por persona (normalmente más barato que el avión), por personas
        por_persona = rng.randint(45, 170)
        precio = _precio_bonito(por_persona * personas)
        # monto la opción con sus dos tramos y su enlace de compra
        opciones.append(
            OpcionTransporte(
                modo="tren",
                proveedor=operador,
                ida=_trayecto(origen, destino, llegada_iso, hora_ida, dur, escalas),
                vuelta=_trayecto(destino, origen, salida_iso, hora_vuelta, dur, escalas),
                precio_total=precio,
                enlace_reserva=enlace_tren(origen, destino, llegada_iso, salida_iso),
            )
        )

    # aplico la preferencia de directos si la piden
    opciones = _preferir_directos(opciones, preferencias)
    # ordeno de más barato a más caro
    opciones.sort(key=lambda o: o.precio_total)
    return opciones


# --- Taxi -----------------------------------------------------------------

# genero las sugerencias de taxi/traslado en la ciudad del evento
def buscar_taxis(
    ciudad_destino: str, personas: int, preferencias: str | None, semilla: str,
) -> list[OpcionTaxi]:
    # siembro el azar de forma reproducible
    rng = _rng(semilla, "taxi", ciudad_destino)
    # elijo proveedores distintos del catálogo
    proveedores = rng.sample(_TAXIS, k=min(SUGERENCIAS_POR_TIPO, len(_TAXIS)))
    # si viajan más de 4, hará falta un vehículo grande (encarece)
    recargo = 1.4 if personas > 4 else 1.0

    # preparo la lista de opciones
    opciones: list[OpcionTaxi] = []
    # genero una opción por proveedor
    for i, proveedor in enumerate(proveedores):
        # elijo un tipo de servicio
        servicio = _TAXI_SERVICIOS[i % len(_TAXI_SERVICIOS)]
        # precio estimado del traslado, con recargo por tamaño de grupo
        precio = _precio_bonito(rng.randint(22, 55) * recargo)
        # nombro el proveedor añadiendo la ciudad al radio taxi
        nombre = f"{proveedor} {ciudad_destino}" if proveedor == "Radio Taxi" else proveedor
        # monto la opción con su enlace
        opciones.append(
            OpcionTaxi(
                proveedor=nombre,
                descripcion=servicio,
                precio_estimado=precio,
                enlace_reserva=enlace_taxi(ciudad_destino),
            )
        )
    # ordeno de más barato a más caro
    opciones.sort(key=lambda o: o.precio_estimado)
    return opciones


# --- Coche de alquiler -----------------------------------------------------

# genero las sugerencias de coche de alquiler en el destino
def buscar_coches(
    ciudad_destino: str, llegada_iso: str, salida_iso: str, dias: int,
    personas: int, preferencias: str | None, semilla: str,
) -> list[OpcionCoche]:
    # siembro el azar de forma reproducible
    rng = _rng(semilla, "coche", llegada_iso, salida_iso)
    # elijo compañías distintas del catálogo
    companias = rng.sample(_COCHES, k=min(SUGERENCIAS_POR_TIPO, len(_COCHES)))
    # la categoría depende del tamaño del grupo
    categoria = "Monovolumen" if personas > 4 else ("Familiar" if personas > 2 else "Compacto")

    # preparo la lista de opciones
    opciones: list[OpcionCoche] = []
    # genero una opción por compañía
    for compania in companias:
        # precio por día según la categoría, con un poco de azar
        base = {"Compacto": 32, "Familiar": 45, "Monovolumen": 62}[categoria]
        precio_dia = _precio_bonito(base + rng.randint(-6, 18))
        # alterno la oficina de recogida entre aeropuerto y centro
        oficina = rng.choice([f"Aeropuerto de {ciudad_destino}", f"Centro de {ciudad_destino}"])
        # monto la opción con su precio total y su enlace
        opciones.append(
            OpcionCoche(
                compania=compania,
                categoria=categoria,
                oficina=oficina,
                precio_dia=precio_dia,
                dias=dias,
                precio_total=_precio_bonito(precio_dia * dias),
                enlace_reserva=enlace_coche(ciudad_destino, llegada_iso, salida_iso),
            )
        )
    # ordeno de más barato a más caro
    opciones.sort(key=lambda o: o.precio_total)
    return opciones


# --- Informe (sin LLM) -----------------------------------------------------

# redacto un resumen del viaje sin llamar al LLM (heurística sencilla)
def redactar_informe(propuesta) -> str:
    # cuento cuántas opciones de cada tipo hay
    n_hoteles = len(propuesta.hoteles)
    n_vuelos = len(propuesta.vuelos)
    n_trenes = len(propuesta.trenes)
    # armo la lista de lo que se ha buscado
    partes = []
    if propuesta.necesita_hotel:
        partes.append(f"{n_hoteles} hoteles")
    if propuesta.necesita_viaje:
        medios = []
        if n_vuelos:
            medios.append(f"{n_vuelos} de avión")
        if n_trenes:
            medios.append(f"{n_trenes} de tren")
        partes.append(" y ".join(medios) if medios else "sin opciones de transporte")
    if propuesta.necesita_taxi:
        partes.append(f"{len(propuesta.taxis)} de taxi")
    if propuesta.necesita_coche:
        partes.append(f"{len(propuesta.coches)} de coche de alquiler")
    # uno lo buscado en una frase
    texto = " y ".join(partes) if partes else "nada"
    # saco origen y nombre de evento con textos por defecto
    origen = propuesta.ponente.ciudad_origen or "origen sin definir"
    evento = propuesta.evento.nombre or "el evento"
    # devuelvo un párrafo resumen del viaje del ponente
    return (
        f"Viaje de {propuesta.ponente.nombre} desde {origen} "
        f"a {propuesta.evento.ciudad} para «{evento}». "
        f"Estancia de {propuesta.noches} noche{'s' if propuesta.noches != 1 else ''} "
        f"({propuesta.fecha_llegada} → {propuesta.fecha_salida}) para "
        f"{propuesta.personas} persona{'s' if propuesta.personas != 1 else ''}. "
        f"Se proponen {texto}. [demo]"
    )
