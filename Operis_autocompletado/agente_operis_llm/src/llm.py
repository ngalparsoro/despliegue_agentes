# src/llm.py
# =====================================================================
# LLM - MOTOR DE EXTRACCIÓN CON GROQ
# =====================================================================
# Usa un LLM en Groq (openai/gpt-oss-120b) para rellenar el esquema de
# salida de 4 bloques (Evento, Cliente, Ponentes, Nota Bene).
#
# El prompt de sistema vive en prompts/prompt_sistema.md.
#
# Regla de oro: el LLM nunca debe inventar un dato. Si un campo no
# aparece explícitamente en el texto, su valor debe ser "" o [].
#
# Cambios principales:
#   - Nuevo parámetro bloques_a_actualizar para actualización parcial
#   - El prompt incluye instrucciones para proteger bloques no seleccionados
#   - Mejora en el procesamiento de nota_bene para garantizar que se rellene
# =====================================================================

import json
from pathlib import Path
from datetime import datetime

from config import settings
from src.schemas import (
    crear_estructura_vacia_completa,
    generar_aviso_y_validacion,
    extraer_ultimo_estado
)

BASE_DIR = Path(__file__).resolve().parent.parent
RUTA_PROMPT_SISTEMA = BASE_DIR / "prompts" / "prompt_sistema.md"


# =====================================================================
# 1. ESQUEMA DE SALIDA (4 BLOQUES)
# =====================================================================
# Mismo esquema que schemas.crear_estructura_vacia_completa().
# Si ese esquema cambia, actualizar aquí también.
ESQUEMA_SALIDA = {
    "evento": [
        "nombre_evento", "ciudad", "lugar_confirmado", "fecha_inicio",
        "fecha_fin", "numero_personas", "tipo_evento", "estado", "nota"
    ],
    "cliente": [
        "cliente", "empresa", "email", "telefono", "sector", "ciudad",
        "personas_contacto", "cliente_existente", "nota_cliente"
    ],
    "ponentes": [
        "nombre_ponente", "doc_identificacion", "email", "sector", "telefono",
        "foto_link", "cv_link", "empresa", "cargo", "nombre_hotel",
        "nota_transporte", "horario_ida_transporte", "horario_vuelta_transporte",
        "localizacion_hotel", "horario_ponencia", "checking_horario",
        "ponente_estado", "presentacion_link", "billete_ida_link",
        "billete_vuelta_link", "tipo_ponencias", "nota_ponente"
    ],
    "nota_bene": {
        "cabecera": [
            "nombre_evento", "estado_evento", "fecha_celebracion",
            "cliente_principal", "persona_contacto", "presupuesto_total_estimado",
            "ultima_actualizacion"
        ],
        "presupuesto_servicios": {
            "ubicacion": ["descripcion", "precio_estimado", "nota", "estado"],
            "catering": ["descripcion", "precio_estimado", "nota", "estado"],
            "audiovisuales": ["descripcion", "precio_estimado", "nota", "estado"],
            "otros": ["descripcion", "precio_estimado", "nota", "estado"]
        },
        "informacion_adicional": [
            "notas_generales", "requerimientos_especiales", "riesgos_detectados",
            "acciones_pendientes", "dependencias", "historico_actualizaciones"
        ]
    }
}


