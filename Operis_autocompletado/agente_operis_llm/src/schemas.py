# src/schemas.py
# =====================================================================
# SCHEMAS - CONTRATO DE SALIDA DEL AGENTE OPERIS
# =====================================================================
# Define la estructura de los 4 bloques de salida:
#   1. Evento
#   2. Cliente (con múltiples contactos)
#   3. Ponentes
#   4. Nota Bene (cajón de sastre con presupuesto, servicios e histórico)
#
# También incluye la validación de campos obligatorios (solo para Evento)
# y la generación de avisos para el usuario.
# =====================================================================

from datetime import datetime


# =====================================================================
# 1. CAMPOS OBLIGATORIOS DEL EVENTO (para validación)
# =====================================================================
# Estos son los campos mínimos que debe tener un evento para considerarse
# "completo". La validación SOLO aplica al bloque Evento.
# Nota Bene NO cuenta para el porcentaje de completado.
CAMPOS_OBLIGATORIOS_EVENTO = [
    "nombre_evento",
    "ciudad",
    "fecha_inicio",
    "fecha_fin",
    "numero_personas",
    "tipo_evento"
]

CAMPOS_OBJETIVO_DEFAULT = {
    "evento": CAMPOS_OBLIGATORIOS_EVENTO,
    "cliente": ["cliente", "empresa", "email", "telefono", "sector", "ciudad"],
    "ponente": ["nombre_ponente", "email", "telefono", "sector", "empresa", "cargo"],
    "ponentes": ["nombre_ponente", "email", "telefono", "sector", "empresa", "cargo"],
}

TIPO_OBJETIVO_A_BLOQUE = {
    "evento": "evento",
    "cliente": "cliente",
    "ponente": "ponentes",
    "ponentes": "ponentes",
}


def _normalizar_tipo_objetivo(tipo_objetivo):
    return str(tipo_objetivo or "evento").strip().lower() or "evento"


def _normalizar_campos_objetivo(campos_objetivo):
    if not campos_objetivo:
        return []
    return [str(campo).strip() for campo in campos_objetivo if str(campo).strip()]


def _valor_presente(valor):
    if isinstance(valor, list):
        return any(_valor_presente(item) for item in valor)
    if isinstance(valor, dict):
        return any(_valor_presente(item) for item in valor.values())
    return valor is not None and str(valor).strip() != ""


def _campo_detectado_en_bloque(datos_bloque, campo):
    if isinstance(datos_bloque, dict):
        return _valor_presente(datos_bloque.get(campo))
    if isinstance(datos_bloque, list):
        return any(
            isinstance(item, dict) and _valor_presente(item.get(campo))
            for item in datos_bloque
        )
    return False


