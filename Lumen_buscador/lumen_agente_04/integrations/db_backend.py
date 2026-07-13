"""
integrations/db_backend.py — Cliente de SOLO LECTURA para la base de datos real (Postgres,
hoy alojada en Neon) descrita en data/rag/documentos/esquema_bd.md.

Fuente unica de datos (ver src/lectura_datos.py): no hay mock JSON ni API HTTP intermedia — se
retiraron deliberadamente. Esta conexion cubre las 8 tablas permitidas, incluidas salas,
presupuestos, estados y ponencias.

Solo lectura reforzada en tres capas, no una sola:
1. Este modulo NUNCA construye ni ejecuta INSERT/UPDATE/DELETE - no existen esas funciones aqui.
2. Cada conexion se abre con `set_session(readonly=True)`, que hace que Postgres rechace
   cualquier sentencia de escritura a nivel de protocolo, aunque hubiera un bug en el codigo.
3. La tabla `usuarios` sigue bloqueada en config/permisos.py (TABLAS_EXCLUIDAS) y ese bloqueo se
   comprueba aqui tambien (_verificar_tabla), antes de construir cualquier consulta.

Seguridad de las consultas: el nombre de tabla se interpola en el SQL (psycopg2 no permite
parametrizar identificadores), pero SIEMPRE viene de config/permisos.TABLAS_PERMITIDAS - nunca de
texto libre del usuario ni del payload. Los valores (ids, filtros) siempre van parametrizados
con %s, nunca concatenados. `listar()` concatena nombres de columna en el WHERE, pero quien
llama a esta funcion (src/lectura_datos.py) siempre pasa nombres de columna fijos del propio
codigo, nunca claves que vengan directamente de la pregunta del usuario.

Esquema verificado en vivo contra la BD real (Neon) con integrations/verificar_conexion_bd.py:
las tablas y columnas coinciden con data/rag/documentos/esquema_bd.md. La unica diferencia detectada
fue la columna presupuestos.observaciones (presente en la BD y antes no documentada), ya añadida al
esquema. Como las lecturas son SELECT *, cualquier columna nueva se devuelve sin tocar codigo; si en
el futuro cambian nombres de tabla o columna, re-ejecuta ese script para detectarlo.

Normalizacion de tipos (_serializar_fila): psycopg2 devuelve datetime.date/datetime para columnas
de fecha, decimal.Decimal para numeric/money y uuid.UUID para columnas uuid - no str/float como
los datos mock antiguos. TODA fila que sale de este modulo (obtener_por_id, listar) pasa por
_serializar_fila antes de devolverse, precisamente para que src/nucleo.py (que concatena fechas
en strings) y json.dumps() (para el prompt del LLM) reciban siempre tipos planos compatibles.
"""

import datetime
import decimal
import uuid
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from config.permisos import TABLAS_EXCLUIDAS, TABLAS_PERMITIDAS
from config.settings import DATABASE_URL


class DbBackendError(RuntimeError):
    """Fallo de conexion, permisos o consulta al hablar con la base de datos real."""


def _serializar_valor(valor):
    """
    psycopg2 devuelve tipos nativos de Python para columnas date/timestamp (datetime.date /
    datetime.datetime), numeric (decimal.Decimal) y uuid (uuid.UUID) - no str/float como los
    datos mock antiguos. El resto del codigo (concatenacion de strings en src/nucleo.py,
    json.dumps() para el prompt del LLM) asume valores JSON-planos, asi que sin esta conversion
    revientan: p.ej. "del " + datos["fecha_inicio"] con un datetime.date da
    TypeError: can only concatenate str (not "datetime.date") to str, y json.dumps() sobre un
    Decimal o un date lanza TypeError: Object of type ... is not JSON serializable (esto ultimo
    se tragaba en silencio en _responder_con_llm por su except Exception generico, y el fallback
    determinista rompia igual, sin capturar, al no pasar por ese try).
    """
    if isinstance(valor, datetime.datetime):
        # Las fechas de evento (fecha_inicio/fecha_fin) se guardan como timestamp a medianoche; se
        # muestran como fecha sola (2026-12-10) en vez de 2026-12-10T00:00:00+00:00. Un timestamp
        # con hora real (p.ej. horarios de transporte) se conserva entero.
        if valor.hour == 0 and valor.minute == 0 and valor.second == 0 and valor.microsecond == 0:
            return valor.date().isoformat()
        return valor.isoformat()
    if isinstance(valor, datetime.date):
        return valor.isoformat()
    if isinstance(valor, decimal.Decimal):
        return float(valor)
    if isinstance(valor, uuid.UUID):
        return str(valor)
    return valor


