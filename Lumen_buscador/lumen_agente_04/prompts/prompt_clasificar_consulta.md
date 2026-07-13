# prompt_clasificar_consulta.md — Lumen

Se ejecuta antes de tocar la base de datos. Clasifica la petición entrante para decidir si se resuelve,
se pide aclaración o se bloquea, sin gastar una consulta a la BD en vano.

```
Clasifica la siguiente consulta de un usuario interno de Mitumi sobre la plataforma Ágora en
EXACTAMENTE una de estas categorías:

1. "consulta_datos_evento" — pregunta sobre un evento concreto (ponentes, presupuesto, sala, espacio,
   cliente, fechas, estado) identificable por id_evento, nombre o cliente.
2. "consulta_metricas_globales" — pregunta agregada o transversal a varios eventos (conteos, totales,
   comparativas, tendencias) que no requiere un id_evento único.
3. "aclaracion_necesaria" — la pregunta es válida dentro del alcance pero falta un filtro imprescindible
   (qué evento, qué rango de fechas, qué cliente) para poder responder sin adivinar.
4. "fuera_de_alcance_escritura" — pide crear, modificar, borrar, confirmar o aprobar algo en la BD, o
   ejecutar una acción externa (enviar email, mensaje, reserva).
5. "fuera_de_alcance_usuarios" — menciona la tabla `usuarios`, credenciales, contraseñas o roles de
   acceso a la plataforma.
6. "no_relacionada" — no tiene relación con los datos de la plataforma Ágora.

Reglas:
- Si la consulta combina una parte válida y una parte de escritura ("dime el presupuesto y súbelo un
  10%"), clasifica como "fuera_de_alcance_escritura" y añade en el motivo qué parte sí se podría
  responder por separado.
- Ante la duda entre "consulta_datos_evento" y "aclaracion_necesaria", prioriza "aclaracion_necesaria"
  si falta el identificador del evento.
- No inventes una categoría fuera de esta lista.

Entrada:
<consulta_usuario>{{consulta_usuario}}</consulta_usuario>
<contexto_conversacion>{{contexto_conversacion_opcional}}</contexto_conversacion>

Salida — responde SOLO este JSON, sin texto adicional:
{
  "categoria": "una_de_las_6_categorias",
  "id_evento_detectado": null,
  "filtros_detectados": {},
  "falta_para_responder": [],
  "motivo": "una frase"
}
```

## Nota de implementación

El esqueleto de código (`src/agente.py`) incluye hoy una versión determinista de esta clasificación
(basada en palabras clave) para poder ejecutarse en modo demo sin credenciales de LLM. Al conectar el
LLM elegido (`LLM_PROVIDER`/`LLM_MODEL` en `.env`), este prompt sustituye a esa lógica por reglas.
