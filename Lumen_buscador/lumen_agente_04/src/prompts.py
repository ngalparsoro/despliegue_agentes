"""
Carga de los prompts de prompts/*.md.

Extrae el bloque de codigo (```...```) que contiene el prompt real a enviar al LLM, para no
duplicar el texto en el codigo Python: prompts/*.md sigue siendo la unica fuente de verdad de
lo que se le dice al modelo.
"""

import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = BASE_DIR / "prompts"

_CACHE = {}


def cargar_prompt(nombre_archivo: str) -> str:
    if nombre_archivo in _CACHE:
        return _CACHE[nombre_archivo]

    ruta = PROMPTS_DIR / nombre_archivo
    texto = ruta.read_text(encoding="utf-8")

    match = re.search(r"```\n(.*?)\n```", texto, re.DOTALL)
    if not match:
        raise ValueError(f"No se encontro un bloque de prompt (```...```) en {nombre_archivo}")

    prompt = match.group(1)
    _CACHE[nombre_archivo] = prompt
    return prompt
