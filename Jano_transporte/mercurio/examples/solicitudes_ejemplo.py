"""Solicitudes de ejemplo para la demo y para los tests.

Simulan lo que rellenaría el organizador en el formulario. Cubren distintos
casos: hotel + viaje, solo hotel, solo viaje, internacional (sin tren) y con
preferencias en texto libre.
"""

# lista de solicitudes de muestra (los campos del formulario)
SOLICITUDES: list[dict] = [
    # nacional con tren, hotel + viaje, con preferencia de cercanía
    {
        "nombre_ponente": "Elena Vidal",
        "email_ponente": "elena.vidal@example.com",
        "nombre_evento": "Congreso Gastronómico Euskadi 2026",
        "ciudad_evento": "San Sebastián",
        "fecha_inicio": "2026-09-15",
        "fecha_fin": "2026-09-17",
        "ciudad_origen": "Madrid",
        "personas": 1,
        "preferencias": "cerca del recinto",
        "necesita_hotel": True,
        "necesita_viaje": True,
    },
    # internacional (Londres): hotel + viaje, sin tren, con preferencia de directo
    {
        "nombre_ponente": "James Whitmore",
        "email_ponente": "james.whitmore@example.com",
        "nombre_evento": "Congreso Gastronómico Euskadi 2026",
        "ciudad_evento": "San Sebastián",
        "fecha_inicio": "2026-09-15",
        "fecha_fin": "2026-09-16",
        "ciudad_origen": "Londres",
        "personas": 2,
        "preferencias": "vuelo directo",
        "necesita_hotel": True,
        "necesita_viaje": True,
    },
    # solo hotel (no necesita viaje): no hace falta ciudad de origen
    {
        "nombre_ponente": "Lucía Herrera",
        "email_ponente": "lucia.herrera@example.com",
        "nombre_evento": "Jornada de Cultura y Territorio",
        "ciudad_evento": "Vitoria-Gasteiz",
        "fecha_inicio": "2026-11-20",
        "fecha_fin": "2026-11-20",
        "ciudad_origen": None,
        "personas": 1,
        "preferencias": None,
        "necesita_hotel": True,
        "necesita_viaje": False,
    },
    # solo viaje (no necesita hotel), grupo de 3 personas
    {
        "nombre_ponente": "Marc Soler",
        "email_ponente": "marc.soler@example.com",
        "nombre_evento": "Foro de Innovación Industrial",
        "ciudad_evento": "Bilbao",
        "fecha_inicio": "2026-10-02",
        "fecha_fin": "2026-10-03",
        "ciudad_origen": "Barcelona",
        "personas": 3,
        "preferencias": None,
        "necesita_hotel": False,
        "necesita_viaje": True,
    },
]
