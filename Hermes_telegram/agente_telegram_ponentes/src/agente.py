from config.settings import AGENT_NAME, MIN_CONFIDENCE_TO_REPLY, SAVE_CONVERSATION_LOG
from config.permisos import (
    ESCALATE_UNKNOWN_SPEAKER,
    ESCALATE_MULTIPLE_ACTIVE_EVENTS,
    ESCALATE_MISSING_DATA,
    ESCALATE_LOW_CONFIDENCE,
)
from src.funciones import (
    cargar_prompt_compuesto,
    guardar_log,
    puede_responder_automaticamente,
    construir_borrador_telegram,
)
from integrations.llm import llamar_llm_json
from src.schemas import validar_payload_entrada, salida_base, extraer_datos_telegram
from src.herramientas import (
    obtener_ponente_por_telegram,
    obtener_eventos_activos_ponente,
    obtener_info_ponente_evento,
    obtener_documentos_ponente_evento,
    registrar_comunicacion,
    crear_incidencia,
)
from src.memoria import obtener_evento_activo_usuario, guardar_evento_activo_usuario
from src.validaciones import validar_decision_llm


ETIQUETAS_SERVICIOS = {
    "comida_restaurante": "comidas, restaurante o catering",
    "coche_alquiler": "coche de alquiler",
    "bus": "autobús, minibús o lanzadera",
    "parking": "aparcamiento",
    "accesibilidad": "accesibilidad",
    "wifi": "wifi o conexión a internet",
    "otro": "ese servicio",
}

TIPOS_SERVICIOS_BD = {
    "comida_restaurante": {"comida"},
    "coche_alquiler": {"coche_alquiler"},
    "bus": {"bus"},
    "parking": {"parking"},
    "accesibilidad": {"accesibilidad"},
    "wifi": {"wifi"},
    "otro": {"otro"},
}


