# Runbook de despliegue

Este documento es solo la guia operativa de Render. La descripcion completa del proyecto, agentes, endpoints y estados vive en [README.md](README.md). El contrato que debe consumir Front/FS vive en [docs/CONTRATO_FRONT_DS.md](docs/CONTRATO_FRONT_DS.md).

## Servicio

```text
https://despliegue-agentes.onrender.com
```

Render despliega la rama `main` de este repositorio.

## Checklist de deploy

1. Confirmar que los cambios estan en `main` y subidos a GitHub.
2. Abrir el servicio `despliegue_agentes` en Render.
3. Pulsar `Manual Deploy` -> `Deploy latest commit`.
4. Esperar a que el evento quede como `Deploy live`.
5. Probar `GET /salud`.
6. Probar el endpoint del agente afectado con los ejemplos de [docs/ejemplos_requests](docs/ejemplos_requests).

## Variables obligatorias

Las variables reales se configuran en Render, nunca en Git. Usar [.env.example](.env.example) como plantilla.

Minimo recomendado:

- `DATABASE_URL`
- `GROQ_API_KEY`
- `LLM_PROVIDER=groq`
- `EVENT_ACTIVE_STATES=Planificado,Reservado,Confirmado`

Segun agente:

- `TELEGRAM_BOT_TOKEN` y `ARRANCAR_HERMES=true` para Hermes.
- `COMPOSIO_API_KEY` y `COMPOSIO_USER_ID` para Garum.

## Arranque local rapido

```bash
cp .env.example .env
./arrancar_todo.sh
./comprobar_salud.sh
```

Para probar Hermes localmente:

```bash
./arrancar_todo.sh --con-hermes
```

Solo debe existir una instancia activa de Hermes con el mismo token: local o Render.

## Diagnostico rapido

| Sintoma | Revision |
|---|---|
| `GET /salud` tarda mucho | Render free puede estar despertando tras inactividad. |
| Un agente responde `AGENTE_CAIDO` | Revisar logs de Render y puerto interno del agente. |
| Lumen no lee datos reales | Revisar `DATABASE_URL` y esquema actual de Neon. |
| Operis no autocompleta archivo | Confirmar envio `multipart/form-data` o campo `texto`/`contenido`. |
| Hermes no responde en Telegram | Verificar token, una sola instancia activa y mapeo ponente/chat. |

Limitaciones y riesgos: [docs/LIMITACIONES_CONOCIDAS.md](docs/LIMITACIONES_CONOCIDAS.md).
