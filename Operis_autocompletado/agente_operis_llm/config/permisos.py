"""
Permisos de agente_operis.

Estos valores son NO configurables al alza: aunque .env intentase
activar escritura, en código se fuerzan siempre a False (defensa en
profundidad) — mismo patrón que Agente_04_Copilot_Raul (Lumen). Operis
es un agente de solo propuesta y esto es una restricción arquitectónica
permanente, no un valor por defecto (ver regla de oro en README.md).
"""

ALLOW_DB_WRITE = False
ALLOW_EXTERNAL_SEND = False
ALLOW_CREATE_EVENT = False
ALLOW_AUTO_APPROVAL = False

# ---------------------------------------------------------------------
# Tablas de la BD real (Neon Postgres) a las que agente_operis puede
# leer -- ver integrations/bd_backend.py y src/lectura_bd.py. Desde que
# se conectó el agente al kit_conexion_agentes_Nora (DESAFIO_MITUMI/),
# Operis SÍ consulta la BD real, aunque solo en modo lectura (ALLOW_DB_
# WRITE se queda en False siempre, sin excepción -- ver arriba).
#
# Mismo conjunto de tablas y misma convención de nombres que usa Lumen
# (Agente_04_Copilot_Raul/config/permisos.py): TABLAS_EXCLUIDAS /
# TABLAS_PERMITIDAS. "usuarios" está fuera de alcance para TODOS los
# agentes de data del proyecto, no es una decisión propia de Operis.
# ---------------------------------------------------------------------
TABLAS_EXCLUIDAS = {"usuarios"}

TABLAS_PERMITIDAS = {
    "clientes",
    "eventos",
    "presupuestos",
    "ponentes",
    "ponencias",
    "estados",
    "salas",
    "espacios",
}

# Nota sobre correspondencia con el esquema de salida de Operis (evento/
# cliente/ponentes/nota_bene): "evento", "cliente" y "ponentes" siguen
# reutilizando literalmente los nombres de columna de sus tablas, pero
# "espacios", "salas" y "presupuestos" ya no tienen un bloque de salida
# propio -- su información se resume dentro de nota_bene (cabecera +
# presupuesto_servicios), que es un resumen calculado por el LLM, NO una
# copia campo a campo de esas columnas. Un futuro backend que quiera un
# INSERT directo en esas tres tablas tendría que traducir nota_bene, no
# volcarla tal cual.
#
# Nota sobre "ponencias": en el esquema real de la BD (ver
# Agente_04_Copilot_Raul/data/rag/documentos/esquema_bd.md), cada evento
# enlaza como mucho con UNA ponencia (y por tanto un único ponente) --
# no existe la tabla "evento_ponente" (N:N) que asumían versiones
# anteriores de esta ficha. Operis sigue modelando `ponentes` como una
# lista en su esquema de salida (para no perder información si el
# briefing menciona varios), pero al leer o fusionar con la BD real,
# esa lista tendrá como mucho un elemento -- limitación real de la BD,
# no del agente (ver README.md, sección 8).
