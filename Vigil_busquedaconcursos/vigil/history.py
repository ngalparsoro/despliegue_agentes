"""Registro histórico de concursos encontrados (SQLite).

Mientras `dedupe.py` solo recuerda *qué* expedientes se han visto (para no
reprocesarlos), este módulo guarda el concurso **entero** de cada convocatoria
encontrada — sea relevante para Mitumi o no — para que la plataforma pueda
ofrecer un histórico consultable con filtros (texto, diputación, urgencia, solo
los que siguen en plazo, solo los relevantes).

Vive en el mismo fichero SQLite que el dedupe (`config.SQLITE_PATH`), en una
tabla aparte `concursos`; se conecta con el mismo `dedupe.get_connection`, así
que la tabla se crea sola la primera vez.
"""

# traigo json para serializar las listas (etiquetas, campos no verificables)
import json
# traigo sqlite3 solo para las anotaciones de tipo
import sqlite3

# traigo el helper que pasa el plazo a ISO (para filtrar/ordenar por plazo)
from vigil.dates import plazo_a_iso
# traigo los moldes que uso como entrada al guardar
from vigil.schemas import Convocatoria, Urgencia, VeredictoRelevancia

# escribo la orden que crea la tabla del histórico si todavía no existe
_SCHEMA = """
CREATE TABLE IF NOT EXISTS concursos (
    id_expediente TEXT PRIMARY KEY,
    diputacion TEXT,
    objeto TEXT,
    organo_convocante TEXT,
    importe TEXT,
    plazo_presentacion TEXT,
    plazo_iso TEXT,
    enlace_pliego TEXT,
    fecha_publicacion TEXT,
    fecha_ultima_publicacion TEXT,
    relevante INTEGER,
    motivo TEXT,
    etiquetas TEXT,
    campos_no_verificables TEXT,
    urgencia_nivel TEXT,
    urgencia_dias INTEGER,
    visto_por_primera_vez TEXT NOT NULL DEFAULT (datetime('now')),
    ultima_actualizacion TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# guardo el orden en que quiero devolver las columnas al consultar
_COLUMNAS = [
    "id_expediente",
    "diputacion",
    "objeto",
    "organo_convocante",
    "importe",
    "plazo_presentacion",
    "plazo_iso",
    "enlace_pliego",
    "fecha_publicacion",
    "fecha_ultima_publicacion",
    "relevante",
    "motivo",
    "etiquetas",
    "campos_no_verificables",
    "urgencia_nivel",
    "urgencia_dias",
    "visto_por_primera_vez",
    "ultima_actualizacion",
]


# me aseguro de que la tabla del histórico existe en esta conexión
def asegurar_tabla(conn: sqlite3.Connection) -> None:
    # creo la tabla si no estaba
    conn.execute(_SCHEMA)
    # confirmo el cambio
    conn.commit()


# guardo (o actualizo) un concurso en el histórico
def guardar_concurso(
    conn: sqlite3.Connection,
    convocatoria: Convocatoria,
    veredicto: VeredictoRelevancia | None,
    urgencia: Urgencia | None,
    relevante: bool,
) -> None:
    """Inserta o actualiza un concurso encontrado (relevante o no).

    Conserva `visto_por_primera_vez` de la primera vez que se vio y refresca
    `ultima_actualizacion` en cada aparición (p. ej. si se modifica el pliego).
    """
    # me aseguro de que la tabla existe antes de escribir
    asegurar_tabla(conn)

    # calculo el plazo en formato ISO para poder filtrar/ordenar por él
    plazo_iso = plazo_a_iso(convocatoria.plazo_presentacion)
    # serializo las etiquetas a JSON (o None si no hubo veredicto)
    etiquetas = json.dumps(veredicto.etiquetas, ensure_ascii=False) if veredicto else None
    # serializo los campos no verificables a JSON (o None si no hubo veredicto)
    no_verificables = (
        json.dumps(veredicto.campos_no_verificables, ensure_ascii=False) if veredicto else None
    )
    # saco el motivo del veredicto (o None si no hubo)
    motivo = veredicto.motivo if veredicto else None
    # saco el nivel y los días de urgencia (o None si no se calculó)
    urgencia_nivel = urgencia.nivel if urgencia else None
    urgencia_dias = urgencia.dias_habiles_restantes if urgencia else None

    # inserto la fila; si ya existía ese expediente, actualizo todo menos la
    # fecha en que se vio por primera vez, y refresco la última actualización
    conn.execute(
        """
        INSERT INTO concursos (
            id_expediente, diputacion, objeto, organo_convocante, importe,
            plazo_presentacion, plazo_iso, enlace_pliego, fecha_publicacion,
            fecha_ultima_publicacion, relevante, motivo, etiquetas,
            campos_no_verificables, urgencia_nivel, urgencia_dias
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id_expediente) DO UPDATE SET
            diputacion = excluded.diputacion,
            objeto = excluded.objeto,
            organo_convocante = excluded.organo_convocante,
            importe = excluded.importe,
            plazo_presentacion = excluded.plazo_presentacion,
            plazo_iso = excluded.plazo_iso,
            enlace_pliego = excluded.enlace_pliego,
            fecha_publicacion = excluded.fecha_publicacion,
            fecha_ultima_publicacion = excluded.fecha_ultima_publicacion,
            relevante = excluded.relevante,
            motivo = excluded.motivo,
            etiquetas = excluded.etiquetas,
            campos_no_verificables = excluded.campos_no_verificables,
            urgencia_nivel = excluded.urgencia_nivel,
            urgencia_dias = excluded.urgencia_dias,
            ultima_actualizacion = datetime('now')
        """,
        (
            convocatoria.id_expediente,
            convocatoria.diputacion,
            convocatoria.objeto,
            convocatoria.organo_convocante,
            convocatoria.importe,
            convocatoria.plazo_presentacion,
            plazo_iso,
            convocatoria.enlace_pliego,
            convocatoria.fecha_publicacion,
            convocatoria.fecha_ultima_publicacion,
            1 if relevante else 0,
            motivo,
            etiquetas,
            no_verificables,
            urgencia_nivel,
            urgencia_dias,
        ),
    )
    # confirmo el cambio en el fichero
    conn.commit()


# convierto una fila de la base de datos en un diccionario cómodo para la API
def _fila_a_dict(fila: sqlite3.Row) -> dict:
    # parto de un diccionario con todas las columnas por su nombre
    d = {col: fila[col] for col in _COLUMNAS}
    # convierto el 0/1 de relevante en un booleano (o None si no se evaluó)
    d["relevante"] = None if d["relevante"] is None else bool(d["relevante"])
    # devuelvo las etiquetas ya como lista (o lista vacía si no había)
    d["etiquetas"] = json.loads(d["etiquetas"]) if d["etiquetas"] else []
    # devuelvo los campos no verificables ya como lista
    d["campos_no_verificables"] = (
        json.loads(d["campos_no_verificables"]) if d["campos_no_verificables"] else []
    )
    # devuelvo el diccionario listo
    return d


# consulto el histórico con los filtros que pida la plataforma
def consultar(
    conn: sqlite3.Connection,
    *,
    q: str | None = None,
    diputacion: str | None = None,
    urgencia: str | None = None,
    solo_en_plazo: bool = False,
    solo_relevantes: bool = False,
    limite: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Devuelve concursos del histórico ordenados por plazo (los más próximos antes).

    - `q`: busca el texto en el objeto y en el órgano convocante.
    - `diputacion`: filtra por territorio (Araba / Gipuzkoa / Bizkaia).
    - `urgencia`: filtra por nivel (alta / media / baja / cerrado / desconocida).
    - `solo_en_plazo`: solo los que tienen plazo y aún no ha vencido.
    - `solo_relevantes`: solo los que el LLM marcó como relevantes para Mitumi.
    """
    # me aseguro de que la tabla existe antes de leer
    asegurar_tabla(conn)
    # uso filas accesibles por nombre de columna
    conn.row_factory = sqlite3.Row

    # empiezo con una lista de condiciones vacía y sus parámetros
    condiciones: list[str] = []
    parametros: list = []

    # si buscan texto, filtro por objeto u órgano convocante
    if q:
        condiciones.append("(objeto LIKE ? OR organo_convocante LIKE ?)")
        parametros.extend([f"%{q}%", f"%{q}%"])
    # si filtran por diputación, la añado
    if diputacion:
        condiciones.append("diputacion = ?")
        parametros.append(diputacion)
    # si filtran por nivel de urgencia, lo añado
    if urgencia:
        condiciones.append("urgencia_nivel = ?")
        parametros.append(urgencia)
    # si solo quieren los que siguen en plazo, comparo el plazo ISO con hoy
    if solo_en_plazo:
        condiciones.append("plazo_iso IS NOT NULL AND date(plazo_iso) >= date('now')")
    # si solo quieren los relevantes, lo añado
    if solo_relevantes:
        condiciones.append("relevante = 1")

    # monto la cláusula WHERE solo si hay alguna condición
    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    # monto la consulta: ordeno por plazo (los sin plazo al final) y pagino
    sql = (
        f"SELECT * FROM concursos {where} "
        "ORDER BY plazo_iso IS NULL, plazo_iso ASC "
        "LIMIT ? OFFSET ?"
    )
    # añado el límite y el desplazamiento como últimos parámetros
    parametros.extend([limite, offset])

    # ejecuto la consulta y convierto cada fila en diccionario
    filas = conn.execute(sql, parametros).fetchall()
    return [_fila_a_dict(fila) for fila in filas]


# recupero un único concurso por su id de expediente (o None si no está)
def obtener(conn: sqlite3.Connection, id_expediente: str) -> dict | None:
    # me aseguro de que la tabla existe antes de leer
    asegurar_tabla(conn)
    # uso filas accesibles por nombre de columna
    conn.row_factory = sqlite3.Row
    # busco la fila de ese expediente
    fila = conn.execute(
        "SELECT * FROM concursos WHERE id_expediente = ?", (id_expediente,)
    ).fetchone()
    # si no existe, devuelvo None; si existe, la convierto a diccionario
    return _fila_a_dict(fila) if fila is not None else None


# cuento cuántos concursos hay guardados (lo usa la API para saber cuántos son nuevos)
def contar(conn: sqlite3.Connection) -> int:
    # me aseguro de que la tabla existe
    asegurar_tabla(conn)
    # devuelvo el total de filas
    return conn.execute("SELECT COUNT(*) FROM concursos").fetchone()[0]
