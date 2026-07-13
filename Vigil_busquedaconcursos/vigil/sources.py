"""Lectura de KontratazioA (Plataforma de Contratación Pública de Euskadi).

Validado en vivo antes de escribir este módulo (ver sección 5 del build
brief): la vista de resultados en formato tabla ("formatoTabla") depende de
un grid AJAX propio del Gobierno Vasco no documentado — un POST directo
devuelve 405 o "Introduzca más criterios de filtrado" sin importar el
payload probado. La vista "ampliado" (formatoAmpliado), en cambio, es una
página de resultados renderizada en servidor y paginada por el propio
servidor, con cada convocatoria en HTML semántico (legend + dl de
etiqueta/valor). Se usa Playwright únicamente para llegar a esa página con
las cookies de sesión y las interacciones de UI correctas (autocompletado de
poder adjudicador); el parsing en sí es BeautifulSoup sobre HTML ya
renderizado, no scraping de un widget JS en vivo.
"""

# traigo re para buscar patrones de texto (el número total de resultados)
import re
# traigo utilidades de fechas para calcular la ventana de días a mirar
from datetime import datetime, timedelta

# traigo BeautifulSoup para leer y recorrer el HTML de la web
from bs4 import BeautifulSoup
# traigo Playwright para manejar un navegador de verdad sin ventana
from playwright.sync_api import Page, sync_playwright

# traigo del config la lista de diputaciones, la URL y el molde Diputacion
from vigil.config import DIPUTACIONES, KONTRATAZIOA_URL, Diputacion

# guardo la dirección base del portal para completar los enlaces
BASE_URL = "https://www.contratacion.euskadi.eus"
# decido cuántos días hacia atrás miro; dedupe.py ya descarta lo repetido
LOOKBACK_DAYS = 7
# pongo un tope de páginas por seguridad (cada página trae 10 resultados)
MAX_PAGINAS = 50


# escribo el nombre de la diputación en el buscador y la selecciono
def _seleccionar_diputacion(page: Page, diputacion: Diputacion) -> bool:
    """Escribe el término de búsqueda en el autocompletado y selecciona la diputación.

    El autocompletado del portal no siempre devuelve la entidad correcta en
    primera posición (ni siquiera al buscar su nombre oficial completo — ver
    el comentario en config.py), así que se busca la sugerencia cuyo texto
    coincide EXACTAMENTE con el nombre de la diputación, no "la primera".
    Devuelve False si no aparece ninguna sugerencia con ese texto exacto, o
    si el id seleccionado no coincide con el esperado.
    """
    # hago clic en la casilla del poder adjudicador
    page.click("#poderAdjudicador_label")
    # borro lo que pudiera haber escrito antes
    page.fill("#poderAdjudicador_label", "")
    # tecleo el término de búsqueda letra a letra (con pequeña pausa)
    page.type("#poderAdjudicador_label", diputacion.busqueda, delay=40)
    # espero a que aparezca la lista de sugerencias
    try:
        # doy hasta 8 segundos a que salga al menos una sugerencia
        page.wait_for_selector("#poderAdjudicador_menu li", timeout=8000)
    # si no aparece ninguna sugerencia...
    except Exception:
        # aviso de que no pude seleccionarla
        return False

    # recojo todas las sugerencias que han aparecido
    opciones = page.query_selector_all("#poderAdjudicador_menu li")
    # de momento no he encontrado la que busco
    objetivo = None
    # recorro cada sugerencia
    for opcion in opciones:
        # leo su texto y le quito espacios sobrantes
        texto = (opcion.inner_text() or "").strip()
        # si el texto coincide exactamente con el nombre que busco...
        if texto == diputacion.nombre:
            # me quedo con esta sugerencia
            objetivo = opcion
            # dejo de buscar
            break
    # si no encontré ninguna que coincida exactamente...
    if objetivo is None:
        # aviso de que no pude seleccionarla
        return False

    # hago clic en la sugerencia correcta
    objetivo.click()
    # espero un momento a que la web guarde la selección
    page.wait_for_timeout(200)
    # leo el id interno que ha quedado seleccionado
    valor = page.eval_on_selector("#poderAdjudicador", "el => el.value")
    # confirmo que el id seleccionado es el que esperaba
    return str(valor) == str(diputacion.id_poder)


