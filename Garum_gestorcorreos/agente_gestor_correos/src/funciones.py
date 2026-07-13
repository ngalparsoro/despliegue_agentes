"""Funciones de alto nivel y registro del agente."""

import json
from pathlib import Path

from src.gmail import (
    crear_borrador,
    marcar_como_leido,
    obtener_correos_no_leidos,
)
from src.llm import preguntar_json
from src.memoria import (
    obtener_registro_correo,
    registrar_correo,
)
from src.parametros import (
    CLASSIFICATION_MIN_CONFIDENCE,
)


CATEGORIAS = {
    "nuevo_evento_lead",
    "cliente_briefing",
    "cliente_cambio_fecha",
    "cliente_cambio_aforo",
    "cliente_aprobacion",
    "cliente_duda",
    "cliente_cancelacion",
    "cliente_queja",
    "ponente_informacion_general",
    "ponente_confirmacion",
    "ponente_documentacion_cv",
    "ponente_documentacion_foto",
    "ponente_presentacion",
    "ponente_actualizacion_presentacion",
    "ponente_duda_viaje",
    "ponente_duda_hotel",
    "ponente_necesidad_tecnica",
    "ponente_restriccion_alimentaria",
    "ponente_cancelacion",
    "espacio_disponibilidad",
    "espacio_presupuesto",
    "espacio_condiciones",
    "proveedor_presupuesto",
    "proveedor_confirmacion",
    "proveedor_incidencia",
    "proveedor_cambio",
    "factura_cliente",
    "factura_proveedor",
    "factura_ponente",
    "documento_fiscal",
    "justificante_pago",
    "publicidad",
    "newsletter",
    "spam",
    "phishing_sospechoso",
    "respuesta_automatica",
    "fuera_oficina",
    "rebote_email",
    "duplicado",
    "no_relacionado",
    "no_clasificado",
}


ETIQUETAS = {
    "nuevo_evento_lead": "MITUMI/Nuevos eventos",
    "cliente_briefing": "MITUMI/Clientes",
    "cliente_cambio_fecha": "MITUMI/Clientes/Cambios",
    "cliente_cambio_aforo": "MITUMI/Clientes/Cambios",
    "cliente_aprobacion": "MITUMI/Clientes/Aprobaciones",
    "cliente_duda": "MITUMI/Clientes/Consultas",
    "cliente_cancelacion": "MITUMI/Urgente",
    "cliente_queja": "MITUMI/Urgente",
    "ponente_informacion_general": "MITUMI/Ponentes",
    "ponente_confirmacion": "MITUMI/Ponentes/Confirmaciones",
    "ponente_documentacion_cv": "MITUMI/Ponentes/Documentacion",
    "ponente_documentacion_foto": "MITUMI/Ponentes/Documentacion",
    "ponente_presentacion": "MITUMI/Ponentes/Presentaciones",
    "ponente_actualizacion_presentacion": "MITUMI/Ponentes/Presentaciones",
    "ponente_duda_viaje": "MITUMI/Ponentes/Viajes",
    "ponente_duda_hotel": "MITUMI/Ponentes/Hoteles",
    "ponente_necesidad_tecnica": "MITUMI/Ponentes/Necesidades tecnicas",
    "ponente_restriccion_alimentaria": "MITUMI/Ponentes/Catering",
    "ponente_cancelacion": "MITUMI/Urgente",
    "espacio_disponibilidad": "MITUMI/Espacios",
    "espacio_presupuesto": "MITUMI/Espacios/Presupuestos",
    "espacio_condiciones": "MITUMI/Espacios/Condiciones",
    "proveedor_presupuesto": "MITUMI/Proveedores/Presupuestos",
    "proveedor_confirmacion": "MITUMI/Proveedores/Confirmaciones",
    "proveedor_incidencia": "MITUMI/Urgente",
    "proveedor_cambio": "MITUMI/Proveedores/Cambios",
    "factura_cliente": "MITUMI/Facturacion",
    "factura_proveedor": "MITUMI/Facturacion",
    "factura_ponente": "MITUMI/Facturacion",
    "documento_fiscal": "MITUMI/Facturacion",
    "justificante_pago": "MITUMI/Facturacion",
    "publicidad": "MITUMI/Publicidad",
    "newsletter": "MITUMI/Publicidad",
    "spam": "MITUMI/Spam sospechoso",
    "phishing_sospechoso": "MITUMI/Spam sospechoso",
    "respuesta_automatica": "MITUMI/Automaticos",
    "fuera_oficina": "MITUMI/Automaticos",
    "rebote_email": "MITUMI/Rebotes",
    "duplicado": "MITUMI/Duplicados",
    "no_relacionado": "MITUMI/No relacionado",
    "no_clasificado": "MITUMI/No clasificado",
}


