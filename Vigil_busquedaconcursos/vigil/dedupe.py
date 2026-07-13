"""Persistencia en SQLite: evita duplicados y detecta modificaciones (Vigil 2.0).

Además de recordar qué convocatorias ya se procesaron (como en la v1),
guardo la "fecha de última publicación" de cada una. Si un expediente que ya
conocía reaparece con una última publicación distinta, es que el pliego se ha
modificado (p. ej. una ampliación de plazo) y hay que volver a avisar.
"""

# traigo sqlite3 para trabajar con la base de datos local
import sqlite3
# traigo contextmanager para crear un "with" que abre y cierra la conexión solo
from contextlib import contextmanager
# traigo Iterator y Literal para anotar bien los tipos
from typing import Iterator, Literal

# escribo la orden que crea la tabla de convocatorias procesadas si no existe
_SCHEMA = """
CREATE TABLE IF NOT EXISTS procesados (
    id_expediente TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    fecha_ultima_publicacion TEXT,
    procesado_en TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# defino los tres estados posibles de una convocatoria al mirarla
EstadoConvocatoria = Literal["nueva", "modificada", "vista"]


# marco esta función como un context manager para usarla con "with"
@contextmanager
def get_connection(db_path: str) -> Iterator[sqlite3.Connection]:
    # abro la conexión con el fichero de base de datos
    conn = sqlite3.connect(db_path)
    # intento usar la conexión y me aseguro de cerrarla al final
    try:
        # creo la tabla si todavía no existía
        conn.execute(_SCHEMA)
        # confirmo (guardo) ese cambio
        conn.commit()
        # entrego la conexión a quien la pidió con el "with"
        yield conn
    # pase lo que pase, cierro la conexión al terminar
    finally:
        conn.close()


# miro en qué estado está una convocatoria: nueva, modificada o ya vista
def estado_convocatoria(
    conn: sqlite3.Connection, id_expediente: str, fecha_ultima_publicacion: str | None
) -> EstadoConvocatoria:
    # busco si ya tengo guardado ese expediente y su última publicación
    cur = conn.execute(
        "SELECT fecha_ultima_publicacion FROM procesados WHERE id_expediente = ?",
        (id_expediente,),
    )
    # cojo la fila encontrada (o None si no existe)
    fila = cur.fetchone()
    # si no existe, es una convocatoria nueva
    if fila is None:
        return "nueva"
    # saco la fecha de última publicación que tenía guardada
    fecha_guardada = fila[0]
    # si la última publicación ha cambiado, es una modificación
    if fecha_ultima_publicacion and fecha_ultima_publicacion != fecha_guardada:
        return "modificada"
    # en cualquier otro caso, ya la había visto y no ha cambiado
    return "vista"


# guardo o actualizo una convocatoria como procesada
def registrar(
    conn: sqlite3.Connection,
    id_expediente: str,
    url: str,
    fecha_ultima_publicacion: str | None,
) -> None:
    # inserto la fila; si ya existía ese id, actualizo url y última publicación
    conn.execute(
        """
        INSERT INTO procesados (id_expediente, url, fecha_ultima_publicacion)
        VALUES (?, ?, ?)
        ON CONFLICT(id_expediente) DO UPDATE SET
            url = excluded.url,
            fecha_ultima_publicacion = excluded.fecha_ultima_publicacion,
            procesado_en = datetime('now')
        """,
        (id_expediente, url, fecha_ultima_publicacion),
    )
    # confirmo (guardo) el cambio en el fichero
    conn.commit()
