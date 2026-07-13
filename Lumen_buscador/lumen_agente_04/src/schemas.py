"""
Contrato de entrada/salida comun del proyecto Agora, adaptado a Lumen (Agente 04 - Copilot).
Ver README.md secciones 9 y 10 para la version documentada de este contrato.
"""

import datetime

CAMPOS_ENTRADA_OBLIGATORIOS = [
    "tipo_peticion",
    "origen",
    "usuario_solicitante",
    "rol_usuario",
    "datos",
    "contexto",
    "modo",
]


def validar_entrada(payload: dict) -> list:
    """
    Valida el payload de entrada contra el contrato comun.
    Devuelve una lista de errores (vacia si el payload es valido).

    Nota: a diferencia del contrato comun, en Lumen 'id_evento' puede ser null
    (consultas transversales a varios eventos), pero el campo debe estar presente.
    """
    errores = []

    if not isinstance(payload, dict):
        return ["El payload debe ser un diccionario JSON."]

    for campo in CAMPOS_ENTRADA_OBLIGATORIOS:
        valor = payload.get(campo, None)
        if campo not in payload or valor in (None, ""):
            errores.append(f"Falta el campo obligatorio '{campo}'.")

    if "id_evento" not in payload:
        errores.append("Falta el campo 'id_evento' (puede ser null para consultas transversales).")

    if not isinstance(payload.get("datos"), dict):
        errores.append("El campo 'datos' debe ser un objeto (dict), aunque este vacio.")

    return errores


def construir_salida_base(agente: str, tipo_peticion: str) -> dict:
    """Construye la salida base con el contrato comun, lista para rellenar."""
    return {
        "ok": True,
        "agente": agente,
        "tipo_peticion": tipo_peticion,
        "resumen": "",
        "datos_detectados": {},
        "acciones_propuestas": [],
        "bloqueos_detectados": [],
        "borradores_generados": [],
        "requiere_validacion_humana": False,
        "nivel_riesgo": "bajo",
        "errores": [],
        "trazas": {
            "fuentes_consultadas": [],
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "modo": "consulta",
        },
    }
