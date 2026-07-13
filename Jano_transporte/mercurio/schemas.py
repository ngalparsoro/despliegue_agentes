"""Modelos Pydantic v2 de Mercurio.

El agente ya no lee de ninguna base de datos: la búsqueda se dispara con un
formulario. La entrada es una `SolicitudBusqueda` (los campos del formulario) y
la salida es una `PropuestaViaje` con las sugerencias de hotel y/o viaje.
"""

# importo las anotaciones de tipo modernas para poder escribir "str | None"
from __future__ import annotations

# traigo Literal (lista cerrada de valores) y Optional (algo que puede ser None)
from typing import Literal, Optional

# traigo la clase base de Pydantic, Field y el validador de modelo
from pydantic import BaseModel, Field, model_validator

# defino los dos modos de transporte que contempla el agente
ModoTransporte = Literal["vuelo", "tren"]


# creo el molde de la solicitud de búsqueda (lo que llega del formulario)
class SolicitudBusqueda(BaseModel):
    """Los campos del formulario que disparan una búsqueda."""

    # --- ponente ---
    # nombre del ponente (obligatorio; sale en los informes)
    nombre_ponente: str
    # email del ponente (opcional; para enviarle el PDF)
    email_ponente: Optional[str] = None

    # --- evento ---
    # nombre del evento (opcional; sale en el informe)
    nombre_evento: Optional[str] = None
    # ciudad donde se celebra el evento (el destino del viaje)
    ciudad_evento: str
    # primer día del evento (fecha ISO YYYY-MM-DD)
    fecha_inicio: str
    # último día del evento (fecha ISO YYYY-MM-DD)
    fecha_fin: str

    # --- viaje ---
    # ciudad de origen del ponente (obligatoria SOLO si se pide viaje)
    ciudad_origen: Optional[str] = None

    # --- opciones ampliadas ---
    # número de personas que viajan (el ponente y posibles acompañantes)
    personas: int = Field(default=1, ge=1, le=20)
    # preferencias en texto libre (p. ej. "sin escalas", "cerca del recinto")
    preferencias: Optional[str] = None

    # --- qué se busca (una casilla "Necesita" por servicio) ---
    # si el ponente necesita hotel (alojamiento)
    necesita_hotel: bool = True
    # si el ponente necesita viaje (vuelos y trenes)
    necesita_viaje: bool = True
    # si el ponente necesita taxi (traslados en la ciudad del evento)
    necesita_taxi: bool = False
    # si el ponente necesita coche de alquiler en el destino
    necesita_coche: bool = False

    # valido que la solicitud tenga sentido antes de buscar
    @model_validator(mode="after")
    def _coherente(self) -> "SolicitudBusqueda":
        # tiene que pedir al menos un servicio
        if not any((self.necesita_hotel, self.necesita_viaje, self.necesita_taxi, self.necesita_coche)):
            raise ValueError("Marca al menos un servicio (hotel, viaje, taxi o coche) para buscar.")
        # si pide viaje (vuelos/trenes), la ciudad de origen es obligatoria
        if self.necesita_viaje and not (self.ciudad_origen or "").strip():
            raise ValueError("Para buscar viaje hace falta la ciudad de origen.")
        # devuelvo la propia solicitud ya validada
        return self


# creo el molde de un ponente (datos que salen en los informes)
class Ponente(BaseModel):
    """Los datos del ponente que se muestran y se vuelcan a los PDFs."""

    # nombre del ponente
    nombre: str
    # correo del ponente (para enviarle el informe)
    email: Optional[str] = None
    # ciudad desde la que viaja el ponente
    ciudad_origen: Optional[str] = None


# creo el molde de un evento
class Evento(BaseModel):
    """Los datos del evento (destino y fechas del viaje)."""

    # nombre del evento (puede faltar)
    nombre: Optional[str] = None
    # ciudad donde se celebra el evento (el destino del viaje)
    ciudad: str
    # primer día del evento (fecha ISO)
    fecha_inicio: str
    # último día del evento (fecha ISO)
    fecha_fin: str


# creo el molde de una sugerencia de hotel
class Hotel(BaseModel):
    """Una sugerencia de alojamiento en la ciudad del evento."""

    # nombre comercial del hotel
    nombre: str
    # categoría en estrellas (1-5)
    estrellas: int
    # valoración media de los huéspedes (0-10)
    valoracion: float
    # distancia en km hasta el recinto del evento
    distancia_recinto_km: float
    # precio por noche (de una habitación)
    precio_noche: float
    # número de noches de la estancia
    noches: int
    # número de habitaciones necesarias para el grupo
    habitaciones: int = 1
    # precio total de la estancia (precio_noche * noches * habitaciones)
    precio_total: float
    # moneda de los precios
    moneda: str = "EUR"
    # enlace directo para reservar (la "opción de ir al link de compra")
    enlace_reserva: str


