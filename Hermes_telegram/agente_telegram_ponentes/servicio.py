import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config.settings import (
    TELEGRAM_ENABLED,
    TELEGRAM_CHECK_SECONDS,
    SERVICE_LOOP_SECONDS,
    SHOW_STEPS,
    QUIET_MODE_ENABLED,
    ADMIN_TELEGRAM_CHAT_ID,
    TIMEZONE,
)
from config.permisos import ALLOW_SEND_TELEGRAM, ALLOW_NOTIFY_ADMIN
from src.agente import ejecutar_agente
from src.memoria import (
    guardar_evento_activo_usuario,
    obtener_evento_activo_usuario,
    limpiar_evento_activo_usuario,
    guardar_solicitud_contacto_pendiente,
    obtener_solicitud_contacto_pendiente,
    confirmar_solicitud_contacto,
    limpiar_solicitud_contacto,
)
from src.herramientas import (
    obtener_ponente_por_telegram,
    obtener_eventos_activos_ponente,
    obtener_documentos_ponente_evento,
    registrar_documento_pendiente,
    crear_incidencia,
)
from integrations.telegram import (
    leer_updates,
    enviar_mensaje,
    enviar_mensaje_con_botones,
    enviar_mensaje_con_eventos,
    enviar_mensaje_con_documentos,
    enviar_mensaje_con_contacto,
    enviar_documento,
    responder_callback,
    descargar_archivo,
    update_a_payload,
    extraer_texto_respuesta,
)


AGENT_ROOT = Path(__file__).resolve().parent
BOTON_URGENCIA = "🚨 Urgencia"
BOTON_SELECCIONAR_EVENTO = "📅 Seleccionar evento"
COMANDOS_BIENVENIDA = {"/start", "start", "menu", "/menu", "ayuda", "/ayuda"}

BOTONES_NORMALIZADOS = {
    "✈️ vuelo": {
        "texto": "Consulta de botón: mostrar solo la información de vuelo de ida y vuelta.",
        "intencion": "consulta_viaje",
        "servicio_consultado": "vuelo",
    },
    "✈ vuelo": {
        "texto": "Consulta de botón: mostrar solo la información de vuelo de ida y vuelta.",
        "intencion": "consulta_viaje",
        "servicio_consultado": "vuelo",
    },
    "🏨 hotel": {
        "texto": "Consulta de botón: mostrar solo hotel, dirección, check-in y traslados del hotel.",
        "intencion": "consulta_alojamiento",
        "servicio_consultado": "hotel",
    },
    "🚕 taxi": {
        "texto": "Consulta de botón: mostrar solo taxis y traslados locales con sus horas.",
        "intencion": "consulta_taxi",
        "servicio_consultado": "taxi",
    },
    "📍 lugar evento": {
        "texto": "Consulta de botón: mostrar solo lugar, ciudad, fecha y hora de la ponencia.",
        "intencion": "consulta_lugar",
        "servicio_consultado": "lugar_evento",
    },
    "📍 lugar": {
        "texto": "Consulta de botón: mostrar solo lugar, ciudad, fecha y hora de la ponencia.",
        "intencion": "consulta_lugar",
        "servicio_consultado": "lugar_evento",
    },
    "📄 documentación": {
        "texto": "Consulta de botón: mostrar documentación pendiente y disponible.",
        "intencion": "consulta_documentacion",
        "servicio_consultado": "documentacion",
    },
    "📄 documentacion": {
        "texto": "Consulta de botón: mostrar documentación pendiente y disponible.",
        "intencion": "consulta_documentacion",
        "servicio_consultado": "documentacion",
    },
    "🧭 resumen viaje": {
        "texto": "Consulta de botón: mostrar el resumen cronológico completo del viaje.",
        "intencion": "resumen_viaje",
        "servicio_consultado": "resumen_viaje",
    },
}


def _normalizar_id(valor) -> str:
    return str(valor).strip() if valor is not None else ""


def _normalizar_texto(valor: str | None) -> str:
    return (valor or "").strip().lower()


