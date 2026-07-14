# src/nucleo.py
# =====================================================================
# NÚCLEO - LÓGICA PRINCIPAL DEL AGENTE OPERIS
# =====================================================================
# Punto de entrada ejecutar_agente(payload).
# Valida la entrada, elige el motor (ahora solo LLM), ejecuta la
# extracción, genera la validación y construye la salida.
#
# Cambios principales:
#   - Solo motor LLM (eliminado motor de reglas)
#   - Acepta historial_anterior en el contexto para modo actualización
#   - id_evento es opcional (si llega, permite usar historico)
#   - Acepta bloques_a_actualizar para actualización parcial
#   - NUEVO: la protección de bloques no actualizados y la continuidad
#     del histórico de cambios (nota_bene.informacion_adicional.
#     historico_actualizaciones) ya no dependen de que el LLM las
#     reproduzca bien -- se hacen aquí, en Python, a partir del último
#     estado conocido (ver _proteger_bloques_no_actualizados). Esto
#     también permite que src/llm.py mande solo la última versión del
#     histórico al modelo en vez de la lista completa de versiones, que
#     es lo que hacía saltar el límite de tokens por minuto del free
#     tier de Groq tras varias rondas de actualización.
# =====================================================================

from datetime import datetime
from src.validaciones import validar_entrada
from src.llm import extraer_briefing_llm
from src.schemas import (
    crear_estructura_vacia_completa,
    generar_aviso_y_validacion,
    construir_salida_base,
    extraer_ultimo_estado
)

BLOQUES_PRINCIPALES = ["evento", "cliente", "ponentes", "nota_bene"]
TIPO_OBJETIVO_A_BLOQUES = {
    "evento": ["evento"],
    "cliente": ["cliente"],
    "ponente": ["ponentes"],
    "ponentes": ["ponentes"],
}


