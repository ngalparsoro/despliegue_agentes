"""Resumen del concurso en PDF (lo que muestra "Ver pliego" en la plataforma).

cuando alguien pulsa "ver pliego", vigil devuelve este pdf: un resumen de las
condiciones principales del concurso —objeto, poder adjudicador, importe, plazo,
urgencia, encaje con mitumi y áreas temáticas— más el enlace al anuncio oficial
en kontratazioa, que es el documento vinculante.

el resumen se arma solo con los datos que vigil ya tiene del concurso en el
histórico; no añade cláusulas que no estén en esos datos. para las condiciones
completas (criterios de adjudicación, solvencia, etc.) hay que consultar el
pliego oficial, cuyo enlace se incluye al final.
"""

# traigo datetime para sellar el pdf con la fecha de generación
from datetime import datetime
# traigo BytesIO para construir el pdf en memoria (sin escribir a disco)
from io import BytesIO

# traigo el color para los detalles visuales
from reportlab.lib import colors
# traigo el tamaño de página A4
from reportlab.lib.pagesizes import A4
# traigo la paleta de estilos y el constructor de estilos de párrafo
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# traigo las unidades de medida (milímetros)
from reportlab.lib.units import mm
# traigo los ladrillos del documento (párrafos, espacios, tablas)
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# traduzco el nivel de urgencia interno a un texto legible
_URGENCIA_TEXTO = {
    "alta": "Alta",
    "media": "Media",
    "baja": "Baja",
    "cerrado": "Cerrado (fuera de plazo)",
    "desconocida": "Sin determinar",
}


# construyo la hoja de estilos de párrafo que uso en el resumen
def _estilos():
    # parto de los estilos de ejemplo de reportlab
    base = getSampleStyleSheet()
    # título principal del documento
    base.add(
        ParagraphStyle(
            "TituloResumen",
            parent=base["Title"],
            fontSize=16,
            leading=20,
            spaceAfter=4,
        )
    )
    # subtítulo bajo el título (el objeto del contrato)
    base.add(
        ParagraphStyle(
            "Subtitulo",
            parent=base["Normal"],
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#444444"),
            spaceAfter=10,
        )
    )
    # nota aclaratoria de que es un resumen automático
    base.add(
        ParagraphStyle(
            "Nota",
            parent=base["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#666666"),
        )
    )
    # encabezado de cada apartado
    base.add(
        ParagraphStyle(
            "Apartado",
            parent=base["Heading2"],
            fontSize=11.5,
            leading=15,
            spaceBefore=12,
            spaceAfter=4,
            textColor=colors.HexColor("#1f2a5a"),
        )
    )
    # texto normal de cada apartado
    base.add(
        ParagraphStyle(
            "Cuerpo",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            spaceAfter=4,
        )
    )
    # devuelvo la hoja de estilos ya ampliada
    return base


# preparo el texto de la urgencia (nivel + días hábiles), o None si no hay
def _texto_urgencia(registro: dict) -> str | None:
    # leo el nivel de urgencia guardado
    nivel = registro.get("urgencia_nivel")
    # si no hay nivel, no muestro nada
    if not nivel:
        return None
    # traduzco el nivel a un texto legible
    texto = _URGENCIA_TEXTO.get(nivel, nivel)
    # leo los días hábiles restantes
    dias = registro.get("urgencia_dias")
    # si los tengo, los añado al texto cuidando el singular/plural
    if dias is not None:
        # uso "día hábil" cuando queda solo uno, y "días hábiles" en el resto
        if dias == 1:
            texto += " · 1 día hábil restante"
        else:
            texto += f" · {dias} días hábiles restantes"
    # devuelvo el texto montado
    return texto


# armo la tabla de "ficha del expediente" con los datos clave del concurso
def _tabla_ficha(registro: dict, estilos) -> Table:
    # preparo las parejas etiqueta/valor solo con los datos que existen
    posibles = [
        ("Expediente", registro.get("id_expediente")),
        ("Poder adjudicador", registro.get("organo_convocante")),
        ("Territorio (Diputación Foral)", registro.get("diputacion")),
        ("Presupuesto sin IVA", f"{registro['importe']} €" if registro.get("importe") else None),
        ("Fecha de publicación", registro.get("fecha_publicacion")),
        ("Fecha límite de presentación", registro.get("plazo_presentacion")),
        ("Urgencia", _texto_urgencia(registro)),
    ]
    # me quedo solo con las filas que tienen valor
    filas = [(etiqueta, valor) for etiqueta, valor in posibles if valor]
    # convierto cada pareja en dos párrafos (para que ajusten el ancho de celda)
    datos = [
        [Paragraph(f"<b>{etiqueta}</b>", estilos["Cuerpo"]), Paragraph(str(valor), estilos["Cuerpo"])]
        for etiqueta, valor in filas
    ]
    # creo la tabla con dos columnas de ancho fijo
    tabla = Table(datos, colWidths=[70 * mm, 95 * mm])
    # le doy un estilo sobrio con líneas suaves entre filas
    tabla.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    # devuelvo la tabla lista
    return tabla


