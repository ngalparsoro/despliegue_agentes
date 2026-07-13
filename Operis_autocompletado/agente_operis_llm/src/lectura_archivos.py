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


def leer_archivo(ruta_archivo):
    """
    Lee un archivo y devuelve su contenido como texto plano.

    Formatos soportados:
        - .txt  -> lectura directa
        - .pdf  -> usando PyPDF2 o pypdf
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
            try:
                import PyPDF2
                lector = PyPDF2.PdfReader(ruta_archivo)
                texto = ""
                for pagina in lector.pages:
                    texto += pagina.extract_text() + "\n"
                return texto
            except ImportError:
                try:
                    import pypdf
                    lector = pypdf.PdfReader(ruta_archivo)
                    texto = ""
                    for pagina in lector.pages:
                        texto += pagina.extract_text() + "\n"
                    return texto
                except ImportError:
                    raise ImportError(
                        "No se encontró ninguna librería para leer PDF. "
                        "Instala PyPDF2 o pypdf: pip install PyPDF2"
                    )
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
