"""Memoria SQLite mínima del agente."""

import json
import sqlite3
from datetime import datetime

from src.parametros import DATABASE_PATH


ESTADO_PENDIENTE_LECTURA = "pendiente_marcar_leido"


def conectar():
    """Abre la base de datos local."""

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    return sqlite3.connect(
        DATABASE_PATH
    )


def inicializar_memoria():
    """Crea la tabla necesaria sin borrar datos."""

    conexion = conectar()

    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS correos (
            message_id TEXT PRIMARY KEY,
            fecha_proceso TEXT NOT NULL,
            categoria TEXT NOT NULL,
            confianza REAL,
            accion TEXT,
            estado_gmail TEXT,
            draft_id TEXT,
            requiere_revision INTEGER,
            error TEXT,
            resultado TEXT
        )
        """
    )

    conexion.commit()
    conexion.close()


def obtener_ids_procesados():
    """Devuelve correos que no necesitan reintento."""

    inicializar_memoria()
    conexion = conectar()

    filas = conexion.execute(
        """
        SELECT message_id
        FROM correos
        WHERE estado_gmail != ?
        """,
        (
            ESTADO_PENDIENTE_LECTURA,
        ),
    ).fetchall()

    conexion.close()

    return [
        fila[0]
        for fila in filas
    ]


def obtener_registro_correo(
    message_id,
):
    """Recupera el registro guardado de un correo."""

    inicializar_memoria()
    conexion = conectar()

    fila = conexion.execute(
        """
        SELECT categoria, confianza, accion, estado_gmail,
               draft_id, requiere_revision, error, resultado
        FROM correos
        WHERE message_id = ?
        """,
        (
            message_id,
        ),
    ).fetchone()

    conexion.close()

    if not fila:
        return None

    try:
        resultado = json.loads(
            fila[7]
            or "{}"
        )
    except json.JSONDecodeError:
        resultado = {}

    return {
        "categoria": fila[0],
        "confianza": fila[1],
        "accion": fila[2],
        "estado_gmail": fila[3],
        "draft_id": fila[4],
        "requiere_revision": bool(
            fila[5]
        ),
        "error": fila[6],
        "resultado": resultado,
    }


def registrar_correo(
    message_id,
    categoria,
    confianza,
    accion,
    estado_gmail,
    draft_id="",
    requiere_revision=False,
    error="",
    resultado=None,
):
    """Guarda el resultado final o parcial de un correo."""

    inicializar_memoria()
    conexion = conectar()

    conexion.execute(
        """
        INSERT OR REPLACE INTO correos (
            message_id,
            fecha_proceso,
            categoria,
            confianza,
            accion,
            estado_gmail,
            draft_id,
            requiere_revision,
            error,
            resultado
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            message_id,
            datetime.now().isoformat(
                timespec="seconds",
            ),
            categoria,
            confianza,
            accion,
            estado_gmail,
            draft_id,
            int(
                bool(
                    requiere_revision
                )
            ),
            error,
            json.dumps(
                resultado or {},
                ensure_ascii=False,
                default=str,
            ),
        ),
    )

    conexion.commit()
    conexion.close()

    return {
        "ok": True,
        "message_id": message_id,
        "categoria": categoria,
        "accion": accion,
        "estado_gmail": estado_gmail,
        "draft_id": draft_id,
        "requiere_revision": bool(
            requiere_revision
        ),
    }