CATEGORIAS_SIN_BORRADOR = {
    "publicidad",
    "newsletter",
    "spam",
    "phishing_sospechoso",
    "respuesta_automatica",
    "fuera_oficina",
    "rebote_email",
    "duplicado",
    "no_relacionado",
    "no_clasificado",
}


DOCUMENTOS_CRITICOS = {
    "factura",
    "contrato",
    "documento_fiscal",
    "documento_no_clasificado",
    "pdf_pendiente_clasificacion",
}


def convertir_confianza(valor):
    """Convierte una confianza a número entre 0 y 1."""

    try:
        confianza = float(valor)
    except (TypeError, ValueError):
        return 0.0

    return max(0.0, min(confianza, 1.0))


def convertir_booleano(valor):
    """Convierte valores habituales del LLM a booleano."""

    if isinstance(valor, bool):
        return valor

    return str(valor).strip().lower() in {
        "true",
        "1",
        "si",
        "sí",
        "yes",
    }


def clasificar_correo(correo, prompts):
    """Clasifica semánticamente un correo con LLM obligatorio."""

    prompt = (
        prompts["reglas"]
        + "\n\n"
        + prompts["clasificacion"]
    )

    contenido = json.dumps(
        {
            "remitente": correo.get("remitente", ""),
            "asunto": correo.get("asunto", ""),
            "cuerpo": correo.get("cuerpo", ""),
            "adjuntos": correo.get("adjuntos", []),
        },
        ensure_ascii=False,
    )

    try:
        datos = preguntar_json(
            prompt,
            contenido,
        )
    except Exception as error:
        return {
            "ok": False,
            "error": str(error),
        }

    if not isinstance(datos, dict):
        return {
            "ok": False,
            "error": "El LLM no devolvió JSON válido.",
        }

    categoria = (
        datos.get("categoria")
        or datos.get("clasificacion")
        or ""
    ).strip().lower()
    confianza = convertir_confianza(
        datos.get("confianza")
    )

    if categoria not in CATEGORIAS:
        categoria = "no_clasificado"

    if confianza < CLASSIFICATION_MIN_CONFIDENCE:
        categoria = "no_clasificado"

    prioridad = str(
        datos.get("prioridad")
        or "media"
    ).strip().lower()

    if prioridad not in {"baja", "media", "alta"}:
        prioridad = "media"

    riesgo = str(
        datos.get("riesgo")
        or "medio"
    ).strip().lower()

    if riesgo not in {"bajo", "medio", "alto"}:
        riesgo = "medio"

    evento = datos.get("evento_detectado")

    if not isinstance(evento, str) or not evento.strip():
        evento = None

    requiere_asociacion = datos.get(
        "requiere_asociacion_evento"
    )

    if evento is None:
        requiere_asociacion = True
    else:
        requiere_asociacion = convertir_booleano(
            requiere_asociacion
        )

    extraidos = datos.get("datos_extraidos")

    if not isinstance(extraidos, dict):
        extraidos = {}

    return {
        "ok": True,
        "categoria": categoria,
        "confianza": confianza,
        "prioridad": prioridad,
        "riesgo": riesgo,
        "requiere_respuesta": convertir_booleano(
            datos.get("requiere_respuesta")
        ),
        "motivo": str(
            datos.get("motivo")
            or "Clasificación sin motivo."
        ).strip(),
        "evento_detectado": evento,
        "requiere_asociacion_evento": requiere_asociacion,
        "datos_extraidos": extraidos,
    }


