"""Carga los prompts editables del proyecto."""

from src.parametros import PROMPTS_DIR


ARCHIVOS_PROMPT = {
    "reglas": "reglas_comunes.txt",
    "clasificacion": "prompt_clasificacion.txt",
    "redaccion": "prompt_redaccion.txt",
}


def cargar_prompts():
    """Lee todos los prompts desde archivos separados."""

    prompts = {}

    for nombre, archivo in ARCHIVOS_PROMPT.items():
        ruta = PROMPTS_DIR / archivo

        prompts[nombre] = ruta.read_text(
            encoding="utf-8",
        )

    return prompts
