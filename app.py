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
# 🎨 TEMA: "ORIÓ BIONIC" (Alto Contraste y Legibilidad)
# ==============================================================================

COLOR_ACCION = "#FF9F1C" # Naranja Intenso (Orión)
COLOR_SECUNDARIO = "#2EC4B6"  # Turquesa/Verde Tecnológico
COLOR_FONDO_OSCURO = "#0B0E14" # Negro Azulado Profundo
COLOR_TEXTO_BLANCO = "#FFFFFF" # Blanco Puro para máximo contraste

st.markdown(f"""
    <style>
    /* 1. FONDO GLOBAL */
    .stApp {{
        background: radial-gradient(circle at 50% 0%, #1B2336, {COLOR_FONDO_OSCURO});
        color: {COLOR_TEXTO_BLANCO};
    }}

    /* 2. BARRA LATERAL (Alto Contraste) */
    [data-testid="stSidebar"] {{
        background-color: #050608;
        border-right: 1px solid #333;
    }}
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {{
        color: #E0E0E0 !important; /* Texto gris muy claro */
    }}

    /* 3. TÍTULOS (Estilo Orión) */
    h1, h2, h3 {{
        color: {COLOR_TEXTO_BLANCO} !important;
        font-family: 'Helvetica', sans-serif;
        font-weight: 800 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    
    /* 4. TARJETAS (Mejora de Contraste) */
    .card-style {{
        background: rgba(22, 27, 34, 0.95); /* Fondo casi opaco para leer mejor */
        border-radius: 12px;
        padding: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        margin-bottom: 20px;
    }}

    /* 5. TÍTULOS DE LAS GRÁFICAS (Nuevo Estilo) */
    .chart-title {{
        font-size: 1.2rem;
        font-weight: bold;
        margin-bottom: 10px;
        border-bottom: 2px solid {COLOR_ACCION};
        padding-bottom: 5px;
        display: inline-block;
        color: {COLOR_TEXTO_BLANCO};
    }}

    /* 6. MENÚS DESPLEGABLES (Corrección de Texto Invisible) */
    .stSelectbox > div > div {{
        background-color: #161B22 !important;
        color: white !important;
        border: 1px solid #444 !important;
    }}
    div[data-baseweb="popover"], div[data-baseweb="menu"] {{
        background-color: #0D1117 !important;
    }}
    div[data-baseweb="menu"] li {{
        color: white !important; /* Texto de opciones blanco */
    }}
    div[data-baseweb="menu"] li:hover {{
        background-color: {COLOR_ACCION} !important;
        color: black !important;
    }}
    
    /* 7. INPUTS */
    .stTextInput input, .stTextArea textarea {{
        background-color: #0D1117 !important;
        color: white !important;
        border: 1px solid #333 !important;
        border-radius: 6px;
    }}
    
    /* 8. BOTONES */
    div.stButton > button:first-child {{
        background: linear-gradient(90deg, {COLOR_ACCION}, #FF6B35) !important;
        color: white !important;
        border: none;
        font-weight: bold;
        border-radius: 6px;
        padding: 0.5rem 1rem;
    }}

    /* 9. MÉTRICAS */
    [data-testid="stMetric"] {{
        background: #161B22;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid {COLOR_SECUNDARIO};
        box-shadow: 0 2px 5px rgba(0,0,0,0.3);
    }}
    [data-testid="stMetricLabel"] {{ color: #A0A0A0 !important; font-size: 0.9rem; }}
    [data-testid="stMetricValue"] {{ color: white !important; font-size: 1.8rem; }}
    
    </style>
""", unsafe_allow_html=True)


# --- 2. CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except:
        return None

supabase = init_supabase()
if not supabase:
    st.error("Error conectando a Supabase.")
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
        except:
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

# --- GRÁFICOS (SIN TÍTULOS INTERNOS, SOLO DATOS) ---

