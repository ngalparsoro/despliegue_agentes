"""
Punto de entrada comun de Lumen (Agente 04 - Copilot).

Este es el nombre de fichero y funcion OBLIGATORIOS segun el contrato del proyecto (README.md,
seccion 1): src/agente.py debe exponer ejecutar_agente(payload) -> dict, sin excepcion.

La implementacion real vive en src/nucleo.py (logica de clasificacion, consulta y respuesta) y
src/lectura_datos.py (acceso de solo lectura a los datos). Este archivo es solo el punto de
entrada estable que main.py, servidor.py o una futura API deben poder importar siempre igual.
"""

from src.nucleo import ejecutar_agente

__all__ = ["ejecutar_agente"]