def obtener_admin_chat_id() -> str:
    return _normalizar_id(ADMIN_TELEGRAM_CHAT_ID)


def construir_mensaje_bienvenida(payload: dict) -> str:
    datos = payload.get("datos", {}) or {}
    telegram_user_id = _normalizar_id(datos.get("telegram_user_id"))
    ponente = obtener_ponente_por_telegram(telegram_user_id)
    if not ponente:
        return (
            "Hola. No encuentro tu usuario de Telegram vinculado a un ponente registrado. "
            "MITUMI debe revisar la vinculación antes de continuar."
        )

    nombre = ponente.get("nombre") or datos.get("nombre_usuario") or "ponente"
    return (
        f"Hola, {nombre} 👋\n\n"
        "Bienvenido al asistente de ponentes de MITUMI. "
        "Puedo ayudarte con tu viaje, alojamiento, traslados, lugar del evento, "
        "documentación y otros servicios logísticos.\n\n"
        "Primero debes seleccionar el evento sobre el que quieres consultar."
    )


def enviar_bienvenida_y_eventos(payload: dict) -> None:
    datos = payload.get("datos", {}) or {}
    chat_id = datos.get("telegram_chat_id")
    telegram_user_id = _normalizar_id(datos.get("telegram_user_id"))
    ponente = obtener_ponente_por_telegram(telegram_user_id)

    if not ponente:
        enviar_mensaje(chat_id, construir_mensaje_bienvenida(payload))
        return

    # /start y /menu inician una sesión nueva: la selección vuelve a ser obligatoria.
    limpiar_evento_activo_usuario(telegram_user_id)
    limpiar_solicitud_contacto(telegram_user_id)

    enviar_mensaje(chat_id, construir_mensaje_bienvenida(payload))
    eventos = obtener_eventos_activos_ponente(ponente.get("id_ponente"))
    if not eventos:
        enviar_mensaje(
            chat_id,
            "No encuentro eventos disponibles asociados a tu perfil. MITUMI debe revisar la asignación.",
        )
        return

    cantidad = len(eventos)
    enviar_mensaje_con_eventos(
        chat_id,
        f"Tienes {cantidad} evento{'s' if cantidad != 1 else ''} disponible{'s' if cantidad != 1 else ''}. "
        "Selecciona uno para continuar:",
        eventos,
    )


def es_comando_bienvenida(texto: str) -> bool:
    return _normalizar_texto(texto) in COMANDOS_BIENVENIDA


def es_boton_urgencia(texto: str) -> bool:
    texto_norm = _normalizar_texto(texto)
    return "🚨" in texto_norm or texto_norm == _normalizar_texto(BOTON_URGENCIA)


def es_boton_seleccionar_evento(texto: str) -> bool:
    texto_norm = _normalizar_texto(texto)
    return "📅" in texto_norm or texto_norm == _normalizar_texto(BOTON_SELECCIONAR_EVENTO)


def normalizar_payload_boton(payload: dict) -> dict:
    datos = payload.get("datos", {}) or {}
    texto = datos.get("texto", "")
    texto_norm = _normalizar_texto(texto)

    configuracion = BOTONES_NORMALIZADOS.get(texto_norm)
    if configuracion:
        payload = dict(payload)
        payload["datos"] = dict(datos)
        payload["datos"]["texto_original_boton"] = texto
        payload["datos"]["texto"] = configuracion["texto"]
        payload["datos"]["intencion_forzada"] = configuracion["intencion"]
        payload["datos"]["servicio_consultado_forzado"] = configuracion.get("servicio_consultado")

    return payload


