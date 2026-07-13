"""Perfil de negocio de Mitumi, usado como contexto fijo para el filtro de relevancia.

Contenido tomado tal cual de la sección 6 del build brief (basado en la web de
Mitumi y documentos reales, no es especulativo).
"""

# guardo en una constante todo el texto que describe a Mitumi
MITUMI_PROFILE = """\
QUIÉN ES: Agencia de eventos boutique con sede en Vitoria-Gasteiz. Equipo
reducido de forma deliberada, apoyado en una red de colaboradores externos
(comunicación, diseño digital, fotografía, sonido).

TIPOS DE EVENTO QUE ORGANIZA:
- Eventos corporativos (family days, encuentros internos, inauguraciones,
  aniversarios)
- Entregas de premios (con secretaría técnica y protocolo)
- Marketing experiencial y eventos de calle (ferias, activaciones de marca,
  presentaciones de producto)
- Congresos y asambleas, tanto empresariales como INSTITUCIONALES (gestión
  del espacio, ponentes, catering; presencial, virtual o híbrido)
- Eventos gastronómicos — especialidad de la casa (showcookings, catas,
  degustaciones, talleres)
- Formación en creatividad, procesos participativos y de escucha, diseño
  gráfico

FUERA DE PERFIL: fiestas privadas (bodas, comuniones, bautizos) — no
relevante para contratación pública.

TRACK RECORD CON EL SECTOR PÚBLICO:
- Cliente institucional recurrente: Ayuntamiento de Vitoria-Gasteiz
  (campañas de comercio urbano, congresos, festivales, campañas de
  sensibilización).
- Cliente recurrente: Diputación Foral de Álava, varios proyectos.
- Trabaja también con entes semipúblicos de Álava: BIC Araba, Egibide,
  Cámara de Comercio de Álava, Tuvisa, CIC energiGUNE.
- SIN historial conocido de contratos en Bizkaia o Gipuzkoa — tratar esos
  territorios como oportunidad de expansión, no como trayectoria
  consolidada.
- Los proyectos institucionales conocidos parecen sobre todo contratos
  directos o de importe menor, no grandes licitaciones formales — no
  asumir trayectoria en concursos de gran volumen.

ESCALA: agencia boutique — formato pequeño-mediano (decenas a varios
cientos de asistentes), no macroproducciones. Tiene acceso a recintos
mucho más grandes (hasta miles de asistentes) a través de su red, pero
no es su terreno habitual.

ZONA GEOGRÁFICA: núcleo en Vitoria-Gasteiz/Araba, opera con normalidad
en toda la Comunidad Autónoma del País Vasco. Logística de ponentes con
alcance nacional.

NO VERIFICABLE — no asumir ni en un sentido ni en otro, marcar como tal
si el pliego lo exige:
- Certificaciones formales (ISO 20121 u otras de gestión sostenible de
  eventos)
- Facturación / clasificación empresarial
"""


# devuelvo el texto del perfil para que otros módulos lo usen
def get_business_profile() -> str:
    # entrego la constante con el perfil de Mitumi
    return MITUMI_PROFILE
