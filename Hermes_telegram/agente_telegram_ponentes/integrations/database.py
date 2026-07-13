"""Adaptador PostgreSQL/Neon para el agente Telegram Ponentes.

Los datos operativos se leen exclusivamente de PostgreSQL/Neon. La relación
Telegram -> id_ponente se mantiene temporalmente en
``data/estado/mapeo_telegram_ponentes.json`` porque el esquema actual no tiene
una tabla específica para dicha vinculación.
"""

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from psycopg2 import connect
from psycopg2.extras import RealDictCursor

from config.settings import (
    DATABASE_URL,
    DB_CONNECT_TIMEOUT_SECONDS,
    EVENT_ACTIVE_STATES,
    TIMEZONE,
)
from config.fuentes import DATA_PATH

MAPEO_TELEGRAM_PATH = DATA_PATH / "estado" / "mapeo_telegram_ponentes.json"
ZONA_LOCAL = ZoneInfo(TIMEZONE)


def _normalizar_id(valor: Any) -> str:
    return str(valor).strip() if valor is not None else ""


def _normalizar_recurso(valor: Any) -> str | None:
    """Mantiene URLs y prioriza los PDF portables incluidos en la entrega."""
    recurso = _normalizar_id(valor)
    if not recurso:
        return None

    if recurso.startswith(("http://", "https://")):
        return recurso

    # La BD de prueba todavía puede contener rutas absolutas a antiguos TXT.
    # Se busca primero el PDF equivalente empaquetado con el proyecto.
    nombre_archivo = recurso.replace("\\", "/").rsplit("/", 1)[-1]
    nombre = Path(nombre_archivo)
    pdf_portable = DATA_PATH / "documentos_prueba" / f"{nombre.stem}.pdf"
    if pdf_portable.exists():
        return str(pdf_portable.resolve())

    ruta_portable = DATA_PATH / "documentos_prueba" / nombre_archivo
    if ruta_portable.exists():
        return str(ruta_portable.resolve())

    ruta_original = Path(recurso)
    if ruta_original.exists():
        return str(ruta_original.resolve())

    return recurso


def _conectar():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL no configurado en .env")
    return connect(DATABASE_URL, connect_timeout=DB_CONNECT_TIMEOUT_SECONDS)


def _a_hora_local(valor: Any) -> datetime | None:
    if not isinstance(valor, datetime):
        return None
    if valor.tzinfo is None:
        return valor.replace(tzinfo=ZONA_LOCAL)
    return valor.astimezone(ZONA_LOCAL)


def _fmt_fecha_hora(valor: Any) -> str | None:
    if not valor:
        return None
    fecha = _a_hora_local(valor)
    return fecha.strftime("%d/%m/%Y %H:%M") if fecha else str(valor)


def _fmt_fecha(valor: Any) -> str | None:
    if not valor:
        return None
    fecha = _a_hora_local(valor)
    return fecha.strftime("%d/%m/%Y") if fecha else str(valor)


def _fmt_hora(valor: Any) -> str | None:
    if not valor:
        return None
    fecha = _a_hora_local(valor)
    return fecha.strftime("%H:%M") if fecha else str(valor)


def _texto_sin_acentos(valor: str | None) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or "").lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def _clasificar_detalle(descripcion: str) -> tuple[str, str]:
    """Devuelve ``(categoria, tipo_servicio)`` para una línea logística."""
    texto = _texto_sin_acentos(descripcion)

    if "taxi" in texto:
        return "taxi", "taxi"
    if any(p in texto for p in ["coche de alquiler", "coche alquiler", "rent a car", "vehiculo de alquiler"]):
        return "transporte_principal", "coche_alquiler"
    if any(p in texto for p in ["autobus", "bus ", " bus", "minibus", "lanzadera", "shuttle"]):
        return "transporte_principal", "bus"
    if any(p in texto for p in ["vuelo", "avion", "aeropuerto"]):
        return "transporte_principal", "vuelo"
    if any(p in texto for p in ["tren", "estacion", "ave "]):
        return "transporte_principal", "tren"
    if any(p in texto for p in ["ferry", "barco"]):
        return "transporte_principal", "ferry"
    if any(p in texto for p in ["desayuno", "comida", "almuerzo", "cena", "restaurante", "catering"]):
        return "servicio_adicional", "comida"
    if any(p in texto for p in ["parking", "aparcamiento", "garaje"]):
        return "servicio_adicional", "parking"
    if any(p in texto for p in ["accesibilidad", "accesible", "silla de ruedas", "movilidad reducida"]):
        return "servicio_adicional", "accesibilidad"
    if any(p in texto for p in ["wifi", "internet"]):
        return "servicio_adicional", "wifi"
    if any(p in texto for p in ["hotel", "check-in", "check in", "check-out", "check out"]):
        return "hotel", "hotel"

    return "otro", "otro"


