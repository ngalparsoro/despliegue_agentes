"""
lectura_archivos.py — utilidad de lectura de archivos (.txt/.pdf/.docx).

Antes vivía en src/funciones.py junto con el motor de reglas (regex +
etiquetas). El motor de reglas se eliminó (ver README.md, "Motor de
extracción": ahora solo "llm") porque quedó incompatible con el nuevo
esquema de 4 bloques + Nota Bene — construía su salida sobre los 6
bloques antiguos (espacio/sala/presupuesto ya no existen como bloques
propios). leer_archivo() en cambio es independiente del motor: solo
convierte un documento a texto plano, así que se mantiene tal cual.

Usada por main.py y streamlit_app.py antes de construir el payload.
"""

import os


OCR_MAX_PAGES_DEFAULT = 8


def _leer_pdf_con_libreria(ruta_archivo):
    """Extrae texto de un PDF con capa de texto usando PyPDF2 o pypdf."""
    try:
        import PyPDF2
        lector = PyPDF2.PdfReader(ruta_archivo)
    except ImportError:
        try:
            import pypdf
            lector = pypdf.PdfReader(ruta_archivo)
        except ImportError as exc:
            raise ImportError(
                "No se encontró ninguna librería para leer PDF. "
                "Instala PyPDF2 o pypdf."
            ) from exc

    textos = []
    for pagina in lector.pages:
        texto_pagina = pagina.extract_text() or ""
        if texto_pagina.strip():
            textos.append(texto_pagina)
    return "\n".join(textos).strip()


def _limite_paginas_ocr():
    valor = os.getenv("OPERIS_OCR_MAX_PAGES", str(OCR_MAX_PAGES_DEFAULT))
    try:
        return max(1, int(valor))
    except ValueError:
        return OCR_MAX_PAGES_DEFAULT


def _leer_pdf_con_ocr(ruta_archivo):
    """
    Extrae texto de PDFs escaneados usando OCR.

    Requiere dependencias Python (pdf2image, pytesseract, Pillow) y dependencias
    del sistema en el contenedor/maquina (poppler-utils y tesseract-ocr).
    """
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError as exc:
        raise ImportError(
            "El PDF no tiene texto extraible y OCR no esta disponible. "
            "Instala pdf2image, pytesseract, Pillow, poppler-utils y tesseract-ocr."
        ) from exc

    max_paginas = _limite_paginas_ocr()
    paginas = convert_from_path(
        ruta_archivo,
        dpi=200,
        first_page=1,
        last_page=max_paginas,
    )

    textos = []
    for pagina in paginas:
        texto_pagina = pytesseract.image_to_string(pagina, lang="spa+eng") or ""
        if texto_pagina.strip():
            textos.append(texto_pagina)
    return "\n".join(textos).strip()


def _leer_pdf(ruta_archivo):
    texto = _leer_pdf_con_libreria(ruta_archivo)
    if texto:
        return texto
    return _leer_pdf_con_ocr(ruta_archivo)


def leer_archivo(ruta_archivo):
    """
    Lee un archivo y devuelve su contenido como texto plano.

    Formatos soportados:
        - .txt  -> lectura directa
        - .pdf  -> pypdf/PyPDF2; si no hay texto, OCR sobre las primeras paginas
        - .docx -> usando python-docx

    Args:
        ruta_archivo (str): Ruta al archivo.

    Returns:
        str: Contenido del archivo como texto.

    Raises:
        ValueError: Si el formato no está soportado.
        Exception: Si hay un error al leer el archivo.
    """
    extension = os.path.splitext(ruta_archivo)[1].lower()

    if extension == ".txt":
        try:
            with open(ruta_archivo, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            with open(ruta_archivo, "r", encoding="latin-1") as f:
                return f.read()

    elif extension == ".pdf":
        try:
            return _leer_pdf(ruta_archivo)
        except Exception as e:
            raise Exception(f"Error al leer el PDF: {str(e)}")

    elif extension == ".docx":
        try:
            import docx
            documento = docx.Document(ruta_archivo)
            texto = ""
            for parrafo in documento.paragraphs:
                texto += parrafo.text + "\n"
            return texto
        except ImportError:
            raise ImportError(
                "No se encontró la librería para leer DOCX. "
                "Instala python-docx: pip install python-docx"
            )
        except Exception as e:
            raise Exception(f"Error al leer el DOCX: {str(e)}")

    else:
        raise ValueError(
            f"Lo siento, no soy capaz de leer este formato ({extension}). "
            "Solamente puedo leer .pdf, .docx y .txt"
        )