def seleccionar_evento(payload: dict) -> None:
    datos = payload.get("datos", {}) or {}
    chat_id = datos.get("telegram_chat_id")
    telegram_user_id = _normalizar_id(datos.get("telegram_user_id"))
    ponente = obtener_ponente_por_telegram(telegram_user_id)

    if not ponente:
        enviar_mensaje(chat_id, "No encuentro tu usuario vinculado a un ponente registrado.")
        return

    eventos = obtener_eventos_activos_ponente(ponente.get("id_ponente"))
    if not eventos:
        enviar_mensaje(chat_id, "No encuentro eventos disponibles asociados a tu perfil.")
        return

    limpiar_evento_activo_usuario(telegram_user_id)
    limpiar_solicitud_contacto(telegram_user_id)
    enviar_mensaje_con_eventos(
        chat_id,
        "Selecciona el evento sobre el que quieres consultar información:",
        eventos,
    )


def procesar_callback_evento(payload: dict) -> None:
    datos = payload.get("datos", {}) or {}
    callback_id = datos.get("telegram_callback_query_id")
    callback_data = datos.get("callback_data", "")
    chat_id = datos.get("telegram_chat_id")
    telegram_user_id = _normalizar_id(datos.get("telegram_user_id"))

    partes = callback_data.split("|")
    if len(partes) != 2:
        responder_callback(callback_id, "Selección no válida")
        return

    id_evento = partes[1]
    ponente = obtener_ponente_por_telegram(telegram_user_id)
    if not ponente:
        responder_callback(callback_id, "Ponente no identificado")
        enviar_mensaje_con_botones(chat_id, "No tengo tu usuario vinculado a un ponente registrado.")
        return

    eventos = obtener_eventos_activos_ponente(ponente.get("id_ponente"))
    evento = next((e for e in eventos if str(e.get("id_evento")) == str(id_evento)), None)
    if not evento:
        responder_callback(callback_id, "Evento no disponible")
        enviar_mensaje_con_botones(chat_id, "Ese evento no aparece como activo para tu perfil.")
        return

    guardar_evento_activo_usuario(telegram_user_id, ponente.get("id_ponente"), id_evento, evento.get("nombre_evento"))
    limpiar_solicitud_contacto(telegram_user_id)
    responder_callback(callback_id, "Evento seleccionado")

    lineas = [f"📅 Evento seleccionado: {evento.get('nombre_evento')}."]
    if evento.get("fecha"):
        lineas.append(f"Fecha: {evento.get('fecha')}")
    if evento.get("ciudad"):
        lineas.append(f"Ciudad: {evento.get('ciudad')}")
    lineas.extend([
        "",
        "Ya puedes consultar vuelo, hotel, taxi, lugar del evento, documentación, "
        "resumen del viaje u otros servicios escribiendo tu pregunta.",
    ])
    enviar_mensaje_con_botones(chat_id, "\n".join(lineas))


def procesar_callback_documento(payload: dict) -> None:
    datos = payload.get("datos", {}) or {}
    callback_id = datos.get("telegram_callback_query_id")
    callback_data = datos.get("callback_data", "")
    chat_id = datos.get("telegram_chat_id")
    telegram_user_id = _normalizar_id(datos.get("telegram_user_id"))

    partes = callback_data.split("|")
    if len(partes) != 3:
        responder_callback(callback_id, "Documento no válido")
        return

    _, id_evento, tipo_documento = partes
    ponente = obtener_ponente_por_telegram(telegram_user_id)
    if not ponente:
        responder_callback(callback_id, "Ponente no identificado")
        return

    documentos = obtener_documentos_ponente_evento(ponente.get("id_ponente"), id_evento, tipo_documento)
    if not documentos:
        responder_callback(callback_id, "Documento no disponible")
        enviar_mensaje_con_botones(chat_id, "No encuentro ese documento disponible para descarga. Lo reviso con la organización si lo necesitas.")
        return

    doc = documentos[0]
    ruta_o_url = doc.get("url") or doc.get("ruta_local_absoluta") or doc.get("ruta_local")
    if not ruta_o_url:
        responder_callback(callback_id, "Documento sin ruta")
        enviar_mensaje_con_botones(chat_id, "El documento existe, pero no tengo una ruta de descarga válida. Lo reviso con la organización.")
        return

    responder_callback(callback_id, "Enviando documento")
    caption = doc.get("descripcion") or doc.get("nombre_archivo") or "Documento MITUMI"
    respuesta = enviar_documento(chat_id, ruta_o_url, caption=caption)
    if SHOW_STEPS:
        print(f"[DOCUMENTO] Enviado documento {tipo_documento}: {respuesta.get('ok')}")
        if not respuesta.get("ok"):
            print(f"[DOCUMENTO] Error Telegram: {respuesta}")


