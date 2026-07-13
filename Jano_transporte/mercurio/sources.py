"""Fuentes reales de búsqueda de hoteles, vuelos y trenes (a cablear).

Este módulo es el equivalente al `sources.py` de Vigil: aquí se integrarían los
proveedores reales (Amadeus para vuelos, Booking/Hotels para alojamiento,
Renfe/Trainline para trenes). De momento solo definen la firma de las tres
funciones de búsqueda; en modo demo se sustituyen por las de `demo.py`.

Para activar una integración real, implementa aquí la llamada al proveedor (con
su API key en variable de entorno, ver config.py) y devuelve las mismas
estructuras (`Hotel`, `OpcionTransporte`) que consume el resto del pipeline.
Las firmas coinciden con las de `demo.py` para poder intercambiarlas.
"""

# importo las anotaciones modernas
from __future__ import annotations

# traigo los moldes que devuelven estas funciones
from mercurio.schemas import Hotel, OpcionCoche, OpcionTaxi, OpcionTransporte

# mensaje común para las tres funciones aún sin integrar
_PENDIENTE = (
    "Integración real de proveedores pendiente. Usa el modo demo "
    "(MERCURIO_DEMO=1) o implementa la llamada al proveedor en sources.py."
)


# busco hoteles reales en la ciudad del evento para las fechas de la estancia
def buscar_hoteles(
    ciudad_destino: str, llegada_iso: str, salida_iso: str, noches: int,
    personas: int, preferencias: str | None, semilla: str,
) -> list[Hotel]:
    # todavía no hay proveedor real cableado
    raise NotImplementedError(_PENDIENTE)


# busco vuelos reales de ida y vuelta entre el origen y la ciudad del evento
def buscar_vuelos(
    origen: str, destino: str, llegada_iso: str, salida_iso: str,
    personas: int, preferencias: str | None, semilla: str,
) -> list[OpcionTransporte]:
    # todavía no hay proveedor real cableado
    raise NotImplementedError(_PENDIENTE)


# busco trenes reales de ida y vuelta entre el origen y la ciudad del evento
def buscar_trenes(
    origen: str, destino: str, llegada_iso: str, salida_iso: str,
    personas: int, preferencias: str | None, semilla: str,
) -> list[OpcionTransporte]:
    # todavía no hay proveedor real cableado
    raise NotImplementedError(_PENDIENTE)


# busco servicios reales de taxi/traslado en la ciudad del evento
def buscar_taxis(
    ciudad_destino: str, personas: int, preferencias: str | None, semilla: str,
) -> list[OpcionTaxi]:
    # todavía no hay proveedor real cableado
    raise NotImplementedError(_PENDIENTE)


# busco coches de alquiler reales en el destino para esas fechas
def buscar_coches(
    ciudad_destino: str, llegada_iso: str, salida_iso: str, dias: int,
    personas: int, preferencias: str | None, semilla: str,
) -> list[OpcionCoche]:
    # todavía no hay proveedor real cableado
    raise NotImplementedError(_PENDIENTE)