# =====================================================================
# 2. ESTRUCTURA VACÍA COMPLETA (4 BLOQUES)
# =====================================================================
def crear_estructura_vacia_completa():
    """
    Devuelve la estructura completa de salida con todos los campos vacíos.
    
    Returns:
        dict: Estructura con 4 bloques (Evento, Cliente, Ponentes, Nota Bene)
              y los campos _validacion y _aviso_agente para la UI.
    """
    return {
        # ===== BLOQUE 1: EVENTO =====
        "evento": {
            "nombre_evento": "",
            "ciudad": "",
            "lugar_confirmado": "",
            "fecha_inicio": "",
            "fecha_fin": "",
            "numero_personas": "",
            "tipo_evento": "",
            "estado": "",
            "nota": ""
        },
        
        # ===== BLOQUE 2: CLIENTE =====
        "cliente": {
            "cliente": "",
            "empresa": "",
            "email": "",
            "telefono": "",
            "sector": "",
            "ciudad": "",
            # Múltiples personas de contacto
            "personas_contacto": [
                # {
                #     "nombre": "",
                #     "cargo": "",
                #     "email": "",
                #     "telefono": "",
                #     "nota": ""
                # }
            ],
            # Sugerencia: ¿parece un cliente existente o nuevo?
            "cliente_existente": False,
            "nota_cliente": ""
        },
        
        # ===== BLOQUE 3: PONENTES =====
        "ponentes": [
            # {
            #     # Datos de ponente (tabla ponentes)
            #     "nombre_ponente": "",
            #     "doc_identificacion": "",
            #     "email": "",
            #     "sector": "",
            #     "telefono": "",
            #     "foto_link": "",
            #     "cv_link": "",
            #     "empresa": "",
            #     "cargo": "",
            #     # Datos de ponencia (tabla ponencias)
            #     "nombre_hotel": "",
            #     "nota_transporte": "",
            #     "horario_ida_transporte": "",
            #     "horario_vuelta_transporte": "",
            #     "localizacion_hotel": "",
            #     "horario_ponencia": "",
            #     "checking_horario": "",
            #     "ponente_estado": "",
            #     "presentacion_link": "",
            #     "billete_ida_link": "",
            #     "billete_vuelta_link": "",
            #     "tipo_ponencias": "",
            #     "nota_ponente": ""
            # }
        ],
        
        # ===== BLOQUE 4: NOTA BENE =====
        "nota_bene": {
            # Cabecera resumen (siempre visible, golpe de vista)
            "cabecera": {
                "nombre_evento": "",
                "estado_evento": "",
                "fecha_celebracion": "",      # "15-17/10/2026"
                "cliente_principal": "",
                "persona_contacto": "",
                "presupuesto_total_estimado": "",
                "ultima_actualizacion": ""    # ISO timestamp
            },
            
            # Presupuesto y servicios (4 sub-bloques)
            "presupuesto_servicios": {
                "ubicacion": {
                    "descripcion": "",
                    "precio_estimado": "",
                    "nota": "",
                    "estado": ""   # Pendiente, Confirmado, Cotizando
                },
                "catering": {
                    "descripcion": "",
                    "precio_estimado": "",
                    "nota": "",
                    "estado": ""
                },
                "audiovisuales": {
                    "descripcion": "",
                    "precio_estimado": "",
                    "nota": "",
                    "estado": ""
                },
                "otros": {
                    "descripcion": "",
                    "precio_estimado": "",
                    "nota": "",
                    "estado": ""
                }
            },
            
            # Cajón de sastre: todo lo que no encaja en los bloques anteriores
            "informacion_adicional": {
                "notas_generales": "",
                "requerimientos_especiales": "",
                "riesgos_detectados": "",
                "acciones_pendientes": [],
                "dependencias": [],
                # Histórico de actualizaciones (se llena con cada nueva versión)
                "historico_actualizaciones": [
                    # {
                    #     "fecha": "2026-07-10T10:00:00",
                    #     "cambios_detectados": "Se añadió presupuesto de catering",
                    #     "version": 2
                    # }
                ]
            }
        },
        
        # ===== CAMPOS INTERNOS (para UI y validación) =====
        "_validacion": {
            "porcentaje_completado": 0,
            "campos_pendientes": []
        },
        "_aviso_agente": {
            "mensaje": ""
        }
    }


# =====================================================================
# 3. ESTRUCTURA VACÍA PARA EL HISTÓRICO (BACKEND)
# =====================================================================
def crear_estructura_vacia_historico():
    """
    Devuelve la estructura vacía para el histórico que guarda el backend.

    Returns:
        dict: Estructura para almacenar versiones del briefing.
    """
    return {
        "evento_id": "",
        "versiones": [
            # {
            #     "fecha": "2026-07-10T10:00:00",
            #     "archivo": "briefing_v1.txt",
            #     "resumen": "Propuesta inicial",
            #     "datos": {}  # Aquí va el JSON completo del agente
            # }
        ],
        "ultima_actualizacion": ""
    }