# saco los datos de un bloque de resultado del HTML
def _parse_resultado(bloque, diputacion_nombre: str) -> dict:
    # busco el titular del bloque (el objeto del contrato)
    legend = bloque.select_one("legend")
    # cojo su texto limpio, o cadena vacía si no hay
    objeto = legend.get_text(strip=True) if legend else ""

    # busco el enlace de "ver detalle" dentro del bloque
    enlace_a = bloque.select_one(".ver-detalle a")
    # construyo la URL completa del pliego, o vacía si no hay enlace
    enlace = BASE_URL + enlace_a["href"] if enlace_a and enlace_a.get("href") else ""

    # preparo un diccionario para los campos de etiqueta/valor
    campos: dict[str, str | None] = {}
    # busco la lista de definiciones (dl) con los campos
    dl = bloque.select_one("dl")
    # si existe esa lista...
    if dl:
        # recorro cada etiqueta (dt) de la lista
        for dt in dl.find_all("dt"):
            # leo el nombre del campo (la etiqueta)
            clave = dt.get_text(strip=True)
            # busco el valor que va justo después de la etiqueta
            dd = dt.find_next_sibling("dd")
            # guardo el valor limpio, o None si no hay
            campos[clave] = dd.get_text(strip=True) if dd else None

    # devuelvo un diccionario con todos los datos que he sacado
    return {
        # apunto a qué diputación pertenece
        "diputacion": diputacion_nombre,
        # apunto el objeto del contrato
        "objeto": objeto,
        # apunto el enlace al pliego
        "enlace_pliego": enlace,
        # apunto el código de expediente
        "id_expediente": campos.get("Expediente"),
        # apunto la fecha de primera publicación
        "fecha_publicacion": campos.get("Fecha primera publicación"),
        # apunto la fecha de última publicación (para detectar modificaciones)
        "fecha_ultima_publicacion": campos.get("Fecha última publicación"),
        # apunto el tipo de contrato
        "tipo_contrato": campos.get("Tipo de contrato"),
        # apunto el estado de la tramitación
        "estado_tramitacion": campos.get("Estado de la tramitación"),
        # apunto la fecha límite de presentación
        "plazo_presentacion": campos.get("Fecha límite de presentación"),
        # apunto el presupuesto sin IVA
        "importe": campos.get("Presupuesto del contrato sin IVA"),
        # apunto el poder adjudicador
        "organo_convocante": campos.get("Poder adjudicador"),
        # apunto la entidad impulsora
        "entidad_impulsora": campos.get("Entidad Impulsora"),
    }


# extraigo todos los resultados de la página actual
def _extraer_pagina(page: Page, diputacion_nombre: str) -> list[dict]:
    # leo el HTML completo de la página con BeautifulSoup
    soup = BeautifulSoup(page.content(), "html.parser")
    # busco todos los bloques de resultado
    bloques = soup.select("div.bloqueResultado")
    # convierto cada bloque en un diccionario y los devuelvo en una lista
    return [_parse_resultado(b, diputacion_nombre) for b in bloques]


# leo cuántos resultados en total ha encontrado la búsqueda
def _total_items(page: Page) -> int:
    # intento leer el mensaje que dice "N items encontrados"
    try:
        # cojo el texto de ese mensaje
        texto = page.eval_on_selector("div.mensajeInfo span", "el => el.innerText")
    # si no lo encuentro...
    except Exception:
        # asumo que hay cero
        return 0
    # busco el número dentro del texto con un patrón
    m = re.search(r"(\d+)\s+items?\s+encontrado", texto)
    # devuelvo ese número, o cero si no lo encontré
    return int(m.group(1)) if m else 0