def redactar_borrador(correo, clasificacion, prompts):
    """Redacta un borrador con LLM obligatorio."""

    prompt = (
        prompts["reglas"]
        + "\n\n"
        + prompts["redaccion"]
    )

    contenido = json.dumps(
        {
            "correo": {
                "remitente": correo.get("remitente", ""),
                "asunto": correo.get("asunto", ""),
                "cuerpo": correo.get("cuerpo", ""),
                "adjuntos": correo.get("adjuntos", []),
            },
            "clasificacion": clasificacion,
        },
        ensure_ascii=False,
    )

    try:
        datos = preguntar_json(
            prompt,
            contenido,
        )
    except Exception as error:
        return {
            "ok": False,
            "error": str(error),
        }

    if not isinstance(datos, dict):
        return {
            "ok": False,
            "error": "El LLM no devolvió JSON válido para el borrador.",
        }

    cuerpo = str(
        datos.get("cuerpo")
        or ""
    ).strip()

    if not cuerpo:
        return {
            "ok": False,
            "error": "El LLM devolvió un borrador vacío.",
        }

    asunto_original = correo.get("asunto", "")
    asunto = asunto_original

    if not asunto.lower().startswith("re:"):
        asunto = "Re: " + asunto

    return {
        "ok": True,
        "asunto": asunto,
        "asunto_sugerido_llm": datos.get(
            "asunto_sugerido"
        ),
        "cuerpo": cuerpo,
    }


def tipo_documento(nombre, categoria):
    """Clasifica un adjunto por su nombre y contexto."""

    texto = (nombre or "").lower()
    extension = Path(texto).suffix

    if "cv" in texto or "curriculum" in texto or "biografia" in texto:
        return "cv_ponente"

    if "foto" in texto or extension in {".jpg", ".jpeg", ".png", ".webp"}:
        return "foto_ponente"

    if (
        "presentacion" in texto
        or "ponencia" in texto
        or extension in {".ppt", ".pptx"}
    ):
        return "presentacion_ponente"

    if "factura" in texto or categoria.startswith("factura_"):
        return "factura"

    if "presupuesto" in texto or "oferta" in texto:
        return "presupuesto"

    if "contrato" in texto:
        return "contrato"

    if "billete" in texto or "vuelo" in texto or "tren" in texto:
        return "billete_vuelo"

    if "hotel" in texto or "alojamiento" in texto or "reserva" in texto:
        return "reserva_hotel"

    if "fiscal" in texto or "cif" in texto or "nif" in texto:
        return "documento_fiscal"

    if "ficha" in texto:
        return "ficha_ponente"

    if categoria == "ponente_documentacion_cv":
        return "cv_ponente"

    if categoria == "ponente_documentacion_foto":
        return "foto_ponente"

    if categoria in {
        "ponente_presentacion",
        "ponente_actualizacion_presentacion",
    }:
        return "presentacion_ponente"

    if extension == ".pdf":
        return "pdf_pendiente_clasificacion"

    return "documento_no_clasificado"


def detectar_documentos(correo, categoria):
    """Registra los metadatos de todos los adjuntos."""

    documentos = []

    for adjunto in correo.get("adjuntos", []) or []:
        nombre = (
            adjunto.get("nombre")
            or adjunto.get("filename")
            or "adjunto_sin_nombre"
        )

        documentos.append(
            {
                "nombre_archivo": nombre,
                "tipo_documento_detectado": tipo_documento(
                    nombre,
                    categoria,
                ),
                "mime_type": (
                    adjunto.get("mime_type")
                    or adjunto.get("mimeType")
                    or ""
                ),
                "size_bytes": (
                    adjunto.get("size_bytes")
                    or adjunto.get("size")
                    or 0
                ),
                "estado_documental": "pendiente_revision_humana",
                "requiere_validacion_humana": True,
            }
        )

    return documentos


