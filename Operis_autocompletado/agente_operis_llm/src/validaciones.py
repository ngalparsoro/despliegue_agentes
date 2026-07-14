# src/validaciones.py
# =====================================================================
# VALIDACIONES - CONTRATO DE ENTRADA DEL AGENTE OPERIS
# =====================================================================
# Valida que el payload recibido cumpla con el contrato de entrada.
#
# Cambios principales:
#   - id_evento es opcional: si llega se valida, si no llega se procesa sin historico de evento
#   - El motor solo puede ser "llm"
#   - Se valida que contexto.historial_anterior sea un dict si existe
#   - NUEVO: validación de bloques_a_actualizar (lista de bloques válidos)
# =====================================================================


# =====================================================================
# 1. CAMPOS OBLIGATORIOS DEL PAYLOAD
# =====================================================================
CAMPOS_OBLIGATORIOS = [
    "tipo_peticion",
    "origen",
    "usuario_solicitante",
    "rol_usuario",
    "datos",
    "contexto",
    "modo"
]

MODOS_VALIDOS = ["propuesta"]

TIPOS_PETICION_VALIDOS = ["extraer_briefing"]

MOTORES_VALIDOS = ["llm"]

# Bloques válidos para actualización parcial
BLOQUES_VALIDOS = ["evento", "cliente", "ponentes", "nota_bene"]


