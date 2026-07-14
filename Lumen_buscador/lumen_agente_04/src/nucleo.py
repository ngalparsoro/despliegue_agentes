"""
Punto de entrada comun de Lumen (Agente 04 - Copilot).

Lo usan main.py (local) y servidor.py (API HTTP para el frontend), ya sea por import directo o
por una futura API. La firma de ejecutar_agente(payload) -> dict es el unico
contrato que NO puede cambiar (ver README.md, seccion 1).

Motor de LLM: Groq (ver src/llm.py). Si no hay API key configurada en .env, o si el LLM falla,
este modulo cae siempre a reglas deterministas - Lumen nunca debe quedarse sin responder.

Clasificador LLM de respaldo (prompts/prompt_clasificar_consulta.md): la clasificacion de
preguntas transversales/estado sigue siendo determinista por palabras clave (seccion 1 y
SINONIMOS_ESTADO_EVENTO) y es SIEMPRE lo primero que se intenta. El LLM solo entra en juego
como respaldo, y unicamente cuando: (a) la pregunta no trae id_evento, y (b) ninguna regla
determinista reconocio nada en ella. En ese caso, y solo en ese caso, se le pide al LLM UNA
etiqueta de una lista cerrada de 6 categorias (nunca SQL, nunca datos) para intentar rescatar
preguntas formuladas de una forma que las palabras clave no cubren. Ver
_responder_con_clasificador_respaldo() y README.md para el detalle y las garantias de seguridad.
"""

import json
import re
import unicodedata

from config.permisos import ALLOW_DB_WRITE
from config.settings import SETTINGS
from src.schemas import validar_entrada, construir_salida_base
from src.lectura_datos import (
    TablaNoPermitida,
    resumen_evento,
    ponentes_sin_billete_vuelta,
    ponentes_sin_billete_ida,
    contexto_completo_evento,
    estados_disponibles,
    eventos_por_estado,
    todos_los_eventos,
)
from src.validaciones import auditar_salida
from src.prompts import cargar_prompt
from src.llm import llamar_llm, llm_disponible
from integrations.db_backend import DbBackendError

# Defensa en profundidad: si alguna vez esto no fuera False, preferimos que el agente no arranque
# a que escriba en la BD por error.
assert ALLOW_DB_WRITE is False, "Lumen nunca debe tener ALLOW_DB_WRITE=True."

NOMBRE_AGENTE = "lumen_copilot"

PALABRAS_ESCRITURA = [
    "modifica", "modificar", "actualiza", "actualizar", "borra", "borrar", "elimina", "eliminar",
    "aprueba", "aprobar", "confirma", "confirmar", "sube el presupuesto", "crea un evento",
    "crear evento", "cambia la fecha", "reserva",
]
PALABRAS_USUARIOS = ["usuarios", "contraseña", "password", "credencial", "credenciales"]

# --- Consultas transversales por estado de evento (sin id_evento) --------------------------
# Catalogo real de `public.estados` actualizado el 14/07/2026:
# 0. Planificado -> evento creado en la app; lo activa el boton "crear evento".
# 1. Reservado   -> sala/espacio seleccionado o reservado; lo activa "Reservar lugar".
# 2. Confirmado  -> cliente acepta lugar y presupuesto; requiere "confirmar lugar" +
#                  "confirmar presupuesto".
# 3. Finalizado  -> evento ya celebrado; no tiene boton, se activa el dia posterior al evento.
# 4. Cancelado   -> evento no se realiza; lo activa "Cancelar evento" con doble validacion.
#
# Las claves de SINONIMOS_ESTADO_EVENTO deben coincidir EXACTAMENTE con estados.descripcion,
# porque lectura_datos.eventos_por_estado compara por igualdad contra la BD. Los nombres antiguos
# se conservan solo como sinonimos para que Lumen entienda preguntas formuladas con el catalogo
# previo o con etiquetas del prototipo. El dict prioriza "Reservado" antes que "Planificado" para
# que "pre-reservado" no se confunda con "pre-evento" por la tolerancia a errores tipograficos.
SINONIMOS_ESTADO_EVENTO = {
    "Reservado": [
        "reservado", "reservados", "reservada", "reservadas", "reservar lugar",
        "lugar reservado", "sala reservada", "espacio reservado", "con sala", "con espacio",
        "pre-reservado", "pre reservado", "pre-reserva", "pre reserva", "presupuestado",
        "presupuestados", "con presupuesto", "pendiente de aprobacion",
        "pendientes de aprobacion", "por aprobar", "pendiente", "pendientes", "por confirmar",
    ],
    "Planificado": [
        "planificado", "planificados", "planificada", "planificadas", "en planificacion",
        "en planificación", "fase inicial", "creado", "creados", "evento creado",
        "crear evento", "pre-evento", "pre evento", "borrador", "borradores", "en borrador",
    ],
    "Confirmado": [
        "confirmado", "confirmados", "confirmada", "confirmadas", "cerrado", "cerrados",
        "pre-confirmado", "pre confirmado", "lugar confirmado", "presupuesto confirmado",
        "confirmar lugar", "confirmar presupuesto", "lugar y presupuesto aceptados",
        "cliente acepta lugar", "cliente acepta presupuesto",
    ],
    "Finalizado": [
        "finalizado", "finalizados", "finalizada", "finalizadas", "celebrado", "celebrados",
        "celebrada", "celebradas", "terminado", "terminados", "terminada", "terminadas",
        "facturado", "facturados", "facturada", "facturadas", "evento celebrado",
    ],
    "Cancelado": ["cancelado", "cancelados", "cancelada", "canceladas"],
}

