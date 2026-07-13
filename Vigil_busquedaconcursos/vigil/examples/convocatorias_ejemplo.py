"""Convocatorias de ejemplo (simuladas) para probar el pipeline 2.0 sin depender
de que haya novedades ese día en KontratazioA.

Tienen la misma forma que los diccionarios "crudos" que devuelve
sources.obtener_convocatorias(). Están pensadas para lucir las mejoras de la
2.0: distintas urgencias (según el plazo), etiquetas temáticas y una que se
marcará como modificación. Las fechas están puestas en relación a julio de 2026.
"""

# creo una lista con varias convocatorias de ejemplo para la demo visual
EJEMPLOS: list[dict] = [
    # relevante + urgencia ALTA (plazo muy cercano) — congreso institucional
    {
        "diputacion": "Araba",
        "objeto": (
            "Servicio de organización integral y secretaría técnica del Congreso "
            "Institucional sobre Transición Energética 2026, incluyendo gestión del "
            "espacio, ponentes, catering y modalidad híbrida."
        ),
        "enlace_pliego": "https://www.contratacion.euskadi.eus/ejemplo/congreso-transicion-energetica",
        "id_expediente": "EJEMPLO-2026-0000001",
        "fecha_publicacion": "05/07/2026",
        "fecha_ultima_publicacion": "05/07/2026",
        "tipo_contrato": "Servicios",
        "estado_tramitacion": "Abierto / Plazo de presentación",
        "plazo_presentacion": "14/07/2026 23:59:00",
        "importe": "45.000,00",
        "organo_convocante": "Diputación Foral de Álava",
        "entidad_impulsora": "Departamento de Desarrollo Económico y Sostenibilidad",
    },
    # relevante + urgencia MEDIA — evento gastronómico (especialidad de Mitumi)
    {
        "diputacion": "Araba",
        "objeto": (
            "Diseño y ejecución de una serie de showcookings y catas de producto local "
            "para la campaña de promoción gastronómica del territorio, con degustaciones "
            "abiertas al público."
        ),
        "enlace_pliego": "https://www.contratacion.euskadi.eus/ejemplo/showcooking-gastronomia",
        "id_expediente": "EJEMPLO-2026-0000004",
        "fecha_publicacion": "06/07/2026",
        "fecha_ultima_publicacion": "06/07/2026",
        "tipo_contrato": "Servicios",
        "estado_tramitacion": "Abierto / Plazo de presentación",
        "plazo_presentacion": "22/07/2026 23:59:00",
        "importe": "28.000,00",
        "organo_convocante": "Diputación Foral de Álava",
        "entidad_impulsora": "Departamento de Agricultura",
    },
    # relevante + urgencia BAJA — formación y procesos participativos
    {
        "diputacion": "Gipuzkoa",
        "objeto": (
            "Diseño y dinamización de una jornada de participación ciudadana y talleres "
            "creativos sobre movilidad sostenible, con facilitación gráfica."
        ),
        "enlace_pliego": "https://www.contratacion.euskadi.eus/ejemplo/jornada-participacion",
        "id_expediente": "EJEMPLO-2026-0000005",
        "fecha_publicacion": "07/07/2026",
        "fecha_ultima_publicacion": "07/07/2026",
        "tipo_contrato": "Servicios",
        "estado_tramitacion": "Abierto / Plazo de presentación",
        "plazo_presentacion": "12/08/2026 23:59:00",
        "importe": "18.500,00",
        "organo_convocante": "Diputación Foral de Gipuzkoa",
        "entidad_impulsora": "Departamento de Movilidad",
    },
    # relevante + MODIFICACIÓN — gala de premios cuyo plazo se ha ampliado
    # (en la demo, la base de datos ya la tiene con una última publicación anterior)
    {
        "diputacion": "Araba",
        "objeto": (
            "Organización de la gala de entrega de premios del comercio local, con "
            "secretaría técnica, protocolo y producción del acto."
        ),
        "enlace_pliego": "https://www.contratacion.euskadi.eus/ejemplo/gala-premios-comercio",
        "id_expediente": "EJEMPLO-2026-0000006",
        "fecha_publicacion": "20/06/2026",
        "fecha_ultima_publicacion": "08/07/2026",
        "tipo_contrato": "Servicios",
        "estado_tramitacion": "Abierto / Plazo de presentación",
        "plazo_presentacion": "25/08/2026 23:59:00",
        "importe": "22.000,00",
        "organo_convocante": "Diputación Foral de Álava",
        "entidad_impulsora": "Departamento de Comercio",
    },
    # NO relevante — obra pública, fuera del perfil de Mitumi
    {
        "diputacion": "Gipuzkoa",
        "objeto": (
            "Obras de renovación del firme y del sistema de drenaje en la carretera "
            "GI-2132, tramo Azpeitia-Azkoitia."
        ),
        "enlace_pliego": "https://www.contratacion.euskadi.eus/ejemplo/obras-gi2132",
        "id_expediente": "EJEMPLO-2026-0000002",
        "fecha_publicacion": "03/07/2026",
        "fecha_ultima_publicacion": "03/07/2026",
        "tipo_contrato": "Obras",
        "estado_tramitacion": "Abierto / Plazo de presentación",
        "plazo_presentacion": "20/08/2026 23:59:00",
        "importe": "1.230.000,00",
        "organo_convocante": "Diputación Foral de Gipuzkoa",
        "entidad_impulsora": "Departamento de Movilidad e Infraestructuras Viarias",
    },
    # NO relevante — suministro sanitario, fuera del perfil de Mitumi
    {
        "diputacion": "Bizkaia",
        "objeto": "Suministro de material sanitario fungible para centros de la Diputación Foral de Bizkaia.",
        "enlace_pliego": "https://www.contratacion.euskadi.eus/ejemplo/suministro-sanitario",
        "id_expediente": "EJEMPLO-2026-0000003",
        "fecha_publicacion": "01/07/2026",
        "fecha_ultima_publicacion": "01/07/2026",
        "tipo_contrato": "Suministros",
        "estado_tramitacion": "Abierto / Plazo de presentación",
        "plazo_presentacion": "15/07/2026 23:59:00",
        "importe": "89.500,00",
        "organo_convocante": "Diputación Foral de Bizkaia",
        "entidad_impulsora": "Departamento de Acción Social",
    },
]