def _esquema_para_prompt():
    """
    Versión de ESQUEMA_SALIDA que se le enseña al LLM en el prompt: los
    mismos campos, pero con la FORMA real esperada (objetos con sus
    claves, listas de objetos donde corresponda) en vez de listas planas
    de nombres de campo.

    ESQUEMA_SALIDA guarda listas de nombres ("evento": ["nombre_evento",
    "ciudad", ...]) porque _fusionar_sobre_plantilla las usa para saber
    qué claves son válidas en cada bloque. Pero mandarle esa MISMA forma
    al LLM como "así debe verse tu respuesta" es ambiguo: en una prueba
    real, el modelo interpretó que el valor de "evento" debía ser ese
    array, y devolvió evento/cliente como listas de valores posicionales
    en vez de objetos -- lo que invalidó el JSON completo (error 400
    json_validate_failed). Aquí se construye la forma real (dict/list
    anidados) que sí se espera en la respuesta, reutilizando los mismos
    nombres de campo de ESQUEMA_SALIDA para no duplicarlos.
    """
    ps = ESQUEMA_SALIDA["nota_bene"]["presupuesto_servicios"]
    return {
        "evento": {campo: "" for campo in ESQUEMA_SALIDA["evento"]},
        "cliente": {
            "cliente": "", "empresa": "", "email": "", "telefono": "",
            "sector": "", "ciudad": "",
            "personas_contacto": [
                {"nombre": "", "cargo": "", "email": "", "telefono": "", "nota": ""}
            ],
            "cliente_existente": False,
            "nota_cliente": ""
        },
        "ponentes": [
            {campo: "" for campo in ESQUEMA_SALIDA["ponentes"]}
        ],
        "nota_bene": {
            "cabecera": {campo: "" for campo in ESQUEMA_SALIDA["nota_bene"]["cabecera"]},
            "presupuesto_servicios": {
                sub: {campo: "" for campo in campos} for sub, campos in ps.items()
            },
            "informacion_adicional": {
                "notas_generales": "",
                "requerimientos_especiales": "",
                "riesgos_detectados": "",
                "acciones_pendientes": [],
                "dependencias": [],
                "historico_actualizaciones": []
            }
        }
    }


# =====================================================================
# 2. CONSTRUCCIÓN DEL PROMPT DE SISTEMA
# =====================================================================
def construir_prompt_sistema(
    historial_anterior=None,
    bloques_a_actualizar=None,
    tipo_objetivo=None,
    campos_objetivo=None,
):
    """
    Carga prompts/prompt_sistema.md y le inserta el esquema de salida.

    Args:
        historial_anterior (dict, optional): histórico completo (ver
            src/schemas.py::crear_estructura_vacia_historico). Solo se usa
            la ÚLTIMA versión guardada (extraer_ultimo_estado): nunca se
            manda la lista completa de "versiones" al LLM, porque crece
            con cada ronda de actualización y era lo que hacía saltar el
            límite de tokens por minuto del free tier de Groq.
        bloques_a_actualizar (list, optional): Lista de bloques a
            actualizar. Ej: ["nota_bene"]. Los bloques que NO estén en
            esta lista no hace falta que el LLM los reproduzca con
            exactitud: src/nucleo.py los protege directamente a partir del
            último estado conocido, sin depender de que el modelo los
            copie bien (ver _proteger_bloques_no_actualizados).

    Returns:
        str: Prompt de sistema completo
    """
    plantilla = RUTA_PROMPT_SISTEMA.read_text(encoding="utf-8")

    # El "EJEMPLO COMPLETO" al final de prompt_sistema.md (marcado con
    # <!-- EJEMPLO_SOLO_SIN_HISTORIAL -->) solo aporta en extracciones en
    # frío: cuando hay histórico, el "ESTADO ACTUAL DEL EVENTO" de más
    # abajo ya es un ejemplo real y mejor del mismo esquema, así que el
    # ejemplo estático se recorta -- es la parte más pesada del prompt y
    # era lo que hacía saltar el límite de tokens por minuto del free
    # tier de Groq en actualizaciones con histórico.
    estado_actual = extraer_ultimo_estado(historial_anterior)
    cuerpo, _, ejemplo = plantilla.partition("<!-- EJEMPLO_SOLO_SIN_HISTORIAL -->")
    plantilla = cuerpo if estado_actual else (cuerpo + ejemplo)

    prompt = plantilla.replace(
        "{esquema}",
        json.dumps(_esquema_para_prompt(), ensure_ascii=False, indent=2)
    )

    # Si hay histórico, añadir solo la ÚLTIMA versión conocida como
    # contexto de fusión (nunca la lista completa de versiones).
    if estado_actual:
        prompt += f"""

# =====================================================================
# ESTADO ACTUAL DEL EVENTO (ÚLTIMA VERSIÓN CONOCIDA)
# =====================================================================

Este es el estado más reciente del briefing, antes de procesar el nuevo
texto. Úsalo como referencia para FUSIONAR, no para empezar de cero.

## Estado actual:
{json.dumps(estado_actual, ensure_ascii=False, indent=2)}

## INSTRUCCIONES DE FUSIÓN:

1. **Mantén** la información que ya existía y que el nuevo texto no contradice.
2. **Actualiza** solo lo que el nuevo texto modifique o añada.
3. **Nunca borres** información anterior a menos que el nuevo texto la
   contradiga explícitamente.
4. No hace falta que reproduzcas con precisión los bloques que no te pidan
   actualizar (ver más abajo): el sistema los mantiene intactos a partir
   del estado actual, independientemente de lo que devuelvas para ellos.
   Concentra el esfuerzo en los bloques que sí debes actualizar.

### Para el presupuesto total estimado:
Si hay cambio en el presupuesto, indícalo así:
"3200€ (anterior: 2500€)"
o
"3200€ (+700€ respecto a versión anterior)"

### Fechas de celebración:
Si el nuevo documento modifica las fechas, actualiza fecha_celebracion.

"""

    # Si hay bloques_a_actualizar, indicar cuáles son prioritarios.
    if bloques_a_actualizar:
        bloques_texto = ", ".join(bloques_a_actualizar)
        prompt += f"""

# =====================================================================
# BLOQUES A ACTUALIZAR
# =====================================================================

Presta atención especial y actualiza con el nuevo texto estos bloques:
**{bloques_texto}**

Para el resto de bloques no es necesario que los reproduzcas con
exactitud en tu respuesta: el sistema los protege directamente a partir
del estado actual mostrado arriba, tanto si los incluyes como si no.

"""
    elif estado_actual:
        prompt += """

# =====================================================================
# MODO ACTUALIZACIÓN COMPLETA
# =====================================================================

No se han especificado bloques concretos a actualizar. Actualiza todos
los bloques que el nuevo documento modifique, fusionando con el estado
actual mostrado arriba.

"""

    if tipo_objetivo:
        campos_texto = ", ".join(campos_objetivo or [])
        prompt += f"""

# =====================================================================
# PANTALLA OBJETIVO
# =====================================================================

Estas autocompletando la pantalla o entidad: **{tipo_objetivo}**.
Campos visibles que se intentan rellenar: **{campos_texto or "no especificados"}**.

Extrae solo informacion que aparezca en el texto. Si un campo no aparece,
dejalo vacio. No inventes datos y no trates los campos ausentes como error:
la aplicacion validara antes de guardar.

"""

    return prompt


