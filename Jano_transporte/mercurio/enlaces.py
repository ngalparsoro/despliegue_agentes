"""Construcción de los enlaces de compra (la "opción de ir al link de compra").

Genera URLs de búsqueda ya rellenadas hacia proveedores reales (Booking para
hoteles, Google Flights para vuelos, Renfe para trenes) con la ciudad, las
fechas y el número de personas. Así, aunque los *resultados* de la demo sean
simulados, el botón "Reservar/Comprar" lleva a una búsqueda real y coherente.
"""

# importo las anotaciones modernas para escribir "str | None"
from __future__ import annotations

# traigo quote_plus para poder meter ciudades con espacios/tildes en una URL
from urllib.parse import quote_plus


# armo el enlace de reserva de un hotel en Booking para esa ciudad y fechas
def enlace_hotel(ciudad: str, llegada_iso: str, salida_iso: str, personas: int = 1) -> str:
    # monto la búsqueda de Booking con destino, fechas y número de adultos
    return (
        "https://www.booking.com/searchresults.es.html"
        f"?ss={quote_plus(ciudad)}"
        f"&checkin={llegada_iso}"
        f"&checkout={salida_iso}"
        f"&group_adults={max(1, personas)}"
    )


# armo el enlace de compra de un vuelo de ida y vuelta en Google Flights
def enlace_vuelo(origen: str, destino: str, ida_iso: str, vuelta_iso: str) -> str:
    # Google Flights entiende una búsqueda en lenguaje natural en la query
    consulta = f"Vuelos {origen} a {destino} {ida_iso[:10]} vuelta {vuelta_iso[:10]}"
    # devuelvo la URL de búsqueda con esa consulta codificada
    return "https://www.google.com/travel/flights?q=" + quote_plus(consulta)


# armo el enlace de compra de un tren en Renfe para esa ruta y fechas
def enlace_tren(origen: str, destino: str, ida_iso: str, vuelta_iso: str) -> str:
    # Renfe no acepta bien parámetros directos, así que llevo a su buscador
    # con la ruta indicada en la query para dejar constancia de la búsqueda
    consulta = f"{origen} {destino} {ida_iso[:10]}"
    return "https://www.renfe.com/es/es?busqueda=" + quote_plus(consulta)


# armo el enlace para contratar un taxi/traslado en la ciudad del evento
def enlace_taxi(ciudad: str) -> str:
    # llevo a una búsqueda de servicios de taxi en la ciudad de destino
    return "https://www.google.com/search?q=" + quote_plus(f"taxi traslado {ciudad}")


# armo el enlace para alquilar un coche en el destino para esas fechas
def enlace_coche(ciudad: str, llegada_iso: str, salida_iso: str) -> str:
    # llevo a una búsqueda de alquiler de coche en el destino con las fechas
    consulta = f"alquiler de coche {ciudad} {llegada_iso[:10]} a {salida_iso[:10]}"
    return "https://www.google.com/search?q=" + quote_plus(consulta)
