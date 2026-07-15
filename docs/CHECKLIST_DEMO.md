# Checklist de demo DS

Objetivo: ensenar que la capa DS aporta agentes funcionales conectados al producto.

## Antes de empezar

- Avisar a Front/FS de que la URL oficial es `https://despliegue-agentes.onrender.com`.
- Despertar Render con `GET /salud`.
- Esperar si el plan free tarda 50-60 segundos.
- Tener Thunder Client abierto con los ejemplos de `docs/ejemplos_requests/`.
- Tener capturas o respuestas JSON guardadas como plan B.

## Flujo recomendado

1. Health general
   - `GET /salud`
   - Objetivo: demostrar que el gateway ve los agentes.

2. Operis
   - `POST /agentes/operis/autocompletar`
   - Usar `operis_cliente.json` o archivo real.
   - Mensaje clave: extrae datos y propone campos editables; no guarda solo.

3. Lumen
   - `POST /agentes/lumen/chat`
   - Preguntar por eventos o ponentes.
   - Mensaje clave: consulta la BBDD y responde en lenguaje natural.

4. Jano
   - `POST /agentes/jano/buscar`
   - Abrir PDF de ponente y PDF interno.
   - Mensaje clave: propone transporte/alojamiento/taxi y genera documentos.

5. Vigil
   - `GET /agentes/vigil/concursos?limite=5`
   - Abrir ICS o PDF de pliego si hay `id_expediente`.
   - Mensaje clave: monitoriza oportunidades externas utiles para Mituyo/Mitumi.

6. Hermes
   - Probar solo si esta estable.
   - El ponente envia `/start` en Telegram.
   - Mensaje clave: canal directo para ponentes sin entrar en la app.

7. Garum
   - Probar solo si Composio esta configurado.
   - `POST /agentes/garum/ciclos`.
   - Mensaje clave: clasifica correo y prepara borradores/propuestas.

## Plan B

Si falla Render:

- Mostrar capturas de respuesta.
- Mostrar JSON guardado.
- Explicar que Render free puede dormirse.
- No improvisar cambios de codigo en directo.

Si falla Hermes:

- Revisar que no haya otra instancia local usando el mismo token.
- Revisar `ARRANCAR_HERMES` y `TELEGRAM_BOT_TOKEN`.
- Pedir al usuario de Telegram que envie `/start` de nuevo.

Si falla Operis con archivos:

- Probar primero JSON plano.
- Confirmar que el campo del archivo se llama `archivo`, `file`, `documento` o `upload`.
- Confirmar que el archivo es `.txt`, `.pdf` o `.docx`.
