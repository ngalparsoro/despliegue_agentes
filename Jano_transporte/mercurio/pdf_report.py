"""Genera los informes de viaje en PDF (para enviar por email o mensaje).

Hay dos variantes de la misma propuesta:

- **informe del ponente** (`incluir_precios=False`): sin ningún importe, para que
  el ponente no elija siempre la opción más cara.
- **informe para Mitumi** (`incluir_precios=True`): con precios, coste estimado y
  la recomendación con importes, para que la organización decida.

Usa reportlab (platypus). Si reportlab no está instalado, no rompe: registra el
aviso y devuelve None (la búsqueda sigue funcionando, solo sin PDF).
"""

# importo las anotaciones modernas
from __future__ import annotations

# traigo logging para avisar si no se puede generar el PDF
import logging
# traigo os para componer rutas de los ficheros
import os

# traigo el molde de la propuesta y sus horarios
from mercurio.schemas import OpcionTransporte, PropuestaViaje

# creo un registrador con el nombre de este módulo
logger = logging.getLogger(__name__)


# formateo un datetime ISO a "dd/mm HH:MM" para las tablas del PDF
def _hm(dt_iso: str) -> str:
    # traigo datetime solo aquí para no cargarlo si no genero PDF
    from datetime import datetime
    # intento parsear; si no puedo, devuelvo el texto tal cual
    try:
        d = datetime.fromisoformat(dt_iso)
        return d.strftime("%d/%m %H:%M")
    except (ValueError, TypeError):
        return dt_iso


# convierto minutos en un texto "2h 15min"
def _dur(minutos: int) -> str:
    # separo horas y minutos
    h, m = divmod(minutos, 60)
    # devuelvo el formato compacto
    return f"{h}h {m:02d}min"


# describo una opción de transporte en una fila (con o sin precio)
def _fila_transporte(op: OpcionTransporte, incluir_precios: bool) -> list[str]:
    # marco si es directo o cuántas escalas tiene
    escalas = "Directo" if op.ida.escalas == 0 else f"{op.ida.escalas} escala(s)"
    # armo las celdas comunes
    fila = [
        op.proveedor,
        f"{_hm(op.ida.salida)} → {_hm(op.ida.llegada)}",
        f"{_hm(op.vuelta.salida)} → {_hm(op.vuelta.llegada)}",
        f"{_dur(op.ida.duracion_min)} · {escalas}",
    ]
    # solo en la versión de Mitumi añado el precio
    if incluir_precios:
        fila.append(f"{op.precio_total:.0f} {op.moneda}")
    return fila