def procesar_documento_recibido(payload: dict) -> None:
    """Guarda el documento localmente para revisión; no valida ni actualiza la BD."""
    datos = payload.get("datos", {}) or {}
    chat_id = datos.get("telegram_chat_id")
    telegram_user_id = _normalizar_id(datos.get("telegram_user_id"))
    documento = datos.get("documento") or {}

    ponente = obtener_ponente_por_telegram(telegram_user_id)
    if not ponente:
        enviar_mensaje_con_botones(chat_id, "He recibido el archivo, pero no tengo tu usuario vinculado a un ponente registrado. Aviso a la organización.")
        return

    id_evento = obtener_evento_activo_usuario(telegram_user_id)
    eventos = obtener_eventos_activos_ponente(ponente.get("id_ponente"))

    if id_evento is None:
        enviar_mensaje_con_eventos(chat_id, "He recibido el archivo, pero antes necesito que selecciones el evento al que pertenece:", eventos)
        return

    nombre_archivo = documento.get("file_name") or f"documento_{int(time.time())}.bin"
    ruta_temporal = AGENT_ROOT / "data" / "uploads" / "tmp" / f"{int(time.time())}_{nombre_archivo}"
    descargado = descargar_archivo(documento.get("file_id"), ruta_temporal)

    payload_revision = {
        "tipo_evento": "documento_recibido_ponente",
        "origen": "telegram",
        "id_ponente": ponente.get("id_ponente"),
        "nombre_ponente": ponente.get("nombre"),
        "telegram_user_id": telegram_user_id,
        "id_evento": id_evento,
        "documento": {
            "telegram_file_id": documento.get("file_id"),
            "nombre_archivo": nombre_archivo,
            "mime_type": documento.get("mime_type"),
            "tamano_bytes": documento.get("file_size"),
            "ruta_temporal": str(ruta_temporal) if descargado else None,
            "descargado_localmente": descargado,
        },
        "accion_solicitada": "revisar_y_registrar_documento",
        "requiere_validacion_humana": True,
        "timestamp": datetime.now(ZoneInfo(TIMEZONE)).isoformat(),
    }
    nombre_payload = f"documento_recibido_{datetime.now(ZoneInfo(TIMEZONE)).strftime('%Y%m%d_%H%M%S')}.json"
    ruta = registrar_documento_pendiente(nombre_payload, payload_revision)

    if SHOW_STEPS:
        print(f"[DOCUMENTO] Registro local pendiente guardado: {ruta}")

    enviar_mensaje_con_botones(chat_id, "📎 Documento recibido. Ha quedado pendiente de revisión por el equipo de MITUMI. No queda aprobado todavía.")



def procesar_callback_contacto(payload: dict) -> None:
    datos = payload.get("datos", {}) or {}
    callback_id = datos.get("telegram_callback_query_id")
    callback_data = datos.get("callback_data", "")
    chat_id = datos.get("telegram_chat_id")
    telegram_user_id = _normalizar_id(datos.get("telegram_user_id"))

    partes = callback_data.split("|")
    if len(partes) != 2:
        responder_callback(callback_id, "Solicitud no válida")
        return

    id_evento = partes[1]
    solicitud = obtener_solicitud_contacto_pendiente(telegram_user_id)
    if not solicitud or str(solicitud.get("id_evento")) != str(id_evento):
        responder_callback(callback_id, "La solicitud ha caducado")
        enviar_mensaje_con_botones(
            chat_id,
            "No encuentro la consulta pendiente. Vuelve a escribir qué información necesitas.",
        )
        return

    solicitud = confirmar_solicitud_contacto(telegram_user_id) or solicitud
    motivo = solicitud.get("motivo") or "consulta logística del ponente"
    crear_incidencia({
        "tipo": "solicitud_contacto_ponente",
        "telegram_user_id": telegram_user_id,
        "id_ponente": solicitud.get("id_ponente"),
        "id_evento": id_evento,
        "motivo": motivo,
        "mensaje_original": solicitud.get("mensaje_original"),
    })

    # Las solicitudes normales de contacto se registran, pero no generan
    # mensajes Telegram al administrador. Solo las urgencias pueden hacerlo.
    responder_callback(callback_id, "Solicitud registrada")
    texto = (
        f"He registrado tu solicitud sobre: {motivo}. "
        "MITUMI podrá revisarla por el circuito ordinario. "
        "Si la situación requiere atención inmediata, usa el botón 🚨 Urgencia."
    )
    enviar_mensaje_con_botones(chat_id, texto)


