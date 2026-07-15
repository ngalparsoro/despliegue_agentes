# Limitaciones conocidas

Este documento recoge limitaciones actuales para que Front/FS y DS no las confundan con errores inesperados.

## Infraestructura

- Render free puede dormirse por inactividad.
- La primera peticion tras dormir puede tardar alrededor de 50-60 segundos.
- El gateway es la unica URL publica; los puertos internos no deben usarse desde Front.

## BBDD y estados

- No existe tabla `estados` ni `eventos.id_estado`.
- El estado operativo vive en `eventos.estado`.
- Catalogo vigente: `Planificado`, `Reservado`, `Confirmado`, `Finalizado`, `Cancelado`.
- Los agentes leen con rol readonly; las escrituras reales son responsabilidad del backend FS.

## Lumen

- Es solo consulta.
- No consulta `usuarios`.
- Para mantener memoria, Front debe reenviar `sesion_id`.

## Operis

- La salida es propuesta editable, no guardado automatico.
- Requiere validacion humana.
- Archivos soportados: `.txt`, `.pdf`, `.docx`.
- PDFs escaneados pueden fallar si no hay texto extraible/OCR suficiente.

## Jano

- No lee BBDD; funciona con el formulario que le manda Front.
- Si `necesita_viaje=true`, `ciudad_origen` es obligatorio.
- Los PDFs generados son efimeros y dependen del almacenamiento temporal del servicio.

## Vigil

- En Render puede servir historico y documentos.
- El scraping vivo puede estar limitado por entorno, dependencias o navegador headless.
- Para demo, priorizar `GET /concursos` y documentos ya generables.

## Hermes

- Solo puede haber una instancia activa con el mismo `TELEGRAM_BOT_TOKEN`.
- No es endpoint HTTP para Front; se prueba desde Telegram.
- Depende de `mapeo_telegram_ponentes.json` para vincular usuario Telegram con `id_ponente`.
- Si cambia el mapeo, conviene limpiar:
  - `eventos_activos_telegram.json`
  - `solicitudes_contacto_telegram.json`

## Garum

- Depende de Composio/Gmail.
- No debe enviar correos automaticamente en demo; debe generar borradores/propuestas.
- Si faltan credenciales, debe fallar de forma controlada.
