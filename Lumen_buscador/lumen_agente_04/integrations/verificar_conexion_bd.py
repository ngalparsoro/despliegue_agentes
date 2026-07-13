"""
integrations/verificar_conexion_bd.py — Script manual de verificacion de la BD real.

El entorno donde se escribio integrations/db_backend.py no tenia salida de red hacia la BD
(Neon), asi que el esquema asumido (data/rag/documentos/esquema_bd.md) no se pudo confirmar en
vivo. Este script se ejecuta UNA VEZ, a mano, en un entorno con acceso real a internet, para:

1. Confirmar que la conexion funciona con las credenciales de .env (DATABASE_URL).
2. Listar las tablas y columnas reales de la BD.
3. Compararlas contra lo que Lumen espera (esquema_bd.md) y avisar de cualquier diferencia
   (tabla que falta, columna que falta, columna de mas) para corregir el codigo si hace falta.

Uso:
    cd lumen_agente_04
    python integrations/verificar_conexion_bd.py

No escribe nada en la BD (misma conexion de solo lectura que usa db_backend.py).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2  # noqa: E402
import psycopg2.extras  # noqa: E402

from config.settings import DATABASE_URL  # noqa: E402

# Lo que Lumen espera segun data/rag/documentos/esquema_bd.md (campos_bbdd.md del usuario).
ESQUEMA_ESPERADO = {
    "clientes": {"id", "cliente", "email", "telefono", "empresa", "sector", "ciudad"},
    "eventos": {
        "id", "nombre_evento", "ciudad", "lugar_confirmado", "fecha_inicio", "fecha_fin",
        "numero_personas", "tipo_evento", "nota", "id_presupuesto", "id_cliente", "id_estado",
        "id_sala", "id_ponencia",
    },
    "presupuestos": {
        "id", "estado_presupuesto", "total", "fecha", "nota_ubicacion", "precio_ubicacion",
        "catering", "nota_catering", "precio_catering", "audiovisuales", "nota_audiovisuales",
        "precio_audiovisuales", "otros", "nota_otros", "precio_otros", "observaciones",
    },
    "salas": {"id", "nombre_sala", "tipo_sala", "capacidad_max_sala", "nota_sala", "id_espacio"},
    "espacios": {
        "id", "nombre_espacio", "ciudad", "direccion", "aforo", "nota", "telefono_contacto",
        "nombre_contacto", "email_contacto",
    },
    "ponencias": {
        "id", "nombre_hotel", "nota_transporte", "horario_ida_transporte",
        "horario_vuelta_transporte", "localizacion_hotel", "horario_ponencia", "checkin_horario",
        "ponente_estado", "presentacion_link", "billete_ida_link", "billete_vuelta_link",
        "tipo_ponencia", "id_ponente",
    },
    "ponentes": {
        "id", "nombre_ponente", "docu_identificacion", "email", "sector", "telefono",
        "foto_link", "cv_link", "empresa", "cargo",
    },
    "estados": {"id", "descripcion"},
}


def main():
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL no esta configurada en .env")
        sys.exit(1)

    print("Conectando a la BD real (solo lectura)...")
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
    conn.set_session(readonly=True, autocommit=True)
    print("Conexion OK.\n")

    cur = conn.cursor()
    cur.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' "
        "ORDER BY table_name;"
    )
    tablas_reales = {fila[0] for fila in cur.fetchall()}
    print("Tablas encontradas en la BD:", sorted(tablas_reales))
    print()

    hay_diferencias = False

    for tabla, columnas_esperadas in ESQUEMA_ESPERADO.items():
        if tabla not in tablas_reales:
            print(f"[FALTA TABLA] '{tabla}' no existe en la BD real.")
            hay_diferencias = True
            continue

        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s;",
            (tabla,),
        )
        columnas_reales = {fila[0] for fila in cur.fetchall()}

        faltan = columnas_esperadas - columnas_reales
        de_mas = columnas_reales - columnas_esperadas

        if faltan or de_mas:
            hay_diferencias = True
            print(f"[DIFERENCIA] tabla '{tabla}':")
            if faltan:
                print(f"   Lumen espera y NO estan en la BD real: {sorted(faltan)}")
            if de_mas:
                print(f"   Existen en la BD real y Lumen no las conoce: {sorted(de_mas)}")
        else:
            print(f"[OK] tabla '{tabla}' coincide exactamente con lo esperado.")

    tabla_usuarios = "usuarios"
    if tabla_usuarios in tablas_reales:
        print(f"\n[INFO] la tabla '{tabla_usuarios}' existe en la BD real, tal y como se "
              "esperaba - confirma que sigue bloqueada en config/permisos.py (TABLAS_EXCLUIDAS).")

    cur.close()
    conn.close()

    print()
    if hay_diferencias:
        print("Hay diferencias entre el esquema esperado y la BD real - revisa "
              "integrations/db_backend.py y data/rag/documentos/esquema_bd.md antes de dar "
              "esto por probado.")
        sys.exit(1)
    else:
        print("El esquema real coincide con lo que Lumen espera. Todo listo.")


if __name__ == "__main__":
    main()
