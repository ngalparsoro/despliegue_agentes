"""Modelos Pydantic v2 usados a lo largo del pipeline (Vigil 2.0)."""

# importo las anotaciones de tipo modernas para poder escribir "str | None"
from __future__ import annotations

# traigo Literal (lista cerrada de valores) y Optional (algo que puede ser None)
from typing import Literal, Optional

# traigo la clase base de Pydantic y Field para describir cada campo
from pydantic import BaseModel, Field

# defino que una diputación solo puede ser una de estas tres palabras exactas
Diputacion = Literal["Araba", "Gipuzkoa", "Bizkaia"]

# defino los niveles posibles del semáforo de urgencia
NivelUrgencia = Literal["alta", "media", "baja", "cerrado", "desconocida"]


# creo el molde de una convocatoria ya limpia y estructurada
class Convocatoria(BaseModel):
    """Una convocatoria/licitación tal como se estructura tras pasar por extractor.py."""

    # guardo el código de expediente (el identificador único de la convocatoria)
    id_expediente: str
    # guardo a qué diputación pertenece (solo Araba, Gipuzkoa o Bizkaia)
    diputacion: Diputacion
    # guardo el objeto del contrato (qué se pide en el concurso)
    objeto: str
    # guardo quién convoca el concurso
    organo_convocante: str
    # guardo el importe; lo dejo en None si no consigo sacarlo del pliego
    importe: Optional[str] = Field(
        default=None, description="Null si el pliego no permite extraer un importe claro."
    )
    # guardo la fecha límite para presentarse; None si no la puedo sacar
    plazo_presentacion: Optional[str] = Field(
        default=None, description="Null si no se pudo extraer una fecha límite clara."
    )
    # guardo el enlace al pliego para poder abrirlo desde el email
    enlace_pliego: str
    # guardo la fecha de primera publicación si está disponible
    fecha_publicacion: Optional[str] = None
    # guardo la fecha de última publicación (la uso para detectar modificaciones)
    fecha_ultima_publicacion: Optional[str] = None


# creo el molde del veredicto que devuelve el filtro de relevancia
class VeredictoRelevancia(BaseModel):
    """Salida del filtro semántico de relevance.py."""

    # apunto si la convocatoria es relevante (True) o no (False)
    relevante: bool
    # explico con palabras por qué encaja o no encaja con Mitumi
    motivo: str = Field(
        description="Explicación concreta del encaje (o no encaje) con el perfil de Mitumi, "
        "no basta con 'es relevante'."
    )
    # guardo las etiquetas temáticas para poder repartir la revisión por áreas
    etiquetas: list[str] = Field(
        # si el modelo no devuelve ninguna, empiezo con una lista vacía
        default_factory=list,
        description="Etiquetas temáticas del concurso (p. ej. Institucional, Cultura, "
        "Gastronomía). Sirven para que el equipo se reparta la revisión.",
    )
    # guardo una lista de requisitos que no puedo confirmar contra el perfil de Mitumi
    campos_no_verificables: list[str] = Field(
        # si no hay ninguno, empiezo con una lista vacía
        default_factory=list,
        description="Requisitos del pliego que no se pueden confirmar ni descartar contra el "
        "perfil de Mitumi (p. ej. certificaciones, facturación mínima).",
    )


# creo el molde del resultado del semáforo de urgencia
class Urgencia(BaseModel):
    """Resultado del cálculo de urgencia (ver urgency.py)."""

    # guardo el nivel: alta, media, baja, cerrado o desconocida
    nivel: NivelUrgencia
    # guardo cuántos días hábiles quedan; None si no lo puedo calcular
    dias_habiles_restantes: Optional[int] = None
    # guardo el texto que mostraré en el email (p. ej. "URGENCIA ALTA · 3 días hábiles")
    etiqueta: str


# creo el molde que junta todo lo de una convocatoria relevante para el email
class Alerta(BaseModel):
    """Empaqueta una convocatoria relevante con todo lo que necesita el email."""

    # guardo la convocatoria estructurada
    convocatoria: Convocatoria
    # guardo el veredicto de relevancia (motivo, etiquetas, etc.)
    veredicto: VeredictoRelevancia
    # guardo el resultado del semáforo de urgencia
    urgencia: Urgencia
    # apunto si esta convocatoria es una modificación de una ya vista
    es_modificacion: bool = False
