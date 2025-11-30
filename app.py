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
    /* ELIMINADO: Nuevo estilo para el FORMULARIO DE LOGIN ahora que no está en un card-style grande */
    .login-container {{
        /* background: {BG_CARD}; */
        border-radius: 12px;
        padding: 30px;
        /* border: 1px solid rgba(245, 158, 11, 0.2); 
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); */
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
    
    /* Aseguramos que no haya padding extra en la columna central del login */
    div.stVerticalBlock > div:first-child > div:nth-child(2) > div:first-child {{
        padding-top: 0 !important;
    }}
    </style>
""", unsafe_allow_html=True)


# --- 2. CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_supabase():
    try:
        # 1. Intentamos leer las claves. Si fallan, se lanza KeyError.
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        
        # 2. Si las claves se leyeron, intentamos crear el cliente.
        return create_client(url, key) 
        
    except KeyError as e:
        # Captura específica si la clave no existe en secrets.toml
        st.error(f"❌ ERROR CRÍTICO: La clave {e} no se encuentra en la configuración de Streamlit Secrets (secrets.toml).")
        return None
    except Exception as e:
        # Captura de cualquier otro error (conexión, SSL, URL malformada, etc.)
        st.error(f"❌ Error desconocido al conectar a Supabase. Verifique URL y clave. Detalles: {e}")
        return None


supabase = init_supabase()
if not supabase:
    st.stop()

# --- 3. FUNCIONES AUXILIARES ---

def run_query(table_name):
    try:
        response = supabase.table(table_name).select("*").order("id").execute()
        return pd.DataFrame(response.data)
    except:
        return pd.DataFrame()

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
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0),
        height=250,
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
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        height=250,
        showlegend=False,
        margin=dict(l=0, r=0, t=10, b=10)
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
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0),
        height=250,
        xaxis=dict(showgrid=False),
        yaxis=dict(title=None)
    )
    fig.update_traces(textfont_size=14, textposition='inside')
    st.plotly_chart(fig, use_container_width=True)

# --- NOTIFICACIONES ---
def mostrar_notificaciones():
    if 'notification' in st.session_state:
        notif = st.session_state['notification']
        if notif:
            tipo = notif.get('type')
            msg = notif.get('message')
            if tipo == 'success':
                st.balloons()
                st.success(f"✅ {msg}")
            elif tipo == 'delete':
                st.error(f"🗑️ {msg}")
        del st.session_state['notification']


# --- FUNCIÓN DE VALIDACIÓN DE ÓRDENES ABIERTAS ---
def check_open_orders(user_id):
    """Verifica si el ID de usuario tiene órdenes de trabajo activas."""
    try:
        # Se asume que tecnico_asignado en 'ordenes' guarda el ID del usuario de la tabla 'usuarios'
        response = supabase.table("ordenes").select("id").eq("tecnico_asignado", user_id).neq("estado", "Concluida").execute()
        return len(response.data) > 0
    except Exception as e:
        # En caso de error de conexión o consulta, asumimos que no hay órdenes para no bloquear
        # st.error(f"Error al verificar órdenes: {e}") 
        return False
# --- FIN FUNCIÓN DE VALIDACIÓN ---


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
# 🚀 LOGIN (FINAL - ESPACIO OPTIMIZADO)
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
        
        # 1. ENCABEZADO Y TÍTULOS (Flotante)
        render_orion_svg(PRO_ORANGE)

        st.markdown(f"""
            <h1 style='text-align: center; font-size: 3.5rem; margin-bottom: -15px; text-shadow: 0 0 10px {PRO_ORANGE};'>ORIÓN</h1>
            <p style='text-align: center; color: #E5E7EB; font-size: 1.2rem; letter-spacing: 2px; margin-top: 5px; margin-bottom: 20px; font-weight: 300;'>
                PLATAFORMA INTEGRAL DE MANTENIMIENTO
            </p>
        """, unsafe_allow_html=True)
        
        # 2. CUADRO DE CORREO (Ubicado para ocupar el espacio)
        st.markdown(f"""
            <div class='card-style' style='padding: 10px; margin-top: 0px; margin-bottom: 30px; text-align: center; font-size: 0.85em; color: {PRO_ORANGE}; border: none; box-shadow: none; background: #1F2937;'>
                <p style='margin: 0;'>Desarrollado por: <b>Jhonestebanpenagos@gmail.com</b></p>
            </div>
            <hr style="border: none; height: 1px; background: linear-gradient(90deg, transparent, {PRO_ORANGE}, transparent); margin-bottom: 30px;">
        """, unsafe_allow_html=True)
        
        # 3. CONTENIDO DE LOGIN (Elementos Streamlit)
        
        st.markdown("<h3 style='text-align: center; margin-bottom: 20px;'>ACCESO DE USUARIOS</h3>", unsafe_allow_html=True)
        
        # FORMULARIO
        with st.form("login_form"):
            documento = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("ACCEDER AL SISTEMA", type="primary", use_container_width=True)
            if submitted:
                # 📢 INICIO DE LA CORRECCIÓN DEL ERROR DE RED (FALLO EN EL PRIMER INTENTO)
                
                # Paso 1: Mostrar un spinner y pausar la ejecución brevemente
                with st.spinner("Conectando y validando credenciales..."):
                    time.sleep(1) 
                
                # Paso 2: Intentar la consulta a Supabase
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
                    # El error de red ocurrirá aquí si el retardo no fue suficiente
                    st.error(f"Error de conexión. Intente nuevamente. Detalles: {e}")
                # 📢 FIN DE LA CORRECCIÓN DEL ERROR DE RED

    st.stop()

# ==============================================================================
# 🚀 DASHBOARD PRIVADO
# ==============================================================================

rol = st.session_state['rol']
usuario = st.session_state['usuario']

with st.sidebar:
    # 🎨 SECCIÓN DE BIENVENIDA MÁS ESTILIZADA Y FLOTANTE
    st.markdown(f"""
        <div style="text-align: center; margin-bottom: 25px; margin-top: 10px;">
            <p style="margin:0; font-size: 1.2rem; color: white; font-weight: 600; letter-spacing: 0.5px;">👋 Hola, {usuario}!</p>
            <span style="color: {PRO_GREEN}; font-size: 0.85rem; font-weight: bold; letter-spacing: 1px;">{rol.upper()}</span>
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("Cerrar Sesión", use_container_width=True): logout()
    st.write("") 

    opts = []
    if rol == "Admin": opts = ["Tablero de Mando", "Inventario Activos", "Crear Orden", "Cerrar Orden", "Usuarios"]
    elif rol == "Programador": opts = ["Tablero de Mando", "Crear Orden", "Usuarios"] 
    elif rol == "Tecnico": opts = ["Cerrar Orden"] 
    
    choice = option_menu(menu_title="NAVEGACIÓN", options=opts, 
        icons=["speedometer2", "box-seam", "plus-circle", "check2-circle", "people"], default_index=0,
        styles={"container": {"background-color": "transparent"}, "icon": {"color": PRO_ORANGE}, "nav-link": {"color": "#9CA3AF"}, "nav-link-selected": {"background-color": "#1F2937", "color": "white", "border-left": f"4px solid {PRO_ORANGE}"}})

# --- PANTALLAS ---

if choice == "Tablero de Mando":
    st.title("TABLERO DE MANDO")
    mostrar_notificaciones()
    
    df = run_query("ordenes")
    if not df.empty:
        # MÉTRICAS
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Órdenes", len(df))
        c2.metric("Pendientes", len(df[df['estado']=='Abierta']))
        c3.metric("Finalizadas", len(df[df['estado']=='Concluida']))
        
        st.write("") 

        # --- GRÁFICOS ---
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

    else: st.info("No hay datos para mostrar.")

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
                res = supabase.table("activos").insert({"nombre":nom, "area":area, "ubicacion":ubic, "categoria":cat}).execute()
                if res.data:
                    nid = res.data[0]['id']
                    url = generar_qr_activo(nid, nom)
                    supabase.table("activos").update({"qr_url":url}).eq("id", nid).execute()
                    st.session_state['notification'] = {'type':'success', 'message':'Activo creado.'}
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        if not df_act.empty:
            sel = st.selectbox("Buscar Activo", df_act['nombre'].values)
            dat = df_act[df_act['nombre']==sel].iloc[0]
            st.markdown("<div class='card-style'>", unsafe_allow_html=True)
            c1, c2 = st.columns([1,3])
            c1.image(dat['qr_url'])
            c2.info(f"ID: {dat['id']} | {dat['area']}")
            
            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander("Eliminar Activo"):
                st.markdown(f"<div class='danger-zone'><p>Esto borrará el historial completo.</p></div>", unsafe_allow_html=True)
                if st.button("ELIMINAR DEFINITIVAMENTE"):
                    supabase.table("ordenes").delete().eq("activo_id", dat['id']).execute()
                    supabase.table("activos").delete().eq("id", dat['id']).execute()
                    st.session_state['notification'] = {'type':'delete', 'message':'Eliminado.'}
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

elif choice == "Crear Orden":
    st.title("GENERAR ORDEN")
    mostrar_notificaciones()
    df_act = run_query("activos")
    if not df_act.empty:
        act_dict = dict(zip(df_act['nombre'], df_act['id']))
        st.markdown("<div class='card-style'>", unsafe_allow_html=True)
        sel = st.selectbox("Equipo", list(act_dict.keys()))
        c1, c2 = st.columns(2)
        tipo = c1.selectbox("Tipo", ["Correctivo", "Preventivo"])
        crit = c2.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"])
        desc = st.text_area("Descripción")
        tec = st.text_input("Asignar a (Opcional)")
        if st.button("CREAR ORDEN", type="primary"):
            supabase.table("ordenes").insert({"activo_id":act_dict[sel], "descripcion":desc, "criticidad":crit, "tipo_mantenimiento":tipo, "estado":"Abierta", "tecnico_asignado":tec, "fecha_creacion": datetime.now().isoformat()}).execute()
            st.session_state['notification'] = {'type':'success', 'message':'Orden creada.'}
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

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
                    st.session_state['notification'] = {'type':'success', 'message':'Orden cerrada.'}
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else: st.info("No hay pendientes.")

elif choice == "Usuarios":
    st.title("USUARIOS")
    mostrar_notificaciones()
    
    # Estructura de pestañas para Crear y Gestionar usuarios
    tab_crear, tab_gestionar = st.tabs(["CREAR USUARIO", "GESTIONAR USUARIOS"])
    
    # Inicializamos la variable de sesión para el último ID seleccionado
    if 'last_selected_user_id' not in st.session_state:
        st.session_state['last_selected_user_id'] = None

    # ----------------------------------------------------
    # TAB 1: CREAR USUARIO (Sin card-style)
    # ----------------------------------------------------
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
                    try:
                        # Insertar el nuevo usuario en la tabla 'usuarios'
                        res = supabase.table("usuarios").insert({
                            "documento": documento, 
                            "nombre": nombre, 
                            "password": password, 
                            "rol": rol
                        }).execute()
                        
                        if res.data:
                            st.session_state['notification'] = {'type':'success', 'message':f'Usuario {nombre} registrado con éxito.'}
                            st.rerun()
                        else:
                            st.error("Error al registrar el usuario en la base de datos.")
                            
                    except Exception as e:
                        st.error(f"Error de base de datos: Asegúrese de que el Documento no exista ya. Detalles: {e}")
                else:
                    st.warning("Por favor, complete todos los campos.")

    # ----------------------------------------------------
    # TAB 2: GESTIONAR USUARIOS (Con Edición/Eliminación usando data_editor)
    # ----------------------------------------------------
    with tab_gestionar:
        df_users = run_query("usuarios")
        
        if not df_users.empty:
            
            st.subheader("Lista de Usuarios (Marque una casilla para gestionar)")
            
            # --- PREPARACIÓN PARA LA SELECCIÓN ÚNICA ---
            # 1. Creamos la columna de selección si no existe
            if 'select' not in df_users.columns:
                df_users['select'] = False
            
            # 2. Si hay un ID seleccionado previamente, marcamos su casilla
            if st.session_state['last_selected_user_id'] is not None:
                # Nos aseguramos de que solo la fila del ID previamente seleccionado esté marcada al cargar
                df_users['select'] = (df_users['id'] == st.session_state['last_selected_user_id'])
            
            # 3. Configuramos y mostramos el data_editor (la columna 'select' actúa como nuestro checkbox)
            edited_df = st.data_editor(
                df_users[['select', 'id', 'documento', 'nombre', 'rol']],
                column_config={
                    "select": st.column_config.CheckboxColumn(
                        "Seleccionar",
                        help="Marque para editar/eliminar este usuario.",
                        default=False
                    ),
                    "id": st.column_config.Column("ID", disabled=True),
                    "documento": st.column_config.Column("Documento", disabled=True),
                    "nombre": st.column_config.Column("Nombre", disabled=True),
                    "rol": st.column_config.Column("Rol", disabled=True),
                },
                hide_index=True,
                use_container_width=True,
                key="user_data_editor"
            )

            # 4. Identificamos el usuario seleccionado en el data_editor
            selected_user_row = edited_df[edited_df['select'] == True]
            
            if len(selected_user_row) == 1:
                # --- NUEVA SELECCIÓN VÁLIDA ---
                selected_user = selected_user_row.iloc[0]
                user_id = selected_user['id']
                
                # Actualizamos la variable de sesión para mantener la selección en la próxima recarga
                st.session_state['last_selected_user_id'] = user_id
                
                st.markdown("---")
                st.markdown(f"**Usuario seleccionado:** **{selected_user['nombre']}** (ID: {user_id})")
                
                
                # Formulario de Edición
                with st.form(key="edit_user_form", clear_on_submit=False):
                    st.subheader("Editar Información")
                    
                    c1, c2 = st.columns(2)
                    
                    # Pre-cargamos los valores del usuario seleccionado
                    edit_doc = c1.text_input("Documento/ID", value=selected_user['documento'], key="edit_user_doc")
                    edit_name = c2.text_input("Nombre Completo", value=selected_user['nombre'], key="edit_user_name")
                    
                    # Manejo de índice para el Selectbox
                    rol_options = ["Tecnico", "Programador", "Admin"]
                    current_rol_index = rol_options.index(selected_user['rol']) if selected_user['rol'] in rol_options else 0
                    new_rol = st.selectbox("Rol", rol_options, index=current_rol_index, key="edit_user_rol")
                    
                    new_password = st.text_input("Nueva Contraseña (Dejar vacío para no cambiar)", type="password", key="edit_user_pass")
                    
                    col_edit, col_delete_btn = st.columns([1, 1])
                    
                    update_submitted = col_edit.form_submit_button("ACTUALIZAR USUARIO", type="primary")
                    
                    if update_submitted:
                        
                        # Validación del cambio de rol si el rol es diferente
                        if new_rol != selected_user['rol']:
                            if check_open_orders(user_id):
                                st.error(f"❌ ERROR: El usuario **{selected_user['nombre']}** tiene Órdenes de Trabajo pendientes. Debe cerrarlas antes de cambiar su rol.")
                                st.stop()
                        
                        update_data = {
                            "documento": edit_doc,
                            "nombre": edit_name,
                            "rol": new_rol
                        }
                        if new_password:
                            update_data["password"] = new_password
                            
                        try:
                            supabase.table("usuarios").update(update_data).eq("id", user_id).execute()
                            st.session_state['notification'] = {'type':'success', 'message':f'Usuario {edit_name} actualizado.'}
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar: {e}")
                
                # Botón de Eliminación 
                if st.button("🔴 ELIMINAR USUARIO SELECCIONADO", type="secondary", use_container_width=True, help="Borrar el usuario seleccionado"):
                    
                    # Validación de eliminación
                    if check_open_orders(user_id):
                        st.error(f"❌ ERROR: El usuario **{selected_user['nombre']}** tiene Órdenes de Trabajo pendientes. No puede ser eliminado.")
                    else:
                        try:
                            supabase.table("usuarios").delete().eq("id", user_id).execute()
                            # Limpiar la selección después de la eliminación
                            st.session_state['last_selected_user_id'] = None 
                            st.session_state['notification'] = {'type':'delete', 'message':f'Usuario {selected_user["nombre"]} eliminado.'}
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al eliminar: {e}")
                            
            elif len(selected_user_row) > 1:
                st.warning("⚠️ Seleccione solo un usuario a la vez para gestionar su información.")

            else:
                # Si el data_editor se actualiza y no hay nada seleccionado, borramos la variable de sesión
                if st.session_state['last_selected_user_id'] is not None:
                    st.session_state['last_selected_user_id'] = None
                    st.rerun() # Forzamos recarga para limpiar la interfaz si se desmarcó

                st.info("Haga clic en la columna 'Seleccionar' para elegir un usuario y gestionar sus datos.")
            
        else:
            st.info("No se encontraron usuarios en la base de datos. Use la pestaña 'CREAR USUARIO'.")
