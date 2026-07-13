# streamlit_app.py
# =====================================================================
# INTERFAZ DE PRUEBA PARA EL AGENTE OPERIS - v4 (esquema de 4 bloques)
# =====================================================================
# Esta aplicación Streamlit permite probar el agente Operis con:
#   - Subida de archivos (.txt, .pdf, .docx)
#   - Pegado de texto manual
#   - id_evento (obligatorio en el contrato) y clave de Groq pegable
#   - Selector de bloques a actualizar (actualización parcial)
#   - Histórico LOCAL por id_evento
#   - Visualización de los 4 bloques:
#       * Evento, Cliente, Ponentes como pestañas
#       * NOTA BENE como panel fijo en la parte superior (destacado)
#   - Descarga del JSON de salida
#
# Motor único: llm (Groq). El motor de reglas se eliminó del agente.
#
# Uso:
#   streamlit run streamlit_app.py
# =====================================================================

import streamlit as st
import json
from pathlib import Path
from datetime import datetime
import tempfile
import os

# Configuración de la página
st.set_page_config(
    page_title="Agente Operis - Pruebas",
    page_icon="📋",
    layout="wide"
)

# ---------------------------------------------------------------------
# 1. IMPORTACIONES DEL PROYECTO
# ---------------------------------------------------------------------
import sys
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.nucleo import ejecutar_agente
from src.lectura_archivos import leer_archivo
from src.schemas import CAMPOS_OBLIGATORIOS_EVENTO, crear_estructura_vacia_historico
from src.validaciones import BLOQUES_VALIDOS
from config import settings

try:
    from integrations.bd_backend import bd_disponible
    from src.lectura_bd import evento_existe
    _BD_IMPORTABLE = True
except ImportError:
    _BD_IMPORTABLE = False