# genero el PDF del resumen de un concurso y lo devuelvo como bytes
def generar_pliego_pdf(registro: dict) -> bytes:
    """Construye el PDF de resumen de un concurso a partir de su registro histórico.

    `registro` es el diccionario que devuelve `history.obtener(...)`.
    Devuelve el contenido del PDF en bytes, listo para servir.
    """
    # preparo el buffer en memoria donde se escribe el pdf
    buffer = BytesIO()
    # creo el documento A4 con márgenes cómodos
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
        title=f"Resumen del concurso {registro.get('id_expediente', '')}",
    )
    # traigo la hoja de estilos
    estilos = _estilos()
    # aquí voy juntando los elementos del documento en orden
    elementos = []

    # título del resumen
    elementos.append(Paragraph("Resumen del concurso", estilos["TituloResumen"]))
    # subtítulo: el objeto del contrato
    elementos.append(Paragraph(registro.get("objeto") or "(sin objeto)", estilos["Subtitulo"]))

    # ficha con los datos clave del expediente
    elementos.append(_tabla_ficha(registro, estilos))
    elementos.append(Spacer(1, 6))

    # apartado con el objeto completo del contrato
    elementos.append(Paragraph("Objeto del contrato", estilos["Apartado"]))
    elementos.append(Paragraph(registro.get("objeto") or "—", estilos["Cuerpo"]))

    # apartado con el encaje del concurso en el perfil de Mitumi
    relevante = registro.get("relevante")
    # redacto el veredicto según sea relevante, no relevante o sin evaluar
    if relevante is True:
        encaje = "Sí, encaja con el perfil de Mitumi (agencia de eventos)."
    elif relevante is False:
        encaje = "No encaja con el perfil de Mitumi."
    else:
        encaje = "Sin evaluar."
    elementos.append(Paragraph("Encaje con Mitumi", estilos["Apartado"]))
    elementos.append(Paragraph(encaje, estilos["Cuerpo"]))
    # si hay un motivo explicativo, lo añado
    if registro.get("motivo"):
        elementos.append(Paragraph(registro["motivo"], estilos["Cuerpo"]))

    # apartado con las áreas temáticas (etiquetas), si las hay
    etiquetas = registro.get("etiquetas") or []
    if etiquetas:
        elementos.append(Paragraph("Áreas temáticas", estilos["Apartado"]))
        elementos.append(Paragraph(", ".join(etiquetas) + ".", estilos["Cuerpo"]))

    # apartado con los requisitos que vigil no ha podido verificar, si los hay
    no_verificables = registro.get("campos_no_verificables") or []
    if no_verificables:
        elementos.append(Paragraph("Requisitos a verificar en el pliego", estilos["Apartado"]))
        elementos.append(
            Paragraph(
                "Vigil no ha podido confirmar estos requisitos contra el perfil de "
                "Mitumi; conviene revisarlos en el pliego oficial:",
                estilos["Cuerpo"],
            )
        )
        # listo cada requisito como una viñeta
        for req in no_verificables:
            elementos.append(Paragraph(f"• {req}", estilos["Cuerpo"]))

    # apartado con el enlace al anuncio oficial (el documento vinculante)
    enlace = registro.get("enlace_pliego")
    elementos.append(Paragraph("Pliego oficial", estilos["Apartado"]))
    # si el enlace es una url http(s), lo pongo como enlace clicable
    if enlace and enlace.startswith("http"):
        elementos.append(
            Paragraph(
                f'Consulta el pliego completo y las condiciones oficiales en KontratazioA: '
                f'<a href="{enlace}" color="#1f5ad6">{enlace}</a>',
                estilos["Cuerpo"],
            )
        )
    # si no hay enlace válido, lo digo claramente
    else:
        elementos.append(
            Paragraph("No consta enlace al pliego oficial en los datos del concurso.", estilos["Cuerpo"])
        )

    # pie del documento: aclaro que es un resumen automático y de dónde salen los datos
    elementos.append(Spacer(1, 14))
    elementos.append(
        Paragraph(
            "Resumen automático generado por Vigil a partir del anuncio de KontratazioA "
            f"el {datetime.now().strftime('%d/%m/%Y %H:%M')}. El documento vinculante es "
            "el pliego oficial enlazado arriba.",
            estilos["Nota"],
        )
    )

    # construyo el pdf con todos los elementos
    doc.build(elementos)
    # devuelvo los bytes del buffer
    return buffer.getvalue()


# construyo un nombre de fichero limpio para la descarga del resumen
def nombre_fichero_pliego(registro: dict) -> str:
    # cojo el id de expediente (o "concurso" si no hubiera)
    id_exp = registro.get("id_expediente") or "concurso"
    # cambio los caracteres problemáticos por guiones bajos
    seguro = id_exp.replace("/", "_").replace(" ", "_")
    # devuelvo el nombre con extensión .pdf
    return f"resumen_{seguro}.pdf"