# genero UN PDF (variante ponente o Mitumi) en la ruta indicada
def generar_pdf(propuesta: PropuestaViaje, ruta: str, incluir_precios: bool) -> str | None:
    """Escribe el informe en `ruta`. Devuelve la ruta, o None si falla.

    `incluir_precios=False` → informe del ponente (sin importes).
    `incluir_precios=True`  → informe para Mitumi (con importes).
    """
    # intento importar reportlab; si no está, aviso y sigo sin PDF
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        )
    except ImportError:
        # dejo constancia: se puede instalar con `pip install reportlab`
        logger.warning(
            "reportlab no está instalado; no genero PDF. Instálalo con "
            "`pip install reportlab` para activar el informe."
        )
        return None

    # intento construir el documento y capturo cualquier fallo
    try:
        # preparo la hoja de estilos base y añado los míos
        estilos = getSampleStyleSheet()
        estilos.add(ParagraphStyle(name="Kicker", fontSize=9, textColor=colors.HexColor("#0d9488"), spaceAfter=2))
        estilos.add(ParagraphStyle(name="H1b", fontSize=18, leading=22, spaceAfter=6, textColor=colors.HexColor("#1a1d24")))
        estilos.add(ParagraphStyle(name="Sec", fontSize=12, leading=16, spaceBefore=12, spaceAfter=4, textColor=colors.HexColor("#1a1d24")))
        estilos.add(ParagraphStyle(name="Small", fontSize=9, leading=13, textColor=colors.HexColor("#6b7280")))

        # creo el documento sobre el fichero de salida
        doc = SimpleDocTemplate(
            ruta, pagesize=A4,
            leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
        )
        # preparo la lista de elementos (el "flujo" del documento)
        el: list = []
        # saco el ponente para escribir más corto
        pon = propuesta.ponente
        # el destinatario cambia el subtítulo de cabecera
        destinatario = "Informe para Mitumi" if incluir_precios else "Informe de viaje"

        # --- cabecera ---
        el.append(Paragraph("MERCURIO · MITUMI BACKSTAGE", estilos["Kicker"]))
        el.append(Paragraph(f"{destinatario} — {pon.nombre}", estilos["H1b"]))
        el.append(Paragraph(
            f"{propuesta.evento.nombre or 'Evento'}<br/>"
            f"{pon.ciudad_origen or 'origen sin definir'} → {propuesta.evento.ciudad} · "
            f"Llegada {propuesta.fecha_llegada} · Salida {propuesta.fecha_salida} · "
            f"{propuesta.noches} noche(s) · {propuesta.personas} persona(s)",
            estilos["Small"],
        ))

        # --- resumen (sin precios en ambas variantes) ---
        if propuesta.resumen:
            el.append(Paragraph("Resumen", estilos["Sec"]))
            el.append(Paragraph(propuesta.resumen, estilos["BodyText"]))

        # --- recomendación (con o sin importes según la variante) ---
        recomendacion = propuesta.recomendacion if incluir_precios else propuesta.recomendacion_sin_precio
        if recomendacion:
            el.append(Paragraph("Recomendación", estilos["Sec"]))
            el.append(Paragraph(recomendacion, estilos["BodyText"]))
            # el coste estimado solo en la versión de Mitumi
            if incluir_precios and propuesta.coste_estimado is not None:
                el.append(Paragraph(
                    f"Coste estimado (hotel + transporte): "
                    f"<b>{propuesta.coste_estimado:.0f} EUR</b>",
                    estilos["BodyText"],
                ))

        # --- por qué esta recomendación ---
        # al ponente le doy los motivos de comodidad (sin precio); a Mitumi, los de coste
        justificacion = propuesta.justificacion if incluir_precios else propuesta.justificacion_ponente
        if justificacion:
            el.append(Paragraph("¿Por qué esta recomendación?", estilos["Sec"]))
            el.append(Paragraph(justificacion, estilos["BodyText"]))

        # estilo común para las tablas
        estilo_tabla = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef1f6")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#455065")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e6e8ec")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafbfc")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])

        # --- hoteles ---
        if propuesta.hoteles:
            el.append(Paragraph("Hoteles sugeridos", estilos["Sec"]))
            if incluir_precios:
                # versión Mitumi: con precio por noche y total
                datos = [["Hotel", "Cat.", "Valor.", "Dist.", "Hab.", "€/noche", "Total"]]
                for h in propuesta.hoteles:
                    datos.append([
                        h.nombre, f"{h.estrellas}★", f"{h.valoracion:.1f}",
                        f"{h.distancia_recinto_km:.1f} km", str(h.habitaciones),
                        f"{h.precio_noche:.0f}", f"{h.precio_total:.0f} {h.moneda}",
                    ])
                anchos = [5.3 * cm, 1.2 * cm, 1.4 * cm, 1.7 * cm, 1.1 * cm, 1.8 * cm, 2.5 * cm]
            else:
                # versión ponente: sin ningún importe
                datos = [["Hotel", "Cat.", "Valoración", "Distancia al recinto"]]
                for h in propuesta.hoteles:
                    datos.append([
                        h.nombre, f"{h.estrellas}★", f"{h.valoracion:.1f} / 10",
                        f"{h.distancia_recinto_km:.1f} km",
                    ])
                anchos = [8.5 * cm, 1.8 * cm, 3.0 * cm, 3.7 * cm]
            t = Table(datos, colWidths=anchos)
            t.setStyle(estilo_tabla)
            el.append(t)

        # preparo la cabecera y anchos de las tablas de transporte según la variante
        if incluir_precios:
            cab_trans = ["", "Ida", "Vuelta", "Duración", "Precio"]
            anchos_trans = [3.3 * cm, 3.4 * cm, 3.4 * cm, 3.0 * cm, 2.3 * cm]
        else:
            cab_trans = ["", "Ida", "Vuelta", "Duración"]
            anchos_trans = [3.5 * cm, 4.5 * cm, 4.5 * cm, 4.5 * cm]

        # --- vuelos ---
        if propuesta.vuelos:
            el.append(Paragraph("Vuelos (ida y vuelta)", estilos["Sec"]))
            datos = [["Aerolínea", *cab_trans[1:]]]
            datos.extend(_fila_transporte(v, incluir_precios) for v in propuesta.vuelos)
            t = Table(datos, colWidths=anchos_trans)
            t.setStyle(estilo_tabla)
            el.append(t)

        # --- trenes ---
        if propuesta.trenes:
            el.append(Paragraph("Trenes (ida y vuelta)", estilos["Sec"]))
            datos = [["Operador", *cab_trans[1:]]]
            datos.extend(_fila_transporte(tr, incluir_precios) for tr in propuesta.trenes)
            t = Table(datos, colWidths=anchos_trans)
            t.setStyle(estilo_tabla)
            el.append(t)

        # --- taxi ---
        if propuesta.taxis:
            el.append(Paragraph("Taxi / traslados", estilos["Sec"]))
            if incluir_precios:
                datos = [["Proveedor", "Servicio", "Precio est."]]
                for tx in propuesta.taxis:
                    datos.append([tx.proveedor, tx.descripcion, f"{tx.precio_estimado:.0f} {tx.moneda}"])
                anchos = [4.0 * cm, 8.5 * cm, 2.5 * cm]
            else:
                datos = [["Proveedor", "Servicio"]]
                for tx in propuesta.taxis:
                    datos.append([tx.proveedor, tx.descripcion])
                anchos = [5.0 * cm, 10.0 * cm]
            t = Table(datos, colWidths=anchos)
            t.setStyle(estilo_tabla)
            el.append(t)

        # --- coche de alquiler ---
        if propuesta.coches:
            el.append(Paragraph("Coche de alquiler", estilos["Sec"]))
            if incluir_precios:
                datos = [["Compañía", "Categoría", "Oficina", "€/día", "Total"]]
                for co in propuesta.coches:
                    datos.append([co.compania, co.categoria, co.oficina, f"{co.precio_dia:.0f}", f"{co.precio_total:.0f} {co.moneda}"])
                anchos = [3.2 * cm, 2.6 * cm, 4.8 * cm, 1.8 * cm, 2.6 * cm]
            else:
                datos = [["Compañía", "Categoría", "Oficina"]]
                for co in propuesta.coches:
                    datos.append([co.compania, co.categoria, co.oficina])
                anchos = [4.0 * cm, 3.5 * cm, 7.5 * cm]
            t = Table(datos, colWidths=anchos)
            t.setStyle(estilo_tabla)
            el.append(t)

        # --- pie ---
        el.append(Spacer(1, 16))
        # el pie cambia: al ponente no le hablo de precios
        if incluir_precios:
            pie = ("Precios y horarios orientativos. Documento interno de Mitumi. "
                   "Generado automáticamente por Mercurio.")
        else:
            pie = ("Horarios orientativos. La reserva la gestiona la organización de "
                   "Mitumi. Generado automáticamente por Mercurio.")
        el.append(Paragraph(pie, estilos["Small"]))

        # construyo el PDF sobre la ruta
        doc.build(el)
        # devuelvo la ruta como confirmación
        return ruta
    # si algo falla al construir el PDF...
    except Exception:
        # dejo el error en el registro y sigo sin PDF
        logger.exception("Fallo al generar el PDF (%s).", ruta)
        return None


# genero las DOS variantes (ponente y Mitumi) de una propuesta en una carpeta
def generar_ambos(propuesta: PropuestaViaje, carpeta: str) -> dict[str, str | None]:
    """Escribe los dos PDFs y devuelve {'ponente': ruta|None, 'mitumi': ruta|None}."""
    # me aseguro de que la carpeta existe
    os.makedirs(carpeta, exist_ok=True)
    # compongo las rutas de los dos ficheros a partir del id de la búsqueda
    ruta_ponente = os.path.join(carpeta, f"{propuesta.id}_ponente.pdf")
    ruta_mitumi = os.path.join(carpeta, f"{propuesta.id}_mitumi.pdf")
    # genero cada variante
    return {
        "ponente": generar_pdf(propuesta, ruta_ponente, incluir_precios=False),
        "mitumi": generar_pdf(propuesta, ruta_mitumi, incluir_precios=True),
    }
