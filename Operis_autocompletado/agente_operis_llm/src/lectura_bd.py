"""
lectura_bd.py — traduce el esquema real de la BD (Neon Postgres, ver
Agente_04_Copilot_Raul/data/rag/documentos/esquema_bd.md) al esquema de
salida de agente_operis (evento/cliente/ponentes/nota_bene), para poder
usar el estado actual de un evento como `contexto.historial_anterior`
sin depender de que un backend externo lo guarde y lo pase.

Solo lectura, igual que integrations/bd_backend.py (del que depende).
Import perezoso: si `psycopg` no está instalado o DATABASE_URL no está
configurada, las funciones de aquí devuelven None/False en vez de
reventar -- el resto del agente sigue funcionando sin BD (ver
src/nucleo.py, que solo llama a esto si bd_disponible() es True).

LIMITACIÓN REAL DE LA BD (no de este código, ver config/permisos.py):
cada evento enlaza como mucho con UNA ponencia/ponente. La lista
`ponentes` que construye este módulo tendrá 0 o 1 elemento, nunca más,
aunque el esquema de salida de Operis modele `ponentes` como lista.
"""

import datetime

from config.permisos import TABLAS_PERMITIDAS
from integrations.bd_backend import bd_disponible, obtener_por_id, BdBackendError
from src.schemas import crear_estructura_vacia_historico