# =====================================================================
# 3. FUSIÓN SOBRE PLANTILLA VACÍA
# =====================================================================
def _fusionar_sobre_plantilla(datos_llm):
    """
    Fusiona lo que devuelve el LLM sobre la plantilla vacía completa.
    
    Si el LLM omite un campo (pese a la instrucción), se queda en "".
    Esto asegura que la estructura siempre sea completa y no rompa el pipeline.
    
    Args:
        datos_llm (dict): JSON parseado que devolvió el LLM
    
    Returns:
        dict: Estructura completa con 4 bloques y sus sub-bloques
    """
    resultado = crear_estructura_vacia_completa()
    
    # ----- BLOQUE 1: EVENTO -----
    evento_llm = datos_llm.get("evento")
    if isinstance(evento_llm, dict):
        for campo in resultado["evento"]:
            valor = evento_llm.get(campo)
            if valor is not None and str(valor).strip():
                resultado["evento"][campo] = str(valor).strip()
    
    # ----- BLOQUE 2: CLIENTE -----
    cliente_llm = datos_llm.get("cliente")
    if isinstance(cliente_llm, dict):
        # Campos planos
        for campo in ["cliente", "empresa", "email", "telefono", "sector", "ciudad", "nota_cliente"]:
            valor = cliente_llm.get(campo)
            if valor is not None and str(valor).strip():
                resultado["cliente"][campo] = str(valor).strip()
        
        # cliente_existente (booleano)
        if "cliente_existente" in cliente_llm:
            valor = cliente_llm.get("cliente_existente")
            if isinstance(valor, bool):
                resultado["cliente"]["cliente_existente"] = valor
        
        # personas_contacto (lista)
        contactos_llm = cliente_llm.get("personas_contacto")
        if isinstance(contactos_llm, list):
            contactos = []
            claves_contacto = ["nombre", "cargo", "email", "telefono", "nota"]
            for contacto_llm in contactos_llm:
                if not isinstance(contacto_llm, dict):
                    continue
                contacto = {clave: "" for clave in claves_contacto}
                for clave in claves_contacto:
                    valor = contacto_llm.get(clave)
                    if valor is not None and str(valor).strip():
                        contacto[clave] = str(valor).strip()
                # Solo añadir si tiene al menos un campo con valor
                if any(contacto.values()):
                    contactos.append(contacto)
            resultado["cliente"]["personas_contacto"] = contactos
    
    # ----- BLOQUE 3: PONENTES -----
    ponentes_llm = datos_llm.get("ponentes")
    if isinstance(ponentes_llm, list):
        claves_ponente = ESQUEMA_SALIDA["ponentes"]
        ponentes = []
        for ponente_llm in ponentes_llm:
            if not isinstance(ponente_llm, dict):
                continue
            ponente = {clave: "" for clave in claves_ponente}
            for clave in claves_ponente:
                valor = ponente_llm.get(clave)
                if valor is not None and str(valor).strip():
                    ponente[clave] = str(valor).strip()
            # Solo añadir si tiene al menos un campo con valor
            if any(ponente.values()):
                ponentes.append(ponente)
        resultado["ponentes"] = ponentes
    
    # ----- BLOQUE 4: NOTA BENE -----
    nb_llm = datos_llm.get("nota_bene")

    if isinstance(nb_llm, dict):
        # 4.1 Cabecera
        cabecera_llm = nb_llm.get("cabecera")
        if isinstance(cabecera_llm, dict):
            for campo in ESQUEMA_SALIDA["nota_bene"]["cabecera"]:
                valor = cabecera_llm.get(campo)
                if valor is not None and str(valor).strip():
                    resultado["nota_bene"]["cabecera"][campo] = str(valor).strip()

        # 4.2 Presupuesto y servicios
        ps_llm = nb_llm.get("presupuesto_servicios")
        if isinstance(ps_llm, dict):
            for servicio in ["ubicacion", "catering", "audiovisuales", "otros"]:
                servicio_llm = ps_llm.get(servicio)
                if isinstance(servicio_llm, dict):
                    for campo in ESQUEMA_SALIDA["nota_bene"]["presupuesto_servicios"][servicio]:
                        valor = servicio_llm.get(campo)
                        if valor is not None and str(valor).strip():
                            resultado["nota_bene"]["presupuesto_servicios"][servicio][campo] = str(valor).strip()

        # 4.3 Información adicional
        ia_llm = nb_llm.get("informacion_adicional")
        if isinstance(ia_llm, dict):
            # Campos de texto planos
            for campo in ["notas_generales", "requerimientos_especiales", "riesgos_detectados"]:
                valor = ia_llm.get(campo)
                if valor is not None and str(valor).strip():
                    resultado["nota_bene"]["informacion_adicional"][campo] = str(valor).strip()

            # Listas
            for campo in ["acciones_pendientes", "dependencias"]:
                valor = ia_llm.get(campo)
                if isinstance(valor, list):
                    items = [str(v).strip() for v in valor if v and str(v).strip()]
                    if items:
                        resultado["nota_bene"]["informacion_adicional"][campo] = items

            # Histórico de actualizaciones
            historico_llm = ia_llm.get("historico_actualizaciones")
            if isinstance(historico_llm, list):
                historico = []
                claves_historico = ["fecha", "cambios_detectados", "version"]
                for entrada_llm in historico_llm:
                    if not isinstance(entrada_llm, dict):
                        continue
                    entrada = {clave: "" for clave in claves_historico}
                    for clave in claves_historico:
                        valor = entrada_llm.get(clave)
                        if valor is not None and str(valor).strip():
                            entrada[clave] = str(valor).strip()
                    if any(entrada.values()):
                        historico.append(entrada)
                resultado["nota_bene"]["informacion_adicional"]["historico_actualizaciones"] = historico

    # Red de seguridad: si tras procesar la respuesta del LLM la cabecera de
    # nota_bene sigue completamente vacía (el LLM omitió nota_bene, lo devolvió
    # como {} o con la cabecera incompleta), reconstruimos una cabecera mínima
    # a partir de Evento/Cliente en vez de dejarla en blanco.
    cabecera_vacia = not any(resultado["nota_bene"]["cabecera"].values())
    if cabecera_vacia and (datos_llm.get("evento") or datos_llm.get("cliente")):
        evento = datos_llm.get("evento") or {}
        cliente = datos_llm.get("cliente") or {}

        resultado["nota_bene"]["cabecera"]["nombre_evento"] = str(evento.get("nombre_evento") or "").strip()
        resultado["nota_bene"]["cabecera"]["estado_evento"] = str(evento.get("estado") or "").strip()
        if evento.get("fecha_inicio") and evento.get("fecha_fin"):
            resultado["nota_bene"]["cabecera"]["fecha_celebracion"] = f"{evento.get('fecha_inicio')} - {evento.get('fecha_fin')}"
        elif evento.get("fecha_inicio"):
            resultado["nota_bene"]["cabecera"]["fecha_celebracion"] = str(evento.get("fecha_inicio")).strip()
        resultado["nota_bene"]["cabecera"]["cliente_principal"] = str(cliente.get("cliente") or "").strip()
        contactos = cliente.get("personas_contacto")
        if isinstance(contactos, list) and contactos and isinstance(contactos[0], dict):
            resultado["nota_bene"]["cabecera"]["persona_contacto"] = str(contactos[0].get("nombre") or "").strip()

        # presupuesto_total_estimado y ultima_actualizacion se dejan vacíos:
        # los rellena el código/usuario, no esta red de seguridad.

    return resultado


