import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
from streamlit_option_menu import option_menu
import io
import urllib.parse
import json
import qrcode
import cv2 
import numpy as np
import time
import plotly.express as px
import plotly.graph_objects as go 

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Orión | Mantenimiento", layout="wide", initial_sidebar_state="collapsed")

# ==============================================================================
# 🎨 TEMA: "ORIÓN HIGH CONTRAST"
# ==============================================================================

PRO_ORANGE = "#F59E0B" 
PRO_GREEN = "#10B981"  
BG_DARK_CLEAN = "#111827" 
BG_CARD = "rgba(31, 41, 55, 0.95)" 
TEXT_WHITE = "#FFFFFF"

st.markdown(f"""
    <style>
    /* 1. FONDO GENERAL */
    .stApp {{
        background: radial-gradient(circle at 50% 0%, #374151 0%, {BG_DARK_CLEAN} 80%);
        background-attachment: fixed;
        color: {TEXT_WHITE};
    }}

    /* 2. BARRA LATERAL */
    [data-testid="stSidebar"] {{
        background-color: {BG_DARK_CLEAN};
        border-right: 1px solid #374151;
    }}
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {{
        color: #D1D5DB !important;
    }}

    /* 3. TÍTULOS */
    h1, h2, h3 {{
        background: linear-gradient(90deg, {PRO_ORANGE}, {PRO_GREEN});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}

    /* 4. TARJETAS */
    .card-style {{
        background: {BG_CARD};
        backdrop-filter: blur(10px);
        border-radius: 12px;
        padding: 30px;
        border: 1px solid rgba(245, 158, 11, 0.2); 
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        margin-bottom: 20px;
    }}
    .login-container {{
        border-radius: 12px;
        padding: 30px;
        margin-top: 20px;
    }}

    /* 5. TÍTULOS DE GRÁFICAS */
    .chart-header {{
        font-size: 1.1rem;
        font-weight: 700;
        color: {PRO_ORANGE};
        margin-bottom: 15px;
        border-bottom: 1px solid #374151;
        padding-bottom: 8px;
        display: block;
    }}

    /* 6. MENÚS DESPLEGABLES */
    .stSelectbox > div > div {{
        background-color: #1F2937 !important; 
        color: white !important;
        border: 1px solid #4B5563 !important;
    }}
    div[data-baseweb="popover"], div[data-baseweb="menu"] {{
        background-color: #111827 !important;
        border: 1px solid {PRO_ORANGE};
    }}
    div[data-baseweb="menu"] li {{
        color: white !important;
    }}
    div[data-baseweb="menu"] li:hover {{
        background-color: {PRO_ORANGE} !important;
        color: white !important;
    }}
    
    /* 7. INPUTS TEXTO Y ETIQUETAS */
    .stTextInput label {{
        color: #FFFFFF !important;
        font-size: 16px !important;
        font-weight: 600 !important;
    }}
    .stTextInput input, .stTextArea textarea {{
        background-color: #0F1115 !important; 
        color: white !important;
        border: 1px solid #4B5563 !important;
        border-radius: 6px;
    }}
    
    /* 8. BOTONES */
    div.stButton > button:first-child {{
        background: linear-gradient(90deg, {PRO_ORANGE} 0%, {PRO_GREEN} 100%) !important;
        color: white !important;
        border: none;
        font-weight: bold;
        border-radius: 6px;
        padding: 0.6rem 1.2rem;
        transition: transform 0.2s;
    }}
    div.stButton > button:first-child:hover {{
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
    }}

    /* 9. MÉTRICAS */
    [data-testid="stMetric"] {{
        background: #1F2937;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid {PRO_GREEN};
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }}
    [data-testid="stMetricLabel"] {{ color: #9CA3AF !important; }}
    [data-testid="stMetricValue"] {{ color: white !important; }}

    /* 10. PESTAÑAS (TABS) */
    .stTabs [data-baseweb="tab"] {{ color: #9CA3AF; font-weight: 600; }}
    .stTabs [aria-selected="true"] {{ color: {PRO_ORANGE} !important; background-color: transparent !important; }}
    
    /* 11. ZONA PELIGRO */
    .danger-zone {{
        background: rgba(220, 38, 38, 0.1);
        border: 1px solid #EF4444;
        color: #EF4444;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
    }}

    /* 12. BOTÓN DE ELIMINACIÓN CON ALTO CONTRASTE */
    div.stButton > button[kind="secondary"] {{
        background: linear-gradient(135deg, #DC2626 0%, #991B1B 100%) !important;
        color: #FFFFFF !important;
        border: 2px solid #FCA5A5 !important;
        font-weight: 700 !important;
        border-radius: 8px !important;
        padding: 0.75rem 1.5rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 12px rgba(220, 38, 38, 0.4) !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
    }}

    div.stButton > button[kind="secondary"]:hover {{
        background: linear-gradient(135deg, #991B1B 0%, #7F1D1D 100%) !important;
        border-color: #FEE2E2 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(220, 38, 38, 0.6) !important;
    }}

    div.stButton > button[kind="secondary"]:active {{
        transform: translateY(0px) !important;
        box-shadow: 0 2px 8px rgba(220, 38, 38, 0.5) !important;
    }}
    
    /* --- HACK AVANZADO: OCULTAR CONTENEDORES VACÍOS --- */
    div[data-testid="stVerticalBlock"] > div:empty,
    div[data-testid="stVerticalBlock"] > div > div:empty {{
        height: 0 !important;
        min-height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        border: none !important;
        box-shadow: none !important;
        background: transparent !important;
        overflow: hidden !important;
    }}
    
    div.stVerticalBlock > div:first-child > div:nth-child(2) > div:first-child {{
        padding-top: 0 !important;
    }}
    </style>
""", unsafe_allow_html=True)

