# Contrato Front - Backend DS

Base URL produccion:

```text
https://despliegue-agentes.onrender.com
```

Todas las rutas pasan por el gateway. Front no debe llamar a puertos internos.

## Formato de errores

Formato comun esperado:

```json
{
  "error": true,
  "codigo": "...",
  "mensaje": "..."
}
```

Algunos agentes pueden anadir `detail` por compatibilidad con Flask/FastAPI.

## Health

```http
GET /salud
```

Uso: comprobar que el backend DS esta despierto antes de una demo.

## Lumen - consultas sobre BBDD

```http
POST /agentes/lumen/chat
Content-Type: application/json
```

Body:

```json
{
  "pregunta": "cuantos eventos confirmados tenemos?",
  "sesion_id": "demo-001"
}
```

Notas:

- `sesion_id` es opcional, pero Front debe conservarlo si quiere memoria conversacional.
- Lumen es solo lectura.
- No consulta `usuarios`.

## Operis - autocompletado

```http
POST /agentes/operis/autocompletar
```

JSON minimo:

```json
{
  "tipo_objetivo": "cliente",
  "texto": "Cliente: TechCorp SL. Email: laura@techcorp.es. Ciudad: Bilbao."
}
```

Multipart permitido:

- Campo archivo: `archivo`, `file`, `documento` o `upload`.
- Formatos: `.txt`, `.pdf`, `.docx`.
- Campos utiles: `tipo_objetivo`, `campos_objetivo`, `id_evento` opcional.

Notas:

- `id_evento` no es obligatorio.
- La respuesta es una propuesta editable.
- `requiere_validacion_humana` debe tratarse como `true`.

## Jano - hotel, viaje, taxi y PDFs

```http
POST /agentes/jano/buscar
Content-Type: application/json
```

Body ejemplo:

```json
{
  "nombre_ponente": "Carlos Barrabes",
  "email_ponente": "carlos@example.com",
  "nombre_evento": "Tech Summit 2026",
  "ciudad_evento": "Vitoria-Gasteiz",
  "fecha_inicio": "2026-09-18",
  "fecha_fin": "2026-09-18",
  "ciudad_origen": "Madrid",
  "personas": 1,
  "preferencias": "cerca del recinto",
  "necesita_hotel": true,
  "necesita_viaje": true,
  "necesita_taxi": true,
  "necesita_coche": false
}
```

Respuesta incluye:

```json
{
  "propuesta": { "id": "..." },
  "pdf_ponente": "/informes/{id}/ponente.pdf",
  "pdf_mitumi": "/informes/{id}/mitumi.pdf"
}
```

Para abrir PDF desde gateway:

```text
/agentes/jano/informes/{id}/ponente.pdf
/agentes/jano/informes/{id}/mitumi.pdf
```

## Vigil - concursos publicos

Listar:

```http
GET /agentes/vigil/concursos?limite=5
```

Filtros frecuentes:

```text
q=eventos
en_plazo=true
limite=5
offset=0
```

Documentos:

```http
GET /agentes/vigil/concursos/{id_expediente}/calendario.ics
GET /agentes/vigil/concursos/{id_expediente}/pliego.pdf
```

Ejecucion:

```http
POST /agentes/vigil/ejecuciones
GET /agentes/vigil/ejecuciones/{run_id}
```

## Garum - gestor de correos

Lanzar ciclo:

```http
POST /agentes/garum/ciclos
```

Consultar:

```http
GET /agentes/garum/ciclos/{id_ciclo}
```

Garum no envia correos automaticamente; deja borradores/propuestas segun configuracion.

## Hermes - Telegram

Hermes no es endpoint HTTP para Front. Es un bot de Telegram.

Condiciones para probarlo:

- `TELEGRAM_BOT_TOKEN` configurado.
- Una sola instancia activa del bot.
- `ARRANCAR_HERMES=true` si corre en Render.
- `data/estado/mapeo_telegram_ponentes.json` vincula usuario Telegram con `id_ponente`.
- Si se cambia el mapeo, conviene limpiar:
  - `data/estado/eventos_activos_telegram.json`
  - `data/estado/solicitudes_contacto_telegram.json`

## Checklist para Front/FS

Antes de integrar:

- Usar siempre la base URL de Render o la local del gateway, no puertos internos.
- Tratar errores `4xx/5xx` como errores de agente, no como fallo visual sin mensaje.
- En Operis, pintar datos como propuesta editable.
- En Jano, prefijar `/agentes/jano` a rutas de PDF devueltas como `/informes/...`.
- En Lumen, conservar `sesion_id` si se quiere memoria.
- En demo, despertar Render con `GET /salud` antes de empezar.