def ejecutar_agente(payload: dict) -> dict:
    """Punto de entrada del agente con contrato estructurado estable."""
    salida = salida_base(payload, ok=True)
    errores_payload = validar_payload_entrada(payload)
    if errores_payload:
        salida["ok"] = False
        salida["resumen"] = "Payload de entrada inválido."
        salida["errores"].extend(errores_payload)
        salida["nivel_riesgo"] = "medio"
        return salida

    datos_telegram = extraer_datos_telegram(payload)
    telegram_user_id = datos_telegram["telegram_user_id"]
    telegram_chat_id = datos_telegram["telegram_chat_id"]
    texto = datos_telegram["texto"]

    if not telegram_user_id or not texto:
        salida["ok"] = False
        salida["resumen"] = "Faltan datos mínimos de Telegram."
        salida["errores"].append("faltan_datos_telegram")
        salida["bloqueos_detectados"].append({"tipo": "datos_telegram_incompletos"})
        salida["requiere_validacion_humana"] = True
        return salida

    ponente = obtener_ponente_por_telegram(telegram_user_id)
    salida["trazas"]["fuentes_consultadas"].append("ponente_por_telegram")

    if not ponente:
        texto_respuesta = (
            "Hola. No encuentro tu usuario de Telegram vinculado a un ponente registrado. "
            "La organización debe revisar la vinculación antes de continuar."
        )
        salida.update({
            "resumen": "Ponente no identificado por Telegram.",
            "requiere_validacion_humana": True,
            "nivel_riesgo": "medio",
        })
        salida["bloqueos_detectados"].append({
            "tipo": "ponente_no_identificado",
            "telegram_user_id": telegram_user_id,
        })
        salida["borradores_generados"].append(
            construir_borrador_telegram(telegram_chat_id, texto_respuesta, False)
        )
        if ESCALATE_UNKNOWN_SPEAKER:
            salida["acciones_propuestas"].append({
                "tipo": "escalar_a_organizacion",
                "motivo": "ponente_no_identificado",
            })
        crear_incidencia({"tipo": "ponente_no_identificado", "payload": payload})
        _registrar_y_devolver(payload, salida)
        return salida

    id_ponente = ponente.get("id_ponente")
    eventos = obtener_eventos_activos_ponente(id_ponente)
    salida["trazas"]["fuentes_consultadas"].append("eventos_activos_ponente")
    salida["datos_detectados"].update({
        "id_ponente": id_ponente,
        "nombre_ponente": ponente.get("nombre"),
        "telegram_user_id": telegram_user_id,
    })

    if not eventos:
        texto_respuesta = (
            "Hola. Ahora mismo no encuentro ningún evento disponible asociado a tu perfil. "
            "MITUMI debe revisar la asignación antes de que podamos continuar."
        )
        salida["resumen"] = "El ponente no tiene eventos activos asociados."
        salida["bloqueos_detectados"].append({
            "tipo": "sin_eventos_activos",
            "id_ponente": id_ponente,
        })
        salida["borradores_generados"].append(
            construir_borrador_telegram(telegram_chat_id, texto_respuesta, False)
        )
        salida["requiere_validacion_humana"] = True
        salida["nivel_riesgo"] = "medio"
        if ESCALATE_MISSING_DATA:
            salida["acciones_propuestas"].append({
                "tipo": "crear_incidencia",
                "motivo": "sin_eventos_activos",
            })
        crear_incidencia({"tipo": "sin_eventos_activos", "id_ponente": id_ponente})
        _registrar_y_devolver(payload, salida)
        return salida

    # La selección del evento es obligatoria incluso si solo existe uno.
    id_evento = _resolver_evento_activo(payload, telegram_user_id, id_ponente, eventos)
    if id_evento is None:
        texto_respuesta = _texto_pedir_evento(eventos)
        salida["resumen"] = "Debe seleccionarse un evento antes de continuar."
        salida["datos_detectados"]["eventos_activos"] = eventos
        salida["bloqueos_detectados"].append({
            "tipo": "evento_activo_no_seleccionado",
            "eventos": eventos,
        })
        salida["borradores_generados"].append(
            construir_borrador_telegram(telegram_chat_id, texto_respuesta, True)
        )
        salida["requiere_validacion_humana"] = False
        salida["nivel_riesgo"] = "bajo"
        if ESCALATE_MULTIPLE_ACTIVE_EVENTS:
            salida["acciones_propuestas"].append({
                "tipo": "solicitar_seleccion_evento",
                "canal": "telegram",
            })
        _registrar_y_devolver(payload, salida)
        return salida

    info = obtener_info_ponente_evento(id_ponente, id_evento)
    salida["trazas"]["fuentes_consultadas"].append("info_ponente_evento")

    if not info:
        texto_respuesta = (
            "No encuentro todavía la información logística de este evento. "
            "Prefiero que MITUMI la confirme antes de darte un dato incorrecto."
        )
        salida["resumen"] = "No hay datos del ponente para el evento seleccionado."
        salida["datos_detectados"]["id_evento"] = id_evento
        salida["bloqueos_detectados"].append({
            "tipo": "datos_ponente_evento_no_encontrados",
            "id_ponente": id_ponente,
            "id_evento": id_evento,
        })
        salida["borradores_generados"].append(
            construir_borrador_telegram(telegram_chat_id, texto_respuesta, False)
        )
        salida["requiere_validacion_humana"] = True
        salida["nivel_riesgo"] = "medio"
        crear_incidencia({
            "tipo": "datos_ponente_evento_no_encontrados",
            "id_ponente": id_ponente,
            "id_evento": id_evento,
        })
        _registrar_y_devolver(payload, salida)
        return salida

    evento = _buscar_evento(eventos, id_evento)
    if evento:
        guardar_evento_activo_usuario(
            telegram_user_id,
            id_ponente,
            id_evento,
            evento.get("nombre_evento"),
        )

    documentos = obtener_documentos_ponente_evento(
        id_ponente,
        id_evento,
        info=info,
    )
    if documentos:
        salida["trazas"]["fuentes_consultadas"].append("documentos_ponente_evento")

    datos_payload = payload.get("datos", {}) or {}
    intencion_forzada = datos_payload.get("intencion_forzada")

    if intencion_forzada:
        # Los botones son acciones deterministas: no necesitan LLM. Esto evita
        # clasificaciones erróneas y reduce notablemente el tiempo de respuesta.
        decision = validar_decision_llm({
            "intencion": intencion_forzada,
            "urgencia": "normal",
            "respuesta_ponente": "",
            "requiere_escalado": False,
            "motivo_escalado": None,
            "confianza": 1.0,
            "servicio_consultado": datos_payload.get("servicio_consultado_forzado"),
        })
    else:
        system_prompt = cargar_prompt_compuesto()
        contexto_llm = {
            "mensaje_ponente": texto,
            "ponente": ponente,
            "eventos_activos": eventos,
            "id_evento_seleccionado": id_evento,
            "info_ponente_evento": info,
            "documentos_disponibles": documentos,
            "servicios_adicionales_confirmados": info.get("servicios_adicionales", []),
        }
        decision = validar_decision_llm(llamar_llm_json(system_prompt, contexto_llm))

    # También en preguntas libres, "vuelo" debe significar vuelo y no el
    # itinerario completo. Se completa el subtipo si el LLM no lo devuelve.
    if decision.get("intencion") == "consulta_viaje" and not decision.get("servicio_consultado"):
        texto_transporte = texto.lower()
        if any(palabra in texto_transporte for palabra in ("vuelo", "avión", "avion", "aeropuerto")):
            decision["servicio_consultado"] = "vuelo"
        elif any(palabra in texto_transporte for palabra in ("tren", "ave", "estación", "estacion")):
            decision["servicio_consultado"] = "tren"

    servicios_encontrados = _buscar_servicios_adicionales(decision, info)
    ofrecer_contacto = (
        decision.get("intencion") == "consulta_servicio_adicional"
        and not servicios_encontrados
    )
    motivo_contacto = _motivo_contacto(decision) if ofrecer_contacto else None

    texto_respuesta = construir_respuesta(
        decision,
        info,
        documentos,
        servicios_encontrados=servicios_encontrados,
    )
    confianza = float(decision.get("confianza", 0.0) or 0.0)

    # Cuando no hay un servicio adicional confirmado, no se escala automáticamente:
    # se ofrece al ponente decidir si quiere contacto humano.
    escalado_por_confianza = (
        confianza < MIN_CONFIDENCE_TO_REPLY
        and ESCALATE_LOW_CONFIDENCE
        and not ofrecer_contacto
    )
    requiere_escalado = (
        bool(decision.get("requiere_escalado")) or escalado_por_confianza
    ) and not ofrecer_contacto

    if escalado_por_confianza:
        texto_respuesta = (
            "He entendido tu consulta, pero prefiero que MITUMI confirme el dato "
            "antes de responderte de forma incorrecta."
        )

    apto_envio = not requiere_escalado and puede_responder_automaticamente()
    documentos_descarga = _seleccionar_documentos_descarga(decision, documentos, info)

    salida["resumen"] = f"Consulta clasificada como {decision.get('intencion')}."
    salida["datos_detectados"].update({
        "id_evento": id_evento,
        "nombre_evento": info.get("nombre_evento"),
        "evento_activo": id_evento,
        "intencion": decision.get("intencion"),
        "servicio_consultado": decision.get("servicio_consultado"),
        "servicios_encontrados": servicios_encontrados,
        "urgencia": decision.get("urgencia"),
        "confianza": confianza,
        "respuesta_ponente": texto_respuesta,
        "documentos_descarga": documentos_descarga,
        "ofrecer_contacto_mitumi": ofrecer_contacto,
        "motivo_contacto": motivo_contacto,
        "mensaje_original": texto,
    })
    salida["borradores_generados"].append(
        construir_borrador_telegram(telegram_chat_id, texto_respuesta, apto_envio)
    )
    salida["requiere_validacion_humana"] = requiere_escalado
    salida["nivel_riesgo"] = "medio" if requiere_escalado else "bajo"

    if ofrecer_contacto:
        salida["acciones_propuestas"].append({
            "tipo": "ofrecer_contacto_mitumi",
            "motivo": motivo_contacto,
            "requiere_confirmacion_ponente": True,
        })
    elif requiere_escalado:
        salida["acciones_propuestas"].append({
            "tipo": "escalar_a_organizacion",
            "motivo": decision.get("motivo_escalado") or "confianza_baja_o_dato_sensible",
        })
    else:
        salida["acciones_propuestas"].append({
            "tipo": "responder_telegram",
            "canal": "telegram",
            "requiere_permiso_envio": True,
        })

    for doc in documentos_descarga:
        salida["acciones_propuestas"].append({
            "tipo": "ofrecer_documento_descarga",
            "id_evento": id_evento,
            "tipo_documento": doc.get("tipo_documento"),
            "nombre_archivo": doc.get("nombre_archivo"),
        })

    if not puede_responder_automaticamente():
        salida["bloqueos_detectados"].append({"tipo": "fuera_de_horario_ordinario"})

    registrar_comunicacion({
        "agente": AGENT_NAME,
        "telegram_user_id": telegram_user_id,
        "id_ponente": id_ponente,
        "id_evento": id_evento,
        "texto_entrada": texto,
        "salida": salida,
    })
    _registrar_y_devolver(payload, salida)
    return salida


