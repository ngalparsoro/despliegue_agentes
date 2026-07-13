# knowledge/status_3.py

# Estados del evento (tabla `estados`). Verificado 1:1 contra
# Datos_alimentación_bbdd_Leire_Eduardo/estados.csv (id_estado,
# descripcion) — es un catálogo cerrado, no una muestra parcial.
EVENT_STATUS = [
    "Borrador",
    "Presupuestado",
    "Pendiente de aprobación",
    "Confirmado",
    "En ejecución",
    "Celebrado",
    "Cancelado",
    "Facturado"
]

# Estado del presupuesto (columna `estado_presupuesto` de la tabla
# `presupuestos`). A diferencia de EVENT_STATUS, esto NO es un catálogo
# cerrado documentado en ningún sitio: son los únicos valores que
# aparecen en la muestra de datos de
# Datos_alimentación_bbdd_Leire_Eduardo/presupuestos.csv ("Aprobado",
# "Pendiente"). Si en el futuro se define un enum formal para este
# campo (o aparecen más valores en la BD real), esta lista habrá que
# ampliarla — no se puede dar por cerrada como EVENT_STATUS.
BUDGET_STATUS = [
    "Aprobado",
    "Pendiente"
]