# =====================================================================
# 2. FUNCIÓN PRINCIPAL DE VALIDACIÓN
# =====================================================================
def validar_entrada(payload):
    """
    Valida que el payload cumpla con el contrato de entrada.
    
    Args:
        payload (dict): Payload recibido por el agente
    
    Returns:
        list: Lista de errores encontrados. Vacía si todo es correcto.
    """
    errores = []
    
    # ----- 1. VALIDAR CAMPOS OBLIGATORIOS DEL PAYLOAD -----
    for campo in CAMPOS_OBLIGATORIOS:
        if campo not in payload:
            errores.append(f"Falta el campo obligatorio: '{campo}'")
    
    # Si faltan campos obligatorios, no continuamos con validaciones más profundas
    if errores:
        return errores
    
    # ----- 2. VALIDAR id_evento (OPCIONAL; si llega, contra la BD real) -----
    id_evento = payload.get("id_evento")
    if id_evento is not None and str(id_evento).strip():
        # Verificación real, no solo de forma: si hay conexión a la BD
        # (kit_conexion_agentes_Nora, ver integrations/bd_backend.py),
        # se comprueba que el evento exista de verdad, no solo que la
        # cadena no esté vacía. Sin BD disponible (sin DATABASE_URL, o
        # sin psycopg instalado), se mantiene el comportamiento anterior
        # -- no se puede verificar, así que no se bloquea por esto.
        try:
            from integrations.bd_backend import bd_disponible
            from src.lectura_bd import evento_existe
            if bd_disponible() and not evento_existe(id_evento):
                errores.append(
                    f"id_evento '{id_evento}' no existe en la BD real. "
                    "El agente solo actualiza eventos ya creados por el backend."
                )
        except ImportError:
            pass  # psycopg no instalado: sin BD, no se puede verificar -- no se bloquea.

    # ----- 3. VALIDAR tipo_peticion -----
    tipo = payload.get("tipo_peticion")
    if tipo not in TIPOS_PETICION_VALIDOS:
        errores.append(f"tipo_peticion debe ser 'extraer_briefing'. Recibido: '{tipo}'")
    
    # ----- 4. VALIDAR modo -----
    modo = payload.get("modo")
    if modo not in MODOS_VALIDOS:
        errores.append(f"modo debe ser 'propuesta'. Recibido: '{modo}'")
    
    # ----- 5. VALIDAR datos -----
    datos = payload.get("datos", {})
    if not isinstance(datos, dict):
        errores.append("datos debe ser un diccionario")
    else:
        # 5.1 Validar texto si se proporciona.
        if "texto_briefing" in datos and datos["texto_briefing"] is not None:
            if not str(datos["texto_briefing"]).strip():
                errores.append("El campo 'datos.texto_briefing' no puede estar vacio si se proporciona")

        # 5.2 Validar motor (si existe)
        motor = datos.get("motor", "llm")
        if motor not in MOTORES_VALIDOS:
            errores.append(
                f"motor debe ser 'llm'. Recibido: '{motor}'. "
                f"El motor de reglas ha sido eliminado."
            )
        
        # 5.3 Validar groq_api_key (si existe, debe ser string no vacío)
        api_key = datos.get("groq_api_key")
        if api_key is not None and not isinstance(api_key, str):
            errores.append("datos.groq_api_key debe ser un string")
        elif api_key is not None and not api_key.strip():
            errores.append("datos.groq_api_key no puede estar vacío si se proporciona")
        
        # 5.4 NUEVO: Validar bloques_a_actualizar (si existe)
        bloques = datos.get("bloques_a_actualizar")
        if bloques is not None:
            if not isinstance(bloques, list):
                errores.append("datos.bloques_a_actualizar debe ser una lista")
            else:
                for bloque in bloques:
                    if bloque not in BLOQUES_VALIDOS:
                        errores.append(
                            f"Bloque '{bloque}' no válido. "
                            f"Opciones permitidas: {', '.join(BLOQUES_VALIDOS)}"
                        )
                # Verificar que no haya duplicados
                if len(bloques) != len(set(bloques)):
                    errores.append("datos.bloques_a_actualizar contiene duplicados")
    
    # ----- 6. VALIDAR contexto -----
    contexto = payload.get("contexto", {})
    if not isinstance(contexto, dict):
        errores.append("contexto debe ser un diccionario")
    else:
        # 6.1 Validar historial_anterior (si existe)
        historial = contexto.get("historial_anterior")
        if historial is not None:
            if not isinstance(historial, dict):
                errores.append("contexto.historial_anterior debe ser un diccionario")
            else:
                # Validar estructura mínima del histórico
                if "versiones" in historial and not isinstance(historial["versiones"], list):
                    errores.append("contexto.historial_anterior.versiones debe ser una lista")
                if "ultima_actualizacion" in historial and not isinstance(historial["ultima_actualizacion"], str):
                    errores.append("contexto.historial_anterior.ultima_actualizacion debe ser un string")
        
        # 6.2 Validar modo_actualizacion (si existe)
        modo_act = contexto.get("modo_actualizacion")
        if modo_act is not None and modo_act not in ["fusionar", "sobrescribir"]:
            errores.append(
                f"contexto.modo_actualizacion debe ser 'fusionar' o 'sobrescribir'. "
                f"Recibido: '{modo_act}'"
            )
    
    # ----- 7. VALIDAR usuario_solicitante -----
    usuario = payload.get("usuario_solicitante")
    if not usuario or not str(usuario).strip():
        errores.append("usuario_solicitante no puede estar vacío")
    
    # ----- 8. VALIDAR rol_usuario -----
    rol = payload.get("rol_usuario")
    if not rol or not str(rol).strip():
        errores.append("rol_usuario no puede estar vacío")
    
    # ----- 9. VALIDAR origen -----
    origen = payload.get("origen")
    if not origen or not str(origen).strip():
        errores.append("origen no puede estar vacío")
    
    return errores


# =====================================================================
# 3. FUNCIÓN DE VALIDACIÓN RÁPIDA (PARA PRUEBAS)
# =====================================================================
def es_payload_valido(payload):
    """
    Versión simplificada que devuelve True/False.
    
    Args:
        payload (dict): Payload a validar
    
    Returns:
        bool: True si es válido, False si no
    """
    errores = validar_entrada(payload)
    return len(errores) == 0


# =====================================================================
# 4. EXPORTACIÓN EXPLÍCITA
# =====================================================================
__all__ = ["validar_entrada", "es_payload_valido", "BLOQUES_VALIDOS"]