def construir_respuesta(
    decision: dict,
    info: dict,
    documentos: list[dict] | None = None,
    servicios_encontrados: list[dict] | None = None,
) -> str:
    intencion = decision.get("intencion")
    documentos = documentos or []
    servicios_encontrados = servicios_encontrados or []

    if intencion == "consulta_alojamiento":
        return _respuesta_hotel(info)

    if intencion == "consulta_viaje":
        return _respuesta_transporte(info, documentos, decision)

    if intencion == "consulta_taxi":
        return _respuesta_taxi(info)

    if intencion == "consulta_horario":
        horario = info.get("horario_ponencia")
        lugar = info.get("lugar")
        nombre = info.get("nombre_evento") or "el evento"
        if horario:
            texto = f"🕒 HORARIO DE TU PONENCIA\n\nEvento: {nombre}\nFecha y hora: {horario}"
            if lugar:
                texto += f"\nLugar: {lugar}"
            return texto
        return (
            "Todavía no tengo confirmado el horario de tu ponencia en los datos del evento. "
            "MITUMI debe revisarlo antes de que te dé una hora concreta."
        )

    if intencion == "consulta_lugar":
        return _respuesta_lugar_evento(info, documentos)

    if intencion == "consulta_documentacion":
        pendientes = info.get("documentos_pendientes", [])
        lineas = ["📄 DOCUMENTACIÓN", ""]
        if pendientes:
            lineas.append("Pendiente de aportar: " + ", ".join(pendientes) + ".")
        else:
            lineas.append("No veo documentación pendiente por tu parte en este momento.")
        if documentos:
            lineas.append("")
            lineas.append("Documentos disponibles para descargar:")
            for doc in documentos:
                lineas.append(f"• {doc.get('titulo_boton') or doc.get('tipo_documento')}")
        return "\n".join(lineas)

    if intencion == "solicitud_documento":
        if documentos:
            return (
                "📎 He encontrado documentación asociada a este evento. "
                "Selecciona el archivo que necesitas en los botones inferiores."
            )
        return (
            "No encuentro documentos disponibles para descarga en este evento. "
            "Puedo ayudarte a solicitar que MITUMI lo revise."
        )

    if intencion == "resumen_viaje":
        return construir_resumen_viaje(info, documentos)

    if intencion == "consulta_servicio_adicional":
        return _respuesta_servicio_adicional(decision, info, servicios_encontrados)

    if intencion == "seleccionar_evento":
        return "Claro. Usa el botón 📅 Seleccionar evento para elegir o cambiar el evento activo."

    if intencion == "incidencia":
        respuesta = decision.get("respuesta_ponente")
        return respuesta or (
            "He recibido tu aviso. El equipo de MITUMI debe revisar esta incidencia lo antes posible."
        )

    if intencion == "saludo":
        nombre_evento = info.get("nombre_evento") or "tu evento"
        return (
            f"Hola. Encantado de ayudarte con {nombre_evento}. "
            "Puedes preguntarme por tu viaje, hotel, taxis, lugar del evento, documentación "
            "u otros servicios logísticos."
        )

    respuesta = decision.get("respuesta_ponente")
    if respuesta:
        return respuesta

    return (
        "He recibido tu consulta. No encuentro una respuesta confirmada en los datos disponibles. "
        "Explícame un poco más qué necesitas y trataré de orientarte sin inventar información."
    )