# =====================================================================
# 1. FUNCIÓN PRINCIPAL
# =====================================================================
def ejecutar_agente(payload):
    """
    Punto de entrada único del agente Operis.
    
    Args:
        payload (dict): Contrato de entrada con los siguientes campos:
            - id_evento (str, optional): ID del evento para cargar historico si existe
            - id_registro (str, optional)
            - tipo_peticion (str): "extraer_briefing"
            - origen (str): "backend", "manual", etc.
            - usuario_solicitante (str)
            - rol_usuario (str)
            - datos (dict):
                - texto_briefing (str): Texto del briefing a procesar
                - motor (str, optional): "llm" (por defecto)
                - groq_api_key (str, optional): API key de Groq
                - bloques_a_actualizar (list, optional): Bloques a actualizar
            - contexto (dict, optional):
                - historial_anterior (dict, optional): Estado previo para actualización
                - modo_actualizacion (str, optional): "fusionar" (por defecto)
            - modo (str): "propuesta" (siempre)
    
    Returns:
        dict: Salida completa del agente siguiendo el contrato
    """
    try:
        # ----- 1. VALIDAR ENTRADA -----
        errores_validacion = validar_entrada(payload)
        if errores_validacion:
            return _construir_respuesta_error(errores_validacion)
        
        # ----- 2. EXTRAER DATOS DEL PAYLOAD -----
        datos_payload = payload.get("datos", {})
        texto = str(datos_payload.get("texto_briefing") or "").strip()
        motor = datos_payload.get("motor", "llm")
        api_key = datos_payload.get("groq_api_key")
        evento_id = payload.get("id_evento")
        historial_anterior = payload.get("contexto", {}).get("historial_anterior")
        modo_actualizacion = payload.get("contexto", {}).get("modo_actualizacion", "fusionar")
        tipo_objetivo = str(datos_payload.get("tipo_objetivo") or "evento").strip().lower() or "evento"
        campos_objetivo = datos_payload.get("campos_objetivo")
        if isinstance(campos_objetivo, str):
            campos_objetivo = [campo.strip() for campo in campos_objetivo.split(",") if campo.strip()]

        # Si quien llama no pasó contexto.historial_anterior explícito,
        # se intenta autocargar el estado ACTUAL del evento desde la BD
        # real (kit_conexion_agentes_Nora, ver src/lectura_bd.py) --
        # así el modo actualización funciona sin depender de que un
        # backend externo guarde y pase el histórico. Si la BD no está
        # disponible (sin DATABASE_URL, sin psycopg, o el evento no
        # existe todavía en la BD real), esto devuelve None sin fallar
        # -- se procesa igual, como una extracción inicial sin histórico.
        historial_desde_bd = False
        if not historial_anterior and evento_id:
            try:
                from src.lectura_bd import construir_historial_desde_bd
                historial_anterior = construir_historial_desde_bd(evento_id)
                historial_desde_bd = historial_anterior is not None
            except ImportError:
                historial_anterior = None
        
        # NUEVO: Extraer bloques_a_actualizar
        bloques_a_actualizar = datos_payload.get("bloques_a_actualizar")
        if isinstance(bloques_a_actualizar, str):
            bloques_a_actualizar = [bloque.strip() for bloque in bloques_a_actualizar.split(",") if bloque.strip()]
        if not bloques_a_actualizar:
            bloques_a_actualizar = TIPO_OBJETIVO_A_BLOQUES.get(tipo_objetivo)
        
        # ----- 3. VERIFICAR MOTOR (SOLO LLM) -----
        if motor != "llm":
            return _construir_respuesta_error(
                [f"Motor '{motor}' no soportado. El único motor disponible es 'llm'."]
            )
        
        # ----- 4. VERIFICAR TEXTO A PROCESAR -----
        if not texto:
            return _construir_respuesta_error(
                ["No se ha recibido texto para autocompletar. Envia texto, texto_briefing, contenido o datos.texto_briefing."]
            )
        
        # ----- 5. EJECUTAR EXTRACCIÓN CON LLM -----
        try:
            resultado = extraer_briefing_llm(
                texto=texto,
                api_key=api_key,
                historial_anterior=historial_anterior,
                bloques_a_actualizar=bloques_a_actualizar,
                tipo_objetivo=tipo_objetivo,
                campos_objetivo=campos_objetivo
            )
        except Exception as e:
            return _construir_respuesta_error(
                [f"Error en el motor LLM: {str(e)}"]
            )
        
        # ----- 6. PROTEGER BLOQUES NO ACTUALIZADOS -----
        # El LLM ya no es responsable de reproducir con exactitud los
        # bloques fuera de bloques_a_actualizar (ver src/llm.py): aquí se
        # sobreescriben directamente con el último estado conocido, sin
        # depender de que el modelo los haya copiado bien.
        estado_previo = extraer_ultimo_estado(historial_anterior)
        if estado_previo:
            resultado = _proteger_bloques_no_actualizados(
                resultado, estado_previo, bloques_a_actualizar
            )

        # ----- 7. GENERAR VALIDACIÓN Y AVISOS -----
        resultado = generar_aviso_y_validacion(
            resultado,
            tipo_objetivo=tipo_objetivo,
            campos_objetivo=campos_objetivo
        )

        # ----- 8. AÑADIR METADATOS DE ACTUALIZACIÓN -----
        if historial_anterior:
            # El histórico de cambios se construye a partir del último
            # estado conocido (estado_previo), no de lo que haya
            # devuelto el LLM: así no se pierde continuidad aunque el
            # bloque nota_bene no se haya enviado al modelo esta vez
            # (protegido) o el modelo no lo reproduzca fielmente.
            historico_previo = []
            if estado_previo:
                historico_previo = list(
                    estado_previo.get("nota_bene", {})
                                 .get("informacion_adicional", {})
                                 .get("historico_actualizaciones", []) or []
                )

            # El número de versión se basa en cuántas entradas tiene ya el
            # propio histórico de cambios (historico_previo), no en
            # cuántas "versiones" trae el wrapper de historial_anterior:
            # ese wrapper siempre tiene una única versión cuando el
            # histórico se autocarga desde la BD real (ver
            # src/lectura_bd.py::construir_historial_desde_bd), así que
            # contar sus versiones dejaría la numeración clavada en 2
            # para siempre en producción.
            if bloques_a_actualizar:
                cambios = f"Actualización de bloques: {', '.join(bloques_a_actualizar)}"
            else:
                cambios = "Actualización completa del briefing"

            historico_previo.append({
                "fecha": datetime.now().isoformat(),
                "cambios_detectados": cambios,
                "version": len(historico_previo) + 1
            })
            resultado["nota_bene"]["informacion_adicional"]["historico_actualizaciones"] = historico_previo

            # Actualizar timestamp
            resultado["nota_bene"]["cabecera"]["ultima_actualizacion"] = datetime.now().isoformat()

        # ----- 9. CONSTRUIR SALIDA BASE -----
        salida = construir_salida_base(
            datos_detectados=resultado,
            motor_usado="llm",
            errores=None
        )

        # Traza de transparencia: si el histórico se autocargó de la BD
        # real (en vez de venir explícito en el payload), que quede
        # constancia en trazas.fuentes_consultadas -- útil para depurar
        # por qué un bloque salió "protegido"/fusionado sin que quien
        # llamó pasara contexto.historial_anterior él mismo.
        if historial_desde_bd:
            salida["trazas"]["fuentes_consultadas"].append("bd:eventos(historial_anterior)")

        return salida
        
    except Exception as e:
        return _construir_respuesta_error([f"Error inesperado: {str(e)}"])