def hay_escalado(resultado: dict) -> bool:
    if resultado.get("requiere_validacion_humana"):
        return True

    datos = resultado.get("datos_detectados", {}) or {}
    if datos.get("urgencia") == "alta":
        return True

    acciones = resultado.get("acciones_propuestas", []) or []
    for accion in acciones:
        if accion.get("tipo") in {"escalar_a_organizacion", "crear_incidencia"}:
            return True

    return False


def es_urgencia_para_admin(resultado: dict) -> bool:
    """Solo una urgencia alta permite avisar por Telegram al administrador."""
    datos = resultado.get("datos_detectados", {}) or {}
    urgencia = str(datos.get("urgencia") or "").strip().lower()
    return urgencia == "alta"


def construir_mensaje_admin(payload: dict, resultado: dict) -> str:
    datos_payload = payload.get("datos", {}) or {}
    datos_resultado = resultado.get("datos_detectados", {}) or {}
    acciones = resultado.get("acciones_propuestas", []) or []
    bloqueos = resultado.get("bloqueos_detectados", []) or []

    telegram_user_id = _normalizar_id(datos_payload.get("telegram_user_id"))
    contacto = obtener_ponente_por_telegram(telegram_user_id) or {}

    nombre = datos_resultado.get("nombre_ponente") or contacto.get("nombre") or datos_payload.get("nombre_usuario") or "No identificado"
    evento = datos_resultado.get("nombre_evento") or "No disponible"
    telefono = contacto.get("telefono") or "No disponible"
    email = contacto.get("email") or "No disponible"
    mensaje_original = datos_payload.get("texto_original_boton") or datos_payload.get("texto", "")
    intencion = datos_resultado.get("intencion", "No clasificada")
    urgencia = datos_resultado.get("urgencia", "No clasificada")
    resumen = resultado.get("resumen", "Sin resumen")

    motivos = []
    for accion in acciones:
        motivo = accion.get("motivo")
        if motivo:
            motivos.append(str(motivo))
    for bloqueo in bloqueos:
        tipo = bloqueo.get("tipo")
        if tipo:
            motivos.append(str(tipo))

    motivo_texto = ", ".join(motivos) if motivos else "Requiere revisión humana"

    return (
        "🚨 MITUMI - URGENCIA DE PONENTE\n\n"
        f"Ponente: {nombre}\n"
        f"Evento: {evento}\n"
        f"Teléfono: {telefono}\n"
        f"Email: {email}\n"
        f"Telegram user_id: {telegram_user_id}\n\n"
        f"Urgencia: {urgencia}\n"
        f"Intención: {intencion}\n"
        f"Motivo: {motivo_texto}\n\n"
        f"Mensaje original:\n{mensaje_original}\n\n"
        f"Resumen agente:\n{resumen}"
    )


def construir_resultado_escalado_directo(motivo: str, urgencia: str = "alta") -> dict:
    return {
        "ok": True,
        "resumen": motivo,
        "datos_detectados": {
            "intencion": "incidencia" if urgencia == "alta" else "contactar_mitumi",
            "urgencia": urgencia,
        },
        "acciones_propuestas": [{"tipo": "escalar_a_organizacion", "motivo": motivo}],
        "bloqueos_detectados": [],
        "borradores_generados": [],
        "requiere_validacion_humana": True,
        "nivel_riesgo": "medio",
        "errores": [],
    }