# --- 2. CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key) 
    except KeyError as e:
        st.error(f"❌ ERROR CRÍTICO: La clave {e} no se encuentra en la configuración de Streamlit Secrets (secrets.toml).")
        return None
    except Exception as e:
        st.error(f"❌ Error desconocido al conectar a Supabase. Verifique URL y clave. Detalles: {e}")
        return None

supabase = init_supabase()
if not supabase:
    st.stop()

# --- 3. FUNCIONES AUXILIARES MEJORADAS ---

@st.cache_data(ttl=300)  # Cache de 5 minutos
def run_query(table_name, filters=None, order_by="id"):
    """Función optimizada para consultas con cache y filtros"""
    try:
        query = supabase.table(table_name).select("*")
        
        if filters:
            for key, value in filters.items():
                if value is not None:
                    query = query.eq(key, value)
        
        query = query.order(order_by)
        response = query.execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Error en consulta {table_name}: {e}")
        return pd.DataFrame()

def mostrar_estado_carga(mensaje):
    """Muestra un estado de carga elegante"""
    return st.status(f"⏳ {mensaje}", expanded=False)

def subir_imagen(archivo, carpeta="evidencias"):
    if archivo:
        try:
            if isinstance(archivo, bytes):
                file_bytes = archivo
                file_name = f"qr_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                mime_type = "image/png"
            else:
                file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{archivo.name}"
                file_bytes = archivo.getvalue()
                mime_type = archivo.type

            supabase.storage.from_(carpeta).upload(path=file_name, file=file_bytes, file_options={"content-type": mime_type})
            return supabase.storage.from_(carpeta).get_public_url(file_name)
        except Exception as e:
            st.error(f"Error al subir imagen: {e}")
            return None
    return None

def generar_qr_activo(id_activo, nombre_activo):
    base_url = "https://mantenimiento-app-esw6r3vpeqxngz3ifyp5ey.streamlit.app" 
    link = f"{base_url}/?id_activo_qr={id_activo}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    return subir_imagen(img_byte_arr, "evidencias")

def leer_qr_imagen(uploaded_image):
    try:
        file_bytes = np.asarray(bytearray(uploaded_image.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        detector = cv2.QRCodeDetector()
        data, bbox, _ = detector.detectAndDecode(img)
        if data:
            parsed_url = urllib.parse.urlparse(data)
            params = urllib.parse.parse_qs(parsed_url.query)
            if 'id_activo_qr' in params:
                return params['id_activo_qr'][0]
        return None
    except:
        return None
def convertir_tipos_python(data_dict):
    """
    Convierte los valores de un diccionario a tipos nativos de Python
    para evitar errores de serialización JSON
    """
    converted = {}
    for key, value in data_dict.items():
        if value is None:
            converted[key] = None
        elif isinstance(value, (pd.Timestamp, datetime)):
            converted[key] = value.isoformat()
        elif isinstance(value, (np.integer, np.int64)):
            converted[key] = int(value)
        elif isinstance(value, (np.floating, np.float64)):
            converted[key] = float(value)
        elif isinstance(value, (np.bool_, bool)):
            converted[key] = bool(value)
        elif isinstance(value, (np.ndarray, pd.Series)):
            converted[key] = value.tolist()
        else:
            converted[key] = value
    return converted

# --- SISTEMA DE NOTIFICACIONES MEJORADO ---
def mostrar_notificaciones():
    """Sistema de notificaciones más robusto"""
    if 'notifications' not in st.session_state:
        st.session_state.notifications = []
    
    for notif in st.session_state.notifications[:]:
        tipo = notif.get('type')
        mensaje = notif.get('message')
        
        if tipo == 'success':
            st.success(f"✅ {mensaje}")
        elif tipo == 'error':
            st.error(f"❌ {mensaje}")
        elif tipo == 'warning':
            st.warning(f"⚠️ {mensaje}")
        elif tipo == 'info':
            st.info(f"ℹ️ {mensaje}")
        
        st.session_state.notifications.remove(notif)

def agregar_notificacion(tipo, mensaje):
    """Agrega una notificación al sistema"""
    if 'notifications' not in st.session_state:
        st.session_state.notifications = []
    
    st.session_state.notifications.append({
        'type': tipo,
        'message': mensaje
    })

# --- COMPONENTE REUTILIZABLE PARA TARJETAS ---
def tarjeta_estilo(titulo, contenido, color_borde=PRO_ORANGE):
    """Componente reutilizable para tarjetas con estilo"""
    return st.markdown(f"""
        <div class='card-style' style='border-left: 4px solid {color_border}'>
            <span class='chart-header'>{titulo}</span>
            {contenido}
        </div>
    """, unsafe_allow_html=True)

# --- VALIDACIONES MEJORADAS ---
def validar_usuario_unico(documento, usuario_id=None):
    """Valida que el documento sea único en el sistema"""
    try:
        query = supabase.table("usuarios").select("id").eq("documento", documento)
        if usuario_id:
            query = query.neq("id", usuario_id)
        
        response = query.execute()
        return len(response.data) == 0
    except:
        return False

def check_open_orders(user_id):
    """Verifica si el usuario tiene órdenes de trabajo activas"""
    try:
        user_id_str = str(user_id)
        response = supabase.table("ordenes") \
            .select("id, descripcion, fecha_creacion, estado") \
            .eq("tecnico_asignado", user_id_str) \
            .neq("estado", "Concluida") \
            .execute()
        
        if response.data and len(response.data) > 0:
            return True
        return False
    except Exception as e:
        return True

def get_open_orders_details(user_id):
    """Obtiene los detalles de las órdenes pendientes de un usuario"""
    try:
        user_id_str = str(user_id)
        response = supabase.table("ordenes") \
            .select("id, descripcion, criticidad, tipo_mantenimiento, fecha_creacion, estado") \
            .eq("tecnico_asignado", user_id_str) \
            .neq("estado", "Concluida") \
            .execute()
        return response.data if response.data else []
    except:
        return []

# --- MÉTRICAS INTELIGENTES ---
def mostrar_metricas_inteligentes(df_ordenes):
    """Muestra métricas con análisis contextual"""
    if df_ordenes.empty:
        st.info("No hay datos para mostrar métricas")
        return
    
    total = len(df_ordenes)
    pendientes = len(df_ordenes[df_ordenes['estado'] == 'Abierta'])
    concluidas = len(df_ordenes[df_ordenes['estado'] == 'Concluida'])
    
    # Calcular porcentajes
    porcentaje_concluidas = (concluidas / total * 100) if total > 0 else 0
    eficiencia = "🟢 Excelente" if porcentaje_concluidas > 80 else "🟡 Regular" if porcentaje_concluidas > 50 else "🔴 Crítico"
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Órdenes", total)
    
    with col2:
        st.metric("Pendientes", pendientes)
    
    with col3:
        st.metric("Finalizadas", concluidas, f"{porcentaje_concluidas:.1f}%")
    
    with col4:
        st.metric("Eficiencia", eficiencia)

# --- GRÁFICOS (PLOTLY) ---
def graficar_criticidad(df):
    if df.empty: return
    conteo = df['criticidad'].value_counts().reset_index()
    conteo.columns = ['Nivel', 'Cantidad']
    orden = ["Baja", "Media", "Alta", "Crítica"]
    conteo['Nivel'] = pd.Categorical(conteo['Nivel'], categories=orden, ordered=True)
    conteo = conteo.sort_values('Nivel')
    colores = {"Baja": "#10B981", "Media": "#F59E0B", "Alta": "#EA580C", "Crítica": "#EF4444"}
    fig = px.bar(conteo, x='Nivel', y='Cantidad', color='Nivel', 
                 color_discrete_map=colores, text='Cantidad')
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'), showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0), height=250,
        xaxis=dict(title=None),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)')
    )
    fig.update_traces(textfont_size=14, textposition='outside', marker_line_width=0)
    st.plotly_chart(fig, use_container_width=True)

