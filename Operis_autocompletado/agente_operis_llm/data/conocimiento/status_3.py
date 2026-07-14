# knowledge/status_3.py

# Estados del evento (tabla `public.estados`). Catalogo real actualizado el
# 14/07/2026 tras simplificar el flujo operativo a 5 estados.
# Planificado -> crear evento; Reservado -> reservar lugar; Confirmado ->
# confirmar lugar + confirmar presupuesto; Finalizado -> dia posterior al
# evento; Cancelado -> cancelar evento con doble validacion.
EVENT_STATUS = [
    "Planificado",
    "Reservado",
    "Confirmado",
    "Finalizado",
    "Cancelado",
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
