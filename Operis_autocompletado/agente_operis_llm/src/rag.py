"""
rag.py — consulta de documentación externa / bases de conocimiento. NO
APLICA a este agente: sigue sin consultar la BD ni documentación
externa (ver config/permisos.py).

Nota: esto ya NO significa que el agente sea "sin memoria entre
documentos" — desde la incorporación del modo actualización, SÍ puede
recibir y fusionar el histórico de versiones anteriores de un mismo
evento (contexto.historial_anterior, ver src/nucleo.py y
src/llm.py::construir_prompt_sistema). Pero ese histórico lo carga y
guarda el BACKEND y llega ya incluido en el payload — el agente nunca
va a buscarlo por su cuenta a una base de datos o RAG, así que este
módulo sigue sin aplicar.

Se mantiene como stub (en vez de borrar el archivo) para conservar la
misma estructura interna que otros agentes del proyecto — ver
Agente_04_Copilot_Raul/lumen_agente_04/, que sí usa RAG (data/rag/) por
ser un agente de consulta sobre el histórico de la BD; agente_operis no
lo necesita porque no consulta la BD en absoluto.
"""


def consultar_contexto(*args, **kwargs):
    """No aplica a este agente — ver docstring del módulo."""
    return None
