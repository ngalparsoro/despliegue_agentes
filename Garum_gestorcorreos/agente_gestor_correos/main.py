"""Ejecuta un ciclo completo del agente gestor de correos MITUMI."""

import json

from src.agente import ejecutar_agente
from src.funciones import funciones
from src.memoria import inicializar_memoria
from src.prompts import cargar_prompts
from src.tools import tools


def ejecutar_ciclo():
    """Prepara memoria, prompts, tools y funciones."""

    inicializar_memoria()
    prompts = cargar_prompts()

    return ejecutar_agente(
        tools=tools,
        funciones=funciones,
        prompts=prompts,
    )


if __name__ == "__main__":
    resultado = ejecutar_ciclo()

    print("\n===== RESULTADO DEL CICLO =====")
    print(
        json.dumps(
            resultado,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )
