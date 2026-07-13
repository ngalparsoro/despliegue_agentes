import os
import logging
import psycopg
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
logger = logging.getLogger("backend_agentes.database")

# Mapeo estático para simulación de telegram_user_id si la columna no existe en la BBDD.
# Relaciona telegram_user_id con el email o id de los ponentes reales de Neon.
MAPEO_TELEGRAM_DEMO = {
    "8907670673": {
        "email": "juan.jesus.garcia@mitumi.test",
        "nombre_ponente": "Juan Jesús García",
        "id": "00000000-0000-0000-0000-000000000301"
    },
    "222222": {
        "email": "l.martin@energia.es",
        "nombre_ponente": "Luis Martín",
        "id": "fd1228b8-5ccc-4b55-aba7-778f2a1e7106"
    }
}

def get_connection():
    if not DATABASE_URL:
        raise ValueError("La variable de entorno DATABASE_URL no está configurada")
    return psycopg.connect(DATABASE_URL)

def verificar_columna_telegram():
    """
    Verifica si existe la columna telegram_user_id en la tabla ponentes.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name = 'ponentes' AND column_name = 'telegram_user_id'
                """)
                return cur.fetchone() is not None
    except Exception as e:
        logger.error(f"Error al verificar columna telegram_user_id: {e}")
        return False

def obtener_ponente_por_telegram(telegram_user_id: str) -> dict | None:
    """
    Recupera la información del ponente buscando por telegram_user_id.
    Si la columna no existe en la BBDD, realiza un fallback al mapa de demos estático.
    """
    telegram_user_id = str(telegram_user_id).strip()
    columna_existe = verificar_columna_telegram()
    
    ponente_data = None
    
    if columna_existe:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, nombre_ponente, docu_identificacion, email, sector, telefono, foto_link, cv_link, empresa, cargo
                        FROM ponentes
                        WHERE telegram_user_id = %s
                        LIMIT 1
                    """, (telegram_user_id,))
                    row = cur.fetchone()
                    if row:
                        ponente_data = {
                            "id": str(row[0]),
                            "id_ponente": str(row[0]),
                            "nombre": row[1],
                            "nombre_ponente": row[1],
                            "docu_identificacion": row[2],
                            "email": row[3],
                            "sector": row[4],
                            "telefono": row[5],
                            "telefono_contacto": row[5],
                            "foto_link": row[6],
                            "cv_link": row[7],
                            "empresa": row[8],
                            "cargo": row[9],
                            "telegram_user_id": telegram_user_id
                        }
        except Exception as e:
            logger.error(f"Error al consultar ponente por telegram_user_id: {e}")
            
    # Fallback si no se encontró en base de datos o si la columna no existe
    if not ponente_data and telegram_user_id in MAPEO_TELEGRAM_DEMO:
        demo = MAPEO_TELEGRAM_DEMO[telegram_user_id]
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, nombre_ponente, docu_identificacion, email, sector, telefono, foto_link, cv_link, empresa, cargo
                        FROM ponentes
                        WHERE id = %s OR email = %s OR nombre_ponente = %s
                        LIMIT 1
                    """, (demo["id"], demo["email"], demo["nombre_ponente"]))
                    row = cur.fetchone()
                    if row:
                        ponente_data = {
                            "id": str(row[0]),
                            "id_ponente": str(row[0]),
                            "nombre": row[1],
                            "nombre_ponente": row[1],
                            "docu_identificacion": row[2],
                            "email": row[3],
                            "sector": row[4],
                            "telefono": row[5],
                            "telefono_contacto": row[5],
                            "foto_link": row[6],
                            "cv_link": row[7],
                            "empresa": row[8],
                            "cargo": row[9],
                            "telegram_user_id": telegram_user_id
                        }
        except Exception as e:
            logger.error(f"Error en fallback de ponente por telegram: {e}")

    # Estructura híbrida compatible tanto con el agente de Telegram (raíz) como con el patch (data)
    if ponente_data:
        return {
            "ok": True,
            **ponente_data,
            "data": ponente_data
        }
    return None

def obtener_eventos_activos_ponente(id_ponente: str) -> list:
    """
    Retorna la lista de eventos activos asociados a un ponente.
    Bajo el nuevo esquema, busca en la tabla ponencias las ponencias del id_ponente,
    e interactúa con eventos para obtener el nombre y fecha.
    """
    eventos = []
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Obtenemos las ponencias y eventos asociados
                cur.execute("""
                    SELECT e.id, e.nombre_evento, e.fecha_inicio
                    FROM ponencias po
                    INNER JOIN eventos e ON e.id = po.id_evento
                    WHERE po.id_ponente = %s
                """, (id_ponente,))
                rows = cur.fetchall()
                for row in rows:
                    fecha_str = row[2].strftime("%Y-%m-%d") if hasattr(row[2], 'strftime') else (str(row[2]) if row[2] else "")
                    eventos.append({
                        "id_ponente": id_ponente,
                        "id_evento": str(row[0]),
                        "nombre_evento": row[1],
                        "estado": "activo",  # Por defecto activo si está programado
                        "fecha": fecha_str
                    })
    except Exception as e:
        logger.error(f"Error al obtener eventos activos para ponente {id_ponente}: {e}")
    return eventos