# Se deriva de SINONIMOS_ESTADO_EVENTO en vez de mantener una lista aparte a mano. Asi cualquier
# sinonimo nuevo que se añada al catalogo queda reconocido automaticamente como consulta por estado.
PALABRAS_TRANSVERSAL_ESTADO = ["estado"]
for _sinonimos in SINONIMOS_ESTADO_EVENTO.values():
    PALABRAS_TRANSVERSAL_ESTADO.extend(_sinonimos)

# Preguntas transversales que NO piden un estado concreto, solo un conteo o listado general
# ("cuantos eventos tenemos", "que eventos hay", "listame los eventos"...).
PALABRAS_TRANSVERSAL_GENERAL = [
    "cuantos", "cuantas", "todos los eventos", "lista de eventos", "listar eventos",
    "listame los eventos", "que eventos hay", "numero de eventos", "total de eventos",
]

# Preguntas que piden la LISTA de estados posibles (no un estado concreto, y sin mencionar
# "evento" necesariamente - "¿que estados hay?" es inequivoco en este dominio).
PALABRAS_LISTAR_ESTADOS = [
    "que estados hay", "estados hay", "estados existen", "estados disponibles",
    "lista de estados", "listar estados", "listado de estados", "que estados existen",
]

# --- Clasificador LLM de respaldo (prompts/prompt_clasificar_consulta.md) --------------------
# Enum cerrado tal cual lo define el prompt - si el LLM devuelve cualquier otra cosa (o texto
# libre en vez de una de estas 6 categorias), no se adivina: se trata como si no hubiese
# respondido nada util y la pregunta sigue el mismo camino que antes de conectar este respaldo.
CATEGORIAS_CLASIFICACION_VALIDAS = {
    "consulta_datos_evento",
    "consulta_metricas_globales",
    "aclaracion_necesaria",
    "fuera_de_alcance_escritura",
    "fuera_de_alcance_usuarios",
    "no_relacionada",
}

# Activado por defecto. Se puede desactivar sin tocar codigo con CLASIFICADOR_LLM_RESPALDO=false
# en .env - por ejemplo para pruebas que exigen determinismo total en cada ejecucion.
CLASIFICADOR_LLM_RESPALDO_ACTIVO = (
    SETTINGS.get("CLASIFICADOR_LLM_RESPALDO", "true") or "true"
).strip().lower() not in ("false", "0", "no")


def _normalizar(texto):
    """minusculas, sin acentos, sin guiones/underscores -> facilita comparar frases del usuario."""
    texto = texto.strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.replace("-", " ").replace("_", " ")
    return " ".join(texto.split())


# --- Tolerancia a errores tipograficos en las palabras clave de estado -----------------------
# Solo se aplica aqui (listas de estado/transversal), NUNCA a PALABRAS_ESCRITURA ni
# PALABRAS_USUARIOS - esos bloqueos de seguridad se quedan en coincidencia exacta a proposito.
# Motivo real: "dime los eventos prendientes de aprobacion" (typo de "pendientes") no reconocia
# ningun estado y caia al mensaje generico de "necesito mas contexto".
#
# Umbral elegido tras probar con un vocabulario de control: distancia de edicion <= 1 (una sola
# letra insertada/borrada/cambiada) y solo en palabras de 6+ letras. Con un umbral mas laxo
# (ratio de difflib) aparecian falsos positivos reales entre palabras DISTINTAS que comparten
# raiz, p.ej. "presupuesto" ~ "presupuestado" o "cancelar" ~ "cancelado" - cosas que no deben
# confundirse. Con distancia de edicion <= 1 esos casos se rechazan y los typos genuinos
# ("confimados", "canceladoss", "prendientes") se siguen reconociendo.
LONGITUD_MINIMA_TYPO = 6
DISTANCIA_MAXIMA_TYPO = 1