def _parsear_detalles(texto_fuente: str | None, fuente: str) -> list[dict]:
    """Parsea líneas conservando el orden original, sin reordenarlas por hora."""
    if not texto_fuente:
        return []

    detalles = []
    for orden, linea in enumerate(str(texto_fuente).splitlines(), start=1):
        texto = linea.strip(" -\t")
        if not texto:
            continue

        match = re.match(r"^(\d{1,2}:\d{2})\s*[-–—·:]?\s*(.+)$", texto)
        if match:
            hora, descripcion = match.groups()
        else:
            hora, descripcion = None, texto

        categoria, tipo_servicio = _clasificar_detalle(descripcion)
        detalles.append(
            {
                "orden": orden,
                "hora": hora,
                "descripcion": descripcion.strip(),
                "categoria": categoria,
                "tipo_servicio": tipo_servicio,
                "fuente": fuente,
            }
        )
    return detalles


def _deduplicar_detalles(detalles: list[dict]) -> list[dict]:
    salida = []
    vistos = set()
    for item in detalles:
        clave = (_texto_sin_acentos(item.get("descripcion")), item.get("hora"))
        if clave in vistos:
            continue
        vistos.add(clave)
        salida.append(item)
    return salida


def _leer_mapeo_telegram() -> dict[str, str]:
    if not MAPEO_TELEGRAM_PATH.exists():
        raise RuntimeError(f"No existe el archivo de vinculación Telegram: {MAPEO_TELEGRAM_PATH}")

    try:
        contenido = json.loads(MAPEO_TELEGRAM_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"El archivo de vinculación Telegram no contiene JSON válido: {MAPEO_TELEGRAM_PATH}"
        ) from exc

    if not isinstance(contenido, dict):
        raise RuntimeError(
            f"El archivo de vinculación Telegram debe contener un objeto JSON: {MAPEO_TELEGRAM_PATH}"
        )

    return {str(k).strip(): str(v).strip() for k, v in contenido.items()}


def obtener_ponente_por_telegram_db(telegram_user_id: str) -> dict | None:
    telegram_user_id = _normalizar_id(telegram_user_id)
    if not telegram_user_id:
        return None

    mapeo = _leer_mapeo_telegram()
    id_ponente = _normalizar_id(mapeo.get(telegram_user_id))
    if not id_ponente:
        print(f"[BD] Telegram user_id sin vinculación en {MAPEO_TELEGRAM_PATH}: {telegram_user_id}")
        return None

    with _conectar() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, nombre_ponente, email, telefono, empresa, cargo,
                       sector, foto_link, cv_link
                FROM public.ponentes
                WHERE id = %s
                LIMIT 1;
                """,
                (id_ponente,),
            )
            row = cur.fetchone()

    if not row:
        print(f"[BD] El UUID vinculado a Telegram no existe en public.ponentes: {id_ponente}")
        return None

    return {
        "id_ponente": _normalizar_id(row["id"]),
        "nombre": row.get("nombre_ponente"),
        "email": row.get("email"),
        "telefono": row.get("telefono"),
        "empresa": row.get("empresa"),
        "cargo": row.get("cargo"),
        "sector": row.get("sector"),
        "foto_link": _normalizar_recurso(row.get("foto_link")),
        "cv_link": _normalizar_recurso(row.get("cv_link")),
        "telegram_user_id": telegram_user_id,
        "fuente": "database_direct",
    }


def obtener_eventos_activos_ponente_db(id_ponente: str) -> list[dict]:
    estados_activos = [estado.lower() for estado in EVENT_ACTIVE_STATES if estado.strip()]
    if not estados_activos:
        raise RuntimeError("EVENT_ACTIVE_STATES está vacío en .env")

    with _conectar() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    e.id AS id_evento,
                    e.nombre_evento,
                    e.ciudad,
                    e.lugar_confirmado,
                    e.fecha_inicio,
                    e.fecha_fin,
                    e.tipo_evento,
                    e.id_estado,
                    est.descripcion AS estado_evento,
                    p.id AS id_ponencia,
                    p.ponente_estado,
                    p.tipo_ponencia,
                    p.horario_ponencia
                FROM public.ponencias p
                JOIN public.eventos e ON e.id = p.id_evento
                JOIN public.estados est ON est.id = e.id_estado
                WHERE p.id_ponente = %s
                  AND LOWER(TRIM(COALESCE(est.descripcion, ''))) = ANY(%s)
                ORDER BY e.fecha_inicio ASC;
                """,
                (id_ponente, estados_activos),
            )
            rows = cur.fetchall()

    return [
        {
            "id_evento": _normalizar_id(row["id_evento"]),
            "id_ponente": _normalizar_id(id_ponente),
            "id_ponencia": _normalizar_id(row["id_ponencia"]),
            "id_estado": _normalizar_id(row.get("id_estado")),
            "nombre_evento": row.get("nombre_evento"),
            "ciudad": row.get("ciudad"),
            "lugar_confirmado": row.get("lugar_confirmado"),
            "fecha": _fmt_fecha(row.get("fecha_inicio")),
            "fecha_inicio": _fmt_fecha_hora(row.get("fecha_inicio")),
            "fecha_fin": _fmt_fecha_hora(row.get("fecha_fin")),
            "tipo_evento": row.get("tipo_evento"),
            "tipo_ponencia": row.get("tipo_ponencia"),
            "horario_ponencia": _fmt_fecha_hora(row.get("horario_ponencia")),
            "estado": row.get("estado_evento"),
            "fuente": "database_direct",
        }
        for row in rows
    ]


