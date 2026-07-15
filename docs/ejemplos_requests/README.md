# Ejemplos de requests para Thunder Client

Base URL de produccion:

```text
https://despliegue-agentes.onrender.com
```

Antes de probar en demo, despertar Render:

```http
GET https://despliegue-agentes.onrender.com/salud
```

## Lumen

Consulta general:

```http
POST /agentes/lumen/chat
Content-Type: application/json
```

Body: [lumen_chat_eventos.json](lumen_chat_eventos.json)

Consulta global de ponentes:

```http
POST /agentes/lumen/chat
Content-Type: application/json
```

Body: [lumen_chat_ponentes.json](lumen_chat_ponentes.json)

Reset de sesion:

```http
POST /agentes/lumen/chat/reset
Content-Type: application/json
```

Body: [lumen_reset.json](lumen_reset.json)

## Operis

Autocompletar cliente desde texto:

```http
POST /agentes/operis/autocompletar
Content-Type: application/json
```

Body: [operis_cliente.json](operis_cliente.json)

Autocompletar evento desde texto:

```http
POST /agentes/operis/autocompletar
Content-Type: application/json
```

Body: [operis_evento.json](operis_evento.json)

Para archivo, usar `multipart/form-data`:

- file field: `archivo`, `file`, `documento` o `upload`
- campos opcionales: `tipo_objetivo`, `campos_objetivo`, `id_evento`
- formatos: `.txt`, `.pdf`, `.docx`

## Jano

Buscar alojamiento, viaje y taxi:

```http
POST /agentes/jano/buscar
Content-Type: application/json
```

Body: [jano_buscar.json](jano_buscar.json)

Si la respuesta devuelve:

```json
{
  "pdf_ponente": "/informes/{id}/ponente.pdf",
  "pdf_mitumi": "/informes/{id}/mitumi.pdf"
}
```

Abrir desde gateway:

```text
GET /agentes/jano/informes/{id}/ponente.pdf
GET /agentes/jano/informes/{id}/mitumi.pdf
```

## Vigil

Health:

```http
GET /agentes/vigil/health
```

Listar concursos:

```http
GET /agentes/vigil/concursos?limite=5
```

Filtrar:

```http
GET /agentes/vigil/concursos?q=eventos&en_plazo=true&limite=5
```

Documentos por expediente:

```http
GET /agentes/vigil/concursos/{id_expediente}/calendario.ics
GET /agentes/vigil/concursos/{id_expediente}/pliego.pdf
```

Lanzar ejecucion:

```http
POST /agentes/vigil/ejecuciones
```

Consultar ejecucion:

```http
GET /agentes/vigil/ejecuciones/{run_id}
```

## Garum

Lanzar ciclo:

```http
POST /agentes/garum/ciclos
```

Consultar ciclo:

```http
GET /agentes/garum/ciclos/{id_ciclo}
```

## Hermes

Hermes no se prueba con Thunder Client: es bot de Telegram.

Checklist de prueba:

1. Confirmar que solo hay una instancia activa del bot.
2. Confirmar `TELEGRAM_BOT_TOKEN` en Render.
3. Si corre en Render, `ARRANCAR_HERMES=true`.
4. El usuario de Telegram debe estar en `Hermes_telegram/agente_telegram_ponentes/data/estado/mapeo_telegram_ponentes.json`.
5. El usuario envia `/start` en Telegram.