def graficar_torta_tipo(df):
    if df.empty: return
    conteo = df['tipo_mantenimiento'].value_counts().reset_index()
    conteo.columns = ['Tipo', 'Cantidad']
    colores_torta = ["#3B82F6", "#8B5CF6", "#EC4899"] 
    fig = go.Figure(data=[go.Pie(
        labels=conteo['Tipo'], values=conteo['Cantidad'], hole=.5, 
        marker=dict(colors=colores_torta, line=dict(color='#111827', width=2)),
        textinfo='label+percent', textfont=dict(color='white')
    )])
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', font=dict(color='white'),
        height=250, showlegend=False, margin=dict(l=0, r=0, t=10, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)

def graficar_estado_barras(df):
    if df.empty: return
    conteo = df['estado'].value_counts().reset_index()
    conteo.columns = ['Estado', 'Cantidad']
    colores = {"Abierta": PRO_ORANGE, "Concluida": PRO_GREEN}
    fig = px.bar(conteo, x='Cantidad', y='Estado', orientation='h', 
                 color='Estado', color_discrete_map=colores, text='Cantidad')
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'), showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0), height=250,
        xaxis=dict(showgrid=False), yaxis=dict(title=None)
    )
    fig.update_traces(textfont_size=14, textposition='inside')
    st.plotly_chart(fig, use_container_width=True)

