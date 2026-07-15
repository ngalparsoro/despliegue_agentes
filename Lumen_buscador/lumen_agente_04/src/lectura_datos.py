"""
Acceso de SOLO LECTURA a los datos de Agora para Lumen (Agente 04 - Copilot).

Fuente unica: conexion directa de solo lectura a Postgres (integrations/db_backend.py,
DATABASE_URL en .env). Ya no hay mock JSON ni API HTTP intermedia — se retiraron
deliberadamente para que Lumen dependa de una unica base de datos, sin ambiguedad sobre de
donde sale cada dato. Si la conexion falla, estas funciones no inventan ni aproximan nada:
dejan que DbBackendError suba hasta src/nucleo.py, que lo convierte en un bloqueo explicito.

La tabla `usuarios` esta bloqueada aqui a nivel de codigo, no solo por prompt: es defensa en
profundidad ante un fallo del LLM o de la capa que lo invoque. integrations/db_backend.py hace la misma
comprobacion de forma independiente (defensa en dos capas).
"""

from config.permisos import TABLAS_EXCLUIDAS, TABLAS_PERMITIDAS
from integrations import db_backend


class TablaNoPermitida(PermissionError):
    """Se lanza si se intenta acceder a una tabla fuera del alcance de Lumen (p.ej. 'usuarios')."""


def tabla_existe(nombre_tabla):
    return nombre_tabla in TABLAS_PERMITIDAS


def _verificar_permiso(tabla):
    if tabla in TABLAS_EXCLUIDAS:
        raise TablaNoPermitida("Lumen no tiene acceso a la tabla '" + tabla + "'.")
    if tabla not in TABLAS_PERMITIDAS:
        raise TablaNoPermitida("Tabla '" + tabla + "' fuera del alcance de Lumen.")


def _obtener_por_id(tabla, id_valor, conn=None):
    _verificar_permiso(tabla)
    return db_backend.obtener_por_id(tabla, id_valor, conn=conn)


def _listar(tabla):
    _verificar_permiso(tabla)
    return db_backend.listar(tabla) or []


def evento_existe(id_evento):
    return resumen_evento(id_evento) is not None


def resumen_evento(id_evento):
    """Devuelve el registro de eventos correspondiente, o None si no existe."""
    return _obtener_por_id("eventos", id_evento)


def _ponente_por_id(id_ponente, conn=None):
    if id_ponente is None:
        return None
    return _obtener_por_id("ponentes", id_ponente, conn=conn)


def _ponencia_del_evento(evento, conn=None):
    """
    Devuelve la ponencia enlazada al evento (via eventos.id_ponencia), o None si el evento no
    tiene ninguna ponencia asociada. Un evento enlaza como mucho con una unica ponencia (y por
    tanto un unico ponente) - ver data/rag/documentos/esquema_bd.md.
    """
    id_ponencia = evento.get("id_ponencia")
    if id_ponencia is None:
        return None
    return _obtener_por_id("ponencias", id_ponencia, conn=conn)


def ponentes_sin_billete_vuelta(id_evento):
    """
    Devuelve la lista de ponentes (dicts) del evento dado cuyo billete_vuelta_link
    esta vacio. Devuelve None si el evento no existe. Con el esquema actual la lista
    contendra como mucho un elemento (un evento enlaza con una unica ponencia/ponente).
    """
    evento = resumen_evento(id_evento)
    if evento is None:
        return None

    ponencia = _ponencia_del_evento(evento)
    if ponencia is None or ponencia.get("billete_vuelta_link"):
        return []

    ponente = _ponente_por_id(ponencia.get("id_ponente"))
    return [ponente] if ponente else []


def ponentes_sin_billete_ida(id_evento):
    """Analogo a ponentes_sin_billete_vuelta pero para el billete de ida."""
    evento = resumen_evento(id_evento)
    if evento is None:
        return None

    ponencia = _ponencia_del_evento(evento)
    if ponencia is None or ponencia.get("billete_ida_link"):
        return []

    ponente = _ponente_por_id(ponencia.get("id_ponente"))
    return [ponente] if ponente else []



