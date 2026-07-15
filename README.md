# Backend DS oficial - Agentes de Eventos

Este es el repositorio canonico del equipo de Data Science para el proyecto Mituyo/Mitumi Backstage. Desde ahora, este repo es la fuente de verdad para el backend agentico desplegado en Render.

URL de produccion:

```text
https://despliegue-agentes.onrender.com
```

El repositorio anterior `Agentes_Eventos` queda como historico/desarrollo previo. Cualquier cambio que deba llegar a Front o a Render debe hacerse aqui.

## Que contiene

Un unico servicio desplegable que levanta varias piezas internas y expone una sola URL publica mediante el gateway:

| Pieza | Funcion | Consumo |
|---|---|---|
| Gateway | Entrada unica para Front | HTTP `/agentes/...` |
| Lumen | Chat de consulta sobre la BBDD | HTTP |
| Operis | Autocompletado desde texto/archivo | HTTP |
| Jano | Busqueda de hotel, viaje, taxi y PDFs | HTTP |
| Vigil | Concursos publicos, ICS y PDF | HTTP |
| Garum | Gestion/clasificacion de correo | HTTP por ciclos |
| Hermes | Bot de Telegram para ponentes | Telegram, no HTTP de Front |
| Backend agentes | Lectura auxiliar de Neon | Interno |

## Arquitectura

```text
Front / FS
   |
   v
https://despliegue-agentes.onrender.com
   |
   v
Gateway FastAPI (:5003)
   |-- Lumen (:5001)
   |-- Operis (:5002)
   |-- Jano (:8001)
   |-- Vigil (:8000)
   |-- Garum (ciclos bajo demanda)
   |-- Backend agentes (:5004)
   '-- Hermes (bot Telegram, opcional en Render)
```

## Endpoints principales

Base URL:

```text
https://despliegue-agentes.onrender.com
```

| Agente | Metodo | Ruta | Uso |
|---|---:|---|---|
| Salud | GET | `/salud` | Health agregado de agentes |
| Lumen | POST | `/agentes/lumen/chat` | Preguntas sobre la BBDD |
| Lumen | POST | `/agentes/lumen/chat/reset` | Reset de una sesion |
| Operis | POST | `/agentes/operis/autocompletar` | Autocompletar formularios desde texto o archivo |
| Jano | POST | `/agentes/jano/buscar` | Buscar hotel/viaje/taxi/coche |
| Jano | GET | `/agentes/jano/informes/{id}/ponente.pdf` | PDF sin precios para ponente |
| Jano | GET | `/agentes/jano/informes/{id}/mitumi.pdf` | PDF interno con precios |
| Vigil | GET | `/agentes/vigil/concursos` | Lista/filtro de concursos publicos |
| Vigil | GET | `/agentes/vigil/concursos/{id}/calendario.ics` | Calendario ICS |
| Vigil | GET | `/agentes/vigil/concursos/{id}/pliego.pdf` | PDF/resumen de pliego |
| Vigil | POST | `/agentes/vigil/ejecuciones` | Lanza ejecucion de busqueda |
| Vigil | GET | `/agentes/vigil/ejecuciones/{run_id}` | Estado de ejecucion |
| Garum | POST | `/agentes/garum/ciclos` | Lanza ciclo de correo |
| Garum | GET | `/agentes/garum/ciclos/{id_ciclo}` | Consulta resultado del ciclo |

Contrato detallado para Front/FS: [docs/CONTRATO_FRONT_DS.md](docs/CONTRATO_FRONT_DS.md).

## Estados de evento

La BBDD actual no tiene tabla `estados` ni `eventos.id_estado`. El estado operativo vive directamente en `eventos.estado` como texto.

Catalogo vigente:

```text
Planificado, Reservado, Confirmado, Finalizado, Cancelado
```

Hermes considera activos, por defecto:

```text
Planificado, Reservado, Confirmado
```

## Variables de entorno

Las claves reales se configuran en Render o en `.env` local. Nunca se suben al repo.

| Variable | Uso |
|---|---|
| `DATABASE_URL` | Neon/Postgres readonly para agentes |
| `GROQ_API_KEY` | LLM de Lumen, Operis, Jano, Vigil |
| `LLM_PROVIDER` | Proveedor LLM, normalmente `groq` |
| `TELEGRAM_BOT_TOKEN` | Bot Hermes |
| `ARRANCAR_HERMES` | `true` solo si Hermes corre en Render |
| `EVENT_ACTIVE_STATES` | Estados activos para Hermes |
| `COMPOSIO_API_KEY` | Garum/Gmail |
| `COMPOSIO_USER_ID` | Usuario Composio de Garum |

Ver ejemplo completo en [.env.example](.env.example).

## Despliegue en Render

Render esta conectado a este repo. Para desplegar cambios:

1. Hacer commit y push a `main`.
2. Ir al servicio `despliegue_agentes` en Render.
3. Pulsar `Manual Deploy` -> `Deploy latest commit`.
4. Probar `GET /salud`.

El plan free puede dormirse tras inactividad; la primera peticion puede tardar alrededor de 50-60 segundos.

## Arranque local

```bash
cp .env.example .env
# rellenar variables
./arrancar_todo.sh
./comprobar_salud.sh
```

Para arrancar Hermes localmente:

```bash
./arrancar_todo.sh --con-hermes
```

Ojo: solo debe haber una instancia del bot de Telegram activa con el mismo token, ya sea local o Render.

## Reglas de trabajo

- Este repo es el oficial para DS y Render.
- No duplicar cambios en repos antiguos salvo necesidad puntual.
- No subir `.env`, tokens, credenciales ni cadenas owner de Neon.
- Los agentes proponen o consultan; no ejecutan escrituras reales de negocio.
- Antes de tocar logica estable, probar endpoints actuales y coordinar con Front/FS.

## Limitaciones conocidas

- Render free puede dormirse.
- Vigil en Render sirve resultados y documentos; el scraping vivo puede estar limitado por entorno.
- Hermes depende del mapeo Telegram -> ponente y de que la BBDD tenga ponencias/eventos enlazados.
- Garum necesita Composio configurado para Gmail.
- Operis requiere validacion humana: su salida es propuesta editable, no guardado automatico.