def _respuesta_hotel(info: dict) -> str:
    hotel = info.get("hotel")
    if not hotel:
        return (
            "🏨 ALOJAMIENTO\n\nTodavía no tengo un hotel confirmado para este evento. "
            "MITUMI debe revisar el alojamiento antes de que te dé un dato concreto."
        )

    lineas = ["🏨 ALOJAMIENTO", "", f"Hotel: {hotel}"]
    if info.get("direccion_hotel"):
        lineas.append(f"Dirección: {info.get('direccion_hotel')}")
    if info.get("checkin_horario"):
        lineas.append(f"Check-in previsto: {info.get('checkin_horario')}")

    traslados_hotel = info.get("traslados_hotel") or []
    if traslados_hotel:
        lineas.extend(["", "Traslados relacionados con el hotel:"])
        for item in traslados_hotel:
            lineas.append(f"• {_formatear_item(item)}")

    return "\n".join(lineas)


def _respuesta_transporte(info: dict, documentos: list[dict], decision: dict) -> str:
    servicio = decision.get("servicio_consultado")
    transportes = info.get("transportes_principales") or []

    # El botón Vuelo no es un alias de "viaje completo": filtra únicamente
    # líneas identificadas como vuelo. Tren, bus, taxi y hotel quedan fuera.
    if servicio == "vuelo":
        vuelos = [item for item in transportes if item.get("tipo_servicio") == "vuelo"]
        if not vuelos:
            return (
                "✈️ VUELO\n\n"
                "No encuentro ningún vuelo confirmado en la información de este evento. "
                "La base de datos puede contener otro medio de transporte, pero no lo mostraré "
                "como si fuera un vuelo. Puedes consultar 🧭 Resumen viaje para ver el itinerario completo."
            )

        lineas = ["✈️ VUELO", ""]
        etiquetas = ["IDA", "VUELTA"]
        for indice, vuelo in enumerate(vuelos[:2]):
            if indice:
                lineas.append("")
            lineas.append(etiquetas[indice])
            lineas.append(f"• {_formatear_item(vuelo)}")

        if len(vuelos) == 1:
            lineas.extend(["", "VUELTA", "• Vuelo de vuelta pendiente de confirmar."])

        if _hay_documento_tipo(documentos, {"billete_ida", "billete_vuelta"}):
            lineas.extend(["", "Los billetes de vuelo disponibles aparecen en los botones inferiores."])
        return "\n".join(lineas)

    # Para preguntas libres sobre transporte se conserva una respuesta genérica,
    # pero sin mezclar hotel, taxis, lugar ni horario del evento.
    if not transportes:
        return (
            "🧳 TRANSPORTE PRINCIPAL\n\n"
            "No tengo confirmado el medio de transporte principal para este evento."
        )

    lineas = ["🧳 TRANSPORTE PRINCIPAL", ""]
    for item in transportes:
        lineas.append(f"• {_formatear_item(item)}")
    return "\n".join(lineas)