def _distancia_edicion(a, b):
    """Distancia de Levenshtein simple (DP), suficiente para palabras sueltas cortas."""
    m, n = len(a), len(b)
    fila = list(range(n + 1))
    for i in range(1, m + 1):
        anterior, fila[0] = fila[0], i
        for j in range(1, n + 1):
            temp = fila[j]
            fila[j] = anterior if a[i - 1] == b[j - 1] else 1 + min(anterior, fila[j], fila[j - 1])
            anterior = temp
    return fila[n]


def _palabra_aproximada(palabra, tokens):
    """True si `palabra` esta literal en `tokens`, o (solo si tiene 6+ letras) si algun token de
    la pregunta esta a distancia de edicion <= 1 - tolera un typo de una letra, no mas."""
    if palabra in tokens:
        return True
    if len(palabra) < LONGITUD_MINIMA_TYPO:
        return False
    for token in tokens:
        if abs(len(token) - len(palabra)) <= DISTANCIA_MAXIMA_TYPO and \
                _distancia_edicion(palabra, token) <= DISTANCIA_MAXIMA_TYPO:
            return True
    return False


def _frase_aproximada(frase_normalizada, texto_normalizado, tokens):
    """True si la frase completa aparece literal (caso comun, rapido), o si CADA palabra de la
    frase tiene una coincidencia exacta o aproximada (typo de una letra) en la pregunta."""
    if frase_normalizada in texto_normalizado:
        return True
    return all(_palabra_aproximada(p, tokens) for p in frase_normalizada.split())


def _parece_consulta_transversal_eventos(pregunta_lower):
    """
    True si la pregunta pinta a una consulta transversal sobre eventos (por estado, o un
    conteo/listado general), sin referirse a un evento concreto por id_evento.

    "estado"/"estados" dispara esta rama aunque la pregunta no diga "evento" explicitamente
    ("¿que estados hay?") - en este dominio un "estado" siempre es un estado de evento, no hay
    ambiguedad. El resto de disparadores si exigen la palabra "evento" para no reaccionar a
    preguntas sueltas sin relacion con la plataforma.
    """
    texto = _normalizar(pregunta_lower)
    tokens = texto.split()
    if any(_frase_aproximada(_normalizar(p), texto, tokens) for p in PALABRAS_LISTAR_ESTADOS) or "estado" in pregunta_lower:
        return True
    if "evento" not in pregunta_lower:
        return False
    todas = PALABRAS_TRANSVERSAL_ESTADO + PALABRAS_TRANSVERSAL_GENERAL
    return any(_frase_aproximada(_normalizar(p), texto, tokens) for p in todas)


def _detectar_estado_pedido(pregunta_lower):
    """
    Intenta mapear la frase del usuario a uno de los estados reales de la tabla `estados`.
    Devuelve (estado_canonico, True) si hay coincidencia, o (None, False) si no se reconoce
    ningun estado - Lumen no adivina un estado que no existe en los datos.
    """
    texto = _normalizar(pregunta_lower)
    tokens = texto.split()
    for estado_canonico, sinonimos in SINONIMOS_ESTADO_EVENTO.items():
        for sinonimo in sinonimos:
            if _frase_aproximada(_normalizar(sinonimo), texto, tokens):
                return estado_canonico, True
    return None, False


def buscar_evento_por_nombre(pregunta):
    """
    Intenta resolver a que evento se refiere la pregunta por su NOMBRE, no por id_evento.

    Los id reales de la BD son UUID (ver data/rag/documentos/esquema_bd.md) - nadie los escribe a
    mano en una conversacion normal. En la practica el usuario nombra el evento ("dime la fecha
    del evento Congreso Energia"), y sin esta resolucion esa pregunta caia siempre al mensaje
    generico de "necesito el id_evento" aunque el nombre estuviera ahi mismo, en la pregunta.

    Se llama desde src/memoria.py (antes de construir el payload), no desde ejecutar_agente: hace
    falta leer todos_los_eventos() de la BD para comparar nombres, y ejecutar_agente recibe el
    id_evento ya resuelto por contrato (README.md, seccion 1).

    Devuelve (id_evento, nombres_ambiguos):
      - (id, []) si el nombre de EXACTAMENTE un evento aparece en la pregunta.
      - (None, [nombre1, nombre2, ...]) si aparece mas de uno - no se adivina cual, se devuelven
        los nombres en conflicto para que la capa de chat pida aclaracion.
      - (None, []) si ningun nombre de evento aparece en la pregunta (no es un fallo: la mayoria
        de preguntas de seguimiento, "¿y su presupuesto?", tampoco nombran ningun evento).
    """
    texto = _normalizar(pregunta)
    try:
        eventos = todos_los_eventos() or []
    except (TablaNoPermitida, DbBackendError):
        # Si la BD falla aqui, no bloqueamos la resolucion: se deja caer al flujo normal
        # (memoria / id_evento explicito / fallback), que ya sabe manejar el fallo de la BD.
        return None, []

    coincidencias = [
        evento for evento in eventos
        if evento.get("nombre_evento") and _normalizar(evento["nombre_evento"]) in texto
    ]

    if len(coincidencias) > 1:
        # Un nombre corto que es prefijo/substring de otro nombre coincidente ("Congreso Energia"
        # dentro de "Congreso Energia Renovable") no es una ambiguedad real: si el usuario escribio
        # el nombre largo, se queda solo con las coincidencias mas especificas (no substring de
        # ninguna otra coincidencia) en vez de pedir aclaracion sin necesidad.
        nombres_norm = [_normalizar(e["nombre_evento"]) for e in coincidencias]
        coincidencias = [
            e for e, nombre in zip(coincidencias, nombres_norm)
            if not any(nombre != otro and nombre in otro for otro in nombres_norm)
        ]

    if len(coincidencias) == 1:
        return coincidencias[0].get("id"), []
    if len(coincidencias) > 1:
        return None, [e.get("nombre_evento") for e in coincidencias]
    return None, []