# --- FUNCIÓN AISLADA PARA EL SVG ---
def render_orion_svg(PRO_ORANGE):
    ORION_SVG = f"""
        <svg width="250" height="250" viewBox="0 0 400 400" fill="none" xmlns="http://www.w3.org/2000/svg">
            <style>
                .star {{ fill: white; filter: drop-shadow(0 0 2px white); }}
                .belt {{ stroke: {PRO_ORANGE}; filter: drop-shadow(0 0 5px {PRO_ORANGE}); stroke-width: 2; opacity: 0.8; }}
                .line {{ stroke: {PRO_ORANGE}; stroke-width: 1; opacity: 0.4; }}
            </style>
            <path class="line" d="M100 150 L200 50 L300 150 L250 250 L150 250 L100 150 Z"/>
            <line class="belt" x1="160" y1="180" x2="200" y2="200"/>
            <line class="belt" x1="200" y1="200" x2="240" y2="220"/>
            <circle class="star" cx="200" cy="50" r="5"/> 
            <circle class="star" cx="100" cy="150" r="4"/> 
            <circle class="star" cx="240" cy="220" r="6"/> 
            <circle class="star" cx="200" cy="200" r="6"/> 
            <circle class="star" cx="160" cy="180" r="6"/> 
            <circle class="star" cx="300" cy="150" r="5"/> 
            <circle class="star" cx="250" cy="250" r="7"/> 
        </svg>
    """
    st.markdown(f"""
        <div style="display: flex; justify-content: center; margin-bottom: -30px;">
            {ORION_SVG}
        </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# 🚀 INTERCEPTOR PÚBLICO (ACCESO QR)
# ==============================================================================
query_params = st.query_params
if "id_activo_qr" in query_params:
    id_qr = query_params["id_activo_qr"]
    try:
        datos_activo = supabase.table("activos").select("*").eq("id", id_qr).execute()
    except:
        st.error("Error de conexión.")
        st.stop()

    if datos_activo.data:
        activo = datos_activo.data[0]
        st.markdown(f"<h1 style='text-align: center;'>ORIÓN: {activo['nombre']}</h1>", unsafe_allow_html=True)
        st.markdown(f"""
            <div class="card-style">
                <span class="chart-header">Ficha Técnica</span>
                <p><strong>📍 Área:</strong> {activo.get('area', 'N/A')}</p>
                <p><strong>🏢 Ubicación:</strong> {activo['ubicacion']}</p>
                <p><strong>🔧 Categoría:</strong> {activo.get('categoria', 'N/A')}</p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("<h3 style='margin-top:20px;'>Historial</h3>", unsafe_allow_html=True)
        try:
            ots = supabase.table("ordenes").select("*").eq("activo_id", id_qr).order("id", desc=True).limit(5).execute()
            if ots.data:
                st.table(pd.DataFrame(ots.data)[['fecha_creacion', 'tipo_mantenimiento', 'estado']])
            else:
                st.info("Sin registros.")
        except: pass

        st.markdown("---")
        if st.button("🏠 Inicio"):
            st.query_params.clear()
            st.rerun()
    else:
        st.error("❌ Activo no encontrado.")
        if st.button("Volver"):
            st.query_params.clear()
            st.rerun()
    st.stop() 

# ==============================================================================
# 🚀 LOGIN
# ==============================================================================

if 'usuario' not in st.session_state: st.session_state['usuario'] = None
if 'rol' not in st.session_state: st.session_state['rol'] = None

def logout():
    st.session_state['usuario'] = None
    st.session_state['rol'] = None
    st.query_params.clear()
    st.rerun()

if st.session_state['usuario'] is None:
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        render_orion_svg(PRO_ORANGE)

        st.markdown(f"""
            <h1 style='text-align: center; font-size: 3.5rem; margin-bottom: -15px; text-shadow: 0 0 10px {PRO_ORANGE};'>ORIÓN</h1>
            <p style='text-align: center; color: #E5E7EB; font-size: 1.2rem; letter-spacing: 2px; margin-top: 5px; margin-bottom: 20px; font-weight: 300;'>
                PLATAFORMA INTEGRAL DE MANTENIMIENTO
            </p>
        """, unsafe_allow_html=True)

        st.markdown(f"""
            <div class='card-style' style='padding: 10px; margin-top: 0px; margin-bottom: 30px; text-align: center; font-size: 0.85em; color: {PRO_ORANGE}; border: none; box-shadow: none; background: #1F2937;'>
                <p style='margin: 0;'>Desarrollado por: <b>Jhonestebanpenagos@gmail.com</b></p>
            </div>
            <hr style="border: none; height: 1px; background: linear-gradient(90deg, transparent, {PRO_ORANGE}, transparent); margin-bottom: 30px;">
        """, unsafe_allow_html=True)

        st.markdown("<h3 style='text-align: center; margin-bottom: 20px;'>ACCESO DE USUARIOS</h3>", unsafe_allow_html=True)

        with st.form("login_form"):
            documento = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("ACCEDER AL SISTEMA", type="primary", use_container_width=True)
            if submitted:
                with st.spinner("Conectando y validando credenciales..."):
                    time.sleep(1) 

                try:
                    response = supabase.table("usuarios").select("*").eq("documento", documento).eq("password", password).execute()

                    if response.data:
                        user = response.data[0]
                        st.session_state['usuario'] = user['nombre']
                        st.session_state['rol'] = user['rol']
                        st.rerun()
                    else: 
                        st.error("Acceso denegado. Usuario o contraseña incorrectos.")
                except Exception as e: 
                    st.error(f"Error de conexión. Intente nuevamente. Detalles: {e}")

    st.stop()

# ==============================================================================
# 🚀 DASHBOARD PRIVADO
# ==============================================================================

rol = st.session_state['rol']
usuario = st.session_state['usuario']

with st.sidebar:
    st.markdown(f"""
        <div style="text-align: center; margin-bottom: 25px; margin-top: 10px;">
            <p style="margin:0; font-size: 1.2rem; color: white; font-weight: 600; letter-spacing: 0.5px;">👋 Hola, {usuario}!</p>
            <span style="color: {PRO_GREEN}; font-size: 0.85rem; font-weight: bold; letter-spacing: 1px;">{rol.upper()}</span>
        </div>
    """, unsafe_allow_html=True)

    if st.button("Cerrar Sesión", use_container_width=True): logout()
    st.write("") 

    opts = []
    icons_list = []
    
    if rol == "Admin":
        opts = ["Tablero de Mando", "Inventario Activos", "Crear Orden", "Gestionar Órdenes", "Cerrar Orden", "Usuarios"]
        icons_list = ["speedometer2", "box-seam", "plus-circle", "list-task", "check2-circle", "people"]
    elif rol == "Programador":
        opts = ["Tablero de Mando", "Crear Orden", "Gestionar Órdenes", "Usuarios"]
        icons_list = ["speedometer2", "plus-circle", "list-task", "people"]
    elif rol == "Tecnico":
        opts = ["Cerrar Orden"]
        icons_list = ["check2-circle"]

    choice = option_menu(
        menu_title="NAVEGACIÓN",
        options=opts,
        icons=icons_list,
        default_index=0,
        styles={
            "container": {"background-color": "transparent"},
            "icon": {"color": PRO_ORANGE},
            "nav-link": {"color": "#9CA3AF"},
            "nav-link-selected": {
                "background-color": "#1F2937",
                "color": "white",
                "border-left": f"4px solid {PRO_ORANGE}"
            }
        }
    )

# ==============================================================================
# 📊 PANTALLAS
# ==============================================================================

if choice == "Tablero de Mando":
    st.title("TABLERO DE MANDO")
    mostrar_notificaciones()
    
    df = run_query("ordenes")
    
    if not df.empty:
        # Métricas inteligentes
        mostrar_metricas_inteligentes(df)

        st.write("") 

        c_left, c_mid, c_right = st.columns(3)

        with c_left:
            st.markdown(f"<div class='card-style'><span class='chart-header'>Progreso de Órdenes</span>", unsafe_allow_html=True)
            graficar_estado_barras(df)
            st.markdown("</div>", unsafe_allow_html=True)

        with c_mid:
            st.markdown(f"<div class='card-style'><span class='chart-header'>Gravedad de las Fallas</span>", unsafe_allow_html=True)
            graficar_criticidad(df) 
            st.markdown("</div>", unsafe_allow_html=True)

        with c_right:
            st.markdown(f"<div class='card-style'><span class='chart-header'>Tipos de Mantenimiento</span>", unsafe_allow_html=True)
            graficar_torta_tipo(df) 
            st.markdown("</div>", unsafe_allow_html=True)

    else: 
        st.info("No hay datos para mostrar.")

elif choice == "Inventario Activos":
    st.title("INVENTARIO")
    mostrar_notificaciones()
    
    df_act = run_query("activos")

    tab1, tab2 = st.tabs(["NUEVO ACTIVO", "EDITAR / QR"])

    with tab1:
        st.markdown("<div class='card-style'>", unsafe_allow_html=True)
        with st.form("new_asset"):
            c1, c2 = st.columns(2)
            nom = c1.text_input("Nombre Activo")
            area = c2.selectbox("Área", ["Producción", "Logística", "Servicios Generales", "Calidad"])
            ubic = c1.text_input("Ubicación Exacta")
            cat = c2.selectbox("Categoría", ["Mecánico", "Eléctrico", "Hidráulico", "Infraestructura"])
            if st.form_submit_button("GUARDAR"):
                if nom and ubic:
                    res = supabase.table("activos").insert({"nombre":nom, "area":area, "ubicacion":ubic, "categoria":cat}).execute()
                    if res.data:
                        nid = res.data[0]['id']
                        url = generar_qr_activo(nid, nom)
                        supabase.table("activos").update({"qr_url":url}).eq("id", nid).execute()
                        agregar_notificacion('success', 'Activo creado exitosamente.')
                        st.rerun()
                else:
                    agregar_notificacion('error', 'Nombre y ubicación son obligatorios.')
        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        if not df_act.empty:
            sel = st.selectbox("Buscar Activo", df_act['nombre'].values)
            dat = df_act[df_act['nombre']==sel].iloc[0]
            st.markdown("<div class='card-style'>", unsafe_allow_html=True)
            c1, c2 = st.columns([1,3])
            if dat['qr_url']:
                c1.image(dat['qr_url'])
            c2.info(f"ID: {dat['id']} | {dat['area']}")

            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander("Eliminar Activo"):
                st.markdown(f"<div class='danger-zone'><p>Esto borrará el historial completo.</p></div>", unsafe_allow_html=True)
                if st.button("ELIMINAR DEFINITIVAMENTE"):
                    try:
                        supabase.table("ordenes").delete().eq("activo_id", dat['id']).execute()
                        supabase.table("activos").delete().eq("id", dat['id']).execute()
                        agregar_notificacion('delete', 'Activo eliminado permanentemente.')
                        st.rerun()
                    except Exception as e:
                        agregar_notificacion('error', f'Error al eliminar: {e}')
            st.markdown("</div>", unsafe_allow_html=True)
elif choice == "Crear Orden":
    st.title("GENERAR ORDEN")
    mostrar_notificaciones()
    
    df_act = run_query("activos")
    df_users = run_query("usuarios")
    
    if not df_act.empty:
        act_dict = dict(zip(df_act['nombre'], df_act['id']))
        
        st.markdown("<div class='card-style'>", unsafe_allow_html=True)
        
        # Selectbox para seleccionar el activo
        sel = st.selectbox("Equipo", list(act_dict.keys()))
        
        c1, c2 = st.columns(2)
        tipo = c1.selectbox("Tipo", ["Correctivo", "Preventivo"])
        crit = c2.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"])
        
        desc = st.text_area("Descripción")
        
        # Campo de asignación mejorado con selectbox
        if not df_users.empty:
            # Crear un diccionario con nombre + rol como clave y el ID como valor
            user_options = {
                f"{row['nombre']} - {row['rol']}": str(row['id']) 
                for _, row in df_users.iterrows()
            }
            
            # Añadir opción por defecto
            user_options_list = ["-- Seleccione un técnico --"] + list(user_options.keys())
            
            selected_tech = st.selectbox(
                "Asignar a (Obligatorio) *",
                user_options_list,
                help="Seleccione el técnico o usuario responsable de esta orden"
            )
            
            # Validar que se haya seleccionado un técnico
            if st.button("CREAR ORDEN", type="primary", use_container_width=True):
                if selected_tech == "-- Seleccione un técnico --":
                    agregar_notificacion('error', 'Debe seleccionar un técnico para asignar la orden.')
                elif not desc.strip():
                    agregar_notificacion('error', 'Debe ingresar una descripción para la orden.')
                else:
                    # Obtener el ID del técnico seleccionado
                    tecnico_id = user_options[selected_tech]
                    
                    # Insertar la orden en la base de datos
                    try:
                        supabase.table("ordenes").insert({
                            "activo_id": act_dict[sel], 
                            "descripcion": desc, 
                            "criticidad": crit, 
                            "tipo_mantenimiento": tipo, 
                            "estado": "Abierta", 
                            "tecnico_asignado": tecnico_id, 
                            "fecha_creacion": datetime.now().isoformat()
                        }).execute()
                        
                        agregar_notificacion('success', f'Orden creada y asignada a {selected_tech.split(" - ")[0]}.')
                        st.rerun()
                    except Exception as e:
                        agregar_notificacion('error', f'Error al crear orden: {e}')
        else:
            st.warning("⚠️ No hay usuarios registrados. Debe crear usuarios antes de generar órdenes.")
            
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.warning("⚠️ No hay activos registrados. Debe crear activos antes de generar órdenes.")

elif choice == "Gestionar Órdenes":
    st.title("GESTIONAR ÓRDENES DE TRABAJO")
    mostrar_notificaciones()
    
    # FORZAR ACTUALIZACIÓN DEL CACHE AL ENTRAR A ESTA SECCIÓN
    st.cache_data.clear()
    
    df_ordenes = run_query("ordenes")
    df_activos = run_query("activos")
    df_users = run_query("usuarios")
    
    if not df_ordenes.empty:
        
        # Filtros en la parte superior
        st.markdown("### 🔍 Filtros")
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            filter_estado = st.selectbox(
                "Estado:",
                ["Todas", "Abierta", "Concluida"],
                key="filter_estado"
            )
        
        with col_f2:
            filter_criticidad = st.selectbox(
                "Criticidad:",
                ["Todas", "Baja", "Media", "Alta", "Crítica"],
                key="filter_criticidad"
            )
        
        with col_f3:
            filter_tipo = st.selectbox(
                "Tipo:",
                ["Todos", "Correctivo", "Preventivo"],
                key="filter_tipo"
            )
        
        # Aplicar filtros
        df_filtered = df_ordenes.copy()
        
        if filter_estado != "Todas":
            df_filtered = df_filtered[df_filtered['estado'] == filter_estado]
        
        if filter_criticidad != "Todas":
            df_filtered = df_filtered[df_filtered['criticidad'] == filter_criticidad]
        
        if filter_tipo != "Todos":
            df_filtered = df_filtered[df_filtered['tipo_mantenimiento'] == filter_tipo]
        
        # Mostrar tabla con las órdenes filtradas
        st.markdown("---")
        st.markdown(f"### 📋 Órdenes Encontradas: **{len(df_filtered)}**")
        
        if not df_filtered.empty:
            # Crear DataFrame mejorado con información de activo y técnico
            df_display = df_filtered.copy()
            
            # Mapear nombres de activos
            if not df_activos.empty:
                activo_map = dict(zip(df_activos['id'], df_activos['nombre']))
                df_display['activo_nombre'] = df_display['activo_id'].map(activo_map)
            
            # Mapear nombres de técnicos - ACTUALIZADO PARA USAR DATOS EN TIEMPO REAL
            if not df_users.empty:
                user_map = dict(zip(df_users['id'].astype(str), df_users['nombre']))
                df_display['tecnico_nombre'] = df_display['tecnico_asignado'].astype(str).map(user_map).fillna('Sin asignar')
            
            # Mostrar tabla con clave única para forzar actualización
            st.dataframe(
                df_display[['id', 'activo_nombre', 'tipo_mantenimiento', 'criticidad', 
                           'estado', 'tecnico_nombre', 'fecha_creacion']].rename(columns={
                    'id': 'ID',
                    'activo_nombre': 'Activo',
                    'tipo_mantenimiento': 'Tipo',
                    'criticidad': 'Criticidad',
                    'estado': 'Estado',
                    'tecnico_nombre': 'Asignado a',
                    'fecha_creacion': 'Fecha Creación'
                }),
                hide_index=True,
                use_container_width=True,
                key=f"tabla_ordenes_{datetime.now().timestamp()}"  # Clave única para forzar actualización
            )
            
            # Selector de orden para editar
            st.markdown("---")
            st.markdown("### ✏️ Editar / Reasignar Orden")
            
            # Crear opciones para el selectbox
            orden_options = {
                f"OT-{row['id']} | {activo_map.get(row['activo_id'], 'N/A')} | {row['estado']}": row['id']
                for _, row in df_filtered.iterrows()
            }
            
            orden_options_list = ["-- Seleccione una orden --"] + list(orden_options.keys())
            
            selected_orden_option = st.selectbox(
                "Orden de Trabajo:",
                orden_options_list,
                key="orden_selector"
            )
            
            if selected_orden_option != "-- Seleccione una orden --":
                orden_id = orden_options[selected_orden_option]
                orden_actual = df_ordenes[df_ordenes['id'] == orden_id].iloc[0]
                
                st.markdown(f"""
                    <div class='card-style' style='border-left: 4px solid {PRO_ORANGE}; background: rgba(245, 158, 11, 0.05);'>
                        <p><strong>📌 Orden Seleccionada:</strong> OT-{orden_actual['id']}</p>
                        <p><strong>🔧 Activo:</strong> {activo_map.get(orden_actual['activo_id'], 'N/A')}</p>
                        <p><strong>📅 Creada:</strong> {orden_actual['fecha_creacion']}</p>
                    </div>
                """, unsafe_allow_html=True)
                
                # Formulario de edición
                with st.form(key=f"edit_orden_form_{orden_id}"):
                    st.markdown("#### Información de la Orden")
                    
                    col1, col2 = st.columns(2)
                    
                    # Campo Activo
                    activo_actual = activo_map.get(orden_actual['activo_id'], 'N/A')
                    activo_index = list(df_activos['nombre']).index(activo_actual) if activo_actual in df_activos['nombre'].values else 0
                    nuevo_activo = col1.selectbox(
                        "Activo",
                        df_activos['nombre'].values,
                        index=activo_index
                    )
                    
                    # Campo Tipo
                    tipo_options = ["Correctivo", "Preventivo"]
                    tipo_index = tipo_options.index(orden_actual['tipo_mantenimiento']) if orden_actual['tipo_mantenimiento'] in tipo_options else 0
                    nuevo_tipo = col2.selectbox(
                        "Tipo de Mantenimiento",
                        tipo_options,
                        index=tipo_index
                    )
                    
                    # Campo Criticidad
                    crit_options = ["Baja", "Media", "Alta", "Crítica"]
                    crit_index = crit_options.index(orden_actual['criticidad']) if orden_actual['criticidad'] in crit_options else 0
                    nueva_crit = col1.select_slider(
                        "Criticidad",
                        crit_options,
                        value=crit_options[crit_index]
                    )
                    
                    # Campo Estado
                    estado_options = ["Abierta", "Concluida"]
                    estado_index = estado_options.index(orden_actual['estado']) if orden_actual['estado'] in estado_options else 0
                    nuevo_estado = col2.selectbox(
                        "Estado",
                        estado_options,
                        index=estado_index
                    )
                    
                    # Campo Descripción
                    nueva_desc = st.text_area(
                        "Descripción",
                        value=orden_actual.get('descripcion', ''),
                        height=100
                    )
                    
                    # Campo Reasignar Técnico
                    st.markdown("#### 👤 Reasignación de Técnico")
                    
                    if not df_users.empty:
                        user_options = {
                            f"{row['nombre']} - {row['rol']}": str(row['id'])
                            for _, row in df_users.iterrows()
                        }
                        
                        # Encontrar el índice del técnico actual
                        tecnico_actual_id = str(orden_actual.get('tecnico_asignado', ''))
                        tecnico_actual_nombre = user_map.get(tecnico_actual_id, 'Sin asignar')
                        
                        # Buscar la opción que corresponde al técnico actual
                        current_tech_option = None
                        for option, uid in user_options.items():
                            if uid == tecnico_actual_id:
                                current_tech_option = option
                                break
                        
                        user_options_list = list(user_options.keys())
                        current_index = user_options_list.index(current_tech_option) if current_tech_option else 0
                        
                        nuevo_tecnico_option = st.selectbox(
                            "Asignar a:",
                            user_options_list,
                            index=current_index,
                            help=f"Actualmente asignado a: {tecnico_actual_nombre}"
                        )
                        
                        nuevo_tecnico_id = user_options[nuevo_tecnico_option]
                    else:
                        st.warning("No hay usuarios disponibles")
                        nuevo_tecnico_id = tecnico_actual_id
                    
                    # Comentarios adicionales
                    comentarios = st.text_area(
                        "Comentarios de cierre (Opcional)",
                        value=orden_actual.get('comentarios_cierre', ''),
                        height=80
                    )
                    
                    # Botones de acción
                    st.markdown("<br>", unsafe_allow_html=True)
                    col_btn1, col_btn2 = st.columns(2)
                    
                    with col_btn1:
                        actualizar_btn = st.form_submit_button(
                            "✅ ACTUALIZAR ORDEN",
                            type="primary",
                            use_container_width=True
                        )
                    
                    with col_btn2:
                        cancelar_btn = st.form_submit_button(
                            "🗑️ ELIMINAR ORDEN",
                            type="secondary",
                            use_container_width=True
                        )
                    
                    # PROCESAR ACTUALIZACIÓN
                    if actualizar_btn:
                        try:
                            # Obtener el ID del activo seleccionado
                            nuevo_activo_id = int(df_activos[df_activos['nombre'] == nuevo_activo].iloc[0]['id'])
                            
                            # Preparar los datos actualizados con conversión explícita
                            update_data = {
                                "activo_id": nuevo_activo_id,
                                "tipo_mantenimiento": str(nuevo_tipo),
                                "criticidad": str(nueva_crit),
                                "estado": str(nuevo_estado),
                                "descripcion": str(nueva_desc),
                                "tecnico_asignado": str(nuevo_tecnico_id),
                                "comentarios_cierre": str(comentarios) if comentarios else None
                            }
                            
                            # Validar datos requeridos
                            if not update_data["descripcion"].strip():
                                agregar_notificacion('error', 'La descripción no puede estar vacía.')
                            else:
                                # Ejecutar actualización
                                supabase.table("ordenes").update(update_data).eq("id", int(orden_id)).execute()
                                
                                # LIMPIAR CACHE Y FORZAR ACTUALIZACIÓN
                                st.cache_data.clear()
                                
                                # Mensaje personalizado
                                if nuevo_tecnico_id != tecnico_actual_id:
                                    agregar_notificacion('success', f'Orden OT-{orden_id} actualizada y reasignada a {nuevo_tecnico_option.split(" - ")[0]}.')
                                else:
                                    agregar_notificacion('success', f'Orden OT-{orden_id} actualizada correctamente.')
                                
                                # Forzar recarga completa de la página
                                st.rerun()
                                
                        except Exception as e:
                            agregar_notificacion('error', f'Error al actualizar la orden: {str(e)}')
                    
                    # PROCESAR ELIMINACIÓN
                    if cancelar_btn:
                        try:
                            # Confirmación adicional para eliminar
                            st.warning(f"⚠️ Está a punto de eliminar permanentemente la orden OT-{orden_id}")
                            confirmar = st.checkbox("Confirmar eliminación")
                            
                            if confirmar:
                                supabase.table("ordenes").delete().eq("id", int(orden_id)).execute()
                                
                                # LIMPIAR CACHE Y FORZAR ACTUALIZACIÓN
                                st.cache_data.clear()
                                
                                agregar_notificacion('delete', f'Orden OT-{orden_id} eliminada permanentemente.')
                                st.rerun()
                                
                        except Exception as e:
                            agregar_notificacion('error', f'Error al eliminar la orden: {str(e)}')
        
        else:
            st.info("No se encontraron órdenes con los filtros seleccionados.")
    
    else:
        st.info("📭 No hay órdenes de trabajo registradas en el sistema.")
elif choice == "Cerrar Orden":
    st.title("CERRAR ORDEN")
    mostrar_notificaciones()
    

        df_ot = run_query("ordenes")
        
    if not df_ot.empty:
        my_ots = df_ot[(df_ot['estado']!='Concluida')]
        if not my_ots.empty:
            st.markdown("<div class='card-style'>", unsafe_allow_html=True)
            st.dataframe(my_ots[['id','descripcion','criticidad']], use_container_width=True)
            sid = st.selectbox("ID Orden", my_ots['id'].values)
            with st.form("close"):
                rep = st.text_area("Reporte Técnico")
                img = st.file_uploader("Foto")
                if st.form_submit_button("FINALIZAR"):
                    url = subir_imagen(img)
                    supabase.table("ordenes").update({"estado":"Concluida", "comentarios_cierre":rep, "evidencia_url":url}).eq("id",sid).execute()
                    agregar_notificacion('success', 'Orden cerrada exitosamente.')
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else: 
            st.info("No hay órdenes pendientes para cerrar.")

elif choice == "Usuarios":
    st.title("USUARIOS")
    mostrar_notificaciones()

    tab_crear, tab_gestionar = st.tabs(["CREAR USUARIO", "GESTIONAR USUARIOS"])

    with tab_crear:
        st.subheader("Registrar Nuevo Usuario")

        with st.form("new_user_form"):
            c1, c2 = st.columns(2)
            documento = c1.text_input("Documento/ID", key="new_user_doc")
            nombre = c2.text_input("Nombre Completo", key="new_user_name")
            password = c1.text_input("Contraseña", type="password", key="new_user_pass")
            rol = c2.selectbox("Rol", ["Tecnico", "Programador", "Admin"], key="new_user_rol")

            submitted = st.form_submit_button("REGISTRAR USUARIO", type="primary")

            if submitted:
                if documento and nombre and password and rol:
                    if not validar_usuario_unico(documento):
                        agregar_notificacion('error', 'El documento ya existe en el sistema.')
                    elif len(password) < 4:
                        agregar_notificacion('error', 'La contraseña debe tener al menos 4 caracteres.')
                    else:
                        try:
                            res = supabase.table("usuarios").insert({
                                "documento": documento, 
                                "nombre": nombre, 
                                "password": password, 
                                "rol": rol
                            }).execute()

                            if res.data:
                                agregar_notificacion('success', f'Usuario {nombre} registrado con éxito.')
                                st.rerun()
                            else:
                                agregar_notificacion('error', 'Error al registrar el usuario en la base de datos.')
                        except Exception as e:
                            agregar_notificacion('error', f'Error de base de datos: {e}')
                else:
                    agregar_notificacion('warning', 'Por favor, complete todos los campos.')

    with tab_gestionar:

            df_users = run_query("usuarios")

        if not df_users.empty:
            st.subheader("Seleccionar Usuario para Gestionar")

            user_options = {f"{row['nombre']} (ID: {row['id']})": row['id'] 
                           for _, row in df_users.iterrows()}
            
            user_options_list = ["-- Seleccione un usuario --"] + list(user_options.keys())
            
            selected_option = st.selectbox(
                "Usuario:",
                user_options_list,
                key="user_selector"
            )

            st.markdown("### Lista Completa de Usuarios")
            st.dataframe(
                df_users[['id', 'documento', 'nombre', 'rol']],
                hide_index=True,
                use_container_width=True
            )

            if selected_option != "-- Seleccione un usuario --":
                user_id = user_options[selected_option]
                selected_user = df_users[df_users['id'] == user_id].iloc[0]

                st.markdown("---")
                st.markdown(f"### Editando: **{selected_user['nombre']}** (ID: {user_id})")

                with st.form(key=f"edit_user_form_{user_id}"):
                    st.subheader("Información del Usuario")

                    c1, c2 = st.columns(2)

                    edit_doc = c1.text_input(
                        "Documento/ID", 
                        value=selected_user['documento']
                    )
                    edit_name = c2.text_input(
                        "Nombre Completo", 
                        value=selected_user['nombre']
                    )

                    rol_options = ["Tecnico", "Programador", "Admin"]
                    current_rol_index = rol_options.index(selected_user['rol']) if selected_user['rol'] in rol_options else 0
                    new_rol = st.selectbox("Rol", rol_options, index=current_rol_index)

                    new_password = st.text_input(
                        "Nueva Contraseña (Dejar vacío para no cambiar)", 
                        type="password"
                    )

                    st.markdown("<br>", unsafe_allow_html=True)
                    update_submitted = st.form_submit_button("✅ ACTUALIZAR USUARIO", type="primary", use_container_width=True)

                    if update_submitted:
                        if new_rol != selected_user['rol']:
                            if check_open_orders(user_id):
                                agregar_notificacion('error', f'El usuario **{selected_user["nombre"]}** tiene Órdenes de Trabajo pendientes. Debe cerrarlas antes de cambiar su rol.')
                                st.stop()

                        if not validar_usuario_unico(edit_doc, user_id):
                            agregar_notificacion('error', 'El documento ya está en uso por otro usuario.')
                        else:
                            update_data = {
                                "documento": edit_doc,
                                "nombre": edit_name,
                                "rol": new_rol
                            }
                            if new_password:
                                if len(new_password) < 4:
                                    agregar_notificacion('error', 'La contraseña debe tener al menos 4 caracteres.')
                                else:
                                    update_data["password"] = new_password

                            try:
                                supabase.table("usuarios").update(update_data).eq("id", user_id).execute()
                                agregar_notificacion('success', f'Usuario {edit_name} actualizado.')
                                st.rerun()
                            except Exception as e:
                                agregar_notificacion('error', f'Error al actualizar: {e}')

                st.markdown("---")
                st.markdown("### 🗑️ Zona de Eliminación")
                
                has_open_orders = check_open_orders(user_id)
                
                if has_open_orders:
                    st.markdown(f"""
                        <div style='background: rgba(239, 68, 68, 0.15); 
                                    border: 2px solid #EF4444; 
                                    border-radius: 8px; 
                                    padding: 20px; 
                                    text-align: center;'>
                            <p style='color: #FCA5A5; margin: 0; font-size: 1.1rem;'>
                                ⚠️ <strong>ELIMINACIÓN BLOQUEADA</strong>
                            </p>
                            <p style='color: #FEE2E2; margin-top: 10px; font-size: 0.95rem;'>
                                El usuario <strong>{selected_user['nombre']}</strong> tiene Órdenes de Trabajo pendientes.<br>
                                Debe cerrarlas o reasignarlas antes de eliminar este usuario.
                            </p>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.warning(f"⚠️ Esta acción eliminará permanentemente al usuario **{selected_user['nombre']}**")
                    
                    if st.button(
                        "🗑️ ELIMINAR USUARIO PERMANENTEMENTE",
                        type="secondary",
                        use_container_width=True,
                        key=f"delete_btn_{user_id}"
                    ):
                        try:
                            supabase.table("usuarios").delete().eq("id", user_id).execute()
                            agregar_notificacion('delete', f'Usuario {selected_user["nombre"]} eliminado.')
                            st.rerun()
                        except Exception as e:
                            agregar_notificacion('error', f'Error al eliminar: {e}')

        else:
            st.info("No se encontraron usuarios en la base de datos. Use la pestaña 'CREAR USUARIO'.")
