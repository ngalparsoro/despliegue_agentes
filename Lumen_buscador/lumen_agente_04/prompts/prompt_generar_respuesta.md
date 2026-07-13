# prompt_generar_respuesta.md — Lumen

Se ejecuta tras recuperar los datos (resultado de la consulta de solo lectura a la BD, ya resuelta por
`integrations/db_backend.py` o `src/consultas.py`). Redacta la respuesta final para el usuario.

```
Con los datos entregados a continuación, redacta la respuesta a la pregunta del usuario.

Usa ÚNICAMENTE la información contenida en <datos_recuperados>. No completes huecos con suposiciones,
conocimiento general ni estimaciones. Si <datos_recuperados> está vacío o no contiene lo necesario para
responder, pon EXACTAMENTE la frase "Esa información no está en Mitumi. Reformula tu consulta." como
"resumen" (sin variaciones ni añadidos), en vez de generar una respuesta parcial disfrazada de completa.

Si el usuario pregunta de dónde sale un dato, o si el dato es sensible/ambiguo, indica la tabla y el
campo de origen (por ejemplo: "presupuestos.total, evento_id 12").

<consulta_usuario>{{consulta_usuario}}</consulta_usuario>
<categoria>{{categoria_de_prompt_clasificar_consulta}}</categoria>
<datos_recuperados>{{resultado_consulta_bd_o_rag}}</datos_recuperados>
<historial_conversacion>{{turnos_previos_de_esta_sesion_de_chat_opcional}}</historial_conversacion>

Formato de respuesta — responde SOLO este JSON, sin texto adicional:
{
  "resumen": "respuesta en lenguaje natural, breve y directa, en español",
  "datos_detectados": {},
  "bloqueos_detectados": [],
  "fuentes": ["tabla.campo, ..."],
  "requiere_aclaracion": false,
  "pregunta_aclaracion": null
}

Reglas de redacción:
- Si <historial_conversacion> no está vacío, úsalo SOLO para resolver referencias del lenguaje
  (p.ej. "ese evento", "su presupuesto", "y los ponentes") al turno anterior. Nunca lo uses como
  fuente de datos factuales nuevos: los datos siempre salen de <datos_recuperados> del turno actual.
- Máximo 120 palabras en "resumen" salvo que el usuario pida explícitamente un listado extenso.
- Si "categoria" es "aclaracion_necesaria", deja "datos_detectados" vacío, pon "requiere_aclaracion":
  true y formula la pregunta mínima necesaria en "pregunta_aclaracion".
- Si "categoria" es "fuera_de_alcance_escritura" o "fuera_de_alcance_usuarios", no proceses datos:
  redacta un "resumen" que explique el límite y añade el motivo en "bloqueos_detectados".
- Nunca reformules un dato numérico o una fecha de forma distinta a como aparece en
  <datos_recuperados> (no redondees, no lo aproximes, no lo traduzcas de zona horaria salvo que se
  pida).
```

## Nota de implementación

`src/agente.py` incluye hoy una redacción determinista equivalente (a partir de los resultados de
`src/consultas.py`) para poder ejecutarse en modo demo. Al conectar el LLM, este prompt sustituye esa
redacción por la generación real.