def enviar_aviso_admin_si_aplica(payload: dict, resultado: dict) -> None:
    # Salida silenciosa para consultas normales. Solo una urgencia alta llega
    # a evaluar configuración, construir el mensaje y llamar a Telegram.
    if not es_urgencia_para_admin(resultado):
        return

    if not ALLOW_NOTIFY_ADMIN:
        if SHOW_STEPS:
            print("[ADMIN] Urgencia detectada, pero ALLOW_NOTIFY_ADMIN=False")
        return

    admin_chat_id = obtener_admin_chat_id()
    if not admin_chat_id:
        if SHOW_STEPS:
            print("[ADMIN] Urgencia detectada, pero ADMIN_TELEGRAM_CHAT_ID no está configurado")
        return

    mensaje_admin = construir_mensaje_admin(payload, resultado)
    respuesta = enviar_mensaje(admin_chat_id, mensaje_admin)

    if SHOW_STEPS:
        print(f"[ADMIN] Aviso enviado al admin: {respuesta.get('ok')}")
        if not respuesta.get("ok"):
            print(f"[ADMIN] Error Telegram: {respuesta}")


def enviar_respuesta_ponente(chat_id, texto: str, resultado: dict) -> None:
    datos = resultado.get("datos_detectados", {}) or {}
    documentos = datos.get("documentos_descarga", []) or []
    ofrecer_contacto = bool(datos.get("ofrecer_contacto_mitumi"))

    eventos_pendientes = None
    for bloqueo in resultado.get("bloqueos_detectados", []) or []:
        if bloqueo.get("tipo") == "evento_activo_no_seleccionado":
            eventos_pendientes = bloqueo.get("eventos") or datos.get("eventos_activos")
            break

    if eventos_pendientes:
        respuesta = enviar_mensaje_con_eventos(chat_id, texto, eventos_pendientes)
    elif ofrecer_contacto:
        guardar_solicitud_contacto_pendiente(
            datos.get("telegram_user_id"),
            datos.get("id_ponente"),
            datos.get("id_evento"),
            datos.get("motivo_contacto") or "consulta logística",
            datos.get("mensaje_original"),
        )
        respuesta = enviar_mensaje_con_contacto(chat_id, texto, datos.get("id_evento"))
    elif documentos:
        respuesta = enviar_mensaje_con_documentos(chat_id, texto, documentos)
    else:
        respuesta = enviar_mensaje_con_botones(chat_id, texto)

    if SHOW_STEPS:
        print(f"[PONENTE] Respuesta enviada al ponente: {respuesta.get('ok')}")
        if not respuesta.get("ok"):
            print(f"[PONENTE] Error Telegram: {respuesta}")