def ejecutar_agente(payload):
    """
    Punto de entrada comun del agente Lumen.
    Lo usan el main.py local, servidor.py o una futura API.
    """
    errores_entrada = validar_entrada(payload)
    salida = construir_salida_base(NOMBRE_AGENTE, payload.get("tipo_peticion", "desconocido"))

    if errores_entrada:
        salida["ok"] = False
        salida["errores"] = errores_entrada
        salida["resumen"] = "No se pudo procesar la peticion: faltan campos obligatorios."
        return auditar_salida(salida)

    pregunta = (payload.get("datos") or {}).get("pregunta", "")
    pregunta = pregunta.strip()
    pregunta_lower = pregunta.lower()
    id_evento = payload.get("id_evento")
    # Historial opcional de la conversacion (lo rellena la capa de chat: main.py o servidor.py). No es
    # memoria propia de ejecutar_agente -- sigue siendo stateless, el llamador es quien recuerda
    # turnos anteriores y los pasa aqui en cada llamada. Solo se usa para resolver referencias del
    # lenguaje ("ese evento", "su presupuesto") cuando la pregunta pasa por el LLM.
    historial = (payload.get("contexto") or {}).get("historial_conversacion")

    # --- 1. Clasificacion (equivalente a prompts/prompt_clasificar_consulta.md) --------------
    if _contiene_alguna(pregunta_lower, PALABRAS_USUARIOS):
        salida["resumen"] = (
            "Esa consulta esta fuera de mi alcance: no tengo acceso a la tabla 'usuarios' ni a "
            "credenciales de la plataforma."
        )
        salida["bloqueos_detectados"] = ["consulta sobre tabla usuarios / credenciales"]
        salida["nivel_riesgo"] = "alto"
        salida["requiere_validacion_humana"] = True
        return auditar_salida(salida)

    if _contiene_alguna(pregunta_lower, PALABRAS_ESCRITURA):
        salida["resumen"] = (
            "No puedo modificar, aprobar ni borrar datos - solo consulto informacion existente. "
            "Esa accion queda fuera de mi alcance y requiere validacion humana."
        )
        salida["bloqueos_detectados"] = ["la peticion implica una escritura, fuera del alcance de Lumen"]
        salida["nivel_riesgo"] = "medio"
        salida["requiere_validacion_humana"] = True
        return auditar_salida(salida)

    if id_evento is None and ("billete" in pregunta_lower or "ponente" in pregunta_lower):
        salida["resumen"] = "De que evento (id_evento) necesitas consultar esa informacion?"
        salida["bloqueos_detectados"] = ["falta id_evento para resolver la consulta"]
        return auditar_salida(salida)

    # --- 2. Consulta de solo lectura (BD real, integrations/db_backend.py) -------------------
    # TablaNoPermitida y DbBackendError pueden saltar en cualquiera de estas ramas (incluida
    # la transversal, que tambien lee eventos de la BD) - de ahi que todas vivan dentro del
    # mismo try.
    try:
        if id_evento is None and _parece_consulta_transversal_eventos(pregunta_lower):
            return _responder_consulta_transversal_eventos(salida, pregunta_lower)

        if id_evento is not None and "billete" in pregunta_lower and "vuelta" in pregunta_lower:
            return _responder_ponentes_sin_billete(salida, id_evento, "vuelta")

        if id_evento is not None and "billete" in pregunta_lower and "ida" in pregunta_lower:
            return _responder_ponentes_sin_billete(salida, id_evento, "ida")

        if id_evento is not None:
            # Preguntas libres sobre un evento (presupuesto, sala, espacio, cliente...): si hay
            # LLM configurado, se responde con el prompt de generacion sobre el contexto real
            # del evento. Si el LLM no esta disponible o falla, cae al resumen determinista.
            if llm_disponible():
                resultado_llm = _responder_con_llm(salida, pregunta, id_evento, historial)
                if resultado_llm is not None:
                    return resultado_llm
            return _responder_resumen_evento(salida, id_evento)

        # --- 2.5 Respaldo: clasificador LLM (prompts/prompt_clasificar_consulta.md) ----------
        # Solo se llega aqui si id_evento es None Y ninguna regla determinista de arriba
        # reconocio nada (ni bloqueo de seguridad, ni billete/ponente, ni transversal). Es un
        # respaldo, no un reemplazo: la clasificacion por palabras clave sigue siendo lo primero
        # que se intenta siempre, y si esta desactivada o falla, el comportamiento es identico
        # al de antes de conectar este respaldo (cae a la seccion 3, mensaje fijo).
        if CLASIFICADOR_LLM_RESPALDO_ACTIVO and llm_disponible():
            resultado_respaldo = _responder_con_clasificador_respaldo(
                salida, pregunta, pregunta_lower, historial
            )
            if resultado_respaldo is not None:
                return resultado_respaldo

    except TablaNoPermitida as exc:
        salida["ok"] = False
        salida["resumen"] = "No puedo acceder a esa informacion: esta fuera de mi alcance de consulta."
        salida["bloqueos_detectados"] = [str(exc)]
        salida["nivel_riesgo"] = "alto"
        salida["requiere_validacion_humana"] = True
        return auditar_salida(salida)

    except DbBackendError as exc:
        # Fallo de la conexion directa a la BD real (fallo de red, credenciales o consulta) -
        # tampoco se confunde con "el dato no existe".
        salida["ok"] = False
        salida["resumen"] = (
            "No he podido consultar la base de datos real ahora mismo, asi que no puedo "
            "confirmar este dato con seguridad."
        )
        salida["bloqueos_detectados"] = ["fallo de la base de datos real: " + str(exc)]
        salida["nivel_riesgo"] = "medio"
        salida["requiere_validacion_humana"] = True
        return auditar_salida(salida)

    # --- 3. Sin id_evento y sin patron reconocido: nada en el dominio de Lumen encaja --------
    # A diferencia de la linea 286 (falta id_evento pero SI se reconoce el tema: billete/ponente),
    # aqui no se reconocio ningun tema de la plataforma en absoluto -- lo mas probable es que la
    # pregunta sea sobre algo que sencillamente no esta en la base de datos de Mitumi (clima,
    # cultura general, otra empresa...). Respuesta fija y literal, a proposito: no se redacta con
    # variaciones para que sea facil de reconocer en pruebas y en la documentacion (ver README).
    salida["resumen"] = "Esa información no está en Mitumi. Reformula tu consulta."
    salida["bloqueos_detectados"] = ["pregunta fuera del alcance de datos de Mitumi"]
    return auditar_salida(salida)


