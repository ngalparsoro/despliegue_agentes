"""
integrations/bd_backend.py — acceso de SOLO LECTURA a la BBDD real (Neon Postgres).

Copiado de kit_conexion_agentes_Nora/bd_backend.py (DESAFIO_MITUMI/), el kit oficial
del proyecto para que cualquier agente de data lea la BD real -- es el mismo patrón
que ya usa Lumen en producción (Agente_04_Copilot_Raul/integrations/db_backend.py).
Adaptado para agente_operis: importa DATABASE_URL desde config/settings.py (en vez
de os.environ directo) y la lista blanca de tablas usa las tablas del dominio
(evento/cliente/ponentes/nota_bene tocan todas ellas conceptualmente).

Defensas incluidas (no las quites, ver README del kit):
- Lista blanca de tablas: el nombre de tabla NUNCA viene del LLM ni del usuario.
- Conexión marcada read-only: aunque la credencial permitiera escribir, Postgres lo rechaza.
- El rol agente_readonly además no tiene GRANT sobre `usuarios` (tercera capa, en la BBDD).
- Tipos normalizados (UUID→str, timestamps de medianoche→AAAA-MM-DD, Decimal→float).

Añadido sobre la plantilla del kit: obtener_por_id() y listar_filtrado(), con los
mismos valores SIEMPRE parametrizados (nunca concatenados) -- necesarios para que
src/lectura_bd.py pueda reconstruir el estado actual de UN evento concreto sin traer
la tabla entera cada vez.

`psycopg` se importa DENTRO de cada función, no a nivel de módulo: la conexión a BD
es opcional (ver DATABASE_URL en config/settings.py) -- si `psycopg` no estuviera
instalado, un import a nivel de módulo rompería la carga de este archivo entero, y
con ella la de src/nucleo.py (que lo importa indirectamente vía src/lectura_bd.py),
tumbando TODO el agente aunque nadie estuviera usando la BD. Mismo patrón que el
import perezoso de `groq` en src/llm.py.
"""

import datetime
import decimal
import uuid

from config.settings import DATABASE_URL

# Tablas del dominio de negocio de agente_operis (evento/cliente/ponentes/nota_bene
# tocan todas ellas; `estados` desaparecio del contrato Prisma y el estado vive en
# eventos.estado. Mismo conjunto que usa Lumen (TABLAS_PERMITIDAS) y que expone
# el rol agente_readonly -- ver kit_conexion_agentes_Nora/README.md.
_TABLAS_BD = {
    "clientes", "eventos", "presupuestos", "ponentes",
    "ponencias", "salas", "espacios",
}


class BdBackendError(RuntimeError):
    """Fallo de conexión o consulta contra la BD real."""


def bd_disponible() -> bool:
    return bool(DATABASE_URL)


def _normalizar_valor(v):
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, datetime.datetime):
        return v.date().isoformat() if v.time() == datetime.time(0, 0) else v.isoformat()
    if isinstance(v, datetime.date):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return float(v)
    return v


def _normalizar_fila(fila: dict) -> dict:
    return {k: _normalizar_valor(v) for k, v in fila.items()}


def _verificar_tabla(tabla: str) -> None:
    if tabla not in _TABLAS_BD:
        raise BdBackendError("Tabla '" + tabla + "' fuera de la lista blanca de BD.")
    if not bd_disponible():
        raise BdBackendError("DATABASE_URL no configurada en .env.")


def _importar_psycopg():
    try:
        import psycopg
        from psycopg.rows import dict_row
        return psycopg, dict_row
    except ImportError:
        raise ImportError(
            "La conexión a BD requiere el paquete 'psycopg'. Instálalo con: "
            'pip install "psycopg[binary]"'
        )


def leer_tabla(tabla: str) -> list:
    """SELECT * de una tabla de la lista blanca, como lista de dicts serializables."""
    _verificar_tabla(tabla)
    psycopg, dict_row = _importar_psycopg()
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=10, row_factory=dict_row) as conn:
            conn.read_only = True
            filas = conn.execute('SELECT * FROM "' + tabla + '"').fetchall()
    except psycopg.Error as exc:
        raise BdBackendError("No se pudo leer la tabla '" + tabla + "' de la BD real.") from exc

    return [_normalizar_fila(fila) for fila in filas]


def obtener_por_id(tabla: str, id_valor):
    """
    Devuelve el registro de `tabla` cuyo id coincide, o None si no existe.
    `id_valor` siempre va parametrizado (%s) -- nunca se concatena en el SQL.
    """
    _verificar_tabla(tabla)
    if id_valor is None:
        return None
    psycopg, dict_row = _importar_psycopg()
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=10, row_factory=dict_row) as conn:
            conn.read_only = True
            fila = conn.execute(
                'SELECT * FROM "' + tabla + '" WHERE id = %s', (id_valor,)
            ).fetchone()
    except psycopg.Error as exc:
        raise BdBackendError("No se pudo consultar '" + tabla + "' por id.") from exc

    return _normalizar_fila(fila) if fila else None


def listar_filtrado(tabla: str, columna_filtro: str, valor_filtro) -> list:
    """
    SELECT * de `tabla` filtrado por igualdad exacta en UNA columna.
    `columna_filtro` SIEMPRE debe venir del propio código (nombre fijo), nunca de
    texto libre del usuario -- el valor sí va parametrizado (%s).
    """
    _verificar_tabla(tabla)
    if valor_filtro is None:
        return []
    psycopg, dict_row = _importar_psycopg()
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=10, row_factory=dict_row) as conn:
            conn.read_only = True
            filas = conn.execute(
                'SELECT * FROM "' + tabla + '" WHERE "' + columna_filtro + '" = %s',
                (valor_filtro,)
            ).fetchall()
    except psycopg.Error as exc:
        raise BdBackendError("No se pudo consultar '" + tabla + "' filtrado.") from exc

    return [_normalizar_fila(fila) for fila in filas]
