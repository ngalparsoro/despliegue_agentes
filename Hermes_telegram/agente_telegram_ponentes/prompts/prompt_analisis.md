# Tarea de análisis

Analiza el mensaje del ponente y devuelve siempre JSON válido, sin markdown, con esta estructura exacta:

```json
{
  "intencion": "consulta_alojamiento | consulta_viaje | consulta_taxi | consulta_horario | consulta_lugar | consulta_documentacion | consulta_servicio_adicional | solicitud_documento | resumen_viaje | seleccionar_evento | incidencia | saludo | otro",
  "urgencia": "baja | normal | alta",
  "servicio_consultado": "comida_restaurante | coche_alquiler | bus | parking | accesibilidad | wifi | otro | null",
  "respuesta_ponente": "texto amable para Telegram, solo cuando sea útil",
  "requiere_escalado": true,
  "motivo_escalado": "motivo o null",
  "confianza": 0.0
}
```

Reglas de clasificación:

- Vuelo, tren, billete o transporte principal: `consulta_viaje`.
- Taxi o traslado local: `consulta_taxi`.
- Hotel, habitación o check-in: `consulta_alojamiento`.
- Hora de ponencia o agenda: `consulta_horario`.
- Ubicación, dirección, sala o lugar del evento: `consulta_lugar`.
- Documentación pendiente: `consulta_documentacion`.
- Descargar o recibir un PDF, billete, presentación, agenda o documento: `solicitud_documento`.
- Resumen completo, itinerario o cronología del viaje: `resumen_viaje`.
- Restaurante, comida, desayuno, cena, catering, dietas o alergias: `consulta_servicio_adicional` y `servicio_consultado: comida_restaurante`.
- Coche de alquiler: `consulta_servicio_adicional` y `servicio_consultado: coche_alquiler`.
- Autobús, bus, minibús, lanzadera o shuttle: `consulta_servicio_adicional` y `servicio_consultado: bus`.
- Parking o aparcamiento: `consulta_servicio_adicional` y `servicio_consultado: parking`.
- Accesibilidad o movilidad reducida: `consulta_servicio_adicional` y `servicio_consultado: accesibilidad`.
- Wifi o internet: `consulta_servicio_adicional` y `servicio_consultado: wifi`.
- Cambiar o elegir evento: `seleccionar_evento`.
- Pérdida de billete, cancelación, retraso crítico o problema inmediato: `incidencia` y `urgencia: alta`.

Si falta un servicio adicional, no lo inventes y no marques escalado automático: el sistema ofrecerá al ponente un botón para solicitar contacto con MITUMI.

## Criterio estricto de urgencia

Marca `urgencia: alta` únicamente cuando el mensaje describa una situación inmediata que requiera intervención humana rápida, por ejemplo:

- pérdida de billete con salida próxima;
- vuelo o tren cancelado;
- ponente bloqueado o perdido sin poder continuar el viaje;
- imposibilidad inmediata de llegar al evento;
- accidente, problema de seguridad o emergencia;
- petición explícita y razonable de ayuda urgente.

No marques `urgencia: alta` por:

- falta de un dato no inmediato;
- preguntas normales sobre hotel, taxi, restaurante, horario o documentación;
- baja confianza de clasificación;
- servicio adicional no confirmado;
- solicitud ordinaria de contacto con MITUMI;
- saludo, selección de evento o consulta no comprendida.

Los avisos Telegram al administrador dependen de este campo. Ante duda y sin riesgo inmediato, utiliza `urgencia: normal`.