def _fecha_iso_a_visible(fecha_iso):
    """AAAA-MM-DD (lo que devuelve la BD) -> DD/MM/AAAA (formato de salida de Operis)."""
    if not fecha_iso:
        return ""
    try:
        return datetime.date.fromisoformat(str(fecha_iso)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(fecha_iso)


def evento_existe(id_evento) -> bool:
    """
    True si `id_evento` existe en la tabla `eventos` de la BD real.
    Si la BD no está disponible (sin DATABASE_URL, o sin psycopg
    instalado), devuelve False -- quien llama debe tratar eso como
    "no se pudo verificar", no como "no existe" (ver src/validaciones.py).
    """
    if not bd_disponible():
        return False
    try:
        return obtener_por_id("eventos", id_evento) is not None
    except BdBackendError:
        return False


def _mapear_evento_actual(fila_evento: dict) -> dict:
    """eventos -> bloque `evento` de Operis; el estado vive en eventos.estado."""
    estado_texto = str(fila_evento.get("estado") or "").strip()

    return {
        "nombre_evento": fila_evento.get("nombre_evento", "") or "",
        "ciudad": fila_evento.get("ciudad", "") or "",
        "lugar_confirmado": fila_evento.get("lugar_confirmado", "") or "",
        "fecha_inicio": _fecha_iso_a_visible(fila_evento.get("fecha_inicio")),
        "fecha_fin": _fecha_iso_a_visible(fila_evento.get("fecha_fin")),
        "numero_personas": str(fila_evento.get("numero_personas") or ""),
        "tipo_evento": fila_evento.get("tipo_evento", "") or "",
        "estado": estado_texto,
        "nota": fila_evento.get("nota", "") or "",
    }


def _mapear_cliente_actual(id_cliente) -> dict:
    """clientes -> bloque `cliente` de Operis. cliente_existente=True: viene de la BD real."""
    cliente = {
        "cliente": "", "empresa": "", "email": "", "telefono": "", "sector": "", "ciudad": "",
        "personas_contacto": [], "cliente_existente": False, "nota_cliente": "",
    }
    if not id_cliente:
        return cliente
    fila = obtener_por_id("clientes", id_cliente)
    if not fila:
        return cliente
    cliente.update({
        "cliente": fila.get("cliente", "") or "",
        "empresa": fila.get("empresa", "") or "",
        "email": fila.get("email", "") or "",
        "telefono": fila.get("telefono", "") or "",
        "sector": fila.get("sector", "") or "",
        "ciudad": fila.get("ciudad", "") or "",
        "cliente_existente": True,
    })
    return cliente


def _mapear_ponentes_actual(id_ponencia) -> list:
    """
    ponencias + ponentes -> lista `ponentes` de Operis (0 o 1 elemento,
    ver limitación real de la BD en la cabecera del módulo).
    """
    if not id_ponencia:
        return []
    ponencia = obtener_por_id("ponencias", id_ponencia)
    if not ponencia:
        return []

    ponente_datos = {}
    if ponencia.get("id_ponente"):
        fila_ponente = obtener_por_id("ponentes", ponencia["id_ponente"])
        if fila_ponente:
            ponente_datos = fila_ponente

    return [{
        "nombre_ponente": ponente_datos.get("nombre_ponente", "") or "",
        "doc_identificacion": ponente_datos.get("docu_identificacion", "") or "",
        "email": ponente_datos.get("email", "") or "",
        "sector": ponente_datos.get("sector", "") or "",
        "telefono": ponente_datos.get("telefono", "") or "",
        "foto_link": ponente_datos.get("foto_link", "") or "",
        "cv_link": ponente_datos.get("cv_link", "") or "",
        "empresa": ponente_datos.get("empresa", "") or "",
        "cargo": ponente_datos.get("cargo", "") or "",
        "nombre_hotel": ponencia.get("nombre_hotel", "") or "",
        "nota_transporte": ponencia.get("nota_transporte", "") or "",
        "horario_ida_transporte": ponencia.get("horario_ida_transporte", "") or "",
        "horario_vuelta_transporte": ponencia.get("horario_vuelta_transporte", "") or "",
        "localizacion_hotel": ponencia.get("localizacion_hotel", "") or "",
        "horario_ponencia": ponencia.get("horario_ponencia", "") or "",
        "checking_horario": ponencia.get("checkin_horario", "") or "",
        "ponente_estado": ponencia.get("ponente_estado", "") or "",
        "presentacion_link": ponencia.get("presentacion_link", "") or "",
        "billete_ida_link": ponencia.get("billete_ida_link", "") or "",
        "billete_vuelta_link": ponencia.get("billete_vuelta_link", "") or "",
        "tipo_ponencias": ponencia.get("tipo_ponencia", "") or "",
        "nota_ponente": "",
    }]


def _mapear_nota_bene_actual(fila_evento: dict, cliente: dict) -> dict:
    """
    presupuestos (+ salas/espacios para la ubicación) -> bloque
    `nota_bene` de Operis. Es una TRADUCCIÓN, no una copia -- la BD no
    tiene un "nota_bene" propio, así que se reconstruye a partir de las
    columnas más afines de cada tabla.
    """
    nota_bene = {
        "cabecera": {
            "nombre_evento": fila_evento.get("nombre_evento", "") or "",
            "estado_evento": "",
            "fecha_celebracion": "",
            "cliente_principal": cliente.get("cliente", ""),
            "persona_contacto": "",
            "presupuesto_total_estimado": "",
            "ultima_actualizacion": datetime.datetime.now().isoformat(timespec="seconds"),
        },
        "presupuesto_servicios": {
            "ubicacion": {"descripcion": "", "precio_estimado": "", "nota": "", "estado": ""},
            "catering": {"descripcion": "", "precio_estimado": "", "nota": "", "estado": ""},
            "audiovisuales": {"descripcion": "", "precio_estimado": "", "nota": "", "estado": ""},
            "otros": {"descripcion": "", "precio_estimado": "", "nota": "", "estado": ""},
        },
        "informacion_adicional": {
            "notas_generales": "",
            "requerimientos_especiales": "",
            "riesgos_detectados": "",
            "acciones_pendientes": [],
            "dependencias": [],
            "historico_actualizaciones": [],
        },
    }

    fecha_inicio = _fecha_iso_a_visible(fila_evento.get("fecha_inicio"))
    fecha_fin = _fecha_iso_a_visible(fila_evento.get("fecha_fin"))
    if fecha_inicio and fecha_fin:
        nota_bene["cabecera"]["fecha_celebracion"] = (
            fecha_inicio if fecha_inicio == fecha_fin else f"{fecha_inicio}-{fecha_fin}"
        )

    # --- Presupuesto (via eventos.id_presupuesto) ---
    if fila_evento.get("id_presupuesto"):
        presu = obtener_por_id("presupuestos", fila_evento["id_presupuesto"])
        if presu:
            total = presu.get("total")
            nota_bene["cabecera"]["presupuesto_total_estimado"] = f"{total}€" if total else ""
            ps = nota_bene["presupuesto_servicios"]
            ps["ubicacion"]["precio_estimado"] = str(presu.get("precio_ubicacion") or "")
            ps["ubicacion"]["nota"] = presu.get("nota_ubicacion", "") or ""
            ps["catering"]["descripcion"] = presu.get("catering", "") or ""
            ps["catering"]["precio_estimado"] = str(presu.get("precio_catering") or "")
            ps["catering"]["nota"] = presu.get("nota_catering", "") or ""
            ps["audiovisuales"]["descripcion"] = presu.get("audiovisuales", "") or ""
            ps["audiovisuales"]["precio_estimado"] = str(presu.get("precio_audiovisuales") or "")
            ps["audiovisuales"]["nota"] = presu.get("nota_audiovisuales", "") or ""
            ps["otros"]["descripcion"] = presu.get("otros", "") or ""
            ps["otros"]["precio_estimado"] = str(presu.get("precio_otros") or "")
            ps["otros"]["nota"] = presu.get("nota_otros", "") or ""
            nota_bene["informacion_adicional"]["notas_generales"] = presu.get("observaciones", "") or ""

    # --- Ubicación (via eventos.id_sala -> salas.id_espacio -> espacios) ---
    if fila_evento.get("id_sala"):
        sala = obtener_por_id("salas", fila_evento["id_sala"])
        if sala:
            partes_desc = [sala.get("nombre_sala", "")]
            espacio = obtener_por_id("espacios", sala["id_espacio"]) if sala.get("id_espacio") else None
            if espacio:
                partes_desc.append(espacio.get("nombre_espacio", ""))
            descripcion_actual = nota_bene["presupuesto_servicios"]["ubicacion"]["descripcion"]
            nueva_desc = " - ".join(p for p in partes_desc if p)
            if nueva_desc:
                nota_bene["presupuesto_servicios"]["ubicacion"]["descripcion"] = (
                    descripcion_actual + " | " + nueva_desc if descripcion_actual else nueva_desc
                )

    return nota_bene


def construir_historial_desde_bd(id_evento):
    """
    Lee el estado ACTUAL de `id_evento` en la BD real y lo devuelve con
    la forma de `contexto.historial_anterior` (ver
    src/schemas.py::crear_estructura_vacia_historico), con una única
    "versión" que representa "lo que ya hay guardado ahora mismo".

    Sustituye a que un backend externo tenga que guardar y pasar el
    histórico -- si la BD está disponible, es la propia BD la fuente de
    verdad del estado anterior. Si el backend algún día SÍ pasa
    contexto.historial_anterior explícito en el payload, ese tiene
    prioridad (ver src/nucleo.py) y esta función ni se llama.

    Returns:
        dict | None: None si la BD no está disponible, si `id_evento`
            no existe, o si falla la conexión (nunca lanza excepción
            hacia arriba -- un fallo de BD no debe tumbar la extracción,
            solo hace que se procese sin histórico, como si no lo
            hubiera).
    """
    if not bd_disponible():
        return None

    try:
        fila_evento = obtener_por_id("eventos", id_evento)
        if not fila_evento:
            return None

        cliente = _mapear_cliente_actual(fila_evento.get("id_cliente"))
        datos_actuales = {
            "evento": _mapear_evento_actual(fila_evento),
            "cliente": cliente,
            "ponentes": _mapear_ponentes_actual(fila_evento.get("id_ponencia")),
            "nota_bene": _mapear_nota_bene_actual(fila_evento, cliente),
        }
    except BdBackendError:
        return None

    historico = crear_estructura_vacia_historico()
    historico["evento_id"] = str(id_evento)
    historico["versiones"] = [{
        "fecha": datetime.datetime.now().isoformat(timespec="seconds"),
        "archivo": "(estado actual en BD real)",
        "resumen": "Estado leído de la BD real antes de fusionar con el nuevo briefing.",
        "datos": datos_actuales,
    }]
    historico["ultima_actualizacion"] = datetime.datetime.now().isoformat(timespec="seconds")
    return historico


__all__ = ["evento_existe", "construir_historial_desde_bd", "TABLAS_PERMITIDAS"]