def extraer_ultimo_estado(historial_anterior):
    """
    Devuelve solo los 4 bloques (evento/cliente/ponentes/nota_bene) de la
    última versión guardada en un histórico, o None si no hay ninguna.

    Se usa para no tener que mandar al LLM (ni fusionar en Python) la
    lista completa de "versiones", que crece con cada actualización: solo
    hace falta la foto más reciente del evento para fusionar el nuevo
    briefing sobre ella. Mandar el histórico completo era lo que hacía
    saltar el límite de tokens por minuto del free tier de Groq tras
    varias rondas de actualización sobre el mismo evento.

    Args:
        historial_anterior (dict | None): con la forma de
            crear_estructura_vacia_historico()

    Returns:
        dict | None: los 4 bloques de la versión más reciente, o None
    """
    if not historial_anterior:
        return None
    versiones = historial_anterior.get("versiones") or []
    if not versiones:
        return None
    return versiones[-1].get("datos") or None


# =====================================================================
# 4. GENERAR VALIDACIÓN Y AVISOS
# =====================================================================
def generar_aviso_y_validacion(datos, tipo_objetivo="evento", campos_objetivo=None):
    """
    Calcula una validacion contextual para la pantalla que invoca al agente.

    Para `tipo_objetivo="evento"` mantiene la validacion historica de campos
    obligatorios del evento. Para pantallas independientes como `cliente`, el
    agente solo informa de campos detectados/no detectados: no bloquea ni marca
    error por campos vacios. La validacion obligatoria antes de guardar pertenece
    al front/backend, no al agente.
    
    Args:
        datos (dict): Datos extraídos (debe contener la clave "evento")
    
    Returns:
        dict: Los mismos datos con las claves "_validacion" y "_aviso_agente" añadidas
    """
    tipo = _normalizar_tipo_objetivo(tipo_objetivo)
    campos = (
        _normalizar_campos_objetivo(campos_objetivo)
        or CAMPOS_OBJETIVO_DEFAULT.get(tipo, [])
    )

    if tipo != "evento":
        bloque = TIPO_OBJETIVO_A_BLOQUE.get(tipo, tipo)
        datos_bloque = datos.get(bloque, {})
        detectados = []
        no_detectados = []

        for campo in campos:
            if _campo_detectado_en_bloque(datos_bloque, campo):
                detectados.append(campo)
            else:
                no_detectados.append(campo)

        total = len(campos)
        porcentaje = int((len(detectados) / total) * 100) if total > 0 else 0

        datos["_validacion"] = {
            "tipo_objetivo": tipo,
            "campos_objetivo": campos,
            "campos_detectados": detectados,
            "campos_no_detectados": no_detectados,
            "porcentaje_completado": porcentaje,
            "campos_pendientes": []
        }
        datos["_aviso_agente"] = {
            "mensaje": (
                f"Autocompletado de {tipo}: {len(detectados)}/{total} "
                "campos detectados. Revisa la propuesta antes de guardar."
            )
        }
        return datos

    evento = datos.get("evento", {})
    
    completados = 0
    total = len(CAMPOS_OBLIGATORIOS_EVENTO)
    pendientes = []
    
    for campo in CAMPOS_OBLIGATORIOS_EVENTO:
        valor = evento.get(campo, "")
        if valor and str(valor).strip():
            completados += 1
        else:
            pendientes.append(campo)
    
    porcentaje = int((completados / total) * 100) if total > 0 else 0
    
    datos["_validacion"] = {
        "porcentaje_completado": porcentaje,
        "campos_pendientes": pendientes
    }
    
    if porcentaje == 100:
        datos["_aviso_agente"] = {
            "mensaje": "✅ Todos los campos obligatorios del evento han sido detectados."
        }
    else:
        faltan = len(pendientes)
        campos_texto = ", ".join(pendientes)
        datos["_aviso_agente"] = {
            "mensaje": f"⚠️ Faltan {faltan} campos obligatorios: {campos_texto}"
        }
    
    return datos