def _contiene_alguna(texto, palabras):
    """
    Coincidencia por palabra completa (no subcadena). Bug real detectado al probar
    "¿qué eventos están confirmados?": con "in" simple, "confirma" (de PALABRAS_ESCRITURA)
    hacia falso positivo dentro de "confirmados" y bloqueaba una pregunta de solo lectura
    legitima como si fuese una escritura. Con \\b esto ya no ocurre, y "confirma el pedido"
    sigue detectandose igual que antes.
    """
    for palabra in palabras:
        if re.search(r"\b" + re.escape(palabra) + r"\b", texto):
            return True
    return False


def _responder_ponentes_sin_billete(salida, id_evento, tipo):
    obtener = ponentes_sin_billete_vuelta if tipo == "vuelta" else ponentes_sin_billete_ida
    resultado = obtener(id_evento)

    if resultado is None:
        salida["resumen"] = "No encuentro el evento con id_evento " + str(id_evento) + " en los datos disponibles."
        salida["bloqueos_detectados"] = ["id_evento " + str(id_evento) + " no existe en los datos"]
        return auditar_salida(salida)

    nombres = [p["nombre_ponente"] for p in resultado]
    if nombres:
        salida["resumen"] = (
            "El evento " + str(id_evento) + " tiene " + str(len(nombres)) +
            " ponente(s) sin billete de " + tipo + ": " + ", ".join(nombres) + "."
        )
    else:
        salida["resumen"] = (
            "Todos los ponentes del evento " + str(id_evento) +
            " tienen su billete de " + tipo + " registrado."
        )

    salida["datos_detectados"] = {"ponentes_sin_billete_" + tipo: nombres}
    salida["trazas"]["fuentes_consultadas"] = [
        "ponencias.billete_" + tipo + "_link",
        "ponentes.nombre_ponente",
    ]
    return auditar_salida(salida)


