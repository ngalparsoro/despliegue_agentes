# =====================================================================
# Imagen unica del sistema de agentes Backstage/Mitumi
# =====================================================================
# Todos los servicios conviven en un contenedor y se hablan por
# 127.0.0.1, igual que en local. El unico puerto expuesto es el del
# gateway (:$PORT), que es la puerta de entrada para el front.
#
# Construir y probar en local:
#   docker build -t agentes-backstage .
#   docker run --rm -p 5010:5003 -e PORT=5003 \
#     -e DATABASE_URL="postgresql://..." -e GROQ_API_KEY="..." \
#     agentes-backstage
#   curl http://localhost:5010/salud
# =====================================================================

FROM python:3.12-slim

WORKDIR /app

# OCR para PDFs escaneados en Operis: poppler convierte PDF->imagen y
# tesseract lee el texto de esas imagenes. spa+eng cubre documentos en
# castellano e ingles.
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-spa \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Primero SOLO los requirements: asi los pip install quedan cacheados
# y no se repiten en cada build al cambiar codigo.
COPY gateway/requirements.txt gateway/requirements.txt
COPY backend/requirements.txt backend/requirements.txt
COPY Lumen_buscador/lumen_agente_04/requirements.txt Lumen_buscador/lumen_agente_04/requirements.txt
COPY Operis_autocompletado/agente_operis_llm/requirements_servidor.txt Operis_autocompletado/agente_operis_llm/requirements_servidor.txt
COPY Jano_transporte/requirements.txt Jano_transporte/requirements.txt
COPY Vigil_busquedaconcursos/requirements.txt Vigil_busquedaconcursos/requirements.txt
COPY Garum_gestorcorreos/agente_gestor_correos/requirements.txt Garum_gestorcorreos/agente_gestor_correos/requirements.txt
COPY Hermes_telegram/agente_telegram_ponentes/requirements.txt Hermes_telegram/agente_telegram_ponentes/requirements.txt

# Operis: su requirements.txt completo arrastra streamlit (~200 MB, solo
# para su interfaz de prueba); aqui instalamos su set de servidor.
# Vigil: playwright se instala como libreria pero SIN navegadores
# (playwright install), asi que las ejecuciones en vivo no funcionan en
# esta imagen; el historico de concursos si (viene en vigil.db).
RUN pip install --no-cache-dir \
    -r gateway/requirements.txt \
    -r backend/requirements.txt \
    -r Lumen_buscador/lumen_agente_04/requirements.txt \
    -r Operis_autocompletado/agente_operis_llm/requirements_servidor.txt \
    -r Jano_transporte/requirements.txt \
    -r Vigil_busquedaconcursos/requirements.txt \
    -r Garum_gestorcorreos/agente_gestor_correos/requirements.txt \
    -r Hermes_telegram/agente_telegram_ponentes/requirements.txt \
    groq pypdf python-docx pdf2image pytesseract Pillow "psycopg[binary]"

# Ahora el codigo completo (lo que excluye .dockerignore no entra)
COPY . .

RUN chmod +x arrancar_render.sh

# Render inyecta PORT; en local se puede fijar con -e PORT=5003
EXPOSE 5003

CMD ["./arrancar_render.sh"]