def obtener_info_ponente_evento(id_ponente: str, id_evento: str) -> dict | None:
    """
    Retorna la información logística de un ponente para un evento específico.
    Los datos se extraen de la tabla ponencias y la tabla eventos de Neon.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        po.nombre_hotel,
                        po.localizacion_hotel,
                        po.nota_transporte,
                        po.horario_ida_transporte,
                        po.horario_vuelta_transporte,
                        po.horario_ponencia,
                        po.checkin_horario,
                        po.ponente_estado,
                        po.presentacion_link,
                        po.billete_ida_link,
                        po.billete_vuelta_link,
                        po.tipo_ponencia,
                        e.nombre_evento,
                        e.lugar_confirmado,
                        e.fecha_inicio
                    FROM ponencias po
                    INNER JOIN eventos e ON e.id = po.id_evento
                    WHERE po.id_ponente = %s AND po.id_evento = %s
                    LIMIT 1
                """, (id_ponente, id_evento))
                row = cur.fetchone()
                if row:
                    # Mapeo de campos a formato esperado por el agente de Telegram (con protección de tipos)
                    horario_ida = row[3].strftime("%Y-%m-%d %H:%M") if hasattr(row[3], 'strftime') else (str(row[3]) if row[3] else "Pendiente de confirmar")
                    horario_vuelta = row[4].strftime("%Y-%m-%d %H:%M") if hasattr(row[4], 'strftime') else (str(row[4]) if row[4] else "Pendiente de confirmar")
                    horario_ponencia = row[5].strftime("%H:%M") if hasattr(row[5], 'strftime') else (str(row[5]) if row[5] else "Pendiente de confirmar")
                    checkin = row[6].strftime("%Y-%m-%d %H:%M") if hasattr(row[6], 'strftime') else (str(row[6]) if row[6] else "Pendiente de confirmar")
                    
                    viaje = f"Transporte: {row[2]}. Ida: {horario_ida}. Vuelta: {horario_vuelta}." if row[2] else "Pendiente de confirmación"
                    vuelo_info = f"Ida: {horario_ida}. Vuelta: {horario_vuelta}." if ("vuelo" in str(row[2]).lower() or "billete" in str(row[2]).lower()) else None
                    
                    # Documentos pendientes
                    docs_pendientes = []
                    if not row[8]: # presentacion_link
                        docs_pendientes.append("presentación final")
                    
                    return {
                        "id_ponente": id_ponente,
                        "id_evento": id_evento,
                        "nombre_evento": row[12],
                        "hotel": row[0] or "Pendiente de confirmación",
                        "direccion_hotel": row[1] or "Pendiente de confirmar",
                        "viaje": viaje,
                        "vuelo": vuelo_info,
                        "taxi_llegada": "Pendiente de confirmar" if not row[2] else "Ver nota de transporte",
                        "taxi_salida": "Pendiente de confirmar" if not row[2] else "Ver nota de transporte",
                        "horario_ponencia": horario_ponencia,
                        "lugar": row[13] or "Pendiente de confirmar",
                        "sala": "Sala principal", # Campo fijo por defecto en base de datos
                        "documentos_pendientes": docs_pendientes
                    }
    except Exception as e:
        logger.error(f"Error al obtener info de ponente {id_ponente} en evento {id_evento}: {e}")
    return None

def obtener_ponentes_evento(id_evento: str) -> list:
    """
    Retorna la lista de ponentes con su logística para un evento específico.
    (Equivalente a GET /eventos/{id}/ponentes propuesto en el patch).
    """
    ponentes = []
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        p.id, p.nombre_ponente, p.email, p.telefono, p.empresa, p.cargo,
                        po.id AS id_ponencia, po.tipo_ponencia, po.ponente_estado, 
                        po.nombre_hotel, po.localizacion_hotel, po.nota_transporte,
                        po.horario_ida_transporte, po.horario_vuelta_transporte, po.horario_ponencia
                    FROM ponencias po
                    INNER JOIN ponentes p ON p.id = po.id_ponente
                    WHERE po.id_evento = %s
                """, (id_evento,))
                rows = cur.fetchall()
                for row in rows:
                    ponentes.append({
                        "id": str(row[0]),
                        "nombre_ponente": row[1],
                        "email": row[2],
                        "telefono": row[3],
                        "empresa": row[4],
                        "cargo": row[5],
                        "ponencia": {
                            "id": str(row[6]),
                            "tipo_ponencia": row[7],
                            "ponente_estado": row[8],
                            "nombre_hotel": row[9],
                            "localizacion_hotel": row[10],
                            "nota_transporte": row[11],
                            "horario_ida_transporte": row[12].isoformat() if hasattr(row[12], 'isoformat') else (str(row[12]) if row[12] else None),
                            "horario_vuelta_transporte": row[13].isoformat() if hasattr(row[13], 'isoformat') else (str(row[13]) if row[13] else None),
                            "horario_ponencia": row[14].isoformat() if hasattr(row[14], 'isoformat') else (str(row[14]) if row[14] else None)
                        }
                    })
    except Exception as e:
        logger.error(f"Error al obtener ponentes del evento {id_evento}: {e}")
    return ponentes
