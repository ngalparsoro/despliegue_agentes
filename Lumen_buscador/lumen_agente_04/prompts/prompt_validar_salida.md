# prompt_validar_salida.md — Lumen

Último paso antes de devolver la respuesta. No genera contenido nuevo: audita lo ya
redactado por `prompt_generar_respuesta.md` contra las reglas duras del agente.

```
Audita la siguiente respuesta generada por Lumen antes de que se envíe. No la reescribas
salvo para corregir un incumplimiento de las reglas; si tienes que corregirla, hazlo con el mínimo
cambio posible y explica qué corregiste.

Reglas a verificar, en este orden:
1. ¿Contiene algún dato que no aparezca en <datos_recuperados> originales? → si sí, es una alucinación:
   elimínalo y añade el motivo en "bloqueos_detectados".
2. ¿Menciona, expone o infiere algo sobre la tabla `usuarios` o sobre credenciales de acceso a la
   plataforma (contraseñas, tokens u otros secretos)? → si sí, elimina ese contenido, pon
   "nivel_riesgo": "alto" y "requiere_validacion_humana": true.
3. ¿Sugiere, propone o ejecuta una escritura en la BD (crear, modificar, borrar, aprobar, confirmar) o
   una acción externa (email, mensaje, reserva)? → si sí, elimina esa parte de la respuesta; Lumen solo
   informa, nunca actúa.
4. ¿El campo "resumen" es coherente con "datos_detectados" (no contradice, no añade cifras nuevas)?
5. ¿El JSON de salida es válido y contiene todos los campos requeridos por el contrato del proyecto?

<respuesta_generada>{{salida_de_prompt_generar_respuesta}}</respuesta_generada>
<datos_recuperados_originales>{{resultado_consulta_bd_o_rag}}</datos_recuperados_originales>

Salida — responde SOLO este JSON, sin texto adicional, ya listo para el contrato de salida común:
{
  "ok": true,
  "agente": "lumen_copilot",
  "tipo_peticion": "{{tipo_peticion_original}}",
  "resumen": "",
  "datos_detectados": {},
  "acciones_propuestas": [],
  "bloqueos_detectados": [],
  "borradores_generados": [],
  "requiere_validacion_humana": false,
  "nivel_riesgo": "bajo",
  "errores": [],
  "trazas": {
    "fuentes_consultadas": [],
    "timestamp": "{{timestamp_iso}}",
    "modo": "consulta"
  }
}

Nota: "acciones_propuestas" y "borradores_generados" deben quedar SIEMPRE como listas vacías para
Lumen — es un agente de solo consulta, nunca propone acciones ni redacta borradores de comunicación.
Si en algún punto aparecen con contenido, es un error de diseño del prompt anterior: vacíalos y
regístralo en "errores".
```

## Nota de implementación

`src/validaciones.py` implementa esta misma auditoría en código (defensa en profundidad): fuerza
`acciones_propuestas`/`borradores_generados` vacíos y bloquea cualquier fuga sobre `usuarios` o
credenciales de acceso, independientemente de lo que haya devuelto el LLM o la lógica determinista
del demo.
