"""Flujo principal del agente gestor de correos MITUMI."""

import json
import re
from datetime import datetime

from src.memoria import ESTADO_PENDIENTE_LECTURA
from src.parametros import (
    AGENTE_VERSION,
    ALLOW_MARK_AS_READ,
    OUTPUTS_DIR,
    SHOW_STEPS,
)


def mostrar(bloque, mensaje):
    """Muestra los pasos del agente."""

    if SHOW_STEPS:
        print(f"[{bloque}] {mensaje}")


def nombre_seguro(valor):
    """Crea un nombre de archivo válido."""

    nombre = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        str(valor or "sin_id"),
    )

    return nombre.strip("._")[:100] or "sin_id"


def guardar_json(resultado):
    """Guarda una copia JSON del resultado del correo."""

    OUTPUTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    ruta = OUTPUTS_DIR / (
        nombre_seguro(
            resultado.get("email_id")
        )
        + ".json"
    )

    ruta.write_text(
        json.dumps(
            resultado,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    return str(ruta)


def registrar(
    funciones,
    correo,
    resultado,
    estado_gmail,
    draft_id="",
):
    """Guarda SQLite y JSON para el correo."""

    resultado["archivo_json"] = guardar_json(
        resultado
    )

    accion = ",".join(
        accion.get("tipo", "")
        for accion in resultado.get(
            "acciones_propuestas",
            [],
        )
        if accion.get("tipo")
    )

    funciones["registrar_correo"](
        message_id=correo.get("message_id", ""),
        categoria=resultado.get(
            "categoria",
            "no_clasificado",
        ),
        confianza=resultado.get(
            "confianza",
            0,
        ),
        accion=accion,
        estado_gmail=estado_gmail,
        draft_id=draft_id,
        requiere_revision=resultado.get(
            "requiere_validacion_humana",
            True,
        ),
        error="; ".join(
            resultado.get("errores", [])
        ),
        resultado=resultado,
    )

    return resultado


def resultado_error_llm(correo, error):
    """Crea una respuesta controlada si falla el LLM."""

    return {
        "ok": False,
        "agente": "agente_gestor_correos_mitumi",
        "version_agente": AGENTE_VERSION,
        "email_id": correo.get("message_id"),
        "thread_id": correo.get("thread_id"),
        "remitente": correo.get("remitente"),
        "asunto": correo.get("asunto"),
        "categoria": "no_clasificado",
        "confianza": 0.0,
        "motivo": error,
        "riesgo": "alto",
        "id_evento_detectado": None,
        "evento_detectado": None,
        "requiere_asociacion_evento": True,
        "documentos_detectados": [],
        "etiquetas_sugeridas": [
            "MITUMI/No clasificado",
            "MITUMI/Pendiente revision humana",
        ],
        "acciones_propuestas": [
            {
                "tipo": "revision_error_llm",
                "estado": "pendiente_humano",
            }
        ],
        "borradores_generados": [],
        "acciones_ejecutadas": [],
        "marcar_como_leido_sugerido": False,
        "requiere_validacion_humana": True,
        "errores": [error],
        "timestamp": datetime.now().isoformat(
            timespec="seconds",
        ),
    }


def procesar_pendiente_lectura(
    correo,
    registro_previo,
    funciones,
):
    """Reintenta únicamente el marcado como leído."""

    mostrar(
        "REINTENTO",
        "El correo ya fue procesado. Se reintenta solo el marcado como leído.",
    )

    resultado = registro_previo.get(
        "resultado"
    ) or {}
    resultado = dict(resultado)
    acciones = list(
        resultado.get(
            "acciones_ejecutadas",
            [],
        )
    )
    errores = []

    lectura = funciones["marcar_como_leido"](
        correo.get("message_id"),
        correo.get("thread_id", ""),
    )

    acciones.append(
        {
            "tipo": "marcar_como_leido",
            "ok": bool(lectura.get("ok")),
            "detalle": lectura,
        }
    )

    if lectura.get("ok"):
        estado_gmail = "leido"
        resultado["ok"] = True
    else:
        estado_gmail = ESTADO_PENDIENTE_LECTURA
        errores.append(
            "No se pudo completar el marcado como leído."
        )
        resultado["ok"] = False

    resultado["acciones_ejecutadas"] = acciones
    resultado["errores"] = errores
    resultado["timestamp"] = datetime.now().isoformat(
        timespec="seconds",
    )

    return registrar(
        funciones=funciones,
        correo=correo,
        resultado=resultado,
        estado_gmail=estado_gmail,
        draft_id=registro_previo.get(
            "draft_id",
            "",
        ),
    )


def procesar_correo(
    correo,
    tools,
    funciones,
    prompts,
):
    """Clasifica y procesa un correo con un único flujo."""

    registro_previo = correo.get(
        "_registro_previo"
    )

    if (
        registro_previo
        and registro_previo.get("estado_gmail")
        == ESTADO_PENDIENTE_LECTURA
    ):
        return procesar_pendiente_lectura(
            correo,
            registro_previo,
            funciones,
        )

    mostrar(
        "1 CORREO",
        correo.get("asunto", "(sin asunto)"),
    )
    mostrar(
        "DATOS",
        (
            f"ID={correo.get('message_id')} | "
            f"Thread={correo.get('thread_id') or 'no_detectado'} | "
            f"Adjuntos={len(correo.get('adjuntos', []))}"
        ),
    )

    mostrar(
        "2 LLM",
        "Clasificando correo",
    )
    clasificacion = funciones["clasificar_correo"](
        correo,
        prompts,
    )

    if not clasificacion.get("ok"):
        error = clasificacion.get(
            "error",
            "Error desconocido del LLM.",
        )
        mostrar("ERROR", error)
        resultado = resultado_error_llm(
            correo,
            error,
        )

        return registrar(
            funciones=funciones,
            correo=correo,
            resultado=resultado,
            estado_gmail="no_leido",
        )

    categoria = clasificacion["categoria"]
    mostrar(
        "3 CLASIFICACIÓN",
        (
            f"{categoria} | "
            f"confianza={clasificacion['confianza']:.2f} | "
            f"riesgo={clasificacion['riesgo']}"
        ),
    )
    mostrar(
        "MOTIVO",
        clasificacion.get("motivo", ""),
    )

    documentos = funciones["detectar_documentos"](
        correo,
        categoria,
    )
    mostrar(
        "4 DOCUMENTOS",
        str(len(documentos)),
    )

    etiquetas = funciones["sugerir_etiquetas"](
        categoria,
        documentos,
        clasificacion.get("riesgo"),
    )
    mostrar(
        "5 ETIQUETAS",
        ", ".join(etiquetas),
    )

    necesita_borrador = funciones["requiere_borrador"](
        clasificacion
    ) if "requiere_borrador" in funciones else False

    acciones = funciones["crear_acciones"](
        clasificacion,
        documentos,
        necesita_borrador,
    ) if "crear_acciones" in funciones else []

    mostrar(
        "6 BORRADOR",
        "sí" if necesita_borrador else "no",
    )

    borradores = []
    ejecutadas = []
    errores = []
    borrador_creado = False
    draft_id = ""

    if necesita_borrador:
        borrador = funciones["redactar_borrador"](
            correo,
            clasificacion,
            prompts,
        )

        if not borrador.get("ok"):
            errores.append(
                borrador.get(
                    "error",
                    "No se pudo redactar el borrador.",
                )
            )
        else:
            propuesta = {
                "canal": "email",
                "asunto": borrador["asunto"],
                "asunto_sugerido_llm": borrador.get(
                    "asunto_sugerido_llm"
                ),
                "cuerpo": borrador["cuerpo"],
                "estado": "pendiente_validacion_humana",
                "thread_id": correo.get("thread_id"),
                "creado_en_gmail": False,
            }
            borradores.append(propuesta)

            mostrar(
                "7 GMAIL",
                "Creando borrador real",
            )
            resultado_borrador = funciones["crear_borrador"](
                correo.get("message_id"),
                borrador["asunto"],
                borrador["cuerpo"],
            )
            borrador_creado = bool(
                resultado_borrador.get("ok")
            )
            draft_id = resultado_borrador.get(
                "draft_id",
                "",
            )
            propuesta["creado_en_gmail"] = borrador_creado
            propuesta["hilo_mantenido"] = resultado_borrador.get(
                "hilo_mantenido",
                False,
            )
            ejecutadas.append(
                {
                    "tipo": "crear_borrador_gmail",
                    "ok": borrador_creado,
                    "detalle": resultado_borrador,
                }
            )

            if not borrador_creado:
                estado = resultado_borrador.get("estado")

                if estado != "borradores_desactivados":
                    errores.append(
                        "No se pudo crear el borrador real en Gmail."
                    )

    puede_leer = funciones["puede_marcar_como_leido"](
        clasificacion,
        documentos,
        necesita_borrador,
        borrador_creado,
        errores,
    ) if "puede_marcar_como_leido" in funciones else False

    mostrar(
        "8 LEÍDO",
        "sí" if puede_leer else "no",
    )

    estado_gmail = "no_leido"

    if puede_leer and ALLOW_MARK_AS_READ:
        lectura = funciones["marcar_como_leido"](
            correo.get("message_id"),
            correo.get("thread_id", ""),
        )
        ejecutadas.append(
            {
                "tipo": "marcar_como_leido",
                "ok": bool(lectura.get("ok")),
                "detalle": lectura,
            }
        )

        if lectura.get("ok"):
            estado_gmail = "leido"
        else:
            estado_gmail = ESTADO_PENDIENTE_LECTURA
            errores.append(
                "No se pudo marcar el correo como leído."
            )

    requiere_revision = bool(
        documentos
        or borradores
        or categoria == "no_clasificado"
        or clasificacion.get("riesgo") == "alto"
        or clasificacion.get("requiere_asociacion_evento")
    )

    resultado = {
        "ok": not errores,
        "agente": "agente_gestor_correos_mitumi",
        "version_agente": AGENTE_VERSION,
        "email_id": correo.get("message_id"),
        "thread_id": correo.get("thread_id"),
        "remitente": correo.get("remitente"),
        "asunto": correo.get("asunto"),
        "categoria": categoria,
        "confianza": clasificacion.get("confianza"),
        "motivo": clasificacion.get("motivo"),
        "riesgo": clasificacion.get("riesgo"),
        "id_evento_detectado": None,
        "evento_detectado": clasificacion.get(
            "evento_detectado"
        ),
        "requiere_asociacion_evento": clasificacion.get(
            "requiere_asociacion_evento"
        ),
        "documentos_detectados": documentos,
        "etiquetas_sugeridas": etiquetas,
        "acciones_propuestas": acciones,
        "borradores_generados": borradores,
        "acciones_ejecutadas": ejecutadas,
        "marcar_como_leido_sugerido": puede_leer,
        "requiere_validacion_humana": requiere_revision,
        "errores": errores,
        "timestamp": datetime.now().isoformat(
            timespec="seconds",
        ),
    }

    return registrar(
        funciones=funciones,
        correo=correo,
        resultado=resultado,
        estado_gmail=estado_gmail,
        draft_id=draft_id,
    )


def ejecutar_agente(
    tools,
    funciones,
    prompts,
):
    """Procesa todos los correos pendientes."""

    faltan = [
        nombre
        for nombre in tools
        if nombre not in funciones
    ]

    if faltan:
        return {
            "ok": False,
            "estado": "faltan_funciones",
            "funciones": faltan,
        }

    mostrar(
        "GMAIL",
        "Buscando correos no leídos",
    )

    try:
        correos = funciones[
            "obtener_correos_no_leidos"
        ]()
    except Exception as error:
        return {
            "ok": False,
            "estado": "error_gmail",
            "error": str(error),
            "resultados": [],
        }

    if not correos:
        return {
            "ok": True,
            "estado": "sin_correos_nuevos",
            "procesados": 0,
            "resultados": [],
        }

    resultados = []

    for numero, correo in enumerate(
        correos,
        start=1,
    ):
        print(
            f"\n===== CORREO "
            f"{numero}/{len(correos)} ====="
        )

        try:
            resultado = procesar_correo(
                correo=correo,
                tools=tools,
                funciones=funciones,
                prompts=prompts,
            )
        except Exception as error:
            resultado = resultado_error_llm(
                correo,
                "Error durante el procesamiento: "
                + str(error),
            )
            registrar(
                funciones=funciones,
                correo=correo,
                resultado=resultado,
                estado_gmail="no_leido",
            )

        resultados.append(resultado)

    return {
        "ok": all(
            resultado.get("ok", False)
            for resultado in resultados
        ),
        "estado": "ciclo_completado",
        "procesados": len(resultados),
        "resultados": resultados,
    }