def main():
    print("[SERVICIO] agente_telegram_ponentes iniciado")
    print(f"[SERVICIO] Telegram enabled: {TELEGRAM_ENABLED}")
    print(f"[SERVICIO] Envío Telegram permitido: {ALLOW_SEND_TELEGRAM}")
    print(f"[SERVICIO] Admin Telegram configurado: {bool(obtener_admin_chat_id())}")
    print(f"[SERVICIO] Avisos al admin solo por urgencias: {ALLOW_NOTIFY_ADMIN}")

    ultimo_update_id = None
    ultimo_check_telegram = 0

    while True:
        ahora = time.time()

        if TELEGRAM_ENABLED and ahora - ultimo_check_telegram >= TELEGRAM_CHECK_SECONDS:
            ultimo_check_telegram = ahora

            if SHOW_STEPS and not QUIET_MODE_ENABLED:
                print("[TELEGRAM] Buscando mensajes nuevos")

            # Blindaje del servicio: un fallo puntual (red de Telegram, BD caída,
            # error del LLM) no puede tumbar el bot entero. Si falla la lectura
            # de updates se espera y se reintenta en el siguiente ciclo; si falla
            # el procesamiento de UN update, se registra y se sigue con el resto
            # (el update_id ya avanzó, así que no se reprocesa en bucle).
            try:
                updates = leer_updates(offset=ultimo_update_id)
            except Exception as error_lectura:
                print(f"[SERVICIO] Error leyendo updates de Telegram (se reintenta): {error_lectura}")
                time.sleep(SERVICE_LOOP_SECONDS)
                continue

            for update in updates:
                ultimo_update_id = update.get("update_id", 0) + 1
                try:
                    payload = update_a_payload(update)
                    if not payload:
                        continue

                    datos_payload = payload.get("datos", {}) or {}
                    chat_id = datos_payload.get("telegram_chat_id")
                    texto_entrada = datos_payload.get("texto", "")
                    callback_data = datos_payload.get("callback_data", "")
                    admin_chat_id = obtener_admin_chat_id()

                    # Evita que mensajes escritos por el admin al bot sean tratados como consultas de ponente.
                    if admin_chat_id and _normalizar_id(chat_id) == _normalizar_id(admin_chat_id):
                        if es_comando_bienvenida(texto_entrada):
                            enviar_mensaje(chat_id, "Bot MITUMI activo. Este chat está configurado como ADMIN.")
                        elif SHOW_STEPS:
                            print("[TELEGRAM] Mensaje recibido desde admin. Se ignora como consulta de ponente.")
                        continue

                    if callback_data.startswith("EVT|"):
                        procesar_callback_evento(payload)
                        continue

                    if callback_data.startswith("DOC|"):
                        procesar_callback_documento(payload)
                        continue

                    if callback_data.startswith("CNT|"):
                        procesar_callback_contacto(payload)
                        continue

                    if datos_payload.get("documento"):
                        procesar_documento_recibido(payload)
                        continue

                    if es_comando_bienvenida(texto_entrada):
                        enviar_bienvenida_y_eventos(payload)
                        if SHOW_STEPS:
                            print("[PONENTE] Bienvenida y selección de evento enviadas")
                        continue

                    if es_boton_seleccionar_evento(texto_entrada):
                        seleccionar_evento(payload)
                        continue

                    if es_boton_urgencia(texto_entrada):
                        texto_ponente = (
                            "🚨 He recibido tu aviso urgente.\n\n"
                            "Si puedes, escribe brevemente qué ocurre para que MITUMI tenga más contexto."
                        )
                        if chat_id and ALLOW_SEND_TELEGRAM:
                            enviar_mensaje_con_botones(chat_id, texto_ponente)
                        resultado = construir_resultado_escalado_directo("boton_urgencia_pulsado", "alta")
                        enviar_aviso_admin_si_aplica(payload, resultado)
                        continue

                    payload = normalizar_payload_boton(payload)
                    resultado = ejecutar_agente(payload)
                    texto = extraer_texto_respuesta(resultado)

                    if not texto and es_urgencia_para_admin(resultado):
                        texto = (
                            "He avisado al equipo de MITUMI porque la consulta se ha "
                            "clasificado como urgente."
                        )
                    elif not texto and hay_escalado(resultado):
                        texto = (
                            "No puedo confirmar ese dato automáticamente. "
                            "Puedes solicitar contacto con MITUMI desde la opción disponible."
                        )

                    if texto and chat_id and ALLOW_SEND_TELEGRAM:
                        enviar_respuesta_ponente(chat_id, texto, resultado)
                    elif SHOW_STEPS:
                        print("[SERVICIO] Respuesta no enviada automáticamente")
                        print(resultado.get("resumen"))

                    enviar_aviso_admin_si_aplica(payload, resultado)
                except Exception as error_update:
                    print(f"[SERVICIO] Error procesando update {update.get('update_id')}: {error_update}")

        time.sleep(SERVICE_LOOP_SECONDS)


if __name__ == "__main__":
    main()