# ---------------------------------------------------------------------
# 2. ESTILO CSS
# ---------------------------------------------------------------------
st.markdown("""
<style>
    /* --- FUENTES Y TAMAÑOS GLOBALES --- */
    html, body, .stApp {
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        font-size: 16px;
    }
    .stApp {
        font-size: 16px;
    }

    /* --- CABECERA --- */
    .main-title {
        font-size: 28px;
        font-weight: 700;
        color: #1a1a1a;
        margin-bottom: 4px;
    }
    .sub-title {
        font-size: 18px;
        color: #555555;
        margin-bottom: 20px;
    }

    /* --- CAMPOS --- */
    .field-label {
        font-size: 15px;
        font-weight: 600;
        color: #2c2c2c;
        margin-bottom: 4px;
        margin-top: 4px;
    }
    .field-value {
        font-size: 16px;
        color: #1a1a1a;
        background-color: #f5f5f5;
        padding: 8px 12px;
        border-radius: 4px;
        border-left: 4px solid #4a90d9;
        margin-bottom: 8px;
        font-family: 'Courier New', monospace;
        font-size: 15px;
    }
    .field-empty {
        font-size: 15px;
        color: #aaaaaa;
        background-color: #f9f9f9;
        padding: 8px 12px;
        border-radius: 4px;
        border-left: 4px solid #cccccc;
        margin-bottom: 8px;
        font-style: italic;
    }

    /* --- TARJETAS DE BLOQUES --- */
    .block-card {
        background-color: #fafafa;
        border-radius: 8px;
        padding: 18px 20px;
        margin-bottom: 14px;
        border: 1px solid #e8e8e8;
    }
    .block-card p, .block-card div {
        font-size: 16px;
    }

    /* --- NOTA BENE (PANEL DESTACADO) --- */
    .nota-bene-panel {
        background-color: #ebf5ff;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 24px;
        border: 2px solid #4a90d9;
        box-shadow: 0 2px 8px rgba(74, 144, 217, 0.15);
    }
    .nota-bene-panel .nb-header {
        font-size: 22px;
        font-weight: 700;
        color: #1a3a5c;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .nota-bene-panel .nb-header small {
        font-size: 15px;
        font-weight: 400;
        color: #4a6a8a;
    }
    .nota-bene-panel .nb-section-title {
        font-size: 17px;
        font-weight: 600;
        color: #1a3a5c;
        margin-top: 16px;
        margin-bottom: 10px;
        padding-bottom: 4px;
        border-bottom: 2px solid #c5d9f0;
    }
    .nota-bene-panel .nb-field-label {
        font-size: 14px;
        font-weight: 600;
        color: #2c4c6c;
    }
    .nota-bene-panel .nb-field-value {
        font-size: 16px;
        color: #1a1a1a;
        background-color: #ffffff;
        padding: 6px 12px;
        border-radius: 4px;
        border-left: 3px solid #4a90d9;
        margin-bottom: 6px;
    }
    .nota-bene-panel .nb-field-empty {
        font-size: 15px;
        color: #8a9aaa;
        background-color: #f0f5fa;
        padding: 6px 12px;
        border-radius: 4px;
        border-left: 3px solid #b0c4d8;
        margin-bottom: 6px;
        font-style: italic;
    }
    .nota-bene-panel .nb-card {
        background-color: #ffffff;
        border-radius: 6px;
        padding: 12px 16px;
        margin-bottom: 10px;
        border: 1px solid #d5e5f5;
    }
    .nota-bene-panel .nb-card p, .nota-bene-panel .nb-card div {
        font-size: 15px;
    }
    .nota-bene-panel .nb-grid-4 {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr 1fr;
        gap: 12px;
    }
    @media (max-width: 800px) {
        .nota-bene-panel .nb-grid-4 {
            grid-template-columns: 1fr 1fr;
        }
    }
    .nota-bene-panel .nb-grid-2 {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
    }
    @media (max-width: 600px) {
        .nota-bene-panel .nb-grid-2 {
            grid-template-columns: 1fr;
        }
    }

    /* --- BADGES --- */
    .status-badge {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 14px;
        font-size: 14px;
        font-weight: 600;
    }
    .status-badge.success {
        background-color: #d4edda;
        color: #155724;
    }
    .status-badge.error {
        background-color: #f8d7da;
        color: #721c24;
    }
    .status-badge.warning {
        background-color: #fff3cd;
        color: #856404;
    }

    /* --- AVISO DEL AGENTE --- */
    .agent-notice {
        background-color: #fff8e1;
        border-radius: 6px;
        padding: 12px 18px;
        margin-bottom: 16px;
        border-left: 5px solid #f5a623;
        font-size: 16px;
        color: #5d4a0e;
    }

    /* --- PESTAÑAS --- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 16px;
        padding: 10px 20px;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background-color: #f0f2f6;
        font-weight: 600;
    }

    /* --- BOTONES Y CONTROLES --- */
    .stButton button {
        font-size: 16px;
        font-weight: 500;
    }
    .stSelectbox, .stTextInput, .stTextArea {
        font-size: 16px;
    }
    .stCaption {
        font-size: 14px;
    }
    .stMarkdown {
        font-size: 16px;
    }

    /* --- SIDEBAR --- */
    .sidebar-title {
        font-size: 18px;
        font-weight: 600;
        margin-bottom: 12px;
        color: #1a1a1a;
    }
    .history-item {
        font-size: 15px;
        color: #2c2c2c;
        padding: 4px 0;
        border-bottom: 1px solid #f1f3f5;
    }
    .history-item:last-child {
        border-bottom: none;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------
# 3. FUNCIONES AUXILIARES DE RENDERIZADO
# =====================================================================

def formatear_valor(valor):
    if valor is None or valor == "":
        return None
    return str(valor)


def mostrar_campo(nombre, valor):
    st.markdown(f'<div class="field-label">{nombre}</div>', unsafe_allow_html=True)
    valor_limpio = formatear_valor(valor)
    if valor_limpio:
        st.markdown(f'<div class="field-value">{valor_limpio}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="field-empty">(no detectado)</div>', unsafe_allow_html=True)


def mostrar_bloque(bloque, omitir=()):
    if not bloque:
        st.markdown('<div class="block-card"><i>No hay información en este bloque.</i></div>', unsafe_allow_html=True)
        return
    st.markdown('<div class="block-card">', unsafe_allow_html=True)
    for campo, valor in bloque.items():
        if campo in omitir:
            continue
        mostrar_campo(campo.replace("_", " ").title(), valor)
    st.markdown('</div>', unsafe_allow_html=True)


def mostrar_ponentes(lista_ponentes):
    if not lista_ponentes:
        st.markdown('<div class="block-card"><i>No hay ponentes detectados.</i></div>', unsafe_allow_html=True)
        return
    for idx, ponente in enumerate(lista_ponentes, 1):
        nombre = ponente.get("nombre_ponente") or f"Ponente {idx}"
        with st.expander(f"Ponente {idx}: {nombre}", expanded=(idx == 1)):
            mostrar_bloque(ponente)


def mostrar_cliente(cliente):
    if not cliente:
        st.markdown('<div class="block-card"><i>No hay información de cliente.</i></div>', unsafe_allow_html=True)
        return

    mostrar_bloque(cliente, omitir=("personas_contacto",))

    contactos = cliente.get("personas_contacto") or []
    st.markdown("**Personas de contacto**")
    if not contactos:
        st.caption("Ninguna detectada.")
    else:
        for contacto in contactos:
            nombre = contacto.get("nombre") or "(sin nombre)"
            with st.expander(f"Contacto: {nombre}"):
                mostrar_bloque(contacto)


def mostrar_nota_bene(nota_bene):
    if not nota_bene:
        st.markdown(
            '<div class="nota-bene-panel">'
            '<div class="nb-header">📌 Nota Bene</div>'
            '<p style="font-size:16px; color:#6a8aaa;">No hay Nota Bene generada para este evento.</p>'
            '</div>',
            unsafe_allow_html=True
        )
        return

    html = f"""
    <div class="nota-bene-panel">
        <div class="nb-header">
            📌 Nota Bene
            <small>— resumen ejecutivo del evento</small>
        </div>
    """

    # ---- 1. CABECERA ----
    cabecera = nota_bene.get("cabecera", {})
    if cabecera and any(cabecera.values()):
        html += """
        <div class="nb-section-title">📋 Resumen ejecutivo</div>
        <div class="nb-grid-2" style="margin-bottom:10px;">
        """
        campos_cabecera = [
            ("nombre_evento", "Evento"),
            ("estado_evento", "Estado"),
            ("fecha_celebracion", "Fechas"),
            ("cliente_principal", "Cliente"),
            ("persona_contacto", "Contacto"),
            ("presupuesto_total_estimado", "Presupuesto total"),
            ("ultima_actualizacion", "Última actualización"),
        ]
        for clave, etiqueta in campos_cabecera:
            valor = cabecera.get(clave)
            if valor and str(valor).strip():
                html += f"""
                <div>
                    <div class="nb-field-label">{etiqueta}</div>
                    <div class="nb-field-value">{str(valor).strip()}</div>
                </div>
                """
            else:
                html += f"""
                <div>
                    <div class="nb-field-label">{etiqueta}</div>
                    <div class="nb-field-empty">(no disponible)</div>
                </div>
                """
        html += "</div>"

    # ---- 2. PRESUPUESTO Y SERVICIOS ----
    ps = nota_bene.get("presupuesto_servicios", {})
    if ps and any(ps.values()):
        html += '<div class="nb-section-title">💶 Presupuesto y servicios</div>'
        html += '<div class="nb-grid-4">'
        nombres = {
            "ubicacion": "Ubicación",
            "catering": "Catering",
            "audiovisuales": "Audiovisuales",
            "otros": "Otros"
        }
        iconos = {
            "ubicacion": "🏢",
            "catering": "🍽️",
            "audiovisuales": "🎬",
            "otros": "📦"
        }
        for clave in ["ubicacion", "catering", "audiovisuales", "otros"]:
            servicio = ps.get(clave, {})
            html += f'<div class="nb-card">'
            html += f'<div style="font-weight:600; font-size:16px; margin-bottom:4px;">{iconos.get(clave, "")} {nombres.get(clave, clave)}</div>'
            desc = servicio.get("descripcion")
            precio = servicio.get("precio_estimado")
            estado = servicio.get("estado")
            nota = servicio.get("nota")
            if desc and str(desc).strip():
                html += f'<div style="font-size:15px; color:#1a1a1a;">{str(desc).strip()}</div>'
            if precio and str(precio).strip():
                html += f'<div style="font-size:15px; font-weight:500; color:#1a5a3a;">{str(precio).strip()}</div>'
            if estado and str(estado).strip():
                html += f'<div style="font-size:14px; color:#4a6a8a;">Estado: {str(estado).strip()}</div>'
            if nota and str(nota).strip():
                html += f'<div style="font-size:14px; color:#6a6a6a; font-style:italic;">{str(nota).strip()}</div>'
            if not any(servicio.values()):
                html += '<div style="font-size:15px; color:#8a9aaa; font-style:italic;">Sin información</div>'
            html += '</div>'
        html += '</div>'

    # ---- 3. INFORMACIÓN ADICIONAL ----
    ia = nota_bene.get("informacion_adicional", {})
    if ia and any(ia.values()):
        html += '<div class="nb-section-title">🗂️ Información adicional</div>'

        # Textos planos
        for clave, etiqueta in [
            ("notas_generales", "Notas generales"),
            ("requerimientos_especiales", "Requerimientos especiales"),
            ("riesgos_detectados", "Riesgos detectados")
        ]:
            valor = ia.get(clave)
            if valor and str(valor).strip():
                html += f"""
                <div style="margin-bottom:6px;">
                    <div class="nb-field-label">{etiqueta}</div>
                    <div class="nb-field-value">{str(valor).strip()}</div>
                </div>
                """

        # Listas
        acciones = ia.get("acciones_pendientes") or []
        dependencias = ia.get("dependencias") or []
        if acciones or dependencias:
            html += '<div class="nb-grid-2" style="margin-top:8px;">'
            if acciones:
                html += '<div class="nb-card">'
                html += '<div style="font-weight:600; font-size:15px;">Acciones pendientes</div>'
                for a in acciones:
                    html += f'<div style="font-size:15px; padding:2px 0;">• {a}</div>'
                html += '</div>'
            if dependencias:
                html += '<div class="nb-card">'
                html += '<div style="font-weight:600; font-size:15px;">Dependencias</div>'
                for d in dependencias:
                    html += f'<div style="font-size:15px; padding:2px 0;">• {d}</div>'
                html += '</div>'
            html += '</div>'

        # Histórico
        historico = ia.get("historico_actualizaciones") or []
        if historico:
            html += '<div style="margin-top:10px;">'
            html += '<div style="font-weight:600; font-size:15px; margin-bottom:4px;">Histórico de actualizaciones</div>'
            for entrada in historico:
                fecha = entrada.get("fecha", "")
                cambios = entrada.get("cambios_detectados", "")
                version = entrada.get("version", "")
                html += f'<div style="font-size:15px; color:#4a6a8a; padding:2px 0;">v{version} — {fecha} — {cambios}</div>'
            html += '</div>'

    html += "</div>"

    # Streamlit/CommonMark trata cualquier linea que empiece con 4+ espacios
    # como un bloque de codigo indentado (no como HTML), y el f-string de
    # arriba conserva la indentacion del propio codigo Python. Sin este
    # "lstrip" por linea, el panel entero se muestra como texto literal en
    # lugar de renderizarse.
    html = "\n".join(linea.lstrip() for linea in html.split("\n"))
    st.markdown(html, unsafe_allow_html=True)


def leer_archivo_subido(archivo_subido):
    if archivo_subido is None:
        return ""
    try:
        nombre = archivo_subido.name
        extension = nombre.split('.')[-1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}") as tmp:
            tmp.write(archivo_subido.getvalue())
            tmp_path = tmp.name
        texto = leer_archivo(tmp_path)
        os.unlink(tmp_path)
        return texto
    except Exception as e:
        st.error(f"Error al leer el archivo: {str(e)}")
        return ""


def calcular_porcentaje_completado(resultado):
    pendientes = resultado.get("bloqueos_detectados", [])
    pendientes_obligatorios = [c for c in pendientes if c in CAMPOS_OBLIGATORIOS_EVENTO]
    if not CAMPOS_OBLIGATORIOS_EVENTO:
        return 0
    detectados = len(CAMPOS_OBLIGATORIOS_EVENTO) - len(pendientes_obligatorios)
    return round(detectados / len(CAMPOS_OBLIGATORIOS_EVENTO) * 100)


# ---------------------------------------------------------------------
# 4. INICIALIZACIÓN DE SESIÓN
# ---------------------------------------------------------------------

if "historial" not in st.session_state:
    st.session_state.historial = []

if "resultado_actual" not in st.session_state:
    st.session_state.resultado_actual = None

if "groq_api_key_desde_env" not in st.session_state:
    st.session_state.groq_api_key_desde_env = settings.GROQ_API_KEY

if "texto_briefing" not in st.session_state:
    st.session_state.texto_briefing = ""

if "nombre_archivo_actual" not in st.session_state:
    st.session_state.nombre_archivo_actual = ""

if "ultimo_texto_procesado" not in st.session_state:
    st.session_state.ultimo_texto_procesado = None

if "historicos_por_evento" not in st.session_state:
    st.session_state.historicos_por_evento = {}


# ---------------------------------------------------------------------
# 5. FUNCIÓN PARA PROCESAR EL TEXTO
# ---------------------------------------------------------------------

def procesar_texto(texto, id_evento, bloques_a_actualizar, usar_historico, modo_actualizacion, nombre_fuente):
    if not texto or not texto.strip():
        st.warning("No hay texto para procesar.")
        return
    if not id_evento or not id_evento.strip():
        st.warning("id_evento es obligatorio (ver barra lateral).")
        return

    contexto = {}
    if usar_historico:
        historico = st.session_state.historicos_por_evento.get(id_evento)
        if historico and historico.get("versiones"):
            contexto["historial_anterior"] = historico
            contexto["modo_actualizacion"] = modo_actualizacion

    payload = {
        "id_evento": id_evento,
        "id_registro": None,
        "tipo_peticion": "extraer_briefing",
        "origen": "streamlit",
        "usuario_solicitante": "pruebas",
        "rol_usuario": "organizador",
        "datos": {
            "texto_briefing": texto,
        },
        "contexto": contexto,
        "modo": "propuesta"
    }
    if bloques_a_actualizar:
        payload["datos"]["bloques_a_actualizar"] = bloques_a_actualizar

    with st.spinner("Extrayendo información con Groq..."):
        resultado = ejecutar_agente(payload)

    if resultado.get("ok", False):
        st.session_state.resultado_actual = resultado
        st.session_state.ultimo_texto_procesado = texto

        historico = st.session_state.historicos_por_evento.setdefault(
            id_evento, crear_estructura_vacia_historico()
        )
        historico["evento_id"] = id_evento
        historico["versiones"].append({
            "fecha": datetime.now().isoformat(timespec="seconds"),
            "archivo": nombre_fuente or "texto manual",
            "resumen": resultado.get("resumen", ""),
            "datos": resultado.get("datos_detectados", {})
        })
        historico["ultima_actualizacion"] = datetime.now().isoformat(timespec="seconds")

        porcentaje = calcular_porcentaje_completado(resultado)
        st.session_state.historial.append({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "porcentaje": porcentaje,
            "id_evento": id_evento
        })
        if len(st.session_state.historial) > 5:
            st.session_state.historial = st.session_state.historial[-5:]

        st.success("Extracción completada.")
    else:
        st.session_state.resultado_actual = None
        errores = resultado.get("errores", ["Error desconocido"])
        st.error(f"Error en la extracción: {'; '.join(errores)}")


# ---------------------------------------------------------------------
# 6. INTERFAZ PRINCIPAL
# ---------------------------------------------------------------------

st.markdown('<div class="main-title">Agente Operis — Extracción de briefings</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Sube un documento o pega el texto de un briefing. Motor único: llm (Groq).</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------
# 6.1 Barra lateral
# ---------------------------------------------------------------------

with st.sidebar:
    st.markdown('<div class="sidebar-title">Configuración</div>', unsafe_allow_html=True)

    id_evento = st.text_input(
        "id_evento",
        value="evt_demo_001",
        help="Obligatorio: el agente solo actualiza eventos ya existentes "
             "(no crea eventos nuevos). En producción lo asigna el backend "
             "al crear el evento.",
        key="id_evento_input"
    )

    bd_conectada = _BD_IMPORTABLE and bd_disponible()
    if bd_conectada:
        if evento_existe(id_evento):
            st.markdown('<span class="status-badge success">BD conectada — evento encontrado</span>', unsafe_allow_html=True)
            st.caption("Se usará el estado actual de la BD como histórico automáticamente.")
        else:
            st.markdown('<span class="status-badge error">BD conectada — id_evento no existe</span>', unsafe_allow_html=True)
            st.caption("El agente rechazará la petición (solo actualiza eventos ya creados).")
    elif _BD_IMPORTABLE:
        st.caption("BD real no configurada (falta DATABASE_URL) — funciona igual.")
    else:
        st.caption("Paquete psycopg no instalado — sin conexión a BD real.")

    api_key_manual = st.text_input(
        "GROQ_API_KEY",
        type="password",
        placeholder="Pégala aquí, o déjala vacía para usar la del .env",
        help="Solo para esta sesión de Streamlit.",
        key="api_key_manual_input"
    )
    settings.GROQ_API_KEY = api_key_manual.strip() or st.session_state.groq_api_key_desde_env

    if settings.GROQ_API_KEY:
        st.markdown('<span class="status-badge success">API key cargada</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-badge error">API key no disponible</span>', unsafe_allow_html=True)
        st.warning("El agente requiere una GROQ_API_KEY.")

    st.markdown("---")
    st.markdown("### Bloques a actualizar")

    bloques_seleccionados = st.multiselect(
        "Selecciona los bloques a actualizar",
        options=BLOQUES_VALIDOS,
        default=[],
        help="Déjalo vacío para actualizar TODOS los bloques. Si seleccionas "
             "alguno, el LLM debe dejar el resto COPIADOS tal cual del histórico."
    )

    st.markdown("---")
    st.markdown("### Histórico local")

    historico_actual = st.session_state.historicos_por_evento.get(id_evento)
    num_versiones = len(historico_actual["versiones"]) if historico_actual else 0

    usar_historico = st.checkbox(
        f"Usar histórico de '{id_evento}' ({num_versiones} versiones)",
        value=False,
        disabled=(num_versiones == 0)
    )

    modo_actualizacion = st.radio(
        "Modo de actualización",
        options=["fusionar", "sobrescribir"],
        horizontal=True,
        disabled=not usar_historico
    )

    if num_versiones and st.button("Borrar histórico de este evento", use_container_width=True):
        del st.session_state.historicos_por_evento[id_evento]
        st.rerun()

    st.markdown("---")
    st.markdown("### Últimas extracciones")

    if st.session_state.historial:
        for i, entry in enumerate(st.session_state.historial[-5:]):
            ts = entry.get("timestamp", "sin fecha")
            pct = entry.get("porcentaje", 0)
            evt = entry.get("id_evento", "?")
            st.caption(f"{i+1}. {ts} — {pct}% ({evt})")
    else:
        st.caption("Aún no hay extracciones guardadas.")

    if st.button("Limpiar todo (sesión + histórico)", use_container_width=True):
        st.session_state.historial = []
        st.session_state.resultado_actual = None
        st.session_state.texto_briefing = ""
        st.session_state.nombre_archivo_actual = ""
        st.session_state.historicos_por_evento = {}
        st.rerun()


# ---------------------------------------------------------------------
# 6.2 Área principal
# ---------------------------------------------------------------------

col_izq, col_der = st.columns([2, 1])

with col_izq:
    fuente = st.radio(
        "Fuente del texto",
        options=["Subir archivo", "Pegar texto"],
        horizontal=True,
        key="fuente_texto"
    )

    texto_para_procesar = ""
    nombre_para_mostrar = ""

    if fuente == "Subir archivo":
        archivo = st.file_uploader(
            "Subir documento",
            type=["txt", "pdf", "docx"],
            help="Formatos: .txt, .pdf, .docx",
            key="file_uploader_principal"
        )
        archivo_no_legible = False
        if archivo is not None:
            texto_leido = leer_archivo_subido(archivo)
            if texto_leido:
                texto_para_procesar = texto_leido
                nombre_para_mostrar = archivo.name
                st.info(f"Archivo cargado: {archivo.name} ({len(texto_leido)} caracteres)")
            else:
                st.warning("El archivo no se pudo leer o está vacío.")
                archivo_no_legible = True
    else:
        texto_manual = st.text_area(
            "Pega el texto del briefing aquí",
            height=200,
            placeholder="Pega aquí el contenido del briefing (email, resumen, etc.)...",
            key="text_area_manual"
        )
        texto_para_procesar = texto_manual.strip()
        nombre_para_mostrar = "texto manual"
        archivo_no_legible = False

    if (texto_para_procesar and texto_para_procesar != st.session_state.ultimo_texto_procesado) \
            or archivo_no_legible:
        st.session_state.resultado_actual = None

    if texto_para_procesar:
        st.session_state.texto_briefing = texto_para_procesar
        st.session_state.nombre_archivo_actual = nombre_para_mostrar

    if usar_historico:
        st.caption(f"Modo actualización de '{id_evento}' ({modo_actualizacion})")
    if bloques_seleccionados:
        st.caption(f"Bloques a actualizar: {', '.join(bloques_seleccionados)} (el resto se protege)")

    if st.button("Procesar documento", type="primary", use_container_width=True):
        if texto_para_procesar:
            procesar_texto(
                texto_para_procesar,
                id_evento,
                bloques_seleccionados,
                usar_historico,
                modo_actualizacion,
                nombre_para_mostrar
            )
        else:
            st.warning("No hay texto para procesar.")


# ---------------------------------------------------------------------
# 6.3 Mostrar resultados
# ---------------------------------------------------------------------

if st.session_state.resultado_actual:
    resultado = st.session_state.resultado_actual
    datos = resultado.get("datos_detectados", {})

    st.markdown("---")
    st.markdown("### Resultados de la extracción")

    pendientes = resultado.get("bloqueos_detectados", [])
    porcentaje = calcular_porcentaje_completado(resultado)

    col_v1, col_v2 = st.columns([3, 1])
    with col_v1:
        st.progress(porcentaje / 100, text=f"Completado (bloque Evento): {porcentaje}%")
        if pendientes:
            st.warning(f"Campos pendientes: {', '.join(pendientes)}")
        else:
            st.success("Todos los campos obligatorios del evento han sido detectados.")

    with col_v2:
        json_str = json.dumps(resultado, ensure_ascii=False, indent=2)
        st.download_button(
            label="Descargar JSON",
            data=json_str,
            file_name=f"briefing_extraido_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )

    if resultado.get("resumen"):
        st.markdown(f'<div class="agent-notice">{resultado["resumen"]}</div>', unsafe_allow_html=True)

    # ---- NOTA BENE: PANEL DESTACADO ----
    st.markdown("### Nota Bene — resumen ejecutivo")
    mostrar_nota_bene(datos.get("nota_bene", {}))

    # ---- RESTO DE BLOQUES: PESTAÑAS ----
    tab1, tab2, tab3, tab4 = st.tabs([
        "Evento",
        "Cliente",
        "Ponentes",
        "JSON completo"
    ])

    with tab1:
        mostrar_bloque(datos.get("evento", {}))

    with tab2:
        mostrar_cliente(datos.get("cliente", {}))

    with tab3:
        mostrar_ponentes(datos.get("ponentes", []))

    with tab4:
        st.json(resultado)

else:
    st.info("Sube un documento o pega un briefing, rellena el id_evento y pulsa 'Procesar documento'.")


# ---------------------------------------------------------------------
# 7. PIE
# ---------------------------------------------------------------------
st.markdown("---")
st.caption("Agente Operis — Extracción de briefings (motor único: llm/Groq) | v4")