def ponentes_registrados():
    """
    Devuelve un listado seguro de ponentes registrados para consultas globales.

    Se excluyen campos personales sensibles como documento, email, telefono, foto o CV.
    Lumen puede dar conteos y listados basicos sin pedir id_evento, pero no exporta datos
    personales masivos desde una pregunta global.
    """
    campos_seguros = ("id", "nombre_ponente", "empresa", "cargo", "sector")
    resultado = []
    for ponente in _listar("ponentes"):
        resumen = {campo: ponente.get(campo) for campo in campos_seguros if ponente.get(campo)}
        if resumen:
            resultado.append(resumen)
    return resultado
ESTADOS_EVENTO_CANONICOS = ("Planificado", "Reservado", "Confirmado", "Finalizado", "Cancelado")


def _estado_evento(evento):
    return str(evento.get("estado") or "").strip()


def estados_disponibles():
    """Lista de estados disponibles desde eventos.estado (Prisma elimino public.estados)."""
    vistos = {_estado_evento(ev) for ev in _listar("eventos") if _estado_evento(ev)}
    extras = sorted(estado for estado in vistos if estado not in ESTADOS_EVENTO_CANONICOS)
    return list(ESTADOS_EVENTO_CANONICOS) + extras


def eventos_por_estado(descripcion_estado):
    """
    Devuelve eventos cuyo campo textual eventos.estado coincide con `descripcion_estado`.
    El catalogo vive ahora en la propia tabla eventos, no en una tabla de traduccion.
    """
    buscado = str(descripcion_estado or "").strip().lower()
    resultado = []
    for ev in _listar("eventos"):
        if _estado_evento(ev).lower() == buscado:
            enriquecido = dict(ev)
            enriquecido["estado"] = _estado_evento(ev)
            resultado.append(enriquecido)
    return resultado


def todos_los_eventos():
    """
    Devuelve todos los eventos usando directamente el campo textual eventos.estado.
    """
    resultado = []
    for ev in _listar("eventos"):
        enriquecido = dict(ev)
        enriquecido["estado"] = _estado_evento(ev)
        resultado.append(enriquecido)
    return resultado


def contexto_completo_evento(id_evento):
    """
    Agrega todo el contexto de negocio de un evento (evento, presupuesto, sala, espacio,
    cliente, ponente via su ponencia) en un unico dict, EXCLUYENDO siempre la tabla `usuarios`.

    Todas las lecturas (evento + hasta 5 tablas relacionadas) van sobre UNA sola conexion
    readonly, no una por tabla: antes esto abria ~6 conexiones a Postgres por cada consulta libre
    de un evento. Si la BD no esta disponible, abrir_conexion() lanza DbBackendError, que sube a
    src/nucleo.py igual que antes.
    """
    with db_backend.abrir_conexion() as conn:
        evento = _obtener_por_id("eventos", id_evento, conn=conn)
        if evento is None:
            return None

        presupuesto_encontrado = _obtener_por_id("presupuestos", evento.get("id_presupuesto"), conn=conn)
        sala_encontrada = _obtener_por_id("salas", evento.get("id_sala"), conn=conn)

        espacio_encontrado = None
        if sala_encontrada:
            espacio_encontrado = _obtener_por_id("espacios", sala_encontrada.get("id_espacio"), conn=conn)

        cliente_encontrado = _obtener_por_id("clientes", evento.get("id_cliente"), conn=conn)

        ponencia_encontrada = _ponencia_del_evento(evento, conn=conn)
        ponentes_del_evento = []
        if ponencia_encontrada is not None:
            ponente = _ponente_por_id(ponencia_encontrada.get("id_ponente"), conn=conn)
            if ponente:
                combinado = dict(ponente)
                combinado.update(ponencia_encontrada)
                ponentes_del_evento.append(combinado)

        return {
            "evento": evento,
            "presupuesto": presupuesto_encontrado,
            "sala": sala_encontrada,
            "espacio": espacio_encontrado,
            "cliente": cliente_encontrado,
            "ponentes": ponentes_del_evento,
        }