def obtener_info_ponente_evento_db(id_ponente: str, id_evento: str) -> dict | None:
    with _conectar() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    e.id AS id_evento,
                    e.nombre_evento,
                    e.ciudad,
                    e.lugar_confirmado,
                    e.fecha_inicio,
                    e.fecha_fin,
                    e.tipo_evento,
                    e.nota AS nota_evento,
                    p.id AS id_ponencia,
                    p.nombre_hotel,
                    p.localizacion_hotel,
                    p.checkin_horario,
                    p.horario_ponencia,
                    p.horario_ida_transporte,
                    p.horario_vuelta_transporte,
                    p.nota_transporte,
                    p.presentacion_link,
                    p.billete_ida_link,
                    p.billete_vuelta_link,
                    p.tipo_ponencia,
                    p.ponente_estado,
                    pon.id AS id_ponente,
                    pon.nombre_ponente,
                    pon.email,
                    pon.telefono,
                    pon.cv_link,
                    pon.foto_link,
                    pon.empresa,
                    pon.cargo
                FROM public.ponencias p
                JOIN public.eventos e ON e.id = p.id_evento
                JOIN public.ponentes pon ON p.id_ponente = pon.id
                WHERE pon.id = %s
                  AND e.id = %s
                LIMIT 1;
                """,
                (id_ponente, id_evento),
            )
            row = cur.fetchone()

    if not row:
        return None

    timeline_transporte = _parsear_detalles(row.get("nota_transporte"), "nota_transporte")
    detalles_evento = _parsear_detalles(row.get("nota_evento"), "nota_evento")
    todos_detalles = _deduplicar_detalles(timeline_transporte + detalles_evento)

    transportes = [item for item in timeline_transporte if item["categoria"] == "transporte_principal"]
    taxis = [item for item in timeline_transporte if item["categoria"] == "taxi"]
    servicios_adicionales = [
        item
        for item in todos_detalles
        if item.get("tipo_servicio") in {
            "comida",
            "coche_alquiler",
            "bus",
            "parking",
            "accesibilidad",
            "wifi",
        }
    ]

    documentos_pendientes = []
    if not row.get("presentacion_link"):
        documentos_pendientes.append("presentación")
    if not row.get("billete_ida_link"):
        documentos_pendientes.append("billete de ida")
    if not row.get("billete_vuelta_link"):
        documentos_pendientes.append("billete de vuelta")

    transporte_ida = transportes[0] if transportes else None
    transporte_vuelta = transportes[-1] if len(transportes) >= 2 else None
    traslados_hotel = [
        item for item in taxis if "hotel" in _texto_sin_acentos(item.get("descripcion"))
    ]

    return {
        "id_evento": _normalizar_id(row["id_evento"]),
        "id_ponente": _normalizar_id(row["id_ponente"]),
        "id_ponencia": _normalizar_id(row["id_ponencia"]),
        "nombre_evento": row.get("nombre_evento"),
        "ciudad": row.get("ciudad"),
        "lugar": row.get("lugar_confirmado"),
        "sala": None,
        "fecha_evento": _fmt_fecha(row.get("fecha_inicio")),
        "fecha_inicio": _fmt_fecha_hora(row.get("fecha_inicio")),
        "fecha_fin": _fmt_fecha_hora(row.get("fecha_fin")),
        "tipo_evento": row.get("tipo_evento"),
        "tipo_ponencia": row.get("tipo_ponencia"),
        "nota_evento": row.get("nota_evento"),
        "hotel": row.get("nombre_hotel"),
        "direccion_hotel": row.get("localizacion_hotel"),
        "checkin_horario": _fmt_fecha_hora(row.get("checkin_horario")),
        "horario_ponencia": _fmt_fecha_hora(row.get("horario_ponencia")),
        "hora_ponencia": _fmt_hora(row.get("horario_ponencia")),
        "horario_ida_transporte": _fmt_fecha_hora(row.get("horario_ida_transporte")),
        "horario_vuelta_transporte": _fmt_fecha_hora(row.get("horario_vuelta_transporte")),
        "nota_transporte": row.get("nota_transporte"),
        "transportes_principales": transportes,
        "transporte_ida": transporte_ida,
        "transporte_vuelta": transporte_vuelta,
        "traslados_taxi": taxis,
        "traslados_hotel": traslados_hotel,
        "servicios_adicionales": servicios_adicionales,
        "timeline_viaje": timeline_transporte,
        # Compatibilidad con funciones anteriores, evitando usar todo el resumen como «vuelo».
        "viaje": row.get("nota_transporte"),
        "vuelo": transporte_ida.get("descripcion") if transporte_ida else None,
        "taxi": "\n".join(
            f"{item.get('hora') + ' · ' if item.get('hora') else ''}{item.get('descripcion')}"
            for item in taxis
        ) or None,
        "taxi_llegada": taxis[0].get("descripcion") if taxis else None,
        "taxi_salida": taxis[-1].get("descripcion") if len(taxis) >= 2 else None,
        "documentos_pendientes": documentos_pendientes,
        "presentacion_link": _normalizar_recurso(row.get("presentacion_link")),
        "billete_ida_link": _normalizar_recurso(row.get("billete_ida_link")),
        "billete_vuelta_link": _normalizar_recurso(row.get("billete_vuelta_link")),
        "cv_link": _normalizar_recurso(row.get("cv_link")),
        "foto_link": _normalizar_recurso(row.get("foto_link")),
        "nombre_ponente": row.get("nombre_ponente"),
        "email": row.get("email"),
        "telefono": row.get("telefono"),
        "empresa": row.get("empresa"),
        "cargo": row.get("cargo"),
        "fuente": "database_direct",
    }


def obtener_documentos_ponente_evento_db(
    id_ponente: str,
    id_evento: str,
    tipo_documento: str | None = None,
    info: dict | None = None,
) -> list[dict]:
    # Si el agente ya consultó la ficha logística, se reutiliza para evitar
    # otra conexión y otra consulta a Neon en la misma interacción.
    info = info or obtener_info_ponente_evento_db(id_ponente, id_evento)
    if not info:
        return []

    candidatos = [
        ("presentacion", "Presentación", info.get("presentacion_link"), "Presentación del ponente"),
        ("billete_ida", "Billete de ida", info.get("billete_ida_link"), "Billete de ida"),
        ("billete_vuelta", "Billete de vuelta", info.get("billete_vuelta_link"), "Billete de vuelta"),
        ("cv", "CV del ponente", info.get("cv_link"), "CV del ponente"),
        ("foto", "Foto del ponente", info.get("foto_link"), "Foto del ponente"),
    ]

    documentos = []
    for tipo, nombre, url, descripcion in candidatos:
        if not url:
            continue
        if tipo_documento and tipo_documento != tipo:
            if not (
                tipo_documento in {"billete_vuelo", "billete_tren", "viaje"}
                and tipo in {"billete_ida", "billete_vuelta"}
            ):
                continue

        nombre_archivo = Path(str(url)).name if not str(url).startswith(("http://", "https://")) else f"{tipo}_{info.get('nombre_evento', 'evento')}"
        documentos.append(
            {
                "id_ponente": _normalizar_id(id_ponente),
                "id_evento": _normalizar_id(id_evento),
                "tipo_documento": tipo,
                "nombre_archivo": nombre_archivo,
                "titulo_boton": nombre,
                "url": url,
                "descripcion": descripcion,
                "fuente": "database_direct",
            }
        )

    return documentos
