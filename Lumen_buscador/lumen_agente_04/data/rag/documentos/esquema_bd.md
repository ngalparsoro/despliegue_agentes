# Esquema de base de datos — Ágora (plataforma Mitumi)

Documento de referencia (grounding) para Lumen. Es la **única fuente de verdad sobre nombres de tablas y campos**. Lumen debe citar siempre tabla y campo cuando responde con un dato concreto, y nunca debe inventar un campo o tabla que no esté aquí.

Si una consulta requiere un dato que no aparece en este esquema, Lumen debe declararlo como `bloqueo_detectado`, no inferirlo ni aproximarlo.

> Nota de versión: en este esquema la clave primaria de cada tabla es siempre el campo genérico `id`
> (no `id_cliente`, `id_evento`, etc.). Las claves foráneas conservan el nombre descriptivo
> (`id_cliente`, `id_estado`, `id_sala`, `id_presupuesto`, `id_ponencia`, `id_espacio`, `id_ponente`)
> y viven todas del lado de la tabla que referencia a la otra — `eventos` es la tabla central del
> modelo y concentra la mayoría de las FK.

## Tablas dentro del alcance de consulta de Lumen

### `clientes`
`id`, `cliente`, `email`, `telefono`, `empresa`, `sector`, `ciudad`

### `eventos`
`id`, `nombre_evento`, `ciudad`, `lugar_confirmado`, `fecha_inicio`, `fecha_fin`, `numero_personas`, `tipo_evento`, `nota`, `id_presupuesto` (FK → `presupuestos`), `id_cliente` (FK → `clientes`), `id_estado` (FK → `estados`), `id_sala` (FK → `salas`), `id_ponencia` (FK → `ponencias`)

### `presupuestos`
`id`, `estado_presupuesto`, `total`, `fecha`, `nota_ubicacion`, `precio_ubicacion`, `catering`, `nota_catering`, `precio_catering`, `audiovisuales`, `nota_audiovisuales`, `precio_audiovisuales`, `otros`, `nota_otros`, `precio_otros`, `observaciones`

No tiene FK propia hacia `eventos`: es `eventos.id_presupuesto` quien apunta a `presupuestos.id`.

### `salas`
`id`, `nombre_sala`, `tipo_sala`, `capacidad_max_sala`, `nota_sala`, `id_espacio` (FK → `espacios`)

### `espacios`
`id`, `nombre_espacio`, `ciudad`, `direccion`, `aforo`, `nota`, `telefono_contacto`, `nombre_contacto`, `email_contacto`

### `ponencias`
`id`, `nombre_hotel`, `nota_transporte`, `horario_ida_transporte`, `horario_vuelta_transporte`, `localizacion_hotel`, `horario_ponencia`, `checkin_horario`, `ponente_estado`, `presentacion_link`, `billete_ida_link`, `billete_vuelta_link`, `tipo_ponencia`, `id_ponente` (FK → `ponentes`)

No tiene FK propia hacia `eventos`: es `eventos.id_ponencia` quien apunta a `ponencias.id`. A diferencia
del modelo anterior (tabla puente `evento_ponente`, N:N entre eventos y ponentes), en este esquema
**cada evento enlaza como mucho con una única ponencia** (y por tanto con un único ponente a través de
ella). Si el usuario pregunta por "los ponentes" (plural) de un evento, Lumen debe responder según lo
que exista realmente — cero o un ponente — sin asumir que puede haber varios como antes.

### `ponentes`
`id`, `nombre_ponente`, `docu_identificacion`, `email`, `sector`, `telefono`, `foto_link`, `cv_link`, `empresa`, `cargo`

### `estados`
`id`, `descripcion`

## Relaciones principales

```text
clientes  1──N eventos          (eventos.id_cliente → clientes.id)
estados   1──N eventos          (eventos.id_estado → estados.id)
salas     1──N eventos          (eventos.id_sala → salas.id)
salas     N──1 espacios         (salas.id_espacio → espacios.id)
eventos   N──1 presupuestos     (eventos.id_presupuesto → presupuestos.id)
eventos   N──1 ponencias        (eventos.id_ponencia → ponencias.id)
ponencias N──1 ponentes         (ponencias.id_ponente → ponentes.id)
```

## Tabla FUERA de alcance — exclusión obligatoria

### `usuarios`
`id`, `nombre_usuario`, `rol`

Esta tabla **no forma parte del dominio de negocio del evento** (espacios, presupuesto, ponentes, clientes) — es la tabla de autenticación/gestión de acceso de la plataforma.

Regla dura, no negociable:

```text
Lumen NUNCA consulta la tabla `usuarios`.
Lumen NUNCA expone, confirma, niega ni infiere nada sobre credenciales de acceso de la plataforma
(contraseñas, tokens u otros secretos), existan o no como campo documentado en este esquema.
Si el usuario pregunta por credenciales, contraseñas, roles de acceso o datos de la tabla `usuarios`,
Lumen responde que está fuera de su alcance y lo marca como `bloqueo_detectado` con nivel_riesgo "alto".
```

Esta regla está implementada en dos capas: `prompts/prompt_sistema.md` (nivel LLM) y
`src/consultas.py` + `src/validaciones.py` (nivel código, defensa en profundidad).

## Datos personales — manejo sensible

`ponentes.docu_identificacion`, `ponentes.email`, `ponentes.telefono`, `clientes.email`, `clientes.telefono` son datos personales. Lumen puede consultarlos dentro de la plataforma para el equipo de Mitumi (uso interno legítimo), pero:

- no debe generar listados masivos exportables de estos campos salvo que el usuario lo pida explícitamente y de forma acotada;
- si la petición implica reenviar estos datos fuera de la plataforma (email externo, exportar a un tercero), debe marcarse `requiere_validacion_humana: true` y `nivel_riesgo: "medio"` como mínimo.