def _respuesta_taxi(info: dict) -> str:
    taxis = info.get("traslados_taxi") or []
    if not taxis:
        return (
            "🚕 TRASLADOS\n\nNo aparece ningún taxi confirmado en la información logística "
            "de este evento."
        )

    lineas = ["🚕 TRASLADOS CONFIRMADOS", ""]
    for item in taxis:
        lineas.append(f"• {_formatear_item(item)}")
    return "\n".join(lineas)


def _respuesta_lugar_evento(info: dict, documentos: list[dict]) -> str:
    lugar = info.get("lugar")
    if not lugar:
        return (
            "📍 LUGAR DEL EVENTO\n\nTodavía no tengo confirmado el lugar del evento. "
            "MITUMI debe revisarlo antes de que te indique una ubicación."
        )

    lineas = [
        "📍 LUGAR DEL EVENTO",
        "",
        f"Evento: {info.get('nombre_evento') or 'Evento MITUMI'}",
        f"Lugar: {lugar}",
    ]
    if info.get("ciudad"):
        lineas.append(f"Ciudad: {info.get('ciudad')}")
    if info.get("fecha_evento"):
        lineas.append(f"Fecha del evento: {info.get('fecha_evento')}")
    if info.get("horario_ponencia"):
        lineas.append(f"Tu ponencia: {info.get('horario_ponencia')}")
    if info.get("tipo_ponencia"):
        lineas.append(f"Participación: {info.get('tipo_ponencia')}")
    if _hay_documento_tipo(documentos, {"plano_ubicacion", "agenda_evento"}):
        lineas.extend(["", "El plano o la agenda están disponibles en los botones inferiores."])
    return "\n".join(lineas)