def _parsear_json_llm(texto):
    """
    El LLM deberia devolver SOLO JSON, pero a veces lo envuelve en ```json ... ``` o le añade
    texto alrededor. Se limpia el envoltorio antes de json.loads para no caer al fallback
    determinista por un simple formato: ese era el "Expecting value: line 1 column 1 (char 0)"
    que aparecia cuando la respuesta venia con fences de markdown o llegaba vacia.
    """
    if not texto or not texto.strip():
        raise ValueError("respuesta vacia del LLM")
    t = texto.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t).strip()
    inicio, fin = t.find("{"), t.rfind("}")
    if inicio != -1 and fin != -1 and fin > inicio:
        t = t[inicio:fin + 1]
    return json.loads(t)


def _responder_con_llm(salida, pregunta, id_evento, historial=None):
    """
    Responde una pregunta libre sobre un evento usando el LLM (Groq) y el contexto real
    recuperado por src/lectura_datos.py. Devuelve None si el LLM falla o no es utilizable,
    para que el llamador haga fallback a la respuesta determinista.

    `historial` (opcional) es una lista de turnos previos [{"pregunta":..., "resumen":...}, ...]
    que la capa de chat (main.py o servidor.py) mantiene entre llamadas. ejecutar_agente sigue siendo
    stateless: no guarda nada el mismo, solo usa lo que le pasan en este turno para que el LLM
    pueda resolver referencias como "ese evento" o "su presupuesto".

    Nota de seguridad: el LLM solo ve el JSON de contexto_completo_evento(), que ya excluye
    `usuarios` a nivel de codigo. Aunque el LLM alucinase o el usuario intentase manipular el
    prompt, auditar_salida() vuelve a filtrar cualquier mencion a usuarios/credenciales antes de
    devolver la respuesta.
    """
    contexto = contexto_completo_evento(id_evento)
    if contexto is None:
        salida["resumen"] = "No encuentro el evento con id_evento " + str(id_evento) + " en los datos disponibles."
        salida["bloqueos_detectados"] = ["id_evento " + str(id_evento) + " no existe en los datos"]
        return auditar_salida(salida)

    historial_texto = "(sin historial previo en esta sesion)"
    if historial:
        lineas = []
        for turno in historial[-6:]:
            lineas.append("Usuario: " + str(turno.get("pregunta", "")))
            lineas.append("Lumen: " + str(turno.get("resumen", "")))
        historial_texto = "\n".join(lineas)

    try:
        prompt_sistema = cargar_prompt("prompt_sistema.md")
        prompt_generar = cargar_prompt("prompt_generar_respuesta.md")
        # Se rellenan los placeholders {{...}} de prompt_generar_respuesta.md con los valores reales.
        # Antes se enviaba la plantilla con los {{...}} SIN sustituir y ademas se anadian los mismos
        # datos aparte, duplicados. La tabla usuarios ya viene excluida de `contexto`
        # (contexto_completo_evento) y auditar_salida vuelve a filtrarla, asi que no hace falta
        # recordarselo al modelo aqui.
        mensaje = (
            prompt_generar
            .replace("{{consulta_usuario}}", pregunta)
            .replace("{{categoria_de_prompt_clasificar_consulta}}", "consulta_datos_evento")
            .replace("{{resultado_consulta_bd_o_rag}}", json.dumps(contexto, ensure_ascii=False))
            .replace("{{turnos_previos_de_esta_sesion_de_chat_opcional}}", historial_texto)
        )
        texto = llamar_llm(prompt_sistema, mensaje)
        datos_llm = _parsear_json_llm(texto)
    except Exception as exc:
        salida.setdefault("errores", []).append("Fallo de LLM, se usa fallback determinista: " + str(exc))
        return None

    salida["resumen"] = datos_llm.get("resumen", "")
    salida["datos_detectados"] = datos_llm.get("datos_detectados", {})
    salida["bloqueos_detectados"] = datos_llm.get("bloqueos_detectados", [])
    if datos_llm.get("requiere_aclaracion"):
        salida["bloqueos_detectados"].append(
            datos_llm.get("pregunta_aclaracion") or "falta informacion para responder"
        )
    salida["trazas"]["fuentes_consultadas"] = datos_llm.get("fuentes", [])
    return auditar_salida(salida)