# =====================================================================
# 2. FUNCIONES AUXILIARES
# =====================================================================
def _proteger_bloques_no_actualizados(resultado, estado_previo, bloques_a_actualizar):
    """
    Sobreescribe con el estado previo (a nivel de código, no del LLM) los
    bloques que NO están en bloques_a_actualizar.

    Antes, la única forma de "proteger" un bloque era pedirle al LLM en
    el prompt que lo copiara literalmente del histórico -- caro en
    tokens (había que mandarle el bloque completo) y frágil (un LLM no
    siempre copia un JSON grande sin alterarlo). Ahora el LLM no necesita
    ni ver esos bloques con detalle: si no están en bloques_a_actualizar,
    el resultado final se toma directamente de estado_previo.

    Args:
        resultado (dict): salida de _fusionar_sobre_plantilla (lo que
            devolvió el LLM ya fusionado sobre la plantilla vacía)
        estado_previo (dict): últimos 4 bloques conocidos del evento
            (ver src/schemas.py::extraer_ultimo_estado)
        bloques_a_actualizar (list | None): si es None o vacío, se
            interpreta como "actualizar todo" y no se protege nada

    Returns:
        dict: resultado con los bloques protegidos reemplazados
    """
    if not bloques_a_actualizar:
        return resultado
    objetivo = set(bloques_a_actualizar)
    for bloque in BLOQUES_PRINCIPALES:
        if bloque not in objetivo and bloque in estado_previo:
            resultado[bloque] = estado_previo[bloque]
    return resultado


def _construir_respuesta_error(errores):
    """
    Construye una respuesta de error siguiendo el contrato de salida.
    
    Args:
        errores (list): Lista de mensajes de error
    
    Returns:
        dict: Salida de error del agente
    """
    datos_vacios = crear_estructura_vacia_completa()
    datos_vacios = generar_aviso_y_validacion(datos_vacios)
    
    return {
        "ok": False,
        "agente": "agente_operis",
        "tipo_peticion": "extraer_briefing",
        "resumen": "❌ Error en la extracción",
        "datos_detectados": datos_vacios,
        "acciones_propuestas": [],
        "bloqueos_detectados": [],
        "borradores_generados": [],
        "requiere_validacion_humana": True,
        "nivel_riesgo": "bajo",
        "errores": errores,
        "trazas": {
            "fuentes_consultadas": ["motor:llm"],
            "timestamp": datetime.now().isoformat(),
            "modo": "propuesta"
        },
        "_validacion": datos_vacios.get("_validacion", {}),
        "_aviso_agente": datos_vacios.get("_aviso_agente", {})
    }


# =====================================================================
# 3. EXPORTACIÓN EXPLÍCITA (PARA CONTRATO)
# =====================================================================
# Esta función es la que importa src/agente.py para exponer el contrato.
# No cambiar el nombre ni los argumentos.
__all__ = ["ejecutar_agente"]
