"""Catálogo interno de tools controladas por Python.

El LLM no recibe estas tools.
"""


tools = {
    "obtener_correos_no_leidos": {
        "area": "gmail",
        "descripcion": "Obtiene correos no leídos.",
    },
    "clasificar_correo": {
        "area": "llm",
        "descripcion": "Clasifica el correo con LLM.",
    },
    "detectar_documentos": {
        "area": "python",
        "descripcion": "Registra los adjuntos del correo.",
    },
    "sugerir_etiquetas": {
        "area": "python",
        "descripcion": "Propone etiquetas MITUMI.",
    },
    "redactar_borrador": {
        "area": "llm",
        "descripcion": "Redacta un borrador.",
    },
    "crear_borrador": {
        "area": "gmail",
        "descripcion": "Crea un borrador sin enviarlo.",
    },
    "marcar_como_leido": {
        "area": "gmail",
        "descripcion": "Quita la etiqueta UNREAD.",
    },
    "obtener_registro_correo": {
        "area": "memoria",
        "descripcion": "Recupera el estado previo.",
    },
    "registrar_correo": {
        "area": "memoria",
        "descripcion": "Guarda el resultado y evita duplicados.",
    },
}
