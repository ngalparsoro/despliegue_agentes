# Guia de despliegue - Backend DS oficial

Este repositorio es la fuente de verdad del backend DS desplegado en Render.

URL de produccion:

```text
https://despliegue-agentes.onrender.com
```

Documentacion principal: [README.md](README.md)
Contrato para Front/FS: [docs/CONTRATO_FRONT_DS.md](docs/CONTRATO_FRONT_DS.md)

## Puesta en marcha local

1. Instalar dependencias:

```bash
for req in $(find . -name "requirements*.txt"); do pip install -r "$req"; done
```

2. Crear `.env`:

```bash
cp .env.example .env
```

3. Rellenar credenciales en `.env`:

- `DATABASE_URL`
- `GROQ_API_KEY`
- `TELEGRAM_BOT_TOKEN` si se prueba Hermes
- `COMPOSIO_API_KEY` si se prueba Garum

4. Arrancar:

```bash
./arrancar_todo.sh
./comprobar_salud.sh
```

Para Hermes local:

```bash
./arrancar_todo.sh --con-hermes
```

## Despliegue en Render

1. Hacer commit y push a `main`.
2. En Render, abrir el servicio `despliegue_agentes`.
3. Pulsar `Manual Deploy` -> `Deploy latest commit`.
4. Probar:

```text
GET https://despliegue-agentes.onrender.com/salud
```

## Variables en Render

Configurar en el panel de Render, nunca en Git:

- `DATABASE_URL`
- `GROQ_API_KEY`
- `LLM_PROVIDER=groq`
- `COMPOSIO_API_KEY`
- `COMPOSIO_USER_ID`
- `TELEGRAM_BOT_TOKEN`
- `ARRANCAR_HERMES`
- `EVENT_ACTIVE_STATES=Planificado,Reservado,Confirmado`

## Estados de evento

No existe tabla `estados` ni `eventos.id_estado`. El estado vive en `eventos.estado`.

Catalogo:

```text
Planificado, Reservado, Confirmado, Finalizado, Cancelado
```

## Mapa de puertos internos

| Puerto | Servicio |
|---|---|
| 5003 | Gateway, unica entrada HTTP publica |
| 5001 | Lumen |
| 5002 | Operis |
| 5004 | Backend de datos para agentes |
| 8000 | Vigil |
| 8001 | Jano |
| - | Hermes y Garum bajo demanda/proceso |