def _clasificar_con_llm_respaldo(pregunta, historial=None):
    """
    Llama al LLM con prompts/prompt_clasificar_consulta.md para obtener UNA etiqueta de una
    lista cerrada de 6 categorias. No construye SQL ni devuelve datos - es exactamente lo que
    se discutio como "clasificador de respaldo": el LLM solo entra cuando el codigo determinista
    no reconocio nada, y solo para decidir a que rama determinista redirigir la pregunta.

    Devuelve el dict JSON que exige el prompt (categoria, id_evento_detectado,
    filtros_detectados, falta_para_responder, motivo), o None si el LLM no esta disponible,
    falla, devuelve JSON invalido, o devuelve una categoria fuera del enum esperado - en
    cualquiera de esos casos el llamador debe seguir tratando la pregunta como "no reconocida"
    (mismo comportamiento que antes de conectar este respaldo, nunca peor).
    """
    contexto_texto = "(sin contexto previo en esta sesion)"
    if historial:
        lineas = []
        for turno in historial[-4:]:
            lineas.append("Usuario: " + str(turno.get("pregunta", "")))
            lineas.append("Lumen: " + str(turno.get("resumen", "")))
        contexto_texto = "\n".join(lineas)

    try:
        prompt_sistema = cargar_prompt("prompt_sistema.md")
        prompt_clasificar = cargar_prompt("prompt_clasificar_consulta.md")
        mensaje = (
            prompt_clasificar
            .replace("{{consulta_usuario}}", pregunta)
            .replace("{{contexto_conversacion_opcional}}", contexto_texto)
        )
        texto = llamar_llm(prompt_sistema, mensaje)
        resultado = _parsear_json_llm(texto)
    except Exception:
        return None

    if not isinstance(resultado, dict) or resultado.get("categoria") not in CATEGORIAS_CLASIFICACION_VALIDAS:
        return None
    return resultado


def _responder_con_clasificador_respaldo(salida, pregunta, pregunta_lower, historial=None):
    """
    Traduce la categoria devuelta por _clasificar_con_llm_respaldo() a una respuesta, siempre
    reutilizando las mismas ramas deterministas que ya existen (nunca se inventa una respuesta
    nueva a partir de lo que diga el LLM). Devuelve None si el LLM no esta disponible/falla, o si
    la categoria es "no_relacionada" - en ambos casos el llamador sigue con el mensaje fijo de la
    seccion 3, exactamente igual que si este respaldo no existiera.

    Seguridad: ninguna rama de aqui deja que el LLM aporte datos - "consulta_metricas_globales"
    reutiliza _responder_consulta_transversal_eventos (que vuelve a leer la BD real por su
    cuenta); el resto son mensajes deterministas ya existentes en la seccion 1. La etiqueta del
    LLM solo decide el ENRUTADO, nunca el contenido de la respuesta.
    """
    resultado = _clasificar_con_llm_respaldo(pregunta, historial)
    if resultado is None:
        return None

    categoria = resultado.get("categoria")

    if categoria == "consulta_metricas_globales":
        # Se reutiliza la misma funcion que usa la deteccion por palabras clave: lee la BD real
        # de nuevo, no se le pasa ningun dato "adivinado" por el LLM.
        return _responder_consulta_transversal_eventos(salida, pregunta_lower)

    if categoria in ("consulta_datos_evento", "aclaracion_necesaria"):
        salida["resumen"] = "¿De que evento necesitas esa informacion? Dime el nombre o el id_evento."
        salida["bloqueos_detectados"] = [
            "falta id_evento para resolver la consulta (detectado por el clasificador LLM de respaldo)"
        ]
        return auditar_salida(salida)

    if categoria == "fuera_de_alcance_escritura":
        # Red de seguridad adicional: la deteccion por palabras clave de la seccion 1 deberia
        # haber atrapado esto antes. Si llega hasta aqui es porque la redaccion de la pregunta no
        # coincidia con ninguna palabra de PALABRAS_ESCRITURA - el mensaje es identico al de esa
        # seccion, solo cambia de donde vino la deteccion.
        salida["resumen"] = (
            "No puedo modificar, aprobar ni borrar datos - solo consulto informacion existente. "
            "Esa accion queda fuera de mi alcance y requiere validacion humana."
        )
        salida["bloqueos_detectados"] = [
            "la peticion implica una escritura, fuera del alcance de Lumen "
            "(detectado por el clasificador LLM de respaldo)"
        ]
        salida["nivel_riesgo"] = "medio"
        salida["requiere_validacion_humana"] = True
        return auditar_salida(salida)

    if categoria == "fuera_de_alcance_usuarios":
        # Misma logica: red de seguridad adicional sobre PALABRAS_USUARIOS, no el primer filtro.
        salida["resumen"] = (
            "Esa consulta esta fuera de mi alcance: no tengo acceso a la tabla 'usuarios' ni a "
            "credenciales de la plataforma."
        )
        salida["bloqueos_detectados"] = [
            "consulta sobre tabla usuarios / credenciales (detectado por el clasificador LLM de respaldo)"
        ]
        salida["nivel_riesgo"] = "alto"
        salida["requiere_validacion_humana"] = True
        return auditar_salida(salida)

    # categoria == "no_relacionada": el LLM confirma que no hay nada que hacer con esta
    # pregunta. Se devuelve None a proposito para no duplicar el mensaje fijo aqui - lo pone la
    # seccion 3 de ejecutar_agente(), que es la unica fuente de esa frase exacta.
    return None