# creo el molde de un tramo del viaje (la ida o la vuelta)
class Trayecto(BaseModel):
    """Un tramo concreto: origen, destino, horarios, duración y escalas."""

    # ciudad de salida del tramo
    origen: str
    # ciudad de llegada del tramo
    destino: str
    # fecha y hora de salida (ISO datetime)
    salida: str
    # fecha y hora de llegada (ISO datetime)
    llegada: str
    # duración del tramo en minutos
    duracion_min: int
    # número de escalas/transbordos (0 = directo)
    escalas: int


# creo el molde de una opción de transporte de ida y vuelta (vuelo o tren)
class OpcionTransporte(BaseModel):
    """Una opción de ida y vuelta en avión o tren, con su enlace de compra."""

    # modo de transporte: "vuelo" o "tren"
    modo: ModoTransporte
    # compañía que opera (aerolínea u operador ferroviario)
    proveedor: str
    # tramo de ida (del origen del ponente a la ciudad del evento)
    ida: Trayecto
    # tramo de vuelta (de la ciudad del evento al origen del ponente)
    vuelta: Trayecto
    # precio total de ida y vuelta para todas las personas
    precio_total: float
    # moneda del precio
    moneda: str = "EUR"
    # enlace directo para comprar los billetes
    enlace_reserva: str


# creo el molde de una sugerencia de taxi (traslado en la ciudad del evento)
class OpcionTaxi(BaseModel):
    """Una sugerencia de taxi/traslado en el destino, con su enlace."""

    # compañía o servicio (radio taxi, Cabify, Uber…)
    proveedor: str
    # qué cubre (p. ej. "Traslado aeropuerto ↔ hotel", "Servicio a demanda")
    descripcion: str
    # precio estimado del servicio
    precio_estimado: float
    # moneda del precio
    moneda: str = "EUR"
    # enlace o teléfono para contratarlo
    enlace_reserva: str


# creo el molde de una sugerencia de coche de alquiler
class OpcionCoche(BaseModel):
    """Una sugerencia de coche de alquiler en el destino, con su enlace."""

    # compañía de alquiler (Europcar, Hertz, Sixt…)
    compania: str
    # categoría del vehículo (Compacto, SUV, Familiar…)
    categoria: str
    # oficina de recogida (aeropuerto, centro…)
    oficina: str
    # precio por día
    precio_dia: float
    # número de días de alquiler
    dias: int
    # precio total del alquiler (precio_dia * dias)
    precio_total: float
    # moneda del precio
    moneda: str = "EUR"
    # enlace directo para reservar
    enlace_reserva: str


# creo el molde que agrupa toda la propuesta de viaje
class PropuestaViaje(BaseModel):
    """El resultado de una búsqueda: sugerencias de hotel y/o viaje."""

    # identificador de esta búsqueda (para descargar sus PDFs)
    id: str
    # el ponente que viaja
    ponente: Ponente
    # el evento al que asiste
    evento: Evento
    # sello de tiempo de cuándo se generó la propuesta (ISO)
    generado_en: str
    # día en que el ponente llega a la ciudad del evento (fecha ISO)
    fecha_llegada: str
    # día en que el ponente se marcha (fecha ISO)
    fecha_salida: str
    # número de noches de hotel
    noches: int
    # número de personas que viajan
    personas: int = 1
    # preferencias tenidas en cuenta (texto libre)
    preferencias: Optional[str] = None
    # si se buscó hotel
    necesita_hotel: bool = True
    # si se buscó viaje
    necesita_viaje: bool = True
    # si se buscó taxi
    necesita_taxi: bool = False
    # si se buscó coche de alquiler
    necesita_coche: bool = False
    # las sugerencias de hotel (vacía si no se pidió hotel)
    hoteles: list[Hotel] = Field(default_factory=list)
    # las sugerencias de vuelo (vacía si no se pidió viaje o no hay ruta)
    vuelos: list[OpcionTransporte] = Field(default_factory=list)
    # las sugerencias de tren (vacía si no se pidió viaje o no hay ruta)
    trenes: list[OpcionTransporte] = Field(default_factory=list)
    # las sugerencias de taxi (vacía si no se pidió taxi)
    taxis: list[OpcionTaxi] = Field(default_factory=list)
    # las sugerencias de coche de alquiler (vacía si no se pidió coche)
    coches: list[OpcionCoche] = Field(default_factory=list)
    # resumen redactado del viaje (sin precios; va también en el PDF del ponente)
    resumen: str = ""
    # recomendación con importes (para el organizador / la plataforma)
    recomendacion: str = ""
    # recomendación SIN precios (para el PDF que se envía al ponente)
    recomendacion_sin_precio: str = ""
    # PORQUÉ de la recomendación para el organizador (puede hablar de coste)
    justificacion: str = ""
    # PORQUÉ para el ponente: por comodidad/conveniencia, SIN hablar de precio
    justificacion_ponente: str = ""
    # coste estimado de la opción recomendada (hotel + transporte), o None
    coste_estimado: Optional[float] = None