def sugerir_etiquetas(categoria, documentos, riesgo):
    """Propone etiquetas de Gmail sin aplicarlas."""

    etiquetas = [
        ETIQUETAS.get(
            categoria,
            "MITUMI/No clasificado",
        )
    ]

    if documentos:
        etiquetas += [
            "MITUMI/Documentos",
            "MITUMI/Pendiente revision humana",
        ]

    if riesgo == "alto":
        etiquetas.append("MITUMI/Urgente")

    return list(dict.fromkeys(etiquetas))


def requiere_borrador(clasificacion):
    """Determina si el correo necesita respuesta."""

    categoria = clasificacion.get("categoria")

    if categoria in CATEGORIAS_SIN_BORRADOR:
        return False

    return bool(
        clasificacion.get("requiere_respuesta")
    )


def crear_acciones(
    clasificacion,
    documentos,
    necesita_borrador,
):
    """Genera acciones propuestas para frontend o revisión."""

    acciones = []

    if clasificacion.get("requiere_asociacion_evento"):
        acciones.append(
            {
                "tipo": "asociar_evento",
                "estado": "pendiente_humano",
            }
        )

    if documentos:
        acciones.append(
            {
                "tipo": "revisar_documentos",
                "estado": "pendiente_humano",
                "cantidad": len(documentos),
            }
        )

    if necesita_borrador:
        acciones.append(
            {
                "tipo": "crear_borrador",
                "estado": "pendiente",
            }
        )

    if clasificacion.get("riesgo") == "alto":
        acciones.append(
            {
                "tipo": "revision_urgente",
                "estado": "pendiente_humano",
            }
        )

    if clasificacion.get("categoria", "").startswith("factura_"):
        acciones.append(
            {
                "tipo": "revisar_facturacion",
                "estado": "pendiente_humano",
            }
        )

    if not acciones:
        acciones.append(
            {
                "tipo": "registrar_correo",
                "estado": "propuesto",
            }
        )

    return acciones


def puede_marcar_como_leido(
    clasificacion,
    documentos,
    necesita_borrador,
    borrador_creado,
    errores,
):
    """Aplica las reglas seguras de marcado como leído."""

    categoria = clasificacion.get("categoria")

    if errores:
        return False

    if clasificacion.get("confianza", 0) < CLASSIFICATION_MIN_CONFIDENCE:
        return False

    if categoria in {
        "no_clasificado",
        "phishing_sospechoso",
        "cliente_cancelacion",
        "cliente_queja",
        "ponente_cancelacion",
        "proveedor_incidencia",
    }:
        return False

    if clasificacion.get("riesgo") == "alto":
        return False

    if necesita_borrador and not borrador_creado:
        return False

    tipos = {
        documento.get("tipo_documento_detectado")
        for documento in documentos
    }

    if tipos & DOCUMENTOS_CRITICOS:
        return False

    return True


funciones = {
    "obtener_correos_no_leidos": obtener_correos_no_leidos,
    "clasificar_correo": clasificar_correo,
    "detectar_documentos": detectar_documentos,
    "sugerir_etiquetas": sugerir_etiquetas,
    "requiere_borrador": requiere_borrador,
    "crear_acciones": crear_acciones,
    "puede_marcar_como_leido": puede_marcar_como_leido,
    "redactar_borrador": redactar_borrador,
    "crear_borrador": crear_borrador,
    "marcar_como_leido": marcar_como_leido,
    "obtener_registro_correo": obtener_registro_correo,
    "registrar_correo": registrar_correo,
}