def _responder_consulta_transversal_eventos(salida, pregunta_lower):
    """
    Responde consultas transversales sin id_evento:
    - '¿qué eventos están en X estado?' -> filtra por ese estado si se reconoce.
    - 'cuántos eventos tenemos / qué eventos hay' -> cuenta/lista todos, sin filtrar.

    'datos_detectados["eventos"]' incluye siempre el id_evento junto al nombre (no solo el
    nombre), para que un llamador con memoria de conversacion (main.py o servidor.py) pueda "engancharse"
    al evento si la respuesta trae uno solo, y luego resolver un "ese evento" en el turno
    siguiente sin tener que volver a pedir el id_evento.
    """
    texto_normalizado = _normalizar(pregunta_lower)
    tokens_normalizado = texto_normalizado.split()
    if any(_frase_aproximada(_normalizar(p), texto_normalizado, tokens_normalizado) for p in PALABRAS_LISTAR_ESTADOS):
        disponibles = estados_disponibles()
        if disponibles:
            salida["resumen"] = "Los estados de evento disponibles son: " + ", ".join(disponibles) + "."
        else:
            salida["resumen"] = "No he podido leer ningun estado en los datos disponibles."
        salida["datos_detectados"] = {"estados_disponibles": disponibles}
        salida["trazas"]["fuentes_consultadas"] = ["estados.descripcion"]
        return auditar_salida(salida)

    estado_canonico, coincide = _detectar_estado_pedido(pregunta_lower)

    if coincide:
        eventos = eventos_por_estado(estado_canonico) or []
        etiqueta = "en estado '" + estado_canonico + "'"
        fuentes = ["eventos.id_estado", "estados.descripcion"]
    else:
        # La pregunta menciona un estado, pero no coincide con ninguno real: no adivinar.
        # Se compara normalizado y con tolerancia a typos, igual que en _detectar_estado_pedido -
        # con _contiene_alguna a secas "ejecucion" (sin tilde, como escribe la gente) no encontraba
        # "en ejecución" (con tilde) y la pregunta caia a listar TODOS los eventos sin filtrar.
        if any(_frase_aproximada(_normalizar(p), texto_normalizado, tokens_normalizado) for p in PALABRAS_TRANSVERSAL_ESTADO):
            disponibles = estados_disponibles()
            salida["resumen"] = (
                "No reconozco ese estado de evento en los datos disponibles. Los estados que "
                "existen son: " + ", ".join(disponibles) + "."
            )
            salida["bloqueos_detectados"] = ["estado de evento no reconocido en la pregunta"]
            salida["datos_detectados"] = {"estados_disponibles": disponibles}
            return auditar_salida(salida)

        eventos = todos_los_eventos()
        etiqueta = "en total"
        fuentes = ["eventos.*"]

    nombres = [e["nombre_evento"] for e in eventos]

    if nombres:
        salida["resumen"] = "Hay " + str(len(nombres)) + " evento(s) " + etiqueta + ": " + ", ".join(nombres) + "."
    else:
        salida["resumen"] = "No hay ningun evento " + etiqueta + " en los datos disponibles."

    salida["datos_detectados"] = {
        "eventos": [{"id_evento": e.get("id"), "nombre_evento": e.get("nombre_evento")} for e in eventos],
    }
    salida["trazas"]["fuentes_consultadas"] = fuentes
    return auditar_salida(salida)


def _responder_resumen_evento(salida, id_evento):
    datos = resumen_evento(id_evento)
    if datos is None:
        salida["resumen"] = "No encuentro el evento con id_evento " + str(id_evento) + " en los datos disponibles."
        salida["bloqueos_detectados"] = ["id_evento " + str(id_evento) + " no existe en los datos"]
        return auditar_salida(salida)

    salida["resumen"] = (
        "Evento " + str(id_evento) + " - " + datos["nombre_evento"] + " (" + datos["ciudad"] + "), " +
        "del " + datos["fecha_inicio"] + " al " + datos["fecha_fin"] + "."
    )
    salida["datos_detectados"] = datos
    salida["trazas"]["fuentes_consultadas"] = ["eventos.*"]
    return auditar_salida(salida)
