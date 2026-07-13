"""
Auditoria final de la salida de Lumen - equivalente en codigo a prompts/prompt_validar_salida.md.

Se ejecuta SIEMPRE antes de devolver la respuesta, tanto en el flujo determinista
de este demo como (en produccion) sobre la salida del LLM. Es la ultima linea de defensa contra:
  - fuga de la tabla `usuarios` o de credenciales de acceso a la plataforma
  - que Lumen proponga o redacte una accion de escritura (no le corresponde)

Nota: no se asume un nombre de campo concreto para la credencial (el esquema actual no lo
documenta) - el filtro bloquea por la tabla `usuarios` y por terminos genericos de credencial.
"""

PALABRAS_PROHIBIDAS = ["usuarios", "contraseña", "password", "credencial"]


def auditar_salida(salida: dict) -> dict:
    # Lumen nunca propone acciones ni redacta borradores: se fuerza siempre, pase lo que pase.
    salida["acciones_propuestas"] = []
    salida["borradores_generados"] = []

    texto = " ".join([
        str(salida.get("resumen", "")),
        str(salida.get("datos_detectados", {})),
    ]).lower()

    if any(palabra in texto for palabra in PALABRAS_PROHIBIDAS):
        salida["resumen"] = "Esa informacion no esta disponible: fuera del alcance de Lumen."
        salida["datos_detectados"] = {}
        salida["nivel_riesgo"] = "alto"
        salida["requiere_validacion_humana"] = True
        mensaje = "fuga bloqueada: referencia a tabla usuarios/credenciales"
        if mensaje not in salida.get("bloqueos_detectados", []):
            salida.setdefault("bloqueos_detectados", []).append(mensaje)

    return salida
