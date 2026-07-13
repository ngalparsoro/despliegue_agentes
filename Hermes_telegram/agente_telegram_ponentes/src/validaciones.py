def validar_decision_llm(decision: dict) -> dict:
    """Normaliza una decisión del LLM o del fallback."""
    if not isinstance(decision, dict):
        return {
            "intencion": "fallback",
            "urgencia": "normal",
            "respuesta_ponente": "",
            "requiere_escalado": True,
            "motivo_escalado": "decision_llm_invalida",
            "confianza": 0.0,
        }

    decision.setdefault("intencion", "otro")
    decision.setdefault("urgencia", "normal")
    decision.setdefault("respuesta_ponente", "")
    decision.setdefault("requiere_escalado", False)
    decision.setdefault("motivo_escalado", None)
    decision.setdefault("confianza", 0.0)
    decision.setdefault("servicio_consultado", None)
    return decision