def _respuesta_servicio_adicional(
    decision: dict,
    info: dict,
    servicios_encontrados: list[dict],
) -> str:
    servicio = decision.get("servicio_consultado") or "otro"
    etiqueta = ETIQUETAS_SERVICIOS.get(servicio, "ese servicio")

    if servicios_encontrados:
        lineas = [f"ℹ️ INFORMACIÓN SOBRE {etiqueta.upper()}", ""]
        for item in servicios_encontrados:
            lineas.append(f"• {_formatear_item(item)}")
        lineas.extend(["", "Estos son los datos que MITUMI tiene confirmados para tu evento."])
        return "\n".join(lineas)

    return (
        f"No encuentro información confirmada sobre {etiqueta} para "
        f"{info.get('nombre_evento') or 'este evento'}. "
        "No quiero darte un dato incorrecto. Si quieres, puedo pedir a MITUMI que lo revise contigo."
    )


def construir_resumen_viaje(info: dict, documentos: list[dict] | None = None) -> str:
    documentos = documentos or []
    timeline = info.get("timeline_viaje") or []
    nombre_evento = info.get("nombre_evento") or "evento"

    lineas = [f"🧭 RESUMEN DEL VIAJE — {nombre_evento}", ""]

    if info.get("horario_ida_transporte"):
        lineas.append(f"Viaje de ida: {info.get('horario_ida_transporte')}")
    if info.get("checkin_horario"):
        lineas.append(f"Check-in: {info.get('checkin_horario')}")
    if info.get("hotel"):
        hotel = info.get("hotel")
        direccion = info.get("direccion_hotel")
        lineas.append(f"Hotel: {hotel}" + (f" — {direccion}" if direccion else ""))
    if info.get("horario_ponencia"):
        lugar = info.get("lugar") or "lugar pendiente de confirmar"
        lineas.append(f"Ponencia: {info.get('horario_ponencia')} — {lugar}")
    if info.get("horario_vuelta_transporte"):
        lineas.append(f"Viaje de vuelta: {info.get('horario_vuelta_transporte')}")

    if timeline:
        lineas.extend(["", "Secuencia logística registrada por MITUMI:"])
        # Se conserva el orden original de la BD. Ordenar solo por hora rompía
        # la secuencia cuando el viaje abarcaba más de un día.
        for item in timeline:
            lineas.append(f"• {_formatear_item(item)}")
    else:
        lineas.extend(["", "No hay un detalle cronológico adicional registrado."])

    servicios = info.get("servicios_adicionales") or []
    if servicios:
        lineas.extend(["", "Otros servicios confirmados:"])
        for item in servicios:
            lineas.append(f"• {_formatear_item(item)}")

    if _hay_documento_tipo(documentos, {"billete_ida", "billete_vuelta"}):
        lineas.extend(["", "Puedes descargar los billetes desde los botones inferiores."])

    return "\n".join(lineas)