def _serializar_fila(fila: dict) -> dict:
    return {clave: _serializar_valor(valor) for clave, valor in fila.items()}


def db_disponible() -> bool:
    """True si hay una cadena de conexion configurada en .env (DATABASE_URL)."""
    return bool(DATABASE_URL)


def _verificar_tabla(tabla: str) -> None:
    if tabla in TABLAS_EXCLUIDAS:
        raise DbBackendError("Lumen no tiene acceso a la tabla '" + tabla + "'.")
    if tabla not in TABLAS_PERMITIDAS:
        raise DbBackendError("Tabla '" + tabla + "' fuera del alcance de Lumen.")


@contextmanager
def _conexion():
    if not db_disponible():
        raise DbBackendError("DATABASE_URL no configurada en .env - no se puede conectar a la BD real.")

    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        # Defensa en profundidad: la sesion completa queda en modo solo lectura a nivel de
        # Postgres, no solo por convencion en el codigo Python.
        conn.set_session(readonly=True, autocommit=True)
        yield conn
    except psycopg2.OperationalError as exc:
        raise DbBackendError("No se pudo conectar a la base de datos real: " + str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


# Reutilizacion de conexion: contexto_completo_evento hace ~6 lecturas seguidas del mismo evento.
# Con una conexion nueva por lectura eran ~6 conexiones a Postgres; pasando `conn` se hacen todas
# sobre una sola. Si `conn` es None se mantiene el comportamiento de antes (abrir y cerrar).
@contextmanager
def _conexion_o(conn):
    if conn is not None:
        yield conn  # reutiliza una conexion ya abierta; la cierra quien la abrio, no aqui
    else:
        with _conexion() as nueva:
            yield nueva


# Alias publico para que src/lectura_datos.py abra UNA conexion y la reutilice en varias lecturas
# (misma sesion readonly). No expone escritura: sigue sin haber INSERT/UPDATE/DELETE.
abrir_conexion = _conexion


def obtener_por_id(tabla: str, id_valor, conn=None):
    """
    Devuelve el registro de `tabla` cuyo id coincide, o None si no existe.
    Si se pasa `conn`, reutiliza esa conexion en vez de abrir una nueva.
    """
    _verificar_tabla(tabla)
    if id_valor is None:
        return None
    consulta = "SELECT * FROM " + tabla + " WHERE id = %s"
    try:
        with _conexion_o(conn) as cx:
            with cx.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(consulta, (id_valor,))
                fila = cur.fetchone()
                return _serializar_fila(fila) if fila else None
    except psycopg2.Error as exc:
        raise DbBackendError("Fallo al consultar '" + tabla + "': " + str(exc)) from exc


def listar(tabla: str, filtros: dict = None, conn=None):
    """
    Devuelve todos los registros de `tabla`, opcionalmente filtrados por igualdad exacta.
    `filtros` debe venir siempre del propio codigo (nombres de columna fijos), nunca de texto
    libre del usuario - ver nota de seguridad en la cabecera del modulo.
    Si se pasa `conn`, reutiliza esa conexion en vez de abrir una nueva.
    """
    _verificar_tabla(tabla)
    consulta = "SELECT * FROM " + tabla
    valores = []
    if filtros:
        condiciones = []
        for campo, valor in filtros.items():
            if valor is None:
                continue
            condiciones.append(campo + " = %s")
            valores.append(valor)
        if condiciones:
            consulta += " WHERE " + " AND ".join(condiciones)
    try:
        with _conexion_o(conn) as cx:
            with cx.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(consulta, valores)
                return [_serializar_fila(fila) for fila in cur.fetchall()]
    except psycopg2.Error as exc:
        raise DbBackendError("Fallo al consultar '" + tabla + "': " + str(exc)) from exc
