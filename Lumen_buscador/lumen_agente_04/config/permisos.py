"""
Permisos de Lumen (Agente 04 - Copilot).

Estos valores son NO configurables al alza: aunque `.env` intentase activar escritura,
en código se fuerzan siempre a False (defensa en profundidad). Lumen es un agente de
solo consulta y esto es una restricción arquitectonica permanente, no un valor por defecto.
"""

ALLOW_DB_WRITE = False
ALLOW_EXTERNAL_SEND = False
ALLOW_CREATE_EVENT = False
ALLOW_AUTO_APPROVAL = False

# Tablas a las que Lumen nunca accede, pase lo que pase en el esquema o en el .env.
TABLAS_EXCLUIDAS = {"usuarios"}

# Tablas dentro del alcance de negocio de Lumen (ver data/rag/documentos/esquema_bd.md).
TABLAS_PERMITIDAS = {
    "clientes",
    "eventos",
    "presupuestos",
    "ponentes",
    "ponencias",
    "salas",
    "espacios",
}