# =====================================================================
# 5. CONSTRUIR SALIDA BASE (CONTRATO CON BACKEND)
# =====================================================================
def construir_salida_base(datos_detectados, motor_usado, errores=None):
    """
    Construye la salida completa del agente siguiendo el contrato.
    
    Args:
        datos_detectados (dict): Datos extraídos (4 bloques)
        motor_usado (str): "llm" (único motor disponible)
        errores (list, optional): Lista de errores si los hay
    
    Returns:
        dict: Salida completa del agente
    """
    es_ok = errores is None or len(errores) == 0
    validacion = datos_detectados.get("_validacion", {})
    tipo_objetivo = validacion.get("tipo_objetivo", "evento")
    bloqueos = validacion.get("campos_pendientes", []) if tipo_objetivo == "evento" else []
    
    salida = {
        "ok": es_ok,
        "agente": "agente_operis",
        "tipo_peticion": "extraer_briefing",
        "tipo_objetivo": tipo_objetivo,
        "resumen": _generar_resumen(datos_detectados),
        "datos_detectados": datos_detectados,
        "acciones_propuestas": [],
        "bloqueos_detectados": bloqueos,
        "campos_objetivo": validacion.get("campos_objetivo", []),
        "campos_detectados": validacion.get("campos_detectados", []),
        "campos_no_detectados": validacion.get("campos_no_detectados", []),
        "borradores_generados": [],
        "requiere_validacion_humana": True,   # SIEMPRE True
        "nivel_riesgo": "bajo",               # SIEMPRE "bajo"
        "errores": errores or [],
        "trazas": {
            "fuentes_consultadas": [f"motor:{motor_usado}"],
            "timestamp": datetime.now().isoformat(),
            "modo": "propuesta"
        }
    }
    
    # Añadir campos de validación si existen
    if "_validacion" in datos_detectados:
        salida["_validacion"] = datos_detectados["_validacion"]
    if "_aviso_agente" in datos_detectados:
        salida["_aviso_agente"] = datos_detectados["_aviso_agente"]
    
    return salida


def _generar_resumen(datos):
    """
    Genera un resumen textual del estado de la extracción.
    
    Args:
        datos (dict): Datos detectados
    
    Returns:
        str: Resumen para el usuario
    """
    validacion = datos.get("_validacion", {})
    porcentaje = validacion.get("porcentaje_completado", 0)
    tipo_objetivo = validacion.get("tipo_objetivo", "evento")

    if tipo_objetivo != "evento":
        detectados = validacion.get("campos_detectados", [])
        objetivo = validacion.get("campos_objetivo", [])
        total = len(objetivo)
        return (
            f"Autocompletado de {tipo_objetivo}: "
            f"{len(detectados)}/{total} campos detectados. "
            "Requiere validacion humana antes de guardar."
        )
    
    # Contar bloques con información
    bloques_con_info = 0
    if datos.get("evento"):
        if any(v for v in datos["evento"].values() if v):
            bloques_con_info += 1
    if datos.get("cliente"):
        if any(v for v in datos["cliente"].values() if v):
            bloques_con_info += 1
    if datos.get("ponentes"):
        if datos["ponentes"]:
            bloques_con_info += 1
    if datos.get("nota_bene"):
        # Comprobar si hay algo en nota_bene
        nb = datos["nota_bene"]
        if nb.get("cabecera") and any(v for v in nb["cabecera"].values() if v):
            bloques_con_info += 1
    
    if porcentaje == 100:
        return f"✅ Evento completo. Información en {bloques_con_info} bloques. Requiere validación humana."
    elif porcentaje >= 50:
        return f"⚠️ Evento parcialmente completado ({porcentaje}%). Información en {bloques_con_info} bloques. Requiere revisión."
    else:
        return f"🔍 Extracción inicial ({porcentaje}%). Información en {bloques_con_info} bloques. Requiere completar campos."