# =====================================================================
# 4. FUNCIÓN PRINCIPAL DE EXTRACCIÓN
# =====================================================================
def extraer_briefing_llm(
    texto,
    api_key=None,
    model=None,
    historial_anterior=None,
    bloques_a_actualizar=None,
    tipo_objetivo=None,
    campos_objetivo=None,
):
    """
    Extrae la información del briefing usando un LLM en Groq.
    
    Args:
        texto (str): Texto completo del briefing
        api_key (str): Clave de API de Groq (opcional, usa .env si no se indica)
        model (str): Modelo de Groq a usar (opcional)
        historial_anterior (dict, optional): Estado anterior del briefing
            para modo actualización. Si se proporciona, se fusiona con el nuevo.
        bloques_a_actualizar (list, optional): Bloques a actualizar.
            Ej: ["nota_bene"]. Si es None, actualiza todo.
    
    Returns:
        dict: Estructura completa con 4 bloques (Evento, Cliente, Ponentes, Nota Bene)
    
    Raises:
        ImportError: si el paquete `groq` no está instalado
        ValueError: si falta GROQ_API_KEY, o si el LLM devuelve JSON inválido
    """
    try:
        from groq import Groq
    except ImportError:
        raise ImportError(
            "El motor LLM requiere el paquete 'groq'. Instálalo con: "
            "pip install groq"
        )
    
    api_key = api_key or settings.GROQ_API_KEY
    if not api_key:
        raise ValueError(
            "Falta GROQ_API_KEY. Defínela en .env o pásala como argumento."
        )
    
    cliente_groq = Groq(api_key=api_key)
    
    # Construir prompt con histórico y bloques a actualizar
    prompt_sistema = construir_prompt_sistema(
        historial_anterior=historial_anterior,
        bloques_a_actualizar=bloques_a_actualizar,
        tipo_objetivo=tipo_objetivo,
        campos_objetivo=campos_objetivo
    )
    
    respuesta = cliente_groq.chat.completions.create(
        model=model or settings.GROQ_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": texto},
        ],
    )
    
    contenido = respuesta.choices[0].message.content
    
    try:
        datos_llm = json.loads(contenido)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"El LLM devolvió un JSON inválido: {e}\n"
            f"Contenido recibido: {contenido[:500]}..."
        )
    
    # Fusionar sobre plantilla vacía
    resultado = _fusionar_sobre_plantilla(datos_llm)
    
    # Añadir validación y avisos
    resultado = generar_aviso_y_validacion(
        resultado,
        tipo_objetivo=tipo_objetivo or "evento",
        campos_objetivo=campos_objetivo
    )
    
    # Si hay histórico anterior, añadir timestamp de actualización
    if historial_anterior:
        resultado["nota_bene"]["cabecera"]["ultima_actualizacion"] = datetime.now().isoformat()
    
    return resultado
