"""
Punto de entrada común de agente_operis.

Este es el nombre de fichero y función OBLIGATORIOS según el contrato
del proyecto (README.md, sección 9): src/agente.py debe exponer
ejecutar_agente(payload) -> dict, sin excepción.

La implementación real vive en src/nucleo.py (validación, extracción con
el motor LLM y construcción de la salida) y src/llm.py (el único motor
de extracción; el motor de reglas se eliminó, ver README.md). Este
archivo es solo el punto de entrada estable que el orquestador, main.py
o una futura API deben poder importar siempre igual — mismo patrón que
Agente_04_Copilot_Raul/lumen_agente_04/src/agente.py.
"""

from src.nucleo import ejecutar_agente

__all__ = ["ejecutar_agente"]