def _formatear_item(item: dict, incluir_hora: bool = True) -> str:
    hora = item.get("hora")
    descripcion = item.get("descripcion") or item.get("detalle") or "Información logística"
    if incluir_hora and hora:
        return f"{hora} · {descripcion}"
    return str(descripcion)


def _buscar_servicios_adicionales(decision: dict, info: dict) -> list[dict]:
    if decision.get("intencion") != "consulta_servicio_adicional":
        return []

    servicio = decision.get("servicio_consultado") or "otro"
    tipos = TIPOS_SERVICIOS_BD.get(servicio, {servicio})
    servicios = info.get("servicios_adicionales") or []
    return [item for item in servicios if item.get("tipo_servicio") in tipos]


def _motivo_contacto(decision: dict) -> str:
    servicio = decision.get("servicio_consultado") or "otro"
    etiqueta = ETIQUETAS_SERVICIOS.get(servicio, "servicio adicional")
    return f"Solicitar información sobre {etiqueta}"


def _resolver_evento_activo(
    payload: dict,
    telegram_user_id: str,
    id_ponente,
    eventos: list[dict],
) -> str | None:
    id_evento_payload = (
        payload.get("id_evento")
        or payload.get("contexto", {}).get("id_evento")
        or payload.get("datos", {}).get("id_evento")
    )
    if id_evento_payload:
        id_evento = str(id_evento_payload)
        evento = _buscar_evento(eventos, id_evento)
        if evento:
            guardar_evento_activo_usuario(
                telegram_user_id,
                id_ponente,
                id_evento,
                evento.get("nombre_evento"),
            )
            return id_evento
        return None

    id_evento_memoria = obtener_evento_activo_usuario(telegram_user_id)
    if id_evento_memoria and _buscar_evento(eventos, id_evento_memoria):
        return id_evento_memoria

    return None


def _buscar_evento(eventos: list[dict], id_evento) -> dict | None:
    for evento in eventos:
        if str(evento.get("id_evento")) == str(id_evento):
            return evento
    return None


def _texto_pedir_evento(eventos: list[dict]) -> str:
    cantidad = len(eventos)
    return (
        f"Antes de continuar necesito que selecciones el evento. "
        f"Tienes {cantidad} evento{'s' if cantidad != 1 else ''} disponible{'s' if cantidad != 1 else ''}."
    )


def _seleccionar_documentos_descarga(
    decision: dict,
    documentos: list[dict],
    info: dict,
) -> list[dict]:
    intencion = decision.get("intencion")
    if not documentos:
        return []

    # Cada botón ofrece únicamente documentos directamente relacionados.
    # Hotel, taxi, lugar y resumen no muestran billetes ni otros archivos.
    if intencion == "consulta_viaje":
        if decision.get("servicio_consultado") == "vuelo":
            hay_vuelo = any(
                item.get("tipo_servicio") == "vuelo"
                for item in (info.get("transportes_principales") or [])
            )
            if not hay_vuelo:
                return []
        tipos = {"billete_ida", "billete_vuelta"}
    elif intencion in {"consulta_documentacion", "solicitud_documento"}:
        tipos = None
    else:
        return []

    seleccionados = documentos if tipos is None else [
        documento
        for documento in documentos
        if documento.get("tipo_documento") in tipos
    ]
    return [dict(documento) for documento in seleccionados]


def _hay_documento_tipo(documentos: list[dict], tipos: set[str]) -> bool:
    return any(doc.get("tipo_documento") in tipos for doc in documentos)


def _registrar_y_devolver(payload: dict, salida: dict) -> None:
    if SAVE_CONVERSATION_LOG:
        guardar_log("conversaciones.jsonl", {"payload": payload, "salida": salida})