# hago la búsqueda completa para una diputación
def consultar_diputacion(page: Page, diputacion: Diputacion, fecha_desde: str) -> list[dict]:
    """Busca en KontratazioA las convocatorias de una diputación desde una fecha dada."""
    # abro la página de búsqueda del portal
    page.goto(KONTRATAZIOA_URL, timeout=30000)
    # espero a que cargue la casilla del poder adjudicador
    page.wait_for_selector("#poderAdjudicador_label", timeout=15000)

    # selecciono la diputación; si no puedo, aviso con un error claro
    if not _seleccionar_diputacion(page, diputacion):
        # lanzo un error explicando que la web pudo haber cambiado
        raise RuntimeError(
            f"No se pudo seleccionar '{diputacion.nombre}' en el autocompletado "
            "de poder adjudicador — la web puede haber cambiado."
        )

    # marco la opción de resultados en formato ampliado
    page.check("#formatoAmpliado")
    # escribo la fecha desde la que quiero buscar
    page.fill("#fechaPublicacionDesde", fecha_desde)
    # hago clic fuera para que la web confirme la selección del buscador
    page.click("body")
    # espero un momento
    page.wait_for_timeout(200)

    # hago clic en el botón de buscar
    page.click("#btnBuscar")
    # espero a que me lleve a la página de resultados ampliados
    page.wait_for_url("**/informacionAmpliadaAnuncios/search", timeout=20000)

    # extraigo los resultados de la primera página
    resultados = _extraer_pagina(page, diputacion.nombre)
    # miro cuántos resultados hay en total
    total = _total_items(page)
    # calculo cuántas páginas hay (10 por página), sin pasar del tope
    total_paginas = min(MAX_PAGINAS, (total + 9) // 10)

    # recorro las páginas que quedan después de la primera
    for _ in range(total_paginas - 1):
        # busco el botón de "siguiente"
        boton_siguiente = page.query_selector("#pagSiguiente")
        # si no hay botón, dejo de paginar
        if boton_siguiente is None:
            break
        # hago clic en "siguiente"
        boton_siguiente.click()
        # espero a que cargue la nueva página
        page.wait_for_timeout(1500)
        # añado los resultados de esta página a la lista
        resultados.extend(_extraer_pagina(page, diputacion.nombre))

    # devuelvo todos los resultados de esta diputación
    return resultados


# compruebo si una convocatoria se publicó dentro de la ventana reciente
def _publicada_recientemente(resultado: dict, limite: datetime) -> bool:
    """Filtro de seguridad en cliente.

    El filtro "fechaPublicacionDesde" del propio portal no se comporta como
    cabría esperar en pruebas (se han visto expedientes de 2024 pidiendo solo
    3 días hacia atrás) — probablemente compara contra la fecha de última
    actualización del registro, no la de primera publicación. Por eso se
    filtra aquí explícitamente por "Fecha primera publicación" para quedarnos
    solo con convocatorias realmente nuevas.
    """
    # leo la fecha de publicación de la convocatoria
    fecha_txt = resultado.get("fecha_publicacion")
    # si no hay fecha, la descarto
    if not fecha_txt:
        return False
    # intento convertir el texto de fecha a una fecha de verdad
    try:
        # transformo "dd/mm/aaaa" en un objeto fecha
        fecha = datetime.strptime(fecha_txt, "%d/%m/%Y")
    # si el texto no tiene ese formato...
    except ValueError:
        # la descarto para no equivocarme
        return False
    # me quedo con ella solo si es igual o posterior al límite
    return fecha >= limite


# función principal del módulo: consulto las tres diputaciones
def obtener_convocatorias() -> list[dict]:
    """Consulta KontratazioA para las tres diputaciones forales.

    Devuelve una lista de diccionarios "crudos" (texto tal como aparece en la
    web), uno por convocatoria publicada en los últimos LOOKBACK_DAYS días.
    extractor.py se encarga de convertirlos al schema Convocatoria.
    """
    # calculo la fecha desde la que buscar, en texto para la web
    fecha_desde = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime("%d/%m/%Y")
    # calculo la misma fecha como objeto, para el filtro de seguridad
    limite = datetime.now() - timedelta(days=LOOKBACK_DAYS)
    # preparo la lista donde junto los resultados de las tres diputaciones
    resultados: list[dict] = []

    # arranco Playwright y me aseguro de cerrarlo al terminar
    with sync_playwright() as p:
        # abro un navegador Chromium sin ventana visible
        browser = p.chromium.launch(headless=True)
        # intento hacer el trabajo y garantizo cerrar el navegador
        try:
            # recorro cada una de las tres diputaciones
            for diputacion in DIPUTACIONES:
                # abro una pestaña nueva (ignorando el aviso de certificado)
                page = browser.new_page(ignore_https_errors=True)
                # intento la búsqueda y me aseguro de cerrar la pestaña
                try:
                    # busco las convocatorias crudas de esta diputación
                    crudos = consultar_diputacion(page, diputacion, fecha_desde)
                    # me quedo solo con las publicadas dentro de la ventana reciente
                    resultados.extend(r for r in crudos if _publicada_recientemente(r, limite))
                # pase lo que pase, cierro la pestaña
                finally:
                    page.close()
        # pase lo que pase, cierro el navegador
        finally:
            browser.close()

    # devuelvo todas las convocatorias recientes de las tres diputaciones
    return resultados