def graficar_criticidad(df):
    if df.empty: return
    conteo = df['criticidad'].value_counts().reset_index()
    conteo.columns = ['Nivel', 'Cantidad']
    orden = ["Baja", "Media", "Alta", "Crítica"]
    conteo['Nivel'] = pd.Categorical(conteo['Nivel'], categories=orden, ordered=True)
    conteo = conteo.sort_values('Nivel')

    # Colores Semánticos (Verde -> Rojo)
    colores = {"Baja": "#2EC4B6", "Media": "#FF9F1C", "Alta": "#E71D36", "Crítica": "#880000"}

    fig = px.bar(conteo, x='Nivel', y='Cantidad', color='Nivel', 
                 color_discrete_map=colores, text='Cantidad')
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0), # Márgenes mínimos
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
    colores = ["#FF9F1C", "#2EC4B6", "#7209B7"] 

    fig = go.Figure(data=[go.Pie(
        labels=conteo['Tipo'], values=conteo['Cantidad'], hole=.6, 
        marker=dict(colors=colores), textinfo='label+percent',
        textfont=dict(color='white')
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
    colores = {"Abierta": "#3A86FF", "Concluida": "#2EC4B6"}

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

# ==============================================================================
# 🚀 INTERCEPTOR PÚBLICO
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
                <span class="chart-title">Ficha Técnica</span>
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
# 🚀 LOGIN / SCANNER
# ==============================================================================

if 'usuario' not in st.session_state: st.session_state['usuario'] = None
if 'rol' not in st.session_state: st.session_state['rol'] = None

def logout():
    st.session_state['usuario'] = None
    st.session_state['rol'] = None
    st.query_params.clear()
    st.rerun()

if st.session_state['usuario'] is None:
    st.markdown("<h1 style='text-align: center; font-size: 3.5rem;'>ORIÓN</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #aaa;'>SISTEMA DE MANTENIMIENTO INTELIGENTE</p>", unsafe_allow_html=True)
    
    st.markdown(f"""<style>.stTabs [aria-selected="true"] {{ color: {COLOR_ACCION} !important; border-bottom: 2px solid {COLOR_ACCION}; }}</style>""", unsafe_allow_html=True)
    
    tab_login, tab_scan = st.tabs(["🔐 INGRESAR", "📷 ESCANEAR QR"])
    
    with tab_login:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            st.markdown("<div class='card-style'>", unsafe_allow_html=True)
            with st.form("login_form"):
                documento = st.text_input("Usuario")
                password = st.text_input("Contraseña", type="password")
                submitted = st.form_submit_button("ACCEDER", type="primary", use_container_width=True)
                if submitted:
                    try:
                        response = supabase.table("usuarios").select("*").eq("documento", documento).eq("password", password).execute()
                        if response.data:
                            user = response.data[0]
                            st.session_state['usuario'] = user['nombre']
                            st.session_state['rol'] = user['rol']
                            st.rerun()
                        else: st.error("Acceso denegado.")
                    except: st.error("Error de red.")
            st.markdown("</div>", unsafe_allow_html=True)

    with tab_scan:
        st.markdown("<div class='card-style' style='text-align:center;'>", unsafe_allow_html=True)
        img_file = st.camera_input("Escanear", label_visibility="collapsed")
        if img_file:
            id_det = leer_qr_imagen(img_file)
            if id_det:
                st.query_params["id_activo_qr"] = id_det
                st.rerun()
            else: st.warning("QR no válido.")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ==============================================================================
# 🚀 DASHBOARD PRIVADO
# ==============================================================================

rol = st.session_state['rol']
usuario = st.session_state['usuario']

with st.sidebar:
    st.markdown(f"""
        <div style="background: #161B22; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px; border: 1px solid #333;">
            <div style="width: 50px; height: 50px; background: {COLOR_ACCION}; border-radius: 50%; margin: 0 auto 10px auto; display: flex; align-items: center; justify-content: center; font-weight:bold; color:black; font-size: 20px;">{usuario[0]}</div>
            <h3 style="margin:5px 0; font-size: 16px; color: white !important;">{usuario}</h3>
            <span style="color: {COLOR_SECUNDARIO}; font-size: 12px; font-weight: bold; letter-spacing: 1px;">{rol.upper()}</span>
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
        styles={"container": {"background-color": "transparent"}, "icon": {"color": COLOR_ACCION}, "nav-link": {"color": "#bbb"}, "nav-link-selected": {"background-color": "#21262D", "color": "white", "border-left": f"4px solid {COLOR_ACCION}"}})

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
        
        st.write("") # Espacio

        # --- GRÁFICOS CON TÍTULOS EXTERNOS ---
        c_left, c_mid, c_right = st.columns(3)
        
        with c_left:
            st.markdown(f"""
                <div class='card-style'>
                    <span class='chart-title' style='border-color: #3A86FF;'>Progreso de Órdenes</span>
            """, unsafe_allow_html=True)
            graficar_estado_barras(df)
            st.markdown("</div>", unsafe_allow_html=True)

        with c_mid:
            st.markdown(f"""
                <div class='card-style'>
                    <span class='chart-title' style='border-color: #E71D36;'>Gravedad de las Fallas</span>
            """, unsafe_allow_html=True)
            graficar_criticidad(df)
            st.markdown("</div>", unsafe_allow_html=True)

        with c_right:
            st.markdown(f"""
                <div class='card-style'>
                    <span class='chart-title' style='border-color: #7209B7;'>Tipos de Mantenimiento</span>
            """, unsafe_allow_html=True)
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
            if c2.button("ELIMINAR ACTIVO"):
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
            st.dataframe(my_ots[['id','descripcion','criticidad']])
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
